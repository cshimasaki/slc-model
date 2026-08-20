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
    # Voids are low by design, not by optimism: a waiting list of pre-selected
    # tenants and security of tenure mean a re-let is the week the keys change
    # hands. 5% is the ceiling even in Stress, where the pressure is put on
    # retrofit cost instead -- that is where the genuine uncertainty is.
    assert base.void_rate == 0.03 and stress.void_rate == 0.05
    assert stress.retrofit_cost > base.retrofit_cost
    assert base.cpi_general == 0.029 and stress.cpi_general == 0.045
    assert base.hpi_shock_year == 0 and stress.hpi_shock_year == 5
    # Stress reverses the sign of the house-price premium: Base has houses
    # growing slower than prices generally (the ONS position in Aug 2026),
    # Stress has them running a point ahead again.
    assert base.hpi_premium == -0.009 and stress.hpi_premium == 0.01
    # ...and inherits everything else, including the shock's own size.
    assert stress.hpi_shock_pct == base.hpi_shock_pct == -0.20
    assert stress.rent_shock_rate == base.rent_shock_rate == 0.0
    assert stress.pf_ltv_limit == base.pf_ltv_limit
    # Rent inflation is NOT worsened in Stress: it stays at Base's 3.7% while
    # CPI goes to 4.5%. The squeeze is the gap, not a rent collapse.
    assert stress.rent_inflation == base.rent_inflation == 0.037


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
    """
    The model never sells, and the ceiling caps what it BUYS.

    The ceiling is the carrying capacity of the logistic growth curve -- how
    many properties the organisation can find, buy and take on. Gifted houses
    do not come through that process, and nobody declines a donated home
    because a growth parameter says the portfolio is full. So the ceiling is
    tested against purchases, not against the total.

    Without that distinction the assertion fails once gifts arrive while the
    portfolio sits at its ceiling -- Optimistic reaches 252 against a ceiling
    of 250, entirely from two gifted houses.
    """
    result = run(scenario)
    g = result.state.growth
    closing = g.portfolio_closing

    assert all(b >= a for a, b in zip(closing, closing[1:])), "portfolio shrank"

    cumulative_gifts = 0.0
    for i, total in enumerate(closing):
        cumulative_gifts += g.properties_gifted[i]
        purchased = total - cumulative_gifts
        assert purchased <= result.assumptions.logistic_ceiling + 1e-9, (
            f"year {i + 1}: bought {purchased:.0f} properties against a ceiling "
            f"of {result.assumptions.logistic_ceiling}"
        )


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
    a.values["pf_release_mode"] = "survivorship"
    c = run(a).state.capital

    releases = [-v for v in c.tf_release if v < 0]
    if not releases:
        return  # scenario never draws Tontine capital

    peak = max(c.tf_closing)
    assert max(releases) < 0.40 * peak, (
        f"a single year discharges {max(releases) / peak:.0%} of the peak balance"
    )

    # And no year may discharge a large share of the balance standing at the
    # time. Measuring against the balance rather than against the previous
    # year's release is what distinguishes a cliff from a ramp: releases climb
    # steeply early on as successive cohorts leave lock-up, which is correct
    # and would trip a year-on-year ratio test for no good reason.
    #
    # Years where almost nothing is left are skipped: a 105-year-old really
    # does have a very high annual mortality rate, so a big proportional
    # release on a trivial balance is the model working, not failing.
    for i, closing in enumerate(c.tf_closing):
        pre_release = c.tf_indexed_opening[i] + c.tf_drawdown[i]
        if pre_release <= 0.01 * peak:
            continue
        share = -c.tf_release[i] / pre_release
        assert share < 0.40, (
            f"year {i + 1} discharges {share:.0%} of the balance standing at the time"
        )


def test_lockup_blocks_early_release():
    """No charge can be released inside its minimum term."""
    from engine.assumptions import load

    a = load("base")
    a.values["pf_release_mode"] = "survivorship"
    r = run(a)
    c = r.state.capital
    first_draw = next(i for i, d in enumerate(c.tf_drawdown) if d > 0)

    # The release is a reconciling residual, so a genuine zero lands on
    # floating-point dust rather than exactly 0.0. A fraction of a penny is
    # noise; anything a person could see is not.
    for i in range(first_draw, first_draw + a.values["pf_lockup_years"]):
        assert abs(c.tf_release[i]) < 0.01, (
            f"a charge was released in year {i + 1}, inside the "
            f"{a.values['pf_lockup_years']}-year lock-up: {c.tf_release[i]:,.6f}"
        )


