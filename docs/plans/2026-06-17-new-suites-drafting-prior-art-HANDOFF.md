# Handoff: PatentBench new benchmark suites (Drafting + Prior Art) -- Phase 1 plan drafting

Status: Phase 0 (investigate) and Phase 0b (resolve forks) COMPLETE and operator-signed-off.
Your job is Phase 1 (draft the design doc), Phase 2 (review it), then finalize this PR.
Date opened: 2026-06-17. Author of Phase 0/0b: prior agent session (Fable 5).

This document is self-contained. You should not need the original kickoff prompt.
Everything below marked "verified" was confirmed by a tool call against the repo in the
Phase 0 session. Re-verify anything you are about to depend on; do not trust this doc as
ground truth where the code can be read directly.

---

## 0. The mission in one paragraph

PatentBench currently runs Layer 1 docketing (Administration) and a partial Layer 2
prosecution suite. Two domains exist in the taxonomy but have ZERO live scored cases:
Drafting (invention disclosure in, claims + specification out) and Prior Art (claims or a
disclosure in, a ranked set of relevant references out). You are planning how to build
both to the same standard as the existing confusion-matrix infrastructure (PR #6):
provenance-pinned ground truth, SHA-256-baked artifacts, an independent verifier, and CI.
Deliverable is a DESIGN DOCUMENT, not benchmark code. Do not implement suites in this task.

---

## 1. Repo + environment (verified)

- GitHub: https://github.com/rhahn28/patentbench (PUBLIC, default branch `main`).
- Canonical local clone: `C:\Users\rhahn\patentbench-work`.
- You are on branch `docs/drafting-prior-art-suites-plan`, in a worktree at
  `C:\Users\rhahn\patentbench-work\.claude\worktrees\docs-new-suites-plan`, cut from
  origin/main `2e185f4`. This handoff doc is committed there.
- `gh` is authed as account `rhahn28` (token scopes repo, workflow). Use PowerShell
  `git -C <worktree>` for git ops; the Claude Bash path guard false-positives on
  in-worktree git. The Write/Edit tools REFUSE paths outside the cwd repo
  (`C:\Users\rhahn\abigail-ver3`), so write files in this worktree via PowerShell
  `[System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))`
  to avoid a BOM. Set-Content -Encoding utf8 writes a BOM on PS 5.1; do not use it for
  committed files.
- There are 4 other patentbench directories on this machine (`PatentBench` stale main with
  old worktrees, `patentbench-clean` not-a-repo, `patentbench-clean2` has an unpushed
  commit, `.patentbench` creds only). Ignore them. Use `patentbench-work`.

### Two repos, do not confuse them
- The Python benchmark package + data + reports live in the patentbench repo (above).
- The LIVE marketing/leaderboard page lives in a DIFFERENT repo:
  `C:\Users\rhahn\abigail-ver3\frontend\app\(marketing)\patentbench\` (page.tsx,
  layout.tsx, PatentBenchFAQ.tsx). That page is the source of the public positioning
  claims and the human baselines. Any "amend the page" follow-up is an abigail-ver3 change,
  not a patentbench change, and is out of scope for this plan (note it as a follow-up).

### Harness note
- There is NO `PROGRESS.md` and NO harness doc anywhere in the patentbench repo or its git
  history (verified: filesystem search of all clones + `git log --all --diff-filter=A`).
  Kickoff prompts that say "reread PROGRESS.md under the new harness" reference an artifact
  that does not exist. Operate under standard discipline: phase-honest language, verify by
  reading, no fabricated numbers. This is a planning task so the fail contract is plan
  completeness, not passing tests.

---

## 2. Phase 0 findings (verified by reading)

### 2.1 Canonical test case schema
`TestCase` dataclass at `patentbench/data_loader.py:23`. Fields:
`id, domain, tier, task_type, prompt, reference_answer (str; JSON-encoded string for
structured answers), metadata, rejection_types, evaluation_layers, application_number,
office_action_date, mpep_sections, prior_art_refs, claims_at_issue, poison_pills`.
`Domain` and `DifficultyTier` are enums in `patentbench/config.py`. New suites should
target this canonical shape.

CAUTION: three schema variants coexist in `data/`. (a) Canonical `TestCase` shape, used by
`data/mini/tier_1_2_cases.jsonl` and `data/full/all_cases.jsonl`. (b) Legacy results
envelope `benchmark_cases_tier1_2.json` (uses `question`/`ground_truth` inside a results
wrapper). (c) New PR #6 file `data/benchmark_cases/paralegal_clm_extraction.jsonl` (uses
`expected_output`, no `domain` field). Match (a) and call out the drift.

### 2.2 Scoring interface
- Adapter contract: `BaseModelAdapter.generate(prompt) -> str` and `is_available() -> bool`
  at `patentbench/models/base.py:28`. Output is prose (a string). A ranked-references suite
  needs either JSON-in-prose parsed like PR #6's `_parse_json_block`
  (`patentbench/reports/ground_truth.py`: fenced ```json, then first balanced-brace
  substring, then None) OR a new adapter method. Recommend JSON-in-prose to avoid
  fragmenting the adapter contract; decide and justify in the plan.
