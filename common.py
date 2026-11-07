"""Shared pieces: inputs, hourly weather, tariffs, heat-pump COP, finance."""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ENERGY = os.path.join(HERE, "energy")
ENERGY_INPUTS = os.path.join(ENERGY, "03_inputs", "inputs.csv")
TEAM_DEFAULTS = os.path.join(ENERGY, "03_inputs", "PCM_Hackathon_Defaults.csv")
COSTS_2026 = os.path.join(ENERGY, "03_inputs", "costs_sourced_2026.csv")
BUILDINGS = ("residential", "commercial")          # tank-cost scenarios (costs_sourced_2026.csv)
# One installed PCM wall product layer: 0.6-1 lb/ft2 (costs_sourced_2026.csv wall_pcm_installed_cost note),
# midpoint 0.8 lb/ft2 = 3.906 kg/m2. Thicker designs are priced as proportionally more product.
WALL_PRODUCT_KG_PER_M2 = 0.8 * 4.8824
sys.path.insert(0, os.path.join(ENERGY, "04_model"))
import cost_model as EM                   # energy specialist's model: one tariff implementation for both teams
import merge_inputs                       # merges inputs.csv + PCM_Hackathon_Defaults.csv (+ Sacramento, San Diego)
import house_v2                           # house parameters from the team's standard-house baseline v2

SOURCES = merge_inputs.SOURCES            # "energy" (inputs.csv wins conflicts) or "defaults" (defaults sheet wins)
DEFAULT_SOURCE = os.environ.get("PCM_SOURCE", "energy")


def out_dirs(source):
    """(results, charts, energy outputs) folders; the 'energy' source keeps the original locations."""
    sub = "" if source == "energy" else source
    return (os.path.join(HERE, "results", sub), os.path.join(HERE, "charts", sub),
            os.path.join(ENERGY, "05_outputs", sub))

N_HOURS = 8760
CAL_YEAR = 2026                           # = inputs.csv calendar.reference_year_for_weekdays (Jan 1 = Thursday)
HOURS = pd.date_range(f"{CAL_YEAR}-01-01", periods=N_HOURS, freq="h")
MONTH = HOURS.month.values - 1            # 0..11
HOD = HOURS.hour.values                   # 0..23
WEEKDAY = HOURS.weekday.values < 5        # Mon-Fri (same calendar as the tariffs)
# our generic tariff names -> energy tariff_id suffix; "TOU+demand (SRP)" exists only for Phoenix (SRP E-16)
TARIFF_KINDS = {"TOU": "_TOU", "TOU+demand": "_TOUD", "TOU+demand (SRP)": "_SRP16"}


