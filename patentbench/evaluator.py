"""Evaluation harness for PatentBench.

Implements the 4-layer evaluation framework:
1. DeterministicEvaluator - Binary correctness for objective tasks
2. LLMJudgeEvaluator - Rubric-based scoring using calibrated LLM judges
3. ComparativeEvaluator - Blind side-by-side ranking
4. HumanCalibrationCollector - Expert attorney score collection
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from patentbench.anti_hallucination import AntiHallucinationChecker, HallucinationReport
from patentbench.config import (
    DEFAULT_JUDGE_MAX_TOKENS,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_TEMPERATURE,
    EvaluationLayer,
    LAYER_WEIGHTS,
    MetricType,
    RejectionType,
    USPTO_FEES,
)
from patentbench.data_loader import TestCase
from patentbench.metrics import EvaluationResult, MetricResult, MetricsCalculator


class LLMClient(Protocol):
    """Protocol for LLM clients used by LLMJudgeEvaluator."""

    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str: ...


@dataclass
class RubricDimension:
    """A single scoring dimension in an evaluation rubric."""

    name: str
    description: str
    weight: float = 1.0
    scale_min: int = 1
    scale_max: int = 5
    criteria: dict[int, str] = field(default_factory=dict)


@dataclass
class Rubric:
    """Complete evaluation rubric with multiple dimensions."""

    name: str
    dimensions: list[RubricDimension]
    version: str = "1.0"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Rubric:
        """Load rubric from JSON dict."""
        dims = []
        for d in data["dimensions"]:
            dims.append(RubricDimension(
                name=d["name"],
                description=d["description"],
                weight=d.get("weight", 1.0),
                scale_min=d.get("scale_min", 1),
                scale_max=d.get("scale_max", 5),
                criteria=d.get("criteria", {}),
            ))
        return cls(name=data["name"], dimensions=dims, version=data.get("version", "1.0"))

    @classmethod
    def from_file(cls, path: str) -> Rubric:
        """Load rubric from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(json.load(f))


class BaseEvaluator(ABC):
    """Abstract base for all evaluators."""

    @abstractmethod
    def evaluate(self, case: TestCase, model_output: str) -> EvaluationResult:
        """Evaluate a model output against a test case."""
        ...

    @abstractmethod
    def layer(self) -> EvaluationLayer:
        """Return the evaluation layer this evaluator implements."""
        ...


