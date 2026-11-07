"""
Merge the two team input sheets into one inputs file in the energy model's format.

    energy/03_inputs/inputs.csv                 energy specialist (cities, 8 tariffs, costs, finance)
    energy/03_inputs/PCM_Hackathon_Defaults.csv  team defaults sheet (PCM properties, system cost, SMUD / SDG&E
                                                 tariffs, alternative values for some items)

Both merged files add Sacramento (SMUD R-TOD) and San Diego (SDG&E TOU-DR1) as cities, each with its real TOU
tariff plus a HYPOTHETICAL "+ APS demand charge" version (same rule as decision D6). They differ only where the
two sheets conflict:

    source="energy"   (default)  conflicts resolved with inputs.csv
    source="defaults"            conflicts resolved with the defaults sheet:
        heat pump $/kW 1300 installed, with a 15-yr life (replacement in yr 15, salvage at yr 20)
        Miami FPL RTR-1 0.269 / 0.06 $/kWh, Boston flat 0.36 $/kWh,
        microencapsulated PCM 10 $/kg (9.7-14.3), insulation = R-13 -> R-15 marginal cost

Output: energy/03_inputs/merged/inputs_<source>.csv  (regenerated on every run; edit the two source sheets).
    python merge_inputs.py            # writes both
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INP = os.path.join(HERE, "energy", "03_inputs")
ENERGY_CSV = os.path.join(INP, "inputs.csv")
DEFAULTS_CSV = os.path.join(INP, "PCM_Hackathon_Defaults.csv")
OUT_DIR = os.path.join(INP, "merged")
SOURCES = ("energy", "defaults")

SMUD_URL = "https://smud.org/-/media/Documents/Rate-Information/Rates/1-R-TOD.ashx"
SDGE_URL = "https://www.sdge.com/sites/default/files/regulatory/1-1-26%20Schedule%20TOU-DR1%20Total%20Rates%20Table.pdf"
APS_URL = "https://www.aps.com/demandplan"
ONEBUILDING = ("https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/"
               "USA_United_States_of_America/CA_California/")
DFLT_SRC = "PCM_Hackathon_Defaults.csv"


def _defaults():
    return {r["key"]: r for r in csv.DictReader(open(DEFAULTS_CSV, newline="", encoding="utf-8"))}


def _row(section, key, value, unit="", city="", tariff_id="", season="", low="", high="", status="", source="",
         url="", note=""):
    return dict(section=section, key=key, city=city, tariff_id=tariff_id, season=season, value=value, unit=unit,
                low=low, high=high, status=status, source=source, url=url, note=note)


def _tariff(tid, city, name, status, url, seasons, common, per_season, demand=None):
    """seasons: {season: months}; common: {key: value} for season 'all'; per_season: {season: {key: value}}."""
    rows = [_row("tariff", "name", name, "text", city, tid, "all", status=status, source=DFLT_SRC, url=url)]
    for s, months in seasons.items():
        rows.append(_row("tariff", "months", months, "month list", city, tid, s, status="OFFICIAL", url=url))
    for k, v in common.items():
        rows.append(_row("tariff", k, v, "", city, tid, "all", status="OFFICIAL", source=DFLT_SRC, url=url))
    for s, kv in per_season.items():
        for k, v in kv.items():
            rows.append(_row("tariff", k, v, "USD/kWh" if k.startswith("price") else "", city, tid, s,
                             status="OFFICIAL", source=DFLT_SRC, url=url))
    if demand is None:
        rows.append(_row("tariff", "demand_charge", 0, "USD/kW-month", city, tid, "all", status="OFFICIAL",
                         source=DFLT_SRC, url=url, note="No residential demand charge"))
    else:
        for s, v in demand.items():
            rows.append(_row("tariff", "demand_charge", v, "USD/kW-month", city, tid, s, status="HYPOTHETICAL",
                             source=f"{DFLT_SRC} demand_charge_{s} (APS R-3 base, what-if)", url=APS_URL,
                             note="Synthetic Tariff B: label as assumed (decision D6)"))
    return rows


def california_rows(d):
    v = lambda k: d[k]["default"]
    rows = [
        _row("city", "weather_file", "USA_CA_Sacramento.Exec.AP.724830_TMY3.epw", "file", "Sacramento",
             status="OFFICIAL", source="TMY3 from climate.onebuilding.org (CA folder), file dated 2026-03-16",
             url=ONEBUILDING, note="Station Sacramento Exec AP WMO 724830"),
        _row("city", "weather_file", "USA_CA_San.Diego.Intl.AP-Lindbergh.Field.722900_TMY3.epw", "file",
             "San Diego", status="OFFICIAL", source="TMY3 from climate.onebuilding.org (CA folder), file dated 2026-03-16",
             url=ONEBUILDING, note="Station San Diego Intl AP-Lindbergh Field WMO 722900"),
        _row("city", "utility", "Sacramento Municipal Utility District (SMUD)", "text", "Sacramento",
             status="OFFICIAL", url=SMUD_URL),
        _row("city", "utility", "San Diego Gas & Electric (SDG&E)", "text", "San Diego", status="OFFICIAL", url=SDGE_URL),
    ]
    # SMUD R-TOD (RT02): summer Jun-Sep peak 5-8 pm weekdays, mid-peak noon-5 pm and 8 pm-midnight weekdays,
    # off-peak otherwise (all weekend); non-summer Oct-May peak 5-8 pm weekdays, off otherwise.
    smud = dict(seasons={"summer": "6-9", "winter": "10-5"},
                common={"peak_hours": "17-20", "peak_days": "weekdays"},
                per_season={"summer": {"price_peak": v("sacto_smud_summer_peak"), "price_offpeak": v("sacto_smud_summer_off"),
                                       "price_midpeak": v("sacto_smud_summer_mid"), "midpeak_hours": "12-17;20-24",
                                       "midpeak_days": "weekdays"},
                            "winter": {"price_peak": v("sacto_smud_winter_peak"), "price_offpeak": v("sacto_smud_winter_off")}})
    # SDG&E TOU-DR1 (official, eff. Jan 1 2026): on-peak 4-9 pm every day; super off-peak midnight-6 am every day
    # and 10 am-2 pm on weekends (the extra March-April weekday 10-2 window is not modelled).
    sdge = dict(seasons={"summer": "6-10", "winter": "11-5"},
                common={"peak_hours": "16-21", "peak_days": "all", "superoffpeak_hours": "0-6",
                        "superoffpeak_days": "all", "superoffpeak_hours_weekend": "10-14"},
                per_season={"summer": {"price_peak": v("sandiego_official_summer_on"),
                                       "price_offpeak": v("sandiego_official_summer_off"),
                                       "price_superoffpeak": v("sandiego_official_summer_superoff")},
                            "winter": {"price_peak": v("sandiego_official_winter_on"),
                                       "price_offpeak": v("sandiego_official_winter_off"),
                                       "price_superoffpeak": v("sandiego_official_winter_superoff")}})
    dem = {"summer": v("demand_charge_summer"), "winter": v("demand_charge_winter")}
    rows += _tariff("SAC_TOU", "Sacramento", "SMUD Residential Time-of-Day (R-TOD, RT02)", "OFFICIAL", SMUD_URL, **smud)
    rows += _tariff("SAC_TOUD", "Sacramento", "HYPOTHETICAL: SMUD R-TOD energy prices + APS residential demand charge",
                    "HYPOTHETICAL", SMUD_URL, **smud, demand=dem)
    rows += _tariff("SD_TOU", "San Diego", "SDG&E TOU-DR1 (official, eff. Jan 1 2026)", "OFFICIAL", SDGE_URL, **sdge)
    rows += _tariff("SD_TOUD", "San Diego", "HYPOTHETICAL: SDG&E TOU-DR1 energy prices + APS residential demand charge",
                    "HYPOTHETICAL", SDGE_URL, **sdge, demand=dem)
    return rows


def apply_defaults_conflicts(rows, d):
    """Replace the values the two sheets disagree on with the defaults sheet's values."""
    f = lambda k, c="default": float(d[k][c])
    r_ = next(float(r["value"]) for r in rows if r["section"] == "finance" and r["key"] == "discount_rate_real")
    n = int(next(float(r["value"]) for r in rows if r["section"] == "finance" and r["key"] == "lifetime"))
    life = f("heatpump_life")
    # capacity bought now + replacement at `life` (if inside the analysis) - linear salvage value at the end
    k = 1.0
    if life < n:
        # the replacement unit bought in yr `life` still has (2*life - n)/life of its life left at yr n
        k += (1 + r_) ** -life - ((2 * life - n) / life) * (1 + r_) ** -n
    hp = f("heatpump_cost")

    # R-13 -> R-15 batt: $1.94/m2 buys dR = 2 * 0.1761 m2K/W; XPS gives 1/(100*k) m2K/W per cm
    k_xps = next(float(r["value"]) for r in rows if r["key"] == "insulation_conductivity_xps")
    ins = f("ins_marginal_r13_to_r15") / (2 * 0.1761) / (100 * k_xps)
    ins_lo = f("ins_marginal_r13_to_r15", "low") / (2 * 0.1761) / (100 * k_xps)
    ins_hi = f("ins_marginal_r13_to_r15", "high") / (2 * 0.1761) / (100 * k_xps)

    tag = f"{DFLT_SRC} (source=defaults)"
    for r in rows:
        key, tid = r["key"], r["tariff_id"]
        if r["section"] == "cost" and key == "heat_pump_cost_per_kW":
            r.update(value=round(hp * k, 1), low=round(f("heatpump_cost", "low") * k, 1),
                     high=round(f("heatpump_cost", "high") * k, 1), status="DERIVED", source=tag,
                     url=d["heatpump_cost"]["url"],
                     note=f"Installed {hp:g} $/kW x {k:.3f} life factor ({life:g}-yr life in a {n}-yr analysis at "
                          f"{r_:g}: replacement in yr {life:g}, linear salvage at yr {n})")
        elif r["section"] == "cost" and key == "pcm_price_paraffin":
            r.update(value=f("pcm_microencapsulated_price"), low=f("pcm_microencapsulated_price", "low"),
                     high=f("pcm_microencapsulated_price", "high"), status="SOURCED", source=tag,
                     url=d["pcm_microencapsulated_price"]["url"], note="Microencapsulated PCM product (Kosny 2013, OLD)")
        elif r["section"] == "cost" and key == "insulation_cost_xps":
            r.update(value=round(ins, 3), low=round(ins_lo, 3), high=round(ins_hi, 3), status="DERIVED", source=tag,
                     url=d["ins_marginal_r13_to_r15"]["url"],
                     note="R-13 -> R-15 marginal cost converted to $ per m2 per cm-of-XPS-equivalent R")
        elif r["section"] == "tariff" and tid in ("MIA_TOU", "MIA_TOUD") and key in ("price_peak", "price_offpeak"):
            src = "miami_rtr1_on" if key == "price_peak" else "miami_rtr1_off"
            r.update(value=f(src), low=f(src, "low"), high=f(src, "high"), status="SOURCED", source=tag,
                     url=d[src]["url"], note=d[src]["notes"])
        elif r["section"] == "tariff" and tid in ("BOS_TOU", "BOS_TOUD") and key in ("price_peak", "price_offpeak"):
            r.update(value=f("boston_allin_flat"), low=f("boston_allin_flat", "low"),
                     high=f("boston_allin_flat", "high"), status="SOURCED", source=tag,
                     url=d["boston_allin_flat"]["url"], note="Flat all-in rate: peak = off-peak (no verified TOU)")
    rows.append(_row("finance", "heat_pump_life", life, "years", status=d["heatpump_life"]["status"], source=tag,
                     note="Applied through heat_pump_cost_per_kW life factor"))
    return rows


