"""Structured fact extraction from markdown tables."""
from __future__ import annotations

import re
from dataclasses import dataclass

from kb.markdown_ctx import nearest_heading
from kb.normalize import normalize_value


@dataclass(frozen=True)
class ExtractedFact:
    subject: str
    field: str
    value: str
    raw_row: str
    section: str
    url: str
    snapshot_id: str
    taken_on: str
    authority: float


HEADER_SEP = re.compile(r"^\|\s*[-:]+\s*\|", re.M)


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
                sec = nearest_heading(md, pos)
                subject = row_cells[0]
                if len(header) > 1 and len(row_cells) > 1:
                    h1 = header[1].lower()
                    if any(
                        x in h1
                        for x in (
                            "tier",
                            "balance",
                            "term",
                            "month",
                            "program",
                            "model",
                            "loan",
                        )
                    ):
                        subject = f"{subject} | {row_cells[1]}"
                for j, h in enumerate(header[1:], start=1):
                    if j >= len(row_cells):
                        break
                    val = normalize_value(row_cells[j])
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
                            url=url,
                            snapshot_id=snapshot_id,
                            taken_on=taken_on,
                            authority=authority,
                        )
                    )
            i += 1
    return facts