def test_mortality_gain_split_decides_who_benefits():
    """
    The undecided lever, pinned so its meaning cannot drift.

    At 1.0 a dead investor's charge is extinguished and SLC's liability falls.
    At 0.0 nothing is extinguished -- the entitlement passes to surviving
    investors, so SLC owes exactly as much as before and pays exactly as much
    interest. The difference between those two runs is the whole value of the
    survivorship benefit, and which way it flows is a design decision, not a
    modelling one.
    """
    from engine.assumptions import load

    def run_with(share):
        a = load("base")
        a.values["pf_release_mode"] = "survivorship"
        a.values["pf_mortality_gain_to_commons"] = share
        return run(a, check=False)

    to_commons, to_investors = run_with(1.0), run_with(0.0)

    # All to the Commons: the charge runs off.
    assert to_commons.state.capital.tf_closing[-1] < to_commons.state.capital.tf_closing[9]
    # All to investors: nothing is ever released, so the balance only indexes
    # up. The release is computed as a reconciling residual, so it lands on
    # floating-point dust rather than a clean zero.
    assert all(abs(v) < 1e-6 for v in to_investors.state.capital.tf_release)
    assert to_investors.state.capital.tf_closing[-1] > to_investors.state.capital.tf_closing[9]

    # And SLC pays materially more interest when the gain goes to investors.
    assert -sum(to_investors.state.capital.tf_interest) > -sum(to_commons.state.capital.tf_interest)


def test_release_never_fully_discharges_while_liability_remains():
    """
    The last-survivor floor, which is the point of the rule.

    While technical provisions are positive there is someone left to be paid,
    so some security must remain. This is structural rather than a threshold:
    the target is a multiple of a liability that is only zero once nobody is
    left.
    """
    from engine.assumptions import load
    from engine.tontine_runoff import load_curve

    a = load("base")
    a.values["pf_release_mode"] = "survivorship"
    r = run(a)
    c, curve = r.state.capital, load_curve()
    first = next(i for i, d in enumerate(c.tf_drawdown) if d > 0)

    for i in range(first, r.n_years):
        tp = curve.tp_at(i - first)
        if tp > 1e-6:
            assert c.tf_closing[i] > 0, (
                f"year {i + 1}: charge fully discharged while a liability remains"
            )


def test_coupon_basis_delivers_the_designed_investor_return():
    """
    The investor must receive the real return the design specifies.

    The principal is CPI-uplifted and never repaid, so the investor's entire
    return is the coupon paid on a base that already grows with inflation.
    Their inflation protection is therefore delivered by the indexation, and
    the coupon should be the real spread alone.

    The workbook added CPI to the rate as well, handing the investor CPI twice
    and doubling their real return. This test is what stops that returning.
    """
    from engine.assumptions import load

    a = load("base")
    assert a.pf_coupon_basis == "real"
    r = run(a)
    m, c = r.macro, r.state.capital

    # Under "real" the coupon is the spread, flat, whatever CPI does.
    for i, rate in enumerate(c.tf_coupon_rate):
        assert rate == pytest.approx(a.pf_coupon_spread), f"year {i + 1}"

    # And the real return to the investor is the designed annuity rate.
    real_return = a.pf_coupon_spread - a.pf_fund_op_margin - a.pf_fund_reg_charge
    assert real_return == pytest.approx(a.pf_investor_rate)

    # The workbook basis pays strictly more, and CPI more.
    b = load("base")
    b.values["pf_coupon_basis"] = "nominal"
    nominal = run(b)
    assert nominal.state.capital.tf_coupon_rate[0] == pytest.approx(
        a.pf_coupon_spread + m.cpi_rate[0]
    )
    assert -sum(nominal.state.capital.tf_interest) > -sum(c.tf_interest)


