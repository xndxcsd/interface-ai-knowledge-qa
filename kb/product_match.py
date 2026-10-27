"""Align question product intent with fact row subject and page path (no eval literals)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from kb.textutil import tokenize

GENERIC = frozenset(
    {
        "what",
        "the",
        "is",
        "are",
        "do",
        "does",
        "for",
        "on",
        "to",
        "you",
        "your",
        "dupaco",
        "rate",
        "rates",
        "loan",
        "loans",
        "account",
        "accounts",
        "year",
        "model",
        "month",
        "months",
        "apr",
        "apy",
        "new",
        "current",
        "published",
        "interest",
        "much",
        "many",
        "give",
        "tell",
        "provide",
        "apply",
        "applies",
        "vehicle",
        "vehicles",
    }
)


def _path_tokens(url: str) -> set[str]:
    path = urlparse(url).path.lower()
    return {t for t in re.split(r"[/\-_#]+", path) if len(t) > 2}


def _page_category(url: str) -> str | None:
    u = url.lower()
    if any(x in u for x in ("recreational", "boat", "rv")):
        return "recreational"
    if any(x in u for x in ("auto-motorcycle", "auto-loans", "auto-motorcycle-loans")):
        return "vehicle"
    if "home-loan" in u or "home-loans" in u:
        return "home"
    if "credit-card" in u:
        return "card"
    if "checking" in u:
        return "checking"
    if "savings" in u:
        return "savings"
    return None


def _question_category(question: str) -> str | None:
    q = question.lower()
    if any(w in q for w in ("boat", "rv", "recreational", "marine", "watercraft")):
        return "recreational"
    if any(w in q for w in ("auto", "motorcycle", "car")):
        return "vehicle"
    if any(w in q for w in ("mortgage", "home loan", "refinance", "30-year", "15-year")):
        return "home"
    if "credit card" in q or ("card" in q and "apr" in q):
        return "card"
    if "checking" in q:
        return "checking"
    if any(w in q for w in ("certificate", "share certificate", " cd ", "cd rate")):
        return "savings"
    if "money market" in q:
        return "money_market"
    if re.search(r"\bhsa\b", q):
        return "hsa"
    if "share" in q and "savings" in q and "money market" not in q:
        return "share_savings"
    return None


def product_aligns(question: str, fact) -> bool:
    ql = question.lower()
    path = _path_tokens(fact.url)
    row = set(tokenize(f"{fact.subject} {fact.section} {fact.field}"))
    prod = path | row

    q_cat = _question_category(question)
    f_cat = _page_category(fact.url)
    if q_cat == "vehicle" and f_cat == "recreational":
        return False
    if q_cat == "recreational" and f_cat == "vehicle":
        return False

    if "business" in ql and "business" not in fact.url.lower():
        if "credit" in ql or "card" in ql:
            return False
    if re.search(r"\bpersonal\b", ql) and "business" in fact.url.lower():
        if "credit" in ql or "card" in ql:
            return False

    if q_cat == "money_market":
        return "money" in prod and "market" in prod
    if q_cat == "hsa":
        return "hsa" in prod or "hsa" in fact.url.lower()
    if q_cat == "share_savings":
        if "money" in prod and "market" in prod and "share" not in prod:
            return False
        if "hsa" in prod and "share" not in prod:
            return False

    if q_cat == "checking" and f_cat == "savings" and "checking" not in prod:
        return False

    focus = {t for t in tokenize(question) if len(t) >= 4 and t not in GENERIC}
    if not focus:
        return True
    if focus & prod:
        return True
    if q_cat and f_cat and q_cat == f_cat:
        return True
    if q_cat in ("vehicle", "recreational", "home", "card", "checking", "savings"):
        return f_cat == q_cat
    return True
