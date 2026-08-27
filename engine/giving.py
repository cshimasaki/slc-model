"""
Philanthropic income as something that has to be earned.

The workbook set giving at a flat annual figure with a real growth rate, which
on a five-house portfolio produced GBP 110,000 a year in perpetuity -- against
GBP 34,000 of net rent from the houses themselves. Nobody had chosen that; it
was a plausible-looking number for a large organisation left running on a small
one. A reviewer called it ridiculous, correctly.

Two things are wrong with a flat line, and they pull in opposite directions.

It is too GENEROUS at the start. An organisation with no track record does not
attract legacies. Giving follows demonstrated benefit -- houses actually let to
actual people -- so the curve here ramps with homes delivered rather than with
the calendar. A commons that never grows never earns the giving either, which is
the honest behaviour and the flat line's opposite.

And it is too SMOOTH throughout. Real philanthropic income is lumpy: regular
donations wander year to year, and a bequest either arrives or it does not. A
smooth line understates how bad a bad year is, which for an organisation holding
a covenant is the part that matters. So both streams are drawn randomly, from a
seeded generator: the same seed always gives the same run, and changing it shows
another way the same assumptions could play out.

WHAT THE NUMBERS ARE ANCHORED TO -- read this before trusting them
------------------------------------------------------------------
A search of the public record did NOT produce a per-organisation figure for
philanthropic donations to a small housing-owning CLT, and the defaults here are
therefore judgement rather than evidence. What the search did establish is worth
knowing:

  * Most CLTs are Community Benefit Societies on the FCA Mutuals Public
    Register, not at Companies House -- Bristol CLT is 31423R. Only CLTs
    structured as companies (CLG/CIC) file at Companies House, and only
    registered charities give a donations breakdown at the Charity Commission.
  * The National CLT Network reported GBP 459,036 total income for the year to
    March 2025, of which GBP 242,458 was grant funding -- but that is the
    national body, not a landlord.
  * Homes England allocated GBP 137m across 175 community-led schemes in the
    2021-26 programme, roughly GBP 783,000 a scheme. That is development grant,
    not philanthropy, and belongs in a different line.
  * For charities that do publish it, legacies commonly dominate voluntary
    income -- the Woodland Trust's largest single source is gifts in wills.
    That is the shape these defaults follow: modest regular giving, occasional
    large bequests.

Establishing a real figure means pulling individual accounts off the FCA
register and the Charity Commission one organisation at a time. Until somebody
does, treat `gift_mature_annual` and `beq_mean` as placeholders with a defensible
shape rather than as findings.
"""

from __future__ import annotations

import random


def credibility(homes: float, half_at: float) -> float:
    """
    How much of its mature giving an organisation has earned, at this size.

    Hyperbolic rather than linear: `homes / (homes + half_at)`. Zero at zero
    homes, half at `half_at`, approaching one and never reaching it. The shape
    matters more than the constant -- the first houses buy most of the
    credibility, and the fiftieth buys almost none, which is how a reputation
    for delivering actually behaves.
    """
    if homes <= 0 or half_at <= 0:
        return 0.0
    return homes / (homes + half_at)


def draw(a, n_years: int) -> tuple[list[float], list[float]]:
    """
    A whole run's giving, drawn once: regular donations and bequests, per year.

    Generated up front rather than year by year so the sequence depends only on
    the seed -- a path drawn inside the year loop would shift if anything else
    ever consumed a random number, and a model whose answer moves for reasons
    nobody can see is worse than one that is merely wrong.

    Both streams are scaled by credibility at the time, which the caller applies
    per year; what is drawn here is the multiplier and the arrivals.
    """
    rng = random.Random(getattr(a, "gift_seed", 0))
    cv = max(0.0, getattr(a, "gift_volatility", 0.35))

    regular: list[float] = []
    for _ in range(n_years):
        # Lognormal, so a bad year can halve and a good year cannot go negative
        # -- giving is bounded below by zero and has a long right tail.
        sigma = (cv ** 2 + 1) ** 0.5
        regular.append(rng.lognormvariate(0.0, min(1.5, (sigma - 1) or cv)))

    bequests: list[float] = []
    for _ in range(n_years):
        bequests.append(rng.random())

    return regular, bequests


def bequest_amount(a, rng_value: float, rate: float, mean: float) -> float:
    """
    A bequest this year, or nothing.

    Arrivals are Bernoulli on the credibility-scaled rate, so a young
    organisation mostly gets nothing and occasionally gets a windfall. Sizes are
    a coarse three-point distribution rather than a smooth one: most legacies to
    a small local body are modest, a few are transformative, and pretending to
    know the shape more precisely than that would be false confidence.
    """
    if rng_value >= rate:
        return 0.0
    # Where in the arrival did it land -- reused as the size draw so no extra
    # random number is consumed.
    where = rng_value / rate if rate > 0 else 0.0
    if where < 0.70:
        return mean * 0.5
    if where < 0.95:
        return mean * 1.5
    return mean * 4.0