def test_every_input_file_is_tracked_by_git():
    """
    A file the model needs must be in the repo, not just on someone's disk.

    This has now bitten twice. A broad `*.xlsx` rule swallowed the source
    workbook, and a broad `*.csv` rule swallowed the Tontine run-off curve --
    both source data sitting behind extension rules aimed at generated
    exports. Locally everything works; a fresh clone fails, and the error
    surfaces far from its cause.

    Rather than list files, this asks git directly whether anything the engine
    loads is being ignored.
    """
    import subprocess

    inputs = [
        os.path.join("assumptions", "base.yaml"),
        os.path.join("assumptions", "optimistic.yaml"),
        os.path.join("assumptions", "stress.yaml"),
        os.path.join("assumptions", "labels.yaml"),
        os.path.join("assumptions", "tontine_runoff.csv"),
        os.path.join("validation", "port_reference", "base.yaml"),
    ]

    try:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        pytest.skip("git not available")

    tracked = {line.replace("/", os.sep) for line in tracked if line}
    for path in inputs:
        assert os.path.exists(os.path.join(ROOT, path)), f"missing input file: {path}"
        assert path in tracked, (
            f"{path} exists locally but git is not tracking it -- a fresh clone "
            f"would fail. Check .gitignore for a broad extension rule."
        )


# --------------------------------------------------- operating efficiency ---

def test_efficiency_curve_shape():
    """Falls with scale, monotonically, and stops at the floor."""
    from engine.efficiency import scale_factor

    rate, floor = 0.92, 0.65
    factors = [scale_factor(n, rate, floor) for n in (1, 2, 5, 10, 25, 50, 200)]

    assert factors[0] == 1.0, "a single property has no scale to exploit"
    assert all(b <= a for a, b in zip(factors, factors[1:])), "cost per property rose with scale"
    assert min(factors) >= floor
    # Each doubling takes the stated proportion off, until the floor bites.
    assert scale_factor(2, rate, 0.0) == pytest.approx(rate)
    assert scale_factor(4, rate, 0.0) == pytest.approx(rate ** 2)


def test_efficiency_can_be_switched_off():
    """A learning rate of 1.0 means no scale economies at all."""
    from engine.efficiency import scale_factor

    assert all(scale_factor(n, 1.0, 0.65) == 1.0 for n in (1, 10, 200))


def test_efficiency_lowers_running_costs_but_not_the_sinking_fund():
    """
    The saving applies to running costs, never to the provision.

    A sinking fund contribution is money set aside against future capital
    works. Buying scaffolding more cheaply does not mean the roof needs
    replacing less often, so scaling the provision with estate size would
    quietly under-provision a growing portfolio.

    Property-level running costs now sit inside the 16.67% of rent rather than
    in admin_variable and maint_per_prop, which were double-counting them. So
    the saving is tested where it now lives: the share of rent the Commons
    keeps, which rises as the estate grows. admin_variable is legitimately zero.
    """
    from engine.assumptions import load

    off = load("base")
    off.values["lc_cost_learning_rate"] = 1.0
    on = load("base")

    a, b = run(off), run(on)

    # Running costs fall -- the Commons keeps more of each pound of rent...
    assert b.state.assets.lc_share_effective[-1] > a.state.assets.lc_share_effective[-1]
    assert a.state.assets.lc_share_effective[-1] == pytest.approx(1 - 2 / 12), (
        "with learning switched off the share should stay at its small-scale level"
    )
    # ...the provision does not, at equal portfolio size.
    for i, (x, y) in enumerate(
        zip(a.state.growth.portfolio_closing, b.state.growth.portfolio_closing)
    ):
        if x == y:
            assert a.state.assets.sinking_contribution[i] == pytest.approx(
                b.state.assets.sinking_contribution[i]
            ), f"year {i + 1}: the sinking fund provision was scaled by efficiency"


def test_stress_assumes_no_efficiency_gain():
    """Stress is the world where the savings never materialise."""
    from engine.assumptions import load

    assert load("stress").opex_learning_rate == 1.0


# ------------------------------------------------------- interest cover ---

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_cover_measures_are_ordered(scenario):
    """
    All-income >= cash >= rent-only, in every year, by construction.

    Each strips out strictly more than the one before: cash removes donated
    property, rent-only removes every gift. If that ordering ever inverted it
    would mean a cover measure was including something it claims to exclude.
    """
    c = run(scenario).state.capital
    for i, (allc, cash, rent) in enumerate(
        zip(c.dscr, c.cash_interest_cover, c.rent_only_cover)
    ):
        if not isinstance(allc, (int, float)):
            continue
        assert allc >= cash - 1e-9, f"year {i + 1}: all-income cover below cash cover"
        assert cash >= rent - 1e-9, f"year {i + 1}: cash cover below rent-only cover"


