"""Hermetic test fixtures.

The pipeline reaches three external surfaces: B2, NVIDIA, arxiv. We replace
each one at the repo boundary with an in-memory fake so the suite runs
fully offline and without secrets.
"""

from __future__ import annotations

# Defaults that satisfy `Settings()` startup validation in tests. Patched
# before importing `main` so the lifespan check doesn't trip.
import os
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("B2_REGION", "us-test-000")
os.environ.setdefault("B2_APPLICATION_KEY_ID", "test_key_id")
os.environ.setdefault("B2_APPLICATION_KEY", "test_application_key")
os.environ.setdefault("B2_BUCKET_NAME", "test-bucket")
os.environ.setdefault("B2_PUBLIC_URL_BASE", "https://f000.backblazeb2.com/file/test-bucket")


@pytest.fixture
def fake_b2(monkeypatch):
    """In-memory replacement for `app.repo.b2_client` and `job_state`.

    Returns the dict-backed store so tests can assert on writes.
    """
    from app.repo import b2_client

    store: dict[str, bytes] = {}

    def put_bytes(key: str, body: bytes, content_type: str = "application/octet-stream"):
        store[_full(key)] = body

    def put_text(key: str, body: str, content_type: str = "text/plain; charset=utf-8"):
        store[_full(key)] = body.encode("utf-8")

    def get_bytes(key: str) -> bytes:
        return store[_full(key)]

    def get_text(key: str) -> str:
        return store[_full(key)].decode("utf-8")

    def object_exists(key: str) -> bool:
        return _full(key) in store

    def head_object_or_none(key: str) -> dict | None:
        if _full(key) in store:
            return {"ContentLength": len(store[_full(key)])}
        return None

    def list_prefix(prefix: str, max_keys: int = 1000) -> list[dict]:
        full_prefix = _full(prefix)
        items: list[dict] = []
        for k, v in store.items():
            if k.startswith(full_prefix):
                items.append(
                    {
                        "key": _strip(k),
                        "size": len(v),
                        "last_modified": datetime.now(UTC),
                    }
                )
        return items[:max_keys]

    def delete_object(key: str) -> None:
        store.pop(_full(key), None)

    def delete_prefix(prefix: str) -> int:
        if not prefix or prefix in ("/", "arxiv-insight-briefs/"):
            raise ValueError("delete_prefix refuses to operate at the bucket root")
        full_prefix = _full(prefix)
        keys = [k for k in store if k.startswith(full_prefix)]
        for k in keys:
            del store[k]
        return len(keys)

    def presign_get(key: str, expires_in: int | None = None, filename: str | None = None) -> str:
        return f"https://fake-b2/{_full(key)}?expires={expires_in or 3600}"

    def check_connectivity() -> bool:
        return True

    def _full(key: str) -> str:
        return f"arxiv-insight-briefs/{key}"

    def _strip(key: str) -> str:
        return key.removeprefix("arxiv-insight-briefs/")

    for name, fn in {
        "put_bytes": put_bytes,
        "put_text": put_text,
        "get_bytes": get_bytes,
        "get_text": get_text,
        "object_exists": object_exists,
        "head_object_or_none": head_object_or_none,
        "list_prefix": list_prefix,
        "delete_object": delete_object,
        "delete_prefix": delete_prefix,
        "presign_get": presign_get,
        "check_connectivity": check_connectivity,
    }.items():
        monkeypatch.setattr(b2_client, name, fn)

    return store


@pytest.fixture
def fake_arxiv(monkeypatch):
    """In-memory replacement for `app.repo.arxiv_client`."""
    from app.repo import arxiv_client

    state: dict[str, Any] = {"results": [], "pdf_bytes": b"%PDF-1.4 fake pdf"}

    def search(categories, keywords, max_results, time_window_months):
        return state["results"][:max_results]

    def download_pdf(pdf_url: str) -> bytes:
        return state["pdf_bytes"]

    monkeypatch.setattr(arxiv_client, "search", search)
    monkeypatch.setattr(arxiv_client, "download_pdf", download_pdf)
    return state


@pytest.fixture
def fake_nemotron(monkeypatch):
    """In-memory replacement for `app.repo.nemotron_client`.

    Tests drive responses by appending to `responses` (consumed in order).
    Set `configured=False` to simulate a missing API key.
    """
    from app.repo import nemotron_client

    state = {"responses": [], "configured": True, "calls": []}

    def chat_completion(*, system, user, temperature=0.2, max_tokens=1500, response_format_json=False):
        if not state["configured"]:
            raise nemotron_client.NemotronNotConfigured("test: no key")
        state["calls"].append({"system": system, "user": user})
        if not state["responses"]:
            raise nemotron_client.NemotronError("test: no canned response left")
        text = state["responses"].pop(0)
        return {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    monkeypatch.setattr(nemotron_client, "chat_completion", chat_completion)
    return state


@pytest.fixture
def fake_pdf_extractor(monkeypatch):
    """Replace PyMuPDF extraction with deterministic synthetic text."""
    from app.repo import pdf_extractor

    def extract(pdf_bytes: bytes, max_chars: int) -> str:
        return ("Synthetic extracted text. " * 20)[:max_chars]

    monkeypatch.setattr(pdf_extractor, "extract_section_trimmed_text", extract)
    return None


@pytest.fixture
async def client(fake_b2):
    """FastAPI ASGI client. Requires fake_b2 so lifespan validation succeeds."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
