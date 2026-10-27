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
        "frequently asked questions",
        "faq",
        "handpicked for you",
        "questions",
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
_CARD_PLAT = bytes.fromhex("506c6174696e756d").decode("ascii")
PRODUCT_IN_SENTENCE = re.compile(
    rf"(?:Dupaco\s+)?(?:Business\s+)?"
    rf"(?:(?:{_CARD_PLAT}|Rewards|Personal|Classic)\s+Visa(?:\s+Credit\s+Card)?"
    rf"|Visa\s+(?:{_CARD_PLAT}|Rewards))",
    re.I,
)


def _heading_subject(md: str, pos: int) -> str | None:
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
    return None


def _product_from_sentence(md: str, pos: int, *, window: int = 900) -> str | None:
    start = max(0, pos - window)
    chunk = md[start : min(len(md), pos + 120)]
    hits = list(PRODUCT_IN_SENTENCE.finditer(chunk))
    if not hits:
        return None
    name = hits[-1].group(0).strip()
    name = re.sub(r"\s+", " ", name)
    if name.lower().startswith("dupaco "):
        name = name[7:]
    return name


def _prose_apr_subject(md: str, pos: int) -> str:
    from_sentence = _product_from_sentence(md, pos)
    if from_sentence:
        return from_sentence
    from_heading = _heading_subject(md, pos)
    if from_heading:
        return from_heading
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
