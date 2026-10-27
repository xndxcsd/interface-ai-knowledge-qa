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
    {
        "%",
        "apy",
        "apr",
        "dupaco",
        "rate",
        "rates",
        "business",
        "student",
        "platinum",
        "rewards",
        "savings-account",
        "credit-cards",
        "checking-accounts",
        "personal",
    }
)
COMMON_TITLE = frozenset(
    {
        "what", "how", "when", "where", "who", "why", "which", "does", "can", "could",
        "would", "should", "is", "are", "was", "were", "do", "did", "has", "have",
        "the", "and", "for", "with", "from", "into", "your", "you", "our", "their",
        "free", "annual", "month", "months", "year", "model", "new", "current",
        "member", "members", "service", "phone", "number", "listed", "apply",
        "applies", "offer", "offers", "program", "account", "accounts", "checking",
        "savings", "credit", "loan", "loans", "rate", "rates", "dupaco", "visa",
        "mastercard", "mobile", "online", "banking", "branch", "branches", "lobby",
        "drive", "up", "window", "hours", "open", "close", "address", "street",
        "iowa", "illinois", "wisconsin", "indiana", "minnesota", "missouri",
        "certificate", "fixed", "special", "jumbo", "share", "money", "market",
        "home", "boat", "auto", "vehicle", "mortgage", "refinance", "student",
        "personal", "business", "give", "read", "provide", "include", "answer",
        "quote", "name", "main", "avenue", "lane", "about", "people", "after",
    }
)
SPLIT_STOP = frozenset(
    COMMON_TITLE | ALLOW | {"up", "lab", "mon", "fri", "thu", "tue", "wed", "or", "less", "in", "store"}
)


def token_in_banned(needle: str, banned: set[str]) -> bool:
    n = re.sub(r"\s+", " ", needle.lower().strip())
    for word in re.findall(r"[a-z0-9'.-]+", n):
        if word in banned and len(word) >= 4:
            return True
    for b in banned:
        bl = b.lower()
        if n == bl:
            return True
        if " " in n and n in bl:
            return True
        if " " in bl and bl in n:
            return True
        if re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", bl):
            return True
        if re.search(rf"(?<![a-z0-9]){re.escape(bl)}(?![a-z0-9])", n):
            return True
    return False


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


