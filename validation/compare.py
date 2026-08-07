"""
Diff the Python model against the Excel workbook, row by row, year by year.

This is the check that decides whether the port can be trusted. It runs every
scenario, compares every line item of every engine sheet against the figures
Excel itself produced (validation/baselines/*.json, extracted by
extract_excel_baseline.py), and reports every discrepancy.

A mismatch is a translation bug to chase, not a rounding quirk to wave through.
The tolerance below is set for floating-point noise only -- around a
billionth of a pound on figures in the tens of millions. Anything a person
could notice fails.

Run:  python validation/compare.py            # all scenarios, summary
      python validation/compare.py --verbose  # every mismatching year
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.assumptions import load                # noqa: E402
from engine.model import run                       # noqa: E402
from engine.state import SHEET_MAP                 # noqa: E402

BASELINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines")

# Validation runs on the assumptions frozen at the moment of the port, NOT on
# the live ones in assumptions/. The Excel workbook is a fixed artefact; asking
# whether the engine reproduces it is only meaningful against the inputs it was
# reproduced with. See port_reference/README.md.
PORT_REFERENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "port_reference")

# Relative tolerance for non-trivial numbers, absolute for values near zero.
REL_TOL = 1e-9
ABS_TOL = 1e-6

# How many mismatching years to print per row before truncating.
MAX_DETAIL = 6


class Mismatch:
    def __init__(self, sheet, row, label, year, expected, actual):
        self.sheet = sheet
        self.row = row
        self.label = label
        self.year = year
        self.expected = expected
        self.actual = actual

    @property
    def delta(self):
        if isinstance(self.expected, (int, float)) and isinstance(self.actual, (int, float)):
            return self.actual - self.expected
        return None

    def __str__(self):
        if self.delta is None:
            return f"year {self.year:>2}: excel={self.expected!r} python={self.actual!r}"
        return (
            f"year {self.year:>2}: excel={self.expected:>20,.6f} "
            f"python={self.actual:>20,.6f} delta={self.delta:>+15,.6f}"
        )


def values_match(expected, actual) -> bool:
    """Compare one cell, tolerating floating-point noise but nothing more."""
    # Excel writes "" for a blank guarded result; the model uses "" too.
    if isinstance(expected, str) or isinstance(actual, str):
        e = "" if expected is None else expected
        a = "" if actual is None else actual
        return str(e) == str(a)

    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False

    if expected == actual:
        return True
    diff = abs(actual - expected)
    if diff <= ABS_TOL:
        return True
    return diff <= REL_TOL * max(abs(expected), abs(actual))


class Coverage:
    """
    How much was actually checked.

    A validation that passes because it compared nothing is worse than no
    validation at all, so the run reports its own reach and fails if a row it
    was told to check turned out to be missing on either side.
    """

    def __init__(self):
        self.cells = 0
        self.rows = 0
        self.skipped: list[str] = []


def compare_scenario(scenario: str, verbose: bool = False) -> tuple[list[Mismatch], Coverage]:
    """Run one scenario and diff every captured row against Excel."""
    path = os.path.join(BASELINE_DIR, f"{scenario}.json")
    if not os.path.exists(path):
        sys.exit(
            f"No baseline for {scenario!r}. Run validation/extract_excel_baseline.py first."
        )
    with open(path, encoding="utf-8") as f:
        baseline = json.load(f)

    result = run(load(scenario, assumptions_dir=PORT_REFERENCE_DIR))
    mismatches: list[Mismatch] = []
    cov = Coverage()

    for sheet_name, (state_attr, row_map) in SHEET_MAP.items():
        if sheet_name not in baseline["sheets"]:
            cov.skipped.append(f"{sheet_name} (no baseline)")
            continue
        sheet_baseline = baseline["sheets"][sheet_name]
        state_obj = getattr(result.state, state_attr)

        for row, attr in row_map.items():
            key = str(row)
            if key not in sheet_baseline:
                cov.skipped.append(f"{sheet_name}!row {row} (not in baseline)")
                continue
            expected_values = sheet_baseline[key]["values"]
            label = sheet_baseline[key]["label"] or attr
            actual_values = getattr(state_obj, attr)

            if not actual_values:
                cov.skipped.append(f"{sheet_name}!row {row} ({attr} is empty)")
                continue

            cov.rows += 1
            for idx, expected in enumerate(expected_values):
                if idx >= len(actual_values):
                    break
                cov.cells += 1
                actual = actual_values[idx]
                if not values_match(expected, actual):
                    mismatches.append(Mismatch(sheet_name, row, label, idx + 1, expected, actual))

    _compare_cohorts(baseline, result, mismatches, cov)
    return mismatches, cov


# Asset Register cohort blocks: one row per acquisition vintage. Row 10 is the
# Year-1 vintage's value, row 66 is its rent, and both run 50 rows down.
COHORT_VALUE_FIRST_ROW = 10
COHORT_RENT_FIRST_ROW = 66


def _compare_cohorts(baseline, result, mismatches: list[Mismatch], cov: Coverage) -> None:
    """
    Diff every acquisition vintage individually.

    The portfolio total is a sum over cohorts, so two vintages wrong in
    offsetting directions would leave row 61 looking correct. Checking each
    vintage separately is what rules that out -- and it is where a cohort
    seeded in the wrong year, or compounded by the wrong index, would show up.
    """
    sheet = baseline["sheets"].get("Asset Register")
    if sheet is None:
        cov.skipped.append("Asset Register cohorts (no baseline)")
        return

    blocks = (
        ("value", COHORT_VALUE_FIRST_ROW, result.state.assets.cohort_value),
        ("rent", COHORT_RENT_FIRST_ROW, result.state.assets.cohort_rent),
    )

    for kind, first_row, cohorts in blocks:
        for k, series in enumerate(cohorts):
            row = first_row + k
            key = str(row)
            if key not in sheet:
                cov.skipped.append(f"Asset Register!row {row} (cohort {kind}, not in baseline)")
                continue
            expected_values = sheet[key]["values"]
            label = sheet[key]["label"] or f"cohort {k + 1} {kind}"

            cov.rows += 1
            for idx, expected in enumerate(expected_values):
                if idx >= len(series):
                    break
                cov.cells += 1
                if not values_match(expected, series[idx]):
                    mismatches.append(
                        Mismatch("Asset Register", row, label, idx + 1, expected, series[idx])
                    )


def report(scenario: str, mismatches: list[Mismatch], cov: Coverage, verbose: bool) -> None:
    """Print a per-row summary of what disagrees."""
    if not mismatches:
        print(f"  {scenario:<11} OK — {cov.cells:,} cells across {cov.rows} rows match Excel")
        return

    # Group by (sheet, row) so one broken line item reads as one problem.
    grouped: dict[tuple[str, int], list[Mismatch]] = {}
    for mm in mismatches:
        grouped.setdefault((mm.sheet, mm.row), []).append(mm)

    print(
        f"  {scenario:<11} {len(mismatches)} mismatching cells "
        f"across {len(grouped)} rows (of {cov.cells:,} cells / {cov.rows} rows checked)"
    )
    for (sheet, row), items in sorted(grouped.items()):
        worst = max(
            (m for m in items if m.delta is not None),
            key=lambda m: abs(m.delta),
            default=None,
        )
        worst_str = f", worst delta {worst.delta:+,.6f}" if worst else ""
        print(f"    {sheet}!row {row} — {items[0].label}")
        print(f"      {len(items)} of 50 years differ{worst_str}")
        shown = items if verbose else items[:MAX_DETAIL]
        for mm in shown:
            print(f"        {mm}")
        if not verbose and len(items) > MAX_DETAIL:
            print(f"        ... {len(items) - MAX_DETAIL} more (use --verbose)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", help="only check this scenario")
    parser.add_argument("--verbose", action="store_true", help="show every mismatching year")
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario else ["base", "optimistic", "stress"]

    print("Comparing Python model against Excel baselines")
    print(f"  tolerance: {REL_TOL:g} relative, {ABS_TOL:g} absolute\n")

    total = 0
    skipped: list[str] = []
    for scenario in scenarios:
        mismatches, cov = compare_scenario(scenario, args.verbose)
        total += len(mismatches)
        skipped.extend(f"{scenario}: {s}" for s in cov.skipped)
        report(scenario, mismatches, cov, args.verbose)

    if skipped:
        print(f"\n  {len(skipped)} rows could not be checked:")
        for item in skipped:
            print(f"    {item}")

    print()
    if total == 0 and not skipped:
        print("PASS — the Python model reproduces the Excel workbook exactly.")
        return 0
    if total == 0:
        print("INCOMPLETE — everything checked matches, but some rows were skipped above.")
        return 1
    print(f"FAIL — {total} mismatching cells. Each one is a translation bug to chase.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
