"""Unit tests for traceai.vulnerability.vex module."""

import json

import pytest

from traceai.models import VulnerabilityFinding
from traceai.vulnerability.vex import (
    VexDocument,
    apply_vex_to_findings,
    check_component_linkage,
    load_vex,
    validate_vex_schema,
)

pytestmark = pytest.mark.unit


class TestLoadVex:
    """Tests for load_vex function."""

    def test_load_valid_vex(self, tmp_path, sample_vex_valid):
        """Loading a valid VEX file returns a VexDocument with statements."""
        vex_file = tmp_path / "valid.json"
        vex_file.write_text(json.dumps(sample_vex_valid), encoding="utf-8")

        doc = load_vex(vex_file)

        assert doc is not None
        assert doc.valid is True
        assert len(doc.statements) > 0
        assert doc.statements[0]["vulnerability_id"] == "CVE-2024-12345"


class TestValidateVexSchema:
    """Tests for validate_vex_schema function."""

    def test_validate_vex_schema_valid(self, sample_vex_valid):
        """A properly formed CycloneDX VEX document passes validation."""
        is_valid, errors = validate_vex_schema(sample_vex_valid)

        assert is_valid is True
        assert errors == []

    def test_validate_vex_schema_invalid(self, sample_vex_malformed):
        """A malformed VEX document fails schema validation."""
        is_valid, errors = validate_vex_schema(sample_vex_malformed)

        assert is_valid is False
        assert len(errors) > 0


class TestCheckComponentLinkage:
    """Tests for check_component_linkage function."""

    def test_check_component_linkage_correct(self, sample_vex_valid):
        """Linkage check passes when VEX references the target component."""
        result = check_component_linkage(
            sample_vex_valid,
            target_bom_ref="traceai-inference@1.0.0",
        )

        assert result is True

    def test_check_component_linkage_wrong(self, sample_vex_valid):
        """Linkage check fails when VEX does not reference the target."""
        result = check_component_linkage(
            sample_vex_valid,
            target_bom_ref="nonexistent-component@9.9.9",
        )

        assert result is False


class TestApplyVex:
    """Tests for apply_vex_to_findings function."""

    def test_apply_vex_suppresses_not_affected(self, sample_vex_valid):
        """Findings with not_affected status are suppressed after VEX application."""
        vex_doc = VexDocument(sample_vex_valid)

        findings = [
            VulnerabilityFinding(
                vulnerability_id="CVE-2024-12345",
                package_name="httptools",
                installed_version="0.6.0",
                severity="HIGH",
                scanner="trivy",
            ),
            VulnerabilityFinding(
                vulnerability_id="CVE-2024-99999",
                package_name="other-pkg",
                installed_version="1.0.0",
                severity="MEDIUM",
                scanner="trivy",
            ),
        ]

        remaining, stats = apply_vex_to_findings(findings, vex_doc)

        # CVE-2024-12345 should be suppressed (not_affected)
        assert stats["suppressed"] == 1
        assert stats["total_after"] == 1
        remaining_ids = [f.vulnerability_id for f in remaining]
        assert "CVE-2024-12345" not in remaining_ids
        assert "CVE-2024-99999" in remaining_ids
