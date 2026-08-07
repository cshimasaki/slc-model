"""Export the Tontine liability run-off from the indicative actuarial model."""
import csv
import openpyxl

SRC = r"C:\Users\chika\Documents\Commons\Housing Commons\Finance\SLC_Tontine_Indicative_Model.xlsx"
OUT = r"C:\Users\chika\Documents\Commons\Housing Commons\Finance\slc-model\assumptions\tontine_runoff.csv"

wb = openpyxl.load_workbook(SRC, data_only=True)
proj = wb["Projection"]
cohorts = wb["Cohorts"]
assumptions = wb["Assumptions"]

annual_raise = assumptions["B14"].value
phase = assumptions["B15"].value
total_raise = annual_raise * phase

rows = []
lives0 = None
for r in range(4, 65):
    year = proj[f"A{r}"].value
    lives = proj[f"B{r}"].value
    tp = proj[f"J{r}"].value            # TP incl. expense reserve, real
    if year is None:
        continue
    if lives0 is None:
        lives0 = lives
    # Row 5 is the first entry cohort: lx by years since ITS OWN entry, which
    # is the survival curve a single investor faces. Column C is age 0.
    lx = cohorts.cell(row=5, column=3 + int(year)).value
    rows.append({
        "fund_year": int(year),
        "lives_index": lives / lives0 if lives0 else 0.0,
        "tp_per_pound_raised": (tp or 0.0) / total_raise,
        "cohort_survivorship": lx if lx is not None else 0.0,
    })

HEADER = """\
# Tontine liability run-off - PLACEHOLDER actuarial basis
#
# Exported from SLC_Tontine_Indicative_Model.xlsx (August 2026) by
# validation/extract_tontine_runoff.py.
#
# Population mortality (ONS 2021-23, Gompertz-Makeham fit) with CMI-style
# improvements at 1.25% p.a. This is NOT an annuitant basis: real annuitants
# self-select for longevity and live longer, so this curve UNDERSTATES the
# liability and should be read as a favourable bound.
#
# REPLACE THIS FILE when the Department of Actuarial Mathematics dataset
# arrives (expected September 2026). Nothing else has to change - the release
# rule reads this curve, so re-exporting it re-runs the whole model.
#
# Columns
#   fund_year            years since the first Tontine drawdown (0 = first year)
#   lives_index          annuitants alive, relative to the first year's cohort.
#                        RISES during the investment phase as new cohorts join
#                        (peaking near 9.5x around year 9), then runs off to
#                        approximately zero by year 60. It is an index, not a
#                        survivorship fraction.
#   tp_per_pound_raised  technical provisions per GBP 1 of capital raised, in
#                        real terms, including the expense reserve
#   cohort_survivorship  lx for a SINGLE entry cohort: the probability an
#                        investor entering at 65 is still alive this many
#                        years later. This is what drives the charge, since
#                        a charge is released when its own investor dies.
#                        Taken from the first cohort; later cohorts see
#                        slightly lighter mortality thanks to improvements,
#                        so using one curve for all marginally OVERSTATES
#                        deaths and therefore releases.
"""

with open(OUT, "w", newline="", encoding="utf-8") as f:
    f.write(HEADER)
    w = csv.DictWriter(f, fieldnames=["fund_year", "lives_index", "tp_per_pound_raised", "cohort_survivorship"])
    w.writeheader()
    for row in rows:
        w.writerow({
            "fund_year": row["fund_year"],
            "lives_index": f'{row["lives_index"]:.10f}',
            "tp_per_pound_raised": f'{row["tp_per_pound_raised"]:.10f}',
            "cohort_survivorship": f'{row["cohort_survivorship"]:.10f}',
        })

print(f"wrote {len(rows)} years -> {OUT}")
for i in (0, 9, 10, 25, 40, 50, 54, 56, 60):
    row = next((x for x in rows if x["fund_year"] == i), None)
    if row:
        print(f"  yr {i:>2}  lives_index {row['lives_index']:>7.4f}   "
              f"TP per GBP raised {row['tp_per_pound_raised']:.5f}")