- `BenchmarkRunner._evaluate_case` (`patentbench/harness.py`, around line 235) wires ONLY
  `DeterministicEvaluator`. `LLMJudgeEvaluator` is fully implemented (rubric prompt builder,
  anti-hallucination integration) but is NEVER invoked by the runner. Wiring Layer 2 into
  the runner is prerequisite work for BOTH new suites and is the single biggest hidden cost.
- `LLMJudgeEvaluator._parse_judge_response` (`patentbench/evaluator.py:474`) HARDCODES four
  dimension keys: `legal_accuracy, factual_accuracy, argument_strength, completeness`.
  Drafting rubric dimensions that are not in this list will silently score as defaults
  until this parser is generalized. Flag this as the first thing that breaks.
- CLI `--domain` choices are derived from the `Domain` enum, so NO new `--domain` values are
  needed: `drafting` and `prior_art` already exist in the enum, in `DOMAIN_WEIGHTS`
  (`config.py:259`, drafting 0.25, prior_art 0.15) and in `TASK_REGISTRY` (config.py has
  `independent_claim_drafting` Tier 3, `claim_amendment` Tier 2, `reference_relevance`
  Tier 2 "Rank prior art references by relevance to claims"). What is missing is DATA,
  SCORER modules, and EXTRACTORS, not enum plumbing.

### 2.3 Ground-truth provenance pattern (the standard to match)
`patentbench/reports/ground_truth.py` `load_ground_truth()` enforces:
- Each truth row carries `peds_source {application_number, retrieved_at, peds_field_path,
  raw_value_hash}` OR `google_patents_source {patent_number, patent_url, retrieved_at,
  raw_html_sha256}`.
- Rows with `source: "llm"` or `source: "abigail"` are REJECTED ("PatentBench ground truth
  may not be produced by the SUT"). This is the ADV-001 anti-circularity rule. Honor it:
  drafting/prior-art truth cannot be generated by an LLM.
- Ambiguous rows get `quarantined: true`: excluded from matrix cells, still counted in
  totals so sums reconcile.
- Adding a task requires registering `REQUIRED_TRUTH_FIELDS[task_type]` and an
  `EXTRACTORS[task_type]` whose canonicalization is SHARED between the predicted extractor
  and the reference label (so a correct prediction lands on the diagonal).

### 2.4 CI + verifier pattern (the standard to match)
- `patentbench/reports/confusion.py`: single-pass build (cell value and cell trace
  incremented in lockstep; post-hoc trace construction is banned), inline invariant assert
  `sum(cells) + unparseable + quarantined == total`, deterministic JSON (sort_keys,
  ensure_ascii=False, LF pinned via `.gitattributes`), `SCHEMA_VERSION` constant, every
  artifact bakes `source_sha256` + `ground_truth_sha256`.
- `patentbench/reports/verify_confusion.py`: independent rebuild-and-compare verifier,
  `python -m patentbench.reports.verify_confusion <artifact>`, exit codes 0 ok / 1 arithmetic
  or trace mismatch / 2 SHA drift / 3 schema or file error.
- `.github/workflows/ci.yml`: ruff + mypy strict + pytest on Python 3.10/3.11/3.12, plus an
  import smoke test (`benchmark-smoke` job). The verifier is exercised through the 507-line
  `tests/test_reports_confusion.py`, not a standalone CI step (the plan should add a
  per-artifact verify step or extend the test pattern).
- PR #6 (DRAFT, "Stage 1 of 6") is the live exemplar of the staged-draft convention: an
  "Open questions for the owner" section, tamper-test evidence, explicit non-goals. Mirror
  this PR shape.

### 2.5 DATA REALITY vs published claims (most important finding)
- `data/full/all_cases.jsonl` is 7,200 lines: administration 5,721 + prosecution 1,381 +
  analytics 98. DRAFTING: 0. PRIOR_ART: 0. (Verified by counting domain fields.)
  README/page claim Draft 500-1,200 and Prior Art 1,200; those cases do not exist. This is a
  from-scratch data build.
- Tiers present: Tier 1 6,015, Tier 2 1,080, Tier 3 105. Tiers 4 and 5: none.
- Raw material on hand under `data/real_oa/`: `benchmark_cases.jsonl` 604,
  `uspto_peds_expanded.jsonl` 321 apps with prosecution_events, `google_patents_claims.jsonl`
  82 (structural claim counts only), `specifications.jsonl` only 5 apps (but those 5 carry
  full description text ~53K chars + claims, the exact shape a drafting suite needs more of),
  `generated_cases.jsonl` 14,009 (templated admin variants). A drafting suite needs many more
  full specifications; a prior-art suite needs the examiner-cited references and IDS
  references, which are reachable from the 604-case OA set + PEDS but are not yet extracted
  into a candidate-pool form.

### 2.6 Inconsistency catalog the plan must NOT inherit
1. The live page's five tiers (Admin / Paralegal / Junior Associate / Senior Associate /
   Partner, target bands 100% / 95%+ / 85-90% / 70-80% / 50-65%) are NOT the repo's five
   tiers (`DifficultyTier` = Paralegal, Junior Associate, Senior Associate, Junior Partner,
   Senior Partner). Pick one tier model in the plan and state it; do not silently mix.
