# Model log

## Where this stands — 20 August 2026

Read this first if you are picking the model up. Everything below is either
unresolved or in flight; the sections after it are the decision history.

### The model does not currently clear its covenants, and that is deliberate

`base.yaml` carries `gift_mode: curve`. Making philanthropy something the
organisation has to earn — scaled by homes actually delivered, drawn randomly
rather than smoothed — removed about £5m of assumed giving over fifty years, and
the full model no longer stands up without it:

    scenario     homes   giving/50yr   senior cover   breach years
    base            49         0.57m         -11.79             23
    optimistic     221         1.59m          -3.38             12
    stress           1         0.16m           ----             48

Two readings, and the choice has NOT been made:

* Growth to 185 homes was never fundable on philanthropy and needs grant or
  foundation capital — which is what the foundation deck argues, so this
  strengthens that case rather than undermining it.
* The credibility ramp (`gift_ramp_homes: 25`) is too steep and understates what
  a young organisation attracts.

The ramp has not been tuned to rescue the answer. Deciding this is the first
substantive job, and it should be decided on evidence about what comparable
organisations actually receive — see below.

### The five-house case, which does stand up

Built at a reviewer's request: the fifty-year model is too complex to see the
drivers, and the scale of the later years hides the risk in the early ones. Both
fair. `analysis/five_properties.py` runs the same engine on five houses.

    spent years 1-3   £1,408,634
    raised            £1,242,006   (shares 50% of it)
    gap               £  166,628
    lowest cash       £ -147,160 in year 3, positive from year 15
    rent covers interest from year 4; five deficit years in fifty
    cash at year 50   £1,016,865 real, five homes, no debt left

**£166,628 of ramp capital buys five permanently affordable homes that are
self-supporting from year four and debt-free by year fifty.** That is a more
fundable proposition, and a more checkable one, than any fifty-year projection.

Whether the gap is grant, bridge, or a larger founding raise is undecided, and
the model treats it as raw negative cash because no bridging instrument exists in
it. Those have very different consequences.

### Numbers that are judgement and want replacing

Each says so where it lives; listed together because each moves the answer.

* **Retrofit** £12,000 base / £18,000 stress. An external review put Cotswold
  solid-wall retrofit at £25,000–£35,000. Testing that range: at £25,000 Stress
  breaks; at £35,000 the coupon ceiling falls to 3.19%, below the 4.58% an
  investor needs. **This is the single assumption most able to reopen the
  pricing gap.** A real quote on a representative terrace is the highest-value
  piece of evidence anyone could bring.
* **Corporate cost.** A flat figure from the workbook, wrong at both ends: £237
  per house at 185 homes, and 58% of gross rent at five. Housing Commons manages
  and maintains the homes out of the 16.67% of rent, so this line is only
  accounting, financial management, governance, the FCA return, insurance and
  fund oversight — it is NOT housing management. Wants a build-up by function
  against portfolio size. `--corporate` steers it meanwhile.
* **Founding capital** £25,000, reduced from £150,000 when it became clear the
  old figure was doing the share offer's job.
* **Giving levels** — `gift_mature_annual` and `beq_mean`. See below.

### Evidence nobody has gathered yet

A search failed to produce per-organisation philanthropic income for a small
housing-owning CLT. What it did establish is where to look:

* Most CLTs are Community Benefit Societies on the **FCA Mutuals Public
  Register**, not Companies House — Bristol CLT is 31423R. Only CLTs structured
  as companies (CLG/CIC) file at Companies House; only registered charities give
  a donations breakdown, at the Charity Commission.
* National CLT Network: £459,036 total income to March 2025, £242,458 of it
  grant funding — but that is the national body, not a landlord.
* Homes England allocated £137m across 175 community-led schemes in 2021–26,
  roughly £783,000 a scheme. Development grant, not philanthropy.
* Where charities publish it, legacies commonly dominate voluntary income.

Getting a real figure means pulling individual accounts one organisation at a
time. Until somebody does, the giving defaults are shape-without-substance.

