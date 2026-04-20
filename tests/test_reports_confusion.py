"""Tests for patentbench.reports.confusion — invariants + negative cases.

These tests are the main guard against fabricated artifacts:
  - sum(cells) + unparseable + quarantined == total
  - every non-zero cell has exactly cell_value test_ids in the trace
  - PEDS-less ground truth is rejected
  - LLM-sourced ground truth is rejected
  - quarantined cases are excluded from cells but counted in total
  - byte-for-byte stability across runs on the same input
  - label ordering is alphabetical
  - hallucinated classes are flagged
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from patentbench.reports.confusion import (
    build_confusion_matrix,
    per_class_stats,
)
from patentbench.reports.ground_truth import (
    GroundTruthInvalidError,
    GroundTruthMissingError,
    load_ground_truth,
)

TASK = "paralegal_oa_extraction"


def _peds_block(app: str, path: str, content: dict) -> dict:
    payload = json.dumps(content, sort_keys=True)
    return {
        "application_number": app,
        "retrieved_at": "2026-04-20T12:00:00+00:00",
        "peds_field_path": path,
        "raw_value_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def _truth_row(types: list[str], app: str, *, quarantined: bool = False) -> dict:
    row = {
        "rejection_types": types,
        "claims_affected": [1, 2, 3],
        "cited_references": ["US 10,000,000"],
        "peds_source": _peds_block(app, "prosecutionHistory.events[0]", {"rejection_types": types}),
    }
    if quarantined:
        row["quarantined"] = True
    return row


def _run_row(test_id: str, types: list[str]) -> dict:
    return {
        "test_id": test_id,
        "task_type": TASK,
        "score": "100.0%",
        "raw_response": "```json\n"
        + json.dumps({"rejection_types": types})
        + "\n```",
    }


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture
def dataset(tmp_path: Path) -> dict:
    """Three cases: two agree, one disagrees (model says 103 only, truth is 103+112(b))."""
    run_file = tmp_path / "run.json"
    truth_file = tmp_path / "truth.json"
    _write_json(
        run_file,
        {
            "model": "ABIGAIL v3",
            "run_date": "2026-04-20T00:00:00+00:00",
            "detailed_results": [
                _run_row("oa_001", ["103"]),
                _run_row("oa_002", ["103", "112(b)"]),
                _run_row("oa_003", ["103"]),
            ],
        },
    )
    _write_json(
        truth_file,
        {
            "oa_001": _truth_row(["103"], "16100001"),
            "oa_002": _truth_row(["103", "112(b)"], "16100002"),
            "oa_003": _truth_row(["103", "112(b)"], "16100003"),
        },
    )
    return {"run": run_file, "truth": truth_file}


def test_invariant_sum_cells_plus_buckets_equals_total(dataset):
    result = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )
    matrix_sum = sum(sum(r) for r in result.matrix)
    assert matrix_sum + result.unparseable + result.quarantined == result.total


def test_every_nonzero_cell_trace_len_equals_cell_value(dataset):
    result = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )
    traces = {(t.ground_truth, t.predicted): t.test_ids for t in result.cell_traces}
    for i, gt in enumerate(result.labels):
        for j, pr in enumerate(result.labels):
            cell = result.matrix[i][j]
            if cell == 0:
                assert (gt, pr) not in traces
            else:
                assert len(traces[(gt, pr)]) == cell, f"cell[{gt},{pr}]={cell}"


def test_off_diagonal_correctly_identified(dataset):
    """oa_003: truth=103+112(b), predicted=103 only → off-diagonal cell."""
    result = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )
    assert result.cell("103+112(b)", "103") == 1
    traces = {(t.ground_truth, t.predicted): t.test_ids for t in result.cell_traces}
    assert traces[("103+112(b)", "103")] == ("oa_003",)


def test_labels_alphabetically_sorted(dataset):
    result = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )
    assert list(result.labels) == sorted(result.labels)


def test_unparseable_response_tracked_not_dropped(tmp_path: Path, dataset):
    """Unparseable raw_response must not silently disappear."""
    run_data = json.loads(dataset["run"].read_text(encoding="utf-8"))
    run_data["detailed_results"].append(
        {
            "test_id": "oa_bad",
            "task_type": TASK,
            "score": "0%",
            "raw_response": "sorry I cannot do that Dave",
        }
    )
    truth = json.loads(dataset["truth"].read_text(encoding="utf-8"))
    truth["oa_bad"] = _truth_row(["103"], "16100004")
    run_file = tmp_path / "run2.json"
    truth_file = tmp_path / "truth2.json"
    _write_json(run_file, run_data)
    _write_json(truth_file, truth)

    result = build_confusion_matrix(
        run_file=run_file, task_type=TASK, ground_truth_file=truth_file
    )
    assert result.unparseable == 1
    assert "oa_bad" in result.unparseable_test_ids
    assert sum(sum(r) for r in result.matrix) + result.unparseable == result.total


def test_quarantined_case_excluded_from_matrix(tmp_path: Path, dataset):
    """Quarantined truth rows must not contribute to matrix cells."""
    truth = json.loads(dataset["truth"].read_text(encoding="utf-8"))
    truth["oa_003"]["quarantined"] = True
    truth_file = tmp_path / "truth_q.json"
    _write_json(truth_file, truth)
    result = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=truth_file
    )
    assert result.quarantined == 1
    assert "oa_003" in result.quarantined_test_ids
    # Sum invariant still holds
    assert (
        sum(sum(r) for r in result.matrix)
        + result.unparseable
        + result.quarantined
        == result.total
    )


def test_byte_identical_output_across_runs(tmp_path: Path, dataset):
    """dump_matrix_json twice on the same input must be byte-identical
    modulo the generated_at timestamp (which is excluded below).
    """
    a = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )
    b = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )

    def normalize(r):
        d = r.as_json()
        d.pop("generated_at")
        return json.dumps(d, sort_keys=True, indent=2, ensure_ascii=False)

    assert normalize(a) == normalize(b)


def test_ground_truth_without_peds_source_is_rejected(tmp_path: Path):
    truth = {
        "oa_001": {
            "rejection_types": ["103"],
            "claims_affected": [1],
            "cited_references": ["US 1"],
            # peds_source missing
        }
    }
    truth_file = tmp_path / "bad_truth.json"
    _write_json(truth_file, truth)
    with pytest.raises(GroundTruthInvalidError):
        load_ground_truth(truth_file, task_type=TASK)


def test_ground_truth_sourced_from_llm_is_rejected(tmp_path: Path):
    truth = {
        "oa_001": {
            "source": "llm",
            "rejection_types": ["103"],
            "claims_affected": [1],
            "cited_references": ["US 1"],
            "peds_source": _peds_block("16100001", "x", {"y": 1}),
        }
    }
    truth_file = tmp_path / "llm_truth.json"
    _write_json(truth_file, truth)
    with pytest.raises(GroundTruthInvalidError):
        load_ground_truth(truth_file, task_type=TASK)


def test_ground_truth_sourced_from_abigail_is_rejected(tmp_path: Path):
    truth = {
        "oa_001": {
            "source": "abigail",
            "rejection_types": ["103"],
            "claims_affected": [1],
            "cited_references": ["US 1"],
            "peds_source": _peds_block("16100001", "x", {"y": 1}),
        }
    }
    truth_file = tmp_path / "abi_truth.json"
    _write_json(truth_file, truth)
    with pytest.raises(GroundTruthInvalidError):
        load_ground_truth(truth_file, task_type=TASK)


def test_missing_ground_truth_raises_block(tmp_path: Path, dataset):
    run_data = json.loads(dataset["run"].read_text(encoding="utf-8"))
    run_data["detailed_results"].append(_run_row("oa_orphan", ["103"]))
    run_file = tmp_path / "run_orphan.json"
    _write_json(run_file, run_data)
    with pytest.raises(GroundTruthMissingError) as exc:
        build_confusion_matrix(
            run_file=run_file, task_type=TASK, ground_truth_file=dataset["truth"]
        )
    assert exc.value.test_id == "oa_orphan"


def test_hallucinated_class_flagged(tmp_path: Path):
    """Model emits 'made_up_rejection' that never appears in truth."""
    run_file = tmp_path / "run_h.json"
    truth_file = tmp_path / "truth_h.json"
    _write_json(
        run_file,
        {
            "model": "M",
            "run_date": "2026-04-20T00:00:00+00:00",
            "detailed_results": [
                _run_row("oa_h1", ["103"]),
                _run_row("oa_h2", ["made_up"]),
            ],
        },
    )
    _write_json(
        truth_file,
        {
            "oa_h1": _truth_row(["103"], "1"),
            "oa_h2": _truth_row(["112(b)"], "2"),
        },
    )
    result = build_confusion_matrix(
        run_file=run_file, task_type=TASK, ground_truth_file=truth_file
    )
    assert "made_up" in result.hallucinated_labels
    # Diagonal label "112(b)" should NOT be hallucinated.
    assert "112(b)" not in result.hallucinated_labels


def test_per_class_stats_precision_recall_f1(dataset):
    result = build_confusion_matrix(
        run_file=dataset["run"], task_type=TASK, ground_truth_file=dataset["truth"]
    )
    stats = per_class_stats(result)
    by_label = {s["label"]: s for s in stats}
    # "103" class: TP=1 (oa_001 truth=103 pred=103), FP=1 (oa_003 truth=103+112(b) pred=103), FN=0
    assert by_label["103"]["tp"] == 1
    assert by_label["103"]["fp"] == 1
    assert by_label["103"]["fn"] == 0
    # "103+112(b)" class: TP=1 (oa_002), FP=0, FN=1 (oa_003)
    assert by_label["103+112(b)"]["tp"] == 1
    assert by_label["103+112(b)"]["fp"] == 0
    assert by_label["103+112(b)"]["fn"] == 1


def test_empty_run_raises(tmp_path: Path):
    run_file = tmp_path / "empty.json"
    truth_file = tmp_path / "t.json"
    _write_json(
        run_file,
        {
            "model": "M",
            "run_date": "2026-04-20",
            "detailed_results": [],
        },
    )
    _write_json(truth_file, {})
    with pytest.raises(ValueError, match="No rows"):
        build_confusion_matrix(
            run_file=run_file, task_type=TASK, ground_truth_file=truth_file
        )


def test_run_file_missing_top_level_keys_raises(tmp_path: Path):
    run_file = tmp_path / "broken.json"
    truth_file = tmp_path / "t.json"
    _write_json(run_file, {"detailed_results": []})
    _write_json(truth_file, {})
    with pytest.raises(ValueError, match="missing required keys"):
        build_confusion_matrix(
            run_file=run_file, task_type=TASK, ground_truth_file=truth_file
        )


# -- action_classification (Stage 2 additions) --
#
# These tests cover the new extractor and reference label for the
# action_classification task. The label projection is
# `NF{has_non_final}-F{has_final}-A{has_allowance}`. total_oa_rounds is
# preserved in the truth file for audit but is not a matrix axis.

AC_TASK = "action_classification"


def _ac_peds_block(app: str) -> dict:
    return {
        "application_number": app,
        "retrieved_at": "2026-03-20T22:36:31.381Z",
        "peds_field_path": "prosecution_events",
        "raw_value_hash": hashlib.sha256(app.encode("utf-8")).hexdigest(),
    }


def _ac_truth_row(nf: bool, f: bool, a: bool, rounds: int, app: str) -> dict:
    return {
        "has_non_final": nf,
        "has_final": f,
        "has_allowance": a,
        "total_oa_rounds": rounds,
        "peds_source": _ac_peds_block(app),
        "source": "peds",
    }


def _ac_run_row(test_id: str, nf: bool, f: bool, a: bool, rounds: int) -> dict:
    payload = {
        "has_non_final": nf,
        "has_final": f,
        "has_allowance": a,
        "total_oa_rounds": rounds,
    }
    return {
        "test_id": test_id,
        "task_type": AC_TASK,
        "raw_response": "```json\n" + json.dumps(payload) + "\n```",
    }


def test_action_classification_label_projection_diagonal(tmp_path: Path):
    """Perfect prediction on three representative cases produces a 3x3 diagonal."""
    run_file = tmp_path / "run.json"
    truth_file = tmp_path / "truth.json"
    _write_json(
        run_file,
        {
            "model": "ABIGAIL v3",
            "run_date": "2026-04-20",
            "detailed_results": [
                _ac_run_row("classify_100", True, False, False, 1),
                _ac_run_row("classify_200", True, True, False, 2),
                _ac_run_row("classify_300", True, True, True, 3),
            ],
        },
    )
    _write_json(
        truth_file,
        {
            "classify_100": _ac_truth_row(True, False, False, 1, "100"),
            "classify_200": _ac_truth_row(True, True, False, 2, "200"),
            "classify_300": _ac_truth_row(True, True, True, 3, "300"),
        },
    )
    matrix = build_confusion_matrix(
        run_file=run_file, task_type=AC_TASK, ground_truth_file=truth_file
    )
    assert matrix.labels == ("NF1-F0-A0", "NF1-F1-A0", "NF1-F1-A1")
    assert matrix.cell("NF1-F0-A0", "NF1-F0-A0") == 1
    assert matrix.cell("NF1-F1-A0", "NF1-F1-A0") == 1
    assert matrix.cell("NF1-F1-A1", "NF1-F1-A1") == 1
    assert matrix.total == 3
    assert matrix.unparseable == 0


def test_action_classification_mismatch_records_off_diagonal(tmp_path: Path):
    run_file = tmp_path / "run.json"
    truth_file = tmp_path / "truth.json"
    # Truth says both NF and F; model emits only NF.
    _write_json(
        run_file,
        {
            "model": "ABIGAIL v3",
            "run_date": "2026-04-20",
            "detailed_results": [
                _ac_run_row("classify_501", True, False, False, 1),
            ],
        },
    )
    _write_json(
        truth_file,
        {
            "classify_501": _ac_truth_row(True, True, False, 2, "501"),
        },
    )
    matrix = build_confusion_matrix(
        run_file=run_file, task_type=AC_TASK, ground_truth_file=truth_file
    )
    assert matrix.cell("NF1-F1-A0", "NF1-F0-A0") == 1
    stats = per_class_stats(matrix)
    by_label = {s["label"]: s for s in stats}
    assert by_label["NF1-F1-A0"]["recall"] == 0.0
    assert by_label["NF1-F0-A0"]["precision"] == 0.0


def test_action_classification_non_bool_truth_raises(tmp_path: Path):
    """Truth row with a non-bool boolean must fail loud (no silent coercion)."""
    run_file = tmp_path / "run.json"
    truth_file = tmp_path / "truth.json"
    _write_json(
        run_file,
        {
            "model": "m",
            "run_date": "2026-04-20",
            "detailed_results": [_ac_run_row("classify_1", True, False, False, 1)],
        },
    )
    bad = _ac_truth_row(True, False, False, 1, "1")
    bad["has_non_final"] = "yes"  # string, not bool
    _write_json(truth_file, {"classify_1": bad})
    with pytest.raises(GroundTruthInvalidError, match="non-bool"):
        build_confusion_matrix(
            run_file=run_file, task_type=AC_TASK, ground_truth_file=truth_file
        )


def test_action_classification_non_bool_prediction_is_unparseable(tmp_path: Path):
    """Model emits string booleans (e.g. "true"); row lands in unparseable."""
    run_file = tmp_path / "run.json"
    truth_file = tmp_path / "truth.json"
    _write_json(
        run_file,
        {
            "model": "m",
            "run_date": "2026-04-20",
            "detailed_results": [
                {
                    "test_id": "classify_9",
                    "task_type": AC_TASK,
                    "raw_response": (
                        "```json\n"
                        + json.dumps(
                            {
                                "has_non_final": "true",
                                "has_final": False,
                                "has_allowance": False,
                                "total_oa_rounds": 1,
                            }
                        )
                        + "\n```"
                    ),
                }
            ],
        },
    )
    _write_json(
        truth_file,
        {"classify_9": _ac_truth_row(True, False, False, 1, "9")},
    )
    matrix = build_confusion_matrix(
        run_file=run_file, task_type=AC_TASK, ground_truth_file=truth_file
    )
    assert matrix.unparseable == 1
    assert matrix.unparseable_test_ids == ("classify_9",)
    assert matrix.total == 1
    assert sum(sum(row) for row in matrix.matrix) == 0
