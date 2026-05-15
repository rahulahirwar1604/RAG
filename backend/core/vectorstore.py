"""
DualRAG Core — Qdrant Vector Store Manager
============================================
Supports both local Qdrant (host:port) and Qdrant Cloud (QDRANT_URL).
The connection strategy is selected automatically via settings.qdrant_connection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from core.config import settings

logger = logging.getLogger("dualrag.vectorstore")


class VectorStoreManager:
    """Manages the Qdrant collection used by DualRAG."""

    def __init__(self) -> None:
        # settings.qdrant_connection auto-picks cloud vs local
        self._client     = QdrantClient(**settings.qdrant_connection)
        self._collection = settings.QDRANT_COLLECTION
        logger.info(
            "VectorStoreManager connected (collection=%s)", self._collection
        )

    # ------------------------------------------------------------------
    # Collection lifecycle
    # ------------------------------------------------------------------
    def ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSIONS,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created collection '%s'", self._collection)
        else:
            logger.info("Collection '%s' already exists", self._collection)

        # Payload index for fast filtered deletes/searches
        self._client.create_payload_index(
            collection_name=self._collection,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info("Payload index on 'document_id' ensured")

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------
    def upsert_chunks(
        self,
        embeddings: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> int:
        points = [
            PointStruct(id=str(uuid4()), vector=emb, payload=payload)
            for emb, payload in zip(embeddings, payloads)
        ]
        for i in range(0, len(points), 100):
            self._client.upsert(
                collection_name=self._collection,
                points=points[i : i + 100],
            )
        logger.info(
            "Upserted %d vectors (%s)",
            len(points),
            payloads[0].get("filename", "unknown") if payloads else "?",
        )
        return len(points)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self,
        query_vector: List[float],
        top_k: int = 15,
        doc_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        search_filter = None
        if doc_filter:
            search_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=doc_filter))]
            )
        results = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True,
        )
        return [
            {
                "score":       hit.score,
                "document_id": hit.payload.get("document_id", ""),
                "filename":    hit.payload.get("filename", ""),
                "chunk_id":    hit.payload.get("chunk_id", ""),
                "chunk_text":  hit.payload.get("chunk_text", ""),
            }
            for hit in results
        ]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def delete_by_document_id(self, document_id: str) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )
        logger.info("Deleted vectors for document_id=%s", document_id)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def collection_info(self) -> Dict[str, Any]:
        info = self._client.get_collection(self._collection)
        return {
            "vectors_count": info.vectors_count,
            "points_count":  info.points_count,
            "status":        info.status.value if info.status else "unknown",
        }
