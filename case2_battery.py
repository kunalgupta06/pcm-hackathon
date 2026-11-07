"""
Case 2: PCM thermal battery (cold storage) charged by the heat pump, under three controllers.

House: 1R1C model, T[t+1] = T[t] + (UA*(T_out - T) + gains - Qc + Qh - discharge) / C, hourly.
Tank: E[t+1] = (1 - loss)*E[t] + eta*charge - discharge, 0 <= E <= capacity.
Electricity: Qc/COPc + Qh/COPh + charge/(COPc*charging_factor).

Controllers, each run on the house WITHOUT and WITH the tank (so PCM only gets credit for what it adds):
  fixed : thermostat deadband (heat to 20 C, cool to 25.6 C, float in between); tank charges 00-06, discharges 14-20 (clock, not tariff-aware)
  rule  : tariff-aware; pre-cool/pre-heat over the 2 h before the peak and float in the comfort band during it;
          tank charges in off-peak night hours (spare heat-pump capacity only) and discharges during the peak
  smart : linear program over the whole year with perfect foresight of weather and prices, same comfort
          flexibility as the rule controller (band only around the peak); also picks the heat-pump size.
          Upper bound on what control can do.
"""
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

import common as C


def tank_params(cfg, size_kWh):
    k = cfg["tank"]
    rate = size_kWh / k["hours_to_charge"] if size_kWh > 0 else 0.0
    mass = size_kWh * 3.6e6 / (k["latent_kJ_per_kg"] * 1e3 * k["usable_fraction"]) if size_kWh > 0 else 0.0
    return dict(E=size_kWh, rate=rate, loss=k["loss_per_hour"], eta=k["charge_efficiency"], mass_kg=mass)


def _result(cfg, P, Qc, Qh, ch, dis, T, E, t, cap_kW=None, lat=None):
    lat = np.zeros_like(Qc) if lat is None else lat
    energy, demand, peaks = C.bill(P, t)
    cap = cap_kW if cap_kW is not None else float(max((Qc + ch + lat).max(), Qh.max()))
    AF = C.annuity_factor(cfg)
    return dict(P=P, Qc=Qc, Qh=Qh, ch=ch, dis=dis, T=T, E=E, lat=lat, annual_kWh=float(P.sum()), energy_usd=energy,
                demand_usd=demand, hp_kW=cap, peak_kW_max=float(peaks.max()),
                npv_usd=cfg["heat_pump"]["capex_usd_per_kW_thermal"] * cap + AF * (energy + demand))


# ---------------------------------------------------------------- simple controllers (simulation)
def latent_load(cfg, city, T_out, ghi, t):
    """Latent cooling (kW thermal) in the hours the house needs sensible cooling with the fixed thermostat and no
    tank (baseline v2 rule). The same hours are used for every option so the comparison stays like-for-like."""
    base = simulate_policy(cfg, T_out, ghi, t, 0, "fixed")
    return C.latent_potential(cfg, city) * (base["Qc"] > 1e-9)


