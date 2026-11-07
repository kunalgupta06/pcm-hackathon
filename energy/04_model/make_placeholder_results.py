"""PLACEHOLDER results generator. NOT REAL PHYSICS. FORMAT DEMO ONLY.

Purpose: let the cost model run end to end before Kunal's / the thermal expert's real
results arrive. Every house and PCM number below is an invented placeholder with NO
source; every output row is stamped data_status=PLACEHOLDER. Replace the two output
files with the real ones (same columns) and rerun cost_model.py.

Usage: python make_placeholder_results.py <weather folder> <inputs.csv> <output folder>
"""
import csv, glob, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from cost_model import load_inputs, build_tariff, calendar_arrays

CITY_BY_WMO = {"722780": "Phoenix", "722020": "Miami", "723890": "Fresno", "725090": "Boston"}
# ---- PLACEHOLDER house (no source; thermal expert will replace) ----
WALL_AREA, U_WALL, UA_OTHER = 120.0, 0.35, 120.0       # m2, W/m2K, W/K
T_HEAT, T_COOL, COP_H, COP_C = 20.0, 24.0, 2.8, 3.5
SOLAR_M2, INTERNAL_W = 3.0, 400.0
K_XPS = 0.0288                                           # W/mK (inputs.csv, derived from Fine Homebuilding)
PCM_KG_M2, LATENT_KJ_KG = 5.0, 200.0                     # placeholder PCM wall
TANK_KG, TANK_KW_TH = 400.0, 3.0                         # placeholder thermal battery

def weather(path):
    rows = [r for r in list(csv.reader(open(path)))[8:] if len(r) > 13]
    loc = next(csv.reader(open(path)))
    return CITY_BY_WMO.get(loc[5], loc[1]), np.array([float(r[6]) for r in rows]), np.array([float(r[13]) for r in rows])

def loads(T, ghi, u_wall, t_wall_eff=None):
    tw = T if t_wall_eff is None else t_wall_eff
    gains = ghi * SOLAR_M2 + INTERNAL_W
    q_heat = np.maximum(0, u_wall * WALL_AREA * (T_HEAT - tw) + UA_OTHER * (T_HEAT - T) - gains) / 1000
    q_cool = np.maximum(0, u_wall * WALL_AREA * (tw - T_COOL) + UA_OTHER * (T - T_COOL) + gains) / 1000
    return q_heat, q_cool   # kW thermal

def elec(qh, qc):
    return qh / COP_H + qc / COP_C

def main(wdir, inputs, out):
    tariffs, tariff_city, *_ = load_inputs(inputs)
    cal = calendar_arrays(2026)
    hod = cal[1]
    H, M = [], []
    def add(city, case, opt, ctrl, tid, e, kg, cm, hp):
        for h, v in enumerate(e, 1):
            H.append(dict(city=city, case=case, option=opt, controller=ctrl, tariff_id=tid, hour=h, elec_kWh=round(float(v), 4)))
        M.append(dict(city=city, case=case, option=opt, controller=ctrl, tariff_id=tid, pcm_kg=kg,
                      extra_insulation_cm=cm, wall_area_m2=WALL_AREA, hp_capacity_kW=round(hp, 2), data_status="PLACEHOLDER"))
    for path in sorted(glob.glob(os.path.join(wdir, "*.epw"))):
        city, T, ghi = weather(path)
        # case 1: insulation family + PCM wall (PCM damps the wall's outdoor swing: placeholder)
        for cm in (0, 1, 2, 4, 6, 8, 12):
            u = 1 / (1 / U_WALL + cm / 100 / K_XPS)
            qh, qc = loads(T, ghi, u)
            add(city, "passive_wall", "baseline" if cm == 0 else f"insul_{cm}cm", "none", "", elec(qh, qc), 0, cm, 1.1 * max(qh.max(), qc.max()))
        mean24 = np.convolve(np.r_[T[-12:], T, T[:11]], np.ones(24) / 24, "valid")
        qh, qc = loads(T, ghi, U_WALL, mean24 + 0.5 * (T - mean24))
        add(city, "passive_wall", "pcm_wall", "none", "", elec(qh, qc), PCM_KG_M2 * WALL_AREA, 0, 1.1 * max(qh.max(), qc.max()))
        # case 2: thermal battery (cooling side), three controllers, per tariff
        qh, qc = loads(T, ghi, U_WALL)
        cap = TANK_KG * LATENT_KJ_KG / 3600  # kWh thermal
        for tid in sorted(t for t, c in tariff_city.items() if c == city):
            price, peak, _ = build_tariff(tariffs[tid], cal)
            for ctrl in ("fixed", "rule", "smart"):
                e_nb = elec(qh, qc)
                e_b, qc_b = e_nb.copy(), qc.copy()
                for d in range(365):
                    s = slice(24 * d, 24 * d + 24)
                    day_q = qc[s].copy()
                    if ctrl == "fixed":
                        order = [h for h in range(14, 20)]
                    elif ctrl == "rule":
                        order = [h for h in range(24) if peak[24 * d + h]]
                    else:
                        order = sorted(range(24), key=lambda h: -price[24 * d + h] * (day_q[h] > 0))
                    soc, used = cap, 0.0
                    for h in order:
                        take = min(day_q[h], TANK_KW_TH, soc)
                        day_q[h] -= take; soc -= take; used += take
                    qc_b[s] = day_q
                    e_day = elec(qh[s], day_q)
                    night = [h for h in range(24) if 0 <= hod[24 * d + h] < 6]
                    for h in night:
                        e_day[h] += used / len(night) / (COP_C * 0.85)  # charging at lower COP
                    e_b[s] = e_day
                hp_nb = 1.1 * max(qh.max(), qc.max()); hp_b = 1.1 * max(qh.max(), qc_b.max())
                add(city, "battery", "no_battery", ctrl, tid, e_nb, 0, 0, hp_nb)
                add(city, "battery", "battery", ctrl, tid, e_b, TANK_KG, 0, hp_b)
    os.makedirs(out, exist_ok=True)
    for name, rows in (("results_hourly.csv", H), ("results_meta.csv", M)):
        with open(os.path.join(out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("wrote", len(M), "placeholder runs")

if __name__ == "__main__":
    main(*sys.argv[1:4])
