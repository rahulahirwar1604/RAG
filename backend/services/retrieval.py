"""
DualRAG Services — Smart Retrieval + Rerank Pipeline
======================================================
Embeds query → searches Qdrant → reranks → filters weak matches →
returns only meaningful context.

This prevents irrelevant documents from contaminating general questions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.config import settings

logger = logging.getLogger("dualrag.services.retrieval")

# ------------------------------------------------------------
# Smart confidence thresholds
# ------------------------------------------------------------
MIN_VECTOR_SCORE = 0.35
MIN_RERANK_SCORE = 0.45


class RetrievalService:
    """Stateless smart retrieval orchestrator."""

    def retrieve_and_rerank(
        self,
        *,
        query: str,
        embedding_service: Any,
        vector_store: Any,
        reranker: Any,
        retrieval_top_k: int | None = None,
        rerank_top_n: int | None = None,
    ) -> Dict[str, Any]:

        top_k = retrieval_top_k or settings.RETRIEVAL_TOP_K
        top_n = rerank_top_n or settings.RERANK_TOP_N

        # --------------------------------------------------------
        # 1. Embed user query
        # --------------------------------------------------------
        query_embedding = embedding_service.embed_query(query)

        # --------------------------------------------------------
        # 2. Vector search from Qdrant
        # --------------------------------------------------------
        raw_chunks = vector_store.search(query_embedding, top_k)

        if not raw_chunks:
            logger.info("No chunks found for query: '%s'", query[:80])
            return {
                "raw_chunks": [],
                "reranked_chunks": [],
                "sources": [],
                "confidence": 0.0,
            }

        logger.info("Initial retrieved chunks: %d", len(raw_chunks))

        # --------------------------------------------------------
        # 3. Remove weak vector similarity matches
        # --------------------------------------------------------
        raw_chunks = [
            chunk for chunk in raw_chunks
            if chunk.get("score", 0.0) >= MIN_VECTOR_SCORE
        ]

        if not raw_chunks:
            logger.info("No vector matches above threshold for query: '%s'", query[:80])
            return {
                "raw_chunks": [],
                "reranked_chunks": [],
                "sources": [],
                "confidence": 0.0,
            }

        logger.info("Chunks after vector filtering: %d", len(raw_chunks))

        # --------------------------------------------------------
        # 4. Semantic reranking
        # --------------------------------------------------------
        try:
            reranked_chunks = reranker.rerank(query, raw_chunks, top_n)
        except Exception as exc:
            logger.warning("Reranker failed, using vector order: %s", exc)
            reranked_chunks = raw_chunks[:top_n]

        # --------------------------------------------------------
        # 5. Remove weak rerank semantic matches
        # --------------------------------------------------------
        reranked_chunks = [
            chunk for chunk in reranked_chunks
            if chunk.get("relevance_score", chunk.get("score", 0.0)) >= MIN_RERANK_SCORE
        ]

        logger.info("Chunks after rerank filtering: %d", len(reranked_chunks))

        confidence = self._compute_confidence(reranked_chunks)
        sources = self._build_sources(reranked_chunks)

        return {
            "raw_chunks": raw_chunks,
            "reranked_chunks": reranked_chunks,
            "sources": sources,
            "confidence": confidence,
        }

    # ------------------------------------------------------------
    # Deduplicated source builder
    # ------------------------------------------------------------
    @staticmethod
    def _build_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        seen_docs = set()
        sources = []

        for c in chunks:
            document_id = c.get("document_id", "")
            if document_id in seen_docs:
                continue

            seen_docs.add(document_id)

            sources.append({
                "filename": c.get("filename", "Unknown"),
                "document_id": document_id,
                "chunk_id": c.get("chunk_id", ""),
                "text": c.get("chunk_text", ""),
            })

        return sources

    # ------------------------------------------------------------
    # Confidence calculator
    # ------------------------------------------------------------
    @staticmethod
    def _compute_confidence(chunks: List[Dict[str, Any]]) -> float:
        if not chunks:
            return 0.0

        scores = [
            c.get("relevance_score", c.get("score", 0.0))
            for c in chunks
        ]

        avg = sum(scores) / len(scores)
        return round(min(max(avg, 0.0), 1.0), 3)