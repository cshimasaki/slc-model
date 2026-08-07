"""
Build the JSON bundle: every assumption and every scenario's full results.

This is the handoff between Python and everything that displays results. The
explorer page reads it and renders; it does not recompute. The Excel export
reads the same figures, so the workbook and the web page can never disagree.

The bundle carries all three scenarios at once, which is what makes switching
and comparing instant in the browser with no server and no client-side model.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import yaml

from engine.assumptions import ASSUMPTIONS_DIR, load_all, scenario_deltas
from engine.model import ModelRun, run_all

from .series import CHARTS, HEADLINES, SERIES, SERIES_BY_KEY

SCENARIOS = ["base", "optimistic", "stress"]

# Covenant thresholds now live in assumptions/base.yaml under `covenants`,
# because they are policy rather than reporting furniture. Kept as a fallback
# for the frozen port reference, which predates that section.
DSCR_COVENANT = 1.20
DSCR_TARGET = 1.50


def _resolve(state, source: str) -> list:
    """Pull a series off ModelState given its "attr.field" address."""
    attr, field = source.split(".")
    return list(getattr(getattr(state, attr), field))


def _numeric(values: list) -> list[float]:
    """Drop the blanks the model emits where a ratio is undefined."""
    return [v for v in values if isinstance(v, (int, float))]


def _reduce(values: list, how: str):
    nums = _numeric(values)
    if not nums:
        return None
    if how == "last":
        return values[-1] if isinstance(values[-1], (int, float)) else nums[-1]
    if how == "min":
        return min(nums)
    if how == "max":
        return max(nums)
    raise ValueError(f"unknown reduction {how!r}")


def build_assumptions_block() -> list[dict[str, Any]]:
    """
    All assumptions, grouped by the workbook's sections, with each scenario's
    value side by side and a flag for whether it was overridden or inherited.
    """
    with open(os.path.join(ASSUMPTIONS_DIR, "labels.yaml"), encoding="utf-8") as f:
        labels = yaml.safe_load(f)

    loaded = load_all()
    deltas = scenario_deltas()

    blocks = []
    for section_key, entries in labels.items():
        title = entries.get("_title", section_key)
        params = []
        for key, meta in entries.items():
            if key == "_title":
                continue
            derived = bool(meta.get("derived"))
            params.append({
                "key": key,
                "label": meta["label"],
                "unit": meta["unit"],
                "row": meta["row"],
                # A derived value is computed from other parameters, not read
                # from a scenario file. Flagged so the page can show it as a
                # result rather than something to edit.
                "derived": derived,
                "values": {s: loaded[s].values.get(key) for s in SCENARIOS},
                # True where the scenario file sets the value; False where it
                # inherits Base, mirroring the sheet's "=$E9" cells.
                "overridden": {
                    "base": not derived,
                    "optimistic": (not derived) and key in deltas["optimistic"],
                    "stress": (not derived) and key in deltas["stress"],
                },
            })
        blocks.append({"key": section_key, "title": title, "params": params})
    return blocks


def build_scenario_block(result: ModelRun) -> dict[str, Any]:
    """One scenario's full year-by-year output."""
    state = result.state

    series = {}
    for spec in SERIES:
        values = _resolve(state, spec.source)
        # JSON has no concept of Excel's empty string for an undefined ratio;
        # null is the honest representation and the page skips those points.
        series[spec.key] = [v if isinstance(v, (int, float)) else None for v in values]

    headline = {}
    for key, label, series_key, how in HEADLINES:
        headline[key] = {
            "label": label,
            "value": _reduce(series[series_key], how),
            "unit": SERIES_BY_KEY[series_key].unit,
        }

    # Counts that need a threshold, so they can't come from the generic
    # headline reduction above.
    a = result.assumptions
    cash_min = getattr(a, "cov_cash_cover_min", DSCR_COVENANT)
    rent_min = getattr(a, "cov_rent_only_min", 1.0)
    rent_by = getattr(a, "cov_rent_only_by_year", 20)

    cash = _numeric(series["cash_interest_cover"])
    headline["years_cash_cover_breach"] = {
        "label": f"Years cash cover below {cash_min:.2f}x",
        "value": sum(1 for v in cash if v < cash_min),
        "unit": "count",
    }

    # When does the portfolio start paying its own interest from rent? The
    # single most useful number on this page, and the one currently furthest
    # from where it should be.
    first_self = None
    for idx, v in enumerate(series["rent_only_cover"]):
        if v is not None and v >= rent_min:
            first_self = idx + 1
            break
    headline["first_self_financing_year"] = {
        "label": f"First year rent alone covers interest (target: by {rent_by})",
        "value": first_self,
        "unit": "count",
    }

    dscr = _numeric(series["dscr"])
    headline["years_dscr_breach"] = {
        "label": f"Years all-income cover below {DSCR_COVENANT:.2f}x (legacy)",
        "value": sum(1 for v in dscr if v < DSCR_COVENANT),
        "unit": "count",
    }
    headline["years_capital_call"] = {
        "label": "Years needing a capital call",
        "value": sum(1 for v in series["capital_call"] if v and v > 1),
        "unit": "count",
    }
    headline["years_unfunded"] = {
        "label": "Years with unfunded acquisitions",
        "value": sum(1 for v in series["unfunded_requirement"] if v and v > 1),
        "unit": "count",
    }

    monthly = {
        "months": list(state.monthly.month),
        "model_year": list(state.monthly.model_year),
        "net_movement": list(state.monthly.net_movement),
        "free_cash": list(state.monthly.free_cash),
        "buffer_status": list(state.monthly.buffer_status),
    }

    return {
        "name": result.scenario,
        "years": list(range(1, result.n_years + 1)),
        "calendar_years": list(result.macro.calendar_year),
        "series": series,
        "headline": headline,
        "monthly": monthly,
        # Reference lines the charts draw, resolved per scenario since the LTV
        # limit itself differs between them.
        "reference": {
            "pf_ltv_limit": result.assumptions.pf_ltv_limit,
            "__dscr_covenant": DSCR_COVENANT,
            "__dscr_target": DSCR_TARGET,
            "__cash_cover_min": getattr(result.assumptions, "cov_cash_cover_min", DSCR_COVENANT),
            "__rent_only_min": getattr(result.assumptions, "cov_rent_only_min", 1.0),
            "__rent_only_by": getattr(result.assumptions, "cov_rent_only_by_year", 20),
            "min_cash_buffer": result.assumptions.min_cash_buffer,
        },
    }


def build(results: dict[str, ModelRun] | None = None) -> dict[str, Any]:
    """Assemble the whole bundle."""
    results = results or run_all()

    return {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "source": "Financial Modelling for SLC V2.1.xlsx",
            "n_years": results["base"].n_years,
            "scenarios": SCENARIOS,
            "note": (
                "Computed by the Python model in engine/. This file is generated — "
                "edit assumptions/*.yaml and re-run, never edit this."
            ),
        },
        "assumptions": build_assumptions_block(),
        "charts": [
            {
                "key": c.key, "title": c.title, "unit": c.unit, "kind": c.kind,
                "series": c.series, "reference": c.reference, "caption": c.caption,
            }
            for c in CHARTS
        ],
        "series_meta": {
            s.key: {"label": s.label, "unit": s.unit, "note": s.note} for s in SERIES
        },
        "scenarios": {name: build_scenario_block(r) for name, r in results.items()},
    }


def write(path: str, results: dict[str, ModelRun] | None = None) -> str:
    """Write the bundle to `path` and return it."""
    bundle = build(results)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"))
    return path
