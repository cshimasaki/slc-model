"""
Formatted Excel workbook — the secondary output, for accountants and business plans.

Reproduces the reader-facing statements with proper number formatting, section
grouping and totals. Not a raw data dump: an accountant should be able to open
it and read it as accounts.

Values, not formulas, with one deliberate exception. Python is the source of
computational truth, so the workbook carries the numbers the model computed
rather than re-deriving them in a second, subtly different implementation.

The exception is the "What-if" sheet, which is genuinely live. It is safe to be
live because it does not reproduce the model: it computes the steady-state
economics of a SINGLE HOUSE, which is a page of arithmetic. That page happens to
govern the headline decisions -- marginal cover on one debt-funded house is the
ratio the whole portfolio converges to -- so it is worth being able to poke at.
It has no sense of time, and says so on the face of it.

CSVs of the raw yearly tables are written alongside for anyone who wants the
underlying data.
"""

from __future__ import annotations

import csv
import os
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from engine import pricing
from engine.model import ModelRun, run_all
from engine.state import SHEET_MAP

FONT = "Arial"

# Number formats. Zeros render as "-" and negatives in parentheses, which is
# what an accountant expects to see.
FMT_MONEY = '£#,##0;(£#,##0);-'
FMT_MONEY_DP = '£#,##0.00;(£#,##0.00);-'
FMT_PCT = '0.0%;(0.0%);-'
FMT_RATIO = '0.00"×";(0.00"×");-'
FMT_COUNT = '#,##0;(#,##0);-'
FMT_MONTHS = '0.0" mo";(0.0" mo");-'

FMT_BY_UNIT = {
    "£": FMT_MONEY, "%": FMT_PCT, "x": FMT_RATIO,
    "count": FMT_COUNT, "months": FMT_MONTHS,
}

INK = "FF0B0B0B"
MUTED = "FF52514E"
RULE = "FFBFBFBF"
BAND = "FFF2F2F2"
HEADER_FILL = "FF1F3864"
INPUT_BLUE = "FF0000FF"

thin = Side(style="thin", color=RULE)
medium = Side(style="medium", color=INK)


def _title(ws, text: str, subtitle: str, width: int) -> int:
    """Write the two-line header every sheet carries. Returns the next row."""
    ws["A1"] = text
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=INK)
    ws["A2"] = subtitle
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color=MUTED)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(2, width))
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(2, width))
    return 4


def _year_header(ws, row: int, n_years: int, calendar_years: list[int], first_col: int = 3) -> None:
    """Model year / calendar year column headings, frozen for scrolling."""
    ws.cell(row=row, column=1, value="Line item").font = Font(name=FONT, bold=True, color="FFFFFFFF")
    ws.cell(row=row, column=2, value="Unit").font = Font(name=FONT, bold=True, color="FFFFFFFF")
    for i in range(n_years):
        c = ws.cell(row=row, column=first_col + i, value=f"Y{i + 1}")
        c.font = Font(name=FONT, bold=True, color="FFFFFFFF")
        c.alignment = Alignment(horizontal="right")
    for col in range(1, first_col + n_years):
        ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=HEADER_FILL)

    sub = row + 1
    ws.cell(row=sub, column=1, value="").font = Font(name=FONT)
    for i, cal in enumerate(calendar_years):
        c = ws.cell(row=sub, column=first_col + i, value=cal)
        c.font = Font(name=FONT, size=9, color=MUTED)
        c.number_format = "0"
        c.alignment = Alignment(horizontal="right")
    for col in range(1, first_col + n_years):
        ws.cell(row=sub, column=col).border = Border(bottom=medium)


def _section(ws, row: int, label: str, n_years: int) -> int:
    ws.cell(row=row, column=1, value=label).font = Font(name=FONT, bold=True, size=10, color=INK)
    for col in range(1, 3 + n_years):
        ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=BAND)
    return row + 1


def _line(ws, row: int, label: str, unit: str, values: list, *, bold=False,
          rule_above=False, indent=1) -> int:
    """One line item across the year columns."""
    cell = ws.cell(row=row, column=1, value=label)
    cell.font = Font(name=FONT, bold=bold, color=INK)
    cell.alignment = Alignment(indent=indent)
    ws.cell(row=row, column=2, value=unit).font = Font(name=FONT, size=9, color=MUTED)

    fmt = FMT_BY_UNIT.get(unit, FMT_MONEY)
    for i, value in enumerate(values):
        c = ws.cell(row=row, column=3 + i)
        c.value = value if isinstance(value, (int, float)) else None
        c.number_format = fmt
        c.font = Font(name=FONT, bold=bold, color=INK)
        if rule_above:
            c.border = Border(top=thin)
    if rule_above:
        ws.cell(row=row, column=1).border = Border(top=thin)
        ws.cell(row=row, column=2).border = Border(top=thin)
    return row + 1


def _finish(ws, n_years: int, header_row: int, first_col: int = 3) -> None:
    ws.freeze_panes = ws.cell(row=header_row + 2, column=first_col)
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 9
    for i in range(n_years):
        ws.column_dimensions[get_column_letter(first_col + i)].width = 14
    ws.sheet_view.showGridLines = False


# --------------------------------------------------------------- sheets ----

