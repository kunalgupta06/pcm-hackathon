# PCM hackathon: Kunal's tasks 10–14

```bash
pip install -r requirements.txt
python run_all.py                     # inputs.csv wins conflicts  -> results/, charts/, energy/05_outputs/
python run_all.py --source defaults   # defaults sheet wins        -> results/defaults/, charts/defaults/, energy/05_outputs/defaults/
python api.py                         # demo: best_option(city, tariff, building="residential"|"commercial", source=...)
```

## What's in here

| File | Task | What it does |
|---|---|---|
| `energy/` | — | Energy specialist's workspace (from the team Drive): `03_inputs/inputs.csv` (cities, 8 tariffs, costs, finance, **each with a source**), `01_decisions/decision_log.md`, their `04_model/cost_model.py`, and `05_outputs/` |
| `weather/` | — | TMY3 EPW files for Phoenix, Miami, Fresno, Boston, Sacramento, San Diego + `weather_summary.csv` |
| `inputs.json` | — | **Physics only**: house, wall, heat-pump COP, tank. Still placeholders until the thermal expert confirms (flag F6) |
| `merge_inputs.py` | — | Merges `energy/03_inputs/inputs.csv` + `PCM_Hackathon_Defaults.csv` into `energy/03_inputs/merged/inputs_<source>.csv` (regenerated every run; edit the two source sheets, not the merged files) |
| `baseline_v2/` + `compare_baseline.py` | — | Team "standard-house baseline v2" (ISO 13790 5R1C, 68/78 °F deadband, 78 cities): `CHANGELOG.md`, `House_energy_calculator.html`, `US_home_energy_comparison.xlsx`. `python compare_baseline.py` exports its grid to `baseline_v2/house_grid.csv` and compares our house with it in `results/baseline_v2_comparison.csv` |
| `common.py` | — | Loads both input files, weather, tariffs (using the energy model's tariff builder), bills, COP, finance |
| `case1_wall.py` | 10 | Passive PCM wall vs **the same money spent on XPS insulation**, full year, hourly; tracks PCM liquid fraction |
| `case2_battery.py` | 11, 12 | House + PCM cold-storage tank; **fixed**, **rule-based** and **smart (LP)** controllers |
| `run_all.py` | 13 | Runs everything, writes our tables and charts, exports the energy handoff and runs the energy cost model |
| `api.py` | 14 | `best_option(city, tariff, building="residential")` for the developer's demo; `tariff` is `"TOU"` or `"TOU+demand"`, `building` is `"residential"` or `"commercial"` (tank cost) |

## Outputs

- `results/headline.csv`: **the headline table**. For each city and tariff:
  - Battery: net 20-year savings for a residential tank and a commercial tank. Each is the best PCM option (any controller, any size) against smart control with no tank, after tank capex and O&M. It's split into energy-bill savings, demand savings, heat-pump savings, tank capex and tank O&M.
  - Passive wall: net savings, the break-even $/m², and extra insulation's net savings for comparison.
  - Rows for scenarios `base`, `tank low`, `tank high`, `hp low` and `hp high`.
- `results/small_office_headline.csv`, `results/small_office_case2_runs.csv`: the small-office preset (battery with commercial tank cost; base, tank low and tank high).
- `results/sources.csv`: every input the run used (or deliberately didn't), with its value, source, URL and how it's used.
- `results/summary.csv`: per-controller table (each tank against the same controller with no tank). It has net savings per building, break-even installed $/kWh-th including O&M, and the passive-wall columns.
- `results/case1_designs.csv`, `results/case2_runs.csv` (+ `case2_runs_hp285.csv`, `case2_runs_hp570.csv`): every run, with energy, demand and heat-pump savings, tank capex, O&M and net savings columns.
- `results/energy_handoff/results_hourly.csv` + `results_meta.csv`: our hourly electricity in the energy model's contract (≈44 MB).
- `energy/05_outputs/*_EARLIER_COSTS.csv`: the energy model's break-even, cost breakdown, control premium and sensitivity, computed from our hourly loads. They're **labelled EARLIER COSTS** (with a `cost_basis` column), because `cost_model.py` still prices with `inputs.csv` (heat pump $529/kW, no tank cost or O&M). Use `results/headline.csv` for current costs. They're tagged `_PLACEHOLDER` while `inputs.json` → `results_data_status` is `"PLACEHOLDER"`. Flip it to `"REAL"` once the thermal expert signs off on the house, wall and tank.
- `charts/`: `net_savings.png` (residential battery, commercial battery and passive wall), `break_even_system_cost.png` (against the residential and commercial cost bands), `cost_breakdown.png`, `day_plot.png`, `wall_liquid_fraction.png`, `annual_cost_by_city.png`. Hypothetical tariffs are marked `*`.

## Where the numbers come from

- **Six cities:** Phoenix, Miami, Fresno and Boston from `inputs.csv`, plus Sacramento (SMUD R-TOD, including its summer mid-peak) and San Diego (SDG&E TOU-DR1, official Jan 2026 rates, with super-off-peak every night and weekend middays) from the defaults sheet. Each has a real time-of-use tariff and a HYPOTHETICAL "+ APS demand charge" version, following decision D6. Their TMY3 weather comes from climate.onebuilding.org. The extra March–April weekday super-off-peak in San Diego isn't modelled.
- **Cities, weather, tariffs, costs, discount rate (3% real) and lifetime (20 yr)** all come from `energy/03_inputs/inputs.csv`. Edit them there, then rerun `python run_all.py`. Our generic tariff names map per city: `"TOU"` → `PHX_TOU`, `MIA_TOU`, `FRE_TOU`, `BOS_TOU`, and `"TOU+demand"` → `*_TOUD`. Seasons, weekday-only peaks, Miami's two winter peak windows, Phoenix super-off-peak and monthly demand rates are all modelled. Weekdays follow calendar year 2026.
- **Costs from `energy/03_inputs/costs_sourced_2026.csv` (base column; low/high used for sensitivity):**
  - **Heat pump:** $450/kW marginal (downsizing credit), plus one replacement at year 15, discounted, with no salvage value. That's ×1.642, or $739/kW effective. Heat-pump maintenance is the same for every option and is left out.
  - **Battery:** installed $/kWh-th × tank size. Residential $400 (370–500, Sunamp); commercial $100 (43–200, CALMAC/ACEEE ice storage as a proxy). Tank O&M is 2% of capex per year. No replacement, since the tank lasts at least 20 years.
  - **Passive wall:** installed $60/m² of wall (43–110). That price is for one product layer of about 3.9 kg/m², so thicker designs are priced in proportion to PCM mass. No maintenance or replacement (at least 30-year life).
  - **Not used:** `insulation_installed_cost`, because the energy specialist's sourced XPS cost of $1.99/m²/cm (k = 0.0288, from `inputs.csv`) takes priority. Raw PCM and vessel-only prices are reference only. The energy specialist's `cost_model.py` still uses its own costs from `inputs.csv`.
- **The baseline wall** is 74 mm XPS. That gives the same R as the earlier 90 mm at k = 0.035.
- **From `energy/03_inputs/PCM_Hackathon_Defaults.csv` (team defaults sheet):**
  - PCM latent heat 190 kJ/kg, density 843 kg/m³ and conductivity 0.2 W/m·K, used for both wall and tank.
  - The APS R-3 adjustments (+$0.028407/kWh on every energy rate, +$1.517/kW-month on demand), written into the `PHX_TOUD` rows of `inputs.csv` so both models use them. Original values are kept in the `note` column.
- **Tank sizes** swept: 1, 2, 3, 5, 10, 20 and 40 kWh-th.
- **Small-office preset** (`inputs.json` → `buildings.small_office`, ASSUMED and not sourced):
  - 200 m² floor and 150 m² of wall, occupied 8 am–6 pm on weekdays.
  - Internal gains of 15 W/m² when occupied (3 kW) and 0.4 kW otherwise.
  - Envelope and thermal mass scaled from the house by floor area, with more glazing and a constant setpoint.
  - Battery only, at the commercial tank cost.
  - Tariff: each city's TOU+demand as a **stand-in**, because no commercial demand tariff has been sourced yet (for example APS E-32, PG&E B-19, SDG&E AL-TOU, FPL GSD-1, Eversource G-2).
- **Still placeholders in `inputs.json`:** house, heat-pump COP curves, tank physics (losses, charge rate).

## How the comparison stays fair

- **Case 1:** the PCM wall is compared with the *same dollars* spent on extra insulation, not with an uninsulated wall.
- **Case 2:** every controller runs on the house **without** and **with** the tank. The battery only gets credit for what it adds on top of what that controller already gets from the house's own thermal mass.
- **Net savings** = 20-year (energy + demand + heat-pump) savings − installed cost − O&M, taking the best option. **Break-even installed cost** = savings ÷ (size × (1 + O&M present-value factor)).
- **Smart control** is a full-year linear program with perfect foresight of weather and prices. It also chooses the heat-pump size. Treat it as the upper bound of what control can achieve.

## What the last run says (`--source energy`, 6 cities, sourced 2026 costs, placeholder physics)

Net 20-year savings, present value. Battery: best option against smart control with no tank. Wall: best design against the baseline wall.

- **Residential battery ($400/kWh-th) never pays.** The best option is always the smallest tank (1 kWh), at −$270 to −$520. It's still negative at the low cost ($370) and at the high heat-pump cost.
- **Commercial battery ($100/kWh-th) pays slightly** in 10 of 12 city–tariff cases:
  - Miami TOU+demand: +$720 (10 kWh).
  - Phoenix TOU+demand: +$175.
  - Sacramento and Fresno TOU: about +$140.
  - Boston: negative.
  - At the high cost ($200) every case is negative. At the low heat-pump cost ($285/kW) most are negative.
- **Passive wall ($60/m²) loses $4.9–7.2k everywhere.** It would break even at only $5–22/m².
- **Small office (assumed preset, commercial tank):**
  - Miami: +$2,875 with 40 kWh, mostly from demand savings. That's the largest size swept, so the true optimum may be larger.
  - Phoenix: +$734 (20 kWh).
  - The other cities: about $0–210.
  - At $200/kWh-th, only Miami stays positive.

## House model, weather and checks against baseline v2 (`python compare_baseline.py`)

The house is now built from the team's **standard-house baseline v2** (`baseline_v2/`, the full `pcm_climate_baseline_v2` package):
- **Envelope, mass and gains:** `house_v2.py` derives them from the v2 specification at our floor area (150 m², one story): R-20/R-49/R-30, U-0.30 windows, 0.35 ACH, light mass, RESNET 301 gains.
- **Thermostat:** heat to 68 °F (20 °C), cool to 78 °F (25.6 °C), float in between.
- **Heat-pump efficiency:** v2's COP curves.
- **Latent cooling:** ventilation moisture down to 50% RH plus internal latent gains, in hours with sensible cooling, the same rule as v2.
- **Weather:** OneBuilding **TMYx 2011–2025** for all six cities (the files v2 used), replacing TMY3.
- **Tariffs:**
  - APS R-3 uses v2's **dated monthly adjustors** (PSA, TCA, CRS, LFCR, DSMAC; REAC omitted because the base load already reaches its monthly cap). These replace the flat OpenEI adders.
  - Phoenix gains a third tariff, **SRP E-16**, billed on the average of each day's highest on-peak hour.

Checks against v2:
- **Annual, at our size:** within **+5% to +21%** of v2 in all six cities, with Miami now at 1.05×.
- **Hourly, on v2's own 2,000 ft² house with identical weather:** hourly correlation 0.85–0.96. The bias (NMBE) is −5% to −22%, meaning our model is high. Peak cooling electricity is 4–36% above v2.
- **Likely cause:** our one-node house sends sun and internal heat straight to the cooled air node. v2's ISO 13790 5R1C model buffers them in a separate mass node. So our model **overstates cooling peaks, and with them the heat-pump downsizing and demand-charge value of a PCM battery**.
- **Next upgrade:** a two-node (air + mass) zone with solar on vertical faces.

## Conflicts between the two team input sheets: run either way with `--source`

| Item | `--source energy` (default) | `--source defaults` | Note |
|---|---|---|---|
| Heat pump $/kW | 529 (marginal, Wilson 2024) | 1,300 installed (700–2,050) | |
| Heat pump life | n/a (no replacement) | 15 yr | In defaults mode: × 1.273 life factor (replace in yr 15, salvage at yr 20), giving an effective $1,655/kW |
| Microencapsulated PCM $/kg | 4.00 (derived, Kosny 2013) | 10 (9.7–14.3, Kosny 2013) | Same report, different reading. It sets the market-price band on the chart ($1.65–14.30 in defaults mode) |
| Miami FPL TOU | 0.289 / 0.080 (official insert) | 0.269 / 0.06 (secondary, low confidence) | |
| Boston | Hypothetical TOU around 30.48 ¢ | Flat 36 ¢ (secondary) | With a flat rate, the battery can only help through the demand charge |
| Insulation comparator | XPS $1.99/m²/cm | R-13→R-15 $1.94/m², converted to $1.91 per cm-of-XPS-equivalent | RSMeans location factors not applied |

Not used by the model (reference only): fixed monthly charges (they cancel in comparisons), the demand-response incentive, PCM board price, R-13 batt and exterior insulation retrofit costs, and the reference tank size (14.78 kWh, which sits inside our 5–40 kWh sweep).

## Known simplifications

- Single-zone house (1R1C model).
- The tank stores cold only, so it's used in the cooling season.
- EPW hours are local standard time; daylight saving and utility holidays are ignored (energy decision log, calendar rows).
- The rule-based controller is deliberately simple.
- No PCM hysteresis or supercooling.
