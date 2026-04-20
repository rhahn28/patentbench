"""Build data/ground_truth/action_classification.json from PEDS-sourced cases.

Inputs:
  data/benchmark_cases_tier1_2.json
    - PEDS-derived test cases. Each action_classification case has a
      `ground_truth` block computed deterministically from USPTO PEDS
      prosecution_events. No LLM touches this block.
  data/real_oa/uspto_peds_sample.jsonl
    - The raw PEDS pull the ground truth was computed from. Used for the
      `peds_source` lineage block (application_number, retrieved_at,
      peds_field_path, raw_value_hash).

Output:
  data/ground_truth/action_classification.json
    - Keyed by test_id. Each row carries the truth fields required by
      REQUIRED_TRUTH_FIELDS["action_classification"] plus a peds_source
      lineage block that load_ground_truth will verify.

This script is idempotent and deterministic: given the same inputs it writes
byte-identical output. SHA-256 of prosecution_events is captured per app
so a verifier can detect drift if the upstream PEDS pull is later refreshed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = REPO_ROOT / "data" / "benchmark_cases_tier1_2.json"
PEDS_PATH = REPO_ROOT / "data" / "real_oa" / "uspto_peds_sample.jsonl"
OUT_PATH = REPO_ROOT / "data" / "ground_truth" / "action_classification.json"


def _sha256_of_json(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_peds_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    with PEDS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            app_no = str(record["application_number"])
            index[app_no] = record
    return index


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    peds = load_peds_index()

    rows: dict[str, dict[str, Any]] = {}
    for case in cases["test_cases"]:
        if case.get("task_type") != "action_classification":
            continue
        case_id = case["id"]
        app_no = str(case["application_number"])
        gt = case["ground_truth"]
        peds_record = peds.get(app_no)
        if peds_record is None:
            raise SystemExit(
                f"Missing PEDS lineage for application {app_no!r}; cannot "
                "publish truth without verifiable source."
            )
        # The ground truth for this task is computed from prosecution_events.
        # We record the SHA-256 of that exact list as raw_value_hash so drift
        # in upstream PEDS pulls fails loud.
        events = peds_record["prosecution_events"]
        raw_value_hash = _sha256_of_json(events)
        rows[case_id] = {
            "has_non_final": bool(gt["has_non_final"]),
            "has_final": bool(gt["has_final"]),
            "has_allowance": bool(gt["has_allowance"]),
            "total_oa_rounds": int(gt["total_oa_rounds"]),
            "peds_source": {
                "application_number": app_no,
                "retrieved_at": str(peds_record["pulled_at"]),
                "peds_field_path": "prosecution_events",
                "raw_value_hash": raw_value_hash,
            },
            "source": "peds",
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rows, sort_keys=True, indent=2, ensure_ascii=False)
    if not text.endswith("\n"):
        text = text + "\n"
    OUT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {OUT_PATH} with {len(rows)} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
