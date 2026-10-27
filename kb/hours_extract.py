"""Extract labeled hours lines from any page (not only /contact)."""
from __future__ import annotations

import re

from kb.article_places import infer_article_places, subject_with_place
from kb.markdown_ctx import nearest_heading
from kb.facts import ExtractedFact
from kb.textutil import strip_non_content

TIME_RANGE = re.compile(
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"[^.\n]{0,120}?\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)"
    r"[^.\n]{0,80}?\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)?",
    re.I,
)
LABELED = re.compile(
    r"(?:\*\*)?(Drive[- ]?up|Lobby|Branch|Drive Up Window)[^\n]{0,40}?(?:\*\*)?\s*"
    r"(Mon(?:day)?[^\n]{10,140})",
    re.I,
)
HOURS_CONTEXT = re.compile(
    r"drive[- ]?up|lobby hours|branch hours|drive up window|operating hours",
    re.I,
)
def extract_hours_facts(
    markdown: str,
    *,
    url: str,
    snapshot_id: str,
    taken_on: str,
    authority: float,
    page_title: str = "",
) -> list[ExtractedFact]:
    md = strip_non_content(markdown or "")
    if not HOURS_CONTEXT.search(md) and not TIME_RANGE.search(md):
        return []

    facts: list[ExtractedFact] = []
    seen: set[tuple[str, str, str]] = set()
    newsroom = "/newsroom/" in (url or "").lower()
    place_tags = infer_article_places(page_title, md) if newsroom else []
    place_tag = place_tags[0] if place_tags else ""

    def add(label: str, value: str, raw: str, section: str) -> None:
        val = re.sub(r"\s+", " ", value).strip()
        if len(val) < 10:
            return
        key = (url, "hours", val)
        if key in seen:
            return
        seen.add(key)
        if newsroom and place_tag:
            subject = subject_with_place(place_tag, label)
        elif newsroom and page_title:
            subject = f"{page_title.strip()} | {label}"
        else:
            subject = f"{label} — {val[:36]}"
        sec = section
        if newsroom and place_tags:
            sec = f"article-places:{','.join(place_tags)}"
        facts.append(
            ExtractedFact(
                subject=subject,
                field="hours",
                value=val,
                raw_row=raw[:200],
                section=sec,
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )

    for m in LABELED.finditer(md):
        label = m.group(1).strip()
        add(label, m.group(2), m.group(0), nearest_heading(md, m.start(), default="Hours"))

    if HOURS_CONTEXT.search(md):
        for m in TIME_RANGE.finditer(md):
            add("Schedule", m.group(0), m.group(0), nearest_heading(md, m.start(), default="Hours"))

    return facts
