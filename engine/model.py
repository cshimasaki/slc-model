"""
The orchestrator: runs one scenario over the full horizon.

Everything interesting about this module is the *order* of the calls inside the
year loop. The engines are mutually dependent within a single year, and the
workbook resolves that with a mixture of prior-year lags and a strict left-to-
right, top-to-bottom evaluation order. Reproducing the arithmetic without
reproducing the order gives wrong answers that still look plausible.

The dependency chain within year t, and why each step must sit where it does:

  1. gifts, community shares   -- need only last year's balance sheet
  2. growth: cost & capacity   -- needs (1)'s cash inflows, and last year's
                                  portfolio value, debt and free cash
  3. growth: how many, and admin
  4. asset register            -- needs (3)'s acquisition count
  5. mortgage opening balance  -- needed by the Tontine's LTV headroom
  6. tontine                   -- needs (4)'s portfolio value and cash cost
  7. mortgage                  -- needs (6)'s refinancing transfer
  8. debt service              -- needs (6) and (7)
  9. P&L to row 23             -- needs (3), (4), (6), (7)
 10. dividends                 -- need (9)'s surplus to be affordable
 11. P&L rows 24-27            -- need (10)
 12. cash flow                 -- needs (11)
 13. balance sheet             -- needs (12)'s closing free cash
 14. memorandum, coverage      -- need the completed statements

Only after all 50 years does the monthly view run, since it phases finished
annual figures.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import assets, capital_debt, growth, monthly, statements
from .assumptions import Assumptions, N_MONTHS, N_YEARS, load
from .macro import MacroSeries, compute as compute_macro
from .state import ModelState

# Tolerance for the internal consistency checks. Generous enough not to trip on
# floating-point noise after fifty years of compounding, tight enough that a
# real error in pounds cannot hide under it.
CHECK_TOLERANCE = 1e-6


class ModelError(Exception):
    """Raised when a run violates one of the model's own invariants."""


@dataclass
class ModelRun:
    """A completed scenario run."""

    scenario: str
    assumptions: Assumptions
    macro: MacroSeries
    state: ModelState
    n_years: int


def run(
    scenario: str | Assumptions,
    n_years: int = N_YEARS,
    n_months: int = N_MONTHS,
    check: bool = True,
) -> ModelRun:
    """
    Run one scenario end to end.

    `scenario` may be a name ("base") or an already-loaded Assumptions object,
    so callers can run a modified parameter set without writing a YAML file --
    the seam a what-if API would use later.
    """
    a = load(scenario) if isinstance(scenario, str) else scenario
    m = compute_macro(a, n_years)
    s = ModelState()

    assets.init_cohorts(s, n_years)

    for i in range(n_years):
        # 1. Free capital and junior debt, both driven by last year's position.
        capital_debt.gifts(s, a, m, i)
        capital_debt.community_shares(s, a, m, i)

        # 2-3. How much can we afford, how much do we want, how many do we buy.
        growth.opening_portfolio(s, i)
        growth.costs_and_capacity(s, a, m, i)
        growth.growth_curve(s, a, i)
        growth.acquisitions(s, a, i)
        growth.admin_costs(s, a, m, i)

        # 4. The portfolio those acquisitions produce.
        assets.cohorts(s, a, m, i, n_years)
        assets.totals(s, a, m, i)
        assets.acquisition_costs(s, a, m, i)
        assets.sinking_fund(s, a, m, i)

        # 5-8. Senior debt, and what it costs to service.
        capital_debt.mortgage_opening(s, i)
        capital_debt.tontine(s, a, m, i)
        capital_debt.mortgage(s, a, i)
        capital_debt.debt_service(s, a, i)

        # 9-11. The P&L, pausing so the dividend can be sized against surplus.
        statements.profit_and_loss(s, a, i)
        capital_debt.dividends(s, a, i)
        statements.tax_and_retained(s, a, i)

        # 12-14. Cash, then the balance sheet, then the ratios.
        statements.cash_flow(s, a, i)
        statements.balance_sheet(s, a, i)
        statements.memorandum(s, a, i)
        capital_debt.coverage(s, i)

    monthly.compute(s, a, n_months)

    if check:
        _check_invariants(s, n_years, n_months)

    return ModelRun(scenario=a.name, assumptions=a, macro=m, state=s, n_years=n_years)


def _check_invariants(s: ModelState, n_years: int, n_months: int) -> None:
    """
    Assert the things the model must never get wrong.

    The workbook states two of these as visible check rows that "must read
    zero". In Excel they are a reader's reassurance; here they are enforced, so
    a translation error fails loudly instead of producing a balance sheet that
    silently does not balance.
    """
    for i in range(n_years):
        # Financial Statements row 46: assets = liabilities + reserves.
        if abs(s.statements.balance_check[i]) > CHECK_TOLERANCE:
            raise ModelError(
                f"balance sheet does not balance in year {i + 1}: "
                f"assets - (liabilities + reserves) = {s.statements.balance_check[i]:,.6f}"
            )

        # Asset Register rows 62 vs 10-59: the sheet computes this year's
        # acquisition spend twice, by two different routes. They must agree.
        cohort_seed = s.assets.cohort_value[i][i]
        if abs(cohort_seed - s.assets.additions_at_cost[i]) > CHECK_TOLERANCE:
            raise ModelError(
                f"year {i + 1}: additions at cost ({s.assets.additions_at_cost[i]:,.2f}) "
                f"disagrees with the year's own cohort seed ({cohort_seed:,.2f})"
            )

    # Monthly Cash Flow row 36: each year's twelve months must sum to the
    # annual net change in cash.
    for j in range(n_months):
        value = s.monthly.reconciliation[j]
        if value != "" and abs(value) > 0.01:
            raise ModelError(
                f"month {j + 1}: twelve months do not reconcile to the annual "
                f"cash flow (out by {value:,.2f})"
            )


def run_all(n_years: int = N_YEARS, n_months: int = N_MONTHS) -> dict[str, ModelRun]:
    """Run every scenario, keyed by name."""
    return {s: run(s, n_years, n_months) for s in ("base", "optimistic", "stress")}
