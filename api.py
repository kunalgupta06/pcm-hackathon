"""
Demo function for the developer (task 14). Reads results/ written by run_all.py, so it is instant.

    from api import best_option
    best_option("Phoenix", "TOU+demand")                                  # residential tank cost
    best_option("Phoenix", "TOU+demand", "commercial")                    # commercial tank cost
    best_option("Phoenix", "TOU+demand", source="defaults")               # after python run_all.py --source defaults
"""
import os

import numpy as np
import pandas as pd

import case1_wall as W
import common as C

_CACHE = {}


def _load(source=None):
    source = source or C.DEFAULT_SOURCE
    if source not in _CACHE:
        res = C.out_dirs(source)[0]
        _CACHE[source] = (C.load_inputs(source=source), pd.read_csv(os.path.join(res, "case1_designs.csv")),
                          pd.read_csv(os.path.join(res, "case2_runs.csv")))
    return _CACHE[source]


def options(source=None):
    cfg, c1, _ = _load(source)
    return dict(cities=sorted(c1.city.unique()), tariffs=list(cfg["tariffs"]), sources=list(C.SOURCES))


def best_option(city, tariff, building="residential", source=None):
    """Compare four choices on 20-year net savings vs the baseline house (fixed thermostat), priced with the sourced
    2026 costs: extra insulation, passive PCM wall ($/m2), smart control alone, PCM battery (installed $/kWh_th for
    `building` = "residential" or "commercial", plus O&M; best controller and size)."""
    cfg, c1, c2 = _load(source)
    if building not in C.BUILDINGS:
        raise ValueError(f"building must be one of {C.BUILDINGS}")
    h, c = cfg["house"], cfg["costs"]
    g = c1[(c1.city == city) & (c1.tariff == tariff)]
    if g.empty:
        raise ValueError(f"No results for {city}/{tariff}. Options: {options(source)}")
    base = g[(g.kind == "insulation") & (g.extra_ins_mm == 0)].npv_running_usd.iloc[0]

    ins = g[g.kind == "insulation"].copy()
    ins["cost"] = ins.extra_ins_mm / 1000 * h["wall_area_m2"] * c["insulation_usd_per_m3"]
    ins["net"] = base - ins.npv_running_usd - ins.cost
    bi = ins.loc[ins.net.idxmax()]

    pcm = g[g.kind == "pcm"].copy()
    pcm["cost"] = C.wall_pcm_cost(cfg, pcm.pcm_mm)
    pcm["net"] = base - pcm.npv_running_usd - pcm.cost
    bp = pcm.loc[pcm.net.idxmax()]

    d = c2[(c2.city == city) & (c2.tariff == tariff)].copy()
    fixed0 = d[(d.controller == "fixed") & (d.size_kWh == 0)].npv_usd.iloc[0]
    s0 = d[(d.controller == "smart") & (d.size_kWh == 0)].iloc[0]
    tanks = d[d.size_kWh > 0].copy()
    tanks["net"] = fixed0 - tanks.npv_usd - tanks[f"tank_capex_{building}_usd"] - tanks[f"tank_om_pv_{building}_usd"]
    sb = tanks.loc[tanks.net.idxmax()]
    s0_net = fixed0 - s0.npv_usd

    choices = {
        "Extra insulation": dict(net_savings_usd=bi.net, detail=f"+{bi.extra_ins_mm:.0f} mm XPS"),
        "Passive PCM wall": dict(net_savings_usd=bp.net, detail=f"{bp.pcm_mm:.0f} mm PCM melting at {bp.Tm:.0f} °C, "
                                                                f"${bp.cost:,.0f} installed"),
        "Smart control only": dict(net_savings_usd=s0_net, detail="pre-cool/pre-heat with the house's own mass"),
        "PCM battery": dict(net_savings_usd=sb.net, detail=f"{sb.controller} control + {sb.size_kWh:.0f} kWh tank, "
                                                           f"${sb[f'tank_capex_{building}_usd']:,.0f} installed ({building})"),
    }
    winner = max(choices, key=lambda k: choices[k]["net_savings_usd"])
    t = C.tariff_for(cfg, city, tariff)
    return dict(
        source=cfg["source"], city=city, tariff=tariff, tariff_id=t["id"], tariff_name=t["name"], tariff_status=t["status"],
        building=building, tank_cost_usd_per_kWh_th=cfg["tank_cost"][building][0],
        winner=winner if choices[winner]["net_savings_usd"] > 0 else "Do nothing",
        options={k: dict(net_savings_usd=round(float(v["net_savings_usd"]), 0), detail=v["detail"]) for k, v in choices.items()},
        pcm_battery_adds_over_smart_control_usd=round(float(sb.net - s0_net), 0),
        pcm_worth_it=bool(sb.net > s0_net or bp.net > bi.net),
        note="20-year net savings (present value) vs the baseline house (fixed thermostat). Costs: "
             "energy/03_inputs/costs_sourced_2026.csv (see results/sources.csv); house, wall and tank physics are "
             "still placeholders.")


if __name__ == "__main__":
    import json
    for b in C.BUILDINGS:
        print(json.dumps(best_option("Phoenix", "TOU+demand", b), indent=1, default=float))
