# Energy specialist: decision log

Owner: Energy specialist · Started Saturday 7 Nov 2026 · Every number used in the model lives in `03_inputs/inputs.csv` with its source. This file records the *choices* and why.

Status labels used everywhere:
- **OFFICIAL**: taken directly from a utility, government or peer-reviewed source
- **DERIVED**: calculated from official numbers (the formula is written next to it)
- **HYPOTHETICAL**: a clearly labeled what-if tariff, because no real one exists
- **ASSUMPTION**: no source found; team must confirm
- **PENDING**: still to collect

---

## D1. Cities: Phoenix, Miami, Boston, Fresno

- **Decision:** Use the four cities fixed in the team plan. The only open choice was the California city.

## D2. California city = Fresno (PG&E)

- **Decision:** Fresno.
- **Why (with sources):**
  1. **High peak price.** Fresno is served by PG&E. Its default residential plan E-TOU-C charges $0.52240/kWh at peak in summer (4–9 pm every day), from the [PG&E E-TOU-C tariff, rates effective June 1, 2026](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_E-TOU-C.pdf).
  2. **Real cooling load, plus nights cool enough to recharge PCM.** The National Weather Service lists Fresno's early-July normals as 96–97 °F maximum and 68–69 °F minimum ([NWS Hanford, July normals](https://www.weather.gov/hnx/fat07nrm)). In the TMY3 weather file, Fresno has the largest summer day–night swing of our cities (17.5 °C), and 97% of summer nights drop below 22 °C. In Phoenix and Miami, 0% do (`02_weather/weather_summary.csv`, computed by `04_model/weather_summary.py`).
  3. **Why not San Diego or San Francisco:** both have high prices but mild coastal climates, so there's little load for PCM to shift. Our weather file comparison doesn't include them; this is a qualitative judgment.

## D3. Weather data: TMY3 files from NREL

