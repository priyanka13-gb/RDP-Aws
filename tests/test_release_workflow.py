"""Offline manual release guards, digest handling and least-privilege policy tests."""

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("release_image", SCRIPTS / "release_image.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
IAM_SPEC = importlib.util.spec_from_file_location("release_iam", SCRIPTS / "render_release_iam.py")
iam = importlib.util.module_from_spec(IAM_SPEC)
IAM_SPEC.loader.exec_module(iam)
sys.path.pop(0)


@pytest.mark.parametrize("changes", [
    {}, {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push"},
    {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
     "GITHUB_REF": "refs/heads/untrusted", "GITHUB_REPOSITORY": release.GITHUB_REPOSITORY},
])
def test_only_manual_main_can_release(monkeypatch, changes):
    for key in ["GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_REPOSITORY"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in changes.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(release, "run", lambda *_: "a" * 40)
    with pytest.raises(RuntimeError):
        release.source_revision()


def test_disabled_publish_fails_before_aws(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "WORK", tmp_path)
    (tmp_path / "build.json").write_text('{}')
    monkeypatch.setattr(release, "source_revision", lambda: "a" * 40)
    monkeypatch.delenv("RELEASE_PUBLISH_APPROVED", raising=False)
    aws = Mock(side_effect=AssertionError("AWS must not be called"))
    monkeypatch.setattr(release, "aws", aws)
    with pytest.raises(RuntimeError, match="disabled"):
        release.publish()
    aws.assert_not_called()


def test_local_validation_cannot_be_promoted(monkeypatch):
    monkeypatch.setattr(release, "source_revision", lambda: "a" * 40)
    monkeypatch.setenv("RELEASE_PUBLISH_APPROVED", "true")
    monkeypatch.setenv("RELEASE_GATE_SUCCESS", "true")
    with pytest.raises(RuntimeError, match="Unapproved"):
        release.publish_guard({"revision": "a" * 40, "local_validation_only": True})


def test_failed_tests_gate_cannot_publish(monkeypatch):
    monkeypatch.setattr(release, "source_revision", lambda: "a" * 40)
    monkeypatch.setenv("RELEASE_PUBLISH_APPROVED", "true")
    monkeypatch.setenv("RELEASE_GATE_SUCCESS", "false")
    with pytest.raises(RuntimeError, match="disabled"):
        release.publish_guard({})


def test_tag_collision_refused_before_docker_login(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "WORK", tmp_path)
    (tmp_path / "build.json").write_text(json.dumps({"tag": "git-aaaaaaaaaaaa"}))
    monkeypatch.setattr(release, "publish_guard", lambda _: None)
    monkeypatch.setenv("EXPECTED_AWS_ACCOUNT_ID", "123456789012")

    def aws(operation, *args, **kwargs):
        if operation == "describe-repositories":
            return {"repositories": [{"registryId": "123456789012",
                    "repositoryUri": "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/"
                                     + release.REPOSITORY, "imageTagMutability": "IMMUTABLE",
                    "imageScanningConfiguration": {"scanOnPush": True}}]}
        return {"imageDetails": [{"imageDigest": "existing"}]}

    monkeypatch.setattr(release, "aws", aws)
    docker = Mock(side_effect=AssertionError("Docker login/push must not run"))
    monkeypatch.setattr(release, "run", docker)
    with pytest.raises(RuntimeError, match="already exists"):
        release.publish()
    docker.assert_not_called()


@pytest.mark.parametrize("indexed", [False, True])
def test_remote_single_and_index_bind_config(monkeypatch, indexed):
    root, child, config = "root", "child", "config"
    image = {"config": {"digest": config}}
    index = {"manifests": [{"digest": child, "platform": {"os": "linux",
                                                           "architecture": "amd64"}}]}
    monkeypatch.setattr(release, "remote_manifest", lambda d: index if indexed and d == root
                        else image)
    assert release.verify_remote(root, config) == (child if indexed else root)
    with pytest.raises(RuntimeError, match="differs"):
        release.verify_remote(root, "different-config")


def test_ambiguous_index_is_not_verified(monkeypatch):
    entry = {"digest": "child", "platform": {"os": "linux", "architecture": "amd64"}}
    monkeypatch.setattr(release, "remote_manifest", lambda _: {"manifests": [entry, entry]})
    with pytest.raises(RuntimeError, match="exactly one"):
        release.verify_remote("root", "config")


@pytest.mark.parametrize("oci", [False, True])
def test_archive_formats_have_same_config_digest(tmp_path, oci):
    config = json.dumps({"architecture": "amd64", "os": "linux",
                         "config": {"User": "10001:10001"}}).encode()
    expected = "sha256:" + hashlib.sha256(config).hexdigest()
    files = {}
    if oci:
        manifest = json.dumps({"config": {"digest": expected}}).encode()
        digest = "sha256:" + hashlib.sha256(manifest).hexdigest()
        files["index.json"] = json.dumps({"manifests": [{"digest": digest}]}).encode()
        files["blobs/sha256/" + digest.split(":")[1]] = manifest
        files["blobs/sha256/" + expected.split(":")[1]] = config
    else:
        files["manifest.json"] = json.dumps([{"Config": "config.json"}]).encode()
        files["config.json"] = config
    path = tmp_path / "image.tar"
    with tarfile.open(path, "w") as tar:
        for name, body in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(body)
            tar.addfile(entry, io.BytesIO(body))
    assert release.config_digest(path) == expected


def test_iam_only_one_repository_and_no_infrastructure_permissions():
    subject = "repo:priyanka13-gb/RDP-Aws:environment:ecr-release"
    trust, permissions = iam.policies("123456789012", subject)
    conditions = trust["Statement"][0]["Condition"]["StringEquals"]
    assert conditions["token.actions.githubusercontent.com:sub"] == subject
    assert conditions["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    for statement in permissions["Statement"]:
        assert all(action.startswith("ecr:") for action in statement["Action"])
        assert statement["Condition"]["StringEquals"]["aws:RequestedRegion"] == "ap-southeast-2"
        if statement["Resource"] == "*":
            assert statement["Action"] == ["ecr:GetAuthorizationToken"]
        else:
            assert statement["Resource"].endswith(":repository/" + release.REPOSITORY)
            assert not any(action.endswith(("DeleteImage", "CreateRepository", "DeleteRepository"))
                           for action in statement["Action"])


@pytest.mark.parametrize("subject", ["repo:evil/RDP-Aws:environment:ecr-release", "*",
                                     "repo:priyanka13-gb/RDP-Aws:ref:refs/heads/main"])
def test_no_wildcard_or_wrong_environment_subject(subject):
    with pytest.raises(ValueError):
        iam.policies("123456789012", subject)


def test_immutable_repository_id_subject_supported():
    subject = "repo:priyanka13-gb@123/RDP-Aws@456:environment:ecr-release"
    trust, _ = iam.policies("123456789012", subject)
    assert trust["Statement"][0]["Condition"]["StringEquals"][
        "token.actions.githubusercontent.com:sub"] == subject


@pytest.mark.parametrize("scan_status,counts,passes", [
    ("COMPLETE", {}, True), ("COMPLETE", {"HIGH": 1}, False), ("FAILED", {}, False),
])
def test_published_evidence_never_claims_a_failed_scan_passed(
        monkeypatch, tmp_path, scan_status, counts, passes):
    monkeypatch.setattr(release, "WORK", tmp_path)
    record = {"tag": "git-aaaaaaaaaaaa", "revision": "a" * 40, "image": "local:image",
              "config_digest": "config"}
    (tmp_path / "build.json").write_text(json.dumps(record))
    monkeypatch.setattr(release, "publish_guard", lambda _: None)
    monkeypatch.setenv("EXPECTED_AWS_ACCOUNT_ID", "123456789012")
    root, child = "sha256:" + "a" * 64, "sha256:" + "b" * 64
    described = []

    def aws(operation, *args, **kwargs):
        if operation == "describe-repositories":
            return {"repositories": [{"registryId": "123456789012",
                    "repositoryUri": "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/"
                                     + release.REPOSITORY, "imageTagMutability": "IMMUTABLE",
                    "imageScanningConfiguration": {"scanOnPush": True}}]}
        if operation == "describe-images":
            described.append(True)
            return None if len(described) == 1 else {"imageDetails": [{"imageDigest": root}]}
        assert operation == "describe-image-scan-findings"
        return {"imageScanStatus": {"status": scan_status},
                "imageScanFindings": {"findingSeverityCounts": counts}}

    def command(args, **kwargs):
        return "digest: " + root if args[:2] == ["docker", "push"] else ""

    monkeypatch.setattr(release, "aws", aws)
    monkeypatch.setattr(release, "run", command)
    monkeypatch.setattr(release, "verify_remote", lambda *_: child)
    monkeypatch.setattr(release.subprocess, "run", lambda *a, **k: None)
    if passes:
        release.publish()
    else:
        with pytest.raises(RuntimeError):
            release.publish()
    result = json.loads((tmp_path / "release.json").read_text())
    assert result["root_digest"] == root and result["amd64_digest"] == child
    if scan_status == "COMPLETE":
        assert result["ecr_high_critical_gate_passed"] == passes
    else:
        assert result["status"] == "published; ECR scan failed"
