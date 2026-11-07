"""
Case 1: passive PCM wall vs the same money spent on more insulation.

Full-year 1D wall simulation (implicit finite volume + enthalpy method, 15-min steps) for many
wall designs at once, then the standard house with a fixed thermostat turns wall heat flow into
heat-pump electricity, bills, and heat-pump size. Tracks PCM liquid fraction (does it refreeze?).
"""
import numpy as np
import pandas as pd

import common as C

DT = 900.0                      # s
N_INS, N_PCM, N_DRY = 10, 6, 3
H_OUT, H_IN = 20.0, 8.0
INS_EXTRA_MM = np.array([0, 10, 20, 35, 50, 75, 100, 150, 200, 300, 400, 500])
PCM_MM = np.array([5, 10, 20])
PCM_TM = np.array([21, 22, 23, 24, 25, 26, 27])


def _thomas(a, b, c, d):
    n = b.shape[1]
    cp, dp = np.empty_like(b), np.empty_like(b)
    cp[:, 0], dp[:, 0] = c[:, 0] / b[:, 0], d[:, 0] / b[:, 0]
    for j in range(1, n):
        m = b[:, j] - a[:, j] * cp[:, j - 1]
        cp[:, j] = c[:, j] / m
        dp[:, j] = (d[:, j] - a[:, j] * dp[:, j - 1]) / m
    x = np.empty_like(b)
    x[:, -1] = dp[:, -1]
    for j in range(n - 2, -1, -1):
        x[:, j] = dp[:, j] - cp[:, j] * x[:, j + 1]
    return x


def simulate_walls(cfg, ins_t, pcm_t, Tm, T_sa_hourly, T_in):
    """Batched full-year wall simulation.
    ins_t, pcm_t, Tm: (N,) metres / °C.  T_sa_hourly: (N, 8760) sol-air temperature.
    Returns q_in (N, 8760) W/m2 into the room (hourly mean) and liquid fraction (N, 8760)."""
    w = cfg["wall"]
    N = len(ins_t)
    pcm_t = np.maximum(pcm_t, 1e-4)                       # 0.1 mm stand-in for "no PCM"
    has_pcm = (np.asarray(pcm_t) > 1e-3)

    def layer(a, b, c):
        cols = [np.broadcast_to(np.reshape(v, (-1, 1)) if np.ndim(v) else v, (N, m))
                for v, m in ((a, N_INS), (b, N_PCM), (c, N_DRY))]
        return np.concatenate(cols, axis=1).astype(float)

    dry_t = w["drywall_mm"] / 1000
    dx = layer(ins_t / N_INS, pcm_t / N_PCM, dry_t / N_DRY)
    k = layer(w["insulation_k"], w["pcm_k"], 0.25)
    rho = layer(w["insulation_rho"], w["pcm_rho"], 800.0)
    cp = layer(w["insulation_cp"], w["pcm_cp"], 1090.0)
    L = layer(0.0, np.where(has_pcm, w["pcm_latent_kJ_per_kg"] * 1e3, 0.0), 0.0)
    wr = w["pcm_melt_range_K"]
    T1 = layer(0.0, Tm - wr / 2, 0.0)

    G_face = 1 / (dx[:, :-1] / (2 * k[:, :-1]) + dx[:, 1:] / (2 * k[:, 1:]))
    G_out = 1 / (1 / H_OUT + dx[:, 0] / (2 * k[:, 0]))
    G_in = 1 / (1 / H_IN + dx[:, -1] / (2 * k[:, -1]))
    left = np.concatenate([G_out[:, None], G_face], 1)
    right = np.concatenate([G_face, G_in[:, None]], 1)
    a = -left.copy(); a[:, 0] = 0
    c = -right.copy(); c[:, -1] = 0

    H_of_T = lambda T: cp * T + L * np.clip((T - T1) / wr, 0, 1)

    def T_of_H(h):
        lo, hi = cp * T1, cp * (T1 + wr) + L
        mid = (h + L * T1 / wr) / (cp + L / wr)
        return np.where(h <= lo, h / cp, np.where(h <= hi, mid, (h - L) / cp))

    def solve(cap, T_prev, T_sa):
        b = cap + left + right
        d = cap * T_prev
        d[:, 0] += G_out * T_sa
        d[:, -1] += G_in * T_in
        return _thomas(a, b, c, d)

    spin = 24 * 14                                          # two weeks of spin-up (last days of the year)
    drive = np.concatenate([T_sa_hourly[:, -spin:], T_sa_hourly], axis=1)
    sub = int(3600 / DT)
    T = solve(np.zeros_like(dx), np.zeros_like(dx), drive[:, :24].mean(1))
    h = H_of_T(T)
    pcm_cols = slice(N_INS, N_INS + N_PCM)
    q = np.zeros((N, C.N_HOURS)); lf = np.zeros((N, C.N_HOURS))
    n_total = drive.shape[1]
    for hr in range(n_total):
        nxt = drive[:, min(hr + 1, n_total - 1)]
        acc_q = 0.0
        for s in range(sub):
            T_sa = drive[:, hr] + (nxt - drive[:, hr]) * (s + 1) / sub
            in_win = (T > T1) & (T < T1 + wr)
            cap = rho * (cp + np.where(in_win, L / wr, 0)) * dx / DT
            T_star = solve(cap, T, T_sa)
            h = h + (cap * DT / (rho * dx)) * (T_star - T)          # energy-conserving enthalpy update
            T = T_of_H(h)
            acc_q = acc_q + G_in * (T[:, -1] - T_in)
        if hr >= spin:
            i = hr - spin
            q[:, i] = acc_q / sub
            lf[:, i] = np.clip((T[:, pcm_cols] - T1[:, pcm_cols]) / wr, 0, 1).mean(1)
    return q, lf


