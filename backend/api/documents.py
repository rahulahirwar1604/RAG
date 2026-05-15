"""
DualRAG API — Document Management
===================================
GET    /api/documents          — list all indexed documents
DELETE /api/documents/{doc_id} — delete a document and its vectors

Frontend contract:
  GET  response: { "documents": [{ id, filename, chunk_count, upload_time }] }
  DELETE response: any 200 (frontend only checks response.ok)

Document metadata is persisted in storage/documents.json so it
survives server restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from core.config import settings

logger = logging.getLogger("dualrag.api.documents")

router = APIRouter(tags=["documents"])


# ---------------------------------------------------------------------------
# Helpers for persistent JSON storage
# ---------------------------------------------------------------------------
def _read_document_store() -> List[Dict[str, Any]]:
    """Read the document manifest from disk."""
    store_path = settings.document_store_absolute_path
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return []


def _write_document_store(data: List[Dict[str, Any]]) -> None:
    """Write the document manifest to disk."""
    store_path = settings.document_store_absolute_path
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/documents")
async def list_documents():
    """
    Return all uploaded documents.

    Response shape matches what the frontend expects::

        {
          "documents": [
            {
              "id": "uuid",
              "filename": "report.pdf",
              "chunk_count": 42,
              "upload_time": "2025-01-01T00:00:00+00:00"
            }
          ]
        }
    """
    documents = _read_document_store()
    return {"documents": documents}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, request: Request):
    """
    Delete a document by ID.

    Steps:
      1. Remove all Qdrant vectors where payload.document_id == doc_id
      2. Remove the document entry from storage/documents.json

    The frontend resolves ``doc_id`` from the document object's
    ``id`` field (or falls back to ``doc_id`` / ``filename``).
    """
    vector_store = request.app.state.vector_store

    # 1. Read current manifest
    documents = _read_document_store()
    doc_entry = next((d for d in documents if d.get("id") == doc_id), None)

    if doc_entry is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    # 2. Delete vectors from Qdrant (sync client → offload to thread)
    try:
        await asyncio.to_thread(vector_store.delete_by_document_id, doc_id)
    except Exception as exc:
        logger.error("Failed to delete vectors for doc_id=%s: %s", doc_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to delete vectors from store: {str(exc)}",
        )

    # 3. Remove from manifest and persist
    updated = [d for d in documents if d.get("id") != doc_id]
    _write_document_store(updated)

    logger.info(
        "Deleted document '%s' (id=%s) — vectors removed, manifest updated",
        doc_entry.get("filename", "unknown"),
        doc_id,
    )

    return {"message": f"Document '{doc_entry.get('filename', doc_id)}' deleted successfully"}
