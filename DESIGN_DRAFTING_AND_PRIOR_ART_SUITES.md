# Design: Drafting and Prior Art Benchmark Suites

> **Status: DESIGN ONLY. No benchmark code ships with this document.**
> Every code item in section 4 describes code that does NOT exist yet; this
> is a plan, intentionally ahead of implementation.
>
> Decision of record (operator, 2026-06-10): the Prior Art suite is built as
> **reference analysis over a supplied candidate pool**, not open-corpus
> search. This keeps the public positioning ("Not a prior art search
> benchmark, a prosecution response benchmark," baked into the page metadata)
> intact while implementing the Prior Art domain the taxonomy already
> declares.
>
> Reviewed before commit by a fresh-context evaluator pass over the whole
> plan and a four-reviewer council on the two hardest design questions
> (prior art ground truth and reproducibility; drafting scoring where no
> single correct answer exists). Section 10 records every accepted and
> rejected finding and what changed.

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
| Ground truth provenance | `patentbench/reports/ground_truth.py` | Every truth row carries a lineage block with source id, `retrieved_at`, field path, and raw value hash. `source: "llm"` and `source: "abigail"` are rejected (enforced in `load_ground_truth`). `quarantined: true` rows are excluded from cells but counted in totals |
| Artifact + verifier | `patentbench/reports/confusion.py`, `verify_confusion.py` (PR #6 branch) | Single-pass construction, per-cell test id traces, `source_sha256` and `ground_truth_sha256` baked into every artifact, deterministic JSON serialization, independent rebuild-and-compare verifier with loud failure |
| Layer weights | `config.py` `LAYER_WEIGHTS` | Deterministic 0.30, LLM judge 0.35, comparative 0.25, human calibration 0.10 |
| Tier naming | `config.py` `DifficultyTier` | 1 Paralegal, 2 Junior Associate, 3 Senior Associate, 4 Junior Partner, 5 Senior Partner. The code enum is canonical; the live page's tier card naming is one step out of phase and is corrected separately |

Current-state defects this design depends on fixing (all promoted to
milestone M0):

- `BenchmarkRunner._evaluate_case` (`patentbench/harness.py`) only ever
  invokes the deterministic evaluator; the `run_llm_judge` config flag is
  dead code. Layer 2 has no execution path in the Python harness today.
- `LLMJudgeEvaluator._build_judge_prompt` and `_parse_judge_response`
  hardcode four score keys (`legal_accuracy, factual_accuracy,
  argument_strength, completeness`) that do not match the published rubric
  dimension names (`statutory_correctness, ...`). M0 replaces both with
  rubric-driven keys.
- The anti-hallucination score is currently recorded as one metric among
  many and averaged; METHODOLOGY.md section 4 specifies it as a multiplier
  on the legal-accuracy dimensions. M0 implements the multiplier.

---

## 2. Suite A: Application Drafting

### 2.1 Task definition

Invention disclosure in, claims and specification sections out.

| task_type | Tier | What the model receives | What the model produces |
|---|---|---|---|
| `independent_claim_drafting` | 3 | Disclosure + small known-art set | 1 independent claim + 3 dependent claims |
| `claim_set_drafting` | 4 | Disclosure + known-art set | Full claim set (up to 20 claims, 2 to 3 independent) |
| `specification_support_drafting` | 4 | Disclosure + a fixed claim set | Summary + support paragraphs giving 112(a) support for every claim term |
| `continuation_strategy_drafting` | 5 | Disclosure + parent prosecution summary | Deferred. Defined for tier completeness; not built in v1. Continuation and family context deliberately lives here, not in tiers 3 to 4 |

Tier 1 has no drafting tasks by design (drafting starts at Tier 2 in
`TASK_REGISTRY`; the Tier 2 `claim_amendment` task already declared there is
prosecution-coupled and is a separate workstream, not this suite).

Input realism (added in review): every case prompt carries the invention
`title`, explicit `claim_count_instructions` (e.g. "one independent claim
and three dependent claims"), and the statement that drafting is for US
prosecution. v1 is US-only; jurisdiction variation is out of scope.

### 2.2 Input and output schema

Case (matches `TestCase.from_dict` exactly):

```json
{
  "id": "draft_indep_frontier_0001",
  "domain": "drafting",
  "tier": 3,
  "task_type": "independent_claim_drafting",
  "prompt": "<instructions + title + claim-count instructions + DISCLOSURE text + known-art summaries + output contract>",
  "reference_answer": "{\"anchor_status\": \"granted\", \"anchor_patent_number\": \"US12345678\", \"anchor_issued_claims\": [\"1. A method...\"], \"supplied_art\": [\"US10000001\", \"US10000002\"], \"disclosure_id\": \"disc_0001\", \"key_limitations\": [\"progressive layer unfreezing\", \"domain similarity metric\"]}",
  "evaluation_layers": ["deterministic", "llm_judge", "comparative", "human_calibration"],
  "metadata": {"disclosure_sha256": "<sha256>", "pool": "frontier", "canary_id": "cnry_0001", "technology_center": "TC2100"},
  "application_number": "18999999",
  "poison_pills": {"mpep": ["2199"], "case_law": ["Smith v. USPTO, 999 F.3d 1 (Fed. Cir. 2025)"], "background_refs": ["US 19/999,999"]}
}
```

`reference_answer` is a JSON-wrapped string by repo convention; the loader
does not validate its content, so a new case-file validator (C12) checks at
CI time that every new-suite `reference_answer` parses as JSON and carries
the per-task required keys.

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
   when no grant exists): one admissible answer. Used ONLY in Layer 4
   human review and in post-hoc descriptive scope-delta reporting. The
   automated judge never sees the anchor (review change: anchor-blind
   judge; see section 10, R3-4/R4-2). Never a similarity target.
3. **Scores**: computed from the model output itself against the disclosure
   and supplied art (deterministic layer), and against rubrics (judge +
   human layers).

**Iron rule: similarity-to-issued-text is banned as a scoring signal.** No
BLEU, ROUGE, embedding similarity, or token overlap against the anchor
claims anywhere in the suite. The anchor exists so human raters can see
what an examiner actually allowed, and so scope deltas can be reported
descriptively (broader / narrower / different). Layer 4 reviewer
instructions carry an explicit note: anchor claims issued after rejections
and amendments, so they are often narrower than a sound first draft should
be; reviewers grade what should have been proposed, not what finally
issued.

**Disclosure derivation pipeline (per case):**

| Stage | Action | Lineage recorded |
|---|---|---|
| D1 | Select source application per contamination pool rules (2.4) | `application_number`, selection window |
| D2 | Extract as-filed specification sections (background, summary, embodiments, figure descriptions) from ODP / Google Patents; strip the claims and claim-echo summary sentences | `derived_from {application_number, source_document, retrieved_at, raw_value_hash}` |
| D3 | Rewrite into inventor-disclosure register (problem, solution, embodiments, known art); paragraph ids `[D-nnnn]` assigned; LLM assistance permitted | `derivation_method`, `attorney_reviewer`, review date |
| D4 | Embed one canary string and the poison pills; freeze; record `disclosure_sha256` | `canary_id`, `poison_pills` |

Disclosures live in `data/disclosures/<disclosure_id>.md` with a
`data/disclosures/manifest.json` mapping id to sha256 and lineage. The
drafting verifier recomputes the sha of every disclosure file, checks it
against the manifest, and checks each case's `metadata.disclosure_sha256`
against both.

Anchor truth rows live in `data/ground_truth/independent_claim_drafting.json`
keyed by test id, carrying `google_patents_source` lineage (already
supported by the loader) or ODP document lineage, plus
`anchor_status: "granted" | "as_filed"`. Per-case artifacts and aggregate
reporting are stratified by `anchor_status`.

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

**Cutoff registry (concretized in review).** Frontier assignment requires
`data/sut_cutoffs.json`, committed BEFORE any case is assigned to a pool.
One entry per system: `{system, cutoff_date (ISO 8601), source_url,
attestation_note, recorded_at}`. Ambiguous vendor statements ("trained
through July 2024") resolve conservatively to the last day of the stated
period. Updates land by PR with a linked vendor source, on the same
quarterly cadence as case rotation. The registry is a trust boundary and
is flagged as such: a wrong vendor claim shifts cases between pools, which
is why the legacy-versus-frontier delta (below) is published regardless.

**Memorization probe (protocol concretized in review).** Before scoring a
SUT on a case, the harness sends a probe prompt ("Identify the patent
family or assignee this disclosure derives from, if known to you"). The
quarantine rule is mechanical and published in `data/probe_protocol.json`:
naming the source application or patent number, or reproducing two or more
of the case's cited references, quarantines that case for that SUT (the
existing `quarantined` mechanism: excluded from cells, counted in totals,
listed by id in the artifact). Any other response, including abstention,
proceeds to scoring. Probe outputs are stored in the run file so the
verifier can re-check every quarantine decision.

The probe is a one-sided test: it catches models that honestly surface
memorization and does nothing against a model that recognizes the case and
denies it. The binding control is therefore the frontier pool, which
post-dates every registered cutoff. Per model, the artifact publishes the
legacy-minus-frontier score delta as a standing contamination indicator,
plus the per-model quarantine count and effective case set size, so
cross-model comparability is visible rather than assumed.

Frontier-pool caveat recorded honestly: post-cutoff applications often have
no granted claims yet, so `anchor_status: "as_filed"` cases carry a weaker
anchor. This affects Layer 4 context and descriptive reporting only,
because no score derives from the anchor.

### 2.5 Scoring, mapped to the four layers

**Layer 1, deterministic (weight 0.30).** All checks compute from the model
output plus the committed inputs; none require external truth. New module
`patentbench/claim_checks.py`, pure functions, exhaustively unit-tested.

Gate before scoring (added in review, R3-1): a responsiveness gate. The
output must contain the requested number of claims, and each independent
claim must have a minimum substance floor (at least 25 words and at least
3 distinct limitation clauses, both computed deterministically). Outputs
failing the gate are scored with the structural composite capped at 0.2
and flagged `non_responsive` in the artifact. This closes the degenerate
strategy of trivially short disclosure-copied claims scoring near 1.0 on
every structural check.

| Check | Metric name | Definition | Known limits |
|---|---|---|---|
| Antecedent basis (deterministic part) | `antecedent_basis_rate` | Every "the X" / "said X" in a claim resolves to an earlier "a/an X" in the claim or its dependency chain, exact-match grammar only | Scored. Plural/singular and functional-phrase heuristics are split out below |
| Antecedent basis (heuristic part) | `antecedent_basis_warnings` | Functional-phrase and number-mismatch patterns the exact parser cannot resolve | Advisory only, never scored; surfaced to Layer 2 and in the artifact |
| Dependency structure | `dependency_valid` | Every dependent claim references an existing earlier claim; acyclic; no multiple-dependent-on-multiple-dependent (37 CFR 1.75); sequential numbering | Deterministic. Code note: the 1.75 rule rarely fires in modern practice; a failure here is real but uncommon |
| Claim-disclosure term consistency | `term_support_rate` | Share of claim noun phrases with literal or defined support in the disclosure (for `specification_support_drafting`, disclosure-sourced support ONLY; the model's own spec output never counts, and spec sentences whose n-gram overlap with claim language exceeds 70% are excluded as self-support) | Synonym blindness is intentional: unsupported renames are exactly what 112 flags |
| Disclosure support screen | `disclosure_support_flags` | Claim limitations using vocabulary absent from the disclosure beyond a claim-language stopword list, flagged and counted. (Renamed in review from "new matter screen": section 132 new matter is measured against the application as filed, and in greenfield drafting the model IS drafting the application. This is a grounding check, not a statutory proxy.) | Lexical screen; weight 0.5 in the composite; every flag is re-assessed by the Layer 2 judge |
| 112(f) exposure flag | `mpf_flags` | "means for" / "step for" phrases without recited structure, flagged | Advisory only; feeds the judge's definiteness assessment |
| Format compliance | `format_compliance` | Single sentence per claim, capitalization/period convention, requested claim counts delivered | Deterministic |
| Support citation existence | `citation_exists_rate` | Every `[D-nnnn]` cited by the model exists in the disclosure | Existence only; content fidelity is Layer 2 |

Structural composite = weighted mean of the SCORED checks
(`disclosure_support_flags` at 0.5, the other scored checks at 1.0;
advisory checks excluded), reported per-check and as `drafting_structural`
0.0 to 1.0. The published M3 cell is labeled "structural compliance," not
"drafting quality": Layer 1 is necessary, not sufficient, and the page
copy says so.

**Layer 2, LLM judge (weight 0.35).** Requires M0 wiring fix. New rubric
`data/rubrics/claim_drafting.json` in the exact existing schema. Weights
rebalanced in review (scope_calibration reduced from 2.0 to 1.5 to cap
single-dimension noise amplification; `infringement_architecture` added):

| Dimension | Weight | 1 (fail) | 3 (adequate) | 5 (expert) |
|---|---|---|---|---|
| `scope_calibration` | 1.5 | Reads on the supplied art, or so narrow it has no assertion value | Patentably distinct over the supplied art with reasonable breadth | Broadest defensible scope; deliberate fallback laddering in dependents |
| `support_112a` | 1.5 | Limitations with no written-description or enablement basis in the disclosure | All limitations supported, support is findable | Element-by-element support; no reach beyond the disclosure |
| `definiteness_112b` | 1.5 | Ambiguous terms of degree with no standard; unintended means-plus-function invocation under 112(f) | Claim language clear to a POSITA with minor imprecision | Every term definite; functional language anchored to structure; 112(f) used only deliberately |
| `novelty_over_supplied_art` | 1.5 | A supplied reference discloses every limitation of an independent claim | Distinct over each supplied reference taken alone | Distinctions are the commercially meaningful ones, not trivial appendages |
| `eligibility_101` | 1.0 or 0.25 | Claim is a bare abstract idea / mental process where the field invites it | Recites a practical application | Eligibility designed in (technical effect, specific implementation) without sacrificing scope |
| `claim_architecture` | 1.0 | No dependent structure or duplicative dependents | Sensible dependent progression | Strategic laddering covering design-arounds and fallback positions; for multi-independent sets, independents are distinct enough that restriction exposure is considered |
| `infringement_architecture` | 1.0 | Claims unable to detect foreseeable infringing variants | Covers the main variant classes (method / apparatus / product) where the disclosure supports them | Independent claims placed to catch design-arounds and both direct and indirect infringement lanes |

`eligibility_101` weight is conditional on technology center, recorded per
case in `metadata.technology_center` at build time: full weight 1.0 for
software and business-method centers (e.g. TC2100, TC3600), reduced 0.25
elsewhere (mechanical, chemical, biotech), because 101 exposure is not a
live drafting issue in most non-software fields and full weight there adds
noise.

Judge configuration: temperature 0.0, judge prompts published, rubric
dimension names become the required JSON score keys (M0). The judge is
anchor-blind (2.3). For `scope_calibration` and `novelty_over_supplied_art`
the judge prompt includes the deterministic parser's element list for each
independent claim and requires the judge to complete a mini claim chart
(element by supplied-reference: disclosed where?) in its reasoning BEFORE
emitting scores; the chart is stored in the judge trace. Judge prompts
never contain tier targets or human baseline numbers. Anti-hallucination
is not an eighth dimension: the existing `AntiHallucinationChecker` runs
alongside and applies the established formula
(`max(0, 1 - (fabricated + 2 * poison_hits) / total_citations)`) as a
multiplier on `support_112a`, `novelty_over_supplied_art`, and
`eligibility_101` (the legal-accuracy-family dimensions; enumerated in
review, R3-8), consistent with METHODOLOGY.md section 4.

Published drafting score on the 10-point scale the page already advertises,
remapped in review so the scale floor is 0:
`drafting_score_10 = (weighted_mean(judge dimensions) - 1) * 2.5`, applied
after the anti-hallucination multiplier; a weighted mean of 1.0 maps to
0/10 and 5.0 maps to 10/10. Per-dimension scores are always published
alongside the composite.

**Layer 3, comparative (weight 0.25).** The existing `ComparativeEvaluator`
works unchanged on drafting outputs (two claim sets for the same
disclosure, blind, randomized order, run twice with swapped positions).
Activated once two systems have Layer 2 drafting scores, per METHODOLOGY.

**Layer 4, human calibration (weight 0.10).** Licensed practitioners score
a stratified subset (minimum 20 drafting cases, both tiers, all three
pools) on the same rubric, with the anchor visible and the
post-amendment-narrowness note from 2.3. Inter-rater reliability per
METHODOLOGY (Cohen's Kappa target at least 0.60 overall), PLUS a
dimension-specific gate added in review: no composite drafting number is
published until `scope_calibration` alone reaches Kappa at least 0.60
between the judge and human raters, because that dimension carries the
largest interpretive load. Until calibration round 1 exists the page cell
carries the Layer 1 structural score and a "calibration pending" badge,
mirroring the current per-layer reporting policy.

### 2.6 Anti-hallucination design (drafting-specific)

- Poison pills in every case: one fabricated MPEP section and one fabricated
  case citation in the drafting instructions (from the existing
  `POISON_PILL_*` lists), plus one fabricated background reference
  (a patent number in a format that cannot exist) inside the disclosure's
  known-art discussion. Citing any of them in output trips the 2x penalty.
- Fabricated support citations: `[D-nnnn]` ids that do not exist in the
  disclosure are counted by the deterministic `citation_exists_rate` and
  feed `total_citations` in the anti-hallucination formula.
- Unsupported claims: limitations flagged by both the disclosure support
  screen and the judge's `support_112a` at 1 or 2 are surfaced in the
  artifact as `unsupported_limitations` traces with claim numbers, so
  failures are inspectable, not just aggregated.

### 2.7 Tier targets

Targets are provisional ranges pending Layer 4 measurement; they are never
shown to the judge and never reported as measured human performance until
a calibration round produces them. Review note (R4-3): the page's
published 8.5/10 drafting baseline may be optimistic against this rubric's
severity (a rubric 5 describes senior-attorney review quality, not a
typical competent first draft). Calibration round 1 arbitrates; if
measured baselines land below the published figure, updating the page is
an operator decision flagged in section 9.

| Tier | Task | Provisional target range |
|---|---|---|
| 3 | `independent_claim_drafting` | 6.5 to 8.5 / 10 |
| 4 | `claim_set_drafting`, `specification_support_drafting` | 6.0 to 8.0 / 10 |
| 5 | `continuation_strategy_drafting` (deferred) | 5.0 to 6.5 / 10 |

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

`prior_art_refs` (an existing TestCase field) is informational and holds
the grade>=2 ids for human readability; the authoritative pool membership
and grades live in the ground truth file. `reference_answer` content is
validated by the C12 case-file validator.

Model output contract (in every prompt): fenced JSON
`{"ranking": ["US10000001", ...], "grades": {"US10000001": "X", ...}}` with
grade letters X (anticipates / primary basis), Y (material in combination),
A (background, cited but not applied), N (not material). Letters map to
numeric relevance 3/2/1/0. Parsing uses the existing `_parse_json_block`
pattern; unparseable responses land in the traced `unparseable` bucket.
Any id in the output that is not in the pool is a **fabricated reference**:
recorded per-case as `out_of_pool_ids`, surfaced in the artifact the same
way `hallucinated_labels` works in the confusion module, and stripped
before metric computation; the case is flagged. A model gains nothing and
loses visibility by inventing references.

Parsing edge cases (added in review, R2-3/R2-5), all deterministic:

- Duplicate ids in `ranking`: first occurrence kept, later duplicates
  dropped and flagged `duplicate_ids`.
- Partial ranking (fewer than 20 ids): scored as-is. Positions beyond the
  list contribute nothing; recall@k counts only relevant items actually
  ranked in the top k, so omission is naturally penalized. The case is
  flagged `partial_ranking` with the returned length.
- Ties: impossible by construction; the JSON array is an ordering.
- Missing grade for a ranked id: treated as "N" for `grade` scoring and
  flagged `missing_grades`.

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
deliberately excluded from binary relevance: examiner-cited-not-applied is
ambiguous materiality, and counting it would reward listing everything.
Grade 1 DOES carry nDCG gain 1 (see 3.4): ranking a reference the examiner
found worth citing above a never-cited distractor is desirable attorney
behavior, and the graded and binary metrics deliberately answer different
questions. To keep that choice auditable, every ranking artifact includes
a sensitivity block reporting the binary metrics under both thresholds
(grade >= 1 and grade >= 2).

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
| P4 | **Snapshot-authoritative committal (rewritten in review, R1-4):** the full metadata of every pool member (number, title, abstract, excerpt, CPC codes as retrieved, publication date, retrieval timestamp, raw value hash) is committed in the truth file at build time. Verification NEVER re-queries any API: the committed snapshot is the corpus of record, and the selection recipe (query parameters, seed keyed to case id) is recorded for audit, not for re-execution. CPC reclassification and upstream page drift therefore cannot break a future rebuild |
| P5 | Attorney spot-validation on a 10% sample of pools; any distractor an attorney judges plausibly material is quarantined or regraded with a signed note |

Truth file `data/ground_truth/reference_relevance.json`, keyed by test id,
one row per case: `grades` map, `pool_ids`, full per-reference snapshot
metadata and lineage. Lineage extends the loader with one new accepted
family alongside `peds_source` and `google_patents_source`:

```json
"oa_source": {"application_number": "16100000", "oa_mailing_date": "2021-03-04", "odp_document_id": "<id>", "retrieved_at": "<iso>", "raw_value_hash": "<sha256>"}
```

Same four-invariant shape as the existing families (source id, timestamp,
field path / document id, raw value hash).

**Contamination, restated without overclaim (review change, R1-1).** The
examiner's citation list is printed on the front page of the granted
patent, so for pre-cutoff cases a memorized citation list largely solves
the ranking task: placing the remembered cited references on top is most
of the available nDCG gain, regardless of distractors. Pool restriction
does NOT defeat citation-list memorization. The defenses are therefore:
(a) headline cells are computed from frontier cases only (OAs and grants
post-dating every registered cutoff in `data/sut_cutoffs.json`), with
legacy cases reported separately and flagged; (b) the same memorization
probe and quarantine protocol as drafting (`data/probe_protocol.json`,
probe asks the model to list the references it knows the examiner cited;
two or more reproduced citations or the application number triggers
quarantine); (c) the published per-model legacy-minus-frontier delta as a
standing contamination indicator. The probe remains one-sided (a model can
recognize and deny); the frontier pool is the binding control.

### 3.4 Metrics (Layer 1, deterministic)

For each case, computed from the parsed ranking against truth grades, then
macro-averaged across cases with 95% bootstrap confidence intervals per
METHODOLOGY.md section 7. Pure functions added to
`patentbench/metrics.py::MetricsCalculator`, each unit-tested against
hand-computed fixtures:

| Metric | Definition | k values |
|---|---|---|
| `precision_at_k` | share of top k with grade >= 2 | 3, 5, 10 |
| `recall_at_k` | share of all grade >= 2 references appearing in top k | 3, 5, 10 |
| `map` | mean average precision, binary relevance grade >= 2 | n/a |
| `ndcg_at_k` | DCG with exponential gain `(2^grade - 1) / log2(rank + 1)` over the full 0 to 3 grade scale, normalized by the ideal ordering of the truth grades | 5, 10 |
| `x_hit_at_k` | 1 if any grade 3 reference appears in top k; computed only over cases that contain a grade 3 reference, and every surface that shows the number also shows the coverage denominator (eligible cases / total cases) | 1, 3 |
| `grade_scores` | per-class precision, recall, and F1 for the four grade letters (exact-match accuracy is recorded in the artifact but never used as a headline: the grade distribution is dominated by N/0 distractors, which inflates raw accuracy) | n/a |

**Random-ranking baseline row (added in review, R2-4).** Every ranking
artifact computes and publishes the expected value of each metric under a
uniformly random ranking of the same pools (closed form where available,
otherwise seeded Monte Carlo committed with the artifact). The leaderboard
shows this row so the floor of every metric is visible; no metric is
published without its random baseline.

Case eligibility (enforced at case build time by
`scripts/build_priorart_pools.py`, not at evaluation time):
`reference_relevance` cases require at least one art-based rejection (102
or 103) in the source OA; 112-only and 101-only OAs are excluded from this
task type.

Headline page cells: `ndcg_at_10` (x100) and `x_hit_at_3` with its
coverage denominator, published together over frontier cases. `x_hit_at_k`
is this benchmark's analogue of the X Hit Rate metric the vendor table
attributes to PatSnap, with one difference made explicit wherever the
number appears: theirs measures retrieval from an open corpus, ours
measures recognition and ranking within a supplied pool. The two are not
directly comparable and the page must not imply they are.

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
truth. The artifact also publishes the per-case correlation between
ranking quality (nDCG) and grading quality (per-class F1), because high
ranking with low grading indicates role-classification confusion worth
surfacing.

### 3.6 Tier targets

Provisional design targets, Layer 4 validates; never shown to the judge:

| Tier | Task | Provisional target |
|---|---|---|
| 2 | `reference_relevance` | 85 to 90 (nDCG@10 x100 basis) |
| 3 | `anticipation_detection` | 80 to 90% (label accuracy) |
| 4 | `combination_selection` | 70 to 80% (pair match) |
| 5 | deferred | 50 to 65% per page tier card |

Domain headline remains 85% as published, subject to the same Layer 4
arbitration note as drafting (section 2.7).

---

## 4. Code changes

> Everything in this section is NEW code or NEW data. None of it exists in
> the repo today; the table is the build list, not a description of current
> state.

| # | Change | Files | Notes |
|---|---|---|---|
| C1 (M0) | Wire Layer 2 into the runner: invoke `LLMJudgeEvaluator` when `config.run_llm_judge` and `LLM_JUDGE in case.evaluation_layers`; replace the hardcoded judge-prompt and parser score keys with rubric-driven dimension names; implement the anti-hallucination multiplier (currently the score is only recorded as a metric and averaged, diverging from METHODOLOGY.md section 4); add an `LLMClient` shim backed by the Anthropic adapter | `patentbench/harness.py`, `patentbench/evaluator.py`, `patentbench/models/anthropic_adapter.py`, tests | Prerequisite for every judged score in both suites; ships alone |
| C2 | `claim_checks.py`: responsiveness gate, antecedent basis (deterministic + advisory heuristic split), dependency graph, term support (with self-support exclusion for spec tasks), disclosure support screen, 112(f) flag, format, citation existence | `patentbench/claim_checks.py`, `tests/test_claim_checks.py` | Pure functions; parser limitations documented in module docstring, including the note that the 37 CFR 1.75 check rarely fires in modern practice |
| C3 | Ranking metrics + random-baseline computation | `patentbench/metrics.py`, `tests/test_ranking_metrics.py` | `precision_at_k, recall_at_k, average_precision, ndcg_at_k, x_hit_at_k`, per-class grade P/R/F1, and the random-ranking baseline as `MetricsCalculator` staticmethods |
| C4 | `DeterministicEvaluator` dispatch: `_check_reference_relevance`, `_check_anticipation`, `_check_claim_drafting` | `patentbench/evaluator.py` | Follows the existing `elif` dispatch pattern, including the parsing edge-case rules in 3.2 |
| C5 | Truth loader: accept `oa_source` lineage; register `REQUIRED_TRUTH_FIELDS` and `EXTRACTORS` for `anticipation_detection`; truth-field registration for `reference_relevance` | `patentbench/reports/ground_truth.py` | "Adding a task requires a test and attorney sign-off" policy applies |
| C6 | New artifact builders + verifiers: `build_ranking_report.py` / `verify_ranking.py`, `build_drafting_report.py` / `verify_drafting.py`, plus `verify_all.py` that globs `reports/**` and dispatches by artifact type | `patentbench/reports/` | Same discipline as `verify_confusion`: rebuild from source run + truth, compare every number, exit codes 0/1/2/3. `verify_drafting` also recomputes disclosure SHAs against `data/disclosures/manifest.json` and case metadata, and re-checks every probe-based quarantine decision from recorded probe outputs |
| C7 | CI: add an artifact-verification step running `python -m patentbench.reports.verify_all reports/` | `.github/workflows/ci.yml` | Closes an existing gap: committed artifacts are not currently re-verified in CI. Activates per artifact type as each verifier lands (with M2 at the earliest) |
| C8 | `TASK_REGISTRY`: add `anticipation_detection`, `combination_selection`, `claim_set_drafting`, `specification_support_drafting`; add `DETERMINISTIC` to `independent_claim_drafting` layers | `patentbench/config.py` | |
| C9 | README harmonization: Prior Art row "Search strategy, reference analysis, relevance ranking" becomes "Reference triage, reference analysis, relevance ranking" | `README.md` | The positioning decision, applied |
| C10 | INTEGRATION.md: add a "ranked-output contract" subsection documenting the fenced-JSON ranking format for commercial tools | `INTEGRATION.md` | |
| C11 | Memorization probe runner support: probe prompt per case, probe result recorded in run file, per-SUT quarantine application per `data/probe_protocol.json` | `patentbench/harness.py`, run file schema | Verifier re-checks quarantine decisions from recorded probe outputs |
| C12 | Case-file validator for the new suites: every case's `reference_answer` parses as JSON and carries the per-task required keys; runs in CI | `scripts/validate_cases.py` (or `patentbench/data_loader.py` `--validate` extension), `.github/workflows/ci.yml` | Added in review (E4): `TestCase.reference_answer` is an unvalidated string in the loader |

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
  sut_cutoffs.json                         # per-system training cutoffs (2.4)
  probe_protocol.json                      # memorization probe + quarantine thresholds (2.4)
  disclosures/
    manifest.json                          # id -> sha256 + lineage (D1..D4)
    disc_0001.md ...
  benchmark_cases/
    drafting_v1.jsonl
    prior_art_reference_relevance.jsonl
    prior_art_anticipation.jsonl
  ground_truth/
    independent_claim_drafting.json        # anchors + lineage
    reference_relevance.json               # graded pools + full member snapshots + lineage
    anticipation_detection.json
  rubrics/
    claim_drafting.json
    prior_art_analysis.json
  mini/
    mini_drafting_ids.json                 # frozen id lists + stratification recipe (section 7)
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
  validate_cases.py
tests/
  test_claim_checks.py
  test_ranking_metrics.py
  test_reports_ranking.py
  test_reports_drafting.py
```

Ranking artifact schema (per model): top-level `schema_version, model,
run_date, task_type, per_case[], aggregates{}, random_baseline{},
sensitivity{}, unparseable, unparseable_test_ids, quarantined,
quarantined_test_ids, total, source_run_file, source_sha256,
ground_truth_file, ground_truth_sha256, generated_at, verifier_version`.
Each `per_case` row carries `test_id`, the parsed ranking, predicted and
truth grades, `out_of_pool_ids` and the 3.2 edge-case flags, and every
per-case metric, so any aggregate is an arithmetic fold over visible rows.
`aggregates` includes the legacy-versus-frontier split and the
nDCG-versus-grade-F1 correlation; `sensitivity` holds the grade>=1 versus
grade>=2 binary-metric comparison. The drafting structural artifact
follows the same envelope with per-check rates, `non_responsive` flags,
`unsupported_limitations` traces, and per-model probe/quarantine counts.

---

## 6. CI and independent verification

Every published number is rebuildable from pinned sources, enforced in CI:

1. Builders construct artifacts in a single pass with inline invariant
   checks (the PR #6 discipline).
2. Every artifact bakes in `source_sha256` and `ground_truth_sha256`.
3. `verify_ranking` / `verify_drafting` / `verify_confusion` rebuild each
   artifact from the run file and truth file on disk and compare every cell,
   trace, metric, SHA, random-baseline value, and quarantine decision; exit
   1 arithmetic/trace drift, 2 SHA drift, 3 schema.
4. Verification never performs a network call: committed snapshots are the
   corpus of record (3.3 P4).
5. The new CI step runs `verify_all` over `reports/**` on every push and PR,
   so a drifted or hand-edited artifact cannot merge.
6. `.gitattributes` LF pinning extends to the new artifact paths.

---

## 7. Mini subsets

PatentBench-Mini is 300 of 7,200 (4.2%). Applied proportionally to the
page's target structure:

| Suite | Full target | Mini size | v1 interim |
|---|---|---|---|
| Drafting | 500 | 20 | 10 (frozen id list once M3 lands) |
| Prior Art | 1,200 | 50 | 50 (M2 ships 82 ranking + 82 anticipation cases; mini freezes 50 ids across both) |

Mini membership is a committed id list in `data/mini/`, never a runtime
sample, so mini runs are reproducible byte for byte. Stratification
(added in review, R2-7): mini ids are drawn proportionally across
task_type, pool (frontier/legacy/synthetic), technology center, and
positive-count band, and the stratification recipe is committed next to
the id list.

---

## 8. Phasing and milestones

| Milestone | Content | First verifiable published cell |
|---|---|---|
| M0 | Layer 2 wiring fix (C1) + tests. Code-only PR, no data | none (unblocks M3/M4) |
| M1 | `anticipation_detection`: 82 cases + `oa_source` truth + extractor + confusion matrix artifact for ABIGAIL v3 + verify in CI | **Prior Art cell 1**: anticipation label accuracy + full confusion matrix, verify_confusion green |
| M2 | `reference_relevance`: 82 pools (snapshot-committed) + ranking metrics + evaluator branch + ranking artifact + `verify_ranking` + CI step (C7) + `sut_cutoffs.json` + `probe_protocol.json` | Prior Art headline cells: nDCG@10 and X-Hit@3 (with coverage), frontier-only, random-baseline row published |
| M3 | Drafting structural: 10 frontier disclosures + `claim_checks.py` + structural artifact + `verify_drafting` | **Drafting cell 1**: structural COMPLIANCE rates (antecedent basis, dependency validity, term support), labeled as compliance, not quality |
| M4 | Drafting judged: `claim_drafting.json` rubric + M0 wiring + 30 cases (25 frontier + 5 synthetic) + memorization probes + Layer 4 calibration round 1 (2 attorneys minimum, scope_calibration Kappa gate) | Drafting 10-point score with "calibration round 1" annotation |
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
   in 2.4 (pool split, mechanical probe protocol, canaries,
   anchors-never-scored, anchor-blind judge). Residual: a model may have
   memorized the as-filed spec (same family as the disclosure) without the
   probe firing; the probe is one-sided by design. Accepted and disclosed;
   the synthetic pool is the long-term answer and needs attorney hours.
2. **Contamination (prior art).** Front-page citation lists are
   memorizable, and for legacy cases memorization largely solves the
   ranking task (stated plainly in 3.3). Frontier-only headlines, probe,
   and the published legacy-minus-frontier delta are the defenses; legacy
   numbers never feed headlines.
3. **Examiner citations as truth.** Examiners miss art and make
   idiosyncratic grading choices. The suite scores agreement with what the
   examiner did, which is the practice-relevant question for prosecution
   support, but it is a proxy. Mitigations: pool-restricted task framing,
   EPO cross-check annotation, the grade-threshold sensitivity block,
   Layer 4 blind re-grading with quarantine-on-disagreement.
4. **Distractor false negatives.** A "grade 0" distractor might genuinely
   anticipate. Mitigations: exclusion screens (892, IDS, family), temporal
   validity, attorney spot-validation, quarantine path. Residual risk
   stated in the artifact docs.
5. **No-single-answer scoring (drafting).** Addressed by the three-role
   split (inputs / anchors / scores), the similarity ban, the anchor-blind
   judge, and claim-chart-first judge prompting. Residual: judge
   preference bias toward verbose claim sets; mitigated by
   `claim_architecture` criteria, the responsiveness gate, the comparative
   layer, and calibration.
6. **Deterministic-layer gaming.** The responsiveness gate (2.5) closes
   the trivial-claim strategy; the published cell is labeled compliance,
   not quality. Residual: gate thresholds (word and limitation minimums)
   are coarse and will need tuning against real outputs in M3.
7. **Antecedent-basis parser precision.** Split into a scored exact
   portion and an advisory heuristic portion; disagreements between the
   checker and attorneys become test cases.
8. **Judge gaming and rubric drift.** Judge model pinned by version, judge
   prompts published, anchor withheld, targets withheld, rotation policy
   covers staleness; rubric changes bump `version` per the existing
   schema. The scope_calibration Kappa gate (2.5) blocks composite
   publication until the heaviest dimension is validated.
9. **PatSnap comparison misread.** X-Hit@k within a pool is not an open
   retrieval hit rate. Every surface that shows the number carries the
   one-line distinction and the coverage denominator.
10. **Attorney-hours bottleneck.** Synthetic disclosures, spot-validation,
    and calibration all draw on scarce practitioner time. The phasing
    front-loads everything that does not need it (M0 through M3).
11. **Public data versus held-out policy.** METHODOLOGY.md commits to a
    held-out set, but the repo currently publishes all committed cases.
    These suites follow current practice (publish + rotate). If a held-out
    split is wanted, it is a separate decision affecting all domains.
    **Open question for the operator.**
12. **Published baselines may not survive calibration.** The page's
    8.5/10 drafting and 85% prior art baselines are design targets, not
    measurements. Layer 4 round 1 arbitrates; if measured practitioner
    baselines land below the published figures, revising the page is an
    operator decision. **Open question for the operator.**
13. **Cutoff registry as trust boundary.** `data/sut_cutoffs.json` (2.4)
    depends on vendor cutoff claims that cannot be fully verified.
    Conservative resolution rules, PR-attested updates, and the
    legacy-frontier delta limit the damage of a wrong entry. **Needs
    operator sign-off because it commits us to tracking vendor cutoff
    claims.**
14. **Frontier anchor weakness.** Post-cutoff cases may lack granted
    claims; `anchor_status` records it and reporting stratifies by it. No
    score impact by design.

---

## 10. Review round record (Phase 2)

The drafted plan (commit ba98ebd) went through one fresh-context evaluator
pass (full-plan audit against the repo) and a four-reviewer council, each
reviewer fresh context with no write access: R1 contamination and
reproducibility (prior art), R2 IR evaluation methodology (prior art), R3
measurement validity and gaming (drafting), R4 practicing-prosecutor
realism (drafting). Dispositions:

| # | Finding (condensed) | Disposition | Change |
|---|---|---|---|
| E1 | Judge score keys hardcoded; rubric-driven keys impossible today | Accepted as clarification | Current-state defect list in section 1; C1 explicitly replaces prompt builder and parser |
| E2/E3/E8/E9/E11/E12 | Registry entries, truth fields, verifiers, data dirs, eligibility filter do not exist in the repo | Accepted as clarification (the doc is a plan) | Section 4 preamble states all C-items are new; 3.4 clarifies eligibility is enforced at case build time |
| E4 | `reference_answer` JSON contract unvalidated by loader | Accepted | New C12 case-file validator in CI |
| E5 | "source: llm/abigail ban declared but not enforced" | **Rejected**: enforcement exists in `load_ground_truth` (`ground_truth.py`, the explicit `GroundTruthInvalidError` raise on banned sources); the reviewer read only the module docstring | Section 1 row cites the enforcing function |
| E6 | Anti-hallucination multiplier not implemented in code (metric-only today) | Accepted | Folded into C1 scope and section 1 defect list |
| E7 | `prior_art_refs` versus truth-file pool ambiguity | Accepted | 3.2 marks the field informational; truth file authoritative |
| E10 | Disclosure sha256 not verifiable by any loader | Accepted | C6: verify_drafting cross-checks manifest, files, and case metadata |
| R1-1 | Pool restriction does not defeat citation-list memorization; probe threshold unspecified | Accepted | 3.3 overclaim removed and rewritten; probe protocol concretized (app number or 2+ reproduced citations; `data/probe_protocol.json`) |
| R1-2 | Grade-1 threshold choice hides sensitivity | Accepted | Sensitivity block (grade>=1 vs grade>=2) in every ranking artifact |
| R1-3 | Cutoff registry must be committed, attested, cadenced | Accepted | 2.4 cutoff registry subsection; still operator sign-off (9.13) |
| R1-4 | Distractor re-query is not reproducible (CPC/API drift) | Accepted | P4 rewritten: snapshot-authoritative committal; verification never re-queries (6.4) |
| R1-5 | Probe sandbagging (recognize and deny) | Accepted with reframing | Probe documented as one-sided; frontier pool named the binding control; legacy-minus-frontier delta published per model. R1's high-abstention flag rejected: abstention is the normal honest response for clean models |
| R1-6 | Antecedent checker false positives on functional phrasing | Accepted | Check split: scored exact part + advisory heuristic part |
| R1-7 | as_filed anchors unflagged | Accepted (modified) | Stratified reporting by anchor_status; judge note mooted by the anchor-blind judge |
| R1-8 | Publish ranking-vs-grading correlation | Accepted | 3.5 Layer 4 artifact addition |
| R2-1 | nDCG gain on grade 1 vs binary exclusion incoherent | Accepted as documentation | 3.3 states the rationale explicitly: graded and binary metrics answer different questions; sensitivity block makes it auditable |
| R2-2 | X-Hit denominator/coverage | Accepted (definition kept) | Coverage denominator published on every surface; redefinition to grade>=2 rejected (X-Hit is the anticipation analogue) |
| R2-3/R2-5 | Ranking parsing edge cases undefined | Accepted | 3.2 "Parsing edge cases" rules (duplicates, partial rankings, ties, missing grades) |
| R2-4 | Random baselines near targets for P@k; publish floors | Accepted (recommendation), arithmetic rejected | Random-baseline row computed and published per artifact; the reviewer's E[P@k] arithmetic divided average positives by k instead of using the R/N floor of a random ranking, overstating the floor; headline metrics unchanged (nDCG@10, X-Hit@3) with floors visible |
| R2-6 | grade_accuracy inflated by class imbalance | Accepted | Per-class P/R/F1 replaces accuracy; raw accuracy artifact-only |
| R2-7 | Mini stratification unstated | Accepted | Section 7 stratification recipe committed with id lists |
| R2-8 | C7 sequencing before verifiers exist | Accepted | C7 noted as activating per artifact type, M2 at the earliest |
| R3-1 | Deterministic layer trivially gameable (short copied claims) | Accepted | Responsiveness gate with substance floor; composite capped at 0.2 for non-responsive output; M3 cell relabeled "structural compliance" |
| R3-2 | Judge cannot verify scope/novelty from raw text | Accepted | Judge receives parsed element lists and must complete a mini claim chart before scoring those dimensions |
| R3-3 | scope_calibration 2.0x noise amplification | Accepted | Weight reduced to 1.5; per-dimension publication; scope-specific Kappa gate before composite publication |
| R3-4 / R4-2 | Anchor in judge context biases output (toward anchor-like and toward over-narrow) | Accepted | Judge is anchor-blind; anchor confined to Layer 4 + descriptive scope-delta reporting; Layer 4 instructions carry the post-amendment-narrowness note |
| R3-5 | 10-point mapping floor of 2.0 | Accepted | Remapped to `(weighted_mean - 1) * 2.5` (floor 0, ceiling 10) |
| R3-6 | specification_support_drafting self-support circularity | Accepted | Disclosure-only support for that task + 70% n-gram self-support exclusion |
| R3-7 | Probe quarantine changes effective case sets across models | Accepted (transparency option) | Per-model quarantine counts and effective n published; uniform removal across all systems rejected (one contaminated vendor would shrink the benchmark for everyone; rotation handles the long run) |
| R3-8 | Anti-hallucination multiplier target dimensions unspecified | Accepted | Applies to `support_112a`, `novelty_over_supplied_art`, `eligibility_101`; documented in 2.5 |
| R4-1 | Section 132 "new matter" framing legally wrong for greenfield drafting | Accepted | Check renamed `disclosure_support_screen`, reframed as grounding, statutory framing dropped |
| R4-3 | 8.5/10 tier 3 target incoherent with rubric severity | Accepted (modified) | Tier targets widened to provisional ranges; targets withheld from judge prompts; page-figure revision flagged as operator decision (9.12); the published page number is not changed by this document |
| R4-4 | Missing infringement-detectability dimension | Accepted | `infringement_architecture` (1.0) added to the rubric |
| R4-5 | Restriction-risk awareness missing | Accepted | Folded into `claim_architecture` criteria for multi-independent sets |
| R4-6 | eligibility_101 full weight everywhere adds noise | Accepted (TC mapping corrected) | Conditional weight: 1.0 for software/business-method centers (e.g. TC2100, TC3600), 0.25 elsewhere; the reviewer's TC grouping had software centers mislabeled |
| R4-7 | Input spec missing title, claim-count instructions, jurisdiction, continuation context | Accepted (partial) | Title + claim-count instructions + explicit US-only statement added (2.1/2.2); continuation context deliberately deferred to the Tier 5 task |
| R4-8 | 37 CFR 1.75 rarity docstring note | Accepted | C2 note |
| R4-9 | 112(f) means-plus-function risk unscored | Accepted | Deterministic advisory `mpf_flags` + explicit 112(f) language in `definiteness_112b` criteria |

Evaluator verdict on the draft was NEEDS-REWORK, driven mostly by reading
the build list as claims about current state; the substantive subset of
its findings (E4, E6, E7, E10) is folded in above. The council surfaced
the four changes that most altered the design: the anchor-blind judge, the
responsiveness gate, the snapshot-authoritative distractor committal, and
the honest restatement that pool restriction does not defeat citation-list
memorization (frontier-only headlines instead).
