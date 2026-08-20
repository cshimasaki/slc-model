"""
The funding mix: what proportion of each purchase comes from where.

Before this, the mix was an accident. Community shares issued a fixed amount
each year (£250k, inherited from the V2.1 spreadsheet), gifts arrived on their
own schedule, and the Tontine drew whatever was left. Whatever mix came out the
other end was an arithmetic consequence of those inputs -- on Base it landed at
17% Tontine, 56% shares, 27% gifts, and none of that was chosen.

Now the mix is a stated intention that changes over time. The Tontine leads
early, because that is where retired people's capital is and because a new
organisation has no track record to sell community shares against. As the
balance sheet and the evidence base grow, shares and Rent Credit Obligations
take over.

  IMPORTANT: the weights are judgement, not evidence. They were described as
  "just numbers in my head... it feels like a fairly plausible ratio", and they
  should be read that way until there is fundraising experience to replace
  them. They are among the most consequential and least evidenced inputs in the
  model.

Gifts are deliberately NOT targeted. You cannot decide to receive a gift, so
they arrive on their own terms and simply reduce what the other sources need to
find. The weight below is an expectation of what they will contribute, not an
instruction.

The Tontine takes the slack. If shares fall short of their target, or gifts do
not arrive, the Tontine covers the difference -- subject to its own LTV
headroom and raise cap. That matches the stated design: the ceiling on the
Tontine is viability, not a quota.
"""

from __future__ import annotations


def weights_for_year(a, year: int) -> tuple[float, float, float]:
    """
    Target shares of the funding requirement in a given model year.

    Returns (tontine, community shares, other). "Other" covers gifts and, in
    due course, Rent Credit Obligations.

    The mix glides linearly from its opening weights to its closing weights
    over `mix_transition_years`, then holds. Linear is a placeholder: the real
    trajectory depends on how fast trust actually accumulates, which nobody
    can currently forecast. It is a parameter so it can be replaced by
    something better rather than argued about.
    """
    start_t = getattr(a, "mix_tontine_start", 1.0)
    start_s = getattr(a, "mix_shares_start", 0.0)
    end_t = getattr(a, "mix_tontine_end", start_t)
    end_s = getattr(a, "mix_shares_end", start_s)
    years = max(1, getattr(a, "mix_transition_years", 1))

    progress = min(1.0, max(0.0, (year - 1) / years))
    tontine = start_t + (end_t - start_t) * progress
    shares = start_s + (end_s - start_s) * progress

    # Whatever is left is expected from gifts and RCOs. Never negative.
    other = max(0.0, 1.0 - tontine - shares)
    return tontine, shares, other