def simulate_policy(cfg, T_out, ghi, t, size_kWh, policy, cap_ref=np.inf, lat=None):
    lat = np.zeros(C.N_HOURS) if lat is None else lat
    h = cfg["house"]
    UA, Cm = h["UA_total_kW_per_K"], h["thermal_mass_kWh_per_K"]
    hs, cs = C.deadband(cfg)                                  # heat to hs, cool to cs, float in between
    pk_, fx = h["precool_K"], h["comfort_flex_K"]
    G = C.house_gains(cfg, T_out, ghi)
    copc, coph = C.cop_cool(cfg, T_out), C.cop_heat(cfg, T_out)
    copch = copc * cfg["heat_pump"]["charging_cop_factor"]
    tk = tank_params(cfg, size_kWh)
    price, peak, _ = C.hourly_tariff(t)
    pre1, pre2 = C.pre_peak(t)
    night_cheap = ~peak & ((C.HOD < 7) | (C.HOD >= 22))      # off-peak night hours (per-season prices vary)

    n = C.N_HOURS
    Qc, Qh, ch, dis, P = (np.zeros(n) for _ in range(5))
    T, E = np.full(n + 1, (hs + cs) / 2), np.zeros(n + 1)
    cooled_yesterday = True
    for i in range(n):
        if C.HOD[i] == 0 and i > 0:
            cooled_yesterday = Qc[i - 24:i].sum() + dis[i - 24:i].sum() > 0
        cooling_mode = T_out[i] > (hs + cs) / 2
        if policy == "fixed":
            band = (hs, cs)
            want_charge = (C.HOD[i] < 6) and cooled_yesterday
            want_dis = 14 <= C.HOD[i] < 20
        else:
            if pre1[i]:                                       # pre-cool / pre-heat inside the deadband
                band = (hs, cs - pk_ / 2) if cooling_mode else (hs + pk_ / 2, cs)
            elif pre2[i]:
                band = (hs, cs - pk_) if cooling_mode else (hs + pk_, cs)
            elif peak[i]:
                band = (hs - fx, cs + fx)                     # float beyond the deadband during the peak
            else:
                band = (hs, cs)
            want_charge = night_cheap[i] and cooled_yesterday
            want_dis = peak[i]
        T_free = T[i] + (UA * (T_out[i] - T[i]) + G[i]) / Cm
        target = min(max(T_free, band[0]), band[1])
        need = (T_free - target) * Cm                         # >0 cooling, <0 heating (kWh in this hour)
        if need > 0 and want_dis and tk["E"] > 0:
            dis[i] = min(need, tk["rate"], E[i])
        if need - dis[i] + lat[i] > cap_ref and tk["E"] > 0 and need > 0:   # peak shaving (sensible part only)
            dis[i] += max(min(need - dis[i] + lat[i] - cap_ref, tk["rate"] - dis[i], E[i] - dis[i],
                              need - dis[i]), 0.0)
        Qc[i] = max(need, 0) - dis[i]
        Qh[i] = max(-need, 0)
        if want_charge and tk["E"] > 0:
            spare = max(cap_ref - Qc[i] - lat[i], 0.0)        # charge only with spare heat-pump capacity
            ch[i] = min(tk["rate"], spare, max(tk["E"] - E[i] * (1 - tk["loss"]), 0) / tk["eta"])
        E[i + 1] = E[i] * (1 - tk["loss"]) + tk["eta"] * ch[i] - dis[i]
        T[i + 1] = target
        P[i] = (Qc[i] + lat[i]) / copc[i] + Qh[i] / coph[i] + ch[i] / copch[i]
    return _result(cfg, P, Qc, Qh, ch, dis, T, E, t, lat=lat)


