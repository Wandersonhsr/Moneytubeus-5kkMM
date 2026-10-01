from __future__ import annotations

from app.editorial.agent import build_opportunities, score_source
from app.editorial.pipeline import load_channels
from app.editorial.qa import run_package_qa


def test_opportunity_scoring_prefers_fresh_relevant_sources():
    channel = load_channels()["nexbrain"]
    fresh = {
        "url": "https://blog.google/example",
        "title": "New AI agent automation model",
        "summary": "A new AI agent changes coding and enterprise automation.",
        "publisher": "blog.google",
        "published_at": "2099-01-01T00:00:00+00:00",
    }
    stale = {
        "url": "https://example.com/old",
        "title": "Gardening tips",
        "summary": "How to grow tomatoes.",
        "publisher": "example.com",
        "published_at": "2020-01-01T00:00:00+00:00",
    }
    assert score_source(fresh, channel)["score"] > score_source(stale, channel)["score"]


def test_build_opportunities_deduplicates():
    sources = [
        {"url":"https://example.com/a","title":"AI agents","summary":"AI automation","publisher":"example.com"},
        {"url":"https://example.com/a","title":"AI agents","summary":"AI automation","publisher":"example.com"},
        {"url":"https://example.com/b","title":"AI chips","summary":"AI infrastructure","publisher":"example.com"},
    ]
    result = build_opportunities("nexbrain", sources, limit=10)
    assert len(result) == 2
    assert result[0]["status"] == "candidate"


def test_qa_blocks_missing_summary_and_sources():
    channel = load_channels()["capital-signal"]
    package = {
        "title": "A long enough title about markets and macro systems",
        "script": "word " * 1200,
        "description": "Wrong first line.",
        "summary": "Unique summary.",
        "tags": ["markets"] * 6,
        "research": [{"url":"https://example.com/source","title":"One"}],
    }
    qa = run_package_qa(package, channel, package)
    assert qa["passed"] is False
    checks = {item["check"]: item for item in qa["checks"]}
    assert checks["unique_summary_first_lines"]["passed"] is False
    assert checks["research_depth"]["passed"] is False
