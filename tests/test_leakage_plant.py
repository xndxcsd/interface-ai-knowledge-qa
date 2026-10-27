"""Distinctive eval gold tokens and planted phrases must be in the banned set / caught."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tests.test_no_eval_leakage import (
    SCAN,
    _banned_from_eval,
    _literals_in_python,
    _split_token_groups,
    scan_path_for_violations,
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
        "Oldenburg",
    ]
    banned = _banned_from_eval()
    split_groups = _split_token_groups(banned)
    for plant in plants:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(f'X = "{plant}"\n')
            path = Path(f.name)
        lits = _literals_in_python(path)
        assert plant.lower() in lits, plant
        assert token_in_banned(plant, banned), plant
        assert scan_path_for_violations(path, banned, split_groups), plant
        path.unlink(missing_ok=True)


def test_split_token_evasion_would_fail():
    banned = _banned_from_eval()
    split_groups = _split_token_groups(banned)
    assert token_in_banned("hy-vee", banned)
    assert token_in_banned("oldenburg", banned)
    for src in (
        'if "hy" in q and "vee" in q:\n    pass\n',
        'a, b = "olden", "burg"\n',
    ):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            path = Path(f.name)
        v = scan_path_for_violations(path, banned, split_groups)
        path.unlink(missing_ok=True)
        assert v, src
