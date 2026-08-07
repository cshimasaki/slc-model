"""
Which model outputs get published, and how they should be presented.

A declarative catalogue, so the JSON bundle, the explorer's charts and the
Excel workbook all agree on what a series is called and how it is formatted
without any of them hard-coding it separately. Adding a trajectory to every
output is a matter of adding one entry here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Series:
    key: str            # identifier used in the JSON bundle
    label: str          # what a reader sees
    source: str         # "<state attribute>.<field>" on ModelState
    unit: str           # "£" | "%" | "count" | "x" | "months"
    note: str = ""      # shown as help text where there's room


@dataclass(frozen=True)
class Chart:
    key: str
    title: str
    series: list[str]                   # Series keys to plot together
    unit: str
    kind: str = "line"                  # "line" | "bar"
    reference: list[str] = field(default_factory=list)  # assumption keys drawn as limit lines
    caption: str = ""


SERIES: list[Series] = [
    # Portfolio
    Series("portfolio_units", "Properties in portfolio", "growth.portfolio_closing", "count"),
    Series("properties_acquired", "Properties acquired in year", "growth.properties_acquired", "count"),
    Series("portfolio_value", "Portfolio value (HPI-indexed)", "assets.portfolio_value", "£"),

    # Income and cost
    Series("net_rental_income", "Net rental income to Land Commons", "assets.net_rental_income", "£"),
    Series("total_income", "Total income", "statements.total_income", "£"),
    Series("total_operating_costs", "Total operating costs", "statements.total_operating_costs", "£"),
    Series("operating_surplus", "Operating surplus", "statements.operating_surplus", "£"),
    Series("admin_total", "Admin costs", "growth.admin_total", "£"),

    # Cash
    Series("cf_net_change", "Net change in cash", "statements.cf_net_change", "£"),
    Series("free_cash", "Free cash / operating reserves", "statements.free_cash", "£"),
    Series("cash_closing", "Cash — closing", "statements.cash_closing", "£"),
    Series("sinking_fund", "CapEx sinking fund", "assets.sinking_closing", "£"),

    # Debt and leverage
    Series("total_debt", "Total debt outstanding", "capital.total_debt", "£"),
    Series("ltv", "Loan-to-value", "capital.ltv", "%"),
    Series("total_debt_service", "Total debt service", "capital.total_debt_service", "£"),
    Series("dscr", "Interest cover — all income", "capital.dscr", "x",
           "The workbook's DSCR row. No principal is ever repaid, so this is "
           "interest cover; it also counts a donated house as income."),
    Series("cash_interest_cover", "Interest cover — cash income", "capital.cash_interest_cover", "x",
           "Excludes donated property: an asset, but not money to pay interest with."),
    Series("rent_only_cover", "Interest cover — rent only", "capital.rent_only_cover", "x",
           "No gifts at all. Asks whether the portfolio can service its own debt."),

    # Reserves
    Series("target_reserve", "Target reserve", "capital.target_reserve", "£"),
    Series("min_reserve_covenant", "Minimum reserve covenant", "capital.min_reserve_covenant", "£"),
    Series("reserve_cover", "Reserve cover", "capital.reserve_cover", "months"),

    # Tontine fund
    Series("tontine_balance", "Tontine fund balance", "capital.tf_closing", "£"),
    Series("tontine_drawdown", "Tontine drawdown in year", "capital.tf_drawdown", "£"),
    Series("tontine_release", "Tontine principal released to reserves", "capital.tf_release", "£",
           "Negative: the balance is written down and credited to reserves."),
    Series("tontine_cum_raised", "Cumulative Tontine capital raised", "capital.tf_cum_raised_closing", "£"),
    Series("tontine_indexation", "CPI uplift on Tontine principal", "capital.tf_indexation", "£",
           "A non-cash finance charge — it accrues to the principal."),

    # Community shares
    Series("shares_balance", "Community share capital", "capital.cs_closing", "£"),
    Series("shares_issued", "Community shares issued", "capital.cs_issued", "£"),
    Series("shares_withdrawn", "Community shares withdrawn", "capital.cs_withdrawals", "£"),
    Series("shares_pct_capital", "Community shares as % of capital", "capital.cs_pct_of_capital", "%"),

    # Balance sheet
    Series("net_assets", "Net assets", "statements.net_assets", "£"),
    Series("total_assets", "Total assets", "statements.total_assets", "£"),
    Series("total_liabilities", "Total liabilities", "statements.total_liabilities", "£"),
    Series("cumulative_retained", "Cumulative retained surplus", "statements.cumulative_retained", "£"),
    Series("gift_cumulative", "Cumulative gifts & bequests", "capital.gift_cumulative", "£"),

    # Diagnostics
    Series("unfunded_requirement", "Unfunded acquisition requirement", "capital.unfunded_requirement", "£",
           "Acquisitions the funding could not stretch to — the LTV cap binding."),
    Series("capital_call", "Cash buffer shortfall", "statements.memo_capital_call", "£",
           "How far free cash sits below the minimum buffer. A warning only — "
           "nothing in the model responds to it."),
]

# Charts are grouped so that every series on a given chart shares both a unit
# and an order of magnitude. Stocks and flows are deliberately split apart --
# plotting a £10m Tontine balance beside a £700k drawdown leaves the drawdown
# reading as a flat line at zero, and the fix is two charts, never a second
# y-axis.
CHARTS: list[Chart] = [
    Chart("portfolio_value", "Portfolio value",
          ["portfolio_value"], "£",
          caption="The portfolio at house-price value."),
    Chart("portfolio_units", "Properties held",
          ["portfolio_units"], "count",
          caption="Closing portfolio. Growth stops when funding runs out, not when the "
                  "growth curve flattens."),
    Chart("acquisitions", "Properties acquired each year",
          ["properties_acquired"], "count", kind="bar",
          caption="The lower of what the growth curve wants and what the funding affords."),
    Chart("income_cost", "Income vs cost",
          ["total_income", "total_operating_costs", "operating_surplus"], "£",
          caption="Operating costs are shown negative, as they are in the accounts."),
    Chart("cash", "Cash flow & reserves",
          ["cf_net_change", "free_cash"], "£",
          caption="Free cash excludes the sinking fund, which is earmarked for structural work."),
    Chart("debt", "Debt outstanding",
          ["total_debt"], "£",
          caption="The Tontine fund plus any commercial mortgage."),
    Chart("ltv", "LTV against the limit",
          ["ltv"], "%", reference=["pf_ltv_limit"],
          caption="Where the line meets the limit, the LTV cap is what stopped further acquisitions."),
    Chart("interest_cover", "Interest cover, three ways",
          ["dscr", "cash_interest_cover", "rent_only_cover"], "x",
          reference=["__cash_cover_min", "__rent_only_min"],
          caption="Three lines, three different questions. All-income counts a donated house "
                  "as income; cash income does not; rent-only asks whether the portfolio "
                  "services its own debt with no gifts at all. The gap between top and bottom "
                  "is the reliance on giving that nobody is obliged to continue."),
    Chart("reserves", "Reserves against covenant",
          ["free_cash", "target_reserve", "min_reserve_covenant"], "£",
          caption="Free cash below the covenant line is a breach."),
    Chart("tontine_balance", "Tontine fund balance",
          ["tontine_balance", "tontine_cum_raised"], "£",
          caption="The balance is uplifted by CPI each year rather than amortised, then written "
                  "down from the release year onward."),
    Chart("tontine_flows", "Tontine drawdowns & releases",
          ["tontine_drawdown", "tontine_release", "tontine_indexation"], "£",
          caption="Drawdowns during the investment phase; releases (negative) transfer principal "
                  "to reserves once the release phase begins."),
    Chart("shares_balance", "Community share capital",
          ["shares_balance"], "£",
          caption="Capped as a share of total capital, which is what limits issuance in later years."),
    Chart("shares_flows", "Community share flows",
          ["shares_issued", "shares_withdrawn"], "£",
          caption="Withdrawals are only permitted after the restriction period."),
    Chart("balance_sheet", "Assets, liabilities & net assets",
          ["total_assets", "total_liabilities", "net_assets"], "£"),
    Chart("stress_signals", "Stress signals",
          ["unfunded_requirement", "capital_call"], "£",
          caption="Both are diagnostics only. Neither triggers any response in the model."),
]

# Headline figures for the summary panel: (key, label, series, how to reduce it)
HEADLINES = [
    ("portfolio_final", "Properties at Year 50", "portfolio_units", "last"),
    ("portfolio_value_final", "Portfolio value at Year 50", "portfolio_value", "last"),
    ("net_assets_final", "Net assets at Year 50", "net_assets", "last"),
    ("cumulative_retained_final", "Cumulative retained surplus", "cumulative_retained", "last"),
    ("total_debt_final", "Debt outstanding at Year 50", "total_debt", "last"),
    ("tontine_raised", "Total Tontine capital raised", "tontine_cum_raised", "last"),
    ("gifts_total", "Cumulative gifts & bequests", "gift_cumulative", "last"),
    ("min_dscr", "Worst interest cover (all income)", "dscr", "min"),
    ("min_cash_cover", "Worst cash interest cover", "cash_interest_cover", "min"),
    ("min_rent_only", "Worst rent-only cover", "rent_only_cover", "min"),
    ("max_ltv", "Peak LTV", "ltv", "max"),
    ("min_reserve_cover", "Worst reserve cover", "reserve_cover", "min"),
    ("min_free_cash", "Lowest free cash", "free_cash", "min"),
]

SERIES_BY_KEY = {s.key: s for s in SERIES}
