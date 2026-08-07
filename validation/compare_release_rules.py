"""
Compare the two Tontine release rules, side by side, across every scenario.

This is the evidence for the MODEL_LOG entry on the run-off release rule: what
changing the mechanism actually did, rather than an assertion that it is
better.

Run:  python validation/compare_release_rules.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.assumptions import load                      # noqa: E402
from engine.model import run                             # noqa: E402
from engine.tontine_runoff import load_curve             # noqa: E402

SCENARIOS = ["base", "optimistic", "stress"]


def run_mode(scenario: str, mode: str):
    a = load(scenario)
    a.values["pf_release_mode"] = mode
    return run(a, check=False)


def summarise(r):
    c, f = r.state.capital, r.state.statements
    dscr = [v for v in c.dscr if isinstance(v, (int, float))]
    peak = max(c.tf_closing) or 1.0
    return {
        "balance_y50": c.tf_closing[-1],
        "pct_of_peak": c.tf_closing[-1] / peak,
        "released_total": sum(-v for v in c.tf_release),
        "release_starts": next((i + 1 for i, v in enumerate(c.tf_release) if v < 0), None),
        "min_dscr": min(dscr) if dscr else None,
        "breaches": sum(1 for v in dscr if v < 1.20),
        "net_assets": f.net_assets[-1],
        "reserve_released": f.reserve_tontine_released[-1],
    }


def main() -> int:
    curve = load_curve()
    print("Tontine release rule: geometric (original) vs runoff (liability-tracking)")
    print(f"Actuarial curve: cohort effectively gone by fund year "
          f"{curve.last_survivor_year()} (1% of the initial cohort)\n")

    for scenario in SCENARIOS:
        print(f"--- {scenario.upper()} ---")
        rows = {m: summarise(run_mode(scenario, m)) for m in ("geometric", "runoff")}
        keys = [
            ("release_starts", "First release (model year)", "{:>12}"),
            ("released_total", "Total released over 50 yrs", "{:>12,.0f}"),
            ("balance_y50", "Charge outstanding at Y50", "{:>12,.0f}"),
            ("pct_of_peak", "  as % of peak balance", "{:>12.1%}"),
            ("reserve_released", "Cumulative credit to reserves", "{:>12,.0f}"),
            ("min_dscr", "Minimum DSCR", "{:>12.3f}"),
            ("breaches", "Years below 1.20x covenant", "{:>12}"),
            ("net_assets", "Net assets at Y50", "{:>12,.0f}"),
        ]
        print(f"{'':<32}{'geometric':>14}{'runoff':>14}")
        for key, label, fmt in keys:
            g, n = rows["geometric"][key], rows["runoff"][key]
            gs = fmt.format(g) if g is not None else "          n/a"
            ns = fmt.format(n) if n is not None else "          n/a"
            print(f"{label:<32}{gs:>14}{ns:>14}")
        print()

    print("The geometric rule decays but never completes: a third of the charge is")
    print("still outstanding at year 50, so SLC carries the liability indefinitely.")
    print("The runoff rule discharges as the annuitant liability actually runs off,")
    print("and cannot fully discharge while anyone is still alive to be paid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
