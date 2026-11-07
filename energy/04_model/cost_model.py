"""Energy specialist cost model: 20-year cost, break-even PCM price, sensitivity.

Formula (team Hackathon Plan v2, task 8):
    20-year cost = upfront + PV(energy bills + demand charges) - smaller-heat-pump credit

Inputs
    03_inputs/inputs.csv                 every price/cost with its source (see decision_log.md)
    <results>/results_hourly.csv          hourly grid electricity per option (from Kunal / thermal expert)
    <results>/results_meta.csv            kg PCM, extra insulation cm, wall area, heat pump size per option

Results file contract (agree with Kunal):
    results_hourly.csv : city,case,option,controller,tariff_id,hour,elec_kWh
        hour = 1..8760 (EPW order). tariff_id may be blank when the run does not depend on the tariff.
    results_meta.csv   : city,case,option,controller,tariff_id,pcm_kg,extra_insulation_cm,wall_area_m2,hp_capacity_kW,data_status
    case   = passive_wall  -> options: baseline, insul_<cm>cm (several thicknesses), pcm_wall
    case   = battery       -> options: no_battery, battery ; controllers: fixed, rule, smart

Usage
    python cost_model.py ../03_inputs/inputs.csv <results_folder> <output_folder>
"""
import csv, os, sys, datetime
from collections import defaultdict
import numpy as np

HOURS = 8760

# ----------------------------------------------------------------- inputs
def load_inputs(path):
    rows = list(csv.DictReader(open(path, newline="")))
    tariffs = defaultdict(lambda: defaultdict(dict))   # tariffs[tid][season][key] = row
    tariff_city, costs, finance, cal = {}, {}, {}, {}
    for r in rows:
        if r["section"] == "tariff":
            tariffs[r["tariff_id"]][r["season"]][r["key"]] = r
            tariff_city[r["tariff_id"]] = r["city"]
        elif r["section"] == "cost":
            costs[r["key"]] = r
        elif r["section"] == "finance":
            finance[r["key"]] = r
        elif r["section"] == "calendar":
            cal[r["key"]] = r
    return tariffs, tariff_city, costs, finance, cal

def _num(r, field="value"):
    v = r.get(field, "")
    return float(v) if v not in ("", None) else None

def _months(s):
    out = []
    for part in s.split(";"):                  # several ranges allowed, e.g. "5-6;9-10"
        a, b = [int(x) for x in part.split("-")]
        out += list(range(a, b + 1)) if a <= b else list(range(a, 13)) + list(range(1, b + 1))
    return out

def _hours(s):
    out = set()
    for part in s.split(";"):
        a, b = [int(x) for x in part.split("-")]
        out.update(range(a, b))
    return out

def _get(tdef, season, key):
    if key in tdef.get(season, {}):
        return tdef[season][key]
    return tdef.get("all", {}).get(key)

def calendar_arrays(year=2026):
    t0 = datetime.datetime(year, 1, 1)
    month, hod, weekday = np.zeros(HOURS, int), np.zeros(HOURS, int), np.zeros(HOURS, bool)
    for h in range(HOURS):
        d = t0 + datetime.timedelta(hours=h)
        month[h], hod[h], weekday[h] = d.month, d.hour, d.weekday() < 5
    return month, hod, weekday

