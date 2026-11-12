"""Prepare a read-only demo plan from a clean commit. Never applies resources."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".tools" / "task24a"


def run(args, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / "preparation-error-private.log").write_text(result.stdout + result.stderr)
        raise SystemExit("Preparation failed; see ignored private log. No apply performed.")
    return result.stdout


def main():
    if run(["git", "status", "--porcelain"]).strip():
        raise SystemExit("Commit reviewed source first. Working tree must be clean.")
    revision = run(["git", "rev-parse", "HEAD"]).strip()
    DEST.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(AWS_PROFILE="rdp-dev", AWS_REGION="ap-southeast-2",
               AWS_DEFAULT_REGION="ap-southeast-2")
    # Read-only review: do not create an S3 lock object or modify remote state.
    run(["terraform", "-chdir=infra/envs/dev", "plan", "-input=false", "-lock=false",
         "-var-file=releases/task23.tfvars.example",
         "-out=../../../.tools/task24a/postcommit.tfplan", "-no-color"], env)
    plan = json.loads(run(["terraform", "-chdir=infra/envs/dev", "show", "-json",
                          "../../../.tools/task24a/postcommit.tfplan"], env))
    changes = [r for r in plan["resource_changes"] if r["mode"] == "managed"]
    expected = json.loads((ROOT / "evidence/task23/plan-summary.json").read_text())
    actual = sorted((r["address"], r["type"], r["change"]["actions"]) for r in changes)
    baseline = sorted((r["address"], r["type"], r["actions"]) for r in expected["resources"])
    if actual != baseline:
        raise SystemExit("STOP: resource actions differ from reviewed 34-create baseline.")
    task = next(r for r in changes if r["type"] == "aws_ecs_task_definition")
    image = json.loads(task["change"]["after"]["container_definitions"])[0]["image"]
    if not image.endswith("@" + expected["planned_image_digest"]):
        raise SystemExit("STOP: image digest differs from approved release.")
    if run(["git", "status", "--porcelain"]).strip():
        raise SystemExit("STOP: source changed during planning.")
    record = {"source_commit": revision, "creates": 34, "updates": 0,
              "deletes": 0, "replacements": 0, "image_digest": expected["planned_image_digest"],
              "plan_sha256": hashlib.sha256((DEST / "postcommit.tfplan").read_bytes()).hexdigest(),
              "apply_executed": False, "requires_deployment_approval": True}
    (DEST / "postcommit-verification.json").write_text(json.dumps(record, indent=2) + "\n")
    print("Post-commit review plan matches baseline; STOP before deployment approval.")


if __name__ == "__main__":
    main()
