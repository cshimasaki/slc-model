# What changed in the model — August 2026

A summary for the team of how the Stroud Land Commons financial model has
changed since `Financial Modelling for SLC V2.1.xlsx`, and what it now says.

Written to be read without opening any code.

**→ [Open the explorer](https://cshimasaki.github.io/slc-model/)** to see any of
this year by year, and to compare scenarios.

---

## The short version

The model moved out of Excel into code, and in the process **six substantive
things about the Tontine turned out to be wrong or missing**. One of them — the
coupon — was making the entire plan look precarious when it isn't.

| | As inherited from V2.1 | Now |
|---|---|---|
| Base: houses at Year 50 | 49 | **117** |
| Base: net assets at Year 50 | £62m | **£172m** |
| Base: years breaching covenant | 21 | **0** |
| Stress: years breaching covenant | 34 | **0** |
| Stress: net assets at Year 50 | £60m | **£170m** |

**Every scenario now clears its covenant in every year**, including Stress.
That was not true of any parameter combination we tried before the errors were
found — it is the result of correcting them, not of optimistic assumptions.

---

## The six changes, in order of how much they mattered

### 1. The Tontine coupon was charging inflation twice

**The largest single error, and it was inherited from the spreadsheet.**

The Tontine principal is uplifted by CPI every year, and no principal is ever
repaid. So an investor's entire return is the coupon, paid on a base that
already grows with inflation — their inflation protection is delivered by the
indexation.

The spreadsheet then set the coupon rate to **CPI + 3.25%** and applied it to
that already-indexed principal. The investor received CPI twice.

| | Real return to the investor |
|---|---|
| What the design specifies | **2.50%** |
| What the actuarial model does | **2.50%** ✓ |
| What the spreadsheet did | **5.00%** ✗ |

At Base inflation this overstated SLC's interest cost by **95%**. Fifty-year
interest falls from £12.8m to £6.8m once corrected.

This single fix took Base from breaching its covenant in 10 years to **none**,
and Stress from 27 years to **none**.

### 2. The Tontine was modelled as a repayment schedule, not as mortality

The original model released a flat 6% of the balance each year from Year 25 —
a placeholder, not a mechanism. It never reached zero: more than a third of the
charge was still outstanding at Year 50, with SLC paying coupon on it.

Worse, **interest did not stop when investors died**. At Year 21, 76% of
investors were alive but the model charged interest on the full balance.

It now works as the instrument actually does: each year's investment is a
cohort of investors entering at 65, SLC pays a coupon while they live, and on
death the coupon stops and the charge is extinguished with no principal repaid.
Mortality is the only mechanism. There is no schedule and no redemption date.

Two policy levers sit on top: a **5-year minimum term** before any charge can
be released, and a setting for **what happens to a dead investor's capital** —
see "Still open" below.

### 3. Property gifts can now be modelled

The model could only represent a gift as cash. A house given outright is
different: no purchase price, no debt, no borrowing capacity used, and it earns
rent from the year it arrives.

There is currently no vehicle for gifting property this way in Stroud or in
much of the UK, which makes it a strategically distinctive opportunity.

Deliberately conservative: gifts are treated as **earned by demonstrated
community benefit**, not assumed. Base assumes nothing at all for fourteen
years, then one house every other year. Stress assumes a gift never arrives.

Even on that basis it is powerful — and in the earlier analysis, gift-funded
growth was the *only* route that both grew the portfolio and improved covenant
cover. Every debt-funded route bought fewer houses and worsened cover.

### 4. One covenant became three

The old test was a single "DSCR ≥ 1.20×", and it was measuring the wrong thing
twice over.

- **It is not a DSCR.** Across fifty years the model repays **£0** of principal
  — the Tontine never amortises. It is an *interest cover* ratio, and the DSCR
  label invited comparison with commercial borrowers who carry refinancing risk
  that SLC does not.
- **It counted a house as income.** A donated property is recognised at market
  value, which is right for the accounts and wrong for a covenant. Interest
  cannot be paid with a house.

There are now three tests:

| Test | Threshold | What it asks |
|---|---|---|
| **Cash interest cover** | ≥ 1.25× | Can we cover interest from cash income? |
| **Rent-only cover** | ≥ 1.00× by Year 20 | Can the portfolio service its own debt, with no gifts at all? |
| **Stressed cover** | ≥ 1.00× at CPI +2pts | Does it survive an inflation spike? |

The second is the one that matters. It asks whether the houses pay for
themselves, and it is the honest measure of how much the plan leans on giving
that nobody is obliged to continue.

### 5. Running costs now fall as the estate grows

Per-property costs were flat forever — £150 admin, £700 maintenance, whether
the estate held five houses or two hundred. That ignored bulk material
purchasing, gas safety checks batched across a round of properties, and the
contractual leverage that comes with volume.

Modelled as a learning curve: cost falls 8% for each **doubling** of the
portfolio, floored at 65% of the small-scale cost.

| Houses | Admin/property | Maintenance/property |
|---|---|---|
| 1 | £150 | £700 |
| 10 | £114 | £531 |
| 50+ | £98 | £455 |

Worth £1.9m over fifty years. Real, but second-order next to the coupon fix —
and note this assumes the saving *stays* with the Commons. If it is passed to
tenants as lower rent or consumed by retrofitting, as intended, the benefit to
the balance sheet is smaller or nil.

### 6. Smaller corrections

- **Investor annuity rate** moved from CPI + 3.0% to **CPI + 2.5%**, matching
  the indicative actuarial model. The actuarial work found the fund
  collateralised at 2.13× its liabilities, i.e. it can carry a lower coupon
  than it was originally given.
- **Community share withdrawal restriction** corrected from 5 years to **2**,
  matching the actual offer terms.

---

## What the model now says

On Base assumptions, with the conservative gift profile:

- **117 properties** by Year 50, worth **£172m** in net assets
- **No covenant breach in any year**
- The portfolio pays its own interest from rent alone from **Year 6**
- Total Tontine capital drawn: under **£8m** of the £50m available

Stress — high inflation, 15% voids, a 20% house-price crash in Year 5, halved
share take-up, and no property gifts ever — still clears the covenant in every
year and ends at £170m net assets.

**A caveat worth stating plainly:** this is not because the plan became more
ambitious. It is because the arithmetic was wrong in ways that made it look
worse than it is. The assumptions are, if anything, more conservative than they
were.

---

## Still open

**What happens to a dead investor's capital.** The single most consequential
undecided parameter. Either the charge is extinguished and the Commons holds
the property free of it, or the entitlement passes to surviving investors,
lifting their yield without reducing what SLC owes.

| To the Commons | To investors | Net assets at Year 50 |
|---|---|---|
| 100% | 0% | **£172m** |
| 50% | 50% | £152m |
| 0% | 100% | £130m |

Conceding the whole survivorship benefit to investors costs roughly **£42m** of
net assets — around £10m for every 25 points. It is a commercial judgement —
whether a higher investor yield buys enough acceleration in new investment to
be worth it — not a modelling one. Currently set to 100% to the Commons.

**The mortality basis is a placeholder.** It uses population mortality, not
annuitant mortality. Real annuitants live longer, so the current figures are a
*favourable bound*. The Department of Actuarial Mathematics dataset expected in
September replaces one file and re-runs everything.

**Community share withdrawals are unrealistically smooth.** They are modelled
as a steady rate, where reality would cluster — after a life event, or if
confidence dips. Clustering is the part that matters, because withdrawals
concentrating in a bad year is exactly when the Commons can least afford them.
Director discretion over withdrawals provides a real buffer that is also not
yet modelled.

**Where efficiency savings go** is not modelled — see change 5.

**Rent Credit Obligations are deliberately out of scope.** They are a separate
vehicle with different economics: debt-free, zero net surplus by design, no
gearing and no covenant. Grafting them onto this model would corrupt both.
Two vehicles, two models.

---

## How much of this can be trusted

The model reproduces the original spreadsheet **cell for cell — 13,150 figures
across all three scenarios** — when run on the original assumptions. That check
runs automatically on every change, so the arithmetic core is provably
unchanged since the port.

Beyond that it is checked by **51 automated tests**, including one that
deliberately breaks the model to prove the checking works at all.

What that does *not* cover: whether the assumptions are right. The model is
arithmetic, not judgement. Every figure above depends on inputs that are
estimates, and the ones most worth arguing with are listed under "Still open".

---

*Generated from the model on 7 August 2026. Full technical detail, including
every decision and the reasoning behind it, is in [MODEL_LOG.md](MODEL_LOG.md).*
