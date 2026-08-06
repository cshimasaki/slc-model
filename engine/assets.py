"""
Asset Register.

Tracks the property portfolio as a set of cohorts: each acquisition year is its
own vintage, carried separately for all 50 years.

The reason for cohorts rather than one pooled number is rent. A property's rent
is set at purchase, as a yield on the price paid that year, and then grows with
rent inflation from *that* starting point. A house bought in year 20 at year-20
prices starts at a higher rent than one bought in year 1, and the gap persists.
Pooling would lose that, and would misstate rental income whenever the purchase
price and rent indices diverge -- which is exactly what the HPI premium makes
them do.

Cohort values follow house prices; cohort rents follow rent inflation.
"""

from __future__ import annotations

from .assumptions import Assumptions
from .excelfns import prior
from .macro import MacroSeries
from .state import ModelState


def init_cohorts(s: ModelState, n_years: int) -> None:
    """One cohort per model year, each a full-length series of zeros."""
    s.assets.cohort_value = [[0.0] * n_years for _ in range(n_years)]
    s.assets.cohort_rent = [[0.0] * n_years for _ in range(n_years)]


def cohorts(s: ModelState, a: Assumptions, m: MacroSeries, i: int, n_years: int) -> None:
    """
    Rows 10-59 and 66-115 -- every vintage's value and rent in year i.

    Each cohort is dormant until its acquisition year, seeded in that year, and
    compounded thereafter.
    """
    A = s.assets
    acquired = s.growth.properties_acquired[i]

    for k in range(n_years):
        start = k + 1          # the model year this cohort was acquired
        year = i + 1

        if year < start:
            continue           # not yet acquired; stays zero

        if year == start:
            # Seeded at cost, and at a rent equal to that cost times the yield.
            A.cohort_value[k][i] = acquired * m.avg_price[i]
            A.cohort_rent[k][i] = acquired * m.avg_price[i] * a.gross_yield
        else:
            # Value tracks house prices, rent tracks rent inflation.
            A.cohort_value[k][i] = A.cohort_value[k][i - 1] * (1 + m.hpi_rate[i])
            A.cohort_rent[k][i] = A.cohort_rent[k][i - 1] * (1 + m.rent_rate[i])


def totals(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """Rows 61-63, 117, 119 -- portfolio totals and rental income."""
    A = s.assets

    A.portfolio_value.append(sum(c[i] for c in A.cohort_value))          # row 61

    # Row 62: this year's acquisition spend. The sheet computes this
    # independently of the cohort rows rather than reading the active cohort;
    # both routes must agree, and model.py asserts that they do.
    A.additions_at_cost.append(s.growth.properties_acquired[i] * m.avg_price[i])

    # Row 63: the revaluation gain is what is left after stripping out the
    # prior year's portfolio and this year's purchases -- i.e. pure movement in
    # house prices on stock we already held. Year 1 has no prior portfolio, and
    # the sheet's Year-1 formula genuinely has one fewer term.
    if i == 0:
        A.revaluation_gain.append(A.portfolio_value[i] - A.additions_at_cost[i])
    else:
        A.revaluation_gain.append(
            A.portfolio_value[i] - A.portfolio_value[i - 1] - A.additions_at_cost[i]
        )

    A.gross_rent.append(sum(c[i] for c in A.cohort_rent))                # row 117

    # Row 119: only the Land Commons' share, and only on occupied properties.
    A.net_rental_income.append(A.gross_rent[i] * a.lc_share * (1 - a.void_rate))


def acquisition_costs(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """
    Rows 122-128 -- what buying this year's properties costs in cash.

    Per-property fees are charged on properties bought *this year* (a flow),
    unlike the sinking fund below which is charged on the whole portfolio.
    """
    A = s.assets
    acquired = s.growth.properties_acquired[i]

    A.purchase_price.append(A.additions_at_cost[i])                      # row 122
    A.sdlt.append(A.purchase_price[i] * a.sdlt_rate)                     # row 123
    A.conveyancing.append(acquired * a.conveyancing * m.cost_index[i])   # row 124
    A.surveys.append(acquired * a.survey_cost * m.cost_index[i])         # row 125
    A.retrofit.append(acquired * a.retrofit_cost * m.cost_index[i])      # row 126
    A.transaction_costs.append(                                          # row 127
        A.sdlt[i] + A.conveyancing[i] + A.surveys[i] + A.retrofit[i]
    )
    A.acquisition_cash_cost.append(A.purchase_price[i] + A.transaction_costs[i])  # row 128


def sinking_fund(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """
    Rows 131-135 -- the capital-expenditure sinking fund.

    Money set aside per property per year for future structural work, less what
    is actually spent on maintenance. Both are charged on the *closing*
    portfolio, since they apply to the whole stock rather than to new purchases.

    This balance is a real asset but is not free cash: Financial Statements
    subtracts it again when reporting operating reserves.
    """
    A = s.assets

    A.sinking_opening.append(prior(A.sinking_closing, i))                # row 131
    A.sinking_contribution.append(                                       # row 132
        a.sinking_per_prop * s.growth.portfolio_closing[i] * m.cost_index[i]
    )
    A.sinking_return.append(A.sinking_opening[i] * a.sinking_return)     # row 133
    A.maintenance_spend.append(                                          # row 134 (negative)
        -a.maint_per_prop * s.growth.portfolio_closing[i] * m.cost_index[i]
    )
    A.sinking_closing.append(                                            # row 135
        A.sinking_opening[i] + A.sinking_contribution[i]
        + A.sinking_return[i] + A.maintenance_spend[i]
    )
