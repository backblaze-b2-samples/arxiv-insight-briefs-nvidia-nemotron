"""Tests for `app.repo.arxiv_client` rate-limit handling.

The real retry policy uses 30s -> 240s exponential backoff, which would
make this suite useless in CI. We monkey-patch `wait_exponential` -> 0
so the retry semantics are exercised without actually sleeping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import arxiv
import httpx
import pytest
import tenacity

from app.repo import arxiv_client


def _zero_wait(monkeypatch):
    """Replace the tenacity wait on `_search_with_retry` and `download_pdf`
    with `wait_fixed(0)` so retries fire instantly in tests."""
    monkeypatch.setattr(
        arxiv_client._search_with_retry.retry, "wait", tenacity.wait_fixed(0)
    )
    monkeypatch.setattr(
        arxiv_client.download_pdf.retry, "wait", tenacity.wait_fixed(0)
    )


def _fake_paper():
    """Minimal duck-typed stand-in for `arxiv.Result`."""
    return SimpleNamespace(
        get_short_id=lambda: "2401.12345v1",
        title="Test Paper",
        authors=[SimpleNamespace(name="A. Researcher")],
        summary="Abstract goes here.",
        primary_category="cs.NI",
        published=datetime(2024, 1, 5, tzinfo=UTC),
        pdf_url="https://arxiv.org/pdf/2401.12345v1",
    )


def test_search_retries_on_429_then_succeeds(monkeypatch):
    """Two 429s followed by a real result: retry budget absorbs the throttle."""
    _zero_wait(monkeypatch)

    calls = {"n": 0}

    def fake_results(_search_obj):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise arxiv.HTTPError(url="https://export.arxiv.org/api", status=429, retry=calls["n"])
        # Third call succeeds — generators are consumed by `for ... in`
        return iter([_fake_paper()])

    monkeypatch.setattr(arxiv_client._client, "results", fake_results)

    papers = arxiv_client.search(
        categories=["cs.NI"], keywords=["quic"], max_results=10, time_window_months=12
    )

    assert len(papers) == 1
    assert papers[0]["arxiv_id"] == "2401.12345v1"
    assert calls["n"] == 3  # two failures + one success


def test_search_raises_rate_limit_error_after_budget(monkeypatch):
    """After the 4-attempt budget the wrapper raises `ArxivRateLimitError`."""
    _zero_wait(monkeypatch)

    def always_429(_search_obj):
        raise arxiv.HTTPError(url="https://export.arxiv.org/api", status=429, retry=1)

    monkeypatch.setattr(arxiv_client._client, "results", always_429)

    with pytest.raises(arxiv_client.ArxivRateLimitError):
        arxiv_client.search(
            categories=["cs.NI"], keywords=["quic"], max_results=10, time_window_months=12
        )


def test_search_translates_unexpected_empty_page(monkeypatch):
    """`UnexpectedEmptyPageError` is also treated as a rate-limit symptom."""
    _zero_wait(monkeypatch)

    def empty_page(_search_obj):
        raise arxiv.UnexpectedEmptyPageError(
            url="https://export.arxiv.org/api", retry=1, raw_feed=None
        )

    monkeypatch.setattr(arxiv_client._client, "results", empty_page)

    with pytest.raises(arxiv_client.ArxivRateLimitError):
        arxiv_client.search(
            categories=["cs.NI"], keywords=["quic"], max_results=10, time_window_months=12
        )


def test_download_pdf_retries_on_429(monkeypatch):
    """PDF endpoint 429s should also be retried with the same budget."""
    _zero_wait(monkeypatch)

    calls = {"n": 0}

    class FakeResponse:
        def __init__(self, status: int, content: bytes):
            self.status_code = status
            self.content = content

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "rate limited",
                    request=httpx.Request("GET", "https://arxiv.org/pdf/x"),
                    response=httpx.Response(self.status_code),
                )

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def get(self, _url):
            calls["n"] += 1
            if calls["n"] <= 2:
                return FakeResponse(429, b"")
            return FakeResponse(200, b"%PDF-1.4 fake")

    monkeypatch.setattr(arxiv_client.httpx, "Client", FakeClient)

    body = arxiv_client.download_pdf("https://arxiv.org/pdf/2401.12345v1")
    assert body == b"%PDF-1.4 fake"
    assert calls["n"] == 3
