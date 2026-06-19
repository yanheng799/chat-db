"""Embedding client for the local bge service (OpenAI-compatible ``/v1/embeddings``).

V1 note: calls are synchronous (``urllib``) under async wrappers. Knowledge-base
build is a background job, not a hot path, so blocking briefly is acceptable;
``run_learning`` already tolerates suppressed failures.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from config.settings import Settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Batched embedder against the configured local embedding service."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._url = self._settings.embedding_base_url.rstrip("/") + "/embeddings"
        self._model = self._settings.embedding_model
        self._batch_size = self._settings.embedding_batch_size
        self._max_len = self._settings.embedding_max_input_length

    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in batches; each input truncated to ``max_input_length``."""
        out: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = [t[: self._max_len] for t in texts[start : start + self._batch_size]]
            payload = json.dumps({"model": self._model, "input": batch}).encode("utf-8")
            req = urllib.request.Request(
                self._url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            out.extend(item["embedding"] for item in data["data"])
        return out

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_sync(texts)

    async def embed_one(self, text: str) -> list[float]:
        return self.embed_sync([text])[0]
