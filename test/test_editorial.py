from __future__ import annotations

from app.editorial import pipeline
from app.editorial.store import EditorialStore


def _episode(store: EditorialStore, monkeypatch) -> dict:
    monkeypatch.setattr(pipeline, "store", store)
    return pipeline.create_episode(
        "nexbrain", "Test episode", "AI workflow", "AI tools"
    )


def test_editorial_state_gate_and_approval(tmp_path, monkeypatch):
    store = EditorialStore(str(tmp_path / "editorial.db"))
    episode = _episode(store, monkeypatch)

    pipeline.attach_research(
        episode["id"],
        [{"url": "https://example.com/source", "title": "Source"}],
    )
    pipeline.attach_script(
        episode["id"],
        "A factual script.",
        "A unique summary of this episode.",
        ["ai", "automation"],
    )

    episode = store.get(episode["id"])
    episode["state"] = "review"
    episode["video_paths"] = ["/tmp/video.mp4"]
    store.save(episode)

    pipeline.review(episode["id"], True, "human reviewed")
    assert store.get(episode["id"])["state"] == "approved"
    assert store.get(episode["id"])["publish_approved"] is True


def test_placeholder_blocks_approval(tmp_path, monkeypatch):
    store = EditorialStore(str(tmp_path / "editorial.db"))
    episode = _episode(store, monkeypatch)
    episode["state"] = "review"
    episode["video_paths"] = ["/tmp/video.mp4"]
    episode["description"] = "Summary [SOURCES]"
    store.save(episode)

    try:
        pipeline.review(episode["id"], True)
    except pipeline.EditorialError as exc:
        assert "placeholder" in str(exc)
    else:
        raise AssertionError("placeholder should block approval")


def test_learning_snapshot(tmp_path, monkeypatch):
    store = EditorialStore(str(tmp_path / "editorial.db"))
    episode = _episode(store, monkeypatch)
    episode["state"] = "published"
    episode["metrics"] = {"views": 1000, "ctr": 5.0}
    store.save(episode)

    snapshot = pipeline.learning_snapshot("nexbrain")
    assert snapshot["measured_episodes"] == 1
    assert snapshot["averages"]["views"] == 1000.0
    assert snapshot["averages"]["ctr"] == 5.0
