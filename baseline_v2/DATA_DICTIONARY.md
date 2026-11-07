# Data dictionary

## v2 additions (see CHANGELOG.md)

- **Join key:** `city_id` = "City, ST" in every v2 output. City names alone are not unique (Portland OR/ME, Charleston SC/WV).
- `hvac_core.py`: ISO 13790 5R1C model used by every v2 output. Default parameters are in `assumptions.json`.
- `House_energy_calculator.html`: self-contained calculator embedding direct v2 runs every 62.5 ft² (750–5,000 ft², 1–2 stories), interpolated linearly. Built by `deep_research/build_calculator.py` from `calculator_template.html`, which is a template and does nothing when opened directly.
- `deep_research/calculator_grid.json`: per city, `grid["1"|"2"]` rows `[area_ft2, heating_kWh, cooling_kWh, backup_kWh, cooling_over_capacity_hours]`.
- `deep_research/calculator_validation.csv`: per city × stories, maximum interpolation error against direct off-grid simulations (kWh, %, USD).
- `tests/test_results.json`, `tests/test_independent_results.json`: test outcomes (energy balance, independent steady-state and transient solves, periodic closure, v1 limit case).
- v1 audit and exact-calculator files are in `v1_steady_state_results/v1_exact_calculator/`. They describe the v1 model only.

All prices/costs are nominal USD at 2025 electricity-price levels. Weather values describe a synthetic TMYx year assembled from 2011–2025, not 2025 observations. Missing values are not replaced with zeros. Data collection date: November 7, 2026.

## Annual city comparison

One record per city-state pair. The pair is the join key; city names alone are not unique (for example Portland and Charleston).

- `city`, `state`, `state_name`: human-readable location and two-letter state identifier. DC is included.
- `price_year`: EIA price year, 2025.
- `electricity_cents_kWh`: residential state-average electricity price in cents per electrical kWh.
- `price_geography`: identifies the state-average proxy; it is not a city-specific tariff.
- `weather_period`: TMYx 2011–2025.
- `weather_station`, `station_id`: weather file station name and identifier. Treat the identifier as text.
- `latitude`, `longitude`: decimal degrees; negative longitude is west.
- `elevation_m`: station elevation in meters.
- `mean_temp_F`, `min_TMY_temp_F`, `max_TMY_temp_F`: mean, minimum and maximum hourly dry-bulb temperatures in the selected typical year. These are not design extremes.
- `HDD65_F_days`, `CDD65_F_days`: sums of daily heating/cooling degree days at a 65°F base, using mean hourly daily temperature.
- `mean_daily_temp_range_F`: annual mean of each day's max-minus-min hourly temperature.
- `mean_RH_percent`: arithmetic average hourly relative humidity; not humidity ratio or average dew point.
- `annual_GHI_kWh_m2`: annual global horizontal solar irradiation, kWh/m².
- `mean_wind_m_s`: arithmetic average hourly wind speed.
- `heating_delivered_kWh_th`: thermal energy delivered for space heating.
- `cooling_sensible_kWh_th`: sensible heat removed.
- `cooling_latent_kWh_th`: modeled outdoor-air moisture removal plus internal latent gains, during sensible-cooling hours only.
- `heating_electricity_kWh`: electric heat-pump heating plus resistance backup.
- `backup_electricity_kWh`: subset of heating electricity; do not add it to the heating total.
- `cooling_electricity_kWh`: modeled electricity for sensible and included latent cooling.
- `HVAC_electricity_kWh`: heating plus cooling electricity.
- `heating_cost_USD`, `cooling_cost_USD`, `HVAC_cost_USD`: modeled annual electricity costs. HVAC cost is heating plus cooling.
- `effective_heating_COP`: delivered annual heat divided by total heating electricity, including resistance backup.
- `peak_hour_HVAC_electric_kW`: maximum hourly-average electric input in the TMY model, not utility billing demand or a design peak.
- `cooling_over_rated_capacity_hours`: count of hours exceeding the assumed 10.55 kW cooling capacity. Zero in this run.
- `days_with_heating_and_cooling` (v2): days on which the model both heats and cools. v1 had 45–348 (median 209); v2 has 0–1.
- `hours_free_floating_in_deadband` (v2): hours when indoor air stays between 68 and 78 °F with no heating or cooling.
- `mean_indoor_temp_F` (v2): annual mean indoor air temperature.
- `v1_HVAC_cost_USD`, `change_vs_v1_percent`, `v1_cost_rank` (v2): v1 steady-state result for comparison.
- `weather_source_url`, `price_source_url`, `retrieved_date`: provenance.
- `cost_rank`: ascending annual HVAC cost among the sampled 78 cities.
- `energy_rank`: ascending annual HVAC electrical energy among the sampled 78 cities.

