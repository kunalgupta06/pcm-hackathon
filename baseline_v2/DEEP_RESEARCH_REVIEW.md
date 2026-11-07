# Deeper audit: house size, electricity tariffs and PCM economics

> **v2 update (7 Nov 2026):** the house-size and tariff tables below now use the v2 model: ISO 13790 5R1C with thermal mass, 68/78 °F deadband, RESNET internal gains. Tariff scenarios include SRP's May–Oct 2026 fuel decrease, Seattle's Q1-2026 surcharge and the PG&E date fix. Sensitivities are 144 runs. Other text citing v1 specifics (102 sensitivities, exact calculator, 72 °F) refers to v1. See CHANGELOG.md.

Updated November 7, 2026. This expands the original 78-city screening study. It does not establish a final cheapest-city ranking or demonstrate PCM savings.

## What is now available

| Deliverable | Coverage |
|---|---:|
| National climate and state-average price baseline | 78 cities, all 50 states and DC |
| Hourly weather and original modeled loads | 683,280 records |
| Geometry-aware size runs | 2,808 |
| House size range | 750–5,000 conditioned ft²; one or two stories |
| One-variable sensitivity runs | 144 across six cities (v2) |
| Residential utility-rate records downloaded | 14,707 |
| Utility IDs in those records | 2,668 |
| Energy-period and tier rows extracted | 44,846 |
| Official tariff component schedules checked and modeled | 9 across 5 utilities, applied to 6 cities |
| Annual tariff / base-load / baseline-zone scenarios | 120 |
| Hourly tariff-schedule records | 113,880 |
| Variables audited | 134 |

The 14,707 database records include historical and restricted plans. They are **not 14,707 verified current options**. The separate nine-plan sample has official-source checks but still needs address, account, tax and meter-cycle confirmation. The remaining 72 cities use state-average screening prices in this package.

## Per square foot: what transfers and what does not

Annual HVAC intensity = annual HVAC kWh / conditioned floor ft².

Annual HVAC cost intensity = annual HVAC dollars / conditioned floor ft².

These are useful comparison metrics. Multiplying an intensity by another house's area is only a rough proportional estimate. Roof area, exposed wall perimeter, stories, windows, air volume, people, equipment capacity and billing thresholds do not all scale together.

The v2 model recomputes footprint = floor area / stories; uses a 1.25 rectangular aspect ratio; recomputes wall perimeter and glazing at the same window-to-wall ratio; scales air volume; applies RESNET 301 internal gains for the floor area (3 bedrooms, 85% sensible); scales the heat-pump capacity with the house's design heat-loss coefficient (1.0 at the 2,000-ft² one-story reference). Door area stays at 40 ft². Insulation, the 68/78 °F deadband and the heat-pump COP curve stay unchanged. The 2,000-ft² one-story run reproduces the national baseline exactly.

The workbook calculator interpolates between direct v2 runs every 62.5 ft² (the same grid as the HTML calculator) and refuses out-of-range inputs. It is not a universal model of arbitrary architecture. The underlying model accepts custom positive areas, but a new shape, foundation, zoning, insulation or equipment choice must be modeled explicitly. In v2 the heat pump is scaled to each house's design heat loss; a positive capacity-warning count still means the ideal temperature may not be achievable with that equipment.

Illustrative **2025 state-average price screening**, rounded dollars:

| City | Conditioned ft² | Stories | HVAC $/year | $/ft²/year | HVAC kWh/year | Cooling over capacity, hours |
|---|---:|---:|---:|---:|---:|---:|
| Seattle | 1,000 | 1 | 163 | 0.163 | 1,240 | 0 |
| Seattle | 2,000 | 1 | 293 | 0.147 | 2,226 | 0 |
| Seattle | 3,000 | 1 | 415 | 0.138 | 3,149 | 0 |
| Seattle | 3,000 | 2 | 403 | 0.134 | 3,060 | 0 |
| Phoenix | 1,000 | 1 | 456 | 0.456 | 2,990 | 0 |
| Phoenix | 2,000 | 1 | 712 | 0.356 | 4,667 | 0 |
| Phoenix | 3,000 | 1 | 951 | 0.317 | 6,231 | 0 |
| Phoenix | 3,000 | 2 | 1,013 | 0.338 | 6,641 | 0 |
| Minneapolis | 1,000 | 1 | 568 | 0.568 | 3,591 | 0 |
| Minneapolis | 2,000 | 1 | 995 | 0.498 | 6,287 | 0 |
| Minneapolis | 3,000 | 1 | 1,395 | 0.465 | 8,812 | 0 |
| Minneapolis | 3,000 | 2 | 1,365 | 0.455 | 8,622 | 0 |

