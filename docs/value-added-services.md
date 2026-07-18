# Value-Added Services — External Data Integration

Five services enabled by combining smart meter data with outside temperature and occupancy detection.

---

## 1. Heating Efficiency Scoring

Compare gas consumption against outside temperature (degree-days). Flag days where gas usage is anomalously high for the temperature — a sign of poor insulation, a faulty boiler, or a door/window left open. Benchmark each home against similar-weather peers.

## 2. Vacancy-Aware Anomaly Suppression

Occupancy detection (PIR, phone presence, or calendar integration) removes false positives from the flat-line and spike detectors. A flat-line during a two-week holiday is expected; one during a normal week is a fault. Occupancy context separates the two and dramatically improves alert signal-to-noise.

## 3. Heating Pre-Warm Optimisation

Correlate occupancy arrival time with outside temperature to recommend the optimal boiler start time. Colder weather needs an earlier start; mild weather needs less lead time. Delivered as a daily push notification: "Turn heating on at 6:45 today."

## 4. Standby and Phantom Load Detection

When occupancy sensors confirm the property is empty, any sustained non-zero electricity consumption is standby or forgotten-on appliances. Quantify and benchmark against similar unoccupied periods to surface devices worth replacing or switching off at the wall.

## 5. Comfort vs Cost Trade-Off Reporting

Combine temperature (indoor from a smart thermostat, outdoor from a weather API) with occupancy hours to produce a weekly "comfort score" — how warm the home was when people were actually in it — against energy spend. Lets consumers see whether their heating schedule is efficient or heating an empty home.

## 6. Battery Size Optimisation

Using half-hourly consumption data combined with time-of-use tariff rates, determine what battery capacity gives a reasonable payback period. The analysis models how much cheap-rate electricity a battery of a given size could store and discharge during peak-rate periods, calculates the daily saving, and projects the break-even point against typical installed costs. For meters with solar production data, the model also accounts for self-consumption — storing surplus generation rather than exporting it at a lower rate.

## 7. Appliance Load Disaggregation

Half-hourly electricity data contains characteristic consumption signatures for high-draw appliances (washing machines, dishwashers, EV chargers, immersion heaters). Pattern-matching against known signatures can identify which appliances ran and when — without any additional hardware. Combined with ToU tariff data, this surfaces which appliances are running at expensive times and quantifies the saving from shifting them to off-peak slots.

## 8. Carbon-Aware Demand Shifting

National Grid ESO publishes half-hourly carbon intensity forecasts for the next 48 hours. Overlaying these against a household's flexible loads (identified from disaggregation above, or from EV/battery schedules) enables a "run this now vs. later" recommendation that optimises simultaneously for cost and carbon. Particularly powerful for EV charging and battery charge cycles.

## 9. Micro-Leak and Frost Detection

A sustained low-level non-zero gas reading during confirmed vacant/overnight periods — too small to be a boiler cycle but persistent across multiple half-hours — is a signature of a slow gas leak, a pilot light, or a dripping hot tap keeping the cylinder topped up. Combined with an outdoor temperature sensor, the same logic flags frost-risk nights where the heating hasn't fired as expected, enabling a pre-emptive alert before pipes freeze.

## 10. Thermal Mass / Insulation Decay Profiling

After heating turns off (identifiable from the gas half-hourly drop to zero), track how quickly indoor temperature falls relative to outdoor temperature. The rate of decay is a direct measure of the building's thermal mass and insulation quality. Tracked over months and across weather conditions, this produces a "heat retention score" that degrades measurably if insulation settles, a window seal fails, or a loft hatch is left open — and benchmarks the home before and after retrofit work.

### 10a. EPC Enhancement — Measured vs Modelled Performance Gap

Current EPCs are based on SAP (Standard Assessment Procedure) — a modelled estimate from construction type, not actual behaviour. The heat decay rate from service #10 gives a *measured* fabric heat loss coefficient (HLC) for that specific property. Comparing measured HLC against the SAP-predicted value quantifies the performance gap — many homes perform 30–50% worse than their EPC implies. This is actionable intelligence for both occupants and policymakers.

### 10b. EPC Enhancement — Continuous / Dynamic EPC

A traditional EPC is a snapshot valid for 10 years. Continuous monitoring of heat retention produces a rolling, evidence-based efficiency score that updates automatically — degrading when insulation settles or a seal fails, improving after retrofit. This is a "living EPC" rather than a decaying paper certificate.

### 10c. EPC Enhancement — Retrofit Impact Verification

Before/after measurements of the heat decay rate provide objective evidence that insulation, window, or heat pump retrofits delivered their claimed improvement. Currently retrofit schemes (ECO4, Great British Insulation Scheme) rely on modelled predictions. Measured before/after HLC makes verification independent and auditable — valuable for both grant compliance and consumer trust.

### 10d. EPC Enhancement — Green Mortgage and Valuation Support

Lenders offering green mortgages at preferential rates for high EPC properties currently rely on the certificate alone. A measured performance profile provides stronger evidence of genuine efficiency — and could challenge a fraudulently inflated or simply inaccurate EPC rating.

### 10e. EPC Enhancement — National Housing Stock Carbon Accuracy

EPCs feed into national carbon accounting for the housing sector. Measured HLC data at scale would significantly improve the accuracy of those estimates, which currently inherit all the errors in SAP modelling assumptions.