## Monthly comparison

One record per city-state-month; 12 rows per city. `month` is 1–12 in the synthetic typical year. Heating includes backup. Costs use the same flat annual state price in every month.

## Hourly weather and modeled loads

One record per city-state-month-day-hour; 8,760 per city. The file is gzip-compressed CSV.

- `hour_ending_local_standard`: 1–24. Hour 1 represents the interval ending at 01:00. No daylight-saving-time shift is applied.
- `source_year`: historical year selected by the TMY assembler. It can change across months. Do not treat it as a single continuous observed year or directly map its weekdays to a tariff calendar.
- `outdoor_temp_C`, `dewpoint_C`: Celsius dry-bulb and dew-point temperatures.
- `RH_percent`: relative humidity in percent.
- `pressure_Pa`: station atmospheric pressure in Pa.
- `GHI_Wh_m2`, `DNI_Wh_m2`, `DHI_Wh_m2`: global horizontal, direct normal, and diffuse horizontal irradiation over the one-hour interval. Numerically equal to the interval-average W/m² for a one-hour record, but stored units remain Wh/m².
- `wind_m_s`: wind speed in m/s.
- `indoor_air_temp_C`, `mass_temp_C` (v2): modeled indoor air and lumped-mass temperatures, °C.
- `heat_delivered_kWh`, `cool_sensible_kWh`, `cool_latent_kWh`: thermal energy over that hour, kWh thermal.
- `heatpump_heating_kWh`, `resistance_heating_kWh`, `cooling_electricity_kWh`: electricity consumed over that hour.
- `heating_cost_USD`, `cooling_cost_USD`: hourly electric cost using the state-average proxy.

Hourly modeled fields are exported to four decimals. Tiny summation differences from full-precision annual results are rounding, not additional load.

## State electricity prices

One record per state/D.C. `residential_cents_kWh_2025` and `_2024` retain EIA source precision. `source_url` points to Table 2.10. No state average climate or heating cost is implied by this table.

## Source manifest and quality

`city_manifest.json` stores a city-to-station mapping, original ZIP download URL, relative EPW filename and original ZIP SHA-256. The archive contains the EPW extracted from each downloaded ZIP. The SHA-256 refers to the original source ZIP, not the EPW or the delivered data package.

`data_quality.csv` records total/unique hourly counts, annual energy-balance error including storage change (Wh), mass-temperature closure over the recorded year (K), and hours above nominal cooling capacity.

`city_manifest.json` (v2) uses forward-slash relative paths and includes `city_id`.

## Expanded research data

All files below are in `deep_research/`. Currency is USD. A numeric zero means a modeled zero; missing or unpriced variables are explicitly labeled and are not silently treated as verified zero costs.

