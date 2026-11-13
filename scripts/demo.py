"""On-demand demo operations. AWS mutations exist only behind typed confirmation."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / ".tools" / "demo"
REGION = "ap-southeast-2"
PROFILE = "rdp-dev"
NAME = "aws-resilient-delivery-platform-dev"
BUCKET = "rdp-tfstate-sydney-be4bb3dfae"
KEY = "aws-resilient-delivery-platform/dev/terraform.tfstate"
DIGEST = "sha256:e86be3d8597649995145a5e1633bfc4ccf19b8ca1185127ea6720d72d2bf0be1"
RELEASE = "git-9b18a3109aa2"
APP_SHA = "9b18a3109aa2fd1d3bc6a2dc0ffb0fc17ec27823"
VARS = "releases/task23.tfvars.example"
COST = "Baseline ~$0.055/hour; quiet example ~$0.066/hour, before credits/tax."


class Refusal(RuntimeError):
    """A failed prerequisite or unsafe operation; no raw service response printed."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def environment():
    require(not os.getenv("TF_DATA_DIR"), "Unset TF_DATA_DIR; use existing dev metadata.")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("TF_VAR_", "TF_CLI_ARGS"))}
    for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "AWS_SECURITY_TOKEN", "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE"]:
        env.pop(key, None)
    env.update(AWS_PROFILE=PROFILE, AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION,
               AWS_PAGER="", TF_IN_AUTOMATION="1", TF_WORKSPACE="default")
    return env


def aws_failure(stderr):
    """Extract only an operation-independent category/code, never service message text."""
    match = re.search(r"An error occurred \(([A-Za-z0-9_.-]{1,64})\)", stderr, re.I)
    code = match.group(1) if match else "CLI_ERROR"
    if re.search(r"[0-9]{12}|AKIA|ASIA", code):
        code = "AWS_SERVICE_ERROR"
    text = stderr.lower()
    if (code in {"ExpiredToken", "ExpiredTokenException", "RequestExpired"}
            or re.search(r"(?:session|credentials|token).{0,40}expired", text)
            or "unauthorizedssotoken" in text or "refresh token" in text):
        return "authentication/session-expired", code if match else "CLI_SESSION_EXPIRED"
    if any(word in text for word in ("accessdenied", "unauthorizedoperation", "not authorized",
                                    "forbidden")):
        return "authorization", code if match else "CLI_ACCESS_DENIED"
    if any(word in text for word in ("could not connect", "endpointconnection", "connect timeout",
                                    "read timeout", "proxyconnection", "name resolution",
                                    "ssl validation", "certificate verify")):
        return "network/TLS", code if match else "CLI_NETWORK_ERROR"
    if any(word in text for word in ("unable to locate credentials", "invalidclienttokenid",
                                    "unrecognizedclient", "invalidgrant", "signaturedoesnotmatch")):
        return "authentication", code if match else "CLI_NO_CREDENTIALS"
    if "profile" in text and any(word in text for word in ("not found", "could not be found")):
        return "configuration/profile", "CLI_PROFILE_NOT_FOUND"
    if any(word in text for word in ("throttl", "serviceunavailable", "internalerror",
                                    "requestlimitexceeded")):
        return "service/throttling", code
    if code in {"404", "NoSuchKey", "NoSuchBucket", "ResourceNotFoundException",
                "RepositoryNotFoundException", "ImageNotFoundException"}:
        return "resource/not-found", code
    return "service/CLI", code


