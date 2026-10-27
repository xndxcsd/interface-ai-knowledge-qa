"""Fail if eval gold literals appear in submission source (anti-cheating)."""
from __future__ import annotations

import ast
import json
import re
import tokenize as py_tokenize
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
SCAN = [ROOT / "solution.py", *sorted((ROOT / "kb").glob("*.py"))]
STRUCTURAL = re.compile(r"^(personal|business|connect|about)/[\w\-/]+$")
ALLOW = frozenset(
    {"%", "apy", "apr", "dupaco", "rate", "rates", "business", "student", "platinum", "rewards"}
)
TIME_RANGE = re.compile(
    r"\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)\s*[-–—]\s*"
    r"\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)",
    re.I,
)


def _literals_in_python(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts: list[str] = []

    class V(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str):
                parts.append(node.value)

    V().visit(tree)
    return "\n".join(parts).lower()


def _comments_in_python(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    out: list[str] = []
    try:
        for tok in py_tokenize.generate_tokens(StringIO(src).readline):
            if tok.type == py_tokenize.COMMENT:
                out.append(tok.string.lstrip("#").strip())
    except py_tokenize.TokenError:
        pass
    return "\n".join(out).lower()


def _tokens_from_must_token(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    low = s.lower()
    if not low:
        return out
    if (
        any(c.isdigit() for c in low)
        or "dupaco.com" in low
        or " " in low
        or len(low) >= 12
    ):
        out.add(low)
    for m in re.finditer(r"\d+\.\d+", low):
        out.add(m.group(0))
    for m in re.finditer(r"\b\d{9}\b", low):
        out.add(m.group(0))
    for m in re.finditer(r"\b\d{5}\b", low):
        out.add(m.group(0))
    for m in re.finditer(r"\d{1,2}:\d{2}", low):
        out.add(m.group(0))
    for m in TIME_RANGE.finditer(s):
        out.add(re.sub(r"\s+", " ", m.group(0).lower()))
    if "join." in low or ("dupaco.com" in low and len(low) >= 10):
        out.add(low)
        if "join." in low:
            out.add("join.dupaco.com")
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        out.add(m.group(0).lower())
    return {t for t in out if t and not STRUCTURAL.match(t) and t not in ALLOW}


def _tokens_from_expected_answer(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    low = s.lower()
    if len(low) >= 16:
        out.add(low)
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        out.add(m.group(0).lower())
    for m in TIME_RANGE.finditer(s):
        out.add(re.sub(r"\s+", " ", m.group(0).lower()))
    return {t for t in out if t and t not in ALLOW}


def _tokens_from_question(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        out.add(m.group(0).lower())
    for m in TIME_RANGE.finditer(s):
        out.add(re.sub(r"\s+", " ", m.group(0).lower()))
    return {t for t in out if t and t not in ALLOW}


def _banned_from_eval() -> set[str]:
    out: set[str] = set()
    for path in EVAL_DIR.glob("*.jsonl"):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            for key in ("must_include", "must_not_include"):
                val = item.get(key)
                if isinstance(val, list):
                    for raw in val:
                        if raw:
                            out |= _tokens_from_must_token(str(raw))
            exp = item.get("expected_answer")
            if isinstance(exp, str) and exp.strip():
                out |= _tokens_from_expected_answer(exp)
            q = item.get("question")
            if isinstance(q, str) and q.strip():
                out |= _tokens_from_question(q)
    return out


def test_no_eval_literals_in_kb_source():
    banned = _banned_from_eval()
    violations: list[str] = []
    for path in SCAN:
        lits = _literals_in_python(path)
        comments = _comments_in_python(path)
        combined = lits + "\n" + comments
        whole = path.read_text(encoding="utf-8").lower()
        for tok in banned:
            if len(tok) >= 9 and tok.isdigit():
                if tok in whole:
                    violations.append(f"{path.name}: {tok!r}")
            elif len(tok) >= 4 and tok in combined:
                violations.append(f"{path.name}: {tok!r}")
            elif "dupaco.com" in tok and tok in combined:
                violations.append(f"{path.name}: {tok!r}")
    assert not violations, "Eval leakage in string literals:\n" + "\n".join(
        sorted(set(violations))
    )