def _dashboard(wb: Workbook, result: ModelRun) -> None:
    from .json_bundle import DSCR_COVENANT
    from .series import HEADLINES

    ws = wb.create_sheet("Dashboard")
    state = result.state
    row = _title(ws, "Stroud Land Commons — Dashboard",
                 f"Scenario: {result.scenario.title()} · {result.n_years}-year projection · "
                 f"computed by the Python model", 4)

    ws.cell(row=row, column=1, value="Headline figures").font = Font(name=FONT, bold=True, size=11)
    row += 1

    from .json_bundle import build_scenario_block
    block = build_scenario_block(result)
    for key, meta in block["headline"].items():
        ws.cell(row=row, column=1, value=meta["label"]).font = Font(name=FONT)
        c = ws.cell(row=row, column=2, value=meta["value"])
        c.number_format = FMT_BY_UNIT.get(meta["unit"], FMT_MONEY)
        c.font = Font(name=FONT, bold=True)
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Covenant position").font = Font(name=FONT, bold=True, size=11)
    row += 1
    a = result.assumptions
    checks = [
        ("Minimum cash interest cover", block["headline"]["min_cash_cover"]["value"],
         getattr(a, "cov_cash_cover_min", DSCR_COVENANT), "above", FMT_RATIO),
        ("Minimum rent-only interest cover", block["headline"]["min_rent_only"]["value"],
         getattr(a, "cov_rent_only_min", 1.0), "above", FMT_RATIO),
        ("Minimum interest cover (all income, legacy)",
         block["headline"]["min_dscr"]["value"], DSCR_COVENANT, "above", FMT_RATIO),
        ("Peak LTV", block["headline"]["max_ltv"]["value"],
         result.assumptions.pf_ltv_limit, "below", FMT_PCT),
        ("Minimum reserve cover", block["headline"]["min_reserve_cover"]["value"],
         result.assumptions.reserve_min_months, "above", FMT_MONTHS),
    ]
    ws.cell(row=row, column=1, value="Measure").font = Font(name=FONT, bold=True)
    ws.cell(row=row, column=2, value="Value").font = Font(name=FONT, bold=True)
    ws.cell(row=row, column=3, value="Limit").font = Font(name=FONT, bold=True)
    ws.cell(row=row, column=4, value="Status").font = Font(name=FONT, bold=True)
    row += 1
    for label, value, limit, direction, fmt in checks:
        ws.cell(row=row, column=1, value=label).font = Font(name=FONT)
        c = ws.cell(row=row, column=2, value=value); c.number_format = fmt; c.font = Font(name=FONT)
        c = ws.cell(row=row, column=3, value=limit); c.number_format = fmt; c.font = Font(name=FONT)
        ok = (value >= limit) if direction == "above" else (value <= limit + 1e-9)
        c = ws.cell(row=row, column=4, value="OK" if ok else "BREACH")
        c.font = Font(name=FONT, bold=True, color="FF006300" if ok else "FFC00000")
        row += 1

    ws.column_dimensions["A"].width = 42
    for col in "BCD":
        ws.column_dimensions[col].width = 16
    ws.sheet_view.showGridLines = False


def _financial_statements(wb: Workbook, result: ModelRun) -> None:
    ws = wb.create_sheet("Financial Statements")
    f = result.state.statements
    n = result.n_years
    cal = result.macro.calendar_year

    row = _title(ws, "Financial Statements",
                 f"Scenario: {result.scenario.title()} · P&L, balance sheet and cash flow · "
                 f"all figures £ unless stated", 3 + n)
    header_row = row
    _year_header(ws, row, n, cal)
    row += 2

    row = _section(ws, row, "PROFIT & LOSS", n)
    row = _line(ws, row, "Rental income (net of voids)", "£", f.rental_income)
    row = _line(ws, row, "Bequests, gifts & founding capital", "£", f.gifts_and_bequests)
    row = _line(ws, row, "Gift Aid recovery", "£", f.gift_aid)
    row = _line(ws, row, "Total income", "£", f.total_income, bold=True, rule_above=True)
    row = _line(ws, row, "Admin costs", "£", f.admin_costs)
    row = _line(ws, row, "Acquisition transaction costs", "£", f.acquisition_costs)
    row = _line(ws, row, "Structural maintenance", "£", f.maintenance)
    row = _line(ws, row, "Community share issuance costs", "£", f.cs_issue_costs)
    row = _line(ws, row, "Total operating costs", "£", f.total_operating_costs, bold=True, rule_above=True)
    row = _line(ws, row, "Operating surplus", "£", f.operating_surplus, bold=True, rule_above=True)
    row = _line(ws, row, "Interest — Tontine", "£", f.interest_tontine)
    row = _line(ws, row, "Interest — commercial mortgage", "£", f.interest_mortgage)
    row = _line(ws, row, "Indexation uplift on Tontine principal (non-cash)", "£", f.indexation_charge)
    row = _line(ws, row, "Surplus before dividends & tax", "£", f.surplus_before_div_tax,
                bold=True, rule_above=True)
    row = _line(ws, row, "Community share dividends", "£", f.dividends)
    row = _line(ws, row, "Corporation tax", "£", f.corporation_tax)
    row = _line(ws, row, "Retained surplus for the year", "£", f.retained_surplus, bold=True, rule_above=True)
    row = _line(ws, row, "Cumulative retained surplus", "£", f.cumulative_retained, bold=True)
    row += 1

    row = _section(ws, row, "BALANCE SHEET", n)
    row = _line(ws, row, "Property portfolio at HPI value", "£", f.property_at_hpi)
    row = _line(ws, row, "CapEx sinking fund", "£", f.sinking_fund)
    row = _line(ws, row, "Free cash / operating reserves", "£", f.free_cash_asset)
    row = _line(ws, row, "Total assets", "£", f.total_assets, bold=True, rule_above=True)
    row = _line(ws, row, "Tontine fund", "£", f.liability_tontine)
    row = _line(ws, row, "Commercial mortgage", "£", f.liability_mortgage)
    row = _line(ws, row, "Community share capital (junior debt)", "£", f.liability_shares)
    row = _line(ws, row, "Total liabilities", "£", f.total_liabilities, bold=True, rule_above=True)
    row = _line(ws, row, "Cumulative retained surplus", "£", f.reserve_retained)
    row = _line(ws, row, "HPI revaluation reserve", "£", f.reserve_revaluation)
    row = _line(ws, row, "Tontine principal released to reserves", "£", f.reserve_tontine_released)
    row = _line(ws, row, "Net assets", "£", f.net_assets, bold=True, rule_above=True)
    row = _line(ws, row, "Total liabilities & reserves", "£", f.total_liab_and_reserves, bold=True)
    row = _line(ws, row, "Check: assets less liabilities & reserves (must be nil)", "£",
                f.balance_check, rule_above=True)
    row += 1

    row = _section(ws, row, "CASH FLOW", n)
    row = _line(ws, row, "Operating surplus", "£", f.cf_operating_surplus)
    row = _line(ws, row, "Interest paid (cash)", "£", f.cf_interest_paid)
    row = _line(ws, row, "Dividends paid", "£", f.cf_dividends_paid)
    row = _line(ws, row, "Tax paid", "£", f.cf_tax_paid)
    row = _line(ws, row, "Net cash from operations", "£", f.cf_from_operations, bold=True, rule_above=True)
    row = _line(ws, row, "Property purchases", "£", f.cf_property_purchases)
    row = _line(ws, row, "Net cash from investing", "£", f.cf_from_investing, bold=True, rule_above=True)
    row = _line(ws, row, "Tontine drawdown", "£", f.cf_tontine_drawdown)
    row = _line(ws, row, "Community shares issued", "£", f.cf_shares_issued)
    row = _line(ws, row, "Community shares withdrawn", "£", f.cf_shares_withdrawn)
    row = _line(ws, row, "Commercial mortgage principal repaid", "£", f.cf_mortgage_principal)
    row = _line(ws, row, "Net cash from financing", "£", f.cf_from_financing, bold=True, rule_above=True)
    row = _line(ws, row, "Net change in cash", "£", f.cf_net_change, bold=True, rule_above=True)
    row = _line(ws, row, "Cash — opening", "£", f.cash_opening)
    row = _line(ws, row, "Cash — closing", "£", f.cash_closing, bold=True)
    row = _line(ws, row, "Less: CapEx sinking fund (earmarked)", "£", f.less_sinking_earmark)
    row = _line(ws, row, "Free cash / operating reserves", "£", f.free_cash, bold=True, rule_above=True)

    _finish(ws, n, header_row)


