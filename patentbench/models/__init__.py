"""Model adapters for PatentBench.

Provides a unified interface for evaluating different AI models
on patent prosecution tasks.
"""

from patentbench.models.base import BaseModelAdapter
from patentbench.models.huggingface_adapter import HuggingFaceAdapter

__all__ = ["BaseModelAdapter", "HuggingFaceAdapter"]
