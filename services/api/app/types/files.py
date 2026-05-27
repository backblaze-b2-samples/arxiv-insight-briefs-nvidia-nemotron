"""File-browser response models — keep in sync with packages/shared/src/types.ts.

These are *generic* bucket-object models used by the file explorer page.
Briefing-specific models live in `app/types/briefings.py`.

The arxiv-insight-briefs sample restored this view per user request after
the first-run smoke test (initial scaffold had trimmed it). The browser
is intentionally unguarded — it can delete anything under the configured
B2 prefix, including cached `papers/` PDFs. See `docs/features/file-browser.md`.
"""

from datetime import datetime

from pydantic import BaseModel


class FileMetadata(BaseModel):
    """Lightweight per-object record used by list/preview/detail views."""

    key: str
    filename: str
    folder: str
    size_bytes: int
    size_human: str
    content_type: str
    uploaded_at: datetime
    url: str | None = None


class FileMetadataDetail(BaseModel):
    """Detail-view model surfaced by `GET /files/{key}/metadata`.

    The starter ships richer Image/PDF metadata fields populated by
    Pillow + PyPDF2; those deps are NOT in this sample's
    requirements.txt, so the corresponding fields here are always `None`.
    The frontend renders "no detailed metadata available" when the
    image / PDF blocks are empty.
    """

    filename: str
    size_bytes: int
    size_human: str
    mime_type: str
    extension: str
    uploaded_at: datetime
    etag: str | None = None
