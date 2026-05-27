"""FastAPI test-client coverage for the restored file-browser router.

All hermetic — exercises the `/files/*` endpoints against the in-memory
`fake_b2` fixture from `conftest.py`. Includes a focused test confirming
the "full CRUD, no guard" contract: `papers/` objects can be deleted.
"""

from __future__ import annotations

import pytest


def _seed(fake_b2: dict[str, bytes]) -> None:
    """Drop a handful of representative objects into the fake bucket."""
    fake_b2["arxiv-insight-briefs/papers/2401.12345v1.pdf"] = b"%PDF-1.4 fake paper"
    fake_b2["arxiv-insight-briefs/papers/2401.12345v1.txt"] = b"extracted text"
    fake_b2["arxiv-insight-briefs/briefs/abc/manifest.json"] = b"{}"
    fake_b2["arxiv-insight-briefs/briefs/abc/brief.md"] = b"# brief\n"


@pytest.mark.asyncio
async def test_list_files_no_prefix_returns_everything(client, fake_b2):
    _seed(fake_b2)

    resp = await client.get("/files")
    assert resp.status_code == 200
    data = resp.json()
    keys = {row["key"] for row in data}
    # Keys are stripped of the bucket-level prefix by `list_prefix`.
    assert "papers/2401.12345v1.pdf" in keys
    assert "briefs/abc/manifest.json" in keys
    assert len(data) == 4


@pytest.mark.asyncio
async def test_list_files_with_prefix_filters(client, fake_b2):
    _seed(fake_b2)

    resp = await client.get("/files?prefix=papers/")
    assert resp.status_code == 200
    data = resp.json()
    assert all(row["key"].startswith("papers/") for row in data)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_file_metadata_returns_head_fields(client, fake_b2):
    _seed(fake_b2)

    resp = await client.get("/files/papers/2401.12345v1.pdf/metadata")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "2401.12345v1.pdf"
    assert body["size_bytes"] == len(b"%PDF-1.4 fake paper")
    assert body["extension"] == "pdf"


@pytest.mark.asyncio
async def test_get_file_metadata_missing_is_404(client, fake_b2):
    _seed(fake_b2)

    resp = await client.get("/files/papers/does-not-exist.pdf/metadata")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_redirects_to_presigned_url(client, fake_b2):
    _seed(fake_b2)

    # Don't follow the redirect — we want to assert the 302 + Location.
    resp = await client.get(
        "/files/papers/2401.12345v1.pdf/download", follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://fake-b2/")
    assert "papers/2401.12345v1.pdf" in resp.headers["location"]


@pytest.mark.asyncio
async def test_delete_removes_object(client, fake_b2):
    _seed(fake_b2)

    resp = await client.delete("/files/briefs/abc/brief.md")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True
    assert "arxiv-insight-briefs/briefs/abc/brief.md" not in fake_b2


@pytest.mark.asyncio
async def test_delete_papers_object_is_allowed_no_guard(client, fake_b2):
    """The user explicitly requested no protection on the `papers/` prefix.
    This is the contract test for that choice."""
    _seed(fake_b2)

    full_key = "arxiv-insight-briefs/papers/2401.12345v1.pdf"
    assert full_key in fake_b2  # sanity

    resp = await client.delete("/files/papers/2401.12345v1.pdf")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert full_key not in fake_b2


@pytest.mark.asyncio
async def test_delete_invalid_key_rejected(client, fake_b2):
    resp = await client.delete("/files/..%2Fetc%2Fpasswd")
    # FastAPI URL-decodes before our regex sees it — the dangerous pattern
    # is caught by `validate_key`.
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_file_returns_metadata(client, fake_b2):
    _seed(fake_b2)

    resp = await client.get("/files/briefs/abc/brief.md")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "brief.md"
    assert body["folder"] == "briefs/abc/"


@pytest.mark.asyncio
async def test_empty_bucket_returns_empty_list(client, fake_b2):
    resp = await client.get("/files")
    assert resp.status_code == 200
    assert resp.json() == []
