---
title: "Introducing PatentBench: The First Reproducible Benchmark for Patent Prosecution AI"
date: 2026-03-19
author: Roger Hahn
category: guides
meta_description: "PatentBench is the first open, reproducible benchmark for patent prosecution AI. 300 real USPTO Office Actions, 5 difficulty tiers, 4-layer evaluation, and anti-hallucination testing."
tags:
 - patent AI
 - AI benchmark
 - patent prosecution
 - legal AI
 - hallucination
 - open source
 - PatentBench
 - SWE-bench
 - evaluation
---

# Introducing PatentBench: The First Reproducible Benchmark for Patent Prosecution AI

Every serious AI domain has a benchmark that keeps it honest. Computer vision has ImageNet. Code generation has SWE-bench. Question answering has SQuAD. Legal contract analysis has CUAD.

Patent prosecution, a \$7 billion market being rapidly reshaped by AI, has had nothing.

Today we are announcing PatentBench: the first open, reproducible benchmark for evaluating AI systems on patent prosecution tasks. PatentBench measures what matters to practicing attorneys: Can the AI correctly parse an Office Action? Can it construct a legally sound 103 argument? Can it draft a claim amendment that actually overcomes the rejection? And critically, does it hallucinate?

This post explains what PatentBench measures, how it works, and how you can use it.

## Why Patent Prosecution Needs Its Own Benchmark

Patent prosecution is fundamentally different from other legal tasks that have received benchmarking attention. Contract review, the focus of CUAD and legalbenchmarks.ai, involves extracting and classifying information from a single document type. Patent prosecution involves a multi-turn adversarial dialogue between an applicant and an examiner, grounded in highly technical subject matter, governed by a complex regulatory framework, and requiring simultaneous fluency in law, engineering, and strategy.

A system that excels at identifying indemnification clauses in contracts tells you nothing about whether it can distinguish a patent claim over a combination of three prior art references under 35 U.S.C. 103.

Existing benchmarks also fail to capture a critical dimension of patent prosecution quality: hallucination. When a legal research AI hallucinates a case citation, the attorney can verify it with a simple search. When a patent prosecution AI fabricates a teaching in a prior art reference, claiming that "Smith et al. disclose a thermally conductive adhesive layer" when the reference says nothing of the sort, the error is far harder to catch. The attorney must re-read the cited reference, compare the AI's characterization against the actual text, and assess whether the fabricated teaching materially affects the argument.

Stanford's research found 17-33% hallucination rates in production legal AI tools. Patent prosecution AI has never been measured. PatentBench changes that.

## What PatentBench Measures

PatentBench evaluates patent prosecution AI across four core capability dimensions:

### 1. Office Action Parsing

Before an AI system can respond to an Office Action, it must correctly understand what the Office Action says. This sounds trivial. It is not.

A typical Office Action contains:
- Multiple rejection grounds (102, 103, 112) across different claim sets
- Specific prior art citations with paragraph-level references
- Examiner reasoning explaining why the claims are obvious or anticipated
- Formal requirements (restriction requirements, objections, election requirements)
- Deadlines and procedural posture

PatentBench tests whether a system can extract this structured information accurately. Specific metrics include:

| Metric | What It Measures |
|--------|-----------------|
| Rejection type identification | Does the system correctly identify 102 vs. 103 vs. 112 rejections? |
| Claim mapping accuracy | Does it correctly identify which claims are rejected under which grounds? |
| Prior art extraction | Does it correctly identify all cited references and their relevant passages? |
| Examiner reasoning capture | Does it accurately characterize the examiner's rationale? |
| Deadline/procedural parsing | Does it correctly extract response deadlines and procedural requirements? |

### 2. Section 103 Argument Quality

The 103 obviousness rejection is the most common substantive rejection in patent prosecution and the most difficult to overcome. Responding effectively requires the attorney to:

- Accurately characterize what each prior art reference actually teaches
- Identify specific limitations in the claims that are missing from the prior art
- Construct a persuasive narrative for why a person of ordinary skill would not have combined the references
- Address the examiner's specific motivation-to-combine reasoning

PatentBench evaluates 103 arguments along multiple axes:

