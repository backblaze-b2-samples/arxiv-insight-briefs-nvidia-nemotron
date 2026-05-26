"""topic_router tests — taxonomy validation + LLM fallback paths."""

import json

from app.service import topic_router


def test_valid_llm_response(fake_nemotron):
    fake_nemotron["responses"].append(
        json.dumps(
            {
                "categories": ["cs.NI", "cs.DC"],
                "keywords": ["quic", "file transfer"],
                "time_window_months": 6,
            }
        )
    )
    resolved = topic_router.resolve_query("how do we send files faster?", None)
    assert resolved.categories == ["cs.NI", "cs.DC"]
    assert "quic" in resolved.keywords
    assert resolved.time_window_months == 6
    assert resolved.fallback_used is False
    assert resolved.warnings == []


def test_drops_invalid_categories(fake_nemotron):
    fake_nemotron["responses"].append(
        json.dumps(
            {
                "categories": ["cs.NI", "cs.AGI", "cs.WTF"],
                "keywords": ["bbr"],
                "time_window_months": 12,
            }
        )
    )
    resolved = topic_router.resolve_query("congestion control", None)
    assert resolved.categories == ["cs.NI"]
    assert any("cs.AGI" in w for w in resolved.warnings)


def test_all_invalid_falls_back_to_cs_prefix(fake_nemotron):
    fake_nemotron["responses"].append(
        json.dumps(
            {"categories": ["cs.AGI"], "keywords": ["foo"], "time_window_months": 12}
        )
    )
    resolved = topic_router.resolve_query("anything", None)
    assert resolved.categories == ["cs"]


def test_no_nvidia_key_uses_keyword_fallback(fake_nemotron):
    fake_nemotron["configured"] = False
    resolved = topic_router.resolve_query(
        "how does QUIC handle congestion in mobile networks", 24
    )
    assert resolved.fallback_used is True
    assert resolved.categories == ["cs"]
    assert resolved.time_window_months == 24
    # Naive keyword extraction must drop stopwords and dedupe.
    assert "the" not in resolved.keywords
    assert len(resolved.keywords) <= 6


def test_non_json_response_falls_back(fake_nemotron):
    fake_nemotron["responses"].append("not json")
    resolved = topic_router.resolve_query("anything at all", None)
    assert resolved.fallback_used is True