def _monthly(wb: Workbook, result: ModelRun) -> None:
    ws = wb.create_sheet("Monthly Cash Flow")
    mo = result.state.monthly
    n = len(mo.month)

    row = _title(ws, "Monthly Cash Flow — Years 1–5",
                 f"Scenario: {result.scenario.title()} · phasing of the annual cash flow. "
                 f"Acquisitions and their funding fall in the acquisition month.", 3 + n)
    header_row = row

    ws.cell(row=row, column=1, value="Line item").font = Font(name=FONT, bold=True, color="FFFFFFFF")
    ws.cell(row=row, column=2, value="Unit").font = Font(name=FONT, bold=True, color="FFFFFFFF")
    for i in range(n):
        c = ws.cell(row=row, column=3 + i, value=f"M{mo.month[i]}")
        c.font = Font(name=FONT, bold=True, color="FFFFFFFF")
        c.alignment = Alignment(horizontal="right")
    for col in range(1, 3 + n):
        ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=HEADER_FILL)
    for i in range(n):
        c = ws.cell(row=row + 1, column=3 + i, value=f"Y{mo.model_year[i]}")
        c.font = Font(name=FONT, size=9, color=MUTED)
        c.alignment = Alignment(horizontal="right")
    for col in range(1, 3 + n):
        ws.cell(row=row + 1, column=col).border = Border(bottom=medium)
    row += 2

    row = _section(ws, row, "RECEIPTS", n)
    row = _line(ws, row, "Rental income received", "£", mo.rental_income)
    row = _line(ws, row, "Cash gifts, bequests & Gift Aid", "£", mo.gifts)
    row = _line(ws, row, "Founding capital injection", "£", mo.founding_capital)
    row = _line(ws, row, "Tontine capital drawn", "£", mo.tontine_drawn)
    row = _line(ws, row, "Community shares issued", "£", mo.shares_issued)
    row += 1

    row = _section(ws, row, "PAYMENTS", n)
    row = _line(ws, row, "Admin costs", "£", mo.admin_costs)
    row = _line(ws, row, "Structural maintenance", "£", mo.maintenance)
    row = _line(ws, row, "Acquisition transaction costs", "£", mo.acquisition_costs)
    row = _line(ws, row, "Share issuance / marketing costs", "£", mo.share_issue_costs)
    row = _line(ws, row, "Property purchases", "£", mo.property_purchases)
    row = _line(ws, row, "Interest paid", "£", mo.interest_paid)
    row = _line(ws, row, "Commercial mortgage principal repaid", "£", mo.mortgage_principal)
    row = _line(ws, row, "Community share dividends", "£", mo.dividends)
    row = _line(ws, row, "Corporation tax", "£", mo.corporation_tax)
    row = _line(ws, row, "Community shares withdrawn", "£", mo.shares_withdrawn)
    row += 1

    row = _line(ws, row, "Net movement in cash", "£", mo.net_movement, bold=True, rule_above=True)
    row = _line(ws, row, "Cash — opening", "£", mo.cash_opening)
    row = _line(ws, row, "Cash — closing", "£", mo.cash_closing, bold=True)
    row = _line(ws, row, "Less: sinking fund earmarked (pro-rated)", "£", mo.less_sinking_earmark)
    row = _line(ws, row, "Free cash — closing", "£", mo.free_cash, bold=True, rule_above=True)

    ws.cell(row=row, column=1, value="Below minimum operating cash buffer?").font = Font(name=FONT)
    ws.cell(row=row, column=2, value="").font = Font(name=FONT)
    for i, status in enumerate(mo.buffer_status):
        c = ws.cell(row=row, column=3 + i, value=status)
        c.font = Font(name=FONT, bold=status == "BREACH",
                      color="FFC00000" if status == "BREACH" else "FF006300")
        c.alignment = Alignment(horizontal="right")

    _finish(ws, n, header_row)


