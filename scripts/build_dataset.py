#!/usr/bin/env python3
"""Build unified PatentBench datasets from raw source files.

Transforms all existing data into the canonical DataLoader schema and
populates data/mini/ and data/full/ directories.

Usage:
    python scripts/build_dataset.py
"""

from __future__ import annotations

import json
import logging
import random
from collections import Counter
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Task type -> domain mapping
DOMAIN_MAP = {
    "deadline_calculation": "administration",
    "deadline_computation": "administration",
    "action_classification": "administration",
    "fee_computation": "administration",
    "timeline_analysis": "administration",
    "examiner_extraction": "prosecution",
    "prosecution_history_parsing": "prosecution",
    "prosecution_strategy": "prosecution",
    "103_argument": "prosecution",
    "101_argument": "prosecution",
    "102_argument": "prosecution",
    "112_argument": "prosecution",
    "claim_amendment": "drafting",
    "oa_parsing": "prosecution",
}


def convert_tier12_case(raw: dict) -> dict:
    """Convert Tier 1-2 case (id/question/ground_truth schema)."""
    task_type = raw["task_type"]
    gt = raw["ground_truth"]
    return {
        "id": raw["id"],
        "domain": DOMAIN_MAP.get(task_type, "administration"),
        "tier": raw["tier"],
        "task_type": task_type,
        "prompt": raw["question"],
        "reference_answer": json.dumps(gt) if isinstance(gt, dict) else str(gt),
        "evaluation_layers": ["deterministic"],
        "metadata": {
            "application_number": raw.get("application_number", ""),
            "title": raw.get("title", ""),
        },
    }


def convert_tier3_expanded(raw: dict) -> dict:
    """Convert Tier 3 expanded case (scenario/claim_at_issue/task schema)."""
    parts = [raw.get("scenario", "")]
    if raw.get("claim_at_issue"):
        parts.append(f"\nClaim at issue: {raw['claim_at_issue']}")
    if raw.get("task"):
        parts.append(f"\nTask: {raw['task']}")
    prompt = "\n".join(p for p in parts if p)

    rejection = raw.get("rejection_type", "103")
    task_type = f"{rejection}_argument" if not rejection.endswith("_argument") else rejection

    return {
        "id": raw["id"],
        "domain": "prosecution",
        "tier": raw.get("tier", 3),
        "task_type": task_type,
        "prompt": prompt,
        "reference_answer": raw.get("model_response", ""),
        "evaluation_layers": ["llm_judge"],
        "metadata": {
            "technology_center": raw.get("technology_center", ""),
            "rejection_type": rejection,
        },
    }


def convert_real_oa_case(raw: dict) -> dict:
    """Convert real_oa JSONL case (case_id/input/expected_output schema)."""
    inp = raw.get("input", {})
    expected = raw.get("expected_output", {})
    task_type = raw.get("task_type", "deadline_calculation")

    # Normalize variant names
    if task_type == "deadline_computation":
        task_type = "deadline_calculation"

    # Handle both schemas: some have 'input.instruction', some have 'question'
    if "question" in raw:
        prompt = raw["question"]
    elif isinstance(inp, dict) and "instruction" in inp:
        ctx = "\n".join(f"{k}: {v}" for k, v in inp.items() if k != "instruction")
        prompt = f"{inp['instruction']}\n\n{ctx}" if ctx else inp["instruction"]
    else:
        prompt = str(inp)

    if isinstance(expected, dict):
        ref = json.dumps(expected)
    else:
        ref = str(expected)

    return {
        "id": raw.get("case_id", raw.get("id", "")),
        "domain": raw.get("domain", DOMAIN_MAP.get(task_type, "administration")),
        "tier": raw.get("tier", 1),
        "task_type": task_type,
        "prompt": prompt,
        "reference_answer": ref,
        "evaluation_layers": ["deterministic"] if raw.get("tier", 1) <= 2 else ["llm_judge"],
        "metadata": {
            "application_number": raw.get("application_number", ""),
            "technology_center": raw.get("technology_center", ""),
        },
    }