### Outputs that are now overstated

The published foundation deck and the reviewer note in `docs/` both quote
flat-gift figures — 185 homes, all scenarios clearing. Neither is true under the
current assumptions. Both need revisiting before they go anywhere.

`dist/` holds two stale base workbooks that were locked open in Excel and could
not be overwritten.

### Branches

Everything since the port sits on `structure/real-costs-and-indexation`. Four
earlier branches are also unmerged: `model-update-august-2026`,
`pricing/investor-rate-4.25`, `structure/funding-mix`, `structure/property-gifts`.
`main` still carries the old configuration, so anyone cloning the repo gets a
model several months behind. Merging is overdue.

### Designed but not built

* **Gear to income, not to value.** `pf_ltv_limit` is a value test while the
  covenant is a rent test; when house prices outrun rents, a constant-LTV policy
  drives cover toward zero mechanically. Replacing it with `charge ≤ net rent ÷
  (target cover × coupon)` makes cover constant by construction and is what an
  open-ended investment phase would need. Derived, never implemented.
* **Withdrawal clustering.** Modelled as a smooth 2% a year, which cannot
  express withdrawals concentrating in a bad year — precisely when they hurt.
  An explicit stress spike, parameterised like the HPI shock, is the cheaper of
  the two candidate approaches and answers the question directly.
* **Tontine syndication.** An external review proposed a multi-commons master
  vehicle issuing charges across several regional commons with local
  ring-fencing, to get past the ~£20m below which a regulated annuity fund is
  uneconomic. Note it heads toward the £50m technical-provisions NDF threshold
  under PS2/24, where the regulatory character changes.
* **Longevity sensitivity as a standing script.** The September actuarial
  dataset replaces `assumptions/tontine_runoff.csv`. At current Tontine scale
  (~£3.5m) shifting median survival from 87 to 92 costs two basis points of
  coupon ceiling — immaterial. At the scale syndication proposes it adds 52% to
  the outstanding charge. The exposure arrives with the scale.

---

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

## The funding mix becomes a variable — and turns out to be an output, not an input

**Branch:** `structure/funding-mix` · **Date:** 2026-08-20 · **Decision:** adopt the
mechanism, park the target weights

**Hypothesis.** The 17% / 56% / 27% split between Tontine, community shares and
gifts that the model had been producing was not a finding. It was an artefact of
three unrelated V2.1 parameters — a flat annual share issuance, a fixed gift
baseline, and a Tontine that only ever drew the residual — colliding. Nobody
chose it. So the mix should be something the model is *told*, not something it
happens to produce.

The intended shape, from the design discussion: Tontine around 80% at the start
because that is where large sums of pensioner capital actually sit, community
shares around 15%, the remaining 5% split between gifts and RCOs. As later
cohorts arrive the weight shifts toward shares and RCOs, but never away from the
Tontine entirely. The Tontine takes up the slack, and viability is the ceiling.

These weights are judgement, not evidence, and the assumptions file says so in
those words.

**What changed.**

`engine/funding_mix.py` (new) holds `weights_for_year()`: a linear glide from the
start weights to the end weights over `mix_transition_years`, defaulting to
80/15/5 gliding to 30/50/20 across 30 years.

`engine/capital_debt.py::community_shares()` gains a `share_of_need` mode. Shares
are now issued as their target proportion of what this year's planned purchases
will cost, rather than a flat inflated amount. The old `fixed` behaviour is kept
and selectable, because it is what the workbook did and the validation harness
still has to reproduce it.

Only shares are targeted. Gifts arrive on their own terms and the Tontine draws
whatever acquisitions still need — which is precisely "the Tontine takes up the
slack" expressed as code.

This forced a reordering of the year loop in `engine/model.py`. Share issuance
now has to know the unit acquisition cost, which used to be computed after it.
`growth.costs_and_capacity` is split into `unit_cost` (row 23, depends only on
price indices) and `capacity` (rows 27, 24, 25, depends on current-year cash), so
the cost can be established early and the capacity test still run late. No
behaviour changes in `fixed` mode; validation confirms it.

