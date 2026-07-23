"""Focused tests for Phase 3-5 scripts and new functionality."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))


# ===========================================================================
# Phase 3 Tests: RQ3 Agreement Views
# ===========================================================================

class TestPhase3Agreement:
    """Tests for Phase 3 scanner agreement analysis."""

    def test_extract_trivy_findings(self):
        """Trivy extraction produces correct finding structure."""
        from phase3_rq3_agreement import extract_trivy_findings

        sample = {
            "Results": [{
                "Vulnerabilities": [{
                    "VulnerabilityID": "CVE-2023-37920",
                    "PkgName": "certifi",
                    "InstalledVersion": "2022.9.24",
                    "Severity": "HIGH",
                    "FixedVersion": "2023.7.22",
                    "DataSource": {"ID": "ghsa"},
                }]
            }]
        }
        findings = extract_trivy_findings(sample)
        assert len(findings) == 1
        f = findings[0]
        assert f["primary_id"] == "CVE-2023-37920"
        assert f["pkg_name"] == "certifi"
        assert f["version"] == "2022.9.24"
        assert f["severity"] == "HIGH"
        assert f["purl"] == "pkg:pypi/certifi@2022.9.24"
        assert f["scanner"] == "trivy"

    def test_extract_grype_findings(self):
        """Grype extraction produces correct finding structure."""
        from phase3_rq3_agreement import extract_grype_findings

        sample = {
            "matches": [{
                "vulnerability": {
                    "id": "GHSA-xqr8-7jwr-rhp7",
                    "severity": "High",
                    "dataSource": "https://github.com/advisories/GHSA-xqr8-7jwr-rhp7",
                    "fix": {"versions": ["2023.7.22"], "state": "fixed"},
                },
                "relatedVulnerabilities": [{"id": "CVE-2023-37920"}],
                "artifact": {
                    "name": "certifi",
                    "version": "2022.9.24",
                    "purl": "pkg:pypi/certifi@2022.9.24",
                },
            }]
        }
        findings = extract_grype_findings(sample)
        assert len(findings) == 1
        f = findings[0]
        assert f["primary_id"] == "GHSA-xqr8-7jwr-rhp7"
        assert f["pkg_name"] == "certifi"
        assert f["purl"] == "pkg:pypi/certifi@2022.9.24"
        assert f["scanner"] == "grype"

    def test_compute_overlap(self):
        """Set overlap computation with Jaccard."""
        from phase3_rq3_agreement import compute_overlap

        a = {"CVE-1", "CVE-2", "CVE-3"}
        b = {"CVE-2", "CVE-3", "CVE-4"}
        result = compute_overlap(a, b, "test")
        assert result["intersection_size"] == 2
        assert result["union_size"] == 4
        assert result["jaccard"] == 0.5
        assert result["a_only_size"] == 1
        assert result["b_only_size"] == 1

    def test_alias_map_from_grype(self):
        """Alias map correctly extracts GHSA->CVE from relatedVulnerabilities."""
        from phase3_rq3_agreement import build_alias_map_from_scanner_output

        grype_data = {
            "matches": [{
                "vulnerability": {"id": "GHSA-xqr8-7jwr-rhp7"},
                "relatedVulnerabilities": [{"id": "CVE-2023-37920"}],
            }]
        }
        trivy_data = {"Results": []}

        alias_map = build_alias_map_from_scanner_output(grype_data, trivy_data)
        assert "GHSA-xqr8-7jwr-rhp7" in alias_map
        assert "CVE-2023-37920" in alias_map["GHSA-xqr8-7jwr-rhp7"]
        # Bidirectional
        assert "CVE-2023-37920" in alias_map
        assert "GHSA-xqr8-7jwr-rhp7" in alias_map["CVE-2023-37920"]

    def test_alias_expanded_overlap_computable(self):
        """Alias expansion increases overlap when aliases bridge namespaces."""
        from phase3_rq3_agreement import compute_alias_expanded_overlap

        trivy_ids = {"CVE-2023-37920", "CVE-2024-0001"}
        grype_ids = {"GHSA-xqr8-7jwr-rhp7", "GHSA-yyyy-0001"}
        alias_map = {
            "GHSA-xqr8-7jwr-rhp7": {"CVE-2023-37920"},
            "CVE-2023-37920": {"GHSA-xqr8-7jwr-rhp7"},
        }
        result = compute_alias_expanded_overlap(trivy_ids, grype_ids, alias_map)
        assert result["computable"] is True
        # CVE-2023-37920 and GHSA-xqr8-7jwr-rhp7 now overlap
        assert result["intersection_size"] >= 2

    def test_alias_expanded_not_computable(self):
        """Returns NOT_COMPUTABLE when alias map is empty."""
        from phase3_rq3_agreement import compute_alias_expanded_overlap

        result = compute_alias_expanded_overlap({"A"}, {"B"}, {})
        assert result["computable"] is False
        assert result["result"] == "NOT_COMPUTABLE"

    @pytest.mark.skipif(
        not (ROOT / "generated" / "rq3" / "phase3_agreement").exists(),
        reason="Phase 3 outputs not generated yet (run phase3_rq3_agreement.py first)"
    )
    def test_phase3_outputs_exist(self):
        """Phase 3 outputs were generated."""
        out_dir = ROOT / "generated" / "rq3" / "phase3_agreement"
        assert out_dir.exists()
        assert (out_dir / "rq3_agreement_summary.json").exists()
        assert (out_dir / "rq3_agreement_table.tex").exists()
        summary = json.loads(
            (out_dir / "rq3_agreement_summary.json").read_text(encoding="utf-8")
        )
        assert summary["trivy_total_findings"] == 54
        assert summary["grype_total_findings"] == 35
        assert summary["raw_primary_id_overlap"]["intersection_size"] == 4


# ===========================================================================
# Phase 4 Tests: RQ4 CPU Diagnostic
# ===========================================================================

class TestPhase4CPUDiagnostic:
    """Tests for Phase 4 outcome classification."""

    def test_classify_outcome_completed(self):
        """Status 200 classifies as COMPLETED."""
        from phase4_rq4_cpu_diagnostic import classify_outcome
        assert classify_outcome(200, False) == "COMPLETED"

    def test_classify_outcome_rate_limit(self):
        """Status 429 classifies as EXPECTED_RATE_LIMIT."""
        from phase4_rq4_cpu_diagnostic import classify_outcome
        assert classify_outcome(429, False) == "EXPECTED_RATE_LIMIT"

    def test_classify_outcome_circuit_breaker(self):
        """503 with circuit breaker detail classifies correctly."""
        from phase4_rq4_cpu_diagnostic import classify_outcome
        assert classify_outcome(503, False, "Circuit breaker open") == "EXPECTED_CIRCUIT_BREAKER"

    def test_classify_outcome_queue_full(self):
        """503 with queue full detail classifies correctly."""
        from phase4_rq4_cpu_diagnostic import classify_outcome
        assert classify_outcome(503, False, "Queue full") == "EXPECTED_QUEUE_REJECTION"

    def test_classify_outcome_timeout(self):
        """Timeout classifies correctly."""
        from phase4_rq4_cpu_diagnostic import classify_outcome
        assert classify_outcome(504, True) == "TIMEOUT"
        assert classify_outcome(504, False) == "TIMEOUT"

    def test_classify_outcome_server_error(self):
        """5xx without specific detail classifies as SERVER_ERROR."""
        from phase4_rq4_cpu_diagnostic import classify_outcome
        assert classify_outcome(500, False) == "SERVER_ERROR"
        assert classify_outcome(503, False, "some other error") == "SERVER_ERROR"

    @pytest.mark.skipif(
        not (ROOT / "generated" / "rq4" / "phase4_cpu_diagnostic").exists(),
        reason="Phase 4 outputs not generated yet (run phase4_rq4_cpu_diagnostic.py first)"
    )
    def test_phase4_outputs_exist(self):
        """Phase 4 outputs were generated with per-config metrics."""
        out_dir = ROOT / "generated" / "rq4" / "phase4_cpu_diagnostic"
        assert out_dir.exists()
        diag = json.loads(
            (out_dir / "rq4_cpu_diagnostic.json").read_text(encoding="utf-8")
        )
        assert "configurations" in diag
        for cid in ["C0", "C1", "C2", "C3"]:
            assert cid in diag["configurations"]
            cfg = diag["configurations"][cid]
            assert "outcome_counts" in cfg
            assert "latency_stats" in cfg
            assert cfg["n_requests"] == 20


# ===========================================================================
# Phase 5 Tests: GPU Runbook
# ===========================================================================

class TestPhase5GPURunbook:
    """Tests for Phase 5 GPU preflight checks."""

    def test_check_torch_installed(self):
        """torch_installed check passes (torch IS installed in this env)."""
        from phase5_gpu_runbook import check_torch_installed
        result = check_torch_installed()
        assert result.passed is True
        assert "PyTorch" in result.message

    def test_check_device_config_default(self):
        """device_config check passes with default 'auto'."""
        from phase5_gpu_runbook import check_torch_device_config
        result = check_torch_device_config()
        assert result.passed is True

    @pytest.mark.skipif(
        not (ROOT / "generated" / "gpu_runbook").exists(),
        reason="GPU runbook outputs not generated yet (run phase5_gpu_runbook.py first)"
    )
    def test_preflight_results_exist(self):
        """Phase 5 outputs were generated."""
        out_dir = ROOT / "generated" / "gpu_runbook"
        assert out_dir.exists()
        preflight = json.loads(
            (out_dir / "preflight_results.json").read_text(encoding="utf-8")
        )
        assert "recommended_device" in preflight
        assert preflight["recommended_device"] in ("cpu", "cuda")
        assert preflight["total_checks"] == 7
        assert (out_dir / "gpu_runbook.md").exists()
        assert (out_dir / "gpu_preflight_table.tex").exists()


# ===========================================================================
# Service endpoint test
# ===========================================================================

class TestServiceConfigEndpoint:
    """Test the PUT /configuration endpoint exists in app module."""

    def test_update_config_model_exists(self):
        """UpdateConfigRequest model is importable."""
        from traceai.service.app import UpdateConfigRequest
        req = UpdateConfigRequest(max_new_tokens=50, rate_limit_rpm=100)
        assert req.max_new_tokens == 50
        assert req.rate_limit_rpm == 100

    def test_controls_update(self):
        """ControlsManager.update_configuration works."""
        from traceai.service.controls import ControlsManager
        cm = ControlsManager(max_new_tokens=100, rate_limit_rpm=120)
        changes = cm.update_configuration(max_new_tokens=50)
        assert "max_new_tokens" in changes
        assert cm.max_new_tokens == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
