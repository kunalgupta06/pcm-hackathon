# U.S. same-house heating and cooling comparison: v2

**v2 (7 November 2026)** fixes every problem found in an independent audit of v1; see [CHANGELOG.md](CHANGELOG.md). The main change is the physics. v1 used a steady-state balance with no thermal mass and one 72 °F setpoint. As a result the house heated and cooled on the same day for 45–348 days a year (median 209). v2 uses the ISO 13790 hourly 5R1C model with thermal mass and a 68/78 °F deadband, and same-day heating plus cooling now occurs on 0–1 days a year. v1 results are kept in `v1_steady_state_results/`.

Open [House_energy_calculator.html](House_energy_calculator.html) to work with house size, or `US_home_energy_comparison.xlsx` (12 sheets) for all data. These numbers come from a screening prototype. They do not establish real-house accuracy or PCM savings.

## What was collected (unchanged from v1)

- **51 electricity prices**: EIA Electric Power Annual Table 2.10, residential, 2025 (all states plus DC). The audit re-verified all 51 against the source.
- **78 city weather files**: OneBuilding TMYx 2011–2025, 8,760 hours each, every state plus DC. All SHA-256 hashes were re-verified.
- **683,280 hourly records**: weather plus modeled indoor air temperature, mass temperature, loads and costs.
- **9 official tariffs in 6 cities**, 120 bill scenarios, and a 14,707-record OpenEI rate inventory.

## Main findings (v2, flat 2025 state-average prices, 2,000 ft², one story)

Lowest modeled HVAC cost: **San Francisco $203/yr, Los Angeles $248, San Diego $291, Seattle $293, Portland (OR) $375**. Highest: Fairbanks $4,469, Honolulu $1,770, Anchorage $1,758. Median across the 78 cities: **$561** (v1: $900).

The ranking changed from v1 because thermal mass and a deadband let mild coastal climates float between 68 and 78 °F most of the year. San Francisco floats on 6,105 of 8,760 hours.

**Thermostat assumptions dominate in mild climates.** Holding the house at 72/72 °F (with mass) raises San Francisco's HVAC energy 266% and Sacramento's 90%. A 70/75 °F band raises them 64% and 29%. Treat close ranks, especially among mild cities, as conditional on the comfort band. See the `Sensitivity` sheet.

These rank HVAC **operating cost** for one fixed, high-performance prototype house. They are not total cost of living, and not typical homes in each city.

## Fixed house and equipment

| Parameter | v2 baseline |
|---|---|
| Floor area and geometry | 2,000 ft², one story, 50 × 40 ft, 8 ft ceilings; the size calculator covers 750–5,000 ft², 1–2 stories |
| **Thermostat** | **68 °F heating / 78 °F cooling deadband** (ANSI/RESNET/ICC 301 reference home); ideal control of air temperature |
| **Thermal mass** | **ISO 13790 class "light" (wood frame): C_m = 110 kJ/K per m² floor, A_m = 2.5 A_f** |
| Effective wall / ceiling / floor insulation | R-20 / R-49 / R-30 (US units, whole-assembly) |
| Foundation | Raised floor over vented crawlspace, approximated at outdoor temperature |
| Windows | 300 ft², U-0.30, SHGC 0.30 × ISO angular factor 0.9 × shading 0.70, evenly on four faces |
| Doors | 40 ft², R-5 |
| Air exchange | 0.35 ACH |
| **Internal gains** | **RESNET 301: 17,900 + 23.8·CFA + 4,104·N_bedrooms Btu/day (≈950 W at 2,000 ft², 3 BR); 85% sensible, 15% latent** |
| Solar / long-wave | Wall α 0.50, roof α 0.40, h_out 20 W/m²K; **ISO 13790 §11.3.5 sky long-wave loss** (h_r 4.5 W/m²K; ΔT_sky 13 / 11 / 9 K for tropical / mid / sub-polar latitudes) |
| Heat pump | Generic air-source; heating COP 1.4–4.2 vs outdoor temperature; cooling COP 4.5–2.0. Capacity 5.3–10.55 kW (about 3 tons) at the 2,000-ft² one-story reference, **scaled with each house's design heat-loss coefficient** (0.48× at 750 ft² to 2.1× at 5,000 ft²) |
| Backup | Electric resistance (COP 1) above heat-pump capacity or below −13 °F |
| Latent cooling | Ventilation moisture to 50% RH at the cooling setpoint, plus internal latent gains, in hours with sensible cooling |

## Calculation method

Each hour, `hvac_core.py` solves the ISO 13790:2008 Annex C three-node network: air, surface and mass, with one lumped capacitance and a Crank–Nicolson step. First it computes the free-floating air temperature. If that falls below 68 °F or rises above 78 °F, it computes the exact heating or cooling power needed to hold the setpoint. Each run uses one warm-up year, so the mass starts and ends the recorded year at the same temperature.

