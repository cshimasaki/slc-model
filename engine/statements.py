"""
Financial Statements -- P&L, balance sheet and cash flow.

Mostly this sheet gathers what the other engines computed and arranges it into
three statements. Two things are worth flagging before reading the code.

**Sign conventions are not uniform, and that is faithful.** Some source rows
already hold negative numbers (maintenance, share issue costs) and are carried
straight through; others hold positive numbers (admin, transaction costs) and
are negated here. The workbook does exactly this, cell by cell. Imposing a
tidier convention would be a silent change to the numbers, so each line says
which it is.

**The indexation uplift is a charge but not a payment.** Row 22 charges the
Tontine's CPI uplift to the P&L; the cash-flow statement's "interest paid"
deliberately excludes it. That is the correct treatment for an index-linked
liability whose principal grows rather than being serviced in cash, and it is
why operating surplus and net cash from operations diverge.
"""

from __future__ import annotations

from .assumptions import Assumptions
from .excelfns import prior
from .state import ModelState


def profit_and_loss(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 10-23 -- income down to surplus before dividends and tax.

    Stops at row 23 because the dividend depends on it: Capital & Debt reads
    this surplus to decide what it can afford to pay, and only then can rows
    24-27 be completed.
    """
    f, c, A, g = s.statements, s.capital, s.assets, s.growth

    f.rental_income.append(A.net_rental_income[i])                       # row 10
    f.gifts_and_bequests.append(                                         # row 11
        c.gifts_living[i] + c.bequests[i] + c.founding_capital[i]
    )
    f.gift_aid.append(c.gift_aid[i])                                     # row 12
    f.total_income.append(f.rental_income[i] + f.gifts_and_bequests[i] + f.gift_aid[i])

    f.admin_costs.append(-g.admin_total[i])                              # row 14 (negated)
    f.acquisition_costs.append(-A.transaction_costs[i])                  # row 15 (negated)
    f.maintenance.append(A.maintenance_spend[i])                         # row 16 (already negative)
    f.cs_issue_costs.append(c.cs_issue_costs[i])                         # row 17 (already negative)
    f.total_operating_costs.append(                                      # row 18
        f.admin_costs[i] + f.acquisition_costs[i] + f.maintenance[i] + f.cs_issue_costs[i]
    )
    f.operating_surplus.append(f.total_income[i] + f.total_operating_costs[i])  # row 19

    f.interest_tontine.append(c.tf_interest[i])                          # row 20 (already negative)
    f.interest_mortgage.append(c.cm_interest[i])                         # row 21 (already negative)
    f.indexation_charge.append(-c.tf_indexation[i])                      # row 22 (non-cash)
    f.surplus_before_div_tax.append(                                     # row 23
        f.operating_surplus[i] + f.interest_tontine[i]
        + f.interest_mortgage[i] + f.indexation_charge[i]
    )


def tax_and_retained(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 24-27 -- dividends, tax and the retained surplus.

    On the tax base: the workbook computes tax on surplus *after* deducting
    dividends (row 23 + row 24, where dividends are negative). That is unusual
    -- dividends are normally paid out of taxed profit -- and it is preserved
    here rather than corrected. It makes no difference while
    `ct_exempt_toggle` is 1, which it is in all three scenarios, but it would
    if the exemption were ever switched off. Logged in MODEL_LOG.md.
    """
    f, c = s.statements, s.capital

    f.dividends.append(-c.cs_dividends[i])                               # row 24 (negated)

    if a.ct_exempt_toggle == 1:                                          # row 25
        f.corporation_tax.append(0.0)
    else:
        taxable = max(0.0, f.surplus_before_div_tax[i] + f.dividends[i])
        f.corporation_tax.append(-taxable * a.ct_rate)

    f.retained_surplus.append(                                           # row 26
        f.surplus_before_div_tax[i] + f.dividends[i] + f.corporation_tax[i]
    )
    f.cumulative_retained.append(prior(f.cumulative_retained, i) + f.retained_surplus[i])  # row 27


def cash_flow(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 49-65 -- the cash-flow statement.

    Runs before the balance sheet, which needs the closing free-cash figure.
    """
    f, c, A = s.statements, s.capital, s.assets

    f.cf_operating_surplus.append(f.operating_surplus[i])                # row 49

    # Row 50: cash interest only. Row 22's indexation uplift is excluded --
    # it accrues to the principal instead of being paid.
    f.cf_interest_paid.append(f.interest_tontine[i] + f.interest_mortgage[i])

    f.cf_dividends_paid.append(f.dividends[i])                           # row 51
    f.cf_tax_paid.append(f.corporation_tax[i])                           # row 52
    f.cf_from_operations.append(                                         # row 53
        f.cf_operating_surplus[i] + f.cf_interest_paid[i]
        + f.cf_dividends_paid[i] + f.cf_tax_paid[i]
    )

    f.cf_property_purchases.append(-A.purchase_price[i])                 # row 54 (negated)
    f.cf_from_investing.append(f.cf_property_purchases[i])               # row 55

    f.cf_tontine_drawdown.append(c.tf_drawdown[i])                       # row 56
    f.cf_shares_issued.append(c.cs_issued[i])                            # row 57
    f.cf_shares_withdrawn.append(c.cs_withdrawals[i])                    # row 58 (already negative)
    f.cf_mortgage_principal.append(c.cm_principal[i])                    # row 59 (already negative)
    f.cf_from_financing.append(                                          # row 60
        f.cf_tontine_drawdown[i] + f.cf_shares_issued[i]
        + f.cf_shares_withdrawn[i] + f.cf_mortgage_principal[i]
    )

    f.cf_net_change.append(                                              # row 61
        f.cf_from_operations[i] + f.cf_from_investing[i] + f.cf_from_financing[i]
    )
    f.cash_opening.append(prior(f.cash_closing, i))                      # row 62
    f.cash_closing.append(f.cash_opening[i] + f.cf_net_change[i])        # row 63

    # Rows 64-65: the sinking fund is cash in the bank but earmarked for
    # structural work, so it is stripped out to leave genuinely free reserves.
    f.less_sinking_earmark.append(-A.sinking_closing[i])
    f.free_cash.append(f.cash_closing[i] + f.less_sinking_earmark[i])


def balance_sheet(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 30-46 -- the balance sheet, and the check that it balances.

    Reserves have three components, only one of which is cash-generated: the
    accumulated retained surplus, the unrealised revaluation of property, and
    the cumulative Tontine principal released to the Commons.
    """
    f, c, A = s.statements, s.capital, s.assets

    f.property_at_hpi.append(A.portfolio_value[i])                       # row 30
    f.sinking_fund.append(A.sinking_closing[i])                          # row 31
    f.free_cash_asset.append(f.free_cash[i])                             # row 32
    f.total_assets.append(f.property_at_hpi[i] + f.sinking_fund[i] + f.free_cash_asset[i])

    f.liability_tontine.append(c.tf_closing[i])                          # row 35
    f.liability_mortgage.append(c.cm_closing[i])                         # row 36
    f.liability_shares.append(c.cs_closing[i])                           # row 37
    f.total_liabilities.append(                                          # row 38
        f.liability_tontine[i] + f.liability_mortgage[i] + f.liability_shares[i]
    )

    f.reserve_retained.append(f.cumulative_retained[i])                  # row 40
    f.reserve_revaluation.append(                                        # row 41 (cumulative)
        prior(f.reserve_revaluation, i) + A.revaluation_gain[i]
    )
    f.reserve_tontine_released.append(                                   # row 42 (cumulative)
        prior(f.reserve_tontine_released, i) - c.tf_release[i]
    )
    f.net_assets.append(                                                 # row 43
        f.reserve_retained[i] + f.reserve_revaluation[i] + f.reserve_tontine_released[i]
    )
    f.total_liab_and_reserves.append(f.total_liabilities[i] + f.net_assets[i])  # row 44

    f.balance_check.append(f.total_assets[i] - f.total_liab_and_reserves[i])    # row 46


def memorandum(s: ModelState, a: Assumptions, i: int) -> None:
    """
    Rows 68-71 -- capital movements and the cash-buffer flag.

    Row 71 is a warning light, not a mechanism: it reports how far free cash
    has fallen below the minimum buffer, but nothing in the model responds to
    it. If the buffer is breached the model carries on with negative reserves.
    Making a capital call actually happen would be a structural change, not a
    parameter change -- see MODEL_LOG.md.
    """
    f, c = s.statements, s.capital

    f.memo_shares_raised.append(c.cs_issued[i])                          # row 68
    f.memo_tontine_drawn.append(c.tf_drawdown[i])                        # row 69
    f.memo_total_raised.append(f.memo_shares_raised[i] + f.memo_tontine_drawn[i])
    f.memo_capital_call.append(max(0.0, a.min_cash_buffer - f.free_cash[i]))    # row 71
