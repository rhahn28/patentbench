"""
Create PatentBench test cases from real USPTO PEDS data.
Generates Tier 1-3 benchmark cases from pulled prosecution histories.
"""
import json
import os
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "real_oa")
INPUT_FILE = os.path.join(DATA_DIR, "uspto_peds_sample.jsonl")
OUTPUT_FILE = os.path.join(DATA_DIR, "benchmark_cases.jsonl")


def parse_date(date_str):
    """Parse various date formats from USPTO."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.split("+")[0].split("Z")[0], fmt)
        except ValueError:
            continue
    return None


def compute_response_deadline(mail_date_str, is_final=False):
    """Compute OA response deadline: 3 months for non-final, 3 months for final (shortened)."""
    mail_date = parse_date(mail_date_str)
    if not mail_date:
        return None
    # Non-final: 3 months from mailing date
    # Can be extended to 6 months with extensions of time
    months = 3
    deadline = mail_date.replace(month=mail_date.month + months) if mail_date.month + months <= 12 else \
        mail_date.replace(year=mail_date.year + 1, month=(mail_date.month + months) % 12 or 12)
    return deadline.strftime("%Y-%m-%d")


def create_tier1_deadline_case(record, event):
    """Tier 1: What is the response deadline for this Office Action?"""
    is_final = event["code"] == "CTFR"
    deadline = compute_response_deadline(event["date"], is_final)
    if not deadline:
        return None

    return {
        "case_id": f"T1-DL-{record['application_number']}-{event['code']}",
        "tier": 1,
        "task_type": "deadline_computation",
        "domain": "administration",
        "application_number": record["application_number"],
        "technology_center": record["technology_center"],
        "input": {
            "instruction": "What is the response deadline for this Office Action?",
            "office_action_type": "Final" if is_final else "Non-Final",
            "mail_date": event["date"],
            "entity_status": record.get("entity_status", "UNDISCOUNTED"),
        },
        "expected_output": {
            "deadline": deadline,
            "is_final": is_final,
            "extension_available": True,
            "max_extension_months": 3,
        },
        "evaluation": {
            "type": "deterministic",
            "scoring": "exact_match_deadline",
        },
        "source": "USPTO PEDS",
        "created_at": datetime.utcnow().isoformat(),
    }


def create_tier2_parse_case(record):
    """Tier 2: List all prosecution events and classify them."""
    oa_events = [e for e in record["prosecution_events"] if e["code"] in ("CTNF", "CTFR", "CTFP", "CTEQ", "FOJR")]
    if not oa_events:
        return None

    return {
        "case_id": f"T2-PARSE-{record['application_number']}",
        "tier": 2,
        "task_type": "prosecution_history_parsing",
        "domain": "prosecution",
        "application_number": record["application_number"],
        "technology_center": record["technology_center"],
        "input": {
            "instruction": "Parse this prosecution history and list all Office Actions with their types, dates, and event codes.",
            "prosecution_events": record["prosecution_events"],
        },
        "expected_output": {
            "total_office_actions": len(oa_events),
            "office_actions": [
                {
                    "type": "Final" if e["code"] == "CTFR" else "Non-Final" if e["code"] == "CTNF" else e["description"],
                    "code": e["code"],
                    "date": e["date"],
                }
                for e in oa_events
            ],
            "has_allowance": record["has_allowance"],
            "final_status": record["status"],
        },
        "evaluation": {
            "type": "deterministic",
            "scoring": "f1_events",
        },
        "source": "USPTO PEDS",
        "created_at": datetime.utcnow().isoformat(),
    }


def create_tier2_examiner_case(record):
    """Tier 2: Extract examiner information."""
    if not record.get("examiner_name"):
        return None

    return {
        "case_id": f"T2-EXAM-{record['application_number']}",
        "tier": 2,
        "task_type": "examiner_extraction",
        "domain": "analytics",
        "application_number": record["application_number"],
        "technology_center": record["technology_center"],
        "input": {
            "instruction": "Identify the examiner for this application and their art unit.",
            "application_number": record["application_number"],
        },
        "expected_output": {
            "examiner_name": record["examiner_name"],
            "art_unit": record["art_unit"],
            "technology_center": record["technology_center"],
        },
        "evaluation": {
            "type": "deterministic",
            "scoring": "exact_match_fields",
        },
        "source": "USPTO PEDS",
        "created_at": datetime.utcnow().isoformat(),
    }


def create_tier3_classify_case(record, event):
    """Tier 3: Classify the type of Office Action."""
    code_to_type = {
        "CTNF": "Non-Final Rejection",
        "CTFR": "Final Rejection",
        "CTFP": "Final Rejection (Patent)",
        "CTEQ": "Examiner's Answer",
        "FOJR": "First Office Action Rejection",
    }

    return {
        "case_id": f"T3-CLASS-{record['application_number']}-{event['code']}",
        "tier": 3,
        "task_type": "oa_classification",
        "domain": "prosecution",
        "application_number": record["application_number"],
        "technology_center": record["technology_center"],
        "input": {
            "instruction": "Classify this Office Action: What type is it? What are the likely rejection bases (§101, §102, §103, §112)?",
            "event_code": event["code"],
            "event_description": event["description"],
            "event_date": event["date"],
            "patent_title": record["patent_title"],
            "art_unit": record["art_unit"],
        },
        "expected_output": {
            "oa_type": code_to_type.get(event["code"], "Unknown"),
            "is_final": event["code"] in ("CTFR", "CTFP"),
            "technology_area": record["tc_description"],
        },
        "evaluation": {
            "type": "hybrid",
            "deterministic_fields": ["oa_type", "is_final"],
            "llm_judge_fields": ["rejection_bases_analysis"],
        },
        "source": "USPTO PEDS",
        "created_at": datetime.utcnow().isoformat(),
    }


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        print("Run pull_real_oa_data.py first.")
        return

    # Load PEDS data
    records = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Loaded {len(records)} records from PEDS data")

    # Generate benchmark cases
    cases = []
    for record in records:
        # Tier 1: Deadline cases (one per OA event)
        for event in record["prosecution_events"]:
            if event["code"] in ("CTNF", "CTFR", "FOJR"):
                case = create_tier1_deadline_case(record, event)
                if case:
                    cases.append(case)

        # Tier 2: Prosecution history parsing
        case = create_tier2_parse_case(record)
        if case:
            cases.append(case)

        # Tier 2: Examiner extraction
        case = create_tier2_examiner_case(record)
        if case:
            cases.append(case)

        # Tier 3: OA classification
        for event in record["prosecution_events"]:
            if event["code"] in ("CTNF", "CTFR", "CTFP", "CTEQ", "FOJR"):
                case = create_tier3_classify_case(record, event)
                if case:
                    cases.append(case)

    # Write benchmark cases
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case) + "\n")

    # Summary
    from collections import Counter
    tier_counts = Counter(c["tier"] for c in cases)
    type_counts = Counter(c["task_type"] for c in cases)
    tc_counts = Counter(c["technology_center"] for c in cases)

    print(f"\n{'=' * 60}")
    print(f"BENCHMARK CASES GENERATED")
    print(f"{'=' * 60}")
    print(f"Total cases: {len(cases)}")
    print(f"\nBy Tier:")
    for tier, count in sorted(tier_counts.items()):
        print(f"  Tier {tier}: {count}")
    print(f"\nBy Task Type:")
    for task, count in sorted(type_counts.items()):
        print(f"  {task}: {count}")
    print(f"\nBy Technology Center:")
    for tc, count in sorted(tc_counts.items()):
        print(f"  {tc}: {count}")
    print(f"\nOutput: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
