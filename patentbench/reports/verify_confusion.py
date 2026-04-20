"""Independent verifier for committed confusion-matrix artifacts.

Re-reads the source run file, re-loads the ground truth, rebuilds the
matrix from scratch, and compares every cell, every trace, every SHA, and
the label ordering against the committed artifact. Any mismatch fails
loud so that a fabricated or drifted artifact cannot survive CI.

Run via: `python -m patentbench.reports.verify_confusion path/to/matrix.json`

Exit codes:
  0 - artifact matches reconstructed result byte-for-byte on the audited
      fields
  1 - arithmetic or trace mismatch
  2 - SHA mismatch (source data changed since artifact was generated)
  3 - schema or file error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from patentbench.reports.confusion import (
    SCHEMA_VERSION,
    build_confusion_matrix,
)


def verify(artifact_path: Path) -> int:
    if not artifact_path.is_file():
        print(f"Artifact not found: {artifact_path}", file=sys.stderr)
        return 3
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Artifact JSON parse error: {exc}", file=sys.stderr)
        return 3

    if artifact.get("schema_version") != SCHEMA_VERSION:
        print(
            f"Schema mismatch: artifact={artifact.get('schema_version')} "
            f"verifier={SCHEMA_VERSION}",
            file=sys.stderr,
        )
        return 3

    run_file = Path(artifact["source_run_file"])
    truth_file = Path(artifact["ground_truth_file"])

    if not run_file.is_file():
        print(f"Source run file missing: {run_file}", file=sys.stderr)
        return 2
    if not truth_file.is_file():
        print(f"Ground truth file missing: {truth_file}", file=sys.stderr)
        return 2

    rebuilt = build_confusion_matrix(
        run_file=run_file,
        task_type=artifact["task_type"],
        ground_truth_file=truth_file,
        model_override=artifact.get("model"),
        verifier_version=artifact.get("verifier_version", "1.0.0"),
    )

    errors: list[str] = []
    if rebuilt.source_sha256 != artifact["source_sha256"]:
        errors.append(
            f"source_sha256 drift: artifact={artifact['source_sha256'][:12]} "
            f"rebuilt={rebuilt.source_sha256[:12]}"
        )
    if rebuilt.ground_truth_sha256 != artifact["ground_truth_sha256"]:
        errors.append(
            f"ground_truth_sha256 drift: artifact={artifact['ground_truth_sha256'][:12]} "
            f"rebuilt={rebuilt.ground_truth_sha256[:12]}"
        )
    if list(rebuilt.labels) != artifact["labels"]:
        errors.append(f"labels mismatch: {rebuilt.labels} vs {artifact['labels']}")
    if [list(r) for r in rebuilt.matrix] != artifact["matrix"]:
        errors.append("matrix values differ")
    if rebuilt.unparseable != artifact["unparseable"]:
        errors.append(
            f"unparseable count differs: rebuilt={rebuilt.unparseable} "
            f"artifact={artifact['unparseable']}"
        )
    if rebuilt.quarantined != artifact["quarantined"]:
        errors.append(
            f"quarantined count differs: rebuilt={rebuilt.quarantined} "
            f"artifact={artifact['quarantined']}"
        )
    if rebuilt.total != artifact["total"]:
        errors.append(
            f"total differs: rebuilt={rebuilt.total} artifact={artifact['total']}"
        )

    # Trace correctness: for every non-zero matrix cell, the trace has
    # exactly that many test_ids, and each test_id refers to a row in the
    # source run file.
    run_ids = {
        r.get("test_id")
        for r in json.loads(run_file.read_text(encoding="utf-8")).get(
            "detailed_results", []
        )
        if r.get("test_id")
    }
    rebuilt_traces = {
        (t.ground_truth, t.predicted): tuple(t.test_ids) for t in rebuilt.cell_traces
    }
    for gt_i, gt in enumerate(rebuilt.labels):
        for pr_j, pr in enumerate(rebuilt.labels):
            cell_val = rebuilt.matrix[gt_i][pr_j]
            trace = rebuilt_traces.get((gt, pr), ())
            if cell_val == 0:
                if trace:
                    errors.append(f"cell[{gt},{pr}]=0 but trace has {trace}")
                continue
            if len(trace) != cell_val:
                errors.append(
                    f"cell[{gt},{pr}]={cell_val} but trace has {len(trace)} ids"
                )
                continue
            for tid in trace:
                if tid not in run_ids:
                    errors.append(
                        f"trace test_id {tid!r} for cell[{gt},{pr}] not "
                        "present in source run file"
                    )

    if errors:
        print("Confusion matrix verification FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"VERIFIED: {artifact_path}")
    return 0


@click.command()
@click.argument("artifact", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def main(artifact: Path) -> None:
    """Verify a committed confusion matrix JSON artifact."""
    sys.exit(verify(artifact))


if __name__ == "__main__":
    main()
