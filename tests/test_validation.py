"""
Tests for the validation harness itself.

The most important test here is `test_validator_detects_drift`. A comparison
that always passes is indistinguishable from a comparison that works, until the
day it matters. This proves the harness fails when it should.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "validation"))

from engine.assumptions import load                    # noqa: E402
from engine.model import run                           # noqa: E402
from engine.state import SHEET_MAP                     # noqa: E402

import importlib.util                                  # noqa: E402

_spec = importlib.util.spec_from_file_location("compare", os.path.join(ROOT, "validation", "compare.py"))
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)

SCENARIOS = ["base", "optimistic", "stress"]


def _baseline_exists(scenario: str) -> bool:
    return os.path.exists(os.path.join(compare.BASELINE_DIR, f"{scenario}.json"))


requires_baselines = pytest.mark.skipif(
    not all(_baseline_exists(s) for s in SCENARIOS),
    reason="Excel baselines not extracted; run validation/extract_excel_baseline.py",
)


@requires_baselines
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_matches_excel(scenario):
    """Every captured row reproduces the Excel workbook exactly."""
    mismatches, cov = compare.compare_scenario(scenario)
    assert not cov.skipped, f"rows went unchecked: {cov.skipped}"
    assert cov.cells > 10000, f"suspiciously few cells checked: {cov.cells}"
    assert not mismatches, "\n".join(
        f"{m.sheet}!row {m.row} year {m.year}: excel={m.expected} python={m.actual}"
        for m in mismatches[:20]
    )


@requires_baselines
def test_validator_detects_drift():
    """
    The negative control.

    Nudge one parameter by a tenth of a percent -- the smallest plausible
    fat-finger -- and the comparison must notice. If this test ever passes
    while test_matches_excel also passes with a broken model, the harness is
    lying.
    """
    with open(os.path.join(compare.BASELINE_DIR, "base.json"), encoding="utf-8") as f:
        baseline = json.load(f)

    # Perturb the FROZEN port-time assumptions, not the live ones. Starting
    # from the live assumptions would mismatch anyway -- they have moved on
    # from the workbook by design -- so the test would pass without proving
    # anything about the harness.
    a = load("base", assumptions_dir=compare.PORT_REFERENCE_DIR)
    a.values["void_rate"] *= 1.001
    result = run(a, check=False)

    mismatches = []
    for sheet_name, (attr, row_map) in SHEET_MAP.items():
        if sheet_name not in baseline["sheets"]:
            continue
        sheet_baseline = baseline["sheets"][sheet_name]
        state_obj = getattr(result.state, attr)
        for row, name in row_map.items():
            if str(row) not in sheet_baseline:
                continue
            expected = sheet_baseline[str(row)]["values"]
            actual = getattr(state_obj, name)
            if not actual:
                continue
            for i, exp in enumerate(expected):
                if i >= len(actual):
                    break
                if not compare.values_match(exp, actual[i]):
                    mismatches.append((sheet_name, row, i + 1))

    assert mismatches, (
        "a 0.1% change to void_rate produced no mismatches -- "
        "the validation harness cannot detect drift"
    )


@requires_baselines
def test_excel_check_survives_assumption_changes():
    """
    Changing a project assumption must NOT break the Excel comparison.

    This is the whole point of freezing the port-time inputs. The workbook is a
    fixed artefact; the project's assumptions are not. If tuning an assumption
    turned the validation red, people would learn to ignore it, and the next
    genuine translation bug would arrive to an audience that had stopped
    reading the signal.
    """
    live = load("base")
    frozen = load("base", assumptions_dir=compare.PORT_REFERENCE_DIR)

    assert live.pf_investor_rate != frozen.pf_investor_rate, (
        "this test is vacuous unless the live assumptions have actually moved "
        "away from the frozen port-time ones"
    )

    mismatches, cov = compare.compare_scenario("base")
    assert not mismatches, "the Excel check must not depend on live assumptions"
    assert cov.cells > 10000


def test_port_reference_is_complete():
    """Every scenario the comparison checks must have a frozen input file."""
    for scenario in SCENARIOS:
        path = os.path.join(compare.PORT_REFERENCE_DIR, f"{scenario}.yaml")
        assert os.path.exists(path), f"missing frozen assumptions for {scenario}"
        loaded = load(scenario, assumptions_dir=compare.PORT_REFERENCE_DIR)
        assert loaded.pf_max_raise > 0


def test_values_match_tolerates_only_float_noise():
    """The tolerance admits floating-point dust and nothing a person would see."""
    assert compare.values_match(1_000_000.0, 1_000_000.0 + 1e-9)
    assert compare.values_match(0.0, 1e-12)
    assert not compare.values_match(1_000_000.0, 1_000_000.01)   # a penny
    assert not compare.values_match(100.0, 100.5)
    assert compare.values_match("", "")
    assert not compare.values_match("", 0.0)
