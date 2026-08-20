"""
Operating efficiency from scale.

Per-property running costs fall as the estate grows. The mechanisms are
ordinary procurement ones: materials bought in bulk, gas safety checks batched
across many houses in a round rather than booked one at a time, and enough
contracted volume to negotiate on price at all.

Modelled as a **learning curve**, the standard form for this: unit cost falls by
a fixed proportion for every *doubling* of the portfolio.

    factor(n) = n ** log2(learning_rate),  floored

A learning rate of 0.92 means each doubling takes 8% off the per-property cost.
The shape matters more than the number: the first ten houses buy most of the
saving, and the two hundredth buys almost none. That is how procurement
leverage actually behaves, and it is why a linear "x% saving at N properties"
would flatter the later years.

The floor exists because the curve never stops falling on its own, and a
per-property cost heading toward zero is nonsense. Somebody still has to attend
the property.

WHAT THIS DOES NOT MODEL
------------------------
Where the saving goes. Here it simply improves the operating surplus and stays
with the Commons. The stated intent is to share it between tenants and
investors, and most likely to consume it through retrofitting -- all of which
would reduce or remove the benefit shown here. Passing it to tenants is a rent
reduction; spending it on retrofit is capex. Neither is modelled, so treat
these figures as the size of the prize rather than the gain to the balance
sheet.
"""

from __future__ import annotations

import math


def scale_factor(
    portfolio: float,
    learning_rate: float,
    floor: float,
) -> float:
    """
    Multiplier on per-property operating cost at a given portfolio size.

    Returns 1.0 for an empty or single-property portfolio -- the baseline costs
    in the assumptions are small-scale costs, so there is nothing yet to save.
    """
    if portfolio <= 1:
        return 1.0
    if not (0 < learning_rate < 1):
        # 1.0 or above means no learning; anything else is meaningless here.
        return 1.0

    exponent = math.log2(learning_rate)
    return max(floor, portfolio ** exponent)


def factor_for(a, portfolio: float) -> float:
    """
    The factor for this scenario, or 1.0 where efficiency is not configured.

    Reads through `getattr` so the frozen port-time assumptions -- which predate
    this module -- keep the workbook's flat per-property costs and the Excel
    comparison stays valid.
    """
    return scale_factor(
        portfolio,
        getattr(a, "opex_learning_rate", 1.0),
        getattr(a, "opex_efficiency_floor", 1.0),
    )


def commons_rent_share(a, portfolio: float) -> float:
    """
    The share of gross rent the Commons keeps, at a given portfolio size.

    The workbook held this at a flat 80%. Two corrections are folded in here.

    The level: maintenance and the other running costs of a house are
    conventionally about two months of rent in twelve, which is 16.67% and
    leaves 83.33% -- not the 20%/80% the sheet assumed.

    The slope: that cost share falls as the estate grows, for the same
    procurement reasons per-property admin does, so the Commons keeps a little
    more of each pound as it scales. Same learning curve, its own rate and
    floor, because maintenance has less headroom than administration -- you can
    batch a gas safety round, but the roof still needs somebody on it.

    Falls back to the flat `lc_share` when the newer parameters are absent,
    which is what keeps the frozen port-reference assumptions reproducing the
    workbook exactly.
    """
    months = getattr(a, "lc_maintenance_months", None)
    if months is None:
        return a.lc_share

    cost_share = (months / 12.0) * scale_factor(
        portfolio,
        getattr(a, "lc_cost_learning_rate", 1.0),
        getattr(a, "lc_cost_floor", 1.0),
    )
    return 1.0 - cost_share
