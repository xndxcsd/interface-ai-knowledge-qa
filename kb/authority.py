"""Page authority and staleness heuristics."""
from __future__ import annotations

import re
from urllib.parse import urlparse

EFFECTIVE_RE = re.compile(
    r"rates?\s+are\s+effective\s+as\s+of\s+(\d{1,2})/(\d{1,2})/(\d{4})",
    re.I,
)

RATE_CANONICAL_PATHS = (
    "/personal/savings-account",
    "/personal/checking-accounts",
    "/personal/loans/home-loans",
    "/personal/loans/auto-motorcycle-loans",
    "/personal/loans/personal-loans",
    "/personal/loans/recreational-loans",
    "/personal/credit-cards",
    "/business/credit-cards",
    "/business/cash-management",
    "/contact",
    "/about/join",
)


def normalize_url(url: str) -> str:
    p = urlparse(url if "://" in url else f"https://{url}")
    path = p.path.rstrip("/").lower() or "/"
    host = p.netloc.lower().removeprefix("www.")
    return f"https://{host}{path}"


def url_path(url: str) -> str:
    return urlparse(url if "://" in url else f"https://{url}").path.lower()


def authority_score(url: str, title: str = "") -> float:
    path = url_path(url)
    if "info.dupaco.com" in url.lower():
        return 0.05
    if "/calculators/" in path:
        return 0.15
    if any(p in path for p in RATE_CANONICAL_PATHS):
        return 1.0
    if path == "/contact" or path == "/":
        return 0.95
    if "/newsroom/" in path:
        return 0.55
    if "/learn/blog/" in path:
        return 0.3
    if "/hubfs/" in path or path.endswith(".pdf"):
        return 0.25
    return 0.45


def is_likely_stale_for_rates(url: str, markdown: str) -> bool:
    path = url_path(url)
    if "/calculators/" in path:
        return True
    if "info.dupaco.com" in url.lower():
        return True
    if "/newsroom/" in path and "rate" in markdown.lower()[:2000]:
        return True
    return False


def parse_effective_dates(markdown: str) -> list[str]:
    """Return ISO dates from 'Rates are effective as of MM/DD/YYYY' lines."""
    out: list[str] = []
    for m in EFFECTIVE_RE.finditer(markdown):
        mo, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        out.append(f"{year:04d}-{mo:02d}-{day:02d}")
    return out


def newest_effective_date(markdown: str) -> str | None:
    dates = parse_effective_dates(markdown)
    return max(dates) if dates else None
