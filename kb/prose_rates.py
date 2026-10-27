"""Extract APR rate ranges from markdown prose (not only tables)."""
from __future__ import annotations

import re

from kb.facts import ExtractedFact
from kb.textutil import strip_non_content

SECTION = re.compile(r"^#{1,4}\s+(.+)$", re.M)
APR_RANGE = re.compile(
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:–|-|—|to)\s*(\d{1,2}(?:\.\d+)?)\s*%\s*(?:APR|apr)",
    re.I,
)
APR_NEAR = re.compile(
    r"(?:APR|apr)[^.]{0,40}?(\d{1,2}(?:\.\d+)?)\s*%\s*(?:–|-|—|to)\s*(\d{1,2}(?:\.\d+)?)\s*%",
    re.I,
)
FROM_TO_APR = re.compile(
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*APR\s*(?:to|–|-|—)\s*(\d{1,2}(?:\.\d+)?)\s*%\s*APR",
    re.I,
)


def _section_at(md: str, pos: int) -> str:
    name = "Rates"
    for m in SECTION.finditer(md[:pos]):
        t = m.group(1).strip()
        if len(t) > 2:
            name = t
    return name


def extract_prose_apr_facts(
    markdown: str,
    *,
    url: str,
    snapshot_id: str,
    taken_on: str,
    authority: float,
) -> list[ExtractedFact]:
    md = strip_non_content(markdown or "")
    if not md or not re.search(r"\bapr\b", md, re.I):
        return []
    facts: list[ExtractedFact] = []
    seen: set[tuple[str, str]] = set()

    def add(subject: str, lo: str, hi: str, raw: str, pos: int) -> None:
        val = f"{lo}% to {hi}% APR"
        key = (subject.lower(), val)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            ExtractedFact(
                subject=subject,
                field="APR range",
                value=val,
                raw_row=raw[:240],
                section=_section_at(md, pos),
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )

    for m in APR_RANGE.finditer(md):
        subj = _section_at(md, m.start())
        add(subj, m.group(1), m.group(2), m.group(0), m.start())
    for m in APR_NEAR.finditer(md):
        subj = _section_at(md, m.start())
        add(subj, m.group(1), m.group(2), m.group(0), m.start())
    for m in FROM_TO_APR.finditer(md):
        subj = _section_at(md, m.start())
        add(subj, m.group(1), m.group(2), m.group(0), m.start())
    return facts
