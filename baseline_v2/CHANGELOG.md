# Changelog: v1 → v2 (7 November 2026)

Rows 16–18 were added after a second independent audit of v2, which found no high-severity errors.

v2 fixes every problem found in an independent audit of the v1 package. v1 outputs are kept unchanged in `v1_steady_state_results/` for comparison.

## Problems found and how each was fixed

| # | Problem in v1 | Impact | Fix in v2 |
|---|---|---|---|
| 1 | **No thermal mass.** Hourly steady-state balance; the house responded instantly to sun and outdoor temperature. | 45–348 days/yr (median 209) with heating AND cooling on the same day (v2: 0–1); spurious January cooling in Phoenix, Las Vegas and Los Angeles; overstated both loads. A no-mass baseline also overstates the loads PCM would absorb, which would inflate any later PCM-savings estimate. | `hvac_core.py`: ISO 13790:2008 simple hourly method (5R1C, Annex C), lumped thermal mass class "light" (110 kJ/K per m² floor, wood frame). One warm-up year; periodic closure checked. |
| 2 | **Single 72 °F setpoint for heating and cooling.** | No float band; heated and cooled to the same temperature. | Deadband 68 °F heating / 78 °F cooling (ANSI/RESNET/ICC 301 reference home). Sensitivities 70/75, 72/72 and 66/80. |
| 3 | **Internal gains 450 W**, about half a typical reference house; no internal latent gain. | Load split skewed toward heating; humid-climate latent load understated. | RESNET 301 reference-home internal gains (17,900 + 23.8·CFA + 4,104·N_br Btu/day; ≈950 W for 2,000 ft², 3 BR), 85% sensible; the latent share is added to cooling latent load. |
| 4 | **No long-wave radiation to the sky.** | Roof gains slightly high, night losses low. | ISO 13790 §11.3.5 long-wave term on roof, walls and windows. |
| 5 | **Windows-only paths** (`raw\weather\...`) in `city_manifest.json`. | `analyze.py` crashed on macOS/Linux. | Forward slashes; scripts also normalise at load time. |
| 6 | **Duplicate city names** (Portland OR/ME, Charleston SC/WV). | Joins on city name silently mixed rows. | `city_id` = "City, ST" added to manifest and every output. |
| 7 | **SRP May–Oct 2026 fuel-cost decrease missing.** | SRP E-16 Phoenix overstated ~$18/yr. | −$0.0038/kWh on every period, May–Oct (current E-16 PDF). Applied to E-28 as an assumption: board-approved for all plans but not yet on the linked E-28 PDF. |
| 8 | Seattle City Light 4% RSA surcharge (Jan–Mar 2026) ignored. | Small. | ×1.04 on energy charges Jan–Mar. |
| 9 | PG&E E-TOU-C effective date labelled 2026-06-01. | Label only. | Relabelled 2026-03-27 (rates unchanged and matching). |
| 10 | **Workbook cost-rank formula** matched 15-digit text copies; after recalculation Newark and Detroit tied at 63 and rank 62 vanished. | Wrong ranks after any recalculation. | `RANK()` formulas. |
| 11 | Workbook size-calculator error understated (0.522% claimed, 0.530% found). | Documentation. | Workbook and HTML now interpolate the same 62.5-ft² direct-run grid; the error stated is measured against direct off-grid simulations. |
| 12 | Per-ft² cells labelled "USD/year" and "kWh/year". | Misleading units. | Labels now $/ft²/yr and kWh/ft²/yr. |
| 13 | `calculator_template.html` threw an error when opened directly. | Confusing. | Marked as a build template; shows a message instead of crashing. |
| 14 | Workbook builder required the unavailable `@oai/artifact-tool` package. | Not reproducible. | `build_workbook.py` (openpyxl). The old `.mjs` is moved to `v1_steady_state_results/`. |
| 15 | Variable audit described v1 (72 °F, steady state, no long-wave, no internal latent, 200/250 W gains). | Stale. | 13 rows corrected at the source (`deep_research/build_audit.py`) and regenerated. |
| 16 | **One fixed 10.55 kW heat pump for every house size** (found by the independent v2 audit). | At 5,000 ft² Minneapolis drew 26% of heating electricity from resistance backup; large Phoenix houses exceeded cooling capacity. | Heat-pump capacity scales with each house's design heat-loss coefficient (2,000-ft² one-story reference = 10.55 kW, so the national baseline is unchanged in sizing). Minneapolis 5,000 ft² backup share falls to 1.7%; no capacity exceedance at any size. `equipment_sizing='fixed'` reproduces the old behaviour. |
| 17 | Tests were not independent: the energy balance holds by construction, and the transient tolerance was loose (0.35 K). Equipment and latent logic were untested. | Weak verification. | Added `tests/test_independent.py`: a separate re-implementation with solar on (within 0.2%) and hand checks of cutoff, capacity cap, backup, COP and latent. Transient tolerance tightened to 0.01 K; the balance test is relabelled as a consistency identity. |
| 18 | Small physics details: no ISO window angular factor; fixed 11 K sky ΔT; `ground_reflectance` override ignored; gains sensitivity silently dropped latent. | About ±2–3% in sunny cities. | F_w = 0.9 (ISO 13790 §11.3.3); sky ΔT 13 / 11 / 9 K by latitude (§11.4.6); albedo override applied; separate `internal_latent_gains_W` parameter. |

## Retired v1 components

The v1 "exact calculator" (`mathematical_core.py`, `build_exact_calculator.py`, `defend_model.py` and their outputs) relied on annual energy being a closed-form function of area. That holds only for the steady-state v1 model. With thermal mass it no longer does, so these files are moved to `v1_steady_state_results/v1_exact_calculator/`. They are replaced by a direct-run grid with measured interpolation error (`deep_research/calculator_validation.csv`) and the physics tests in `tests/`.

## What v2 still does not do

- **No PCM yet.** The 5R1C model gives the time-stepping base a PCM layer needs, but a single lumped capacitance cannot represent phase-change enthalpy, melt temperature or hysteresis. Add a layered wall (enthalpy-method finite difference, or COMSOL) coupled to the zone before predicting PCM savings.
- Not calibrated to measured homes; no duct, fan, defrost or cycling losses; no humidity balance outside cooling hours.
- Flat state-average prices in the national ranking; only 9 verified tariffs in 6 cities.
