"""
Growth Engine.

Decides how many properties are acquired each year, and what the organisation
costs to run at that size.

Two things govern acquisitions, and the model takes the lower of them:

  * the growth curve  -- how fast we *want* to grow (rows 26, 9-11)
  * affordability     -- how fast we *can* pay for it (rows 23-25)

The affordability test is the part worth reading carefully. Every balance it
consults is the *prior* year's closing position, never the current year's.
That lag is what keeps the model acyclic: this year's acquisitions depend on
last year's balance sheet, so they can be decided before this year's portfolio,
rent and cash are known. Replicating the lag is not optional -- using
current-year values would introduce a circular reference the workbook
deliberately avoids, and would change the answer.
"""

from __future__ import annotations

import math

from . import efficiency
from .assumptions import Assumptions
from .excelfns import excel_int, excel_round, prior
from .macro import MacroSeries
from .state import ModelState

# The sheet's "unconstrained" sentinel when the affordability cap is switched
# off (Growth Engine row 25). Large enough that the MIN in row 10 always picks
# the growth curve instead.
UNCONSTRAINED = 999999


def opening_portfolio(s: ModelState, i: int) -> None:
    """Row 9 -- last year's closing portfolio, or zero in Year 1."""
    s.growth.portfolio_opening.append(prior(s.growth.portfolio_closing, i))