def build_tariff(tdef, cal_arrays, tier="value"):
    """Hourly price (USD/kWh), on-peak flag, and demand rate per month (USD/kW-month)."""
    month, hod, weekday = cal_arrays
    seasons = [s for s in tdef if s != "all"] or ["all"]
    season_of_month = {}
    for s in seasons:
        mrow = _get(tdef, s, "months")
        for m in _months(mrow["value"]):
            season_of_month[m] = s
    price, peak = np.zeros(HOURS), np.zeros(HOURS, bool)
    demand = np.zeros(13)
    for h in range(HOURS):
        s = season_of_month[month[h]]
        days = _get(tdef, s, "peak_days")["value"]
        dayok = weekday[h] if days == "weekdays" else True
        is_peak = dayok and hod[h] in _hours(_get(tdef, s, "peak_hours")["value"])
        r_peak, r_off = _get(tdef, s, "price_peak"), _get(tdef, s, "price_offpeak")
        p_peak = _num(r_peak, tier) if _num(r_peak, tier) is not None else _num(r_peak)
        p_off = _num(r_off, tier) if _num(r_off, tier) is not None else _num(r_off)
        p = p_peak if is_peak else p_off
        # optional mid-peak tier (e.g. SMUD TOD): price_midpeak + midpeak_hours [+ midpeak_days, default weekdays]
        mid = _get(tdef, s, "price_midpeak")
        if mid and not is_peak:
            md = _get(tdef, s, "midpeak_days")
            mdok = weekday[h] if (md is None or md["value"] == "weekdays") else True
            if mdok and hod[h] in _hours(_get(tdef, s, "midpeak_hours")["value"]):
                p = _num(mid)
        # super-off-peak: superoffpeak_hours on superoffpeak_days (default weekdays, the original behaviour),
        # plus optional superoffpeak_hours_weekend (e.g. SDG&E TOU-DR1 10am-2pm on weekends)
        sop = _get(tdef, s, "price_superoffpeak")
        if sop and not is_peak:
            sd = _get(tdef, s, "superoffpeak_days")
            sdok = weekday[h] if (sd is None or sd["value"] == "weekdays") else True
            hit = sdok and hod[h] in _hours(_get(tdef, s, "superoffpeak_hours")["value"])
            we = _get(tdef, s, "superoffpeak_hours_weekend")
            hit = hit or (we is not None and not weekday[h] and hod[h] in _hours(we["value"]))
            if hit:
                p = _num(sop)
        price[h], peak[h] = p, is_peak
    # optional per-month energy adder (e.g. APS dated adjustors): "a1;a2;...;a12" USD/kWh, on every hour
    add = _get(tdef, "all", "price_adder_by_month")
    if add:
        adders = [float(x) for x in add["value"].split(";")]
        price = price + np.array([adders[m - 1] for m in month])
    for m in range(1, 13):
        demand[m] = _num(_get(tdef, season_of_month[m], "demand_charge"))
    return price, peak, demand

# ---------------------------------------------------------------- results
def load_results(folder):
    hourly = defaultdict(lambda: np.zeros(HOURS))
    for r in csv.DictReader(open(os.path.join(folder, "results_hourly.csv"), newline="")):
        k = (r["city"], r["case"], r["option"], r["controller"], r["tariff_id"])
        hourly[k][int(r["hour"]) - 1] = float(r["elec_kWh"])
    meta = {}
    for r in csv.DictReader(open(os.path.join(folder, "results_meta.csv"), newline="")):
        k = (r["city"], r["case"], r["option"], r["controller"], r["tariff_id"])
        meta[k] = r
    return hourly, meta

def bills(elec, price, peak, demand, month, rule="monthly_max"):
    energy = float((elec * price).sum())
    dem = 0.0
    day = np.arange(HOURS) // 24
    for m in range(1, 13):
        mask = (month == m) & peak
        if demand[m] > 0 and mask.any():
            if rule == "avg_daily_max":                    # SRP E-16: average of daily on-peak maxima
                kw = float(np.mean([elec[mask & (day == d)].max() for d in np.unique(day[mask])]))
            else:                                          # single highest on-peak hour (APS R-3)
                kw = float(elec[mask].max())               # hourly kWh = average kW over the hour
            dem += demand[m] * kw
    return energy, dem

def pv_factor(r, n):
    return sum(1.0 / (1.0 + r) ** t for t in range(1, n + 1))