def load_inputs(path=os.path.join(HERE, "inputs.json"), source=None):
    """Physics (house, wall, heat pump, tank) from inputs.json; cities, tariffs, costs and finance from the merged
    team inputs (energy/03_inputs/inputs.csv + PCM_Hackathon_Defaults.csv, see merge_inputs.py)."""
    source = source or DEFAULT_SOURCE
    energy_path = merge_inputs.build(source)
    with open(path) as f:
        cfg = json.load(f)
    cfg["source"] = source
    h = cfg["house"]
    if h.get("derive_from_v2"):                       # envelope, mass, gains, solar from baseline v2 at this size
        h.update(house_v2.derive(h["floor_area_m2"], h.get("stories", 1)))
    tariffs, tariff_city, costs, finance, cal = EM.load_inputs(energy_path)
    rows = pd.read_csv(energy_path, dtype=str).fillna("")
    num = EM._num
    assert int(num(cal["reference_year_for_weekdays"])) == CAL_YEAR, "calendar year mismatch with inputs.csv"

    cfg["cities"] = {r.city: {"epw": r.value} for r in rows[(rows.section == "city") & (rows.key == "weather_file")].itertuples()}
    cfg["tariffs"] = list(TARIFF_KINDS)
    cfg["tariff_ids"] = {c: {k: f for k in TARIFF_KINDS for f, fc in tariff_city.items()
                             if fc == c and f.endswith(TARIFF_KINDS[k])} for c in cfg["cities"]}
    cfg["_energy"] = dict(tariffs=tariffs, path=energy_path)

    cfg["costs"] = dict(cfg.get("costs", {}))
    cfg["costs"]["years"] = int(num(finance["lifetime"]))
    cfg["costs"]["discount_rate"] = num(finance["discount_rate_real"])
    cfg["costs"]["insulation_usd_per_m3"] = num(costs["insulation_cost_xps"]) * 100     # $/m2/cm -> $/m3
    pcm = [costs[k] for k in ("pcm_price_paraffin", "pcm_price_biobased", "pcm_price_salt_hydrate")]
    cfg["costs"]["typical_pcm_price_usd_per_kg"] = [min(num(r, "low") for r in pcm), max(num(r, "high") for r in pcm)]
    cfg["heat_pump"]["capex_usd_per_kW_thermal"] = num(costs["heat_pump_cost_per_kW"])
    cfg["wall"]["insulation_k"] = num(costs["insulation_conductivity_xps"])

    # Team defaults sheet: sourced PCM properties and installed thermal-battery system cost.
    if os.path.exists(TEAM_DEFAULTS):
        dflt = pd.read_csv(TEAM_DEFAULTS).set_index("key")
        v = lambda k, col="default": float(dflt.loc[k, col])
        cfg["wall"]["pcm_latent_kJ_per_kg"] = v("pcm_latent_heat")
        cfg["wall"]["pcm_rho"] = v("pcm_density_liquid")
        cfg["wall"]["pcm_k"] = v("pcm_conductivity")
        cfg["tank"]["latent_kJ_per_kg"] = v("pcm_latent_heat")

    # Sourced 2026 costs (base column), overriding the earlier values. low/high drive the sensitivity rows.
    if os.path.exists(COSTS_2026):
        cs = pd.read_csv(COSTS_2026).set_index("parameter")
        trio = lambda k: [float(cs.loc[k, c]) for c in ("base", "low", "high")]
        cfg["_costs2026"] = cs
        cfg["tank_cost"] = {b: trio(f"tank_installed_cost_{b}") for b in BUILDINGS}      # USD/kWh_th installed
        cfg["tank"]["om_fraction"] = float(cs.loc["tank_om_fraction", "base"])
        cfg["tank"]["lifetime"] = float(cs.loc["tank_lifetime", "base"])
        cfg["wall"]["installed_usd_per_m2"] = trio("wall_pcm_installed_cost")
        cfg["wall"]["lifetime"] = float(cs.loc["wall_pcm_lifetime", "base"])
        cfg["heat_pump"]["marginal_usd_per_kW"] = trio("hp_marginal_cost")
        cfg["heat_pump"]["lifetime"] = float(cs.loc["hp_lifetime", "base"])
        n = cfg["costs"]["years"]
        assert cfg["tank"]["lifetime"] >= n and cfg["wall"]["lifetime"] >= n, "tank/wall replacement not modelled"
        cfg = set_hp_cost(cfg, cfg["heat_pump"]["marginal_usd_per_kW"][0])
    return cfg


def set_hp_cost(cfg, marginal_usd_per_kW):
    """Copy of cfg with the heat-pump capacity cost set from a marginal $/kW plus one replacement at the end of
    the heat pump's life (discounted; no salvage value), so a smaller unit also saves on the replacement."""
    r, n = cfg["costs"]["discount_rate"], cfg["costs"]["years"]
    life = cfg["heat_pump"].get("lifetime", n)
    factor = 1.0 + sum((1 + r) ** -y for y in np.arange(life, n, life)) if life < n else 1.0
    hp = dict(cfg["heat_pump"], hp_marginal_usd_per_kW=float(marginal_usd_per_kW), hp_replacement_factor=factor,
              capex_usd_per_kW_thermal=float(marginal_usd_per_kW) * factor)
    return dict(cfg, heat_pump=hp)


def wall_pcm_cost(cfg, pcm_mm, usd_per_m2=None):
    """Installed PCM wall cost: $/m2 of wall for one product layer, scaled by PCM mass per m2."""
    w = cfg["wall"]
    price = w["installed_usd_per_m2"][0] if usd_per_m2 is None else usd_per_m2
    layers = np.asarray(pcm_mm) / 1000 * w["pcm_rho"] / WALL_PRODUCT_KG_PER_M2
    return price * cfg["house"]["wall_area_m2"] * layers


def tank_costs(cfg, size_kWh, usd_per_kWh_th):
    """Installed tank capex and the 20-yr present value of its O&M (om_fraction of capex per year)."""
    capex = usd_per_kWh_th * np.asarray(size_kWh, float)
    return capex, cfg["tank"]["om_fraction"] * capex * annuity_factor(cfg)