def load_source_files() -> list[dict]:
    """Load all source files and convert to unified schema."""
    all_cases: list[dict] = []

    # 1. Tier 1-2 (benchmark_cases_tier1_2.json)
    path = DATA_DIR / "benchmark_cases_tier1_2.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        cases = raw.get("test_cases", raw if isinstance(raw, list) else [])
        assert len(cases) > 0, f"No test_cases found in {path}"
        converted = [convert_tier12_case(c) for c in cases]
        all_cases.extend(converted)
        log.info("  [ok] %4d cases from benchmark_cases_tier1_2.json", len(converted))

    # 2. Tier 3 mini JSONL (already in DataLoader format)
    mini_dir = DATA_DIR / "mini"
    if mini_dir.exists():
        for p in sorted(mini_dir.glob("*.jsonl")):
            if p.name == "tier_1_2_cases.jsonl":
                continue  # skip our own generated file
            count = 0
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_cases.append(json.loads(line))
                        count += 1
            log.info("  [ok] %4d cases from mini/%s", count, p.name)

    # 3. Tier 3 expanded (scenario/claim/task schema)
    path = DATA_DIR / "tier3_reasoning_expanded.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        tc_list = raw.get("test_cases", [])
        assert len(tc_list) > 0, f"No test_cases found in {path}"
        converted = [convert_tier3_expanded(c) for c in tc_list]
        all_cases.extend(converted)
        log.info("  [ok] %4d cases from tier3_reasoning_expanded.json", len(converted))

    # 4. real_oa JSONL (case_id/input/expected_output schema)
    path = DATA_DIR / "real_oa" / "benchmark_cases.jsonl"
    if path.exists():
        count = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_cases.append(convert_real_oa_case(json.loads(line)))
                    count += 1
        assert count > 0, f"No cases found in {path}"
        log.info("  [ok] %4d cases from real_oa/benchmark_cases.jsonl", count)

    return all_cases


def deduplicate(cases: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for c in cases:
        if c["id"] not in seen:
            seen.add(c["id"])
            out.append(c)
    return out


def write_jsonl(cases: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    log.info("  -> %4d cases to %s", len(cases), path.relative_to(PROJECT_ROOT))


def build_mini(all_cases: list[dict], target: int = 300) -> list[dict]:
    """Stratified sample across tiers."""
    random.seed(42)
    by_tier: dict[int, list[dict]] = {}
    for c in all_cases:
        by_tier.setdefault(c["tier"], []).append(c)

    mini: list[dict] = []
    for tier in sorted(by_tier):
        pool = by_tier[tier]
        n = max(5, round(len(pool) / len(all_cases) * target))
        n = min(n, len(pool))
        mini.extend(random.sample(pool, n))

    if len(mini) < target and 1 in by_tier:
        used = {c["id"] for c in mini}
        extras = [c for c in by_tier[1] if c["id"] not in used]
        mini.extend(extras[: target - len(mini)])

    return mini[:target]


def main() -> None:
    log.info("Building PatentBench unified datasets\n")
    log.info("Loading sources:")
    all_cases = deduplicate(load_source_files())

    tc = Counter(c["tier"] for c in all_cases)
    tt = Counter(c["task_type"] for c in all_cases)
    log.info("\n  Total unique: %d", len(all_cases))
    log.info("  By tier: %s", dict(sorted(tc.items())))
    log.info("  By task: %s", dict(sorted(tt.items())))

    # Write full/
    log.info("\nWriting data/full/:")
    write_jsonl(all_cases, DATA_DIR / "full" / "all_cases.jsonl")

    # Write mini/
    log.info("\nWriting data/mini/:")
    mini = build_mini(all_cases)
    write_jsonl(mini, DATA_DIR / "mini" / "tier_1_2_cases.jsonl")
    mc = Counter(c["tier"] for c in mini)
    log.info("  Mini total: %d, by tier: %s", len(mini), dict(sorted(mc.items())))

    log.info("\nDone.")


if __name__ == "__main__":
    main()
