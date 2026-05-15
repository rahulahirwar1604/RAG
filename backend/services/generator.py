"""
DualRAG Services — Production Hybrid Grounded Generator
========================================================
True RAG-first answer generation with intelligent fallback to general LLM knowledge.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from core.llm import LLMService

logger = logging.getLogger("dualrag.services.generator")


SYSTEM_PROMPT = """YYou are DualRAG, an intelligent AI research assistant.

Your job is to answer naturally, clearly, and conversationally like ChatGPT.

RULES:
1. If relevant document context is provided, prioritize that information.
2. If document context is missing or insufficient, answer confidently using your own general knowledge.
3. Never say "according to provided documents" or "based on context" unless user explicitly asks for sources.
4. Write answers in a human helpful tone, not robotic.
5. If answer is short factual, answer directly in 1-3 lines.
6. If answer requires explanation, explain cleanly with structure.
7. Never mention that retrieval failed.
8. Never mention internal system limitations.
"""


HISTORY_TEMPLATE = """
=== CONVERSATION HISTORY ===
{history}
=== END CONVERSATION HISTORY ===
"""


class AnswerGenerator:
    def __init__(self) -> None:
        self._llm = LLMService()

    @staticmethod
    def _build_prompt(
        query: str,
        chunks: List[Dict[str, Any]],
        history_context: str = "",
    ) -> str:

        # ---------------------------------------------------------
        # Rich source context formatting
        # ---------------------------------------------------------
        if chunks:
            context_text = []
            for i, chunk in enumerate(chunks, 1):
                filename = chunk.get("filename", "Unknown")
                text = chunk.get("chunk_text", "")
                score = chunk.get("relevance_score", chunk.get("score", ""))

                context_text.append(
                    f"""
DOCUMENT SOURCE {i}
Filename: {filename}
Relevance: {score}

Document Excerpt:
{text}
"""
                )

            context_block = (
                "=== RETRIEVED DOCUMENT CONTEXT ===\n"
                + "\n".join(context_text)
                + "\n=== END DOCUMENT CONTEXT ==="
            )
        else:
            context_block = (
                "=== RETRIEVED DOCUMENT CONTEXT ===\n"
                "No relevant document passages were retrieved.\n"
                "=== END DOCUMENT CONTEXT ==="
            )

        # ---------------------------------------------------------
        # History formatting
        # ---------------------------------------------------------
        history_block = ""
        if history_context:
            history_block = HISTORY_TEMPLATE.format(history=history_context)

        # ---------------------------------------------------------
        # Final prompt
        # ---------------------------------------------------------
        prompt = f"""
{SYSTEM_PROMPT}

{context_block}

{history_block}

USER QUESTION:
{query}

FINAL ANSWER:
"""

        return prompt

    def generate(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
        history_context: str = "",
        model: Optional[str] = None,
    ) -> str:
        prompt = self._build_prompt(query, chunks, history_context)
        logger.debug("Generation prompt length: %d chars", len(prompt))

        answer = self._llm.generate(prompt, model_override=model)
        logger.info("Generated final answer (%d chars)", len(answer))
        return answer

    def generate_stream(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
        history_context: str = "",
        model: Optional[str] = None,
    ) -> Iterator[str]:
        prompt = self._build_prompt(query, chunks, history_context)
        logger.debug("Streaming prompt length: %d chars", len(prompt))

        yield from self._llm.generate_stream(prompt, model_override=model)

    async def async_generate_stream(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
        history_context: str = "",
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[str | Exception]] = asyncio.Queue()

        def _producer():
            try:
                for chunk in self.generate_stream(
                    query=query,
                    chunks=chunks,
                    history_context=history_context,
                    model=model,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _producer)

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item