def _distinctive_proper_nouns(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    for m in re.finditer(r"(?<=[a-z]\s)[A-Z][a-z]{4,}[A-Za-z'\-]*\b", s):
        w = m.group(0).lower().rstrip("'s")
        if w not in COMMON_TITLE and w not in ALLOW:
            out.add(w)
    for m in re.finditer(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b", s):
        w = m.group(0).lower()
        if w not in ALLOW:
            out.add(w)
    return out


def _tokens_from_must_token(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    low = s.lower()
    if not low:
        return out
    if len(low) >= 4:
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
    for m in re.finditer(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b", s):
        out.add(m.group(0).lower())
    return {t for t in out if t and not STRUCTURAL.match(t) and t not in ALLOW}


def _tokens_from_expected_answer(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    low = s.lower()
    if len(low) >= 16:
        out.add(low)
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        phrase = m.group(0).lower()
        out.add(phrase)
        for w in phrase.split():
            if len(w) >= 5 and w not in COMMON_TITLE:
                out.add(w)
    for m in TIME_RANGE.finditer(s):
        out.add(re.sub(r"\s+", " ", m.group(0).lower()))
    out |= _distinctive_proper_nouns(s)
    return {t for t in out if t and t not in ALLOW}


def _tokens_from_question(raw: str) -> set[str]:
    s = str(raw).strip()
    out: set[str] = set()
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", s):
        out.add(m.group(0).lower())
    for m in TIME_RANGE.finditer(s):
        out.add(re.sub(r"\s+", " ", m.group(0).lower()))
    for m in re.finditer(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b", s):
        out.add(m.group(0).lower())
    out |= _distinctive_proper_nouns(s)
    low = s.lower()
    for m in re.finditer(r"[a-z][a-z\s,'-]{8,}[a-z]", low):
        phrase = re.sub(r"\s+", " ", m.group(0).strip())
        if len(phrase.split()) >= 2 and len(phrase) >= 12:
            out.add(phrase)
    return {t for t in out if t and t not in ALLOW}


def _set_like_string_literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()

    def collect_from_set(node: ast.Set) -> None:
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.add(elt.value.lower())

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else ""
            if name in ("frozenset", "set") and node.args and isinstance(node.args[0], ast.Set):
                collect_from_set(node.args[0])
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            if isinstance(node.value, ast.Set):
                collect_from_set(node.value)
            self.generic_visit(node)

    V().visit(tree)
    return out


def _frozenset_string_literals(path: Path) -> set[str]:
    return _set_like_string_literals(path)


def _eval_questions() -> list[str]:
    out: list[str] = []
    for path in EVAL_DIR.glob("*.jsonl"):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            q = item.get("question")
            if isinstance(q, str) and q.strip():
                out.append(q.strip())
    return out


def _question_ngrams_from_eval(min_words: int = 4) -> set[str]:
    ngrams: set[str] = set()
    for q in _eval_questions():
        words = re.findall(r"[a-z0-9'.-]+", q.lower())
        for n in range(min_words, len(words) + 1):
            for i in range(len(words) - n + 1):
                ngrams.add(" ".join(words[i : i + n]))
    return ngrams


def _eval_question_vocab() -> set[str]:
    vocab: set[str] = set()
    for q in _eval_questions():
        vocab |= _whole_words(q.lower())
    return {w for w in vocab if len(w) >= 3 and w not in COMMON_TITLE}


def _sets_in_python(path: Path) -> list[frozenset[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[frozenset[str]] = []

    def add_members(members: set[str]) -> None:
        if len(members) >= 2:
            out.append(frozenset(members))

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else ""
            if name in ("frozenset", "set") and node.args and isinstance(node.args[0], ast.Set):
                members: set[str] = set()
                for elt in node.args[0].elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        members.add(elt.value.lower())
                add_members(members)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            if isinstance(node.value, ast.Set):
                members = {
                    elt.value.lower()
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                }
                add_members(members)
            self.generic_visit(node)

    V().visit(tree)
    return out


def _frozensets_in_python(path: Path) -> list[frozenset[str]]:
    return _sets_in_python(path)


def _and_in_q_split_violations(path: Path, split_groups: list[tuple[str, ...]]) -> list[str]:
    if not split_groups:
        return []
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    violations: list[str] = []
    q_names = {"q", "ql", "question", "query", "text"}

    def compare_literal(node: ast.AST) -> str | None:
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            return None
        if not isinstance(node.ops[0], ast.In):
            return None
        if len(node.comparators) != 1:
            return None
        comp = node.comparators[0]
        if isinstance(comp, ast.Name) and comp.id in q_names:
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                return node.left.value.lower()
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.And):
            continue
        lits = [compare_literal(v) for v in node.values]
        lits = [x for x in lits if x]
        if len(lits) < 2:
            continue
        parts = tuple(sorted(lits))
        for group in split_groups:
            if tuple(sorted(group)) == parts:
                violations.append(
                    f"{path.name}: and-in-q split {parts!r} (evasion of compound eval phrase)"
                )
                break
    return violations


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


def _split_token_groups(banned: set[str]) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for tok in banned:
        if "-" in tok:
            parts = tuple(p for p in tok.split("-") if len(p) >= 2)
            if len(parts) >= 2 and not any(p in SPLIT_STOP for p in parts):
                if parts not in seen:
                    seen.add(parts)
                    groups.append(parts)
        if tok.isalpha() and len(tok) >= 8:
            for i in range(3, len(tok) - 2):
                parts = (tok[:i], tok[i:])
                if len(parts[0]) >= 4 and len(parts[1]) >= 3 and not any(
                    p in SPLIT_STOP for p in parts
                ):
                    if parts not in seen:
                        seen.add(parts)
                        groups.append(parts)
    return groups


def _whole_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9'.-]+", text.lower()))


def scan_path_for_violations(
    path: Path,
    banned: set[str],
    split_groups: list[tuple[str, ...]],
    *,
    question_ngrams: set[str] | None = None,
    eval_q_vocab: set[str] | None = None,
) -> list[str]:
    question_ngrams = question_ngrams or set()
    eval_q_vocab = eval_q_vocab or set()
    violations: list[str] = []
    lits = _literals_in_python(path)
    comments = _comments_in_python(path)
    combined = lits + "\n" + comments
    words = _whole_words(combined)
    whole = path.read_text(encoding="utf-8").lower()
    for ng in question_ngrams:
        if len(ng) < 12:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(ng)}(?![a-z0-9])", combined):
            violations.append(f"{path.name}: question n-gram {ng!r}")
    for tok in banned:
        if " " in tok and len(tok) >= 12 and re.search(
            rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", combined
        ):
            violations.append(f"{path.name}: question phrase {tok!r}")
    for fs in _frozensets_in_python(path):
        if len(fs) < 2:
            continue
        if all(w in eval_q_vocab for w in fs):
            violations.append(
                f"{path.name}: frozenset all eval question words {sorted(fs)!r}"
            )
    for tok in _frozenset_string_literals(path):
        if tok in banned and len(tok) >= 4:
            violations.append(f"{path.name}: stopword {tok!r}")
    for tok in banned:
        if len(tok) >= 9 and tok.isdigit():
            if tok in whole:
                violations.append(f"{path.name}: {tok!r}")
        elif len(tok) >= 4 and re.search(
            rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", combined
        ):
            violations.append(f"{path.name}: {tok!r}")
        elif "dupaco.com" in tok and tok in combined:
            violations.append(f"{path.name}: {tok!r}")
    for parts in split_groups:
        if all(p in words for p in parts):
            violations.append(
                f"{path.name}: split tokens {parts!r} (evasion of compound eval phrase)"
            )
    violations.extend(_and_in_q_split_violations(path, split_groups))
    return violations


def test_no_eval_literals_in_kb_source():
    banned = _banned_from_eval()
    split_groups = _split_token_groups(banned)
    question_ngrams = _question_ngrams_from_eval()
    eval_q_vocab = _eval_question_vocab()
    violations: list[str] = []
    for path in SCAN:
        violations.extend(
            scan_path_for_violations(
                path,
                banned,
                split_groups,
                question_ngrams=question_ngrams,
                eval_q_vocab=eval_q_vocab,
            )
        )
    assert not violations, "Eval leakage in string literals:\n" + "\n".join(
        sorted(set(violations))
    )
