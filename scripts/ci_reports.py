"""Upload-safe reports: no raw tracebacks, environment, paths, ARNs or image layers."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def test_summary(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {key: sum(int(s.get(key, "0")) for s in suites)
            for key in ["tests", "failures", "errors", "skipped"]}


def scan_summary(path):
    data = json.loads(path.read_text())
    if data.get("SchemaVersion") != 2 or not isinstance(data.get("Results"), list):
        raise ValueError("Invalid Trivy report; refusing to treat it as a clean scan")
    inventory = {result.get("Class"): len(result.get("Packages") or [])
                 for result in data["Results"]}
    if not inventory.get("os-pkgs") or not inventory.get("lang-pkgs"):
        raise ValueError("Missing OS/Python inventory coverage; refusing a clean scan")
    findings = [{"id": v["VulnerabilityID"], "package": v["PkgName"],
                 "installed": v["InstalledVersion"], "fixed": v.get("FixedVersion", ""),
                 "severity": v["Severity"], "class": result.get("Class", "unknown")}
                for result in data["Results"] for v in result.get("Vulnerabilities") or []]
    return {"counts": dict(Counter(v["severity"] for v in findings)), "findings": findings,
            "packages": inventory,
            "high_critical_gate_passed": not any(v["severity"] in {"HIGH", "CRITICAL"}
                                                 for v in findings)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["tests", "scan"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    report = test_summary(args.source) if args.kind == "tests" else scan_summary(args.source)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.kind == "scan" and not report["high_critical_gate_passed"]:
        print("HIGH/CRITICAL findings remain (including unfixed); inspect sanitized scan report.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
