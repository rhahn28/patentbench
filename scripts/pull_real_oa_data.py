"""
Pull real Office Action data from USPTO Patent Examination Data System (PEDS).
Targets 5 Technology Centers for PatentBench-Mini.
"""
import requests
import json
import os
import time
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "real_oa")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "uspto_peds_sample.jsonl")

# Technology Centers to sample
TC_QUERIES = {
    "TC1600_Biotech": {
        "searchText": "appStatus:(patented OR allowed) AND appType:Utility",
        "fq": ["appGrpArtNumber:[1600 TO 1699]"],
        "description": "Biotechnology / Organic Chemistry"
    },
    "TC2100_Software": {
        "searchText": "appStatus:(patented OR allowed) AND appType:Utility",
        "fq": ["appGrpArtNumber:[2100 TO 2199]"],
        "description": "Computer Architecture / Software"
    },
    "TC2800_Electrical": {
        "searchText": "appStatus:(patented OR allowed) AND appType:Utility",
        "fq": ["appGrpArtNumber:[2800 TO 2899]"],
        "description": "Semiconductors / Electrical"
    },
    "TC3600_Business": {
        "searchText": "appStatus:(patented OR allowed) AND appType:Utility",
        "fq": ["appGrpArtNumber:[3600 TO 3699]"],
        "description": "Transportation / Construction / eCommerce"
    },
    "TC3700_Mechanical": {
        "searchText": "appStatus:(patented OR allowed) AND appType:Utility",
        "fq": ["appGrpArtNumber:[3700 TO 3799]"],
        "description": "Mechanical Engineering"
    },
}

PEDS_API = "https://ped.uspto.gov/api/queries"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def query_peds(tc_name, query_config, rows=20):
    """Query USPTO PEDS for applications in a Technology Center."""
    payload = {
        "searchText": query_config["searchText"],
        "fq": query_config.get("fq", []),
        "fl": "*",
        "mm": "100%",
        "df": "patentTitle",
        "facet": False,
        "sort": "appFilingDate desc",
        "start": 0,
        "rows": rows,
    }

    print(f"  Querying PEDS for {tc_name}...")
    try:
        resp = requests.post(PEDS_API, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        docs = data.get("queryResults", {}).get("searchResponse", {}).get("response", {}).get("docs", [])
        print(f"  -> Got {len(docs)} results")
        return docs
    except requests.exceptions.HTTPError as e:
        print(f"  -> HTTP Error {e.response.status_code}: {e.response.text[:200]}")
        return []
    except Exception as e:
        print(f"  -> Error: {e}")
        return []


def query_peds_v2_fallback(tc_name, art_unit_range, rows=20):
    """Fallback: use simpler search parameters."""
    payload = {
        "searchText": f"appGrpArtNumber:[{art_unit_range[0]} TO {art_unit_range[1]}]",
        "fl": "*",
        "mm": "100%",
        "sort": "appFilingDate desc",
        "start": 0,
        "rows": rows,
    }
    print(f"  Fallback query for {tc_name}...")
    try:
        resp = requests.post(PEDS_API, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        docs = data.get("queryResults", {}).get("searchResponse", {}).get("response", {}).get("docs", [])
        print(f"  -> Got {len(docs)} results")
        return docs
    except Exception as e:
        print(f"  -> Fallback error: {e}")
        return []


def extract_app_data(doc, tc_name, tc_desc):
    """Extract relevant fields from a PEDS document."""
    # Extract prosecution history events
    transactions = doc.get("transactions", [])
    oa_events = []
    for txn in transactions:
        code = txn.get("transactionCode", "")
        desc = txn.get("transactionDescription", "")
        date = txn.get("recordDate", "")
        # Office Action codes: CTNF=Non-Final, CTFR=Final, NOA=Notice of Allowance
        if code in ("CTNF", "CTFR", "CTFP", "CTEQ", "FOJR", "NOA", "CTRS",
                     "ELC", "REM", "AMND", "N/AP", "ABN8", "ABN9"):
            oa_events.append({
                "code": code,
                "description": desc,
                "date": date,
            })

    return {
        "application_number": doc.get("applId", ""),
        "patent_title": doc.get("patentTitle", ""),
        "technology_center": tc_name,
        "tc_description": tc_desc,
        "art_unit": doc.get("appGrpArtNumber", ""),
        "examiner_name": f"{doc.get('appExamPrefrdName', '')} {doc.get('appExamPrefrdLastName', '')}".strip(),
        "filing_date": doc.get("appFilingDate", ""),
        "status": doc.get("appStatus", ""),
        "patent_number": doc.get("patentNumber", ""),
        "app_type": doc.get("appType", ""),
        "entity_status": doc.get("appEntityStatus", ""),
        "num_prosecution_events": len(oa_events),
        "prosecution_events": oa_events,
        "has_office_action": any(e["code"] in ("CTNF", "CTFR", "CTFP", "CTEQ", "FOJR") for e in oa_events),
        "has_allowance": any(e["code"] == "NOA" for e in oa_events),
        "pulled_at": datetime.utcnow().isoformat(),
    }


def main():
    print("=" * 60)
    print("PatentBench - USPTO PEDS Data Pull")
    print(f"Target: {len(TC_QUERIES)} Technology Centers, 20 apps each")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_records = []
    tc_ranges = {
        "TC1600_Biotech": (1600, 1699),
        "TC2100_Software": (2100, 2199),
        "TC2800_Electrical": (2800, 2899),
        "TC3600_Business": (3600, 3699),
        "TC3700_Mechanical": (3700, 3799),
    }

    for tc_name, config in TC_QUERIES.items():
        print(f"\n--- {tc_name}: {config['description']} ---")
        docs = query_peds(tc_name, config)

        # Fallback if primary query fails
        if not docs and tc_name in tc_ranges:
            docs = query_peds_v2_fallback(tc_name, tc_ranges[tc_name])

        for doc in docs:
            record = extract_app_data(doc, tc_name, config["description"])
            all_records.append(record)

        # Rate limiting
        time.sleep(1)

    # Write JSONL
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    print(f"\n{'=' * 60}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total records: {len(all_records)}")
    print(f"With Office Actions: {sum(1 for r in all_records if r['has_office_action'])}")
    print(f"With Allowance: {sum(1 for r in all_records if r['has_allowance'])}")
    print(f"Output: {OUTPUT_FILE}")

    # Print per-TC breakdown
    from collections import Counter
    tc_counts = Counter(r["technology_center"] for r in all_records)
    for tc, count in tc_counts.items():
        oa_count = sum(1 for r in all_records if r["technology_center"] == tc and r["has_office_action"])
        print(f"  {tc}: {count} apps, {oa_count} with OAs")


if __name__ == "__main__":
    main()
