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

## The coupon was charging inflation twice
**Branch:** `structure/property-gifts` (folded in) · **Date:** 2026-08-07 · **Decision:** adopt · **Impact: the largest in the project so far**

**How it surfaced.** Decomposing why Stress fails so badly. CPI alone accounts
for nearly all of it — Base plus CPI 4.5% gives 0.73x, identical to full
Stress. Letting rent track CPI barely helped (0.73 → 0.77), which did not fit
an instrument supposedly hedged against inflation on both sides. That
mismatch was the thread worth pulling.

**The error.** The Tontine principal is uplifted by CPI every year, and **no
principal is ever repaid** — so the investor's entire return is the coupon,
paid on a base that already grows with inflation. Their inflation protection is
delivered by the indexation.

The workbook then set the coupon rate to **CPI + spread** and applied it to
that already-indexed principal. The investor receives CPI twice.

| | Real return to the investor |
|---|---|
| Design intent | **2.50%** |
| Indicative actuarial model (3.25% flat on indexed principal) | **2.50%** ✓ |
| Workbook / our port (CPI + 3.25% on indexed principal) | **5.00%** ✗ |

The actuarial model is unambiguous in its own arithmetic: charge principal
£50m real, charge income £1.625m real, exactly 3.25%. Its note reading
"CPI + 3.25% on the inflating principal" describes the investor's *total*
nominal return — CPI via the principal, 3.25% via the coupon — not the rate to
apply.

At CPI 2.5% the workbook overstates SLC's interest cost by **95%**.

**What changed.** `pf_coupon_basis`: `real` (coupon = spread) or `nominal`
(coupon = CPI + spread, the workbook). Base is now `real`; the port reference
keeps `nominal`, so the Excel comparison still passes all 13,150 cells.

**Result — every scenario becomes viable.**

| | Min cash cover | Years <1.25x | Self-financing from | 50-yr interest | Net assets |
|---|---|---|---|---|---|
| Base, workbook | 1.04 | 10 | year 19 | £12.8m | £140m |
| **Base, corrected** | **1.97** | **0** | **year 6** | **£6.8m** | **£170m** |
| Stress, workbook | 0.73 | 27 | year 36 | £19.7m | £102m |
| **Stress, corrected** | **1.74** | **0** | **year 11** | **£8.3m** | **£170m** |
| Optimistic, corrected | 2.91 | 0 | year 3 | £7.4m | £502m |

**Stress now clears the 1.25x covenant in every year**, which no amount of
parameter tuning had achieved. The apparent precariousness of the whole plan
was substantially an artefact of this one formula.

One reading note: minimum *rent-only* cover looks worse after the fix
(−2.62 → −4.63). That is an artefact of a ratio with a much smaller
denominator in the earliest years, when interest is tiny and the numerator is
negative. The meaningful measure is the first self-financing year, which
improves from 19 to 6.

**Decision: adopt**, with a caveat that this should be confirmed with whoever
built V2.1 before it drives external figures. It is a material change to the
economics and it contradicts the spreadsheet. The evidence — the actuarial
model's own arithmetic, and the design-intent check on the investor's real
return — is strong, but "the model says so" is not the same as the designer
confirming intent.

---

## Operating efficiency from scale
**Branch:** `structure/property-gifts` (folded in) · **Date:** 2026-08-07 · **Decision:** adopt

**Hypothesis.** Per-property running costs were flat forever — £150 admin and
£700 maintenance per house, whether the estate holds five houses or two
hundred. That understates a real effect: materials bought in bulk, gas safety
checks batched across a round rather than booked singly, and enough contracted
volume to negotiate on price.

**What changed.** `engine/efficiency.py` applies a **learning curve** — unit
cost falls by a fixed proportion for every *doubling* of the portfolio, floored.
Base: 8% per doubling, floor 65%. Optimistic 12% and floor 55%; Stress switches
the mechanism off entirely, on the view that the savings simply never
materialise.

Applies to `admin_per_prop` and `maint_per_prop`. Deliberately **not** to
`sinking_per_prop`: that is a provision against future capital works, not a
running cost, and buying scaffolding more cheaply does not mean the roof needs
replacing less often. Scaling it would quietly under-provision a growing
portfolio, so a test pins it.

**Result.**

| Houses | Cost factor | Saving | Admin/prop | Maint/prop |
|---|---|---|---|---|
| 1 | 1.000 | — | £150 | £700 |
| 10 | 0.758 | 24% | £114 | £531 |
| 25 | 0.679 | 32% | £102 | £475 |
| 50+ | 0.650 | 35% | £98 | £455 |

Base: 50-year admin and maintenance falls **£5.41m → £3.53m**, cash cover
1.97 → 2.02, net assets £170m → £172m.

**Two things worth stating plainly.**

*The floor binds at about fifty houses.* So this parameterisation says most of
the saving is banked by house 50 and the two-hundredth buys nothing further.
That is a claim about procurement leverage, and it is the parameter to argue
with — not the curve.

*The effect is second-order.* £1.9m saved over fifty years against £6.8m of
interest. Worth having, and worth not overselling: it does not change viability
the way the coupon correction did.

**What is not modelled: where the saving goes.** Here it improves the surplus
and stays with the Commons. The stated intent is to share it between tenants
and investors and most likely to consume it through retrofitting — a rent
reduction and capex respectively. Neither is represented, so these figures are
the size of the prize, not the gain to the balance sheet. Modelling the
distribution is the obvious follow-on.

---

## Investor rate raised to CPI + 4.25%, and the analysis around it
**Branch:** `pricing/investor-rate-4.25` · **Date:** 2026-08-20 · **Decision:** adopt, with an open question

