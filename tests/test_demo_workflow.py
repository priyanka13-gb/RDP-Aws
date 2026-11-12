"""Offline refusal-path tests. Never invoke AWS or Terraform apply."""

import copy
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location("demo", Path(__file__).parents[1] / "scripts/demo.py")
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


@pytest.fixture
def plan():
    return json.loads((Path(__file__).parent / "fixtures/demo-plan.json").read_text())


def resource(plan, kind):
    return next(r for r in plan["resource_changes"] if r["type"] == kind)


def test_full_demo_and_partial_cleanup_allowed(plan):
    assert len(demo.validate_plan(plan)) == 34
    partial = copy.deepcopy(plan)
    partial["resource_changes"] = partial["resource_changes"][:2]
    for r in partial["resource_changes"]:
        r["change"]["actions"] = ["delete"]
    assert len(demo.validate_plan(partial, destroy=True)) == 2
    assert demo.validate_plan({"resource_changes": []}, destroy=True) == []


@pytest.mark.parametrize("action", [["update"], ["delete"], ["delete", "create"], ["forget"]])
def test_prepare_rejects_unexpected_actions(plan, action):
    plan["resource_changes"][0]["change"]["actions"] = action
    with pytest.raises(demo.Refusal):
        demo.validate_plan(plan)


@pytest.mark.parametrize("kind", ["aws_s3_bucket", "aws_ecr_repository", "aws_nat_gateway",
                                  "aws_db_instance"])
def test_foreign_resources_never_destroyed(plan, kind):
    plan["resource_changes"] = [{"mode": "managed", "address": "module.foreign.resource",
                                 "type": kind, "change": {"actions": ["delete"]}}]
    with pytest.raises(demo.Refusal):
        demo.validate_plan(plan, destroy=True)


def test_wrong_digest_refused(plan):
    task = resource(plan, "aws_ecs_task_definition")["change"]["after"]
    containers = json.loads(task["container_definitions"])
    containers[0]["image"] = "repo:latest"
    task["container_definitions"] = json.dumps(containers)
    with pytest.raises(demo.Refusal, match="Wrong image"):
        demo.validate_plan(plan)


def test_wrong_capacity_and_public_ingress_refused(plan):
    service = resource(plan, "aws_ecs_service")["change"]["after"]
    service["desired_count"] = 2
    with pytest.raises(demo.Refusal):
        demo.validate_plan(plan)


