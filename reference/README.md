# Reference — the original workbook

`Financial Modelling for SLC V2.1.xlsx` is the Excel model this project was
ported from. It is kept here for three reasons:

1. **It is the validation reference.** The figures in
   `validation/baselines/*.json` were extracted from this exact file. Keeping
   the workbook alongside them means anyone can regenerate the baselines and
   check that claim, rather than taking it on trust.
2. **It is the historical record.** This is where the model came from, and the
   spec the port was written against. The formulas *were* the specification.
3. **It travels with the repo.** A teammate who clones gets it, without having
   to be sent a copy separately.

## This is not the live model any more

**The Python model in `engine/` is the source of truth.** Editing this workbook
changes nothing: no output is generated from it, and nothing reads it except
the baseline extractor, on demand.

To change an assumption, edit `assumptions/*.yaml` and re-run the export. See
[INSTALL.md](../INSTALL.md).

## Frozen at V2.1

This file is the version the port was validated against, cell for cell, across
all three scenarios. Treat it as frozen.

If the spreadsheet is ever revised, **do not overwrite this file**. Add the new
version alongside it and treat re-validating against it as a deliberate piece
of work — the baselines would need regenerating, and any resulting difference
in the Python model's output is a finding to investigate, not a number to
accept. Overwriting silently would destroy the only record of what the port was
actually checked against.

## Regenerating the baselines from it

Windows with Excel, plus `pip install pywin32`. From the repo root:

```bash
python validation/extract_excel_baseline.py
```

It finds this file automatically. It drives Excel to switch the scenario
dropdown and force a full recalculation, working on a temporary copy — this
file is never modified.

Extraction is deterministic: re-running it against an unchanged workbook
produces byte-identical baselines. So if `git diff validation/baselines/` shows
changes after a run, something real has changed, and it is worth understanding
what before committing.

## Integrity

```
SHA-256  6dbadc5e1e741a08be4d4e5229a8f3e3d791c8919c93bdea76a1265949ad2088
Size     373,224 bytes
```

Recorded so the file this project was validated against can be identified
unambiguously later:

```bash
sha256sum "reference/Financial Modelling for SLC V2.1.xlsx"
```