class DeterministicEvaluator(BaseEvaluator):
    """Evaluator for objectively correct/incorrect answers.

    Handles:
    - Deadline calculation accuracy
    - Fee computation accuracy
    - Action classification accuracy
    - Timeline analysis accuracy
    - Entity status determination
    - Office Action parsing accuracy
    - Generic field matching (fallback)
    """

    def layer(self) -> EvaluationLayer:
        return EvaluationLayer.DETERMINISTIC

    def _parse_ref(self, case: TestCase) -> dict[str, Any]:
        """Parse reference_answer as JSON dict or return raw wrapper."""
        ref = case.reference_answer
        if isinstance(ref, dict):
            return ref
        ref = ref.strip()
        if ref.startswith("{"):
            try:
                return json.loads(ref)
            except json.JSONDecodeError:
                pass
        return {"_raw": ref}

    def evaluate(self, case: TestCase, model_output: str) -> EvaluationResult:
        """Evaluate model output deterministically."""
        result = EvaluationResult(
            case_id=case.id,
            model_name="",
            model_output=model_output,
        )

        task_type = case.task_type
        if task_type in ("deadline_calculation", "deadline_computation"):
            metric = self._check_deadline(case, model_output)
        elif task_type == "fee_computation":
            metric = self._check_fee(case, model_output)
        elif task_type == "action_classification":
            metric = self._check_action_classification(case, model_output)
        elif task_type == "timeline_analysis":
            metric = self._check_timeline(case, model_output)
        elif task_type == "entity_status":
            metric = self._check_entity_status(case, model_output)
        elif task_type == "oa_parsing":
            metric = self._check_oa_parsing(case, model_output)
        else:
            metric = self._check_generic(case, model_output)

        result.add_metric(metric)
        result.layer_scores[EvaluationLayer.DETERMINISTIC.value] = metric.value
        result.passed = metric.value >= 0.5
        return result

    # ---- date extraction helpers ----

    _DATE_PATTERNS = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
    ]

    def _extract_dates(self, text: str) -> list[str]:
        dates: list[str] = []
        for p in self._DATE_PATTERNS:
            dates.extend(re.findall(p, text))
        return dates

    def _dates_match(self, date_str: str, expected: str) -> bool:
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%B %d %Y"]
        d1 = d2 = None
        for fmt in formats:
            try:
                d1 = d1 or datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                pass
            try:
                d2 = d2 or datetime.strptime(expected.strip(), fmt)
            except ValueError:
                pass
        if d1 and d2:
            return d1.date() == d2.date()
        return date_str.strip() == expected.strip()

    # ---- task checkers ----

    def _check_deadline(self, case: TestCase, output: str) -> MetricResult:
        ref = self._parse_ref(case)
        extracted = self._extract_dates(output)
        if not extracted:
            return MetricResult(name="deadline_accuracy", value=0.0, count=1,
                                details={"reason": "no date found"})

        date_keys = [k for k in ref if "deadline" in k or "date" in k.lower()]
        if not date_keys and "_raw" in ref:
            matched = any(self._dates_match(d, ref["_raw"]) for d in extracted)
            return MetricResult(name="deadline_accuracy", value=1.0 if matched else 0.0, count=1)

        checks = hits = 0
        details: dict[str, Any] = {"found": extracted}
        for key in date_keys:
            checks += 1
            exp_val = str(ref[key])
            ok = any(self._dates_match(d, exp_val) for d in extracted)
            details[key] = {"expected": exp_val, "matched": ok}
            if ok:
                hits += 1

        return MetricResult(name="deadline_accuracy",
                            value=hits / checks if checks else 0.0,
                            count=checks, details=details)

    def _check_fee(self, case: TestCase, output: str) -> MetricResult:
        ref = self._parse_ref(case)
        amounts = [a.replace(",", "") for a in re.findall(r"\$?([\d,]+(?:\.\d{2})?)", output)]

        fee_keys = [k for k in ref if k not in ("_raw", "explanation", "action_type")]
        checks = hits = 0
        for k in fee_keys:
            val = str(ref[k]).replace("$", "").replace(",", "")
            try:
                float(val)
            except ValueError:
                continue
            checks += 1
            if val in amounts:
                hits += 1

        if checks == 0 and "_raw" in ref:
            raw = ref["_raw"].replace("$", "").replace(",", "")
            return MetricResult(name="fee_accuracy", value=1.0 if raw in amounts else 0.0, count=1)

        return MetricResult(name="fee_accuracy",
                            value=hits / checks if checks else 0.0, count=checks)

    def _check_action_classification(self, case: TestCase, output: str) -> MetricResult:
        ref = self._parse_ref(case)
        out_lower = output.lower()
        checks = hits = 0
        for key, val in ref.items():
            if key in ("technology_center", "art_unit", "examiner", "explanation", "_raw"):
                continue
            checks += 1
            sval = str(val).lower()
            if sval in out_lower:
                hits += 1
        return MetricResult(name="classification_accuracy",
                            value=hits / checks if checks else 0.0, count=checks)

    def _check_timeline(self, case: TestCase, output: str) -> MetricResult:
        ref = self._parse_ref(case)
        checks = hits = 0
        for key in ("total_events", "first_event_date", "last_event_date", "prosecution_days",
                     "total_oa_count"):
            if key not in ref:
                continue
            checks += 1
            if str(ref[key]) in output:
                hits += 1
        return MetricResult(name="timeline_accuracy",
                            value=hits / checks if checks else 0.0, count=checks)

    def _check_entity_status(self, case: TestCase, output: str) -> MetricResult:
        """Verify entity status determination.

        Handles both plain string and JSON reference_answers.
        """
        ref = self._parse_ref(case)
        if "_raw" in ref:
            expected = ref["_raw"].strip().lower()
        else:
            expected = str(ref.get("entity_status", ref.get("status", ""))).strip().lower()

        output_lower = output.lower()

        valid_statuses = ["micro", "small", "large"]
        found_status = None
        for status in valid_statuses:
            if status in output_lower:
                found_status = status
                break

        match = found_status == expected
        return MetricResult(
            name="entity_status_accuracy",
            value=1.0 if match else 0.0,
            count=1,
            details={"expected": expected, "found": found_status},
        )

    def _check_oa_parsing(self, case: TestCase, output: str) -> MetricResult:
        """Verify Office Action parsing accuracy.

        Checks extraction of rejection types, claim numbers, and grounds.
        """
        ref_data = self._parse_ref(case)

        scores: list[float] = []

        # Check rejection type extraction
        if "rejection_types" in ref_data:
            expected_types = set(ref_data["rejection_types"])
            found_types: set[str] = set()
            for rt in RejectionType:
                if rt.value in output or rt.display_name.lower() in output.lower():
                    found_types.add(rt.value)
            if expected_types:
                overlap = expected_types & found_types
                precision = len(overlap) / len(found_types) if found_types else 0.0
                recall = len(overlap) / len(expected_types)
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                scores.append(f1)

        # Check claim number extraction
        if "claims" in ref_data:
            expected_claims = set(ref_data["claims"])
            found_claims = set(int(c) for c in re.findall(r"claim\s*(\d+)", output, re.IGNORECASE))
            if expected_claims:
                overlap = expected_claims & found_claims
                precision = len(overlap) / len(found_claims) if found_claims else 0.0
                recall = len(overlap) / len(expected_claims)
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                scores.append(f1)

        value = sum(scores) / len(scores) if scores else 0.0
        return MetricResult(
            name="oa_parsing_accuracy",
            value=value,
            count=1,
            details={"sub_scores": scores},
        )

    def _check_generic(self, case: TestCase, output: str) -> MetricResult:
        """Generic field matching for task types without a dedicated checker."""
        ref = self._parse_ref(case)
        if "_raw" in ref:
            return MetricResult(name="generic_accuracy",
                                value=1.0 if ref["_raw"].lower() in output.lower() else 0.0,
                                count=1)
        checks = hits = 0
        for k, v in ref.items():
            sval = str(v)
            if len(sval) <= 1:
                continue
            checks += 1
            if sval.lower() in output.lower():
                hits += 1
        return MetricResult(name="generic_accuracy",
                            value=hits / checks if checks else 0.0, count=checks)


