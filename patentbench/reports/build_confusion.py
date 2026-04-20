"""CLI to generate confusion matrix artifacts from a committed benchmark run.

Usage:
    python -m patentbench.reports.build_confusion \
        --run-file data/benchmark_runs/abigail/2026-04-20.json \
        --task-type paralegal_oa_extraction \
        --ground-truth data/ground_truth/paralegal_oa_extraction.json \
        --out reports/confusion_matrices/abigail/paralegal_oa_extraction

Emits:
    <out>.json - machine-readable matrix artifact (deterministic)
    <out>.md   - human-readable markdown with per-class P/R/F1
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from patentbench.reports.confusion import (
    ConfusionMatrixResult,
    build_confusion_matrix,
    dump_matrix_json,
    per_class_stats,
)


def _fmt_float(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _render_markdown(
    result_json_path: Path,
    matrix: ConfusionMatrixResult,
    stats: list[dict[str, Any]],
) -> str:
    """Render a self-contained markdown report for the matrix."""
    lines: list[str] = []
    lines.append(f"# Confusion Matrix — {matrix.model} — {matrix.task_type}")
    lines.append("")
    lines.append(f"- Run date: `{matrix.run_date}`")
    lines.append(f"- Total cases: `{matrix.total}`")
    lines.append(f"- Unparseable: `{matrix.unparseable}`")
    lines.append(f"- Quarantined: `{matrix.quarantined}`")
    lines.append(f"- Source run file: `{matrix.source_run_file}`")
    lines.append(f"- Source SHA-256: `{matrix.source_sha256}`")
    lines.append(f"- Ground truth file: `{matrix.ground_truth_file}`")
    lines.append(f"- Ground truth SHA-256: `{matrix.ground_truth_sha256}`")
    lines.append(f"- Schema version: `{matrix.schema_version}`")
    lines.append(f"- Verifier version: `{matrix.verifier_version}`")
    lines.append(f"- Generated at: `{matrix.generated_at}`")
    lines.append("")
    lines.append("## Axis convention")
    lines.append("")
    lines.append(
        "- Rows: **ground truth** (what the USPTO PEDS record or verified truth says)."
    )
    lines.append("- Cols: **predicted** (what the system under test emitted).")
    lines.append(
        "- Cell `[row=A, col=B]` counts the cases where truth was A and the "
        "model predicted B."
    )
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    header = "| truth \\ predicted |" + "|".join(
        f" `{label}` " for label in matrix.labels
    ) + "|"
    sep = "|" + "---|" * (len(matrix.labels) + 1)
    lines.append(header)
    lines.append(sep)
    for i, row_label in enumerate(matrix.labels):
        row_cells = [f"`{row_label}`"]
        for j in range(len(matrix.labels)):
            value = matrix.matrix[i][j]
            row_cells.append("**" + str(value) + "**" if i == j else str(value))
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")
    if matrix.hallucinated_labels:
        lines.append(
            "Labels present only in model predictions (never in ground truth, flagged "
            "as hallucinated): "
            + ", ".join(f"`{label}`" for label in matrix.hallucinated_labels)
        )
        lines.append("")

    lines.append("## Per-class precision, recall, F1")
    lines.append("")
    lines.append("| label | support | TP | FP | FN | precision | recall | F1 | hallucinated |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in stats:
        lines.append(
            "| `{label}` | {support} | {tp} | {fp} | {fn} | {p} | {r} | {f1} | {halluc} |".format(
                label=s["label"],
                support=s["support"],
                tp=s["tp"],
                fp=s["fp"],
                fn=s["fn"],
                p=_fmt_float(s["precision"]),
                r=_fmt_float(s["recall"]),
                f1=_fmt_float(s["f1"]),
                halluc="yes" if s["hallucinated"] else "no",
            )
        )
    lines.append("")

    if matrix.cell_traces:
        lines.append("## Off-diagonal traces")
        lines.append("")
        for trace in matrix.cell_traces:
            if trace.ground_truth == trace.predicted:
                continue
            lines.append(
                f"- `truth={trace.ground_truth}`, `predicted={trace.predicted}`: "
                + ", ".join(f"`{tid}`" for tid in trace.test_ids)
            )
        lines.append("")

    lines.append("## Verification")
    lines.append("")
    lines.append(
        "This artifact can be verified by: "
        "`python -m patentbench.reports.verify_confusion "
        f"{result_json_path}`"
    )
    lines.append("")
    return "\n".join(lines)


_PATH_IN = click.Path(exists=True, dir_okay=False, path_type=Path)


@click.command()
@click.option("--run-file", type=_PATH_IN, required=True)
@click.option("--task-type", type=str, required=True)
@click.option("--ground-truth", type=_PATH_IN, required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option(
    "--model-override",
    type=str,
    default=None,
    help="Override the model name in the artifact (for anonymization).",
)
@click.option("--verifier-version", type=str, default="1.0.0")
def main(
    run_file: Path,
    task_type: str,
    ground_truth: Path,
    out: Path,
    model_override: str | None,
    verifier_version: str,
) -> None:
    """Build a confusion matrix artifact (JSON + Markdown)."""
    result = build_confusion_matrix(
        run_file=run_file,
        task_type=task_type,
        ground_truth_file=ground_truth,
        model_override=model_override,
        verifier_version=verifier_version,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    md_path = out.with_suffix(".md")

    dump_matrix_json(result, json_path)

    stats = per_class_stats(result)
    md_text = _render_markdown(json_path, result, stats)
    if not md_text.endswith("\n"):
        md_text = md_text + "\n"
    md_path.write_text(md_text, encoding="utf-8", newline="\n")

    click.echo(f"Wrote {json_path}")
    click.echo(f"Wrote {md_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
