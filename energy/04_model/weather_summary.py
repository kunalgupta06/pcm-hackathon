"""Summarise TMY3 EPW weather files into the climate statistics used by the team.

Usage: python weather_summary.py <folder with .epw files> <output csv>
EPW column layout follows the EnergyPlus Auxiliary Programs guide (field 6 = dry-bulb
temperature in C, field 13 = global horizontal irradiation in Wh/m2).
"""
import csv, glob, os, sys
from collections import defaultdict

CITY_BY_WMO = {"722780": "Phoenix", "722020": "Miami", "723890": "Fresno", "725090": "Boston"}

def read_epw(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    loc = rows[0]
    data = [r for r in rows[8:] if len(r) > 13]
    return loc, data

def summarise(path):
    loc, data = read_epw(path)
    temps = [float(r[6]) for r in data]
    ghi = [float(r[13]) for r in data]
    days = defaultdict(list)
    for r in data:
        days[(int(r[1]), int(r[2]))].append(float(r[6]))
    swings = {k: max(v) - min(v) for k, v in days.items()}
    summer = [k for k in days if k[0] in (6, 7, 8)]
    july = [k for k in days if k[0] == 7]
    hdd = sum(max(0.0, 18.0 - sum(v) / len(v)) for v in days.values())
    cdd = sum(max(0.0, sum(v) / len(v) - 18.0) for v in days.values())
    return {
        "city": CITY_BY_WMO.get(loc[5], loc[1]),
        "station": loc[1], "state": loc[2], "wmo": loc[5], "source_type": loc[4],
        "lat": loc[6], "lon": loc[7], "utc_offset_h": loc[8],
        "annual_mean_C": round(sum(temps) / len(temps), 1),
        "july_mean_daily_max_C": round(sum(max(days[k]) for k in july) / len(july), 1),
        "july_mean_daily_min_C": round(sum(min(days[k]) for k in july) / len(july), 1),
        "mean_daily_swing_annual_C": round(sum(swings.values()) / len(swings), 1),
        "mean_daily_swing_summer_C": round(sum(swings[k] for k in summer) / len(summer), 1),
        "HDD18_Cday": round(hdd), "CDD18_Cday": round(cdd),
        "summer_nights_min_below_22C_share": round(sum(1 for k in summer if min(days[k]) < 22) / len(summer), 2),
        "annual_GHI_kWh_m2": round(sum(ghi) / 1000),
        "file": os.path.basename(path),
    }

if __name__ == "__main__":
    folder, out = sys.argv[1], sys.argv[2]
    rows = [summarise(p) for p in sorted(glob.glob(os.path.join(folder, "*.epw")))]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    for r in rows: print(r)