def _asset_register(wb: Workbook, result: ModelRun) -> None:
    ws = wb.create_sheet("Asset Register")
    A = result.state.assets
    g = result.state.growth
    n = result.n_years
    cal = result.macro.calendar_year

    row = _title(ws, "Asset Register",
                 f"Scenario: {result.scenario.title()} · portfolio value, rent and acquisition "
                 f"costs. Each acquisition year is tracked as its own cohort.", 3 + n)
    header_row = row
    _year_header(ws, row, n, cal)
    row += 2

    row = _section(ws, row, "PORTFOLIO", n)
    row = _line(ws, row, "Properties — opening", "count", g.portfolio_opening)
    row = _line(ws, row, "Properties acquired in year", "count", g.properties_acquired)
    row = _line(ws, row, "Properties — closing", "count", g.portfolio_closing, bold=True)
    row = _line(ws, row, "Portfolio value (HPI-indexed)", "£", A.portfolio_value, bold=True)
    row = _line(ws, row, "Additions at cost in year", "£", A.additions_at_cost)
    row = _line(ws, row, "HPI revaluation gain / (loss)", "£", A.revaluation_gain)
    row += 1

    row = _section(ws, row, "RENT", n)
    row = _line(ws, row, "Total gross annual rent", "£", A.gross_rent)
    row = _line(ws, row, "Land Commons net rental income", "£", A.net_rental_income, bold=True)
    row += 1

    row = _section(ws, row, "ACQUISITION COSTS", n)
    row = _line(ws, row, "Purchase price paid", "£", A.purchase_price)
    row = _line(ws, row, "SDLT", "£", A.sdlt)
    row = _line(ws, row, "Conveyancing", "£", A.conveyancing)
    row = _line(ws, row, "Surveys", "£", A.surveys)
    row = _line(ws, row, "Initial retrofit", "£", A.retrofit)
    row = _line(ws, row, "Total transaction costs", "£", A.transaction_costs, bold=True, rule_above=True)
    row = _line(ws, row, "Total acquisition cash cost", "£", A.acquisition_cash_cost, bold=True)
    row += 1

    row = _section(ws, row, "CAPEX SINKING FUND", n)
    row = _line(ws, row, "Opening balance", "£", A.sinking_opening)
    row = _line(ws, row, "Contribution", "£", A.sinking_contribution)
    row = _line(ws, row, "Investment return", "£", A.sinking_return)
    row = _line(ws, row, "Structural maintenance spend", "£", A.maintenance_spend)
    row = _line(ws, row, "Closing balance", "£", A.sinking_closing, bold=True, rule_above=True)

    _finish(ws, n, header_row)


def _capital(wb: Workbook, result: ModelRun) -> None:
    ws = wb.create_sheet("Capital & Debt")
    c = result.state.capital
    n = result.n_years
    cal = result.macro.calendar_year

    row = _title(ws, "Capital & Debt",
                 f"Scenario: {result.scenario.title()} · Tontine fund (index-linked, "
                 f"interest-only), community shares (junior debt), gifts and bequests.", 3 + n)
    header_row = row
    _year_header(ws, row, n, cal)
    row += 2

    row = _section(ws, row, "BEQUESTS & GIFTS", n)
    row = _line(ws, row, "Cash gifts from living donors", "£", c.gifts_living)
    row = _line(ws, row, "Bequests from estates", "£", c.bequests)
    row = _line(ws, row, "Founding capital injection", "£", c.founding_capital)
    row = _line(ws, row, "Gift Aid recovery", "£", c.gift_aid)
    row = _line(ws, row, "Total gift income", "£", c.gift_income_total, bold=True, rule_above=True)
    row = _line(ws, row, "Cumulative gifts & bequests", "£", c.gift_cumulative)
    row += 1

    row = _section(ws, row, "COMMUNITY SHARES (JUNIOR DEBT)", n)
    row = _line(ws, row, "Opening share capital", "£", c.cs_opening)
    row = _line(ws, row, "Shares issued", "£", c.cs_issued)
    row = _line(ws, row, "Withdrawals", "£", c.cs_withdrawals)
    row = _line(ws, row, "Issuance / marketing costs", "£", c.cs_issue_costs)
    row = _line(ws, row, "Closing share capital", "£", c.cs_closing, bold=True, rule_above=True)
    row = _line(ws, row, "Dividends payable", "£", c.cs_dividends)
    row = _line(ws, row, "Share capital as % of total capital", "%", c.cs_pct_of_capital)
    row += 1

    row = _section(ws, row, "TONTINE FUND", n)
    row = _line(ws, row, "Opening balance", "£", c.tf_opening)
    row = _line(ws, row, "CPI indexation uplift on principal", "£", c.tf_indexation)
    row = _line(ws, row, "Indexed opening balance", "£", c.tf_indexed_opening)
    row = _line(ws, row, "Drawdown", "£", c.tf_drawdown)
    row = _line(ws, row, "Cumulative capital raised", "£", c.tf_cum_raised_closing)
    row = _line(ws, row, "Interest paid", "£", c.tf_interest)
    row = _line(ws, row, "Progressive release to reserves", "£", c.tf_release)
    row = _line(ws, row, "Transferred on refinancing", "£", c.tf_transferred)
    row = _line(ws, row, "Closing balance", "£", c.tf_closing, bold=True, rule_above=True)
    row += 1

    row = _section(ws, row, "COMMERCIAL MORTGAGE", n)
    row = _line(ws, row, "Opening balance", "£", c.cm_opening)
    row = _line(ws, row, "Drawdown on refinancing", "£", c.cm_drawdown)
    row = _line(ws, row, "Interest paid", "£", c.cm_interest)
    row = _line(ws, row, "Principal repaid", "£", c.cm_principal)
    row = _line(ws, row, "Closing balance", "£", c.cm_closing, bold=True, rule_above=True)
    row += 1

    row = _section(ws, row, "DEBT SERVICE, LEVERAGE & RESERVES", n)
    row = _line(ws, row, "Total interest paid", "£", c.total_interest)
    row = _line(ws, row, "Total principal repaid", "£", c.total_principal)
    row = _line(ws, row, "Total debt service", "£", c.total_debt_service, bold=True, rule_above=True)
    row = _line(ws, row, "Total debt outstanding", "£", c.total_debt, bold=True)
    row = _line(ws, row, "Loan-to-value", "%", c.ltv)
    row = _line(ws, row, "Target reserve", "£", c.target_reserve)
    row = _line(ws, row, "Minimum reserve covenant", "£", c.min_reserve_covenant)
    row = _line(ws, row, "Unfunded acquisition requirement", "£", c.unfunded_requirement)
    row = _line(ws, row, "Interest cover — all income", "x", c.dscr, bold=True)
    row = _line(ws, row, "Interest cover — cash income", "x", c.cash_interest_cover, bold=True)
    row = _line(ws, row, "Interest cover — rent only", "x", c.rent_only_cover, bold=True)
    row = _line(ws, row, "Reserve cover", "months", c.reserve_cover)

    _finish(ws, n, header_row)


