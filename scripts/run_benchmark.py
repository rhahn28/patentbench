#!/usr/bin/env python3
"""CLI entry point for running PatentBench benchmarks.

Usage:
    python scripts/run_benchmark.py --model openai:gpt-4o --subset mini
    python scripts/run_benchmark.py --model anthropic:claude-sonnet-4 --domain prosecution --tier 3
    python scripts/run_benchmark.py --model abigail --api-key YOUR_KEY
    python scripts/run_benchmark.py --help
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from patentbench.config import Domain, DifficultyTier
from patentbench.data_loader import DataLoader
from patentbench.harness import BenchmarkConfig, BenchmarkRunner


def _create_model_adapter(model_spec: str, api_key: str | None = None):
    """Create a model adapter from a specification string.

    Formats:
        "openai:gpt-4o"
        "anthropic:claude-sonnet-4"
        "google:gemini-2.5-pro"
        "abigail"
    """
    if model_spec == "abigail":
        from patentbench.models.abigail import AbigailAdapter
        if not api_key:
            raise click.BadParameter("ABIGAIL requires --api-key")
        return AbigailAdapter(api_key=api_key)

    if ":" not in model_spec:
        raise click.BadParameter(
            f"Invalid model spec '{model_spec}'. "
            "Use format 'provider:model_name' (e.g., 'openai:gpt-4o')"
        )

    provider, model_name = model_spec.split(":", 1)

    if provider == "openai":
        from patentbench.models.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(model_name=model_name, api_key=api_key)
    elif provider == "anthropic":
        from patentbench.models.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(model_name=model_name, api_key=api_key)
    elif provider == "google":
        from patentbench.models.google_adapter import GoogleAdapter
        return GoogleAdapter(model_name=model_name, api_key=api_key)
    else:
        raise click.BadParameter(f"Unknown provider: {provider}")


@click.command()
@click.option(
    "--model", "-m",
    required=True,
    help="Model specification (e.g., 'openai:gpt-4o', 'anthropic:claude-sonnet-4', 'abigail')",
)
@click.option(
    "--subset", "-s",
    default="mini",
    type=click.Choice(["mini", "full", "oa", "draft"]),
    help="Benchmark subset to run (default: mini)",
)
@click.option(
    "--domain", "-d",
    default=None,
    type=click.Choice([d.value for d in Domain]),
    help="Filter by domain",
)
@click.option(
    "--tier", "-t",
    default=None,
    type=click.IntRange(1, 5),
    help="Filter by difficulty tier (1-5)",
)
@click.option(
    "--max-cases", "-n",
    default=None,
    type=int,
    help="Maximum number of test cases to run",
)
@click.option(
    "--api-key", "-k",
    default=None,
    help="API key for the model provider",
)
@click.option(
    "--output-dir", "-o",
    default="results",
    help="Directory to save results (default: results)",
)
@click.option(
    "--data-dir",
    default="data",
    help="Data directory (default: data)",
)
@click.option(
    "--no-judge",
    is_flag=True,
    help="Skip LLM-judge evaluation layer",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON to stdout",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
def main(
    model: str,
    subset: str,
    domain: str | None,
    tier: int | None,
    max_cases: int | None,
    api_key: str | None,
    output_dir: str,
    data_dir: str,
    no_judge: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Run PatentBench evaluation on a model.

    Examples:

        # Run mini benchmark with GPT-4o
        patentbench run --model openai:gpt-4o --subset mini

        # Run prosecution domain, tier 3 only
        patentbench run --model anthropic:claude-sonnet-4 --domain prosecution --tier 3

        # Run with ABIGAIL
        patentbench run --model abigail --api-key YOUR_KEY
    """
    if verbose:
        click.echo(f"PatentBench Benchmark Runner")
        click.echo(f"Model: {model}")
        click.echo(f"Subset: {subset}")
        click.echo(f"Domain: {domain or 'all'}")
        click.echo(f"Tier: {tier or 'all'}")
        click.echo()

    # Create model adapter
    try:
        adapter = _create_model_adapter(model, api_key)
    except Exception as exc:
        click.echo(f"Error creating model adapter: {exc}", err=True)
        sys.exit(1)

    # Check availability
    if not adapter.is_available():
        click.echo(
            f"Warning: Model '{model}' may not be available. "
            "Check API key configuration.",
            err=True,
        )

    # Build config
    config = BenchmarkConfig(
        subset=subset,
        domains=[Domain(domain)] if domain else None,
        tiers=[DifficultyTier(tier)] if tier else None,
        max_cases=max_cases,
        output_dir=output_dir,
        run_llm_judge=not no_judge,
    )

    # Resolve data directory -- try several locations
    data_path = Path(data_dir)
    if not data_path.is_absolute():
        # Try relative to CWD first
        if data_path.exists():
            pass
        # Then relative to project root
        elif (PROJECT_ROOT / data_path).exists():
            data_path = PROJECT_ROOT / data_path
        # Then relative to the patentbench package
        else:
            pkg_data = Path(__file__).resolve().parent.parent / "patentbench" / "data"
            if pkg_data.exists():
                data_path = pkg_data
            else:
                data_path = PROJECT_ROOT / data_path

    # Run benchmark
    runner = BenchmarkRunner(model=adapter, data_dir=data_path, config=config)

    if verbose:
        click.echo("Loading test cases...")

    try:
        results = runner.run()
    except FileNotFoundError as exc:
        click.echo(f"Data not found: {exc}", err=True)
        click.echo("Make sure test case files exist in the data directory.", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Benchmark error: {exc}", err=True)
        sys.exit(1)

    # Output results
    if json_output:
        click.echo(json.dumps(results.to_dict(), indent=2))
    else:
        click.echo(results.summary())

    # Save results
    output_path = Path(output_dir) / f"{results.run_id}_{model.replace(':', '_')}.json"
    results.save(output_path)
    if verbose:
        click.echo(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
