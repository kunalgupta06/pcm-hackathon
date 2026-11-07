# Mathematical methods and evidence for the house-energy and PCM study

> **v2 note (7 Nov 2026):** Sections 2–4 and the calculator/regression results in section 7 describe the **v1 steady-state model**. Its exact closed-form size reduction does not hold once thermal mass is added, so those files are archived in `v1_steady_state_results/v1_exact_calculator/`. v2 equations are in `hvac_core.py` (ISO 13790 Annex C). v2 verification is in `tests/test_hvac_core.py`: energy balance, independent steady-state and 1-minute transient solves, periodic closure and the v1 limit case, plus `tests/test_independent.py` (separate re-implementation with solar on, equipment hand checks); 24/24 passing. Calculator interpolation is validated in `deep_research/calculator_validation.csv` (max 0.04%). Sections 5, 6 and 8 (billing, PCM equations, economic comparison and evidence gates) apply unchanged.


Prepared 7 November 2026. Applies to the delivered prototype and archived inputs, not to every real building.

## Decision and scope

Use direct evaluation of the stated heat-balance equations for the current house-size calculator. A Gaussian process is unnecessary for this relatively inexpensive, algebraically reducible model. The new `House_energy_calculator.html` evaluates a compiled, piecewise analytical expression. It does not fit or interpolate annual energy results. The spreadsheet retains its original linear interpolation for convenience, with its numerical limitation disclosed.

There are three distinct evidence standards:

