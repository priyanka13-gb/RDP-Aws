"""Monitoring must never infer rollback eligibility from missing/stale health proof."""

import copy
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("monitor", SCRIPTS / "monitor_demo.py")
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)
DRILL = importlib.util.spec_from_file_location("drill", SCRIPTS / "local_failure_drill.py")
drill = importlib.util.module_from_spec(DRILL)
DRILL.loader.exec_module(drill)
sys.path.pop(0)


@pytest.fixture
def healthy():
    service = {
        "taskDefinition": "private-definition",
        "desiredCount": 1,
        "runningCount": 1,
        "pendingCount": 0,
        "launchType": "FARGATE",
        "deploymentConfiguration": {"deploymentCircuitBreaker": {"enable": True, "rollback": True}},
        "deployments": [
            {
                "status": "PRIMARY",
                "rolloutState": "COMPLETED",
                "taskDefinition": "private-definition",
            }
        ],
        "loadBalancers": [{"targetGroupArn": "private-target"}],
    }
    tasks = [
        {
            "lastStatus": "RUNNING",
            "healthStatus": "HEALTHY",
            "taskDefinitionArn": "private-definition",
            "containers": [
                {"name": "app", "healthStatus": "HEALTHY", "imageDigest": monitor.control.DIGEST}
            ],
        }
    ]
    targets = [{"TargetHealth": {"State": "healthy"}}]
    return service, tasks, targets


def test_current_completed_healthy_baseline_required(healthy):
    assert monitor.rollback_eligible(*healthy, True)
    assert not monitor.rollback_eligible(*healthy, False)


@pytest.mark.parametrize(
    "case",
    [
        "first_deploy",
        "old_completed",
        "zero_tasks",
        "pending",
        "unhealthy_task",
        "unhealthy_target",
        "wrong_image",
        "wrong_definition",
        "no_breaker",
    ],
)
def test_rollback_refuses_incomplete_or_unhealthy_baseline(healthy, case):
    service, tasks, targets = copy.deepcopy(healthy)
    if case in {"first_deploy", "old_completed"}:
        service["deployments"][0]["rolloutState"] = "IN_PROGRESS"
        if case == "old_completed":
            service["deployments"].append(
                {
                    "status": "ACTIVE",
                    "rolloutState": "COMPLETED",
                    "taskDefinition": "old-private-definition",
                }
            )
    elif case == "zero_tasks":
        tasks.clear()
    elif case == "pending":
        service["pendingCount"] = 1
    elif case == "unhealthy_task":
        tasks[0]["healthStatus"] = "UNHEALTHY"
    elif case == "unhealthy_target":
        targets[0]["TargetHealth"]["State"] = "unhealthy"
    elif case == "wrong_image":
        tasks[0]["containers"][0]["imageDigest"] = "different"
    elif case == "wrong_definition":
        tasks[0]["taskDefinitionArn"] = "different"
    else:
        service["deploymentConfiguration"]["deploymentCircuitBreaker"]["rollback"] = False
    assert not monitor.rollback_eligible(service, tasks, targets, True)


def test_missing_metrics_are_unknown_not_zero():
    assert monitor.metric_summary([]) == {"samples": 0, "latest_average": None, "maximum": None}


def test_absent_deployment_never_claims_rollback(monkeypatch):
    monkeypatch.setattr(monitor.control, "context", lambda: None)
    monkeypatch.setattr(
        monitor.control, "aws", lambda *a: {"clusters": [], "failures": [{"reason": "MISSING"}]}
    )
    report = monitor.collect()
    assert report["state"] == "not deployed" and not report["rollback_baseline_eligible"]


def test_monitor_failure_invalidates_old_healthy_snapshot(monkeypatch):
    monkeypatch.setattr(monitor, "collect", Mock(side_effect=monitor.control.Refusal("denied")))
    save = Mock()
    monkeypatch.setattr(monitor.control, "save", save)
    with pytest.raises(monitor.control.Refusal):
        monitor.snapshot()
    assert save.call_args.args[1]["rollback_baseline_eligible"] is False
    assert save.call_args.args[1]["state"] == "monitoring incomplete"


def test_monitor_output_redacts_identifiers_and_log_bodies(monkeypatch, healthy):
    service, tasks, targets = healthy
    monkeypatch.setattr(monitor.control, "context", lambda: None)
    lb_name = (
        monitor.control.NAME[:23]
        + "-"
        + monitor.hashlib.sha1(monitor.control.NAME.encode()).hexdigest()[:8]
    )

    def aws(namespace, operation, *args):
        if operation == "describe-clusters":
            return {"clusters": [{"status": "ACTIVE"}]}
        if operation == "describe-services":
            return {"services": [{**service, "status": "ACTIVE"}]}
        if operation == "list-tasks":
            return {"taskArns": [] if "STOPPED" in args else ["private-task"]}
        if operation == "describe-tasks":
            return {"tasks": tasks}
        if operation == "describe-target-health":
            return {"TargetHealthDescriptions": targets}
        if operation == "describe-target-groups":
            return {
                "TargetGroups": [
                    {"HealthCheckPath": "/ready", "Port": 8000, "Matcher": {"HttpCode": "200"}}
                ]
            }
        if operation == "describe-task-definition":
            return {
                "taskDefinition": {
                    "containerDefinitions": [
                        {
                            "name": "app",
                            "logConfiguration": {
                                "logDriver": "awslogs",
                                "options": {
                                    "awslogs-group": "/ecs/" + monitor.control.NAME,
                                    "awslogs-region": monitor.control.REGION,
                                },
                            },
                        }
                    ]
                }
            }
        if operation == "describe-log-groups":
            return {
                "logGroups": [
                    {"logGroupName": "/ecs/" + monitor.control.NAME, "retentionInDays": 7}
                ]
            }
        if operation == "describe-load-balancers":
            return {
                "LoadBalancers": [
                    {
                        "LoadBalancerName": lb_name,
                        "LoadBalancerArn": "private:loadbalancer/app/test/id",
                    }
                ]
            }
        if operation == "get-metric-statistics":
            return {"Datapoints": []}
        assert operation == "filter-log-events"
        return {"events": [{"message": '{"level":"INFO","message":"private-token"}'}]}

    monkeypatch.setattr(monitor.control, "aws", aws)
    report = monitor.collect()
    assert report["rollback_baseline_eligible"]
    assert report["logging_config_correct"] and report["target_group_config_correct"]
    assert report["recent_log_levels"] == {"INFO": 1}
    assert "private" not in json.dumps(report)
    assert all(r["samples"] == 0 for r in report["ecs_metrics"].values())


@pytest.mark.parametrize(
    "name,health,ready,docker_health",
    [
        ("unhealthy_application", 503, 200, "unhealthy"),
        ("failed_readiness", 200, 503, "healthy"),
        ("healthy_recovery", 200, 200, "healthy"),
    ],
)
def test_local_failure_contracts(name, health, ready, docker_health):
    assert drill.expected(name) == (health, ready, docker_health)


def test_local_faults_are_ephemeral_commands_not_production_changes():
    assert drill.scenario_command("healthy_baseline") == []
    assert "LOCAL_DRILL_STARTUP_FAILURE" in drill.scenario_command("startup_failure")[-1]
    assert "/health" in drill.scenario_command("unhealthy_application")[-1]
    assert "/ready" in drill.scenario_command("failed_readiness")[-1]
    with pytest.raises(ValueError):
        drill.scenario_command("live_aws")
