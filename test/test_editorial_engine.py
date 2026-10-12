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


def test_content_engine_builds_full_package(monkeypatch):
    from app.editorial import content_engine

    script = ("AI systems are changing how companies work. " * 140).strip()
    monkeypatch.setattr(content_engine.llm, "generate_script", lambda **kwargs: script)
    research = [
        {"url": "https://blog.google/source", "title": "Google AI", "publisher": "blog.google", "summary": "Documented AI development.", "published_at": "2099-01-01T00:00:00+00:00"},
        {"url": "https://microsoft.com/source", "title": "Microsoft AI", "publisher": "microsoft.com", "summary": "Documented agent development.", "published_at": "2099-01-01T00:00:00+00:00"},
        {"url": "https://example.com/source", "title": "Research source", "publisher": "example.com", "summary": "Independent context.", "published_at": "2099-01-01T00:00:00+00:00"},
    ]
    package = content_engine.generate_package(
        "nexbrain",
        "AI Agents Are Changing How Companies Work",
        "AI agents and enterprise automation",
        research,
        "The visible product is only the first layer.",
    )
    assert package["summary"]
    assert package["description"].startswith(package["summary"])
    assert len(package["title_variants"]) == 5
    assert package["visual_beats"]
    assert package["thumbnail_brief"]
    assert package["qa"]["passed"] is True


def test_dashboard_snapshot_exposes_human_gates(tmp_path, monkeypatch):
    from app.editorial import pipeline
    from app.editorial.store import EditorialStore

    store = EditorialStore(str(tmp_path / "editorial.db"))
    monkeypatch.setattr(pipeline, "store", store)
    pipeline.create_episode("nexbrain", "Dashboard test", "AI agents")
    snapshot = pipeline.dashboard_snapshot()
    assert snapshot["totals"]["episodes"] == 1
    assert snapshot["human_gates"]["public_auto_publish"] is False
    assert snapshot["queue"][0]["state"] == "idea"
