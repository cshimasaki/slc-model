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

## Tontine release tracks the liability run-off
**Branch:** `structure/tontine-runoff-release` · **Date:** 2026-08-07 · **Decision:** adopt

**Hypothesis.** The original release rule — a flat 6% of the outstanding
balance from year 25 — is a parametric stand-in, not a mechanism. The
indicative actuarial model (Aug 2026) found the binding constraint is not the
release *start* date but its *completion* date: discharge the charges before
the last annuitant dies and the survivors are left unbacked, which is terminal
insolvency however healthy the fund looked at year 25. A rule that tracks the
actual liability should remove that failure mode by construction.

**What changed.** `engine/tontine_runoff.py` adds a second release rule,
selected by `pf_release_mode`:

```
target outstanding(t) = pf_release_coverage_target x technical provisions(t)
release(t)            = outstanding(t) - target outstanding(t), floored at 0
```

Technical provisions come from `assumptions/tontine_runoff.csv`, exported from
the actuarial model and scaled to the capital this model actually raises.
Because provisions are non-zero exactly while someone is left to be paid, the
last-survivor floor is structural — there is no threshold to mis-set.

`geometric` remains available and remains the default in
`validation/port_reference/`, so the Excel comparison still passes unchanged.
That is deliberate: it keeps port fidelity and the new mechanism independently
verifiable, and it is what makes the two rules comparable at all.

**Result.** `python validation/compare_release_rules.py`, all three scenarios.
Base:

| | geometric | runoff |
|---|---|---|
| Charge outstanding at Y50 | £3,875,804 (38% of peak) | £3,054 (0.0%) |
| Total Tontine interest paid | £18,899,707 | £9,802,003 |
| Properties at Y50 | 56 | 71 |
| Cumulative retained surplus | £14,137,501 | £33,650,098 |
| Net assets at Y50 | £70,724,013 | £97,849,486 |
| Years below 1.20x covenant | 16 | 16 |

Stress: covenant breaches fall from 34 years to 22. Optimistic: net assets
£251.8m → £281.8m.

The mechanism behind the size of the gain is worth stating, because £27m from a
release-rule change looks implausible until traced. The geometric rule leaves
SLC **paying coupon on a charge that should already have been discharged** —
£9.1m of avoidable interest over 50 years. That saving compounds into retained
surplus, and the lower balance frees LTV headroom, which buys 15 more homes,
which adds £22.7m of portfolio value and £7.6m of revaluation reserve.

Minimum DSCR is unchanged in every scenario, as expected: the release is a
non-cash credit and does not touch debt service in the year it happens.

**Decision: adopt**, with `pf_release_mode: runoff` as the live default.
Two caveats recorded rather than buried:

- The curve is **population mortality, not annuitant mortality**. Real
  annuitants live longer, so the liability is understated and these figures are
  a favourable bound. The September dataset replaces one CSV.
- Scaling the curve by total capital raised assumes this model's drawdown has
  the same *shape* as the indicative model's level £5m a year. Ours is
  demand-driven and lumpier. Acceptable for a placeholder; revisit when the
  real basis lands.

---

## Property gifts — capital contributed in kind
**Branch:** `structure/property-gifts` · **Date:** 2026-08-07 · **Decision:** adopt

**Hypothesis.** The model could only represent gifts as *cash*. A house given
outright is structurally different: no purchase price, no debt, no LTV draw,
and it earns rent from the year it arrives. Exploratory runs suggested this was
the single strongest lever in the model — the only route that reached a large
portfolio with **zero covenant breaches** — so it was worth representing
properly rather than proxying with cash.

There is also a strategic reason, which is the reason it was raised: **there is
currently no vehicle for gifting property in Stroud, or in much of the UK.**

**What changed.** A distinct gift channel, parameterised by a start year, a
rate, and a retrofit multiple:

- Gifts bypass the affordability test entirely. Nobody's funding capacity
  applies to a house someone gives you, and no growth curve produces one.
- The house is recognised as **income at market value** in the year it arrives,
  and stripped straight back out of the cash-flow statement — the same
  treatment the Tontine indexation uplift gets. Without the income recognition
  the balance sheet stops balancing; without the cash-flow reversal the model
  would think a house was money.
- Fractional rates accumulate: 0.5 a year means one house every other year, not
  half a house annually. Portfolio counts stay whole.
- Gifted stock carries a higher retrofit cost (3x standard), being older and
  less chosen than a property bought on the market.

**Conservative by construction.** Gifts are treated as *earned by demonstrated
community benefit*, not assumed — hence a start year, not just a rate. Base
assumes nothing at all for fourteen years. Stress assumes a gift never arrives,
because the stress case is precisely the world where the case is never made
compellingly enough for anyone to hand over a house.

