"""
What the Commons actually buys.

The workbook carried a single average house: one price, one gross yield. That
hides the largest single lever in the whole model, which is not a financing
decision at all -- it is which houses you buy.

The reason is that rent tracks BEDROOMS while price tracks PROPERTY TYPE, and
the two come apart. In Stroud (ONS, mid-2026) a three-bedroom terrace and a
three-bedroom semi command the same GBP 1,176 a month, but the semi costs GBP
55,000 more. On rent-recovery logic the semi is simply a worse asset: 19% more
capital for identical income. Meanwhile a two-bed flat at GBP 166,000 lets for
GBP 960 and yields nearly 7%.

Spread across a portfolio that is a wider spread than moving the LTV limit from
70% to 30%, or than any coupon decision we have modelled. Buying the wrong stock
costs more than any plausible mistake in the capital stack.

A caution about averages
------------------------
An earlier version of this analysis divided Stroud's average rent by Stroud's
average house price and got 3.57%, which would have been close to unfinanceable.
That was wrong: the two figures describe different populations. The sale average
includes GBP 563,000 detached houses that never appear in the rental market at
all, so dividing one by the other understates the yield on lettable stock by
about 140 basis points. Yields here are always computed per stock type, price
and rent matched to the same kind of house.

What this module does NOT do
----------------------------
It blends the mix into a single average price and yield, which the rest of the
model then uses exactly as before. It does not track cohorts per stock type. So
it answers "what does this acquisition policy cost and earn?" but not "what
happens if the flats do well and the terraces do badly?". Divergent maintenance,
void or rent-growth behaviour between types would need per-type cohorts, which
is a much larger change and is not yet justified.
"""

from __future__ import annotations

MONTHS = 12


class StockError(Exception):
    """Raised when a stock mix is malformed."""


def _validate(types: list[dict]) -> None:
    if not types:
        raise StockError("stock_types is empty -- the model needs something to buy")

    for i, t in enumerate(types):
        for key in ("name", "share", "price", "rent_pcm"):
            if key not in t:
                raise StockError(f"stock_types[{i}] has no {key!r}")
        if t["price"] <= 0:
            raise StockError(f"{t['name']!r}: price must be positive")
        if t["rent_pcm"] <= 0:
            raise StockError(f"{t['name']!r}: rent_pcm must be positive")
        if t["share"] < 0:
            raise StockError(f"{t['name']!r}: share cannot be negative")

    total = sum(t["share"] for t in types)
    # Tight rather than forgiving. Shares that do not sum to one are a typo, and
    # silently normalising them would change every downstream number while
    # looking like it had worked.
    if abs(total - 1.0) > 1e-6:
        listed = ", ".join(f"{t['name']}={t['share']:.0%}" for t in types)
        raise StockError(
            f"stock_types shares sum to {total:.4f}, not 1.0 ({listed})"
        )


def blended(types: list[dict]) -> tuple[float, float]:
    """
    The average price and gross yield implied by an acquisition mix.

    The yield is total rent over total price across the mix -- NOT the average
    of each type's yield. Averaging the yields would weight a GBP 166,000 flat
    equally with a GBP 342,000 semi and overstate what the portfolio earns.
    """
    _validate(types)

    price = sum(t["share"] * t["price"] for t in types)
    rent = sum(t["share"] * t["rent_pcm"] * MONTHS for t in types)
    return price, rent / price


def describe(types: list[dict]) -> list[tuple[str, float, float, float, float]]:
    """(name, share, price, annual rent, gross yield) per type. For reporting."""
    return [
        (t["name"], t["share"], float(t["price"]),
         t["rent_pcm"] * MONTHS, t["rent_pcm"] * MONTHS / t["price"])
        for t in types
    ]
