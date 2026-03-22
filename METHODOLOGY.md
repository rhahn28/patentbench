# PatentBench Methodology

This document describes the evaluation methodology, scoring framework, contamination prevention measures, and economic validity analysis underlying PatentBench.

## 1. Evaluation Framework

PatentBench uses a 4-layer evaluation framework. Each layer captures different aspects of system quality, from objective correctness to subjective expert judgment. Systems are evaluated as black boxes — the underlying model architecture is irrelevant; only outputs are measured.

### Layer 1: Deterministic Evaluation

**Purpose**: Measure binary correctness on tasks with objectively verifiable answers.

**Status**: Live. 298 test cases across 82 real USPTO Office Actions from 8 Technology Centers.

**Tasks covered**:
- **Deadline calculation** (125 tests): Response deadlines from OA mailing dates. Shortened statutory period (3 months) and maximum deadline (6 months) under 37 CFR 1.134 and 35 USC 133. Includes end-of-month clamping edge cases.
- **Action classification** (82 tests): Parsing prosecution event codes (CTNF, CTFR, NOA, etc.) to identify Non-Final, Final, and Allowance actions plus total OA round count.
- **Fee computation** (10 tests): USPTO fee lookups based on entity status (micro/small/large), including extension fees, RCE fees, and issue fees at current 2025 rates.
- **Timeline analysis** (81 tests): Reconstructing prosecution timelines from event records — total events, first/last dates, prosecution duration in days.

**Scoring**: Binary (correct/incorrect) per field. Each test case has multiple scored fields (e.g., deadline tests score shortened_deadline, max_deadline, action_type, and options separately). Final score = correct fields / total fields.

**Ground truth generation**: Ground truth is computed deterministically from USPTO Open Data Portal API data. No human annotation required — these are mathematical/lookup tasks with single correct answers. The ground truth generator and scorer are open-source in `scripts/`.

**Weight in composite score**: 30%

### Layer 2: LLM-as-Judge Evaluation

**Purpose**: Score subjective quality dimensions on Tier 3 prosecution reasoning tasks using calibrated rubrics and an automated judge.

**Status**: In progress. 25 Tier 3 test cases completed. Rubrics published in `data/rubrics/`.

**Tasks covered**:
- §103 Obviousness traversal arguments (8 tests across TC1600, TC2100, TC2800, TC3700)
- §102 Anticipation arguments (5 tests)
- §112 Indefiniteness arguments (4 tests)
- §101 Alice/Mayo eligibility arguments (4 tests)
- Claim amendment drafting (4 tests)

Each test provides: a rejection scenario, the specific claim at issue, cited prior art with pinpoint references, and asks the system to generate a full prosecution argument.

**Dimensions scored** (published rubrics in `data/rubrics/`):

1. **Statutory Correctness** (weight: 1.5x): Are 35 U.S.C. section references correct? Does the response apply the right legal standard? Scored 1-5.
2. **MPEP Accuracy** (weight: 1.0x): Are MPEP sections real, relevant, and correctly applied? Scored 1-5.
3. **Case Law Accuracy** (weight: 1.5x): Are case citations real, correctly cited, and properly applied? Fabricated case law = automatic 1. Scored 1-5.
4. **Factual Grounding** (weight: 1.5x): Does the argument cite specific claim language and prior art disclosures, or make generic assertions? Scored 1-5.
5. **Argument Strength** (weight: 1.0x): Quality of legal reasoning. Does the argument identify the strongest distinguishing limitations? Scored 1-5.

**Judge configuration**: Automated LLM judge at temperature 0.0. The judge model is a calibrated frontier model (specific model identity is not disclosed to prevent gaming). Judge prompts and rubrics are fully published.

**Anti-hallucination integration**: Citation verification scores are factored into legal accuracy:
- Fabricated MPEP sections: automatic 1 on MPEP accuracy dimension
- Fabricated case law: automatic 1 on case law accuracy dimension
- Poison pill citation adoption: 2x penalty (see Section 4)

**Calibration**: Judge scores are validated against human attorney scores on a calibration set (Layer 4). Systematic biases are corrected via linear calibration.

