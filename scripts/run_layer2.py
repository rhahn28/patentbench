#!/usr/bin/env python3
"""Run Layer 2 (LLM-Judge) evaluation on Tier 3 reasoning cases.

Converts tier3_reasoning_expanded.json scenarios into proper TestCase format,
runs them through a model, and evaluates with Gemini Flash as LLM-Judge.

Usage:
    python scripts/run_layer2.py --model google:gemini-2.5-flash --judge-key YOUR_KEY
    python scripts/run_layer2.py --model anthropic:claude-sonnet-4 --judge-key YOUR_KEY
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from patentbench.config import Domain, DifficultyTier, EvaluationLayer
from patentbench.data_loader import TestCase
from patentbench.evaluator import DeterministicEvaluator, LLMJudgeEvaluator
from patentbench.harness import BenchmarkConfig, BenchmarkRunner, BenchmarkResults
from patentbench.metrics import MetricsCalculator


# Map rejection types to domains
REJECTION_TO_DOMAIN = {
    "103": Domain.PROSECUTION,
    "102": Domain.PROSECUTION,
    "112": Domain.PROSECUTION,
    "101": Domain.PROSECUTION,
    "amendment": Domain.DRAFTING,
}


def load_tier3_cases(data_dir: Path) -> list[TestCase]:
    """Convert tier3_reasoning_expanded.json into TestCase objects."""
    path = data_dir / "tier3_reasoning_expanded.json"
    if not path.exists():
        raise FileNotFoundError(f"Tier 3 data not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cases = []
    for tc in raw["test_cases"]:
        # Build the prompt from scenario + claim + task
        claim = tc.get("claim_at_issue") or tc.get("original_claim", "")
        prompt = (
            f"## Scenario\n{tc['scenario']}\n\n"
            f"## Claim at Issue\n{claim}\n\n"
            f"## Task\n{tc['task']}"
        )

        # Reference answer is the model_response argument or explanation
        mr = tc["model_response"]
        ref = mr.get("argument") or mr.get("explanation") or json.dumps(mr)

        # Determine domain from rejection type
        rtype = tc.get("rejection_type", "103")
        domain = REJECTION_TO_DOMAIN.get(rtype, Domain.PROSECUTION)

        # Determine task_type
        if rtype in ("103", "102", "112", "101"):
            task_type = "103_argument"
        else:
            task_type = "amendment_drafting"

        case = TestCase(
            id=tc["id"],
            domain=domain,
            tier=DifficultyTier.SENIOR_ASSOCIATE,  # Tier 3
            task_type=task_type,
            prompt=prompt,
            reference_answer=ref,
            evaluation_layers=[EvaluationLayer.LLM_JUDGE],
            mpep_sections=tc["model_response"].get("legal_citations", []),
            metadata={
                "rejection_type": rtype,
                "technology_center": tc.get("technology_center", ""),
                "reasoning_chain": tc["model_response"].get("reasoning_chain", []),
            },
        )
        cases.append(case)

    return cases


class GeminiJudgeClient:
    """Wraps GoogleAdapter as an LLMClient for the LLM-Judge evaluator."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction="You are an expert patent attorney evaluating AI-generated patent prosecution arguments. Score rigorously.",
        )

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.0) -> str:
        import google.generativeai as genai
        config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        response = self._model.generate_content(prompt, generation_config=config)
        return response.text or ""


