"""Read-only ECS/ALB/log monitoring. No AWS mutation operations are implemented."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

import demo as control

STOPS = {
    "TaskFailedToStart",
    "EssentialContainerExited",
    "UserInitiated",
    "ServiceSchedulerInitiated",
    "SpotInterruption",
    "TerminationNotice",
}


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def rollback_eligible(service, tasks, targets, logging_ok):
    primary = [d for d in service.get("deployments", []) if d.get("status") == "PRIMARY"]
    breaker = service.get("deploymentConfiguration", {}).get("deploymentCircuitBreaker", {})
    desired = service.get("desiredCount", 0)
    return bool(
        len(primary) == 1
        and primary[0].get("rolloutState") == "COMPLETED"
        and primary[0].get("taskDefinition") == service.get("taskDefinition")
        and not any(d.get("rolloutState") == "IN_PROGRESS" for d in service.get("deployments", []))
        and service.get("launchType") == "FARGATE"
        and desired >= 1
        and service.get("runningCount") == desired
        and service.get("pendingCount") == 0
        and len(tasks) == desired
        and all(
            t.get("lastStatus") == "RUNNING"
            and t.get("healthStatus") == "HEALTHY"
            and t.get("taskDefinitionArn") == service.get("taskDefinition")
            and t.get("containers")
            and all(
                c.get("healthStatus") == "HEALTHY" and c.get("imageDigest") == control.DIGEST
                for c in t["containers"]
                if c.get("name") == "app"
            )
            and any(c.get("name") == "app" for c in t["containers"])
            for t in tasks
        )
        and len(targets) >= desired
        and all(t.get("TargetHealth", {}).get("State") == "healthy" for t in targets)
        and breaker.get("enable")
        and breaker.get("rollback")
        and logging_ok
    )


def metric_summary(points):
    return {
        "samples": len(points),
        "latest_average": max(points, key=lambda p: p["Timestamp"])["Average"] if points else None,
        "maximum": max(p["Maximum"] for p in points) if points else None,
    }


def collect():
    control.context()  # Auth/account/backend read checks; does not initialize or write state.
    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "region": control.REGION,
        "service": control.NAME,
        "rollback_baseline_eligible": False,
        "read_only": True,
    }
    clusters = control.aws("ecs", "describe-clusters", "--clusters", control.NAME)
    control.require(
        all(f.get("reason") == "MISSING" for f in clusters.get("failures", [])),
        "Cluster lookup incomplete; health unknown.",
    )
    if not any(c.get("status") == "ACTIVE" for c in clusters["clusters"]):
        report["state"] = "not deployed"
        return report
    response = control.aws(
        "ecs", "describe-services", "--cluster", control.NAME, "--services", control.NAME
    )
    control.require(
        all(f.get("reason") == "MISSING" for f in response.get("failures", [])),
        "Service lookup incomplete; health unknown.",
    )
    active = [s for s in response["services"] if s.get("status") == "ACTIVE"]
    if not active:
        report["state"] = "cluster exists; service absent"
        return report
    control.require(len(active) == 1, "Ambiguous service identity.")
    service = active[0]
    listed = control.aws(
        "ecs",
        "list-tasks",
        "--cluster",
        control.NAME,
        "--service-name",
        control.NAME,
        "--max-items",
        "20",
    )
    control.require(
        not listed.get("NextToken"), "Running-task inventory truncated; health unknown."
    )
    tasks = []
    if listed["taskArns"]:
        detail = control.aws(
            "ecs", "describe-tasks", "--cluster", control.NAME, "--tasks", *listed["taskArns"]
        )
        control.require(
            not detail.get("failures") and len(detail["tasks"]) == len(listed["taskArns"]),
            "Running-task inventory incomplete.",
        )
        tasks = detail["tasks"]
    targets = []
    for group in service.get("loadBalancers", []):
        targets.extend(
            control.aws(
                "elbv2", "describe-target-health", "--target-group-arn", group["targetGroupArn"]
            )["TargetHealthDescriptions"]
        )
    definition = control.aws(
        "ecs", "describe-task-definition", "--task-definition", service["taskDefinition"]
    )["taskDefinition"]
    app = next((c for c in definition["containerDefinitions"] if c["name"] == "app"), {})
    logconfig = app.get("logConfiguration", {})
    expected_group = "/ecs/" + control.NAME
    groups = control.aws("logs", "describe-log-groups", "--log-group-name-prefix", expected_group)[
        "logGroups"
    ]
    group = next((g for g in groups if g["logGroupName"] == expected_group), {})
    logging_ok = (
        logconfig.get("logDriver") == "awslogs"
        and logconfig.get("options", {}).get("awslogs-group") == expected_group
        and logconfig.get("options", {}).get("awslogs-region") == control.REGION
        and group.get("retentionInDays") == 7
    )
    end = datetime.now(UTC)
    start = end - timedelta(minutes=15)
    metrics = {}
    for name in ["CPUUtilization", "MemoryUtilization"]:
        data = control.aws(
            "cloudwatch",
            "get-metric-statistics",
            "--namespace",
            "AWS/ECS",
            "--metric-name",
            name,
            "--dimensions",
            "Name=ClusterName,Value=" + control.NAME,
            "Name=ServiceName,Value=" + control.NAME,
            "--start-time",
            start.isoformat(),
            "--end-time",
            end.isoformat(),
            "--period",
            "60",
            "--statistics",
            "Average",
            "Maximum",
        )
        metrics[name] = metric_summary(data["Datapoints"])
    lbs = control.aws("elbv2", "describe-load-balancers")["LoadBalancers"]
    lb_name = control.NAME[:23] + "-" + hashlib.sha1(control.NAME.encode()).hexdigest()[:8]
    lb = next((item for item in lbs if item["LoadBalancerName"] == lb_name), None)
    control.require(lb is not None, "Service ALB not found; monitoring incomplete.")
    lb_dimension = lb["LoadBalancerArn"].split("loadbalancer/")[1]
    alb_metrics = {}
    for name, statistics in [
        ("TargetResponseTime", ["Average", "Maximum"]),
        ("HTTPCode_Target_5XX_Count", ["Sum"]),
    ]:
        data = control.aws(
            "cloudwatch",
            "get-metric-statistics",
            "--namespace",
            "AWS/ApplicationELB",
            "--metric-name",
            name,
            "--dimensions",
            "Name=LoadBalancer,Value=" + lb_dimension,
            "--start-time",
            start.isoformat(),
            "--end-time",
            end.isoformat(),
            "--period",
            "60",
            "--statistics",
            *statistics,
        )
        points = data["Datapoints"]
        alb_metrics[name] = (
            metric_summary(points)
            if name == "TargetResponseTime"
            else {"samples": len(points), "sum": sum(p["Sum"] for p in points) if points else None}
        )
    target_config_ok = bool(service.get("loadBalancers"))
    for item in service.get("loadBalancers", []):
        groups = control.aws(
            "elbv2", "describe-target-groups", "--target-group-arns", item["targetGroupArn"]
        )["TargetGroups"]
        target_config_ok &= (
            len(groups) == 1
            and groups[0].get("HealthCheckPath") == "/ready"
            and groups[0].get("Port") == 8000
            and groups[0].get("Matcher", {}).get("HttpCode") == "200"
        )
    levels = Counter()
    traceback_sample = False
    if group:
        sample = control.aws(
            "logs",
            "filter-log-events",
            "--log-group-name",
            expected_group,
            "--start-time",
            str(int(start.timestamp() * 1000)),
            "--limit",
            "100",
            "--no-paginate",
        )
        for event in sample.get("events", []):
            message = event.get("message", "")
            traceback_sample |= "Traceback" in message
            try:
                level = json.loads(message).get("level", "other")
            except (ValueError, AttributeError):
                level = "other"
            levels[
                level if level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "other"
            ] += 1
        report["log_sample_has_more_pages"] = bool(sample.get("nextToken"))
    stopped = control.aws(
        "ecs",
        "list-tasks",
        "--cluster",
        control.NAME,
        "--service-name",
        control.NAME,
        "--desired-status",
        "STOPPED",
        "--max-items",
        "10",
    )
    stop_counts = Counter()
    exits = []
    if stopped["taskArns"]:
        detail = control.aws(
            "ecs", "describe-tasks", "--cluster", control.NAME, "--tasks", *stopped["taskArns"]
        )
        control.require(not detail.get("failures"), "Stopped-task history incomplete.")
        for task in detail["tasks"]:
            reason = task.get("stopCode", "other")
            stop_counts[reason if reason in STOPS else "other"] += 1
            exits.extend(c["exitCode"] for c in task.get("containers", []) if "exitCode" in c)
    report.update(
        state="deployed",
        desired=service["desiredCount"],
        running=service["runningCount"],
        pending=service["pendingCount"],
        deployments=[
            {
                "status": d.get("status"),
                "rollout": d.get("rolloutState"),
                "task_definition_fingerprint": fingerprint(d["taskDefinition"]),
            }
            for d in service.get("deployments", [])
        ],
        task_definition_fingerprint=fingerprint(service["taskDefinition"]),
        task_health=dict(Counter(t.get("healthStatus", "UNKNOWN") for t in tasks)),
        target_health=dict(Counter(t["TargetHealth"]["State"] for t in targets)),
        logging_config_correct=logging_ok,
        log_retention_days=group.get("retentionInDays"),
        recent_log_levels=dict(levels),
        traceback_in_sample=traceback_sample,
        stopped_task_codes=dict(stop_counts),
        stopped_exit_codes=exits,
        ecs_metrics=metrics,
        alb_metrics=alb_metrics,
        target_group_config_correct=target_config_ok,
        rollback_baseline_eligible=rollback_eligible(
            service, tasks, targets, logging_ok and target_config_ok and not traceback_sample
        ),
    )
    return report


def snapshot(require_baseline=False):
    try:
        report = collect()
    except (control.Refusal, OSError, ValueError, KeyError):
        control.save(
            "monitor.json",
            {
                "observed_at": datetime.now(UTC).isoformat(),
                "state": "monitoring incomplete",
                "rollback_baseline_eligible": False,
                "read_only": True,
            },
        )
        raise
    control.save("monitor.json", report)
    print(json.dumps(report, indent=2))
    print("Read-only sample, not an alarm or cost cap. Cleanup timers still apply.")
    if require_baseline:
        control.require(
            report["rollback_baseline_eligible"],
            "NO-GO: no current completed healthy deployment baseline for rollback.",
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-rollback-baseline", action="store_true")
    args = parser.parse_args()
    try:
        snapshot(args.require_rollback_baseline)
    except (control.Refusal, OSError, ValueError, KeyError):
        print(
            "Monitoring incomplete or rollback baseline unavailable. No AWS changes made.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
