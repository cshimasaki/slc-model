"""
Monthly Cash Flow -- years 1-5 only.

This engine computes nothing new. It phases the annual figures across twelve
months to show whether the organisation can actually meet its obligations as
they fall due, which an annual statement hides: a year that ends with healthy
reserves can still run dry in month 12 when the acquisition completes, the
dividend is paid and the quarterly debt service all land together.

Three phasing patterns:

  * **Even** -- rent, gifts, admin, maintenance, share flows: an annual figure
    divided by twelve.
  * **Event** -- acquisitions and their funding, dividends, tax: the whole
    annual amount in one nominated month.
  * **Periodic** -- debt service: split evenly across `debt_pay_freq` payments.

Row 36 reconciles each year's twelve months back to the annual cash-flow
statement and must come to nil.
"""

from __future__ import annotations

from .assumptions import Assumptions, N_MONTHS
from .excelfns import excel_round, prior
from .state import ModelState


def compute(s: ModelState, a: Assumptions, n_months: int = N_MONTHS) -> None:
    """Phase the annual results across `n_months` months."""
    mo, f, A = s.monthly, s.statements, s.assets

    for j in range(n_months):
        month = j + 1
        year = (month - 1) // 12 + 1        # row 7
        month_in_year = month - 12 * (year - 1)  # row 8
        y = year - 1                        # index into the annual series

        mo.month.append(month)
        mo.model_year.append(year)
        mo.month_in_year.append(month_in_year)

        is_acq_month = month_in_year == a.acq_month
        is_div_month = month_in_year == a.div_month
        is_year_end = month_in_year == 12
        # Debt service falls in every 12/freq-th month: quarterly means months
        # 3, 6, 9 and 12.
        is_debt_month = month_in_year % (12 / a.debt_pay_freq) == 0

        # --- receipts, rows 11-15 ---
        mo.rental_income.append(f.rental_income[y] / 12)
        mo.gifts.append(
            (s.capital.gifts_living[y] + s.capital.bequests[y] + s.capital.gift_aid[y]) / 12
        )
        # Founding capital lands in month 1 of year 1, not the acquisition month.
        mo.founding_capital.append(a.founding_capital if (year == 1 and month_in_year == 1) else 0.0)
        # The Tontine drawdown accompanies the purchase it funds.
        mo.tontine_drawn.append(f.cf_tontine_drawdown[y] if is_acq_month else 0.0)
        mo.shares_issued.append(f.cf_shares_issued[y] / 12)

        # --- payments, rows 18-27 ---
        mo.admin_costs.append(f.admin_costs[y] / 12)
        mo.maintenance.append(f.maintenance[y] / 12)
        mo.acquisition_costs.append(f.acquisition_costs[y] if is_acq_month else 0.0)
        mo.share_issue_costs.append(f.cs_issue_costs[y] / 12)
        mo.property_purchases.append(f.cf_property_purchases[y] if is_acq_month else 0.0)
        mo.interest_paid.append(f.cf_interest_paid[y] / a.debt_pay_freq if is_debt_month else 0.0)
        mo.mortgage_principal.append(
            f.cf_mortgage_principal[y] / a.debt_pay_freq if is_debt_month else 0.0
        )
        mo.dividends.append(f.cf_dividends_paid[y] if is_div_month else 0.0)
        # Tax is always paid at year end, regardless of the dividend month.
        mo.corporation_tax.append(f.cf_tax_paid[y] if is_year_end else 0.0)
        mo.shares_withdrawn.append(f.cf_shares_withdrawn[y] / 12)

        # --- rows 29-33 ---
        mo.net_movement.append(
            mo.rental_income[j] + mo.gifts[j] + mo.founding_capital[j]
            + mo.tontine_drawn[j] + mo.shares_issued[j]
            + mo.admin_costs[j] + mo.maintenance[j] + mo.acquisition_costs[j]
            + mo.share_issue_costs[j] + mo.property_purchases[j] + mo.interest_paid[j]
            + mo.mortgage_principal[j] + mo.dividends[j] + mo.corporation_tax[j]
            + mo.shares_withdrawn[j]
        )
        mo.cash_opening.append(prior(mo.cash_closing, j))
        mo.cash_closing.append(mo.cash_opening[j] + mo.net_movement[j])

        # The sinking fund accrues through the year, so the earmark is
        # pro-rated by months elapsed rather than applied in full from month 1.
        mo.less_sinking_earmark.append(-A.sinking_closing[y] * month_in_year / 12)
        mo.free_cash.append(mo.cash_closing[j] + mo.less_sinking_earmark[j])

        mo.buffer_status.append("BREACH" if mo.free_cash[j] < a.min_cash_buffer else "OK")

    # Row 36: at each year end, the twelve months must sum to the annual net
    # change in cash. Blank in every other month, as in the sheet.
    for j in range(n_months):
        if mo.month_in_year[j] != 12:
            mo.reconciliation.append("")
            continue
        year = mo.model_year[j]
        twelve = sum(mo.net_movement[k] for k in range(n_months) if mo.model_year[k] == year)
        mo.reconciliation.append(excel_round(twelve - f.cf_net_change[year - 1], 2))
