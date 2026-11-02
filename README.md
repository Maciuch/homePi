# homePi

Raspberry Pi (`192.168.1.246`) boiler-room steering and telemetry publisher for Home Assistant (`192.168.1.49`).

## Hardware
- **Controller**: Raspberry Pi Revision B with Gertboard I/O and relay modules
- **Temperature Sensors**: 7× DS18B20 1-Wire probes (`/sys/bus/w1/devices/28-*`)
- **Power Meters**: Orno / impulse electricity counters (`1000 imp/kWh` and `800 imp/kWh` for solar PV)

---

## DS18B20 1-Wire Sensor Map

| Sensor ID | Location | Height | MQTT Topic |
| :--- | :--- | :---: | :--- |
| `28-00000bedd00d` | Water Heater **Point N** (Top zone) | `1340 mm` (84%) | `homeassistant/number/water_heater_top_n_temp` |
| `28-00000bec9d24` | Water Heater **Point J** (Upper-Mid / CWU coil) | `815 mm` (51%) | `homeassistant/number/water_heater_upper_mid_j_temp` |
| `28-00000bed4c93` | Water Heater **Point E** (Lower-Mid / Solar upper) | `445 mm` (28%) | `homeassistant/number/water_heater_lower_mid_e_temp` |
| `28-00000bedc62e` | Water Heater **Point C** (Bottom / Solar pocket) | `275 mm` (17%) | `homeassistant/number/water_heater_bottom_c_temp` |
| `28-00000bec9e52` | **Heat Pump 2 Outlet** (CWU coil supply `K`) | `1060 mm` | `homeassistant/number/heat_pump_2_outlet_temp` |
| `28-00000becad1f` | **Heat Pump 2 Inlet** (CWU coil return `I`) | `675 mm` | `homeassistant/number/heat_pump_2_inlet_temp` |
| `28-000003b7ff50` | **Solar Collector Return** (Solar coil `F/B`) | `545 / 225 mm` | `homeassistant/number/solar_temp_powrot` |

---

## GPIO Pin Assignments

| BCM Pin | Direction | Function | Script |
| :---: | :---: | :--- | :--- |
| `GPIO 22` | `OUT` | 3 kW Water Heater Electric Heater Relay (`G = 605 mm`) | `CWU_Recirculation/recyrkulacja_cron.py` |
| `GPIO 25` | `OUT` | Hot Water Recirculation Pump (`O [1600 mm] -> A [225 mm]`) | `CWU_Recirculation/recyrkulacja_cron.py` |
| `GPIO 23` | `OUT` | Rekuperator Gear 2 Relay | `Rekuperator/rekuperator.py` |
| `GPIO 24` | `OUT` | Rekuperator Gear 3 / Gear 1 Relay | `Rekuperator/rekuperator.py` |
| `GPIO 14` | `IN (IRQ)` | Water Heater Power Meter (`1000 imp/kWh`) | `Power_Counters/pwrMeters.py` |
| `GPIO 15` | `IN (IRQ)` | House Master Power Meter (`1000 imp/kWh`) | `Power_Counters/pwrMeters.py` |
| `GPIO 17` | `IN (IRQ)` | Heat Pump 1 Power Meter (`1000 imp/kWh`) | `Power_Counters/pwrMeters.py` |
| `GPIO 7` | `IN (IRQ)` | Solar PV Power Meter (`800 imp/kWh`) | `Power_Counters/pwrMeters.py` |

---

## Components

- **`CWU_Recirculation/recyrkulacja_cron.py`** *(runs every minute via cron)*:
  - Reads all 4 DS18B20 water heater probes (`N`, `J`, `E`, `C`) using an exclusive file lock (`/tmp/w1_bus.lock`) to prevent 1-Wire bus collisions.
  - Minimizes 3 kW electric heater (`GPIO 22`) operation by prioritizing **Heat Pump 2** (`CWU coil 675–1060 mm`), activating the electric booster only if both `N (1340 mm)` and `J (815 mm)` drop below Heat Pump 2's normal operating band (`N < 43 °C` & `J < 40 °C` in G12 off-peak tariff `T2`; `N < 38 °C` & `J < 36 °C` emergency backup in peak tariff `T1`).
  - Controls the external recirculation pump (`GPIO 25`, `O -> A`) for solar thermal bottom-up heat harvesting ($\max(T_E, T_C) > T_J + 4\,^\circ\text{C}$) and off-peak surplus top-down heat transfer ($T_N > 50\,^\circ\text{C} \land T_J > 49\,^\circ\text{C}$).
  - Persists relay hysteresis state in `/tmp/cwu_state.json` and publishes all sensor values and states to Home Assistant via MQTT.
- **`CO/co_cron.py`** *(runs every minute via cron)*:
  - Reads `solar_temp_powrot`, `heat_pump_2_inlet_temp`, and `heat_pump_2_outlet_temp` (synchronized via `/tmp/w1_bus.lock`) and publishes to MQTT.
- **`Power_Counters/pwrMeters.py`** *(daemon started via `/etc/rc.local`)*:
  - Interrupt-driven pulse period measurement for real-time power (`kW`) publishing to Home Assistant via MQTT.
- **`Rekuperator/rekuperator.py`** *(daemon started via `/etc/rc.local`)*:
  - Subscribes to `rekuperator/gear` on MQTT and switches ventilation speed relays (`GPIO 23`, `GPIO 24`).
