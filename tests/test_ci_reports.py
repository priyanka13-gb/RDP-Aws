"""Security-report gates must keep unfixed findings and exclude raw secrets."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("reports", Path(__file__).parents[1]
                                              / "scripts/ci_reports.py")
reports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reports)


@pytest.mark.parametrize("severity,passed", [("HIGH", False), ("CRITICAL", False), ("LOW", True)])
def test_scan_gate_includes_unfixed_without_raw_metadata(tmp_path, severity, passed):
    path = tmp_path / "scan.json"
    path.write_text(json.dumps({"SchemaVersion": 2, "ArtifactName": "sensitive-registry",
                               "Results": [{"Class": "lang-pkgs", "Packages": [{"Name": "app"}]},
                                           {"Class": "os-pkgs", "Packages": [{"Name": "os"}],
                                            "Vulnerabilities": [
                                   {"VulnerabilityID": "CVE-test", "PkgName": "test",
                                    "InstalledVersion": "1", "Severity": severity}]}]}))
    result = reports.scan_summary(path)
    assert result["high_critical_gate_passed"] == passed
    assert result["findings"][0]["fixed"] == ""
    assert "sensitive-registry" not in json.dumps(result)


def test_invalid_scan_is_not_a_clean_result(tmp_path):
    path = tmp_path / "scan.json"
    path.write_text('{}')
    with pytest.raises(ValueError):
        reports.scan_summary(path)


def test_test_report_drops_secret_failure_details(tmp_path):
    path = tmp_path / "tests.xml"
    path.write_text('<testsuites><testsuite tests="1" failures="1"><testcase name="secret">'
                    '<failure>private-token</failure></testcase></testsuite></testsuites>')
    result = reports.test_summary(path)
    assert result == {"tests": 1, "failures": 1, "errors": 0, "skipped": 0}
    assert "private-token" not in json.dumps(result)
