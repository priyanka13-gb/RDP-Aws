"""Credential-free Terraform validation in a fresh local copy; never initializes S3."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".tools" / "ci"
ROOTS = ["bootstrap", "envs/dev", "envs/ecr", "modules/network", "modules/alb",
         "modules/ecr", "modules/ecs_service", "modules/iam", "modules/observability"]
TEST_ROOTS = {"bootstrap", "envs/dev", "envs/ecr", "modules/network"}


def main():
    # A new copy/data directory avoids touching any developer backend metadata/state.
    import tempfile

    WORK.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="terraform-", dir=WORK))
    infra = sandbox / "infra"
    for source in (ROOT / "infra").rglob("*"):
        relative = source.relative_to(ROOT / "infra")
        if (source.is_file() and ".terraform" not in relative.parts
                and source.name != "backend.hcl"
                and (source.suffix == ".tf" or source.name.endswith(".tftest.hcl")
                     or source.name == ".terraform.lock.hcl")):
            target = infra / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("AWS_", "TF_VAR_", "TF_CLI_ARGS"))}
    env.update(AWS_EC2_METADATA_DISABLED="true", AWS_REGION="ap-southeast-2",
               AWS_DEFAULT_REGION="ap-southeast-2", TF_IN_AUTOMATION="1",
               AWS_CONFIG_FILE=str(sandbox / "empty-config"),
               AWS_SHARED_CREDENTIALS_FILE=str(sandbox / "empty-credentials"),
               TF_WORKSPACE="default")
    cache = WORK / "provider-cache"
    cache.mkdir(exist_ok=True)
    env["TF_PLUGIN_CACHE_DIR"] = str(cache.resolve())
    results = []
    reports = WORK / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    raw = WORK / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name in ROOTS:
        path = infra / name
        lock = path / ".terraform.lock.hcl"
        if not lock.exists():
            shutil.copyfile(infra / "envs/dev/.terraform.lock.hcl", lock)
        env["TF_DATA_DIR"] = str((sandbox / "data" / name).resolve())
        commands = [("init", ["init", "-backend=false", "-input=false", "-lockfile=readonly",
                              "-no-color"]), ("validate", ["validate", "-no-color"])]
        if name in TEST_ROOTS:
            commands.append(("mock-test", ["test", "-no-color"]))
        for stage, args in commands:
            p = subprocess.run(["terraform", "-chdir=" + str(path), *args], env=env,
                               capture_output=True, text=True, timeout=600)
            (raw / (name.replace("/", "-") + "-" + stage + ".log")).write_text(
                p.stdout + p.stderr, encoding="utf-8")
            result = {"root": name, "stage": stage, "passed": p.returncode == 0}
            if stage == "mock-test":
                count = re.search(r"Success! (\d+) passed, (\d+) failed", p.stdout)
                result["tests_passed"] = int(count[1]) if count else 0
                result["tests_failed"] = int(count[2]) if count else 0
            results.append(result)
            (reports / "terraform.json").write_text(json.dumps(results, indent=2) + "\n")
            print(name, stage, "passed" if p.returncode == 0 else "FAILED", flush=True)
            if p.returncode:
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
