"""
Capital & Debt.

Four capital layers, in the order the sheet lays them out:

  1. Bequests & gifts     -- free capital, plus Gift Aid on the living-donor part
  2. Community shares     -- junior debt: withdrawable, capped, dividend-paying
  3. The Tontine fund     -- the senior layer, and the unusual one
  4. Commercial mortgage  -- dormant unless refinancing is switched on

The Tontine is a closed-end lifetime annuity mutual, and behaves unlike a
normal loan in three ways:

  * It is *interest-only and index-linked*. The principal is never amortised;
    instead it is uplifted every year (row 31) on whatever basis
    `pf_index_basis` selects -- rent by default, since the charge is secured on
    houses that are never sold and rent is the only cash they produce. That
    uplift is a real charge to the P&L but never touches cash.
  * Drawdowns are capped three ways at once (row 37): by what the acquisitions
    actually need, by LTV headroom, and by what remains of the maximum raise --
    and only during the investment phase. In practice the FIRST of those binds
    in almost every year: the fund draws what the houses need, so its size
    reflects its place in the funding queue rather than any limit on appetite.
  * The charge is *extinguished by death*, not by a schedule. Each drawdown is
    a cohort of investors who entered at 65; while they live SLC pays the
    coupon, and as they die both the coupon and the charge go with them, with
    no principal ever repaid. `pf_release_mode: survivorship` is that
    behaviour. The workbook's flat percentage release survives as "geometric"
    only so the model can still reproduce the spreadsheet.
"""

from __future__ import annotations

from . import funding_mix, tontine_runoff
from .assumptions import Assumptions
from .excelfns import prior
from .macro import MacroSeries
from .state import ModelState

# Loaded once. The curve is a fixed data file, not per-run state.
#
# Deliberately NOT wrapped in a try/except. An earlier version swallowed a
# missing curve into `None`, which turned "the mortality data is absent" into
# an obscure crash thousands of lines later. The file is required input; if it
# is gone, saying so at import is the useful behaviour.
runoff_curve = tontine_runoff.load_curve()



# ---------------------------------------------------------------- gifts ----

