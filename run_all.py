"""
Run everything: case 1 (passive wall) and case 2 (PCM battery, 3 controllers), price them with the sourced 2026
costs (energy/03_inputs/costs_sourced_2026.csv), then write results/ tables and charts/ figures.

    python run_all.py                     # inputs.csv wins conflicts between the team sheets
    python run_all.py --source defaults   # PCM_Hackathon_Defaults.csv wins

Money is 20-year present value at the real discount rate. Heat-pump cost = marginal $/kW x (1 + replacement in
yr 15, discounted). Battery = installed $/kWh_th x size (residential or commercial) + O&M (fraction of capex per
year). Passive wall = installed $/m2 of wall (scaled by PCM mass). Heat-pump maintenance is the same for every
option and is left out.
"""
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import case1_wall as W
import case2_battery as B
import common as C

OUT, FIG, ENERGY_OUT = C.out_dirs(C.DEFAULT_SOURCE)          # reset in main() from --source
CTRL = ["fixed", "rule", "smart"]
BLD = C.BUILDINGS
plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})
RAW_COLS = ["city", "tariff", "tariff_id", "controller", "size_kWh", "mass_kg", "annual_kWh", "energy_usd",
            "demand_usd", "hp_kW", "peak_kW_max"]


# ---------------------------------------------------------------- case 2 runs and metrics
def run_case2(cfg, weather, controllers=CTRL):
    rows, keep = [], {}
    sizes = [0] + list(cfg["tank"]["sizes_kWh_thermal"])
    for city, (T_out, ghi) in weather.items():
        for tname in C.city_tariffs(cfg, city):
            t = C.tariff_for(cfg, city, tname)
            lat = B.latent_load(cfg, city, T_out, ghi, t)
            for ctrl in controllers:
                for s in sizes:
                    r = B.run_one(cfg, T_out, ghi, t, s, ctrl, lat=lat)
                    rows.append(dict(city=city, tariff=tname, tariff_id=t["id"], controller=ctrl, size_kWh=s,
                                     mass_kg=B.tank_params(cfg, s)["mass_kg"], annual_kWh=r["annual_kWh"],
                                     energy_usd=r["energy_usd"], demand_usd=r["demand_usd"], hp_kW=r["hp_kW"],
                                     peak_kW_max=r["peak_kW_max"]))
                    keep[(city, tname, ctrl, s)] = r
            print(f"  case 2: {city} / {tname} done ({', '.join(controllers)})", flush=True)
    return case2_metrics(cfg, pd.DataFrame(rows)), keep


def _value_split(cfg, ref, opt):
    """20-year value of opt vs ref: energy bills, demand charges, heat-pump size (incl. the yr-15 replacement)."""
    AF, hp = C.annuity_factor(cfg), cfg["heat_pump"]["capex_usd_per_kW_thermal"]
    return (AF * (ref.energy_usd - opt.energy_usd), AF * (ref.demand_usd - opt.demand_usd),
            hp * (ref.hp_kW - opt.hp_kW))


def case2_metrics(cfg, df, tank_cost=None, bld=BLD):
    """Each tank vs the SAME controller without a tank: value split, break-even installed cost, and net savings
    for each building's installed tank cost (capex + O&M)."""
    df = df[RAW_COLS].reset_index(drop=True)
    AF, hp = C.annuity_factor(cfg), cfg["heat_pump"]["capex_usd_per_kW_thermal"]
    tank_cost = tank_cost or {b: cfg["tank_cost"][b][0] for b in bld}
    df["hp_marginal_usd_per_kW"] = cfg["heat_pump"]["hp_marginal_usd_per_kW"]
    df["npv_usd"] = hp * df.hp_kW + AF * (df.energy_usd + df.demand_usd)       # operating + heat pump, no tank
    ref = df[df.size_kWh == 0].set_index(["city", "tariff", "controller"])
    ref = ref.loc[list(zip(df.city, df.tariff, df.controller))].reset_index(drop=True)
    e, d, h = _value_split(cfg, ref, df)
    df["energy_savings_pv_usd"], df["demand_savings_pv_usd"], df["hp_savings_usd"] = e, d, h
    df["savings_usd"] = e + d + h
    om_pv_per_usd = cfg["tank"]["om_fraction"] * AF
    # highest installed $/kWh_th at which the tank still pays, O&M included
    df["break_even_system_usd_per_kWh_th"] = np.where(
        df.size_kWh > 0, df.savings_usd / (df.size_kWh.replace(0, np.nan) * (1 + om_pv_per_usd)), np.nan)
    for b in bld:
        capex, om = C.tank_costs(cfg, df.size_kWh, tank_cost[b])
        df[f"tank_capex_{b}_usd"], df[f"tank_om_pv_{b}_usd"] = capex, om
        df[f"net_savings_{b}_usd"] = np.where(df.size_kWh > 0, df.savings_usd - capex - om, np.nan)
    return df