| Axis | Evaluation Criteria |
|------|-------------------|
| Factual accuracy | Are all prior art characterizations verifiable against the actual references? |
| Completeness | Does the argument address every rejection ground and every cited reference? |
| Distinction quality | Are the identified distinctions between the claims and prior art meaningful and specific? |
| Persuasiveness | Does the argument construct a coherent narrative, not just a list of differences? |
| Legal soundness | Does the argument apply the correct legal framework (Graham factors, TSM test, KSR rationale)? |

### 3. Amendment Quality

When arguments alone cannot overcome a rejection, attorneys amend the claims. Effective claim amendments require balancing prosecution success (overcoming the rejection) against patent scope (maintaining commercially valuable coverage). PatentBench evaluates:

- Whether the amendment incorporates limitations that actually address the rejection
- Whether the amendment is supported by the specification (35 U.S.C. 112 compliance)
- Whether the amendment unnecessarily narrows claim scope
- Whether the amendment introduces new issues (e.g., new matter, indefiniteness)

### 4. Citation Accuracy (Anti-Hallucination)

This is the dimension that no patent AI vendor wants to discuss. PatentBench includes dedicated anti-hallucination testing that measures:

- **Fabricated reference detection:** Does the system cite prior art references that do not exist in the prosecution history?
- **Mischaracterized teachings:** Does the system attribute teachings to references that the references do not actually contain?
- **Invented passages:** Does the system quote specific paragraphs, columns, or figures that do not exist in the cited reference?
- **Phantom legal authority:** Does the system cite case law, MPEP sections, or rules that do not exist or do not support the proposition claimed?

Each test case in PatentBench includes the complete prior art references, allowing automated verification of every citation the AI system generates.

## Five Difficulty Tiers

Not all patent prosecution tasks are equally challenging. A system that correctly parses a simple single-reference 102 rejection but fails on a complex multi-reference 103 combination is not "accurate", it is accurate on easy cases.

PatentBench stratifies test cases across five difficulty tiers:

### Tier 1: Administrative (Paralegal-level)
- Office Action parsing and extraction
- Deadline calculation
- Formality compliance checking
- Response shell generation

### Tier 2: Foundational (Junior Associate-level)
- Single-reference 102 rejections
- Simple 112 rejections (written description, enablement)
- Straightforward claim amendments
- IDS preparation

### Tier 3: Standard (Mid-level Associate)
- Two-reference 103 rejections
- 103 rejections with secondary considerations
- Dependent claim fallback strategies
- Interview summaries and follow-up

### Tier 4: Complex (Senior Associate-level)
- Three or more reference 103 combinations
- Mixed 102/103/112 rejections in a single Office Action
- Design-around amendments that preserve scope
- Restriction requirement responses with strategic election

### Tier 5: Strategic (Partner-level)
- Prosecution strategy across a patent family
- Continuation/divisional planning
- Terminal disclaimer decisions
- Appeal brief preparation
- Portfolio-level claim differentiation

PatentBench-Mini (our initial release) focuses on Tiers 1-3, with Tiers 4-5 following in subsequent releases.

## Four-Layer Evaluation Architecture

Evaluating patent prosecution quality is inherently more complex than evaluating, say, code generation (where you can run the code and check if tests pass). PatentBench uses a four-layer evaluation architecture that combines automated metrics with expert human judgment:

### Layer 1: Structural Validation (Automated)
Checks whether the output is well-formed and complete:
- Does the response address all rejection grounds?
- Are all claims accounted for?
- Is the response formatted correctly for USPTO filing?
- Are all required sections present?

This layer runs automatically with no human intervention and provides immediate pass/fail signals.

### Layer 2: Factual Verification (Automated + Reference Lookup)
Verifies every factual claim against source documents:
- Prior art characterizations are checked against actual reference text
- Legal citations are verified against MPEP and case law databases
- Claim language is checked against the specification for support
- Paragraph/column/figure references are verified for existence

This layer catches hallucinations. It is the most technically complex layer and the one most conspicuously absent from vendor self-evaluations.