class LLMJudgeEvaluator(BaseEvaluator):
    """Rubric-based evaluation using a calibrated LLM judge.

    Uses an LLM judge to score model outputs across multiple
    quality dimensions defined by rubrics.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        rubrics: list[Rubric] | None = None,
        judge_model: str = DEFAULT_JUDGE_MODEL,
        temperature: float = DEFAULT_JUDGE_TEMPERATURE,
        max_tokens: int = DEFAULT_JUDGE_MAX_TOKENS,
    ) -> None:
        self.llm_client = llm_client
        self.rubrics = rubrics or []
        self.judge_model = judge_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.anti_hallucination = AntiHallucinationChecker()

    def layer(self) -> EvaluationLayer:
        return EvaluationLayer.LLM_JUDGE

    def evaluate(self, case: TestCase, model_output: str) -> EvaluationResult:
        """Evaluate model output using LLM judge with rubrics."""
        result = EvaluationResult(
            case_id=case.id,
            model_name="",
            model_output=model_output,
        )

        # Run anti-hallucination checks
        hal_report = self.anti_hallucination.check_with_context(
            model_output,
            expected_mpep=case.mpep_sections,
        )
        result.add_metric(MetricResult(
            name="anti_hallucination",
            value=hal_report.score,
            count=1,
            details={
                "poison_pill_hits": hal_report.poison_pill_hits,
                "fabricated_cases": hal_report.fabricated_cases,
                "invalid_mpep": hal_report.invalid_mpep_sections,
            },
        ))

        # Get rubric-based scores from LLM judge
        rubric_scores = self._judge_with_rubric(case, model_output)
        for dimension_name, score in rubric_scores.items():
            result.add_metric(MetricResult(
                name=dimension_name,
                value=score,
                count=1,
            ))

        # Compute aggregate layer score
        all_scores = [m.value for m in result.metrics.values()]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        result.layer_scores[EvaluationLayer.LLM_JUDGE.value] = avg_score
        result.passed = avg_score >= 0.5
        return result

    def _judge_with_rubric(self, case: TestCase, model_output: str) -> dict[str, float]:
        """Use LLM to judge model output against rubric dimensions."""
        prompt = self._build_judge_prompt(case, model_output)
        response = self.llm_client.generate(
            prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return self._parse_judge_response(response)

    def _build_judge_prompt(self, case: TestCase, model_output: str) -> str:
        """Build the evaluation prompt for the LLM judge."""
        rubric_text = ""
        for rubric in self.rubrics:
            for dim in rubric.dimensions:
                rubric_text += f"\n### {dim.name}\n{dim.description}\n"
                rubric_text += f"Scale: {dim.scale_min} to {dim.scale_max}\n"
                for score_val, criteria in sorted(dim.criteria.items()):
                    rubric_text += f"  {score_val}: {criteria}\n"

        return f"""You are an expert patent attorney evaluating an AI system's output on a patent prosecution task.