# ---------------------------------------------------------------- headline
def headline(cfg, res1, df2, scenario="base", tank_cost=None, bld=BLD):
    """Per city & tariff:
      battery: best PCM option (any controller, any tank size) vs smart control with no tank, net of the installed
               tank cost and O&M, for each building type;
      wall:    best PCM wall design vs the baseline wall house, net of the installed wall cost."""
    tank_cost = tank_cost or {b: cfg["tank_cost"][b][0] for b in bld}
    area = cfg["house"]["wall_area_m2"]
    om_pv_per_usd = cfg["tank"]["om_fraction"] * C.annuity_factor(cfg)
    rows = []
    for (city, tname), g in df2.groupby(["city", "tariff"], sort=False):
        g = g.reset_index(drop=True)
        ref = g[(g.controller == "smart") & (g.size_kWh == 0)].iloc[0]
        opt = g[g.size_kWh > 0].copy()
        opt["e"], opt["d"], opt["h"] = _value_split(cfg, ref, opt)
        opt["sav"] = opt.e + opt.d + opt.h
        row = dict(scenario=scenario, city=city, tariff=tname, tariff_id=g.tariff_id.iloc[0],
                   hp_marginal_usd_per_kW=cfg["heat_pump"]["hp_marginal_usd_per_kW"],
                   hp_effective_usd_per_kW=cfg["heat_pump"]["capex_usd_per_kW_thermal"],
                   tank_om_fraction=cfg["tank"]["om_fraction"],
                   wall_pcm_usd_per_m2=cfg["wall"]["installed_usd_per_m2"][0])
        for b in bld:
            capex, om = (pd.Series(v, index=opt.index) for v in C.tank_costs(cfg, opt.size_kWh, tank_cost[b]))
            net = opt.sav - capex - om
            i = net.idxmax(); o = opt.loc[i]
            row.update({f"tank_cost_{b}_usd_per_kWh_th": tank_cost[b],
                        f"battery_{b}_net_savings_usd": net[i], f"battery_{b}_option": f"{o.controller} {o.size_kWh:g} kWh",
                        f"battery_{b}_energy_bill_savings_usd": o.e + o.d, f"battery_{b}_demand_savings_usd": o.d,
                        f"battery_{b}_hp_savings_usd": o.h, f"battery_{b}_tank_capex_usd": capex[i],
                        f"battery_{b}_tank_om_usd": om[i]})
        bw = (opt.sav / (opt.size_kWh * (1 + om_pv_per_usd)))
        row["battery_break_even_installed_usd_per_kWh_th"] = max(bw.max(), 0)
        row["battery_break_even_option"] = f"{opt.loc[bw.idxmax()].controller} {opt.loc[bw.idxmax()].size_kWh:g} kWh"
        if res1 is None:                                   # building presets: battery only
            rows.append(row)
            continue

        w = res1[(res1.city == city) & (res1.tariff == tname)]
        wb = w[(w.kind == "insulation") & (w.extra_ins_mm == 0)].iloc[0]
        p = w[w.kind == "pcm"].copy()
        p["e"], p["d"], p["h"] = _value_split(cfg, wb, p)
        p["cost"] = C.wall_pcm_cost(cfg, p.pcm_mm)
        p["net"] = p.e + p.d + p.h - p.cost
        p["be_m2"] = (p.e + p.d + p.h) / C.wall_pcm_cost(cfg, p.pcm_mm, 1.0)    # $/m2 (per product layer) that breaks even
        pb = p.loc[p.net.idxmax()]
        ins = w[(w.kind == "insulation") & (w.extra_ins_mm > 0)].copy()
        ins["e"], ins["d"], ins["h"] = _value_split(cfg, wb, ins)
        ins["cost"] = cfg["costs"]["insulation_usd_per_m3"] * ins.extra_ins_mm / 1000 * area
        ins["net"] = ins.e + ins.d + ins.h - ins.cost
        ib = ins.loc[ins.net.idxmax()]
        row.update(wall_net_savings_usd=pb.net, wall_design=f"{pb.pcm_mm:g} mm @ {pb.Tm:g} C",
                   wall_energy_bill_savings_usd=pb.e + pb.d, wall_hp_savings_usd=pb.h, wall_cost_usd=pb.cost,
                   wall_break_even_usd_per_m2=max(p.be_m2.max(), 0),
                   insulation_net_savings_usd=ib.net, insulation_design=f"+{ib.extra_ins_mm:g} mm XPS")
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity(cfg, res1, df2, weather):
    """Headline at base, tank cost low/high (recost only) and heat-pump cost low/high (smart LP re-solved;
    fixed/rule size to their load, so they are only recosted)."""
    tc = cfg["tank_cost"]
    heads = [headline(cfg, res1, df2, "base")]
    for k, lab in ((1, "tank low"), (2, "tank high")):
        cost = {b: tc[b][k] for b in BLD}
        heads.append(headline(cfg, res1, case2_metrics(cfg, df2, cost), lab, cost))
    _, lo, hi = cfg["heat_pump"]["marginal_usd_per_kW"]
    for v, lab in ((lo, "hp low"), (hi, "hp high")):
        print(f"Sensitivity: heat pump ${v:g}/kW marginal (smart LP re-solved)")
        cfg_s = C.set_hp_cost(cfg, v)
        smart_s, _ = run_case2(cfg_s, weather, ["smart"])
        df_s = case2_metrics(cfg_s, pd.concat([df2[df2.controller != "smart"], smart_s], ignore_index=True))
        df_s.to_csv(os.path.join(OUT, f"case2_runs_hp{v:g}.csv"), index=False)
        heads.append(headline(cfg_s, res1, df_s, lab))
    return pd.concat(heads, ignore_index=True)