def test_donated_property_lifts_all_income_cover_but_not_cash():
    """
    The reason cash cover exists.

    A gifted house is income at market value, so it flatters the headline
    ratio. It cannot be used to pay interest, so it must not flatter the
    covenant test.
    """
    r = run("base")
    c, A = r.state.capital, r.state.assets

    gift_years = [i for i, v in enumerate(A.gift_property_value) if v > 0
                  and isinstance(c.dscr[i], (int, float))]
    assert gift_years, "no property gift arrived, so this test proves nothing"

    i = gift_years[0]
    assert c.dscr[i] > c.cash_interest_cover[i], (
        "a donated house should lift all-income cover above cash cover"
    )


def test_covenant_thresholds_are_parameters_not_hardcoded():
    """Self-imposed covenants must be visible and editable, not buried."""
    a = load("base")
    assert a.cov_cash_cover_min > 0
    assert a.cov_rent_only_min > 0
    assert 1 <= a.cov_rent_only_by_year <= 50


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


def test_stock_mix_blends_by_capital_not_by_averaging_yields():
    """
    The blended yield is total rent over total price, not the mean of yields.

    Averaging each type's yield would weight a GBP 166,000 flat equally with a
    GBP 342,000 semi and overstate what the portfolio earns -- the flat is the
    higher-yielding one, so the error flatters.
    """
    from engine import stock

    types = [
        {"name": "cheap, high yield", "share": 0.5, "price": 100_000, "rent_pcm": 1_000},
        {"name": "dear, low yield", "share": 0.5, "price": 300_000, "rent_pcm": 1_000},
    ]
    price, yld = stock.blended(types)

    assert price == pytest.approx(200_000)
    # Half the houses cost 100k and half cost 300k, all letting for 12k a year:
    # 12k of rent against 200k of capital, so 6.0%.
    assert yld == pytest.approx(0.06)

    # Averaging the two yields instead gives 8.0% -- it credits the cheap
    # high-yielding house with half the portfolio's weight when it only absorbs
    # a quarter of its capital. That error always flatters.
    naive = (12_000 / 100_000 + 12_000 / 300_000) / 2
    assert naive == pytest.approx(0.08)
    assert yld < naive, "capital-weighting must not be replaced by averaging yields"


def test_stock_shares_must_sum_to_one():
    """A mix that does not sum to 1.0 is a typo, not something to normalise."""
    from engine import stock

    types = [
        {"name": "a", "share": 0.5, "price": 200_000, "rent_pcm": 900},
        {"name": "b", "share": 0.3, "price": 200_000, "rent_pcm": 900},
    ]
    with pytest.raises(stock.StockError, match="sum to 0.8"):
        stock.blended(types)


def test_stock_mix_drives_price_and_yield_in_every_scenario():
    """avg_price and gross_yield are outputs of the mix, not free inputs."""
    from engine import stock
    from engine.assumptions import load

    for name in ("base", "optimistic", "stress"):
        a = load(name)
        price, yld = stock.blended(a.stock_types)
        assert a.avg_price == pytest.approx(price)
        assert a.gross_yield == pytest.approx(yld)

    # Optimistic buys better stock, Stress is pushed into worse -- and neither
    # moves rent, which is the point: the yield spread is an acquisition
    # decision, not a tenant one.
    assert load("optimistic").gross_yield > load("base").gross_yield
    assert load("stress").gross_yield < load("base").gross_yield


def test_same_rent_dearer_house_is_a_worse_asset():
    """
    A 3-bed semi and a 3-bed terrace let for the same money; the semi costs
    more. The model must show that as a lower yield, since it is the whole
    reason stock selection matters.
    """
    from engine import stock

    terrace = [{"name": "terrace", "share": 1.0, "price": 287_000, "rent_pcm": 1176}]
    semi = [{"name": "semi", "share": 1.0, "price": 342_000, "rent_pcm": 1176}]

    _, y_terrace = stock.blended(terrace)
    _, y_semi = stock.blended(semi)
    assert y_terrace > y_semi
    assert y_terrace - y_semi == pytest.approx(0.0079, abs=1e-4)
