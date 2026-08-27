# Working on this model

A fifty-year financial model of Stroud Land Commons — a housing commons that buys
homes, lets them below market rent, and never sells. Ported from
`Financial Modelling for SLC V2.1.xlsx` into Python so the assumptions, the
mechanics and the outputs are separable and version-controlled.

Read `MODEL_LOG.md` before changing anything structural. It carries what was
tried, what the numbers said, and what was decided — including the things that
turned out to be wrong.

## Two invariants. Do not break either.

**The Excel comparison must stay exact.** `python validation/compare.py` reproduces
13,150 cells across three scenarios. A frozen copy of the port-time assumptions
lives in `validation/port_reference/` and must keep reproducing the workbook, so
every new behaviour is gated — `if getattr(a, "some_mode", "old") == "new"` — and
the old path survives. This has caught real mistakes; when it fails, the check is
working.

**Structural changes go on a branch with a MODEL_LOG entry.** Hypothesis, what the
three scenarios produced, adopt or park. A change without that record is a change
nobody can argue with later.

## Running it

    python -m pytest tests/ -q                    # 56 tests
    python validation/compare.py                  # must print PASS
    python -m export.build_all                    # workbook + explorer + CSVs
    python analysis/five_properties.py --sensitivity

## Where things are

| | |
|---|---|
| `assumptions/base.yaml` | every parameter, heavily commented — the layer a non-coder edits |
| `assumptions/{optimistic,stress}.yaml` | deltas only; a diff IS the scenario |
| `engine/` | one module per workbook sheet, plus `giving`, `pricing`, `funding_mix`, `tontine_runoff`, `efficiency` |
| `analysis/five_properties.py` | the model at five houses, readable line by line |
| `MODEL_LOG.md` | decisions, with the reasoning and the reversals |
| `docs/` | the reviewer note, HTML and Markdown |

## House rules, learned the hard way

**Say when a number is judgement.** Several parameters look authoritative and are
guesses — retrofit cost, founding capital, corporate cost, the funding-mix
weights. Each says so in `base.yaml`. Keep that up; a figure without provenance
gets quoted as a finding within a week.

**Never tune an assumption to rescue a result.** When making giving honest broke
the headline, the credibility ramp was NOT softened to bring it back. Fitting the
input to the desired output is the failure mode this whole project has been
correcting.

**Check a favourable result harder than an unfavourable one.** Most of the real
errors found here were things that looked good: a validation that passed too
easily, a funding mix reported as a finding when it was an artefact, a coupon
frontier that had gone stale by 150bp.

**Watch for numbers that are wrong at both ends.** A flat corporate cost was
simultaneously far too small at 185 homes and 58% of gross rent at five. Anything
that does not scale with the portfolio deserves suspicion.

**Real terms, unless there is a reason.** Fifty years of compounding makes nominal
figures flatter the later years and hide the early ones, which is where the risk is.

## The assumptions that actually move the answer

Ranked by what testing showed, not by how much attention they get:

1. **What stock is bought** — a 3-bed terrace and a 3-bed semi let for the same
   rent and the semi costs £55,000 more. Wider spread than any financing lever.
2. **Retrofit cost** — at £25,000 Stress breaks; at £35,000 the coupon ceiling
   falls below what an investor needs.
3. **Giving** — the old flat assumption was worth £5m over fifty years and was
   carrying the entire model.
4. **Corporate cost** — needs a proper build-up by function against portfolio size.

Voids, gearing and the coupon rate matter far less than they look like they should.
