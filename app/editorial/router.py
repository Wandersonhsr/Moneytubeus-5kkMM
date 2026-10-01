from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app.controllers import base
from app.controllers.v1.base import new_router

from .agent import build_opportunities
from .content_engine import generate_package
from .qa import run_package_qa
from .research import collect
from .pipeline import (
    EditorialError,
    attach_research,
    attach_script,
    approve_public,
    mark_public,
    attach_opportunity,
    attach_package,
    collect_research,
    create_episode,
    generate,
    learning_snapshot,
    load_channels,
    publish,
    record_metrics,
    review,
    sync_generation,
)
from .store import store

router = new_router(dependencies=[Depends(base.verify_token)])
router.prefix += "/editorial"
router.tags = ["editorial"]


class EpisodeCreate(BaseModel):
    channel: str
    title: str
    topic: str
    pillar: str = ""
    hook: str = ""


class ResearchAttach(BaseModel):
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ScriptAttach(BaseModel):
    script: str
    description: str
    tags: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    approved: bool
    notes: str = ""


class MetricsRequest(BaseModel):
    metrics: dict[str, Any] = Field(default_factory=dict)


class PublicApprovalRequest(BaseModel):
    notes: str = ""


class PublicMarkRequest(BaseModel):
    youtube_url: str


class OpportunityRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class PackageRequest(BaseModel):
    title: str | None = None


def _ok(data: Any) -> dict[str, Any]:
    return {"status": 200, "message": "success", "data": data}


def _fail(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/channels")
def get_channels():
    return _ok(load_channels())


@router.get("/episodes")
def get_episodes(channel: str | None = None, state: str | None = None):
    return _ok(store.list(channel=channel, state=state))


@router.get("/insights")
def get_insights(channel: str | None = None):
    return _ok(learning_snapshot(channel))


@router.post("/opportunities")
def post_opportunities(channel: str, body: OpportunityRequest):
    try:
        channels = load_channels()
        if channel not in channels:
            raise EditorialError(f"unknown channel: {channel}")
        sources = collect("", channels[channel].get("research_feeds", []))
        return _ok(build_opportunities(channel, sources, body.limit))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/opportunity")
def post_opportunity(episode_id: str, opportunity: dict[str, Any]):
    try:
        return _ok(attach_opportunity(episode_id, opportunity))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/package")
def post_package(episode_id: str, body: PackageRequest | None = None):
    try:
        episode = store.get(episode_id)
        if not episode:
            raise EditorialError("episode not found")
        title = (body.title if body else None) or episode["title"]
        package = generate_package(
            channel_name=episode["channel"],
            title=title,
            topic=episode["topic"],
            research=episode.get("research", []),
            hook=episode.get("hook", ""),
        )
        return _ok(attach_package(episode_id, package))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/qa")
def post_qa(episode_id: str):
    try:
        episode = store.get(episode_id)
        if not episode:
            raise EditorialError("episode not found")
        channel = load_channels()[episode["channel"]]
        return _ok(run_package_qa(episode, channel, episode.get("content_package") or episode))
    except EditorialError as exc:
        _fail(exc)



@router.post("/episodes")
def post_episode(body: EpisodeCreate):
    try:
        return _ok(create_episode(**body.model_dump()))
    except EditorialError as exc:
        _fail(exc)


@router.get("/episodes/{episode_id}")
def get_episode(episode_id: str):
    episode = store.get(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="episode not found")
    return _ok(episode)


@router.post("/episodes/{episode_id}/research/collect")
def post_research_collect(episode_id: str):
    try:
        return _ok(collect_research(episode_id))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/research")
def post_research(episode_id: str, body: ResearchAttach):
    try:
        return _ok(attach_research(episode_id, body.sources))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/script")
def post_script(episode_id: str, body: ScriptAttach):
    try:
        return _ok(
            attach_script(
                episode_id, body.script, body.description, body.tags
            )
        )
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/generate")
def post_generate(episode_id: str):
    try:
        return _ok(generate(episode_id))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/sync")
def post_sync(episode_id: str):
    try:
        return _ok(sync_generation(episode_id))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/review")
def post_review(episode_id: str, body: ReviewRequest):
    try:
        return _ok(review(episode_id, body.approved, body.notes))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/publish")
def post_publish(episode_id: str):
    try:
        return _ok(publish(episode_id))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/metrics")
def post_metrics(episode_id: str, body: MetricsRequest):
    try:
        return _ok(record_metrics(episode_id, body.metrics))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/public-approve")
def post_public_approve(episode_id: str, body: PublicApprovalRequest):
    try:
        return _ok(approve_public(episode_id, body.notes))
    except EditorialError as exc:
        _fail(exc)


@router.post("/episodes/{episode_id}/mark-public")
def post_mark_public(episode_id: str, body: PublicMarkRequest):
    try:
        return _ok(mark_public(episode_id, body.youtube_url))
    except EditorialError as exc:
        _fail(exc)