`Heating electricity = heat-pump heat / COP(T_out) + resistance heat`
`Cooling electricity = (sensible + latent cooling) / COP_cool(T_out)`
`Annual HVAC cost = Σ hourly electricity × state 2025 average price`

**Verification** (24/24 pass: `tests/test_hvac_core.py` 15, `tests/test_independent.py` 9):
- A separate re-implementation (own weather parser, geometry, sun model and a full linear solve with solar on) matches annual heating and sensible cooling within 0.2% in Minneapolis, Phoenix and Miami.
- Hand checks of the heat-pump capacity cap, the −13 °F cutoff, resistance backup, COP use and one hour of latent load.
- Annual energy-balance identity, storage included, closes to ≤1e-13 relative. This holds by construction, so it catches bookkeeping and unit slips only.
- Steady state matches an independent 3-node linear solve exactly.
- Free-floating temperatures match an independent 1-minute implicit solve within 0.003 K (test tolerance 0.01 K).
- Mass temperature closes over the year.
- With near-zero mass, a 72 °F setpoint and v1 gains, the model reproduces v1 within 3–6%.

**Calculators:** the workbook and HTML both interpolate the same grid of direct runs every 62.5 ft². The largest error against 3,120 off-grid direct simulations is 0.04% ($0.22/yr).

## Limitations

- **No PCM yet.** One lumped capacitance cannot represent latent heat, melt temperature or hysteresis. To answer the MIT challenge, add a layered wall model (enthalpy-method finite difference, or COMSOL) coupled to this zone. Then run baseline, extra insulation and PCM through the **same** transient model and the same tariffs.
- Not calibrated to bills or EnergyPlus. No ducts, fans, defrost or cycling. No humidity balance outside cooling hours.
- One TMY year per city; no extremes or future climate.
- Windows stay closed: no natural or night ventilation. This overstates cooling in mild coastal and tropical cities (SF, LA, Seattle, Honolulu).
- Fairbanks is dominated by the −13 °F heat-pump cutoff (most of its heating electricity is resistance backup). Cold-climate results depend strongly on that cutoff.
- Bedrooms are fixed at 3 for every floor area. The 85% sensible split of internal gains is an analyst assumption. The floor is coupled directly to outdoor air (vented crawlspace).
- The national ranking uses flat state-average prices; only 9 tariffs are verified, in 6 cities.
- Single-parameter sensitivities only; no uncertainty interval.

## Tariff scenarios (v2 loads, 2,000 ft², flat 4,800 kWh/yr base load)

Phoenix: APS R-3 $735/yr (of which $288 demand), SRP E-16 $546 ($148 demand), SRP E-28 $551. Bakersfield PG&E E-TOU-D $1,005. San Francisco E-TOU-D $232. Sacramento SMUD TOD $363. Seattle TOU $287. These are incremental HVAC bills, Bill(base + HVAC) − Bill(base), not complete quoted bills. v2 applies SRP's May–Oct 2026 fuel decrease (assumed for E-28), Seattle's Q1-2026 4% surcharge, and corrects PG&E's effective-date label.

## Sources

EIA prices: https://www.eia.gov/electricity/annual/html/epa_02_10.html · Weather: https://climate.onebuilding.org/ · ISO 13790:2008, *Energy performance of buildings: calculation of energy use for space heating and cooling*, Annex C · ANSI/RESNET/ICC 301 reference-home setpoints and internal gains · Heat-pump context: https://www.energystar.gov/products/air_source_heat_pumps/key-product-criteria · Tariff PDFs: see `deep_research/verified_tariff_components.csv`.

## Reproduce

```
python3 analyze.py                      # 78 cities, ~75 s
python3 deep_research/size_model.py     # size grid, sensitivities, calculator grid, ~7 min
python3 deep_research/tariff_model.py   # 120 tariff scenarios
python3 deep_research/build_calculator.py
python3 build_workbook.py               # then recalculate in Excel or LibreOffice
python3 tests/test_hvac_core.py
python3 tests/test_independent.py      # ~3 min
```
Requires Python 3 with numpy (and openpyxl for the workbook). Paths work on Windows, macOS and Linux.

## Files

`US_home_energy_comparison.xlsx` · `House_energy_calculator.html` · `city_annual_comparison.csv` (78 rows; key `city_id`) · `city_monthly_comparison.csv` (936) · `hourly_weather_and_loads.csv.gz` (683,280) · `state_electricity_prices.csv` · `city_manifest.json` · `assumptions.json` · `data_quality.csv` · `hvac_core.py` · `tests/` · `deep_research/` · `raw/weather/*.epw` · `v1_steady_state_results/` · `CHANGELOG.md` · `DATA_DICTIONARY.md`.
