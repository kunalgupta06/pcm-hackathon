"""
Cross-check our house model against the team's standard-house baseline v2 (baseline_v2/; ISO 13790 5R1C,
68/78 F deadband, RESNET gains, latent cooling, TMYx 2011-2025 weather).

    python compare_baseline.py

1. Annual check at OUR house size (150 m2, 1 story): exports the calculator grid to baseline_v2/house_grid.csv
   and compares annual heating / cooling electricity -> results/baseline_v2_comparison.csv.
2. Hourly check on v2's OWN reference house (2,000 ft2, 1 story) with the same TMYx weather: our 1R1C model built
   from the same specification (house_v2.derive) against v2's hourly_weather_and_loads.csv.gz, with ASHRAE
   Guideline 14 style statistics (NMBE, CV(RMSE)) at hourly, daily and monthly resolution
   -> results/baseline_v2_hourly_check.csv.
Both use the fixed deadband thermostat and no PCM (our case-2 baseline).
"""
import json
import os
import re

import numpy as np
import pandas as pd

import case2_battery as B
import common as C
import house_v2

HTML = os.path.join(C.HERE, "baseline_v2", "House_energy_calculator.html")
HOURLY = os.path.join(C.HERE, "baseline_v2", "hourly_weather_and_loads.csv.gz")
GRID_CSV = os.path.join(C.HERE, "baseline_v2", "house_grid.csv")
M2_TO_FT2 = house_v2.FT2_PER_M2
CITY_ID = {"Phoenix": "Phoenix, AZ", "Miami": "Miami, FL", "Fresno": "Fresno, CA", "Boston": "Boston, MA",
           "Sacramento": "Sacramento, CA", "San Diego": "San Diego, CA"}


