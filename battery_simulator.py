def simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh,
                 round_trip_efficiency=0.90, max_c_rate=0.5, min_soc=0.20):
    """
    Simulate one day of battery arbitrage across 48 half-hourly slots.

    Charges at the lowest rate in tariff_hh; discharges at the highest.
    Saving formula accounts for round-trip losses:
        saving_p = delivered * (peak_rate - (off_peak_rate / efficiency))

    Args:
        consumption_hh: list of 48 floats, kWh consumed per half-hour
        tariff_hh:      list of 48 floats, p/kWh for each half-hour
        battery_capacity_kwh: usable capacity in kWh
        round_trip_efficiency: fraction of charged energy delivered (default 0.90)
        max_c_rate:     max charge/discharge as fraction of capacity per hour (default 0.5)
        min_soc:        minimum state of charge as fraction of capacity (default 0.20)

    Returns:
        dict with keys:
            daily_saving_p      — net saving in pence
            charge_cycled_kwh   — total energy put into battery
            peak_kwh_displaced  — total energy delivered to home from battery
    """
    off_peak_rate = min(tariff_hh)
    peak_rate = max(tariff_hh)
    max_hh_kwh = battery_capacity_kwh * max_c_rate * 0.5
    min_energy = battery_capacity_kwh * min_soc

    soc = min_energy
    total_delivered = 0.0
    charge_cycled = 0.0

    for i in range(48):
        rate = tariff_hh[i]
        if rate <= off_peak_rate:
            space = battery_capacity_kwh - soc
            charge = min(max_hh_kwh, space)
            soc += charge
            charge_cycled += charge
        elif rate >= peak_rate:
            available = soc - min_energy
            # draw enough from battery to deliver consumption_hh[i] kWh to home,
            # accounting for round-trip losses; cap at C-rate and available energy
            draw = min(max_hh_kwh, available,
                       consumption_hh[i] / round_trip_efficiency)
            draw = max(0.0, draw)
            soc -= draw
            total_delivered += draw * round_trip_efficiency

    # Net saving: avoided peak cost minus extra off-peak charging cost (per kWh delivered)
    saving_p = total_delivered * (peak_rate - off_peak_rate / round_trip_efficiency)

    return {
        "daily_saving_p": saving_p,
        "charge_cycled_kwh": charge_cycled,
        "peak_kwh_displaced": total_delivered,
    }
