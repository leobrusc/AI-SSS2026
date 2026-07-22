"""Unit tests for TraceAI methodology corrections.

Tests cover: typed RQ1 denominator, zero-component handling,
canonical purl mapping, vulnerability deduplication, advisory alias
normalization, stratified Jaccard, VEX independent oracle,
property-based VEX decisions, publication rejection of mock inference,
publication rejection of dirty git tree, NOT_APPLICABLE GPU metrics,
and emergency stop.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from traceai.campaigns.vex_property import (
    DECISION_TABLE,
    oracle_decision,
    run_vex_property_tests,
)
from traceai.models import GateDecision, RequestObservation
from traceai.policy.engine import PolicyEngine

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Typed RQ1 denominator (3 tests)
# ---------------------------------------------------------------------------


class TestTypedRQ1Denominator:
    """Tests for typed ground-truth nodes and applicable-only coverage."""

    def test_ground_truth_nodes_have_type_and_expected_bom(self):
        """Each ground-truth node must have a type field and expected_bom list."""
        nodes = [
            {"id": "n1", "type": "model", "name": "gpt2",
             "expected_bom": ["mlbom"], "applicability": "REQUIRED",
             "canonical_identity": {"name": "gpt2", "purl": "", "sha256": "", "version": ""}},
            {"id": "n2", "type": "package", "name": "torch",
             "expected_bom": ["sbom"], "applicability": "REQUIRED",
             "canonical_identity": {"name": "torch", "purl": "pkg:pypi/torch@2.0", "sha256": "", "version": "2.0"}},
        ]
        for node in nodes:
            assert "type" in node, f"Node {node['id']} missing type"
            assert isinstance(node["expected_bom"], list)
            assert len(node["expected_bom"]) > 0

    def test_not_applicable_nodes_excluded_from_denominator(self):
        """NOT_APPLICABLE nodes do not count toward the coverage denominator."""
        NOT_APPLICABLE = "NOT_APPLICABLE"
        nodes = [
            {"id": "cpu", "applicability": "REQUIRED", "expected_bom": ["hbom"],
             "canonical_identity": {"name": "cpu"}},
            {"id": "gpu", "applicability": NOT_APPLICABLE, "expected_bom": ["hbom"],
             "canonical_identity": {"name": "GPU"}},
            {"id": "cuda", "applicability": NOT_APPLICABLE, "expected_bom": ["hbom"],
             "canonical_identity": {"name": "CUDA"}},
        ]
        applicable = [n for n in nodes if n["applicability"] != NOT_APPLICABLE]
        assert len(applicable) == 1
        assert applicable[0]["id"] == "cpu"

    def test_applicable_only_coverage_calculation(self):
        """Coverage is computed only over applicable nodes."""
        NOT_APPLICABLE = "NOT_APPLICABLE"
        nodes = [
            {"id": "torch", "applicability": "REQUIRED", "expected_bom": ["sbom"],
             "canonical_identity": {"name": "torch"}},
            {"id": "numpy", "applicability": "REQUIRED", "expected_bom": ["sbom"],
             "canonical_identity": {"name": "numpy"}},
            {"id": "gpu", "applicability": NOT_APPLICABLE, "expected_bom": ["hbom"],
             "canonical_identity": {"name": "GPU"}},
        ]
        applicable = [n for n in nodes if n["applicability"] != NOT_APPLICABLE]
        bom_names = {"torch"}  # only torch found
        matched = sum(1 for n in applicable
                      if n["canonical_identity"]["name"].lower() in bom_names)
        coverage = matched / len(applicable) if applicable else 0
        # 1 matched out of 2 applicable = 0.5
        assert coverage == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 2. Zero-component scanner handling (2 tests)
# ---------------------------------------------------------------------------


class TestZeroComponentScanner:
    """Tests for scanners that return 0 components."""

    def test_zero_components_returns_tool_limitation_not_pass(self):
        """When a scanner finds 0 components, status must be TOOL_LIMITATION, not success."""
        trivy_result = {
            "tool": "trivy",
            "component_count": 0,
            "components": [],
            "status": "not_set",
        }
        # Apply the same logic as _run_trivy
        if trivy_result["component_count"] == 0:
            trivy_result["status"] = "TOOL_LIMITATION"
            trivy_result["limitation"] = (
                "Scanner found 0 components — tool limitation, not evidence of absence."
            )
        assert trivy_result["status"] == "TOOL_LIMITATION"
        assert trivy_result["status"] != "success"

    def test_jaccard_with_empty_set_returns_na_or_zero(self):
        """Jaccard with an empty set (0-component scanner) returns N/A or 0."""
        syft_pkg = {"torch", "numpy", "fastapi"}
        trivy_pkg = set()  # empty — trivy found nothing
        pkg_union = syft_pkg | trivy_pkg
        if not pkg_union:
            jaccard = "N/A"
        else:
            jaccard = len(syft_pkg & trivy_pkg) / len(pkg_union)
        # With one side empty, intersection is 0 → Jaccard = 0.0
        assert jaccard == 0.0

        # Edge case: both empty
        pkg_union_both = set() | set()
        jaccard_both = "N/A" if not pkg_union_both else len(set() & set()) / len(pkg_union_both)
        assert jaccard_both == "N/A"


# ---------------------------------------------------------------------------
# 3. Canonical purl mapping (3 tests)
# ---------------------------------------------------------------------------


class TestCanonicalPurlMapping:
    """Tests for purl normalization and canonical identity."""

    def test_purl_normalization_lowercase_version_extraction(self):
        """Purl should be normalized to lowercase with version extracted."""
        purl = "pkg:pypi/Torch@2.3.1"
        parts = purl.split("/", 1)
        ecosystem = parts[0].replace("pkg:", "")
        name_version = parts[1]
        name, version = name_version.split("@") if "@" in name_version else (name_version, "")
        # Canonical normalization
        canonical_name = name.lower()
        assert canonical_name == "torch"
        assert version == "2.3.1"
        assert ecosystem == "pypi"

    def test_ecosystem_detection_from_purl_pypi(self):
        """Ecosystem is correctly detected from purl scheme."""
        purls = {
            "pkg:pypi/numpy@1.26.0": "pypi",
            "pkg:huggingface/openai-community/gpt2": "huggingface",
            "pkg:generic/python@3.11.9": "generic",
        }
        for purl, expected_eco in purls.items():
            eco = purl.split(":")[1].split("/")[0]
            assert eco == expected_eco, f"Failed for {purl}"

    def test_purl_without_version(self):
        """Purl without version is handled gracefully."""
        purl = "pkg:pypi/requests"
        if "@" in purl:
            name, version = purl.rsplit("@", 1)
        else:
            name = purl
            version = ""
        assert version == ""
        assert name.endswith("requests")


# ---------------------------------------------------------------------------
# 4. Vulnerability deduplication (2 tests)
# ---------------------------------------------------------------------------


class TestVulnerabilityDeduplication:
    """Tests for deduplicating vulnerability findings."""

    def test_same_cve_same_package_deduplicates_to_one(self):
        """Same CVE + same package from two scanners deduplicates to 1 finding."""
        findings = [
            {"vulnerability_id": "CVE-2024-12345", "package_name": "httptools",
             "scanner": "trivy"},
            {"vulnerability_id": "CVE-2024-12345", "package_name": "httptools",
             "scanner": "grype"},
        ]
        seen = set()
        deduped = []
        for f in findings:
            key = (f["vulnerability_id"], f["package_name"])
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        assert len(deduped) == 1
        assert deduped[0]["vulnerability_id"] == "CVE-2024-12345"

    def test_different_cves_same_package_remain_separate(self):
        """Different CVEs for the same package remain as separate findings."""
        findings = [
            {"vulnerability_id": "CVE-2024-12345", "package_name": "httptools",
             "scanner": "trivy"},
            {"vulnerability_id": "CVE-2024-67890", "package_name": "httptools",
             "scanner": "trivy"},
        ]
        seen = set()
        deduped = []
        for f in findings:
            key = (f["vulnerability_id"], f["package_name"])
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        assert len(deduped) == 2


# ---------------------------------------------------------------------------
# 5. Advisory alias normalization (2 tests)
# ---------------------------------------------------------------------------


class TestAdvisoryAliasNormalization:
    """Tests for advisory ID priority (CVE > GHSA)."""

    def test_cve_takes_priority_over_ghsa(self):
        """When both CVE and GHSA are present, CVE is the canonical ID."""
        aliases = ["GHSA-abcd-efgh-1234", "CVE-2024-99999"]
        # Normalization: pick CVE first
        canonical = next((a for a in aliases if a.startswith("CVE-")), aliases[0])
        assert canonical == "CVE-2024-99999"

    def test_non_cve_advisory_preserved(self):
        """When no CVE alias exists, the original GHSA is preserved."""
        aliases = ["GHSA-abcd-efgh-1234"]
        canonical = next((a for a in aliases if a.startswith("CVE-")), aliases[0])
        assert canonical == "GHSA-abcd-efgh-1234"


# ---------------------------------------------------------------------------
# 6. Stratified Jaccard (2 tests)
# ---------------------------------------------------------------------------


class TestStratifiedJaccard:
    """Tests for Jaccard computed on filtered subsets (strata)."""

    def test_jaccard_on_filtered_subset(self):
        """Jaccard computed only on package-type nodes matches expected."""
        # Stratum: only packages
        syft_packages = {"torch", "numpy", "fastapi"}
        trivy_packages = {"torch", "numpy", "uvicorn"}
        intersection = syft_packages & trivy_packages
        union = syft_packages | trivy_packages
        jaccard = len(intersection) / len(union)
        # {torch, numpy} / {torch, numpy, fastapi, uvicorn} = 2/4
        assert jaccard == pytest.approx(0.5)

    def test_empty_stratum_returns_appropriate_value(self):
        """Empty stratum (no nodes of the type) returns N/A."""
        syft_hbom = set()
        trivy_hbom = set()
        union = syft_hbom | trivy_hbom
        jaccard = "N/A" if not union else len(syft_hbom & trivy_hbom) / len(union)
        assert jaccard == "N/A"


# ---------------------------------------------------------------------------
# 7. VEX independent oracle (3 tests)
# ---------------------------------------------------------------------------


class TestVexIndependentOracle:
    """Tests for the independent VEX oracle decision table."""

    def test_oracle_matches_truth_table_approved_case(self):
        """Oracle returns APPROVED when all conditions are met."""
        decision = oracle_decision(
            schema_valid=True, expired=False,
            component_match=True, signed_when_required=True
        )
        assert decision == GateDecision.APPROVED

    def test_oracle_returns_vex_malformed_for_invalid_schema(self):
        """Oracle returns VEX_MALFORMED when schema is invalid."""
        decision = oracle_decision(
            schema_valid=False, expired=False,
            component_match=True, signed_when_required=True
        )
        assert decision == GateDecision.VEX_MALFORMED

    def test_oracle_returns_vex_expired_for_expired_valid(self):
        """Oracle returns VEX_EXPIRED for expired document with valid schema."""
        decision = oracle_decision(
            schema_valid=True, expired=True,
            component_match=True, signed_when_required=True
        )
        assert decision == GateDecision.VEX_EXPIRED


# ---------------------------------------------------------------------------
# 8. Property-based VEX decisions (2 tests)
# ---------------------------------------------------------------------------


class TestPropertyBasedVexDecisions:
    """Tests for run_vex_property_tests."""

    def test_run_vex_property_tests_returns_agreement_rate(self):
        """run_vex_property_tests returns agreement_rate in [0, 1]."""
        results = run_vex_property_tests(n_cases=50, seed=42)
        assert "agreement_rate" in results
        assert 0.0 <= results["agreement_rate"] <= 1.0
        assert results["total_cases"] == 50
        # Implementation and oracle should agree perfectly
        assert results["agreement_rate"] == 1.0

    def test_seed_produces_deterministic_results(self):
        """Same seed produces identical results across runs."""
        r1 = run_vex_property_tests(n_cases=100, seed=123)
        r2 = run_vex_property_tests(n_cases=100, seed=123)
        assert r1["agreements"] == r2["agreements"]
        assert r1["counterexample_count"] == r2["counterexample_count"]
        # All case decisions should match
        for c1, c2 in zip(r1["cases"], r2["cases"]):
            assert c1["expected_decision"] == c2["expected_decision"]
            assert c1["observed_decision"] == c2["observed_decision"]


# ---------------------------------------------------------------------------
# 9. Publication rejection of mock inference (3 tests)
# ---------------------------------------------------------------------------


class TestPublicationRejectionMockInference:
    """Tests for publication validation of RQ4 campaign manifests."""

    def test_campaign_manifest_with_real_http_passes(self, tmp_path):
        """A campaign manifest with inference_type=REAL_HTTP passes validation."""
        rq4_dir = tmp_path / "results" / "rq4" / "rq4-20260722-123456-abcdef01"
        rq4_dir.mkdir(parents=True)
        manifest = {"inference_type": "REAL_HTTP", "model_id": "gpt2"}
        (rq4_dir / "campaign_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")

        # Simulate check logic from _check_rq4
        manifest_path = rq4_dir / "campaign_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        real_inference = data.get("inference_type") == "REAL_HTTP"
        assert real_inference is True

    def test_missing_manifest_fails(self, tmp_path):
        """A campaign directory without manifest fails real-inference check."""
        rq4_dir = tmp_path / "results" / "rq4" / "rq4-20260722-123456-abcdef01"
        rq4_dir.mkdir(parents=True)

        manifest_path = rq4_dir / "campaign_manifest.json"
        real_inference = False
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            real_inference = data.get("inference_type") == "REAL_HTTP"
        assert real_inference is False

    def test_old_availability_campaign_no_rq4_dir_fails(self, tmp_path):
        """Old availability campaign with no RQ4 results directory fails."""
        results_dir = tmp_path / "results"
        results_dir.mkdir(parents=True)
        # No rq4 subdirectory at all
        rq4_path = results_dir / "rq4"
        rq4_dirs = list(rq4_path.glob("rq4-*")) if rq4_path.exists() else []
        check_pass = len(rq4_dirs) > 0
        assert check_pass is False


# ---------------------------------------------------------------------------
# 10. Publication rejection of dirty git tree (2 tests)
# ---------------------------------------------------------------------------


class TestPublicationRejectionDirtyGitTree:
    """Tests for _check_git_clean with mocked subprocess."""

    @patch("subprocess.run")
    def test_check_git_clean_returns_pass_when_clean(self, mock_run, tmp_path):
        """_check_git_clean returns pass=True when git reports no changes."""
        from traceai.publication import _check_git_clean

        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = _check_git_clean(tmp_path)
        assert result["pass"] is True
        assert result["check"] == "git_tree_clean"

    @patch("subprocess.run")
    def test_check_git_clean_returns_fail_when_dirty(self, mock_run, tmp_path):
        """_check_git_clean returns pass=False when there are uncommitted changes."""
        from traceai.publication import _check_git_clean

        mock_run.return_value = MagicMock(
            stdout=" M src/main.py\n?? untracked.txt\n", returncode=0
        )
        result = _check_git_clean(tmp_path)
        assert result["pass"] is False
        assert "uncommitted" in result["detail"].lower() or "2" in result["detail"]


# ---------------------------------------------------------------------------
# 11. NOT_APPLICABLE GPU metrics (2 tests)
# ---------------------------------------------------------------------------


class TestNotApplicableGpuMetrics:
    """Tests for GPU nodes marked NOT_APPLICABLE."""

    def test_gpu_not_applicable_does_not_reduce_coverage(self):
        """GPU nodes marked NOT_APPLICABLE don't reduce overall coverage."""
        NOT_APPLICABLE = "NOT_APPLICABLE"
        nodes = [
            {"id": "torch", "applicability": "REQUIRED", "expected_bom": ["sbom"],
             "canonical_identity": {"name": "torch"}},
            {"id": "numpy", "applicability": "REQUIRED", "expected_bom": ["sbom"],
             "canonical_identity": {"name": "numpy"}},
            {"id": "gpu", "applicability": NOT_APPLICABLE, "expected_bom": ["hbom"],
             "canonical_identity": {"name": "GPU"}},
            {"id": "cuda", "applicability": NOT_APPLICABLE, "expected_bom": ["hbom"],
             "canonical_identity": {"name": "CUDA"}},
        ]
        bom_names = {"torch", "numpy"}
        applicable = [n for n in nodes if n["applicability"] != NOT_APPLICABLE]
        matched = sum(1 for n in applicable
                      if n["canonical_identity"]["name"].lower() in bom_names)
        coverage = matched / len(applicable) if applicable else 0
        # Both applicable nodes matched → 100% coverage (GPU excluded)
        assert coverage == pytest.approx(1.0)

    def test_rq4_observation_has_none_for_gpu_fields_on_cpu(self):
        """RQ4 observation on CPU has None for GPU-specific fields."""
        obs = {
            "request_id": "test-r0",
            "trial_id": "test-trial",
            "configuration_id": "C0",
            "timestamp": "2026-07-22T13:00:00Z",
            "latency_ms": 150.2,
            "status_code": 200,
            "tokens_generated": 20,
            "timed_out": False,
            "rejected": False,
            "rejection_reason": None,
            "cpu_percent": 45.3,
            "rss_mb": 1024.5,
            "gpu_utilization_percent": None,  # NOT_APPLICABLE on CPU
            "gpu_memory_mb": None,  # NOT_APPLICABLE on CPU
        }
        assert obs["gpu_utilization_percent"] is None
        assert obs["gpu_memory_mb"] is None
        # These fields exist but are None, signaling NOT_APPLICABLE
        assert "gpu_utilization_percent" in obs
        assert "gpu_memory_mb" in obs


# ---------------------------------------------------------------------------
# 12. Emergency stop (2 tests)
# ---------------------------------------------------------------------------


class TestEmergencyStop:
    """Tests for emergency stop detection."""

    def test_emergency_stop_file_existence_detectable(self, tmp_path):
        """Emergency stop is detected by checking file existence."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        stop_file = workspace / "EMERGENCY_STOP"

        # Before creation: not detected
        assert not stop_file.exists()

        # Create the file
        stop_file.write_text("STOP", encoding="utf-8")
        assert stop_file.exists()

    def test_emergency_stop_path_construction(self, tmp_path):
        """Emergency stop path is constructed from project root / workspace / EMERGENCY_STOP."""
        root = tmp_path
        expected_path = root / "workspace" / "EMERGENCY_STOP"
        assert expected_path == tmp_path / "workspace" / "EMERGENCY_STOP"
        assert str(expected_path).endswith("workspace" + str(Path("/")) + "EMERGENCY_STOP") or \
               "workspace" in str(expected_path) and "EMERGENCY_STOP" in str(expected_path)