**Weight in composite score**: 35%

### Layer 3: Comparative Evaluation

**Purpose**: Direct head-to-head comparison of system outputs to establish relative ranking when absolute scores are close.

**Status**: Planned. Will begin once 3+ systems have Layer 2 scores.

**Protocol**:
1. Two system outputs for the same test case are presented to the judge with randomized order (position deblinding)
2. The judge selects the better output or declares a tie
3. Confidence level is recorded (high/medium/low)
4. Win rates are computed per system pair across all test cases
5. Results are aggregated across both orderings to cancel position bias

**Position bias mitigation**: Each comparison is run twice with swapped order. Only consistent judgments (same winner in both orderings, or tie) are counted at full weight. Inconsistent judgments are counted at 0.5x weight.

**Minimum sample size**: Each system pair requires at least 25 comparison cases for statistical validity. Ties are excluded from win rate calculation but reported separately.

**Weight in composite score**: 25%

### Layer 4: Human Calibration

**Purpose**: Anchor automated metrics against expert patent attorney judgment. This layer validates Layers 2 and 3 rather than producing a separate score.

**Status**: Recruiting evaluators. Target: 5 licensed patent attorneys with 5+ years prosecution experience.

**Protocol**:
1. A stratified random subset of Tier 3 test cases (minimum 50, covering all rejection types and Technology Centers) is scored by at least 2 licensed patent attorneys
2. Attorneys score the same dimensions as the automated judge (1-5 scale per dimension) using identical rubrics
3. Attorneys also provide free-text feedback on argument quality, missed issues, and strategic concerns
4. Inter-rater reliability is computed:
   - Cohen's Kappa between each attorney pair
   - Cohen's Kappa between each attorney and the automated judge
   - Krippendorff's Alpha across all raters
5. Results calibrate the automated judge — if judge systematically over/under-scores a dimension, a linear correction is applied

**Inter-rater reliability target**: Cohen's Kappa >= 0.60 (substantial agreement). If below 0.60, rubrics are refined and re-calibrated.

**Evaluator qualifications**:
- Active USPTO registration (patent attorney or patent agent)
- Minimum 5 years patent prosecution experience
- Experience in at least 2 of the 8 Technology Centers covered
- No financial interest in any evaluated system

**Weight in composite score**: 10% (calibration weight applied to adjust Layers 2-3)

## 2. Difficulty Tiers

PatentBench test cases are stratified into 5 difficulty tiers based on the experience level required to perform the task competently in professional practice.

| Tier | Level | Experience | Task Characteristics | Current Status |
|------|-------|------------|----------------------|----------------|
| 1 | Paralegal | 0-1 years | Lookup-based, deterministic answers, no legal judgment required | **298 tests live** |
| 2 | Junior Associate | 1-3 years | Pattern recognition, structured extraction | **Included in Layer 1** |
| 3 | Senior Associate | 3-6 years | Complex legal reasoning, multiple arguments, strategic choices | **25 tests live** |
| 4 | Junior Partner | 6-10 years | Multi-rejection OAs, prosecution strategy, continuation decisions | Planned |
| 5 | Senior Partner | 10+ years | Portfolio strategy, IPR/PTAB defense, prosecution history estoppel | Planned |

**Tier assignment criteria**:
- Based on billing rate surveys (AIPLA Economic Survey)
- Validated by 3 independent patent practitioners
- Each test case's tier is the minimum experience level at which a competent practitioner would produce a high-quality response

## 3. Composite Scoring

The composite benchmark score (0-100) is computed as:

```
composite = sum(layer_weight[l] * layer_score[l] for l in layers) * 100
```

Where:
- `layer_weight` = {deterministic: 0.30, llm_judge: 0.35, comparative: 0.25, human_calibration: 0.10}
- `layer_score` = mean score across test cases for that layer (0.0 to 1.0)

**Current reporting**: Until all 4 layers are operational, scores are reported per-layer rather than as a composite. This prevents misleading composite scores that only reflect Layer 1 deterministic tasks.

Domain-specific scores use the same formula but aggregated per domain:
- Administration (10%), Drafting (25%), Prosecution (35%), Analytics (15%), Prior Art (15%)

