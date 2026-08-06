"""
Extract ground-truth baselines from the original Excel workbook.

Drives Excel via COM to switch the Dashboard scenario dropdown, force a full
recalculation, and dump every year-series row of every engine sheet to JSON.
The Python model is then diffed against these files by compare.py.

This is the authority the port is validated against, so it reads the real
workbook through the real Excel calculation engine -- not openpyxl's cached
values, which only ever hold the last-saved scenario (Base).

The original workbook is never modified: it is copied to a temp file first and
that copy is closed without saving.

Run:  python validation/extract_excel_baseline.py
"""

import json
import os
import shutil
import sys
import tempfile

SOURCE_XLSX = r"C:\Users\chika\Documents\Commons\Housing Commons\Finance\Financial Modelling for SLC V2.1.xlsx"

SCENARIOS = ["Base", "Optimistic", "Stress"]

# Year-series sheets run model years 1..50 across columns D..BA.
YEAR_FIRST_COL, YEAR_LAST_COL = "D", "BA"
# Monthly Cash Flow runs months 1..60 across columns D..BK.
MONTH_FIRST_COL, MONTH_LAST_COL = "D", "BK"

# (sheet name) -> list of row numbers to capture across the year columns.
# Row numbers are the workbook's own; labels live in column A and are captured
# separately so the JSON is readable without the spreadsheet open.
YEAR_ROWS = {
    "Macro & Indexation": list(range(6, 21)),
    "Growth Engine": [9, 10, 11] + list(range(14, 21)) + list(range(23, 28)),
    "Capital & Debt": (
        list(range(10, 16))
        + list(range(18, 29))
        + list(range(30, 44))
        + list(range(46, 51))
        + list(range(53, 63))
        + [64, 65]
    ),
    # Includes the 50 value-cohort rows (10-59) and 50 rent-cohort rows (66-115)
    # so a mismatch can be traced to a single acquisition vintage.
    "Asset Register": (
        list(range(10, 64))
        + list(range(66, 120))
        + list(range(122, 129))
        + list(range(131, 136))
    ),
    "Financial Statements": (
        list(range(10, 28))
        + list(range(30, 47))
        + list(range(49, 66))
        + list(range(68, 72))
    ),
}

MONTH_ROWS = {
    "Monthly Cash Flow": [6, 7, 8] + list(range(11, 16)) + list(range(18, 28)) + list(range(29, 35)) + [36],
}

# Dashboard is a reporting sheet of single cells rather than year series.
DASHBOARD_CELLS = (
    ["C3", "C4", "C5"]
    + [f"C{r}" for r in range(10, 26)]                      # KEY METRICS
    + [f"{c}{r}" for r in range(30, 37) for c in "CDEF"]    # HEALTH CHECK
    + [f"C{r}" for r in range(39, 48)]                      # WORST CASE
)


def _clean(v):
    """Normalise a COM value into something JSON-serialisable."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    # Excel error values and dates arrive as odd COM types; stringify them so a
    # mismatch is visible rather than crashing the extract.
    return str(v)


def extract(app, wb, scenario):
    """Switch to `scenario`, recalculate, and return every captured value."""
    dash = wb.Worksheets("Dashboard")
    dash.Range("C3").Value = scenario
    app.CalculateFullRebuild()

    got = dash.Range("C3").Value
    if got != scenario:
        raise RuntimeError(f"Dashboard!C3 is {got!r} after setting {scenario!r}")

    out = {"scenario": scenario, "sheets": {}, "dashboard": {}}

    for sheet_name, rows in YEAR_ROWS.items():
        ws = wb.Worksheets(sheet_name)
        sheet_out = {}
        for row in rows:
            label = _clean(ws.Range(f"A{row}").Value)
            rng = ws.Range(f"{YEAR_FIRST_COL}{row}:{YEAR_LAST_COL}{row}").Value2
            # A single-row range comes back as a 1-tuple of a 50-tuple.
            values = [_clean(v) for v in rng[0]]
            sheet_out[str(row)] = {"label": label, "values": values}
        out["sheets"][sheet_name] = sheet_out

    for sheet_name, rows in MONTH_ROWS.items():
        ws = wb.Worksheets(sheet_name)
        sheet_out = {}
        for row in rows:
            label = _clean(ws.Range(f"A{row}").Value)
            rng = ws.Range(f"{MONTH_FIRST_COL}{row}:{MONTH_LAST_COL}{row}").Value2
            values = [_clean(v) for v in rng[0]]
            sheet_out[str(row)] = {"label": label, "values": values}
        out["sheets"][sheet_name] = sheet_out

    for addr in DASHBOARD_CELLS:
        out["dashboard"][addr] = _clean(dash.Range(addr).Value)

    return out


def main():
    import win32com.client

    if not os.path.exists(SOURCE_XLSX):
        sys.exit(f"Source workbook not found: {SOURCE_XLSX}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines")
    os.makedirs(out_dir, exist_ok=True)

    # Work on a copy so the user's workbook is never touched.
    tmp_dir = tempfile.mkdtemp(prefix="slc_baseline_")
    work_xlsx = os.path.join(tmp_dir, "work.xlsx")
    shutil.copy2(SOURCE_XLSX, work_xlsx)

    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False
    app.AskToUpdateLinks = False
    app.ScreenUpdating = False

    wb = None
    try:
        wb = app.Workbooks.Open(work_xlsx, UpdateLinks=0, ReadOnly=False)
        original = wb.Worksheets("Dashboard").Range("C3").Value
        print(f"Workbook opened. Dashboard scenario on disk: {original!r}")

        for scenario in SCENARIOS:
            print(f"  extracting {scenario} ...", flush=True)
            data = extract(app, wb, scenario)
            path = os.path.join(out_dir, f"{scenario.lower()}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            print(f"    -> {path}")
    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        app.Quit()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("Done.")


if __name__ == "__main__":
    main()
