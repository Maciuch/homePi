#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Water Heater (300L TWIN SOLAR) & Recirculation Steering Script.

Runs every minute via cron on the boiler-room Raspberry Pi (192.168.1.246).
Reads 4 DS18B20 1-Wire temperature sensors along the vertical profile of the
300L tank, steers the 3 kW backup electric heater (GPIO 22) and external
recirculation pump (GPIO 25), and publishes telemetry to Home Assistant via MQTT.

DS18B20 1-Wire Water Heater (300L TWIN SOLAR) sensors:
- N (1340 mm, 84% height - Top):        28-00000bedd00d
- J (815 mm,  51% height - Upper-Mid):  28-00000bec9d24
- E (445 mm,  28% height - Lower-Mid):  28-00000bed4c93
- C (275 mm,  17% height - Bottom):     28-00000bedc62e
"""

import fcntl
import json
import os
import RPIO
import glob
import time
import datetime
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

mqtt_broker_ip = "192.168.1.49"
mqtt_broker_port = 1883
haauth = {"username": "mqttuser", "password": "asdsa11"}
base_dir = "/sys/bus/w1/devices/"
state_file = "/tmp/cwu_state.json"

water_heater_top_n       = "28-00000bedd00d"  # Point N (1340 mm) - Top
water_heater_upper_mid_j = "28-00000bec9d24"  # Point J (815 mm)  - Upper-Mid (CWU coil)
water_heater_lower_mid_e = "28-00000bed4c93"  # Point E (445 mm)  - Lower-Mid (Solar coil upper)
water_heater_bottom_c    = "28-00000bedc62e"  # Point C (275 mm)  - Bottom (Solar pocket above inlet A)

pinRec = 25
pinHeater = 22
RPIO.setwarnings(False)


def load_prev_state():
    """
    Load the previous relay states (electric heater and recirculation pump)
    from a temporary JSON file so hysteresis bands are preserved across
    1-minute cron invocations.

    Returns:
        tuple[str, str]: (heater_state, pump_state), each "ON" or "OFF".
    """
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                data = json.load(f)
                return data.get("heater", "OFF"), data.get("pump", "OFF")
    except Exception:
        pass
    return "OFF", "OFF"


def save_state(heater_state, pump_state):
    """
    Persist the current relay states ("ON" or "OFF") and timestamp to disk
    for use by the next cron invocation.

    Args:
        heater_state (str): Current state of the 3 kW electric heater ("ON" / "OFF").
        pump_state (str): Current state of the recirculation pump ("ON" / "OFF").
    """
    try:
        with open(state_file, "w") as f:
            json.dump({"heater": heater_state, "pump": pump_state, "ts": time.time()}, f)
    except Exception:
        pass


def read_temp_raw(device):
    """
    Read raw lines from the Linux 1-Wire sysfs slave file for a DS18B20 sensor.

    Args:
        device (str): 1-Wire sensor folder ID (e.g. "28-00000bedd00d").

    Returns:
        list[str]: Two-line raw output from /sys/bus/w1/devices/<device>/w1_slave.
    """
    device_folder = glob.glob(base_dir + device)[0]
    device_file = device_folder + "/w1_slave"
    with open(device_file, "r") as f:
        return f.readlines()


def read_temp(device):
    """
    Parse the temperature in degrees Celsius from a DS18B20 1-Wire sensor.
    Retries up to 5 times if the 1-Wire CRC check ("YES") has not succeeded yet.

    Args:
        device (str): 1-Wire sensor folder ID (e.g. "28-00000bedd00d").

    Returns:
        float: Measured temperature in deg C.

    Raises:
        RuntimeError: If the sensor fails CRC verification after 5 attempts.
    """
    for _ in range(5):
        lines = read_temp_raw(device)
        if lines and lines[0].strip()[-3:] == "YES":
            equals_pos = lines[1].find("t=")
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                return float(temp_string) / 1000.0
        time.sleep(0.2)
    raise RuntimeError("Failed to read 1-Wire sensor: " + device)


def is2ndTariff():
    """
    Check whether the current local time falls within the cheaper G12 off-peak
    electricity tariff windows:
    - Daytime off-peak window: 13:00 to 15:00
    - Nighttime off-peak window: 22:00 to 06:00

    Returns:
        bool: True if currently in 2nd (off-peak) tariff, False in 1st (peak) tariff.
    """
    now = time.localtime()
    return (now.tm_hour >= 13 and now.tm_hour < 15) or (now.tm_hour >= 22 or now.tm_hour < 6)


def main():
    """
    Main 1-minute control loop:
    1. Acquires an exclusive lock (/tmp/w1_bus.lock) and reads all 4 water heater
       DS18B20 sensors (N, J, E, C).
    2. Evaluates 3 kW electric heater steering (GPIO 22) with priority given to
       Heat Pump 2 (CWU coil at 675-1060 mm), activating the electric booster
       only if both upper sensors (N and J) fall below threshold.
    3. Evaluates external recirculation loop steering (GPIO 25, O -> A) for
       bottom-up solar heat harvesting or off-peak surplus top heat transfer.
    4. Updates GPIO outputs, saves hysteresis state, and publishes all sensor
       readings and states to Home Assistant via MQTT.
    """
    prev_heater, prev_pump = load_prev_state()

    # Acquire exclusive lock so concurrent cron scripts do not collide on the 1-Wire bus
    lock_file = open("/tmp/w1_bus.lock", "w")
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    try:
        t_top_n       = read_temp(water_heater_top_n)
        t_upper_mid_j = read_temp(water_heater_upper_mid_j)
        t_lower_mid_e = read_temp(water_heater_lower_mid_e)
        t_bottom_c    = read_temp(water_heater_bottom_c)
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

    # 1. Electric Heater Steering (pinHeater = 22, located at G = 605 mm)
    # Heat Pump 2 heats the CWU coil (675-1060 mm, sensor J = 815 mm & top N = 1340 mm) to 45-48.5 C at COP ~3.
    # Do NOT trigger electric heater from E (445 mm) or C (275 mm) cooling, because E & C sit below the CWU coil.
    # Only use the 3 kW electric heater as a booster when BOTH N (1340 mm) and J (815 mm) drop below HP2 operating range.
    if is2ndTariff():
        if t_top_n < 43.0 and t_upper_mid_j < 40.0:
            heaterState = "ON"
        elif t_top_n >= 46.0 or t_upper_mid_j >= 43.0 or t_lower_mid_e >= 38.0:
            heaterState = "OFF"
        else:
            heaterState = prev_heater
    else:
        # 1st Tariff (Peak): emergency backup only if upper hot water reserve (N & J) is genuinely depleted
        if t_top_n < 38.0 and t_upper_mid_j < 36.0:
            heaterState = "ON"
        elif t_top_n >= 41.0 or t_upper_mid_j >= 39.0:
            heaterState = "OFF"
        else:
            heaterState = prev_heater

    # 2. Recirculation Steering (pinRec = 25, external loop O [1600 mm] -> A [225 mm])
    # - Solar harvest (any tariff): if solar coil heats bottom/lower-mid (E or C) >4 C above J (815 mm), circulate bottom-up.
    # - Surplus top heat transfer (2nd tariff only): if top & upper-mid are >50 C / >49 C and lower-mid E < 42 C,
    #   transfer surplus heat down until J drops to 46 C or E reaches 45 C or C reaches 40 C.
    solar_bottom_hot = max(t_lower_mid_e, t_bottom_c) > (t_upper_mid_j + 4.0)
    solar_equalized  = max(t_lower_mid_e, t_bottom_c) <= (t_upper_mid_j + 1.5)

    if solar_bottom_hot:
        pumpState = "ON"
    elif is2ndTariff():
        if t_top_n > 50.0 and t_upper_mid_j > 49.0 and t_lower_mid_e < 42.0:
            pumpState = "ON"
        elif (t_upper_mid_j < 46.0 or t_top_n < 47.0 or t_lower_mid_e >= 45.0 or t_bottom_c >= 40.0) and solar_equalized:
            pumpState = "OFF"
        else:
            pumpState = prev_pump
    else:
        if solar_equalized:
            pumpState = "OFF"
        else:
            pumpState = prev_pump

    # Drive GPIO relay outputs without resetting pin state during setup
    RPIO.setup(pinHeater, RPIO.OUT, initial=(RPIO.HIGH if heaterState == "ON" else RPIO.LOW))
    RPIO.output(pinHeater, heaterState == "ON")

    RPIO.setup(pinRec, RPIO.OUT, initial=(RPIO.HIGH if pumpState == "ON" else RPIO.LOW))
    RPIO.output(pinRec, pumpState == "ON")

    save_state(heaterState, pumpState)

    # Publish all temperatures and binary states to Home Assistant MQTT broker
    msgs = [
        {"topic": "homeassistant/number/water_heater_top_n_temp", "payload": t_top_n, "retain": True},
        {"topic": "homeassistant/number/water_heater_upper_mid_j_temp", "payload": t_upper_mid_j, "retain": True},
        {"topic": "homeassistant/number/water_heater_lower_mid_e_temp", "payload": t_lower_mid_e, "retain": True},
        {"topic": "homeassistant/number/water_heater_bottom_c_temp", "payload": t_bottom_c, "retain": True},
        # Legacy topics kept for backward compatibility
        {"topic": "homeassistant/number/water_heater_top_temp", "payload": t_upper_mid_j, "retain": True},
        {"topic": "homeassistant/number/water_heater_bottom_temp", "payload": t_lower_mid_e, "retain": True},
        {"topic": "homeassistant/binary_sensor/heater_state", "payload": heaterState, "retain": True},
        {"topic": "homeassistant/binary_sensor/hot_water_recirculation", "payload": pumpState, "retain": True},
    ]
    publish.multiple(
        msgs,
        hostname=mqtt_broker_ip,
        port=mqtt_broker_port,
        client_id="",
        keepalive=60,
        will=None,
        auth=haauth,
        tls=None,
        protocol=mqtt.MQTTv311,
    )


main()
