"""Document chunking utilities for the investment document review flow."""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SELECT_MAX_CHARS = 4000
CHUNK_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text with LangChain's recursive character splitter."""
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=min(CHUNK_OVERLAP, max(chunk_size - 1, 0)),
        separators=CHUNK_SEPARATORS,
        keep_separator=True,
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]


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
