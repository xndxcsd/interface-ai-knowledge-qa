"""Infer branch/city tags from newsroom article title and lead."""
from __future__ import annotations

import re

from kb.textutil import strip_non_content

PLACE_STOP = frozenset(
    {
        "dupaco", "community", "credit", "union", "new", "the", "our", "your",
        "grand", "opening", "celebrates", "opens", "open", "first", "official",
        "news", "room", "article", "branch", "location", "member", "members",
        "street", "avenue", "road", "drive", "lane", "highway", "north", "south",
        "east", "west", "downtown", "area", "local", "team", "staff",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    }
)

BRANCH_IN_TITLE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Bb]ranch\b"
)
DATELINE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z][a-z]{3,})\b"
)
IN_CITY = re.compile(
    r"\b(?:in|at|for)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
)


def _norm_place(raw: str) -> str | None:
    p = re.sub(r"\s+", " ", raw.strip()).lower()
    if len(p) < 3 or p in PLACE_STOP:
        return None
    if all(w in PLACE_STOP for w in p.split()):
        return None
    return p


def infer_article_places(title: str, markdown: str, *, lead_chars: int = 1200) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: str) -> None:
        p = _norm_place(raw)
        if p and p not in seen:
            seen.add(p)
            out.append(p)

    for m in BRANCH_IN_TITLE.finditer(title or ""):
        add(m.group(1))
    lead = strip_non_content(markdown or "")[:lead_chars]
    for m in DATELINE.finditer(lead):
        add(m.group(1))
    for m in IN_CITY.finditer(lead):
        add(m.group(1))
    if not out and title:
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", title):
            add(m.group(1))
    return out


def subject_with_place(place: str, label: str) -> str:
    p = place.strip()
    if not p:
        return label
    return f"{p} | {label}"
