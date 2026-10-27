"""Structured fact extraction from markdown tables."""
from __future__ import annotations

import re
from dataclasses import dataclass

from kb.authority import newest_effective_date
from kb.textutil import clean_markdown


@dataclass(frozen=True)
class ExtractedFact:
    subject: str
    field: str
    value: str
    raw_row: str
    section: str
    effective_date: str | None
    url: str
    snapshot_id: str
    taken_on: str
    authority: float


TABLE_ROW = re.compile(r"^\|(.+)\|\s*$", re.M)
HEADER_SEP = re.compile(r"^\|\s*[-:]+\s*\|", re.M)
SECTION = re.compile(r"^#{1,4}\s+(.+)$", re.M)


def _parse_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip("|").split("|")]
    return cells


def extract_table_facts(
    markdown: str,
    *,
    url: str,
    snapshot_id: str,
    taken_on: str,
    authority: float,
) -> list[ExtractedFact]:
    md = markdown or ""
    effective = newest_effective_date(md)
    sections: list[tuple[int, str]] = [(0, "")]
    for m in SECTION.finditer(md):
        sections.append((m.start(), m.group(1).strip()))
    sections.sort()

    def section_at(pos: int) -> str:
        name = ""
        for start, title in sections:
            if start <= pos:
                name = title
        return name

    facts: list[ExtractedFact] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip().startswith("|") or i + 1 >= len(lines):
            i += 1
            continue
        if not HEADER_SEP.match(lines[i + 1]):
            i += 1
            continue
        header = _parse_row(line)
        i += 2
        while i < len(lines) and lines[i].strip().startswith("|"):
            row_cells = _parse_row(lines[i])
            if len(row_cells) >= 2 and row_cells[0] != "---":
                raw = lines[i]
                pos = md.find(raw)
                sec = section_at(pos)
                subject = row_cells[0]
                for j, h in enumerate(header[1:], start=1):
                    if j >= len(row_cells):
                        break
                    val = row_cells[j]
                    if not val or val in ("—", "-"):
                        continue
                    if "%" not in val and not re.search(r"\d", val):
                        continue
                    facts.append(
                        ExtractedFact(
                            subject=subject,
                            field=h,
                            value=val,
                            raw_row=raw,
                            section=sec,
                            effective_date=effective,
                            url=url,
                            snapshot_id=snapshot_id,
                            taken_on=taken_on,
                            authority=authority,
                        )
                    )
            i += 1
    return facts


def find_table_rows(markdown: str, needle: str) -> list[str]:
    needle_l = needle.lower()
    rows = []
    for line in (markdown or "").splitlines():
        if line.strip().startswith("|") and needle_l in line.lower():
            rows.append(line)
    return rows


def page_text(markdown: str) -> str:
    return clean_markdown(markdown)
