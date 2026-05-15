"""
DualRAG Backend — FastAPI Application Entry Point
===================================================
Production-ready FastAPI server for the DualRAG Agentic Intelligence platform.

Responsibilities:
  - Mount all API routers under /api prefix
  - Configure CORS for Vite frontend
  - Initialize Qdrant collection on startup
  - Initialize document storage on startup
  - Provide lifespan-managed startup/shutdown hooks
"""

import os
import sys
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ---------------------------------------------------------------------------
# Ensure backend package is importable when running from project root
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
# Load environment variables BEFORE importing internal modules
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# ---------------------------------------------------------------------------
# Internal imports (after env is loaded)
# ---------------------------------------------------------------------------
from core.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-24s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dualrag")




# ---------------------------------------------------------------------------
# Document storage initialization
# ---------------------------------------------------------------------------
def _init_document_storage() -> None:
    """Ensure storage/documents.json exists with a valid structure."""
    store_path = Path(settings.DOCUMENT_STORE_PATH)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    if not store_path.exists():
        store_path.write_text(json.dumps([], indent=2), encoding="utf-8")
        logger.info("Created document storage at %s", store_path)
    else:
        # Validate existing file is parseable
        try:
            data = json.loads(store_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("Root must be a JSON array")
            logger.info(
                "Loaded document storage with %d document(s)", len(data)
            )
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Corrupt document storage (%s) — resetting to empty list", exc
            )
            store_path.write_text(json.dumps([], indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # Late imports to avoid circular dependency chains
    from core.vectorstore import VectorStoreManager
    from core.memory import ConversationMemory
    from core.embeddings import EmbeddingService
    from core.reranker import RerankService
    from services.generator import AnswerGenerator

    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("DualRAG Backend starting up …")
    logger.info("=" * 60)

    # 1. Initialize document JSON storage
    _init_document_storage()

    # 2. Create singleton managers and attach to app.state
    vector_store = VectorStoreManager()
    memory = ConversationMemory(max_turns=3)
    embedding_service = EmbeddingService()
    reranker = RerankService()
    generator = AnswerGenerator()

    app.state.vector_store = vector_store
    app.state.memory = memory
    app.state.embedding_service = embedding_service
    app.state.reranker = reranker
    app.state.generator = generator

    # 3. Initialize Qdrant collection + payload index
    try:
        vector_store.ensure_collection()
        logger.info("Qdrant collection '%s' ready", settings.QDRANT_COLLECTION)
    except Exception as exc:
        logger.error("Failed to initialize Qdrant: %s", exc)
        logger.warning(
            "Backend will start but upload/query will fail until Qdrant is available"
        )

    logger.info("DualRAG Backend is ready — accepting requests")
    logger.info(
        "Expecting frontend at origins: %s",
        ", ".join(settings.cors_origins_list),
    )

    yield  # ── Application runs here ─────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("DualRAG Backend shutting down …")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="DualRAG API",
    description="Agentic Intelligence — Document Chat RAG Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "Accept",
    ],
    expose_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# Mount API routers under /api prefix
# ---------------------------------------------------------------------------
from api.health import router as health_router
from api.upload import router as upload_router
from api.documents import router as documents_router
from api.query import router as query_router

app.include_router(health_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(query_router, prefix="/api")


# ---------------------------------------------------------------------------
# Root redirect (convenience)
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "DualRAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
