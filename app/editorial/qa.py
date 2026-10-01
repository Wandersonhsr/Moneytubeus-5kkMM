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
