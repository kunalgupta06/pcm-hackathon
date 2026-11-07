"""
Post-processing only (no simulation): adds two conservative variants to the headline and small-office tables.

    python postprocess.py        # after run_all.py and compare_baseline.py

For every option (residential battery, commercial battery, passive PCM wall; office: commercial battery):
  base           : net savings as computed by run_all.py
  no_hp_credit   : energy + demand savings - installed cost - O&M   (retrofit: no smaller heat pump is bought)
  peak_corrected : base, with the heat-pump-size and demand-charge savings scaled by v2 peak / our peak
                   cooling electricity for that city (results/baseline_v2_hourly_check.csv, v2's 2,000 ft2
                   reference house on the same weather; our model overstates peaks, see README)

Adds columns <option>_net_no_hp_credit_usd and <option>_net_peak_corrected_usd to results/headline.csv and
results/small_office_headline.csv (rewritten in place; re-running is idempotent) and prints the base scenario.
"""
import os

import pandas as pd

import common as C

R = os.path.join(C.HERE, "results")


def peak_factors():
    hc = pd.read_csv(os.path.join(R, "baseline_v2_hourly_check.csv"))
    return dict(zip(hc.city, hc.v2_peak_cool_kW / hc.ours_peak_cool_kW))


def wall_demand_savings(cfg, head):
    """PV of demand-charge savings of the chosen PCM wall design vs the baseline wall (from case1_designs.csv)."""
    c1 = pd.read_csv(os.path.join(R, "case1_designs.csv"))
    AF = C.annuity_factor(cfg)
    out = []
    for r in head.itertuples():
        g = c1[(c1.city == r.city) & (c1.tariff == r.tariff)]
        base = g[(g.kind == "insulation") & (g.extra_ins_mm == 0)].iloc[0]
        mm, tm = r.wall_design.split(" mm @ ")
        d = g[(g.kind == "pcm") & (g.pcm_mm == float(mm)) & (g.Tm == float(tm.split()[0]))].iloc[0]
        out.append(AF * (base.demand_usd - d.demand_usd))
    return out


def add_columns(df, buildings, f, wall_dem=None):
    k = df.city.map(f)
    df["peak_factor_v2_over_ours"] = k
    for b in buildings:
        bill, dem = df[f"battery_{b}_energy_bill_savings_usd"], df[f"battery_{b}_demand_savings_usd"]
        hp, capex, om = df[f"battery_{b}_hp_savings_usd"], df[f"battery_{b}_tank_capex_usd"], df[f"battery_{b}_tank_om_usd"]
        df[f"battery_{b}_net_no_hp_credit_usd"] = bill - capex - om
        df[f"battery_{b}_net_peak_corrected_usd"] = (bill - dem) + k * dem + k * hp - capex - om
    if wall_dem is not None:
        df["wall_demand_savings_usd"] = wall_dem
        bill, hp, cost = df.wall_energy_bill_savings_usd, df.wall_hp_savings_usd, df.wall_cost_usd
        df["wall_net_no_hp_credit_usd"] = bill - cost
        df["wall_net_peak_corrected_usd"] = (bill - df.wall_demand_savings_usd) + k * df.wall_demand_savings_usd + k * hp - cost
    return df


def triple(df, prefix, base_col):
    return pd.DataFrame({"base": df[base_col], "no HP credit": df[f"{prefix}_net_no_hp_credit_usd"],
                         "peak-corr.": df[f"{prefix}_net_peak_corrected_usd"]}).round(0).astype(int)


def main():
    cfg = C.load_inputs()
    f = peak_factors()
    pd.set_option("display.width", 250)

    hp = os.path.join(R, "headline.csv")
    head = pd.read_csv(hp)
    head = add_columns(head, C.BUILDINGS, f, wall_demand_savings(cfg, head))
    head.to_csv(hp, index=False)
    base = head[head.scenario == "base"].reset_index(drop=True)
    t = pd.concat({"": base[["city", "tariff_id"]],
                   "Residential battery": triple(base, "battery_residential", "battery_residential_net_savings_usd"),
                   "Commercial battery": triple(base, "battery_commercial", "battery_commercial_net_savings_usd"),
                   "Passive PCM wall": triple(base, "wall", "wall_net_savings_usd")}, axis=1)
    t[("", "peak factor")] = base.peak_factor_v2_over_ours.round(2)
    print("HEADLINE: net 20-year savings ($, present value; > 0 = pays), base scenario.\n"
          "base = as modelled | no HP credit = retrofit, no smaller heat pump bought | "
          "peak-corr. = HP-size and demand savings x (v2 peak / our peak cooling)")
    print(t.to_string(index=False))

    op = os.path.join(R, "small_office_headline.csv")
    if os.path.exists(op):
        off = pd.read_csv(op)
        off = add_columns(off, ("commercial",), f)
        off.to_csv(op, index=False)
        ob = off[off.scenario == "base"].reset_index(drop=True)
        t2 = pd.concat({"": ob[["city", "tariff_id"]],
                        "Commercial battery (office)": triple(ob, "battery_commercial",
                                                              "battery_commercial_net_savings_usd")}, axis=1)
        t2[("", "option")] = ob.battery_commercial_option
        t2[("", "peak factor")] = ob.peak_factor_v2_over_ours.round(2)
        print("\nSMALL OFFICE (assumed preset; TOU+demand stand-in tariff), commercial tank $100/kWh-th + O&M.")
        print(t2.to_string(index=False))
    print("\nPeak factors (v2 / ours, peak hourly cooling electricity): "
          + ", ".join(f"{c} {v:.2f}" for c, v in f.items()))


if __name__ == "__main__":
    main()