### Layer 3: Quality Assessment (Expert Human Evaluation)
Practicing patent attorneys evaluate:
- Argument persuasiveness (would this argument move an examiner?)
- Strategic soundness (is this the right approach for this prosecution posture?)
- Claim amendment quality (does this balance scope preservation and overcoming the rejection?)
- Overall prosecution competence (would you send this to a client?)

Evaluators use calibrated rubrics with detailed scoring criteria and anchor examples. Inter-rater reliability is measured and reported.

### Layer 4: Comparative Ranking (Holistic)
For each test case, evaluators rank outputs from multiple systems without knowing which system produced which output. This blind comparative evaluation provides the most ecologically valid measure of relative system quality.

## Anti-Hallucination Testing: How It Works

Hallucination testing in PatentBench goes beyond simply checking whether citations exist. Our methodology is designed to catch the subtle, dangerous hallucinations that fluent AI outputs can hide.

**Passage-level verification.** For every prior art characterization in a generated response, we verify that the cited passage actually contains the teaching attributed to it. A system that says "Smith discloses a wireless transceiver (col. 4, lines 20-35)" must be checked not just for whether Smith exists and has a column 4, but whether lines 20-35 of column 4 actually discuss a wireless transceiver.

**Adversarial test cases.** PatentBench includes test cases specifically designed to induce hallucination:
- Office Actions citing references with very similar but legally distinct teachings
- Rejections where the examiner's characterization of the prior art is itself arguably incorrect
- Cases where the most "obvious" argument requires fabricating a distinction that does not exist
- References with confusingly similar nomenclature across different embodiments

**Hallucination taxonomy.** Not all hallucinations are equally harmful. PatentBench categorizes them:

| Category | Severity | Example |
|----------|----------|---------|
| Phantom citation | Critical | Citing a reference not in the prosecution history |
| Fabricated teaching | Critical | Attributing content to a reference that it does not contain |
| Distorted teaching | High | Materially mischaracterizing what a reference teaches |
| Unsupported inference | Moderate | Drawing conclusions from a reference that the text does not support |
| Imprecise characterization | Low | Loosely paraphrasing a teaching in a way that is technically inaccurate |

Systems are scored separately on each hallucination category, providing granular insight into where and how they fail.

## PatentBench-Mini: What Ships First

The initial release. PatentBench-Mini, includes:

- **300 test cases** drawn from real USPTO Office Actions
- **Tiers 1-3** difficulty coverage
- **8 technology domains:** software, electrical, mechanical, chemical, biotech, medical devices, telecommunications, materials science
- **Complete prior art references** for factual verification
- **Expert-annotated gold standard responses** for Tiers 1-2
- **Evaluation rubrics** with calibrated scoring criteria
- **Automated evaluation scripts** for Layers 1 and 2
- **Baseline results** for GPT-4, Claude, Gemini, and ABIGAIL

## How to Run PatentBench

PatentBench is designed to be easy to use. Running the benchmark requires three steps:

### Installation

```bash
pip install patentbench
```

### Quick Start

```python
from patentbench import PatentBench, evaluate

# Load the benchmark
bench = PatentBench.load("mini")  # or "full" when available

# Run your system against the benchmark
results = []
for case in bench.cases:
    response = your_system.respond(case.office_action)
    result = evaluate(case, response)
    results.append(result)

# Generate report
report = bench.report(results)
report.save("patentbench_results.json")
report.summary()
```

### Output

```
PatentBench-Mini Results
========================
Overall Score: 72.3 / 100

Tier 1 (Administrative):  91.2 / 100
Tier 2 (Foundational):    78.5 / 100
Tier 3 (Standard):        54.1 / 100

Hallucination Rate:        8.3%
  - Phantom citations:     1.2%
  - Fabricated teachings:   3.7%
  - Distorted teachings:    2.1%
  - Unsupported inference:  1.3%

Citation Accuracy:         91.7%
Completeness:             85.4%
Structural Validity:      97.8%
```

## Open Source and Open Data

PatentBench is fully open source under the Apache 2.0 license.