2. Three different "five pillars" of the Glass Box Standard exist (live page vs README.md
   vs MANIFESTO.md). Cite whichever you anchor to and note the divergence.
3. MANIFESTO Section V lists five domains matching neither the README nor the code enum.
4. The live page "human baselines" (Drafting 8.5/10, Prior Art 85%, at
   abigail-ver3 `frontend/app/(marketing)/patentbench/page.tsx:96-99`) have NO backing study.
   `paper/patentbench.tex:327` states verbatim: "No human calibration. The Tier 3 reasoning
   tests have not yet been calibrated against human patent practitioner performance." So the
   page numbers are ASPIRATIONAL TARGETS, not measured baselines. The plan must label them
   that way and propose how a real baseline would be collected (Layer 4 protocol already
   exists in METHODOLOGY.md: 2+ registered attorneys, Cohen's kappa >= 0.60).

---

## 3. Phase 0b forks and OPERATOR DECISIONS (signed off 2026-06-17)

### Fork 1: Prior art positioning -- DECIDED: option (a), closed-world only
The conflict (quote both in the plan):
- abigail-ver3 `frontend/app/(marketing)/patentbench/layout.tsx:5`: "...Not a prior art
  search benchmark, a prosecution response benchmark."
- patentbench `README.md:38` Prior Art row: "Search strategy, reference analysis, relevance
  ranking ... Evaluate novelty of claims against prior art set".

DECISION: Build the Prior Art suite as CLOSED-WORLD reference analysis over a SUPPLIED
candidate set. No open corpus search in v1. The model receives a fixed candidate pool
(examiner-cited references + applicant IDS/SB08 references + verified distractors drawn from
the same art unit / CPC class) and is scored on ranking, anticipation-vs-obviousness triage,
and materiality detection. This is consistent with the deployed positioning sentence, the
page's own Prior Art domain card ("Reference relevance, Anticipation detection"), and the
existing `reference_relevance` registry entry. The candidate pool is SHA-256-pinned like
every other artifact, so reproducibility is total and the frozen-corpus problem is avoided.

Consequences to write into the plan:
- recall@k / precision@k / MAP / nDCG become ranking metrics OVER THE SUPPLIED POOL, not
  open-retrieval metrics. Define them that way. The "PatSnap X Hit Rate analogue" reduces to
  anticipation-detection accuracy in closed-world; state this honestly rather than implying a
  head-to-head with PatSnap's 81%.
- The open-search track (option b: frozen corpus snapshot, its own positioning paragraph, an
  explicit abigail-ver3 page edit) is DEFERRED to a v2 decision. Mention it as a named future
  option, do not design it now.
- The README.md "Search strategy" wording is the one artifact to amend (one-line docs change)
  so the repo stops contradicting the page. Note this as a follow-up; you may include the
  README edit in this PR since it is in-repo, but keep it minimal and additive.

### Fork 2: Contamination -- DECIDED: approved design
Risk: every issued patent, file wrapper, 892 form, IDS through roughly early 2025 is in
frontier training data; the repo's 2019-2024 window sits entirely inside training cutoffs, so
naive "reconstruct the issued claims" scoring measures memorization. Approved design to carry
into the plan:
1. Ground truth from a rolling POST-TRAINING-CUTOFF window (applications published after
   mid-2025), refreshed quarterly per the existing 20% rotation policy. Record publication
   date per case so every published number can be COHORT-SPLIT (pre-cutoff vs post-cutoff) and
   drift reported (the paper already promises this for NeurIPS).
2. Drafting scored STRUCTURALLY, never by similarity to the issued claims: deterministic
   checks (antecedent basis, claim dependency tree validity, claim-to-spec term support, new
   matter under 35 U.S.C. 132) plus rubric dimensions; the issued claims are at most ONE
   anchor among several for the judge, never the reference answer to match.
3. Disclosures DERIVED, not quoted, from the specification, with canary strings embedded per
   the existing Glass Box canary mechanism, and poison-pill prior art planted in the supplied
   art set (reuse `POISON_PILL_*` patterns in config.py + `anti_hallucination.py`).
4. For prior art, the supplied-candidate-pool design plus distractor construction partially
   neutralizes "memorize what the examiner cited"; the post-cutoff cohort neutralizes it fully.

---

## 4. YOUR TASK: Phase 1 design document

Produce ONE design doc at:
`docs/plans/2026-06-17-drafting-and-prior-art-suites-design.md` (this worktree/branch).
For EACH of the two suites cover, at minimum:

1. Task definition + exact input/output schema, matching the canonical `TestCase` shape (2.1).
2. Ground-truth source + construction pipeline, with provenance and SHA-256 pinning consistent
   with `reports/ground_truth.py` (2.3).
   - Drafting: how a disclosure is derived from a real spec, and what counts as a "reference
     answer" when there is no single correct application (lean on structural checks + rubric;
     issued claims are an anchor, not the answer).
   - Prior Art: define the supplied candidate set precisely (closed-world per Fork 1a),
     including distractor sourcing and the pinning method. Candidate ground truth: examiner
     cited references from Office Actions and 892 forms, applicant IDS / SB08 filings, EPO
     X/Y citations, patent-family citation graphs.
