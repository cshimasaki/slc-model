"""
The coupon frontier: the highest rate each scenario can carry.

This was previously four numbers typed into the reviewer sheet. They were
correct when written and wrong within a month, because almost every structural
change since has moved them -- the coupon basis fix, maintenance corrected to
two months of rent, the ONS macro update, rent indexation, the stock mix. A
frontier that is remembered rather than computed will always drift, and this one
drifts into a document that goes to an external reviewer.

The ceiling is the highest investor rate at which a scenario breaches NO
covenant in any year: cash interest cover stays above its minimum every year,
and rent-only cover reaches its own minimum by the year required. Both tests,
not just the first -- an earlier version checked only cover and reported
ceilings around 40bp too high.
"""

from __future__ import annotations

from .assumptions import load
from .model import run

# Investor break-even: the coupon at which an annuitant entering at 65 recovers
# their capital by median survival (age 87), given ~21.9 expected years of
# payments on a principal that is never repaid. A property of the mortality
# basis and the instrument, not of SLC's finances, so it does not move with the
# scenarios and is stated rather than solved.
INVESTOR_BREAK_EVEN = 0.0458

LOW, HIGH, ITERATIONS = 0.005, 0.12, 14


def _clears(scenario: str, rate: float) -> bool:
    a = load(scenario)
    a.values["pf_investor_rate"] = rate
    a.values["pf_coupon_spread"] = (
        rate + a.pf_fund_op_margin + a.pf_fund_reg_charge
    )
    r = run(a)
    c = r.state.capital

    cover = [v for v in c.cash_interest_cover if isinstance(v, (int, float))]
    if any(v < a.cov_cash_cover_min for v in cover):
        return False

    year = int(a.cov_rent_only_by_year)
    rent_only = c.rent_only_cover[year - 1]
    if not isinstance(rent_only, (int, float)):
        return False
    return rent_only >= a.cov_rent_only_min


def ceiling(scenario: str) -> float | None:
    """
    Highest investor rate this scenario carries with no breach, or None.

    None means the scenario cannot clear its covenants at any rate worth
    offering -- a real answer, and a more useful one than a number near zero.
    """
    if not _clears(scenario, LOW):
        return None

    lo, hi = LOW, HIGH
    for _ in range(ITERATIONS):
        mid = (lo + hi) / 2
        if _clears(scenario, mid):
            lo = mid
        else:
            hi = mid
    return lo


def frontier() -> dict[str, float | None]:
    """Every scenario's ceiling, plus the investor's break-even requirement."""
    out: dict[str, float | None] = {
        s: ceiling(s) for s in ("optimistic", "base", "stress")
    }
    out["investor_break_even"] = INVESTOR_BREAK_EVEN
    return out


def gap(front: dict[str, float | None] | None = None) -> float | None:
    """
    Basis points between what the binding scenario bears and what an investor
    needs. Positive means there IS a rate that satisfies both.
    """
    front = front or frontier()
    binding = front["stress"]
    if binding is None:
        return None
    return (binding - front["investor_break_even"]) * 10_000