**Result.**

| | Base | Base + gifts | Optimistic | Opt + gifts | Stress |
|---|---|---|---|---|---|
| Gifts received | 0 | 18 (from yr 16) | 0 | 41 (from yr 10) | 0 |
| Properties Y50 | 71 | **100** | 151 | **235** | 36 |
| Years below 1.20x | 16 | **9** | 0 | 0 | 22 |
| Net assets Y50 | £98m | **£143m** | £282m | **£465m** | £104m |

Base covenant breaches nearly halve and net assets rise 46%, on an assumption
of one house every other year starting in year 16. Tontine drawdown is
unchanged in every scenario: gifts do not displace borrowing, they add to it.

**A caveat that emerged from a failing test.** Gifts are not free. A larger
portfolio carries more admin and sinking-fund cost, and gifted houses need
retrofitting, so purchases in individual later years can *fall* relative to a
no-gift run. The first gift year isolates the question cleanly and confirms no
displacement there; beyond it, only the outcome is asserted. The test was
written asserting the wrong thing first, and the model was right.

**Decision: adopt**, with the conservative Base parameters above.

---

## Housing Commons and RCOs — deliberately out of scope
**Date:** 2026-08-07 · **Decision:** park, as a separate model

Recorded so that the absence is legible as a decision rather than an oversight.

Rent Credit Obligations are the intended long-run capital vehicle: investors buy
RCOs at a discount, the capital buys property **debt-free**, and tenants then
buy RCOs from investors to pay rent in lieu of cash, always below market rent.
The investor's return is the discount margin. RCOs are denominated in **square
metres**, so they are inflation-proof by construction rather than by indexation,
and they retire on redemption over roughly 25 years — as they retire, rent falls
for everyone until it reaches maintenance cost.

**This does not belong in this model.** In the RCO vehicle each property is
designed to net *zero* surplus (16.6% operations, 83.4% redeemed to investors).
There is no debt, no coupon, no DSCR and no LTV. This model's entire spine is
borrow-against-portfolio, service-the-debt, watch-the-covenant. Grafting one
onto the other would not extend either; it would corrupt both.

Two vehicles, two models, one shared reality. The intended path is a gradual
transition from Tontine toward community shares and RCOs as trust and evidence
accumulate — see the transition note below, which remains the right place for
the *interface* between them.

Source: `Housing Commons Draft Prospectus.pdf`.

---

## Tontine release is mortality-driven, not scheduled — supersedes the run-off rule
**Branch:** `structure/property-gifts` (folded in) · **Date:** 2026-08-07 · **Decision:** adopt

**What was wrong.** Both earlier release rules were built on a misreading of
the instrument. Spotted from a chart: debt outstanding fell off a cliff at
year 25. It was not mortality — lives fall 5.2% that year, entirely gradually.

Checking the mechanic against how the Tontine actually works surfaced three
divergences, of which the first two were material:

1. **Interest did not stop when investors died.** At year 21, 76.5% of
   investors were alive but the model charged interest on a balance that had
   *grown* to £9.46m — £544k that year against roughly £416k owed. It paid
   coupon on dead investors' capital until the release phase opened.
2. **The charge did not track survivorship.** It grew at CPI on the full
   amount regardless of who was alive.
3. **Release was modelled as a scheduled phase.** It is not. There is no
   release phase, no coverage ratio, no glide and no redemption date.

The root error was mine: I inferred the mechanic from the actuarial model's
*solvency* framing rather than asking how the instrument works. That produced a
coverage-target rule solving a problem — "how much security should back the
remaining liability" — that this structure does not have, because the charge is
per-investor and dies with the investor.

**The instrument as designed.** Each drawdown is a cohort of investors entering
at 65. SLC pays a coupon while they live. On death the coupon stops, the charge
is extinguished, and **no principal is repaid**. Mortality is the only
mechanism. Two policy levers sit on top:

- `pf_lockup_years` (5) — a minimum term before any charge can be released.
- `pf_mortality_gain_to_commons` (1.0) — what happens to a dead investor's
  capital.

`pf_release_start_yr`, `pf_release_coverage_target` and
`pf_release_glide_years` are gone. `geometric` is retained solely for Excel
fidelity.

**The open question, quantified.** The mortality-gain split is undecided, and
it is the most consequential parameter in the Tontine. It decides whether the
survivorship benefit accrues to the Commons or lifts investor yield — which
may in turn accelerate further investment.

| To Commons | To investors | Y50 balance | 50-yr interest | Net assets |
|---|---|---|---|---|
| 100% | 0% | £0.11m | £12.8m | £141m |
| 75% | 25% | £5.18m | £17.5m | £125m |
| 50% | 50% | £9.79m | £21.3m | £109m |
| 0% | 100% | £19.4m | £30.3m | £80m |