SCENARIO_ORDER = ["base", "optimistic", "stress"]


def _stock_rows(ws, row: int, p: dict) -> int:
    """
    The acquisition mix, one property type per row, per scenario column.

    Shows the share of acquisitions each type takes, and beneath the label the
    price and rent that produce its yield -- because the yield is the whole
    reason this section exists, and a reader who cannot see where it came from
    will assume it was chosen rather than derived.
    """
    ws.cell(row=row, column=1, value=p["label"]).font = Font(name=FONT, italic=True)
    ws.cell(row=row, column=1).alignment = Alignment(indent=1)
    ws.cell(row=row, column=2, value="share of purchases").font = Font(
        name=FONT, size=9, color=MUTED
    )

    # Union of the types across scenarios, in the order Base lists them, so a
    # type that only Optimistic buys still gets a row rather than vanishing.
    names: list[str] = []
    for scenario in SCENARIO_ORDER:
        for t in p["values"][scenario]:
            if t["name"] not in names:
                names.append(t["name"])

    for k, name in enumerate(names, start=1):
        r = row + k
        detail = next(
            (t for s in SCENARIO_ORDER for t in p["values"][s] if t["name"] == name), None
        )
        ws.cell(row=r, column=1, value=name).font = Font(name=FONT)
        ws.cell(row=r, column=1).alignment = Alignment(indent=2)
        if detail:
            yld = detail["rent_pcm"] * 12 / detail["price"]
            ws.cell(
                row=r, column=2,
                value=f"£{detail['price']:,.0f} · £{detail['rent_pcm']:,.0f} pcm · {yld:.2%}",
            ).font = Font(name=FONT, size=9, color=MUTED)

        for j, scenario in enumerate(SCENARIO_ORDER):
            share = next(
                (t["share"] for t in p["values"][scenario] if t["name"] == name), None
            )
            # A blank, not a zero: this scenario does not buy that type at all,
            # which is a different statement from buying none of it this year.
            c = ws.cell(row=r, column=3 + j, value=share if share is not None else "—")
            c.font = Font(name=FONT, color=INPUT_BLUE if share is not None else MUTED)
            c.number_format = "0%" if share is not None else "General"
    return row + len(names) + 1


def _assumptions_sheet(wb: Workbook, results: dict[str, ModelRun]) -> None:
    """All three scenarios' inputs side by side, as the workbook's own sheet did."""
    from .json_bundle import build_assumptions_block

    ws = wb.create_sheet("Assumptions")
    row = _title(ws, "Assumptions",
                 "All parameters, grouped as in Control & Parameters. Blue values are set by "
                 "that scenario; grey values are inherited from Base.", 5)

    for col, head in enumerate(["Parameter", "Unit", "Base", "Optimistic", "Stress"], start=1):
        c = ws.cell(row=row, column=col, value=head)
        c.font = Font(name=FONT, bold=True, color="FFFFFFFF")
        c.fill = PatternFill("solid", fgColor=HEADER_FILL)
    row += 1

    for section in build_assumptions_block():
        ws.cell(row=row, column=1, value=section["title"]).font = Font(name=FONT, bold=True, size=10)
        for col in range(1, 6):
            ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=BAND)
        row += 1
        for p in section["params"]:
            # The stock mix is a table, not a number: each scenario holds a list
            # of property types with their own price and rent. Writing the list
            # into a cell is not possible and flattening it to a string would
            # bury the most consequential decision in the model in a wall of
            # punctuation. It gets its own rows instead.
            if isinstance(p["values"]["base"], list):
                _stock_rows(ws, row, p)
                row += 1 + max(len(p["values"][s]) for s in SCENARIO_ORDER)
                continue

            ws.cell(row=row, column=1, value=p["label"]).font = Font(name=FONT)
            ws.cell(row=row, column=1).alignment = Alignment(indent=1)
            ws.cell(row=row, column=2, value=p["unit"]).font = Font(name=FONT, size=9, color=MUTED)
            for j, scenario in enumerate(["base", "optimistic", "stress"]):
                value = p["values"][scenario]
                c = ws.cell(row=row, column=3 + j, value=value)
                overridden = p["overridden"][scenario]
                c.font = Font(name=FONT, color=INPUT_BLUE if overridden else MUTED,
                              bold=overridden and scenario != "base")
                unit = p["unit"] or ""
                if "%" in unit:
                    c.number_format = "0.00%"
                elif unit.startswith("£"):
                    c.number_format = FMT_MONEY
                else:
                    c.number_format = "General"
            row += 1

    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 22
    for col in "CDE":
        ws.column_dimensions[col].width = 16
    ws.sheet_view.showGridLines = False


def _comparison(wb: Workbook, results: dict[str, ModelRun]) -> None:
    """Base / Optimistic / Stress headline figures on one page."""
    from .json_bundle import build_scenario_block

    ws = wb.create_sheet("Scenario Comparison", 1)
    row = _title(ws, "Scenario comparison",
                 "Headline figures for all three scenarios, from the same computed model run.", 4)

    blocks = {name: build_scenario_block(r) for name, r in results.items()}
    for col, head in enumerate(["Measure", "Base", "Optimistic", "Stress"], start=1):
        c = ws.cell(row=row, column=col, value=head)
        c.font = Font(name=FONT, bold=True, color="FFFFFFFF")
        c.fill = PatternFill("solid", fgColor=HEADER_FILL)
    row += 1

    for key in blocks["base"]["headline"]:
        meta = blocks["base"]["headline"][key]
        ws.cell(row=row, column=1, value=meta["label"]).font = Font(name=FONT)
        for j, name in enumerate(["base", "optimistic", "stress"]):
            h = blocks[name]["headline"][key]
            c = ws.cell(row=row, column=2 + j, value=h["value"])
            c.number_format = FMT_BY_UNIT.get(h["unit"], FMT_MONEY)
            c.font = Font(name=FONT)
        row += 1

    ws.column_dimensions["A"].width = 44
    for col in "BCD":
        ws.column_dimensions[col].width = 18
    ws.sheet_view.showGridLines = False