def summarize(cfg, be1, df2, head):
    """Per-controller table (each tank vs the same controller without a tank) + passive wall."""
    s = be1.set_index(["city", "tariff"])[["case1_break_even_usd_kg", "pcm_daily_swing", "pcm_full_cycle_days"]].copy()
    hb = head.set_index(["city", "tariff"])
    for c in ("wall_net_savings_usd", "wall_design", "wall_break_even_usd_per_m2", "insulation_net_savings_usd"):
        s[c] = hb[c]
    pos = df2[df2.size_kWh > 0]
    sys_be = pos.groupby(["city", "tariff", "controller"]).break_even_system_usd_per_kWh_th.max().unstack("controller")
    for b in BLD:
        net = pos.groupby(["city", "tariff", "controller"])[f"net_savings_{b}_usd"].max().unstack("controller")
        for c in CTRL:
            s[f"case2_{c}_net_savings_{b}_usd"] = net[c]
    for c in CTRL:
        s[f"case2_{c}_break_even_system_usd_per_kWh_th"] = sys_be[c].clip(lower=0)
    s["control_premium_usd_per_kWh_th"] = s.case2_smart_break_even_system_usd_per_kWh_th - s.case2_rule_break_even_system_usd_per_kWh_th
    s = s.reset_index()
    ids = {(c, k): t for c, d in cfg["tariff_ids"].items() for k, t in d.items()}
    tdat = {t: C.tariff_for(cfg, c, k) for (c, k), t in ids.items()}
    s.insert(2, "tariff_id", [ids[(r.city, r.tariff)] for r in s.itertuples()])
    s.insert(3, "tariff_status", [tdat[t]["status"] for t in s.tariff_id])
    return s


# ---------------------------------------------------------------- sources
def sources_table(cfg):
    """Every input the run used (or deliberately did not), with its source and URL."""
    rows = []
    usage = {
        "tank_installed_cost_residential": "USED: tank capex = $/kWh_th x size (residential scenario); low/high in sensitivity",
        "tank_installed_cost_commercial": "USED: tank capex = $/kWh_th x size (commercial scenario); low/high in sensitivity",
        "tank_vessel_only_cost": "not used (reference only)",
        "pcm_raw_salt_hydrate": "not used (material reference; installed tank cost includes PCM)",
        "pcm_raw_paraffin_generic": "not used (material reference; installed tank cost includes PCM)",
        "wall_pcm_installed_cost": f"USED: PCM wall cost = $/m2 x wall area x (PCM kg/m2 / {C.WALL_PRODUCT_KG_PER_M2:.2f} kg/m2 per product layer)",
        "insulation_installed_cost": "not used: energy specialist's sourced XPS cost (insulation_cost_xps) is used instead",
        "tank_om_fraction": "USED: tank O&M per year = fraction x capex, 20-yr present value",
        "tank_lifetime": "USED: >= 20 yr, so no tank replacement",
        "wall_pcm_lifetime": "USED: >= 20 yr, so no wall replacement, no maintenance",
        "hp_marginal_cost": "USED: heat-pump downsizing credit; low/high in sensitivity",
        "hp_lifetime": f"USED: one replacement at yr 15 (discounted, no salvage): cost x {cfg['heat_pump']['hp_replacement_factor']:.3f}",
        "hp_maintenance": "not used: same for every option, cancels",
    }
    for k, r in cfg["_costs2026"].iterrows():
        rows.append(dict(file="costs_sourced_2026.csv", parameter=k, base=r.base, low=r.low, high=r.high, unit=r.unit,
                         used=usage.get(k, ""), source=r.source, url=r.url, source_year=r.source_year, note=r.note))
    m = pd.read_csv(cfg["_energy"]["path"], dtype=str).fillna("")
    keep = {("finance", "discount_rate_real"): "USED: discount rate", ("finance", "lifetime"): "USED: analysis period",
            ("cost", "insulation_cost_xps"): "USED: extra insulation cost (case 1)",
            ("cost", "insulation_conductivity_xps"): "USED: insulation conductivity",
            ("cost", "heat_pump_cost_per_kW"): "superseded by hp_marginal_cost (costs_sourced_2026.csv)"}
    for r in m.itertuples():
        if (r.section, r.key) in keep:
            rows.append(dict(file=os.path.basename(cfg["_energy"]["path"]), parameter=r.key, base=r.value, low=r.low,
                             high=r.high, unit=r.unit, used=keep[(r.section, r.key)], source=r.source, url=r.url,
                             source_year="", note=r.note))
        elif r.section == "tariff" and r.key == "name":
            rows.append(dict(file=os.path.basename(cfg["_energy"]["path"]), parameter=f"tariff {r.tariff_id}",
                             base=r.value, low="", high="", unit="", used=f"USED: {r.city} tariff ({r.status})",
                             source=r.source, url=r.url, source_year="", note=r.note))
        elif r.section == "city" and r.key == "weather_file":
            rows.append(dict(file=os.path.basename(cfg["_energy"]["path"]), parameter=f"weather {r.city}", base=r.value,
                             low="", high="", unit="", used="USED: hourly weather", source=r.source, url=r.url,
                             source_year="", note=r.note))
    if os.path.exists(C.TEAM_DEFAULTS):
        d = pd.read_csv(C.TEAM_DEFAULTS).set_index("key")
        for k, use in (("pcm_latent_heat", "USED: wall and tank latent heat"), ("pcm_density_liquid", "USED: PCM density"),
                       ("pcm_conductivity", "USED: PCM conductivity"),
                       ("storage_bos_cost", "superseded by tank_installed_cost_* (costs_sourced_2026.csv)")):
            r = d.loc[k]
            rows.append(dict(file="PCM_Hackathon_Defaults.csv", parameter=k, base=r.default, low=r.low, high=r.high,
                             unit=r.unit, used=use, source=r.source, url=r.url, source_year="", note=r.notes))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- energy specialist handoff