## Task
{case.prompt}

## Reference Answer
{case.reference_answer}

## Model Output Being Evaluated
{model_output}

## Evaluation Rubric
{rubric_text}

## Instructions
Score each dimension on the specified scale. Return your evaluation as JSON:
{{
    "legal_accuracy": <score 1-5>,
    "factual_accuracy": <score 1-5>,
    "argument_strength": <score 1-5>,
    "completeness": <score 1-5>,
    "reasoning": "<brief explanation>"
}}

Return ONLY the JSON object, no additional text."""

    def _parse_judge_response(self, response: str) -> dict[str, float]:
        """Parse LLM judge response into dimension scores (normalized 0-1)."""
        try:
            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
            if not json_match:
                return self._default_scores()
            data = json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError):
            return self._default_scores()

        scores: dict[str, float] = {}
        for key in ["legal_accuracy", "factual_accuracy", "argument_strength", "completeness"]:
            raw = data.get(key, 1)
            # Normalize from 1-5 scale to 0-1
            scores[key] = max(0.0, min(1.0, (float(raw) - 1.0) / 4.0))

        return scores

    @staticmethod
    def _default_scores() -> dict[str, float]:
        return {
            "legal_accuracy": 0.0,
            "factual_accuracy": 0.0,
            "argument_strength": 0.0,
            "completeness": 0.0,
        }


class ComparativeEvaluator(BaseEvaluator):
    """Blind side-by-side evaluation comparing two model outputs.

    Presents two outputs (model A vs model B) to a judge without revealing
    which model produced which output. The judge selects the better output
    or declares a tie.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def layer(self) -> EvaluationLayer:
        return EvaluationLayer.COMPARATIVE

    def evaluate(self, case: TestCase, model_output: str) -> EvaluationResult:
        """Not applicable for single-model evaluation. Use compare() instead."""
        return EvaluationResult(
            case_id=case.id,
            model_name="",
            model_output=model_output,
            error="ComparativeEvaluator requires two outputs. Use compare() method.",
        )

    def compare(
        self,
        case: TestCase,
        output_a: str,
        output_b: str,
        model_a_name: str = "Model A",
        model_b_name: str = "Model B",
    ) -> ComparisonResult:
        """Compare two model outputs blind.

        Args:
            case: The test case.
            output_a: First model's output.
            output_b: Second model's output.
            model_a_name: Name of first model (not shown to judge).
            model_b_name: Name of second model (not shown to judge).

        Returns:
            ComparisonResult with winner and reasoning.
        """
        # Randomize order to eliminate position bias
        import random
        if random.random() > 0.5:
            first, second = output_a, output_b
            first_is_a = True
        else:
            first, second = output_b, output_a
            first_is_a = False

        prompt = f"""You are an expert patent attorney comparing two AI-generated responses to the same patent prosecution task.

## Task
{case.prompt}

## Reference Answer
{case.reference_answer}

## Response 1
{first}

## Response 2
{second}

## Instructions
Compare the two responses on these dimensions:
1. Legal accuracy and correctness
2. Quality of argumentation
3. Completeness of the response
4. Practical utility for a patent practitioner

Select the better response. Return your evaluation as JSON:
{{
    "winner": <1 or 2 or 0 for tie>,
    "confidence": <"high", "medium", or "low">,
    "reasoning": "<brief explanation>"
}}

Return ONLY the JSON object."""

        response = self.llm_client.generate(prompt=prompt, max_tokens=2048, temperature=0.0)

        try:
            json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        raw_winner = data.get("winner", 0)
        if raw_winner == 1:
            winner = model_a_name if first_is_a else model_b_name
        elif raw_winner == 2:
            winner = model_b_name if first_is_a else model_a_name
        else:
            winner = "tie"

        return ComparisonResult(
            case_id=case.id,
            model_a=model_a_name,
            model_b=model_b_name,
            winner=winner,
            confidence=data.get("confidence", "low"),
            reasoning=data.get("reasoning", ""),
        )


@dataclass
class ComparisonResult:
    """Result of a comparative evaluation between two models."""

    case_id: str
    model_a: str
    model_b: str
    winner: str  # model name or "tie"
    confidence: str  # "high", "medium", "low"
    reasoning: str = ""


