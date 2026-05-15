"""
DualRAG Services — Ingestion Pipeline
=======================================
Orchestrates the full document ingestion flow:
  parse → chunk → embed → upsert to Qdrant → persist metadata

This is the PRIMARY business logic for document upload.
The API route (``api/upload.py``) is a thin controller that validates
input and delegates here.

Entirely synchronous — the API layer wraps the call in
``asyncio.to_thread()``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from core.config import settings
from services.parser import parse_document
from services.chunker import chunk_text

logger = logging.getLogger("dualrag.services.ingestion")


class IngestionService:
    """Stateless document ingestion orchestrator."""

    def ingest(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        extension: str,
        vector_store: Any,
        embedding_service: Any,
    ) -> Dict[str, Any]:
        """
        Run the full ingestion pipeline for one document.

        Parameters
        ----------
        file_bytes : bytes
            Raw uploaded file content.
        filename : str
            Original filename.
        extension : str
            Lowercased extension with dot (e.g. ``".pdf"``).
        vector_store : VectorStoreManager
            Qdrant manager singleton from ``app.state``.
        embedding_service : EmbeddingService
            OpenAI embedding singleton from ``app.state``.

        Returns
        -------
        dict with keys: message, document_id, filename, chunks

        Raises
        ------
        ValueError  — parsing / chunking failures
        RuntimeError — embedding / vector storage failures
        """
        document_id = str(uuid4())
        upload_timestamp = datetime.now(timezone.utc).isoformat()

        # ── 1. Parse ─────────────────────────────────────────────────
        logger.info("Ingesting '%s' (id=%s, %d bytes)", filename, document_id, len(file_bytes))
        raw_text = parse_document(file_bytes, extension)

        if not raw_text or not raw_text.strip():
            raise ValueError("No text could be extracted from the document")

        # ── 2. Chunk ─────────────────────────────────────────────────
        chunks = chunk_text(
            raw_text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

        if not chunks:
            raise ValueError("Document produced no text chunks after processing")

        logger.info("Created %d chunks from '%s'", len(chunks), filename)

        # ── 3. Embed ─────────────────────────────────────────────────
        try:
            embeddings = embedding_service.embed_texts(chunks)
        except Exception as exc:
            raise RuntimeError(f"Embedding generation failed: {exc}") from exc

        # ── 4. Build payloads and upsert to Qdrant ───────────────────
        payloads: List[Dict[str, Any]] = [
            {
                "document_id": document_id,
                "filename": filename,
                "chunk_id": f"{document_id}_chunk_{i}",
                "chunk_text": chunk,
                "upload_timestamp": upload_timestamp,
            }
            for i, chunk in enumerate(chunks)
        ]

        try:
            vector_store.upsert_chunks(embeddings, payloads)
        except Exception as exc:
            raise RuntimeError(f"Vector storage failed: {exc}") from exc

        # ── 5. Persist document metadata ─────────────────────────────
        self._save_document_metadata(document_id, filename, len(chunks), upload_timestamp)

        logger.info(
            "Ingestion complete: '%s' → %d chunks (id=%s)",
            filename, len(chunks), document_id,
        )

        return {
            "message": "Document uploaded successfully",
            "document_id": document_id,
            "filename": filename,
            "chunks": len(chunks),
        }

    @staticmethod
    def _save_document_metadata(
        document_id: str,
        filename: str,
        chunk_count: int,
        upload_timestamp: str,
    ) -> None:
        """Append document metadata to storage/documents.json."""
        store_path = settings.document_store_absolute_path
        try:
            data = json.loads(store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            data = []

        data.append(
            {
                "id": document_id,
                "filename": filename,
                "chunk_count": chunk_count,
                "upload_time": upload_timestamp,
            }
        )
        store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Persisted metadata for '%s' (id=%s)", filename, document_id)
