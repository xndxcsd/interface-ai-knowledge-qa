"""Map question themes to canonical site paths (structure only)."""
from __future__ import annotations

import re

from kb.textutil import has_any_word, has_word


def is_list_question(question: str) -> bool:
    q = question.lower()
    if re.search(r"\bcredit\s+cards?\b", q):
        return True
    if has_word(q, "card") and has_any_word(
        q, ("list", "each", "every", "all", "both", "types", "which", "what", "offer")
    ):
        return True
    if " and " in q and has_any_word(q, ("card", "certificate", "account", "loan", "visa")):
        return True
    return has_any_word(q, ("list", "each", "every", "all", "both", "types")) and has_any_word(
        q, ("card", "certificate", "rate", "loan", "visa", "apy", "apr")
    )


def is_broad_rate_question(question: str) -> bool:
    q = question.lower()
    return has_any_word(q, ("rates", "rate sheet")) and has_any_word(
        q, ("mortgage", "certificate", "checking", "savings", "loan", "credit")
    )


def is_hours_question(question: str) -> bool:
    q = question.lower()
    return has_any_word(q, ("hour", "hours", "open", "close")) and has_any_word(
        q, ("lobby", "drive", "branch")
    )


def is_rate_question(question: str) -> bool:
    if has_any_word(
        question,
        ("rate", "rates", "apy", "apr", "dividend", "interest", "yield", "percent"),
    ):
        return True
    if has_word(question, "cd") or has_word(question, "certificate"):
        return True
    return "%" in question


def canonical_path_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    if has_word(q, "card") or re.search(r"\bvisa\b", q):
        hints.extend(["personal/credit-cards", "business/credit-cards"])
    pairs = (
        (("certificate", "cd"), "personal/savings-account"),
        (("checking",), "personal/checking-accounts"),
        (("mortgage", "refinance"), "personal/loans/home-loans"),
        (("auto", "motorcycle", "vehicle"), "personal/loans/auto-motorcycle-loans"),
        (("boat", "recreational"), "personal/loans/recreational-loans"),
        (("routing", "aba"), "business/cash-management"),
        (("branch", "lobby", "atm", "locator", "address"), "contact"),
        (("join", "membership", "eligible"), "about/join"),
        (("wallet", "mobile"), "connect/online-and-mobile-banking"),
        (("savings",), "personal/savings-account"),
    )
    for keys, path in pairs:
        if has_any_word(q, keys):
            hints.append(path)
    if re.search(r"\bpersonal\s+loans?\b", q):
        hints.append("personal/loans/personal-loans")
    if has_word(q, "money") and has_word(q, "market"):
        hints.append("personal/savings-account")
    if has_word(q, "rv"):
        hints.append("personal/loans/recreational-loans")
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def expand_list_path_hints(path_hints: list[str], question: str) -> list[str]:
    if not is_list_question(question):
        return path_hints
    q = question.lower()
    hints = list(path_hints)
    if has_word(q, "card") or has_word(q, "visa") or re.search(r"\bcredit\s+cards?\b", q):
        for p in ("personal/credit-cards", "business/credit-cards"):
            if p not in hints:
                hints.append(p)
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