# ---------------------------------------------------------------- baseline v2 package (baseline_v2/)
V2_DIR = os.path.join(HERE, "baseline_v2")
V2_SRC = "Team standard-house baseline v2 package (pcm_climate_baseline_v2)"
TMYX = {"Phoenix": "USA_AZ_Phoenix-Sky.Harbor.Intl.AP.722780_TMYx.2011-2025.epw",
        "Miami": "USA_FL_Miami.Natl.Hurricane.Center.722020_TMYx.2011-2025.epw",
        "Fresno": "USA_CA_Fresno.Yosemite.Intl.AP.723890_TMYx.2011-2025.epw",
        "Boston": "USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2011-2025.epw",
        "Sacramento": "USA_CA_Sacramento.Intl.AP.724839_TMYx.2011-2025.epw",
        "San Diego": "USA_CA_San.Diego.Intl.AP-Lindbergh.Field.722900_TMYx.2011-2025.epw"}
SRP_URL = ("https://www.srpnet.com/v3/assets/bltefc1fc708dcc94e7/blt3bc0beaf4fade7d9/"
           "2025-Ratebook-E-16-with-TCA-and-Export-Rate.pdf")
APS_ADJ_URL = "https://www.aps.com/en/Utility/Regulatory-and-Legal/Rates-Schedules-and-Adjustors/Bill-Adjustors"


