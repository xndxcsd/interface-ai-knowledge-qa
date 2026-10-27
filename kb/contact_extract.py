"""Extract branch addresses, phones, and hours as structured facts."""
from __future__ import annotations

import re

from kb.facts import ExtractedFact

ADDRESS = re.compile(
    r"^(\d[\d\sA-Za-z.\-]+,\s*(?:IL|IA|WI),\s*\d{5})\s*$", re.M
)
PHONE = re.compile(r"\b(800-373-7600)\b")
ROUTING = re.compile(r"\b(273974581)\b")
HOURS_RANGE = re.compile(
    r"(Monday[–\-]Friday[^.\n]{0,80}|Mon[–\-][^.\n]{0,80}8:30[^.\n]{0,80}|"
    r"8:30\s*a\.?\s*m\.?\s*[–\-]\s*[^.\n]{0,40}|"
    r"8\s*a\.?\s*m\.?\s*[–\-]\s*6\s*p\.?\s*m\.?)",
    re.I,
)
BRANCH_HEAD = re.compile(r"^#{1,4}\s+(.+)$", re.M)


def _branch_name_before(md: str, pos: int) -> str:
    name = "Dupaco Branch"
    for m in BRANCH_HEAD.finditer(md[:pos]):
        title = m.group(1).strip()
        if "Dupaco" in title or "Branch" in title or "ATM" in title:
            name = title
    lines = md[:pos].splitlines()[-8:]
    for ln in reversed(lines):
        if "Branch" in ln and ln.startswith("###"):
            return ln.lstrip("#").strip()
        if "Galena" in ln or "Peosta" in ln:
            return ln.strip()
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
    for m in ADDRESS.finditer(md):
        addr = m.group(1).replace(", ", ", ").strip()
        pos = m.start()
        branch = _branch_name_before(md, pos)
        if "Galena" in addr:
            branch = "Galena Branch"
        facts.append(
            ExtractedFact(
                subject=branch,
                field="address",
                value=addr,
                raw_row=addr,
                section="locations",
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )
    for m in PHONE.finditer(md):
        facts.append(
            ExtractedFact(
                subject="Dupaco member services",
                field="phone",
                value=m.group(1),
                raw_row=m.group(0),
                section="contact",
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )
    for m in ROUTING.finditer(md):
        facts.append(
            ExtractedFact(
                subject="Dupaco",
                field="routing number",
                value=m.group(1),
                raw_row=m.group(0),
                section="contact",
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )
    for m in HOURS_RANGE.finditer(md):
        val = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(val) < 8:
            continue
        facts.append(
            ExtractedFact(
                subject="Branch hours",
                field="lobby or drive-up",
                value=val,
                raw_row=val,
                section="hours",
                effective_date=None,
                url=url,
                snapshot_id=snapshot_id,
                taken_on=taken_on,
                authority=authority,
            )
        )
    return facts
