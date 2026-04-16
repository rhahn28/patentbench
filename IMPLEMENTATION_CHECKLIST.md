# PatentBench Implementation Checklist

> **Goal**: Ship the first reproducible, open benchmark for patent prosecution AI.
> **Timeline**: 12 weeks to v1.0 launch, 6 months to full scale.

---

## CODE TO ENABLE

Existing ABIGAIL code that maps directly to PatentBench needs:

| PatentBench Need | Existing Code | Notes |
|---|---|---|
| XML Office Action Parser | `backend/services/xml_office_action_parser.py` | Parses USPTO XML OA format into structured data. Production-tested on 10K+ OAs. |
| Evaluation Judges | `backend/services/evaluation/*.py` | LLM judge framework with rubric-based scoring. Needs calibration for benchmark use. |
| Benchmark API | `backend/orchestrator/routes/benchmark.py` | Route skeleton exists. Needs test-case runner endpoints. |
| USPTO Client | `backend/shared/clients/uspto_client.py` | PEDS API client for bulk OA download. Rate-limited, pagination implemented. |
| ROA Pipeline | `backend/services/openclaw/async_roa_drafter.py` | Response to Office Action drafting. Core prosecution evaluation target. |
| Expert Nodes | `backend/orchestrator/nodes/expert_*.py` | Domain-specific reasoning nodes (claims, prior art, prosecution). Reusable as evaluation subjects. |
| Document Parser | `backend/services/document_parser.py` | Multi-format document ingestion (PDF, DOCX, XML). Needed for test case input processing. |
| IDS Parser | `backend/services/ids_parser.py` | Information Disclosure Statement parser. Relevant for Admin domain test cases. |

---

## Phase 0: Foundation (Weeks 1-2)

### Code Tasks

- [ ] **P0** | Owner: `___` | Effort: 2h | Deps: None
 Initialize PatentBench repo structure:
  ```
  patentbench/
    bench/             # Core benchmark runner
    data/              # Test cases (gitignored, pulled from HF)
    judges/            # LLM judge configs and prompts
    rubrics/           # Scoring rubrics per domain/tier
    results/           # Output directory
    scripts/           # Data collection and processing
    frontend/          # Landing page (Next.js)
    tests/             # Unit and integration tests
  ```

- [ ] **P0** | Owner: `___` | Effort: 3h | Deps: Repo init
 Set up CI pipeline (GitHub Actions):
 - Lint (ruff, mypy)
 - Unit tests (pytest)
 - Rubric schema validation
 - Test case format validation
 Leverage: ABIGAIL `.github/workflows/` for patterns.

- [ ] **P0** | Owner: `___` | Effort: 4h | Deps: Repo init
 Create Python package structure (`pyproject.toml`, `bench/` module):
 - `bench/runner.py`, orchestrates evaluation runs
 - `bench/loader.py`, loads test cases from HuggingFace or local
 - `bench/scorer.py`, routes to appropriate judge per layer
 - `bench/reporter.py`, generates markdown/JSON result reports
 Leverage: `backend/services/evaluation/*.py` for judge patterns.

- [ ] **P1** | Owner: `___` | Effort: 2h | Deps: Package setup
 Create `bench/adapters/` for model interfaces:
 - `base.py`, abstract adapter class
 - `openai_adapter.py`. GPT-5 / GPT-4o
 - `anthropic_adapter.py`. Claude Sonnet
 - `google_adapter.py`. Gemini
 - `abigail_adapter.py`. ABIGAIL API
 Leverage: ABIGAIL LLM client patterns.

- [ ] **P1** | Owner: `___` | Effort: 2h | Deps: Repo init
 Set up pre-commit hooks: black, isort, ruff, JSON schema validation for test cases.

### Content Tasks

