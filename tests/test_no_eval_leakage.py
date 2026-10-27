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
        "join.dupaco.com", "credit", "union", "visa", "checking", "savings", "home",
        "market", "money", "boat", "branch", "hours", "lobby", "drive", "street",
        "avenue", "mon", "fri", "thu", "tue", "wed", "model", "year",
    }
)
COMMON = frozenset(
    {
        "what", "when", "where", "which", "who", "how", "does", "give", "provide",
        "quote", "main", "named", "tell", "your", "our", "the", "and", "for",
        "answer", "include", "about", "month", "certificate", "shared",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
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


def _whole_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9'.-]+", text.lower()))


def _tokens_from_must(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    low = s.lower()
    if 4 <= len(low) <= 40 and " " not in low and low not in ALLOW and low not in COMMON:
        out.add(low)
    for m in re.finditer(r"\b\d{5,}\b", low):
        out.add(m.group(0))
    for m in re.finditer(r"\d{1,2}:\d{2}", low):
        out.add(m.group(0))
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        out.add(m.group(0).lower())
    for m in re.finditer(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b", s):
        out.add(m.group(0).lower())
    for m in re.finditer(r"\b[A-Z][a-z]{5,}\b", s):
        w = m.group(0).lower()
        if w not in ALLOW | COMMON:
            out.add(w)
    return {t for t in out if t and t not in ALLOW and not STRUCTURAL.match(t)}


def _tokens_from_question(q: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", q):
        phrase = m.group(0).lower()
        if phrase not in ALLOW and not all(w in ALLOW | COMMON for w in phrase.split()):
            out.add(phrase)
    for m in re.finditer(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b", q):
        tok = m.group(0).lower()
        if tok not in ALLOW:
            out.add(tok)
    for m in re.finditer(r"\b([A-Z][a-z]{5,})\b", q):
        w = m.group(1).lower()
        if w not in ALLOW | COMMON:
            out.add(w)
    return {t for t in out if t not in ALLOW and t not in COMMON}


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
                        if raw:
                            out |= _tokens_from_must(str(raw))
            exp = item.get("expected_answer")
            if isinstance(exp, str) and exp.strip():
                out |= _tokens_from_must(exp)
            q = item.get("question")
            if isinstance(q, str) and q.strip():
                out |= _tokens_from_question(q)
    return {
        t
        for t in out
        if t not in ALLOW
        and not (t in COMMON and " " not in t and "-" not in t and not any(c.isdigit() for c in t))
    }


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
    seen: set[tuple[str, ...]] = set()
    for tok in banned:
        if "-" in tok:
            parts = tuple(p for p in tok.split("-") if len(p) >= 3)
            if len(parts) >= 2 and parts not in seen:
                seen.add(parts)
                groups.append(parts)
        if tok.isalpha() and len(tok) >= 8 and tok not in ALLOW:
            for i in range(3, len(tok) - 2):
                parts = (tok[:i], tok[i:])
                if any(p in ALLOW | COMMON for p in parts):
                    continue
                if len(parts[0]) >= 4 and len(parts[1]) >= 3 and parts not in seen:
                    seen.add(parts)
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


def _has_whole_word(haystack: str, token: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack) is not None


def scan_path_for_literals(
    path: Path,
    banned: set[str],
    groups: list[tuple[str, ...]],
    ngrams: set[str],
) -> list[str]:
    """Return violation messages for one source file (used by tests and main scan)."""
    violations: list[str] = []
    lits = _literals(path)
    words = _whole_words(lits)
    for tok in banned:
        if tok in ALLOW | COMMON or STRUCTURAL.match(tok):
            continue
        if len(tok) >= 4 and _has_whole_word(lits, tok):
            violations.append(f"{path.name}: {tok!r}")
        elif len(tok) >= 9 and tok.isdigit() and tok in lits:
            violations.append(f"{path.name}: {tok!r}")
    for ng in ngrams:
        if _has_whole_word(lits, ng):
            violations.append(f"{path.name}: n-gram {ng!r}")
    for parts in groups:
        if any(p in ALLOW | COMMON for p in parts):
            continue
        if all(_has_whole_word(lits, p) for p in parts):
            violations.append(f"{path.name}: split {parts!r}")
        elif all(p in words for p in parts):
            violations.append(f"{path.name}: split-words {parts!r}")
    violations.extend(_and_in_q_splits(path, groups))
    return violations


def test_no_eval_literals_in_kb_source():
    banned = _banned_tokens()
    ngrams = _question_ngrams()
    groups = _split_groups(banned)
    violations: list[str] = []
    for path in SCAN:
        violations.extend(scan_path_for_literals(path, banned, groups, ngrams))
    assert not violations, "Eval leakage:\n" + "\n".join(sorted(set(violations)))
