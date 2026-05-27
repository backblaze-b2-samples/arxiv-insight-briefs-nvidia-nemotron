"""Detail metadata for an object — head-object only, no body fetch.

The starter ships rich Image (Pillow) and PDF (PyPDF2) metadata
extraction. This sample deliberately drops those dependencies (we already
use PyMuPDF for paper extraction in the briefing pipeline; introducing a
second PDF stack just for the file browser is wasted complexity).

The detail panel therefore shows what `HeadObject` returns and nothing
more. The UI degrades gracefully — image/PDF blocks render
"no detailed metadata available" for those mime types.
"""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime

from app.repo import b2_client
from app.service.files import FileKeyError, FileNotFoundError, validate_key
from app.types import FileMetadataDetail
from app.types.formatting import humanize_bytes


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def get_metadata(key: str) -> FileMetadataDetail:
    """Read HeadObject for `key` and project it onto `FileMetadataDetail`.

    Raises `FileKeyError` for bad keys, `FileNotFoundError` for misses.
    """
    validate_key(key)
    head = b2_client.head_object_or_none(key)
    if head is None:
        raise FileNotFoundError()

    filename = key.rsplit("/", 1)[-1]
    size = int(head.get("ContentLength", 0))
    content_type = head.get("ContentType") or mimetypes.guess_type(key)[0] or "application/octet-stream"
    last_modified = head.get("LastModified") or datetime.now(UTC)
    etag = head.get("ETag")
    if isinstance(etag, str):
        etag = etag.strip('"')

    return FileMetadataDetail(
        filename=filename,
        size_bytes=size,
        size_human=humanize_bytes(size),
        mime_type=content_type,
        extension=_extension(filename),
        uploaded_at=last_modified,
        etag=etag,
    )


__all__ = ["FileKeyError", "FileNotFoundError", "get_metadata"]
