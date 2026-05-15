"""
DualRAG Core — Embedding Service (OpenRouter Raw HTTP)
======================================================
Uses direct HTTP requests to OpenRouter embeddings endpoint for
nvidia/llama-nemotron-embed-vl-1b-v2:free.
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from core.config import settings

logger = logging.getLogger("dualrag.embeddings")


class EmbeddingService:
    def __init__(self) -> None:
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY is not set — embedding calls will fail")

        self._api_key = settings.OPENROUTER_API_KEY
        self._base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        self._model = settings.EMBEDDING_MODEL

        logger.info(
            "EmbeddingService initialised (model=%s, base_url=%s)",
            self._model,
            self._base_url,
        )

    def _request_embeddings(self, inputs: List[str]) -> List[List[float]]:
        url = f"{self._base_url}/embeddings"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "input": inputs
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

        if "data" not in result or result["data"] is None:
            raise RuntimeError(f"Invalid embedding response from OpenRouter: {result}")

        embeddings = [item["embedding"] for item in result["data"]]
        return embeddings

    # --------------------------------------------------------
    def embed_query(self, text: str) -> List[float]:
        vectors = self._request_embeddings([text])
        logger.debug("Embedded query (%d chars → %d dims)", len(text), len(vectors[0]))
        return vectors[0]

    # --------------------------------------------------------
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        all_embeddings: List[List[float]] = []
        batch_size = 64

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self._request_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

            logger.debug(
                "Embedded batch %d–%d (%d texts)",
                i,
                i + len(batch) - 1,
                len(batch),
            )

        logger.info("Embedded %d text chunks total", len(all_embeddings))
        return all_embeddings