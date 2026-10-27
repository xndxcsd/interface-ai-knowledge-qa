"""Normalize fact keys and values for dedup and conflict detection."""
from __future__ import annotations

import re

from kb.authority import normalize_url

FOOTNOTE_VAL = re.compile(r"^(\d+(?:\.\d+)?%?)\d+$")
FOOTNOTE_FIELD = re.compile(r"(\d+)$")


def normalize_field(field: str) -> str:
    f = (field or "").lower().strip()
    f = FOOTNOTE_FIELD.sub("", f)
    f = re.sub(r"[^a-z0-9]+", " ", f)
    return " ".join(f.split())


def normalize_subject(subject: str) -> str:
    s = (subject or "").lower().strip()
    s = re.sub(r"[^a-z0-9$+./\-–—]+", " ", s)
    return " ".join(s.split())


def normalize_value(value: str) -> str:
    v = (value or "").strip()
    m = FOOTNOTE_VAL.match(v.replace(" ", ""))
    if m:
        return m.group(1)
    v = re.sub(r"(\d+\.\d+%)\d+$", r"\1", v)
    return v


def fact_key(url: str, subject: str, field: str) -> tuple[str, str, str]:
    return (normalize_url(url), normalize_subject(subject), normalize_field(field))