def export_energy_handoff(cfg, res1, be1, df2, keep):
    """Write results_hourly.csv + results_meta.csv in the energy model's contract (energy/04_model/cost_model.py)
    and run it, so its break-even / cost-breakdown / sensitivity tables use our simulated hourly loads."""
    folder = os.path.join(OUT, "energy_handoff")
    os.makedirs(folder, exist_ok=True)
    status = cfg.get("results_data_status", "PLACEHOLDER")
    area, rho = cfg["house"]["wall_area_m2"], cfg["wall"]["pcm_rho"]
    hours = np.arange(1, C.N_HOURS + 1)
    hourly, meta = [], []

    def add(city, case, option, ctrl, tid, P, kg, cm, hp):
        hourly.append(pd.DataFrame(dict(city=city, case=case, option=option, controller=ctrl, tariff_id=tid,
                                        hour=hours, elec_kWh=np.round(P, 5))))
        meta.append(dict(city=city, case=case, option=option, controller=ctrl, tariff_id=tid, pcm_kg=round(kg, 2),
                         extra_insulation_cm=cm, wall_area_m2=area, hp_capacity_kW=round(hp, 3), data_status=status))

    # case 1: the wall runs do not depend on the tariff (fixed thermostat), so tariff_id is blank.
    # pcm_wall = the PCM design our own equal-budget analysis picks for the city's TOU tariff.
    first = res1[res1.tariff == cfg["tariffs"][0]]
    for city, g in first.groupby("city"):
        for d in g[g.kind == "insulation"].itertuples():
            cm = d.extra_ins_mm / 10
            add(city, "passive_wall", "baseline" if cm == 0 else f"insul_{cm:g}cm", "none", "",
                res1.attrs["P"][(city, d.design)], 0, cm, d.hp_kW)
        b = be1[(be1.city == city) & (be1.tariff == cfg["tariffs"][0])].iloc[0]
        p = g[(g.kind == "pcm") & (g.pcm_mm == b.best_pcm_mm) & (g.Tm == b.best_Tm)].iloc[0]
        add(city, "passive_wall", "pcm_wall", "none", "", res1.attrs["P"][(city, p.design)],
            p.pcm_mm / 1000 * rho * area, 0, p.hp_kW)

    # case 2: per controller, no battery vs the tank size with the best break-even installed cost.
    for (city, tname, ctrl), g in df2.groupby(["city", "tariff", "controller"]):
        tid = g.tariff_id.iloc[0]
        n0 = g[g.size_kWh == 0].iloc[0]
        nb = g[g.size_kWh > 0].sort_values("break_even_system_usd_per_kWh_th").iloc[-1]
        add(city, "battery", "no_battery", ctrl, tid, keep[(city, tname, ctrl, 0)]["P"], 0, 0, n0.hp_kW)
        add(city, "battery", "battery", ctrl, tid, keep[(city, tname, ctrl, nb.size_kWh)]["P"], nb.mass_kg, 0, nb.hp_kW)

    pd.concat(hourly).to_csv(os.path.join(folder, "results_hourly.csv"), index=False)
    pd.DataFrame(meta).to_csv(os.path.join(folder, "results_meta.csv"), index=False)

    out, inputs = ENERGY_OUT, cfg["_energy"]["path"]
    os.makedirs(out, exist_ok=True)
    C.EM.equal_budget_table(inputs, out)
    be, st = C.EM.run(inputs, folder, out)
    C.EM.sensitivity(inputs, folder, out)
    # cost_model.py still prices with inputs.csv (HP $529/kW, no replacement, no tank cost or O&M): label its
    # outputs "earlier costs" so nobody mistakes them for the costs_sourced_2026.csv results (results/headline.csv).
    label = ("EARLIER COSTS: energy specialist cost_model.py with inputs.csv (heat pump $529/kW, no replacement; "
             "battery break-even excludes tank cost and O&M). Not updated to costs_sourced_2026.csv; "
             "use results/headline.csv")
    for f in sorted(os.listdir(out)):
        path = os.path.join(out, f)
        if (os.path.isfile(path) and f.endswith(".csv") and "EARLIER_COSTS" not in f
                and f.split("_PLACEHOLDER")[0].split(".csv")[0] in ("breakeven", "cost_breakdown", "control_premium", "sensitivity")):
            df = pd.read_csv(path)
            df.insert(0, "cost_basis", label)
            df.to_csv(path.replace(".csv", "_EARLIER_COSTS.csv"), index=False)
            os.remove(path)
    print(f"  energy model: {len(be)} break-even rows -> {os.path.relpath(out, C.HERE)} "
          f"(data_status {st}; labelled EARLIER_COSTS)")


