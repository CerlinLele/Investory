"""Document chunking utilities for the investment document review flow."""

from __future__ import annotations

import re

CHUNK_SIZE = 500
SELECT_MAX_CHARS = 4000


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into overlapping paragraph-aware chunks.

    Splits first on double newlines (paragraph boundaries), then merges
    adjacent paragraphs until each chunk reaches `chunk_size` characters.
    Short paragraphs are merged greedily; paragraphs longer than `chunk_size`
    are hard-split at the character level.
    """
    if not text:
        return []

    # Split on paragraph boundaries, keep non-empty paragraphs.
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        # If a single paragraph exceeds chunk_size, hard-split it first.
        if len(para) > chunk_size:
            # Flush whatever is pending.
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_len = 0
            for i in range(0, len(para), chunk_size):
                chunks.append(para[i : i + chunk_size])
            continue

        if current_len + len(para) > chunk_size and current_parts:
            chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_len = 0

        current_parts.append(para)
        current_len += len(para)

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def select_relevant_chunks(
    chunks: list[str],
    focus_keywords: list[str],
    max_chars: int = SELECT_MAX_CHARS,
) -> str:
    """Return a focused excerpt built from chunks that match the focus keywords.

    Chunks are scored by the number of distinct keywords that appear (case-
    insensitive). Top-scoring chunks are appended in their original document
    order until `max_chars` is reached. If no chunk matches any keyword, the
    first chunks up to `max_chars` are returned as a fallback.
    """
    if not chunks:
        return ""

    lower_keywords = [kw.lower() for kw in focus_keywords if kw]

    def _score(chunk: str) -> int:
        lower_chunk = chunk.lower()
        return sum(1 for kw in lower_keywords if kw in lower_chunk)

    scored = sorted(enumerate(chunks), key=lambda t: _score(t[1]), reverse=True)

    # Take top-scoring chunks, then restore original order before joining.
    selected_indices: list[int] = []
    total = 0
    for idx, chunk in scored:
        if total + len(chunk) > max_chars:
            break
        selected_indices.append(idx)
        total += len(chunk)
        if total >= max_chars:
            break

    if not selected_indices:
        # Fallback: no keyword match — return the leading chunks.
        fallback_parts: list[str] = []
        used = 0
        for chunk in chunks:
            if used + len(chunk) > max_chars:
                break
            fallback_parts.append(chunk)
            used += len(chunk)
        return "\n\n".join(fallback_parts)

    selected_indices.sort()
    return "\n\n".join(chunks[i] for i in selected_indices)