"""Structured facts from newsroom articles (phones, size, tagged by place)."""
from __future__ import annotations

import re

from kb.article_places import infer_article_places, subject_with_place
from kb.facts import ExtractedFact
from kb.patterns import US_PHONE
from kb.textutil import strip_non_content

SQ_FT = re.compile(
    r"\b([\d,]{3,7})\s*(?:square\s+feet|sq\.?\s*ft\.?)\b",
    re.I,
)
SQ_FT_HYPHEN = re.compile(
    r"\b([\d,]{3,7})[\-\s]+square[\-\s]+foot\b",
    re.I,
)


def extract_newsroom_facts(
    markdown: str,
    *,
    url: str,
    page_title: str,
    snapshot_id: str,
    taken_on: str,
    authority: float,
) -> list[ExtractedFact]:
    if "/newsroom/" not in (url or "").lower():
        return []
    md = strip_non_content(markdown or "")
    if not md:
        return []
    tags = infer_article_places(page_title, md)
    place = tags[0] if tags else ""
    facts: list[ExtractedFact] = []
    seen: set[tuple[str, str, str]] = set()

    def add(subject: str, field: str, value: str, raw: str) -> None:
        key = (field, value, subject)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            ExtractedFact(
                subject=subject,
                field=field,
                value=value,
                raw_row=raw[:200],
                section=f"article-places:{','.join(tags)}" if tags else "article",
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority * 0.92,
            )
        )

    for m in US_PHONE.finditer(md):
        add(subject_with_place(place, "phone"), "phone", m.group(0), m.group(0))

    for pat in (SQ_FT, SQ_FT_HYPHEN):
        for m in pat.finditer(md):
            val = re.sub(r",", "", m.group(1))
            add(
                subject_with_place(place, "facility size"),
                "square feet",
                f"{val} sq ft",
                m.group(0),
            )

    return facts
