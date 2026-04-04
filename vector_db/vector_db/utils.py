"""Text preprocessing and utility functions."""

from __future__ import annotations

import re
import uuid
from typing import List


def preprocess(text: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def chunk_text(text: str, max_tokens: int = 256, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks by word count.

    Args:
        text: Input text to chunk.
        max_tokens: Maximum words per chunk.
        overlap: Number of overlapping words between chunks.

    Returns:
        List of text chunks.
    """
    if not text:
        return []
    words = text.split()
    if len(words) <= max_tokens:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + max_tokens
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap
    return chunks


def generate_id() -> str:
    """Generate a unique ID."""
    return uuid.uuid4().hex[:16]
