"""Atomic per-brief state writes to B2.

We persist the manifest after every stage so an interrupted pipeline leaves
a recoverable record. There is no DB — the bucket IS the archive. Writes
are last-writer-wins; the manifest is single-writer (one brief, one task).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.repo import b2_client
from app.types import BriefManifest


def manifest_key(brief_id: str) -> str:
    return f"briefs/{brief_id}/manifest.json"


def query_key(brief_id: str) -> str:
    return f"briefs/{brief_id}/query.json"


def brief_markdown_key(brief_id: str) -> str:
    return f"briefs/{brief_id}/brief.md"


def paper_pdf_key(arxiv_id: str) -> str:
    return f"papers/{arxiv_id}.pdf"


def paper_text_key(arxiv_id: str) -> str:
    return f"papers/{arxiv_id}.txt"


def save_manifest(manifest: BriefManifest) -> None:
    """Write the manifest to B2 with an updated timestamp."""
    manifest.updated_at = datetime.now(UTC)
    body = manifest.model_dump_json(indent=2)
    b2_client.put_text(
        manifest_key(manifest.brief_id),
        body,
        content_type="application/json; charset=utf-8",
    )


def load_manifest(brief_id: str) -> BriefManifest | None:
    """Read the manifest from B2, or None if it doesn't exist."""
    if not b2_client.object_exists(manifest_key(brief_id)):
        return None
    raw = b2_client.get_text(manifest_key(brief_id))
    data = json.loads(raw)
    return BriefManifest.model_validate(data)


def save_query(brief_id: str, payload: dict) -> None:
    b2_client.put_text(
        query_key(brief_id),
        json.dumps(payload, indent=2, default=str),
        content_type="application/json; charset=utf-8",
    )


def save_brief_markdown(brief_id: str, markdown: str) -> str:
    """Write the brief markdown body to B2 and return the storage key."""
    key = brief_markdown_key(brief_id)
    b2_client.put_text(key, markdown, content_type="text/markdown; charset=utf-8")
    return key