# ---------------------------------------------------------------- charts
def _xlabels(ax, d):
    ax.set_xticks(np.arange(len(d)))
    ax.set_xticklabels([f"{r.city}\n{r.tariff_id}" + ("*" if r.tariff_status == "HYPOTHETICAL" else "")
                        for r in d.itertuples()], fontsize=7)


def chart_net_savings(cfg, head, summ):
    tariffs = list(cfg["tariffs"])
    status = summ.set_index("tariff_id").tariff_status
    fig, axes = plt.subplots(1, len(tariffs), figsize=(6 * len(tariffs), 4.8), sharey=True)
    cols = [("battery_residential_net_savings_usd", f"PCM battery, residential (${cfg['tank_cost']['residential'][0]:g}/kWh-th)", "#E4572E"),
            ("battery_commercial_net_savings_usd", f"PCM battery, commercial (${cfg['tank_cost']['commercial'][0]:g}/kWh-th)", "#0E7C7B"),
            ("wall_net_savings_usd", f"Passive PCM wall (${cfg['wall']['installed_usd_per_m2'][0]:g}/m²)", "#8D99AE")]
    for ax, tn in zip(np.atleast_1d(axes), tariffs):
        d = head[head.tariff == tn].assign(tariff_status=lambda x: x.tariff_id.map(status))
        x = np.arange(len(d)); w = 0.27
        for i, (c, lab, col) in enumerate(cols):
            ax.bar(x + (i - 1) * w, d[c], w, label=lab, color=col)
        ax.axhline(0, color="#333", lw=0.8)
        _xlabels(ax, d); ax.set_title(tn)
    np.atleast_1d(axes)[0].set_ylabel("20-year net savings [$]\n(> 0 = pays)")
    h, l = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle("Does PCM pay? Best PCM option vs smart control with no tank (battery) / baseline wall (wall)"
                 "   (* = hypothetical tariff)", fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(os.path.join(FIG, "net_savings.png")); plt.close(fig)


def chart_system_cost(cfg, summ):
    tariffs = list(cfg["tariffs"])
    fig, axes = plt.subplots(1, len(tariffs), figsize=(6 * len(tariffs), 4.8), sharey=True)
    cols = [("fixed", "Fixed schedule", "#F2A541"), ("rule", "Rule-based", "#E4572E"), ("smart", "Smart control", "#0E7C7B")]
    (rb, rl, rh), (cb, cl, ch) = cfg["tank_cost"]["residential"], cfg["tank_cost"]["commercial"]
    for ax, tn in zip(np.atleast_1d(axes), tariffs):
        d = summ[summ.tariff == tn]
        x = np.arange(len(d)); w = 0.26
        ax.axhspan(cl, ch, color="#B8D8D8", alpha=0.5, label=f"commercial installed ${cl:g}–{ch:g}/kWh-th")
        ax.axhspan(rl, rh, color="#F3C7BC", alpha=0.5, label=f"residential installed ${rl:g}–{rh:g}/kWh-th")
        for i, (c, lab, col) in enumerate(cols):
            ax.bar(x + (i - 1) * w, d[f"case2_{c}_break_even_system_usd_per_kWh_th"], w, label=lab, color=col)
        _xlabels(ax, d); ax.set_title(tn)
    np.atleast_1d(axes)[0].set_ylabel("Break-even installed cost incl. O&M\n[$/kWh thermal] (pays below this)")
    h, l = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("PCM thermal battery: what may an installed system cost?   (* = hypothetical tariff)", fontsize=11)
    fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(os.path.join(FIG, "break_even_system_cost.png")); plt.close(fig)


def chart_day(cfg, keep, weather, city, tname):
    T_out, _ = weather[city]
    size = max(cfg["tank"]["sizes_kWh_thermal"][:2])
    a = keep[(city, tname, "smart", 0)]; b = keep[(city, tname, "smart", size)]
    day = int(np.argmax(np.convolve(a["Qc"], np.ones(24), "valid")[::24]))   # hottest-load day
    sl = slice(day * 24, day * 24 + 24); hrs = np.arange(24)
    price, peak, _ = C.hourly_tariff(C.tariff_for(cfg, city, tname))
    fig, ax = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for axx in ax:
        for hh in hrs[peak[sl]]:
            axx.axvspan(hh, hh + 1, color="#F2A541", alpha=0.15, lw=0)
    ax[0].step(hrs, a["P"][sl], where="post", color="#8D99AE", lw=2, label="No PCM (smart control)")
    ax[0].step(hrs, b["P"][sl], where="post", color="#0E7C7B", lw=2, label=f"With {size} kWh PCM battery")
    ax[0].set_ylabel("Heat-pump electricity [kW]"); ax[0].legend(frameon=False, fontsize=8)
    ax[0].set_title(f"{city}, hottest day, {tname} (shaded = peak price)  ·  outdoor {T_out[sl].min():.0f}–{T_out[sl].max():.0f} °C")
    ax[1].plot(np.arange(25), b["E"][day * 24: day * 24 + 25] / size * 100, color="#0E7C7B", lw=2)
    ax[1].set_ylabel("PCM charged [%]"); ax[1].set_xlabel("Hour of day"); ax[1].set_ylim(0, 105)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "day_plot.png")); plt.close(fig)


