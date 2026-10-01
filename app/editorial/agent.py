from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any

from .pipeline import load_channels


SCORE_WEIGHTS = {
    "freshness": 20,
    "audience_relevance": 20,
    "novelty": 15,
    "evidence_strength": 15,
    "visual_potential": 15,
    "hook_potential": 10,
    "production_feasibility": 5,
}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}", text or "")
    }


def _days_old(published_at: str | None) -> float | None:
    if not published_at:
        return None
    try:
        value = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - value).total_seconds() / 86400)
    except ValueError:
        return None


def _clamp(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _domain(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def score_source(item: dict[str, Any], channel: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title", "")).strip()
    summary = str(item.get("summary", "")).strip()
    corpus = f"{title} {summary}".lower()
    niche = str(channel.get("niche", ""))
    pillars = channel.get("pillars", [])
    niche_terms = _tokens(niche) | {
        token.lower() for pillar in pillars for token in _tokens(str(pillar))
    }

    overlap = len(_tokens(corpus) & niche_terms)
    relevance = _clamp(45 + min(45, overlap * 7))

    age = _days_old(item.get("published_at"))
    if age is None:
        freshness = 55
    elif age <= 1:
        freshness = 100
    elif age <= 3:
        freshness = 90
    elif age <= 7:
        freshness = 78
    elif age <= 30:
        freshness = 62
    elif age <= 90:
        freshness = 45
    else:
        freshness = 25

    evidence = 85 if _domain(item.get("url", "")) else 45
    publisher = str(item.get("publisher", "")).lower()
    if any(term in publisher for term in ("sec.gov", "federalreserve.gov", "bls.gov", "imf.org", "blog.google", "microsoft.com")):
        evidence = 100

    visual_terms = {
        "model", "ai", "agent", "robot", "chip", "space", "satellite", "market",
        "money", "bank", "stock", "economy", "office", "coding", "automation",
        "data", "cloud", "factory", "science", "security",
    }
    visual = _clamp(35 + len(_tokens(corpus) & visual_terms) * 8)

    hook = _clamp(40 + min(50, max(0, len(title) - 30)) + (15 if any(
        marker in title.lower() for marker in ("new", "why", "how", "first", "future", "launch", "changes")
    ) else 0))

    novelty = _clamp(50 + (25 if age is not None and age <= 7 else 0) + min(20, max(0, 8 - overlap)))
    feasibility = _clamp(85 if title and summary else 55)

    dimensions = {
        "freshness": freshness,
        "audience_relevance": relevance,
        "novelty": novelty,
        "evidence_strength": evidence,
        "visual_potential": visual,
        "hook_potential": hook,
        "production_feasibility": feasibility,
    }
    total = sum(dimensions[key] * SCORE_WEIGHTS[key] / 100 for key in SCORE_WEIGHTS)
    return {
        "score": round(total, 1),
        "dimensions": dimensions,
        "source_domain": _domain(item.get("url", "")),
    }


def _dedupe_key(item: dict[str, Any]) -> str:
    url = str(item.get("url", "")).strip().lower()
    if url:
        return url
    return re.sub(r"\W+", " ", str(item.get("title", "")).lower()).strip()


def build_opportunities(
    channel_name: str,
    sources: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    channels = load_channels()
    if channel_name not in channels:
        raise ValueError(f"unknown channel: {channel_name}")

    channel = channels[channel_name]
    seen: set[str] = set()
    ranked: list[dict[str, Any]] = []

    for source in sources:
        key = _dedupe_key(source)
        if not key or key in seen:
            continue
        seen.add(key)
        scoring = score_source(source, channel)
        title = str(source.get("title", "")).strip()
        summary = str(source.get("summary", "")).strip()
        ranked.append(
            {
                "opportunity_id": f"opp_{abs(hash(key)) % 10**10:010d}",
                "channel": channel_name,
                "title": title,
                "topic": title,
                "angle": _build_angle(title, channel),
                "hook": _build_hook(title, channel),
                "source": source,
                "source_count": 1,
                "priority": "high" if scoring["score"] >= 75 else "normal",
                **scoring,
                "status": "candidate",
            }
        )

    ranked.sort(key=lambda item: (item["score"], item.get("source_count", 0)), reverse=True)
    return ranked[: max(1, limit)]


def _build_angle(title: str, channel: dict[str, Any]) -> str:
    if channel.get("review_risk") == "high":
        return f"What the documented development means for the system around it: {title}"
    return f"The second-order change behind the headline: {title}"


def _build_hook(title: str, channel: dict[str, Any]) -> str:
    if channel.get("review_risk") == "high":
        return f"The headline is only the first layer. The real question is what changes next: {title}"
    return f"Something important just changed — and the obvious story is not the whole story: {title}"


def merge_related_sources(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in opportunities:
        words = sorted(_tokens(item.get("title", "")))
        key = " ".join(words[:5]) if words else item.get("opportunity_id", "")
        groups.setdefault(key, []).append(item)

    merged = []
    for group in groups.values():
        primary = dict(max(group, key=lambda x: x.get("score", 0)))
        primary["source_count"] = len(group)
        primary["related_sources"] = [entry["source"] for entry in group]
        primary["score"] = round(min(100, primary["score"] + min(10, (len(group) - 1) * 3)), 1)
        merged.append(primary)
    return sorted(merged, key=lambda item: item["score"], reverse=True)
