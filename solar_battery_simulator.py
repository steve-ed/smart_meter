def simulate_day_solar(
    consumption_hh,
    tariff_hh,
    solar_hh,
    battery_capacity_kwh,
    round_trip_efficiency=0.92,
    max_c_rate=0.5,
    min_soc=0.20,
    export_rate_p=15.0,
    max_soc=1.0,
):
    """
    Simulate one day of solar + battery dispatch across 48 half-hourly slots.

    Dispatch priority per slot:
      1. Solar offsets consumption (self-consumption)
      2. Surplus solar charges battery (up to C-rate)
      3. Remaining surplus exported at export_rate_p
      4. Off-peak: grid tops up battery with remaining C-rate capacity
      5. Peak: battery discharges to cover net load (after solar offset)
      6. Grid covers any remaining net load

    Args:
        consumption_hh:       list[48] kWh consumed per half-hour
        tariff_hh:            list[48] p/kWh for each half-hour
        solar_hh:             list[48] kWh generated per half-hour
        battery_capacity_kwh: usable battery capacity in kWh
        round_trip_efficiency: fraction of charged energy delivered (default 0.92)
        max_c_rate:           max charge/discharge as fraction of capacity per hour
        min_soc:              minimum state of charge as fraction of capacity
        export_rate_p:        p/kWh received for exported solar

    Returns:
        dict with keys:
            daily_saving_p          — net saving vs no-solar no-battery baseline (pence)
            solar_self_consumed_kwh — solar directly offsetting consumption
            solar_exported_kwh      — solar sent to grid
            peak_kwh_displaced      — energy delivered from battery at peak
    """
    off_peak_rate = min(tariff_hh)
    peak_rate = max(tariff_hh)
    max_hh_kwh = battery_capacity_kwh * max_c_rate * 0.5
    min_energy = battery_capacity_kwh * min_soc
    max_energy = battery_capacity_kwh * max_soc

    soc = min_energy
    baseline_cost_p = sum(c * r for c, r in zip(consumption_hh, tariff_hh))
    grid_cost_p = 0.0
    export_revenue_p = 0.0
    total_self_consumed = 0.0
    total_exported = 0.0
    total_peak_displaced = 0.0

    for i in range(48):
        rate = tariff_hh[i]
        solar = solar_hh[i]
        consumption = consumption_hh[i]

        # 1. Solar self-consumption
        self_consumed = min(solar, consumption)
        surplus_solar = solar - self_consumed
        net_load = consumption - self_consumed
        total_self_consumed += self_consumed

        # 2. Surplus solar charges battery
        charge_from_solar = 0.0
        if surplus_solar > 0 and battery_capacity_kwh > 0:
            space = max_energy - soc
            charge_from_solar = min(max_hh_kwh, space, surplus_solar)
            soc += charge_from_solar
            surplus_solar -= charge_from_solar

        # 3. Remaining surplus exported
        total_exported += surplus_solar
        export_revenue_p += surplus_solar * export_rate_p

        # 4 & 5: off-peak grid charges OR peak battery discharges (mutually exclusive)
        if rate <= off_peak_rate and battery_capacity_kwh > 0:
            remaining_c_rate = max_hh_kwh - charge_from_solar
            space = max_energy - soc
            charge_from_grid = min(remaining_c_rate, space)
            soc += charge_from_grid
            net_load += charge_from_grid
        elif rate >= peak_rate and battery_capacity_kwh > 0 and net_load > 0:
            available = soc - min_energy
            draw = min(max_hh_kwh, available, net_load / round_trip_efficiency)
            draw = max(0.0, draw)
            soc -= draw
            delivered = draw * round_trip_efficiency
            net_load -= delivered
            total_peak_displaced += delivered

        # 6. Grid covers remaining net load
        grid_cost_p += max(0.0, net_load) * rate

    saving_p = baseline_cost_p - grid_cost_p + export_revenue_p

    return {
        "daily_saving_p": saving_p,
        "solar_self_consumed_kwh": total_self_consumed,
        "solar_exported_kwh": total_exported,
        "peak_kwh_displaced": total_peak_displaced,
    }
