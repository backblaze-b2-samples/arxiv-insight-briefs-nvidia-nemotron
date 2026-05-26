"""synthesis tests — prompt shape + skeleton fallback."""

from app.service import synthesis
from app.service.prompts import SYNTHESIS_SYSTEM, build_synthesis_user


def test_paper_envelope_in_user_prompt():
    user = build_synthesis_user(
        "How does X work?",
        [("2401.12345", "Paper body one."), ("2403.55555", "Paper body two.")],
    )
    assert "<question>" in user
    assert "How does X work?" in user
    assert '<paper id="2401.12345">' in user
    assert '<paper id="2403.55555">' in user
    # System prompt must explicitly call out the untrusted content posture.
    assert "untrusted" in SYNTHESIS_SYSTEM.lower()


def test_synthesize_returns_markdown_and_usage(fake_nemotron):
    fake_nemotron["responses"].append(
        "# Key Findings\n- Finding [arxiv:2401.12345]\n"
    )
    body, usage = synthesis.synthesize("q", [("2401.12345", "text")])
    assert body is not None
    assert "Key Findings" in body
    assert usage["total_tokens"] == 15


def test_synthesize_returns_none_without_key(fake_nemotron):
    fake_nemotron["configured"] = False
    body, usage = synthesis.synthesize("q", [("2401.12345", "text")])
    assert body is None
    assert usage == {}


def test_no_analysis_brief_lists_candidates():
    body = synthesis.build_no_analysis_brief(
        "q",
        [
            ("2401.12345", "Title One", "Abstract one"),
            ("2403.55555", "Title Two", "Abstract two"),
        ],
    )
    assert "Title One" in body
    assert "arxiv:2401.12345" in body


def test_no_results_brief_echoes_question():
    body = synthesis.build_no_results_brief("the question")
    assert "the question" in body
