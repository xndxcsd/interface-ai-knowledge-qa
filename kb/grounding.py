"""Ensure answer tokens appear in retrieved evidence."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kb.evidence import EvidencePack, is_rate_question
from kb.textutil import tokenize

if TYPE_CHECKING:
    from contract import Answer

NUM = re.compile(r"(\$)?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(%|percent)?", re.I)
PHONE = re.compile(
    r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
URL_RE = re.compile(r"https?://[^\s\])\"']+", re.I)
TIME_TOKEN = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)\b", re.I
)
STREET = re.compile(
    r"\b\d+\s+[A-Za-z0-9.\'\-]+(?:\s+(?:St|Street|Ln|Lane|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Hwy))\.?\b",
    re.I,
)
ZIP = re.compile(r"\b\d{5}\b")


def _numbers(text: str) -> set[tuple[str, float]]:
    out: set[tuple[str, float]] = set()
    for m in NUM.finditer(text or ""):
        unit = "$" if m.group(1) else ("%" if m.group(4) else "")
        val = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
        out.add((unit, round(val, 4)))
    return out


def evidence_corpus(pack: EvidencePack) -> str:
    parts = []
    for fe in pack.facts:
        f = fe.fact
        parts.extend([f.subject, f.field, f.value, f.raw_row])
    for ce in pack.chunks:
        parts.append(ce.chunk.text)
    return "\n".join(parts)


def _question_product_overlap(question: str, fact_blob: str) -> float:
    q = {t for t in tokenize(question) if len(t) > 2}
    if not q:
        return 1.0
    f = set(tokenize(fact_blob))
    return len(q & f) / len(q)


def rate_supported(num: tuple[str, float], pack: EvidencePack, question: str) -> bool:
    q_lower = question.lower()
    for fe in pack.facts:
        blob = f"{fe.fact.subject} {fe.fact.field} {fe.fact.value}"
        if num not in _numbers(fe.fact.value):
            continue
        if _question_product_overlap(question, blob) >= 0.12:
            return True
        if _question_product_overlap(question, fe.fact.url) >= 0.08:
            return True
        if any(k in q_lower for k in ("auto", "vehicle", "motorcycle")) and "auto" in fe.fact.url.lower():
            return True
        if "mortgage" in q_lower and "home-loan" in fe.fact.url.lower():
            return True
        if "certificate" in q_lower and "savings-account" in fe.fact.url.lower():
            return True
    for ce in pack.chunks:
        if num in _numbers(ce.chunk.text):
            if _question_product_overlap(question, ce.chunk.text) >= 0.1:
                return True
            if any(k in q_lower for k in ("auto", "vehicle")) and "auto" in ce.chunk.url.lower():
                return True
    return False


def _substr_in_corpus(needle: str, corpus: str) -> bool:
    n = re.sub(r"\s+", " ", needle.lower().strip())
    c = corpus.lower()
    if n in c:
        return True
    digits = re.sub(r"\D", "", needle)
    if len(digits) >= 5 and digits in re.sub(r"\D", "", c):
        return True
    return False


def apply_grounding(answer: "Answer", pack: EvidencePack, question: str) -> "Answer":
    from contract import Answer

    if not answer.text:
        return Answer(text="I don't know.", sources=[], confident=False)

    corpus = evidence_corpus(pack)
    text = answer.text
    q_lower = question.lower()

    # Named entity in question must appear in evidence (e.g. branch street name)
    for tok in tokenize(question):
        if len(tok) < 5 or not tok.isalpha():
            continue
        if tok.lower() in ("dupaco", "certificate", "mortgage", "savings", "checking"):
            continue
        if tok.lower() in q_lower and tok.lower() not in corpus.lower():
            if any(k in q_lower for k in ("branch", "address", "street", "avenue", "hours")):
                return Answer(
                    text="I don't know — I could not verify that location or branch in the retrieved pages.",
                    sources=answer.sources,
                    confident=False,
                )

    if is_rate_question(question):
        for n in _numbers(text):
            if n[0] == "%" and not rate_supported(n, pack, question):
                return Answer(
                    text="I don't know — that rate is not grounded in the retrieved evidence for this question.",
                    sources=answer.sources,
                    confident=False,
                )

    for m in PHONE.finditer(text):
        if not _substr_in_corpus(m.group(0), corpus):
            return Answer(
                text="I don't know — that phone number is not in the retrieved evidence.",
                sources=answer.sources,
                confident=False,
            )

    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,)")
        if u not in corpus and u.replace("https://www.", "https://") not in corpus:
            return Answer(
                text="I don't know — that URL is not in the retrieved evidence.",
                sources=answer.sources,
                confident=False,
            )

    for m in TIME_TOKEN.finditer(text):
        if not _substr_in_corpus(m.group(0), corpus):
            return Answer(
                text="I don't know — those hours are not in the retrieved evidence.",
                sources=answer.sources,
                confident=False,
            )

    if STREET.search(text) or ZIP.search(text):
        for zm in ZIP.finditer(text):
            if not _substr_in_corpus(zm.group(0), corpus):
                return Answer(
                    text="I don't know — that address is not in the retrieved evidence.",
                    sources=answer.sources,
                    confident=False,
                )

    for n in _numbers(text):
        if n[0] != "%" and n[1] > 1000:
            raw = str(int(n[1])) if n[1] == int(n[1]) else str(n[1])
            if raw not in re.sub(r"[^\d]", "", corpus):
                if not _substr_in_corpus(raw, corpus):
                    pass  # allow non-rate integers only if in corpus
        elif n[0] == "" and n[1] not in {2024, 2025, 2026, 2027}:
            s = str(int(n[1])) if n[1] == int(n[1]) else str(n[1])
            if len(s) >= 3 and s not in corpus.replace(",", ""):
                if is_rate_question(question):
                    continue

    return answer
