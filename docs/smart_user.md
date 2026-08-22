# Smart Meter Home Energy — User Guide

This app analyses your smart meter data to help you spend less on energy, keep your home comfortable, and make informed decisions about upgrades. Features unlock progressively depending on what data you share.

---

## What you need to get started

| Level | What to provide | Features unlocked |
|---|---|---|
| Basic | Smart meter (electricity or gas) | Features 1–4 |
| + Weather | Your postcode | Features 5–10 |
| + Occupancy | A presence signal (phone, CO₂ sensor, or calendar) | Features 11–12 |
| + Indoor sensor | A small temperature sensor in your living room | Features 13–14 |

All analysis works from the half-hourly readings your smart meter already records. You simply grant consent for the app to read them.

---

## Feature 1 — Find a cheaper tariff

The app calculates what you would have paid on every available electricity tariff, using your actual usage history — not an estimate. It ranks tariffs by projected annual saving and explains why each one suits (or doesn't suit) your household.

**What you see:** a ranked list of tariffs, your estimated annual saving on each, and a plain-English explanation (e.g. "You use a lot of electricity overnight, which makes Economy 7 worth considering").

**What to do with it:** if a tariff shows a saving that holds up even if your usage changes by 10%, the app marks it as a stable recommendation. Unstable rankings (where two tariffs are very close) are flagged so you don't switch for a marginal gain.

**Needs:** 8 weeks of smart meter data for a reliable result; 4 weeks gives an indicative result with a caveat.

---

## Feature 2 — Find the right battery size

If you're considering a home battery, the app simulates every common battery size against your actual usage and your tariff, then plots the annual saving against the upfront cost for each size.

**What you see:** a payback curve showing how many years each battery size would take to pay for itself, plus a 10-year financial return. The app highlights the size with the shortest payback and the size with the best long-term return — these are often different, and both are shown so you can make the call.

If you have solar panels, the app factors in your export data to make the numbers more accurate.

**What to do with it:** take the recommended size and payback period to installer quotes as a reference point.

**Needs:** 8 weeks of data; 52 weeks gives the most accurate seasonal picture.

---

## Feature 3 — See which appliances are using the most electricity

By comparing your half-hourly readings against your typical background usage, the app identifies the electrical signature of large appliances — EV charger, immersion heater, washing machine, dishwasher, electric oven, and heat pump — and builds up a picture of which ones are in your home and how often they run.

**What you see:** a list of likely appliances with a confidence rating, how many times each was detected, and — for appliances that could be shifted to a cheaper time of day — how much you could save annually by running them off-peak.

**What to do with it:** if your EV charger is running at peak-rate periods and you're on a time-of-use tariff, shifting it overnight could save over £100/year. The app calculates the exact figure for your tariff.

**Needs:** 8 weeks of data; smaller appliances (microwave, kettle) are below the resolution of smart meter data and won't appear.

---

## Feature 4 — Find out if a heat pump makes financial sense for you

The app uses your gas consumption history and local weather data to estimate how much of your gas bill is space heating (as opposed to hot water and cooking), then models what that heating would cost if you switched to an air-source heat pump.

**What you see:**
- Your current annual heating cost in gas
- The estimated annual cost on a heat pump, shown as a range (better case: underfloor heating / larger radiators; worse case: standard UK radiators)
- The payback period after the £7,500 Boiler Upgrade Scheme grant
- A simple checklist of whether your home is a good candidate

**The key number to understand:** the break-even COP. At current UK energy prices (electricity around 24p/kWh, gas around 6p/kWh), a heat pump needs to deliver 4 units of heat per unit of electricity to match gas on running costs. Modern heat pumps typically achieve 2.5–3.5 in UK conditions, which means running costs depend strongly on your tariff. The app shows this clearly.

**Needs:** 12 months of gas data, ideally 24 months.

---

## Feature 5 — Early warning if your boiler is losing efficiency

As a boiler ages or develops scale, it consumes more gas per unit of heating demand. The app tracks your gas usage per degree of outdoor coldness (a "heating degree day") over time and alerts you if it rises by 15% or more above your historical baseline — before the boiler breaks down.

**What you see:** a trend chart of normalised gas efficiency over the heating season, and an alert if the trend is heading the wrong way. The app also distinguishes between a gradual decline (normal wear) and a sudden step change (possible fault event), so the alert message gives you the right guidance.

**What to do with it:** if you get a gradual-trend alert, book a boiler service. If you get a step-change alert, call an engineer sooner.

**Needs:** two full heating seasons (October–April). The first season builds the baseline; the second is where comparison begins.

---

## Feature 6 — Daily heating efficiency score and peer comparison

Each heating day, the app compares your actual gas use against what your home would be expected to use for that outdoor temperature. Days where you used significantly more than expected are flagged.

**What you see:** a score for each day (100 = exactly as expected; higher = over-consuming for the conditions), anomalous days highlighted, and a benchmark showing how your home compares against similar properties (by type and build era) from national data.

**What to do with it:** if anomalous days cluster around windy weather, the likely cause is draughts. If they appear randomly, occupancy changes (guests, working from home) are the most common explanation and no action is needed.

**Needs:** one heating season.

---

## Feature 7 — Monthly energy budget forecast

At any point during a month, the app uses the 14-day weather forecast and your home's historical gas-per-degree relationship to project what you're likely to spend on gas by the end of the month.

**What you see:** a projected month-end gas cost with a range (warmer-than-forecast vs colder-than-forecast), compared against a budget you set. If you're on track to exceed your budget, the app tells you by how much and suggests the thermostat reduction (in degrees Celsius) that would close the gap.

**What to do with it:** useful for budgeting and for households on prepayment meters.

**Needs:** one heating season to calibrate the model; the weather forecast is free and automatic.

---

## Feature 8 — Run appliances at the greenest (and cheapest) time of day

Using the National Grid's half-hourly carbon intensity forecast for your region, the app recommends the best time to run each of your large flexible appliances — dishwasher, washing machine, EV charger — to minimise your carbon footprint.

**What you see:** for each detected appliance, a recommended run window for today, the carbon saving versus running it at its typical time, and — if you're on a time-of-use tariff — whether the lowest-carbon window is also the cheapest (they often coincide overnight, but not always).

**What to do with it:** for EV charging, the app schedules by how much charge you need and your departure time, so you don't have to work it out manually.

**Needs:** Feature 3 must have detected your appliances first (at least 4 weeks of data).

---

## Feature 9 — Optimal boiler start time each morning

Without a smart thermostat, most boiler timers run on a fixed schedule that ignores outdoor temperature. On mild mornings, this wastes gas heating the house earlier than needed. On very cold mornings, it starts too late.

The app learns from your boiler's actual behaviour over a heating season — when it typically fires relative to the overnight temperature — and uses the morning forecast to recommend a start time each day.

**What you see:** a daily recommended start time ("Turn your heating on at 06:30 today — 3°C forecast"), personalised to your home's warm-up characteristics, not a generic rule.

**Note:** if you already have a Hive, Nest, or Tado thermostat, the app will detect this from your gas pattern and suppress this feature — your thermostat is already doing it.

**Needs:** one heating season (approximately 40 boiler-start observations).

---

## Feature 10 — Gas leak detection and frost alerts

**Micro-leak detection:** the app establishes your home's normal overnight gas consumption in summer, when no space heating is running. If overnight gas readings in winter are consistently well above that baseline for 3 or more hours, it flags a possible issue — slow gas leak, continuously running pilot light, hot water cylinder heat loss, or a boiler fault.

**Frost alerts — vacant property:** if the app hasn't seen any heating activity for 12 hours and the overnight forecast drops below 2°C, it sends a frost alert. Below -3°C, the alert is marked critical (pipe burst risk within hours).

**Frost alerts — heating failure:** if the boiler should be running based on outdoor temperature and time of day, but no gas activity is detected and frost is forecast, the app flags a likely boiler fault before you come home to a cold house.

**Needs:** micro-leak detection needs 3 summer months to build the overnight baseline. Frost detection works from day one.

---

## Feature 11 — Smarter alerts when you're away from home

Without occupancy context, energy anomaly detectors generate false alarms: a flat-line gas reading on a two-week holiday looks like a fault. Conversely, unusual activity in an empty home is more alarming than the same reading when you're in.

Feature 11 connects your occupancy signal (phone presence, CO₂ sensor, or a holiday calendar entry) to the anomaly detector, so:
- Flat-line readings while you're away are silently suppressed
- Unexpected activity (gas or electricity spike) in an empty home triggers a high-priority alert
- Unexplained flat-lines while you're home are flagged immediately

**What to do with it:** declare holidays in the app's calendar, or connect your phone's home Wi-Fi presence, to get the most accurate alert filtering.

---

## Feature 12 — Phantom load and standby waste detection

When your home is confirmed empty, any electricity you're using is either unavoidable always-on load (fridge, router, alarm) or phantom load — TVs on standby, forgotten phone chargers, appliances left on.

The app measures your typical empty-home electricity use, separates the unavoidable floor from the avoidable phantom load, puts a pound figure on it annually, and benchmarks it against similar homes.

**What you see:** your estimated annual phantom load cost, a percentile rank against similar properties ("73% of similar homes have a lower standby load"), and an alert if your phantom load jumps — indicating something new has been left plugged in.

**Needs:** at least 24 confirmed hours of vacancy (from your occupancy signal) to build the baseline.

---

## Feature 13 — How well does your home hold heat?

This feature uses an indoor temperature sensor to measure how quickly your home cools down when the heating is off. From repeated overnight cooling events, the app calculates your home's thermal time constant — a single number that captures how well your insulation and thermal mass retain heat.

A higher time constant means better heat retention. The app translates this into a heat loss coefficient (W/K) — the rate at which your home loses heat for every degree of indoor-outdoor temperature difference.

**Sub-features unlocked alongside this:**

**13a — EPC performance gap:** compares your measured heat loss against what your Energy Performance Certificate predicts. UK research consistently finds that older properties lose 30–50% more heat than their EPC suggests. The app puts a pound figure on this gap — the extra annual heating cost from the shortfall.

**13b — Living EPC:** your EPC band, updated monthly from real measurement rather than a one-off assessment that may be years old. If your band improves after a retrofit, you see it immediately.

**13c — Retrofit verification:** if you install insulation, new windows, or any other fabric upgrade, the app compares your heat loss before and after (with a 6-week settling period) and tells you whether the improvement matches what the installer claimed, with statistical confidence.

**13d — Green mortgage evidence:** generates a structured evidence package summarising your measured fabric performance, suitable as supporting documentation for green mortgage applications or remortgaging where the EPC band affects your rate.

**13e — National data contribution:** with your consent, your anonymised measurement contributes to a national dataset that helps improve UK carbon accounting for the housing sector. No individual home is identifiable.

**Needs:** Feature 13 requires a heating season (October–April) to accumulate enough overnight cooling events — typically 10–20. Feature 14 (below) delivers value from week one while you wait.

---

## Feature 14 — Comfort vs cost report

Each week, the app combines your indoor temperature readings with your energy costs and occupancy data to answer a simple question: are you paying for warmth when it matters, and is energy being wasted when it doesn't?

**What you see:**
- The percentage of occupied time your home was within the comfortable temperature range (18–22°C)
- The proportion of your weekly energy spend that occurred while the home was empty
- A four-quadrant summary: are you efficient and comfortable, comfortable but expensive, under-heated, or paying a lot for too little warmth?
- A health alert if indoor temperature fell below 16°C while the home was occupied

**What to do with it:** the most common finding is that 20–35% of heating cost occurs in an empty home. The app estimates what a tighter schedule would save annually.

**Needs:** works from the first week of indoor sensor data.

---

## Privacy

- Smart meter data is accessed only with your explicit consent via the smart meter consent process.
- Occupancy data (Feature 11/12) requires a separate opt-in. Raw occupancy labels are never shared.
- Retrofit and EPC data contributed to national analysis (Feature 13e) is anonymised — no segment containing fewer than 10 households is ever reported.
- Your tariff comparison results are valid only at the rates current when calculated. The app re-runs the comparison automatically when tariff rates change.

---

## Technical Reference

This section describes the underlying methods for each feature at an engineering level. Each entry covers the core algorithm, an honest assessment of its accuracy and reliability in practice, and directions for future improvement.

---

### Feature 1 — Tariff Matching

**Method:** The algorithm maps every historical half-hourly meter reading to the rate it would attract under each candidate tariff, then sums to produce an annualised cost. For flat and two-rate tariffs this is a direct lookup; for time-of-use tariffs it requires a rate band table; for Agile-style tariffs it replays actual published half-hourly prices from the tariff's historical rate archive. A consumption shape profile (night fraction, evening peak fraction, weekend ratio) is calculated alongside to explain the ranking. A ±10% perturbation test checks whether the top-ranked tariff is sensitive to small changes in usage — if the ranking flips, it is flagged as unstable.

**Accuracy and reliability:** For flat and two-rate tariffs the cost calculation is exact given correct tariff data. For Agile tariffs it is retrospective — it models what the household *would* have paid, not what they *would have done* if they had shifted demand. This understates the Agile benefit for flexible households and overstates it for inflexible ones. Accuracy also degrades for households with strong seasonal variation when fewer than 26 weeks of data are available, because the sample may miss peak consumption periods. Tariff data must be kept current; stale rates silently invalidate the ranking.

**Future work:** Incorporating a demand-flexibility model (drawing on appliance detection from Feature 3) would give a more realistic Agile cost estimate for households that can shift loads. Machine learning on a large consented dataset could learn household flexibility from historical patterns without requiring manual input. Integration with a live tariff database (e.g. Ofgem's registered tariff feed) would eliminate the data-freshness problem.

---

### Feature 2 — Battery Size Optimisation

**Method:** A deterministic simulation steps through every half-hourly period in the historical dataset, applying a rule-based dispatch strategy: charge from the grid during cheap-rate periods up to the battery's capacity and charge-rate limits; discharge into the home load during expensive periods up to the discharge-rate limit. The simulation tracks state of charge (SoC) with explicit efficiency losses (96% charge, 96% discharge, giving ~92% round-trip). It is run repeatedly across a sweep of battery capacities (2–16 kWh). For each capacity, installed cost is estimated at £700/kWh and payback is calculated as net cost divided by annual saving. A 10-year net present value (NPV) is also computed at a 3.5% discount rate. Battery degradation of 2%/year is applied when projecting multi-year returns.

**Accuracy and reliability:** The simulation is physically grounded and reproduces the behaviour of most rule-based home battery systems well. Key uncertainties are: (1) the installed cost benchmark is a market average — individual quotes vary ±30%; (2) the rule-based dispatch assumes perfect knowledge of cheap/expensive periods, which is broadly true for fixed-schedule tariffs (Economy 7) but less so for Agile where the battery controller sees only yesterday's prices; (3) degradation is modelled as linear, whereas real LFP degradation is non-linear (fast early degradation followed by a plateau). The NPV calculation is sensitive to assumptions about future electricity prices, which the model does not forecast.

**Future work:** Replacing the rule-based dispatch with a model predictive control (MPC) simulation — using a rolling price forecast — would give a more accurate Agile tariff result. Incorporating real degradation curves from manufacturer datasheets (rather than a fixed 2%/year) would improve long-term NPV accuracy. Monte Carlo simulation over a range of future electricity price scenarios would replace the single-point NPV with a probability distribution, giving a more honest picture of investment risk.

---

### Feature 3 — Appliance Load Disaggregation

**Method:** A background weekly profile is built from the median consumption at each of the 336 (weekday, half-hour period) slots in a week, using 8 weeks of history. The median is used rather than the mean because half-hourly energy data is right-skewed. A residual series is computed by subtracting the background from each reading; contiguous blocks of residual above a 0.25 kWh threshold are identified as load events. Each event is characterised by duration, peak power, and start time, then scored against a library of appliance signatures using a weighted sum of three sub-scores: duration match, peak power match, and time-of-day affinity. Events scoring above 0.40 are matched. Appliance presence is confirmed only when at least four matching events are found with a mean confidence of 0.55 or above. For confirmed appliances, a time-of-use shift saving is computed by comparing the actual rate paid against the minimum available rate on the same day.

**Accuracy and reliability:** At 30-minute resolution, the method reliably detects appliances that draw at least 1.5 kW for a full half-hour or longer: EV chargers, immersion heaters, and heat pumps. Detection of washing machines and dishwashers is weaker because their duty cycles often straddle period boundaries, diluting the power signature. Short-cycle appliances (microwave, kettle) are below the detection threshold. The background subtraction assumes the household's baseline is stable, which fails if a new always-on appliance is added mid-dataset. Multi-appliance overlap — two large loads running simultaneously — can cause misclassification. Overall, the method is reliable for EV and immersion detection (>80% precision in practice on comparable datasets) but is better treated as indicative for smaller loads.

**Future work:** Non-intrusive load monitoring (NILM) at higher resolution (1-second or 1-minute data from a clamp meter) would dramatically improve disaggregation accuracy and enable detection of short-cycle appliances. At 30-minute resolution, factorial hidden Markov models (FHMM) or deep learning approaches trained on labelled sub-metered datasets can improve multi-appliance overlap resolution. Feedback from the householder ("yes, I have an EV") could be used to bias the prior probabilities and increase confidence.

---

### Feature 4 — Heat Pump Suitability Scoring

**Method:** Summer gas consumption (May–September) is used to estimate the base load (hot water and cooking) as the seasonal median daily consumption. For each heating-season day, space-heating gas is the total daily gas minus the base load. A coefficient of performance (COP) is modelled for an air-source heat pump at each half-hourly outdoor temperature using a Carnot-bounded formula scaled by a practical efficiency factor (η = 0.45, representative of modern UK ASHPs from MCS data). Thermal energy delivered by the existing boiler (at 89% efficiency for a modern condensing unit) is divided by the COP to give the electricity the heat pump would need for the same output. This is priced against the household's existing electricity tariff. The analysis is run at two flow temperatures — 45°C (underfloor or oversized radiators) and 55°C (standard UK radiators) — to bound the range. Payback is calculated net of the £7,500 Boiler Upgrade Scheme grant.

**Accuracy and reliability:** The base load separation is a simplification: any gas used for hot water heating in winter is attributed to space heating, which overstates the heat pump requirement slightly. The COP model captures the dominant temperature-dependent effect but does not account for defrost cycles (which reduce effective COP by 5–10% in cold wet conditions), part-load operation, or the specific design of the installed system. The flow temperature assumption is the largest single source of uncertainty: misclassifying a 70°C system as 55°C produces a COP overestimate of roughly 30%. The payback calculation uses current gas and electricity prices, which are volatile; the app presents the break-even COP as the primary decision metric precisely because it depends only on the price ratio, not absolute prices.

**Future work:** Integrating the EPC register to read the actual heating system description would allow automatic flow temperature selection. Incorporating degree-day normalisation over multiple years would reduce sensitivity to warm or cold winters in the sample period. A Monte Carlo simulation over plausible electricity/gas price ratio scenarios (and COP uncertainty) would replace the point estimate payback with a probability distribution — giving a more rigorous investment case. Connecting to MCS installation data for the household's postcode would allow installer quote benchmarking.

---

### Feature 5 — Boiler Efficiency Trending

**Method:** Space-heating gas (total minus summer base load) is normalised by heating degree-days (HDD, base 15.5°C) to produce a daily kWh/HDD metric. A quadratic correction term is applied to account for condensing boiler behaviour, which means efficiency actually improves on very cold days as the boiler enters deeper condensing mode. A rolling 28-day window of normalised efficiency is compared against the baseline established in the first full heating season. An alert fires when the recent window exceeds the baseline by 15% or more. A pattern classifier distinguishes gradual trends (slow ramp upward, suggesting normal wear) from step changes (abrupt jump, suggesting a discrete fault event), so that the alert message gives different guidance in each case.

**Accuracy and reliability:** The method is effective at detecting 15%+ efficiency loss over a season, which corresponds to a meaningful increase in annual gas costs. The main limitation is confounding: a step change in household occupancy (someone moving in or out), a new appliance, or a change in thermostat setpoint all alter kWh/HDD without any change in boiler performance. The algorithm cannot distinguish these from boiler degradation without additional context. The quadratic HDD correction helps but does not fully remove the condensing/non-condensing bias. Reliability improves significantly with a second full heating season of baseline data.

**Future work:** Incorporating occupancy data (Tier 3) as a covariate in the regression would reduce false positives from occupancy changes. Bayesian change-point detection would give a probabilistic estimate of when a degradation event occurred, rather than a simple threshold alert. Linking to boiler servicing records (if the user logs them) would allow the model to reset its baseline after a service and track post-service recovery.

---

### Feature 6 — Heating Efficiency Scoring and Peer Benchmarking

**Method:** An ordinary least squares (OLS) regression is fitted to the household's (HDD, daily heating gas) data from the heating season. This gives a slope (kWh per degree-day, representing the building's heat loss rate) and an intercept (the non-heating base load). For each heating day, an efficiency score is computed as the ratio of actual to expected gas, expressed as a percentage (100 = exactly on trend). Days more than 2.5 standard deviations above expected are flagged as anomalous. Peer benchmarking uses BEIS NEED dataset values (median, 25th, 75th percentile of kWh/HDD by property type and build era) to estimate a percentile rank for the household.

**Accuracy and reliability:** The regression fit quality (R²) is reported alongside results. An R² below 0.60 means HDD alone does not explain the gas pattern well — possibly because the household has a non-condensing boiler, inconsistent thermostat behaviour, or high occupancy variability — and results are withheld until more data accumulates. The peer benchmarks are national averages from BEIS data; they do not account for geography (northern Scotland is colder than southern England) or for differences in internal temperature setpoint. A household running at 19°C will appear "inefficient" compared to one running at 17°C, even with identical fabric.

**Future work:** Replacing national BEIS benchmarks with platform-internal peer data (from the consented user base, stratified by postcode district and floor area band) would substantially improve the benchmark precision. Adding indoor temperature (Tier 4) as a regression covariate would decouple setpoint behaviour from fabric performance, making the score a purer measure of insulation quality.

---

### Feature 7 — Monthly Budget Forecasting

**Method:** The household's HDD–gas regression (from Feature 6) is used to convert a 14-day temperature forecast into a projected daily gas consumption for each remaining day in the month. The Open-Meteo forecast provides mean temperatures with an uncertainty that grows with forecast horizon (approximately 0.35°C per day to the power of 0.7). Three projections are produced: central (mean forecast temperature), high (one standard deviation colder), and low (one standard deviation warmer). Actual spend to date is added to the remaining projection to give a month-end total cost range. If the high-end projection exceeds the user's budget, an alert fires. A thermostat nudge calculation converts the budget gap into a recommended setpoint reduction in degrees Celsius, using the regression slope as the gas-per-degree sensitivity.

**Accuracy and reliability:** The forecast is reliable within the 5-day window where weather forecast accuracy is high. Beyond 10 days, the uncertainty range widens significantly and the projection should be treated as indicative. The method inherits all limitations of the underlying HDD regression (R² dependency, occupancy confounds). The thermostat nudge is a linear approximation: CIBSE guidance suggests 1°C reduction saves approximately 8–10% of heating demand, which is consistent with the regression-based result for most properties. For very low-HDD months (mild weather), the regression prediction becomes noisy and the forecast is less reliable.

**Future work:** Ensemble weather forecasting (averaging multiple forecast models) would reduce temperature forecast uncertainty. Incorporating stochastic pricing (for variable-rate tariffs) would extend the cost uncertainty range to reflect both weather and price risk. A user-configurable budget that automatically adjusts for seasonal baseline (higher in winter, lower in summer) would make the feature more useful year-round.

---

### Feature 8 — Carbon-Aware Demand Shifting

**Method:** The National Grid ESO's half-hourly carbon intensity forecast for the household's DNO region is fetched via the carbonintensity.org.uk API (48-hour forecast, gCO₂eq/kWh). For each detected flexible appliance (from Feature 3), a sliding window search finds the contiguous block of forecast periods with the lowest mean carbon intensity within the user's allowed run window (constrained by earliest start and latest end times). For EV charging, the required energy is known approximately from historical charge events and the session is scheduled by ranking periods in ascending carbon order until the energy requirement is met, subject to a departure-time hard constraint. Where the lowest-carbon window differs from the lowest-cost window, both are presented with the trade-off quantified.

**Accuracy and reliability:** Carbon intensity forecasts are well-calibrated within 24 hours (ESO's own accuracy assessment shows MAE of approximately 20 gCO₂/kWh). Beyond 24 hours, accuracy degrades sharply as renewable generation becomes harder to predict. The appliance scheduling recommendation depends on Feature 3 having correctly identified the appliance; misclassification propagates directly into the recommendation. EV energy requirement is estimated from historical charge events — if the user charges to different levels on different days, the estimate will be approximate. The joint carbon/cost optimisation is currently a simplified approximation for the cost side; it uses a proxy rather than computing exact tariff cost for each candidate window.

**Future work:** Integrating a smart EV charger API (OCPP-compatible chargers from Ohme, Hypervolt, etc.) would allow the app to send the schedule directly to the charger rather than relying on the user to act on the recommendation. Replacing the proxy cost calculation with the full tariff rate lookup would make the trade-off analysis exact. Extending the scheduling horizon to 36–48 hours (using the outer forecast window with wider uncertainty bounds) would allow better scheduling for multi-day plans.

---

### Feature 9 — Heating Pre-Warm Optimisation

**Method:** The first morning heating period is extracted from each day's gas data by identifying the earliest half-hour where consumption exceeds 0.15 kWh (the minimum consistent with a boiler running rather than a pilot light). This produces a time series of (boiler start period, outdoor temperature at 06:00) observations over the heating season. An OLS regression fits start period as a function of outdoor temperature: colder mornings are expected to need an earlier start. Each morning, the model takes the day's 06:00 forecast temperature, computes the predicted start period, and presents it as a recommended time. A smart thermostat detection check (low variance in historical start times regardless of temperature) suppresses the feature if a thermostat is already performing this function.

**Accuracy and reliability:** The regression R² is used as a quality gate — if it falls below 0.45, the recommendation is withheld because the household's start time pattern is too inconsistent to model reliably. In practice, households with fixed routines (same wake time every day) and no smart thermostat typically yield R² of 0.5–0.75. The prediction uncertainty is approximately ±1 hour (±2 periods) at moderate R², which is disclosed to the user. The method fails for households where occupant routine varies significantly (shift workers, irregular schedules) — the regression captures a mean pattern that may not apply on any given day.

**Future work:** Adding day-of-week as a regression variable would capture weekend lie-in patterns. Incorporating occupancy departure and arrival times (from Tier 3 phone presence) as additional predictors would significantly improve both accuracy and applicability to variable-routine households. Connecting to a smart thermostat API (Hive, Tado, Nest) would allow the recommendation to be pushed as a schedule update rather than a notification.

---

### Feature 10 — Micro-Leak and Frost Detection

**Method (micro-leak):** Overnight gas consumption (00:00–04:00 and 22:00–24:00) during summer months (May–September) is used to establish a baseline: median overnight kWh and 95th/99th percentile values. During the heating season, overnight readings are compared against this baseline. An alert fires when readings exceed 3× the summer median for at least 6 consecutive half-hour periods (3 hours). Triage logic maps the excess magnitude to probable causes (pilot light artefact, hot water cylinder heat loss, slow gas leak, boiler misfiring).

**Method (frost detection):** Two independent triggers: (1) vacancy detection — no gas activity for 12 hours — combined with a sub-2°C overnight forecast low; (2) expected boiler operation (based on HDD and time of day) absent from the gas signal, combined with a frost forecast. Alert severity is escalated to CRITICAL below -3°C.

**Accuracy and reliability:** The micro-leak detector's 3× threshold is deliberately conservative to minimise false positives. The main false positive source is boiler frost-protection mode, which fires automatically on cold nights and produces exactly the kind of sustained overnight gas reading the detector looks for. The algorithm suppresses alerts on declared frost-protection nights where a smart thermostat profile is known, but this requires the user to have declared their thermostat. Frost detection from day one (no historical data required) is the most reliable feature in the system: the logic is purely threshold-based on forecast temperature and a binary vacancy signal, with no statistical model to go wrong.

**Future work:** Machine learning on labelled leak datasets (from gas network incident records) would allow the 3× threshold to be tuned per property type and season. Connecting to British Gas or Cadent Network emergency data feeds would allow correlated reporting (multiple alerts in a street suggests a distribution network issue rather than individual faults). For frost detection, integrating with building insurance APIs would allow automatic claim notification or temporary heating activation via a smart thermostat.

---

### Feature 11 — Vacancy-Aware Anomaly Suppression

**Method:** Occupancy signals (PIR, CO₂, phone Wi-Fi presence, manual calendar) are fused into a per-period three-state label: OCCUPIED, VACANT, or UNKNOWN. A priority order resolves conflicts: manual calendar entries override sensor signals; CO₂ and phone presence are equally weighted; PIR can confirm OCCUPIED but cannot confirm VACANT. Anomaly detection runs on the energy data (flat-line and spike detection using a median/MAD baseline), and the result is modified by the occupancy label: flat-lines are suppressed during VACANT periods; spikes during VACANT periods are escalated.

**Accuracy and reliability:** The quality of the suppression is entirely determined by the quality of the occupancy signal. Phone Wi-Fi presence is the most practical signal for most households and has high precision (false OCCUPIED detections are rare) but can produce false VACANT readings when phones enter sleep mode or switch to mobile data. CO₂ sensors are the most accurate passive signal but require installation. Manual calendar entries are perfectly accurate but require user discipline to maintain. The UNKNOWN state is handled conservatively: flat-lines escalate after 24 hours, not immediately.

**Future work:** Probabilistic occupancy modelling — rather than hard three-state labels — would propagate uncertainty more cleanly into the downstream alerting logic. Routine learning (household is always occupied on Sunday mornings, always vacant on Tuesday afternoons) would allow UNKNOWN periods to be filled with probabilistic estimates. Federated learning across the consented user base (without sharing raw data) could build population-level occupancy priors that improve cold-start behaviour.

---

### Feature 12 — Phantom Load Detection

**Method:** During confirmed VACANT periods, electricity consumption is measured and a distribution is built: the 10th percentile is treated as the unavoidable always-on floor (fridge, router, alarm); the median is the typical standby level; the 90th and 95th percentiles define elevated phantom load thresholds. Each VACANT period is classified into one of four bands (ALWAYS_ON, LOW_PHANTOM, ELEVATED_PHANTOM, HIGH_PHANTOM). An alert fires when at least 4 consecutive periods exceed the 90th percentile threshold and the mean excess is above 0.05 kWh/period (approximately 100 W average). A trend detector compares rolling 4-week medians to identify step changes caused by new always-on devices. Peer benchmarking uses property type and bedroom count to place the household's median VACANT consumption in a percentile distribution.

**Accuracy and reliability:** The method is reliable for detecting sustained phantom loads above ~100 W. Loads below 50 W (phone charger, LED indicator lights) are below the practical detection threshold of half-hourly meter data. The 4-consecutive-period requirement for alerting reduces false positives from single anomalous readings but means a phantom load that runs for less than 2 hours will not trigger an alert. The peer benchmarks depend on having a sufficient number of similar consented properties in the platform dataset — the current benchmarks are populated from national averages as a bootstrap.

**Future work:** At 1-minute sub-metering resolution (from a clamp meter), individual always-on devices could be identified by their specific steady-state draw. At half-hourly resolution, clustering analysis across multiple VACANT periods could fingerprint recurring phantom load patterns and attribute them to specific device categories (e.g. a gaming console in standby draws a distinctive ~15 W continuously). Integration with smart plug data would allow confirmation and remote switch-off.

---

### Feature 13 — Thermal Mass and Insulation Profiling (τ and HLC)

**Method:** During periods when the boiler is confirmed off (gas < 0.05 kWh/period) and the indoor-outdoor temperature difference exceeds 3°C, the building undergoes free cooling following Newton's Law of Cooling. The log-transformed indoor-outdoor temperature differential is regressed against time using OLS: the gradient of the log-linear fit equals -1/τ, where τ is the thermal time constant in hours. Only fits with R² ≥ 0.85 are accepted. Multiple event estimates are combined using a weighted mean (weighted by R² × number of data points). The heat loss coefficient (HLC, W/K) is calculated as C/τ, where C is the building's effective thermal capacitance estimated from property type and build era lookup tables (based on ISO 13786 and BEIS NEED data). Results are reported with 95% confidence intervals derived from the scatter in individual event estimates.

**Accuracy and reliability:** The τ estimation from a single overnight cooling event typically has an uncertainty of ±15–25%, reducing to ±8–12% when 20 or more good-quality events are averaged. The dominant systematic uncertainty is the assumed thermal capacitance C: the property type lookup introduces approximately ±20% uncertainty, which adds in quadrature to the statistical uncertainty in τ. The overall HLC estimate should be regarded as reliable within ±25% for relative comparisons (before vs after retrofit, vs EPC prediction) but not as a precise absolute value. The method requires a sufficiently cold outdoor temperature to drive a significant indoor-outdoor differential — in mild climates or well-heated homes in early autumn, qualifying events may be sparse.

**Future work:** Active thermal testing (a brief, controlled period of elevated heating followed by monitored cool-down) would allow τ measurement in any season and would remove dependence on the passive overnight event. Measuring thermal capacitance directly from a step-response heating experiment (rather than from lookup tables) would eliminate the largest source of systematic uncertainty. Integrating with EPC lodgement data to obtain actual U-values and dimensions would allow a physics-based HLC calculation as a cross-check, replacing the lookup table approximation.

---

### Features 13a–13e — EPC Enhancement Services

**Method summary:** All five sub-features derive from the τ/HLC estimate from Feature 13. The SAP HTC (heat transfer coefficient) is estimated by inverting the SAP energy equation from the EPC register's published energy consumption per m², giving an implied modelled heat loss. The performance gap is the difference between measured and modelled HLC as a percentage. The dynamic EPC band is assigned by mapping HLC/m² to published SAP EER band boundaries, calibrated for property archetype. Retrofit verification uses Welch's t-test (unequal variance) to compare the distribution of τ estimates before and after an installation date, with a 6-week post-installation settling period. The evidence package for green mortgages assembles these outputs into a structured JSON document. National stock aggregation applies k=10 anonymity to segment-level statistics before any external reporting.

**Accuracy and reliability:** The EPC band assignment is an approximation: full SAP calculates EER from multiple inputs (heating system, lighting, renewable generation) whereas this method back-calculates from fabric performance alone. The band assignment should be treated as indicative rather than replacing a formal SAP assessment for legal or regulatory purposes. Retrofit verification statistical power depends heavily on the number of pre- and post-retrofit events: with fewer than 10 post-retrofit events, the t-test has low power and moderate improvements (8–15%) may not reach significance. The 6-week settling period is a practical rule of thumb — some materials (solid wall insulation, for example) take longer to reach thermal equilibrium.

**Using Feature 13 as a pre-screening tool for professional U-value measurement:** A specific and practical application of the performance gap (Feature 13a) is to help a homeowner decide whether to commission a professional in-situ U-value measurement — typically costing around £200 for a single wall element using heat flux plate equipment — before requesting a formal EPC reassessment. The rationale is that RdSAP assessors must use conservative default U-values when no measured data is available, and for many properties those defaults significantly understate actual fabric performance. If the measured HLC is materially lower than the SAP prediction, this is evidence that one or more building elements is performing better than the default assumption, and a measured U-value could unlock a higher EPC band.

The recommended decision framework based on the performance gap magnitude is:

| Measured gap | Interpretation | Recommended action |
|---|---|---|
| < 15% better than SAP | Within measurement noise | No action — gap not reliably detectable |
| 15–30% better than SAP | Probable real improvement | Commission an RdSAP reassessment first (£100–150); assessor visit may capture improvements (e.g. CWI injection) already, at lower cost than U-value measurement |
| > 30% better than SAP, seen across two or more heating seasons | Strong evidence of under-rated fabric | Calculate EPC band uplift value; if financial benefit exceeds £200, proceed to professional U-value measurement |

It is important to understand what the τ measurement can and cannot tell you. Because HLC is a whole-building number, a significant gap indicates that *something* is performing better than SAP assumes, but not *which element* is responsible. Before commissioning a U-value measurement, the probable source of the gap should be identified from the property's construction type and age band:

- **Pre-1945 solid brick walls** — SAP defaults (≈1.7 W/m²K) are frequently pessimistic; actual performance is often 1.2–1.4 W/m²K due to surface finishes, dense mortar, and thermal mass effects not captured in the steady-state default. Wall U-value measurement is most likely to be productive here.
- **Cavity walls with injected insulation** — if CWI was installed post-construction but never re-lodged on the EPC, the assessor will default to an uninsulated cavity value. A measured U-value (or simply providing installer certification) corrects this at no measurement cost.
- **Loft insulation above the standard assumed depth** — visible inspection during an assessor visit resolves this without specialist equipment.
- **Air tightness** — if the gap is large but wall and loft construction is unremarkable, improved air tightness (from draft-proofing works) may be the driver. Air permeability measurement (blower door test, typically £300–500) would be the appropriate follow-on, not U-value plates.

Professional U-value measurement using heat flux plates requires a minimum 72-hour monitoring period under stable conditions (indoor-outdoor temperature difference > 10°C, no solar gain on the measured surface), making it a winter-only measurement and logistically similar in commitment to the τ measurement itself. The app should flag this constraint and suggest commissioning the measurement in November–February for reliable results.

**Future work:** Partnership with MHCLG to access full SAP lodgement data (not just the summary register) would allow a properly physics-based HLC comparison rather than the inversion approximation. Formal accreditation of the retrofit verification methodology with relevant bodies (e.g. BEIS, MCS, PAS 2035) would allow the evidence package to be used in grant scheme compliance sign-off, removing the need for a separate post-installation inspection in straightforward cases. The decision framework above should be implemented as an interactive recommendation within the app, automatically calculating the EPC band uplift value from the current performance gap and property characteristics, and presenting a personalised go/no-go recommendation with a confidence rating. Extending to commercial properties would require a different thermal capacitance model and a separate HDD base temperature.

---

### Feature 14 — Comfort vs Cost Reporting

**Method:** Indoor temperature readings are scored against the WHO/CIBSE comfort band (18–22°C) using a continuous score: 0 at or below 16°C (health risk threshold), linearly rising to 1.0 at 18°C, and remaining 1.0 above 18°C. Scores are averaged over occupied periods only (using the Tier 3 occupancy label). Weekly energy cost is split into occupied and vacant components using the same occupancy labels and the household's tariff from Feature 1. The comfort/cost quadrant classifies the household relative to peer medians: above/below peer comfort combined with above/below peer cost gives four outcomes (efficient and comfortable; comfortable but expensive; under-heated; cold and expensive).

**Accuracy and reliability:** The comfort score depends on the accuracy of the indoor temperature sensor placement and the quality of the occupancy signal. A poorly placed sensor (near a radiator or in direct sunlight) will produce systematically optimistic comfort scores. The peer comparison inherits the limitations of the peer dataset: if the consented population skews towards engaged, energy-conscious households, the peer medians will be biased towards higher comfort and lower cost than the general population. The health-risk alert (below 16°C while occupied) is a hard threshold aligned with WHO guidance for sedentary adults; it may not be appropriate for households with highly active occupants or those with different thermal comfort preferences.

**Future work:** Multiple indoor sensors (bedroom, living room, kitchen) would give a spatial comfort map rather than a single-point estimate, which would be particularly valuable for identifying cold rooms in multi-zone properties. Integrating with smart thermostat setpoint data would allow the model to distinguish between under-heating driven by thermostat settings (behavioural) and under-heating driven by an inability to reach the setpoint (fabric or boiler performance issue). Personalised comfort bands (the user can declare their preferred temperature range) would make the score more meaningful for households with atypical preferences.

---

### Air Infiltration Pre-Screening — Indicator for Blower Door Testing

A blower door pressure test (BS EN ISO 9972) measures the air permeability of a building at 50 Pa pressurisation, giving a result in m³/h/m² (q50) or air changes per hour at 50 Pa (n50). It is the definitive method for quantifying air leakage and feeds directly into the SAP air permeability field, replacing the conservative default assumptions used when no test has been done. The test typically costs £300–500 for a residential property.

The same principle applied to Feature 13's U-value pre-screening applies here: a low-cost indicator from existing data can determine whether a blower door test is likely to improve the EPC rating before committing to the expenditure. Two complementary methods are available.

#### Method 1 — Wind-speed regression on τ estimates (no additional hardware)

The whole-building heat loss coefficient has two additive components:

```
HLC = H_fabric + ρ·cₚ · N(v) · V
```

Where `H_fabric` is conductive loss through the building fabric (W/K); `ρ·cₚ` is the volumetric heat capacity of air (≈ 0.33 Wh/m³K); `N(v)` is the air change rate in ACH at wind speed v; and `V` is the internal volume in m³. As a first approximation, infiltration increases linearly with wind speed:

```
N(v) = N₀ + k·v
```

Where `N₀` is the still-air infiltration rate and `k` is the wind sensitivity coefficient (ACH per m/s). Since `1/τ = HLC/C`, this gives:

```
1/τ = (H_fabric + ρ·cₚ·(N₀ + k·v)·V) / C
```

This is linear in wind speed. Feature 13 already produces a (τ, wind speed) pair for every overnight free-cooling event. Regressing `1/τ` against wind speed `v` gives:

- **Slope** — proportional to the wind-driven infiltration sensitivity coefficient `k`
- **Intercept** — proportional to the still-air HLC, from which N₀ can be extracted given V and an assumed H_fabric

The wind correlation coefficient alone is a reliable qualitative indicator regardless of absolute calibration: a strong positive correlation (r > 0.5 between 1/τ and wind speed) identifies infiltration as the dominant gap driver and directs the homeowner toward a blower door test rather than a U-value survey. A weak correlation with a persistent gap indicates a fabric problem instead.

**Limitation:** H_fabric must be assumed from construction data, introducing the same ±20% systematic uncertainty as the τ method itself. The absolute N₀ estimate should be treated as indicative. A minimum of 20 overnight decay events across a range of wind conditions is needed for a statistically meaningful regression.

#### Method 2 — CO₂ tracer gas decay (requires the Tier 3 CO₂ sensor)

When occupants are present, exhaled CO₂ raises indoor concentration above the outdoor ambient of approximately 420 ppm. When the property becomes vacant (confirmed by the occupancy signal), CO₂ decays back toward ambient driven by air infiltration and mechanical ventilation:

```
C(t) = C_outdoor + (C₀ − C_outdoor) · exp(−N · t)
```

Where `C(t)` is indoor CO₂ at time t, `C₀` is the concentration at vacancy onset, and `N` is the air change rate in ACH. Log-linearising and applying OLS regression to the post-vacancy readings gives N directly — the same mathematical structure as the τ decay fit in Feature 13. This runs automatically and passively every time the property becomes vacant after a period of occupancy, producing repeated measurements that can be averaged to reduce uncertainty.

The result is the **natural-condition ACH**. To compare with a blower door result, the Sherman conversion factor is applied:

```
n₅₀ ≈ N_natural × f
```

Where `f` ≈ 20 for a typical two-storey UK house (range: 15 for sheltered single-storey to 25 for exposed multi-storey). This conversion carries ±30–40% uncertainty and is a screening estimate only.

**Practical constraints:** CO₂ must be elevated above approximately 600 ppm at vacancy onset, requiring at least 1–2 hours of prior occupancy. The method assumes well-mixed air — open-plan layouts give the most reliable result; heavily compartmentalised properties with closed doors give a partial-zone estimate. The decay window is typically 2–4 hours; shorter for draughty properties.

#### Decision framework

SAP default natural infiltration assumptions by age band:

| Age band | SAP default natural ACH |
|---|---|
| Pre-1945 | 0.7 – 1.0 |
| 1945 – 1980 | 0.5 – 0.7 |
| Post-1980 | 0.3 – 0.5 |
| Post-2006 (Part L) | 0.15 – 0.3 |

| Measured ACH vs SAP default | Recommended action |
|---|---|
| Within 15% of default | Within noise — no action |
| 15–35% below default | Check mechanical ventilation entries in the EPC first; an assessor visit may resolve without testing |
| > 35% below default, seen across 5+ measurements | Blower door test is likely to improve SAP rating; calculate band uplift value before commissioning |
| Above default | Property is leakier than SAP assumes; blower door would reduce the rating — no benefit unless air-tightness works are planned |

#### Directing spend: infiltration vs fabric

The two pre-screening methods address distinct components of HLC and should be interpreted together before committing to either test:

- **Weak wind correlation + CO₂ ACH consistent with SAP default** → gap is fabric-driven → pursue U-value measurement (£200)
- **Strong wind correlation + CO₂ ACH well below SAP default** → gap is infiltration-driven → pursue blower door test (£300–500)
- **Strong wind correlation + CO₂ ACH consistent with SAP default** → wind-driven stack infiltration is significant but baseline is as expected → consider draught-proofing assessment before a full blower door test
- **Weak wind correlation + CO₂ ACH well below SAP default** → property is tight but fabric underperforms; both measurements may be warranted, or the τ uncertainty is masking a fabric improvement

**Future work:** Automating the decision tree within the app — combining the wind-correlation coefficient, the CO₂-derived ACH, and the performance gap magnitude — would produce a single recommendation with a confidence rating and an estimated EPC band uplift for each test option. Calibrating the Sherman factor `f` per property using geometry data from the EPC register (floor area, storeys, exposed perimeter) would reduce the n50 conversion uncertainty from ±40% to approximately ±20%. Integrating with the Gas Safe and CORGI databases would allow the app to recommend certified blower door testers in the household's postcode.

---

## Additional Sensors — Value and Feasibility

The features described in this document are built from smart meter data, a free weather API, an occupancy signal, and a single indoor temperature sensor. A number of additional low-cost sensors would materially improve the accuracy of existing features or unlock new ones. The following describes each sensor, what it adds, and where it sits in a cost-versus-impact assessment.

---

### CT Clamp / Whole-Home Electricity Monitor

**Examples:** Efergy Engage, Sense, Emporia Vue, Shelly EM — £50–150, clipped onto the consumer unit tails by a competent person.

**What it adds:** Real power measurement at sub-minute or second-level resolution, replacing the half-hourly smart meter as the primary electricity signal. This transforms Feature 3 (appliance disaggregation) from an indicative pattern-matching exercise into genuine non-intrusive load monitoring (NILM). At 1-second resolution, individual appliances have distinctive load signatures — motor start transients, switching noise, steady-state draw — that allow confident identification and separation even when multiple loads run simultaneously. Washing machines, dishwashers, and short-cycle appliances (kettle, microwave) that are invisible at 30-minute resolution become clearly detectable.

**Impact on existing features:** Feature 3 accuracy improves from approximately 80% on EV and immersion heater detection to over 90% across all target appliances. Feature 8 (carbon-aware scheduling) benefits from precise per-appliance energy quantification rather than event-duration estimates. Feature 12 (phantom load) can resolve individual standby draws rather than a household aggregate.

**Accuracy note:** Some whole-home monitors use machine learning trained on appliance databases rather than physics-based signatures, which makes them accurate for common appliances but unreliable for unusual or older equipment. Physics-based approaches using current waveform analysis are more generalisable across the housing stock.

---

### Heat Meter on the Heating Circuit

**Examples:** Sontex 531, Kamstrup Multical — £150–400 including flow sensor and temperature probes, plumber-installed.

**What it adds:** Direct measurement of thermal energy delivered by the heating system in kWh. This is the measurement that actually determines system efficiency — gas consumed divided by heat delivered gives true system efficiency, whereas Feature 5 currently infers efficiency from the gas/HDD relationship and cannot separate boiler efficiency from building heat loss. For heat pumps, thermal output divided by electrical input gives measured COP rather than the modelled estimate used in Feature 4.

**Impact on existing features:** Feature 4 (heat pump suitability) moves from a modelled COP with ±30% uncertainty to a directly measured seasonal COP. Feature 5 (boiler efficiency trending) can detect efficiency loss directly rather than via the HDD-normalised proxy, reducing false positives from occupancy and setpoint changes. Heat meter data also enables direct verification of whether a heat pump is hitting its MCS-rated performance — relevant to warranty claims and ECO4 compliance.

**Note:** A heat meter on a gas boiler system measures the thermal output of the heat emitter circuit, not the boiler's combustion efficiency directly. For condensing boilers this is a closer proxy than the gas/HDD method because it eliminates the HDD regression uncertainty. For heat pumps it is the definitive measurement.

---

### Flow and Return Temperature Probes

**Examples:** Clip-on pipe thermistors, DS18B20 probes — £20–50 for a pair, no plumbing required.

**What it adds:** Direct measurement of heating circuit flow and return temperatures. The delta-T (flow minus return) indicates how well the heat is being extracted by the emitters — a small delta-T suggests the radiators or underfloor circuit is not absorbing heat efficiently due to sludge, airlocks, or an oversized pump. Flow temperature is the single most uncertain input in the heat pump COP model — Feature 4 currently assumes either 45°C or 55°C, whereas the actual value may differ significantly from either assumption depending on the system design and weather compensation settings.

**Impact on existing features:** Feature 4 COP uncertainty drops from ±30% to approximately ±10% when flow temperature is measured directly. Feature 5 gains a second degradation indicator: a rising return temperature at constant outdoor conditions indicates heat exchanger fouling. These sensors connect to the same gateway as the Tier 4 indoor temperature sensor, requiring no additional hub.

---

### Hot Water Cylinder Temperature Sensor

**Examples:** Clip-on probe or immersion pocket sensor — £10–30.

**What it adds:** Direct measurement of cylinder temperature, typically at the mid-point and top of the tank. This enables: (1) confirmation that the cylinder reaches 60°C for legionella pasteurisation at least weekly; (2) measurement of cylinder standing heat loss — the cylinder is a known-volume thermal store, so its overnight cooling rate gives a heat loss coefficient directly; (3) identification of whether the immersion heater is doing useful work or duplicating heat already provided by the boiler or heat pump.

**Impact on existing features:** Feature 10 (micro-leak detection) currently flags sustained overnight gas as a possible cylinder heat loss but cannot confirm it. A cylinder sensor resolves this — if overnight gas correlates with the cylinder cooling below setpoint and reheating, the cause is cylinder heat loss rather than a gas leak. Feature 3 (appliance disaggregation) gains a direct confirmation signal for immersion heater detection. For solar thermal systems the cylinder sensor is the primary measure of solar yield.

---

### Multiple Indoor Temperature Sensors

**Examples:** Same specification as the Tier 4 sensor — £15–30 each, placed in bedrooms, hallway, and the coldest room.

**What it adds:** Spatial temperature distribution across the property. A single living room sensor gives a whole-house comfort score that conceals cold bedrooms or poorly performing extensions. Multiple sensors enable per-room comfort scoring, identification of rooms where the heating system is not balancing correctly, and detection of local insulation failures — a room decaying significantly faster than others during a free cooling event is indicative of missing or failed cavity wall insulation in a specific wall section, or air leakage around a window reveal. This directs a fabric investigation to a specific location rather than triggering a whole-building survey.

**Impact on existing features:** Feature 13 (τ measurement) can be run per-room to produce a spatial map of heat retention quality. Feature 14 comfort reporting becomes zone-level. A three-sensor deployment at £45–90 total provides substantially more diagnostic value than a single sensor for the insulation pre-screening use cases.

---

### Humidity Sensors

**Examples:** Combined temperature/humidity sensors (SHT30, DHT22) — available integrated with most modern indoor temperature sensors at marginal additional cost of £0–10.

**What it adds:** Indoor relative humidity (RH). In the context of building energy performance, humidity matters for three reasons: (1) high RH combined with cold surfaces creates condensation and mould risk — a common and serious consequence of retrofit insulation that shifts the dew point to the internal face of the original wall; (2) RH correction improves the accuracy of the comfort score, since apparent temperature is a function of both temperature and humidity; (3) moisture content in building fabric affects thermal conductivity — wet insulation performs significantly worse than its dry rated U-value.

**Impact on existing features:** Feature 14 comfort scoring becomes more accurate. A new alert category becomes possible: RH exceeding 70% in a cold room is a leading indicator of mould formation, typically preceding visible damage by several weeks. Post-retrofit monitoring of RH is particularly important after solid wall insulation installation, where interstitial condensation in the insulation layer is a known failure mode that thermal sensors alone cannot detect.

---

### Solar Inverter API

**Examples:** SolarEdge, SMA, Fronius, Growatt, Solis — all expose local or cloud APIs, free if the inverter has Wi-Fi.

**What it adds:** Direct half-hourly solar generation data rather than inferring generation from net import/export figures. The smart meter export reading confounds solar generation with battery discharge and demand reduction — it is a net figure, not a gross one. Direct inverter data separates these cleanly, enabling accurate battery sizing modelling (Feature 2) and a direct solar self-consumption calculation. Inverter data also enables panel degradation detection — a gradual fall in output per unit of irradiance over months indicates soiling, shading, or cell degradation.

**Impact on existing features:** Feature 2 battery dispatch simulation becomes significantly more accurate for solar households. Self-consumption rate can be calculated and used to optimise battery charge/discharge strategy. No hardware cost if the inverter already has Wi-Fi connectivity.

---

### EV State of Charge via Vehicle API

**Examples:** Tesla API, Nissan Leaf, Volkswagen We Connect, Ohme or Hypervolt charger API — free.

**What it adds:** Actual battery state of charge and departure time, replacing the estimated energy requirement used in Feature 8. Currently the EV scheduling algorithm estimates required charge from historical session durations, which may overestimate on days where the car is already partially charged. Direct SoC data enables precise scheduling — charge exactly the required kWh, no more — and confirmation of session completion. The algorithm can also incorporate range anxiety thresholds (always charge to at least 30% regardless of schedule) and trip planning overrides.

---

### Smart Radiator Valves (TRVs)

**Examples:** Tado, Drayton Wiser, Honeywell Evohome — £30–50 per valve.

**What it adds:** Per-room temperature setpoint control combined with per-room temperature measurement. In the context of this system, the primary value is multi-zone temperature data (equivalent to multiple indoor sensors) plus direct evidence of whether individual radiators are functioning — a radiator that fails to reach the room setpoint despite the boiler running indicates sludge, airlock, or incorrect balancing. Occupancy-linked setback (lowering setpoint in vacant rooms from the Tier 3 occupancy signal) becomes possible with per-room control, and boiler start time optimisation (Feature 9) can be refined by room-level temperature response.

---

### Local Weather Station

**Examples:** Davis Vantage Vue, Ecowitt GW1100 — £50–150.

**What it adds:** Property-specific microclimate data — temperature, wind speed, and rainfall — rather than the gridded weather API reanalysis. Properties in frost pockets, urban heat islands, coastal locations, or on exposed hillsides can differ from the nearest API grid point by 1–3°C on extreme nights. For the air infiltration pre-screening (Method 1), local wind speed at the building face is more relevant than the 10m station wind from Open-Meteo, particularly for properties in sheltered valleys or dense urban areas where surroundings strongly modify the local wind environment.

**Cost-effectiveness:** Marginal improvement over the weather API for most properties. Most valuable for locations known to diverge significantly from regional averages, and for the wind-speed regression used in infiltration screening.

---

### Thermal Infrared Camera (Periodic Diagnostic)

Not a continuous sensor, but included because it directly complements the τ and infiltration pre-screening outputs. Where Feature 13 quantifies *how much* heat is being lost and the infiltration methods estimate *how much* air is leaking, a thermal image taken on a cold night with the heating on shows *where* both are occurring — missing insulation visible as warm patches on an external wall, air leakage paths as cold streaks around window frames and socket boxes, thermal bridging at structural elements.

**Use case in this system:** Once the performance gap pre-screening identifies a significant gap, a thermal image taken before commissioning a U-value survey or blower door test can direct the investigation to the specific element responsible, potentially saving the cost of a full blower door test if the image clearly shows a single large air leakage path that can be sealed cheaply. The conditions required for a useful thermal image (minimum 10°C indoor-outdoor differential, heating running for at least 2 hours, clear dry night) are identical to those that produce the best τ decay events — the two diagnostic methods are naturally complementary in timing.

#### Thermal Camera — Current Market Options

**Budget (£150–300) — smartphone attachments**

**InfiRay P2 Pro** — approximately £150–180, USB-C. 256×192 native thermal resolution, which is higher than the FLIR One Pro at a lower price. The most cost-effective option for building diagnostics where resolution matters more than brand recognition. Recommended for this system's use case.

**FLIR One Pro** — approximately £200–230, USB-C or Lightning. 160×120 native thermal resolution with MSX edge enhancement, which overlays the visible camera image onto the thermal to make cold spots and air leakage paths significantly easier to interpret. Widely recognised by assessors, surveyors, and insurers — relevant if the image output will form part of a formal evidence package (mortgage application, ECO4 compliance, insurance claim).

**Seek Thermal CompactPro** — approximately £180–220. Similar resolution to the FLIR One Pro with slightly better raw thermal sensitivity, but FLIR's MSX image blending is generally more useful for building surveys than Seek's raw output.

**Mid-range (£300–600) — standalone handheld**

**Hti-Xintai HT-A2 and similar Xinfrared/Hti units** — £250–400. Standalone devices requiring no phone, 256×192 resolution. Lower build quality than FLIR but often using the same Lepton thermal core. Practical for repeated periodic surveys without dependence on a specific smartphone model.

**FLIR C5** — approximately £500. The entry point to FLIR's standalone range. Wi-Fi enabled, 160×120 with MSX, touchscreen display. The brand carries weight in formal reporting contexts.

**Recommendation for this system**

For the diagnostic application described in this guide — identifying cold spots, air leakage paths, and missing insulation on a domestic property to support the Feature 13 pre-screening decision — the **InfiRay P2 Pro** at approximately £150–180 offers the best resolution per pound. The 10°C indoor-outdoor differential requirement for a useful building image is comfortably met on a winter night, and at those conditions the sensitivity difference between the P2 Pro and more expensive units is negligible. If the output is likely to be reviewed by a third party in a formal context, step up to the **FLIR One Pro** for the brand recognition alone.

Prices in this segment change frequently. Verify current availability on Amazon UK and the InfiRay/Xinfrared direct sites before purchasing.

---

### Summary — Sensor Value vs Cost

| Sensor | Approx cost | Primary features improved | Impact |
|---|---|---|---|
| CT clamp whole-home monitor | £50–150 | Feature 3, 8, 12 | High — transforms disaggregation accuracy |
| Heat meter | £150–400 | Feature 4, 5 | High — enables measured COP |
| Flow/return temperature probes | £20–50 | Feature 4, 5 | High — eliminates largest COP model uncertainty |
| Hot water cylinder sensor | £10–30 | Feature 3, 10 | Medium — resolves DHW vs space heating ambiguity |
| Additional indoor temp sensors | £15–30 each | Feature 13, 14 | Medium — enables spatial fabric diagnosis |
| Humidity sensors | £0–10 marginal | Feature 14, mould alert | Medium — building health monitoring |
| Solar inverter API | Free | Feature 2, 8 | Medium for solar households |
| EV SoC API | Free | Feature 8 | Medium for EV households |
| Smart TRVs | £30–50 per valve | Feature 9, 13, 14 | Medium — multi-zone control and measurement |
| Local weather station | £50–150 | Feature 6, 9, infiltration screening | Low-medium — marginal over API for most locations |
| Thermal IR camera | £250–350 one-off | Fabric and infiltration diagnosis | High diagnostic value, used periodically |

The highest-value additions for a property with gas heating and no solar are the CT clamp, flow/return temperature probes, and a hot water cylinder sensor — collectively under £250 — which together enable measured boiler efficiency, direct appliance identification, and DHW isolation. For a heat pump property, the heat meter replaces the flow/return probes as the priority, giving a directly measured seasonal COP that validates or challenges the installer's performance claims.

---

## Enhanced EPC Assessment — Value-Added Activities On Site

A standard RdSAP domestic EPC assessment takes 45–90 minutes and uses almost no instruments. It is primarily a visual inspection and room measurement exercise that feeds into a software model relying heavily on age-band default values for U-values, air permeability, and boiler efficiency. Most of the uncertainty in the resulting certificate comes from those defaults. An assessor carrying a modest sensor kit can substantially improve accuracy, reduce the reliance on defaults, and offer a tiered range of chargeable additional services.

### What the Standard Visit Covers

- Floor area and ceiling height measurement
- Visual identification of wall, roof, and floor construction type and age
- Heating system, controls, and fuel type
- Glazing type and estimated area
- Visible evidence of insulation (loft hatch inspection, CWI certificate)
- Lighting type
- Entry into RdSAP software, which applies default U-values and infiltration rates for the age band

Everything that cannot be seen — actual U-values, air permeability, boiler combustion efficiency, moisture content, thermal bridging — uses a published default. For older properties these defaults are almost always pessimistic; for poorly constructed newer ones they can be optimistic.

---

### No Additional Equipment Beyond a Smartphone

**Solar PV suitability screening**
Roof orientation and pitch can be measured with a phone compass and clinometer app. Combined with satellite imagery for shading and roof area derived from the floor plan, this produces an indicative generation estimate and payback period in five minutes. A natural upsell conversation for any property without existing solar.

**Smart meter connectivity check**
Many SMETS1 meters lost data connectivity after a supplier switch and have never been re-enrolled. The assessor can check IHD function, confirm meter type, and flag whether half-hourly data sharing is enabled — the prerequisite for all the smart meter analytics in this system. Identifying this at the point of EPC assessment creates an immediate referral pathway to data-driven monitoring services.

**EV charger and battery storage readiness**
Visual check: driveway or garage present; distance to consumer unit; existing 32A circuit; external wall space for a battery unit. Two minutes on site produces a readiness score directly relevant to the household's electrification pathway.

**Radiator sizing assessment**
Measuring radiator dimensions (height × length × type) allows heat output at various flow temperatures to be calculated. This is the key input for heat pump feasibility — whether existing radiators can deliver sufficient output at 45–50°C flow rather than the 70–80°C required by a conventional boiler. This is rarely done during a standard EPC visit, yet it is the most common single cause of heat pump installation underperformance.

---

### Simple Handheld Instruments (Under £100 Total)

**Loft insulation depth probe — £5–10**
The standard approach is to look through the loft hatch and estimate. A probe takes a precise reading in seconds. The difference between recording 150mm and 300mm can be one EPC band in some property archetypes. Under-recording insulation depth is one of the most common sources of EPC underscoring.

**Pin moisture meter — £20–50**
Measures moisture content in walls, floors, and window reveals. Cavity wall insulation is contraindicated in walls with moisture above approximately 20%. An assessor who identifies elevated moisture before recommending CWI prevents a costly installation failure and protects both the homeowner and the ECO4 scheme from a defective measure. Also identifies condensation-related moisture at cold bridges, which correlates directly with thermal image findings.

**CO₂, temperature, and humidity meter — £60–100**
Taking indoor air quality readings at the time of visit produces a snapshot that is immediately useful and establishes a baseline for comparison with the continuous monitoring this system provides. A CO₂ reading above 1,500 ppm in a bedroom with the door closed indicates a ventilation failure the RdSAP assessment will not flag. Humidity above 70% in a cold room is an active mould risk. Neither is currently recorded in a standard EPC.

**Carbon monoxide detector or analyser — £30–80**
A CO reading near gas appliances takes thirty seconds. At sub-acute poisoning levels (50–100 ppm) many occupants attribute symptoms to illness rather than a faulty appliance. The EPC visit is one of the few professional touchpoints at which a property receives any kind of inspection — flagging a CO risk has significant safety value and no commercial downside.

---

### Moderate Investment Instruments (£150–500)

**Thermal infrared camera — £150–350**
The highest-value instrument for an EPC assessor to carry. In a single walk around the property exterior on a cold morning after the heating has run overnight, the camera reveals: missing or failed cavity wall insulation sections (visible as warm patches on the external leaf); air leakage paths around window frames, loft hatches, and electrical sockets; thermal bridging at lintels, floor junctions, and corners; and glazing failures (broken sealed unit showing as a cold patch). Internally it identifies cold rooms, uninsulated pipes, and areas where insulation is absent above suspended ceilings.

This supports the EPC in three ways: (1) confirms or challenges the age-band default U-value assumptions; (2) identifies the specific locations where insulation is absent or failed, enabling targeted rather than whole-element recommendations; (3) produces photographic evidence that supports grant applications and helps the homeowner understand what the EPC score means in physical terms. See the previous section for recommended models — the InfiRay P2 Pro at approximately £150–180 is the most cost-effective option for this use case.

The requirement for a minimum 10°C indoor-outdoor differential means this works best between October and March. Assessors working in this period should carry one routinely.

**Flue gas analyser — £200–500**
Measures O₂, CO, CO₂, and flue gas temperature at the boiler flue outlet. From these the combustion efficiency is calculated directly — the actual efficiency of the boiler on the day of the visit, not the manufacturer's rated figure or the SAP default. A boiler running at 78% combustion efficiency rather than the 89% SAP assumes is losing approximately £120/year in wasted gas at current prices for an average household.

The flue gas result also indicates whether the boiler is condensing: a flue temperature below approximately 55°C confirms condensing operation; above 65°C suggests the return temperature is too high for condensing mode, often because the system is poorly balanced or the flow temperature is set too high for the installed radiators. This is directly actionable information for the homeowner and a natural referral to a heating engineer.

**Cavity wall inspection camera (endoscope) — £50–150**
A small flexible camera inserted through a 12mm drill hole at high level in the external wall confirms whether cavity wall insulation is present and its current condition — settled, absent in sections, or saturated. This resolves the ambiguity that a thermal image creates (missing insulation or structural element?) and provides unambiguous evidence for or against a CWI recommendation. A drill, the camera, and a matching filler plug is a complete kit.

---

### Structured Additional Services — Commercial Packaging

The activities above bundle naturally into tiered offerings beyond the basic EPC:

**Enhanced EPC — £50–80 additional**
Standard RdSAP plus thermal imaging walkround, loft depth probe, moisture meter check, and CO₂/humidity snapshot. Produces a report with photographic evidence of the specific elements driving the EPC score and the improvement recommendations. Directly feeds the pre-screening framework for U-value measurement and blower door decisions described in this guide.

**Heating system health check — £40–60 additional**
Flue gas analysis, radiator sizing calculation, system pressure check, and flow temperature verification. Produces a boiler efficiency reading, a COP projection for heat pump replacement at current radiator sizes, and an indicative heat pump feasibility verdict. Natural referral to an MCS installer.

**Indoor environment report — £30–50 additional**
CO₂, humidity, temperature, and CO readings at multiple points in the property, with a plain-English interpretation. Flags ventilation failures, condensation risk zones, and any CO concern. Stands alone as a health and comfort report and is particularly valuable for landlords ahead of the anticipated minimum EPC C requirement for the private rented sector.

**Retrofit readiness pack — £80–120 additional**
Combines enhanced EPC, cavity wall endoscope inspection, moisture mapping, and solar PV and EV charger suitability assessment. Produces a prioritised list of improvement measures with indicative costs, savings, and payback periods — a light-touch retrofit assessment bridging the gap between an EPC and a full PAS 2035 assessment.

---

### Connection to This System

The EPC visit is the natural point at which to enrol the property in continuous smart meter monitoring. The assessor can confirm smart meter type and connectivity, enable half-hourly data sharing, install the indoor temperature sensor (a five-minute task), and explain what the system will do over the following months.

The EPC score becomes the baseline; the system then tracks whether actual performance matches the certificate and flags when professional investigation is warranted. This creates a recurring relationship between the assessor and the property rather than a one-off transaction — the assessor becomes the natural referral point when the system recommends a U-value measurement, a blower door test, a boiler service, or a heat pump feasibility assessment. The smart meter analytics effectively extend the assessor's professional reach into the property between visits, creating a continuous monitoring and referral service built on top of the initial EPC.

---

## Value-Added Activities for Landlords and HMOs

The features described in this document are written primarily for owner-occupiers. For landlords — particularly those managing Houses in Multiple Occupation (HMOs) or similar multi-tenancy properties — the value proposition shifts. Landlords pay for the boiler, insulation, and EPC compliance; tenants pay the energy bills. The strongest applications are therefore the **compliance and risk track** rather than the cost-saving track, which accrues to tenants unless energy costs are bundled into inclusive rent.

---

### Regulatory Compliance (Most Urgent Driver)

**Indoor environment report** — The most immediately relevant commercial offering for landlords ahead of the anticipated minimum EPC C requirement for the private rented sector. CO₂, humidity, temperature, and CO readings across a multi-room property address Awaab's Law obligations (damp and mould duty of care), CO detector requirements, and ventilation failures that a standard EPC does not capture. Packaged as a landlord compliance report, this is a distinct chargeable service from the EPC itself.

**Living EPC — Feature 13b** — Monthly-updated EPC band derived from real measurement rather than a one-off certificate. Landlords managing a portfolio can track which properties are drifting toward non-compliance before a formal reassessment triggers enforcement action. A portfolio dashboard showing band trends across multiple properties would be a natural extension.

---

### Vacant Property Risk Management

**Feature 10 — Frost alerts for vacant properties** — The alert logic is designed explicitly for unoccupied properties: no heating activity detected for 12 hours combined with a sub-2°C overnight forecast fires an alert; below -3°C the alert is marked critical (pipe burst risk within hours). This is directly valuable between tenancies and during void periods, when a burst pipe creates an insurance claim, loss of rental income, and potential damage to neighbouring units in a converted building.

**Feature 11 — Vacancy-aware anomaly suppression** — Unexpected gas or electricity activity in a confirmed-empty property triggers a high-priority alert. For a landlord managing multiple properties remotely, this provides early warning of a break-in or appliance fault without requiring a physical visit.

---

### Multi-Room Diagnostics

**Multiple indoor temperature sensors** — In an HMO with individual lettable rooms, per-room sensors enable condition monitoring at room level. The document notes that a room decaying significantly faster than others during a free-cooling event indicates failed or missing insulation in a specific wall section. This directs repair spend precisely rather than triggering a whole-building survey, and produces a timestamped evidence record relevant to disrepair defences.

**Humidity sensors and mould alerts** — Relative humidity exceeding 70% in a cold room is a leading indicator of mould formation, typically preceding visible damage by several weeks. For landlords, early detection with a timestamped data trail is both a practical intervention and a legal protection. Post-retrofit humidity monitoring is particularly important after solid wall insulation installation, where interstitial condensation is a known failure mode.

**Smart TRVs** — In a shared property where tenants control individual rooms, smart TRVs give the landlord visibility of heating distribution without intruding on tenants' usage. A room that consistently fails to reach the setpoint despite the boiler running indicates a radiator fault, sludge, or imbalance — problems the landlord is responsible for but would not otherwise detect until a complaint.

---

### Portfolio Efficiency

**Feature 6 — Peer benchmarking** — Compares each property against similar type and build-era properties from national data. A landlord with a portfolio of similar terraced houses can rank them by normalised heating efficiency and prioritise insulation spend on the worst performers, rather than applying upgrades uniformly regardless of baseline condition.

**Feature 5 — Boiler efficiency trending** — Alerts to gradual or sudden efficiency decline before breakdown. In a rented property the landlord bears the replacement cost; earlier detection reduces emergency call-out costs and avoids tenant complaints or claims arising from loss of heating.

**Retrofit readiness pack** — Produces a prioritised list of improvement measures with indicative costs, savings, and payback periods for each property. For landlords planning EPC C upgrades across a portfolio or seeking ECO4 funding, this is a structured briefing document that avoids commissioning a full PAS 2035 assessment for every property before knowing which measures are worth pursuing.

---

### The Split Incentive Problem

The central challenge for landlord-facing services is that most energy cost savings from this system flow to tenants, not landlords. The exceptions are:

- **Boiler and fabric maintenance** — avoided replacement and repair costs accrue to the landlord
- **Void period risk** — frost damage and appliance faults during vacant periods are the landlord's liability
- **Compliance risk** — EPC non-compliance, damp and mould claims, and CO incidents are the landlord's legal exposure
- **All-inclusive tenancies** — where energy is bundled into rent, consumption savings directly improve landlord margin

For standard assured shorthold tenancies where tenants pay their own bills, the landlord pitch is built on compliance, risk mitigation, and asset protection rather than energy cost reduction. Services priced and marketed on that basis — particularly the indoor environment report and the living EPC — are the most natural fit for the private rented sector.

---

## Value-Added Services for Property Sellers

The seller's situation is the reverse of the landlord's. Where a landlord faces a split incentive — improvements benefit tenants, not them — a seller benefits directly from anything that increases buyer confidence, widens the buyer pool, or justifies a higher asking price. Energy performance shifts from a compliance burden to a marketing asset.

---

### Green Mortgage Eligibility — Feature 13d

The most commercially significant angle. Feature 13d generates a structured evidence package of measured fabric performance. If the property qualifies for a green mortgage (typically EPC B or above, or demonstrably strong measured performance), a buyer can access a preferential rate — typically 0.1–0.2% below standard. On a £300,000 mortgage over 25 years, that difference is worth £5,000–10,000 to the buyer.

A seller who can hand a buyer pre-assembled green mortgage evidence — measured heat loss, living EPC band, retrofit verification — removes a significant friction from the buyer's decision and differentiates the property from comparable listings where the buyer would have to commission this themselves post-sale.

---

### Living EPC and Performance Gap — Features 13a and 13b

A standard EPC is a one-off snapshot that may be years old and relies heavily on age-band defaults. For many properties, the actual fabric performance is materially better than the certificate suggests — Feature 13a puts a pound figure on this gap.

For a seller, this is directly usable marketing material: "This property carries a D certificate, but 18 months of measured data shows it performs at the C/B boundary — here is the evidence." This widens the buyer pool (buyers filtering on EPC band), supports asking price, and preempts the buyer's surveyor flagging the EPC as a risk.

If the living EPC band (Feature 13b) is higher than the lodged certificate, the seller can choose to commission a formal RdSAP reassessment using the measured data as the basis — potentially achieving a band uplift before going to market.

---

### Transparent Running Costs — Features 1 and 6

Feature 1 produces an actual annual energy cost from real consumption history, not a modelled estimate. Feature 6 benchmarks the property against similar type and build-era properties. Together these give a buyer something an EPC cannot: verified running costs.

Packaged as a one-page energy profile — "this property cost £X to heat and power over the past 12 months, placing it in the top 30% of similar properties" — this addresses one of the most common buyer anxieties about older homes and removes an information asymmetry that otherwise favours the buyer in negotiation.

---

### Retrofit Roadmap — Features 2, 4, and Retrofit Readiness Pack

A buyer purchasing an older property faces uncertainty about what it will cost to upgrade. A seller who provides a pre-commissioned retrofit readiness pack — prioritised measures, indicative costs, payback periods, heat pump feasibility verdict, battery sizing — converts that uncertainty into a defined plan. The buyer sees not just what the property is today but what it can become and at what cost.

Feature 4 (heat pump feasibility including radiator sizing assessment) is particularly valuable: the most common single cause of heat pump installation underperformance is radiators sized for 70–80°C flow that cannot deliver at 45–50°C. A seller who has already done this analysis removes a risk that sophisticated buyers price into their offers.

---

### Enhanced EPC with Thermal Imaging

A thermal imaging walkround on a cold morning before marketing produces photographic evidence of where heat is and is not escaping. For a well-insulated property this is positive marketing material — images showing uniform exterior temperature, no cold spots at window frames, no missing insulation sections. For a property with known fabric issues it identifies them before a buyer's surveyor does, allowing the seller to either remedy them or price accordingly.

The Enhanced EPC (thermal imaging, loft depth probe, moisture check, CO₂ snapshot) packaged as a pre-marketing survey gives buyers and their solicitors a higher-quality information base, which can materially speed up conveyancing — relevant in chains where delays are costly.

---

### Indoor Environment History

Feature 14 (comfort vs cost) and the humidity and mould monitoring together produce a timestamped record of indoor conditions during occupation. A property with 12–24 months of recorded data showing consistently warm, dry, well-ventilated conditions addresses buyer concerns about damp and cold that are common in older housing stock and that a buyer cannot otherwise verify from a single viewing.

For a property that has passed through a cold winter without triggering any humidity or mould alerts, that record is a genuine asset. It is also a legal protection for the seller — documented evidence of conditions during ownership.

---

### Boiler Condition Record — Feature 5

Feature 5 trend data shows whether the boiler's efficiency has been stable, gradually declining, or experienced a step-change event. A seller who can demonstrate a flat efficiency trend over two heating seasons — with no degradation alerts — removes buyer risk around a hidden boiler problem and reduces the likelihood of a buyer using boiler age as a negotiating lever.

---

### The Seller's Pack

All of the above bundles naturally into a pre-marketing property energy pack:

| Document | Source | Value to buyer |
|---|---|---|
| Living EPC with performance gap | Features 13a/13b | Actual band vs certificate |
| Verified annual running costs | Features 1 and 6 | Removes cost uncertainty |
| Green mortgage evidence package | Feature 13d | Direct mortgage rate benefit |
| Retrofit roadmap | Features 2, 4, readiness pack | Defined upgrade pathway |
| Thermal image survey | Enhanced EPC | Visual fabric evidence |
| Indoor environment history | Features 14, humidity monitoring | Damp and comfort record |
| Boiler condition record | Feature 5 | Hidden maintenance risk removed |

The structural advantage for sellers over all other user types is that the cost of generating this evidence is borne by the seller, but the financial benefit — a wider buyer pool, a stronger asking price, and faster conveyancing — accrues directly to them. There is no split incentive. Every pound spent on pre-marketing energy evidence has a direct return through the sale.

---

## Value-Added Services for Property Buyers

The buyer occupies the opposite position to the seller. Where the seller uses energy evidence to support asking price, the buyer uses it to discover hidden costs, identify negotiating leverage, and plan what the property will actually cost to own and improve. The same tools serve opposite interests — and crucially, a buyer should commission independent assessment rather than relying solely on evidence provided by the seller.

---

### Pre-Purchase Due Diligence — Independent Fabric Assessment

The most important distinction for a buyer is independence. A seller's energy pack may be accurate, but it will not include anything that damages the seller's position. A buyer commissioning their own pre-purchase survey using the methods described in this guide gets an unfiltered picture.

**Thermal imaging walkround** — Conducted on a cold morning with the heating running, this reveals what neither a standard survey nor the EPC will show: specific sections of missing or failed cavity wall insulation, air leakage paths around window frames and loft hatches, thermal bridging at structural elements, and glazing failures. For a property where the seller claims CWI was installed, a thermal image either confirms it or shows the sections where it has settled or is absent. This cannot be hidden from an independent survey.

**Cavity wall endoscope inspection** — A 12mm drill hole at high level in the external wall gives a direct visual of whether cavity insulation is present and in good condition. Saturated or absent insulation in a property marketed as insulated is a significant defect and a direct negotiating point.

**Moisture meter readings** — Elevated moisture content in walls adjacent to a cavity insulation claim, or at ground floor level, indicates either a failing installation or rising damp. Neither will appear on an EPC. A reading above 20% at a CWI wall is a contraindication for the insulation's effectiveness and a likely future remediation cost.

**Flue gas analysis** — The actual combustion efficiency of the boiler on the day of the survey, not the manufacturer's rating or the SAP default. A boiler running at 78% efficiency rather than the assumed 89% represents approximately £120/year in additional gas costs. An old boiler running below 75% is a near-term replacement cost that should be reflected in the offer.

---

### Negotiating Leverage from Measured Evidence

Every significant discrepancy between what the EPC assumes and what measurement shows is a potential negotiating point:

**Performance gap working against the buyer** — If Feature 13a shows the property loses heat materially faster than the EPC predicts (a positive performance gap in the wrong direction), this is evidence the property is worse than certificated. The pound figure on the additional annual heating cost is a direct input to a price reduction argument: if the property costs £400/year more to heat than a comparable certificated property, a buyer can argue for a commensurate price adjustment.

**Boiler efficiency shortfall** — Flue gas analysis showing combustion efficiency 10+ percentage points below the SAP assumption quantifies an ongoing cost and a near-term capital replacement. A boiler quote obtained before exchange gives a concrete figure for renegotiation.

**Missing or failed insulation** — Thermal imaging or endoscope evidence of absent or degraded CWI, combined with the retrofit cost to remedy it, is a well-evidenced basis for price reduction or a seller contribution to works.

**Moisture and damp** — Elevated moisture readings in multiple locations, particularly where the property has been decorated recently, shift the burden of explanation to the seller and may warrant a specialist damp survey before exchange.

---

### Green Mortgage Eligibility

If the property qualifies for a green mortgage — typically requiring EPC B or above, or measured performance evidence meeting the lender's criteria — the buyer can access a preferential interest rate of approximately 0.1–0.2% below standard. On a £300,000 mortgage over 25 years this is worth £5,000–10,000 over the mortgage term.

Feature 13d generates a structured evidence package of measured fabric performance suitable for green mortgage applications. Where the seller has already produced this, the buyer should verify it with an independent assessment before relying on it in a mortgage application. Where the seller has not produced it, the buyer can commission it — potentially qualifying for a rate the seller was unaware was available.

If the living EPC band (Feature 13b) is demonstrably higher than the lodged certificate, the buyer may be able to qualify for a green mortgage on a property that would not qualify on its certificate alone — without waiting for a formal reassessment.

---

### Running Cost Verification

Feature 1 produces an actual annual energy cost from real consumption history. A seller who provides smart meter consumption data is offering something verifiable — the buyer can request the half-hourly data directly from the smart meter consent service and reproduce the calculation independently. This removes a common area of dispute: whether the seller's claimed running costs are based on actual usage or an optimistic estimate.

Feature 6 benchmarks the property against similar type and build-era properties. If the property is in the bottom quartile of its peer group for normalised heating efficiency, this is an early signal of either insulation failure or a heating system problem — either of which warrants further investigation before exchange.

---

### Upgrade Cost Planning

A buyer purchasing an older property needs to understand not just what it costs today but what it will cost to bring it to a satisfactory standard. The retrofit readiness pack provides a prioritised improvement plan with indicative costs and payback periods. Commissioned pre-purchase, this converts upgrade uncertainty — often the largest source of price negotiation disagreement — into a defined schedule that both buyer and seller can reference.

**Heat pump feasibility — Feature 4** — If the buyer intends to install a heat pump, the radiator sizing assessment is the critical pre-purchase check. Existing radiators sized for 70–80°C flow will underperform at the 45–50°C that a heat pump operates at efficiently. Discovering this before purchase allows the buyer to factor in radiator replacement costs; discovering it after installation is expensive. A pre-purchase feasibility verdict with a radiator audit takes 30 minutes on site.

**Battery and solar readiness** — EV charger readiness (driveway, consumer unit proximity, existing circuit), solar PV suitability (roof orientation, shading, available area), and battery storage space can all be assessed on a single pre-purchase visit and feed directly into the buyer's electrification budget.

---

### Post-Purchase Baseline

Commissioning a fabric assessment before moving in establishes a pre-occupation baseline that has two uses. First, it documents the condition of the property at the point of purchase — relevant if disputes arise with the seller about undisclosed defects. Second, it provides a measured starting point against which any subsequent retrofit improvements can be verified (Feature 13c), confirming that insulation, windows, or draught-proofing works have delivered the claimed improvement.

Establishing smart meter data sharing, installing an indoor temperature sensor, and running the system from day one means the buyer builds up a full heating season of data in their first winter — the fastest route to the living EPC, the performance gap analysis, and the boiler efficiency trending that require a season of data to initialise.

---

### The Buyer's Pre-Purchase Survey Pack

| Assessment | Method | Buyer's purpose |
|---|---|---|
| Independent thermal imaging | Enhanced EPC on buyer's instruction | Identify insulation defects not in seller's pack |
| Cavity wall endoscope | Endoscope inspection | Confirm or challenge CWI claims |
| Moisture mapping | Pin moisture meter | Identify damp risk before exchange |
| Boiler efficiency reading | Flue gas analysis | Quantify replacement risk |
| Fabric performance vs EPC | Feature 13a pre-screening | Identify if property underperforms certificate |
| Running cost verification | Feature 1 from independent data request | Verify seller's cost claims |
| Peer benchmarking | Feature 6 | Flag heating efficiency outliers |
| Green mortgage eligibility | Feature 13d assessment | Qualify for preferential rate |
| Retrofit cost plan | Retrofit readiness pack | Convert upgrade uncertainty to defined budget |
| Radiator sizing for heat pump | Feature 4 radiator audit | Identify hidden electrification cost |

The buyer's structural advantage is timing: all of this information is available before contracts are exchanged. A buyer who commissions independent pre-purchase assessment enters negotiation with the same quality of evidence the seller holds — or better, if the seller's pack was incomplete. The cost of a comprehensive pre-purchase energy survey is modest relative to the purchase price and the potential for a price reduction or the avoidance of a costly post-purchase surprise.