def unit_cost(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """
    Row 23 -- the all-in cost of one property.

    Split out from the capacity calculation because community share issuance
    can now be sized as a proportion of what this year's planned purchases will
    cost, so the cost has to be known before shares are decided. It depends
    only on price indices, so it can be computed at any point in the year.

    The purchase price moves with house prices; the transaction and retrofit
    costs move with CPI. Two different index series, deliberately.
    """
    s.growth.unit_acquisition_cost.append(
        m.avg_price[i] * (1 + a.sdlt_rate)
        + (a.conveyancing + a.survey_cost + a.retrofit_cost) * m.cost_index[i]
    )


def capacity(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """
    Rows 27, 24, 25 -- what we can afford, given this year's inflows.

    Runs after gift income and community-share flows are known, since both are
    current-year cash, and before the acquisition count is settled.
    """
    g, c = s.growth, s.capital
    year = i + 1

    # Row 27: is new Tontine capital available this year at all? Only during the
    # investment phase, only before any refinancing, and only while the £50m
    # cap has headroom left (measured on last year's cumulative raise).
    tontine_available = (
        year <= a.pf_invest_phase_yrs
        and (a.pf_refi_toggle == 0 or year < a.pf_refi_year)
        and prior(c.tf_cum_raised_closing, i) < a.pf_max_raise
    )
    g.tontine_available.append(1.0 if tontine_available else 0.0)

    # Row 24: funding capacity, in three parts.
    #
    #   1. New gearing, available only if the Tontine gate above is open: the
    #      lesser of LTV headroom on last year's portfolio and what remains of
    #      the maximum raise.
    #   2. Surplus cash above whichever is larger, the target reserve or the
    #      minimum operating buffer.
    #   3. This year's own non-debt inflows: gifts, share issuance net of
    #      withdrawals and issue costs.
    gearing_headroom = min(
        max(0.0, a.pf_ltv_limit * prior(s.assets.portfolio_value, i)
            - prior(c.tf_closing, i) - prior(c.cm_closing, i)),
        max(0.0, a.pf_max_raise - prior(c.tf_cum_raised_closing, i)),
    )
    surplus_cash = max(
        0.0,
        prior(s.statements.free_cash, i) - max(prior(c.target_reserve, i), a.min_cash_buffer),
    )
    g.funding_capacity.append(
        g.tontine_available[i] * gearing_headroom
        + surplus_cash
        + c.gift_income_total[i] + c.cs_issued[i] + c.cs_withdrawals[i] + c.cs_issue_costs[i]
    )

    # Row 25: how many properties that capacity buys. When new Tontine capital
    # is available only the equity slice of each purchase has to come out of
    # capacity -- the rest is geared -- so the divisor shrinks to (1 - LTV).
    #
    # The MAX(0.01, ...) floor is the sheet's guard against an LTV limit of
    # 100%, which would otherwise divide by zero. It is preserved here for
    # fidelity, but see validate() below: at that point the answer is
    # arithmetically meaningless and the model says so rather than quietly
    # returning a number.
    if a.constrain_growth == 1:
        equity_fraction = max(0.01, 1 - a.pf_ltv_limit) if g.tontine_available[i] == 1 else 1.0
        g.affordable_properties.append(
            float(max(0, excel_int(g.funding_capacity[i] / (g.unit_acquisition_cost[i] * equity_fraction))))
        )
    else:
        g.affordable_properties.append(float(UNCONSTRAINED))


def growth_curve(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Row 26 -- how fast we want to grow, before affordability bites.

    Years 1-3 are hand-set counts. From year 4 the model switches to a logistic
    S-curve: growth is fastest mid-way and flattens as the portfolio approaches
    its ceiling.

    Note the two regimes are gated on different things -- the hand-set years on
    a literal `year <= 3`, the curve on `logistic_start_yr`. They agree only
    because logistic_start_yr is 4. See MODEL_LOG.md, "Years 1-3 override".
    """
    g = s.growth
    year = i + 1
    opening = g.portfolio_opening[i]

    if year <= 3:
        g.curve_properties.append(float([a.acq_year1, a.acq_year2, a.acq_year3][year - 1]))
        return

    # Intrinsic growth rate implied by the doubling time: r = ln(2)/years.
    r = math.log(2) / a.logistic_dbl_yrs
    if year >= a.logistic_start_yr:
        logistic = excel_round(r * opening * (1 - opening / a.logistic_ceiling), 0)
    else:
        logistic = 0.0

    # Never below the floor, never past the ceiling.
    g.curve_properties.append(
        min(max(a.logistic_floor, logistic), max(0.0, a.logistic_ceiling - opening))
    )


def acquisitions(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 10-11 -- take the lower of want and can, then add any gifts.

    Purchases are the lower of the growth curve and what the funding affords.
    Gifted properties are neither: nobody's affordability test applies to a
    house someone gives you, and no growth curve produces one. They arrive on
    their own terms and are simply added.

    That is also why they compound so strongly. A gift raises the portfolio
    value, which raises next year's LTV headroom, which buys more houses --
    without ever having consumed funding capacity itself.
    """
    g = s.growth
    year = i + 1

    g.properties_acquired.append(min(g.curve_properties[i], g.affordable_properties[i]))

    # Fractional entitlement accumulates until it crosses a whole house, so a
    # rate of 0.5 means one house every other year rather than half a house
    # every year. Portfolio counts stay whole numbers.
    start = getattr(a, "gift_property_start_yr", 0)
    rate = getattr(a, "gift_property_rate", 0.0)
    if start and rate > 0 and year >= start:
        earned = (year - start + 1) * rate
        already = sum(g.properties_gifted)
        gifted = float(int(earned - already))
    else:
        gifted = 0.0
    g.properties_gifted.append(max(0.0, gifted))

    g.properties_added.append(g.properties_acquired[i] + g.properties_gifted[i])
    g.portfolio_closing.append(g.portfolio_opening[i] + g.properties_added[i])


def admin_costs(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """
    Rows 14-20 -- running costs.

    Fixed costs ramp linearly from their early-years level to their target
    level, reaching target at `logistic_start_yr` and staying there. Variable
    admin scales with the portfolio. Everything is then inflated by CPI.
    """
    g = s.growth
    year = i + 1

    # Row 14: 0 in Year 1, 1 from logistic_start_yr onward, linear in between.
    ramp = min(1.0, max(0.0, (year - 1) / max(1, a.logistic_start_yr - 1)))
    g.ramp_factor.append(ramp)

    def ramped(early: float, target: float) -> float:
        return (early + ramp * (target - early)) * m.cost_index[i]

    g.admin_board.append(ramped(a.board_early, a.board_target))          # row 15
    g.admin_accounting.append(ramped(a.acct_early, a.acct_target))       # row 16
    g.admin_fca.append(ramped(a.fca_early, a.fca_target))                # row 17
    g.admin_insurance.append(ramped(a.ins_early, a.ins_target))          # row 18

    # Row 19: charged on the closing portfolio, so properties bought this year
    # carry a full year of admin even though they may complete in month 12.
    #
    # Scaled down as the estate grows: administering fifty houses costs less
    # per house than administering five. See engine/efficiency.py.
    scale = efficiency.factor_for(a, g.portfolio_closing[i])
    g.admin_variable.append(
        a.admin_per_prop * scale * g.portfolio_closing[i] * m.cost_index[i]
    )
    g.opex_scale_factor.append(scale)

    # Running the Tontine fund itself: administrator, actuarial valuation and
    # audit. Not in the workbook, which buried this in a 0.50% margin added to
    # the coupon -- a percentage that yields GBP 20,000 on a small fund (too
    # little to pay an actuary) and GBP 1m on a large one (far more than the job
    # costs). It is mostly a person, so it is modelled as a person: part-time
    # and pro-rata at the start, growing to a full role as the fund matures.
    #
    # It sits in operating costs rather than in the coupon because that is what
    # it is. The investor receives pf_investor_rate; this is what it costs the
    # Commons to run the vehicle that pays them, and putting it here means it
    # reduces the operating surplus and shows up in the cover ratios honestly.
    #
    # Board and trustees are assumed voluntary or on small honoraria, so there
    # is no separate governance salary line.
    # It scales with the FUND, not with the calendar. A time-based ramp puts a
    # full salary on a fund that never grew -- under Stress that produced an
    # administrator costing 47% of all rental income to look after fifteen
    # houses, which is not a decision anybody would make. Staffing follows the
    # work, so the ramp is driven by how much has actually been raised.
    #
    # Measured on last year's cumulative raise: this runs before tontine() sets
    # the current year's, and using the prior close keeps the model acyclic in
    # the same way the affordability test does.
    early = getattr(a, "pf_fund_admin_early", 0.0)
    if early:
        target = getattr(a, "pf_fund_admin_target", early)
        mature = max(1.0, getattr(a, "pf_fund_admin_mature_raise", 20_000_000))
        raised = prior(s.capital.tf_cum_raised_closing, i)
        fund_ramp = min(1.0, max(0.0, raised / mature))
        g.admin_fund.append((early + fund_ramp * (target - early)) * m.cost_index[i])
    else:
        g.admin_fund.append(0.0)

    g.admin_total.append(                                                # row 20
        g.admin_board[i] + g.admin_accounting[i] + g.admin_fca[i]
        + g.admin_insurance[i] + g.admin_variable[i] + g.admin_fund[i]
    )
