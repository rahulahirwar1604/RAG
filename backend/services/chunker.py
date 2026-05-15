"""
DualRAG Services — Text Chunker
=================================
Splits cleaned document text into overlapping chunks suitable for
embedding and vector storage.
"""

from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger("dualrag.services.chunker")

# Sentence-ending patterns for smart boundary detection
_SENTENCE_END = re.compile(r"[.!?]\s+")


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[str]:
    """
    Split text into overlapping character-based chunks.

    The chunker tries to break at sentence boundaries within a
    tolerance window to avoid cutting mid-sentence.

    Parameters
    ----------
    text : str
        The full document text.
    chunk_size : int
        Target number of characters per chunk.
    chunk_overlap : int
        Number of overlapping characters between consecutive chunks.

    Returns
    -------
    list[str] — Non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If the entire text fits in one chunk, return as-is
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        if end >= text_len:
            # Last chunk — take everything remaining
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Try to find a sentence boundary near the end of the chunk
        # Search in the last 20% of the chunk for a clean break
        search_start = start + int(chunk_size * 0.8)
        search_region = text[search_start:end]

        best_break = None
        for match in _SENTENCE_END.finditer(search_region):
            best_break = search_start + match.end()

        if best_break and best_break > start:
            end = best_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Advance by (chunk_size - overlap), but at least 1 char
        step = max(end - start - chunk_overlap, 1)
        start = start + step

    # Remove any chunks that are too short to be meaningful
    min_length = 50
    chunks = [c for c in chunks if len(c) >= min_length]

    logger.info(
        "Chunked %d chars → %d chunks (size=%d, overlap=%d)",
        text_len,
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks
