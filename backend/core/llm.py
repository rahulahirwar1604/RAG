"""
DualRAG Core — LLM Service (Claude via OpenRouter)
===================================================
Replaces Google Gemini.  Uses the same `openai` SDK already in
requirements.txt, pointed at OpenRouter's OpenAI-compatible endpoint.

Model: anthropic/claude-sonnet-4-20250514  (set in config.py / env)

Public interface is unchanged — AnswerGenerator calls the same three
methods and required zero edits.
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from openai import OpenAI

from core.config import settings

logger = logging.getLogger("dualrag.llm")


class LLMService:
    """
    Answer generation using Claude via OpenRouter.

    All heavy config (model, temperature, max_tokens) lives in Settings
    so this class never needs to be edited to change the model.
    """

    def __init__(self) -> None:
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set — LLM calls will fail")

        # OpenRouter's OpenAI-compatible endpoint
        self._client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        self._model       = settings.LLM_MODEL
        self._temperature = settings.LLM_TEMPERATURE
        self._max_tokens  = settings.LLM_MAX_TOKENS

        logger.info(
            "LLMService ready — model=%s  temp=%.1f  max_tokens=%d",
            self._model, self._temperature, self._max_tokens,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _model_name(self, override: Optional[str]) -> str:
        return override or self._model

    @staticmethod
    def _to_messages(prompt: str) -> list[dict]:
        """Wrap flat prompt string into chat format."""
        return [{"role": "user", "content": prompt}]

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------
    def generate(self, prompt: str, model_override: Optional[str] = None) -> str:
        resp = self._client.chat.completions.create(
            model=self._model_name(model_override),
            messages=self._to_messages(prompt),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        text = resp.choices[0].message.content or ""
        logger.debug("Generated %d chars", len(text))
        return text

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    def generate_stream(
        self,
        prompt: str,
        model_override: Optional[str] = None,
    ) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self._model_name(model_override),
            messages=self._to_messages(prompt),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
