"""Ground-truth loading with mandatory PEDS provenance.

Ground-truth rows MUST carry `peds_source` lineage that identifies which
USPTO PEDS application, retrieval timestamp, and field path produced the
reference value. Rows without `peds_source` are rejected. Rows tagged with
`source: "llm"` or `source: "abigail"` are rejected to prevent the
SUT-as-labeler circularity flagged during the adversarial review (ADV-001,
GAP-001).

Rows may be `quarantined: true` when PEDS provenance is ambiguous or two
authoritative sources disagree (GAP-R2-001). Quarantined rows are excluded
from matrix cells but counted in the artifact total so sums reconcile.

Prediction extraction runs on the model's raw_response. The parser is
intentionally small and deterministic: regex for fenced ```json blocks,
fallback to the first balanced-brace substring, None otherwise. `eval` and
`exec` are banned.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class GroundTruthMissingError(Exception):
    """Raised when a run row has no corresponding ground-truth entry."""

    def __init__(self, test_id: str) -> None:
        super().__init__(
            f"Ground truth missing for test_id={test_id!r}. "
            "Publication is blocked until the case is added to the truth "
            "file with verifiable PEDS lineage or explicitly quarantined."
        )
        self.test_id = test_id


class GroundTruthInvalidError(Exception):
    """Raised when a ground-truth file does not meet provenance requirements."""


# Row type alias. We keep it loose because the set of required fields varies
# by task_type. The loader enforces shape per task.
GroundTruthRow = dict[str, Any]


# Per-task required truth fields. The loader fails loud if any required
# field is missing. Adding a task requires a test and attorney sign-off
# per CONTRIBUTING.md task registry policy.
REQUIRED_TRUTH_FIELDS: dict[str, tuple[str, ...]] = {
    "paralegal_oa_extraction": (
        "rejection_types",
        "claims_affected",
        "cited_references",
    ),
    "paralegal_clm_extraction": (
        "independent_claims",
        "dependent_claims",
    ),
    # Admin-tier deterministic tasks kept for future Admin-matrix work.
    # Admin must be 100% accuracy by design (DB-lookup deterministic
    # behavior) so confusion matrix should be diagonal with zero off-diag.
    "deadline_calculation": (
        "shortened_deadline",
        "max_deadline",
        "action_type",
    ),
    # action_classification asks the model to emit a structured tuple
    # describing the prosecution history shape. The confusion-matrix label
    # is derived from has_non_final, has_final, has_allowance; total_oa_rounds
    # is recorded for provenance but is a count, not a class, so it does
    # not enter the matrix axis.
    "action_classification": (
        "has_non_final",
        "has_final",
        "has_allowance",
        "total_oa_rounds",
    ),
}


# Prediction extractors per task. Each returns the predicted LABEL string
# used as the column key in the confusion matrix, or None when the raw
# response cannot be parsed. No task extractor is allowed to invent a label
# that is not present in the model's raw_response.
def _parse_json_block(raw_response: str) -> dict[str, Any] | None:
    """Extract JSON from a model response.

    Order:
      1. Regex-match a ```json ... ``` fenced block.
      2. Fallback: first balanced-brace substring.
      3. Return None.
    """
    if not raw_response:
        return None
    fenced = re.search(r"```json\s*(.*?)```", raw_response, re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Balanced-brace scan; linear O(n).
    depth = 0
    start = -1
    for i, ch in enumerate(raw_response):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(raw_response[start : i + 1])
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    start = -1
                    continue
    return None


def _extract_action_type(row: dict[str, Any]) -> str | None:
    parsed = _parse_json_block(row.get("raw_response", ""))
    if not parsed:
        return None
    value = parsed.get("action_type")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


# For the multi-class paralegal OA extraction task we reduce the
# multi-label rejection-type output to a SORTED-TUPLE label per the
# matrix convention. E.g. a case where the model emits ["103", "112(b)"]
# and the truth is ["103", "112(b)"] produces the label "103+112(b)".
# This mapping is DETERMINISTIC and produces the same label in predicted
# and reference axes so diagonals are diagonal.
def _canonicalize_rejection_set(values: Any) -> str | None:
    if not isinstance(values, list):
        return None
    cleaned: list[str] = []
    for v in values:
        if not isinstance(v, str):
            return None
        stripped = v.strip()
        if not stripped:
            return None
        cleaned.append(stripped)
    if not cleaned:
        return "<none>"
    return "+".join(sorted(set(cleaned)))


def _extract_paralegal_oa(row: dict[str, Any]) -> str | None:
    parsed = _parse_json_block(row.get("raw_response", ""))
    if not parsed:
        return None
    return _canonicalize_rejection_set(parsed.get("rejection_types"))


def _extract_paralegal_clm(row: dict[str, Any]) -> str | None:
    """Label = "I{num_indep}_D{num_dep}" — the structural signature of the
    claim set. Diagonal means the model correctly identified both counts.
    """
    parsed = _parse_json_block(row.get("raw_response", ""))
    if not parsed:
        return None
    indep = parsed.get("independent_claims")
    dep = parsed.get("dependent_claims")
    if not isinstance(indep, list) or not isinstance(dep, list):
        return None
    return f"I{len(indep)}_D{len(dep)}"


def _canonicalize_action_classification(
    has_nf: Any, has_f: Any, has_a: Any
) -> str | None:
    """Project the three booleans into a deterministic label.

    Label format: `NF{0|1}-F{0|1}-A{0|1}`. Any non-bool value short-circuits
    to None so the row lands in the unparseable bucket rather than silently
    producing a misleading class.
    """
    if not isinstance(has_nf, bool) or not isinstance(has_f, bool):
        return None
    if not isinstance(has_a, bool):
        return None
    return f"NF{int(has_nf)}-F{int(has_f)}-A{int(has_a)}"


def _extract_action_classification(row: dict[str, Any]) -> str | None:
    parsed = _parse_json_block(row.get("raw_response", ""))
    if not parsed:
        return None
    return _canonicalize_action_classification(
        parsed.get("has_non_final"),
        parsed.get("has_final"),
        parsed.get("has_allowance"),
    )


EXTRACTORS: dict[str, Any] = {
    "paralegal_oa_extraction": _extract_paralegal_oa,
    "paralegal_clm_extraction": _extract_paralegal_clm,
    "action_classification": _extract_action_classification,
    "deadline_calculation": _extract_action_type,
}


def _reference_label(task_type: str, truth_row: dict[str, Any]) -> str:
    """Derive the reference (ground truth) label for the matrix axis.

    Uses the same canonicalization as the predicted extractor so that
    a correct prediction lands on the diagonal.
    """
    if task_type == "paralegal_oa_extraction":
        canon = _canonicalize_rejection_set(truth_row.get("rejection_types"))
        if canon is None:
            raise GroundTruthInvalidError(
                f"paralegal_oa_extraction truth row has bad rejection_types: "
                f"{truth_row!r}"
            )
        return canon
    if task_type == "paralegal_clm_extraction":
        indep = truth_row.get("independent_claims")
        dep = truth_row.get("dependent_claims")
        if not isinstance(indep, list) or not isinstance(dep, list):
            raise GroundTruthInvalidError(
                f"paralegal_clm_extraction truth row has bad claim lists: "
                f"{truth_row!r}"
            )
        return f"I{len(indep)}_D{len(dep)}"
    if task_type == "action_classification":
        label = _canonicalize_action_classification(
            truth_row.get("has_non_final"),
            truth_row.get("has_final"),
            truth_row.get("has_allowance"),
        )
        if label is None:
            raise GroundTruthInvalidError(
                f"action_classification truth row has non-bool booleans: {truth_row!r}"
            )
        return label
    if task_type == "deadline_calculation":
        value = truth_row.get("action_type")
        if not isinstance(value, str) or not value.strip():
            raise GroundTruthInvalidError(
                f"{task_type} truth row missing action_type: {truth_row!r}"
            )
        return value.strip()
    raise GroundTruthInvalidError(f"Unknown task_type={task_type!r}")


def extract_predictions_and_truth(
    row: dict[str, Any],
    truth_row: dict[str, Any],
    task_type: str,
) -> tuple[str | None, str]:
    """Extract (predicted_label, reference_label) for a run row.

    Predicted may be None when the raw_response cannot be parsed; the
    caller then places the row in the unparseable bucket. Reference is
    always a non-empty string. Raises GroundTruthInvalidError for malformed
    truth rows.
    """
    extractor = EXTRACTORS.get(task_type)
    if extractor is None:
        raise GroundTruthInvalidError(f"No extractor registered for task {task_type!r}")
    predicted = extractor(row)
    reference = _reference_label(task_type, truth_row)
    return predicted, reference


def load_ground_truth(path: Path, task_type: str) -> dict[str, GroundTruthRow]:
    """Load and validate a ground-truth file for the given task.

    Enforces:
      - JSON object keyed by test_id.
      - Each row has `peds_source` with {application_number, retrieved_at,
        peds_field_path, raw_value_hash}.
      - No row has `source: "llm"` or `source: "abigail"`.
      - Required truth fields for the task (per REQUIRED_TRUTH_FIELDS) are
        present unless the row is `quarantined: true`.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GroundTruthInvalidError(
            f"{path} must be a JSON object keyed by test_id"
        )

    required = REQUIRED_TRUTH_FIELDS.get(task_type)
    if required is None:
        raise GroundTruthInvalidError(
            f"task_type {task_type!r} not registered in REQUIRED_TRUTH_FIELDS"
        )

    out: dict[str, GroundTruthRow] = {}
    for test_id, row in data.items():
        if not isinstance(row, dict):
            raise GroundTruthInvalidError(
                f"{path} row for {test_id} must be an object"
            )
        source = row.get("source")
        if source in ("llm", "abigail"):
            raise GroundTruthInvalidError(
                f"{path} row for {test_id} uses banned source={source!r}. "
                "PatentBench ground truth may not be produced by the SUT."
            )
        peds = row.get("peds_source")
        if not isinstance(peds, dict):
            raise GroundTruthInvalidError(
                f"{path} row for {test_id} missing peds_source object"
            )
        for peds_field in (
            "application_number",
            "retrieved_at",
            "peds_field_path",
            "raw_value_hash",
        ):
            if peds_field not in peds:
                raise GroundTruthInvalidError(
                    f"{path} row for {test_id} peds_source missing "
                    f"{peds_field!r}"
                )
        if not row.get("quarantined"):
            missing = [f for f in required if f not in row]
            if missing:
                raise GroundTruthInvalidError(
                    f"{path} row for {test_id} missing required fields "
                    f"for {task_type}: {missing}"
                )
        out[test_id] = row
    return out
