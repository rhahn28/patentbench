"""HuggingFace Inference API model adapter for PatentBench.

Supports any model available on the HuggingFace Inference API,
including Mistral, Llama, and other open-source models.
"""

from __future__ import annotations

import os
from typing import Any

from patentbench.models.base import BaseModelAdapter, GenerationConfig


class HuggingFaceAdapter(BaseModelAdapter):
    """Model adapter for HuggingFace Inference API models.

    Uses the ``huggingface_hub`` library's :class:`InferenceClient` to call
    the HuggingFace Inference API (serverless).  Authentication is handled
    via the ``HF_TOKEN`` environment variable or an explicit *api_key*
    parameter.

    Usage:
        adapter = HuggingFaceAdapter()  # defaults to Mistral-7B-Instruct
        adapter = HuggingFaceAdapter(model_name="meta-llama/Llama-3-8B-Instruct")
        response = adapter.generate("Draft arguments against this 103 rejection...")
    """

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-Instruct-v0.3",
        api_key: str | None = None,
        config: GenerationConfig | None = None,
    ) -> None:
        super().__init__(model_name=model_name, config=config)
        self.api_key = api_key or os.environ.get("HF_TOKEN", "")
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazy-initialize the HuggingFace InferenceClient."""
        if self._client is None:
            try:
                from huggingface_hub import InferenceClient
                self._client = InferenceClient(
                    model=self.model_name,
                    token=self.api_key or None,
                )
            except ImportError:
                raise ImportError(
                    "huggingface_hub is not installed. "
                    "Install with: pip install huggingface_hub"
                )
        return self._client

    def generate(self, prompt: str, config: GenerationConfig | None = None) -> str:
        """Generate a response using the HuggingFace Inference API.

        Args:
            prompt: The patent prosecution task prompt.
            config: Optional generation config override.

        Returns:
            The model's response text.
        """
        cfg = config or self.config

        messages: list[dict[str, str]] = []
        if cfg.system_prompt:
            messages.append({"role": "system", "content": cfg.system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat_completion(
            messages=messages,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature if cfg.temperature > 0 else None,
            top_p=cfg.top_p,
            stop=cfg.stop_sequences or None,
        )

        return response.choices[0].message.content or ""

    def is_available(self) -> bool:
        """Check if HuggingFace API token is configured."""
        return bool(self.api_key)
