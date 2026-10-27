"""Distinctive eval gold tokens and planted phrases must be in the banned set / caught."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from tests.test_no_eval_leakage import (
    SCAN,
    _banned_from_eval,
    _literals_in_python,
    token_in_banned,
)


def test_distinctive_gold_tokens_are_banned():
    banned = _banned_from_eval()
    for tok in (
        "273974581",
        "800-373-7600",
        "11375",
        "8:30",
        "fifth",
        "join.dupaco.com",
        "galena branch",
        "hy-vee",
        "galena",
        "oldenburg",
        "forbes",
        "mullan",
        "launchpad",
    ):
        assert token_in_banned(tok, banned), f"expected eval gold token {tok!r} in banned set"


def test_planted_literals_in_source_would_fail():
    plants = [
        "Galena branch",
        "8 a.m.",
        "fifth",
        "join.dupaco.com",
        "Forbes fifth time",
    ]
    banned = _banned_from_eval()
    for plant in plants:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(f'X = "{plant}"\n')
            path = Path(f.name)
        lits = _literals_in_python(path)
        path.unlink(missing_ok=True)
        assert plant.lower() in lits, plant
        assert token_in_banned(plant, banned), plant


def test_split_token_evasion_would_fail():
    banned = _banned_from_eval()
    assert token_in_banned("hy-vee", banned)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write('if "hy" in q and "vee" in q:\n    pass\n')
        path = Path(f.name)
    lits = _literals_in_python(path)
    path.unlink(missing_ok=True)
    from tests.test_no_eval_leakage import _split_token_groups, _whole_words

    words = _whole_words(lits)
    groups = _split_token_groups(banned)
    assert any(all(p in words for p in parts) for parts in groups if "hy" in parts)
