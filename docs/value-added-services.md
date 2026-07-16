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

---

## Recommended Starting Point

**#2 Vacancy-aware anomaly suppression** — occupancy context directly improves the existing anomaly detector, reducing alert fatigue before adding new features on top.
