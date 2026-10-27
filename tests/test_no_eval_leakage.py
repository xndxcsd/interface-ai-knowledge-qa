"""Fail if eval gold literals appear in submission source (anti-cheating)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
SCAN = [ROOT / "solution.py", *sorted((ROOT / "kb").glob("*.py"))]
ALLOW = frozenset(
    {
        "%", "apy", "apr", "dupaco", "rate", "rates", "business", "personal",
        "rewards", "savings-account", "credit-cards", "checking-accounts",
        "personal/savings-account", "personal/credit-cards", "personal/checking-accounts",
    }
)
STRUCTURAL = re.compile(r"^(personal|business|connect|about)/[\w\-/]+$")


def _literals(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts: list[str] = []

    class V(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str):
                parts.append(node.value)

    V().visit(tree)
    return "\n".join(parts).lower()


def _banned_tokens() -> set[str]:
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
                        s = str(raw).strip().lower()
                        if len(s) >= 5 and s not in ALLOW:
                            out.add(s)
            exp = item.get("expected_answer")
            if isinstance(exp, str) and len(exp.strip()) >= 16:
                out.add(exp.strip().lower())
    return out


def _question_ngrams(min_words: int = 4) -> set[str]:
    ngrams: set[str] = set()
    for path in EVAL_DIR.glob("*.jsonl"):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            q = json.loads(line).get("question")
            if not isinstance(q, str):
                continue
            words = re.findall(r"[a-z0-9'.-]+", q.lower())
            for n in range(min_words, len(words) + 1):
                for i in range(len(words) - n + 1):
                    ng = " ".join(words[i : i + n])
                    if len(ng) >= 12:
                        ngrams.add(ng)
    return ngrams


def _split_groups(banned: set[str]) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    for tok in banned:
        if "-" in tok:
            parts = tuple(p for p in tok.split("-") if len(p) >= 3)
            if len(parts) >= 2:
                groups.append(parts)
    return groups


def _and_in_q_splits(path: Path, groups: list[tuple[str, ...]]) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    qnames = {"q", "ql", "question", "query"}

    def lit_in_q(node: ast.AST) -> str | None:
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            return None
        if not isinstance(node.ops[0], ast.In):
            return None
        if len(node.comparators) != 1 or not isinstance(node.comparators[0], ast.Name):
            return None
        if node.comparators[0].id not in qnames:
            return None
        if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            return node.left.value.lower()
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            lits = sorted(x for v in node.values if (x := lit_in_q(v)))
            if len(lits) >= 2:
                for g in groups:
                    if tuple(sorted(g)) == tuple(lits):
                        out.append(f"{path.name}: and-in-q split {lits!r}")
                        break
    return out


def test_no_eval_literals_in_kb_source():
    banned = _banned_tokens()
    ngrams = _question_ngrams()
    groups = _split_groups(banned)
    violations: list[str] = []
    for path in SCAN:
        lits = _literals(path)
        for tok in banned:
            if tok in ALLOW or STRUCTURAL.match(tok):
                continue
            if len(tok) >= 6 and re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", lits):
                violations.append(f"{path.name}: {tok!r}")
        for ng in ngrams:
            if re.search(rf"(?<![a-z0-9]){re.escape(ng)}(?![a-z0-9])", lits):
                violations.append(f"{path.name}: n-gram {ng!r}")
        for parts in groups:
            if any(p in ALLOW for p in parts):
                continue
            if all(re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", lits) for p in parts):
                violations.append(f"{path.name}: split {parts!r}")
        violations.extend(_and_in_q_splits(path, groups))
    assert not violations, "Eval leakage:\n" + "\n".join(sorted(set(violations)))