def wall_U(cfg, ins_t):
    w = cfg["wall"]
    return 1 / (1 / H_OUT + ins_t / w["insulation_k"] + w["drywall_mm"] / 1000 / 0.25 + 1 / H_IN)


def house_from_wall(cfg, q_wall, T_out, ghi, lat_pot=None):
    """Deadband thermostat house with thermal mass (1R1C): hourly cooling/heating load and electricity (kW).
    The wall's hourly heat flow into the room (q_wall, W/m2) replaces that wall's share of the house UA."""
    h, w = cfg["house"], cfg["wall"]
    hs, cs = C.deadband(cfg)
    UA, Cm = h["UA_total_kW_per_K"], h["thermal_mass_kWh_per_K"]
    UA_other = UA - h["wall_area_m2"] * wall_U(cfg, w["baseline_insulation_mm"] / 1000) / 1000
    drive = h["wall_area_m2"] * q_wall / 1000 + C.house_gains(cfg, T_out, ghi)
    cool, heat = np.zeros(C.N_HOURS), np.zeros(C.N_HOURS)
    T = (hs + cs) / 2
    for i in range(C.N_HOURS):
        T_free = T + (UA_other * (T_out[i] - T) + drive[i]) / Cm
        T = min(max(T_free, hs), cs)
        cool[i], heat[i] = max(T_free - T, 0) * Cm, max(T - T_free, 0) * Cm
    lat = (lat_pot if lat_pot is not None else 0.0) * (cool > 1e-9)       # latent only while cooling (v2)
    P = (cool + lat) / C.cop_cool(cfg, T_out) + heat / C.cop_heat(cfg, T_out)
    return P, cool + lat, heat


