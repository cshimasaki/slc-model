"""
The Tontine liability run-off curve, and the release rule built on it.

Background
----------
The original workbook released a flat 6% of the outstanding balance each year
from year 25. That is geometric: with CPI uplift it decays about 3.65% a year
and never reaches zero, so at year 50 more than a third of the charge is still
outstanding. It is a parametric stand-in, not a mechanism.

The indicative actuarial model (August 2026) found the real constraint, and it
is not the release *start* date -- it is the *completion* date. Discharge the
charges before the last annuitant dies and the residual survivors are left with
no assets backing them, which is terminal insolvency however healthy the fund
looked at year 25. Under the placeholder basis the last annuitant dies around
year 54.

The rule implemented here
-------------------------
Discharge tracks the liability run-off, holding a target coverage multiple of
technical provisions, and never fully discharges while any annuitant survives.

    target outstanding(t) = coverage_target x technical provisions(t)
    release(t)            = outstanding(t) - target outstanding(t), floored at 0

Because technical provisions stay positive while anyone is alive, the target
stays positive too, so the last-survivor floor is structural rather than a
separate rule that could be mis-set. The failure mode is removed by
construction, not by choosing parameters carefully.

It also acts directly on the actuarial model's other finding: the fund is
collateralised at 2.13x its liabilities. `coverage_target` is that ratio made
explicit and tunable, rather than an accident of the release schedule.

What is a placeholder here
--------------------------
The curve in assumptions/tontine_runoff.csv is population mortality, not
annuitant mortality, so it understates longevity. And the scaling below assumes
this model's drawdown profile has the same *shape* as the indicative model's
(a level GBP 5m a year for 10 years). Ours is demand-driven and lumpier, so
this is an approximation -- reasonable for a placeholder, and the reason the
whole thing is arranged so the September dataset replaces one CSV.
"""

from __future__ import annotations

import csv
import os
from bisect import bisect_right
from dataclasses import dataclass

ASSUMPTIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assumptions"
)
RUNOFF_FILE = "tontine_runoff.csv"


class RunoffError(Exception):
    """Raised when the run-off curve is missing or malformed."""


@dataclass(frozen=True)
class RunoffCurve:
    """Technical provisions per GBP 1 raised, and lives, by fund year."""

    fund_years: tuple[int, ...]
    tp_per_pound: tuple[float, ...]
    lives_index: tuple[float, ...]
    survivorship: tuple[float, ...]

    def tp_at(self, fund_year: int) -> float:
        """
        Technical provisions per GBP 1 raised, `fund_year` years after the first
        drawdown. Beyond the end of the curve the liability is exhausted.
        """
        if fund_year < 0:
            return 0.0
        if fund_year >= len(self.tp_per_pound):
            return 0.0
        return self.tp_per_pound[fund_year]

    def survival_at(self, age: int) -> float:
        """
        Probability an investor who entered at 65 is alive `age` years later.

        This is the quantity the charge actually depends on: a charge is
        released when its own investor dies, so what matters is that
        investor's survival from their own entry -- not the fund's aggregate
        headcount, which rises during the investment phase as cohorts join.
        """
        if age <= 0:
            return 1.0
        if age >= len(self.survivorship):
            return 0.0
        return self.survivorship[age]

    def lives_at(self, fund_year: int) -> float:
        if fund_year < 0 or fund_year >= len(self.lives_index):
            return 0.0
        return self.lives_index[fund_year]

    # A cohort never mathematically reaches zero -- the survival curve only
    # approaches it -- so "the last annuitant dies" needs a stated threshold.
    # 1% of the first year's cohort is the convention used here.
    LAST_SURVIVOR_THRESHOLD = 0.01

    def last_survivor_year(self, threshold: float | None = None) -> int:
        """
        The fund year by which the cohort is effectively gone, approximately.

        Reporting only. The release rule needs no last-survivor test of its own:
        it tracks a liability that is non-zero exactly while someone is left to
        be paid, so the floor is structural rather than a threshold that could
        be mis-set.
        """
        cut = self.LAST_SURVIVOR_THRESHOLD if threshold is None else threshold
        for i in range(len(self.lives_index) - 1, -1, -1):
            if self.lives_index[i] > cut:
                return self.fund_years[i]
        return 0


def load_curve(assumptions_dir: str | None = None) -> RunoffCurve:
    """Read the run-off curve exported from the actuarial model."""
    path = os.path.join(assumptions_dir or ASSUMPTIONS_DIR, RUNOFF_FILE)
    if not os.path.exists(path):
        raise RunoffError(
            f"Tontine run-off curve not found: {path}\n"
            f"Regenerate it with: python validation/extract_tontine_runoff.py"
        )

    years: list[int] = []
    tp: list[float] = []
    lives: list[float] = []
    surv: list[float] = []
    with open(path, encoding="utf-8") as f:
        # The file leads with a provenance block; csv.DictReader would treat
        # those as data.
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in rows:
            years.append(int(row["fund_year"]))
            tp.append(float(row["tp_per_pound_raised"]))
            lives.append(float(row["lives_index"]))
            surv.append(float(row.get("cohort_survivorship") or 0.0))

    if not years:
        raise RunoffError(f"run-off curve is empty: {path}")
    if years != list(range(len(years))):
        raise RunoffError(
            f"run-off curve must start at fund year 0 and have no gaps; got {years[:5]}..."
        )

    return RunoffCurve(tuple(years), tuple(tp), tuple(lives), tuple(surv))


def outstanding_charge(
    *,
    curve: RunoffCurve,
    drawdowns: list[float],
    cpi_index: list[float],
    year_index: int,
    lockup_years: int,
    gain_to_commons: float,
) -> float:
    """
    The Tontine charge still outstanding, built up cohort by cohort.

    This is the instrument as designed, and it is simpler than a debt schedule
    because it has no schedule. Each year's drawdown is a cohort of investors
    who entered at 65. SLC pays a coupon on that capital for as long as the
    investor lives. When they die the coupon stops and their charge is
    extinguished -- no principal is ever repaid. There is no term, no
    redemption date and no amortisation; mortality is the only mechanism.

    Two policy levers sit on top of it.

    `lockup_years` is a minimum term: a charge cannot be released in the first
    few years after the investment, however unlucky the investor.

    `gain_to_commons` splits what happens to a dead investor's capital. At 1.0
    the whole charge is extinguished and the Commons holds the property free of
    it. At 0.0 none of it is extinguished -- the entitlement passes to the
    surviving investors, lifting their yield without reducing what SLC owes,
    which is the classic tontine survivorship benefit. Anything between splits
    it. This is a live design question, and the parameter is the point at which
    it gets decided rather than assumed.
    """
    total = 0.0
    for k, drawn in enumerate(drawdowns[: year_index + 1]):
        if drawn <= 0:
            continue
        # The principal is CPI-uplifted from the year it was drawn.
        indexation = cpi_index[year_index] / cpi_index[k]

        age = year_index - k
        if age < lockup_years:
            surviving_share = 1.0          # locked: nothing can be released yet
        else:
            alive = curve.survival_at(age)
            # Only the extinguished share reduces what SLC owes; the rest stays
            # outstanding, just owed to fewer people.
            surviving_share = 1.0 - gain_to_commons * (1.0 - alive)

        total += drawn * indexation * surviving_share
    return total
