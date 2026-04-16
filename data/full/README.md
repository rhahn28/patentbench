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
  - n<1K
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

PatentBench evaluates AI systems on real patent prosecution tasks — from parsing USPTO Office Actions to drafting legally sound arguments under 35 U.S.C. sections 101, 102, 103, and 112.

Every test case derives from actual USPTO proceedings. Tasks map to billable activities at patent law firms.

## Dataset Structure

### Splits

| Split | Cases | Purpose |
|-------|-------|---------|
| `full` | 929 | Complete evaluation across all tiers and domains |
| `mini` | 300 | Stratified sample for rapid iteration |

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique case identifier |
| `domain` | string | `administration`, `prosecution`, or `drafting` |
| `tier` | int | Difficulty 1-5 (paralegal to senior partner) |
| `task_type` | string | e.g. `deadline_calculation`, `103_argument`, `oa_parsing` |
| `prompt` | string | The task prompt given to the model |
| `reference_answer` | string | Ground truth (JSON string for structured answers) |
| `evaluation_layers` | list[str] | Which evaluation layers apply (`deterministic`, `llm_judge`) |
| `metadata` | dict | Application number, technology center, etc. |

### Task Types

| Task Type | Domain | Tier | Count |
|-----------|--------|------|-------|
| `deadline_calculation` | administration | 1 | 470 |
| `examiner_extraction` | prosecution | 1 | 98 |
| `action_classification` | administration | 1 | 82 |
| `timeline_analysis` | administration | 1 | 81 |
| `prosecution_history_parsing` | prosecution | 1 | 81 |
| `prosecution_strategy` | prosecution | 1 | 81 |
| `103_argument` | prosecution | 3 | 12 |
| `fee_computation` | administration | 1 | 10 |
| `101_argument` | prosecution | 3 | 4 |
| `102_argument` | prosecution | 3 | 5 |
| `112_argument` | prosecution | 3 | 3 |
| `oa_parsing` | prosecution | 2 | 2 |

## Usage

### With the `datasets` library

```python
from datasets import load_dataset

ds = load_dataset("rhahn/patentbench")
full = ds["full"]
mini = ds["mini"]

# Filter by task type
deadlines = full.filter(lambda x: x["task_type"] == "deadline_calculation")
```

### With the `patentbench` Python package

```bash
pip install patentbench
patentbench run --model openai:gpt-4o --subset mini
```

```python
from patentbench import DataLoader, BenchmarkRunner

loader = DataLoader("data/mini")
cases = loader.load_all()
```

## Evaluation

PatentBench uses a 4-layer evaluation framework:

1. **Deterministic** — Binary correctness for objective tasks (deadlines, fees)
2. **LLM-as-Judge** — Calibrated rubric-based scoring (legal accuracy, argument strength)
3. **Comparative** — Blind side-by-side ranking
4. **Human Calibration** — Expert attorney scores

## Links

- **GitHub:** https://github.com/rhahn28/patentbench
- **PyPI:** https://pypi.org/project/patentbench/
- **Leaderboard:** https://abigail.app/patentbench

## License

Apache 2.0
