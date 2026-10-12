from __future__ import annotations

from app.editorial import pipeline
from app.editorial.store import EditorialStore


def test_public_gate_requires_private_upload(tmp_path, monkeypatch):
    store = EditorialStore(str(tmp_path / "editorial.db"))
    monkeypatch.setattr(pipeline, "store", store)

    episode = pipeline.create_episode(
        "nexbrain", "Gate test", "AI workflow", "AI tools"
    )
    episode["state"] = "uploaded_private"
    episode["video_paths"] = ["/tmp/video.mp4"]
    store.save(episode)

    pipeline.approve_public(episode["id"], "final human approval")
    assert store.get(episode["id"])["state"] == "public_approved"

    pipeline.mark_public(episode["id"], "https://youtube.example/video")
    saved = store.get(episode["id"])
    assert saved["state"] == "published"
    assert saved["published_urls"] == ["https://youtube.example/video"]
