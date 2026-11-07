# COMSOL PCM challenge: Energy specialist workspace

Energy specialist work for the 4 cities (Phoenix, Miami, Boston, Fresno). **Every number and decision has a source.** Numbers are in `03_inputs/inputs.csv` (source URL on each row); decisions and reasoning are in `01_decisions/decision_log.md`.

## Folder map

| Folder | What's inside |
|---|---|
| `01_decisions/decision_log.md` | Every choice (D1–D10) with its reason and source, including flags for the team |
| `02_weather/` | TMY3 weather files for all 4 cities + `weather_summary.csv` (D3) |
| `03_inputs/inputs.csv` | The single inputs file: cities, 8 tariffs, costs, finance, calendar assumptions, each with status + source |
| `04_model/` | `cost_model.py` (20-year cost, break-even, sensitivity), `weather_summary.py`, `make_placeholder_results.py` |
| `05_outputs/` | Break-even, cost breakdown, control premium, sensitivity, equal-budget table |

## Status

| Item | Status |
|---|---|
| Decisions + inputs file | Done |
| Weather | Done (all 4 cities) |
| Tariffs (8) | Done. Phoenix both real; Miami and Fresno TOU real; 4 labeled hypothetical (no real tariff exists) |
| Unit costs, discount rate | Done, all sourced; 2 labor assumptions flagged |
| Cost model | Built and tested; **waiting on Kunal's real results** |
| Break-even + sensitivity | Runs; current outputs are **PLACEHOLDER** |

## Open flags (need a team answer)

| # | Flag | Where it's recorded | Who |
|---|---|---|---|
| F1 | **Outputs are PLACEHOLDER.** Don't use `05_outputs/*_PLACEHOLDER.csv` on slides; rerun `cost_model.py` when real results arrive | file names, `data_status` column, this README | Kunal → Energy |
| F2 | **PCM installation labor = $0** (no source found) | `inputs.csv` row `pcm_installation_labor` (ASSUMPTION, "TEAM TO CONFIRM"); decision log D8 | Team |
| F3 | **Extra insulation installation labor = $0** (no source found) | `inputs.csv` row `insulation_installation_labor` (ASSUMPTION, "TEAM TO CONFIRM"); decision log D8 | Team |
| F4 | **"PCM must cost under ~$1/kg" claim** conflicts with NREL report ($6.6–7.7/kg for 7–10-yr payback in Phoenix) | decision log D10 | Author of the task list |
| F5 | ✅ Resolved: Boston TMY3 weather file added | `inputs.csv` (OFFICIAL); decision log D3 | n/a |
| F6 | Main PCM type and standard house numbers not chosen yet | decision log D8 | Thermal expert |

## For Kunal: results format the cost model reads

Two CSV files (full description at the top of `04_model/cost_model.py`):
- `results_hourly.csv`: city, case, option, controller, tariff_id, hour (1–8760), elec_kWh
- `results_meta.csv`: city, case, option, controller, tariff_id, pcm_kg, extra_insulation_cm, wall_area_m2, hp_capacity_kW, data_status

For the passive-wall case, include insulation-only runs at several extra thicknesses (e.g. 0, 1, 2, 4, 6, 8, 12 cm XPS, k = 0.0288 W/m·K) so the model can match the same budget as any PCM price. `05_outputs/equal_budget_insulation_table.csv` shows how many cm each PCM budget buys.

## For the Developer: output files

| File | Use it for |
|---|---|
| `breakeven.csv` | Headline break-even map (city × tariff, both cases) |
| `cost_breakdown.csv` | Cost-breakdown chart (energy vs demand charges per option) |
| `control_premium.csv` | How much smart control raises the break-even price |
| `sensitivity.csv` | "What would change the answer" slide; last rows = today's PCM market prices |
| `equal_budget_insulation_table.csv` | Explaining the fair comparison |

Check the `data_status` column: **PLACEHOLDER = not for slides.** Label hypothetical tariffs on charts (MIA_TOUD, FRE_TOUD, BOS_TOU, BOS_TOUD; decision log D5–D6).

## How to run

```bash
cd COMSOL-ENE
# weather stats
python 04_model/weather_summary.py 02_weather 02_weather/weather_summary.csv
# when Kunal's results arrive, put results_hourly.csv + results_meta.csv in a folder, then:
python 04_model/cost_model.py 03_inputs/inputs.csv <results_folder> 05_outputs
# to regenerate the placeholder demo results (format test only, NOT real physics):
python 04_model/make_placeholder_results.py 02_weather 03_inputs/inputs.csv 04_model/placeholder_results
```
Requires Python 3 + numpy.

## Important: PLACEHOLDER outputs

The files in `05_outputs/` ending in `_PLACEHOLDER` were computed from **invented house and PCM numbers** in `make_placeholder_results.py` (no sources; deliberately labeled). They only prove the pipeline works. **Don't use them on slides.** `equal_budget_insulation_table.csv` is real (it depends only on sourced costs).