def v2_rows(rows):
    """Apply the baseline v2 package: TMYx 2011-2025 weather for every city (the weather v2 used), APS R-3 dated
    monthly adjustors, and SRP E-16 as a second real Phoenix demand tariff."""
    for r in rows:
        if r["section"] == "city" and r["key"] == "weather_file" and r["city"] in TMYX:
            prev = r["value"]
            r.update(value=TMYX[r["city"]], status="OFFICIAL", url="https://climate.onebuilding.org/",
                     source=f"OneBuilding TMYx 2011-2025, as used by {V2_SRC} (SHA-256 checked there)",
                     note=f"Replaces {prev} (TMY3) so our house runs on the same weather as baseline v2")
    # APS adjustors per month (PSA+TCA+CRS+LFCR+DSMAC); REAC excluded: capped per month and already reached by the
    # assumed household base load, so it does not change the incremental HVAC bill (v2 tariff_model.py).
    adj = list(csv.DictReader(open(os.path.join(V2_DIR, "APS_monthly_adjustors.csv"), newline="")))
    adders = [sum(float(a[k]) for k in ("PSA_USD_kWh", "TCA_USD_kWh", "CRS_USD_kWh", "LFCR_USD_kWh", "DSMAC_USD_kWh"))
              for a in sorted(adj, key=lambda a: int(a["month"]))]
    rows.append(_row("tariff", "price_adder_by_month", ";".join(f"{x:.6f}" for x in adders), "USD/kWh by month",
                     "Phoenix", "PHX_TOUD", "all", status="OFFICIAL", url=APS_ADJ_URL,
                     source=f"APS dated bill adjustors 2026 (PSA, TCA, CRS, LFCR, DSMAC) via {V2_SRC} "
                            "APS_monthly_adjustors.csv",
                     note="REAC omitted (monthly cap reached by base load). Replaces the flat OpenEI R-3 adders."))
    # SRP E-16 Manage Demand 5-10 pm, residential, official 2025 ratebook with 2026 TCA and May-Oct FPPAM -0.0038
    seasons = {"summer": "5-6;9-10", "summerpeak": "7-8", "winter": "11-4"}
    prices = {"summer": (0.1219, 0.0957, 0.0355), "summerpeak": (0.1616, 0.0958, 0.0584),
              "winter": (0.1119, 0.0994, 0.0438)}
    demand = {"summer": 13.56, "summerpeak": 17.78, "winter": 9.61}
    tid, city = "PHX_SRP16", "Phoenix"
    rows.append(_row("tariff", "name", "SRP E-16 Manage Demand 5-10 pm (residential, official)", "text", city, tid,
                     "all", status="OFFICIAL", source=f"SRP 2025 ratebook E-16 via {V2_SRC} "
                     "verified_tariff_components.csv", url=SRP_URL,
                     note="Holidays not modelled (6 SRP holidays). Fixed $30/month cancels in comparisons."))
    for k, v in (("peak_hours", "17-22"), ("peak_days", "weekdays"), ("superoffpeak_hours", "8-15"),
                 ("superoffpeak_days", "all"), ("demand_rule", "avg_daily_max")):
        rows.append(_row("tariff", k, v, "", city, tid, "all", status="OFFICIAL", url=SRP_URL, source=V2_SRC))
    for sname, months in seasons.items():
        pk, off, sup = prices[sname]
        rows.append(_row("tariff", "months", months, "month list", city, tid, sname, status="OFFICIAL", url=SRP_URL))
        for k, v in (("price_peak", pk), ("price_offpeak", off), ("price_superoffpeak", sup)):
            rows.append(_row("tariff", k, v, "USD/kWh", city, tid, sname, status="OFFICIAL", url=SRP_URL,
                             source=V2_SRC, note="May-Oct include temporary FPPAM -0.0038" if sname != "winter" else ""))
        rows.append(_row("tariff", "demand_charge", demand[sname], "USD/kW-month (avg of daily on-peak max)", city,
                         tid, sname, status="OFFICIAL", url=SRP_URL, source=V2_SRC))
    return rows


def build(source="energy"):
    assert source in SOURCES, f"source must be one of {SOURCES}"
    rows = list(csv.DictReader(open(ENERGY_CSV, newline="", encoding="utf-8")))
    fields = list(rows[0].keys())
    d = _defaults()
    rows += california_rows(d)
    rows = v2_rows(rows)
    if source == "defaults":
        rows = apply_defaults_conflicts(rows, d)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"inputs_{source}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in fields} for r in rows)
    return path


if __name__ == "__main__":
    for s in SOURCES:
        print(build(s))
