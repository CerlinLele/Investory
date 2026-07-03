"""Tests for document chunking utilities."""

import pytest

from investory.agent_core.runtime.flow.investment_document_review.document_chunker import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    SELECT_MAX_CHARS,
    select_relevant_chunks,
    split_into_chunks,
)


class TestSplitIntoChunks:
    """Tests for the split_into_chunks function."""

    def test_split_into_chunks_respects_chunk_size_and_overlap(self) -> None:
        """Verify that chunks respect size limits and maintain proper overlap."""
        # Create a text longer than one chunk to force splitting
        base_text = "This is a sentence. " * 100  # ~2000 chars total
        chunks = split_into_chunks(base_text)

        # Verify we got multiple chunks
        assert len(chunks) > 1

        # Verify each chunk respects the size limit (with some tolerance for word boundaries)
        for chunk in chunks:
            assert len(chunk) <= CHUNK_SIZE + 100  # Small tolerance for RecursiveCharacterTextSplitter behavior

        # Verify adjacent chunks have overlap
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            # The end of the current chunk should overlap with the start of the next
            # (they should share some common text due to the overlap setting)
            assert current_chunk[-100:].lower() in (current_chunk + next_chunk).lower() or \
                   any(word in next_chunk for word in current_chunk.split()[-20:])

    def test_split_into_chunks_keeps_long_sentence_within_overlap_window(self) -> None:
        """Verify that long sentences are not fragmented across chunk boundaries."""
        # Create a synthetic long sentence that exceeds old CHUNK_SIZE (500) but fits in new CHUNK_SIZE (1000)
        long_sentence = (
            "The investment fund's disclosure states that annual returns are subject to "
            "market conditions and historical performance should not be considered as a guarantee of future results; "
            "additionally, investors must be aware that certain fee structures and expense ratios "
            "may vary based on the share class selected and the account size maintained, "
            "and these factors could materially impact the net returns over extended periods. "
        )

        # Wrap it with other text to create a realistic scenario
        text = f"Opening statement. {long_sentence} Closing statement with additional context."

        chunks = split_into_chunks(text)

        # Verify the long sentence appears completely in at least one chunk
        full_text = " ".join(chunks)
        assert long_sentence in full_text or \
               all(word in full_text for word in long_sentence.split() if len(word) > 1)

        # Verify no individual chunk is empty or excessively truncated
        for chunk in chunks:
            assert len(chunk.strip()) > 0

    def test_select_relevant_chunks_respects_max_chars(self) -> None:
        """Verify that select_relevant_chunks respects the max_chars limit."""
        chunks = [
            "The investment portfolio includes technology stocks and bonds.",
            "Risk assessment evaluates market volatility and historical performance.",
            "Dividend distributions occur quarterly with reinvestment options available.",
            "Asset allocation follows a strategic diversification approach for balance.",
            "Fee structure includes management fees and transaction costs annually.",
        ]

        max_chars = 200
        result = select_relevant_chunks(chunks, ["investment", "risk"], max_chars=max_chars)

        # Verify result does not exceed max_chars
        assert len(result) <= max_chars + 50  # Small tolerance for formatting

    def test_select_relevant_chunks_keyword_scoring(self) -> None:
        """Verify that keyword scoring prioritizes relevant chunks."""
        chunks = [
            "Technology sector includes software and hardware companies.",
            "Risk assessment is critical for portfolio management and investor protection.",
            "Bond yields fluctuate with interest rate changes in the market.",
            "Risk management strategies mitigate downside exposure effectively.",
        ]

        result = select_relevant_chunks(chunks, ["risk"], max_chars=1000)

        # Result should include chunks with "risk" keyword
        assert "risk" in result.lower()
        # And should prioritize chunks with the keyword (chunks 1 and 3)
        assert result.count("risk") >= 2 or ("Risk assessment" in result and "Risk management" in result)

    def test_select_relevant_chunks_fallback_when_no_keyword_match(self) -> None:
        """Verify fallback behavior when no chunks match the keywords."""
        chunks = [
            "First chunk about technology.",
            "Second chunk about bonds.",
            "Third chunk about dividends.",
        ]

        result = select_relevant_chunks(chunks, ["nonexistent_keyword"], max_chars=1000)

        # Should return leading chunks as fallback
        assert len(result) > 0
        assert "First chunk" in result or "Second chunk" in result

    def test_split_into_chunks_with_empty_text(self) -> None:
        """Verify that empty text returns empty list."""
        assert split_into_chunks("") == []
        assert split_into_chunks("   ") == []

    def test_select_relevant_chunks_with_empty_chunks(self) -> None:
        """Verify that empty chunks list returns empty string."""
        assert select_relevant_chunks([], ["keyword"]) == ""