def run(cfg, cities=None, verbose=True):
    """Simulate every design in every city; return per-design 20-year NPV of running costs."""
    cities = cities or list(cfg["cities"])
    w, h = cfg["wall"], cfg["house"]
    d0 = w["baseline_insulation_mm"] / 1000
    designs = [dict(kind="insulation", extra_ins_mm=e, pcm_mm=0, Tm=np.nan) for e in INS_EXTRA_MM]
    designs += [dict(kind="pcm", extra_ins_mm=0, pcm_mm=p, Tm=t) for p in PCM_MM for t in PCM_TM]
    D = pd.DataFrame(designs)

    rows, weather, lf_store, P_store = [], {}, {}, {}
    ins_t = np.tile(d0 + D.extra_ins_mm.values / 1000, len(cities))
    pcm_t = np.tile(D.pcm_mm.values / 1000, len(cities))
    Tm = np.tile(np.nan_to_num(D.Tm.values, nan=25.0), len(cities))
    T_sa = []
    for city in cities:
        T_out, ghi = C.city_weather(cfg, city)
        weather[city] = (T_out, ghi)
        T_sa.append(np.tile(T_out + w["solar_absorptance"] * w["vertical_to_horizontal_sun"] * ghi / H_OUT, (len(D), 1)))
    if verbose:
        print(f"  case 1: simulating {len(ins_t)} walls x 8760 h ...", flush=True)
    q, lf = simulate_walls(cfg, ins_t, pcm_t, Tm, np.vstack(T_sa), float(np.mean(C.deadband(cfg))))  # indoor ~ mid-deadband

    AF = C.annuity_factor(cfg)
    hp_capex = cfg["heat_pump"]["capex_usd_per_kW_thermal"]
    for ci, city in enumerate(cities):
        T_out, ghi = weather[city]
        lat_pot = C.latent_potential(cfg, city)
        for di, d in D.iterrows():
            r = ci * len(D) + di
            P, cool, heat = house_from_wall(cfg, q[r], T_out, ghi, lat_pot)
            cap_kW = max(cool.max(), heat.max())
            P_store[(city, di)] = P
            lfr = lf[r].reshape(365, 24)
            for tname in C.city_tariffs(cfg, city):
                t = C.tariff_for(cfg, city, tname)
                energy, demand, _ = C.bill(P, t)
                rows.append(dict(city=city, tariff=tname, tariff_id=t["id"], design=di, **d,
                                 annual_kWh=float(P.sum()), energy_usd=energy, demand_usd=demand, hp_kW=cap_kW,
                                 npv_running_usd=hp_capex * cap_kW + AF * (energy + demand),
                                 pcm_daily_swing=float((lfr.max(1) - lfr.min(1)).mean()) if d["kind"] == "pcm" else np.nan,
                                 pcm_full_cycle_days=int(((lfr.max(1) > 0.95) & (lfr.min(1) < 0.05)).sum()) if d["kind"] == "pcm" else np.nan))
            if d["kind"] == "pcm":
                lf_store[(city, d["pcm_mm"], d["Tm"])] = lf[r]
    res = pd.DataFrame(rows)
    res.attrs["P"] = P_store                     # hourly electricity per (city, design index) for the energy handoff
    return res, lf_store, weather


def equal_budget(cfg, res, pcm_price):
    """For one PCM price: best PCM wall vs the same money spent on extra insulation, per city & tariff."""
    w, h, c = cfg["wall"], cfg["house"], cfg["costs"]
    out = []
    for (city, tname), g in res.groupby(["city", "tariff"]):
        base = g[(g.kind == "insulation") & (g.extra_ins_mm == 0)].npv_running_usd.iloc[0]
        ins = g[g.kind == "insulation"].sort_values("extra_ins_mm")
        ins_mm, ins_sav = ins.extra_ins_mm.values, base - ins.npv_running_usd.values
        best = None
        for _, p in g[g.kind == "pcm"].iterrows():
            budget = p.pcm_mm / 1000 * w["pcm_rho"] * pcm_price * h["wall_area_m2"]
            same_money_mm = budget / (c["insulation_usd_per_m3"] * h["wall_area_m2"]) * 1000
            ins_equiv = np.interp(same_money_mm, ins_mm, ins_sav)
            pcm_sav = base - p.npv_running_usd
            edge = pcm_sav - ins_equiv
            if best is None or edge > best["pcm_edge_usd"]:
                best = dict(city=city, tariff=tname, pcm_price=pcm_price, pcm_mm=p.pcm_mm, Tm=p.Tm, budget_usd=budget,
                            same_money_insulation_mm=same_money_mm, pcm_saves_usd=pcm_sav,
                            insulation_saves_usd=ins_equiv, pcm_edge_usd=edge,
                            pcm_net_usd=pcm_sav - budget, pcm_daily_swing=p.pcm_daily_swing,
                            pcm_full_cycle_days=p.pcm_full_cycle_days)
        out.append(best)
    return pd.DataFrame(out)


def break_even(cfg, res, prices=np.round(np.arange(0.05, 10.01, 0.05), 2)):
    """Highest PCM $/kg at which the best PCM wall still beats equal-budget insulation."""
    rows = []
    tables = {p: equal_budget(cfg, res, p) for p in prices}
    for (city, tname), _ in res.groupby(["city", "tariff"]):
        wins = [p for p in prices if (lambda r: r.pcm_edge_usd.iloc[0] > 0)(
            tables[p][(tables[p].city == city) & (tables[p].tariff == tname)])]
        be = max(wins) if wins else 0.0
        ref = tables[prices[0] if not wins else be]
        r = ref[(ref.city == city) & (ref.tariff == tname)].iloc[0]
        rows.append(dict(city=city, tariff=tname, case1_break_even_usd_kg=be, best_pcm_mm=r.pcm_mm, best_Tm=r.Tm,
                         pcm_daily_swing=r.pcm_daily_swing, pcm_full_cycle_days=r.pcm_full_cycle_days))
    return pd.DataFrame(rows)