1. **Derivation:** show that equations follow from declared assumptions and units. Mathematical equivalence can be established conditional on those assumptions.
2. **Verification:** show that the implementations reproduce independent calculations and one another within stated numerical tolerances. Finite tests support an implementation; they do not constitute a formal proof over all floating-point inputs.
3. **Validation:** compare predictions with independent physical measurements or appropriate reference cases. This prototype has not been validated against measured homes, heat-pump performance, or PCM installations. Numerical precision does not resolve that gap. This distinction follows the verification/validation framework described by [NIST](https://www.nist.gov/publications/summary-industrial-verification-validation-and-uncertainty-quantification-procedures).

The justified present claim is: **a reproducible comparison of a specified hypothetical house under sampled climates and stated price assumptions.** It is not a verified ranking of the cheapest places to live, a quote for a real house, or evidence that PCM pays back.

## 1. Geometry and why a universal dollars-per-square-foot multiplier fails

Let A be conditioned floor area in ft²; s ∈ {1,2} the story count; r = 1.25 the footprint aspect ratio; and h = 8 ft the height per story. The same rectangular footprint is used on every story, with all exterior surfaces exposed.

\[
F=A/s,\quad L=\sqrt{rA/s},\quad W=\sqrt{A/(rs)},\quad H=hs.
\]

The gross exterior wall area is

\[
S_w=2(L+W)H=2h\sqrt{s}\left(\sqrt r+1/\sqrt r\right)\sqrt A.
\]

Roof and ground-floor areas are each A/s. Windows occupy f = 300/1440 of gross walls, doors occupy 40 ft², and opaque walls occupy (1−f)S_w−40. The window fraction is fixed; the absolute window area is not. Volume is hA ft³, not hAs, because A already includes all stories. Internal sensible gain is 200 + 250A/2000 W. These are assumptions defining the prototype, not empirical scaling laws for all homes.

This produces area-proportional roof, floor, air exchange and plug terms; square-root-area wall and window terms; and constant door and occupant terms. Even before HVAC mode changes, energy intensity has the form

\[
E(A)/A=\alpha+\beta/\sqrt A+\gamma/A.
\]

Consequently, calculate energy and cost for the actual specified geometry first, then divide by floor area. Multiplying one house's $/ft² by any other area is not generally valid. PCM material area, exterior wall area, and conditioned floor area must remain separate denominators.

## 2. Hourly heat balance and units

Use positive q for net sensible heat entering the indoor zone. Temperatures in heat balances are °C; differences are K. At each one-hour weather interval t,

\[
q_t=(UA+\dot m_t c_p)(T_{o,t}-T_i)+Q_{internal}+Q_{window,t}+Q_{opaque,t}.
\]

Here UA is W/K, mass flow is kg/s, air specific heat is 1006 J/(kg·K), and every q term is W. The indoor temperature is fixed at 72°F. This is an hourly steady-state balance: it assumes immediate removal or supply of the net load and contains no building heat storage.

### Envelope and air exchange

For a surface measured in ft² with U in Btu/(h·ft²·°F),

\[
UA_{SI}=0.527527926\sum_j U_jS_j,\qquad U_j=1/R_j.
\]

The factor is approximately 0.29307107 W/(Btu/h) × 1.8 °F/K. Effective whole-assembly R-values, rather than insulation-cavity R alone, are required. Defaults: wall R20, ceiling R49, floor R30, door R5; window U0.30. The floor uses outdoor air as the temperature boundary, representing a simplified ventilated crawlspace. It does not represent a slab or basement.

\[
\dot V=hA(0.028316846592)\,ACH/3600,\quad
\rho_t=P_t/[287.05(T_{o,t}+273.15)],\quad \dot m_t=\rho_t\dot V.
\]

ACH = 0.35 h⁻¹. Volume conversion is m³/ft³, and division by 3600 gives m³/s. Wind does not affect ACH or exterior films in this version. The moist-air density approximation and constant specific heat are declared approximations.

### Solar terms

Window gain is incident irradiance × window area in m² × SHGC × shading multiplier. The model projects direct solar radiation onto four cardinal vertical faces and adds isotropic diffuse and ground-reflected contributions. It uses 0.20 ground reflectance, SHGC0.30 and a constant shading multiplier 0.70. Opaque solar gains use a sol-air increment ΔT = absorptance × irradiance / exterior film coefficient. Wall/roof absorptance is 0.50/0.40 and the film coefficient is 20 W/(m²·K). Exterior longwave radiation, dynamic shading, snow albedo, terrain and detailed sky-view factors are absent.

EPW radiation is hourly accumulated Wh/m² over a one-hour interval; its numerical value is used as average W/m² for that interval. This equivalence would need explicit time conversion at a different interval length. Solar position is evaluated at the interval midpoint. The source weather is representative TMY weather, not measurements from the reporting calendar year.

### Sensible and latent loads

\[
H_t=\max(-q_t,0)/1000,\quad C_{s,t}=\max(q_t,0)/1000\quad[\mathrm{kW_{thermal}}].
\]

Humidity ratio w = 0.62198 p_v/(P−p_v) is dimensionless kg water/kg dry air. Outdoor vapor pressure is approximated from dew point; the reference indoor value uses 50% RH at 72°F. The saturation-pressure approximation used is 610.94 exp[17.625T/(T+243.04)] Pa. Its use over the full climate domain is a model assumption, especially for subfreezing conditions.

\[
C_{l,t}=\dot m_t(2{,}501{,}000)\max(w_o-w_i,0)\,\mathbf1(q_t>0)/1000.
\]

The latent heat is J/kg. The result is kW. Using total-air mass flow as a dry-air approximation introduces a small additional approximation. There is no indoor moisture state, occupant latent gain, condensate re-evaporation or standalone dehumidification.

**Identified structural defect:** the indicator turns the entire outdoor moisture load on as soon as q becomes positive. If a size change crosses q = 0 while outdoor moisture exceeds the reference, cooling electricity jumps even though the sensible load changes continuously. This is a shortcut in the physical model, not an interpolation bug. It is preserved and disclosed rather than silently smoothed away. A physical improvement requires a moisture balance and equipment latent-performance model.

### Heat pump and backup

For heating capacity K_t and COP_h,t,

\[
P_{h,t}=\min(H_t,K_t)/COP_{h,t}+\max(H_t-K_t,0)/COP_b.
\]

COP_b = 1. Capacity is zero below −13°F. Otherwise capacity and COP are linearly interpolated against outdoor temperature using the documented generic points. This equipment-curve interpolation is distinct from the house-size interpolation audited below. The coefficients are assumptions, not measured or certified product data.

\[
P_{c,t}=(C_{s,t}+C_{l,t})/COP_{c,t},\quad
E_h=\sum_t P_{h,t}\Delta t,\quad E_c=\sum_t P_{c,t}\Delta t.
\]

Power is kW electric, Δt is hours, and energy is kWh electric. Here Δt = 1 h. Cooling energy assumes all load is met even when the fixed 10.55 kW thermal cooling capacity is exceeded; those hours are flagged. This does not prove comfort can be maintained. Separate fan, duct, cycling, defrost, humidity-dependent capacity and installation effects are absent.

## 3. Exact reduction for the current size problem

For fixed weather, story count and all other prototype assumptions, inserting the geometry above into the hourly balance gives

\[
q_t(A)=a_tA+b_t\sqrt A+c_t.
\]

This is algebraic regrouping, with no parameter fitting. a has units W/ft², b has W/ft, and c has W. The heat-pump COP and capacity depend on outdoor temperature, not area. On any interval of A where all hourly HVAC regimes stay fixed, every hourly electricity expression, and therefore its annual sum, is

\[
E(A)=\alpha A+\beta\sqrt A+\gamma.
\]

To find every regime boundary, let x=√A and solve the quadratic a_tx²+b_tx+c_t=0 for heating/cooling transitions, and a_tx²+b_tx+c_t+1000K_t=0 for heating-capacity transitions. Positive roots whose squared values lie within 750–5000 ft² are retained. Degenerate linear equations are handled separately. Cooling-capacity warning transitions additionally solve q_t(A)+1000ℓ_tA=1000K_c when q_t>0, where ℓ_tA is latent thermal kW.

The compiler starts with the annual coefficients for the first interval, changes only the affected hourly contribution at each boundary, and cumulatively sums those coefficient changes. The calculator uses a binary search to locate the interval, then evaluates three terms for heating, cooling and backup. No synthetic annual observations or fitted regressions are involved. Storage and binary search affect speed, not the underlying equations.

The algebra establishes equivalence on open intervals between exact mathematical boundaries. Floating-point roots, accumulated coefficient sums and evaluations introduce rounding. At an exactly stored breakpoint the compiled implementation chooses the **right-hand limit**. The hourly implementation uses strict q>0 and may take a different latent branch at exact equality. The calculator therefore does not claim bit-for-bit equivalence at every discontinuity. This isolated convention is documented explicitly, and both sides of boundaries are tested. Displayed area accepts hundredths of a square foot; such precision is numerical convenience, not a claim about measured construction dimensions.

The separately derived hourly reduction agreed with the original vector model in 624 city/story/size cases, each with 8,760 hourly evaluations and three electricity components. Maximum hourly component difference was 1.4211×10⁻¹⁴ kWh, against a predeclared tolerance of 10⁻⁸ kWh. The compiled calculator retains 146,605 area intervals across 156 city/story groups. It was independently compared against the original model at 19,344 house sizes, including grid nodes, fresh quarter points, seeded random areas and both sides of selected boundaries. Maximum annual component error was 2.0373×10⁻¹⁰ kWh against a tolerance of 10⁻⁶ kWh; every cooling-capacity exceedance count matched. Evidence is recorded in `deep_research/exact_calculator_validation.json` and `exact_calculator_checks.csv`.

## 4. Interpolation and regression comparison

The protocol was saved before running this expanded benchmark. There are 156 city/story groups, each trained on 18 existing size runs at 750, 1000, …, 5000 ft². Separate models are fitted within each group; these tests do not demonstrate transfer to unobserved cities or climates.

Fresh evaluation uses quarter and three-quarter locations in each 250 ft² interval: 5,304 cases. The 2,652 midpoints examined previously remain a diagnostic set, not a newly blind holdout. Another 5,694 cases stress selected humidity and heating-capacity transitions. None of the evaluated targets is used to fit the four surrogate methods. The selected 0.5% maximum-error target is a numerical design choice, not an industry standard or a confidence interval.

| Method | Fresh MAE (kWh/year) | Fresh RMSE (kWh/year) | Fresh 95th-percentile absolute error | Fresh maximum absolute error |
|---|---:|---:|---:|---:|
| Linear interpolation |1.287|1.866|0.0937%|0.5222%|
| Shape-preserving cubic (PCHIP) |0.392|1.046|0.0278%|0.5382%|
| Tested Matérn 3/2 Gaussian process |0.609|1.302|0.0555%|0.5291%|
| Global geometry-basis least squares |24.182|40.262|1.0643%|5.6215%|

All are compared with the original annual total HVAC-electricity calculation, not a measured building. For the first three methods the worst relative case was San Diego, one story, 2687.5 ft². Linear interpolation's maximum annual dollar error across the fresh cases was $6.14 using state-average prices. The prior midpoint maximum of 0.3657% was correct for that smaller set but did not establish a 0.5% bound over all areas. No tested surrogate met the predeclared target on all fresh cases.

The boundary-stress maximum relative errors were 0.2717% linear,0.2941% PCHIP,0.2956% GP and 3.2362% geometry OLS. These selected boundary cases are not an exhaustive worst-case search.

### Linear interpolation and a conditional error bound

For adjacent nodes A₀,A₁ and w=(A−A₀)/(A₁−A₀), L(A)=(1−w)E(A₀)+wE(A₁). For a twice continuously differentiable function on the entire interval,

\[
|E(A)-L(A)|\le (A_1-A_0)^2\max|E''|/8.
\]

Within one fixed regime E''(A)=−β/(4A^(3/2)). The classical bound does **not** apply across a derivative kink or the humidity jump. It would be incorrect to apply it globally to this prototype and call the result proven. The largest audited one-hour humidity jump was approximately 0.447687 kWh at 4652.0902 ft² in Columbus, one story; the independently predicted jump and direct before/after evaluations agree. This is a numerical-model artifact, not evidence that a real home abruptly consumes that much more electricity after a tiny size change.

### What the regression tests actually did

PCHIP uses shape-preserving cubic Hermite interpolation with weighted harmonic interior slopes and limited endpoint slopes, as documented by [SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html). The implementation was checked on affine and monotone examples. It cannot remove missing physical mechanisms.

OLS fits y=β₀+β₁√(A/2000)+β₂A/2000 by least squares. Although this basis is exact within a regime, one global coefficient set cannot represent all changes of regime across the size range. Its larger error is therefore unsurprising; it is not evidence that all regression methods are poor.

The GP uses centered and standardized training outputs, normalized area, zero mean after centering, and

\[
k(x,x')=\sigma_f^2(1+\sqrt3d/\ell)\exp(-\sqrt3d/\ell),\quad d=|x-x'|.
\]

A discrete grid of 24 length scales and 4 amplitudes is selected by training-only log marginal likelihood; covariance diagonal jitter is 10⁻⁸. It is not an exhaustive optimization over GP models. With K the regularized training covariance, posterior mean and conditional variance are μ*=k*ᵀK⁻¹y and v*=k**−k*ᵀK⁻¹k*, undoing output standardization afterward. See the primary derivation in [Rasmussen and Williams, Chapter 2](https://gaussianprocess.org/gpml/chapters/RW2.pdf).

The nominal 95% GP interval contained 99.17% of fresh quarter-point targets and 94.20% of boundary-stress targets. These are descriptive coverages of deterministic simulator outputs under this test distribution. They are not calibrated 95% real-house confidence intervals; hyperparameter uncertainty, weather uncertainty, parameter error and model discrepancy are not included.

If “ISE” means integrated squared error, ISE=∫[Ê(A)−E(A)]²dA is an evaluation criterion, not a predictor. An area weighting or input probability distribution must be specified. This report uses explicitly defined pointwise metrics instead of claiming to have calculated a continuous ISE. If another algorithm was intended, that term has not been silently reinterpreted as a particular method.

## 5. Bills require the full load profile

For interval electricity e_t, power P_t=e_t/Δt, monthly fixed charge F_m, and tariff rules T,

\[
B_T(e)=\sum_m[F_m+\sum_{t\in m}p_te_t+D_m(P)+R_m(e)-C_m(e)].
\]

R includes applicable riders and C includes credits; tiered rates require splitting consumption by the tariff's tier thresholds rather than multiplying all kWh by the final tier's price. The delivered sample-plan implementation handles the documented subset of tariff features, not every tariff appearing in the national database. Eligibility, taxes, unpriced items and date assumptions remain in the tariff audit.

With base load b and HVAC load h, the incremental HVAC bill is

\[
\Delta B_{HVAC}=B_T(b+h)-B_T(b).
\]

In general this is not B_T(h), because demand, tiers and credits depend on total household consumption. Fixed charges cancel only when both cases remain on the same account, plan and service arrangement. The invented base-load profiles are billing scenarios; they are not measured households and are not coupled back into internal heat gains.

For the audited APS on-peak demand formulation,

\[
D_m=d_m\max_{t\in\mathcal P_m}P_t.
\]

For the audited SRP daily-peak-average formulation,

\[
D_m=d_m\frac1{N_m}\sum_{d\in\mathcal D_m}\max_{t\in\mathcal P_{m,d}}P_t.
\]

The sets include only tariff-eligible on-peak intervals and eligible days. Weekend, holiday, season and clock rules must be applied before evaluating the maximum. These formulas apply to the identified plans in the package, not universally to each utility. The corresponding official schedules are [APS R-3](https://www.aps.com/-/media/APS/APSCOM-PDFs/Utility/Regulatory-and-Legal/Regulatory-Plan-Details-Tariffs/Residential/Service-Plans/Time-of-Use4pm-7pmWithDemandChargeR-3.pdf) and [SRP E-16](https://www.srpnet.com/v3/assets/bltefc1fc708dcc94e7/blt3bc0beaf4fade7d9/2025-Ratebook-E-16-with-TCA-and-Export-Rate.pdf). Effective dates and scope are retained in `Tariff components`.

Reducing one 5 kW peak to 3 kW saves only 1 kW of billed maximum when another 4 kW peak remains. This counterexample is independently tested. For PCM, calculate both complete load profiles and rerun the bill; do not multiply a guessed peak reduction by the demand price.

Hourly data can evaluate the modeled 60-minute demand interval. It cannot substantiate 15-minute peaks or a rolling interval offset from the stored hours. EPW standard-time intervals are mapped to the stated 2026 civil billing calendar; DST and holiday cases are tested. Calendar months approximate billing cycles. Applying a current tariff schedule to TMY weather is a hypothetical annualization, not reconstruction of an actual historic bill. A TMY composite's weather/calendar pairing also does not establish the distribution of future coincident peaks.

The [EIA state-price source](https://www.eia.gov/electricity/annual/html/epa_02_10.html) is a revenue-per-kWh average. In the national screen C=p_stateE is an explicit proxy, not an exact marginal tariff. The 9 sample plans and 120 scenarios must not be extrapolated to all 78 cities. Older URDB entries remain unverified until checked against effective official schedules and address eligibility.

## 6. Equations required to answer the PCM challenge

The current model has no state variable for stored heat, so it cannot answer whether PCM shifts load, cycles completely, or beats insulation on lifetime cost. Adding an assumed savings percentage or regressing the baseline cannot supply the missing mechanism.

For a conducting PCM layer, a representative conservation equation is

\[
\rho\frac{\partial h(T,\xi)}{\partial t}=\nabla\cdot(k\nabla T)+\dot q_v,\qquad
h(T,\xi)=\int c_p(T)\,dT+L\xi.
\]

h is J/kg, density kg/m³, conductivity W/(m·K), latent heat L J/kg, melt fraction ξ dimensionless and volumetric source W/m³. Both sides are W/m³. ξ may depend on thermal history: melting/freezing curves and hysteresis must be represented if material data justify them. Contact resistance, encapsulation, thickness and placement set the actual wall heat flux. The [EnergyPlus CondFD engineering documentation](https://bigladdersoftware.com/epx/docs/9-3/engineering-reference/conduction-finite-difference-solution.html) describes an enthalpy-based finite-difference route; this linked reference is explicitly version 9.3, and is methodological context, not a claim that this package ran that solver.

A zone energy state and moisture state must be coupled to the wall and equipment. For a simplified zone, C_z dT_z/dt=ΣQ_surface+Q_air+Q_internal+Q_HVAC. A moisture balance tracks supply, infiltration, occupants and condensate. Controller setpoints, deadband, preconditioning schedule and equipment limits determine the time path. Equal nominal thermostat settings do not establish equal comfort if capacity or humidity constraints are violated.

At periodic steady state, ΔU_storage over a completed cycle is zero. PCM shifts the timing of heat transfer; it is not a net source of energy. Incomplete overnight solidification can reduce available capacity the next day. Simulations must include adequate warm-up and verify storage-state closure, rather than obtaining an apparent benefit by ending the year with a different stored-energy inventory.

### A defensible necessary screen for price arbitrage

Suppose Q thermal kWh is charged using equipment with COP_ch at electricity price p_ch, a fraction η is usefully delivered later, and that delivery displaces equipment with COP_dis at price p_dis. Ignoring demand charges, the gross electric-bill benefit is

\[
S=\eta Q\,p_{dis}/COP_{dis}-Q\,p_{ch}/COP_{ch}-C_{aux}.
\]

A positive value is necessary for this simplified active-shifting mechanism to save operating cost; it is not sufficient for lifecycle benefit. With equal COP, no auxiliary cost and η<1, the price ratio must exceed 1/η. Passive cooling can have a different charging mechanism, but heat rejection, cycling and comfort must still be demonstrated. Thermal kWh and electric kWh must never be equated without efficiency conversion. Demand-charge benefits require the full billing calculation above.

Usable ideal latent capacity is mL/3.6×10⁶ in kWh thermal when L is J/kg. Actual useful capacity also depends on achievable melt fraction, temperature range and heat-transfer rate. Quoted storage over a temperature range can include sensible energy; do not label it all latent heat. The RT25HC source's 230 kJ/kg and 58 Wh/kg values are inconsistent because 230/3.6 ≈ 63.89 Wh/kg. That source conflict remains unresolved and cannot support a precise break-even claim.

### Fair economic comparison

Compare baseline, additional conventional insulation, PCM added to the same assembly, and relevant combined options at the same required comfort and service life. If selecting designs, compare optimized feasible alternatives under the same constraints; a poorly chosen insulation thickness is not a fair benchmark. Record installed material, labor, finishing, permitting, replacement, degradation, maintenance and salvage separately. Historical illustrative costs are not current local installed quotes.

\[
LCC_j=C_{0,j}+\sum_{y=1}^{N}\frac{B_{j,y}+M_{j,y}+R_{j,y}}{(1+r)^y}-\frac{V_{j,N}}{(1+r)^N}.
\]

r and cash flows must both be real or both nominal. Residual value V and replacement costs R must use the same analysis horizon. PCM wins over additional insulation only if ΔLCC=LCC_PCM−LCC_insulation<0 while comfort and other constraints are satisfied. For constant annual net savings S and added initial cost ΔC₀, the simplified break-even condition is ΔC₀ < S[1−(1+r)^(−N)]/r, with NS as the r=0 limit. This annuity identity was checked against an independent 20-year finite sum. It is a mathematical identity, not a source for choosing a discount rate or equipment lifetime.

## 7. Verification results, uncertainty and limits

Eighteen independent cases pass: conduction heating/cooling; constant-COP electricity; zero-load equilibrium; resistance backup; PCHIP affine/monotone behavior; the two demand rules; an off-peak spike; fixed-charge cancellation; baseline-credit saturation; spring/fall DST and Arizona timing; a competing-demand-peak counterexample; and discounted-cash-flow identity. Test tolerances and residuals are retained in `independent_equation_tests.csv`. Earlier weather-integrity, formula, monthly/annual and tariff-adjustor checks remain in the package.

The delivered HTML was also tested in installed Google Chrome using a local file URL. Its JavaScript calculations matched 624 independent Python reference cases within 1.8918×10⁻¹⁰ kWh per annual component. City, fractional area, story count, invalid and blank areas, and restoring the default all passed. The mobile view had no horizontal overflow at 390 pixels; desktop and mobile screenshots were visually reviewed. The 12-sheet workbook was recalculated and its affected views reviewed; exported formulas and cached results were checked, but native Microsoft Excel recalculation was not tested. These interface checks do not add physical validation.

Agreement with a second implementation does not independently validate shared weather data, constants or solar geometry. For example, the reduced model and original model share the weather preparation and solar-position calculation. Numerical tests of an annual steady-state model also do not establish time-step convergence of a future transient PCM model.

The error categories must remain separate:

| Error or uncertainty | Present evidence | What remains |
|---|---|---|
| Arithmetic / annual aggregation | Independent synthetic cases and hourly/monthly reconciliation | Broader independent reference cases |
| House-size approximation | Explicit holdout and boundary tests; direct alternative delivered | No claim of real-house accuracy |
| Weather and solar inputs | Archived 78 representative years; record checks | Measured multi-year variation, extremes, station representativeness and future climate |
| Envelope / occupancy / infiltration | Explicit assumptions and 102 one-input sensitivity runs | Measured parameter distributions and interactions |
| Heat-pump performance | Explicit generic curve and capacity logic | Product-specific capacity, COP, defrost, cycling, latent and installation data |
| Tariff / base load | Official sample-plan details and synthetic billing tests | Address eligibility, interval bills, all riders/taxes and future rate paths |
| Structural building model | Identified omitted storage and moisture dynamics | Transient validated simulation and measurement comparison |
| PCM and installed costs | Source audit; unresolved material-unit discrepancy flagged | Material enthalpy/hysteresis/cycling tests and current installation quotes |

It would be invalid to add surrogate RMSE to unmeasured structural uncertainty and report a comprehensive confidence interval. If independent error bounds ε_i and ε_j on two cost estimates were available, a sufficient ordering condition would be Ĉ_i+ε_i<Ĉ_j−ε_j. Such comprehensive bounds are not currently available. Close city ranks therefore remain conditional.

For future uncertainty analysis, use paired scenarios: apply the same sampled uncertain house/equipment assumptions and consistent weather-year pairing to each candidate so comparisons do not confuse different houses. Input distributions and correlations require evidence; invented uniform ranges yield scenario sensitivity, not measured probabilities. Report the distribution of pairwise cost differences and the probability PCM beats insulation only after the probability model is justified.

## 8. Evidence gates before a PCM conclusion

1. Acquire product-specific heat-pump and PCM properties with unit-consistent provenance. Resolve the material storage discrepancy. Obtain comparable current installation quotes.
2. Build a dynamic baseline and test appropriate building-simulation reference cases. Check zone energy/moisture balance, equipment capacity and comfort. An established simulator still requires correct inputs and suitable validation.
3. Add PCM enthalpy and history dependence. Verify zero-latent-heat, no-PCM, constant-temperature, known conduction and completed-cycle limits. Check energy balance with the stored-energy change included.
4. Establish temporal and spatial convergence. Refine time steps and layer meshes until changes in annual bills, monthly demand and unmet comfort are below predeclared decision-relevant tolerances. Annual energy convergence alone does not certify peak demand. Resolve the utility's actual meter interval.
5. Validate separately against independent measurements; reserve data that were not used for calibration. Quantify residual bias and error across seasons, climates and operating regimes. A favorable annual total can hide compensating seasonal errors.
6. Run paired baseline/insulation/PCM scenarios over multiple weather years, full tariffs and lifetime assumptions. Demonstrate favorable incremental lifecycle cost with uncertainty small enough to support the decision.
7. Only if these dynamic runs become expensive, train a surrogate on designed simulations spanning climate, geometry, envelope, equipment, PCM amount/melt range and controls. Benchmark simple regressions and GPs with grouped held-out cities/weather years and boundary regimes. Choose on out-of-sample bill and decision errors, not model sophistication. Keep tariffs deterministic and separately auditable.

These gates identify missing evidence rather than replacing it with fabricated measurements. They are the conditions under which a future PCM-saving result can be defended.

## 9. Reproducibility and file map

- `House_energy_calculator.html`: self-contained offline direct size calculator; same prototype assumptions and state-price proxy.
- `US_home_energy_comparison.xlsx`: 12-sheet data and scenario workbook; existing approximate size selector retained and labeled.
- `deep_research/validation_protocol.json`: benchmark design recorded before the expanded run.
- `deep_research/surrogate_predictions.csv` and `surrogate_summary.csv`: every evaluated surrogate prediction and grouped metrics, including failed target results.
- `deep_research/mathematical_validation.json`: independent tests, hourly-equivalence results, versions, timing and SHA-256 hashes of calculation inputs/code.
- `deep_research/exact_calculator_validation.json`, `exact_calculator_checks.csv`: compiled-calculator checks by city and story count.
- `deep_research/claim_evidence.csv`: claim-by-claim evidence and unresolved gaps.
- `DEEP_RESEARCH_REVIEW.md` and `deep_research/variable_audit.csv`: source/tariff/material audit and 134-variable inventory.

The original model, tariff engine, compiler, tests, raw weather, data and reports are included in `v1_steady_state_results/US_home_energy_data.zip` (v1). Benchmark outputs describe this revision. Changing the physical assumptions requires recompilation and new checks; editing a report or a displayed number alone does not update the calculator.
