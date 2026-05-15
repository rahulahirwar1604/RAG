"""
DualRAG API — Query Endpoint
==============================
POST /api/query

Thin controller: validates input, delegates retrieval to
RetrievalService and generation to AnswerGenerator,
handles JSON response.

Hybrid mode:
- If relevant documents exist → grounded RAG answer
- If no relevant documents → Gemini general knowledge fallback
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.retrieval import RetrievalService

logger = logging.getLogger("dualrag.api.query")

router = APIRouter(tags=["query"])
_retrieval = RetrievalService()


# ================= REQUEST MODELS =================
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: Optional[int] = Field(default=3)
    stream: Optional[bool] = Field(default=False)
    model: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)


class SourceItem(BaseModel):
    filename: str
    document_id: str
    chunk_id: str
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    retrieved_chunks: int
    confidence: float


# ================= MAIN ROUTE =================
@router.post("/query")
async def query_documents(body: QueryRequest, request: Request):
    vector_store = request.app.state.vector_store
    memory = request.app.state.memory
    embedding_service = request.app.state.embedding_service
    reranker = request.app.state.reranker
    generator = request.app.state.generator

    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    session_id = body.session_id or "default"

    # ===== Retrieval =====
    try:
        retrieval_result = await asyncio.to_thread(
            _retrieval.retrieve_and_rerank,
            query=query,
            embedding_service=embedding_service,
            vector_store=vector_store,
            reranker=reranker,
        )
    except Exception as exc:
        logger.error("Retrieval pipeline failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Retrieval failed: {exc}")

    raw_chunks = retrieval_result["raw_chunks"]
    reranked_chunks = retrieval_result["reranked_chunks"]
    sources = retrieval_result["sources"]
    confidence = retrieval_result["confidence"]

    logger.info("Retrieved chunks: %d | proceeding to generator", len(raw_chunks))

    # ===== Memory Context =====
    history_context = memory.get_context_string(session_id)

    # ===== Streaming (disabled frontend fallback compatible) =====
    if body.stream:
        return StreamingResponse(
            _stream_answer(
                generator=generator,
                query=query,
                reranked_chunks=reranked_chunks,
                history_context=history_context,
                sources=sources,
                confidence=confidence,
                memory=memory,
                session_id=session_id,
                model=body.model,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ===== Final Answer Generation =====
    try:
        answer = await asyncio.to_thread(
            generator.generate,
            query=query,
            chunks=reranked_chunks,
            history_context=history_context,
            model=body.model,
        )
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Answer generation failed: {exc}")

    memory.add_turn(session_id, query, answer)

    final_sources = [SourceItem(**s) for s in sources] if confidence >= 0.35 else []

    return QueryResponse(
        answer=answer,
        sources=final_sources,
        retrieved_chunks=len(raw_chunks),
        confidence=confidence,
    )


# ================= STREAM HELPER =================
async def _stream_answer(
    generator: Any,
    query: str,
    reranked_chunks: List[Dict[str, Any]],
    history_context: str,
    sources: List[Dict[str, str]],
    confidence: float,
    memory: Any,
    session_id: str,
    model: Optional[str] = None,
):
    full_answer = ""

    try:
        async for text_chunk in generator.async_generate_stream(
            query=query,
            chunks=reranked_chunks,
            history_context=history_context,
            model=model,
        ):
            full_answer += text_chunk
            yield f"data: {json.dumps({'done': False, 'text': text_chunk})}\n\n"

    except Exception as exc:
        logger.error("Streaming generation error: %s", exc)
        yield f"data: {json.dumps({'done': False, 'text': f'[Error: {exc}]'})}\n\n"

    final_sources = sources if confidence >= 0.35 else []
    yield f"data: {json.dumps({'done': True, 'sources': final_sources, 'confidence': confidence})}\n\n"

    if full_answer.strip():
        memory.add_turn(session_id, query, full_answer)

    logger.info("Streamed %d chars for query: '%s'", len(full_answer), query[:80])