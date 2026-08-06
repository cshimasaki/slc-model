# Installing and running the SLC model

For someone setting this up on their own machine for the first time.

There are three ways to use this project, and most people only need the first.

---

## 1. I just want to look at the numbers

**Use the published explorer.** Ask whoever set up the repo for the GitHub
Pages URL. Nothing to install — it opens in a browser, and you can switch
scenarios and compare them there.

**Or open the Excel workbook.** Someone with the project installed can run
`python -m export.build_all` and send you `dist/SLC_Financial_Model_base.xlsx`.
It has the dashboard, statements, monthly cash flow, asset register and all
assumptions, formatted to hand to an accountant.

You do not need Python for either of these.

---

## 2. I want to change an assumption and see what happens

You need Python, but you do not need to write any.

### Install

**Python 3.11 or newer.** Check what you have:

```bash
python --version
```

If that says 3.10 or lower, or "command not found", install it from
[python.org/downloads](https://www.python.org/downloads/). On Windows, tick
**"Add Python to PATH"** in the installer — it is easy to miss and everything
below fails without it.

Then, from the project folder:

```bash
pip install -r requirements.txt
```

### Check it works

```bash
python validation/compare.py
```

You should see `PASS — the Python model reproduces the Excel workbook exactly.`
If you see anything else, stop and tell whoever maintains the project — it
means something is wrong before you have changed anything.

### Change something

Open `assumptions/base.yaml` in any text editor. It is grouped under the same
headings as the old spreadsheet's *Control & Parameters* sheet. Find the number
you want to change, change it, save.

**Percentages are fractions.** `0.025` means 2.5%. Writing `2.5` means 250%.

Then rebuild everything:

```bash
python -m export.build_all
```

### Look at the result

```bash
python -m http.server 8000
```

Open <http://localhost:8000/explorer/>. (Opening `explorer/index.html` directly
from your file manager will not work — browsers block it from reading its own
data file. The command above is the way round it.)

Your Excel workbook and CSVs are in `dist/`.

### Share it

Commit the YAML change and push. If the repo has GitHub Pages set up, the
published page rebuilds itself within a couple of minutes — you do not need to
commit anything you built locally.

```bash
git add assumptions/
git commit -m "Raise the void rate assumption to 8%"
git push
```

---

## 3. I want to work on the model itself

Everything above, plus:

```bash
python -m pytest tests/ -q
```

28 tests: the model's own invariants, the assumptions layer's behaviour, and a
negative control proving the Excel validation can actually fail.

### The rule that matters

**Changing an input is a YAML edit. Changing how the model works is a branch.**

Anything that alters the mechanics — a refinancing waterfall, redemption logic,
a new capital layer — goes on `structure/<hypothesis>`, gets compared against
`main` under all three scenarios, and gets an entry in
[`MODEL_LOG.md`](MODEL_LOG.md). Rejected experiments are tagged and left, not
deleted.

### Regenerating the Excel baselines

You will almost certainly never need this. The reference figures the model is
validated against are committed, which is why validation works on any machine.

You only need to regenerate them if the **original spreadsheet itself** changes.
That needs **Windows with Excel installed**, plus `pip install pywin32`:

```bash
python validation/extract_excel_baseline.py
```

The workbook is committed at
[`reference/`](reference/), so this works straight after a clone with no path
to configure. It drives Excel to switch the scenario dropdown and force a
recalculation, working on a temporary copy — the file is never modified.

Extraction is deterministic. Re-running it against an unchanged workbook
produces byte-identical baselines, so if `git diff validation/baselines/` shows
anything afterwards, something real has changed and is worth understanding
before you commit it.

---

## Troubleshooting

**`python: command not found`** — Python is not installed, or not on PATH. On
Windows, re-run the installer and tick "Add Python to PATH". Try `py` instead
of `python` on Windows.

**`ModuleNotFoundError: No module named 'yaml'`** — dependencies are not
installed. Run `pip install -r requirements.txt` from the project folder.

**The explorer page says "Could not load data.json"** — either you opened the
HTML file directly instead of serving it (see above), or you have not run
`python -m export.build_all` yet.

**`validation/compare.py` says FAIL** — the model no longer matches the
spreadsheet. This is meant to be loud. It lists every mismatching figure with
the year and the size of the gap. Do not work around it; it means a real
difference has appeared.

**Charts look empty** — try a hard refresh (Ctrl+F5 / Cmd+Shift+R). The browser
may be holding an old `data.json`.

---

## What depends on what

| You want to | You need |
|---|---|
| Read the numbers | A browser. Nothing else. |
| Change assumptions, rebuild outputs | Python 3.11+ and `requirements.txt` |
| Run the tests | The same |
| Regenerate the Excel baselines | Windows, Excel, and `pywin32` |

The model itself is plain Python and has no compiled dependencies. It runs on
Windows, macOS and Linux. Only the baseline extractor is Windows-only, and it
is optional.
