# Stroud Land Commons — financial model

[![Tests & Excel validation](https://github.com/cshimasaki/slc-model/actions/workflows/ci.yml/badge.svg)](https://github.com/cshimasaki/slc-model/actions/workflows/ci.yml)

A 50-year projection of the Stroud Land Commons: a community land trust that
buys homes using a **Tontine fund** (a closed-end lifetime annuity mutual),
**community shares** (junior debt), and gifts and bequests.

Ported from `Financial Modelling for SLC V2.1.xlsx`, and validated
number-for-number against it across all three scenarios.

**→ [Open the interactive explorer](https://cshimasaki.github.io/slc-model/)**

**New here, or catching up?** [CHANGES.md](CHANGES.md) summarises what has
changed since the original spreadsheet and what the model now says — written
to be read without opening any code.

The badge above is not decoration: it goes red the moment the Python model
stops reproducing the original spreadsheet, cell for cell, across all three
scenarios.

## Three layers, kept separate

| Layer | Where | What it is |
|---|---|---|
| **Assumptions** | [`assumptions/`](assumptions/) | Plain-text YAML. The layer a non-coder reads and edits. |
| **Mechanics** | [`engine/`](engine/) | Python. One module per engine. Changes rarely. |
| **Outputs** | [`export/`](export/), [`explorer/`](explorer/) | An interactive web page, an Excel workbook, and CSVs — all rendered from the same computed figures. |

Python is the single source of computational truth. The explorer page displays
results; it does not re-implement the model.

## Quick start

**Setting this up for the first time? See [INSTALL.md](INSTALL.md)** — it covers
installing Python, what you need for each way of using the project, and
troubleshooting.

Requires Python 3.11+.

```bash
pip install -r requirements.txt
```

Run the model and build every output:

```bash
python -m export.build_all
```

Check it still matches Excel:

```bash
python validation/compare.py
```

Run the tests:

```bash
python -m pytest tests/ -q
```

## The explorer

`explorer/index.html` plus the generated `explorer/data.json` — a single static
page, no server and no build step, deployable to GitHub Pages.

View it locally (the browser blocks reading `data.json` from `file://`, so it
needs to be served):

```bash
python -m http.server 8000
```

then open `http://localhost:8000/explorer/`.

It has three parts: an **assumptions panel** grouped by the workbook's own
headings with Base/Optimistic/Stress side by side; **interactive charts** for
the key trajectories; and a **scenario switcher** with a **compare mode** that
overlays all three scenarios on one measure.

Switching and comparing are instant because every scenario is already in the
JSON. The page displays results — it never recomputes them. Changing an
assumption means editing the YAML and re-running the export.

**The seam for live what-ifs:** all data access goes through the `DataSource`
object at the top of the script. Pointing it at a Python API that accepts
edited assumptions and returns the same bundle shape is a change to `load()`
and nothing else — no chart, table or panel touches the transport.

## Changing an assumption

Edit the relevant value in [`assumptions/base.yaml`](assumptions/base.yaml) (or
a scenario's delta file), then re-run `python -m export.build_all`. The
explorer, the workbook and the CSVs all update from it.

Percentages are fractions: `0.025` is 2.5%.

## Scenarios

Base holds the full parameter set. Optimistic and Stress hold **only their
deltas**, so a diff between two files *is* the scenario definition:

```bash
diff assumptions/base.yaml assumptions/stress.yaml
```

See [`assumptions/README.md`](assumptions/README.md) for what question each
scenario answers.

## Validation

`validation/compare.py` runs the model and diffs **13,150 cells per scenario**
— every line item of every engine sheet, including all 100 acquisition-vintage
cohort rows — against figures Excel itself produced.

The reference figures in `validation/baselines/` are committed, so validation
runs on a machine with no Excel installed. The original workbook is committed
too, at [`reference/`](reference/) — so the claim "these figures came from that
spreadsheet" can be checked rather than taken on trust. To regenerate them
(needs Excel on Windows):

```bash
python validation/extract_excel_baseline.py
```

That script drives Excel via COM to switch the Dashboard's scenario dropdown
and force a full recalculation. It works on a **copy** — the source workbook is
never modified.

The tolerance is set for floating-point noise only (1e-9 relative). Anything a
person could notice fails the check. `tests/test_validation.py` includes a
negative control proving the harness detects a 0.1% single-parameter drift — a
comparison that cannot fail is worse than none.

## What the model currently says

Reproduced faithfully from the workbook, not introduced by the port:

- **Base is in covenant breach.** Minimum DSCR 0.97× against a 1.20× covenant,
  breaching in 21 of 50 years. Minimum reserve cover −8.2 months.
- **Stress is materially worse.** Minimum DSCR 0.61×; cumulative retained
  surplus ends at −£16.9m.
- **Optimistic clears its covenants**, ending with 130 properties and £237m net
  assets.

These are real results, not artefacts. See [`MODEL_LOG.md`](MODEL_LOG.md) for
the four known quirks carried over from the workbook and why each was
reproduced rather than fixed.

## Making structural changes

Anything that changes how the model *works* — a refinancing waterfall, RCO
redemption logic, a new capital layer — goes on a branch:

```bash
git checkout -b structure/<hypothesis>
```

Compare its outputs against `main` under all three scenarios, then record
hypothesis, change, result and decision in [`MODEL_LOG.md`](MODEL_LOG.md).
Rejected-but-interesting branches get tagged and left, not deleted.

## Layout

```
assumptions/     YAML inputs — base plus per-scenario deltas
engine/          the model: macro, growth, assets, capital_debt, statements, monthly
export/          JSON bundle, Excel workbook, CSVs
explorer/        single-file interactive page (Chart.js from CDN)
validation/      Excel baseline extraction and the row-by-row diff
tests/           invariants, assumptions behaviour, and the validator's negative control
reference/       the original workbook this was ported from (frozen at V2.1)
.github/         CI on every push; Pages deploy rebuilds the explorer from the YAML
```
