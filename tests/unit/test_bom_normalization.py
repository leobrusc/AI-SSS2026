"""Unit tests for traceai.bom.normalization module."""

import pytest

from traceai.bom.normalization import (
    compare_scanners,
    compute_coverage_metrics,
    normalize_bom,
    normalize_component,
)

pytestmark = pytest.mark.unit


class TestNormalizeComponent:
    """Tests for normalize_component function."""

    def test_normalize_component_lowercase(self):
        """Component name should be lowercased and stripped."""
        component = {
            "type": "library",
            "name": "  NumPy  ",
            "version": " 1.26.0 ",
        }
        result = normalize_component(component)

        assert result["name"] == "numpy"
        assert result["version"] == "1.26.0"
        assert result["type"] == "library"


class TestNormalizeBom:
    """Tests for normalize_bom function."""

    def test_normalize_bom_sorted(self):
        """Normalized BOM components should be sorted by (type, name, version)."""
        bom = {
            "components": [
                {"type": "library", "name": "Zlib", "version": "1.0"},
                {"type": "framework", "name": "FastAPI", "version": "0.100"},
                {"type": "library", "name": "Alpha", "version": "2.0"},
            ]
        }
        result = normalize_bom(bom)

        names = [c["name"] for c in result]
        assert names == ["fastapi", "alpha", "zlib"]


class TestComputeCoverage:
    """Tests for compute_coverage_metrics function."""

    def test_compute_coverage_full_match(self):
        """Full match: all ground truth found in generated."""
        gt = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        gen = [{"name": "a"}, {"name": "b"}, {"name": "c"}]

        metrics = compute_coverage_metrics(gt, gen)

        assert metrics["node_coverage"] == 1.0
        assert metrics["jaccard_similarity"] == 1.0
        assert metrics["matched_count"] == 3
        assert metrics["unmatched_ground_truth"] == []

    def test_compute_coverage_partial(self):
        """Partial match: only some ground truth found."""
        gt = [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}]
        gen = [{"name": "a"}, {"name": "b"}, {"name": "x"}]

        metrics = compute_coverage_metrics(gt, gen)

        assert metrics["node_coverage"] == 0.5  # 2 of 4
        assert metrics["matched_count"] == 2
        assert "c" in metrics["unmatched_ground_truth"]
        assert "d" in metrics["unmatched_ground_truth"]
        assert "x" in metrics["extra_generated"]


class TestCompareScanners:
    """Tests for compare_scanners function."""

    def test_compare_scanners_jaccard(self):
        """Jaccard similarity between two scanner BOMs."""
        bom_a = {
            "components": [
                {"type": "library", "name": "numpy", "version": "1.26"},
                {"type": "library", "name": "pandas", "version": "2.0"},
                {"type": "library", "name": "scipy", "version": "1.11"},
            ]
        }
        bom_b = {
            "components": [
                {"type": "library", "name": "numpy", "version": "1.26"},
                {"type": "library", "name": "pandas", "version": "2.0"},
                {"type": "library", "name": "torch", "version": "2.1"},
            ]
        }

        result = compare_scanners(bom_a, bom_b, "syft", "trivy")

        assert result["syft_count"] == 3
        assert result["trivy_count"] == 3
        assert result["intersection_count"] == 2
        assert result["union_count"] == 4
        assert result["jaccard_similarity"] == 0.5
        assert "scipy" in result["unique_to_syft"]
        assert "torch" in result["unique_to_trivy"]
