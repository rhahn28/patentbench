"""Confusion matrix construction with single-pass traceability.

The matrix, label set, cell traces, and unparseable bucket are populated in a
SINGLE pass over the result rows. Two-pass construction is banned because it
lets a buggy second pass produce arithmetically-consistent but
trace-incorrect artifacts. The tamper test suite asserts this invariant.

Schema version 1. Any breaking change must bump the version and keep the
previous version parseable for at least one release cycle.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from patentbench.reports.ground_truth import (
    GroundTruthMissingError,
    extract_predictions_and_truth,
    load_ground_truth,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ConfusionCellTrace:
    """Every non-zero cell must list the exact test IDs that contributed."""

    ground_truth: str
    predicted: str
    test_ids: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "ground_truth": self.ground_truth,
            "predicted": self.predicted,
            "test_ids": list(self.test_ids),
        }


@dataclass
class ConfusionMatrixResult:
    """Structured confusion matrix with enough metadata for external audit.

    Invariants (checked by verify_confusion):
      - sum(cell for row in matrix for cell in row) + unparseable == total
      - For every non-zero cell at (i, j):
            len(cell_trace for (labels[i], labels[j])) == matrix[i][j]
      - Every test_id in any cell_trace is present in the source run file.
      - labels are ASCII-sorted.
      - source_sha256 matches the SHA-256 of the source run file on disk.
    """

    schema_version: int
    model: str
    run_date: str
    task_type: str
    labels: tuple[str, ...]
    matrix: tuple[tuple[int, ...], ...]
    cell_traces: tuple[ConfusionCellTrace, ...]
    unparseable: int
    unparseable_test_ids: tuple[str, ...]
    quarantined: int
    quarantined_test_ids: tuple[str, ...]
    total: int
    hallucinated_labels: tuple[str, ...]
    source_run_file: str
    source_sha256: str
    ground_truth_file: str
    ground_truth_sha256: str
    generated_at: str
    verifier_version: str

    def cell(self, ground_truth: str, predicted: str) -> int:
        i = self.labels.index(ground_truth)
        j = self.labels.index(predicted)
        return self.matrix[i][j]

    def as_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model": self.model,
            "run_date": self.run_date,
            "task_type": self.task_type,
            "labels": list(self.labels),
            "matrix": [list(row) for row in self.matrix],
            "cell_traces": [t.as_json() for t in self.cell_traces],
            "unparseable": self.unparseable,
            "unparseable_test_ids": list(self.unparseable_test_ids),
            "quarantined": self.quarantined,
            "quarantined_test_ids": list(self.quarantined_test_ids),
            "total": self.total,
            "hallucinated_labels": list(self.hallucinated_labels),
            "source_run_file": self.source_run_file,
            "source_sha256": self.source_sha256,
            "ground_truth_file": self.ground_truth_file,
            "ground_truth_sha256": self.ground_truth_sha256,
            "generated_at": self.generated_at,
            "verifier_version": self.verifier_version,
        }


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_confusion_matrix(
    *,
    run_file: Path,
    task_type: str,
    ground_truth_file: Path,
    model_override: str | None = None,
    verifier_version: str = "1.0.0",
) -> ConfusionMatrixResult:
    """Build a confusion matrix in a single pass.

    Args:
      run_file: Path to benchmark_runs/<model>/<run>.json produced by the
        harness. Top-level MUST contain `model`, `run_date`, and
        `detailed_results` (iterable of rows).
      task_type: Restrict to rows where row["task_type"] == task_type.
      ground_truth_file: Path to data/ground_truth/<task_type>.json. Each
        entry carries `peds_source` lineage. Ground truth without PEDS
        lineage is rejected by the loader.
      model_override: If set, use this as `model` in the artifact (for
        anonymization of competitor results per the neutrality policy).
      verifier_version: Version string of the current verifier baked into
        the artifact for drift detection.

    Raises:
      GroundTruthMissingError: if any row in run_file lacks a ground-truth entry.
      ValueError: if run_file is missing required top-level keys.
    """
    run = json.loads(run_file.read_text(encoding="utf-8"))

    if "model" not in run or "run_date" not in run or "detailed_results" not in run:
        raise ValueError(
            f"Run file {run_file} missing required keys: model, run_date, detailed_results"
        )

    truth = load_ground_truth(ground_truth_file, task_type=task_type)

    # First collect labels deterministically. Labels = union of every
    # predicted value AND every ground-truth value observed. The union
    # ensures hallucinated-only classes (model emits a class that never
    # appears in truth) are still represented.
    observed_labels: set[str] = set()
    # Track source-file row count for the task to audit total.
    task_rows: list[dict[str, Any]] = [
        r for r in run["detailed_results"] if r.get("task_type") == task_type
    ]

    if not task_rows:
        raise ValueError(
            f"No rows in {run_file} with task_type={task_type!r}. "
            "Empty matrices are never published."
        )

    # Per-case predicted/truth extraction. Quarantined cases are those for
    # which ground truth exists in the file but PEDS lineage has been
    # marked `quarantined: true` (human review pending). Those cases are
    # tracked separately and NOT shown in the matrix cells.
    rows_with_truth: list[tuple[str, str | None, str]] = []
    quarantined_ids: list[str] = []
    for row in task_rows:
        test_id = row.get("test_id")
        if not test_id:
            raise ValueError(f"Row in {run_file} missing test_id: {row!r}")
        if test_id not in truth:
            raise GroundTruthMissingError(test_id)
        truth_row = truth[test_id]
        if truth_row.get("quarantined"):
            quarantined_ids.append(test_id)
            continue
        predicted, reference = extract_predictions_and_truth(
            row, truth_row, task_type
        )
        rows_with_truth.append((test_id, predicted, reference))
        if predicted is not None:
            observed_labels.add(predicted)
        observed_labels.add(reference)

    labels = tuple(sorted(observed_labels))
    n = len(labels)
    idx = {label: i for i, label in enumerate(labels)}

    matrix = [[0 for _ in range(n)] for _ in range(n)]
    cell_trace_builder: dict[tuple[str, str], list[str]] = {}
    unparseable_ids: list[str] = []

    # SINGLE-PASS: iterate once, incrementing matrix and appending to trace
    # in lockstep. Appending outside this loop is forbidden.
    for test_id, predicted, reference in rows_with_truth:
        if predicted is None:
            unparseable_ids.append(test_id)
            continue
        i = idx[reference]
        j = idx[predicted]
        matrix[i][j] += 1
        key = (reference, predicted)
        cell_trace_builder.setdefault(key, []).append(test_id)

    # Derive hallucinated_labels: classes that appear in predictions but
    # NOT in any ground-truth reference value across the dataset.
    truth_label_set = {reference for _, _, reference in rows_with_truth}
    hallucinated = tuple(
        sorted(label for label in labels if label not in truth_label_set)
    )

    # cell_traces deterministically ordered by (ground_truth, predicted).
    cell_traces = tuple(
        ConfusionCellTrace(
            ground_truth=gt,
            predicted=pr,
            test_ids=tuple(sorted(ids)),
        )
        for (gt, pr), ids in sorted(cell_trace_builder.items())
    )

    total = len(task_rows)
    matrix_tuple = tuple(tuple(row) for row in matrix)

    # Invariant check inline so a misbuilt artifact cannot escape this
    # function. Verifier re-checks independently.
    matrix_sum = sum(sum(row) for row in matrix_tuple)
    if matrix_sum + len(unparseable_ids) + len(quarantined_ids) != total:
        raise AssertionError(
            f"Invariant violation: matrix_sum({matrix_sum}) + "
            f"unparseable({len(unparseable_ids)}) + "
            f"quarantined({len(quarantined_ids)}) != total({total})"
        )
    for trace in cell_traces:
        i = idx[trace.ground_truth]
        j = idx[trace.predicted]
        if matrix_tuple[i][j] != len(trace.test_ids):
            raise AssertionError(
                f"Invariant violation: cell[{trace.ground_truth},{trace.predicted}]="
                f"{matrix_tuple[i][j]} but trace has {len(trace.test_ids)} test_ids"
            )

    return ConfusionMatrixResult(
        schema_version=SCHEMA_VERSION,
        model=model_override or str(run["model"]),
        run_date=str(run["run_date"]),
        task_type=task_type,
        labels=labels,
        matrix=matrix_tuple,
        cell_traces=cell_traces,
        unparseable=len(unparseable_ids),
        unparseable_test_ids=tuple(sorted(unparseable_ids)),
        quarantined=len(quarantined_ids),
        quarantined_test_ids=tuple(sorted(quarantined_ids)),
        total=total,
        hallucinated_labels=hallucinated,
        source_run_file=str(run_file),
        source_sha256=_sha256_of_file(run_file),
        ground_truth_file=str(ground_truth_file),
        ground_truth_sha256=_sha256_of_file(ground_truth_file),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        verifier_version=verifier_version,
    )


def dump_matrix_json(result: ConfusionMatrixResult, out_path: Path) -> None:
    """Deterministic JSON serialization.

    Uses sort_keys=True, indent=2, ensure_ascii=False. Line endings are
    enforced to \\n via explicit write. .gitattributes pins the same in
    the repo so byte-identical output survives cross-platform checkout.
    """
    payload = result.as_json()
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
    if not text.endswith("\n"):
        text = text + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")


def per_class_stats(
    result: ConfusionMatrixResult,
) -> list[dict[str, Any]]:
    """Compute per-class precision, recall, F1 from the matrix.

    Uses the standard convention rows=ground truth, cols=predicted.

    For class c:
      TP = matrix[c][c]
      FP = sum(matrix[i][c] for i != c)
      FN = sum(matrix[c][j] for j != c)
      precision = TP / (TP + FP) if denom > 0 else None
      recall    = TP / (TP + FN) if denom > 0 else None
      f1        = 2 * P * R / (P + R) if both present and nonzero else None
    """
    stats = []
    for i, label in enumerate(result.labels):
        tp = result.matrix[i][i]
        fp = sum(result.matrix[k][i] for k in range(len(result.labels)) if k != i)
        fn = sum(result.matrix[i][k] for k in range(len(result.labels)) if k != i)
        support = sum(result.matrix[i])
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = None
        stats.append(
            {
                "label": label,
                "support": support,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "hallucinated": label in result.hallucinated_labels,
            }
        )
    return stats
