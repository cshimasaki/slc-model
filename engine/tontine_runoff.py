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
    with open(path, encoding="utf-8") as f:
        # The file leads with a provenance block; csv.DictReader would treat
        # those as data.
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in rows:
            years.append(int(row["fund_year"]))
            tp.append(float(row["tp_per_pound_raised"]))
            lives.append(float(row["lives_index"]))

    if not years:
        raise RunoffError(f"run-off curve is empty: {path}")
    if years != list(range(len(years))):
        raise RunoffError(
            f"run-off curve must start at fund year 0 and have no gaps; got {years[:5]}..."
        )

    return RunoffCurve(tuple(years), tuple(tp), tuple(lives))


def release_for_year(
    *,
    curve: RunoffCurve,
    indexed_opening: float,
    drawdown: float,
    cumulative_raised: float,
    fund_year: int,
    coverage_target: float,
    glide_years: int,
    model_year: int,
    release_start_year: int,
) -> float:
    """
    The release for one year under the run-off-tracking rule.

    Returns a negative number, matching the sheet's sign convention: a release
    reduces the outstanding charge and is credited to SLC's reserves.

    `fund_year` is years since the first drawdown, which is what indexes the
    actuarial curve. It is not the model year: if the fund first draws in model
    year 1, the two differ by one, and if it never draws they are unrelated.

    The release has two parts, and the split is the whole design.

    1. **Tracking.** Discharge the same *proportion* the liability itself fell
       by this year. This is what "tracks the run-off" has to mean: the charge
       declines in step with the obligation it secures, smoothly, with no
       schedule of its own.

    2. **Glide.** Any coverage above target is worked off over `glide_years`,
       not corrected in one go.

    Part 2 exists because of a bug this rule had first. Releasing straight down
    to target snapped fifteen years of accumulated over-coverage into a single
    year -- £9.3m discharged at once at year 25, against £150k a year after.
    That is not tracking anything; it is a level target with a cliff in it, and
    it is not a discharge any lender or registrar would recognise.

    The cause is structural rather than arithmetic: the liability peaks around
    fund year 9 and runs off from there, but policy blocks any release until
    year 25. Sixteen years of divergence accrue before the rule is allowed to
    act. Gliding spreads that backlog; starting the release nearer the
    liability peak would avoid creating it at all, but that is a policy choice
    and belongs to whoever sets `pf_release_start_yr`.
    """
    if model_year < release_start_year:
        return 0.0
    if cumulative_raised <= 0:
        return 0.0

    outstanding = indexed_opening + drawdown
    if outstanding <= 0:
        return 0.0

    # Scale the actuarial curve to the capital this model actually raised.
    tp_now = curve.tp_at(fund_year) * cumulative_raised
    tp_prev = curve.tp_at(fund_year - 1) * cumulative_raised

    # 1. Track: the proportion by which the liability fell this year.
    if tp_prev > 0 and tp_now < tp_prev:
        tracking = outstanding * (1 - tp_now / tp_prev)
    else:
        tracking = 0.0

    # 2. Glide: work off any coverage above target gradually.
    remaining = outstanding - tracking
    excess = max(0.0, remaining - coverage_target * tp_now)
    glide = excess / max(1, glide_years)

    total = min(tracking + glide, outstanding)
    if total <= 0:
        return 0.0
    return -total