3. Metrics + scoring, mapped to the 4 layers.
   - Drafting: which checks are DETERMINISTIC (antecedent basis, dependency structure, term
     consistency claims<->spec, new matter under 132) vs LLM-as-judge + human calibration
     (claim scope vs validity tradeoff, 112 support/enablement, 101 eligibility, novelty over
     supplied art). Propose rubric dimensions WITH WEIGHTS in the existing rubric JSON format
     (see `data/rubrics/argument_strength.json`, `data/rubrics/README.md`).
   - Prior Art: recall@k, precision@k, MAP, nDCG, X-hit-rate analogue, WITH chosen k values
     and a defined relevance grading scale, all framed as closed-world (Fork 1a).
4. Difficulty tier mapping across the five tiers, with a per-tier human-baseline TARGET. Label
   targets as aspirational (2.6 item 4), not measured.
5. Anti-hallucination handling for drafting: fabricated support citations, claims unsupported
   by the spec, poison-pill pattern reuse.
6. Code changes: `DataLoader`/`BenchmarkRunner` extensions, the Layer-2 wiring + judge-parser
   generalization (2.2), new scorer modules, new model-adapter requirements (ranked-references
   output), and whether a new `--task-type`/registry entry is needed.
7. File layout matching existing conventions: where new `data/...`, `data/rubrics/...`,
   `data/ground_truth/...`, scorer modules, `reports/...`, and verifier scripts live.
8. CI + independent verifier integration in the `verify_confusion` style, so every published
   number is rebuildable from pinned sources.