The denominator for PCM material and installation is different: retain **treated wall/ceiling area**, PCM mass and conditioned floor area as separate fields. A two-story house can have the same floor area but a different amount of installable PCM surface.

## Correct electricity-bill calculation

For each billing cycle, price the whole-house interval load. Apply the correct seasonal/time period, tiers, baseline allowance, fixed charge, demand definition, adjustors, caps, minimum bill, taxes and credits in the tariff's prescribed order.

**Incremental HVAC cost = Bill(base electricity + HVAC) − Bill(base electricity).**

For the PCM comparison, use **Bill(base + HVAC without PCM) − Bill(base + HVAC with PCM)**. Keep comfort and non-HVAC use consistent. A fixed charge generally cancels if the account and plan stay the same; a tier, capped credit or demand charge may not. Never add a fixed charge on top of an EIA blended state-average price without first separating its components.

Demand is in **kW**, energy in **kWh**. For a one-hour average, the interval's kWh is numerically equal to its average kW. Hourly data cannot recover an unobserved 15-minute or rolling demand peak.

### Why APS and SRP differ

APS R-3 uses the highest on-peak one-hour demand during the billing cycle. Cutting an hour that is below the maximum might save energy but leave the demand charge unchanged. SRP E-16 bills the average of daily maximum on-peak 60-minute demands. Its modeled mean includes days with an on-peak period. Cutting a single day's peak changes that mean by approximately the reduction divided by the number of on-peak days. [APS R-3](https://www.aps.com/-/media/APS/APSCOM-PDFs/Utility/Regulatory-and-Legal/Regulatory-Plan-Details-Tariffs/Residential/Service-Plans/Time-of-Use4pm-7pmWithDemandChargeR-3.pdf), [SRP E-16](https://www.srpnet.com/v3/assets/bltefc1fc708dcc94e7/blt3bc0beaf4fade7d9/2025-Ratebook-E-16-with-TCA-and-Export-Rate.pdf).

This makes load shape and PCM regeneration frequency important. A generic percentage reduction in peak power is insufficient. Recalculate the bill from the entire changed interval-load series, including charging and any later rebound.

### Details now included