@click.command()
@click.option("--model", "-m", required=True, help="Model to evaluate (e.g., google:gemini-2.5-flash)")
@click.option("--api-key", "-k", default=None, help="API key for the model being evaluated")
@click.option("--judge-key", "-j", default=None, help="API key for the Gemini judge (defaults to --api-key)")
@click.option("--judge-model", default="gemini-2.5-flash", help="Model to use as LLM judge")
@click.option("--data-dir", default="data", help="Data directory")
@click.option("--output-dir", "-o", default="results", help="Output directory")
@click.option("--max-cases", "-n", default=None, type=int, help="Max cases to run")
@click.option("--verbose", "-v", is_flag=True)
def main(
    model: str,
    api_key: str | None,
    judge_key: str | None,
    judge_model: str,
    data_dir: str,
    output_dir: str,
    max_cases: int | None,
    verbose: bool,
) -> None:
    """Run Layer 2 LLM-Judge evaluation on Tier 3 reasoning cases."""
    data_path = Path(data_dir)
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path

    # Load tier 3 cases
    cases = load_tier3_cases(data_path)
    click.echo(f"Loaded {len(cases)} Tier 3 reasoning cases")

    if max_cases:
        cases = cases[:max_cases]
        click.echo(f"Limited to {max_cases} cases")

    # Create model adapter
    from scripts.run_benchmark import _create_model_adapter
    adapter = _create_model_adapter(model, api_key)

    if not adapter.is_available():
        click.echo(f"Warning: Model '{model}' may not be available.", err=True)

    # Create judge client
    jk = judge_key or api_key or ""
    judge = GeminiJudgeClient(api_key=jk, model_name=judge_model)

    # Create LLM-Judge evaluator
    llm_judge = LLMJudgeEvaluator(llm_client=judge)

    # Run evaluation
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    model_name = getattr(adapter, "model_name", model)
    click.echo(f"\nRunning Layer 2 evaluation: {model_name}")
    click.echo(f"Judge: {judge_model}")
    click.echo("-" * 60)

    all_results = []
    case_results = []
    total_latency = 0.0

    for i, case in enumerate(cases):
        start = time.time()
        try:
            output = adapter.generate(case.prompt)
            latency = (time.time() - start) * 1000
        except Exception as exc:
            click.echo(f"  [{i+1}/{len(cases)}] {case.id}: ERROR - {exc}")
            case_results.append({
                "case_id": case.id,
                "task_type": case.task_type,
                "tier": case.tier.value,
                "domain": case.domain.value,
                "score": 0.0,
                "passed": False,
                "error": str(exc),
                "latency_ms": (time.time() - start) * 1000,
            })
            continue

        total_latency += latency

        # Evaluate with LLM judge
        try:
            judge_result = llm_judge.evaluate(case, output)
            scores = {k: v.value for k, v in judge_result.metrics.items()}
            avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        except Exception as exc:
            click.echo(f"  [{i+1}/{len(cases)}] {case.id}: JUDGE ERROR - {exc}")
            scores = {}
            avg_score = 0.0

        passed = avg_score >= 0.5
        status = "PASS" if passed else "FAIL"
        click.echo(f"  [{i+1}/{len(cases)}] {case.id}: {avg_score:.2f} ({status})")
        if verbose and scores:
            for dim, score in scores.items():
                click.echo(f"    {dim}: {score:.2f}")

        case_results.append({
            "case_id": case.id,
            "task_type": case.task_type,
            "tier": case.tier.value,
            "domain": case.domain.value,
            "score": round(avg_score, 4),
            "passed": passed,
            "details": {k: round(v, 4) for k, v in scores.items()},
            "latency_ms": round(latency, 1),
            "model_output_preview": output[:200] + "..." if len(output) > 200 else output,
        })

        # Rate limiting for free API
        time.sleep(1)

    # Compute overall score
    all_scores = [c["score"] for c in case_results if c.get("score") is not None]
    overall = sum(all_scores) / len(all_scores) * 100 if all_scores else 0.0

    # Bootstrap CI
    ci = MetricsCalculator.bootstrap_ci(all_scores)

    # Build results
    results = BenchmarkResults(
        model_name=model_name,
        run_id=run_id,
        timestamp=datetime.utcnow().isoformat(),
        config={
            "layer": "llm_judge",
            "tier": 3,
            "judge_model": judge_model,
            "total_tier3_cases": len(cases),
        },
        overall_score=round(overall, 1),
        domain_scores={},
        tier_scores={3: overall},
        layer_scores={"llm_judge": overall},
        case_results=case_results,
        total_cases=len(cases),
        pass_rate=sum(1 for c in case_results if c.get("passed")) / len(case_results) if case_results else 0.0,
        total_latency_ms=total_latency,
        statistics={
            "overall_bootstrap_ci": {
                "mean": round(ci.value * 100, 2),
                "ci_lower": round(ci.details.get("ci_lower", 0) * 100, 2),
                "ci_upper": round(ci.details.get("ci_upper", 0) * 100, 2),
                "ci_level": 0.95,
                "n": ci.count,
            },
        },
    )

    # Save
    output_path = Path(output_dir) / f"{run_id}_{model.replace(':', '_')}_layer2.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.save(output_path)

    # Summary
    click.echo(f"\n{'='*60}")
    click.echo(f"  Layer 2 Results: {model_name}")
    click.echo(f"  Judge: {judge_model}")
    click.echo(f"  Overall Score: {overall:.1f}%")
    click.echo(f"  Pass Rate: {results.pass_rate:.1%}")
    click.echo(f"  Cases: {len(case_results)}")
    click.echo(f"  95% CI: [{ci.details.get('ci_lower', 0)*100:.1f}%, {ci.details.get('ci_upper', 0)*100:.1f}%]")
    click.echo(f"  Saved: {output_path}")
    click.echo(f"{'='*60}")


if __name__ == "__main__":
    main()
