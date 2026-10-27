"""Map question themes to canonical site paths (structure only, not eval wording)."""
from __future__ import annotations

import re


def _has(q: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", q, re.I) is not None


def _has_any(q: str, words: tuple[str, ...]) -> bool:
    return any(_has(q, w) for w in words)


def is_list_question(question: str) -> bool:
    q = question.lower()
    if re.search(r"\bcredit\s+cards?\b", q):
        return True
    if _has(q, "card") and _has_any(q, ("offer", "what", "which", "name", "list", "each")):
        return True
    if " and " in q and _has_any(q, ("card", "certificate", "account", "loan", "visa")):
        return True
    return _has_any(
        q,
        ("list", "each", "every", "all", "both", "types"),
    ) and _has_any(q, ("card", "certificate", "rate", "loan", "visa", "apy", "apr"))


def is_broad_rate_question(question: str) -> bool:
    q = question.lower()
    return _has_any(q, ("rates", "rate sheet")) and _has_any(
        q, ("mortgage", "certificate", "checking", "savings", "loan", "credit")
    )


def is_hours_question(question: str) -> bool:
    q = question.lower()
    return _has_any(q, ("hour", "hours", "open", "close")) and _has_any(
        q, ("lobby", "drive", "branch", "typical", "general")
    )


def canonical_path_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    if _has(q, "card") or re.search(r"\bvisa\b", q):
        hints.extend(["personal/credit-cards", "business/credit-cards"])
    pairs = (
        (("certificate", "cd"), "personal/savings-account"),
        (("checking",), "personal/checking-accounts"),
        (("mortgage", "refinance"), "personal/loans/home-loans"),
        (("auto", "motorcycle", "vehicle"), "personal/loans/auto-motorcycle-loans"),
        (("boat", "recreational"), "personal/loans/recreational-loans"),
        (("routing", "aba"), "business/cash-management"),
        (("branch", "lobby", "atm", "locator", "address"), "contact"),
        (("join", "membership", "eligible", "qualify", "geography"), "about/join"),
        (("wallet", "mobile"), "connect/online-and-mobile-banking"),
        (("student", "college"), "personal/loans"),
        (("bright", "jump", "launchpad", "savings"), "personal/savings-account"),
    )
    for keys, path in pairs:
        if _has_any(q, keys):
            hints.append(path)
    if re.search(r"\bpersonal\s+loans?\b", q):
        hints.append("personal/loans/personal-loans")
    if _has(q, "money") and _has(q, "market"):
        hints.append("personal/savings-account")
    if _has(q, "rv") and not _has(q, "service"):
        hints.append("personal/loans/recreational-loans")
    if _has(q, "forbes"):
        hints.append("newsroom/forbes")
    if _has(q, "volunteer"):
        hints.append("newsroom")
    if _has(q, "hy") and "vee" in q:
        hints.extend(["contact", "newsroom"])
    if is_hours_question(question):
        hints.append("newsroom")
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
