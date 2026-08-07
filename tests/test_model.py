"""
Tests for the model's own invariants and the assumptions layer.

These hold regardless of what the Excel workbook says -- they are the things
that must be true of any correct run, and they keep holding if someone edits an
assumption or puts a structural change on a branch.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.assumptions import AssumptionError, load, load_all   # noqa: E402
from engine.excelfns import excel_int, excel_round               # noqa: E402
from engine.model import ModelError, run                         # noqa: E402

SCENARIOS = ["base", "optimistic", "stress"]


# ------------------------------------------------------------ assumptions ---

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenario_loads(scenario):
    a = load(scenario)
    assert a.name == scenario
    assert a.base_calendar_year == 2026


def test_deltas_apply_over_base():
    base, stress = load("base"), load("stress")
    # Stress overrides these...
    assert base.void_rate == 0.05 and stress.void_rate == 0.15
    assert base.cpi_general == 0.025 and stress.cpi_general == 0.045
    assert base.hpi_shock_year == 0 and stress.hpi_shock_year == 5
    # ...and inherits everything else, including the shock's own size.
    assert stress.hpi_shock_pct == base.hpi_shock_pct == -0.20
    assert stress.rent_shock_rate == base.rent_shock_rate == 0.0
    assert stress.pf_ltv_limit == base.pf_ltv_limit


def test_coupon_spread_is_derived_not_stored():
    """
    Changing a component must move the coupon, as =SUM(E14:E16) does.

    Deliberately asserts the *relationship*, never a literal total. Pinning the
    total would make a legitimate pricing decision look like a broken test --
    which is exactly what happened when the investor rate moved to 2.5%.
    """
    a = load("base")
    assert a.pf_coupon_spread == pytest.approx(
        a.pf_investor_rate + a.pf_fund_op_margin + a.pf_fund_reg_charge
    )

    # And it is genuinely derived: move a component, the total follows.
    bumped = load("base")
    bumped.values["pf_investor_rate"] += 0.01
    from engine.assumptions import _derive
    _derive(bumped.values)
    assert bumped.pf_coupon_spread == pytest.approx(a.pf_coupon_spread + 0.01)


def test_labels_cover_every_parameter():
    """
    labels.yaml and base.yaml must describe the same parameter set.

    They are separate files so base.yaml stays clean for a non-coder to edit,
    but that split means a parameter added to one and not the other would
    silently vanish from the explorer's assumptions panel and the Excel
    workbook. This is the check that stops that.
    """
    import yaml

    with open(os.path.join(ROOT, "assumptions", "base.yaml"), encoding="utf-8") as f:
        base = yaml.safe_load(f)
    with open(os.path.join(ROOT, "assumptions", "labels.yaml"), encoding="utf-8") as f:
        labels = yaml.safe_load(f)

    assert set(base) == set(labels), (
        f"section mismatch — only in base: {set(base) - set(labels)}; "
        f"only in labels: {set(labels) - set(base)}"
    )
    a = load("base")
    for section in base:
        base_keys = set(base[section])
        labelled = {k: v for k, v in labels[section].items() if k != "_title"}
        # A derived value is described here but is not an input, so it is
        # expected to be absent from base.yaml -- and must exist on the loaded
        # assumptions, or the panel would show a blank.
        derived = {k for k, v in labelled.items() if v.get("derived")}
        for key in derived:
            assert key in a.values, f"{key} is marked derived but the model never computes it"
        assert base_keys == set(labelled) - derived, (
            f"section {section!r}: only in base: {base_keys - set(labelled)}; "
            f"only in labels: {set(labelled) - derived - base_keys}"
        )
        for key, meta in labelled.items():
            assert meta.get("label"), f"{key} has no label"


def test_scenario_cannot_invent_parameters():
    """A typo'd key in a scenario file is an error, not a silently ignored line."""
    import tempfile
    import yaml

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(ROOT, "assumptions", "base.yaml"), encoding="utf-8") as f:
            base = yaml.safe_load(f)
        with open(os.path.join(d, "base.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(base, f)
        with open(os.path.join(d, "typo.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump({"rent_yield": {"viod_rate": 0.15}}, f)

        with pytest.raises(AssumptionError, match="viod_rate"):
            load("typo", assumptions_dir=d)


# ----------------------------------------------------------- invariants ---

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_balance_sheet_balances(scenario):
    """Assets = liabilities + reserves, every year. The sheet's own row 46."""
    result = run(scenario)
    for i, check in enumerate(result.state.statements.balance_check):
        assert abs(check) < 1e-6, f"year {i + 1} out by {check}"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_monthly_reconciles_to_annual(scenario):
    """Each year's twelve months sum to the annual net change in cash."""
    result = run(scenario)
    checked = 0
    for value in result.state.monthly.reconciliation:
        if value != "":
            assert abs(value) < 0.01, f"months do not reconcile: out by {value}"
            checked += 1
    assert checked == 5, "expected a reconciliation at each of the 5 year ends"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_portfolio_never_shrinks_and_respects_ceiling(scenario):
    """The model never sells: the portfolio is monotonic and capped."""
    result = run(scenario)
    closing = result.state.growth.portfolio_closing
    assert all(b >= a for a, b in zip(closing, closing[1:])), "portfolio shrank"
    assert max(closing) <= result.assumptions.logistic_ceiling


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_tontine_respects_its_caps(scenario):
    """Drawdowns stop at the raise cap and outside the investment phase."""
    a = run(scenario).assumptions
    result = run(scenario)
    c = result.state.capital

    assert max(c.tf_cum_raised_closing) <= a.pf_max_raise + 1e-6
    for i, drawn in enumerate(c.tf_drawdown):
        if i + 1 > a.pf_invest_phase_yrs:
            assert drawn == 0, f"drew Tontine capital in year {i + 1}, past the investment phase"


def test_stress_fires_the_shock_and_base_does_not():
    """The shock is defined in Base but dormant; Stress switches it on."""
    base, stress = run("base"), run("stress")
    a = stress.assumptions

    assert all(v == 0 for v in base.macro.hpi_shock), "Base should have no shock"
    shock_year_index = a.hpi_shock_year - 1
    assert stress.macro.hpi_shock[shock_year_index] == pytest.approx(-0.20)
    # House prices actually fall that year.
    assert stress.macro.hpi_index[shock_year_index] < stress.macro.hpi_index[shock_year_index - 1]
    # And rent growth is held flat for the two years following.
    for offset in range(a.rent_shock_years):
        assert stress.macro.rent_rate[shock_year_index + offset] == 0.0


def test_invariant_check_can_fail():
    """The invariant guard is real: corrupt the state and it must complain."""
    from engine.model import _check_invariants

    result = run("base", check=False)
    result.state.statements.balance_check[10] = 1.0
    with pytest.raises(ModelError, match="balance sheet does not balance"):
        _check_invariants(result.state, result.n_years, len(result.state.monthly.month))


# ------------------------------------------------------- property gifts ---

def test_gifts_wait_for_the_start_year():
    """Nothing arrives before the Commons has earned it."""
    r = run("base")
    a = r.assumptions
    for i in range(a.gift_property_start_yr - 1):
        assert r.state.growth.properties_gifted[i] == 0, f"a gift arrived in year {i + 1}"
    assert sum(r.state.growth.properties_gifted) > 0, "no gift ever arrived"


def test_gifts_are_whole_houses_arriving_lumpily():
    """
    A rate of 0.5 means one house every other year, not half a house a year.

    Fractional houses would be nonsense in themselves and would also break the
    whole-number portfolio counts the rest of the model relies on.
    """
    r = run("base")
    gifted = r.state.growth.properties_gifted
    assert all(float(g).is_integer() for g in gifted), "a fractional house was gifted"

    a = r.assumptions
    span = len(gifted) - (a.gift_property_start_yr - 1)
    expected = int(span * a.gift_property_rate)
    assert abs(sum(gifted) - expected) <= 1, (
        f"gifted {sum(gifted)} houses over {span} years at {a.gift_property_rate}/yr; "
        f"expected about {expected}"
    )


def test_stress_never_receives_a_gift():
    """Gifts are earned; the stress case is where the case is never made."""
    r = run("stress")
    assert sum(r.state.growth.properties_gifted) == 0


def test_gifted_property_is_income_and_asset_but_never_cash():
    """
    The accounting that makes a gift honest.

    A donated house has to be recognised as income, or it appears as an asset
    with nothing on the other side and the balance sheet stops balancing. But
    it must not touch cash. Getting one of those right and not the other is the
    easy mistake, so both are asserted.
    """
    r = run("base")
    A, f, g = r.state.assets, r.state.statements, r.state.growth

    year = next(i for i, n in enumerate(g.properties_gifted) if n > 0)

    assert A.gift_property_value[year] > 0
    # Recognised in income...
    assert f.gifts_and_bequests[year] >= A.gift_property_value[year]
    # ...and removed again from the cash-flow statement.
    assert f.cf_less_noncash_gifts[year] == pytest.approx(-A.gift_property_value[year])
    # Never counted as money paid for property.
    assert f.cf_property_purchases[year] == pytest.approx(-A.purchase_price[year])
    assert A.purchase_price[year] == pytest.approx(
        g.properties_acquired[year] * r.macro.avg_price[year]
    )


def test_gifts_do_not_consume_funding_capacity():
    """
    A house someone gives you is not something you can afford or not afford.

    Gifts must bypass the affordability test entirely -- if they were netted
    against funding capacity they would displace purchases rather than add to
    them, and the whole point would be lost.
    """
    from engine.assumptions import load

    without = load("base")
    without.values["gift_property_start_yr"] = 0
    withgifts = load("base")

    a, b = run(without), run(withgifts)
    assert sum(b.state.growth.properties_gifted) > 0

    # In the first gift year the two runs are otherwise identical, so this
    # isolates the question cleanly: the gift must not displace a purchase.
    first = next(i for i, n in enumerate(b.state.growth.properties_gifted) if n > 0)
    assert b.state.growth.properties_acquired[first] == a.state.growth.properties_acquired[first]
    assert b.state.growth.properties_added[first] > a.state.growth.properties_added[first]

    # Beyond that year the trajectories legitimately diverge -- a larger
    # portfolio carries more admin and sinking-fund cost, and gifted houses
    # need retrofitting -- so purchases in any single later year may be higher
    # or lower. What must hold is the outcome.
    assert b.state.growth.portfolio_closing[-1] > a.state.growth.portfolio_closing[-1]
    assert b.state.statements.net_assets[-1] > a.state.statements.net_assets[-1]

# ------------------------------------------------------ tontine release ---

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_release_has_no_cliff(scenario):
    """
    Discharge must be gradual, not a step.

    The first version of the run-off rule released straight down to its
    coverage target the moment it was allowed to, discharging sixteen years of
    accumulated over-coverage in one year -- £9.3m at year 25 against £150k a
    year afterwards. No lender or registrar would recognise that as a
    discharge, and it is not "tracking" anything.

    Two things are asserted, because either alone can be satisfied by a wrong
    rule: no single year may dominate the whole discharge, and no year may
    dwarf the year before it.
    """
    from engine.assumptions import load

    a = load(scenario)
    a.values["pf_release_mode"] = "runoff"
    c = run(a).state.capital

    releases = [-v for v in c.tf_release if v < 0]
    if not releases:
        return  # scenario never draws Tontine capital

    peak = max(c.tf_closing)
    assert max(releases) < 0.40 * peak, (
        f"a single year discharges {max(releases) / peak:.0%} of the peak balance"
    )

    for prev, nxt in zip(releases, releases[1:]):
        if prev > 1000:
            assert nxt < 3 * prev, (
                f"release jumps from {prev:,.0f} to {nxt:,.0f} year on year"
            )


def test_release_never_fully_discharges_while_liability_remains():
    """
    The last-survivor floor, which is the point of the rule.

    While technical provisions are positive there is someone left to be paid,
    so some security must remain. This is structural rather than a threshold:
    the target is a multiple of a liability that is only zero once nobody is
    left.
    """
    from engine.assumptions import load
    from engine.capital_debt import _fund_year
    from engine.tontine_runoff import load_curve

    a = load("base")
    a.values["pf_release_mode"] = "runoff"
    r = run(a)
    c, curve = r.state.capital, load_curve()
    first = next(i for i, d in enumerate(c.tf_drawdown) if d > 0)

    for i in range(first, r.n_years):
        tp = curve.tp_at(i - first)
        if tp > 1e-6:
            assert c.tf_closing[i] > 0, (
                f"year {i + 1}: charge fully discharged while a liability remains"
            )


# -------------------------------------------------------- excel semantics ---

def test_excel_round_is_half_away_from_zero():
    """Python's banker's rounding would change the acquisition count."""
    assert excel_round(0.5) == 1        # Python's round() gives 0
    assert excel_round(1.5) == 2
    assert excel_round(2.5) == 3        # Python's round() gives 2
    assert excel_round(-0.5) == -1
    assert excel_round(2.675, 2) == pytest.approx(2.68)


def test_excel_int_floors_toward_negative_infinity():
    assert excel_int(1.9) == 1
    assert excel_int(-1.1) == -2        # Python's int() gives -1
