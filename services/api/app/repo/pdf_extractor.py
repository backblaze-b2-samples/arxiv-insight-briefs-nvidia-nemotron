"""PyMuPDF wrapper — keeps section-trim logic isolated from the service layer.

PyMuPDF (`pymupdf`) is AGPL-licensed; documented in README.
"""

from __future__ import annotations

import io
import re

import pymupdf

# Common section headers we want to drop from extracted text. Order matters
# only insofar as the heuristic looks for the *first* match; downstream content
# is truncated. References / acknowledgments / appendices rarely carry signal
# for an insight brief and inflate the token bill.
_DROP_AFTER = re.compile(
    r"(?im)^\s*(references|bibliography|acknowledg(e?)ments?|appendix|appendices)\b",
)


def extract_section_trimmed_text(pdf_bytes: bytes, max_chars: int) -> str:
    """Extract text from a PDF and drop the references/appendix tail.

    Returns plain text. PyMuPDF's `get_text("text")` keeps reading order
    reasonably well; for an insight brief that's good enough — we are not
    trying to reconstruct figures or tables.
    """
    doc = pymupdf.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    try:
        chunks: list[str] = []
        for page in doc:
            chunks.append(page.get_text("text"))
        raw = "\n".join(chunks)
    finally:
        doc.close()

    trimmed = _trim_after_references(raw)
    # Collapse runs of blank lines (PyMuPDF often emits many) and hard-cap length.
    compact = re.sub(r"\n{3,}", "\n\n", trimmed).strip()
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + "\n\n[truncated]"
    return compact


def _trim_after_references(text: str) -> str:
    match = _DROP_AFTER.search(text)
    if match:
        return text[: match.start()]
    return text
