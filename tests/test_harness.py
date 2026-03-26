"""Unit tests for PatentBench benchmark runner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from patentbench.config import Domain, DifficultyTier, EvaluationLayer
from patentbench.data_loader import TestCase
from patentbench.harness import BenchmarkConfig, BenchmarkRunner, BenchmarkResults


class MockModelAdapter:
    """Mock model adapter for testing."""

    def __init__(self, responses: dict[str, str] | None = None, default: str = "mock output") -> None:
        self.model_name = "mock-model"
        self.responses = responses or {}
        self.default = default
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return self.responses.get(prompt, self.default)

    def is_available(self) -> bool:
        return True

    def get_info(self) -> dict[str, Any]:
        return {"model_name": self.model_name}


def _make_cases() -> list[TestCase]:
    """Create test cases for harness testing."""
    return [
        TestCase(
            id="harness-001",
            domain=Domain.ADMINISTRATION,
            tier=DifficultyTier.PARALEGAL,
            task_type="deadline_calculation",
            prompt="Calculate the deadline",
            reference_answer="2024-06-15",
            evaluation_layers=[EvaluationLayer.DETERMINISTIC],
        ),
        TestCase(
            id="harness-002",
            domain=Domain.ADMINISTRATION,
            tier=DifficultyTier.PARALEGAL,
            task_type="fee_computation",
            prompt="Compute the fee",
            reference_answer="$320.00",
            evaluation_layers=[EvaluationLayer.DETERMINISTIC],
        ),
        TestCase(
            id="harness-003",
            domain=Domain.PROSECUTION,
            tier=DifficultyTier.JUNIOR_ASSOCIATE,
            task_type="entity_status",
            prompt="Determine entity status",
            reference_answer="small",
            evaluation_layers=[EvaluationLayer.DETERMINISTIC],
        ),
    ]


class TestBenchmarkRunner:
    """Tests for the BenchmarkRunner."""

    def test_run_with_provided_cases(self) -> None:
        model = MockModelAdapter(default="The deadline is 2024-06-15.")
        cases = _make_cases()[:1]
        runner = BenchmarkRunner(model=model, cases=cases)
        results = runner.run()

        assert results.total_cases == 1
        assert results.model_name == "mock-model"
        assert model.call_count == 1

    def test_run_multiple_cases(self) -> None:
        model = MockModelAdapter(responses={
            "Calculate the deadline": "The deadline is 2024-06-15.",
            "Compute the fee": "The fee is $320.00.",
            "Determine entity status": "The entity status is small.",
        })
        runner = BenchmarkRunner(model=model, cases=_make_cases())
        results = runner.run()

        assert results.total_cases == 3
        assert model.call_count == 3
        assert results.overall_score > 0

    def test_run_with_model_error(self) -> None:
        class ErrorModel:
            model_name = "error-model"
            def generate(self, prompt: str) -> str:
                raise RuntimeError("API timeout")
            def is_available(self) -> bool:
                return True

        runner = BenchmarkRunner(model=ErrorModel(), cases=_make_cases()[:1])
        results = runner.run()

        assert results.total_cases == 1
        assert results.case_results[0]["error"] is not None

    def test_empty_cases(self) -> None:
        model = MockModelAdapter()
        # Pass empty list explicitly to avoid loading from disk
        config = BenchmarkConfig(subset="mini")
        runner = BenchmarkRunner(model=model, cases=[], config=config)
        results = runner.run()

        # When no cases match, runner returns empty results but may still
        # attempt to load from disk if cases list is falsy (empty list)
        assert model.call_count == 0

    def test_domain_aggregation(self) -> None:
        model = MockModelAdapter(responses={
            "Calculate the deadline": "The deadline is 2024-06-15.",
            "Compute the fee": "The fee is $320.00.",
            "Determine entity status": "The entity status is small.",
        })
        runner = BenchmarkRunner(model=model, cases=_make_cases())
        results = runner.run()

        assert "administration" in results.domain_scores
        assert "prosecution" in results.domain_scores

    def test_tier_aggregation(self) -> None:
        model = MockModelAdapter(default="The deadline is 2024-06-15.")
        runner = BenchmarkRunner(model=model, cases=_make_cases())
        results = runner.run()

        assert 1 in results.tier_scores or 2 in results.tier_scores


class TestBenchmarkResults:
    """Tests for BenchmarkResults serialization."""

    def test_to_dict_v2_schema(self) -> None:
        results = BenchmarkResults(
            model_name="test-model",
            run_id="test-run-001",
            timestamp="2026-03-22T00:00:00",
            overall_score=85.5,
            total_cases=10,
            pass_rate=0.9,
            domain_scores={"administration": 90.0, "prosecution": 80.0},
            tier_scores={1: 95.0, 2: 75.0},
            layer_scores={"deterministic": 85.0},
            case_results=[
                {
                    "case_id": "tc-001",
                    "task_type": "deadline_calculation",
                    "tier": 1,
                    "domain": "administration",
                    "score": 1.0,
                    "passed": True,
                    "details": ["deadline_accuracy: CORRECT"],
                    "latency_ms": 150.0,
                    "error": None,
                }
            ],
        )
        d = results.to_dict()

        # v0.2.0 schema checks
        assert "summary" in d
        assert "scores" in d
        assert "metadata" in d
        assert d["summary"]["overall_score"] == 85.5
        assert d["summary"]["total_cases"] == 10
        assert d["scores"]["by_domain"]["administration"]["score"] == 90.0
        assert d["metadata"]["harness_version"] == results.version

    def test_to_dict_perfect_count(self) -> None:
        results = BenchmarkResults(
            model_name="test",
            case_results=[
                {"case_id": "a", "score": 1.0, "error": None},
                {"case_id": "b", "score": 0.5, "error": None},
                {"case_id": "c", "score": 1.0, "error": "timeout"},
            ],
        )
        d = results.to_dict()
        assert d["summary"]["tests_perfect"] == 2
        assert d["summary"]["tests_with_errors"] == 1

    def test_save_and_load(self, tmp_path: Path) -> None:
        results = BenchmarkResults(
            model_name="test",
            run_id="r1",
            timestamp="2026-03-22",
            overall_score=100.0,
            total_cases=1,
            case_results=[{"case_id": "a", "score": 1.0, "error": None}],
        )
        path = tmp_path / "results.json"
        results.save(path)

        with open(path, "r") as f:
            loaded = json.load(f)

        assert loaded["model"] == "test"
        assert loaded["summary"]["overall_score"] == 100.0

    def test_summary_output(self) -> None:
        results = BenchmarkResults(
            model_name="gpt-4o",
            overall_score=87.3,
            pass_rate=0.92,
            total_cases=50,
            domain_scores={"prosecution": 85.0},
            tier_scores={1: 90.0},
            layer_scores={"deterministic": 87.0},
        )
        text = results.summary()
        assert "gpt-4o" in text
        assert "87.3" in text


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig."""

    def test_defaults(self) -> None:
        config = BenchmarkConfig()
        assert config.subset == "mini"
        assert config.domains is None
        assert config.tiers is None
        assert config.run_deterministic is True
        assert config.run_llm_judge is True

    def test_no_concurrency_field(self) -> None:
        """Concurrency parameter was removed — sequential execution only."""
        config = BenchmarkConfig()
        assert not hasattr(config, "concurrency")