**Result.** The mechanism works. Within the investment phase the realised Tontine
share tracks its target closely — 67% to 74% in years 2 to 10 against a target
falling from 78% to 65%.

Across the full 50 years it does not, and the reason is structural rather than a
calibration problem. Under Base the cumulative split is Tontine 11%, shares 72%,
gifts 17%. The Tontine stops drawing at year 10 when the investment phase closes,
while shares keep issuing for another forty. The intended glide from 80% down to
30% over thirty years cannot happen inside a ten-year raise. The target weights
and the closed-end structure are describing different instruments.

So the obvious question: extend the phase. Under Base, lengthening it does lift
the Tontine's share, but every step costs cover.

| phase | cap | Tontine | houses | net assets | min cover | years in breach |
|------:|----:|--------:|-------:|-----------:|----------:|----------------:|
| 10 | £50m | 11% | 123 | £160m | 1.24 | 1 |
| 20 | £50m | 28% | 192 | £260m | 1.06 | 14 |
| 30 | £50m | 44% | 204 | £302m | 1.06 | 17 |
| 30 | £100m | 53% | 205 | £307m | 1.06 | 19 |
| 50 | £100m | 61% | 207 | £299m | 1.06 | 19 |

Two things to read off it. The Tontine share plateaus around 61% and will not
reach 80% at any phase length, because gifts and shares keep arriving and the
Tontine only ever takes the remainder. And raising the £50m cap buys very little
past a thirty-year phase — at £100m the fund still only draws £79m, because LTV
headroom binds before the cap does.

Under Stress the trade is much worse:

| phase | cap | Tontine | houses | net assets | min cover | years in breach |
|------:|----:|--------:|-------:|-----------:|----------:|----------------:|
| 10 | £50m | 8% | 56 | £149m | 1.14 | 7 |
| 20 | £50m | 21% | 125 | £319m | 0.76 | 26 |
| 30 | £100m | 40% | 186 | £442m | 0.72 | 36 |
| 50 | £100m | 45% | 193 | £441m | 0.72 | 38 |

Stress goes from seven breach years to twenty-six on the first step. Minimum
cover falls to 0.76 — below one, meaning rent does not meet interest at all in
the worst year. The portfolio more than doubles and net assets look excellent,
which is exactly the trap: the balance sheet improves while the ability to pay
the annuity fails. Since the annuity is the promise that has to be kept, the
balance sheet is not the test.

Taking "viability is the ceiling" literally, the ceiling sits somewhere between a
ten and twenty-year investment phase. Base tolerates twenty; Stress does not.

**Decision.** Adopt the mechanism. `base.yaml` keeps `pf_invest_phase_yrs: 10`
unchanged, so this branch does not move the headline numbers — the mix targets
are declared and the machinery honours them, but the closed-end structure still
governs what actually gets raised.

The target weights are parked rather than rejected. They describe an evergreen or
tranched Tontine, and that is a structural decision with its own regulatory
consequences (the NDF threshold work above), not a parameter change. This branch
establishes that the mix is now a lever we can pull; it also establishes that
pulling it is not free.

**Also fixed here.** Gifted properties were bypassing the growth ceiling.
Purchases are capped at `logistic_ceiling` via the growth curve, but gifts were
added on top with no test, so Optimistic reached 252 houses against a ceiling of
250. The ceiling is the carrying capacity of the acquisition process — nobody
declines a donated house because a growth parameter says the portfolio is full —
so the fix is in the test, which now checks purchases against the ceiling and
attributes any excess to gifts. Latent since the property-gifts work; only
surfaced because the new mix grows Optimistic fast enough to reach its ceiling.

---

## Second wave, August 2026 — real costs, real stock, and what the covenant is for

