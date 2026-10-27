"""Extract contact/location structured facts with generic patterns."""
from __future__ import annotations

import re

from kb.facts import ExtractedFact

BRANCH_HEAD = re.compile(r"^#{1,4}\s+(.+)$", re.M)
# Street, city, ST, ZIP (allows extra comma segments in the address line)
ADDRESS = re.compile(
    r"^(\d[\d\sA-Za-z.\'-]+(?:,\s*[A-Za-z.\'\s]+)+,\s*[A-Z]{2},\s*\d{5})\s*$",
    re.M,
)
US_PHONE = re.compile(
    r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
ROUTING_LABELED = re.compile(
    r"(?:routing\s*(?:number|#)?|aba\s*(?:number|#)?)\s*[:(]?\s*(\d{9})\b",
    re.I,
)
ROUTING_BARE = re.compile(r"\b(\d{9})\b")
TIME_RANGE = re.compile(
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"[^.\n]{0,120}?\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)"
    r"[^.\n]{0,80}?\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)?",
    re.I,
)


def _nearest_heading(md: str, pos: int) -> str:
    name = "Location"
    for m in BRANCH_HEAD.finditer(md[:pos]):
        title = m.group(1).strip()
        if len(title) > 2:
            name = title
    return name


def extract_contact_facts(
    markdown: str,
    *,
    url: str,
    snapshot_id: str,
    taken_on: str,
    authority: float,
) -> list[ExtractedFact]:
    md = markdown or ""
    facts: list[ExtractedFact] = []
    seen: set[tuple[str, str, str]] = set()

    def add(subject: str, field: str, value: str, raw: str, section: str) -> None:
        key = (subject, field, value)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            ExtractedFact(
                subject=subject,
                field=field,
                value=value,
                raw_row=raw[:200],
                section=section,
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )

    for m in ADDRESS.finditer(md):
        addr = re.sub(r"\s+", " ", m.group(1)).strip()
        subj = _nearest_heading(md, m.start())
        add(subj, "address", addr, addr, "locations")

    for m in US_PHONE.finditer(md):
        add("Contact phone", "phone", m.group(0), m.group(0), "contact")

    for m in ROUTING_LABELED.finditer(md):
        add("Routing", "routing number", m.group(1), m.group(0), "contact")

    for m in ROUTING_BARE.finditer(md):
        start = max(0, m.start() - 40)
        ctx = md[start : m.end() + 10].lower()
        if "routing" in ctx or "aba" in ctx:
            add("Routing", "routing number", m.group(1), m.group(0), "contact")

    for m in TIME_RANGE.finditer(md):
        val = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(val) >= 10:
            add(_nearest_heading(md, m.start()), "hours", val, val, "hours")

    return facts
