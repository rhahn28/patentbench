---
license: apache-2.0
task_categories:
  - text-generation
  - question-answering
language:
  - en
tags:
  - legal
  - patent
  - benchmark
  - prosecution
  - evaluation
size_categories:
  - 1K<n<10K
configs:
  - config_name: full
    data_files:
      - split: train
        path: data/full/all_cases.jsonl
  - config_name: mini
    data_files:
      - split: train
        path: data/mini/tier_1_2_cases.jsonl
---

# PatentBench

**The First Reproducible Benchmark for Patent Prosecution AI**

## Overview

PatentBench evaluates AI systems on real patent prosecution tasks, from parsing USPTO Office Actions to drafting legally sound arguments under 35 U.S.C. sections 101, 102, 103, and 112.

Every test case derives from actual USPTO proceedings. Tasks map to billable activities at patent law firms.

## Dataset Structure

### Splits

| Split | Cases | Purpose |
|-------|-------|---------|
| `full` | 7,200 | Complete evaluation across all tiers and domains |
| `mini` | 300 | Stratified sample for rapid iteration |

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique case identifier |
| `domain` | string | `administration`, `prosecution`, `drafting`, or `analytics` |
| `tier` | int | Difficulty 1-5 (paralegal to senior partner) |
| `task_type` | string | e.g. `deadline_calculation`, `103_argument`, `fee_computation` |
| `prompt` | string | The task prompt given to the model |
| `reference_answer` | string | Ground truth (JSON string for structured answers) |
| `evaluation_layers` | list[str] | Which evaluation layers apply |
| `metadata` | dict | Application number, technology center, etc. |

### Task Types (7,200 total)

| Task Type | Domain | Count |
|-----------|--------|-------|
| `fee_computation` | administration | 2,050 |
| `deadline_calculation` | administration | 2,049 |
| `action_classification` | administration | 954 |
| `examiner_extraction` | prosecution | 418 |
| `prosecution_history_parsing` | prosecution | 368 |
| `timeline_analysis` | administration | 347 |
| `prosecution_strategy` | prosecution | 346 |
| `technology_center_classification` | prosecution | 321 |
| `filing_date_extraction` | administration | 321 |
| `103_argument` | prosecution | 12 |
| `102_argument` | prosecution | 5 |
| `101_argument` | prosecution | 4 |
| `112_argument` | prosecution | 3 |
| `oa_parsing` | prosecution | 2 |

### Difficulty Distribution

| Tier | Level | Count |
|------|-------|-------|
| 1 | Paralegal | 6,015 |
| 2 | Junior Associate | 1,080 |
| 3 | Senior Associate | 105 |

## Data Sources

All cases are derived from real USPTO data:
- **321 USPTO applications** from Patent Examination Data System (PEDS)
- **1,103 prosecution events** (Office Actions, allowances, etc.)
- **437 Office Actions** (311 Non-Final, 126 Final) across these applications

Test cases include generated variants covering all combinations of:
- Entity status (micro, small, large)
- Extension duration (1, 2, 3 months)
- Fee type (filing, search, examination)

## Usage

### With the `datasets` library

```python
from datasets import load_dataset

ds_full = load_dataset("rhahn/patentbench", "full", split="train")
ds_mini = load_dataset("rhahn/patentbench", "mini", split="train")

# Filter by task type
deadlines = ds_full.filter(lambda x: x["task_type"] == "deadline_calculation")
```

### With the `patentbench` Python package

```bash
pip install patentbench
patentbench --model openai:gpt-4o --subset mini
```

```python
from patentbench import DataLoader, BenchmarkRunner

loader = DataLoader("data/mini")
cases = loader.load_all()
```

## Evaluation

PatentBench uses a 4-layer evaluation framework:

1. **Deterministic**. Binary correctness for objective tasks (deadlines, fees)
2. **LLM-as-Judge**. Calibrated rubric-based scoring (legal accuracy, argument strength)
3. **Comparative**. Blind side-by-side ranking
4. **Human Calibration**. Expert attorney scores

## Links

- **GitHub:** https://github.com/rhahn28/patentbench
- **PyPI:** https://pypi.org/project/patentbench/
- **Leaderboard:** https://abigail.app/patentbench

## License

Apache 2.0