# ------------------------------------------------------------- analysis
def run(inputs_path, results_dir, out_dir, overrides=None, tier="value", write=True):
    tariffs, tariff_city, costs, finance, cal = load_inputs(inputs_path)
    ov = overrides or {}
    r = ov.get("discount", _num(finance["discount_rate_real"]))
    n = int(_num(finance["lifetime"]))
    c_ins = ov.get("insul", _num(costs["insulation_cost_xps"]))
    c_hp = ov.get("hp", _num(costs["heat_pump_cost_per_kW"]))
    pvf = pv_factor(r, n)
    cal_arr = calendar_arrays(int(_num(cal["reference_year_for_weekdays"])))
    month = cal_arr[0]
    hourly, meta = load_results(results_dir)
    status = {m["data_status"] for m in meta.values()}
    data_status = "PLACEHOLDER" if "PLACEHOLDER" in status else "REAL"

    tariff_cache = {tid: build_tariff(tariffs[tid], cal_arr, tier) for tid in tariffs}
    breakdown, breakeven = [], []

    def annual(key, tid):
        price, peak, dem = tariff_cache[tid]
        rule = _get(tariffs[tid], "all", "demand_rule")
        return bills(hourly[key], price, peak, dem, month, rule["value"] if rule else "monthly_max")

    cities = sorted({k[0] for k in meta})
    for city in cities:
        for tid in sorted(t for t, c in tariff_city.items() if c == city):
            # ---------- case 1: passive wall vs equal-budget insulation
            ins = []
            base_key = None
            for k, m in meta.items():
                if k[0] != city or k[1] != "passive_wall":
                    continue
                e, d = annual(k, tid)
                op = pvf * (e + d)
                breakdown.append(dict(city=city, tariff_id=tid, case="passive_wall", option=k[2], controller=k[3],
                                      annual_energy_USD=round(e, 2), annual_demand_USD=round(d, 2),
                                      pv_operating_USD=round(op, 2), pcm_kg=m["pcm_kg"],
                                      extra_insulation_cm=m["extra_insulation_cm"], hp_capacity_kW=m["hp_capacity_kW"],
                                      data_status=data_status))
                if k[2] == "pcm_wall":
                    pcm = (k, m, op)
                elif k[2] == "baseline" or k[2].startswith("insul_"):
                    ins.append((float(m["extra_insulation_cm"]), op, float(m["hp_capacity_kW"]), float(m["wall_area_m2"])))
                    if k[2] == "baseline":
                        base_key = k
            if ins and base_key:
                ins.sort()
                t_arr = np.array([x[0] for x in ins]); op_arr = np.array([x[1] for x in ins]); hp_arr = np.array([x[2] for x in ins])
                area = ins[0][3]
                _, mp, op_p = pcm
                kg, hp_p = float(mp["pcm_kg"]), float(mp["hp_capacity_kW"])
                hp_base = float(meta[base_key]["hp_capacity_kW"])
                pcm_net = op_p - (hp_base - hp_p) * c_hp
                be, note = None, ""
                for p in np.arange(0.0, 50.0001, 0.01):
                    t = p * kg / (c_ins * area)
                    if t > t_arr[-1]:
                        note = "insulation thickness beyond simulated range; break-even may be lower"
                    ins_net = np.interp(t, t_arr, op_arr) - (hp_base - np.interp(t, t_arr, hp_arr)) * c_hp
                    if pcm_net >= ins_net:
                        be = round(float(p), 2); break
                breakeven.append(dict(city=city, tariff_id=tid, case="passive_wall", controller="none",
                                      comparison="PCM wall vs same money on extra insulation",
                                      breakeven_pcm_USD_per_kg=("never wins" if be == 0.0 else be if be is not None else ">50"),
                                      pcm_kg=kg, note=note, data_status=data_status))
            # ---------- case 2: thermal battery vs no battery (same controller)
            for ctrl in ("fixed", "rule", "smart"):
                kb = (city, "battery", "battery", ctrl, tid)
                kn = (city, "battery", "no_battery", ctrl, tid)
                if kb not in meta or kn not in meta:
                    continue
                eb, db = annual(kb, tid); en, dn = annual(kn, tid)
                for k, e, d in ((kb, eb, db), (kn, en, dn)):
                    breakdown.append(dict(city=city, tariff_id=tid, case="battery", option=k[2], controller=ctrl,
                                          annual_energy_USD=round(e, 2), annual_demand_USD=round(d, 2),
                                          pv_operating_USD=round(pvf * (e + d), 2), pcm_kg=meta[k]["pcm_kg"],
                                          extra_insulation_cm=meta[k]["extra_insulation_cm"],
                                          hp_capacity_kW=meta[k]["hp_capacity_kW"], data_status=data_status))
                kg = float(meta[kb]["pcm_kg"])
                credit = (float(meta[kn]["hp_capacity_kW"]) - float(meta[kb]["hp_capacity_kW"])) * c_hp
                pv_sav = pvf * ((en + dn) - (eb + db))
                be = (pv_sav + credit) / kg
                breakeven.append(dict(city=city, tariff_id=tid, case="battery", controller=ctrl,
                                      comparison="PCM thermal battery vs no battery (same controller)",
                                      breakeven_pcm_USD_per_kg=round(be, 2), pcm_kg=kg,
                                      note="never wins" if be <= 0 else "", data_status=data_status))
    # control premium
    premium = []
    idx = {(b["city"], b["tariff_id"], b["controller"]): b for b in breakeven if b["case"] == "battery"}
    for (city, tid, ctrl), b in idx.items():
        if ctrl == "smart" and (city, tid, "fixed") in idx:
            premium.append(dict(city=city, tariff_id=tid,
                                breakeven_fixed=idx[(city, tid, "fixed")]["breakeven_pcm_USD_per_kg"],
                                breakeven_rule=idx.get((city, tid, "rule"), {}).get("breakeven_pcm_USD_per_kg", ""),
                                breakeven_smart=b["breakeven_pcm_USD_per_kg"],
                                control_premium_USD_per_kg=round(b["breakeven_pcm_USD_per_kg"] - idx[(city, tid, "fixed")]["breakeven_pcm_USD_per_kg"], 2),
                                data_status=data_status))
    if write:
        os.makedirs(out_dir, exist_ok=True)
        tag = "_PLACEHOLDER" if data_status == "PLACEHOLDER" else ""
        for name, rows in (("cost_breakdown", breakdown), ("breakeven", breakeven), ("control_premium", premium)):
            if rows:
                with open(os.path.join(out_dir, f"{name}{tag}.csv"), "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return breakeven, data_status

def sensitivity(inputs_path, results_dir, out_dir):
    """One-at-a-time sensitivity of break-even PCM price (team plan: PCM price; task list: tariff, discount)."""
    _, _, costs, finance, _ = load_inputs(inputs_path)
    cases = [("base", {}, "value"),
             ("discount 2% (OMB A-4 2023)", {"discount": 0.02}, "value"),
             ("discount 7% (OMB A-4 2003)", {"discount": 0.07}, "value"),
             ("heat pump $/kW high (NYSERDA)", {"hp": _num(costs["heat_pump_cost_per_kW"], "high")}, "value"),
             ("insulation cost low (EPS)", {"insul": _num(costs["insulation_cost_xps"], "low")}, "value"),
             ("insulation cost high (polyiso)", {"insul": _num(costs["insulation_cost_xps"], "high")}, "value"),
             ("lower price tier (baseline credit / <=1000 kWh)", {}, "low")]
    rows, status = [], "REAL"
    for label, ov, tier in cases:
        be, status = run(inputs_path, results_dir, out_dir, ov, tier, write=False)
        for b in be:
            rows.append(dict(scenario=label, city=b["city"], tariff_id=b["tariff_id"], case=b["case"],
                             controller=b["controller"], breakeven_pcm_USD_per_kg=b["breakeven_pcm_USD_per_kg"],
                             data_status=status))
    # PCM market prices to compare against
    for t in ("pcm_price_paraffin", "pcm_price_biobased", "pcm_price_salt_hydrate"):
        rows.append(dict(scenario=f"market price {t}", city="", tariff_id="", case="reference", controller="",
                         breakeven_pcm_USD_per_kg=f"{costs[t]['value']} ({costs[t]['low']}-{costs[t]['high']})",
                         data_status="OFFICIAL/DERIVED"))
    tag = "_PLACEHOLDER" if status == "PLACEHOLDER" else ""
    with open(os.path.join(out_dir, f"sensitivity{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def equal_budget_table(inputs_path, out_dir):
    """Step 6 handoff to Kunal: cm of extra insulation that the same money buys (REAL, depends only on costs)."""
    _, _, costs, _, _ = load_inputs(inputs_path)
    c = _num(costs["insulation_cost_xps"])
    rows = []
    for kgm2 in (2, 4, 6, 8):
        for p in range(1, 9):
            rows.append(dict(pcm_kg_per_m2_wall=kgm2, pcm_price_USD_per_kg=p,
                             budget_USD_per_m2=kgm2 * p, extra_xps_cm=round(kgm2 * p / c, 2),
                             source="inputs.csv insulation_cost_xps = %.2f USD/m2/cm" % c))
    with open(os.path.join(out_dir, "equal_budget_insulation_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    inp, res, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    equal_budget_table(inp, out)
    be, status = run(inp, res, out)
    sensitivity(inp, res, out)
    print("data_status:", status)
    for b in be:
        print(b["city"], b["tariff_id"], b["case"], b["controller"], b["breakeven_pcm_USD_per_kg"])
