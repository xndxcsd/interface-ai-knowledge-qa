"""Distinctive eval gold tokens and planted phrases must be in the banned set / caught."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tests.test_no_eval_leakage import SCAN, _literals_in_python, _banned_from_eval


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
        "6 p.m.",
    ):
        assert any(tok in b or b in tok for b in banned), (
            f"expected eval gold token {tok!r} in banned set"
        )


def test_planted_literals_in_source_would_fail():
    plants = [
        "Galena branch",
        "8 a.m.",
        "fifth",
        "join.dupaco.com",
    ]
    for plant in plants:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(f'X = "{plant}"\n')
            path = Path(f.name)
        lits = _literals_in_python(path)
        path.unlink(missing_ok=True)
        assert plant.lower() in lits, plant
        banned = _banned_from_eval()
        assert any(plant.lower() in b or b in plant.lower() for b in banned), plant
