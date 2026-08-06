# Scenarios

One line per scenario, saying what question it answers.

| Scenario | File | The question it answers |
|---|---|---|
| **Base** | [`base.yaml`](base.yaml) | "On assumptions we'd defend to a funder, what does the Commons look like over 50 years?" |
| **Optimistic** | [`optimistic.yaml`](optimistic.yaml) | "If fundraising, the housing market and our delivery capacity all run in our favour, how much land can the Commons hold?" |
| **Stress** | [`stress.yaml`](stress.yaml) | "Can the Commons survive a bad decade — high inflation, empty properties, collapsed share appetite and a housing crash — without breaching covenants or running out of cash?" |

## How these files work

`base.yaml` holds the **full** parameter set — all 72 inputs, grouped under the
same section headings as the `Control & Parameters` sheet in the original
workbook, and keyed by the same names the workbook's own formulas use.

`optimistic.yaml` and `stress.yaml` hold **only the values that differ from
Base**. The model loads Base, then applies the scenario file on top. This
mirrors the workbook, where many Optimistic/Stress cells are `=$E9`-style
formulas inheriting the Base value rather than repeating it.

The practical consequence, and the reason it is done this way:

```bash
diff assumptions/base.yaml assumptions/stress.yaml
```

A diff between two scenario files *is* the scenario definition. Nothing is
hidden in a column of near-identical numbers.

## Editing

Change a number here, re-run the model, and every output — the explorer page,
the Excel workbook, the CSVs — updates from it:

```bash
python -m export.build_all
```

Two rules worth knowing:

- **Percentages are fractions.** `0.025` is 2.5%. Writing `2.5` would mean 250%.
- **Don't add a key to a scenario file just to restate the Base value.** If it
  matches Base, leave it out — that is what keeps the diff meaningful. The one
  exception is when restating it documents an intentional decision, in which
  case say so in a comment (see `hpi_shock_pct` in `optimistic.yaml`).

## Derived values

`pf_coupon_spread` — the implied SLC coupon — is **not** an input. The model
derives it as:

```
pf_coupon_spread = pf_investor_rate + pf_fund_op_margin + pf_fund_reg_charge
```

exactly as the workbook derives it with `=SUM(E14:E16)`. To change the coupon,
change one of the three components.

## Structural changes

These files only hold *inputs*. Anything that changes how the model **works** —
a refinancing waterfall, new redemption logic, an extra capital layer — is a
mechanics change: it belongs on a `structure/<hypothesis>` branch with an entry
in [`../MODEL_LOG.md`](../MODEL_LOG.md), not in a YAML file.
