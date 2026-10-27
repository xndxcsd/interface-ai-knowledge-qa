"""Normalize fact keys and values for dedup and conflict detection."""
from __future__ import annotations

import re

from kb.authority import normalize_url

FOOTNOTE_VAL = re.compile(r"^(\d+(?:\.\d+)?%?)\d+$")
FOOTNOTE_FIELD = re.compile(r"(\d+)$")
FOOTNOTE_SUFFIX = re.compile(
    r"(\d+(?:\.\d+)?%?\s*(?:APR|APY)?)\s*\d+\s*$", re.I
)


def normalize_field(field: str) -> str:
    f = (field or "").lower().strip()
    f = FOOTNOTE_FIELD.sub("", f)
    f = re.sub(r"[^a-z0-9]+", " ", f)
    return " ".join(f.split())


def _collapse_dollar_spacing(s: str) -> str:
    def fix(m: re.Match[str]) -> str:
        digits = re.sub(r"\s+", "", m.group(1))
        return "$" + digits

    return re.sub(r"\$\s*([\d\s]+)", fix, s)


def normalize_subject(subject: str) -> str:
    s = _collapse_dollar_spacing(subject or "")
    s = re.sub(r"(\d)(or\s+less\b)", r"\1 \2", s, flags=re.I)
    s = re.sub(r"\$(\d{5,})([a-z])", r"$\1 \2", s, flags=re.I)
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9$+./\-–—]+", " ", s)
    return " ".join(s.split())


def normalize_value(value: str) -> str:
    v = (value or "").strip()
    v = FOOTNOTE_SUFFIX.sub(r"\1", v)
    m = FOOTNOTE_VAL.match(v.replace(" ", ""))
    if m:
        return m.group(1)
    if re.search(r"(?:APR|APY)\s*\d+\s*$", v, re.I):
        v = re.sub(r"\s*\d+\s*$", "", v)
    return v.strip()


def fact_key(url: str, subject: str, field: str) -> tuple[str, str, str]:
    return (normalize_url(url), normalize_subject(subject), normalize_field(field))