def load_grid(path=HTML):
    html = open(path, encoding="utf-8").read()
    data = json.loads(re.search(r'<script id="house-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    rows = []
    for d in data:
        for stories, grid in d["grid"].items():
            for a, h, c, b, over in grid:
                rows.append(dict(city_id=d["city_id"], state=d["state"], state_avg_price_cents_kWh=d["price"],
                                 stories=int(stories), floor_area_ft2=a, heating_kWh=h, cooling_kWh=c,
                                 backup_kWh=b, cooling_capacity_exceed_h=over))
    return pd.DataFrame(rows)


def at_area(grid, city_id, area_ft2, stories=1):
    g = grid[(grid.city_id == city_id) & (grid.stories == stories)].sort_values("floor_area_ft2")
    return {k: float(np.interp(area_ft2, g.floor_area_ft2, g[k])) for k in ("heating_kWh", "cooling_kWh", "backup_kWh")}


def our_hourly(cfg, city):
    """Hourly heating and cooling electricity (kWh) of our house, fixed deadband thermostat, no tank."""
    T, ghi = C.city_weather(cfg, city)
    t = C.tariff_for(cfg, city, cfg["tariffs"][0])
    lat = B.latent_load(cfg, city, T, ghi, t)
    r = B.simulate_policy(cfg, T, ghi, t, 0, "fixed", lat=lat)
    return r["Qh"] / C.cop_heat(cfg, T), (r["Qc"] + lat) / C.cop_cool(cfg, T)


def g14(ours, ref):
    """NMBE and CV(RMSE) in % of the reference mean (ASHRAE Guideline 14 definitions, p = 1)."""
    n, mean = len(ref), ref.mean()
    return (100 * (ref - ours).sum() / ((n - 1) * mean),
            100 * np.sqrt(((ref - ours) ** 2).sum() / (n - 1)) / mean)


def main():
    pd.set_option("display.width", 220)
    grid = load_grid()
    grid.to_csv(GRID_CSV, index=False)
    cfg = C.load_inputs()
    area_ft2 = cfg["house"]["floor_area_m2"] * M2_TO_FT2

    # ---- 1. annual at our size
    rows = []
    for city, cid in CITY_ID.items():
        if city not in cfg["cities"]:
            continue
        b = at_area(grid, cid, area_ft2)
        he, ce = our_hourly(cfg, city)
        h, c = float(he.sum()), float(ce.sum())
        rows.append(dict(city=city, floor_area_ft2=round(area_ft2), ours_heating_kWh=h, v2_heating_kWh=b["heating_kWh"],
                         ours_cooling_kWh=c, v2_cooling_kWh=b["cooling_kWh"], ours_total_kWh=h + c,
                         v2_total_kWh=b["heating_kWh"] + b["cooling_kWh"],
                         ratio_total=(h + c) / (b["heating_kWh"] + b["cooling_kWh"])))
    ann = pd.DataFrame(rows)
    ann.to_csv(os.path.join(C.HERE, "results", "baseline_v2_comparison.csv"), index=False)
    show = ann.copy()
    show.columns = ["city", "ft2", "heat ours", "heat v2", "cool ours", "cool v2", "total ours", "total v2", "ratio"]
    print(f"1) ANNUAL HVAC electricity (kWh), our house: 1 story, {area_ft2:.0f} ft2, same TMYx weather as v2.")
    print(show.round({"heat ours": 0, "heat v2": 0, "cool ours": 0, "cool v2": 0, "total ours": 0, "total v2": 0,
                      "ratio": 2}).to_string(index=False))

    # ---- 2. hourly on v2's reference house (2,000 ft2) with the same weather
    ref_m2 = 2000 / M2_TO_FT2
    cfg2 = dict(cfg, house={**cfg["house"], **house_v2.derive(ref_m2)})
    want = set(CITY_ID.values())
    v2 = pd.concat(c[c.city_id.isin(want)] for c in pd.read_csv(HOURLY, chunksize=200000))
    out = []
    for city, cid in CITY_ID.items():
        if city not in cfg["cities"]:
            continue
        ref = v2[v2.city_id == cid].sort_values(["month", "day", "hour_ending_local_standard"])
        T_ours, _ = C.city_weather(cfg2, city)
        assert np.allclose(ref.outdoor_temp_C.values, T_ours, atol=0.05), f"weather mismatch for {city}"
        rh = (ref.heatpump_heating_kWh + ref.resistance_heating_kWh).values
        rc = ref.cooling_electricity_kWh.values
        he, ce = our_hourly(cfg2, city)
        tot_o, tot_r = he + ce, rh + rc
        rec = dict(city=city)
        for lab, o, r in (("hourly", tot_o, tot_r), ("daily", tot_o.reshape(365, 24).sum(1), tot_r.reshape(365, 24).sum(1))):
            rec[f"NMBE_{lab}_%"], rec[f"CVRMSE_{lab}_%"] = g14(o, r)
        mo = C.MONTH
        mo_o = np.bincount(mo, tot_o, 12); mo_r = np.bincount(mo, tot_r, 12)
        rec["NMBE_monthly_%"], rec["CVRMSE_monthly_%"] = g14(mo_o, mo_r)
        rec["r_hourly"] = float(np.corrcoef(tot_o, tot_r)[0, 1])
        rec.update(ours_annual_kWh=tot_o.sum(), v2_annual_kWh=tot_r.sum(),
                   ours_heat_kWh=he.sum(), v2_heat_kWh=rh.sum(), ours_cool_kWh=ce.sum(), v2_cool_kWh=rc.sum(),
                   ours_peak_cool_kW=ce.max(), v2_peak_cool_kW=rc.max(), ours_peak_heat_kW=he.max(), v2_peak_heat_kW=rh.max())
        out.append(rec)
    hr = pd.DataFrame(out)
    hr.to_csv(os.path.join(C.HERE, "results", "baseline_v2_hourly_check.csv"), index=False)
    s = hr[["city", "ours_annual_kWh", "v2_annual_kWh", "NMBE_hourly_%", "CVRMSE_hourly_%", "CVRMSE_daily_%",
            "CVRMSE_monthly_%", "r_hourly", "ours_peak_cool_kW", "v2_peak_cool_kW", "ours_peak_heat_kW", "v2_peak_heat_kW"]]
    s.columns = ["city", "ours kWh", "v2 kWh", "NMBE h %", "CV(RMSE) h %", "CV d %", "CV m %", "r h",
                 "peak cool ours", "peak cool v2", "peak heat ours", "peak heat v2"]
    print("\n2) HOURLY check on v2's reference house (2,000 ft2, 1 story), same TMYx weather, total HVAC electricity."
          "\n   ASHRAE Guideline 14 calibration criteria for reference: hourly NMBE within +/-10 %, CV(RMSE) <= 30 %;"
          " monthly NMBE +/-5 %, CV(RMSE) <= 15 %.")
    print(s.round(2).to_string(index=False))
    print(f"\n-> {os.path.relpath(GRID_CSV, C.HERE)}, results/baseline_v2_comparison.csv, "
          f"results/baseline_v2_hourly_check.csv")


if __name__ == "__main__":
    main()