- **Seattle:** flat and TOU options; three time periods; Saturday peaks; six NERC holidays. Saturday holidays remain Saturday, unlike a generic Friday-observation assumption. [City Light](https://www.seattle.gov/city-light/residential-services/billing-information/time-of-use).
- **SMUD:** seasonal TOU and fixed options, $27/month fixed charge, utility holiday rules. Fixed-date weekend holidays do not make the adjacent weekday off-peak. Current hydro adjustment is $0/kWh; state/local taxes and optional customer discounts remain separate. [Rate periods](https://www.smud.org/Rate-Information/Residential-rates/Time-of-Day-5-8pm-Rate/Rate-details), [rates and hydro adjustment](https://www.smud.org/Rate-Information).
- **APS:** base seasonal energy/demand charges plus calendar-month representations of six published adjustors. PSA changes in February; TCA in June; November REAC is a credit capped at $12.21, then returns to a charge capped at $2.49 in December. Earlier PSA/TCA rates are derived from the utility's stated increases. Ordinary REAC is used outside November. Actual bill cycles and government charges remain unpriced. [APS adjustors](https://www.aps.com/en/Utility/Regulatory-and-Legal/Rates-Schedules-and-Adjustors/Bill-Adjustors).
- **SRP:** the newer E-16 and E-28 schedules, distinct evening peak windows, daily 08:00–15:00 super-off-peak, and a separate July–August season. Service charge assumes a detached home at no more than 225 A. Published totals already include their listed fuel and transmission adjustments. Government taxes/fees remain excluded. [E-28](https://www.srpnet.com/v3/assets/bltefc1fc708dcc94e7/blt7f2a262ae2e87cf8/2025-Ratebook-E-28-with-TCA-and-Export-Rate.pdf).
- **PG&E:** bundled E-TOU-C and E-TOU-D, June 2026 energy rates, fixed daily charge, climate credit, and all ten all-electric baseline-zone allowances for E-TOU-C. No city is assigned a guessed baseline zone. CCA customers need the correct supplier rate and applicable delivery/PCIA treatment. [E-TOU-C](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_E-TOU-C.pdf), [E-TOU-D](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_E-TOU-D.pdf).

### Illustrative tariff results

These are **modeled incremental HVAC subtotals**, not complete quoted bills. They use a 2,000-ft² house, generic heat pump, synthetic TMY weather mapped to the 2026 calendar, and an assumed flat 4,800-kWh/year non-HVAC load. The year mapping supplies weekdays and holidays; it does not turn TMY into observed 2026 weather. California and Seattle tariff hours use civil time; Phoenix stays on Mountain Standard Time. Calendar months approximate meter-read cycles. SRP's observed Saturday holiday is treated as Friday pending account-calendar confirmation.

PG&E's June rates are annualized rather than reconstructed for January–May; APS's documented rider dates are applied by calendar month. Comparisons with the national 2025-price ranking therefore combine different price bases and should not be read as a controlled year-over-year result.

| City | Plan | Energy + included adjustors, $ | Demand increment, $ | HVAC increment, $/year | $/ft²/year |
|---|---|---:|---:|---:|---:|
| Phoenix | APS | 447 | 288 | 735 | 0.368 |
| Phoenix | SRP16 | 398 | 148 | 546 | 0.273 |
| Phoenix | SRP28 | 551 | 0 | 551 | 0.275 |
| Bakersfield | PGED | 1,005 | 0 | 1,005 | 0.502 |
| Fresno | PGED | 990 | 0 | 990 | 0.495 |
| Sacramento | SMUD | 363 | 0 | 363 | 0.181 |
| Sacramento | SMUD_fixed | 354 | 0 | 354 | 0.177 |
| San Francisco | PGED | 232 | 0 | 232 | 0.116 |
| Seattle | SCL_flat | 303 | 0 | 303 | 0.152 |
| Seattle | SCL | 287 | 0 | 287 | 0.143 |

The full results also include shaped evening base loads of 4,800 and 9,600 kWh/year and the PG&E baseline-zone cases. Those profiles are scenarios, not measured household demand. Appliance heat gains are not coupled to the billing-only base-load profiles; that coupling remains necessary for a fully consistent whole-building model. Do not interpret APS and SRP as interchangeable providers at a given address.

## Audit of the national rate database

The public [OpenEI utility-rate database](https://apps.openei.org/USURDB/) download contains multiple versions and plans with specific eligibility conditions. The collected residential subset contains:

| Date / approval status | Records |
|---|---:|
| Ended | 7,149 |
| Date eligible but current status unverified | 5,897 |
| Start date missing | 490 |
| End date before start date | 299 |
| Not approved in source | 872 |

There are 3,460 records with intraday TOU schedules, 6,212 with multiple energy tiers and 727 with demand structures. These counts overlap and include old records. Absence of an end date does not prove a tariff is current. Keep effective dates, source URLs, service type, restrictions, schedules, tier units, minimum charges and demand fields. National source files and normalized inventories are included. The downloaded inventory itself has zero records upgraded to current-verified status; the manually checked sample schedules are a separate dataset.

## Other variables that materially change the result

The 134-row audit identifies status, units, present assumption or data, needed next input and source for each variable. It covers:

1. Geometry, stories, shared walls, glazing orientation, foundation, attic and thermal zones.
2. Whole-assembly insulation, thermal bridges, solar absorption, shading, longwave radiation and thermal mass.
3. Infiltration, wind/stack effects, ventilation, humidity, internal moisture and night flushing.
4. Hourly weather, station representativeness, actual-year variability, design extremes and future conditions.
5. Heat-pump performance maps, capacity, cycling, defrost, fans, ducts, standby power, backup and controls.
6. Occupancy, appliances, EVs, water heating, pool loads, PV and batteries.
7. Tariff schedules, riders, taxes, caps, credits, eligibility, suppliers and effective dates.
8. PCM enthalpy/hysteresis, conductivity, mass, placement, thermal contact, cycling and recharge.
9. Installed costs, comparator insulation, replacement, incentives, discounting and uncertainty.

A source link in a row marked **missing** identifies a source to obtain or a model-input specification; it is not a claim that the missing value has been collected. Many inputs require a specific property, customer or product. They cannot be inferred uniquely from state or city.

## Literature and material-data corrections

- CEC Table 3 reports PCM + drywall at $2.88/ft² and $2,522 for an 874-ft² **house model**. The model description says 872 ft² conditioned space. Preserve this small source discrepancy; do not relabel the cost as a current quote per treated wall ft². Finishing and painting is a separate reported cost. The study's furnace/AC and thermostat assumptions also differ from this all-electric 72°F prototype. [CEC report, pp. 7 and 27](https://www.energy.ca.gov/sites/default/files/2024-07/CEC-500-2024-086.pdf).
- RT25HC's manufacturer sheet reports 230 kJ/kg and 58 Wh/kg for storage capacity. Those are inconsistent: 230/3.6 = 63.89 Wh/kg. The storage capacity includes sensible and phase-change storage over its stated interval, so do not label the entire value latent heat. The property table is retained with the conflict flagged. [Rubitherm datasheet](https://www.rubitherm.com/media/products/datasheets/Techdata_-RT25HC_EN_09102020.PDF).
- ENERGY STAR's cold-climate criteria include COP at 5°F of at least 1.75 and at least 70% of nominal 47°F heating capacity at 5°F. Those limits do not supply an hourly performance curve or select a particular heat pump. The current model remains generic. EPA dataset metadata were retrieved; the expanded equipment download could not run because the automatic approval service hit a usage limit. [ENERGY STAR criteria](https://www.energystar.gov/products/air_source_heat_pumps/key-product-criteria).
- The literature brief's strong claim that no comparable map exists should remain a research hypothesis until a systematic literature review confirms it. Its studies' costs, climate assumptions and savings should not be transplanted into this prototype as measured inputs.

## What is still needed to answer the MIT challenge

The current hourly physics is a **steady-state screening model**. It has no dynamic building storage or PCM state of charge. It cannot yet predict PCM cycling, hourly shifting, hysteresis, night recharge or savings. It also omits full humidity control, duct/fan/defrost effects and multiple actual weather years. The national ranking remains conditional on those simplifications.

The next physical comparison must simulate the same house and comfort in three cases: existing insulation; the next feasible insulation increment; and PCM added to the same baseline. Use a validated transient wall/building model and manufacturer or laboratory enthalpy curves. Validate partial cycles, timestep convergence, energy conservation, HVAC controls and demand intervals. [EnergyPlus surface-material documentation](https://energyplus.readthedocs.io/en/stable/guides/input-output-reference/1.9-group-surface-construction-elements.html).

For the economic decision, define incremental lifetime cost relative to additional insulation:

**Delta LCC = installed cost(PCM) − installed cost(insulation) + present value[Bill(PCM) − Bill(insulation) + maintenance/replacement difference] − present value[salvage difference].**

PCM wins financially only if Delta LCC is negative at the same comfort and constraints. Compare feasible equal-budget alternatives as a separate optimization. Count HVAC downsizing only when a real installed purchase is avoided. Keep dollars in the same price year and real/nominal discount convention. Use local installed quotes, not raw material prices, for deployment claims.

For illustration only, a constant **$100/year advantage over extra insulation** has a present value of **$1,488 over 20 years at a 3% real discount rate** before maintenance, replacement and salvage differences. That is a break-even premium, not an estimate of PCM savings.

## Verification and limits

- All 78 new 2,000-ft² runs reproduce the previous baseline to less than 0.000001 kWh.
- All 120 tariff scenarios reconcile whole-house minus base bill to their energy, demand and allowance components.
- Tests distinguish APS monthly maximum from SRP average daily maxima and check period/holiday boundaries.
- Workbook tests exercise area, stories, interpolation, invalid area, prices and rankings. Exported formulas are scanned for errors. Native Microsoft Excel recalculation has not been independently tested.
- These checks verify arithmetic and implemented rules. They do not substitute for empirical calibration, full tariff validation or a validated PCM simulation.

## Files and use

Open the workbook's **House size calculator** and edit the blue city, conditioned-area and stories cells. **City comparison** retains the 2,000-ft² state-average baseline and adds annual per-ft² metrics. **Tariff components** shows periods, rates, dates and omissions. **Tariff cost scenarios** contains the 120 fixed 2,000-ft² scenarios. **Variable audit** and **City coverage** show the remaining work.

The data archive contains the raw weather, source inventory, normalized national tariff records, size runs, sensitivity results, tariff schedules, monthly billing outputs, dated APS adjustors, material/cost references and reproducible model inputs. Normalized national records retain source versions rather than pretending every plan is current.