def chart_liquid_fraction(cfg, lf_store, be1, weather, city):
    r = be1[(be1.city == city)].iloc[0]
    key = (city, r.best_pcm_mm, r.best_Tm)
    if key not in lf_store:
        key = [k for k in lf_store if k[0] == city][0]
    lf = lf_store[key]; T_out, _ = weather[city]
    day = int(np.argmax(T_out.reshape(365, 24).mean(1))) - 3
    sl = slice(day * 24, day * 24 + 24 * 7)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(np.arange(24 * 7) / 24, lf[sl] * 100, color="#0E7C7B", lw=2, label="PCM melted [%]")
    ax.set_ylim(-3, 103); ax.set_ylabel("PCM melted [%]"); ax.set_xlabel("Day")
    ax2 = ax.twinx(); ax2.plot(np.arange(24 * 7) / 24, T_out[sl], color="#E4572E", lw=1, alpha=0.7)
    ax2.set_ylabel("Outdoor °C", color="#E4572E")
    ax.set_title(f"Passive PCM wall in {city}, hot week ({key[1]} mm, melts at {key[2]:.0f} °C): does it recharge?")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "wall_liquid_fraction.png")); plt.close(fig)


def chart_annual_cost(cfg, res1):
    base = res1[(res1.kind == "insulation") & (res1.extra_ins_mm == 0)]
    piv = base.assign(total=base.energy_usd + base.demand_usd).pivot(index="city", columns="tariff", values="total")
    ax = piv.plot.bar(figsize=(8, 3.8), color=["#0E7C7B", "#F2A541", "#E4572E"][:piv.shape[1]], rot=0)
    ax.set_ylabel("Annual heating + cooling bill [$]"); ax.set_xlabel("")
    ax.set_title("Standard all-electric house: annual heating and cooling cost")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "annual_cost_by_city.png")); plt.close()


def chart_cost_breakdown(cfg, res1, df2, head, city, tname):
    AF, hp = C.annuity_factor(cfg), cfg["heat_pump"]["capex_usd_per_kW_thermal"]
    hd = head[(head.city == city) & (head.tariff == tname)].iloc[0]
    g = res1[(res1.city == city) & (res1.tariff == tname)]
    a = g[(g.kind == "insulation") & (g.extra_ins_mm == 0)].iloc[0]
    mm, tm = hd.wall_design.split(" mm @ ")
    p = g[(g.kind == "pcm") & (g.pcm_mm == float(mm)) & (g.Tm == float(tm.split()[0]))].iloc[0]
    d = df2[(df2.city == city) & (df2.tariff == tname)]
    c0 = d[(d.controller == "smart") & (d.size_kWh == 0)].iloc[0]

    def batt(b):
        ctrl, size = hd[f"battery_{b}_option"].split()[:2]
        r = d[(d.controller == ctrl) & (d.size_kWh == float(size))].iloc[0]
        return r, f"{ctrl} + {float(size):g} kWh"
    bars = {"A. Baseline house": [AF * a.energy_usd, AF * a.demand_usd, hp * a.hp_kW, 0, 0],
            f"B. + passive PCM wall ({hd.wall_design})": [AF * p.energy_usd, AF * p.demand_usd, hp * p.hp_kW, hd.wall_cost_usd, 0],
            "C0. Smart control, no PCM": [AF * c0.energy_usd, AF * c0.demand_usd, hp * c0.hp_kW, 0, 0]}
    for b, tag in (("residential", "C-res"), ("commercial", "C-com")):
        r, lab = batt(b)
        bars[f"{tag}. {lab} PCM tank ({b})"] = [AF * r.energy_usd, AF * r.demand_usd, hp * r.hp_kW,
                                                 r[f"tank_capex_{b}_usd"], r[f"tank_om_pv_{b}_usd"]]
    labels = ["Energy (20 yr)", "Demand charges (20 yr)", "Heat pump incl. yr-15 replacement", "PCM wall / tank installed",
              "Tank O&M (20 yr)"]
    colors = ["#0E7C7B", "#F2A541", "#8D99AE", "#E4572E", "#7A3B69"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    left = np.zeros(len(bars)); vals = np.array(list(bars.values()))
    for i in range(vals.shape[1]):
        ax.barh(list(bars), vals[:, i], left=left, color=colors[i], label=labels[i]); left += vals[:, i]
    for y, tot in enumerate(left):
        ax.text(tot + 80, y, f"${tot:,.0f}", va="center", fontsize=9)
    ax.invert_yaxis(); ax.set_xlabel("20-year cost [$]"); ax.set_xlim(0, left.max() * 1.18)
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=8, frameon=False)
    ax.set_title(f"{city}, {tname}: 20-year cost by option")
    fig.tight_layout(rect=(0, 0.1, 1, 1)); fig.savefig(os.path.join(FIG, "cost_breakdown.png")); plt.close(fig)