def _what_if(wb: Workbook, result: ModelRun,
             results: dict[str, ModelRun]) -> None:
    """
    A live, editable per-house calculator. The only sheet with real formulas.

    Everything else in this workbook carries values, because Python is the
    source of computational truth and a second implementation in Excel would
    drift. This sheet is the deliberate exception, and it is safe to be one
    because it does NOT reproduce the model: it computes the steady-state
    economics of a single house, which is a page of arithmetic rather than fifty
    years of compounding.

    It earns its place because that arithmetic is what governs the four headline
    decisions. Marginal cover on one debt-funded house is the ratio the whole
    portfolio converges to; the fifty-year model mostly shows how long it takes
    to get there. So a reader who wants to know what a lower LTV or a dearer
    house does can find out here in a second, then check it against the modelled
    scenarios on the other sheets.

    What it cannot tell you is anything about time. Growth, the early-years
    ramp, reserve building, mortality extinguishing the charge, gifts arriving,
    scale efficiency -- none of it is here.
    """
    a = result.assumptions
    ws = wb.create_sheet("What-if", 2)
    row = _title(ws, "What-if \u2014 one house, steady state",
                 "The only sheet with live formulas. Edit the blue cells and everything below "
                 "recalculates. Per-house economics only: it says nothing about growth or time.", 4)

    def head(text, r):
        ws.cell(row=r, column=1, value=text).font = Font(name=FONT, bold=True, size=10)
        for col in range(1, 5):
            ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor=BAND)
        return r + 1

    def field(r, label, value, fmt, note=""):
        ws.cell(row=r, column=1, value=label).font = Font(name=FONT)
        ws.cell(row=r, column=1).alignment = Alignment(indent=1)
        c = ws.cell(row=r, column=2, value=value)
        c.number_format = fmt
        c.font = Font(name=FONT, bold=True, color=INPUT_BLUE)
        c.fill = PatternFill("solid", fgColor="FFEAF1FB")
        c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        if note:
            ws.cell(row=r, column=3, value=note).font = Font(name=FONT, size=9, color=MUTED)
        return r + 1

    st = a.stock_types[0] if getattr(a, "stock_types", None) else None
    price = float(st["price"]) if st else float(a.avg_price)
    rent_pcm = float(st["rent_pcm"]) if st else a.avg_price * a.gross_yield / 12

    row = head("INPUTS \u2014 edit these", row)
    r_price = row;  row = field(row, "House price", price, FMT_MONEY,
                                "the biggest lever on this page")
    r_rent = row;   row = field(row, "Rent per month", rent_pcm, FMT_MONEY,
                                "below market \u2014 a commitment, not a dial")
    r_fees = row;   row = field(row, "Fees and retrofit on purchase",
                                float(a.conveyancing + a.survey_cost + a.retrofit_cost), FMT_MONEY)
    r_maint = row;  row = field(row, "Maintenance + admin, months of rent",
                                float(getattr(a, "lc_maintenance_months", 2.0)), "0.0",
                                "covers admin AND maintenance")
    r_void = row;   row = field(row, "Void rate", float(a.void_rate), FMT_PCT)
    r_sink = row;   row = field(row, "Sinking fund per house per year",
                                float(a.sinking_per_prop), FMT_MONEY,
                                "major works; not inside the months above")
    row += 1
    r_ltv = row;    row = field(row, "LTV limit \u2014 Tontine share of value",
                                float(a.pf_ltv_limit), FMT_PCT)
    r_coup = row;   row = field(row, "Tontine investor rate (real)",
                                float(a.pf_investor_rate), FMT_PCT)
    r_reg = row;    row = field(row, "Fund regulatory capital charge",
                                float(a.pf_fund_reg_charge), FMT_PCT)
    r_srate = row;  row = field(row, "Share rate advertised",
                                float(a.cs_dividend_rate), FMT_PCT)
    r_sshare = row; row = field(row, "Shares \u2014 share of purchase funded",
                                float(getattr(a, "mix_shares_start", 0.45)), FMT_PCT)
    row += 1
    r_target = row; row = field(row, "Target cover (for the max-price answer)",
                                float(getattr(a, "cov_cash_cover_min", 1.25)), FMT_RATIO)
    row += 1

    def B(r):
        return "B%d" % r

    cost = "(%s+%s)" % (B(r_price), B(r_fees))
    gross = "(%s*12)" % B(r_rent)
    net = "(%s*(1-%s/12)*(1-%s))" % (gross, B(r_maint), B(r_void))
    ton_debt = "(%s*%s)" % (B(r_price), B(r_ltv))
    ton_int = "(%s*(%s+%s))" % (ton_debt, B(r_coup), B(r_reg))
    sh_cap = "(%s*%s)" % (cost, B(r_sshare))
    sh_int = "(%s*%s)" % (sh_cap, B(r_srate))
    avail = "(%s-%s)" % (net, B(r_sink))

    row = head("WHAT THE HOUSE EARNS AND OWES", row)
    lines = [
        ("All-in cost to acquire", "=" + cost, FMT_MONEY, "price plus fees and retrofit"),
        ("Gross rent per year", "=" + gross, FMT_MONEY, ""),
        ("Gross yield on price", "=%s/%s" % (gross, B(r_price)), FMT_PCT,
         "matched stock, not average rent over average price"),
        ("Net rent to the Commons", "=" + net, FMT_MONEY, "after maintenance, admin and voids"),
        ("Available after the sinking fund", "=" + avail, FMT_MONEY,
         "this is what capital has to be paid out of"),
        (None, None, None, None),
        ("Tontine debt this house carries", "=" + ton_debt, FMT_MONEY, ""),
        ("Tontine interest per year", "=" + ton_int, FMT_MONEY,
         "extinguishes when the investor dies"),
        ("Share capital this house carries", "=" + sh_cap, FMT_MONEY, ""),
        ("Share interest per year", "=" + sh_int, FMT_MONEY, "permanent, and discretionary"),
        ("Free capital required", "=%s-%s-%s" % (cost, ton_debt, sh_cap), FMT_MONEY,
         "gifts and retained surplus must cover this"),
        ("Free capital as a share of cost",
         "=(%s-%s-%s)/%s" % (cost, ton_debt, sh_cap, cost), FMT_PCT, ""),
    ]
    for label, formula, fmt, note in lines:
        if label is None:
            row += 1
            continue
        ws.cell(row=row, column=1, value=label).font = Font(name=FONT)
        ws.cell(row=row, column=1).alignment = Alignment(indent=1)
        c = ws.cell(row=row, column=2, value=formula)
        c.number_format = fmt
        c.font = Font(name=FONT)
        if note:
            ws.cell(row=row, column=3, value=note).font = Font(name=FONT, size=9, color=MUTED)
        row += 1

    row += 1
    row = head("THE ANSWERS", row)
    maxprice = "%s/(%s*%s*(%s+%s))-%s" % (
        avail, B(r_target), B(r_ltv), B(r_coup), B(r_reg), B(r_fees))
    answers = [
        ("Senior cover \u2014 can rent pay the annuity?", "=%s/%s" % (avail, ton_int), FMT_RATIO,
         "the covenant that protects the annuitant"),
        ("All-in cover \u2014 can it also pay the share offer?",
         "=%s/(%s+%s)" % (avail, ton_int, sh_int), FMT_RATIO,
         "below 1.0 the offer under-delivers; it is not a default"),
        ("Most we can pay for this house, at target cover", "=" + maxprice, FMT_MONEY,
         "compare with the price above"),
        ("Headroom against the price paid", "=(%s)/%s-1" % (maxprice, B(r_price)), FMT_PCT,
         "negative means this house is too dear on these terms"),
        ("Rent discount senior cover would still allow",
         "=1-(%s*%s+%s)/%s" % (B(r_target), ton_int, B(r_sink), net), FMT_PCT,
         "before any growth is given up"),
    ]
    for label, formula, fmt, note in answers:
        ws.cell(row=row, column=1, value=label).font = Font(name=FONT, bold=True)
        ws.cell(row=row, column=1).alignment = Alignment(indent=1)
        c = ws.cell(row=row, column=2, value=formula)
        c.number_format = fmt
        c.font = Font(name=FONT, bold=True)
        ws.cell(row=row, column=3, value=note).font = Font(name=FONT, size=9, color=MUTED)
        row += 1

    row += 2
    row = head("HOW THIS COMPARES WITH THE MODELLED RUNS", row)
    for name, r in results.items():
        cover = [v for v in r.state.capital.cash_interest_cover if isinstance(v, (int, float))]
        allin = [v for v in r.state.capital.all_in_cover if isinstance(v, (int, float))]
        ws.cell(row=row, column=1,
                value="%s \u2014 minimum over 50 years" % name.title()).font = Font(name=FONT)
        ws.cell(row=row, column=1).alignment = Alignment(indent=1)
        c = ws.cell(row=row, column=2, value=min(cover) if cover else None)
        c.number_format = FMT_RATIO
        c.font = Font(name=FONT)
        ws.cell(row=row, column=3,
                value="senior; all-in minimum %.2f" % (min(allin) if allin else 0)
                ).font = Font(name=FONT, size=9, color=MUTED)
        row += 1

    row += 1
    ws.cell(row=row, column=1,
            value="Why those numbers differ from this page \u2014 read this before worrying."
            ).font = Font(name=FONT, bold=True, size=10)
    row += 1
    for line in [
        "This page prices a house bought TODAY, carrying today's capital mix: Tontine and shares",
        "together fund about nine tenths of it, so all-in cover looks thin. The modelled portfolio",
        "does far better because free capital \u2014 gifts, and surplus retained year after year \u2014",
        "grows to roughly three quarters of the balance sheet by year 50, and the Tontine charge",
        "extinguishes as its investors die. Neither of those can appear on a single-house page.",
        "",
        "So the difference is not an error in either place. This page shows the marginal house;",
        "the scenario sheets show the portfolio that owns it.",
        "",
        "It cuts the other way too. A configuration that looks comfortable here can still breach in",
        "year 7, because the early years carry full fixed costs on a handful of houses. Use this",
        "page to understand WHY a change helps or hurts; use the scenario sheets to find out",
        "whether it survives.",
    ]:
        ws.cell(row=row, column=1, value=line).font = Font(name=FONT, size=9, color=MUTED)
        row += 1

    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 54
    ws.sheet_view.showGridLines = False


