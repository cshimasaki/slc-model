"""
Excel semantics that Python does not share.

Small module, but the differences it papers over are exactly the kind that
produce a model which is right to four decimal places and wrong at the fifth.
"""

from __future__ import annotations

import math


def excel_round(value: float, digits: int = 0) -> float:
    """
    Excel's ROUND: half away from zero.

    Python's built-in round() uses banker's rounding, so round(0.5) is 0 and
    round(2.5) is 2. Excel returns 1 and 3. The Growth Engine rounds its
    logistic acquisition count to whole properties every year, so this
    difference would silently change the portfolio.
    """
    if value == 0:
        return 0.0
    factor = 10 ** digits
    scaled = value * factor
    if scaled >= 0:
        rounded = math.floor(scaled + 0.5)
    else:
        rounded = math.ceil(scaled - 0.5)
    return rounded / factor


def excel_int(value: float) -> int:
    """
    Excel's INT: round down toward negative infinity.

    Python's int() truncates toward zero, which differs from Excel for negative
    values (int(-1.5) is -1, Excel's INT(-1.5) is -2).
    """
    return math.floor(value)


def prior(series: list[float], i: int, default: float = 0.0) -> float:
    """
    The previous year's value, or `default` in Year 1.

    The sheet gets this for free: a Year-1 formula pointing one column left
    lands in empty column C, which Excel reads as 0. Here it has to be said out
    loud. Used wherever a balance rolls forward.
    """
    return series[i - 1] if i > 0 else default