# ---------------------------------------------------------------- weather
_EPW_CACHE = {}


def read_epw_full(path):
    """Dry-bulb and dew-point (°C), pressure (Pa), GHI (W/m2) from an EPW file (cached)."""
    if path not in _EPW_CACHE:
        df = pd.read_csv(path, skiprows=8, header=None)
        _EPW_CACHE[path] = {k: df[c].values[:N_HOURS].astype(float) for k, c in
                            (("t", 6), ("td", 7), ("p", 9), ("ghi", 13))}
    return _EPW_CACHE[path]


def read_epw(path):
    """Hourly dry-bulb (°C) and global horizontal irradiance (W/m2) from an EPW file."""
    w = read_epw_full(path)
    return w["t"], w["ghi"]


def synthetic_weather(lat, T_mean, T_seasonal_amp, T_diurnal_amp, cloudiness, seed=0):
    """Placeholder year: seasonal + daily cycles + weather noise, clear-sky sun with random clouds."""
    rng = np.random.default_rng(seed)
    doy = HOURS.dayofyear.values
    noise = np.zeros(N_HOURS)
    for t in range(1, N_HOURS):                      # slow weather fronts (AR(1), ~2 °C)
        noise[t] = 0.97 * noise[t - 1] + rng.normal(0, 0.5)
    T = (T_mean + T_seasonal_amp * np.cos(2 * np.pi * (doy - 200) / 365)
         + T_diurnal_amp * np.cos(2 * np.pi * (HOD - 15) / 24) + noise)
    decl = np.radians(23.45 * np.sin(2 * np.pi * (284 + doy) / 365))
    phi, ha = np.radians(lat), np.radians(15 * (HOD + 0.5 - 12))
    sin_el = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(ha)
    clouds = 1 - cloudiness * rng.random(366)[doy - 1] * 1.6
    ghi = 1000 * 0.75 * np.clip(sin_el, 0, None) ** 1.15 * np.clip(clouds, 0.2, 1)
    return T, ghi


def city_weather(cfg, city):
    c = cfg["cities"][city]
    if c.get("epw") and os.path.exists(os.path.join(HERE, "weather", c["epw"])):
        return read_epw(os.path.join(HERE, "weather", c["epw"]))
    s = c["synthetic"]
    return synthetic_weather(c["lat"], s["T_mean"], s["T_seasonal_amp"], s["T_diurnal_amp"], s["cloudiness"],
                             seed=sum(map(ord, city)))


# ---------------------------------------------------------------- tariffs
_TARIFF_CACHE = {}


def city_tariffs(cfg, city):
    """Generic tariff kinds available in this city (SRP E-16 is Phoenix-only)."""
    return [k for k in cfg["tariffs"] if k in cfg["tariff_ids"].get(city, {})]


def tariff_for(cfg, city, name):
    """Hourly tariff for a city and generic tariff kind ("TOU" / "TOU+demand"), built by the energy model
    (seasons, weekday-only peaks, multiple peak windows, super-off-peak, monthly demand rates)."""
    tid = cfg["tariff_ids"][city][name]
    key = (cfg["_energy"]["path"], tid)
    if key not in _TARIFF_CACHE:
        tdef = cfg["_energy"]["tariffs"][tid]
        price, peak, demand13 = EM.build_tariff(tdef, EM.calendar_arrays(CAL_YEAR))
        rule = EM._get(tdef, "all", "demand_rule")
        _TARIFF_CACHE[key] = dict(id=tid, name=EM._get(tdef, "all", "name")["value"],
                                  status=EM._get(tdef, "all", "name")["status"],
                                  price=price, peak=peak, demand_month=demand13[1:],
                                  demand_rule=rule["value"] if rule else "monthly_max")
    return _TARIFF_CACHE[key]


def hourly_tariff(t):
    """Returns hourly price ($/kWh), peak mask, and demand-window mask (demand is billed on peak hours)."""
    return t["price"], t["peak"], t["peak"]


def pre_peak(t):
    """Masks for the 1st and 2nd hour before each peak block starts (for pre-cooling / pre-heating)."""
    pk = t["peak"]
    nxt1, nxt2 = np.roll(pk, -1), np.roll(pk, -2)
    pre2 = nxt1 & ~pk                       # hour right before the peak
    pre1 = nxt2 & ~nxt1 & ~pk               # two hours before
    return pre1, pre2


