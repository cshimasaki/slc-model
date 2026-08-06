"""
Macro & Indexation engine.

Reproduces the "Macro & Indexation" sheet: the three index series (CPI, rent,
house prices) that every other engine reads, plus the indexed average property
price. All index series start at 1.00 in Year 1.

Nothing here depends on any other engine, so the whole 50-year run is computed
up front and the rest of the model reads it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .assumptions import Assumptions, N_YEARS


@dataclass
class MacroSeries:
    """One entry per model year, index 0 == Year 1."""

    calendar_year: list[int] = field(default_factory=list)      # row 7
    cpi_rate: list[float] = field(default_factory=list)         # row 9
    cpi_index: list[float] = field(default_factory=list)        # row 10
    rent_rate: list[float] = field(default_factory=list)        # row 11 (shock-adjusted)
    rent_index: list[float] = field(default_factory=list)       # row 12
    hpi_base_rate: list[float] = field(default_factory=list)    # row 13
    hpi_shock: list[float] = field(default_factory=list)        # row 14
    hpi_rate: list[float] = field(default_factory=list)         # row 16 (effective)
    hpi_index: list[float] = field(default_factory=list)        # row 17
    avg_price: list[float] = field(default_factory=list)        # row 19
    cost_index: list[float] = field(default_factory=list)       # row 20


def compute(a: Assumptions, n_years: int = N_YEARS) -> MacroSeries:
    """Build every index series for the full horizon."""
    m = MacroSeries()

    for i in range(n_years):
        year = i + 1  # model year, 1-based, matching the sheet's row 6

        # Row 7: calendar year
        m.calendar_year.append(a.base_calendar_year + year - 1)

        # Row 9: CPI is flat at the scenario's rate for every year.
        m.cpi_rate.append(a.cpi_general)

        # Row 10: CPI index, rebased to 1.00 in Year 1.
        m.cpi_index.append(1.0 if year == 1 else m.cpi_index[i - 1] * (1 + m.cpi_rate[i]))

        # Row 11: rent inflation, suppressed for `rent_shock_years` starting in
        # the shock year. Inert unless both the shock year and the tail are set.
        in_rent_shock = (
            a.rent_shock_years > 0
            and a.hpi_shock_year > 0
            and year >= a.hpi_shock_year
            and year < a.hpi_shock_year + a.rent_shock_years
        )
        m.rent_rate.append(a.rent_shock_rate if in_rent_shock else a.rent_inflation)

        # Row 12: rent index.
        m.rent_index.append(1.0 if year == 1 else m.rent_index[i - 1] * (1 + m.rent_rate[i]))

        # Rows 13/14/16: house prices track CPI plus a premium, with a one-off
        # shock added in the shock year only.
        #
        # Row 15 of the sheet is a manual per-year HPI override, left blank in
        # all three scenarios. It is a spreadsheet affordance -- type a rate into
        # a cell to force it -- with no equivalent in a parameter file, so it is
        # not modelled. If a hand-set HPI path is ever needed it belongs in the
        # assumptions layer as an explicit series, not as a hidden override row.
        m.hpi_base_rate.append(a.cpi_general + a.hpi_premium)
        m.hpi_shock.append(a.hpi_shock_pct if (a.hpi_shock_year > 0 and year == a.hpi_shock_year) else 0.0)
        m.hpi_rate.append(m.hpi_base_rate[i] + m.hpi_shock[i])

        # Row 17: house price index.
        m.hpi_index.append(1.0 if year == 1 else m.hpi_index[i - 1] * (1 + m.hpi_rate[i]))

        # Row 19: the average property price, moved by house prices...
        m.avg_price.append(a.avg_price * m.hpi_index[i])

        # Row 20: ...while every other real cost is moved by CPI. The sheet
        # keeps this as its own row even though it just points at row 10, so
        # that cost indexation could later diverge from headline CPI.
        m.cost_index.append(m.cpi_index[i])

    return m