# ---------------------------------------------------------------- printing
def _money(x):
    return f"{x:,.0f}"


def print_tables(cfg, head, summ):
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    base = head[head.scenario == "base"]
    t = pd.DataFrame({
        "city": base.city, "tariff": base.tariff_id,
        "res batt net $": base.battery_residential_net_savings_usd.map(_money),
        "com batt net $": base.battery_commercial_net_savings_usd.map(_money),
        "wall net $": base.wall_net_savings_usd.map(_money),
        "bill sav $ res/com": [f"{_money(a)} / {_money(b)}" for a, b in zip(base.battery_residential_energy_bill_savings_usd,
                                                                             base.battery_commercial_energy_bill_savings_usd)],
        "HP sav $ res/com": [f"{_money(a)} / {_money(b)}" for a, b in zip(base.battery_residential_hp_savings_usd,
                                                                           base.battery_commercial_hp_savings_usd)],
        "tank O&M $ res/com": [f"{_money(a)} / {_money(b)}" for a, b in zip(base.battery_residential_tank_om_usd,
                                                                             base.battery_commercial_tank_om_usd)],
        "wall bill/HP sav $": [f"{_money(a)} / {_money(b)}" for a, b in zip(base.wall_energy_bill_savings_usd,
                                                                             base.wall_hp_savings_usd)],
        "res option": base.battery_residential_option, "com option": base.battery_commercial_option})
    h = cfg["heat_pump"]
    print(f"\nNET 20-YEAR SAVINGS ($, present value; > 0 = pays). Battery: best PCM option (any controller, any size) vs "
          f"smart control with no tank, net of tank capex + O&M. Wall: best PCM design vs baseline wall, net of wall cost.\n"
          f"Heat pump ${h['hp_marginal_usd_per_kW']:g}/kW x {h['hp_replacement_factor']:.3f} (yr-15 replacement) = "
          f"${h['capex_usd_per_kW_thermal']:.0f}/kW. Tank: residential ${cfg['tank_cost']['residential'][0]:g}, commercial "
          f"${cfg['tank_cost']['commercial'][0]:g} per kWh-th, O&M {cfg['tank']['om_fraction']:.1%}/yr. "
          f"Wall ${cfg['wall']['installed_usd_per_m2'][0]:g}/m2. Bill = energy + demand.")
    print(t.to_string(index=False))

    sc = summ[["city", "tariff_id"] + [f"case2_{c}_break_even_system_usd_per_kWh_th" for c in CTRL]
              + ["wall_break_even_usd_per_m2"]].round(0)
    sc.columns = ["city", "tariff", "batt fixed", "batt rule", "batt smart", "wall $/m2"]
    print("\nBREAK-EVEN INSTALLED COST: battery $/kWh-th incl. O&M (each controller vs itself without a tank); "
          "wall $/m2 of wall per product layer. Pays below these.")
    print(sc.to_string(index=False))

    for col, lab in (("battery_residential_net_savings_usd", "RESIDENTIAL battery"),
                     ("battery_commercial_net_savings_usd", "COMMERCIAL battery"), ("wall_net_savings_usd", "PASSIVE WALL")):
        pv = head.pivot_table(index=["city", "tariff_id"], columns="scenario", values=col, sort=False)
        pv = pv[[c for c in ("base", "tank low", "tank high", "hp low", "hp high") if c in pv]]
        print(f"\nSENSITIVITY, {lab} net savings ($). tank low/high: residential "
              f"{cfg['tank_cost']['residential'][1]:g}/{cfg['tank_cost']['residential'][2]:g}, commercial "
              f"{cfg['tank_cost']['commercial'][1]:g}/{cfg['tank_cost']['commercial'][2]:g} $/kWh-th; hp low/high: "
              f"{h['marginal_usd_per_kW'][1]:g}/{h['marginal_usd_per_kW'][2]:g} $/kW marginal.")
        print(pv.map(_money).to_string())