| File | Grain and meaning |
|---|---|
| `city_per_square_foot.csv` | 78 baseline cities. Cost and energy divided by 2,000 conditioned floor ft². These intensities are not universal scaling factors. |
| `house_size_results.csv` | 2,808 city × area × story runs (v2 model; adds `city_id`, `days_with_heating_and_cooling` and `heat_pump_scale`, the capacity multiple vs the 2,000-ft² reference). 750–5,000 ft² in 250-ft² steps; 1 or 2 stories. `total_kWh` is HVAC electricity, `HVAC_USD` uses the state's 2025 proxy price. `backup_kWh` is included in heating. |
| `sensitivity_results.csv` | 144 independent one-input changes around the v2 defaults (6 cities × 24), including setpoint bands, thermal-mass classes and internal gains. `change_percent` is percent, not fraction. The workbook displays it as stored (percent units). These are selected scenarios, not confidence intervals. |
| `national_residential_rate_inventory.csv` | 14,707 residential source versions. `rate_id` identifies an OpenEI record; EIA utility IDs can span many plans. `verified_current` is false for this automated inventory. |
| `national_energy_periods_and_tiers.csv` | 44,846 period/tier entries retaining source rate, adjustment, limit and unit. Source tier/period schedules are zero-indexed. A maximum and minimum do not describe the applicable hourly bill. |
| `residential_urdb.json` | Residential records in the original legacy bulk schema, including 12 × 24 weekday/weekend energy and demand schedules, tiers, caps, lookbacks, source URLs and notes where present. |
| `raw/usurdb.json.gz` | Original downloaded national bulk file; includes nonresidential data and multiple versions. See download manifest for retrieval details and SHA-256. |
| `verified_tariff_components.csv` | Nine manually checked official-source tariff components (v2: SRP May–Oct 2026 fuel decrease, assumed for E-28; Seattle Q1-2026 4% surcharge; PG&E E-TOU-C date 2026-03-27). Plan eligibility, some government charges, and actual bill cycles remain unresolved. A checked component schedule is not an address-verified bill. |
| `APS_monthly_adjustors.csv` | Twelve 2026 calendar-month scenarios. PSA/TCA prior rates are derived from the stated increase; ordinary REAC is used outside November. Negative REAC is a capped credit. Caps apply to the modeled nonsolar account. |
| `hourly_tariff_schedules.csv.gz` | 113,880 city/plan/hour rows. `hour_index` is zero-based EPW order. `local_civil_time` is the start of the corresponding tariff hour in synthetic 2026. `energy_USD_kWh` excludes separate APS monthly adjustors. `demand_USD_kW` is the plan's seasonal demand price, charged only through its billing rule. |
| `tariff_monthly_scenarios.csv` | City × plan × base profile × baseline zone × month. `base_energy_USD` excludes adjustors; `energy_USD` includes them. Fixed, demand, baseline and climate credits are separately recorded. `total_USD` is a subtotal excluding the plan's listed unpriced items. |
| `tariff_annual_scenarios.csv` | 120 annual scenarios. `incremental_HVAC_USD` = whole-house subtotal minus base subtotal. Energy increment includes modeled adjustors. Incremental baseline credit is subtracted. Fixed charges and identical climate credits cancel in this increment. |
| `city_data_coverage.csv` | 78 city coverage rows and analyst utility candidates. Not a parcel-level service-territory join. A missing tariff scenario means that only the state-average screening price was used for that city. |
| `variable_audit.csv` | 134 variables with units, status, present assumption/data, remaining input and source. For missing inputs, a link indicates where to obtain data or the required model specification. |
| `pcm_material_reference.csv` | Example RT25HC manufacturer properties; flags inconsistent capacity units. Does not define a complete phase-change or installed composite model. |
| `historical_cost_reference.csv` | Four 2024 CEC study cost items, preserving the house-area basis and 872/874-ft² source discrepancy. Not current supplier/installer quotes. |

Base-load profiles are illustrative: 4,800 kWh/year flat; 4,800 or 9,600 kWh/year with an evening concentration. Evening hourly relative weights are 0.35 at 00:00–06:00, 0.7 in other non-evening hours, and 1.2, 1.8, 3.2, 4.0, 2.5, 1.4 for the six hours starting at 16:00. Each profile is normalized to the stated annual kWh. These billing-only profiles do not alter the thermal model's internal heat gains.

The package includes model scripts and JSON intermediates for reproducibility. A standalone equipment-performance download script and EPA metadata are included, but no candidate equipment results were downloaded successfully. All savings and bills remain modeled rather than measured.
