"""
DualRAG API — Health Check
===========================
GET /api/health

Returns backend alive status. This endpoint is called by the frontend
without auth headers (raw fetch), so it must NOT require authentication.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter

logger = logging.getLogger("dualrag.api.health")

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Lightweight health probe.

    The frontend calls this every 30 seconds and on startup.
    It uses raw ``fetch()`` (not the ``apiCall`` wrapper), so
    no Authorization / X-API-Key headers are present.

    Returns 200 with a simple status JSON.
    """
    return {"status": "ok"}
