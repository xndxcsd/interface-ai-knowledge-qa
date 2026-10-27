"""Shared regex patterns."""
from __future__ import annotations

import re

US_PHONE = re.compile(
    r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