**Branch:** `structure/real-costs-and-indexation` · **Date:** 2026-08-20 · **Decision:** adopt the mechanics, hold the parameters open

Six changes, each replacing something the model had asserted with something it
can now show. Grouped here because they interact and the order matters.

**Costs became what they are, not what a percentage said.** The fund's 0.50%
operating margin became a staffed cost -- part-time and pro-rata, ramping with
cumulative raise -- and moved out of the coupon into opex, where it reduces the
surplus visibly. A time-based ramp was tried first and was obviously wrong on the
first run: under Stress it put a full salary on a fund that never grew, at 47% of
all rental income for fifteen houses. Separately, `lc_share` (flat 80%) became
two months of rent falling with scale, and `admin_per_prop` / `maint_per_prop`
went to zero because that same 16.67% already covered them -- roughly GBP 850 per
house per year of phantom cost.

**Indexation became a choice.** `pf_index_basis: rent | cpi | hpi`, defaulting to
rent. Under Stress at 70% LTV: rent gives 9 breaches and rent-only cover 0.89,
CPI 9 and 0.79, HPI 13 and 0.72. The hypothesis that a CPI/rent divergence was
the dominant failure mode was WRONG -- correcting the basis moved breaches from
13 to 11, not to zero. The real cause was marginal cover on a debt-funded house,
which is a ratio, not an indexation artefact.

**Community shares became what CCBSA 2014 says they are.** An advertised rate is
a ceiling paid at board discretion, not a promise. Cover splits into senior (can
rent pay the annuity?) and all-in (can it also pay the share offer?), and share
interest is subordinated to the reserve as well as to the annuity. At 40% of
funding need and a 5% advertised rate, Stress holds senior cover at 1.46 with
zero breaches while the offer under-delivers in 15 of 50 years. Shareholders
wait; annuitants do not. An intermediate version treated share interest as a hard
charge and concluded Stress failed -- that was wrong about the instrument.

**Stock became a decision.** The single average house hid the largest lever in
the model. Same finances, three acquisition policies, Base: all 2-bed flats gives
203 houses and senior cover 3.65; all 3-bed terraces 188 and 2.22; all 3-bed
semis 160 and 1.90. A 3-bed terrace and a 3-bed semi let for the same GBP 1,176
and the semi costs GBP 55,000 more. That spread is wider than moving LTV from 70%
to 30%.

**Macro moved to published figures.** CPI 2.9%, rent 3.7%, house prices 2.0% (ONS,
mid-2026). The workbook had rent = CPI and houses = CPI + 1%; the second is wrong
in sign. Stress deliberately keeps the old relationship, because that gap is its
mechanism.

**Two errors worth recording so they are not repeated.** Dividing Stroud average
rent by Stroud average house price gives 3.57% and suggests the model is
unfinanceable -- but those are different populations, and the sale average
includes GBP 563,000 detached houses that never reach the rental market. Matched
by stock type the yield is 4.0-4.9%, so the original 5.0% was close to right.
And the "rent discount is affordable" finding is real but is a transfer, not free
money: a 25% discount passes every covenant, and is paid for by 40 fewer houses
by year 50 and share delivery falling from 96% to 71%.

**Where the parameters stand.** Deliberately NOT updated to the configuration the
exploration arrived at. base.yaml still carries a 4.25% coupon, 70% LTV, a 3%
share rate and shares at 15% of need, and on those settings Stress breaches in 3
of 50 years with rent-only cover at 0.99. The exploration points at roughly 4.75%
/ 45% LTV / 5% shares at 45% of need, which clears everything -- but those are
board decisions with real consequences for tenants and investors, and setting
them quietly in a commit is not the same as choosing them.

**Housekeeping.** The pricing frontier is computed by `engine/pricing.py` rather
than typed into a comment and the reviewer sheet; the hardcoded version had gone
stale by about 150bp. The balance-sheet invariant now scales with the balance
sheet, since a flat cash tolerance refused to run above roughly GBP 500m. Dead
`_fund_year` removed.

---

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
