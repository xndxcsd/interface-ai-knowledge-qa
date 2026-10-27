"""Fail if eval gold literals appear in submission source (anti-cheating)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
SCAN = [ROOT / "solution.py", *sorted((ROOT / "kb").glob("*.py"))]


def _literals_in_python(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts: list[str] = []

    class V(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str):
                parts.append(node.value)

    V().visit(tree)
    return "\n".join(parts).lower()


def _banned_from_eval() -> set[str]:
    out: set[str] = set()
    for path in EVAL_DIR.glob("*.jsonl"):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            for key in ("must_include", "must_not_include"):
                for raw in item.get(key) or []:
                    s = str(raw).strip().lower()
                    if len(s) >= 12 and "dupaco.com" not in s:
                        out.add(s)
                    if len(s) >= 12 and "dupaco.com" in s and " " in s:
                        out.add(s)
                    for m in re.finditer(r"\d+\.\d+", s):
                        out.add(m.group(0))
                    for m in re.finditer(r"\b\d{9}\b", s):
                        out.add(m.group(0))
                    for m in re.finditer(r"\b\d{5}\b", s):
                        out.add(m.group(0))
    structural = re.compile(r"^(personal|business|connect|about)/[\w\-/]+$")
    return {t for t in out if not structural.match(t)}


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
            elif tok in lits:
                violations.append(f"{path.name}: {tok!r}")
    assert not violations, "Eval leakage in string literals:\n" + "\n".join(
        sorted(set(violations))
    )