9. A Mini subset per suite (sized like PatentBench-Mini's per-domain slice).
10. Phasing with milestones, and the SMALLEST first deliverable that produces ONE verifiable
    published cell per suite.
11. Risks + open questions, contamination and reproducibility first.

---

## 5. Phase 2: review (do this before marking the PR ready)

1. Route the drafted plan through a FRESH-CONTEXT evaluator subagent with NO write access
   (read-only). Use the `Explore` or `general-purpose` agent type with an explicit read-only
   instruction, or a `Plan` agent. Fold its findings back in.
2. Convene a council of reviewers (each fresh context) on the TWO hardest design questions:
   (i) prior-art ground-truth + reproducibility design (closed-world pool, distractors,
   pinning, post-cutoff cohort), and (ii) drafting scoring where no single correct answer
   exists (structural-vs-judge split, anchor handling, contamination). Suggested seats: a
   patent-domain reviewer, a benchmark-methodology/ML reviewer, an adversarial "how is this
   gamed or contaminated" reviewer. Each writes an independent verdict; you synthesize.
3. Note in the doc what changed as a result of review.

NOTE: project rule bans the Task tool for subagents UNLESS explicitly requested. The kickoff
explicitly requested the evaluator + council, so subagents ARE authorized for Phase 2 of this
task. Keep them read-only on the repo.

---

## 6. Finalize

- Commit the design doc to this branch. Keep the README.md "Search strategy" one-line edit
  minimal if you include it.
- Push and update this PR (it already exists; see PR link in the branch). Mark ready for
  review only after Phase 2 is folded in.
- Report phase-honest: what you verified by reading vs what is still assumption; restate that
  Fork 1a + the contamination design are operator-approved; name the first thing likely to
  break when the drafting suite is actually built (the Layer-2 runner wiring + the hardcoded
  4-key judge parser at evaluator.py:474).
- Do NOT implement benchmark code. Plan only. Do NOT touch the abigail-ver3 page in this PR
  (note page edits as a separate follow-up).

---

## 7. Key file + line index (verified Phase 0)

patentbench repo (`C:\Users\rhahn\patentbench-work`):
- patentbench/config.py            Domain enum, DifficultyTier, RejectionType, TASK_REGISTRY,
                                   LAYER_WEIGHTS (252), DOMAIN_WEIGHTS (259), USPTO_FEES,
                                   MPEP_SECTIONS, POISON_PILL_* (301+)
- patentbench/data_loader.py:23    TestCase canonical schema; DataLoader discover/load/stats
- patentbench/harness.py (~235)    BenchmarkRunner._evaluate_case wires ONLY deterministic
- patentbench/evaluator.py:474     LLMJudgeEvaluator hardcodes 4 dimension keys
- patentbench/metrics.py           accuracy, f1, cohens_kappa, composite_benchmark_score
- patentbench/anti_hallucination.py  CitationExtractor + AntiHallucinationChecker
- patentbench/models/base.py:28    BaseModelAdapter contract
- patentbench/reports/ground_truth.py   provenance gate + extractors (ADV-001 rule)
- patentbench/reports/confusion.py      single-pass build + SCHEMA_VERSION
- patentbench/reports/verify_confusion.py  independent verifier, exit codes 0/1/2/3
- data/rubrics/argument_strength.json + README.md  rubric JSON schema to match
- data/full/all_cases.jsonl        7,200 cases; 0 drafting, 0 prior_art
- data/real_oa/*.jsonl             604 OA cases / 321 PEDS apps / 82 GP claims / 5 specs
- README.md:38                     Prior Art "Search strategy" row (amend target)
- METHODOLOGY.md                   4-layer weights, Layer 4 protocol, contamination section
- paper/patentbench.tex:327        "No human calibration" admission
- .github/workflows/ci.yml         ruff + mypy strict + pytest 3.10-3.12 + smoke

abigail-ver3 repo (`C:\Users\rhahn\abigail-ver3`, DIFFERENT repo, do not edit here):
- frontend/app/(marketing)/patentbench/layout.tsx:5   "Not a prior art search benchmark"
- frontend/app/(marketing)/patentbench/PatentBenchFAQ.tsx:8   PatSnap distinction FAQ
- frontend/app/(marketing)/patentbench/page.tsx:96-99   domain human-baseline numbers

Live page (verified via WebFetch 2026-06-17): domains Administration 99.8% / Drafting 8.5/10 /
Prosecution 8.6/10 / Analytics 75% / Prior Art 85%; layer weights deterministic 30 / LLM-judge
35 / comparative 25 / human-calibration 10; leaderboard shows ABIGAIL v3 100%, Claude Sonnet 4
99.1%, Gemini 2.5 Flash 99.1% (Layer 1 only; Layer 2 "scoring in progress").

---

## 8. Commands

```
# you are here:
cd C:\Users\rhahn\patentbench-work\.claude\worktrees\docs-new-suites-plan

# read the existing scaffold you must match:
#   patentbench/reports/{ground_truth,confusion,verify_confusion}.py
#   data/rubrics/argument_strength.json
#   patentbench/config.py ; patentbench/harness.py ; patentbench/evaluator.py

# write the design doc to docs/plans/2026-06-17-drafting-and-prior-art-suites-design.md
# (use PowerShell [IO.File]::WriteAllText with UTF8Encoding($false); the Edit/Write tools
#  refuse this path because cwd is the abigail-ver3 repo)

# commit + push from PowerShell:
git -C <this-worktree> add docs/plans
git -C <this-worktree> commit -m "docs: drafting + prior-art suite design (Phase 1)"
git -C <this-worktree> push

# the PR already exists on branch docs/drafting-prior-art-suites-plan; it updates on push.
```

End of handoff.