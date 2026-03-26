"""Metric computation for PatentBench evaluations.

Implements accuracy, F1 score, Cohen's Kappa, and composite quality scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class MetricResult:
    """A single metric computation result."""

    name: str
    value: float
    count: int
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def percentage(self) -> float:
        return self.value * 100.0


@dataclass
class EvaluationResult:
    """Complete evaluation results for a single test case."""

    case_id: str
    model_name: str
    model_output: str
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    layer_scores: dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    passed: bool = False
    error: str | None = None

    def add_metric(self, metric: MetricResult) -> None:
        self.metrics[metric.name] = metric


class MetricsCalculator:
    """Computes all PatentBench metrics."""

    @staticmethod
    def accuracy(predictions: list[Any], references: list[Any]) -> MetricResult:
        """Compute exact-match accuracy."""
        if not predictions:
            return MetricResult(name="accuracy", value=0.0, count=0)
        correct = sum(1 for p, r in zip(predictions, references) if p == r)
        return MetricResult(
            name="accuracy",
            value=correct / len(predictions),
            count=len(predictions),
            details={"correct": correct, "total": len(predictions)},
        )

    @staticmethod
    def f1_score(
        predictions: list[set[str]], references: list[set[str]]
    ) -> MetricResult:
        """Compute macro-averaged F1 score for set-valued predictions.

        Useful for evaluating extraction tasks like claim identification
        or rejection type classification.
        """
        if not predictions:
            return MetricResult(name="f1_score", value=0.0, count=0)

        f1_scores: list[float] = []
        for pred, ref in zip(predictions, references):
            if not ref and not pred:
                f1_scores.append(1.0)
                continue
            if not ref or not pred:
                f1_scores.append(0.0)
                continue
            tp = len(pred & ref)
            precision = tp / len(pred) if pred else 0.0
            recall = tp / len(ref) if ref else 0.0
            if precision + recall == 0:
                f1_scores.append(0.0)
            else:
                f1_scores.append(2 * precision * recall / (precision + recall))

        avg_f1 = float(np.mean(f1_scores))
        return MetricResult(
            name="f1_score",
            value=avg_f1,
            count=len(predictions),
            details={"per_case_f1": f1_scores},
        )

    @staticmethod
    def cohens_kappa(
        rater1: list[int], rater2: list[int], num_categories: int | None = None
    ) -> MetricResult:
        """Compute Cohen's Kappa for inter-rater agreement.

        Used to measure agreement between LLM-judge scores and human calibration
        scores, establishing the reliability of automated evaluation.

        Args:
            rater1: Scores from first rater (e.g., LLM judge).
            rater2: Scores from second rater (e.g., human expert).
            num_categories: Number of possible score categories. Auto-detected if None.

        Returns:
            MetricResult with Kappa value in [-1, 1].
        """
        if not rater1 or len(rater1) != len(rater2):
            return MetricResult(name="cohens_kappa", value=0.0, count=0)

        if num_categories is None:
            num_categories = max(max(rater1), max(rater2)) + 1

        n = len(rater1)

        # Build confusion matrix
        matrix = np.zeros((num_categories, num_categories), dtype=np.float64)
        for r1, r2 in zip(rater1, rater2):
            matrix[r1][r2] += 1

        # Observed agreement
        p_o = float(np.trace(matrix)) / n

        # Expected agreement
        row_sums = matrix.sum(axis=1)
        col_sums = matrix.sum(axis=0)
        p_e = float(np.sum(row_sums * col_sums)) / (n * n)

        if p_e == 1.0:
            kappa = 1.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

        return MetricResult(
            name="cohens_kappa",
            value=kappa,
            count=n,
            details={
                "observed_agreement": p_o,
                "expected_agreement": p_e,
                "confusion_matrix": matrix.tolist(),
            },
        )

    @staticmethod
    def quality_score(
        scores: list[float], weights: list[float] | None = None
    ) -> MetricResult:
        """Compute weighted quality score from rubric-based LLM judge scores.

        Args:
            scores: Individual dimension scores (0.0 to 1.0 each).
            weights: Optional weights for each dimension. Uniform if None.

        Returns:
            MetricResult with composite quality score.
        """
        if not scores:
            return MetricResult(name="quality_score", value=0.0, count=0)

        if weights is None:
            weights = [1.0 / len(scores)] * len(scores)
        else:
            total = sum(weights)
            weights = [w / total for w in weights]

        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return MetricResult(
            name="quality_score",
            value=weighted_sum,
            count=len(scores),
            details={"individual_scores": scores, "weights": weights},
        )

    @staticmethod
    def bootstrap_ci(
        scores: list[float],
        n_bootstrap: int = 10000,
        ci: float = 0.95,
    ) -> MetricResult:
        """Compute bootstrap confidence interval for a set of scores.

        Args:
            scores: List of scores to compute CI for.
            n_bootstrap: Number of bootstrap resamples.
            ci: Confidence level (default 0.95 for 95% CI).

        Returns:
            MetricResult with mean as value and CI bounds in details.
        """
        if not scores:
            return MetricResult(name="bootstrap_ci", value=0.0, count=0)

        arr = np.array(scores)
        n = len(arr)
        rng = np.random.default_rng(seed=42)  # Fixed seed for reproducibility

        bootstrap_means = np.array([
            rng.choice(arr, size=n, replace=True).mean()
            for _ in range(n_bootstrap)
        ])

        alpha = 1.0 - ci
        lower = float(np.percentile(bootstrap_means, 100 * alpha / 2))
        upper = float(np.percentile(bootstrap_means, 100 * (1 - alpha / 2)))

        return MetricResult(
            name="bootstrap_ci",
            value=float(arr.mean()),
            count=n,
            details={
                "ci_lower": lower,
                "ci_upper": upper,
                "ci_level": ci,
                "n_bootstrap": n_bootstrap,
            },
        )

    @staticmethod
    def wilcoxon_signed_rank(
        scores_a: list[float], scores_b: list[float]
    ) -> MetricResult:
        """Compute Wilcoxon signed-rank test for paired model comparison.

        Non-parametric test for whether two paired samples come from the
        same distribution. Used to determine if one model is statistically
        significantly better than another.

        Args:
            scores_a: Scores from model A (one per test case).
            scores_b: Scores from model B (same test cases, same order).

        Returns:
            MetricResult with p-value as value.
        """
        if len(scores_a) != len(scores_b) or not scores_a:
            return MetricResult(name="wilcoxon_signed_rank", value=1.0, count=0)

        differences = np.array(scores_a) - np.array(scores_b)
        # Remove zero differences
        nonzero_mask = differences != 0
        differences = differences[nonzero_mask]

        if len(differences) == 0:
            return MetricResult(
                name="wilcoxon_signed_rank", value=1.0, count=len(scores_a),
                details={"statistic": 0.0, "p_value": 1.0, "note": "no differences"},
            )

        # Rank absolute differences
        abs_diff = np.abs(differences)
        ranks = np.argsort(np.argsort(abs_diff)) + 1.0  # Simple ranking

        # Sum ranks of positive and negative differences
        w_plus = float(np.sum(ranks[differences > 0]))
        w_minus = float(np.sum(ranks[differences < 0]))
        w_stat = min(w_plus, w_minus)

        n = len(differences)
        # Normal approximation for n >= 10
        if n >= 10:
            mean_w = n * (n + 1) / 4
            std_w = np.sqrt(n * (n + 1) * (2 * n + 1) / 24)
            z = (w_stat - mean_w) / std_w if std_w > 0 else 0.0
            # Two-tailed p-value using normal approximation
            from scipy.stats import norm  # type: ignore[import-untyped]
            p_value = float(2 * norm.cdf(-abs(z)))
        else:
            # For small samples, return the statistic without p-value
            p_value = float("nan")

        return MetricResult(
            name="wilcoxon_signed_rank",
            value=p_value,
            count=len(scores_a),
            details={
                "statistic": w_stat,
                "p_value": p_value,
                "w_plus": w_plus,
                "w_minus": w_minus,
                "n_nonzero": n,
            },
        )

    @staticmethod
    def cohens_d(scores_a: list[float], scores_b: list[float]) -> MetricResult:
        """Compute Cohen's d effect size between two sets of scores.

        Measures the standardized difference between two means.
        |d| < 0.2: negligible, 0.2-0.5: small, 0.5-0.8: medium, > 0.8: large.

        Args:
            scores_a: Scores from model A.
            scores_b: Scores from model B.

        Returns:
            MetricResult with Cohen's d as value.
        """
        if not scores_a or not scores_b:
            return MetricResult(name="cohens_d", value=0.0, count=0)

        a = np.array(scores_a)
        b = np.array(scores_b)

        mean_diff = float(a.mean() - b.mean())
        # Pooled standard deviation
        n_a, n_b = len(a), len(b)
        pooled_std = float(np.sqrt(
            ((n_a - 1) * a.var(ddof=1) + (n_b - 1) * b.var(ddof=1))
            / (n_a + n_b - 2)
        )) if (n_a + n_b) > 2 else 1.0

        d = mean_diff / pooled_std if pooled_std > 0 else 0.0

        # Interpret effect size
        abs_d = abs(d)
        if abs_d < 0.2:
            interpretation = "negligible"
        elif abs_d < 0.5:
            interpretation = "small"
        elif abs_d < 0.8:
            interpretation = "medium"
        else:
            interpretation = "large"

        return MetricResult(
            name="cohens_d",
            value=d,
            count=n_a + n_b,
            details={
                "mean_a": float(a.mean()),
                "mean_b": float(b.mean()),
                "pooled_std": pooled_std,
                "interpretation": interpretation,
            },
        )

    @staticmethod
    def bonferroni_correction(p_values: list[float]) -> MetricResult:
        """Apply Bonferroni correction for multiple comparisons.

        Adjusts p-values to control family-wise error rate when making
        multiple statistical comparisons (e.g., comparing many model pairs).

        Args:
            p_values: Raw p-values from individual tests.

        Returns:
            MetricResult with number of significant results (at alpha=0.05)
            as value, adjusted p-values in details.
        """
        if not p_values:
            return MetricResult(name="bonferroni_correction", value=0.0, count=0)

        n = len(p_values)
        adjusted = [min(p * n, 1.0) for p in p_values]
        significant = sum(1 for p in adjusted if p < 0.05)

        return MetricResult(
            name="bonferroni_correction",
            value=float(significant),
            count=n,
            details={
                "raw_p_values": p_values,
                "adjusted_p_values": adjusted,
                "n_comparisons": n,
                "significant_at_005": significant,
            },
        )

    @staticmethod
    def composite_benchmark_score(
        layer_scores: dict[str, float],
        layer_weights: dict[str, float],
    ) -> float:
        """Compute final composite benchmark score across evaluation layers.

        Args:
            layer_scores: Score per evaluation layer (0.0 to 1.0).
            layer_weights: Weight per evaluation layer.

        Returns:
            Weighted composite score (0.0 to 1.0).
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for layer, score in layer_scores.items():
            weight = layer_weights.get(layer, 0.0)
            weighted_sum += score * weight
            total_weight += weight
        if total_weight == 0.0:
            return 0.0
        return weighted_sum / total_weight
