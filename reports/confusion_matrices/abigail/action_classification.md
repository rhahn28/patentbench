# Confusion Matrix — ABIGAIL v3 (Variant B) — action_classification

- Run date: `2026-03-21T04:26:26.591Z`
- Total cases: `82`
- Unparseable: `0`
- Quarantined: `0`
- Source run file: `data\benchmark_results_sonnet.json`
- Source SHA-256: `5920174466f3e2b8848dc8472f820f135479fdaf8f266563f26f6e8f58e34fe0`
- Ground truth file: `data\ground_truth\action_classification.json`
- Ground truth SHA-256: `346acbe7427f2c3ee071c50945d3d5e1001400c5a83f81254646e0948aaee40f`
- Schema version: `1`
- Verifier version: `1.0.0`
- Generated at: `2026-04-20T11:17:07+00:00`

## Axis convention

- Rows: **ground truth** (what the USPTO PEDS record or verified truth says).
- Cols: **predicted** (what the system under test emitted).
- Cell `[row=A, col=B]` counts the cases where truth was A and the model predicted B.

## Matrix

| truth \ predicted | `NF0-F0-A0` | `NF1-F0-A0` | `NF1-F0-A1` | `NF1-F1-A0` | `NF1-F1-A1` |
|---|---|---|---|---|---|
| `NF0-F0-A0` | **1** | 0 | 0 | 0 | 0 |
| `NF1-F0-A0` | 0 | **30** | 0 | 0 | 0 |
| `NF1-F0-A1` | 0 | 0 | **7** | 0 | 0 |
| `NF1-F1-A0` | 0 | 0 | 0 | **33** | 0 |
| `NF1-F1-A1` | 0 | 0 | 0 | 0 | **11** |

## Per-class precision, recall, F1

| label | support | TP | FP | FN | precision | recall | F1 | hallucinated |
|---|---|---|---|---|---|---|---|---|
| `NF0-F0-A0` | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 | no |
| `NF1-F0-A0` | 30 | 30 | 0 | 0 | 1.000 | 1.000 | 1.000 | no |
| `NF1-F0-A1` | 7 | 7 | 0 | 0 | 1.000 | 1.000 | 1.000 | no |
| `NF1-F1-A0` | 33 | 33 | 0 | 0 | 1.000 | 1.000 | 1.000 | no |
| `NF1-F1-A1` | 11 | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | no |

## Off-diagonal traces


## Verification

This artifact can be verified by: `python -m patentbench.reports.verify_confusion reports\confusion_matrices\abigail\action_classification.json`
