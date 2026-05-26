"""FastAPI test-client coverage for the briefings + papers routers."""

from datetime import UTC, datetime

import pytest

from app.repo import job_state
from app.types import BriefManifest, ResolvedQuery


def _manifest(brief_id: str, status: str = "done") -> BriefManifest:
    now = datetime.now(UTC)
    return BriefManifest(
        brief_id=brief_id,
        status=status,
        created_at=now,
        updated_at=now,
        question="q",
        resolved_query=ResolvedQuery(
            question="q",
            categories=["cs.NI"],
            keywords=["quic"],
            time_window_months=12,
        ),
    )


@pytest.mark.asyncio
async def test_get_briefing_404(client):
    resp = await client.get("/briefings/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_briefing_with_markdown(client, fake_b2):
    manifest = _manifest("abc123")
    job_state.save_manifest(manifest)
    job_state.save_brief_markdown(
        "abc123", "# Key Findings\n- Important [arxiv:2401.12345]\n"
    )
    # Also a known paper id so citation rewrite can present a link.
    manifest.brief_markdown_key = job_state.brief_markdown_key("abc123")
    from app.types import RankedPaper

    manifest.ranked_papers = [
        RankedPaper(
            arxiv_id="2401.12345",
            title="t",
            authors=["a"],
            abstract="abs",
            primary_category="cs.NI",
            published=datetime.now(UTC),
            pdf_url="https://arxiv.org/pdf/2401.12345",
        )
    ]
    job_state.save_manifest(manifest)
    # Place the PDF in the cache so presign succeeds.
    fake_b2[f"arxiv-insight-briefs/{job_state.paper_pdf_key('2401.12345')}"] = b"pdf"

    resp = await client.get("/briefings/abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["manifest"]["brief_id"] == "abc123"
    assert data["markdown"] is not None
    assert "fake-b2" in data["markdown"]  # citation rewritten to presigned URL


@pytest.mark.asyncio
async def test_list_briefings(client, fake_b2):
    job_state.save_manifest(_manifest("a"))
    job_state.save_manifest(_manifest("b"))
    resp = await client.get("/briefings")
    assert resp.status_code == 200
    data = resp.json()
    assert {row["brief_id"] for row in data} == {"a", "b"}


@pytest.mark.asyncio
async def test_cancel_briefing_marks_flag(client, fake_b2):
    job_state.save_manifest(_manifest("ccc", status="routing"))
    resp = await client.delete("/briefings/ccc?mode=cancel")
    assert resp.status_code == 204
    refreshed = job_state.load_manifest("ccc")
    assert refreshed.cancel_requested is True


@pytest.mark.asyncio
async def test_clear_briefing_deletes_prefix(client, fake_b2):
    job_state.save_manifest(_manifest("ddd"))
    job_state.save_brief_markdown("ddd", "# body")
    resp = await client.delete("/briefings/ddd?mode=clear")
    assert resp.status_code == 204
    assert job_state.load_manifest("ddd") is None


@pytest.mark.asyncio
async def test_presign_paper_404_when_uncached(client, fake_b2):
    resp = await client.get("/papers/9999.0000/presign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_presign_paper_when_cached(client, fake_b2):
    fake_b2[f"arxiv-insight-briefs/{job_state.paper_pdf_key('2401.99999')}"] = b"pdf"
    resp = await client.get("/papers/2401.99999/presign")
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("https://fake-b2/")


@pytest.mark.asyncio
async def test_submit_briefing_returns_brief_id(client, fake_b2, fake_arxiv, fake_nemotron):
    # Configure responses so the background task can finish (it won't block
    # the response, but we don't want the slot semaphore leaking).
    fake_nemotron["configured"] = False
    fake_arxiv["results"] = []
    resp = await client.post(
        "/briefings",
        json={"question": "how do we send files faster?", "time_window_months": 6},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "brief_id" in data