def _for_review(wb: Workbook, results: dict[str, ModelRun]) -> None:
    """
    A sheet written for the reviewer, not for the model.

    An advisor opening a 50-year projection needs to know two things before the
    numbers mean anything: what has been assumed that is not yet evidenced, and
    which decisions are still open. Burying those in a code repository and
    handing over only the outputs would be presenting the model as more settled
    than it is.
    """
    from engine.tontine_runoff import load_curve

    ws = wb.create_sheet("For Review", 1)
    a = results["base"].assumptions
    curve = load_curve()
    life = sum(curve.survival_at(t) for t in range(61))

    row = _title(ws, "For the reviewer — open questions and known limits",
                 "Read before the figures. Everything here is a judgement the model "
                 "cannot make for itself.", 3)

    def block(heading, lines):
        nonlocal row
        ws.cell(row=row, column=1, value=heading).font = Font(name=FONT, bold=True, size=11)
        for c in range(1, 4):
            ws.cell(row=row, column=c).fill = PatternFill("solid", fgColor=BAND)
        row += 1
        for label, value in lines:
            ws.cell(row=row, column=1, value=label).font = Font(name=FONT)
            ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
            c = ws.cell(row=row, column=2, value=value)
            c.font = Font(name=FONT, bold=True)
            c.alignment = Alignment(horizontal="left")
            row += 1
        row += 1

    inv = a.pf_investor_rate
    recovered = sum(inv * 100 * curve.survival_at(t) for t in range(61))

    # Computed, not remembered. These four numbers were hardcoded and had gone
    # stale by roughly 150bp: every structural change since moves them, and this
    # sheet is the one an external reviewer reads first.
    front = pricing.frontier()
    gap_bp = pricing.gap(front)

    def pct(v):
        return f"{v * 100:.2f}%" if v is not None else "no rate clears"

    # Measured on STRESS, not on whichever scenario the workbook was built for.
    # This line answers "what does the modelled rate cost us in the bad case",
    # and reporting Base's comfortable zero here would answer a question nobody
    # asked while looking like reassurance.
    stress = results["stress"]
    breaches = sum(
        1 for v in stress.state.capital.cash_interest_cover
        if isinstance(v, (int, float)) and v < stress.assumptions.cov_cash_cover_min
    )

    block("1. THE PRICING FRONTIER — the most important open question", [
        ("Highest coupon with no covenant breach: Optimistic", pct(front["optimistic"])),
        ("Highest coupon with no covenant breach: Base", pct(front["base"])),
        ("Highest coupon with no covenant breach: Stress (binding)", pct(front["stress"])),
        ("Coupon an investor needs to break even by median survival (age 87)",
         pct(front["investor_break_even"])),
        ("Gap between what Stress bears and what an investor needs",
         "n/a" if gap_bp is None else f"{gap_bp:+.0f} bp"),
        ("Currently modelled", f"{inv * 100:.2f}%"),
        ("Capital the investor recovers over their expected life", f"{recovered:.0f}%"),
        ("Consequence at the modelled rate",
         f"Stress breaches in {breaches} of {stress.n_years} years"
         if breaches else "Stress clears every covenant in every year"),
        ("The question for you", "Is a self-imposed covenant allowed to breach in a severe stress?"),
    ])

    block("2. WHAT THE INSTRUMENT ACTUALLY IS", [
        ("Principal repaid to the investor", "Never — the charge is extinguished on death"),
        ("So the investor's entire return is", "the coupon, while they live"),
        ("Which means the investor", "does not recover their capital in full"),
        ("And the Commons receives", "the shortfall, as a permanently unencumbered home"),
        ("These are the same transaction", "viewed from opposite sides"),
    ])

    block("3. THE MORTALITY BASIS IS A PLACEHOLDER", [
        ("Source", "ONS population mortality, Gompertz-Makeham fit"),
        ("Improvements applied", "CMI-style, 1.25% p.a."),
        ("Cohort life expectancy at 65 used here", f"{life:.1f} years"),
        ("NOT an annuitant basis", "annuitants self-select and live longer"),
        ("Therefore these figures", "UNDERSTATE longevity cost — a favourable bound"),
        ("Real dataset expected", "Department of Actuarial Mathematics, September 2026"),
    ])

    block("4. DECISIONS STILL OPEN", [
        ("What happens to a dead investor's capital",
         "100% to the Commons is assumed; a split with survivors is undecided"),
        ("Cost of conceding it entirely to investors", "roughly £42m of net assets by Year 50"),
        ("Tranche structure", "single 10-year raise modelled; rolling ring-fenced tranches not yet built"),
        ("Community share cap", f"{a.cs_max_pct_capital:.0%} of capital — binds in 17 of 50 years"),
        ("Rent Credit Obligations", "deliberately out of scope — separate vehicle, different economics"),
    ])

    block("5. WHAT THE MODEL CANNOT TELL YOU", [
        ("Gift and bequest income", "an input, not a forecast — the model cannot bound it"),
        ("Investor appetite at any price", "behavioural, not modelled"),
        ("Where efficiency savings go", "assumed retained; intent is to share or spend on retrofit"),
        ("Withdrawal clustering", "modelled as a smooth rate; reality clusters"),
        ("Credit, default and arrears", "not modelled at all"),
    ])

    ws.column_dimensions["A"].width = 62
    ws.column_dimensions["B"].width = 58
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------- entry ----

