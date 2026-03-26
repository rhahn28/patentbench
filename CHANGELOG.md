# Changelog

## [0.2.0] - 2026-03-22

### Breaking Changes
- Results schema rewritten. `BenchmarkResults.to_dict()` now produces a unified schema with `summary`, `scores`, `case_results`, and `metadata` sections. Old schema with flat `overall_score`/`domain_scores` is no longer produced.
- `BenchmarkConfig.concurrency` parameter removed. Execution is intentionally sequential for reproducibility.
- Benchmark version bumped from 0.1.0 to 0.2.0.

### Bug Fixes
- **Entity status detection**: Fixed false positive where "not a micro entity; they are a small entity" would incorrectly match "micro". Now uses negation-aware regex and supports JSON extraction.
- **Rejection type matching**: Fixed false positives where page numbers (e.g., "page 103") triggered rejection type detection. Now uses word-boundary regex and statutory citation patterns (`§103`, `35 U.S.C. 103`).
- **Empty case list handling**: `BenchmarkRunner` now correctly handles an explicitly empty case list instead of falling through to disk loading.

### New Features
- **LLM-Judge wiring**: `BenchmarkRunner` now invokes `LLMJudgeEvaluator` for cases with `LLM_JUDGE` evaluation layer when a judge client is provided.
- **Statistical methods**: Added `bootstrap_ci`, `wilcoxon_signed_rank`, `cohens_d`, and `bonferroni_correction` to `MetricsCalculator` — all methods previously claimed in METHODOLOGY.md but not implemented.
- **Enriched case results**: Each case result now includes `task_type`, `tier`, `domain`, `details`, and `latency_ms` for full traceability.
- **Multi-model support**: Claude Sonnet 4 results added to leaderboard. GPT-4o and Gemini adapters verified.

### Documentation
- Added conflict-of-interest disclosure to README leaderboard section.
- Fixed test case count claims (was "7,200", now accurately reflects available data).
- Updated Layer 2 status from "In progress" to "Live" with 25 Tier 3 cases.

### Tests
- Added 28 new tests: edge cases for entity status negation, rejection matching, bootstrap CI, Wilcoxon, Cohen's d, Bonferroni correction, BenchmarkRunner lifecycle, and BenchmarkResults serialization.
- Test coverage increased from 540 lines to ~1,100 lines (17.8% to ~33% ratio).

## [0.1.0] - 2026-03-19

- Initial release with 298 deterministic test cases.
- Layer 1 (Deterministic) evaluation live.
- ABIGAIL v3 results published.
