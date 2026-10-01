from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime


def _text(node: ET.Element | None) -> str:
    return "" if node is None else " ".join("".join(node.itertext()).split())


def fetch_feed(url: str, limit: int = 10) -> list[dict]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "MoneyTubeEditorial/1.0"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    items = root.findall(".//item") or root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    )
    result = []
    for item in items[:limit]:
        atom_link = item.find("{http://www.w3.org/2005/Atom}link")
        link = _text(item.find("link")) or (
            atom_link.attrib.get("href", "") if atom_link is not None else ""
        )
        published = _text(item.find("pubDate")) or _text(
            item.find("{http://www.w3.org/2005/Atom}published")
        )
        try:
            published = (
                parsedate_to_datetime(published).isoformat() if published else ""
            )
        except (TypeError, ValueError):
            pass
        result.append(
            {
                "url": link,
                "title": _text(item.find("title"))
                or _text(item.find("{http://www.w3.org/2005/Atom}title")),
                "publisher": urllib.parse.urlparse(url).netloc,
                "published_at": published,
                "summary": _text(item.find("description"))
                or _text(item.find("{http://www.w3.org/2005/Atom}summary")),
            }
        )
    return result


def collect(topic: str, feeds: list[str], per_feed: int = 8) -> list[dict]:
    terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]{4,}", topic)}
    candidates = []
    for feed in feeds:
        try:
            candidates.extend(fetch_feed(feed, per_feed))
        except Exception:
            continue

    if not terms:
        return candidates

    ranked = []
    for item in candidates:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        score = sum(1 for term in terms if term in text)
        ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked[:20]]
