"""PDF text extraction utility for the gateway layer."""

from __future__ import annotations

import io
import re


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF byte payload.

    Pages are concatenated in order. Blank lines are collapsed to a single
    blank line.

    Raises:
        ValueError: if the PDF cannot be opened or yields no extractable text.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is not installed") from exc

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages: list[str] = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
    except Exception as exc:
        raise ValueError(f"Failed to open or parse PDF: {exc}") from exc

    if not pages:
        raise ValueError("No extractable text found in the PDF.")

    combined = "\n\n".join(pages)
    # Collapse runs of 3+ blank lines down to two.
    combined = re.sub(r"\n{3,}", "\n\n", combined)

    return combined
