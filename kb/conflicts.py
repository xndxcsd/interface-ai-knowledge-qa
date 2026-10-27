"""Cross-page conflict detection."""
from __future__ import annotations

import re
from collections import defaultdict

from kb.facts import ExtractedFact

NUM = re.compile(r"(\d+\.\d+)\s*%?")


def _num_key(val: str) -> str | None:
    m = NUM.search(val.replace(",", ""))
    return m.group(1) if m else None


def detect_conflicts(facts: list[ExtractedFact], min_authority: float = 0.9) -> list[dict]:
    """Return conflict dicts ready to become contract.Conflict objects."""
    groups: dict[tuple[str, str], list[ExtractedFact]] = defaultdict(list)
    for f in facts:
        if f.authority < min_authority:
            continue
        if "%" not in f.value and "APR" not in f.field.upper():
            continue
        key = (f.subject.lower().strip(), f.field.lower().strip())
        groups[key].append(f)

    out: list[dict] = []
    for (subject, field), members in groups.items():
        by_num: dict[str, list[ExtractedFact]] = defaultdict(list)
        for m in members:
            nk = _num_key(m.value)
            if nk:
                by_num[nk].append(m)
        if len(by_num) < 2:
            continue
        nums = sorted(by_num.keys(), key=float)
        values = [f"{n}%" for n in nums]
        sources = []
        for n in nums:
            best = max(by_num[n], key=lambda x: (x.taken_on, x.authority))
            sources.append((best.url, best.snapshot_id, best.raw_row[:120]))
        newest = max(members, key=lambda x: x.taken_on)
        resolution = newest.value
        reason = (
            f"Prefer value from newest snapshot ({newest.taken_on}) on official product page."
        )
        topic = f"{subject} — {field}"
        out.append(
            {
                "topic": topic,
                "values": values,
                "sources": sources,
                "resolution": resolution,
                "reason": reason,
            }
        )
    return out
