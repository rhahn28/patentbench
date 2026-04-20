"""Reporting package for PatentBench.

Builds confusion matrices and per-class precision/recall from benchmark run
JSON, using externally-verified ground truth (never LLM-as-labeler). Every
cell is traceable to specific test-case IDs and every artifact is
reconstructable byte-for-byte from source data and committed ground truth.
"""

from patentbench.reports.confusion import (
    ConfusionCellTrace,
    ConfusionMatrixResult,
    build_confusion_matrix,
)
from patentbench.reports.ground_truth import (
    GroundTruthMissingError,
    GroundTruthRow,
    extract_predictions_and_truth,
    load_ground_truth,
)

__all__ = [
    "ConfusionCellTrace",
    "ConfusionMatrixResult",
    "GroundTruthMissingError",
    "GroundTruthRow",
    "build_confusion_matrix",
    "extract_predictions_and_truth",
    "load_ground_truth",
]
