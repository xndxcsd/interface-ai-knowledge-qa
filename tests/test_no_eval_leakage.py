"""Fail if eval gold literals appear in submission source (anti-cheating)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
SCAN = [ROOT / "solution.py", *sorted((ROOT / "kb").glob("*.py"))]
STRUCTURAL = re.compile(r"^(personal|business|connect|about)/[\w\-/]+$")
ALLOW = frozenset(
    {
        "%",
        "apy",
        "apr",
        "dupaco",
        "routing",
        "phone",
        "branch",
        "hours",
        "account",
        "accounts",
        "business",
        "personal",
        "contact",
        "certificate",
        "savings",
        "checking",
        "loan",
        "loans",
        "member",
        "student",
        "share",
        "visa",
        "facts",
        "table",
        "term",
        "info",
        "join",
        "locations",
        "number",
        "that",
        "find",
        "west",
        "dupaco.com",
        "info.dupaco.com",
        "vehicle",
        "vehicles",
        "motorcycle",
        "auto",
        "rate",
        "rates",
    }
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


def _tokens_from_gold(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    low = s.lower()
    if not low:
        return out
    if len(low) >= 12 and low not in ALLOW:
        out.add(low)
    for m in re.finditer(r"\d+\.\d+", low):
        out.add(m.group(0))
    for m in re.finditer(r"\b\d{9}\b", low):
        out.add(m.group(0))
    for m in re.finditer(r"\b\d{5}\b", low):
        out.add(m.group(0))
    for m in re.finditer(r"\d{1,2}:\d{2}", low):
        out.add(m.group(0))
    if "join." in low or "info.dupaco.com" in low and " " in s:
        out.add(low)
        host = re.sub(r"^https?://(www\.)?", "", low).split("/")[0]
        if host and host not in ALLOW and "join." in host:
            out.add(host)
    if len(low) >= 14 and "dupaco.com" in low and "/" in low:
        out.add(low)
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        out.add(m.group(0).lower())
    for m in re.finditer(r"\b[A-Z][a-z]{3,}\b", s):
        out.add(m.group(0).lower())
    for word in re.findall(r"[a-zA-Z']+", s):
        w = word.lower()
        if len(w) >= 5 and w not in ALLOW and w.isalpha():
            out.add(w)
    return out


def _banned_from_eval() -> set[str]:
    out: set[str] = set()
    for path in EVAL_DIR.glob("*.jsonl"):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            for key in ("must_include", "must_not_include", "expected_answer"):
                for raw in item.get(key) or []:
                    if raw:
                        out |= _tokens_from_gold(str(raw))
    return {t for t in out if t and not STRUCTURAL.match(t) and t not in ALLOW}


def test_no_eval_literals_in_kb_source():
    banned = _banned_from_eval()
    violations: list[str] = []
    for path in SCAN:
        lits = _literals_in_python(path)
        whole = path.read_text(encoding="utf-8").lower()
        for tok in banned:
            if len(tok) >= 9 and tok.isdigit():
                if tok in whole:
                    violations.append(f"{path.name}: {tok!r}")
            elif len(tok) >= 4 and tok in lits:
                violations.append(f"{path.name}: {tok!r}")
            elif len(tok) >= 6 and "dupaco" in tok and tok in lits:
                violations.append(f"{path.name}: {tok!r}")
    assert not violations, "Eval leakage in string literals:\n" + "\n".join(
        sorted(set(violations))
    )
