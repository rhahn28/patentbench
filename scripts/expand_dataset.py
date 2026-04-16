#!/usr/bin/env python3
"""Expand PatentBench dataset to 7,200+ cases using USPTO PEDS prosecution data.

Generates test cases from data/real_oa/uspto_peds_expanded.jsonl (321 applications,
1,103 prosecution events, 437 Office Actions).

Per Office Action (437):
  - deadline_calculation (basic shortened + max deadline)
  - action_classification (Final vs Non-Final)
  - extension_fee_computation (× 3 entity statuses)
  - deadline_with_extension (× 3 extension months)

Per Application (321):
  - examiner_extraction
  - entity_status_determination
  - timeline_analysis
  - prosecution_history_parsing
  - fee_computation (× 3 fee types)
  - technology_center_classification
  - filing_date_extraction
  - prosecution_strategy

Usage:
    python scripts/expand_dataset.py
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PEDS_FILE = DATA_DIR / "real_oa" / "uspto_peds_expanded.jsonl"
OUT_FILE = DATA_DIR / "real_oa" / "generated_cases.jsonl"

# USPTO fee schedule (2026 estimates, in dollars)
USPTO_FEES = {
    "filing_utility": {"micro": 80, "small": 160, "large": 320},
    "search": {"micro": 165, "small": 330, "large": 660},
    "examination": {"micro": 191, "small": 382, "large": 764},
    "extension_1_month": {"micro": 52, "small": 104, "large": 208},
    "extension_2_month": {"micro": 152, "small": 304, "large": 608},
    "extension_3_month": {"micro": 356, "small": 712, "large": 1424},
    "rce": {"micro": 320, "small": 640, "large": 1280},
}

# Office Action codes
OA_CODES = {
    "CTNF": ("Non-Final", False),
    "MCTNF": ("Non-Final", False),  # Mail event (skip, paired with CTNF)
    "CTFR": ("Final", True),
    "MCTFR": ("Final", True),  # Mail event (skip, paired with CTFR)
}


def normalize_entity(entity: str) -> str:
    """Map PEDS entity status to micro/small/large."""
    e = (entity or "").lower()
    if "micro" in e:
        return "micro"
    if "small" in e or "discounted" in e:
        return "small"
    return "large"


def add_months(date: datetime, months: int) -> datetime:
    """Add N months to a date (simple calendar arithmetic)."""
    m = date.month - 1 + months
    year = date.year + m // 12
    month = m % 12 + 1
    day = min(date.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30,
                         31, 31, 30, 31, 30, 31][month - 1])
    return date.replace(year=year, month=month, day=day)


def get_office_actions(app: dict) -> list[dict]:
    """Extract OA events from an application (deduplicated, prefer CTNF/CTFR over M* variants)."""
    seen_dates: dict[tuple, dict] = {}
    for ev in app.get("prosecution_events", []):
        code = ev.get("code", "")
        if code not in OA_CODES:
            continue
        action_type, is_final = OA_CODES[code]
        date = ev.get("date", "")
        # Prefer non-M prefix (actual action over mail event)
        key = (date, action_type)
        if key not in seen_dates or not code.startswith("M"):
            seen_dates[key] = {
                "date": date,
                "action_type": action_type,
                "is_final": is_final,
                "code": code,
            }
    return sorted(seen_dates.values(), key=lambda x: x["date"])


def parse_date(d: str) -> datetime | None:
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


# ---- Case generators ----


def gen_deadline_calculation(app: dict, oa: dict, idx: int) -> dict | None:
    """Standard deadline: 3-month shortened + 6-month max."""
    mail_date = parse_date(oa["date"])
    if not mail_date:
        return None
    shortened = add_months(mail_date, 3)
    max_dl = add_months(mail_date, 6)
    app_num = app.get("application_number", "")
    return {
        "id": f"deadline_{oa['action_type'].lower()}_{app_num}_{idx}",
        "domain": "administration",
        "tier": 1,
        "task_type": "deadline_calculation",
        "prompt": (
            f"A {oa['action_type']} Office Action was mailed on {oa['date']} for "
            f"application {app_num}. What is the shortened statutory response "
            f"deadline and the maximum statutory deadline?"
        ),
        "reference_answer": json.dumps({
            "shortened_deadline": shortened.strftime("%Y-%m-%d"),
            "max_deadline": max_dl.strftime("%Y-%m-%d"),
            "action_type": oa["action_type"],
            "explanation": (
                f"{oa['action_type']} OA: 3 months shortened period, "
                f"6 months statutory max under 37 CFR 1.134"
            ),
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num, "oa_date": oa["date"]},
    }


def gen_deadline_with_extension(app: dict, oa: dict, months: int, idx: int) -> dict | None:
    """Deadline with N-month extension filed."""
    mail_date = parse_date(oa["date"])
    if not mail_date:
        return None
    shortened = add_months(mail_date, 3)
    extended = add_months(shortened, months)
    app_num = app.get("application_number", "")
    return {
        "id": f"deadline_ext{months}_{app_num}_{idx}",
        "domain": "administration",
        "tier": 1,
        "task_type": "deadline_calculation",
        "prompt": (
            f"A {oa['action_type']} Office Action was mailed on {oa['date']} for "
            f"application {app_num}. If the applicant files a {months}-month "
            f"extension of time under 37 CFR 1.136(a), what is the extended "
            f"response deadline?"
        ),
        "reference_answer": json.dumps({
            "shortened_deadline": shortened.strftime("%Y-%m-%d"),
            "extended_deadline": extended.strftime("%Y-%m-%d"),
            "extension_months": months,
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num, "oa_date": oa["date"]},
    }


def gen_action_classification(app: dict, oa: dict, idx: int) -> dict:
    """Classify OA as Final or Non-Final."""
    app_num = app.get("application_number", "")
    return {
        "id": f"classify_{app_num}_{oa['date']}_{idx}",
        "domain": "administration",
        "tier": 1,
        "task_type": "action_classification",
        "prompt": (
            f"For application {app_num}, an Office Action was mailed on "
            f"{oa['date']}. Is this a Final or Non-Final Office Action?"
        ),
        "reference_answer": json.dumps({
            "action_type": oa["action_type"],
            "is_final": oa["is_final"],
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num, "oa_date": oa["date"]},
    }


def gen_extension_fee(app: dict, oa: dict, entity: str, months: int, idx: int) -> dict:
    """Extension fee lookup for entity status and duration."""
    app_num = app.get("application_number", "")
    fee_key = f"extension_{months}_month"
    fee = USPTO_FEES[fee_key][entity]
    return {
        "id": f"ext_fee_{entity}_{months}mo_{app_num}_{idx}",
        "domain": "administration",
        "tier": 1,
        "task_type": "fee_computation",
        "prompt": (
            f"For application {app_num} ({entity} entity), what is the USPTO fee "
            f"for a {months}-month extension of time under 37 CFR 1.136(a) in "
            f"response to the {oa['date']} Office Action?"
        ),
        "reference_answer": json.dumps({
            "fee_amount": fee,
            "entity_status": entity,
            "extension_months": months,
            "fee_code": fee_key,
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_examiner_extraction(app: dict) -> dict | None:
    """Extract examiner name from prosecution record."""
    examiner = app.get("examiner_name", "").strip()
    if not examiner:
        return None
    app_num = app.get("application_number", "")
    return {
        "id": f"examiner_{app_num}",
        "domain": "prosecution",
        "tier": 1,
        "task_type": "examiner_extraction",
        "prompt": (
            f"For USPTO application {app_num} (Art Unit "
            f"{app.get('art_unit', '')}), who is the assigned examiner?"
        ),
        "reference_answer": json.dumps({
            "examiner_name": examiner,
            "art_unit": app.get("art_unit", ""),
            "technology_center": app.get("technology_center", ""),
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_entity_status(app: dict) -> dict | None:
    """Determine entity status (micro/small/large)."""
    entity_raw = app.get("entity_status", "")
    if not entity_raw:
        return None
    entity = normalize_entity(entity_raw)
    app_num = app.get("application_number", "")
    return {
        "id": f"entity_{app_num}",
        "domain": "administration",
        "tier": 1,
        "task_type": "entity_status",
        "prompt": (
            f"Based on USPTO records for application {app_num} "
            f"(filed {app.get('filing_date', '')}), what is the applicant's "
            f"entity status for fee purposes (micro, small, or large)?"
        ),
        "reference_answer": entity,
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num, "raw_status": entity_raw},
    }


def gen_timeline_analysis(app: dict) -> dict | None:
    """Count events and extract timeline boundaries."""
    events = app.get("prosecution_events", [])
    if not events:
        return None
    dates = sorted(e.get("date", "") for e in events if e.get("date"))
    if not dates:
        return None
    oa_count = sum(1 for e in events if e.get("code") in ("CTNF", "CTFR"))
    app_num = app.get("application_number", "")
    return {
        "id": f"timeline_{app_num}",
        "domain": "administration",
        "tier": 2,
        "task_type": "timeline_analysis",
        "prompt": (
            f"Analyze the prosecution timeline for application {app_num}. "
            f"How many total prosecution events are recorded, what were the "
            f"first and last event dates, and how many Office Actions were issued?"
        ),
        "reference_answer": json.dumps({
            "total_events": len(events),
            "first_event_date": dates[0],
            "last_event_date": dates[-1],
            "total_oa_count": oa_count,
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_prosecution_history_parsing(app: dict) -> dict | None:
    """Extract structured prosecution history."""
    events = app.get("prosecution_events", [])
    if not events:
        return None
    app_num = app.get("application_number", "")
    oa_dates = [e["date"] for e in events if e.get("code") in ("CTNF", "CTFR")]
    allowance_dates = [e["date"] for e in events if e.get("code") == "CNOA"]
    return {
        "id": f"history_{app_num}",
        "domain": "prosecution",
        "tier": 2,
        "task_type": "prosecution_history_parsing",
        "prompt": (
            f"Parse the prosecution history for application {app_num}. "
            f"List the dates of all Office Actions and any Notice of Allowance."
        ),
        "reference_answer": json.dumps({
            "oa_dates": oa_dates,
            "allowance_dates": allowance_dates,
            "status": app.get("status", ""),
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_fee_computation(app: dict, fee_type: str) -> dict | None:
    """Basic filing/search/examination fee lookup."""
    entity_raw = app.get("entity_status", "")
    if not entity_raw:
        return None
    entity = normalize_entity(entity_raw)
    fee_map = {
        "filing": "filing_utility",
        "search": "search",
        "examination": "examination",
    }
    fee_key = fee_map[fee_type]
    fee = USPTO_FEES[fee_key][entity]
    app_num = app.get("application_number", "")
    return {
        "id": f"fee_{fee_type}_{app_num}",
        "domain": "administration",
        "tier": 1,
        "task_type": "fee_computation",
        "prompt": (
            f"For utility patent application {app_num} filed by a {entity} "
            f"entity, what is the USPTO {fee_type} fee?"
        ),
        "reference_answer": json.dumps({
            "fee_amount": fee,
            "entity_status": entity,
            "fee_type": fee_type,
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_technology_center(app: dict) -> dict | None:
    """Identify technology center from application."""
    tc = app.get("technology_center", "")
    if not tc:
        return None
    app_num = app.get("application_number", "")
    return {
        "id": f"tc_{app_num}",
        "domain": "prosecution",
        "tier": 1,
        "task_type": "technology_center_classification",
        "prompt": (
            f"Application {app_num} is assigned to Art Unit {app.get('art_unit', '')}. "
            f"What USPTO Technology Center handles this application?"
        ),
        "reference_answer": json.dumps({
            "technology_center": tc,
            "tc_description": app.get("tc_description", ""),
            "art_unit": app.get("art_unit", ""),
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_filing_date(app: dict) -> dict | None:
    """Extract filing date."""
    filing = app.get("filing_date", "")
    if not filing:
        return None
    app_num = app.get("application_number", "")
    return {
        "id": f"filing_{app_num}",
        "domain": "administration",
        "tier": 1,
        "task_type": "filing_date_extraction",
        "prompt": (
            f"What is the filing date of USPTO application {app_num}?"
        ),
        "reference_answer": json.dumps({
            "filing_date": filing,
            "application_number": app_num,
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


def gen_prosecution_strategy(app: dict) -> dict | None:
    """Recommend prosecution strategy based on history."""
    events = app.get("prosecution_events", [])
    oa_count = sum(1 for e in events if e.get("code") in ("CTNF", "CTFR"))
    final_count = sum(1 for e in events if e.get("code") == "CTFR")
    if oa_count == 0:
        return None
    app_num = app.get("application_number", "")

    # Simple strategy heuristic
    if final_count >= 2:
        strategy = "appeal"
        rationale = "Multiple final rejections suggest appeal may be warranted"
    elif final_count == 1:
        strategy = "rce_or_appeal"
        rationale = "One final rejection - consider RCE with amendments or appeal"
    elif oa_count >= 2:
        strategy = "amend_and_respond"
        rationale = "Multiple non-final OAs - continue amending and arguing"
    else:
        strategy = "respond"
        rationale = "First OA - prepare substantive response with amendments"

    return {
        "id": f"strategy_{app_num}",
        "domain": "prosecution",
        "tier": 2,
        "task_type": "prosecution_strategy",
        "prompt": (
            f"Application {app_num} has received {oa_count} Office Action(s), "
            f"including {final_count} Final rejection(s). What is the "
            f"recommended next prosecution step?"
        ),
        "reference_answer": json.dumps({
            "recommended_strategy": strategy,
            "oa_count": oa_count,
            "final_count": final_count,
            "rationale": rationale,
        }),
        "evaluation_layers": ["deterministic"],
        "metadata": {"application_number": app_num},
    }


# ---- Main expansion driver ----


def expand_from_peds() -> list[dict]:
    """Generate all test cases from PEDS expanded data."""
    apps = []
    with open(PEDS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                apps.append(json.loads(line))

    log.info("Loaded %d USPTO applications from PEDS", len(apps))

    cases: list[dict] = []
    counts: dict[str, int] = {}

    def add(case: dict | None, tag: str) -> None:
        if case is not None:
            cases.append(case)
            counts[tag] = counts.get(tag, 0) + 1

    # Per-application cases
    for app in apps:
        add(gen_examiner_extraction(app), "examiner_extraction")
        add(gen_entity_status(app), "entity_status")
        add(gen_timeline_analysis(app), "timeline_analysis")
        add(gen_prosecution_history_parsing(app), "prosecution_history_parsing")
        add(gen_technology_center(app), "technology_center_classification")
        add(gen_filing_date(app), "filing_date_extraction")
        add(gen_prosecution_strategy(app), "prosecution_strategy")
        for fee_type in ("filing", "search", "examination"):
            add(gen_fee_computation(app, fee_type), "fee_computation")

    # Per-OA cases
    for app in apps:
        for idx, oa in enumerate(get_office_actions(app)):
            add(gen_deadline_calculation(app, oa, idx), "deadline_calculation")
            add(gen_action_classification(app, oa, idx), "action_classification")
            for months in (1, 2, 3):
                add(gen_deadline_with_extension(app, oa, months, idx),
                    "deadline_with_extension")
            for entity in ("micro", "small", "large"):
                for months in (1, 2, 3):
                    add(gen_extension_fee(app, oa, entity, months, idx),
                        "extension_fee_computation")

    log.info("\nGenerated cases by task type:")
    for tag, n in sorted(counts.items(), key=lambda x: -x[1]):
        log.info("  %4d  %s", n, tag)
    log.info("\nTotal generated: %d", len(cases))

    return cases


def main() -> None:
    log.info("Expanding PatentBench dataset from USPTO PEDS data\n")
    cases = expand_from_peds()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    log.info("\nWrote %d cases to %s", len(cases), OUT_FILE.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
