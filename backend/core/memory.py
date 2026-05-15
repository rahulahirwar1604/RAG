"""
DualRAG Core — Conversation Memory
====================================
Maintains a sliding window of the last N user↔assistant exchanges
per session.  Used to provide conversational context to the LLM
without bloating the prompt.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger("dualrag.memory")


@dataclass
class Turn:
    """A single user↔assistant exchange."""
    user: str
    assistant: str


class ConversationMemory:
    """
    In-memory sliding-window conversation store.

    Parameters
    ----------
    max_turns : int
        Maximum number of past exchanges to retain per session.
    """

    def __init__(self, max_turns: int = 3) -> None:
        self._max_turns = max_turns
        # session_id → list of Turn objects
        self._store: Dict[str, List[Turn]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Record a completed user↔assistant exchange."""
        turns = self._store[session_id]
        turns.append(Turn(user=user_msg, assistant=assistant_msg))
        # Trim to max window
        if len(turns) > self._max_turns:
            self._store[session_id] = turns[-self._max_turns :]
        logger.debug(
            "Memory[%s]: stored turn (%d/%d)",
            session_id[:8],
            len(self._store[session_id]),
            self._max_turns,
        )

    def get_history(self, session_id: str) -> List[Turn]:
        """Return all stored turns for a session (up to max_turns)."""
        return list(self._store.get(session_id, []))

    def get_history_as_messages(
        self, session_id: str
    ) -> List[Dict[str, str]]:
        """
        Return conversation history formatted as a list of
        {"role": ..., "content": ...} dicts suitable for LLM prompt building.
        """
        messages: List[Dict[str, str]] = []
        for turn in self.get_history(session_id):
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        return messages

    def get_context_string(self, session_id: str) -> str:
        """
        Return conversation history as a single formatted string
        for injection into a system/user prompt.
        """
        turns = self.get_history(session_id)
        if not turns:
            return ""
        parts = []
        for i, turn in enumerate(turns, 1):
            parts.append(f"[Turn {i}]")
            parts.append(f"User: {turn.user}")
            parts.append(f"Assistant: {turn.assistant}")
            parts.append("")
        return "\n".join(parts)

    def clear_session(self, session_id: str) -> None:
        """Remove all memory for a session."""
        self._store.pop(session_id, None)

    def clear_all(self) -> None:
        """Wipe all stored conversations."""
        self._store.clear()

    @property
    def active_sessions(self) -> int:
        """Number of sessions with stored history."""
        return len(self._store)
