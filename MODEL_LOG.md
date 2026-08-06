# Model log

A decision log for **structural** experiments — changes to how the model
*works*, not what it's fed. Parameter changes belong in `assumptions/`; they
don't need an entry here.

Each entry: hypothesis, what changed, result, decision, date.

Rejected-but-interesting branches get **tagged and left**, not deleted. A dead
end that was properly measured is worth more than the disk space it costs, and
the tag is how it gets resurrected.

---

## Open questions carried over from the Excel model

These are quirks found while porting `Financial Modelling for SLC V2.1.xlsx`.
All were **reproduced faithfully rather than fixed**, so that the Python model
could be validated number-for-number against the workbook first. Each is a
candidate for a `structure/` branch.

Recorded 2026-08-06.

### 1. Corporation tax is charged on surplus *after* dividends

**What the model does.** `Financial Statements` row 25 computes the tax base as
row 23 + row 24 — surplus before dividends and tax, *plus* dividends (which are
negative). Community share dividends therefore reduce taxable profit.

**Why it's odd.** Dividends are normally paid out of taxed profit, not deducted
before it. For a co-operative or community benefit society this *may* be right
— some distributions to members are deductible — but it is atypical enough to
need a real answer from an accountant.

**Current impact: none.** `ct_exempt_toggle` is 1 in all three scenarios, so
the whole line is zero. It would bite immediately if the exemption were ever
switched off.

**Decision: park.** Confirm the intended CT treatment with an accountant before
changing anything. If it turns out to be wrong, the fix is a one-line change in
`engine/statements.py::tax_and_retained`.

### 2. Years 1–3 acquisitions ignore `logistic_start_yr`

**What the model does.** `Growth Engine` row 26 hard-branches on `year <= 3` to
read `acq_year1/2/3`, then switches to the logistic curve. The curve's own start
is governed separately by `logistic_start_yr`.

**Why it's odd.** The two agree only because `logistic_start_yr` is 4. Set it to
2 and years 2–3 would still silently use the hand-set counts, ignoring the
parameter the user just changed. The parameter would appear to do nothing.

**Decision: park.** Low impact while the default holds, but it's a trap for
whoever next edits that parameter. Candidate fix: drive the hand-set years off
`logistic_start_yr` (`year < logistic_start_yr`) so the two can't drift apart,
and treat `acq_year1/2/3` as a list rather than three scalars.

### 3. The capital call is a warning light, not a mechanism

**What the model does.** `Financial Statements` row 71 reports how far free cash
has fallen below `min_cash_buffer`. Nothing consumes it. When the buffer is
breached the model simply carries on with negative reserves.

**Why it matters.** In Base this flag fires in 13 of 50 years, and minimum free
cash reaches **−£317,425**. The model is projecting a position that, in reality,
would require either an emergency raise, a halt to acquisitions, or insolvency
— and it models none of the three.

**Decision: park, but this is the most substantive of the four.** The obvious
`structure/` experiment: make a breach actually do something — throttle
acquisitions until reserves recover, or trigger a modelled capital call — and
compare portfolio trajectory against `main` under all three scenarios.

### 4. The Base scenario is in covenant breach, and the model says so

**What the model shows.** Base minimum DSCR is **0.97×**, against a 1.20×
covenant and a 1.00× break-even. It breaches in 21 of 50 years. Minimum reserve
cover is **−8.2 months**. 30 of 50 years carry an unfunded acquisition
requirement.

**This is not a porting bug.** The workbook's own Dashboard says so in its
narrative text, and the Python model reproduces every one of these figures
exactly. The model is correctly surfacing a real financial problem in the plan
as currently parameterised.

**Decision: not a model issue — a plan issue.** Recorded here so that nobody
later "fixes the model" to make the red numbers go away. The lever is the
assumptions or the structure, not the arithmetic.

---

## Structural experiments

_None yet. First entry goes below when the first `structure/` branch lands._

<!--
Template:

## <short title>
**Branch:** `structure/<hypothesis>` · **Date:** YYYY-MM-DD · **Decision:** adopt / reject / park

**Hypothesis.** What we thought would happen and why.

**What changed.** The mechanics, precisely — which module, which behaviour.

**Result.** Numbers against `main`, all three scenarios. Headline figures at
minimum: portfolio at Y50, net assets, min DSCR, min reserve cover, years in
breach.

**Decision.** Adopt / reject / park, and the reasoning. If rejected, the tag
that preserves it: `git tag experiment/<name>`.
-->