DAY = np.arange(N_HOURS) // 24


def billing_demand(P_kW, t):
    """Billing demand per month (kW): highest peak-window hour (APS-style 'monthly_max') or the average of each
    day's highest peak-window hour ('avg_daily_max', SRP E-16)."""
    window = t["peak"]
    out = np.zeros(12)
    for m in range(12):
        mw = (MONTH == m) & window
        if not mw.any():
            continue
        if t.get("demand_rule") == "avg_daily_max":
            days = np.unique(DAY[mw])
            out[m] = np.mean([P_kW[mw & (DAY == d)].max() for d in days])
        else:
            out[m] = P_kW[mw].max()
    return out


def bill(P_kW, t):
    """Annual energy and demand cost for an hourly electric load."""
    energy = float((t["price"] * P_kW).sum())
    peaks = billing_demand(P_kW, t)
    return energy, float((t["demand_month"] * peaks).sum()), peaks


# ---------------------------------------------------------------- heat pump
def cop_cool(cfg, T_out):
    c = np.array(cfg["heat_pump"]["cooling_curve_C_COP"], float)
    return np.interp(T_out, c[:, 0], c[:, 1])


def cop_heat(cfg, T_out):
    h = cfg["heat_pump"]
    c = np.array(h["heating_curve_C_COP"], float)
    return np.where(np.asarray(T_out) < h["heating_cutoff_C"], 1.0, np.interp(T_out, c[:, 0], c[:, 1]))


def deadband(cfg):
    h = cfg["house"]
    return h["heating_setpoint_C"], h["cooling_setpoint_C"]


# ---------------------------------------------------------------- finance
def annuity_factor(cfg):
    r, n = cfg["costs"]["discount_rate"], cfg["costs"]["years"]
    return (1 - (1 + r) ** -n) / r


def internal_gains(cfg):
    """Internal sensible gains (kW). Optional occupancy schedule (building presets): internal_gains_occupied_W_per_m2
    x floor area during occupied hours, internal_gains_kW otherwise."""
    h = cfg["house"]
    gains = np.full(N_HOURS, float(h["internal_gains_kW"]))
    if "internal_gains_occupied_W_per_m2" in h:
        a, b = h["occupied_hours"]
        occ = (HOD >= a) & (HOD < b) & (WEEKDAY if h.get("occupied_days", "weekdays") == "weekdays" else True)
        gains = np.where(occ, h["internal_gains_occupied_W_per_m2"] * h["floor_area_m2"] / 1000, gains)
    return gains


def house_gains(cfg, T_out, ghi):
    """Solar + internal sensible gains into the building, minus sky long-wave loss (kW)."""
    h = cfg["house"]
    return h["solar_aperture_m2"] * ghi / 1000 + internal_gains(cfg) - h.get("sky_loss_kW", 0.0)


def latent_potential(cfg, city):
    """Latent cooling load the system must remove WHEN it is cooling (kW thermal), as in baseline v2: ventilation
    moisture down to the indoor target (cooling setpoint at 50 % RH) plus internal latent gains. Callers apply it
    only in hours with sensible cooling."""
    h = cfg["house"]
    w = read_epw_full(os.path.join(HERE, "weather", cfg["cities"][city]["epw"]))
    sat = lambda T: 610.94 * np.exp(17.625 * T / (T + 243.04))               # Pa (Magnus, as v2)
    vo = sat(w["td"])
    vi = sat(h["cooling_setpoint_C"]) * h.get("indoor_RH_cooling_percent", 50) / 100
    wo, wi = 0.62198 * vo / (w["p"] - vo), 0.62198 * vi / (w["p"] - vi)
    rho = w["p"] / (287.05 * (w["t"] + 273.15))
    flow = h.get("volume_m3", h["floor_area_m2"] * 2.438) * h.get("air_changes_per_hour", 0.35) / 3600
    vent = rho * flow * 2501.0 * np.maximum(wo - wi, 0)                       # kW
    sf = h.get("internal_sensible_fraction", 0.85)
    return vent + internal_gains(cfg) * (1 - sf) / sf


def building_cfg(cfg, name):
    """cfg for a building preset from inputs.json["buildings"]: house overrides, its tariff and tank-cost type."""
    b = cfg["buildings"][name]
    return dict(cfg, house=dict(cfg["house"], **b["house"]), tariffs=[b["tariff"]], building=name,
                building_tank_cost=b["tank_cost"])