**Why.** The principal is never repaid, so the coupon is the investor's entire
return. At 2.5% an investor recovers ~55% of capital over their expected life
and breaks even at age 104 — i.e. never, under any outcome. That is
philanthropy with a yield, not a bet on longevity, and it will not raise money
from anyone comparing it with an annuity.

**The frontier.** Ceiling = highest coupon with zero covenant breaches:

| | Rate |
|---|---|
| Optimistic | 6.00% |
| Base | 4.28% |
| **Stress (binding)** | **3.77%** |
| Investor break-even by median survival (age 87) | **4.58%** |

**No rate clears every scenario and repays the investor — the gap is 81bp.** An
earlier note in this log said 30bp; that was computed on Base alone and was
wrong. Stress binds, and all three should have been checked before quoting a
ceiling.

4.25% is adopted as a deliberate judgement: Base and Optimistic stay clean,
Stress breaches in 10 of 50 years, on the view that a *severe* stress (15%
voids, CPI 4.5%, housing crash, halved take-up, no gifts ever) may breach a
self-imposed covenant. If the covenant must hold in all worlds, the rate falls
to 3.75% and the investor recovers ~82%. **This is the reviewer's decision, not
the model's**, and it is stated as such on the workbook's "For Review" sheet.

### Findings from the same session, none yet built

**Evergreen vs closed is a mission question, not a financing one.** With
portfolio-wide charging the free share of the portfolio is pinned at ~30%
forever — old debt runs off, headroom reappears, and it is re-lent against the
same houses. A closed 10-year raise reaches 100% unencumbered by year 43.

**Ring-fenced tranches beat both.** If each tranche's charge sits only on the
houses that tranche bought, total debt stabilises while the portfolio grows, so
the free share climbs indefinitely — 70% by year 40, 92% by year 100, with
specific houses fully free from year 42. The tranche interval (5 or 10 years)
barely matters; the ring-fencing is the whole effect. **Not implemented:** the
LTV test would become per-tranche, plus a release-ordering layer.

**Property attribution, solved.** Pool survivorship across all tranches — a
single £5m tranche sees ~88% year-to-year volatility in deaths, pooled across
eight it falls to ~31% — but attribute property release oldest-tranche-first.
Pooling changes only the *variance* of run-off, never its expectation, so the
release schedule is unaffected and no tranche is penalised for its own luck.
Liability-side pooling and asset-side attribution are separate decisions.

**Borrowing against freed assets is a non-question.** Nothing is fully
unencumbered until year 42, so the acceleration it would buy is unavailable in
the years growth is actually constrained. The ethical position costs nothing.

**The Tontine is the cheapest capital, at every plausible price.** PV of what
SLC gives up per £100 raised, at a 3.25% real discount rate: Tontine 65,
community shares 82 (held) to 99 (repaid over 25y), RCO 114. It stays cheapest
up to 5.38%, above the whole range in play — because the principal is never
repaid and the obligation dies with the investor. Cheapness is bought with the
charge: shares and RCOs cost more precisely because they take no security.

**But they are segments, not substitutes.** Tontine suits pensioners, shares
suit believers, RCOs suit investors wanting inflation-indexed, asset-denominated
compounding. They draw on three different resources — property value, balance
sheet size, goodwill — and each hits a different limit. On Base the actual mix
is 57% shares, 27% gifts, **16% Tontine**: the instrument this project has spent
most effort on supplies the least capital.

**The community share cap binds in 17 of 50 years** at 20% of total capital,
while the Tontine uses only 13% of its own cap. The most enthusiastic segment is
being turned away by a structural limit. Given director discretion over
withdrawals, that cap is the cheapest available unlock and should be tested.

### The Pollen Community Wealth Fund proposal

A member's fund-side proposal, reviewed. It is the investor vehicle rather than
a competing SLC model, so most of it sits above this one. Three findings:

- Its headline mortality figure ("19% male / 15% female at 75") is decade-
  *cumulative* mortality from 65 to 75, used as if it were an annual rate. The
  annual rate at 75 is 2.5%; 19% is reached around age 95. The 12.5% payout it
  justifies is nonetheless roughly defensible — it needs a 2.43% real return —
  so the reasoning needs replacing, not the number.
- Its payout is **not fundable from an SLC charge as designed**: £155 out per
  £100 in against £71 the charge generates, and the charge is never repaid so
  cannot be realised to cover the gap. SLC can only ever be a minority of such
  a fund's assets.
- Its higher promise raises technical provisions ~2.5x, so the £50m NDF
  threshold arrives at £45m raised rather than £113m — halving the runway before
  full insurance regulation.

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

### Community share withdrawals are unrealistically smooth

The mechanic is: withdrawals in year t = a fixed rate applied to the closing
balance from `cs_withdrawal_years` ago. Because issuance is smooth, withdrawals
come out as a smooth lagged echo of it — a clean curve where reality would be
lumpy.

Real withdrawals are driven by individual circumstances and are likely to
*cluster*: after a life event, when confidence dips, or when a dividend is cut.
The clustering is the part that matters, because withdrawals concentrating in a
bad year is precisely when the Commons can least afford them, and the current
mechanic cannot express that at all.

Two candidate structural changes, neither yet attempted:

- **Behavioural feedback.** Let the withdrawal rate respond to something the
  model already knows — a dividend paid short of the declared rate is the
  obvious trigger. Keeps the model deterministic and reproducible, which the
  validation depends on.
- **Explicit stress event.** A one-off withdrawal spike in a nominated year,
  parameterised like the HPI shock, to size the liquidity risk directly.

The second is probably more useful first: it answers "what if a fifth of
withdrawable shares were called in the year after a bad result?" without
pretending to predict when.

Note the restriction period itself was wrong (5 years in the workbook, 2 in the
actual offer terms) and is corrected in `base.yaml`.

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
