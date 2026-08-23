"""
The whole thing at five properties, so it can be read.

Written in response to a reviewer's objection that the fifty-year model is too
complex to see the drivers, and that the scale of the later years hides the risk
in the early ones. Both are fair. This runs the SAME engine -- no separate
arithmetic, nothing simplified away -- but on a portfolio small enough to read
line by line, and it surfaces two things the main outputs never showed:

  * The Tontine as PEOPLE. Who invested, in which year, at what age, how many
    are still alive, how many died this year, and what we paid them. The model
    always computed this; nothing ever printed it.
  * The cost of running the organisation, separated into the corporate function
    and the property-level share, so the staffing question can be argued about
    with a number rather than an impression.

    python analysis/five_properties.py            # base
    python analysis/five_properties.py --stress   # and the bad case
    python analysis/five_properties.py --csv out  # tables as CSV

Everything is shown in REAL year-1 money. Nominal figures over fifty years of
compounding flatter the later years and are the main reason a long model
misleads about its early ones.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.assumptions import load                       # noqa: E402
from engine.capital_debt import runoff_curve              # noqa: E402
from engine.model import run                              # noqa: E402

# Five houses, bought 2/2/1 over three years, then nothing. The ceiling and the
# floor are set to hold it there: without them the logistic curve keeps buying.
PLAN = (2, 2, 1)

# What one investor typically puts in. Purely a headcount device -- the model
# works in pounds and does not care -- but "eleven investors, four still alive"
# is a sentence somebody can check against reality, and "GBP 548,000 of charge"
# is not.
TICKET = 50_000
ENTRY_AGE = 65


def build(scenario: str, corporate: float | None = None,
          gift_mult: float = 1.0):
    a = load(scenario)
    a.values["acq_year1"], a.values["acq_year2"], a.values["acq_year3"] = PLAN
    a.values["logistic_ceiling"] = sum(PLAN)
    a.values["logistic_floor"] = 0
    # Gifts would quietly add a sixth house and confuse the point of the exercise.
    a.values["gift_property_start_yr"] = 0
    # Buy the plan, and let the funding tables show what that COST. Left
    # constrained, the model buys four houses instead of five and stops -- which
    # is a real finding about the funding assumptions, but it answers a question
    # nobody asked and hides the one that was. The premise here is "the capital
    # is there"; what it takes to be there is then reported honestly.
    a.values["constrain_growth"] = 0

    # The CCBS corporate function only. Housing Commons manages and maintains the
    # homes, paid through the 16.67% of rent that never reaches the Commons at
    # all -- so this line is accounting, financial management, governance, the
    # FCA return, insurance and oversight of the annuity fund. It is NOT housing
    # management, and benchmarking it against a housing association's staffing
    # compares it to a job it does not do.
    #
    # The workbook's figure is flat from year 5 forever, which is wrong at both
    # ends -- far too small at 185 homes, and 58% of gross rent at five. It wants
    # a proper build-up by function against portfolio size. Until that exists,
    # this is steerable and the sensitivity below shows what it decides.
    if corporate is not None:
        share = corporate / 4.0
        a.values["board_early"] = a.values["board_target"] = share
        a.values["acct_early"] = a.values["acct_target"] = share
        a.values["fca_early"] = a.values["fca_target"] = share
        a.values["ins_early"] = a.values["ins_target"] = share
        a.values["pf_fund_admin_early"] = 0.0
        a.values["pf_fund_admin_target"] = 0.0
    if gift_mult != 1.0:
        a.values["gift_baseline"] *= gift_mult
        a.values["beq_baseline"] *= gift_mult
        a.values["founding_capital"] *= gift_mult
    return run(a)


def cohorts(r):
    """
    Per-year Tontine detail, from the drawdowns and the survival curve.

    Recomputed here rather than read from state so the arithmetic is visible:
    a cohort that invested in year k is aged ENTRY_AGE + (i - k) in year i, and
    the proportion still alive is the curve's survival at that duration.
    """
    c = r.state.capital
    draws = [(k, d) for k, d in enumerate(c.tf_drawdown) if d > 1e-6]
    rows = []
    for i in range(r.n_years):
        alive = deaths = 0.0
        ages: list[tuple[float, int]] = []
        for k, d in draws:
            if i < k:
                continue
            n = d / TICKET
            dur = i - k
            s_now = runoff_curve.survival_at(dur)
            s_prev = runoff_curve.survival_at(dur - 1) if dur > 0 else 1.0
            alive += n * s_now
            deaths += n * (s_prev - s_now)
            if n * s_now > 0.005:
                ages.append((n * s_now, ENTRY_AGE + dur))
        oldest = max((age for _, age in ages), default=0)
        weighted = sum(w * age for w, age in ages) / alive if alive > 0.005 else 0
        rows.append(dict(alive=alive, deaths=deaths, mean_age=weighted, oldest=oldest))
    return rows


def sensitivity(scenario: str) -> None:
    """
    Do five houses wash their face? Across the two numbers nobody has yet fixed.

    Corporate cost is not settled, and neither is how much giving a five-house
    commons can count on. Rather than pick one of each and present the answer as
    a finding, this shows the grid -- because which cell you are in decides
    whether the thing works, and that is the honest state of knowledge.

    Rent-only cover is the measure that matters here: it strips every gift and
    asks whether the HOUSES service the debt. Cash cover flatters this portfolio
    badly, reading above 4x while rent alone covers 0.04x.
    """
    print(f"\n{'=' * 100}")
    print(f"DOES IT WASH ITS FACE? — {scenario.upper()}, five houses")
    print(f"{'=' * 100}")
    print("  Rent-only cover at year 20 — gifts stripped out entirely.")
    print("  Below 1.00 means the five houses do not service their own interest.\n")

    print(f"{'corporate':<14}{'rent-only cover at yr 20':>26}{'years in deficit':>40}")
    print(f"{'cost / yr':<14}{'(gifts stripped)':>26}"
          f"{'gifts as modelled':>18}{'half':>10}{'none':>12}")
    print("-" * 80)
    for corp in (8_000, 15_000, 25_000, 38_292):
        ro = None
        defics = []
        for mult in (1.0, 0.5, 0.0):
            r = build(scenario, corporate=corp, gift_mult=mult)
            c = r.state.capital
            if ro is None:
                ro = c.rent_only_cover[19]
            defics.append(sum(1 for v in r.state.statements.retained_surplus if v < 0))
        label = f"£{corp:,.0f}" + ("*" if corp > 38_000 else "")
        ro_s = f"{ro:.2f}x" if isinstance(ro, (int, float)) else "—"
        print(f"{label:<14}{ro_s:>26}{defics[0]:>18}{defics[1]:>10}{defics[2]:>12}")
    print()
    print("  * the figure currently in the model, which is a flat corporate cost")
    print("    carried over from the workbook and never sized to a portfolio.")
    print()
    print("  Two separate questions, and the grid separates them:")
    print()
    print("  Rent-only cover moves ONLY with corporate cost, because the measure")
    print("  strips gifts by definition. Sized for five houses (£8-15k for")
    print("  bookkeeping, an independent examination, the FCA return and insurance)")
    print("  the houses service their own interest comfortably by year 20 — 2.08x to")
    print("  2.45x. At the modelled £38,292 they scrape 1.04x, and that is the")
    print("  corporate figure failing, not the houses.")
    print()
    print("  Gifts decide the JOURNEY, not the destination. With giving as modelled")
    print("  there is no deficit year at any corporate cost. With none, there are 9")
    print("  to 26 — the houses still get there, but something has to fund them")
    print("  while they do.")


def report(scenario: str, csv_dir: str | None, corporate: float | None = None) -> None:
    r = build(scenario, corporate=corporate)
    a, s, m = r.assumptions, r.state, r.macro
    g, A, c, f = s.growth, s.assets, s.capital, s.statements
    coh = cohorts(r)

    def real(x, i):
        return x / m.cpi_index[i]

    unit = g.unit_acquisition_cost[0]
    print(f"\n{'=' * 100}")
    print(f"FIVE PROPERTIES — {scenario.upper()}    (all figures in real year-1 money)")
    print(f"{'=' * 100}")
    print(f"  {sum(PLAN)} houses bought {PLAN[0]}/{PLAN[1]}/{PLAN[2]} over three years")
    print(f"  All-in cost per house  £{unit:,.0f}   total outlay  £{unit * sum(PLAN):,.0f}")
    print(f"  Let at £{a.avg_price * a.gross_yield / 12:,.0f}/month, below market, "
          f"rising {a.rent_inflation:.1%} a year")
    print(f"  Tontine investors enter at {ENTRY_AGE}; headcount shown at "
          f"£{TICKET:,} average holding")

    print(f"\n{'-' * 100}")
    print("OPERATIONS — what the HOUSES earn and cost, with nothing else mixed in")
    print(f"{'-' * 100}")
    print("  Gifts and founding capital are deliberately NOT in this table. Counting them")
    print("  as operating income is what makes year 1 look profitable on one let house.")
    print()
    print(f"{'yr':>3}{'homes':>6}{'gross rent':>12}{'property':>11}{'corporate':>11}"
          f"{'sinking':>10}{'from houses':>13}")
    for i in range(r.n_years):
        if not (i < 15 or (i + 1) % 5 == 0):
            continue
        gross = real(A.gross_rent[i], i)
        prop = gross * (1 - A.lc_share_effective[i]) + gross * a.void_rate
        corp = real(g.admin_total[i], i)
        sink = real(A.sinking_contribution[i], i)
        maint = real(-f.maintenance[i], i)
        from_houses = gross - prop - corp - sink - maint
        print(f"{i + 1:>3}{g.portfolio_closing[i]:>6.0f}{gross:>12,.0f}{prop:>11,.0f}"
              f"{corp:>11,.0f}{sink:>10,.0f}{from_houses:>13,.0f}")

    print(f"\n{'-' * 100}")
    print("FUNDING — what it took to buy five houses in three years")
    print(f"{'-' * 100}")
    print(f"{'yr':>3}{'bought':>8}{'cost':>12}{'tontine':>11}{'shares':>11}"
          f"{'gifts+founding':>16}{'from cash':>11}")
    for i in range(6):
        cost = real(A.acquisition_cash_cost[i], i)
        ton = real(c.tf_drawdown[i], i)
        sh = real(c.cs_issued[i] + c.cs_withdrawals[i] + c.cs_issue_costs[i], i)
        gi = real(c.gift_income_total[i], i)
        print(f"{i + 1:>3}{g.properties_added[i]:>8.0f}{cost:>12,.0f}{ton:>11,.0f}"
              f"{sh:>11,.0f}{gi:>16,.0f}{cost - ton - sh - gi:>11,.0f}")
    t3 = sum(real(A.acquisition_cash_cost[i], i) for i in range(3))
    print(f"{'':>3}{'':>8}{'—' * 10:>12}")
    print(f"  Three-year outlay £{t3:,.0f} — against a reviewer's estimate of £1.8m")

    print(f"\n{'-' * 100}")
    print("THE TONTINE — the investors, and what happens to them")
    print(f"{'-' * 100}")
    print(f"{'yr':>3}{'drawn':>11}{'investors':>11}{'mean age':>10}{'oldest':>8}"
          f"{'died':>7}{'coupon paid':>13}{'charge left':>13}")
    for i in range(r.n_years):
        if not (i < 15 or (i + 1) % 5 == 0):
            continue
        k = coh[i]
        drawn = real(c.tf_drawdown[i], i)
        live = k["alive"] > 0.05
        drawn_s = format(drawn, ",.0f") if drawn > 0.5 else "—"
        age_s = format(k["mean_age"], ".0f") if live else "—"
        oldest_s = str(k["oldest"]) if live else "—"
        died_s = format(k["deaths"], ".2f") if k["deaths"] > 0.004 else "—"
        print(f"{i + 1:>3}{drawn_s:>11}{k['alive']:>11.1f}{age_s:>10}{oldest_s:>8}"
              f"{died_s:>7}{real(-c.tf_interest[i], i):>13,.0f}"
              f"{real(c.tf_closing[i], i):>13,.0f}")

    print(f"\n{'-' * 100}")
    print("THE BOTTOM LINE — can it pay, and does it hold cash")
    print(f"{'-' * 100}")
    print("  'income' here DOES include gifts and Gift Aid — that is what actually")
    print("  pays the bills in the early years, and pretending otherwise would be worse.")
    print()
    print(f"{'yr':>3}{'income':>11}{'interest':>11}{'share int':>11}"
          f"{'retained':>11}{'free cash':>12}{'cover':>8}")
    for i in range(r.n_years):
        if not (i < 15 or (i + 1) % 5 == 0):
            continue
        cover = c.cash_interest_cover[i]
        print(f"{i + 1:>3}{real(f.operating_surplus[i], i):>11,.0f}"
              f"{real(c.total_interest[i], i):>11,.0f}"
              f"{real(c.cs_dividends[i], i):>11,.0f}"
              f"{real(f.retained_surplus[i], i):>11,.0f}"
              f"{real(f.free_cash[i], i):>12,.0f}"
              f"{(f'{cover:.2f}' if isinstance(cover, (int, float)) else '—'):>8}")

    worst = min(((v, i) for i, v in enumerate(c.cash_interest_cover)
                 if isinstance(v, (int, float))), default=(None, None))
    neg = [i + 1 for i in range(r.n_years) if f.retained_surplus[i] < 0]
    last_investor = next((i + 1 for i in range(r.n_years - 1, -1, -1)
                          if coh[i]["alive"] > 0.01), None)
    print(f"\n  Worst cover           {worst[0]:.2f}× in year {worst[1] + 1}")
    print(f"  Years in deficit      {len(neg)}"
          + (f"  (years {neg[0]}–{neg[-1]})" if neg else ""))
    print(f"  Last investor alive   around year {last_investor}")
    print(f"  Charge at year 50     £{real(c.tf_closing[-1], r.n_years - 1):,.0f}")
    print(f"  Free cash at year 50  £{real(f.free_cash[-1], r.n_years - 1):,.0f}")

    if csv_dir:
        os.makedirs(csv_dir, exist_ok=True)
        path = os.path.join(csv_dir, f"five_properties_{scenario}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["year", "homes", "gross_rent", "property_costs", "corporate_costs",
                        "sinking", "net_operating", "tontine_drawn", "investors_alive",
                        "mean_age", "deaths", "coupon_paid", "charge_outstanding",
                        "share_interest", "retained", "free_cash", "cover"])
            for i in range(r.n_years):
                gross = real(A.gross_rent[i], i)
                cover = c.cash_interest_cover[i]
                w.writerow([
                    i + 1, g.portfolio_closing[i], round(gross),
                    round(gross * (1 - A.lc_share_effective[i]) + gross * a.void_rate),
                    round(real(g.admin_total[i], i)),
                    round(real(A.sinking_contribution[i], i)),
                    round(real(f.operating_surplus[i], i)),
                    round(real(c.tf_drawdown[i], i)),
                    round(coh[i]["alive"], 2), round(coh[i]["mean_age"]),
                    round(coh[i]["deaths"], 3),
                    round(real(-c.tf_interest[i], i)),
                    round(real(c.tf_closing[i], i)),
                    round(real(c.cs_dividends[i], i)),
                    round(real(f.retained_surplus[i], i)),
                    round(real(f.free_cash[i], i)),
                    round(cover, 3) if isinstance(cover, (int, float)) else "",
                ])
        print(f"\n  CSV: {os.path.relpath(path, ROOT)}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stress", action="store_true", help="also run the stress case")
    p.add_argument("--csv", metavar="DIR", help="write the tables as CSV")
    p.add_argument("--corporate", type=float, metavar="GBP",
                   help="CCBS corporate cost per year, real (default: as modelled)")
    p.add_argument("--sensitivity", action="store_true",
                   help="grid over corporate cost and giving")
    args = p.parse_args()

    report("base", args.csv, args.corporate)
    if args.stress:
        report("stress", args.csv, args.corporate)
    if args.sensitivity:
        sensitivity("base")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
