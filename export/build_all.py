"""
Build every output from one model run.

    python -m export.build_all

Runs each scenario once and renders all outputs from those same figures, so the
web page, the workbook and the CSVs cannot disagree with each other.
"""

from __future__ import annotations

import argparse
import os

from engine.model import run_all

from . import excel_export, json_bundle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPLORER_DIR = os.path.join(ROOT, "explorer")
DIST_DIR = os.path.join(ROOT, "dist")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="base",
                        help="scenario for the single-scenario Excel workbook (default: base)")
    parser.add_argument("--skip-excel", action="store_true", help="only build the explorer bundle")
    parser.add_argument("--separate", action="store_true",
                        help="one workbook per scenario instead of a single combined one")
    args = parser.parse_args()

    print("Running the model ...")
    results = run_all()
    for name, result in results.items():
        headline = result.state.statements.net_assets[-1]
        print(f"  {name:<11} {result.n_years} years · "
              f"{result.state.growth.portfolio_closing[-1]:.0f} properties · "
              f"net assets £{headline:,.0f}")

    print("\nExplorer bundle")
    bundle_path = os.path.join(EXPLORER_DIR, "data.json")
    json_bundle.write(bundle_path, results)
    size_kb = os.path.getsize(bundle_path) / 1024
    print(f"  {os.path.relpath(bundle_path, ROOT)}  ({size_kb:,.0f} KB)")

    if not args.skip_excel:
        print("\nExcel workbook")
        if args.separate:
            xlsx_path = os.path.join(DIST_DIR, f"SLC_Financial_Model_{args.scenario}.xlsx")
            excel_export.write_workbook(xlsx_path, args.scenario, results)
        else:
            # The default. Three separate workbooks repeated three identical
            # sheets and left the Base file looking complete when it held no
            # detail for the other two scenarios.
            xlsx_path = os.path.join(DIST_DIR, "SLC_Financial_Model.xlsx")
            excel_export.write_combined(xlsx_path, results)
        print(f"  {os.path.relpath(xlsx_path, ROOT)}")

        print("\nCSVs")
        csv_dir = os.path.join(DIST_DIR, "csv")
        written = excel_export.write_csvs(csv_dir, results)
        print(f"  {len(written)} files in {os.path.relpath(csv_dir, ROOT)}")

    print("\nDone. View the explorer with:")
    print("  python -m http.server 8000")
    print("  http://localhost:8000/explorer/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