def test_no_noninteractive_or_cancelled_apply(monkeypatch):
    monkeypatch.setattr(demo.sys.stdin, "isatty", lambda: False)
    with pytest.raises(demo.Refusal, match="Interactive"):
        demo.confirm("deploy", "abcdef")
    monkeypatch.setattr(demo.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(demo.Refusal, match="Cancelled"):
        demo.confirm("cleanup", "abcdef")


@pytest.fixture
def approval(tmp_path):
    path = tmp_path / "deploy.tfplan"
    path.write_bytes(b"saved plan")
    ctx = {"account_fingerprint": demo.hashlib.sha256(b"123456789012").hexdigest(),
           "backend_hash": "test", "state_exists": False}
    rec = {"kind": "deploy", "commit": "commit", "checksum": demo.sha(path), "context": ctx,
           "created": datetime.now(UTC).isoformat(), "consumed": False}
    return path, ctx, rec


@pytest.mark.parametrize("field,value", [("checksum", "bad"), ("commit", "changed"),
                                         ("consumed", True)])
def test_stale_tampered_consumed_plan_refused(approval, field, value):
    path, ctx, rec = approval
    rec[field] = value
    with pytest.raises(demo.Refusal):
        demo.check_record(rec, path, ctx, "commit")


def test_expired_and_wrong_account_plan_refused(approval):
    path, ctx, rec = approval
    rec["created"] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with pytest.raises(demo.Refusal, match="expired"):
        demo.check_record(rec, path, ctx, "commit")
    rec["created"] = datetime.now(UTC).isoformat()
    ctx = {**ctx, "account_fingerprint": "other"}
    with pytest.raises(demo.Refusal, match="Account"):
        demo.check_record(rec, path, ctx, "commit")


def test_cancel_happens_before_apply(plan, approval, monkeypatch):
    path, ctx, rec = approval
    monkeypatch.setattr(demo, "STORE", path.parent)
    demo.save("deploy.json", rec)
    monkeypatch.setattr(demo, "context", lambda: ctx)
    monkeypatch.setattr(demo, "clean_commit", lambda: "commit")
    monkeypatch.setattr(demo, "release_check", lambda: None)
    tf = Mock(return_value=json.dumps(plan))
    monkeypatch.setattr(demo, "tf", tf)
    monkeypatch.setattr(demo, "confirm", Mock(side_effect=demo.Refusal("Cancelled")))
    with pytest.raises(demo.Refusal):
        demo.apply_approved("deploy")
    assert all(call.args[0] != "apply" for call in tf.call_args_list)


def test_partial_failure_consumes_plan_and_requires_reprepare(plan, approval, monkeypatch):
    path, ctx, rec = approval
    monkeypatch.setattr(demo, "STORE", path.parent)
    demo.save("deploy.json", rec)
    monkeypatch.setattr(demo, "context", lambda: ctx)
    monkeypatch.setattr(demo, "clean_commit", lambda: "commit")
    monkeypatch.setattr(demo, "release_check", lambda: None)
    monkeypatch.setattr(demo, "confirm", lambda *_: None)

    def fake_tf(*args, **kwargs):
        if args[0] == "apply":
            raise demo.Refusal("simulated partial apply")
        return json.dumps(plan)

    monkeypatch.setattr(demo, "tf", fake_tf)
    with pytest.raises(demo.Refusal):
        demo.apply_approved("deploy")
    assert json.loads((path.parent / "deploy.json").read_text())["consumed"]
    with pytest.raises(demo.Refusal, match="already attempted"):
        demo.apply_approved("deploy")


def test_dirty_source_refused_and_cli_overrides_removed(monkeypatch):
    monkeypatch.setattr(demo, "run", lambda _: " M source.py")
    with pytest.raises(demo.Refusal, match="clean"):
        demo.clean_commit()
    monkeypatch.setenv("TF_VAR_desired_count", "10")
    monkeypatch.setenv("TF_CLI_ARGS_plan", "-target=anything")
    env = demo.environment()
    assert "TF_VAR_desired_count" not in env
    assert "TF_CLI_ARGS_plan" not in env
    assert env["AWS_REGION"] == "ap-southeast-2"


def test_failed_aws_check_cannot_report_clean(monkeypatch):
    monkeypatch.setattr(demo, "context", Mock(side_effect=demo.Refusal("Access denied")))
    with pytest.raises(demo.Refusal):
        demo.status()


def test_missing_state_status_is_not_a_permission_bypass(monkeypatch):
    monkeypatch.setattr(demo, "context", lambda: {"state_exists": False})
    report = {"running_or_pending_tasks": 0, "load_balancers": 0, "vpcs": 0,
              "enis": 0, "log_groups": 0, "state_resources": 0, "tagged_elastic_ips": 0}
    inventory = Mock(return_value=(report, []))
    monkeypatch.setattr(demo, "inventory", inventory)
    monkeypatch.setattr(demo, "save", lambda *_: None)
    assert not demo.status()["possible_recurring_charges"]
    inventory.assert_called_once_with(state_exists=False)


def test_cleanup_leftovers_are_failures():
    report = dict.fromkeys(["running_or_pending_tasks", "load_balancers", "vpcs",
                            "enis", "log_groups", "state_resources", "tagged_elastic_ips",
                            "ecs_clusters", "ecs_services"], 0)
    demo.confirm_removed(report)
    for key in report:
        with pytest.raises(demo.Refusal, match="INCOMPLETE"):
            demo.confirm_removed({**report, key: 1})


def test_cleanup_plan_cannot_create_or_replace(plan):
    plan["resource_changes"][0]["change"]["actions"] = ["create"]
    with pytest.raises(demo.Refusal):
        demo.validate_plan(plan, destroy=True)


def test_wrong_image_account_refused(plan):
    with pytest.raises(demo.Refusal, match="account"):
        demo.check_image_account(plan, {"account_fingerprint": "different"})


def test_repeated_deploy_noop_does_not_apply(plan, approval, monkeypatch):
    path, ctx, rec = approval
    monkeypatch.setattr(demo, "STORE", path.parent)
    demo.save("deploy.json", rec)
    monkeypatch.setattr(demo, "context", lambda: ctx)
    monkeypatch.setattr(demo, "clean_commit", lambda: "commit")
    for r in plan["resource_changes"]:
        r["change"]["actions"] = ["no-op"]
    tf = Mock(return_value=json.dumps(plan))
    monkeypatch.setattr(demo, "tf", tf)
    monkeypatch.setattr(demo, "confirm", Mock(side_effect=AssertionError("Must not prompt/apply")))
    demo.apply_approved("deploy")
    assert all(c.args[0] != "apply" for c in tf.call_args_list)
