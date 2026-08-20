# Rebuilding the SLC Model

**Stroud Land Commons — financial model — review note**

What changed between the V2.1 spreadsheet and the model you have now: the corrections that moved the answer, and the ones that turned out to be mistakes of our own.

| | |
|---|---|
| Prepared | 20 August 2026 |
| Validation | 13,150 cells against the source workbook, exact |
| Horizon | 50 years, three scenarios |

---

## Where it stands

**Every scenario now clears every covenant.** This is the first configuration for which that has been true. It is worth saying plainly that it was not true three months ago, and that most of the distance was closed by finding errors rather than by choosing more favourable assumptions.

| Scenario | Properties | Net assets | Senior cover | Breach years | Rent-only | Share delivery |
|---|---:|---:|---:|---:|---:|---:|
| Base | 185 | £111m | 2.10× | 0 | 3.01× | 98% |
| Optimistic | 258 | £461m | 2.63× | 0 | 6.71× | 100% |
| Stress | 125 | £274m | 1.52× | 0 | 2.44× | 97% |

*Senior cover* asks whether rent services the annuity — the covenant that protects the Tontine investor. *Rent-only* strips out every gift, measured at year 20. *Share delivery* is the proportion of advertised share interest actually paid over fifty years.

> **The pricing gap has reversed.** In May the highest coupon a severe stress could carry was 3.77%, against 4.58% needed for an investor to recover their capital by median survival — an 81 basis point gap, with no rate satisfying both. Stress now carries **6.06%**. The gap is **+148bp in the Commons' favour**, and the modelled rate of 4.75% sits comfortably inside it.

---

## The port: from spreadsheet to code, number for number

The V2.1 workbook was reimplemented in Python with the parameters separated from the mechanics, then checked cell by cell against the original: **13,150 values across three scenarios, matching exactly**, including Excel's own rounding conventions and the prior-year lags the sheet used to avoid circular references.

That fidelity is deliberately preserved. A frozen copy of the port-time assumptions still reproduces the workbook, so every subsequent change can be shown to be a decision rather than a translation error. The validation runs on every commit.

Two habits came out of that stage and have earned their place since. A negative control proves the checker actually fails when it should — introducing a 0.1% drift produces 2,676 mismatches. And every structural change goes on its own branch with a written record of what was hypothesised, what the numbers said, and whether it was adopted.

---

## First wave: corrections that changed the answer

These emerged from reading the workbook's mechanics against what the instrument is actually supposed to do. Three of them changed the model's conclusions materially.

### The coupon was charging inflation twice

The sheet applied CPI plus the spread to a principal that had *already* been uplifted by CPI that year. The investor received inflation twice.

- Investor's real return: **5.0% → 2.5%**
- SLC's interest cost was overstated by **95%**

This is the single largest correction in the project. It had been hiding in plain sight since the workbook was written, because the formula looks correct until you notice which row it is pointing at.

### The Tontine now runs on mortality, not on a schedule

The workbook released a flat 6% of the balance each year from year 25 — a parametric stand-in, not a mechanism. The instrument is a lifetime annuity: the coupon stops and the charge is extinguished when the investor dies, and no principal is ever repaid.

Rebuilt on cohort survivorship from an actuarial run-off curve, with a five-year lock-up. The rule cannot fully discharge while any annuitant survives, and that floor is structural rather than a threshold someone could set wrongly.

### One DSCR became three interest cover tests

Debt service cover is the wrong instrument here: no principal is ever repaid, so the denominator was measuring something that does not happen. It is replaced by cover on cash income excluding donated property, cover on rent alone with no gifts at all, and the original ratio kept for comparison.

### Scale economies, property gifts, and the share withdrawal term

Per-property running costs now fall on a learning curve as the estate grows. Properties given outright are modelled, including the heavier retrofit that gifted stock tends to need. The community share withdrawal restriction was corrected from five years to two, matching the actual offer terms.

### The investor rate, and the question it exposed

Moved from 3.0% to 2.5% to **4.75%**. At 2.5% an investor recovers about 55% of their capital over their expected life and never breaks even — philanthropy with a yield, not a bet on longevity, and not something that raises money against a commercial annuity.

- Capital recovered by age 87: **55% → 104%**

---

## Second wave: costs became what they are, not what a percentage said

The first wave fixed mechanics. The second replaced assumptions the workbook had asserted with figures that can be defended — and in three places the assumption turned out to be describing a different organisation entirely.

### What the Commons buys is the largest lever in the model

The workbook carried one average house. But rent tracks *bedrooms* while price tracks *property type*, and they come apart: in Stroud a three-bed terrace and a three-bed semi both let for £1,176 a month, and the semi costs £55,000 more.

| Acquisition policy | Yield | Properties | Senior cover |
|---|---:|---:|---:|
| All two-bed flats | 6.94% | 203 | 3.65× |
| All three-bed terraces | 4.92% | 188 | 2.22× |
| All three-bed semis | 4.13% | 160 | 1.90× |

Identical finances, identical rent policy — only the stock differs. A 27% spread on portfolio size and 92% on cover, wider than moving the LTV limit from 70% to 30%.

The flats row is not a recommendation: a commons that houses nobody with children has not done the job, and leasehold costs are not modelled.

### The fund's costs are a person, not a percentage

A flat 0.50% margin on the fund yields £20,000 on a £4m fund — which does not pay for an actuarial valuation — and £1m on a £200m fund for the same job. It is now a staffed cost: part-time and pro-rata at the start, growing with the amount actually raised, and charged as an operating cost rather than buried in the coupon, so it reduces the surplus visibly.

### Community shares now behave as the 2014 Act defines them

