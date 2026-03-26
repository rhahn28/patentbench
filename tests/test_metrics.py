"""Unit tests for PatentBench metrics and statistical methods."""

from __future__ import annotations

import math

import pytest

from patentbench.metrics import MetricsCalculator


class TestBootstrapCI:
    """Tests for bootstrap confidence interval computation."""

    def test_basic_ci(self) -> None:
        scores = [0.8, 0.85, 0.9, 0.75, 0.92, 0.88, 0.7, 0.95, 0.82, 0.87]
        result = MetricsCalculator.bootstrap_ci(scores)
        assert result.count == 10
        assert 0.8 < result.value < 0.9  # Mean should be ~0.844
        assert result.details["ci_lower"] < result.value
        assert result.details["ci_upper"] > result.value
        assert result.details["ci_level"] == 0.95

    def test_empty_scores(self) -> None:
        result = MetricsCalculator.bootstrap_ci([])
        assert result.value == 0.0
        assert result.count == 0

    def test_single_value(self) -> None:
        result = MetricsCalculator.bootstrap_ci([0.9])
        assert result.value == 0.9
        # CI should be [0.9, 0.9] for single value
        assert result.details["ci_lower"] == 0.9
        assert result.details["ci_upper"] == 0.9

    def test_perfect_scores(self) -> None:
        result = MetricsCalculator.bootstrap_ci([1.0] * 20)
        assert result.value == 1.0
        assert result.details["ci_lower"] == 1.0
        assert result.details["ci_upper"] == 1.0


class TestWilcoxonSignedRank:
    """Tests for Wilcoxon signed-rank test."""

    def test_identical_scores(self) -> None:
        scores = [0.8, 0.9, 0.7, 0.85, 0.95]
        result = MetricsCalculator.wilcoxon_signed_rank(scores, scores)
        assert result.details["note"] == "no differences"
        assert result.value == 1.0

    def test_clearly_different(self) -> None:
        a = [0.9, 0.95, 0.88, 0.92, 0.87, 0.91, 0.93, 0.89, 0.94, 0.90]
        b = [0.5, 0.55, 0.48, 0.52, 0.47, 0.51, 0.53, 0.49, 0.54, 0.50]
        result = MetricsCalculator.wilcoxon_signed_rank(a, b)
        assert result.value < 0.05  # Should be significant

    def test_mismatched_lengths(self) -> None:
        result = MetricsCalculator.wilcoxon_signed_rank([0.8], [0.8, 0.9])
        assert result.count == 0

    def test_empty(self) -> None:
        result = MetricsCalculator.wilcoxon_signed_rank([], [])
        assert result.count == 0


class TestCohensD:
    """Tests for Cohen's d effect size."""

    def test_no_difference(self) -> None:
        scores = [0.8, 0.85, 0.9, 0.75]
        result = MetricsCalculator.cohens_d(scores, scores)
        assert result.value == 0.0
        assert result.details["interpretation"] == "negligible"

    def test_large_effect(self) -> None:
        a = [0.9, 0.95, 0.88, 0.92]
        b = [0.3, 0.35, 0.28, 0.32]
        result = MetricsCalculator.cohens_d(a, b)
        assert abs(result.value) > 0.8
        assert result.details["interpretation"] == "large"

    def test_empty(self) -> None:
        result = MetricsCalculator.cohens_d([], [0.5])
        assert result.value == 0.0
        assert result.count == 0

    def test_symmetry(self) -> None:
        a = [0.9, 0.8, 0.85]
        b = [0.5, 0.4, 0.45]
        d1 = MetricsCalculator.cohens_d(a, b)
        d2 = MetricsCalculator.cohens_d(b, a)
        assert abs(d1.value + d2.value) < 1e-10  # Should be opposite signs


class TestBonferroniCorrection:
    """Tests for Bonferroni p-value correction."""

    def test_basic_correction(self) -> None:
        p_values = [0.01, 0.03, 0.05, 0.001]
        result = MetricsCalculator.bonferroni_correction(p_values)
        assert result.count == 4
        # 0.01 * 4 = 0.04 < 0.05 → significant
        # 0.001 * 4 = 0.004 < 0.05 → significant
        # 0.03 * 4 = 0.12 > 0.05 → not significant
        # 0.05 * 4 = 0.20 > 0.05 → not significant
        assert result.value == 2.0  # 2 significant after correction

    def test_no_significant(self) -> None:
        p_values = [0.1, 0.2, 0.3]
        result = MetricsCalculator.bonferroni_correction(p_values)
        assert result.value == 0.0

    def test_all_significant(self) -> None:
        p_values = [0.001, 0.002]
        result = MetricsCalculator.bonferroni_correction(p_values)
        assert result.value == 2.0

    def test_empty(self) -> None:
        result = MetricsCalculator.bonferroni_correction([])
        assert result.count == 0

    def test_cap_at_one(self) -> None:
        """Adjusted p-values should be capped at 1.0."""
        p_values = [0.8, 0.9]
        result = MetricsCalculator.bonferroni_correction(p_values)
        for adj_p in result.details["adjusted_p_values"]:
            assert adj_p <= 1.0
