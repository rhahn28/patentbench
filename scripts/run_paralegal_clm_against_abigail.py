"""Run the paralegal_clm_extraction cases against abigail.app.

Produces a `detailed_results` run file compatible with
`patentbench.reports.build_confusion`.

Requires:
  - ABIGAIL_API_KEY environment variable.
  - The abigail.app /api/v1/patentbench/generate endpoint to be available
    (the current deployed build returns HTTP 501 if the
    `expert_prosecution` module is not installed; see
    backend/orchestrator/routes/patentbench.py for the gate).

Inputs:
  data/benchmark_cases/paralegal_clm_extraction.jsonl

Outputs:
  data/benchmark_runs/abigail/{timestamp}_paralegal_clm.json
    {
      "model": "ABIGAIL v3",
      "run_date": "<rfc3339>",
      "detailed_results": [
        {"test_id": "clm_...", "task_type": "paralegal_clm_extraction",
         "raw_response": "..."},
        ...
      ]
    }

Then build the matrix:
    python -m patentbench.reports.build_confusion \
      --run-file data/benchmark_runs/abigail/<ts>_paralegal_clm.json \
      --task-type paralegal_clm_extraction \
      --ground-truth data/ground_truth/paralegal_clm_extraction.json \
      --out reports/confusion_matrices/abigail/paralegal_clm_extraction

And verify:
    python -m patentbench.reports.verify_confusion \
      reports/confusion_matrices/abigail/paralegal_clm_extraction.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = REPO_ROOT / "data" / "benchmark_cases" / "paralegal_clm_extraction.jsonl"
OUT_DIR = REPO_ROOT / "data" / "benchmark_runs" / "abigail"
API_BASE = "https://abigail.app/api/v1/patentbench"


def main(limit: int | None, timeout: float) -> int:
    api_key = os.environ.get("ABIGAIL_API_KEY")
    if not api_key:
        print("ABIGAIL_API_KEY not set; aborting.", file=sys.stderr)
        return 2

    cases: list[dict[str, object]] = []
    with CASES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    if limit is not None:
        cases = cases[:limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"{stamp}_paralegal_clm.json"

    detailed: list[dict[str, object]] = []
    t0 = time.time()
    with httpx.Client(
        timeout=timeout,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    ) as client:
        for i, case in enumerate(cases, 1):
            prompt = case["prompt"]
            response = client.post(
                f"{API_BASE}/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": 200,
                    "temperature": 0,
                    "system_prompt": (
                        "Respond with a single JSON object and nothing else. "
                        "Use keys num_independent_claims and num_dependent_claims."
                    ),
                },
            )
            if response.status_code != 200:
                print(
                    f"[{i}/{len(cases)}] {case['id']}: HTTP "
                    f"{response.status_code} {response.text[:200]}",
                    file=sys.stderr,
                )
                return 3
            data = response.json()
            raw = data.get("response", data.get("text", ""))
            detailed.append(
                {
                    "test_id": case["id"],
                    "task_type": "paralegal_clm_extraction",
                    "raw_response": raw,
                }
            )
            if i % 10 == 0:
                elapsed = time.time() - t0
                print(
                    f"  {i}/{len(cases)} done ({elapsed:.0f}s elapsed)",
                    file=sys.stderr,
                )

    run = {
        "model": "ABIGAIL v3",
        "run_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "detailed_results": detailed,
    }
    text = json.dumps(run, sort_keys=True, indent=2, ensure_ascii=False)
    if not text.endswith("\n"):
        text = text + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    raise SystemExit(main(args.limit, args.timeout))
