from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from app.config import config
from app.controllers.manager.memory_manager import InMemoryTaskManager
from app.controllers.manager.redis_manager import RedisTaskManager
from app.models.schema import VideoParams
from app.services import state as sm
from app.services import task as tm
from app.services import upload_post
from .research import collect
from .store import store

STATES = (
    "idea", "researched", "scripted", "generated", "review",
    "approved", "uploaded_private", "public_approved", "published", "measured", "learning", "rejected", "failed",
)


class EditorialError(RuntimeError):
    pass


def utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def load_channels() -> dict[str, dict[str, Any]]:
    path = os.path.join(os.path.dirname(__file__), "channels.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["channels"]


def _build_task_manager():
    app_cfg = config.app
    if app_cfg.get("enable_redis", False):
        password = app_cfg.get("redis_password") or None
        host = app_cfg.get("redis_host", "localhost")
        port = int(app_cfg.get("redis_port", 6379))
        db = int(app_cfg.get("redis_db", 0))
        redis_url = (
            f"redis://:{password}@{host}:{port}/{db}"
            if password else f"redis://{host}:{port}/{db}"
        )
        return RedisTaskManager(
            max_concurrent_tasks=int(app_cfg.get("max_concurrent_tasks", 5)),
            redis_url=redis_url,
            max_queued_tasks=int(app_cfg.get("max_queued_tasks", 100)),
        )
    return InMemoryTaskManager(
        max_concurrent_tasks=int(app_cfg.get("max_concurrent_tasks", 5)),
        max_queued_tasks=int(app_cfg.get("max_queued_tasks", 100)),
    )


_task_manager = _build_task_manager()


def create_episode(
    channel: str, title: str, topic: str, pillar: str = "", hook: str = ""
) -> dict:
    channels = load_channels()
    if channel not in channels:
        raise EditorialError(f"unknown channel: {channel}")
    episode = {
        "id": f"ep_{uuid.uuid4().hex[:12]}",
        "channel": channel,
        "title": title,
        "topic": topic,
        "pillar": pillar,
        "state": "idea",
        "hook": hook,
        "script": "",
        "description": "",
        "tags": [],
        "research": [],
        "motor_task_id": "",
        "video_paths": [],
        "review_notes": "",
        "publish_approved": False,
        "published_urls": [],
        "publish_results": [],
        "metrics": {},
        "opportunity": {},
        "content_package": {},
        "qa": {},
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    return store.save(episode)


def transition(episode: dict, state: str) -> dict:
    if state not in STATES:
        raise EditorialError(f"invalid state: {state}")
    episode["state"] = state
    episode["updated_at"] = utcnow()
    return store.save(episode)


def attach_research(episode_id: str, sources: list[dict]) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if not sources:
        raise EditorialError("research packet cannot be empty")
    episode["research"] = sources
    return transition(episode, "researched")


def collect_research(episode_id: str) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    channel = load_channels()[episode["channel"]]
    sources = collect(episode["topic"], channel.get("research_feeds", []))
    if not sources:
        raise EditorialError("no research sources were collected")
    return attach_research(episode_id, sources)


def attach_script(
    episode_id: str, script: str, description: str, tags: list[str] | None = None
) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "researched":
        raise EditorialError("research must be completed before scripting")
    if not script.strip() or not description.strip():
        raise EditorialError("script and description are required")
    episode.update(
        {"script": script, "description": description, "tags": tags or []}
    )
    return transition(episode, "scripted")


def attach_package(episode_id: str, package: dict[str, Any]) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "researched":
        raise EditorialError("research must be completed before content packaging")
    if not package.get("script") or not package.get("description"):
        raise EditorialError("content package must contain script and description")
    episode.update(
        {
            "title": package.get("title") or episode["title"],
            "hook": package.get("hook") or episode.get("hook", ""),
            "script": package["script"],
            "description": package["description"],
            "tags": package.get("tags", []),
            "content_package": package,
            "qa": package.get("qa", {}),
        }
    )
    return transition(episode, "scripted")


def attach_opportunity(episode_id: str, opportunity: dict[str, Any]) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    episode["opportunity"] = opportunity
    episode["title"] = opportunity.get("title") or episode["title"]
    episode["topic"] = opportunity.get("topic") or episode["topic"]
    episode["hook"] = opportunity.get("hook") or episode.get("hook", "")
    episode["updated_at"] = utcnow()
    return store.save(episode)


def generate(episode_id: str) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "scripted":
        raise EditorialError("episode must be scripted before generation")

    channel = load_channels()[episode["channel"]]
    params = VideoParams(
        video_subject=episode["title"],
        video_script=episode["script"],
        video_language=channel["language"],
        video_aspect=channel["video_aspect"],
        video_source=channel["video_source"],
        subtitle_enabled=channel["subtitle_enabled"],
        voice_name=channel["voice_name"],
        video_count=1,
    )
    task_id = f"editorial_{uuid.uuid4().hex}"
    sm.state.update_task(task_id)
    try:
        _task_manager.add_task(
            tm.start, task_id=task_id, params=params, stop_at="video"
        )
    except Exception:
        sm.state.delete_task(task_id)
        raise

    episode["motor_task_id"] = task_id
    return transition(episode, "generated")


def sync_generation(episode_id: str) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    task_id = episode.get("motor_task_id")
    if not task_id:
        raise EditorialError("motor task not started")

    task = sm.state.get_task(task_id)
    if not task:
        raise EditorialError("motor task not found")

    if task.get("state") == -1:
        episode["state"] = "failed"
        episode["review_notes"] = task.get("error", "generation failed")
    elif task.get("state") == 1:
        episode["video_paths"] = (
            task.get("videos") or task.get("combined_videos") or []
        )
        if not episode["video_paths"]:
            episode["state"] = "failed"
            episode["review_notes"] = "motor reported completion without a video"
        else:
            episode["state"] = "review"
    episode["updated_at"] = utcnow()
    return store.save(episode)


def review(episode_id: str, approved: bool, notes: str = "") -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "review":
        raise EditorialError("episode is not awaiting review")

    if approved:
        if not episode.get("video_paths"):
            raise EditorialError("generated video is required before approval")
        placeholder = re.compile(r"\[[A-Za-z][A-Za-z0-9 _-]{2,}\]")
        if placeholder.search(episode["description"]) or placeholder.search(
            episode.get("script", "")
        ):
            raise EditorialError("replace bracket placeholders before approval")
        episode["publish_approved"] = True
        episode["review_notes"] = notes
        return transition(episode, "approved")

    episode["publish_approved"] = False
    episode["review_notes"] = notes
    return transition(episode, "rejected")


def publish(episode_id: str) -> dict:
    """Upload the approved episode to YouTube as PRIVATE only."""
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "approved" or not episode.get("publish_approved"):
        raise EditorialError("human approval is required before private upload")
    if not episode.get("video_paths"):
        raise EditorialError("no generated video available")

    results = []
    for video_path in episode["video_paths"]:
        results.append(
            upload_post.cross_post_video(
                video_path=video_path,
                title=episode["title"],
                platforms=["youtube"],
                youtube_extra={
                    "youtube_title": episode["title"],
                    "youtube_description": episode["description"],
                    "tags": episode.get("tags", []),
                    "privacyStatus": "private",
                    "containsSyntheticMedia": True,
                },
            )
        )

    episode["publish_results"] = results
    episode["published_urls"] = [
        r.get("url") or r.get("video_url")
        for r in results
        if isinstance(r, dict) and (r.get("url") or r.get("video_url"))
    ]
    if any(not r.get("success") for r in results if isinstance(r, dict)):
        episode["review_notes"] = (
            "Private upload returned one or more failures: "
            + json.dumps(results, ensure_ascii=False)
        )
        episode["state"] = "failed"
    else:
        episode["state"] = "uploaded_private"
    episode["updated_at"] = utcnow()
    return store.save(episode)


def approve_public(episode_id: str, notes: str = "") -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "uploaded_private":
        raise EditorialError("episode must be privately uploaded before public approval")
    episode["public_publish_approved"] = True
    episode["review_notes"] = notes
    return transition(episode, "public_approved")


def mark_public(episode_id: str, youtube_url: str) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    if episode["state"] != "public_approved" or not episode.get("public_publish_approved"):
        raise EditorialError("final public approval is required before marking published")
    if not youtube_url.strip():
        raise EditorialError("YouTube URL is required")
    episode["published_urls"] = [youtube_url.strip()]
    episode["state"] = "published"
    episode["updated_at"] = utcnow()
    return store.save(episode)


def record_metrics(episode_id: str, metrics: dict[str, Any]) -> dict:
    episode = store.get(episode_id)
    if not episode:
        raise EditorialError("episode not found")
    episode["metrics"] = {
        **episode.get("metrics", {}),
        **metrics,
        "updated_at": utcnow(),
    }
    if episode["state"] in {"published", "measured", "learning"}:
        episode["state"] = "measured"
    episode["updated_at"] = utcnow()
    return store.save(episode)


def learning_snapshot(channel: str | None = None) -> dict[str, Any]:
    episodes = store.list(channel=channel)
    measured = [e for e in episodes if e.get("metrics")]

    def avg(key: str) -> float | None:
        values = [
            float(e["metrics"][key])
            for e in measured
            if isinstance(e.get("metrics", {}).get(key), (int, float))
        ]
        return round(sum(values) / len(values), 3) if values else None

    return {
        "channel": channel,
        "episodes": len(episodes),
        "measured_episodes": len(measured),
        "averages": {
            "views": avg("views"),
            "likes": avg("likes"),
            "comments": avg("comments"),
            "impressions": avg("impressions"),
            "ctr": avg("ctr"),
            "average_view_duration_seconds": avg("average_view_duration_seconds"),
            "watch_time_minutes": avg("watch_time_minutes"),
            "retention": avg("retention"),
            "subscribers_gained": avg("subscribers_gained"),
        },
        "next_action": (
            "Collect at least five measured episodes before changing channel-level rules."
            if len(measured) < 5
            else "Compare pillars, hooks, duration and publish windows before changing templates."
        ),
    }
