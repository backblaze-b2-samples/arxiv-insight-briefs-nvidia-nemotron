"""File-browser orchestration — list, lookup, delete, presign.

Sits between the `/files/*` runtime layer and the B2 repo. Translates
generic S3 list rows into `FileMetadata`, and validates user-supplied
object keys before any B2 call.

Layer rules: no boto3 here (only in `app.repo.b2_client`); no LLM /
arxiv calls.

This module is unguarded by design — per user request, the file browser
can delete anything under the sample's B2 prefix, including the cached
`papers/` PDFs. If you re-introduce protection later, do it here (one
place to maintain).
"""

from __future__ import annotations

import logging
import mimetypes
import re

from app.repo import b2_client
from app.types import FileMetadata
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

# Refuses keys that look like path-traversal attempts. Keys are URL-encoded
# in the request path; this is a defense-in-depth check on the decoded form.
_DANGEROUS_KEY_RE = re.compile(r"(\.\./|/\.\.|\\|%2e%2e|%00|\x00)")


class FileKeyError(Exception):
    """Raised when an object key is empty or contains a traversal pattern."""

    def __init__(self, detail: str = "Invalid file key"):
        self.detail = detail
        super().__init__(detail)


class FileNotFoundError(Exception):
    """Raised when the requested object isn't in B2."""

    def __init__(self, detail: str = "File not found"):
        self.detail = detail
        super().__init__(detail)


def validate_key(key: str) -> None:
    if not key:
        raise FileKeyError()
    if _DANGEROUS_KEY_RE.search(key.lower()):
        raise FileKeyError()


def _guess_content_type(key: str) -> str:
    mime, _ = mimetypes.guess_type(key)
    return mime or "application/octet-stream"


def _split_key(key: str) -> tuple[str, str]:
    """(folder, filename) split. Root-level keys return ("", key)."""
    parts = key.rsplit("/", 1)
    if len(parts) == 2:
        return parts[0] + "/", parts[1]
    return "", parts[0]


def list_files(prefix: str = "", limit: int = 100) -> list[FileMetadata]:
    """List objects under `prefix`, newest first."""
    if limit < 1 or limit > 1000:
        raise ValueError("Limit must be between 1 and 1000")
    # S3 list_objects_v2 returns lexicographic order — fetch a full batch
    # and sort newest-first ourselves before slicing.
    raw = b2_client.list_prefix(prefix, max_keys=1000)
    files: list[FileMetadata] = []
    for row in raw:
        folder, filename = _split_key(row["key"])
        files.append(
            FileMetadata(
                key=row["key"],
                filename=filename,
                folder=folder,
                size_bytes=row["size"],
                size_human=humanize_bytes(row["size"]),
                content_type=_guess_content_type(row["key"]),
                uploaded_at=row["last_modified"],
            )
        )
    files.sort(key=lambda f: f.uploaded_at, reverse=True)
    return files[:limit]


def get_file(key: str) -> FileMetadata:
    """Return metadata for one object. Raises `FileNotFoundError` on miss."""
    validate_key(key)
    head = b2_client.head_object_or_none(key)
    if head is None:
        raise FileNotFoundError()
    folder, filename = _split_key(key)
    return FileMetadata(
        key=key,
        filename=filename,
        folder=folder,
        size_bytes=head.get("ContentLength", 0),
        size_human=humanize_bytes(head.get("ContentLength", 0)),
        content_type=head.get("ContentType", _guess_content_type(key)),
        uploaded_at=head.get("LastModified") or b2_client.now_utc(),
    )


def get_download_url(key: str) -> str:
    """Presigned GET URL with an attachment disposition for browser download."""
    validate_key(key)
    head = b2_client.head_object_or_none(key)
    if head is None:
        raise FileNotFoundError()
    _, filename = _split_key(key)
    return b2_client.presign_get(key, filename=filename)


def get_preview_url(key: str) -> str:
    """Presigned URL for inline preview (no attachment disposition)."""
    validate_key(key)
    head = b2_client.head_object_or_none(key)
    if head is None:
        raise FileNotFoundError()
    return b2_client.presign_get(key)


def remove_file(key: str) -> None:
    """Delete the object. No guard on `papers/` — matches starter behavior."""
    validate_key(key)
    b2_client.delete_object(key)
