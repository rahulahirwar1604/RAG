"""
DualRAG Core — NVIDIA Rerank Service
====================================
Uses NVIDIA hosted reranking API to reorder retrieved chunks.
Falls back gracefully if rerank unavailable.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

import httpx

from core.config import settings

logger = logging.getLogger("dualrag.reranker")


class RerankService:
    def __init__(self) -> None:
        if not settings.NVIDIA_API_KEY:
            logger.warning("NVIDIA_API_KEY is not set — reranking will fail")

        self._api_key = settings.NVIDIA_API_KEY
        self._url = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"
        self._model = "nvidia/llama-3.2-nv-rerankqa-1b-v2"
        self._timeout = 40.0

        logger.info(
            "RerankService initialised (model=%s, url=%s)",
            self._model,
            self._url,
        )

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:

        if not chunks or not self._api_key:
            return chunks[:top_n]

        documents = [c.get("chunk_text", "") for c in chunks]

        payload = {
         "model": self._model,
         "query": {"text": query},
          "documents": [{"text": doc} for doc in documents],
         "top_n": min(top_n, len(documents)),
         "truncate": "END"
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(self._url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

        except Exception as exc:
            logger.warning("Reranker failed, using vector order: %s", exc)
            return chunks[:top_n]

        results = data.get("rankings", []) or data.get("results", [])

        if not results:
            logger.warning("Reranker returned empty results")
            return chunks[:top_n]

        reranked: List[Dict[str, Any]] = []

        for item in results:
            idx = item.get("index", 0)
            score = item.get("relevance_score", item.get("score", 0.0))
            
            if idx < len(chunks):
                chunk = chunks[idx].copy()
                chunk["relevance_score"] = self._normalize(score)
                reranked.append(chunk)

        logger.info(
            "Reranked %d -> %d chunks successfully (top score=%.4f)",
            len(chunks),
            len(reranked),
            reranked[0]["relevance_score"] if reranked else 0.0,
        )

        return reranked

    @staticmethod
    def _normalize(score: float) -> float:
        try:
            return round(1 / (1 + math.exp(-score)), 4)
        except:
            return 0.5