Every 25 points conceded to investors costs SLC roughly £15m of net assets and
£4.5m of interest. At 0% the charge never runs off at all — it only indexes
upward, and SLC owes as much at year 50 as it ever did.

**Decision: adopt**, defaulting to 100% to the Commons, which is the mechanic
as described. The split stays exposed as a parameter because it is a live
commercial decision, not a modelling one.

**Answered while doing this:** entry age stays a single blended 65; a spouse or
joint annuitant is out of scope for now; the lock-up is a genuine minimum term
rather than an observation about when first deaths occur.

---

## Three interest cover tests replace one DSCR
**Branch:** `structure/property-gifts` (folded in) · **Date:** 2026-08-07 · **Decision:** adopt

**Hypothesis.** The single 1.20x covenant was self-imposed and, on inspection,
measuring the wrong thing in two ways.

**What the diagnosis found.**

*It is not a DSCR.* Total principal repaid across 50 years is **£0** — the
Tontine never amortises and the mortgage is undrawn. It is an interest cover
ratio, and calling it DSCR invites comparison with geared commercial borrowers
who carry refinancing and maturity risk that SLC does not.

*It counts a house as income.* A donated property is recognised at market
value, which is right for the accounts and wrong for a covenant. At year 16 a
gift lifts cover from 1.24x to 2.29x; at year 20, 1.54x to 2.75x. Interest
cannot be paid with a house.

*And the real exposure was invisible.* Stripping gifts out entirely:

| Measure | Worst |
|---|---|
| All income (the old metric) | 1.05 |
| Excluding donated property | 1.05 |
| **Rent only, no gifts** | **0.38** |

**Rent alone does not cover interest until year 19.** For eighteen years the
portfolio depends on non-contractual giving to service its debt. No covenant
number fixes that; it was simply not being measured.

**What changed.** Two new series — `cash_interest_cover` and
`rent_only_cover` — computed in `capital_debt.coverage()`, carried through the
JSON bundle, the explorer and the Excel workbook. Neither appears in `ROW_MAP`:
the workbook never had them, so the Excel comparison cannot and should not
check them.

Thresholds moved out of code into an `assumptions/base.yaml` `covenants`
section, because they are policy:

- `cov_cash_cover_min: 1.25`
- `cov_rent_only_min: 1.00`, `cov_rent_only_by_year: 20`
- `cov_legacy_dscr_min: 1.20` (retained for continuity)

The third test is the first measured under CPI +2pts rather than a separate
ratio, because the coupon is CPI-linked and reprices immediately while rents
review annually. Stress already is CPI +2, and **fails it at 0.73**.

**Where the covenant level came from.** The structural case is for the lower
half of the 1.10-1.50 range UK housing associations typically covenant: no
maturity, no amortisation, no refinancing risk, and the liability extinguishes
on death. What argues it back up is the gift dependency, single-locality
concentration, and deliberately sub-market rents leaving little room to raise
out of trouble. 1.25x is the balance of those.

**Decision: adopt.** The headline number matters less than the second test,
which is failing today for eighteen years and is the one to manage against.

---

## Planned — not yet started

Recorded 2026-08-07 from the design discussion, so the sequence is not lost.

### The capital-mix transition (highest priority)

Tontine is the booster rocket: it buys escape velocity, and should decline as a
share of funding once the balance sheet and the evidence base can carry
**community shares** (widely understood) and **Rent Credit Obligations**
(novel). The model currently has no notion of this shift at all — each capital
layer has fixed parameters and no trajectory.

Needs: capital-layer weights that vary over time, with Base / Optimistic /
Stress differing in *how fast* the transition happens, not just in levels. The
LTV limit becomes part of that trajectory rather than a constant — high while
Tontine-led, falling as equity-like capital takes over.

### Rent Credit Obligations

An owner of an unencumbered property transfers it to the commons, retains
lifetime occupancy with maintenance provided, and receives an RCO that passes
to their children on death.

This is not a variant of an existing layer. It is capital contributed **in
kind**, with a retained life interest, and an instrument that is inheritable
and denominated in rent. Modelling it needs decisions this log cannot make:
how the RCO is valued at issue, whether the property yields rent during the
donor's lifetime, whether the RCO is a liability or equity, and how the
inherited credit is extinguished. Questions raised with the design team
2026-08-07.

### The leverage multiplier as a published figure

"£20k of community shares releases £80k of pension capital" is a fundraising
message that falls straight out of the LTV relationship. Cheap to compute and
publish in the explorer — for each £1 of community share, how much total
capital is deployed. Worth doing once the transition work above settles what
LTV is doing over time.

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
