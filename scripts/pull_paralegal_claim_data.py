"""Pull independent/dependent claim counts from Google Patents for issued patents.

Source: https://patents.google.com/patent/US{patent_number}{kind}/en (public HTML).
We parse the structural markers `<div class="claim">` (independent claim root)
and `<div class="claim-dependent">` (dependent claim). Google Patents renders
these deterministically from the grant XML, so the counts are stable.

Inputs:
  data/real_oa/uspto_peds_sample.jsonl  - applications with patent_number for
                                          issued cases.

Outputs:
  data/real_oa/google_patents_claims.jsonl  - one JSONL row per patent with
    { application_number, patent_number, patent_url, retrieved_at,
      raw_html_sha256, num_independent, num_dependent }.

Properties:
  - 1 req/s rate limit to Google Patents.
  - Writes atomically; idempotent (safe to re-run).
  - Records SHA-256 of the raw HTML so downstream verifiers can detect drift.
  - Records retrieved_at in RFC3339 UTC.
  - Skips applications without patent_number (pending / abandoned cases).
  - Fails loud on HTTP errors after 3 retries.

CLI:
    python scripts/pull_paralegal_claim_data.py --limit 20
    python scripts/pull_paralegal_claim_data.py   # all issued patents in sample
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT = REPO_ROOT / "data" / "real_oa" / "uspto_peds_sample.jsonl"
OUTPUT = REPO_ROOT / "data" / "real_oa" / "google_patents_claims.jsonl"
USER_AGENT = "PatentBench/0.2 (+https://github.com/rhahn28/patentbench)"
RATE_LIMIT_S = 1.0
MAX_RETRIES = 3
TIMEOUT = 30.0

CLAIM_INDEP = re.compile(r'<div class="claim"(?:\s|>)', re.I)
CLAIM_DEP = re.compile(r'<div class="claim-dependent"(?:\s|>)', re.I)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch(client: httpx.Client, patent_number: str) -> tuple[str, bytes]:
    """Return (url, raw_bytes) for a patent's Google Patents page.

    We try a handful of kind-code suffixes because Google Patents needs them
    to resolve an issued US grant cleanly: B2 for later issuances, B1 for
    first-issuance grants. Pending/published apps (A1/A2) are out of scope
    here because they are not "issued" claim sets.
    """
    last_exc: Exception | None = None
    for kind in ("B2", "B1"):
        url = f"https://patents.google.com/patent/US{patent_number}{kind}/en"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.get(url)
                if response.status_code == 404:
                    break  # try next kind code
                if response.status_code >= 500:
                    time.sleep(2 ** (attempt - 1))
                    continue
                response.raise_for_status()
                return url, response.content
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(
        f"Google Patents fetch failed for US{patent_number}: {last_exc}"
    )


def parse_claim_counts(html: str) -> tuple[int, int]:
    """Return (num_independent, num_dependent) from Google Patents HTML.

    Parses structural class markers only. No heuristics, no LLM.
    """
    indep = len(CLAIM_INDEP.findall(html))
    dep = len(CLAIM_DEP.findall(html))
    return indep, dep


def _iter_input() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with INPUT.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _existing_keys() -> set[str]:
    if not OUTPUT.exists():
        return set()
    keys: set[str] = set()
    with OUTPUT.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            keys.add(obj["application_number"])
    return keys


def main(limit: int | None) -> int:
    rows = _iter_input()
    issued = [r for r in rows if r.get("patent_number")]
    if limit is not None:
        issued = issued[:limit]

    already = _existing_keys()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    failures: list[str] = []
    with httpx.Client(
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        follow_redirects=True,
    ) as client, OUTPUT.open("a", encoding="utf-8", newline="\n") as out:
        last_call = 0.0
        for row in issued:
            app = str(row["application_number"])
            pn = str(row["patent_number"])
            if app in already:
                continue
            # Global rate limit across all kind-code retries for this app.
            elapsed = time.monotonic() - last_call
            wait = RATE_LIMIT_S - elapsed
            if wait > 0:
                time.sleep(wait)
            try:
                url, html_bytes = _fetch(client, pn)
            except RuntimeError as exc:
                print(f"FAIL {app} US{pn}: {exc}", file=sys.stderr)
                failures.append(app)
                last_call = time.monotonic()
                continue
            last_call = time.monotonic()
            html = html_bytes.decode("utf-8", errors="replace")
            indep, dep = parse_claim_counts(html)
            record = {
                "application_number": app,
                "patent_number": pn,
                "patent_url": url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "raw_html_sha256": _sha256(html_bytes),
                "num_independent": indep,
                "num_dependent": dep,
            }
            out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            out.flush()
            processed += 1
            if processed % 10 == 0:
                print(f"  {processed} processed...", file=sys.stderr)

    print(
        f"Done. Processed {processed} new patents. "
        f"Skipped (already in output): {len(already)}. "
        f"Failures: {len(failures)}.",
        file=sys.stderr,
    )
    if failures:
        print("Failed applications: " + ", ".join(failures), file=sys.stderr)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of patents to fetch this run (for smoke testing).",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.limit))
