from __future__ import annotations

import re
from typing import Any


PLACEHOLDER_RE = re.compile(r"\[[A-Za-z][A-Za-z0-9 _-]{2,}\]")
DANGEROUS_FINANCE_RE = re.compile(
    r"\b(guaranteed return|risk-free|you should buy|you should sell|guaranteed profit)\b",
    re.IGNORECASE,
)


def _result(name: str, passed: bool, severity: str = "error", detail: str = "") -> dict[str, Any]:
    return {
        "check": name,
        "passed": passed,
        "severity": severity,
        "detail": detail,
    }


def run_package_qa(
    episode: dict[str, Any],
    channel: dict[str, Any],
    package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    package = package or episode
    script = str(package.get("script", episode.get("script", ""))).strip()
    description = str(package.get("description", episode.get("description", ""))).strip()
    title = str(package.get("title", episode.get("title", ""))).strip()
    tags = package.get("tags", episode.get("tags", [])) or []
    research = package.get("research", episode.get("research", [])) or []
    summary = str(package.get("summary", "")).strip()
    original_angle = str(package.get("original_angle", "")).strip()
    viewer_payoff = str(package.get("viewer_payoff", "")).strip()
    visual_beats = package.get("visual_beats", []) or []
    assets = package.get("assets", package.get("visual_assets", [])) or []
    risk = channel.get("review_risk", "standard")

    checks = []
    words = len(re.findall(r"\b\w+[’'-]?\w*\b", script))

    checks.append(_result("title_present", bool(title), detail="title is required"))
    checks.append(_result("title_length", 20 <= len(title) <= 100, detail=f"{len(title)} characters"))
    checks.append(_result("script_present", bool(script), detail="script is required"))
    checks.append(
        _result(
            "script_length",
            900 <= words <= 2600,
            "error",
            f"{words} words; target is approximately 8–14 minutes",
        )
    )
    checks.append(_result("description_present", bool(description), detail="description is required"))
    checks.append(
        _result(
            "original_editorial_angle",
            bool(original_angle),
            "error",
            "record the episode-specific thesis/angle; a topic restatement is insufficient",
        )
    )
    checks.append(
        _result(
            "viewer_payoff",
            bool(viewer_payoff),
            "error",
            "state what the viewer will understand or be able to explain after watching",
        )
    )
    checks.append(
        _result(
            "unique_summary_first_lines",
            bool(summary) and description.startswith(summary),
            detail="the first lines must contain the unique episode summary",
        )
    )
    checks.append(
        _result(
            "no_placeholders",
            not PLACEHOLDER_RE.search(script) and not PLACEHOLDER_RE.search(description),
            detail="replace source and template placeholders before approval",
        )
    )
    min_sources = 3 if risk == "high" else 2
    checks.append(
        _result(
            "research_depth",
            len(research) >= min_sources,
            detail=f"{len(research)} sources; minimum is {min_sources}",
        )
    )
    checks.append(
        _result(
            "source_urls",
            all(str(item.get("url", "")).startswith(("http://", "https://")) for item in research),
            detail="every research item must contain a source URL",
        )
    )
    domains = {
        re.sub(r"^www\.", "", __import__("urllib.parse", fromlist=["urlparse"]).urlparse(str(item.get("url", ""))).netloc.lower())
        for item in research
        if str(item.get("url", "")).startswith(("http://", "https://"))
    }
    checks.append(
        _result(
            "source_diversity",
            len(domains) >= min(2, min_sources),
            "warning",
            f"{len(domains)} distinct source domains; use independent sources where available",
        )
    )
    paragraphs = [
        re.sub(r"\W+", " ", item.lower()).strip()
        for item in re.split(r"\n\s*\n", script)
        if item.strip()
    ]
    duplicate_paragraphs = len(paragraphs) != len(set(paragraphs))
    checks.append(
        _result(
            "duplicate_paragraphs",
            not duplicate_paragraphs,
            "error",
            "script contains exact repeated paragraphs",
        )
    )
    checks.append(
        _result(
            "visual_storytelling",
            len(visual_beats) >= 3,
            "warning",
            f"{len(visual_beats)} visual beats; visuals should advance or explain the narrative",
        )
    )
    if assets:
        missing_rights = [
            item for item in assets
            if not (item.get("rights_status") or item.get("license") or item.get("source_url"))
        ]
        checks.append(
            _result(
                "asset_provenance",
                not missing_rights,
                "error",
                f"{len(missing_rights)} assets lack rights/license/source provenance",
            )
        )
    else:
        checks.append(
            _result(
                "asset_provenance",
                False,
                "warning",
                "no asset manifest supplied; verify stock footage, music, images and third-party clips before approval",
            )
        )
    checks.append(
        _result(
            "metadata_tags",
            isinstance(tags, list) and len(tags) >= 5,
            detail=f"{len(tags)} tags",
        )
    )
    if risk == "high":
        checks.append(
            _result(
                "finance_language",
                not DANGEROUS_FINANCE_RE.search(script),
                "error",
                "remove guarantees and individualized buy/sell instructions",
            )
        )
    else:
        checks.append(_result("finance_language", True, "info", "not applicable"))

    errors = [item for item in checks if not item["passed"] and item["severity"] == "error"]
    warnings = [item for item in checks if not item["passed"] and item["severity"] != "error"]
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "word_count": words,
        "minimum_sources": min_sources,
    }