## 4. Anti-Hallucination Framework

Patent prosecution demands zero tolerance for fabricated legal authority. PatentBench includes dedicated anti-hallucination measures.

### Poison Pill Citations

Each Tier 3 test case embeds fabricated MPEP sections and case law citations in the context. If a system references these fabricated citations, it receives a 2x scoring penalty.

**Examples of poison pills**:
- MPEP 2199 (does not exist — MPEP 2100 series ends at 2190)
- "Smith v. USPTO, 999 F.3d 1 (Fed. Cir. 2025)" (fabricated case)
- MPEP 714.19(c) (fabricated subsection)

### Citation Verification

All MPEP section references are validated against the complete MPEP section registry (current as of R-10.2019). Case law citations are checked against a database of Federal Circuit and Supreme Court patent decisions.

**Verification categories**:
- **Valid**: Citation exists and is correctly applied
- **Valid but misapplied**: Citation exists but is used for the wrong legal principle
- **Fabricated**: Citation does not exist in any form
- **Poison pill adopted**: System repeated a planted fabricated citation

### Scoring Impact

```
anti_hallucination_score = max(0, 1 - (fabricated + 2 * poison_hits) / total_citations)
```

This score is incorporated into the Layer 2 judge evaluation as a multiplier on the legal accuracy dimension.

## 5. Contamination Prevention

### Data Isolation

- Test cases in the held-out set are never published in training data
- PatentBench-Mini is the only publicly released subset
- The full benchmark (target: 7,200 cases) will be available through a controlled evaluation API

### Canary Strings

Select test cases contain unique canary strings — distinctive phrases that would be detectable if present in model training data. These serve as contamination detectors for future evaluations.

### Temporal Controls

- Test cases use Office Actions with mailing dates spanning 2019-2024
- Application numbers are verified against USPTO PEDS to confirm they are real public applications
- Post-training-cutoff cases are included to test genuine reasoning vs. memorization

### Version Rotation

- 20% of test cases are rotated each quarter to prevent benchmark overfitting
- Rotated cases are replaced with new expert-curated cases of equivalent difficulty
- Historical results on rotated cases are preserved for trend analysis

## 6. Economic Validity

PatentBench tasks map to real billable activities in patent prosecution practice.

### Task-to-Billing Mapping

| Task Type | Billable Activity | Typical Rate Range |
|-----------|-------------------|-------------------|
| Deadline calculation | Docketing | $50-100/task |
| OA parsing | Office Action review | $200-500/OA |
| 103 argument | OA response drafting | $2,000-8,000/response |
| Claim amendment | Amendment preparation | $1,000-3,000/set |
| Multi-rejection response | Complex OA response | $5,000-15,000/response |

### Economic Impact Calculation

For each system, we estimate the economic value of correct performance:

```
economic_value = sum(task_billing_rate * accuracy_on_task for task in tasks)
```

This provides a dollar-denominated benchmark that is directly meaningful to law firm decision-makers.

## 7. Statistical Methodology

### Confidence Intervals

All reported scores include 95% confidence intervals computed via bootstrap resampling (1,000 iterations).

### Significance Testing

Pairwise system comparisons use the Wilcoxon signed-rank test with Bonferroni correction for multiple comparisons. A difference is reported as significant at p < 0.05 (corrected).

### Effect Sizes

Cohen's d is reported for all pairwise comparisons to indicate practical significance beyond statistical significance.

## 8. How to Submit a System for Evaluation

1. **Layer 1 (self-service)**: Clone this repo, run `node scripts/run_multi_model_benchmark.js --model=your_model` against the published test cases, submit results as a PR.
2. **Layer 2-4 (coordinated)**: Email rhahn@abigail.app with your system name and API access. We run the evaluation and publish results.
3. **Self-evaluation**: All rubrics, test cases, and scoring code are open-source. Run your own evaluation and submit results with raw outputs for verification.

Systems are identified by product name only. Underlying model architectures are treated as trade secrets and are never disclosed in benchmark results.

---

Copyright 2026 Salt Holdings LLC. Licensed under Apache 2.0.