class HumanCalibrationCollector:
    """Collects and manages human expert scores for calibration.

    Human scores are used to:
    1. Anchor automated metrics against expert judgment
    2. Compute inter-rater reliability (Cohen's Kappa)
    3. Identify cases where LLM judges diverge from expert opinion
    """

    def __init__(self) -> None:
        self.scores: list[HumanScore] = []

    def add_score(
        self,
        case_id: str,
        expert_id: str,
        dimension_scores: dict[str, int],
        notes: str = "",
    ) -> HumanScore:
        """Record a human expert score."""
        score = HumanScore(
            case_id=case_id,
            expert_id=expert_id,
            dimension_scores=dimension_scores,
            notes=notes,
            timestamp=datetime.utcnow().isoformat(),
        )
        self.scores.append(score)
        return score

    def get_scores_for_case(self, case_id: str) -> list[HumanScore]:
        """Get all human scores for a specific test case."""
        return [s for s in self.scores if s.case_id == case_id]

    def compute_inter_rater_reliability(
        self, dimension: str
    ) -> MetricResult:
        """Compute Cohen's Kappa between pairs of expert raters for a dimension.

        Returns the average Kappa across all rater pairs.
        """
        # Group scores by case
        case_scores: dict[str, dict[str, int]] = {}
        for score in self.scores:
            if dimension in score.dimension_scores:
                key = score.case_id
                if key not in case_scores:
                    case_scores[key] = {}
                case_scores[key][score.expert_id] = score.dimension_scores[dimension]

        # Find cases scored by at least 2 raters
        multi_rated = {k: v for k, v in case_scores.items() if len(v) >= 2}
        if not multi_rated:
            return MetricResult(name="inter_rater_kappa", value=0.0, count=0)

        # Compute pairwise Kappa
        calculator = MetricsCalculator()
        all_kappas: list[float] = []

        expert_ids = sorted(set(
            eid for scores in multi_rated.values() for eid in scores
        ))

        for i in range(len(expert_ids)):
            for j in range(i + 1, len(expert_ids)):
                rater1_scores: list[int] = []
                rater2_scores: list[int] = []
                for case_id, experts in multi_rated.items():
                    if expert_ids[i] in experts and expert_ids[j] in experts:
                        rater1_scores.append(experts[expert_ids[i]])
                        rater2_scores.append(experts[expert_ids[j]])
                if len(rater1_scores) >= 5:  # minimum sample size
                    kappa = calculator.cohens_kappa(rater1_scores, rater2_scores)
                    all_kappas.append(kappa.value)

        avg_kappa = sum(all_kappas) / len(all_kappas) if all_kappas else 0.0
        return MetricResult(
            name="inter_rater_kappa",
            value=avg_kappa,
            count=len(all_kappas),
            details={"pairwise_kappas": all_kappas, "num_rater_pairs": len(all_kappas)},
        )

    def export_json(self) -> list[dict[str, Any]]:
        """Export all scores as JSON-serializable dicts."""
        return [
            {
                "case_id": s.case_id,
                "expert_id": s.expert_id,
                "dimension_scores": s.dimension_scores,
                "notes": s.notes,
                "timestamp": s.timestamp,
            }
            for s in self.scores
        ]


@dataclass
class HumanScore:
    """A single human expert evaluation score."""

    case_id: str
    expert_id: str
    dimension_scores: dict[str, int]  # dimension name -> score (1-5)
    notes: str = ""
    timestamp: str = ""


class ScoringAggregator:
    """Aggregates scores across evaluation layers into composite benchmark scores."""

    def __init__(
        self,
        layer_weights: dict[str, float] | None = None,
    ) -> None:
        self.layer_weights = layer_weights or {
            layer.value: weight for layer, weight in LAYER_WEIGHTS.items()
        }

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        """Aggregate results across all cases and layers.

        Returns:
            Dictionary with per-layer scores, composite score, and details.
        """
        if not results:
            return {"composite_score": 0.0, "layer_scores": {}, "case_count": 0}

        # Collect layer scores across cases
        layer_totals: dict[str, list[float]] = {}
        for result in results:
            for layer, score in result.layer_scores.items():
                if layer not in layer_totals:
                    layer_totals[layer] = []
                layer_totals[layer].append(score)

        # Average per layer
        layer_averages: dict[str, float] = {}
        for layer, scores in layer_totals.items():
            layer_averages[layer] = sum(scores) / len(scores) if scores else 0.0

        # Composite weighted score
        composite = MetricsCalculator.composite_benchmark_score(
            layer_averages, self.layer_weights
        )

        return {
            "composite_score": composite,
            "layer_scores": layer_averages,
            "case_count": len(results),
            "pass_rate": sum(1 for r in results if r.passed) / len(results),
        }
