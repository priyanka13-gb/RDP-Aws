"""Manual ECR release helpers. No AWS write is reachable without all release guards."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from ci_reports import scan_summary

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".tools" / "release"
REPOSITORY = "aws-resilient-delivery-platform-dev"
GITHUB_REPOSITORY = "priyanka13-gb/RDP-Aws"
REGION = "ap-southeast-2"
DOCKERFILE_SHA = "d36a843ff3521dcc38ea0cadcb4e25370fadb81322e53dcb1f8acbd07ce3cb0a"
PYPROJECT_SHA = "be0ce7810ab574007b6d33293ed6b3f2341b57a8e8890300c561e7eeab7d0450"
TRIVY = "aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def run(args, *, env=None, input_text=None):
    result = subprocess.run(args, cwd=ROOT, env=env, input=input_text,
                            capture_output=True, text=True, timeout=600)
    # Never propagate CalledProcessError, raw AWS/Docker messages, credentials or registry IDs.
    require(result.returncode == 0,
            f"{args[0]} operation failed; output withheld. Stop for review.")
    return result.stdout


def save(name, data):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def source_revision(local=False):
    revision = run(["git", "rev-parse", "HEAD"]).strip()
    require(re.fullmatch(r"[a-f0-9]{40}", revision), "Invalid source revision.")
    if not local:
        require(os.getenv("GITHUB_ACTIONS") == "true" and
                os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch" and
                os.getenv("GITHUB_REPOSITORY") == GITHUB_REPOSITORY and
                os.getenv("GITHUB_REF") == "refs/heads/main", "Manual main-branch release only.")
        require(os.getenv("GITHUB_SHA") == revision, "Checkout does not match dispatched SHA.")
        require(not run(["git", "status", "--porcelain"]).strip(), "Dirty release source.")
    for name, expected in [("app/Dockerfile", DOCKERFILE_SHA), ("pyproject.toml", PYPROJECT_SHA)]:
        digest = hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        require(digest == expected, "Build recipe changed; explicit recipe review required.")
    return revision


def config_digest(archive):
    """Support Docker-classic and OCI archives; bind remote config to the scanned image."""
    with tarfile.open(archive) as tar:
        names = set(tar.getnames())
        if "index.json" not in names:
            manifest = json.load(tar.extractfile("manifest.json"))
            require(len(manifest) == 1, "Ambiguous Docker archive.")
            data = tar.extractfile(manifest[0]["Config"]).read()
        else:
            def find(index):
                candidates = []
                for item in index["manifests"]:
                    blob = tar.extractfile("blobs/sha256/" + item["digest"].split(":")[1]).read()
                    require("sha256:" + hashlib.sha256(blob).hexdigest() == item["digest"],
                            "Archive manifest checksum mismatch.")
                    body = json.loads(blob)
                    if "manifests" in body:
                        candidates.extend(find(body))
                    elif "config" in body:
                        digest = body["config"]["digest"]
                        raw_config = tar.extractfile("blobs/sha256/" + digest.split(":")[1]).read()
                        require("sha256:" + hashlib.sha256(raw_config).hexdigest() == digest,
                                "Archive config checksum mismatch.")
                        parsed = json.loads(raw_config)
                        if parsed.get("architecture") == "amd64" and parsed.get("os") == "linux":
                            candidates.append(digest)
                return candidates
            candidates = find(json.load(tar.extractfile("index.json")))
            require(len(candidates) == 1, "Expected exactly one AMD64 image.")
            data = tar.extractfile("blobs/sha256/" + candidates[0].split(":")[1]).read()
        config = json.loads(data)
        require(config["architecture"] == "amd64" and config["os"] == "linux",
                "Archive architecture mismatch.")
        require(config["config"]["User"] == "10001:10001", "Archive user mismatch.")
        return "sha256:" + hashlib.sha256(data).hexdigest()


def smoke(image, tag, revision):
    container = run(["docker", "run", "-d", "--network", "none", "--memory", "512m",
                     "--cpus", "0.25", "-e", "DATABASE_URL=", "-e", "DATABASE_PASSWORD_FILE=",
                     "-e", "APP_VERSION=" + tag, "-e", "GIT_SHA=" + revision, image]).strip()
    try:
        code = ("import urllib.request,json; result={};\n"
                "for p in ['/health','/ready','/version','/metrics']:\n"
                " with urllib.request.urlopen('http://127.0.0.1:8000'+p,timeout=3) as r: "
                "result[p]={'status':r.status,'body':r.read().decode()}\n"
                "print(json.dumps(result))")
        for _ in range(30):
            try:
                data = json.loads(run(["docker", "exec", container, "python", "-c", code]))
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise RuntimeError("Container startup/HTTP verification failed.")
        require(all(row["status"] == 200 for row in data.values()), "HTTP smoke test failed.")
        require(json.loads(data["/health"]["body"]) == {"status": "healthy"} and
                json.loads(data["/ready"]["body"]) == {"status": "ready"}, "Readiness mismatch.")
        require(json.loads(data["/version"]["body"]) == {"app_version": tag, "git_sha": revision},
                "Version mismatch.")
        require("http_requests_total" in data["/metrics"]["body"], "Metrics missing.")
    finally:
        run(["docker", "stop", "--time", "15", container])
        run(["docker", "rm", container])


def build(local=False):
    revision = source_revision(local)
    tag = "git-" + revision[:12]
    image = "rdp-release:" + tag
    WORK.mkdir(parents=True, exist_ok=True)
    # Explicit Docker exporter supports GitHub's classic image store. No registry export/push.
    run(["docker", "buildx", "build", "--load", "--platform", "linux/amd64",
         "--provenance=false", "--label", "org.opencontainers.image.revision=" + revision,
         "--metadata-file", str(WORK / "build-private.json"), "-f", "app/Dockerfile",
         "-t", image, "."])
    archive = WORK / "image.tar"
    run(["docker", "save", "-o", str(archive), image])
    digest = config_digest(archive)
    run(["docker", "run", "--rm", "-v", str(WORK.resolve()) + ":/work", TRIVY,
         "image", "--input", "/work/image.tar", "--scanners", "vuln", "--list-all-pkgs",
         "--format", "json", "--output", "/work/trivy-private.json", "--exit-code", "0"])
    report = scan_summary(WORK / "trivy-private.json")
    save("scan.json", report)
    require(report["high_critical_gate_passed"], "HIGH/CRITICAL findings remain; no publish.")
    smoke(image, tag, revision)
    record = {"revision": revision, "tag": tag, "image": image, "config_digest": digest,
              "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "local_validation_only": local, "scan_passed": True, "runtime_passed": True,
              "recipe_sha256": DOCKERFILE_SHA, "platform": "linux/amd64", "uid": 10001}
    save("build.json", record)
    print("Build, scan and runtime gate passed:", tag, "linux/amd64 UID10001")


def publish_guard(record):
    revision = source_revision()
    require(os.getenv("RELEASE_PUBLISH_APPROVED") == "true" and
            os.getenv("RELEASE_GATE_SUCCESS") == "true", "Publishing is disabled/unapproved.")
    require(record["revision"] == revision and not record["local_validation_only"] and
            record["scan_passed"] and record["runtime_passed"], "Unapproved build evidence.")
    require(record["tag"] == "git-" + revision[:12], "Wrong immutable tag.")
    require(scan_summary(WORK / "trivy-private.json")["high_critical_gate_passed"],
            "Security gate no longer passes.")
    archive = WORK / "image.tar"
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == record["archive_sha256"] and
            config_digest(archive) == record["config_digest"], "Scanned image changed.")


def aws(operation, *args, missing_image=False):
    p = subprocess.run(["aws", "ecr", operation, *args, "--region", REGION, "--output", "json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    if missing_image and p.returncode and "(ImageNotFoundException)" in p.stderr:
        return None
    require(p.returncode == 0, "ECR read/publish operation failed; raw details withheld.")
    return json.loads(p.stdout)


def remote_manifest(digest):
    response = aws("batch-get-image", "--repository-name", REPOSITORY,
                   "--image-ids", "imageDigest=" + digest)
    require(not response.get("failures") and len(response.get("images", [])) == 1,
            "Remote manifest missing.")
    item = response["images"][0]
    body = item["imageManifest"]
    require(item["imageId"]["imageDigest"] == digest and
            "sha256:" + hashlib.sha256(body.encode()).hexdigest() == digest,
            "Remote manifest digest mismatch.")
    return json.loads(body)


def verify_remote(root, expected_config):
    manifest = remote_manifest(root)
    child = root
    if "manifests" in manifest:
        matches = [m for m in manifest["manifests"] if m.get("platform", {}).get("os") == "linux"
                   and m.get("platform", {}).get("architecture") == "amd64"]
        require(len(matches) == 1, "Remote index needs exactly one AMD64 image.")
        child = matches[0]["digest"]
        manifest = remote_manifest(child)
    require(manifest["config"]["digest"] == expected_config,
            "Remote image differs from the scanned local image config/rootfs.")
    return child


def publish():
    record = json.loads((WORK / "build.json").read_text())
    publish_guard(record)  # Must run before any AWS request or Docker login/push.
    account = os.getenv("EXPECTED_AWS_ACCOUNT_ID", "")
    require(re.fullmatch(r"[0-9]{12}", account), "Missing approved AWS account setting.")
    repo = aws("describe-repositories", "--repository-names", REPOSITORY)["repositories"][0]
    require(repo["registryId"] == account and repo["imageTagMutability"] == "IMMUTABLE" and
            repo["imageScanningConfiguration"]["scanOnPush"], "Repository/account policy mismatch.")
    url = repo["repositoryUri"]
    require(url == f"{account}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}", "Wrong registry.")
    existing = aws("describe-images", "--repository-name", REPOSITORY,
                   "--image-ids", "imageTag=" + record["tag"], missing_image=True)
    require(existing is None, "Immutable tag already exists; no overwrite or automatic retry.")
    # Reload the exact scanned archive, avoiding a tag changed by another local operation.
    run(["docker", "load", "-i", str(WORK / "image.tar")])
    remote = url + ":" + record["tag"]
    run(["docker", "tag", record["image"], remote])
    registry = url.split("/")[0]
    with tempfile.TemporaryDirectory(prefix="auth-", dir=WORK) as temporary:
        require(Path(temporary).resolve().is_relative_to(WORK.resolve()), "Unsafe auth path.")
        env = os.environ.copy()
        env["DOCKER_CONFIG"] = temporary
        try:
            token = run(["aws", "ecr", "get-login-password", "--region", REGION])
            run(["docker", "login", "--username", "AWS", "--password-stdin", registry],
                env=env, input_text=token)
            token = ""
            output = run(["docker", "push", remote], env=env)
            found = re.findall(r"digest: (sha256:[a-f0-9]{64})", output)
            require(len(set(found)) == 1, "Push digest not established; inspect remotely.")
            expected_root = found[0]
        finally:
            subprocess.run(["docker", "logout", registry], env=env, capture_output=True, timeout=30)
    actual = aws("describe-images", "--repository-name", REPOSITORY,
                 "--image-ids", "imageTag=" + record["tag"])["imageDetails"][0]["imageDigest"]
    require(actual == expected_root, "Pushed tag/root digest mismatch.")
    child = verify_remote(actual, record["config_digest"])
    evidence = {"revision": record["revision"], "tag": record["tag"], "repository": REPOSITORY,
                "region": REGION, "root_digest": actual, "amd64_digest": child,
                "scanned_config_digest": record["config_digest"], "digest_verified": True,
                "runtime_verified": True, "local_scan": "HIGH/CRITICAL gate passed",
                "ecs_or_alb_deployed": False, "status": "pushed; awaiting ECR scan",
                "verified_at": datetime.now(UTC).isoformat(), "scanner_image": TRIVY}
    save("release.json", evidence)
    for _ in range(60):
        try:
            scan = aws("describe-image-scan-findings", "--repository-name", REPOSITORY,
                       "--image-id", "imageDigest=" + child)
        except RuntimeError:
            time.sleep(5)
            continue
        status = scan["imageScanStatus"]["status"]
        if status == "COMPLETE":
            counts = scan["imageScanFindings"].get("findingSeverityCounts", {})
            passed = not counts.get("HIGH") and not counts.get("CRITICAL")
            evidence.update(ecr_scan_status=status, ecr_scan_counts=counts,
                            ecr_high_critical_gate_passed=passed,
                            status="published and digest verified" if passed
                            else "published; ECR security review required")
            save("release.json", evidence)
            require(not counts.get("HIGH") and not counts.get("CRITICAL"),
                    "ECR reports HIGH/CRITICAL after push; quarantine/review manually.")
            print("Published and verified:", record["tag"], "AMD64 digest:", child)
            return
        if status not in {"IN_PROGRESS", "PENDING"}:
            evidence.update(ecr_scan_status=status, status="published; ECR scan failed")
            save("release.json", evidence)
            raise RuntimeError("ECR scan failed; inspect published image.")
        time.sleep(5)
    raise RuntimeError("Image published but ECR scan unverified; do not deploy it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["build", "publish"])
    parser.add_argument("--local-validate", action="store_true")
    args = parser.parse_args()
    try:
        require(not args.local_validate or args.operation == "build", "Local publish is forbidden.")
        build(args.local_validate) if args.operation == "build" else publish()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else "Invalid input/tool timeout."
        print(message + " Publishing disabled or verification failed. "
              "Inspect sanitized reports; never overwrite/delete an existing tag.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