# ---------------------------------------------------------------- building presets (e.g. small office)
def run_presets(cfg, weather):
    """Battery case for each building preset in inputs.json["buildings"], with its own tank-cost type."""
    out = {}
    for name in cfg.get("buildings", {}):
        cfg_b = C.building_cfg(cfg, name)
        b = cfg_b["building_tank_cost"]
        print(f"Building preset: {name} ({cfg_b['tariffs'][0]}, {b} tank cost)")
        df_b, _ = run_case2(cfg_b, weather)
        df_b = case2_metrics(cfg_b, df_b, bld=(b,))
        df_b.to_csv(os.path.join(OUT, f"{name}_case2_runs.csv"), index=False)
        tc = cfg["tank_cost"][b]
        hb = pd.concat([headline(cfg_b, None, df_b, "base", bld=(b,))]
                       + [headline(cfg_b, None, case2_metrics(cfg_b, df_b, {b: tc[k]}, (b,)), lab, {b: tc[k]}, (b,))
                          for k, lab in ((1, "tank low"), (2, "tank high"))], ignore_index=True)
        hb.insert(0, "building", name)
        hb.to_csv(os.path.join(OUT, f"{name}_headline.csv"), index=False)
        out[name] = (cfg_b, hb)
    return out


def print_presets(cfg, presets):
    for name, (cfg_b, hb) in presets.items():
        b = cfg_b["building_tank_cost"]
        base = hb[hb.scenario == "base"]
        t = pd.DataFrame({
            "city": base.city, "tariff": base.tariff_id,
            f"{b} batt net $": base[f"battery_{b}_net_savings_usd"].map(_money),
            "bill sav $": base[f"battery_{b}_energy_bill_savings_usd"].map(_money),
            "of which demand $": base[f"battery_{b}_demand_savings_usd"].map(_money),
            "HP sav $": base[f"battery_{b}_hp_savings_usd"].map(_money),
            "tank capex $": base[f"battery_{b}_tank_capex_usd"].map(_money),
            "tank O&M $": base[f"battery_{b}_tank_om_usd"].map(_money),
            "option": base[f"battery_{b}_option"],
            "BE $/kWh-th": base.battery_break_even_installed_usd_per_kWh_th.round(0),
            f"net @ tank low ${cfg['tank_cost'][b][1]:g}": hb[hb.scenario == "tank low"][f"battery_{b}_net_savings_usd"].map(_money).values,
            f"net @ tank high ${cfg['tank_cost'][b][2]:g}": hb[hb.scenario == "tank high"][f"battery_{b}_net_savings_usd"].map(_money).values})
        h = cfg_b["house"]
        print(f"\n{name.upper()} ({h['floor_area_m2']} m2, {h['internal_gains_occupied_W_per_m2']} W/m2 occupied "
              f"{h['occupied_hours'][0]}-{h['occupied_hours'][1]} h {h['occupied_days']}; ASSUMED preset; tariff = "
              f"TOU+demand stand-in): best PCM battery vs smart control with no tank, {b} tank "
              f"${cfg['tank_cost'][b][0]:g}/kWh-th + O&M. Net 20-yr savings ($).")
        print(t.to_string(index=False))


def main():
    global OUT, FIG, ENERGY_OUT
    import argparse
    ap = argparse.ArgumentParser(description="Run both PCM cases and the energy cost model.")
    ap.add_argument("--source", choices=C.SOURCES, default=C.DEFAULT_SOURCE,
                    help="which team sheet wins where they disagree (default: energy = inputs.csv)")
    args = ap.parse_args()
    OUT, FIG, ENERGY_OUT = C.out_dirs(args.source)
    os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)
    cfg = C.load_inputs(source=args.source)
    print(f"Inputs: {os.path.relpath(cfg['_energy']['path'], C.HERE)} + costs_sourced_2026.csv  (source = {args.source})")
    t0 = time.time()
    print("Case 1: passive PCM wall vs equal-budget insulation")
    res1, lf_store, weather = W.run(cfg)
    be1 = W.break_even(cfg, res1)
    res1.to_csv(os.path.join(OUT, "case1_designs.csv"), index=False)
    print("Case 2: PCM thermal battery, fixed / rule / smart control")
    df2, keep = run_case2(cfg, weather)
    df2.to_csv(os.path.join(OUT, "case2_runs.csv"), index=False)
    head = sensitivity(cfg, res1, df2, weather)
    head.to_csv(os.path.join(OUT, "headline.csv"), index=False)
    summ = summarize(cfg, be1, df2, head[head.scenario == "base"])
    summ.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    sources_table(cfg).to_csv(os.path.join(OUT, "sources.csv"), index=False)
    print("Energy specialist handoff + cost model")
    export_energy_handoff(cfg, res1, be1, df2, keep)
    presets = run_presets(cfg, weather)

    city_demo = max(weather, key=lambda c: weather[c][0].max())
    chart_net_savings(cfg, head[head.scenario == "base"], summ)
    chart_system_cost(cfg, summ)
    chart_day(cfg, keep, weather, city_demo, "TOU+demand")
    chart_liquid_fraction(cfg, lf_store, be1, weather, city_demo)
    chart_annual_cost(cfg, res1)
    chart_cost_breakdown(cfg, res1, df2, head[head.scenario == "base"], city_demo, "TOU+demand")

    print_tables(cfg, head, summ)
    print_presets(cfg, presets)
    print(f"\nSources: {os.path.relpath(os.path.join(OUT, 'sources.csv'), C.HERE)}")
    print(f"Done in {time.time() - t0:.0f}s -> {os.path.relpath(OUT, C.HERE)}/ and {os.path.relpath(FIG, C.HERE)}/")


if __name__ == "__main__":
    main()
