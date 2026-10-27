"""Extract contact/location structured facts with generic patterns."""
from __future__ import annotations

import re

from kb.facts import ExtractedFact
from kb.markdown_ctx import nearest_heading
from kb.patterns import US_PHONE
from kb.textutil import strip_non_content

ADDRESS = re.compile(
    r"^(\d[\d\sA-Za-z.\'-]+(?:,\s*[A-Za-z.\'\s]+)+,\s*[A-Z]{2},\s*\d{5})\s*$",
    re.M,
)
ZIP_IN_ADDR = re.compile(r",\s*(\d{5})\s*$")
ROUTING_LABELED = re.compile(
    r"(?:routing\s*(?:number|#)?|aba\s*(?:number|#)?)\s*[:(]?\s*(\d{9})\b",
    re.I,
)
ROUTING_BARE = re.compile(r"\b(\d{9})\b")


def extract_contact_facts(
    markdown: str,
    *,
    url: str,
    snapshot_id: str,
    taken_on: str,
    authority: float,
) -> list[ExtractedFact]:
    md = strip_non_content(markdown or "")
    facts: list[ExtractedFact] = []
    seen: set[tuple[str, str, str]] = set()

    def add(subject: str, field: str, value: str, raw: str, section: str) -> None:
        key = (url, field, value)
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
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )

    for m in ADDRESS.finditer(md):
        addr = re.sub(r"\s+", " ", m.group(1)).strip()
        heading = nearest_heading(md, m.start(), default="Location")
        zm = ZIP_IN_ADDR.search(addr)
        zipc = zm.group(1) if zm else str(m.start())
        subj = f"{heading} — {zipc}"
        add(subj, "address", addr, addr, "locations")

    for m in US_PHONE.finditer(md):
        phone = m.group(0)
        add(f"Phone {phone}", "phone", phone, phone, "contact")

    for m in ROUTING_LABELED.finditer(md):
        add("Routing", "routing number", m.group(1), m.group(0), "contact")

    for m in ROUTING_BARE.finditer(md):
        start = max(0, m.start() - 40)
        ctx = md[start : m.end() + 10].lower()
        if "routing" in ctx or "aba" in ctx:
            add("Routing", "routing number", m.group(1), m.group(0), "contact")

    return facts
