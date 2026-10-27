"""Markdown position helpers."""
from __future__ import annotations

import re

HEADING = re.compile(r"^#{1,4}\s+(.+)$", re.M)


def nearest_heading(markdown: str, pos: int, *, default: str = "") -> str:
    name = default
    for m in HEADING.finditer(markdown[:pos]):
        title = m.group(1).strip()
        if len(title) > 2:
            name = title
    return name
