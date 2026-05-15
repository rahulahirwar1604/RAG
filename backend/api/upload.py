"""
DualRAG API — Document Upload  (with Cloudinary backup)
=========================================================
POST /api/upload

Flow:
  1. Validate file type
  2. Upload raw file to Cloudinary (free CDN backup — optional)
  3. Run parse → chunk → embed → upsert pipeline via IngestionService
  4. Return {message, document_id, filename, chunks, cloudinary_url?}

Cloudinary upload is non-blocking: if it fails the ingestion still
succeeds — we just don't have a CDN backup copy.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from services.ingestion import IngestionService
from core.config import settings

logger = logging.getLogger("dualrag.api.upload")

router    = APIRouter(tags=["upload"])
_ingestion = IngestionService()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _upload_to_cloudinary(file_bytes: bytes, filename: str) -> str | None:
    """
    Upload file bytes to Cloudinary and return the secure URL.
    Returns None if Cloudinary is not configured or upload fails.
    """
    if not all([
        settings.CLOUDINARY_CLOUD_NAME,
        settings.CLOUDINARY_API_KEY,
        settings.CLOUDINARY_API_SECRET,
    ]):
        return None  # Cloudinary not configured — skip silently

    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

        # Upload as raw file (preserves original format)
        result = cloudinary.uploader.upload(
            file_bytes,
            resource_type="raw",
            public_id=f"dualrag/{Path(filename).stem}",
            overwrite=True,
            tags=["dualrag", "document"],
        )
        url = result.get("secure_url", "")
        logger.info("Cloudinary upload OK: %s", url)
        return url

    except Exception as exc:
        logger.warning("Cloudinary upload failed (non-fatal): %s", exc)
        return None


@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """Upload, index, and optionally back up a document to Cloudinary."""

    vector_store      = request.app.state.vector_store
    embedding_service = request.app.state.embedding_service

    # 1. Validate extension
    filename = file.filename or "unknown"
    ext      = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Read bytes
    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {exc}")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    logger.info("Upload received: '%s' (%d bytes)", filename, len(file_bytes))

    # 3. Cloudinary backup (runs in thread — non-blocking to main pipeline)
    cloudinary_url = await asyncio.to_thread(
        _upload_to_cloudinary, file_bytes, filename
    )

    # 4. Ingest (parse → chunk → embed → upsert → save metadata)
    try:
        result = await asyncio.to_thread(
            _ingestion.ingest,
            file_bytes=file_bytes,
            filename=filename,
            extension=ext,
            vector_store=vector_store,
            embedding_service=embedding_service,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.error("Ingestion error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    # 5. Attach Cloudinary URL to response if available
    if cloudinary_url:
        result["cloudinary_url"] = cloudinary_url

    return result
