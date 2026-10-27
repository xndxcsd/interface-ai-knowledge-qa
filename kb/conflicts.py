"""Cross-page conflict detection (precision-focused)."""
from __future__ import annotations

import re
from collections import defaultdict

from kb.facts import ExtractedFact
from kb.normalize import fact_key, normalize_url, normalize_value

NUM = re.compile(r"(\d+(?:\.\d+)?)\s*%?")


def _num_key(val: str) -> str | None:
    v = normalize_value(val)
    m = NUM.search(v.replace(",", ""))
    return m.group(1) if m else None


def _is_rate_field(field: str) -> bool:
    f = field.lower()
    return "%" in f or "apy" in f or "apr" in f or "rate" in f or "dividend" in f


def detect_conflicts(
    facts: list[ExtractedFact],
    *,
    latest_snapshot_date: str,
    min_authority: float = 0.9,
) -> list[dict]:
    """Conflicts: same URL + product row + field, different numeric values."""
    groups: dict[tuple[str, str, str], list[ExtractedFact]] = defaultdict(list)
    for f in facts:
        if f.authority < min_authority:
            continue
        if not _is_rate_field(f.field) and "%" not in f.value:
            continue
        groups[fact_key(f.url, f.subject, f.field)].append(f)

    out: list[dict] = []
    for (canon, subject, field), members in groups.items():
        by_num: dict[str, list[ExtractedFact]] = defaultdict(list)
        for m in members:
            nk = _num_key(m.value)
            if nk:
                by_num[nk].append(m)
        if len(by_num) < 2:
            continue
        nums = sorted(by_num.keys(), key=float)
        values = [f"{n}%" if "%" not in normalize_value(by_num[n][0].value) else normalize_value(by_num[n][0].value) for n in nums]
        sources = []
        for n in nums:
            best = max(by_num[n], key=lambda x: (x.taken_on, x.authority))
            sources.append((best.url, best.snapshot_id, best.raw_row[:120]))
        newest = max(members, key=lambda x: (x.taken_on, x.authority))
        resolution = normalize_value(newest.value)
        reason = (
            f"Prefer value from newest snapshot ({latest_snapshot_date}) on official product page."
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