> **Biggest near-term opportunity: Retrofit Verification** — there is a direct funding trail (ECO4 grants, boiler upgrade scheme) where independently measured proof of improvement has real financial value to installers, lenders, and regulators.

## 11. Degree-Day Budget Forecasting

Combine the historical relationship between this property's gas consumption and heating degree-days (established from service #1) with a 14-day weather forecast to produce a rolling energy spend prediction. Alert the consumer when the forecast implies they will exceed a monthly budget before the month ends — with enough lead time to adjust behaviour (turn the thermostat down 1°C, delay the immersion heater cycle) rather than discovering the overspend on the bill.

## 12. Boiler Efficiency Trending

At a given outdoor temperature, the gas consumed to reach and maintain a target indoor temperature should be consistent. By holding outdoor temperature constant (using degree-day normalisation) and tracking gas consumption over weeks and months, gradual boiler efficiency degradation becomes visible long before it causes a breakdown — a 10–15% rise in normalised consumption is a reliable early warning that the boiler needs a service. Removes the seasonal confound that otherwise masks the signal.

## 13. Heat Pump Suitability Scoring

Using the existing gas consumption profile normalised against outdoor temperature, model what the same heating demand would cost on a heat pump at the property's current electricity tariff. The coefficient of performance (COP) of a heat pump varies with outdoor temperature — colder days yield lower COP. By applying a temperature-dependent COP curve to each half-hour of historical gas demand, produce a realistic annual cost comparison and payback estimate for a heat pump retrofit, specific to this household's actual usage pattern and tariff.

## 14. Smart Tariff Matching

Combine the household's half-hourly electricity consumption shape with outdoor temperature (as a proxy for heating demand seasonality) to score every available market tariff against actual usage. A household with heavy overnight consumption in winter scores very differently on an Agile tariff versus a two-rate Economy 7 versus a flat rate. Produces a ranked list of tariffs with projected annual saving versus current, updated whenever the consumption profile or available tariffs change.

## 15. Condensation and Mould Risk Scoring

Combine indoor temperature, indoor humidity, and outdoor temperature to continuously calculate the dew point relative to surface temperatures (which can be estimated from the indoor/outdoor differential and the insulation score from service #10). When surface temperatures approach dew point — typically on cold external walls in poorly ventilated rooms — flag condensation risk before visible mould develops. Correlate with heating patterns to identify whether longer or lower heating runs would reduce risk more cost-effectively than higher peak temperatures.

## 16. Ventilation Efficiency and Air Quality Optimisation

Indoor humidity rising faster than outdoor humidity during occupied periods is a signature of insufficient ventilation relative to occupancy load (cooking, showering, breathing). By tracking the rate of indoor humidity rise against occupancy signals and outdoor conditions, quantify how much ventilation is needed and when. In homes with MVHR (mechanical ventilation with heat recovery), correlate fan speed and runtime with the humidity delta to score ventilation efficiency and detect filter degradation.

## 17. Illness and Comfort Environment Monitoring

Public health research links sustained indoor temperatures below 18°C and relative humidity outside 40–60% to increased respiratory illness risk, particularly for elderly occupants. Using the half-hourly temperature and humidity streams, produce a weekly "healthy home score" tracking how many occupied hours fell within the WHO-recommended comfort envelope — and at what energy cost. Flags periods where the home was unhealthily cold or humid despite heating being on, pointing to distribution problems (e.g. a radiator off in a bedroom) rather than a generation problem.

---

## Sensor Data Sources

### Water
- **Flow meter / pulse counter** on the mains supply — detect leaks, quantify hot water usage separately from space heating, track daily consumption trends
- **Hot water cylinder temperature sensor** — confirm legionella-safe temperatures are reached, detect immersion heater faults, optimise heat-up timing

### Air Quality
- **CO₂ sensor** — occupancy proxy without privacy concerns (CO₂ rises when people are present), ventilation trigger, correlates with productivity/sleep quality research
- **VOC / particulate sensor** — cooking and cleaning event detection, air quality scoring, correlates with ventilation adequacy from service #16
- **CO detector** (beyond safety role) — quantify incomplete combustion events from the boiler, early warning of burner degradation before efficiency loss shows in gas data

### Electrical
- **Clamp-on CT sensors** per circuit — true appliance disaggregation at circuit level (rather than inferred from half-hourly totals), identifies EV charger, immersion, cooker individually
- **Smart plug energy monitors** — appliance-level consumption and runtime for high-draw devices

### Structural / Environmental
- **Door/window contact sensors** — heat loss events (window left open during heating), security correlation, occupancy refinement
- **Pipe temperature sensors** — detect when radiators aren't heating (balancing issues, TRV faults), confirm boiler flow/return delta T for efficiency scoring
- **Loft/cavity temperature sensor** — quantify insulation effectiveness directly, seasonal comparison

### Behavioural
- **Smart doorbell / presence detection** — ground-truth occupancy for all occupancy-dependent services (#2, #3, #4, #5)
- **Smart thermostat setpoint data** — separates "occupant chose to be cold" from "heating failed to reach setpoint", critical for comfort vs fault distinction

### Recommended Priority
**CO₂ sensor** — gives occupancy without cameras or phones, improves six of the existing seventeen services, and costs under £50.

---

## Recommended Starting Point

**#2 Vacancy-aware anomaly suppression** — occupancy context directly improves the existing anomaly detector, reducing alert fatigue before adding new features on top.
