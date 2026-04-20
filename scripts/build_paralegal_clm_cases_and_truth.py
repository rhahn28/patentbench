"""Generate paralegal_clm_extraction benchmark cases + ground truth.

Inputs:
  data/real_oa/google_patents_claims.jsonl  - independent/dependent counts
    pulled from Google Patents per patent. Produced by
    scripts/pull_paralegal_claim_data.py.
  data/real_oa/uspto_peds_sample.jsonl      - patent metadata (title, TC).

Outputs:
  data/benchmark_cases/paralegal_clm_extraction.jsonl
    - harness-compatible case records. Each row:
      { id, task_type, application_number, patent_number, prompt,
        expected_output: {num_independent_claims, num_dependent_claims} }
  data/ground_truth/paralegal_clm_extraction.json
    - confusion-matrix ground truth keyed by test_id, with
      google_patents_source lineage + source="google_patents".

Deterministic: given the same inputs the outputs are byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GP_PATH = REPO_ROOT / "data" / "real_oa" / "google_patents_claims.jsonl"
PEDS_PATH = REPO_ROOT / "data" / "real_oa" / "uspto_peds_sample.jsonl"
CASES_OUT = REPO_ROOT / "data" / "benchmark_cases" / "paralegal_clm_extraction.jsonl"
TRUTH_OUT = REPO_ROOT / "data" / "ground_truth" / "paralegal_clm_extraction.json"

PROMPT_TEMPLATE = (
    "For US patent number US{pn} (application {app}, titled \"{title}\"), "
    "count the independent and dependent claims in the issued grant. "
    "Return a JSON object with two integer fields: num_independent_claims "
    "and num_dependent_claims. Do not include prose outside the JSON."
)


def _peds_index() -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    with PEDS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[row["application_number"]] = row
    return out


def main() -> int:
    peds = _peds_index()
    cases: list[dict[str, object]] = []
    truth: dict[str, dict[str, object]] = {}

    with GP_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            gp = json.loads(line)
            app = gp["application_number"]
            pn = gp["patent_number"]
            peds_row = peds.get(app)
            if peds_row is None:
                raise SystemExit(
                    f"No PEDS metadata for {app}; cannot build case safely."
                )
            indep = int(gp["num_independent"])
            dep = int(gp["num_dependent"])
            if indep <= 0:
                # A grant with zero independent claims is structurally
                # impossible; flag rather than silently skip.
                raise SystemExit(
                    f"Parse produced 0 independent claims for US{pn}; "
                    "refusing to ship a malformed case."
                )
            case_id = f"clm_{app}"
            cases.append(
                {
                    "id": case_id,
                    "task_type": "paralegal_clm_extraction",
                    "tier": 2,
                    "application_number": app,
                    "patent_number": pn,
                    "technology_center": peds_row.get("technology_center", ""),
                    "art_unit": peds_row.get("art_unit", ""),
                    "prompt": PROMPT_TEMPLATE.format(
                        pn=pn, app=app, title=peds_row.get("patent_title", "")
                    ),
                    "expected_output": {
                        "num_independent_claims": indep,
                        "num_dependent_claims": dep,
                    },
                }
            )
            truth[case_id] = {
                "num_independent_claims": indep,
                "num_dependent_claims": dep,
                "google_patents_source": {
                    "patent_number": pn,
                    "patent_url": gp["patent_url"],
                    "retrieved_at": gp["retrieved_at"],
                    "raw_html_sha256": gp["raw_html_sha256"],
                },
                "source": "google_patents",
            }

    CASES_OUT.parent.mkdir(parents=True, exist_ok=True)
    TRUTH_OUT.parent.mkdir(parents=True, exist_ok=True)

    # JSONL: one compact row per line, deterministic key order.
    with CASES_OUT.open("w", encoding="utf-8", newline="\n") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")

    # JSON: pretty, sorted.
    text = json.dumps(truth, sort_keys=True, indent=2, ensure_ascii=False)
    if not text.endswith("\n"):
        text = text + "\n"
    TRUTH_OUT.write_text(text, encoding="utf-8", newline="\n")

    print(f"Wrote {len(cases)} cases to {CASES_OUT}")
    print(f"Wrote {len(truth)} truth rows to {TRUTH_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
