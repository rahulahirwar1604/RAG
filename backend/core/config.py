"""
DualRAG Core — Application Configuration
==========================================
Free-stack production config:
  LLM        → Claude via OpenRouter (same key as embeddings)
  Vector DB  → Qdrant Cloud (free tier, URL-based connection)
  File Store → Cloudinary (free tier, PDF/image CDN)
  Hosting    → Render (backend) + Vercel (frontend)

Gemini has been fully removed.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):

    # ── Server ─────────────────────────────────────────────────
    HOST:  str  = Field(default="0.0.0.0")
    PORT:  int  = Field(default=8000)
    DEBUG: bool = Field(default=False)

    # ── CORS ───────────────────────────────────────────────────
    # Add your Vercel URL here once deployed, comma-separated
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )

    # ── Optional bearer-token security ─────────────────────────
    API_KEY: str = Field(default="")

    # ── OpenRouter  (embeddings + Claude LLM, one key) ─────────
    OPENROUTER_API_KEY:  str = Field(default="")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")

    # Embedding
    EMBEDDING_MODEL:      str = Field(default="nvidia/llama-nemotron-embed-vl-1b-v2:free")
    EMBEDDING_DIMENSIONS: int = Field(default=2048)

    # LLM — Claude via OpenRouter
    LLM_MODEL:       str   = Field(default="anthropic/claude-sonnet-4-20250514")
    LLM_TEMPERATURE: float = Field(default=0.2)
    LLM_MAX_TOKENS:  int   = Field(default=2048)

    # ── NVIDIA Reranker ────────────────────────────────────────
    NVIDIA_API_KEY:    str = Field(default="")
    NVIDIA_RERANK_URL: str = Field(default="https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking")
    RERANK_MODEL:      str = Field(default="nvidia/llama-3.2-nv-rerankqa-1b-v2")
    RERANK_TOP_N:      int = Field(default=5)

    # ── Qdrant Cloud ───────────────────────────────────────────
    # For Qdrant Cloud set QDRANT_URL to your cluster endpoint,
    # e.g. https://xxxx-xxxx.us-east4-0.gcp.cloud.qdrant.io
    # Leave QDRANT_HOST/PORT for local dev only.
    QDRANT_URL:        str = Field(default="")          # Cloud URL (preferred)
    QDRANT_HOST:       str = Field(default="localhost") # Local fallback
    QDRANT_PORT:       int = Field(default=6333)
    QDRANT_COLLECTION: str = Field(default="dualrag_documents")
    QDRANT_API_KEY:    str = Field(default="")

    # ── Cloudinary (file storage / CDN) ────────────────────────
    CLOUDINARY_CLOUD_NAME: str = Field(default="")
    CLOUDINARY_API_KEY:    str = Field(default="")
    CLOUDINARY_API_SECRET: str = Field(default="")

    # ── Chunking ───────────────────────────────────────────────
    CHUNK_SIZE:    int = Field(default=800)
    CHUNK_OVERLAP: int = Field(default=150)

    # ── Retrieval ──────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = Field(default=15)

    # ── Local metadata storage ─────────────────────────────────
    # On Render's ephemeral filesystem this resets on each deploy.
    # Qdrant payload is the source of truth; this is a convenience cache.
    DOCUMENT_STORE_PATH: str = Field(default="storage/documents.json")

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------
    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def qdrant_connection(self) -> dict:
        """
        Return kwargs for QdrantClient constructor.
        Prefers QDRANT_URL (cloud) over host:port (local).
        """
        if self.QDRANT_URL:
            kwargs = {"url": self.QDRANT_URL, "timeout": 30}
        else:
            kwargs = {"host": self.QDRANT_HOST, "port": self.QDRANT_PORT, "timeout": 30}
        if self.QDRANT_API_KEY:
            kwargs["api_key"] = self.QDRANT_API_KEY
        return kwargs

    @property
    def document_store_absolute_path(self) -> Path:
        p = Path(self.DOCUMENT_STORE_PATH)
        if p.is_absolute():
            return p
        return Path(__file__).resolve().parent.parent / p

    model_config = {
        "env_file":          ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive":    True,
        "extra":             "ignore",
    }


settings = Settings()