# ---------------------------------------------------------------- smart controller (LP)
def smart_lp(cfg, T_out, ghi, t, size_kWh, lat=None):
    lat = np.zeros(C.N_HOURS) if lat is None else lat
    h, hp = cfg["house"], cfg["heat_pump"]
    UA, Cm = h["UA_total_kW_per_K"], h["thermal_mass_kWh_per_K"]
    hs, cs = C.deadband(cfg)
    fx = h["comfort_flex_K"]
    n = C.N_HOURS
    G = C.house_gains(cfg, T_out, ghi)
    ac, ah = 1 / C.cop_cool(cfg, T_out), 1 / C.cop_heat(cfg, T_out)
    ach = ac / hp["charging_cop_factor"]
    tk = tank_params(cfg, size_kWh)
    price, _, window = C.hourly_tariff(t)
    dem = t["demand_month"]                                   # $/kW-month, one per month
    AF = C.annuity_factor(cfg)

    iQc, iQh, ich, idis = (np.arange(n) + k * n for k in range(4))
    iT = 4 * n + np.arange(n + 1)
    iE = 5 * n + 1 + np.arange(n + 1)
    iPk = 6 * n + 2 + np.arange(12)
    iCap = 6 * n + 14
    daily = t.get("demand_rule") == "avg_daily_max"            # SRP E-16: average of daily on-peak maxima
    pk_days = np.unique(C.DAY[window]) if daily and dem.max() > 0 else np.array([], int)
    iDay = iCap + 1 + np.arange(len(pk_days))
    nv = iCap + 1 + len(pk_days)

    cost = np.zeros(nv)
    cost[iQc], cost[iQh], cost[ich] = price * ac, price * ah, price * ach
    if daily:
        mon = C.MONTH[pk_days * 24]
        n_days = np.bincount(mon, minlength=12)
        cost[iDay] = dem[mon] / n_days[mon]                   # $/kW-month spread over that month's peak days
    else:
        cost[iPk] = dem
    cost[iCap] = hp["capex_usd_per_kW_thermal"] / AF          # annualised capacity cost

    r = np.arange(n)
    # zone balance: T[t+1] - (1-UA/C) T[t] + Qc/C - Qh/C + dis/C = (UA*Tout + G)/C
    rows = np.concatenate([r, r, r, r, r]); cols = np.concatenate([iT[1:], iT[:-1], iQc, iQh, idis])
    vals = np.concatenate([np.ones(n), -(1 - UA / Cm) * np.ones(n), np.ones(n) / Cm, -np.ones(n) / Cm, np.ones(n) / Cm])
    A_zone = sp.csr_matrix((vals, (rows, cols)), shape=(n, nv)); b_zone = (UA * T_out + G) / Cm
    # tank balance: E[t+1] - (1-loss) E[t] - eta*ch + dis = 0
    rows = np.concatenate([r, r, r, r]); cols = np.concatenate([iE[1:], iE[:-1], ich, idis])
    vals = np.concatenate([np.ones(n), -(1 - tk["loss"]) * np.ones(n), -tk["eta"] * np.ones(n), np.ones(n)])
    A_tank = sp.csr_matrix((vals, (rows, cols)), shape=(n, nv)); b_tank = np.zeros(n)
    # periodic year
    A_per = sp.csr_matrix(([1, -1, 1, -1], ([0, 0, 1, 1], [iT[-1], iT[0], iE[-1], iE[0]])), shape=(2, nv))
    A_eq = sp.vstack([A_zone, A_tank, A_per]); b_eq = np.concatenate([b_zone, b_tank, [0, 0]])

    ub = []
    bub = []
    # capacity: Qc + ch + latent <= cap, Qh <= cap
    ub.append(sp.csr_matrix((np.concatenate([np.ones(n), np.ones(n), -np.ones(n)]),
                             (np.concatenate([r, r, r]), np.concatenate([iQc, ich, np.full(n, iCap)]))), shape=(n, nv)))
    bub.append(-lat)
    ub.append(sp.csr_matrix((np.concatenate([np.ones(n), -np.ones(n)]),
                             (np.concatenate([r, r]), np.concatenate([iQh, np.full(n, iCap)]))), shape=(n, nv)))
    bub.append(np.zeros(n))
    # demand: electric power (incl. latent) in the demand window <= monthly peak, or <= that day's peak (SRP)
    if dem.max() > 0:
        w = np.flatnonzero(window); m = len(w); rw = np.arange(m)
        pk_col = iDay[np.searchsorted(pk_days, C.DAY[w])] if daily else iPk[C.MONTH[w]]
        ub.append(sp.csr_matrix((np.concatenate([ac[w], ah[w], ach[w], -np.ones(m)]),
                                 (np.concatenate([rw, rw, rw, rw]),
                                  np.concatenate([iQc[w], iQh[w], ich[w], pk_col]))), shape=(m, nv)))
        bub.append(-ac[w] * lat[w])
    A_ub = sp.vstack(ub); b_ub = np.concatenate(bub)

    bounds = np.zeros((nv, 2)); bounds[:, 1] = np.inf
    bounds[ich, 1] = tk["rate"]; bounds[idis, 1] = tk["rate"]
    pre1, pre2 = C.pre_peak(t)
    flex = t["peak"] | pre1 | pre2                               # same flexibility window as the rule controller
    t_lo = np.where(flex, hs - fx, hs); t_hi = np.where(flex, cs + fx, cs)     # deadband; +/- flex around peaks
    bounds[iT[1:], 0], bounds[iT[1:], 1] = t_lo, t_hi
    bounds[iT[0]] = (t_lo[-1], t_hi[-1]); bounds[iE, 1] = tk["E"]
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(f"LP failed: {res.message}")
    x = res.x
    Qc, Qh, ch, dis = (np.maximum(x[i], 0) for i in (iQc, iQh, ich, idis))
    P = (Qc + lat) * ac + Qh * ah + ch * ach
    return _result(cfg, P, Qc, Qh, ch, dis, x[iT], x[iE], t, cap_kW=float(x[iCap]), lat=lat)


def _load_peak(r):
    """Peak heat-pump duty the house itself needs (cooling net of tank discharge, or heating); excludes charging."""
    return float(max((r["Qc"] + r["lat"]).max(), r["Qh"].max()))


def run_one(cfg, T_out, ghi, t, size_kWh, controller, tol_kW=0.02, lat=None):
    """Fixed and rule controllers size the heat pump to their own peak load WITH the tank, so every controller gets
    the downsizing credit (smart picks the size inside its LP). With a tank, they also discharge whenever the load
    exceeds the heat-pump size (peak shaving) and charge only with that unit's spare capacity. The size is the
    smallest one at which the load is always met (bisection between the heating peak and the no-tank size)."""
    if controller == "smart":
        return smart_lp(cfg, T_out, ghi, t, size_kWh, lat)
    r0 = simulate_policy(cfg, T_out, ghi, t, 0, controller, lat=lat)
    if size_kWh == 0:
        return r0
    hi = r0["hp_kW"]
    best = simulate_policy(cfg, T_out, ghi, t, size_kWh, controller, hi, lat)
    lo = float(r0["Qh"].max())                       # a cold tank cannot cut the heating peak
    while hi - lo > tol_kW:
        mid = (lo + hi) / 2
        r = simulate_policy(cfg, T_out, ghi, t, size_kWh, controller, mid, lat)
        if _load_peak(r) <= mid + 1e-6:
            hi, best = mid, r
        else:
            lo = mid
    return best