An advertised rate on withdrawable share capital is a *ceiling paid at the board's discretion*, not a promise. Cover is therefore reported two ways: **senior**, asking whether rent services the annuity, and **all-in**, asking whether it also pays what the share offer advertises. Share interest is subordinated to the reserve as well as to the annuity.

The consequence is deliberate and should be stated to prospective shareholders: under Stress the offer delivers 97% of what it advertises. Shareholders wait so that annuitants never do.

### Maintenance, admin, and a cost counted twice

The flat 80% share of rent became two months in twelve — the trade convention — falling with scale as procurement leverage builds. Separately, per-property admin and maintenance were being charged *on top of* that share, counting roughly £850 per house per year twice.

- Commons' share of rent: **80% → 83.3%**, rising to 89% at scale

### Indexation became a choice

The Tontine principal can be indexed to rent, CPI or house prices. Rent is the default: once a house enters the Commons it is never sold, so its market price is a number that never gets tested, while rent is the only cash it produces. Indexing the liability to rent means it cannot drift away from the income backing it.

### Macro figures, voids and retrofit

Base now carries the published position — CPI 2.9%, private rent 3.7%, house prices 2.0% (ONS, mid-2026). Note the sign: the workbook assumed houses outrun rents by a point; they are currently growing a point and a half *slower*.

Void rates were a private landlord's numbers. With a waiting list of pre-selected tenants and security of tenure, a re-let is the week the keys change hands. Stress was failing partly for a reason that cannot happen.

- Stress voids: **15% → 5%**
- Retrofit on purchase: **£5,000 → £12,000**

---

## Under scrutiny: what we got wrong, and caught

A reviewer should know where the model has been wrong, not only where it is now right. Each of these was found by checking a result that looked convincing.

**A yield of 3.57% that did not exist.** Dividing Stroud's average rent by its average house price gives 3.57% and suggests the whole model is unfinanceable. Those are different populations — the sale average includes £563,000 detached houses that never reach the rental market. Matched by stock type the yield on lettable property is 4.0–4.9%, so the workbook's original 5.0% was close to right.

**Share interest treated as a contractual charge.** An intermediate version made share interest a hard obligation and concluded that Stress failed. That was wrong about the instrument: interest on withdrawable share capital in a community benefit society is discretionary by law.

**A diagnosis that did not survive testing.** We hypothesised that a divergence between CPI and rent was the dominant cause of covenant failure over long horizons. Correcting the indexation basis moved breaches from 13 to 11 — not to zero. The real cause was marginal cover on a debt-funded house, which is a ratio rather than an indexation artefact. The change was kept because it is right; the explanation attached to it was not.

**A funding mix presented as a finding.** An early split of 17% Tontine, 56% shares and 27% gifts was reported as a result. It was an artefact of three unrelated inherited parameters colliding, and nobody had chosen it. The mix is now a declared input whose weights are labelled as judgement, not evidence.

**A frontier that had gone stale by 150 basis points.** The coupon ceilings were typed into the reviewer sheet as literals and quietly overtaken by almost every subsequent change. They are now computed at export. Similarly, a scenario's gearing limit was written as "0.75" when that meant Base plus five points; when Base moved to 45%, it silently became Base plus thirty.

---

## The configuration: four numbers, chosen together

These interact, and moving one without the others generally makes things worse. The reasoning is recorded in the assumptions file itself so it travels with the parameters.

| Parameter | Value | Why not otherwise |
|---|---:|---|
| Investor rate | 4.75% | 4.25% returns only ~93% of capital by median survival |
| LTV limit | 45% | Costs ~2% of the portfolio, buys 30 points of cover |
| Share rate advertised | 5.00% | 3% is +0.10% real; par-value shares have no other protection |
| Shares, % of purchases | 45% | A symbolic tranche makes Stress worse, not better |

### What the balance sheet does over time

The most consequential thing the model has to say is not a single figure but a shape: the Tontine extinguishes with its investors while free capital accumulates. Permanent capital is more expensive than mortal capital over fifty years, and this is where that shows.

| Share of capital employed | Year 10 | Year 30 | Year 50 |
|---|---:|---:|---:|
| Tontine charge | 43% | 8% | 0% |
| Community shares | 41% | 47% | 29% |
| Reserves and gifts | 15% | 45% | 71% |

---

## Open: what the model still cannot tell you

Listed so they are not discovered as surprises. None of these is a defect; each is a limit on what should be concluded.

- **Retrofit cost is judgement, not a quote.** £12,000 in Base and £18,000 in Stress. It moves the all-in cost per house directly and should be replaced with real figures before it drives a decision.
- **The mortality basis is population, not annuitant.** It therefore understates longevity. The September actuarial dataset replaces a single input file, and everything here should be rerun against it.
- **The Tontine only raises £3–4m.** It draws whatever acquisitions still need after gifts and shares, so its size reflects its position in the funding queue rather than investor appetite. Below roughly £20m it is not economic as a separately regulated fund — the administration is a material share of rental income at that size.
- **All-in cover falls below 1.0 under Stress.** This is the share offer under-delivering, not a default, and it is the subordination working as intended. It is the figure most likely to prompt a question.
- **The investment phase stays at ten years.** Extending it needs a covenant sized on income rather than on property value, which is designed but not built.
- **Rent stays below market as a commitment, never as a lever.** A 25% discount passes every covenant — but it is a transfer, paid for by roughly forty fewer houses by year 50 and by share investors receiving less. It is not free money released by declining to take a profit.

---

Model, assumptions, validation harness and decision log are version-controlled. Every structural change carries a written record of what was hypothesised, what the three scenarios produced, and whether it was adopted or parked.

The accompanying workbook holds all three scenarios: **For Review** first, then the comparison and assumptions, then fifty years of statements per scenario. The **What-if** sheets are live — editing the blue cells recalculates the per-house economics that govern the four decisions above.
