# Port reference — assumptions frozen at the moment of the port

These are the assumption files **exactly as they stood when the Python model
was validated against `Financial Modelling for SLC V2.1.xlsx`**. They are
frozen. Do not edit them to reflect current thinking.

## Why they exist

The Excel comparison answers one question: *does the engine faithfully
reproduce the original spreadsheet?* That question has a fixed answer, and it
must keep having one no matter how the project's assumptions evolve.

Without this directory the two things get conflated. The first time someone
changes an input — as happened immediately, moving the investor annuity rate
from 3.0% to 2.5% — validation reports 4,234 mismatching cells. Nothing is
broken: the engine is untouched and still correct. The inputs simply moved,
and the workbook, being a fixed artefact, did not move with them.

Conflating the two has a specific failure mode. Validation goes red for a
legitimate reason, someone concludes the check is noisy, and it stops being
read. The next failure — a real translation bug — arrives to an audience that
has already learned to ignore it.

So:

| Question | Inputs used | Where |
|---|---|---|
| Does the engine reproduce the spreadsheet? | **These frozen files** | `validation/compare.py` |
| What do we currently assume? | `assumptions/*.yaml` | everything else |

## What this means in practice

`validation/compare.py` reads these files, never `assumptions/`. So the Excel
check stays green through any amount of assumption-tuning, and goes red only if
the **mechanics** change in a way that no longer reproduces the workbook.

That is exactly the signal worth having. A structural change on a
`structure/` branch is *expected* to move these numbers — and when it does, the
comparison tells you precisely which line items and by how much, which is the
raw material for a MODEL_LOG entry.

## When to update these files

Almost never. Only if the source workbook in `reference/` is itself replaced by
a corrected version, in which case the baselines get regenerated too and the
pair is updated together, deliberately, in one commit.

Changing a project assumption is **never** a reason to touch these.