- **Code repository:** [github.com/abigail-ai/patentbench](https://github.com/abigail-ai/patentbench)
- **Dataset:** HuggingFace Hub (link available at launch)
- **Evaluation toolkit:** Included in the pip package
- **Baseline results:** Published with the initial release
- **Methodology paper:** Available on arXiv (link available at launch)

We chose open source deliberately. A benchmark that only one company can run is not a benchmark, it is a marketing tool. PatentBench must be independently verifiable to have value.

## How to Contribute

PatentBench is a community effort. We are actively seeking contributions in several areas:

**Test case contributions.** If you are a patent attorney with Office Action examples that would make good test cases (particularly in underrepresented technology domains), we want to hear from you. All contributed cases are anonymized and reviewed for quality before inclusion.

**Evaluator participation.** We need practicing patent attorneys to serve as expert evaluators for Layer 3 and Layer 4 assessment. Evaluators are compensated for their time and credited in publications.

**Technology domain expansion.** PatentBench-Mini covers eight technology domains. We aim to expand to fifteen domains in the full release, including pharma, semiconductors, AI/ML, fintech, clean energy, aerospace, and agricultural technology.

**Benchmark extension.** Researchers interested in adding new evaluation dimensions, for example, international prosecution (EPO, CNIPA, JPO) or post-grant proceedings (IPR, PGR), are welcome to propose extensions.

To contribute, open an issue on [GitHub](https://github.com/abigail-ai/patentbench) or email patentbench@abigail.app.

## Design Principles

PatentBench is built on design principles drawn from the benchmarks that have most successfully advanced their respective fields:

**SWE-bench's realism.** SWE-bench transformed code generation evaluation by using real GitHub issues from real repositories, not synthetic problems. PatentBench uses real USPTO Office Actions, not hypothetical scenarios. The messy complexity of real prosecution, ambiguous examiner reasoning, missing references, unusual procedural postures, is a feature, not a bug.

**MMLU's stratification.** MMLU demonstrated the value of difficulty-stratified evaluation for identifying capability boundaries. PatentBench's five tiers serve the same purpose: we care less about average performance than about where performance degrades.

**HELM's holistic evaluation.** Stanford's HELM framework showed that single-metric evaluation obscures important capability differences. PatentBench's four-layer architecture and multi-dimensional scoring prevent systems from gaming a single metric.

**ImageNet's openness.** ImageNet's greatest contribution was not the dataset itself but the fact that anyone could evaluate against it. PatentBench's open-source release ensures that results are independently verifiable and that the benchmark evolves with community input.

## What PatentBench Does Not Measure

Intellectual honesty requires acknowledging what PatentBench does not cover:

- **Client communication quality.** How well a system explains its recommendations to a non-technical client is important but out of scope.
- **Prior art search.** PatentBench evaluates responses to Office Actions where prior art is already identified. Evaluating the quality of prior art search is a separate (and important) problem.
- **Patent drafting.** Writing patent applications from invention disclosures is a distinct skill from prosecution. A drafting benchmark is on our roadmap but not included in the initial release.
- **Prosecution economics.** Whether AI-assisted prosecution is cost-effective depends on pricing, workflow integration, and attorney review time, factors that a benchmark cannot capture.

## The Road Ahead

PatentBench-Mini ships in Q2 2026 with 300 test cases, automated evaluation, and baseline results. The full benchmark roadmap includes:

- **Q3 2026:** PatentBench-Full with 1,000+ test cases and Tier 4-5 coverage
- **Q4 2026:** International prosecution extension (EPO, CNIPA, JPO)
- **2027 H1:** Patent drafting benchmark (PatentBench-Draft)
- **2027 H2:** Post-grant proceedings benchmark (PatentBench-PGR)

We will publish updated leaderboard results quarterly, tracking the field's progress over time.

## A Standard the Industry Deserves

Patent attorneys make high-stakes decisions based on AI-generated analysis. They deserve to know how well these tools actually work, not how well the marketing department says they work.

PatentBench is our contribution toward making that possible. It is not perfect, and it will improve with community input. But it exists, it is open, and it measures what matters.

The benchmark is live. The question for every patent AI vendor is simple: will you run it?

---

*PatentBench is an open-source project from [ABIGAIL](https://abigail.app). Get started at [abigail.app/patentbench](https://abigail.app/patentbench), explore the code on [GitHub](https://github.com/abigail-ai/patentbench), or read the methodology paper on arXiv.*
