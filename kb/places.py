"""Named places in questions and newsroom fact matching."""
from __future__ import annotations

import re

from kb.facts import ExtractedFact
from kb.textutil import QUERY_STOPWORDS, has_word

PLACE_SKIP = QUERY_STOPWORDS | frozenset(
    {
        "which", "every", "specific", "typical", "general", "exact", "store",
        "through", "branches", "lobby",
    }
)


def named_places(question: str) -> list[str]:
    q = re.sub(r"\bDupaco(?:'s)\b", "", question, flags=re.I)
    raw: list[str] = []
    for m in re.finditer(r"\b([A-Z][A-Za-z]+(?:-[A-Z][A-Za-z]+)+)\b", q):
        raw.append(m.group(1))
    for m in re.finditer(r"\b([A-Z][A-Za-z'\-]+),\s*([A-Z]{2}|[A-Z][a-z]+)\b", q):
        raw.append(m.group(1))
    for m in re.finditer(r"\b([A-Z][A-Za-z'\-]+)\s+[Bb]ranch\b", q):
        if m.start() >= 2 and q[m.start() - 2 : m.start()] == ", ":
            continue
        raw.append(m.group(1))
    for m in re.finditer(r"\bnamed\s+([A-Z][A-Za-z'\-]+)\b", q):
        raw.append(m.group(1))
    for m in re.finditer(
        r"(?:branch|lobby|hours)\s+(?:for|at|on)\s+(?:the\s+)?([A-Z][A-Za-z'\-]{3,})\b",
        q,
    ):
        raw.append(m.group(1))
    out: list[str] = []
    for p in raw:
        key = p.lower()
        if key in PLACE_SKIP or key == "dupaco" or len(key) < 3:
            continue
        if key not in out:
            out.append(key)
    return out


def newsroom_place_match(fact: ExtractedFact, place: str) -> bool:
    p = place.lower()
    blob = f"{fact.subject} {fact.section} {fact.value}".lower()
    if fact.section.lower().startswith("article-places:"):
        tags = fact.section.split(":", 1)[1].lower()
        if p in tags or p.replace("-", " ") in tags:
            return True
    if has_word(blob, p) or p.replace("-", " ") in blob:
        return True
    head = fact.subject.split("|", 1)[0].strip().lower()
    return p == head or p.replace("-", " ") == head


def newsroom_fact_matches_places(fact: ExtractedFact, places: list[str]) -> bool:
    if "/newsroom/" not in fact.url.lower() or not places:
        return True
    return any(newsroom_place_match(fact, p) for p in places)
