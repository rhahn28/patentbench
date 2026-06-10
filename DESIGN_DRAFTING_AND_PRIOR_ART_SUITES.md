# Design: Drafting and Prior Art Benchmark Suites

> **Status: DESIGN ONLY. No benchmark code ships with this document.**
> Decision of record (operator, 2026-06-10): the Prior Art suite is built as
> **reference analysis over a supplied candidate pool**, not open-corpus
> search. This keeps the public positioning ("Not a prior art search
> benchmark, a prosecution response benchmark," baked into the page metadata)
> intact while implementing the Prior Art domain the taxonomy already
> declares.
>
> Reviewed in two rounds before commit: a fresh-context evaluator pass over
> the whole plan, and a four-reviewer council on the two hardest design
> questions (prior art ground truth and reproducibility; drafting scoring
> where no single correct answer exists). Section 10 records what the review
> changed.

---

## 0. Scope and the positioning decision

PatentBench's `Domain` enum (`patentbench/config.py`) has declared
`DRAFTING` and `PRIOR_ART` since v0.1, and `TASK_REGISTRY` already names
`independent_claim_drafting` and `reference_relevance` as task types. The
live page advertises Drafting (500 cases, human baseline 8.5/10) and Prior
Art (1,200 cases, human baseline 85%). The dataset contains zero cases in
either domain: `data/full/all_cases.jsonl` is 7,200 records split
administration 5,721 / prosecution 1,381 / analytics 98. This document
specifies how to build the two missing suites to the standard set by the
Layer 1 docketing suite and the PR #6 confusion-matrix infrastructure.

**Positioning resolution.** The page metadata says, verbatim, "Not a prior
art search benchmark, a prosecution response benchmark." The README's Prior
Art row says "Search strategy, reference analysis, relevance ranking." These
conflict. Resolution: the suite measures what an attorney does with a
candidate reference set (triage, rank, grade, map elements), never retrieval
from an open corpus. Every case supplies the full candidate pool in the
prompt. One harmonization edit ships with implementation: the README Prior
Art row drops "Search strategy" in favor of "Reference triage." A live
retrieval track remains explicitly out of scope; if it is ever wanted it is
a separately positioned product decision, not an extension of this suite.

---

## 1. Inherited contracts this design must satisfy

| Contract | Source | Implication for new suites |
|---|---|---|
| Test case schema | `patentbench/data_loader.py` `TestCase` | New cases use `id, domain, tier, task_type, prompt, reference_answer` (string, JSON-wrapped) plus optional `metadata, evaluation_layers, application_number, prior_art_refs, poison_pills, ...` |
| Adapter contract | `patentbench/models/base.py`, INTEGRATION.md | `generate(prompt: str) -> str`. Structured outputs travel as fenced JSON inside the text response, parsed by deterministic extractors (the `_parse_json_block` pattern in `patentbench/reports/ground_truth.py`) |
| Evaluator dispatch | `patentbench/evaluator.py` `DeterministicEvaluator.evaluate` | New task types get `elif` branches and dedicated checkers; per-field `MetricResult`, layer score 0.0 to 1.0 |
| Rubric schema | `data/rubrics/*.json`, `Rubric.from_json` | `{name, version, dimensions: [{name, description, weight, scale_min, scale_max, criteria: {"1".."5"}}]}` |
| Ground truth provenance | `patentbench/reports/ground_truth.py` | Every truth row carries a lineage block with source id, `retrieved_at`, field path, and raw value hash. `source: "llm"` and `source: "abigail"` are rejected. `quarantined: true` rows are excluded from cells but counted in totals |
| Artifact + verifier | `patentbench/reports/confusion.py`, `verify_confusion.py` (PR #6 branch) | Single-pass construction, per-cell test id traces, `source_sha256` and `ground_truth_sha256` baked into every artifact, deterministic JSON serialization, independent rebuild-and-compare verifier with loud failure |
| Layer weights | `config.py` `LAYER_WEIGHTS` | Deterministic 0.30, LLM judge 0.35, comparative 0.25, human calibration 0.10 |
| Tier naming | `config.py` `DifficultyTier` | 1 Paralegal, 2 Junior Associate, 3 Senior Associate, 4 Junior Partner, 5 Senior Partner. The code enum is canonical; the live page's tier card naming is one step out of phase and is corrected separately |

A wiring defect blocks the drafting suite and is promoted to milestone M0:
`BenchmarkRunner._evaluate_case` (`patentbench/harness.py`) only ever invokes
the deterministic evaluator. The `run_llm_judge` config flag is dead code,
and `LLMJudgeEvaluator._build_judge_prompt` hardcodes four score keys
(`legal_accuracy, factual_accuracy, argument_strength, completeness`) that
do not match the published rubric dimension names
(`statutory_correctness, ...`). Layer 2 has no working execution path in
the Python harness today.

---

## 2. Suite A: Application Drafting

### 2.1 Task definition

Invention disclosure in, claims and specification sections out.

| task_type | Tier | What the model receives | What the model produces |
|---|---|---|---|
| `independent_claim_drafting` | 3 | Disclosure + small known-art set | 1 independent claim + 3 dependent claims |
| `claim_set_drafting` | 4 | Disclosure + known-art set | Full claim set (up to 20 claims, 2 to 3 independent) |
| `specification_support_drafting` | 4 | Disclosure + a fixed claim set | Summary + support paragraphs giving 112(a) support for every claim term |
| `continuation_strategy_drafting` | 5 | Disclosure + parent prosecution summary | Deferred. Defined for tier completeness; not built in v1 |

Tier 1 has no drafting tasks by design (drafting starts at Tier 2 in
`TASK_REGISTRY`; the Tier 2 `claim_amendment` task already declared there is
prosecution-coupled and is a separate workstream, not this suite).

### 2.2 Input and output schema

Case (matches `TestCase.from_dict` exactly):

```json
{
  "id": "draft_indep_frontier_0001",
  "domain": "drafting",
  "tier": 3,
  "task_type": "independent_claim_drafting",
  "prompt": "<instructions + DISCLOSURE text + known-art summaries + output contract>",
  "reference_answer": "{\"anchor_status\": \"granted\", \"anchor_patent_number\": \"US12345678\", \"anchor_issued_claims\": [\"1. A method...\"], \"supplied_art\": [\"US10000001\", \"US10000002\"], \"disclosure_id\": \"disc_0001\", \"key_limitations\": [\"progressive layer unfreezing\", \"domain similarity metric\"]}",
  "evaluation_layers": ["deterministic", "llm_judge", "comparative", "human_calibration"],
  "metadata": {"disclosure_sha256": "<sha256>", "pool": "frontier", "canary_id": "cnry_0001"},
  "application_number": "18999999",
  "poison_pills": {"mpep": ["2199"], "case_law": ["Smith v. USPTO, 999 F.3d 1 (Fed. Cir. 2025)"], "background_refs": ["US 19/999,999"]}
}
```

Output contract (stated in every prompt): claims returned as numbered,
single-sentence claims inside a fenced block tagged `claims`; specification
text inside a fenced block tagged `spec` where applicable; any support
citations to the disclosure use bracketed paragraph ids (`[D-0014]`)
matching ids printed in the disclosure text. A response with no parseable
fenced claims falls back to a numbered-claim regex scan; if that also
fails, the case lands in an `unparseable` bucket (scored 0, traced,
reported), mirroring the confusion-matrix convention.

### 2.3 Ground truth and disclosure construction pipeline

There is no single correct application for a disclosure. The suite
therefore separates three roles that are usually conflated:

1. **Inputs** (the disclosure, the known-art set): constructed by us,
   committed to the repo, SHA-256 pinned. Inputs are not ground truth;
   LLM-assisted drafting of an input is permitted if disclosed in the
   lineage and signed off by an attorney reviewer. The
   `source: "llm"` ban in `ground_truth.py` applies to truth rows and is
   untouched.
2. **Anchors** (the claims that actually issued, or the as-filed claims
   when no grant exists): one admissible answer, used as judge context and
   for scope-comparison reporting. Never a similarity target.
3. **Scores**: computed from the model output itself against the disclosure
   and supplied art (deterministic layer), and against rubrics (judge +
   human layers).

**Iron rule: similarity-to-issued-text is banned as a scoring signal.** No
BLEU, ROUGE, embedding similarity, or token overlap against the anchor
claims anywhere in the suite. The anchor exists so the judge and human
raters can see what an examiner actually allowed, and so scope deltas can
be reported descriptively (broader / narrower / different). This is the
single most important anti-memorization decision in the suite: a model that
reproduces the issued claims verbatim gains nothing from doing so, and the
memorization probe (2.4) will quarantine the case besides.

**Disclosure derivation pipeline (per case):**

| Stage | Action | Lineage recorded |
|---|---|---|
| D1 | Select source application per contamination pool rules (2.4) | `application_number`, selection window |
| D2 | Extract as-filed specification sections (background, summary, embodiments, figure descriptions) from ODP / Google Patents; strip the claims and claim-echo summary sentences | `derived_from {application_number, source_document, retrieved_at, raw_value_hash}` |
| D3 | Rewrite into inventor-disclosure register (problem, solution, embodiments, known art); paragraph ids `[D-nnnn]` assigned; LLM assistance permitted | `derivation_method`, `attorney_reviewer`, review date |
| D4 | Embed one canary string and the poison pills; freeze; record `disclosure_sha256` | `canary_id`, `poison_pills` |

Disclosures live in `data/disclosures/<disclosure_id>.md` with a
`data/disclosures/manifest.json` mapping id to sha256 and lineage. The
drafting verifier recomputes every sha at verification time.

Anchor truth rows live in `data/ground_truth/independent_claim_drafting.json`
keyed by test id, carrying `google_patents_source` lineage (already
supported by the loader) or ODP document lineage, plus
`anchor_status: "granted" | "as_filed"`.

### 2.4 Contamination protocol

Threat model, stated plainly: every issued patent, pre-grant publication,
and public file wrapper through a model's training cutoff is plausibly in
its training data. "Reconstruct the issued claims" measures memorization.

Three case pools, reported separately, never blended in a headline number:

| Pool | Definition | Role |
|---|---|---|
| `frontier` | Source application's earliest publication date is after the newest SUT training cutoff on record; refreshed quarterly per the existing 20% rotation policy (METHODOLOGY.md section 5) | The only pool that feeds headline drafting numbers |
| `legacy` | Pre-cutoff grants (e.g. drawn from the existing 82-application corpus) | Development, regression, and contamination-drift measurement; published with a contamination-risk flag |
| `synthetic` | Attorney-authored disclosures for inventions that never existed as filings; no anchor | Highest-purity subset; small (target 10 to 20 cases); canary strings doubly important here |

Per-run memorization probe: before scoring a SUT on a case, the harness
sends a probe prompt ("Identify the patent family or assignee this
disclosure derives from, if known to you"). A correct identification
quarantines that case for that SUT (the existing `quarantined` mechanism:
excluded from cells, counted in totals, listed by id in the artifact).
Probe outputs are stored in the run file so the verifier can re-check the
quarantine decision.

Frontier-pool caveat recorded honestly: post-cutoff applications often have
no granted claims yet, so `anchor_status: "as_filed"` cases carry a weaker
anchor. This affects judge context, not scoring, because no score derives
from the anchor.

### 2.5 Scoring, mapped to the four layers

**Layer 1, deterministic (weight 0.30).** All checks compute from the model
output plus the committed inputs; none require external truth. New module
`patentbench/claim_checks.py`, pure functions, exhaustively unit-tested.

| Check | Metric name | Definition | Known limits |
|---|---|---|---|
| Antecedent basis | `antecedent_basis_rate` | Every "the X" / "said X" in a claim resolves to an earlier "a/an X" in the claim or its dependency chain | Plural/singular and functional-phrase edge cases; parser published, imperfection documented |
| Dependency structure | `dependency_valid` | Every dependent claim references an existing earlier claim; acyclic; no multiple-dependent-on-multiple-dependent (37 CFR 1.75); sequential numbering | Deterministic, no known limits |
| Claim-spec term consistency | `term_support_rate` | Share of claim noun phrases with literal or defined support in the disclosure plus the model's own spec output | Synonym blindness is intentional: unsupported renames are exactly what 112 flags |
| New matter screen (35 U.S.C. 132 proxy) | `new_matter_flags` | Claim limitations using vocabulary absent from the disclosure beyond a claim-language stopword list, flagged and counted | A lexical screen, not a legal conclusion; the legal question belongs to Layer 2; weight 0.5 inside the structural composite |
| Format compliance | `format_compliance` | Single sentence per claim, capitalization/period convention, requested claim counts delivered | Deterministic |
| Support citation existence | `citation_exists_rate` | Every `[D-nnnn]` cited by the model exists in the disclosure | Existence only; content fidelity is Layer 2 |

Structural composite = weighted mean (new matter screen at 0.5, all others
1.0), reported per-check and as `drafting_structural` 0.0 to 1.0.

**Layer 2, LLM judge (weight 0.35).** Requires M0 wiring fix. New rubric
`data/rubrics/claim_drafting.json` in the exact existing schema:

| Dimension | Weight | 1 (fail) | 3 (adequate) | 5 (expert) |
|---|---|---|---|---|
| `scope_calibration` | 2.0 | Reads on the supplied art, or so narrow it has no assertion value | Patentably distinct over the supplied art with reasonable breadth | Broadest defensible scope; deliberate fallback laddering in dependents |
| `support_112a` | 1.5 | Limitations with no written-description or enablement basis in the disclosure | All limitations supported, support is findable | Element-by-element support; no reach beyond the disclosure |
| `definiteness_112b` | 1.5 | Ambiguous terms of degree with no standard; unclear antecedent meaning | Claim language clear to a POSITA with minor imprecision | Every term definite, functional language properly anchored |
| `novelty_over_supplied_art` | 1.5 | A supplied reference discloses every limitation of an independent claim | Distinct over each supplied reference taken alone | Distinctions are the commercially meaningful ones, not trivial appendages |
| `eligibility_101` | 1.0 | Claim is a bare abstract idea / mental process where the field invites it | Recites a practical application | Eligibility designed in (technical effect, specific implementation) without sacrificing scope |
| `claim_architecture` | 1.0 | No dependent structure or duplicative dependents | Sensible dependent progression | Strategic laddering covering design-arounds and fallback positions |

Judge configuration follows METHODOLOGY.md: temperature 0.0, judge prompts
published, rubric dimension names become the required JSON score keys (part
of the M0 fix). Anti-hallucination is not a seventh dimension: the existing
`AntiHallucinationChecker` runs alongside and applies the established
formula (`max(0, 1 - (fabricated + 2 * poison_hits) / total_citations)`) as
a multiplier on the legal-accuracy-family dimensions, consistent with
METHODOLOGY.md section 4 and the page's "2.0x Anti-Hallucination" framing.

Published drafting score on the 10-point scale the page already advertises:
`drafting_score_10 = 2 * weighted_mean(judge dimensions)` after the
anti-hallucination multiplier. Human baseline target stays the page's
published 8.5/10, to be validated, not assumed, by Layer 4 calibration.

**Layer 3, comparative (weight 0.25).** The existing `ComparativeEvaluator`
works unchanged on drafting outputs (two claim sets for the same
disclosure, blind, randomized order, run twice with swapped positions).
Activated once two systems have Layer 2 drafting scores, per METHODOLOGY.

**Layer 4, human calibration (weight 0.10).** Licensed practitioners score
a stratified subset (minimum 20 drafting cases, both tiers, all three
pools) on the same rubric. Inter-rater reliability per METHODOLOGY
(Cohen's Kappa target at least 0.60). The drafting suite does not publish a
composite drafting number until at least one calibration round exists;
until then the page cell carries the Layer 1 structural score and a
"calibration pending" badge. This mirrors the current "per-layer reporting
until all layers are operational" policy.

### 2.6 Anti-hallucination design (drafting-specific)

- Poison pills in every case: one fabricated MPEP section and one fabricated
  case citation in the drafting instructions (from the existing
  `POISON_PILL_*` lists), plus one fabricated background reference
  (a patent number in a format that cannot exist) inside the disclosure's
  known-art discussion. Citing any of them in output trips the 2x penalty.
- Fabricated support citations: `[D-nnnn]` ids that do not exist in the
  disclosure are counted by the deterministic `citation_exists_rate` and
  feed `total_citations` in the anti-hallucination formula.
- Unsupported claims: limitations flagged by both the new-matter screen and
  the judge's `support_112a` at 1 or 2 are surfaced in the artifact as
  `unsupported_limitations` traces with claim numbers, so failures are
  inspectable, not just aggregated.

### 2.7 Tier targets

Human baseline targets (design targets consistent with the published page;
to be validated by Layer 4, never reported as measured until they are):

| Tier | Task | Target |
|---|---|---|
| 3 | `independent_claim_drafting` | 8.5 to 9.0 / 10 |
| 4 | `claim_set_drafting`, `specification_support_drafting` | 7.0 to 8.0 / 10 |
| 5 | `continuation_strategy_drafting` (deferred) | 5.0 to 6.5 / 10 |

Domain headline remains 8.5/10 as published.

---

## 3. Suite B: Prior Art (reference analysis over a supplied pool)

### 3.1 Task definition

Claims plus a frozen candidate reference pool in; a ranked, graded
assessment out. No retrieval. Two scored task types plus one tier 4
extension:

| task_type | Tier | Input | Output |
|---|---|---|---|
| `reference_relevance` | 2 | Claim 1 (+ key dependents) + pool of 20 references (id, number, title, abstract, key excerpt) | Fenced JSON: full ranking of pool ids + per-id grade X/Y/A/N |
| `anticipation_detection` | 3 | Claim 1 + one reference (excerpt) | Fenced JSON: role label + element mapping |
| `combination_selection` | 4 | Claim 1 + pool | The primary+secondary pair best supporting a 103 rejection, with rationale |
| Tier 5 | | Prosecution-aware art strategy (e.g. IPR-risk grading of a pool against issued claims) | Defined for completeness, deferred |

### 3.2 Input and output schema

```json
{
  "id": "pa_rank_16100000",
  "domain": "prior_art",
  "tier": 2,
  "task_type": "reference_relevance",
  "prompt": "<claim text + POOL listing + output contract>",
  "reference_answer": "{\"grades\": {\"US10000001\": 3, \"US10000002\": 2, \"US10000003\": 1, \"US10000004\": 0}, \"pool_ids\": [\"US10000001\", \"...\"], \"source_oa_mailing_date\": \"2021-03-04\"}",
  "evaluation_layers": ["deterministic", "llm_judge"],
  "application_number": "16100000",
  "prior_art_refs": ["US10000001", "US10000002"]
}
```

Model output contract (in every prompt): fenced JSON
`{"ranking": ["US10000001", ...], "grades": {"US10000001": "X", ...}}` with
grade letters X (anticipates / primary basis), Y (material in combination),
A (background, cited but not applied), N (not material). Letters map to
numeric relevance 3/2/1/0. Parsing uses the existing `_parse_json_block`
pattern; unparseable responses land in the traced `unparseable` bucket.
Any id in the output that is not in the pool is a **fabricated reference**:
recorded per-case as `out_of_pool_ids`, surfaced in the artifact the same
way `hallucinated_labels` works in the confusion module, and scored as
follows: fabricated ids are stripped before metric computation AND the case
is flagged; a model gains nothing and loses visibility by inventing
references.

### 3.3 Candidate pool construction, ground truth grading, provenance

**Frozen versus live, decided with reasons.** Pools are frozen, committed,
and SHA-256 pinned. Live search is rejected because (a) it cannot be
reproduced (corpus and engine drift), (b) it contradicts the published
positioning, and (c) it converts a scoring problem into a retrieval
infrastructure program. The cost of freezing, acknowledged: the suite
measures triage and analysis quality, not recall against the universe of
prior art. That limitation is printed on the page next to the suite's
numbers.

**Grading scale (ground truth), per reference per case:**

| Grade | Definition | Source of truth |
|---|---|---|
| 3 | Applied by the examiner as a 102 anticipation basis, or as the primary reference of a 103 rejection, in the source OA | OA rejection text (ODP document), parsed and attorney-spot-checked |
| 2 | Applied as a secondary reference in a 103 combination | OA rejection text |
| 1 | Cited by the examiner (form PTO-892) but never applied in a rejection | 892 / ODP citation record |
| 0 | Distractor: never cited anywhere in the application's record or family | Constructed (see below) |

Binary "relevant" for recall/precision/MAP means grade >= 2. Grade 1 is
deliberately excluded from "relevant": examiner-cited-not-applied is
ambiguous materiality, and counting it would reward listing everything.
Applicant IDS/SB08 references are excluded from pools entirely (applicant
self-disclosures carry no examiner materiality judgment); IDS membership is
used only as a distractor-exclusion screen. EPO X/Y citations (OPS) are
recorded, where the family has EP prosecution, as a cross-check annotation
(`epo_grade`) and agreement statistic, not as the grade itself: one office,
one grading authority per case, no blended truth.

**Pool assembly per case (target pool size 20):**

| Step | Rule |
|---|---|
| P1 | Positives: all grade 3 and grade 2 references from the source OA (typically 1 to 4) |
| P2 | Grade 1: up to 3 examiner-cited-not-applied references from the 892 |
| P3 | Distractors to fill to 20: same CPC subclass as the application, publication date no later than the application's effective filing date (every pool member must be temporally valid prior art, the same constraint the examiner faced), and not present in the application's 892, IDS, or family citation record |
| P4 | Distractor selection is deterministic: fixed query parameters, seeded ordering keyed to the case id, full selection recipe recorded in lineage |
| P5 | Attorney spot-validation on a 10% sample of pools; any distractor an attorney judges plausibly material is quarantined or regraded with a signed note |

Truth file `data/ground_truth/reference_relevance.json`, keyed by test id,
one row per case: `grades` map, `pool_ids`, per-reference lineage. Lineage
extends the loader with one new accepted family alongside `peds_source` and
`google_patents_source`:

```json
"oa_source": {"application_number": "16100000", "oa_mailing_date": "2021-03-04", "odp_document_id": "<id>", "retrieved_at": "<iso>", "raw_value_hash": "<sha256>"}
```

Same four-invariant shape as the existing families (source id, timestamp,
field path / document id, raw value hash). Distractor metadata carries
`google_patents_source` or ODP bulk lineage with `retrieved_at` and hash.

**Contamination note for this suite.** The examiner's citation list is
printed on the front page of the granted patent, so "name the cited art" is
memorizable. Three mitigations: (a) the task is pool-restricted ranking,
so a memorized front-page list does not by itself order a 20-item pool that
includes never-cited distractors from the same CPC neighborhood; (b) the
same frontier/legacy pool split and quarterly rotation as the drafting
suite, with headline numbers from frontier cases (OAs mailed after the
newest SUT cutoff); (c) a per-case memorization probe ("list the references
the examiner cited against this application") with quarantine-on-hit,
identical machinery to drafting.

### 3.4 Metrics (Layer 1, deterministic)

For each case, computed from the parsed ranking against truth grades, then
macro-averaged across cases. Pure functions added to
`patentbench/metrics.py::MetricsCalculator`, each unit-tested against
hand-computed fixtures:

| Metric | Definition | k values |
|---|---|---|
| `precision_at_k` | share of top k with grade >= 2 | 3, 5, 10 |
| `recall_at_k` | share of all grade >= 2 references appearing in top k | 3, 5, 10 |
| `map` | mean average precision, binary relevance grade >= 2 | n/a |
| `ndcg_at_k` | DCG with exponential gain `(2^grade - 1) / log2(rank + 1)`, normalized by the ideal ordering of the truth grades | 5, 10 |
| `x_hit_at_k` | 1 if any grade 3 reference appears in top k; reported only over cases that contain a grade 3 reference, with coverage stated | 1, 3 |
| `grade_accuracy` | exact-match accuracy of the per-id letter grades against truth | n/a |

Case eligibility: `reference_relevance` cases require at least one
art-based rejection (102 or 103) in the source OA; 112-only and 101-only
OAs are excluded from this task type.

Headline page cells: `ndcg_at_10` (x100) and `x_hit_at_3`, published
together. `x_hit_at_k` is this benchmark's analogue of the X Hit Rate
metric the vendor table attributes to PatSnap, with one difference made
explicit wherever the number appears: theirs measures retrieval from an
open corpus, ours measures recognition and ranking within a supplied pool.
The two are not directly comparable and the page must not imply they are.

`anticipation_detection` (Tier 3) is scored as a four-class label
(`anticipates`, `obviousness_primary`, `obviousness_secondary`,
`background`) where truth is the role the examiner actually gave the
reference. It reuses the PR #6 confusion-matrix pipeline end to end: one
new entry each in `REQUIRED_TRUTH_FIELDS` and `EXTRACTORS`, a truth file
with `oa_source` lineage, and the existing builder and verifier produce and
police the artifact. The element-mapping JSON the model returns alongside
the label is judged in Layer 2, not Layer 1.

### 3.5 Layers 2 through 4

**Layer 2.** New rubric `data/rubrics/prior_art_analysis.json`:

| Dimension | Weight | 1 | 3 | 5 |
|---|---|---|---|---|
| `element_mapping_accuracy` | 1.5 | Mappings misquote the reference or the claim | Key limitations mapped to real disclosure passages | Complete element-by-element mapping with pinpoint cites |
| `materiality_reasoning` | 1.0 | Conclusory ("X is relevant") | Explains which limitations each top reference reaches | Distinguishes anticipation from combination value; notes what is missing from each reference |
| `grade_consistency` | 1.0 | Grades contradict the model's own stated reasoning | Grades and reasoning broadly consistent | Grades, ranking, and rationale fully coherent |

The judge sees the pool excerpts, the claim, the model's ranking and
rationale; it does not see truth grades (it scores reasoning quality, not
agreement; agreement is Layer 1's job).

**Layer 3.** Pairwise comparison of two systems' rationales for the same
pool via the existing `ComparativeEvaluator`, once two systems have Layer 2
scores.

**Layer 4.** Practitioners re-grade a stratified 10% of pools blind
(references presented without examiner usage), producing (a) human baseline
measurements for the published 85% target and (b) validation of the
examiner-derived truth grades themselves; attorney/examiner disagreements
above a threshold quarantine the case. This addresses the known weakness
that examiner citation behavior is a proxy for materiality, not a platonic
truth.

### 3.6 Tier targets

| Tier | Task | Target (design target, Layer 4 validates) |
|---|---|---|
| 2 | `reference_relevance` | 90% (nDCG@10 basis) |
| 3 | `anticipation_detection` | 85% (label accuracy) |
| 4 | `combination_selection` | 75% (pair match) |
| 5 | deferred | 50 to 65% per page tier card |

Domain headline remains 85% as published.

---

## 4. Code changes

| # | Change | Files | Notes |
|---|---|---|---|
| C1 (M0) | Wire Layer 2 into the runner: invoke `LLMJudgeEvaluator` when `config.run_llm_judge` and `LLM_JUDGE in case.evaluation_layers`; build judge prompt score keys from rubric dimension names; add an `LLMClient` shim backed by the Anthropic adapter | `patentbench/harness.py`, `patentbench/evaluator.py`, `patentbench/models/anthropic_adapter.py`, tests | Prerequisite for every judged score in both suites; ships alone |
| C2 | `claim_checks.py`: antecedent basis, dependency graph, term support, new-matter screen, format, citation existence | `patentbench/claim_checks.py`, `tests/test_claim_checks.py` | Pure functions; parser limitations documented in module docstring |
| C3 | Ranking metrics | `patentbench/metrics.py`, `tests/test_ranking_metrics.py` | `precision_at_k, recall_at_k, average_precision, ndcg_at_k, x_hit_at_k` as `MetricsCalculator` staticmethods |
| C4 | `DeterministicEvaluator` dispatch: `_check_reference_relevance`, `_check_anticipation`, `_check_claim_drafting` | `patentbench/evaluator.py` | Follows the existing `elif` dispatch pattern |
| C5 | Truth loader: accept `oa_source` lineage; register `REQUIRED_TRUTH_FIELDS` and `EXTRACTORS` for `anticipation_detection`; truth-field registration for `reference_relevance` | `patentbench/reports/ground_truth.py` | "Adding a task requires a test and attorney sign-off" policy applies |
| C6 | New artifact builders + verifiers: `build_ranking_report.py` / `verify_ranking.py`, `build_drafting_report.py` / `verify_drafting.py`, plus `verify_all.py` that globs `reports/**` and dispatches by artifact type | `patentbench/reports/` | Same discipline as `verify_confusion`: rebuild from source run + truth, compare every number, exit codes 0/1/2/3 |
| C7 | CI: add an artifact-verification step running `python -m patentbench.reports.verify_all reports/` | `.github/workflows/ci.yml` | Closes an existing gap: committed artifacts are not currently re-verified in CI |
| C8 | `TASK_REGISTRY`: add `anticipation_detection`, `combination_selection`, `claim_set_drafting`, `specification_support_drafting`; add `DETERMINISTIC` to `independent_claim_drafting` layers | `patentbench/config.py` | |
| C9 | README harmonization: Prior Art row "Search strategy, reference analysis, relevance ranking" becomes "Reference triage, reference analysis, relevance ranking" | `README.md` | The positioning decision, applied |
| C10 | INTEGRATION.md: add a "ranked-output contract" subsection documenting the fenced-JSON ranking format for commercial tools | `INTEGRATION.md` | |
| C11 | Memorization probe runner support: probe prompt per case, probe result recorded in run file, per-SUT quarantine application | `patentbench/harness.py`, run file schema | Verifier re-checks quarantine decisions from recorded probe outputs |

**Adapter decision (explicit):** no new adapter ABC. The ranked-output suite
keeps `generate(prompt) -> str` and parses fenced JSON, exactly as the
PR #6 extractors already do for classification tasks. Rationale: every
INTEGRATION.md pattern (direct API, CSV round-trip, browser automation)
keeps working for ranking tools; a commercial search tool integrates by
rendering its ranked list as the fenced JSON contract. A dedicated
`RankedOutputAdapter` ABC would buy type safety at the cost of breaking the
universal text contract that the CSV and browser paths depend on.

No new `--domain` values are needed: `drafting` and `prior_art` already
exist in the `Domain` enum and the CLI passes them through.

---

## 5. File layout

```
data/
  disclosures/
    manifest.json                          # id -> sha256 + lineage (D1..D4)
    disc_0001.md ...
  benchmark_cases/
    drafting_v1.jsonl
    prior_art_reference_relevance.jsonl
    prior_art_anticipation.jsonl
  ground_truth/
    independent_claim_drafting.json        # anchors + lineage
    reference_relevance.json               # graded pools + lineage
    anticipation_detection.json
  rubrics/
    claim_drafting.json
    prior_art_analysis.json
  mini/
    mini_drafting_ids.json                 # frozen id lists (see section 7)
    mini_prior_art_ids.json
patentbench/
  claim_checks.py
  reports/
    build_ranking_report.py
    verify_ranking.py
    build_drafting_report.py
    verify_drafting.py
    verify_all.py
reports/
  confusion_matrices/<model>/anticipation_detection.{json,md}
  ranking/<model>/reference_relevance.{json,md}
  drafting/<model>/structural_checks.{json,md}
scripts/
  build_priorart_pools.py
  build_drafting_disclosures.py
tests/
  test_claim_checks.py
  test_ranking_metrics.py
  test_reports_ranking.py
  test_reports_drafting.py
```

Ranking artifact schema (per model): top-level `schema_version, model,
run_date, task_type, per_case[], aggregates{}, unparseable,
unparseable_test_ids, quarantined, quarantined_test_ids, total,
source_run_file, source_sha256, ground_truth_file, ground_truth_sha256,
generated_at, verifier_version`. Each `per_case` row carries `test_id`, the
parsed ranking, predicted and truth grades, `out_of_pool_ids`, and every
per-case metric, so any aggregate is an arithmetic fold over visible rows.
The drafting structural artifact follows the same envelope with per-check
rates and `unsupported_limitations` traces.

---

## 6. CI and independent verification

Every published number is rebuildable from pinned sources, enforced in CI:

1. Builders construct artifacts in a single pass with inline invariant
   checks (the PR #6 discipline).
2. Every artifact bakes in `source_sha256` and `ground_truth_sha256`.
3. `verify_ranking` / `verify_drafting` / `verify_confusion` rebuild each
   artifact from the run file and truth file on disk and compare every cell,
   trace, metric, and SHA; exit 1 arithmetic drift, 2 SHA drift, 3 schema.
4. The new CI step runs `verify_all` over `reports/**` on every push and PR,
   so a drifted or hand-edited artifact cannot merge.
5. `.gitattributes` LF pinning extends to the new artifact paths.

---

## 7. Mini subsets

PatentBench-Mini is 300 of 7,200 (4.2%). Applied proportionally to the
page's target structure:

| Suite | Full target | Mini size | v1 interim |
|---|---|---|---|
| Drafting | 500 | 20 | 10 (frozen id list once M3 lands) |
| Prior Art | 1,200 | 50 | 50 (M2 ships 82 ranking + 82 anticipation cases; mini freezes 50 ids across both) |

Mini membership is a committed id list in `data/mini/`, never a runtime
sample, so mini runs are reproducible byte for byte.

---

## 8. Phasing and milestones

| Milestone | Content | First verifiable published cell |
|---|---|---|
| M0 | Layer 2 wiring fix (C1) + tests. Code-only PR, no data | none (unblocks M3/M4) |
| M1 | `anticipation_detection`: 82 cases + `oa_source` truth + extractor + confusion matrix artifact for ABIGAIL v3 + verify in CI | **Prior Art cell 1**: anticipation label accuracy + full confusion matrix, verify_confusion green |
| M2 | `reference_relevance`: 82 pools + ranking metrics + evaluator branch + ranking artifact + `verify_ranking` + CI step (C7) | Prior Art headline cells: nDCG@10 and X-Hit@3 |
| M3 | Drafting structural: 10 frontier disclosures + `claim_checks.py` + structural artifact + `verify_drafting` | **Drafting cell 1**: structural pass rates (antecedent basis, dependency validity, term support) |
| M4 | Drafting judged: `claim_drafting.json` rubric + M0 wiring + 30 cases (25 frontier + 5 synthetic) + memorization probes + Layer 4 calibration round 1 (2 attorneys minimum) | Drafting 10-point score with "calibration round 1" annotation |
| M5 | Scale toward page targets, quarterly rotation in effect, Tier 4 tasks (`combination_selection`, `claim_set_drafting`, `specification_support_drafting`), mini id freeze, leaderboard wiring | Full domain rows on the page |

The smallest first deliverable per suite is M1 (prior art, reuses the
PR #6 pipeline end to end with one extractor and one truth file) and M3
(drafting, deterministic layer only, no judge dependency). Both produce a
page cell backed by a committed artifact and a green independent verifier.

Sequencing dependency: M1 and M2 build on the `patentbench.reports` module,
which currently lives on the open PR #6 branch (`feat/paralegal-oa-cm-matrices`).
M1 starts after PR #6 merges or rebases onto it explicitly.

---

## 9. Risks and open questions

Ordered, contamination and reproducibility first:

1. **Contamination (drafting).** Highest risk in the benchmark. Mitigations
   in 2.4 (pool split, probes, canaries, anchors-never-scored). Residual:
   a model may have memorized the as-filed spec (same family as the
   disclosure) without the probe firing. Accepted and disclosed; the
   synthetic pool is the long-term answer and needs attorney hours.
2. **Contamination (prior art).** Front-page citation lists are
   memorizable. Mitigations in 3.3. Residual: legacy-pool numbers are
   structurally optimistic; they never feed headlines.
3. **Examiner citations as truth.** Examiners miss art and make
   idiosyncratic grading choices. The suite scores agreement with what the
   examiner did, which is the practice-relevant question for prosecution
   support, but it is a proxy. Mitigations: pool-restricted task framing,
   EPO cross-check annotation, Layer 4 blind re-grading with
   quarantine-on-disagreement.
4. **Distractor false negatives.** A "grade 0" distractor might genuinely
   anticipate. Mitigations: exclusion screens (892, IDS, family), temporal
   validity, attorney spot-validation, quarantine path. Residual risk
   stated in the artifact docs.
5. **No-single-answer scoring (drafting).** Addressed by the three-role
   split (inputs / anchors / scores) and the similarity ban. Residual:
   judge preference bias toward verbose claim sets; mitigated by
   `claim_architecture` criteria, comparative layer, and calibration.
6. **Antecedent-basis parser precision.** Claim grammar is hard. The
   checker ships with a published test corpus; disagreements between the
   checker and attorneys get test cases, and the structural composite
   weights can be revisited at a versioned rubric bump.
7. **Judge gaming and rubric drift.** Judge model pinned by version, judge
   prompts published, rotation policy already covers case staleness;
   rubric changes bump `version` per the existing rubric schema.
8. **PatSnap comparison misread.** X-Hit@k within a pool is not an open
   retrieval hit rate. Every surface that shows the number carries the
   one-line distinction.
9. **Attorney-hours bottleneck.** Synthetic disclosures, spot-validation,
   and calibration all draw on scarce practitioner time. The phasing
   front-loads everything that does not need it (M0 through M3).
10. **Public data versus held-out policy.** METHODOLOGY.md commits to a
    held-out set, but the repo currently publishes all committed cases.
    These suites follow current practice (publish + rotate). If a held-out
    split is wanted, it is a separate decision affecting all domains.
    **Open question for the operator.**
11. **Frontier anchor weakness.** Post-cutoff cases may lack granted
    claims; `anchor_status` records it. No score impact by design.
12. **Open question for the operator:** the frontier window requires a
    declared "newest SUT training cutoff" registry (per-model cutoff dates
    maintained in the repo). Proposed: a `data/sut_cutoffs.json` checked at
    case-assignment time. Needs sign-off because it commits us to tracking
    vendor cutoff claims.

---

## 10. Review round record (Phase 2)

(Filled after the fresh-context evaluator pass and the council review;
records each accepted finding and the resulting edit, plus rejected
findings with reasons.)
