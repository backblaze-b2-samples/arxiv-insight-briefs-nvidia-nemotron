"""Health + metrics smoke tests."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "b2_connected" in data
    assert "nvidia_configured" in data


@pytest.mark.asyncio
async def test_metrics_returns_200(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "briefs_total" in body
    assert "papers_cache_hits_total" in body
    assert "nemotron_tokens_total" in body
