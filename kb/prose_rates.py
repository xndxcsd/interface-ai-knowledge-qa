"""Extract APR rate ranges from markdown prose (not only tables)."""
from __future__ import annotations

import re

from kb.facts import ExtractedFact
from kb.markdown_ctx import HEADING, nearest_heading
from kb.textutil import strip_non_content

GENERIC_HEADINGS = frozenset(
    {
        "the fine print",
        "fine print",
        "disclosures",
        "disclaimer",
        "rates",
        "details",
        "overview",
        "learn more",
    }
)

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
PRODUCT_LINE = re.compile(
    r"^#{1,4}\s+(.+(?:visa|card|rewards|mastercard).*)$",
    re.I | re.M,
)


def _prose_apr_subject(md: str, pos: int) -> str:
    headings = [(m.start(), m.group(1).strip()) for m in HEADING.finditer(md[:pos])]
    for _, title in reversed(headings):
        low = title.lower()
        if low in GENERIC_HEADINGS:
            continue
        if re.search(r"\b(visa|card|rewards|mastercard|checking|savings)\b", title, re.I):
            return title
        if title[:1].isupper() and len(title) > 4:
            return title
    for m in reversed(list(PRODUCT_LINE.finditer(md[:pos]))):
        return m.group(1).strip()
    return "Card APR"


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
                section=nearest_heading(md, pos, default="Rates"),
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )

    for pat in (APR_RANGE, APR_NEAR, FROM_TO_APR):
        for m in pat.finditer(md):
            subj = _prose_apr_subject(md, m.start())
            add(subj, m.group(1), m.group(2), m.group(0), m.start())
    return facts