def aws_operation(args):
    # Log the service/operation only, not arguments (which can contain secrets/IDs).
    words = args[1:3]
    if len(words) == 2 and all(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", w) for w in words):
        return "aws " + " ".join(words)
    return "aws"


def run(args, *, missing=(), timeout=180):
    try:
        result = subprocess.run(args, cwd=ROOT, env=environment(), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        operation = aws_operation(args) if args[0] == "aws" else args[0]
        category = "network/timeout" if isinstance(exc, subprocess.TimeoutExpired) else "local/tool"
        raise Refusal(f"{operation} failed: category={category}; "
                      "inspect tool availability/connectivity before retrying.") from exc
    if result.returncode:
        if args[0] == "aws":
            category, code = aws_failure(result.stderr)
            # Only a structured not-found code may satisfy an expected missing object.
            # Never swallow AccessDenied just because message text happens to contain 404.
            if missing and code in {"404", "NoSuchKey"} and (
                    "404" in missing or "Not Found" in missing):
                return None
            hint = (f" Run aws login --profile {PROFILE} --region {REGION}."
                    if category == "authentication/session-expired" else "")
            raise Refusal(f"{aws_operation(args)} failed: category={category}, "
                          f"code={code}, exit={result.returncode}.{hint} "
                          "Raw output withheld to protect identifiers/secrets.")
        if any(code in result.stderr for code in missing):
            return None
        raise Refusal(f"{args[0]} command failed. Check session, permissions and service events. "
                      "Raw output withheld to protect identifiers/secrets.")
    return result.stdout


def aws(service, operation, *args, missing=()):
    text = run(["aws", service, operation, *args, "--profile", PROFILE, "--region", REGION,
                "--output", "json"], missing=missing)
    return json.loads(text) if text is not None else None


def tf(*args, timeout=180):
    return run(["terraform", "-chdir=infra/envs/dev", *args], timeout=timeout)


def save(name, data):
    STORE.mkdir(parents=True, exist_ok=True)
    path = STORE / name
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_commit():
    require(not run(["git", "status", "--porcelain"]).strip(),
            "Working tree must be clean. Review and commit locally; do not discard evidence.")
    return run(["git", "rev-parse", "HEAD"]).strip()


def baseline():
    data = json.loads((ROOT / "evidence/task23/plan-summary.json").read_text())
    return {r["address"]: r["type"] for r in data["resources"]}


def validate_plan(plan, *, destroy=False):
    """Strict ownership/actions guard; destroy permits partial-state subsets."""
    allowed = baseline()
    managed = [r for r in plan.get("resource_changes", []) if r["mode"] == "managed"]
    require(all(r["address"] in allowed and allowed[r["address"]] == r["type"]
                for r in managed), "STOP: resource outside the reviewed dev allowlist.")
    permitted = [["delete"], ["no-op"]] if destroy else [["create"], ["no-op"]]
    require(all(r["change"]["actions"] in permitted for r in managed),
            "STOP: update/replacement/unexpected action. Review a separate recovery plan.")
    if not destroy:
        require({r["address"] for r in managed} == set(allowed),
                "STOP: expected all 34 dev resources in plan.")
        after = {r["address"]: r["change"]["after"] for r in managed}
        task = after["module.ecs_service.aws_ecs_task_definition.app"]
        container = json.loads(task["container_definitions"])[0]
        require(container["image"].endswith("/" + NAME + "@" + DIGEST), "Wrong image.")
        require(task["cpu"] == "256" and task["memory"] == "512", "Wrong task size.")
        require(task["runtime_platform"][0]["cpu_architecture"] == "X86_64", "Wrong ABI.")
        require(container["user"] == "10001:10001" and
                container["portMappings"][0]["containerPort"] == 8000, "Unsafe task config.")
        settings = {e["name"]: e["value"] for e in container["environment"]}
        require(not settings.get("DATABASE_URL") and not container.get("secrets"),
                "Demo must not introduce database credentials or SSM secrets.")
        require(settings.get("APP_VERSION") == RELEASE and settings.get("GIT_SHA") == APP_SHA,
                "Wrong release metadata.")
        service = after["module.ecs_service.aws_ecs_service.app"]
        require(service["desired_count"] == 1 and
                service["network_configuration"][0]["assign_public_ip"] and
                service["deployment_circuit_breaker"][0] == {"enable": True, "rollback": True},
                "Wrong demo capacity/network/rollback.")
        ingress = after["module.network.aws_vpc_security_group_ingress_rule.ecs_from_alb"]
        require(not ingress.get("cidr_ipv4") and not ingress.get("cidr_ipv6") and
                ingress["from_port"] == ingress["to_port"] == 8000,
                "Task ingress must be SG-only on port8000.")
        require(after["module.alb.aws_lb_target_group.app"]["health_check"][0]["path"]
                == "/ready", "Wrong readiness path.")
        require(after["module.observability.aws_cloudwatch_log_group.app"]
                ["retention_in_days"] == 7, "Wrong log retention.")
    return managed


def context():
    """Verify existing backend only. No init/reconfigure, state migration or lock writes."""
    metadata = ROOT / "infra/envs/dev/.terraform/terraform.tfstate"
    require(metadata.exists(), "Backend not initialized; perform separate backend review.")
    backend = json.loads(metadata.read_text())["backend"]
    config = backend["config"]
    require(backend["type"] == "s3" and config["bucket"] == BUCKET and config["key"] == KEY
            and config["encrypt"] and config["use_lockfile"], "Wrong backend configuration.")
    require(config.get("region") in (None, REGION) and config.get("profile") in (None, PROFILE),
            "Unexpected backend profile/region.")
    require(tf("workspace", "show").strip() == "default", "Wrong Terraform workspace.")
    identity = aws("sts", "get-caller-identity")
    location = aws("s3api", "get-bucket-location", "--bucket", BUCKET,
                   "--expected-bucket-owner", identity["Account"])
    require(location["LocationConstraint"] == REGION, "Wrong bucket region.")
    repo = aws("ecr", "describe-repositories", "--repository-names", NAME)["repositories"][0]
    require(repo["repositoryUri"].split(".")[0] == identity["Account"], "Wrong ECR account.")
    require(repo["imageTagMutability"] == "IMMUTABLE", "ECR repository must be immutable.")
    state = aws("s3api", "head-object", "--bucket", BUCKET, "--key", KEY,
                "--expected-bucket-owner", identity["Account"], missing=("404", "Not Found"))
    return {"account_fingerprint": hashlib.sha256(identity["Account"].encode()).hexdigest(),
            "backend_hash": sha(metadata), "state_exists": state is not None}


def release_check():
    aws("ecr", "describe-images", "--repository-name", NAME,
        "--image-ids", "imageDigest=" + DIGEST)
    scan = aws("ecr", "describe-image-scan-findings", "--repository-name", NAME,
               "--image-id", "imageDigest=" + DIGEST)
    require(scan["imageScanStatus"]["status"] == "COMPLETE" and
            not any(scan["imageScanFindings"].get("findingSeverityCounts", {}).values()),
            "ECR scan incomplete or findings present. Stop for security review.")


def check_image_account(plan, ctx):
    for item in plan.get("resource_changes", []):
        if item["type"] == "aws_ecs_task_definition" and item["change"].get("after"):
            image = json.loads(item["change"]["after"]["container_definitions"])[0]["image"]
            account = image.split(".")[0]
            require(hashlib.sha256(account.encode()).hexdigest() == ctx["account_fingerprint"],
                    "Task image account differs from verified AWS context.")


def make_plan(kind):
    commit = clean_commit() if kind == "deploy" else run(["git", "rev-parse", "HEAD"]).strip()
    ctx = context()
    if kind == "deploy":
        release_check()
        tf("validate", "-no-color")
        quota = aws("service-quotas", "get-service-quota", "--service-code", "fargate",
                    "--quota-code", "L-3032A538")
        require(quota["Quota"]["Value"] >= 0.5, "Insufficient Fargate rollout quota.")
        print("First-use ECS/ELB service-linked roles need iam:CreateServiceLinkedRole. "
              "Plan success does not prove effective create/PassRole permissions.")
    STORE.mkdir(parents=True, exist_ok=True)
    path = STORE / (kind + ".tfplan")
    args = ["plan", "-input=false", "-lock=false", "-no-color", "-var-file=" + VARS,
            "-out=" + str(path)]
    if kind == "cleanup":
        args.append("-destroy")
    # Preparing plans must not modify remote state or create lock objects.
    tf(*args, timeout=300)
    plan = json.loads(tf("show", "-json", str(path)))
    resources = validate_plan(plan, destroy=kind == "cleanup")
    if kind == "deploy":
        check_image_account(plan, ctx)
    require(kind != "deploy" or clean_commit() == commit, "Source changed while planning.")
    record = {"kind": kind, "commit": commit, "checksum": sha(path), "context": ctx,
              "created": datetime.now(UTC).isoformat(), "consumed": False,
              "resources": [{"address": r["address"], "actions": r["change"]["actions"]}
                            for r in resources]}
    save(kind + ".json", record)
    for r in record["resources"]:
        print(f"{','.join(r['actions'])}: {r['address']}")
    print("Plan SHA256:", record["checksum"])
    print(COST, "Public HTTP only. No sensitive data. Cleanup after 1-2 hours.")
    return record


def check_record(record, path, ctx, commit, *, now=None):
    now = now or datetime.now(UTC)
    require(not record["consumed"], "Plan already attempted. Prepare a fresh plan.")
    require(sha(path) == record["checksum"], "Plan checksum mismatch.")
    require(record["commit"] == commit, "Source commit changed; prepare again.")
    require(record["context"]["account_fingerprint"] == ctx["account_fingerprint"] and
            record["context"]["backend_hash"] == ctx["backend_hash"], "Account/backend changed.")
    age = now - datetime.fromisoformat(record["created"])
    require(timedelta(0) <= age <= timedelta(hours=1), "Plan expired; prepare again.")


def confirm(kind, checksum):
    require(sys.stdin.isatty(), "Interactive terminal required; no unattended apply.")
    phrase = f"{'DEPLOY' if kind == 'deploy' else 'DESTROY'} dev {checksum[:12]}"
    print("DEV ONLY. Bootstrap/ECR preserved. This will change AWS and can incur costs.")
    require(input(f"Type '{phrase}' to continue: ") == phrase, "Cancelled; no apply executed.")


def apply_approved(kind):
    record = json.loads((STORE / (kind + ".json")).read_text())
    path = STORE / (kind + ".tfplan")
    ctx = context()
    commit = clean_commit() if kind == "deploy" else run(["git", "rev-parse", "HEAD"]).strip()
    check_record(record, path, ctx, commit)
    plan = json.loads(tf("show", "-json", str(path)))
    resources = validate_plan(plan, destroy=kind == "cleanup")
    if kind == "deploy":
        check_image_account(plan, ctx)
    if not any(r["change"]["actions"] != ["no-op"] for r in resources):
        print("No changes; nothing to apply.")
        if kind == "cleanup":
            confirm_removed(status())
        return
    if kind == "deploy":
        release_check()
    confirm(kind, record["checksum"])
    # Recheck after a human pause; Terraform also rejects stale saved state.
    ctx = context()
    check_record(record, path, ctx, clean_commit() if kind == "deploy" else commit)
    record["consumed"] = True
    record["result"] = "attempting; interrupted run may leave billable partial resources"
    save(kind + ".json", record)
    try:
        tf("apply", "-input=false", "-lock-timeout=60s", str(path), timeout=1800)
    except (Refusal, KeyboardInterrupt):
        print("APPLY FAILED/INTERRUPTED: costs may continue. Run status-demo; preserve state. "
              "Prepare fresh cleanup or recovery plan; never blindly retry or force-unlock.")
        raise
    record["result"] = "apply completed"
    save(kind + ".json", record)
    if kind == "deploy":
        print("Deployment complete; run verify-demo now, then cleanup-demo after the interview.")
        outputs = json.loads(tf("output", "-json"))
        print("HTTP endpoint:", outputs["application_url"]["value"])
    else:
        confirm_removed(status())


def confirm_removed(report):
    require(not any(report[k] for k in ("running_or_pending_tasks", "load_balancers",
                                       "vpcs", "state_resources", "enis", "log_groups",
                                       "tagged_elastic_ips", "ecs_clusters", "ecs_services")),
            "CLEANUP INCOMPLETE: remaining dev resources; inspect status and charges.")


def inventory(*, state_exists=True):
    clusters = aws("ecs", "describe-clusters", "--clusters", NAME)["clusters"]
    clusters = [c for c in clusters if c.get("status") == "ACTIVE"]
    tasks = []
    services = []
    if clusters:
        # list-tasks defaults to desired RUNNING, including provisioning/pending tasks.
        tasks = aws("ecs", "list-tasks", "--cluster", NAME)["taskArns"]
        services = aws("ecs", "describe-services", "--cluster", NAME,
                       "--services", NAME)["services"]
        services = [svc for svc in services if svc["status"] != "INACTIVE"]
    lbs = aws("elbv2", "describe-load-balancers")["LoadBalancers"]
    lb_name = NAME[:23] + "-" + hashlib.sha1(NAME.encode()).hexdigest()[:8]
    lbs = [lb for lb in lbs if lb["LoadBalancerName"] == lb_name]
    vpcs = aws("ec2", "describe-vpcs", "--filters",
               "Name=tag:Name,Values=" + NAME)["Vpcs"]
    # Remember VPC IDs to detect service-managed, untagged ENIs after partial teardown.
    ids = {v["VpcId"] for v in vpcs}
    memo = STORE / "vpcs.json"
    if memo.exists():
        ids.update(json.loads(memo.read_text()))
    if ids:
        save("vpcs.json", sorted(ids))
    enis = []
    for vpc in sorted(ids):
        enis.extend(aws("ec2", "describe-network-interfaces", "--filters",
                        "Name=vpc-id,Values=" + vpc)["NetworkInterfaces"])
    logs = aws("logs", "describe-log-groups", "--log-group-name-prefix", "/ecs/" + NAME)
    groups = [g for g in logs["logGroups"] if g["logGroupName"] == "/ecs/" + NAME]
    addresses = aws("ec2", "describe-addresses", "--filters",
                    "Name=tag:Project,Values=aws-resilient-delivery-platform",
                    "Name=tag:Environment,Values=dev")["Addresses"]
    state_resources = tf("state", "list").strip().splitlines() if state_exists else []
    return {"running_or_pending_tasks": len(tasks), "load_balancers": len(lbs),
            "ecs_clusters": len(clusters), "ecs_services": len(services),
            "vpcs": len(vpcs), "enis": len(enis), "state_resources": len(state_resources),
            "tagged_elastic_ips": len(addresses),
            "log_groups": len(groups), "log_stored_bytes": sum(g.get("storedBytes", 0)
                                                                       for g in groups)}, lbs


def status():
    ctx = context()
    report, _ = inventory(state_exists=ctx["state_exists"])
    report["remote_state_object_exists"] = ctx["state_exists"]
    report["possible_recurring_charges"] = any(report[k] for k in
                                              ["running_or_pending_tasks", "load_balancers",
                                               "enis", "log_groups", "state_resources",
                                               "tagged_elastic_ips"])
    save("status.json", report)
    print(json.dumps(report, indent=2))
    print("ECR image storage and versioned S3 backend storage remain intentionally. "
          "Status checks are not billing data. A zero-task service can still have ALB charges.")
    return report


def verify_http(base):
    for path in ["/health", "/ready", "/version", "/metrics"]:
        try:
            with urlopen(base + path, timeout=15) as response:
                require(response.status == 200, "HTTP smoke check failed.")
                body = response.read().decode()
        except (OSError, HTTPError) as exc:
            raise Refusal("HTTP failed; inspect ALB target health and ECS logs.") from exc
        if path == "/health":
            require(json.loads(body) == {"status": "healthy"}, "Wrong health response.")
        elif path == "/ready":
            require(json.loads(body) == {"status": "ready"}, "Application not ready.")
        elif path == "/version":
            require(json.loads(body) == {"app_version": RELEASE, "git_sha": APP_SHA},
                    "Wrong deployed version.")
        else:
            require("http_requests_total" in body, "Metrics missing.")
        print(path, "passed")


def verify():
    ctx = context()
    run(["aws", "ecs", "wait", "services-stable", "--cluster", NAME, "--services", NAME,
         "--profile", PROFILE, "--region", REGION], timeout=600)
    service = aws("ecs", "describe-services", "--cluster", NAME, "--services", NAME)
    require(not service.get("failures") and len(service["services"]) == 1, "Service missing.")
    svc = service["services"][0]
    require(svc["runningCount"] == svc["desiredCount"] == 1 and svc["pendingCount"] == 0,
            "Service not running one healthy task.")
    tasks = aws("ecs", "list-tasks", "--cluster", NAME)["taskArns"]
    require(bool(tasks), "No running tasks.")
    detail = aws("ecs", "describe-tasks", "--cluster", NAME, "--tasks", *tasks)
    require(not detail.get("failures") and len(detail["tasks"]) == len(tasks) and
            all(t.get("containers") for t in detail["tasks"]) and
            all(c.get("imageDigest") == DIGEST
            for t in detail["tasks"] for c in t["containers"]), "Running digest mismatch.")
    health = aws("elbv2", "describe-target-health", "--target-group-arn",
                 svc["loadBalancers"][0]["targetGroupArn"])["TargetHealthDescriptions"]
    require(health and all(h["TargetHealth"]["State"] == "healthy" for h in health),
            "ALB targets unhealthy.")
    _, lbs = inventory(state_exists=ctx["state_exists"])
    require(len(lbs) == 1, "Demo ALB missing or ambiguous.")
    base = "http://" + lbs[0]["DNSName"]
    print("PUBLIC HTTP ONLY: no credentials/private data. Endpoint:", base)
    verify_http(base)
    logs = aws("logs", "filter-log-events", "--log-group-name", "/ecs/" + NAME,
               "--start-time", str(int((datetime.now(UTC) - timedelta(minutes=15)).timestamp()
                                      * 1000)), "--limit", "100")
    events = logs.get("events", [])
    # Do not echo arbitrary log bodies: they can contain secrets even in a demo.
    require(not any("Traceback" in e.get("message", "") for e in events),
            "Traceback in recent log sample; inspect CloudWatch privately.")
    print("Recent CloudWatch log events sampled:", len(events), "(bodies withheld).")
    require(events, "No recent logs found; inspect logging before declaring demo healthy.")
    save("verification.json", {"verified_at": datetime.now(UTC).isoformat(),
                               "image_digest": DIGEST, "target_health": "healthy",
                               "http_endpoints": "passed", "log_events_sampled": len(events)})
    print("Demo verified. Set an independent phone alarm now. Cleanup after 1-2 hours.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",
                        choices=["prepare", "deploy", "verify", "cleanup", "status", "monitor"])
    command = parser.parse_args().command
    try:
        if command == "prepare":
            make_plan("deploy")
        elif command == "deploy":
            apply_approved("deploy")
        elif command == "verify":
            verify()
        elif command == "monitor":
            from monitor_demo import snapshot

            snapshot()
        elif command == "cleanup":
            make_plan("cleanup")
            apply_approved("cleanup")
        else:
            status()
    except (Refusal, OSError, ValueError, KeyError, KeyboardInterrupt) as exc:
        # Never echo arbitrary AWS errors or user log contents.
        message = (str(exc) if isinstance(exc, Refusal)
                   else "Missing/invalid local data or interrupted.")
        print("STOP:", message, file=sys.stderr)
        print("Troubleshoot: status-demo, ECS events/stopped tasks, ALB target health, "
              "CloudWatch logs. Preserve partial state; see docs/interview-demo-guide.md.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