- [ ] **P0** | Owner: `___` | Effort: 6h | Deps: None
 Finalize landing page (`frontend/patentbench_page.tsx`). Wire up to Next.js app at `abigail.app/patentbench`. Connect email signup to Resend or similar.

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: None
 Write launch blog post: "Why We Built PatentBench" (1,500 words).
 Sections: The transparency problem, what we measure, Glass Box Standard, call to action.

- [ ] **P1** | Owner: `___` | Effort: 4h | Deps: None
 Write the PatentBench Manifesto (500 words). Published as `MANIFESTO.md` in repo and on landing page.

- [ ] **P1** | Owner: `___` | Effort: 3h | Deps: None
 Draft IPWatchdog guest article pitch (300 words). Target: publish week of launch.

### Infrastructure Tasks

- [ ] **P0** | Owner: `___` | Effort: 1h | Deps: None
 Create GitHub repo: `abigail-ai/patentbench`. Public, MIT license (code) + CC-BY-SA 4.0 (data).

- [ ] **P0** | Owner: `___` | Effort: 3h | Deps: Repo created
 Create HuggingFace dataset page: `abigail-ai/patentbench`.
 - Dataset card with full description
 - Splits: `train` (public), `test_held_out` (private)
 - Metadata: domain, tier, technology area tags

- [ ] **P1** | Owner: `___` | Effort: 2h | Deps: None
 Set up benchmark results hosting:
 - Static JSON files in repo (`results/latest.json`)
 - Frontend reads from this for leaderboard
 - GitHub Actions auto-updates on new result pushes

### Outreach Tasks

- [ ] **P0** | Owner: `___` | Effort: 4h | Deps: None
 Identify 15 patent attorneys for expert review panel:
 - 5 prosecution specialists (10+ years)
 - 3 drafting specialists
 - 3 prior art / IPR specialists
 - 4 general practice
 Target: BigLaw, boutique, in-house mix.

- [ ] **P0** | Owner: `___` | Effort: 2h | Deps: Attorney list
 Draft outreach email template for attorney reviewers. Include: what we're asking (2-4 hours/month), compensation (co-authorship + acknowledgment), timeline.

- [ ] **P1** | Owner: `___` | Effort: 2h | Deps: None
 Identify 5 academic groups working on legal AI (Stanford CodeX, MIT CSAIL, Georgetown ICLR). Draft collaboration emails.

---

## Phase 1: Data Collection (Weeks 3-6)

### USPTO Data Pull

- [ ] **P0** | Owner: `___` | Effort: 4h | Deps: Phase 0 code
 Pull 100 Office Actions from USPTO PEDS using existing client.
 Leverage: `backend/shared/clients/uspto_client.py`, already has pagination, rate limiting, and error handling.
 Target: 20 per technology area (software, mechanical, biotech, electrical, chemical).

- [ ] **P0** | Owner: `___` | Effort: 6h | Deps: OA pull
 Parse all 100 OAs using existing XML parser.
 Leverage: `backend/services/xml_office_action_parser.py`, extracts rejections, citations, claims, deadlines.
 Output: Structured JSON per OA with all extractable fields.

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: Parsed OAs
 Build supplementary dataset:
 - Pull corresponding patent applications (claims, spec) via USPTO Bulk Data
 - Pull cited prior art references
 - Pull prosecution history (all actions, amendments, responses)
 Leverage: `backend/shared/clients/uspto_client.py` for PEDS queries.

### Test Case Creation

- [ ] **P0** | Owner: `___` | Effort: 16h | Deps: Parsed OAs
 Create Tier 1 (Admin) test cases, 120 cases:
 - 40 deadline calculation (response deadline, extension fees, RCE timing)
 - 30 entity status detection (from filing data)
 - 25 fee schedule lookups (based on entity, action type, timing)
 - 25 docketing accuracy (next action, status tracking)
 Leverage: `backend/services/ids_parser.py` for IDS-related admin tasks.

