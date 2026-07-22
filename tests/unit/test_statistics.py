"""Unit tests for traceai.analysis.statistics module."""

import numpy as np
import pytest

from traceai.analysis.statistics import (
    block_bootstrap_ci,
    compute_percentiles,
    wilcoxon_signed_rank,
    wilson_confidence_interval,
)

pytestmark = pytest.mark.unit


class TestWilsonCI:
    """Tests for wilson_confidence_interval function."""

    def test_wilson_ci_all_success(self):
        """100% success rate with large sample produces CI close to 1.0."""
        lower, upper = wilson_confidence_interval(successes=100, trials=100)

        assert lower > 0.95
        assert upper == 1.0

    def test_wilson_ci_partial(self):
        """Partial success returns meaningful bounds."""
        lower, upper = wilson_confidence_interval(successes=50, trials=100)

        assert 0.35 < lower < 0.50
        assert 0.50 < upper < 0.65
        assert lower < upper

    def test_wilson_ci_zero_trials(self):
        """Zero trials returns (0.0, 0.0)."""
        lower, upper = wilson_confidence_interval(successes=0, trials=0)

        assert lower == 0.0
        assert upper == 0.0


class TestBootstrapCI:
    """Tests for block_bootstrap_ci function."""

    def test_bootstrap_ci_returns_tuple(self):
        """Bootstrap CI returns a 3-tuple (estimate, lower, upper)."""
        data = np.random.default_rng(42).normal(100, 10, size=50)

        result = block_bootstrap_ci(data, statistic_fn=np.median, seed=42)

        assert isinstance(result, tuple)
        assert len(result) == 3
        estimate, lower, upper = result
        assert lower <= estimate <= upper


class TestComputePercentiles:
    """Tests for compute_percentiles function."""

    def test_compute_percentiles(self):
        """Percentiles are computed correctly for known data."""
        data = np.arange(1, 101, dtype=float)  # 1..100

        result = compute_percentiles(data)

        assert "p50" in result
        assert "p95" in result
        assert "p99" in result
        assert result["p50"] == pytest.approx(50.5, abs=0.5)
        assert result["p95"] == pytest.approx(95.05, abs=1.0)
        assert result["p99"] == pytest.approx(99.01, abs=1.0)


class TestWilcoxonPairedComparison:
    """Tests for wilcoxon_signed_rank function."""

    def test_wilcoxon_paired_comparison(self):
        """Wilcoxon test returns statistic and p-value for paired data."""
        rng = np.random.default_rng(42)
        baseline = rng.normal(100, 5, size=30)
        protected = baseline + rng.normal(2, 1, size=30)  # shifted by ~2

        result = wilcoxon_signed_rank(baseline, protected)

        assert result["statistic"] is not None
        assert result["p_value"] is not None
        assert 0.0 <= result["p_value"] <= 1.0
        assert result["effect_size_r"] is not None
