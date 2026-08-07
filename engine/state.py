"""
The shared state a model run fills in.

Every attribute is a list with one entry per model year (index 0 == Year 1),
named for what it is and carrying the workbook row it reproduces. The row
numbers are not decoration: validation/compare.py uses ROW_MAP to diff each
series against the same row of the same sheet in the original workbook, so a
mismatch points at one line item rather than "the model".
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields


def _years() -> list[float]:
    return []


@dataclass
class GrowthState:
    """Growth Engine sheet."""

    portfolio_opening: list[float] = field(default_factory=_years)      # row 9
    properties_acquired: list[float] = field(default_factory=_years)    # row 10 (purchased)
    portfolio_closing: list[float] = field(default_factory=_years)      # row 11
    # Added after the port: properties given to the Commons outright. Not in
    # the workbook, so they carry no source row and are excluded from the Excel
    # comparison -- which is correct, since the workbook cannot represent them.
    properties_gifted: list[float] = field(default_factory=_years)
    properties_added: list[float] = field(default_factory=_years)       # purchased + gifted
    ramp_factor: list[float] = field(default_factory=_years)            # row 14
    admin_board: list[float] = field(default_factory=_years)            # row 15
    admin_accounting: list[float] = field(default_factory=_years)       # row 16
    admin_fca: list[float] = field(default_factory=_years)              # row 17
    admin_insurance: list[float] = field(default_factory=_years)        # row 18
    admin_variable: list[float] = field(default_factory=_years)         # row 19
    admin_total: list[float] = field(default_factory=_years)            # row 20
    unit_acquisition_cost: list[float] = field(default_factory=_years)  # row 23
    funding_capacity: list[float] = field(default_factory=_years)       # row 24
    affordable_properties: list[float] = field(default_factory=_years)  # row 25
    curve_properties: list[float] = field(default_factory=_years)       # row 26
    tontine_available: list[float] = field(default_factory=_years)      # row 27

    ROW_MAP = {
        9: "portfolio_opening", 10: "properties_acquired", 11: "portfolio_closing",
        14: "ramp_factor", 15: "admin_board", 16: "admin_accounting",
        17: "admin_fca", 18: "admin_insurance", 19: "admin_variable",
        20: "admin_total", 23: "unit_acquisition_cost", 24: "funding_capacity",
        25: "affordable_properties", 26: "curve_properties", 27: "tontine_available",
    }


@dataclass
class AssetState:
    """Asset Register sheet."""

    # Cohorts: cohort_value[k] is the vintage acquired in year k+1, tracked over
    # all 50 years. Rows 10-59 (value) and 66-115 (rent) of the sheet.
    cohort_value: list[list[float]] = field(default_factory=list)
    cohort_rent: list[list[float]] = field(default_factory=list)

    portfolio_value: list[float] = field(default_factory=_years)        # row 61
    additions_at_cost: list[float] = field(default_factory=_years)      # row 62
    revaluation_gain: list[float] = field(default_factory=_years)       # row 63
    gross_rent: list[float] = field(default_factory=_years)             # row 117
    net_rental_income: list[float] = field(default_factory=_years)      # row 119
    purchase_price: list[float] = field(default_factory=_years)         # row 122
    sdlt: list[float] = field(default_factory=_years)                   # row 123
    conveyancing: list[float] = field(default_factory=_years)           # row 124
    surveys: list[float] = field(default_factory=_years)                # row 125
    retrofit: list[float] = field(default_factory=_years)               # row 126
    transaction_costs: list[float] = field(default_factory=_years)      # row 127
    acquisition_cash_cost: list[float] = field(default_factory=_years)  # row 128
    sinking_opening: list[float] = field(default_factory=_years)        # row 131
    sinking_contribution: list[float] = field(default_factory=_years)   # row 132
    sinking_return: list[float] = field(default_factory=_years)         # row 133
    maintenance_spend: list[float] = field(default_factory=_years)      # row 134
    sinking_closing: list[float] = field(default_factory=_years)        # row 135
    # Market value of properties received as gifts. Adds to the portfolio and
    # to income, but never to cash.
    gift_property_value: list[float] = field(default_factory=_years)

    ROW_MAP = {
        61: "portfolio_value", 62: "additions_at_cost", 63: "revaluation_gain",
        117: "gross_rent", 119: "net_rental_income", 122: "purchase_price",
        123: "sdlt", 124: "conveyancing", 125: "surveys", 126: "retrofit",
        127: "transaction_costs", 128: "acquisition_cash_cost",
        131: "sinking_opening", 132: "sinking_contribution",
        133: "sinking_return", 134: "maintenance_spend", 135: "sinking_closing",
    }


@dataclass
class CapitalState:
    """Capital & Debt sheet."""

    # Bequests & gifts
    gifts_living: list[float] = field(default_factory=_years)           # row 10
    bequests: list[float] = field(default_factory=_years)               # row 11
    founding_capital: list[float] = field(default_factory=_years)       # row 12
    gift_aid: list[float] = field(default_factory=_years)               # row 13
    gift_income_total: list[float] = field(default_factory=_years)      # row 14
    gift_cumulative: list[float] = field(default_factory=_years)        # row 15

    # Community shares (junior debt)
    cs_target_issuance: list[float] = field(default_factory=_years)     # row 18
    cs_other_capital: list[float] = field(default_factory=_years)       # row 19
    cs_max_permitted: list[float] = field(default_factory=_years)       # row 20
    cs_opening: list[float] = field(default_factory=_years)             # row 21
    cs_issued: list[float] = field(default_factory=_years)              # row 22
    cs_eligible_withdrawal: list[float] = field(default_factory=_years) # row 23
    cs_withdrawals: list[float] = field(default_factory=_years)         # row 24
    cs_issue_costs: list[float] = field(default_factory=_years)         # row 25
    cs_closing: list[float] = field(default_factory=_years)             # row 26
    cs_dividend_rate: list[float] = field(default_factory=_years)       # row 27
    cs_dividends: list[float] = field(default_factory=_years)           # row 28

    # Tontine fund
    tf_opening: list[float] = field(default_factory=_years)             # row 30
    tf_indexation: list[float] = field(default_factory=_years)          # row 31
    tf_indexed_opening: list[float] = field(default_factory=_years)     # row 32
    tf_cum_raised_opening: list[float] = field(default_factory=_years)  # row 33
    tf_remaining_capacity: list[float] = field(default_factory=_years)  # row 34
    tf_ltv_headroom: list[float] = field(default_factory=_years)        # row 35
    tf_funding_requirement: list[float] = field(default_factory=_years) # row 36
    tf_drawdown: list[float] = field(default_factory=_years)            # row 37
    tf_cum_raised_closing: list[float] = field(default_factory=_years)  # row 38
    tf_coupon_rate: list[float] = field(default_factory=_years)         # row 39
    tf_interest: list[float] = field(default_factory=_years)            # row 40
    tf_release: list[float] = field(default_factory=_years)             # row 41
    tf_transferred: list[float] = field(default_factory=_years)         # row 42
    tf_closing: list[float] = field(default_factory=_years)             # row 43

    # Commercial mortgage (post-refinancing)
    cm_opening: list[float] = field(default_factory=_years)             # row 46
    cm_drawdown: list[float] = field(default_factory=_years)            # row 47
    cm_interest: list[float] = field(default_factory=_years)            # row 48
    cm_principal: list[float] = field(default_factory=_years)           # row 49
    cm_closing: list[float] = field(default_factory=_years)             # row 50

    # Debt service, leverage & reserves
    total_interest: list[float] = field(default_factory=_years)         # row 53
    total_principal: list[float] = field(default_factory=_years)        # row 54
    total_debt_service: list[float] = field(default_factory=_years)     # row 55
    total_debt: list[float] = field(default_factory=_years)             # row 56
    ltv: list[float] = field(default_factory=_years)                    # row 57
    total_capital_employed: list[float] = field(default_factory=_years) # row 58
    cs_pct_of_capital: list[float] = field(default_factory=_years)      # row 59
    target_reserve: list[float] = field(default_factory=_years)         # row 60
    min_reserve_covenant: list[float] = field(default_factory=_years)   # row 61
    unfunded_requirement: list[float] = field(default_factory=_years)   # row 62
    dscr: list[float | str] = field(default_factory=_years)             # row 64
    reserve_cover: list[float | str] = field(default_factory=_years)    # row 65
    # Added Aug 2026. Not in the workbook, so deliberately absent from
    # ROW_MAP -- the Excel comparison cannot check what Excel never had.
    #
    # Row 64 is labelled DSCR but no principal is ever repaid, so it is an
    # interest cover ratio. It also counts a donated house as income, which
    # is right for the accounts and wrong for a covenant. These two strip
    # that out, at two different levels of severity.
    cash_interest_cover: list[float | str] = field(default_factory=_years)
    rent_only_cover: list[float | str] = field(default_factory=_years)

    ROW_MAP = {
        10: "gifts_living", 11: "bequests", 12: "founding_capital", 13: "gift_aid",
        14: "gift_income_total", 15: "gift_cumulative",
        18: "cs_target_issuance", 19: "cs_other_capital", 20: "cs_max_permitted",
        21: "cs_opening", 22: "cs_issued", 23: "cs_eligible_withdrawal",
        24: "cs_withdrawals", 25: "cs_issue_costs", 26: "cs_closing",
        27: "cs_dividend_rate", 28: "cs_dividends",
        30: "tf_opening", 31: "tf_indexation", 32: "tf_indexed_opening",
        33: "tf_cum_raised_opening", 34: "tf_remaining_capacity",
        35: "tf_ltv_headroom", 36: "tf_funding_requirement", 37: "tf_drawdown",
        38: "tf_cum_raised_closing", 39: "tf_coupon_rate", 40: "tf_interest",
        41: "tf_release", 42: "tf_transferred", 43: "tf_closing",
        46: "cm_opening", 47: "cm_drawdown", 48: "cm_interest",
        49: "cm_principal", 50: "cm_closing",
        53: "total_interest", 54: "total_principal", 55: "total_debt_service",
        56: "total_debt", 57: "ltv", 58: "total_capital_employed",
        59: "cs_pct_of_capital", 60: "target_reserve", 61: "min_reserve_covenant",
        62: "unfunded_requirement", 64: "dscr", 65: "reserve_cover",
    }


@dataclass
class StatementState:
    """Financial Statements sheet."""

    # Profit & loss
    rental_income: list[float] = field(default_factory=_years)          # row 10
    gifts_and_bequests: list[float] = field(default_factory=_years)     # row 11
    gift_aid: list[float] = field(default_factory=_years)               # row 12
    total_income: list[float] = field(default_factory=_years)           # row 13
    admin_costs: list[float] = field(default_factory=_years)            # row 14
    acquisition_costs: list[float] = field(default_factory=_years)      # row 15
    maintenance: list[float] = field(default_factory=_years)            # row 16
    cs_issue_costs: list[float] = field(default_factory=_years)         # row 17
    total_operating_costs: list[float] = field(default_factory=_years)  # row 18
    operating_surplus: list[float] = field(default_factory=_years)      # row 19
    interest_tontine: list[float] = field(default_factory=_years)       # row 20
    interest_mortgage: list[float] = field(default_factory=_years)      # row 21
    indexation_charge: list[float] = field(default_factory=_years)      # row 22
    surplus_before_div_tax: list[float] = field(default_factory=_years) # row 23
    dividends: list[float] = field(default_factory=_years)              # row 24
    corporation_tax: list[float] = field(default_factory=_years)        # row 25
    retained_surplus: list[float] = field(default_factory=_years)       # row 26
    cumulative_retained: list[float] = field(default_factory=_years)    # row 27

    # Balance sheet
    property_at_hpi: list[float] = field(default_factory=_years)        # row 30
    sinking_fund: list[float] = field(default_factory=_years)           # row 31
    free_cash_asset: list[float] = field(default_factory=_years)        # row 32
    total_assets: list[float] = field(default_factory=_years)           # row 33
    liability_tontine: list[float] = field(default_factory=_years)      # row 35
    liability_mortgage: list[float] = field(default_factory=_years)     # row 36
    liability_shares: list[float] = field(default_factory=_years)       # row 37
    total_liabilities: list[float] = field(default_factory=_years)      # row 38
    reserve_retained: list[float] = field(default_factory=_years)       # row 40
    reserve_revaluation: list[float] = field(default_factory=_years)    # row 41
    reserve_tontine_released: list[float] = field(default_factory=_years)  # row 42
    net_assets: list[float] = field(default_factory=_years)             # row 43
    total_liab_and_reserves: list[float] = field(default_factory=_years)   # row 44
    balance_check: list[float] = field(default_factory=_years)          # row 46

    # Cash flow
    cf_operating_surplus: list[float] = field(default_factory=_years)   # row 49
    cf_interest_paid: list[float] = field(default_factory=_years)       # row 50
    cf_dividends_paid: list[float] = field(default_factory=_years)      # row 51
    cf_tax_paid: list[float] = field(default_factory=_years)            # row 52
    cf_from_operations: list[float] = field(default_factory=_years)     # row 53
    cf_property_purchases: list[float] = field(default_factory=_years)  # row 54
    cf_from_investing: list[float] = field(default_factory=_years)      # row 55
    cf_tontine_drawdown: list[float] = field(default_factory=_years)    # row 56
    cf_shares_issued: list[float] = field(default_factory=_years)       # row 57
    cf_shares_withdrawn: list[float] = field(default_factory=_years)    # row 58
    cf_mortgage_principal: list[float] = field(default_factory=_years)  # row 59
    cf_from_financing: list[float] = field(default_factory=_years)      # row 60
    cf_net_change: list[float] = field(default_factory=_years)          # row 61
    cash_opening: list[float] = field(default_factory=_years)           # row 62
    cash_closing: list[float] = field(default_factory=_years)           # row 63
    less_sinking_earmark: list[float] = field(default_factory=_years)   # row 64
    free_cash: list[float] = field(default_factory=_years)              # row 65
    # Property gifts are income but never cash, so they are stripped back out
    # of the cash-flow statement -- the same treatment the Tontine indexation
    # uplift gets. Added after the port; no workbook row.
    cf_less_noncash_gifts: list[float] = field(default_factory=_years)

    # Memorandum
    memo_shares_raised: list[float] = field(default_factory=_years)     # row 68
    memo_tontine_drawn: list[float] = field(default_factory=_years)     # row 69
    memo_total_raised: list[float] = field(default_factory=_years)      # row 70
    memo_capital_call: list[float] = field(default_factory=_years)      # row 71

    ROW_MAP = {
        10: "rental_income", 11: "gifts_and_bequests", 12: "gift_aid",
        13: "total_income", 14: "admin_costs", 15: "acquisition_costs",
        16: "maintenance", 17: "cs_issue_costs", 18: "total_operating_costs",
        19: "operating_surplus", 20: "interest_tontine", 21: "interest_mortgage",
        22: "indexation_charge", 23: "surplus_before_div_tax", 24: "dividends",
        25: "corporation_tax", 26: "retained_surplus", 27: "cumulative_retained",
        30: "property_at_hpi", 31: "sinking_fund", 32: "free_cash_asset",
        33: "total_assets", 35: "liability_tontine", 36: "liability_mortgage",
        37: "liability_shares", 38: "total_liabilities", 40: "reserve_retained",
        41: "reserve_revaluation", 42: "reserve_tontine_released",
        43: "net_assets", 44: "total_liab_and_reserves", 46: "balance_check",
        49: "cf_operating_surplus", 50: "cf_interest_paid", 51: "cf_dividends_paid",
        52: "cf_tax_paid", 53: "cf_from_operations", 54: "cf_property_purchases",
        55: "cf_from_investing", 56: "cf_tontine_drawdown", 57: "cf_shares_issued",
        58: "cf_shares_withdrawn", 59: "cf_mortgage_principal",
        60: "cf_from_financing", 61: "cf_net_change", 62: "cash_opening",
        63: "cash_closing", 64: "less_sinking_earmark", 65: "free_cash",
        68: "memo_shares_raised", 69: "memo_tontine_drawn",
        70: "memo_total_raised", 71: "memo_capital_call",
    }


@dataclass
class MonthlyState:
    """Monthly Cash Flow sheet — 60 months (years 1-5)."""

    month: list[int] = field(default_factory=list)                      # row 6
    model_year: list[int] = field(default_factory=list)                 # row 7
    month_in_year: list[int] = field(default_factory=list)              # row 8
    rental_income: list[float] = field(default_factory=list)            # row 11
    gifts: list[float] = field(default_factory=list)                    # row 12
    founding_capital: list[float] = field(default_factory=list)         # row 13
    tontine_drawn: list[float] = field(default_factory=list)            # row 14
    shares_issued: list[float] = field(default_factory=list)            # row 15
    admin_costs: list[float] = field(default_factory=list)              # row 18
    maintenance: list[float] = field(default_factory=list)              # row 19
    acquisition_costs: list[float] = field(default_factory=list)        # row 20
    share_issue_costs: list[float] = field(default_factory=list)        # row 21
    property_purchases: list[float] = field(default_factory=list)       # row 22
    interest_paid: list[float] = field(default_factory=list)            # row 23
    mortgage_principal: list[float] = field(default_factory=list)       # row 24
    dividends: list[float] = field(default_factory=list)                # row 25
    corporation_tax: list[float] = field(default_factory=list)          # row 26
    shares_withdrawn: list[float] = field(default_factory=list)         # row 27
    net_movement: list[float] = field(default_factory=list)             # row 29
    cash_opening: list[float] = field(default_factory=list)             # row 30
    cash_closing: list[float] = field(default_factory=list)             # row 31
    less_sinking_earmark: list[float] = field(default_factory=list)     # row 32
    free_cash: list[float] = field(default_factory=list)                # row 33
    buffer_status: list[str] = field(default_factory=list)              # row 34
    reconciliation: list[float | str] = field(default_factory=list)     # row 36

    ROW_MAP = {
        6: "month", 7: "model_year", 8: "month_in_year",
        11: "rental_income", 12: "gifts", 13: "founding_capital",
        14: "tontine_drawn", 15: "shares_issued", 18: "admin_costs",
        19: "maintenance", 20: "acquisition_costs", 21: "share_issue_costs",
        22: "property_purchases", 23: "interest_paid", 24: "mortgage_principal",
        25: "dividends", 26: "corporation_tax", 27: "shares_withdrawn",
        29: "net_movement", 30: "cash_opening", 31: "cash_closing",
        32: "less_sinking_earmark", 33: "free_cash", 34: "buffer_status",
        36: "reconciliation",
    }


@dataclass
class ModelState:
    """Everything one scenario run produces."""

    growth: GrowthState = field(default_factory=GrowthState)
    assets: AssetState = field(default_factory=AssetState)
    capital: CapitalState = field(default_factory=CapitalState)
    statements: StatementState = field(default_factory=StatementState)
    monthly: MonthlyState = field(default_factory=MonthlyState)


# Which state object reproduces which workbook sheet. Drives validation.
SHEET_MAP = {
    "Growth Engine": ("growth", GrowthState.ROW_MAP),
    "Asset Register": ("assets", AssetState.ROW_MAP),
    "Capital & Debt": ("capital", CapitalState.ROW_MAP),
    "Financial Statements": ("statements", StatementState.ROW_MAP),
    "Monthly Cash Flow": ("monthly", MonthlyState.ROW_MAP),
}