- [ ] **P0** | Owner: `___` | Effort: 24h | Deps: Parsed OAs
 Create Tier 2-3 (Associate/Senior) test cases, 430 cases:
 - 100 claim amendment tasks (given rejection, propose amendment)
 - 80 prior art relevance ranking (given references, rank by relevance)
 - 80 rejection classification (102 vs 103 vs 112, identify type)
 - 70 argument drafting (given rejection + prior art, draft argument)
 - 50 IDS review (given reference list, identify material references)
 - 50 specification adequacy (does spec support proposed claims?)
 Leverage: `backend/services/openclaw/async_roa_drafter.py` for ROA task structure.

- [ ] **P1** | Owner: `___` | Effort: 16h | Deps: Parsed OAs
 Create Tier 4 (Counsel) test cases, 200 cases:
 - 60 multi-reference obviousness analysis
 - 50 claim construction disputes
 - 40 appeal brief arguments (PTAB-style)
 - 50 freedom-to-operate analysis
 Leverage: `backend/orchestrator/nodes/expert_*.py` for domain reasoning patterns.

- [ ] **P2** | Owner: `___` | Effort: 8h | Deps: Attorney panel
 Create Tier 5 (Partner) test cases, 50 cases:
 - 20 portfolio strategy recommendations
 - 15 IPR risk assessment
 - 15 licensing valuation analysis
 (Requires attorney co-creation, these can't be fully automated.)

### Rubric Development

- [ ] **P0** | Owner: `___` | Effort: 20h | Deps: Test cases created
 Build scoring rubrics for each domain:
 - Admin: binary correct/incorrect with partial credit rules
 - Drafting: 10-point scale (scope, enablement, definiteness, form)
 - Prosecution: 10-point scale (accuracy, persuasiveness, completeness)
 - Analytics: precision/recall + qualitative assessment
 - Prior Art: nDCG@10 + binary anticipation/obviousness detection
 Format: JSON schema per rubric type.

- [ ] **P0** | Owner: `___` | Effort: 12h | Deps: Rubrics, attorney panel
 Attorney rubric review (round 1):
 - Send rubrics to 3 attorneys per domain
 - Collect feedback, iterate
 - Target: 80%+ agreement on scoring criteria

- [ ] **P1** | Owner: `___` | Effort: 8h | Deps: Round 1 review
 Attorney rubric review (round 2):
 - Apply feedback from round 1
 - Final sign-off from at least 2 attorneys per domain

### Judge Calibration

- [ ] **P0** | Owner: `___` | Effort: 12h | Deps: Rubrics finalized
 Calibrate LLM judges against human experts:
 - Create 200 gold-standard graded responses (40 per domain)
 - Run Claude, GPT-5, Gemini as judges
 - Compute Cohen's kappa per judge per domain
 - Target: kappa >= 0.7 for all domain-judge pairs
 Leverage: `backend/services/evaluation/*.py` for existing judge framework.

- [ ] **P1** | Owner: `___` | Effort: 6h | Deps: Calibration data
 Build judge consensus mechanism:
 - 3-judge panel per evaluation
 - Majority vote for binary decisions
 - Median score for scalar assessments
 - Flag items with high disagreement for human review

---

## Phase 2: Evaluation Run (Weeks 6-9)

### Model Evaluation

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: Test cases, judges calibrated
 Run full benchmark on ABIGAIL v3:
 - All 800 test cases, all 5 domains, all 5 tiers
 - 3 runs per test case (temperature variation)
 - Capture raw outputs, judge scores, and metadata
 Leverage: `bench/runner.py` + `bench/adapters/abigail_adapter.py`

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: Test cases, judges calibrated
 Run full benchmark on Claude 3.5 Sonnet:
 - Same protocol as ABIGAIL run
 Leverage: `bench/adapters/anthropic_adapter.py`

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: Test cases, judges calibrated
 Run full benchmark on GPT-5:
 - Same protocol
 Leverage: `bench/adapters/openai_adapter.py`

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: Test cases, judges calibrated
 Run full benchmark on Gemini 2.5 Pro:
 - Same protocol
 Leverage: `bench/adapters/google_adapter.py`

- [ ] **P1** | Owner: `___` | Effort: 12h | Deps: Competitor access
 Run benchmark on competitor trial accounts (where available):
 - IPRally (prior art search tasks only)
 - Specifio (drafting tasks only)
 - Any vendor that grants API access
 Document: access method, any limitations, fairness adjustments.

### Human Expert Review

- [ ] **P0** | Owner: `___` | Effort: 16h | Deps: Model runs complete
 Human expert review of Tier 4-5 results:
 - 3 attorneys review each Tier 4-5 response
 - Score using same rubrics as LLM judges
 - Purpose: validate LLM judge accuracy on hardest tasks

- [ ] **P0** | Owner: `___` | Effort: 6h | Deps: Human review complete
 Compute inter-rater reliability:
 - Human-human kappa (baseline)
 - Human-LLM kappa (per judge model)
 - LLM-LLM kappa (cross-judge agreement)
 - Publish all reliability metrics in the paper

### Analysis

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: All runs complete
 Generate comprehensive results analysis:
 - Per-model, per-domain, per-tier score matrices
 - Statistical significance tests (paired bootstrap)
 - Error analysis: categorize failure modes
 - Correlation analysis: domain scores vs. tier difficulty

- [ ] **P1** | Owner: `___` | Effort: 4h | Deps: Analysis complete
 Create visualizations:
 - Radar charts (model x domain)
 - Difficulty curve (tier x score, per model)
 - Confusion matrices for classification tasks
 - Score distributions (violin plots)

---

## Phase 3: Publication Blitz (Weeks 9-12)

### Paper

- [ ] **P0** | Owner: `___` | Effort: 40h | Deps: Analysis complete
 Write arXiv paper (target: 12-15 pages):
 - Abstract, Introduction, Related Work
 - Benchmark Design (domains, tiers, Glass Box Standard)
 - Methodology (data collection, rubric development, judge calibration)
 - Results (tables, figures, error analysis)
 - Discussion (limitations, what surprised us, implications)
 - Conclusion and Future Work
 Target: submit within 1 week of data freeze.

- [ ] **P0** | Owner: `___` | Effort: 4h | Deps: Paper draft
 Internal review of paper (2 reviewers, 48h turnaround).

- [ ] **P0** | Owner: `___` | Effort: 2h | Deps: Review complete
 Submit to arXiv (cs.CL + cs.AI cross-list).

### Data Release

- [ ] **P0** | Owner: `___` | Effort: 4h | Deps: Paper submitted
 Upload final dataset to HuggingFace:
 - Public split: 600 test cases with rubrics and gold answers
 - Held-out split: 200 test cases (private, for contamination checks)
 - Metadata: domain, tier, technology area, difficulty annotations

- [ ] **P0** | Owner: `___` | Effort: 2h | Deps: HF upload
 Tag GitHub repo release: `v1.0.0`
 - Include benchmark runner, all configs, result reproduction instructions
 - Docker image for one-command benchmark run

### Content Blitz

- [ ] **P0** | Owner: `___` | Effort: 6h | Deps: Paper submitted
 Publish launch blog post on abigail.app/blog.

- [ ] **P0** | Owner: `___` | Effort: 8h | Deps: Blog published
 LinkedIn series (5 posts over 2 weeks):
 1. "We spent 12 weeks benchmarking every patent AI. Here's what we found."
 2. "The transparency vacuum in patent AI" (The Problem)
 3. "Where AI falls off: Tier 3 and the prosecution cliff"
 4. "How we built incorruptible scoring" (Glass Box Standard)
 5. "An open challenge to every patent AI vendor"

- [ ] **P0** | Owner: `___` | Effort: 4h | Deps: Blog published
 Submit IPWatchdog article (1,200 words, practitioner-focused).

- [ ] **P1** | Owner: `___` | Effort: 3h | Deps: Blog published
 Reddit posts:
 - r/patentlaw, practitioner angle
 - r/MachineLearning, benchmark methodology angle
 - r/artificial, general AI angle

- [ ] **P1** | Owner: `___` | Effort: 4h | Deps: Results finalized
 Public challenge announcement:
 "We'll benchmark any patent AI system for free. Submit your API endpoint."
 Publish on: GitHub, LinkedIn, Twitter, blog.

- [ ] **P1** | Owner: `___` | Effort: 4h | Deps: Frontend, results JSON
 Launch live leaderboard on abigail.app/patentbench:
 - Wire frontend to `results/latest.json`
 - Add "Last updated" timestamp
 - Add "Submit your system" CTA

---

## Phase 4: Expansion (Months 3-6)

### Scale

- [ ] **P1** | Owner: `___` | Effort: 40h | Deps: v1.0 launched
 Scale to 7,200 test cases:
 - Pull 1,000 additional OAs from USPTO PEDS
 - Expand technology area coverage (add design patents, plant patents)
 - Add multi-turn evaluation (full prosecution history replay)
 Leverage: `backend/shared/clients/uspto_client.py` for bulk pull.

- [ ] **P1** | Owner: `___` | Effort: 20h | Deps: Tier 5 attorney input
 Expand Tier 5 (Partner-Level) tasks to 200:
 - Portfolio optimization across 50+ patent families
 - M&A due diligence patent review
 - Standard-essential patent (SEP) analysis
 - Multi-jurisdiction prosecution strategy

- [ ] **P2** | Owner: `___` | Effort: 8h | Deps: v1.0 infrastructure
 Establish monthly update cadence:
 - 50 new test cases per month
 - Re-run all models on updated set
 - Publish changelog and updated leaderboard
 - Retire stale/contaminated test cases

### Academic

- [ ] **P1** | Owner: `___` | Effort: 20h | Deps: arXiv paper, 6 months of data
 NeurIPS 2026 Datasets & Benchmarks track submission:
 - Extended paper with 6 months of longitudinal data
 - Include contamination analysis (score drift over time)
 - Include multi-turn evaluation results
 Deadline: typically May-June for December conference.

- [ ] **P2** | Owner: `___` | Effort: 8h | Deps: Academic contacts
 Establish academic partnerships:
 - Stanford CodeX: co-develop Tier 5 tasks
 - Georgetown ICLR: legal AI evaluation methodology
 - MIT CSAIL: benchmark infrastructure and tooling

- [ ] **P2** | Owner: `___` | Effort: 4h | Deps: v1.0 launched
 Submit to benchmark aggregators:
 - Papers With Code
 - HELM (Stanford)
 - Open LLM Leaderboard (HuggingFace)

### Community

- [ ] **P2** | Owner: `___` | Effort: 6h | Deps: v1.0 launched
 Create contributor guide:
 - How to submit test cases
 - Test case format specification
 - Rubric authoring guide
 - Review process documentation

- [ ] **P2** | Owner: `___` | Effort: 4h | Deps: Contributor guide
 Set up community infrastructure:
 - GitHub Discussions for proposals
 - Monthly community call (first Tuesday)
 - Discord or Slack channel for contributors

---

## Summary

| Phase | Duration | Key Deliverable | Test Cases |
|---|---|---|---|
| Phase 0 | Weeks 1-2 | Repo, CI, landing page, attorney outreach | 0 |
| Phase 1 | Weeks 3-6 | 800 test cases, calibrated judges | 800 |
| Phase 2 | Weeks 6-9 | Full evaluation run, human validation | 800 |
| Phase 3 | Weeks 9-12 | arXiv paper, HuggingFace dataset, launch blitz | 800 |
| Phase 4 | Months 3-6 | Scale to 7,200, NeurIPS submission | 7,200 |

**Total estimated effort**: ~400 engineering hours + ~80 attorney hours
**Critical path**: Attorney panel recruitment (Phase 0) -> Rubric validation (Phase 1) -> Paper submission (Phase 3)
