"""
Formatted Excel workbook — the secondary output, for accountants and business plans.

Reproduces the reader-facing statements with proper number formatting, section
grouping and totals. Not a raw data dump: an accountant should be able to open
it and read it as accounts.

Values, not formulas. Python is the source of computational truth, so the
workbook carries the numbers the model computed rather than re-deriving them in
a second, subtly different implementation. `--formulas` emits a clearly
separate variant with a live inputs tab for people who want to poke at it; the
authoritative figures remain the default export.

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
    checks = [
        ("Minimum DSCR", block["headline"]["min_dscr"]["value"], DSCR_COVENANT, "above", FMT_RATIO),
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
    row = _line(ws, row, "DSCR", "x", c.dscr, bold=True)
    row = _line(ws, row, "Reserve cover", "months", c.reserve_cover)

    _finish(ws, n, header_row)


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


# ---------------------------------------------------------------- entry ----

def write_workbook(path: str, scenario: str = "base",
                   results: dict[str, ModelRun] | None = None) -> str:
    """Write the formatted workbook for one scenario, plus a comparison sheet."""
    results = results or run_all()
    result = results[scenario]

    wb = Workbook()
    wb.remove(wb.active)

    _dashboard(wb, result)
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
