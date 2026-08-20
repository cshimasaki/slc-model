"""
Loading and resolving the assumptions layer.

A scenario is Base plus a set of deltas. This module flattens the sectioned
YAML into the flat namespace the engine works in -- the section headings exist
for the reader, not for the formulas -- and derives the handful of values the
workbook itself derives rather than takes as input.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import yaml

from . import stock

ASSUMPTIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assumptions")

# Model horizon, fixed by the workbook's layout (columns D:BA).
N_YEARS = 50
# Monthly Cash Flow covers years 1-5 only (columns D:BK).
N_MONTHS = 60


class AssumptionError(Exception):
    """Raised when an assumptions file is missing a parameter or malformed."""


@dataclass
class Assumptions:
    """
    A fully resolved parameter set for one scenario.

    Access is by the workbook's own named ranges (`a.pf_ltv_limit`), so a
    formula that read `pf_ltv_limit` in Excel reads the same name here.
    `sections` keeps the original grouping for the JSON bundle and the
    explorer's assumptions panel.
    """

    name: str
    values: dict[str, Any]
    sections: dict[str, dict[str, Any]]

    def __getattr__(self, key: str) -> Any:
        try:
            return self.values[key]
        except KeyError:
            raise AttributeError(f"no assumption named {key!r} in scenario {self.name!r}") from None

    def __contains__(self, key: str) -> bool:
        return key in self.values


def _deep_merge(base: dict, delta: dict) -> dict:
    """Merge a scenario's deltas onto Base, one section at a time."""
    out = {section: dict(params) for section, params in base.items()}
    for section, params in delta.items():
        if section not in out:
            raise AssumptionError(
                f"section {section!r} is not in base.yaml -- a scenario file can only "
                f"override parameters that Base defines"
            )
        for key, value in params.items():
            if key not in out[section]:
                raise AssumptionError(
                    f"parameter {key!r} in section {section!r} is not in base.yaml -- "
                    f"a scenario file can only override parameters that Base defines"
                )
            out[section][key] = value
    return out


def _derive(values: dict[str, Any]) -> None:
    """
    Add the values the workbook computes rather than accepts as input.

    Control & Parameters row 17 is `=SUM(E14:E16)`: the coupon SLC actually pays
    is the investor's annuity rate plus the fund's operating margin plus its
    regulatory capital charge. Deriving it here keeps the three components as
    the editable inputs, exactly as the sheet does.
    """
    values["pf_coupon_spread"] = (
        values["pf_investor_rate"] + values["pf_fund_op_margin"] + values["pf_fund_reg_charge"]
    )

    # The average house and its yield come from the acquisition mix, when one is
    # given. Everything downstream still reads `avg_price` and `gross_yield`, so
    # the cohort machinery is untouched -- the mix just decides what those two
    # numbers are, instead of somebody typing an average and hoping.
    #
    # Absent in the frozen port-reference assumptions, which carry the
    # workbook's single average house directly. That is what keeps the Excel
    # comparison valid.
    if "stock_types" in values:
        values["avg_price"], values["gross_yield"] = stock.blended(values["stock_types"])


def load(scenario: str, assumptions_dir: str | None = None) -> Assumptions:
    """
    Load a scenario by name ("base", "optimistic", "stress").

    Base is always read first; any other scenario is applied on top of it as a
    set of deltas.
    """
    directory = assumptions_dir or ASSUMPTIONS_DIR
    scenario = scenario.lower()

    base_path = os.path.join(directory, "base.yaml")
    if not os.path.exists(base_path):
        raise AssumptionError(f"base.yaml not found in {directory}")
    with open(base_path, encoding="utf-8") as f:
        sections = yaml.safe_load(f)

    if scenario != "base":
        delta_path = os.path.join(directory, f"{scenario}.yaml")
        if not os.path.exists(delta_path):
            raise AssumptionError(f"scenario file not found: {delta_path}")
        with open(delta_path, encoding="utf-8") as f:
            delta = yaml.safe_load(f) or {}
        sections = _deep_merge(sections, delta)

    values: dict[str, Any] = {}
    for section, params in sections.items():
        for key, value in params.items():
            if key in values:
                raise AssumptionError(f"parameter {key!r} appears in more than one section")
            values[key] = value

    _derive(values)
    return Assumptions(name=scenario, values=values, sections=sections)


def load_all(assumptions_dir: str | None = None) -> dict[str, Assumptions]:
    """Load every scenario, keyed by name."""
    return {s: load(s, assumptions_dir) for s in ("base", "optimistic", "stress")}


def scenario_deltas(assumptions_dir: str | None = None) -> dict[str, dict[str, Any]]:
    """
    Return each non-Base scenario's raw deltas, for display.

    The explorer shows Base/Optimistic/Stress side by side; this says which
    cells are genuinely overridden rather than inherited.
    """
    directory = assumptions_dir or ASSUMPTIONS_DIR
    out: dict[str, dict[str, Any]] = {}
    for scenario in ("optimistic", "stress"):
        with open(os.path.join(directory, f"{scenario}.yaml"), encoding="utf-8") as f:
            sections = yaml.safe_load(f) or {}
        flat = {k: v for params in sections.values() for k, v in params.items()}
        out[scenario] = flat
    return out