def write_workbook(path: str, scenario: str = "base",
                   results: dict[str, ModelRun] | None = None) -> str:
    """Write the formatted workbook for one scenario, plus a comparison sheet."""
    results = results or run_all()
    result = results[scenario]

    wb = Workbook()
    wb.remove(wb.active)

    _dashboard(wb, result)
    _for_review(wb, results)
    _what_if(wb, result, results)
    _comparison(wb, results)
    _financial_statements(wb, result)
    _monthly(wb, result)
    _asset_register(wb, result)
    _capital(wb, result)
    _assumptions_sheet(wb, results)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb.save(path)
    return path


def write_csvs(out_dir: str, results: dict[str, ModelRun] | None = None) -> list[str]:
    """
    Raw yearly tables, one CSV per sheet per scenario.

    Deliberately unformatted: this is the door out of the model for anyone who
    wants the numbers in their own tool.
    """
    results = results or run_all()
    os.makedirs(out_dir, exist_ok=True)
    written = []

    for scenario, result in results.items():
        for sheet_name, (attr, row_map) in SHEET_MAP.items():
            state_obj = getattr(result.state, attr)
            is_monthly = sheet_name == "Monthly Cash Flow"
            periods = (list(result.state.monthly.month) if is_monthly
                       else list(range(1, result.n_years + 1)))
            header = ["line_item", "source_row"] + [
                (f"M{p}" if is_monthly else f"Y{p}") for p in periods
            ]

            slug = sheet_name.lower().replace(" & ", "_").replace(" ", "_")
            path = os.path.join(out_dir, f"{scenario}_{slug}.csv")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                for row_num, field in sorted(row_map.items()):
                    values = getattr(state_obj, field)
                    writer.writerow([field, row_num] + list(values))
            written.append(path)

    return written
