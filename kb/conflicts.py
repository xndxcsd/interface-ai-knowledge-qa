"""Detect real conflicts: cross-snapshot column changes and same-snapshot contradictions."""
from __future__ import annotations

import re
from collections import defaultdict

from kb.facts import ExtractedFact
from kb.normalize import fact_key, normalize_value

NUM = re.compile(r"(\d+(?:\.\d+)?)\s*%?")


def _num_key(val: str) -> str | None:
    v = normalize_value(val)
    m = NUM.search(v.replace(",", ""))
    return m.group(1) if m else None


def _is_rate_field(field: str, value: str) -> bool:
    f = field.lower()
    return "%" in value or "apy" in f or "apr" in f or "rate" in f or "dividend" in f


def detect_conflicts(
    all_facts: list[ExtractedFact],
    *,
    current_facts: list[ExtractedFact],
    latest_snapshot_date: str,
    min_authority: float = 0.9,
) -> list[dict]:
    current_by_key = {
        fact_key(f.url, f.subject, f.field): f
        for f in current_facts
        if f.authority >= min_authority
    }

    groups: dict[tuple[str, str, str], list[ExtractedFact]] = defaultdict(list)
    for f in all_facts:
        if f.authority < min_authority:
            continue
        if not _is_rate_field(f.field, f.value):
            continue
        groups[fact_key(f.url, f.subject, f.field)].append(f)

    out: list[dict] = []
    for key, members in groups.items():
        by_num: dict[str, list[ExtractedFact]] = defaultdict(list)
        for m in members:
            nk = _num_key(m.value)
            if nk:
                by_num[nk].append(m)

        if len(by_num) < 2:
            continue

        cur = current_by_key.get(key)
        if cur is None:
            continue

        cur_val = normalize_value(cur.value)
        older = [m for m in members if m.taken_on < cur.taken_on]
        older_vals = {normalize_value(m.value) for m in older}
        same_snap_vals = {
            normalize_value(m.value)
            for m in members
            if m.snapshot_id == cur.snapshot_id
        }

        cross = bool(older_vals - {cur_val})
        internal = len(same_snap_vals) > 1
        if not cross and not internal:
            continue

        timeline: list[tuple[str, str, ExtractedFact]] = []
        seen_val: set[str] = set()
        for m in sorted(members, key=lambda x: (x.taken_on, x.snapshot_id)):
            nv = normalize_value(m.value)
            if nv in seen_val:
                continue
            seen_val.add(nv)
            timeline.append((m.taken_on, nv, m))

        values = [nv for _, nv, _ in timeline]
        sources = []
        for _, nv, m in timeline:
            sources.append((m.url, m.snapshot_id, normalize_value(m.raw_row[:120])))

        _, subject, field = key
        topic = f"{subject} — {field}"
        reason = (
            f"Use current value from newest snapshot ({latest_snapshot_date}) "
            f"on the official product page."
        )
        out.append(
            {
                "topic": topic,
                "values": values,
                "sources": sources,
                "resolution": cur_val,
                "reason": reason,
            }
        )
    return out
