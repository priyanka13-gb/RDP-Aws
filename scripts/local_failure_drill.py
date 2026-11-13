"""Bounded local-only Docker failures; no AWS calls, host ports, mounts or volumes."""

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_IMAGE = "rdp-release:git-9b18a3109aa2"
WORK = Path(__file__).resolve().parents[1] / ".tools" / "local-failure-drill"


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Local Docker operation failed; raw output withheld.")
    return result.stdout.strip()


def scenario_command(name):
    if name == "startup_failure":
        return ["python", "-c", "raise RuntimeError('LOCAL_DRILL_STARTUP_FAILURE')"]
    if name in {"healthy_baseline", "healthy_recovery"}:
        return []  # Use the actual image command unchanged.
    if name not in {"unhealthy_application", "failed_readiness"}:
        raise ValueError("Unknown local scenario")
    route = "/health" if name == "unhealthy_application" else "/ready"
    program = (
        "import uvicorn; from app.main import create_app,Settings; "
        "from fastapi.responses import JSONResponse; app=create_app(Settings());\n"
        "@app.middleware('http')\n"
        "async def inject(request,call_next):\n"
        f" if request.url.path=={route!r}: return JSONResponse(status_code=503,"
        "content={'status':'local_drill_failure'})\n"
        " return await call_next(request)\n"
        "uvicorn.run(app,host='0.0.0.0',port=8000,access_log=False)"
    )
    return ["python", "-c", program]


def expected(name):
    return {
        "unhealthy_application": (503, 200, "unhealthy"),
        "failed_readiness": (200, 503, "healthy"),
        "healthy_baseline": (200, 200, "healthy"),
        "healthy_recovery": (200, 200, "healthy"),
    }[name]


def run_drill(image=DEFAULT_IMAGE):
    info = json.loads(docker("image", "inspect", image))[0]
    if (
        info["Architecture"] != "amd64"
        or info["Os"] != "linux"
        or info["Config"]["User"] != "10001:10001"
    ):
        raise RuntimeError("Require the reviewed local Linux AMD64 non-root image.")
    WORK.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "scope": "local Docker only",
        "image_id": info["Id"],
        "aws_failures_injected": False,
        "ecs_rollback_verified": False,
        "passed": False,
        "scenarios": [],
    }
    token = uuid.uuid4().hex
    containers = []
    try:
        for name in [
            "healthy_baseline",
            "unhealthy_application",
            "failed_readiness",
            "startup_failure",
            "healthy_recovery",
        ]:
            row = {"scenario": name, "started_at": datetime.now(UTC).isoformat()}
            report["scenarios"].append(row)
            health = (
                "python -c 'import urllib.request; "
                'urllib.request.urlopen("http://127.0.0.1:8000/health",timeout=2).close()' + "'"
            )
            args = [
                "run",
                "-d",
                "--network",
                "none",
                "--memory",
                "512m",
                "--cpus",
                "0.25",
                "--label",
                "rdp.local-drill=" + token,
                "-e",
                "DATABASE_URL=",
                "-e",
                "DATABASE_PASSWORD_FILE=",
                "--health-cmd",
                health,
                "--health-interval",
                "1s",
                "--health-timeout",
                "3s",
                "--health-retries",
                "2",
                image,
                *scenario_command(name),
            ]
            container = docker(*args)
            containers.append(container)
            if name == "startup_failure":
                for _ in range(30):
                    state = json.loads(docker("inspect", container))[0]["State"]
                    if not state["Running"]:
                        break
                    time.sleep(1)
                if state["Running"] or state["ExitCode"] == 0:
                    raise RuntimeError("Startup failure not detected.")
                row.update(exit_code=state["ExitCode"], http_server_started=False)
            else:
                code = (
                    "import urllib.request,urllib.error,json; result={};\n"
                    "for path in ['/health','/ready']:\n"
                    " try: r=urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=3)\n"
                    " except urllib.error.HTTPError as e: r=e\n"
                    " result[path]=r.status\n"
                    "print(json.dumps(result))"
                )
                for _ in range(30):
                    try:
                        statuses = json.loads(docker("exec", container, "python", "-c", code))
                        break
                    except RuntimeError:
                        time.sleep(1)
                else:
                    raise RuntimeError("Local scenario failed to start HTTP server.")
                health_status, ready_status, container_health = expected(name)
                if statuses != {"/health": health_status, "/ready": ready_status}:
                    raise RuntimeError("Unexpected health/readiness behavior.")
                for _ in range(30):
                    state = json.loads(docker("inspect", container))[0]["State"]
                    if state["Health"]["Status"] == container_health:
                        break
                    time.sleep(1)
                if state["Health"]["Status"] != container_health:
                    raise RuntimeError("Container health status mismatch.")
                row.update(http=statuses, container_health=container_health)
            row["observed_at"] = datetime.now(UTC).isoformat()
            print(name, "observed as expected", flush=True)
        report["passed"] = True
    finally:
        cleanup_ok = True
        for container in containers:
            try:
                obj = json.loads(docker("inspect", container))[0]
                if obj["Config"].get("Labels", {}).get("rdp.local-drill") != token:
                    raise RuntimeError("Refusing removal of a container not owned by this drill.")
                docker("rm", "-f", container)
            except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                cleanup_ok = False
        report["own_containers_removed"] = cleanup_ok
        report["finished_at"] = datetime.now(UTC).isoformat()
        (WORK / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if not cleanup_ok:
            raise RuntimeError("Local drill cleanup incomplete; inspect labeled local containers.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args()
    try:
        run_drill(args.image)
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
        KeyboardInterrupt,
    ):
        print(
            "Local drill failed; see ignored .tools/local-failure-drill/report.json. "
            "No AWS operation was performed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
