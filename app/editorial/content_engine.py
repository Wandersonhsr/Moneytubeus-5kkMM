from __future__ import annotations

import re
from typing import Any

from app.services import llm

from .pipeline import load_channels
from .qa import run_package_qa


EDITORIAL_SYSTEM_PROMPT = """
You are the senior writer for a premium faceless documentary channel.

Write an original English-language documentary script for an 8–14 minute video.
The script must feel cinematic, intelligent and evidence-led, not like a generic
AI listicle.

Narrative rules:
- Open with a concrete tension, surprising fact, contradiction, or high-stakes question.
- Establish why the subject matters now.
- Build one coherent thesis instead of listing disconnected facts.
- Separate documented facts from estimates, predictions and attributed interpretations.
- Use only the research packet supplied in the prompt as factual grounding.
- Never invent numbers, quotes, product capabilities, dates or events.
- Explain mechanisms and second-order effects.
- Use short and medium sentences mixed with occasional punchy lines.
- Do not use headings, bullets, stage directions, markdown, citations in parentheses,
  or labels such as narrator/voiceover.
- Do not say "in this video", "welcome back", or mention that you are an AI.
- End with a concise implication and a natural subscribe CTA.
- Target approximately 1,300–2,000 words.
""".strip()


def _source_packet(research: list[dict[str, Any]]) -> str:
    lines = []
    for index, source in enumerate(research, start=1):
        lines.append(
            f"Source {index}: {source.get('title', '')}\n"
            f"Publisher: {source.get('publisher', '')}\n"
            f"Published: {source.get('published_at', '')}\n"
            f"URL: {source.get('url', '')}\n"
            f"Summary: {source.get('summary', '')}"
        )
    return "\n\n".join(lines)


def _clean_words(text: str) -> list[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "about",
        "what", "why", "how", "after", "before", "will", "could", "would",
        "their", "they", "have", "has", "been", "are", "was", "were", "its",
    }
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text)
        if token.lower() not in stop
    ]


def _tags(title: str, topic: str, channel: dict[str, Any]) -> list[str]:
    values = _clean_words(f"{title} {topic}")
    for pillar in channel.get("pillars", []):
        values.extend(_clean_words(str(pillar)))
    result = []
    for value in values:
        if value not in result:
            result.append(value)
        if len(result) >= 15:
            break
    return result


def _summary(title: str, topic: str, channel: dict[str, Any]) -> str:
    if channel.get("review_risk") == "high":
        return (
            f"This episode examines {title}, what the documented evidence shows, "
            f"and which economic mechanisms or second-order effects matter next."
        )
    return (
        f"This episode examines {title} and the deeper shift it reveals about "
        f"{topic.lower() if topic else channel.get('niche', 'technology')}."
    )


def _title_variants(title: str, topic: str) -> list[str]:
    base = title.strip().rstrip(".")
    return [
        base,
        f"The Real Story Behind {base}",
        f"Why {base} Matters Now",
        f"What {base} Changes Next",
        f"The Shift Hidden Inside {base}",
    ]


def _paragraphs(script: str) -> list[str]:
    chunks = [item.strip() for item in re.split(r"\n\s*\n", script) if item.strip()]
    if len(chunks) > 10:
        return chunks[:10]
    return chunks


def _chapters(script: str) -> list[dict[str, str]]:
    paragraphs = _paragraphs(script)
    if not paragraphs:
        return []
    result = []
    elapsed_seconds = 0
    for index, paragraph in enumerate(paragraphs):
        if index:
            elapsed_seconds += max(35, int(len(re.findall(r"\b\w+\b", paragraphs[index - 1])) / 2.35))
        minutes, seconds = divmod(elapsed_seconds, 60)
        label = "Opening" if index == 0 else (
            "Context" if index == 1 else
            "What changed" if index == 2 else
            "How the system works" if index == 3 else
            "The deeper shift" if index == 4 else
            "Second-order effects" if index == 5 else
            "What to watch" if index == 6 else
            "Implications" if index == 7 else
            "The bigger picture"
        )
        result.append({"time": f"{minutes:02d}:{seconds:02d}", "title": label})
    return result


def _visual_beats(script: str, title: str) -> list[dict[str, Any]]:
    paragraphs = _paragraphs(script)
    beats = []
    for index, paragraph in enumerate(paragraphs):
        first_sentence = re.split(r"(?<=[.!?])\s+", paragraph)[0].strip()
        terms = _clean_words(f"{title} {first_sentence}")
        beats.append(
            {
                "scene": index + 1,
                "narration_anchor": first_sentence[:220],
                "visual_search_terms": terms[:5],
                "visual_direction": (
                    "Use cinematic establishing footage, then move into "
                    "specific evidence, interfaces, infrastructure or data visualization."
                ),
            }
        )
    return beats


def _thumbnail_brief(title: str, channel: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept": "One dominant subject + one visual consequence + minimal text.",
        "text_options": [
            title[:34],
            "THE SHIFT",
            "WHAT CHANGED?",
        ],
        "composition": "16:9, single focal object, strong depth, negative space for text, cinematic lighting.",
        "avoid": "Generic robot imagery, clutter, tiny text, fake screenshots, unsupported numbers.",
        "channel_style": channel.get("format", "cinematic documentary"),
    }


def generate_package(
    channel_name: str,
    title: str,
    topic: str,
    research: list[dict[str, Any]],
    hook: str = "",
) -> dict[str, Any]:
    channels = load_channels()
    if channel_name not in channels:
        raise ValueError(f"unknown channel: {channel_name}")
    channel = channels[channel_name]
    if not research:
        raise ValueError("research packet cannot be empty")

    packet = _source_packet(research)
    requirements = (
        f"Episode title: {title}\n"
        f"Topic: {topic}\n"
        f"Opening hook direction: {hook or 'create a strong tension-driven opening'}\n\n"
        f"Research packet:\n{packet}"
    )
    script = llm.generate_script(
        video_subject=title,
        language=channel.get("language", "en-US"),
        paragraph_number=10,
        video_script_prompt=requirements,
        custom_system_prompt=EDITORIAL_SYSTEM_PROMPT,
    ).strip()

    if not script or script.startswith("Error:"):
        raise RuntimeError(script or "LLM returned an empty script")

    summary = _summary(title, topic, channel)
    description = (
        f"{summary}\n\n"
        f"{script[:650].strip()}\n\n"
        "Sources:\n"
        + "\n".join(f"- {item.get('title', '')}: {item.get('url', '')}" for item in research)
    )

    tags = _tags(title, topic, channel)
    package = {
        "title": title,
        "title_variants": _title_variants(title, topic),
        "topic": topic,
        "hook": hook,
        "summary": summary,
        "script": script,
        "description": description,
        "tags": tags,
        "chapters": _chapters(script),
        "visual_beats": _visual_beats(script, title),
        "thumbnail_brief": _thumbnail_brief(title, channel),
        "research": research,
        "evidence_notes": [
            {
                "source": item.get("url", ""),
                "publisher": item.get("publisher", ""),
                "claim_basis": item.get("summary", ""),
            }
            for item in research
        ],
        "synthetic_media": True,
        "review_risk": channel.get("review_risk", "standard"),
    }
    package["qa"] = run_package_qa(package, channel, package)
    return package