def gifts(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """Rows 10-15 -- gifts, bequests, founding capital and Gift Aid."""
    c = s.capital
    year = i + 1

    # Rows 10-11: real growth on top of CPI indexation.
    growth = (1 + a.beq_growth_mult) ** (year - 1)
    c.gifts_living.append(a.gift_baseline * growth * m.cost_index[i])
    c.bequests.append(a.beq_baseline * growth * m.cost_index[i])

    # Row 12: one-off, Year 1 only.
    c.founding_capital.append(a.founding_capital if year == 1 else 0.0)

    # Row 13: Gift Aid is recoverable on living donors' gifts only -- bequests
    # from estates do not qualify.
    c.gift_aid.append(c.gifts_living[i] * a.gift_aid_rate if a.gift_aid_toggle == 1 else 0.0)

    c.gift_income_total.append(                                          # row 14
        c.gifts_living[i] + c.bequests[i] + c.founding_capital[i] + c.gift_aid[i]
    )
    c.gift_cumulative.append(prior(c.gift_cumulative, i) + c.gift_income_total[i])  # row 15


# ------------------------------------------------------ community shares ----

def community_shares(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """
    Rows 18-26 -- issuance, withdrawals and the balance.

    Issuance is demand-led (a baseline times a take-up multiplier) but capped so
    that shares never exceed `cs_max_pct_capital` of total capital. Withdrawals
    are only permitted on shares that have been held past the restriction
    period, which is why the eligible balance looks back several years.
    """
    c = s.capital
    year = i + 1

    # Row 18: what the community would subscribe, before the cap bites.
    #
    #   "fixed"          the original: a flat real amount each year, inflated.
    #                    Whatever mix resulted was an accident of that number.
    #   "share_of_need"  issue a target proportion of what this year's planned
    #                    purchases will cost, so the mix is chosen rather than
    #                    inherited. See engine/funding_mix.py.
    #
    # The basis is the GROWTH CURVE's desired purchases, not actual ones.
    # Actual purchases depend on funding, which depends on this number -- using
    # them here would be circular. The curve is set by policy and capability,
    # independently of money, so it breaks the loop.
    if getattr(a, "cs_issue_mode", "fixed") == "share_of_need":
        _, share_w, _ = funding_mix.weights_for_year(a, year)
        desired_cost = s.growth.curve_properties[i] * s.growth.unit_acquisition_cost[i]
        c.cs_target_issuance.append(share_w * desired_cost)
    else:
        c.cs_target_issuance.append(a.cs_baseline_issue * a.cs_takeup_mult * m.cost_index[i])

    # Row 19: all other capital, from last year's balance sheet. Zero in Year 1.
    c.cs_other_capital.append(
        0.0 if year == 1
        else prior(s.statements.total_liab_and_reserves, i) - prior(c.cs_closing, i)
    )

    # Row 20: the cap, expressed against other capital. If shares may be at most
    # p of total capital, then shares <= p/(1-p) times everything else.
    c.cs_max_permitted.append(a.cs_max_pct_capital / (1 - a.cs_max_pct_capital) * c.cs_other_capital[i])

    c.cs_opening.append(0.0 if year == 1 else prior(c.cs_closing, i))    # row 21

    # Row 22: issue what is wanted, up to the remaining headroom under the cap.
    c.cs_issued.append(min(c.cs_target_issuance[i], max(0.0, c.cs_max_permitted[i] - c.cs_opening[i])))

    # Row 23: shares become eligible for withdrawal once held for the
    # restriction period, so this points back at the closing balance of
    # `cs_withdrawal_years` ago.
    lookback = i - max(1, a.cs_withdrawal_years)
    c.cs_eligible_withdrawal.append(0.0 if lookback < 0 else c.cs_closing[lookback])

    # Row 24: negative. Cannot withdraw more than the opening balance.
    c.cs_withdrawals.append(-min(c.cs_opening[i], c.cs_eligible_withdrawal[i] * a.cs_withdrawal_rate))

    c.cs_issue_costs.append(-c.cs_issued[i] * a.cs_issue_cost_pct)       # row 25
    c.cs_closing.append(c.cs_opening[i] + c.cs_issued[i] + c.cs_withdrawals[i])  # row 26


def dividends(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 27-28 -- the community share dividend.

    Paid on the opening balance, but only out of surplus: if the year's surplus
    before dividends is thin or negative, the dividend is cut to fit. Must run
    after the P&L reaches row 23.
    """
    c = s.capital
    c.cs_dividend_rate.append(a.cs_dividend_rate)

    # What the offer document advertises. Under the Co-operative and Community
    # Benefit Societies Act 2014 this is a CAP, not a promise: the rate must be
    # the minimum necessary to attract and retain the capital, profits cannot be
    # distributed on share capital, and payment is at the board's discretion.
    # Societies routinely pay nothing in early years and step up once the
    # project is cash-generative, which is legally clean precisely because
    # nothing was ever owed.
    offered = c.cs_opening[i] * c.cs_dividend_rate[i]

    # What is actually available, and in what order.
    #
    # `surplus_before_div_tax` is already struck after Tontine and mortgage
    # interest, so share interest is subordinated to the annuity by
    # construction. Subordinating it to the RESERVE as well is the step that
    # makes "interest eats the project" structurally impossible rather than
    # merely unlikely: money is only available to shareholders once the reserve
    # the annuity depends on has been topped up.
    available = max(0.0, s.statements.surplus_before_div_tax[i])
    if getattr(a, "cs_interest_after_reserve", False):
        shortfall = max(0.0, c.target_reserve[i] - prior(s.statements.free_cash, i))
        available = max(0.0, available - shortfall)

    c.cs_dividends.append(min(offered, available))


# -------------------------------------------------------------- tontine ----

def mortgage_opening(s: ModelState, i: int) -> None:
    """Row 46, split out because the Tontine's LTV headroom needs it first."""
    s.capital.cm_opening.append(prior(s.capital.cm_closing, i))


def tontine(s: ModelState, a: Assumptions, m: MacroSeries, i: int) -> None:
    """Rows 30-43 -- the Tontine fund."""
    c = s.capital
    year = i + 1

    c.tf_opening.append(prior(c.tf_closing, i))                          # row 30

    # Row 31: uplift on the principal. A P&L charge, but non-cash -- it is added
    # to the balance owed rather than paid out.
    #
    # What it is indexed to is a choice, and the three options have genuinely
    # different consequences (see pf_index_basis in base.yaml). "rent" is the
    # default: the charge is secured on houses that are never sold, so rent is
    # the only cash the security ever produces, and indexing the liability to it
    # means cover cannot drift apart from the thing paying it. "cpi" is what the
    # workbook did. "hpi" tracks capital value, which an organisation that never
    # sells never realises.
    index_rate = {
        "rent": m.rent_rate,
        "hpi": m.hpi_rate,
        "cpi": m.cpi_rate,
    }[getattr(a, "pf_index_basis", "cpi")][i]
    c.tf_indexation.append(c.tf_opening[i] * index_rate)
    c.tf_indexed_opening.append(c.tf_opening[i] + c.tf_indexation[i])    # row 32

    c.tf_cum_raised_opening.append(prior(c.tf_cum_raised_closing, i))    # row 33
    c.tf_remaining_capacity.append(max(0.0, a.pf_max_raise - c.tf_cum_raised_opening[i]))  # row 34

    # Row 35: how much more could be borrowed before hitting the LTV limit,
    # measured against *this* year's portfolio value.
    c.tf_ltv_headroom.append(
        max(0.0, a.pf_ltv_limit * s.assets.portfolio_value[i]
            - c.tf_indexed_opening[i] - c.cm_opening[i])
    )

    # Row 36: the cash gap this year's acquisitions leave after gifts and share
    # flows, plus whatever is needed to restore the cash buffer.
    c.tf_funding_requirement.append(
        max(0.0,
            s.assets.acquisition_cash_cost[i]
            - c.gift_income_total[i]
            - (c.cs_issued[i] + c.cs_withdrawals[i] + c.cs_issue_costs[i])
            + max(0.0, max(prior(c.target_reserve, i), a.min_cash_buffer)
                  - prior(s.statements.free_cash, i)))
    )

    # Row 37: draw the least of what is needed, what LTV allows and what the
    # raise cap leaves -- and only inside the investment phase.
    can_draw = year <= a.pf_invest_phase_yrs and (a.pf_refi_toggle == 0 or year < a.pf_refi_year)
    c.tf_drawdown.append(
        min(c.tf_funding_requirement[i], c.tf_ltv_headroom[i], c.tf_remaining_capacity[i])
        if can_draw else 0.0
    )
    c.tf_cum_raised_closing.append(c.tf_cum_raised_opening[i] + c.tf_drawdown[i])  # row 38

    # Row 39: the coupon rate.
    #
    # The principal is ALREADY uplifted by CPI each year (row 31), and no
    # principal is ever repaid -- so the investor's entire return is the
    # coupon, paid on a base that grows with inflation. Their inflation
    # protection is therefore already delivered by the indexation.
    #
    #   "real"     coupon = spread. The investor receives CPI (through the
    #              growing principal) plus the spread. This is what the
    #              indicative actuarial model does, and it matches the design
    #              intent of a CPI + 2.5% annuity.
    #   "nominal"  coupon = CPI + spread, the original workbook's formula.
    #              Applied to an already-indexed principal it hands the
    #              investor CPI twice, doubling their real return.
    #
    # "nominal" is retained only so the model still reproduces the
    # spreadsheet. See MODEL_LOG.
    if getattr(a, "pf_coupon_basis", "nominal") == "real":
        c.tf_coupon_rate.append(a.pf_coupon_spread)
    else:
        c.tf_coupon_rate.append(m.cpi_rate[i] + a.pf_coupon_spread)

    # Row 40: interest on the indexed opening balance, with a half-year charged
    # on the money drawn during the year.
    c.tf_interest.append(-(c.tf_indexed_opening[i] + c.tf_drawdown[i] / 2) * c.tf_coupon_rate[i])

    # Rows 41-43: what happens as investors die.
    #
    # "survivorship" is the instrument as designed: each drawdown is a cohort
    # of investors who entered at 65, SLC pays a coupon while they live, and on
    # death the coupon stops and the charge is extinguished with no principal
    # repaid. The closing balance is therefore built from the cohorts directly,
    # and the release is whatever reconciles it -- the fall caused by deaths.
    #
    # "geometric" is the original workbook's flat percentage, kept so the model
    # still reproduces the spreadsheet exactly.
    mode = getattr(a, "pf_release_mode", "geometric")

    if mode == "survivorship":
        # The cohort balances must be uplifted on the SAME basis as row 31,
        # or the charge computed here and the indexation charged there drift
        # apart and the balance sheet stops tying out.
        basis_index = {
            "rent": m.rent_index,
            "hpi": m.hpi_index,
            "cpi": m.cpi_index,
        }[getattr(a, "pf_index_basis", "cpi")]
        closing = tontine_runoff.outstanding_charge(
            curve=runoff_curve,
            drawdowns=c.tf_drawdown,
            cpi_index=basis_index,
            year_index=i,
            lockup_years=getattr(a, "pf_lockup_years", 5),
            gain_to_commons=getattr(a, "pf_mortality_gain_to_commons", 1.0),
        )
        # Release is the residual: whatever the deaths took off the balance.
        c.tf_release.append(closing - (c.tf_indexed_opening[i] + c.tf_drawdown[i]))
    else:
        c.tf_release.append(
            -(c.tf_indexed_opening[i] + c.tf_drawdown[i]) * a.pf_release_rate
            if year >= a.pf_release_start_yr else 0.0
        )

    # Row 42: on refinancing, the whole remaining balance moves to the mortgage.
    c.tf_transferred.append(
        -(c.tf_indexed_opening[i] + c.tf_drawdown[i] + c.tf_release[i])
        if (a.pf_refi_toggle == 1 and year == a.pf_refi_year) else 0.0
    )

    c.tf_closing.append(                                                 # row 43
        c.tf_indexed_opening[i] + c.tf_drawdown[i] + c.tf_release[i] + c.tf_transferred[i]
    )


def mortgage(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 47-50 -- the commercial mortgage.

    Dormant in all three scenarios (pf_refi_toggle is 0), but modelled in full:
    switching refinancing on must work without a rewrite. Unlike the Tontine
    this amortises, straight-line over the remaining term.
    """
    c = s.capital
    year = i + 1

    c.cm_drawdown.append(-c.tf_transferred[i])                           # row 47
    balance = c.cm_opening[i] + c.cm_drawdown[i]
    c.cm_interest.append(-balance * a.pf_refi_rate)                      # row 48

    # Row 49: straight-line over whatever term is left. The MAX(1, ...) stops
    # the remaining term going to zero or negative in the final years.
    if balance == 0:
        c.cm_principal.append(0.0)
    else:
        remaining_term = max(1, a.pf_refi_amort_yrs - (year - a.pf_refi_year))
        c.cm_principal.append(-min(balance, balance / remaining_term))

    c.cm_closing.append(c.cm_opening[i] + c.cm_drawdown[i] + c.cm_principal[i])  # row 50


# ------------------------------------------ debt service and covenants ----

def debt_service(s: ModelState, a: Assumptions, i: int) -> None:
    """Rows 53-57 and 60-62 -- servicing cost, leverage and reserve targets."""
    c = s.capital
    year = i + 1

    # Rows 53-55: restated positive, as a cost to be covered.
    c.total_interest.append(-(c.tf_interest[i] + c.cm_interest[i]))
    c.total_principal.append(-c.cm_principal[i])
    c.total_debt_service.append(c.total_interest[i] + c.total_principal[i])

    c.total_debt.append(c.tf_closing[i] + c.cm_closing[i])               # row 56

    portfolio = s.assets.portfolio_value[i]                              # row 57
    c.ltv.append(0.0 if portfolio == 0 else c.total_debt[i] / portfolio)

    # Row 60: the reserve target is phased in, reaching full strength at
    # `reserve_build_year` -- the organisation is not expected to hold six
    # months of debt service from day one.
    c.target_reserve.append(
        a.reserve_tgt_months / 12 * c.total_debt_service[i] * min(1.0, year / a.reserve_build_year)
    )
    c.min_reserve_covenant.append(a.reserve_min_months / 12 * c.total_debt_service[i])  # row 61

    # Row 62: acquisitions the funding could not stretch to. A diagnostic of
    # the LTV cap binding, not a cash item.
    c.unfunded_requirement.append(max(0.0, c.tf_funding_requirement[i] - c.tf_drawdown[i]))


def coverage(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 58-59 and 64-65 -- capital mix and covenant ratios.

    Runs last: DSCR and reserve cover both need the completed statements. The
    sheet returns an empty string when there is no debt to service, and that is
    preserved -- a blank is honest where a division by zero is not.
    """
    c = s.capital

    c.total_capital_employed.append(s.statements.total_liab_and_reserves[i])   # row 58
    c.cs_pct_of_capital.append(                                                # row 59
        0.0 if c.total_capital_employed[i] == 0
        else c.cs_closing[i] / c.total_capital_employed[i]
    )

    # Community share interest, on the CONTRACTED rate and the opening balance
    # -- what was promised, not what got paid.
    #
    # The distinction matters because cs_dividends is capped at the year's
    # surplus, so in a bad year the paid figure falls with the surplus. Testing
    # cover against the paid amount would divide a small numerator by a small
    # denominator and report that everything is fine, which is precisely the
    # year you want the covenant to fire.
    #
    # In law, interest on withdrawable share capital in a community benefit
    # society is discretionary and capped at "no more than necessary to obtain
    # and retain the capital". Commercially it is nothing of the sort: an offer
    # that skips its interest does not raise again. So it is treated here as a
    # fixed charge for covenant purposes, which is also how any senior lender
    # would look at it.
    c.cs_interest_due.append(c.cs_opening[i] * a.cs_dividend_rate)
    c.cs_interest_shortfall.append(max(0.0, c.cs_interest_due[i] - c.cs_dividends[i]))

    # Two different questions, so two different ratios. Conflating them was the
    # mistake in the previous version, which divided everything by the all-in
    # figure and reported that Stress failed -- when what it had found was that
    # Stress could not pay the SHARE interest, which is a thing Stress is
    # entitled to not pay.
    #
    #   senior   can rent service the annuity? The Tontine investor's covenant.
    #            Share interest is excluded because it ranks behind them and is
    #            discretionary; a year with no share interest is a working year,
    #            not a default.
    #   all-in   can rent service everything the capital stack would LIKE to be
    #            paid? Not a covenant -- a health measure, and the one that says
    #            whether the share offer is deliverable as advertised.
    service = c.total_debt_service[i]
    # The workbook's DSCR and reserve cover are computed on debt service alone,
    # because the sheet left share interest out of every covenant test. Those
    # two rows keep that basis so the Excel comparison still holds. Our own
    # cover tests do not: they use the full financing cost, because a pound of
    # share interest is as due as a pound of Tontine coupon.
    financing = service + c.cs_interest_due[i]
    c.total_financing_cost.append(financing)

    non_cash = s.assets.gift_property_value[i]
    all_gifts = s.statements.gifts_and_bequests[i] + s.statements.gift_aid[i]

    if service <= 0:
        c.dscr.append("")                                                      # row 64
        c.reserve_cover.append("")                                             # row 65
        c.cash_interest_cover.append("")
        c.rent_only_cover.append("")
    else:
        c.dscr.append(s.statements.operating_surplus[i] / service)
        c.reserve_cover.append(s.statements.free_cash[i] / (service / 12))

        # Cash cover: strip out donated property. It is income, and it is an
        # asset, but it is not money -- interest cannot be paid with a house.
        c.cash_interest_cover.append(
            (s.statements.operating_surplus[i] - non_cash) / service
        )

        # Rent-only cover: strip out every gift, cash included. This asks the
        # harder question -- can the portfolio service the annuity from the rent
        # it earns, with no reliance on giving that nobody is obliged to
        # continue?
        c.rent_only_cover.append(
            (s.statements.operating_surplus[i] - all_gifts) / service
        )

    c.all_in_cover.append(
        "" if financing <= 0
        else (s.statements.operating_surplus[i] - non_cash) / financing
    )