- **Decision:** Use NREL TMY3 EPW files (typical year, hourly), the standard EnergyPlus format.
- **Source:** Downloaded from the [NREL EnergyPlus GitHub repository, `weather/` folder](https://github.com/NREL/EnergyPlus/tree/develop/weather) (commit 5f11110, 6 Nov 2026), because climate.onebuilding.org and NREL's site are blocked from Claude's workspace.
- **Boston:** not in that repository, so it was downloaded manually from [climate.onebuilding.org (Massachusetts folder)](https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/): `USA_MA_Boston-Logan.Intl.AP.725090_TMY3` (Boston Logan Intl AP, station 725090, TMY3, file dated 16 Mar 2026). Same TMY3 format as the other three cities.

## D4. Tariffs: two per city, using official utility documents

- **Decision:** For each city, (a) the utility's real residential time-of-use plan, and (b) a time-of-use plan with a demand charge.
- **Source for "2 tariffs per city":** Team *Plan v2*: "2 tariffs (time-of-use, and time-of-use with a demand charge)".
- Each rate's source URL is on its row in `inputs.csv`.

| City | Time-of-use (a) | Time-of-use + demand charge (b) |
|---|---|---|
| Phoenix | APS TOU 4–7 pm Weekdays (**real**) | APS TOU 4–7 pm with Demand Charge, R-3 (**real**) |
| Miami | FPL RS-1 + RTR-1 TOU rider (**real**) | **Hypothetical** (D6) |
| Fresno | PG&E E-TOU-C (**real**) | **Hypothetical** (D6) |
| Boston | **Hypothetical** (D5) | **Hypothetical** (D5 + D6) |

## D5. Boston has no residential time-of-use rate, so we use a hypothetical one

- **Finding:** Eversource's Greater Boston rate summary lists only residential R-1, R-2, R-3 and R-4, with no residential TOU ([Eversource rates](https://www.eversource.com/Content/docs/default-source/rates-tariffs/ema-greater-boston-rates.pdf)). Massachusetts DOER's April 2026 proposal confirms the only seasonal TOU rate (T-1) is closed and non-residential ([DOER TOU Rate Proposal, pp. 14–15](https://www.mass.gov/doc/doers-time-of-use-rate-proposal/download)).
- **Decision:** Build a hypothetical Boston TOU:
  - Peak window **4–8 pm**, from DOER's proposal (p. 22: "an initial peak period of 4-8 PM").
  - Weekdays only (**ASSUMPTION**: DOER's text doesn't say which days).
  - Prices split revenue-neutrally around the 2025 Massachusetts residential average of **30.48 ¢/kWh** (EIA, via [AGA Massachusetts analysis](https://www.aga.org/wp-content/uploads/2026/09/Massachusetts-Residential-Energy-Cost-Analysis.pdf)), using DOER's illustrative **1.77 : 1** peak/off-peak ratio (footnote 107; DOER says it is an illustration, not a proposal).
  - Off-peak = 30.48 / (0.881 + 1.77 × 0.119) = **27.92 ¢/kWh**; peak = **49.42 ¢/kWh** (20 of 168 weekly hours are peak).
- **Pitch framing:** "Boston is a what-if: Massachusetts is considering TOU rates right now."

## D6. Demand charges: only Phoenix is real; the other cities use a labeled what-if

- **Finding:** Of the four utilities, only APS offers a residential demand-charge plan ([APS demand plan](https://www.aps.com/demandplan): $19.585/kW summer, $13.747/kW winter, on the single highest hour from 4–7 pm on weekdays). FPL's demand rates apply only to general service customers of 25 kW and above ([FPL tariff index](https://www.fpl.com/rates/pdf/electric-tariff-section8.pdf)). PG&E's residential plans have no demand charge ([PG&E residential plans](https://www.pge.com/assets/pge/docs/account/billing-and-assistance/bill-inserts/0925-res-rate-plans.pdf)). Eversource lists none for residential customers.
- **Decision:** For Miami, Fresno and Boston, the "with demand charge" tariff = that city's own TOU energy prices + APS's residential demand charge, labeled **HYPOTHETICAL**. I didn't use commercial demand tariffs, because a house wouldn't qualify for them.
- **Why it matters for the pitch:** if the thermal battery only wins under demand charges, that win is real today only in Arizona. That's a finding in itself.

## D7. Which price tier to use

- **Decision:** Use the **marginal** price, i.e. the price the household pays on its *last* kWh, since PCM changes only those kWh.
  - PG&E: no baseline credit (above-baseline usage). Low case includes the −$0.08140/kWh baseline credit.
  - FPL: >1,000 kWh/month tier. Low case uses the ≤1,000 kWh tier.
- **Reason:** An all-electric house with a heat pump usually exceeds the baseline or 1,000 kWh in heavy-cooling months. This is a judgment; the low values in `inputs.csv` let the sensitivity check test it.

## D8. Costs

| Item | Base value | Range | Source |
|---|---|---|---|
| Paraffin PCM (microencapsulated) | $4.00/kg | $3.42–5.71 | DERIVED from [NREL/Fraunhofer, Kosny et al. 2013](https://www.nrel.gov/docs/fy13osti/55553.pdf), pp. 9 and 14 |
| Bio-based PCM | $3.58/kg | $1.65–5.50 | Same report, p. 9 (Entropy Solutions quote) |
| Salt hydrate PCM (packaged) | $4.02/kg | $3.08–4.95 | Same report, p. 10 (PCMEnergy) |
| Extra insulation (XPS) | $1.99 per m² per cm | $1.31 (EPS) to $2.54 (polyiso) | DERIVED from [Fine Homebuilding rigid foam guide](https://finehomebuilding.com/tool-guide/articles/insulation-rigid-foam.aspx) |
| Heat pump capacity | $529/kW | $529–1,275 | DERIVED from [Wilson et al. 2024, NREL](https://nrel.gov/docs/fy24osti/84775.pdf), Table 6; high from [NYSERDA 2022](https://www.nyserda.ny.gov/-/media/Project/Nyserda/Files/Publications/PPSER/Program-Evaluation/22-04-Replacing-Fossil-Fuel-Heat-with-Mini-Split-Heat-Pumps-in-Urban-House-Stock.pdf) |

- **Main PCM type for the base case:** not my call. The thermal expert picks it (question sent). The model runs all three prices, so the choice doesn't block anything.
- **Installation labor** for PCM and extra insulation = $0 (**ASSUMPTION**, no source found).

## D9. Discount rate and lifetime

- **Lifetime:** 20 years (team *Plan v2*, task 8).
- **Discount rate:** **3.0% real**, the federal energy-project rate for 2025 ([NIST IR 85-3273-40, p. 1](https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.85-3273-40.pdf)). Sensitivity: **2%** (OMB Circular A-4, 2023 revision) and **7%** (OMB Circular A-4, 2003 version), both described in the [OMB 2023 announcement](https://bidenwhitehouse.archives.gov/omb/briefing-room/2023/11/09/biden-harris-administration-releases-final-guidance-to-improve-regulatory-analysis).
- **Electricity prices:** held constant in real terms (**ASSUMPTION**).

## D10. FLAG: the "$1/kg" claim in the team task list doesn't match the main source

- The task list says "published studies find passive PCM walls need PCM under about $1/kg to pay off."
- The NREL/Fraunhofer report found the opposite for Phoenix: PCM gypsum board reached a **7-year payback at a PCM price of $3.00/lb (≈ $6.61/kg)**, and a **10-year payback at up to $3.50/lb (≈ $7.72/kg)** ([Kosny et al. 2013, Executive Summary p. ix](https://www.nrel.gov/docs/fy13osti/55553.pdf)). A 2014 paper on low-cost bio-PCM also cites Kosny et al.'s 10-year-payback cost targets of **$3.30–8.80/kg** ([Energy Conversion and Management, 2014](https://www.sciencedirect.com/science/article/abs/pii/S019689041400795X)).
- **Action:** whoever wrote the $1/kg line should find its source before it goes on a slide. Our own model's break-even will settle it for our cases.
