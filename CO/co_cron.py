#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Central Heating (C.O.), Heat Pump 2 CWU Coil & Solar Return Telemetry Script.

Runs every minute via cron on the boiler-room Raspberry Pi (192.168.1.246).
Reads the DS18B20 1-Wire temperature probes on the solar collector return pipe
and Heat Pump 2 inlet/outlet pipes connected to the CWU coil, and publishes
their values to Home Assistant via MQTT.
"""

import fcntl
import glob
import time
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

mqtt_broker_ip = "192.168.1.49"
mqtt_broker_port = 1883
haauth = {"username": "mqttuser", "password": "asdsa11"}
base_dir = "/sys/bus/w1/devices/"

solar               = "28-000003b7ff50"  # Solar collector return pipe sensor
heat_pump_2_inlet   = "28-00000becad1f"  # Heat Pump 2 return (CWU coil lower port I = 675 mm)
heat_pump_2_outlet  = "28-00000bec9e52"  # Heat Pump 2 supply (CWU coil upper port K = 1060 mm)


def read_temp_raw(device):
    """
    Read raw lines from the Linux 1-Wire sysfs slave file for a DS18B20 sensor.

    Args:
        device (str): 1-Wire sensor folder ID (e.g. "28-000003b7ff50").

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
        device (str): 1-Wire sensor folder ID.

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


def main():
    """
    Acquire the 1-Wire bus lock (/tmp/w1_bus.lock), read the solar return and
    Heat Pump 2 inlet/outlet DS18B20 temperatures, and publish them to MQTT.
    """
    lock_file = open("/tmp/w1_bus.lock", "w")
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    try:
        s_t  = read_temp(solar)
        hp2i = read_temp(heat_pump_2_inlet)
        hp2o = read_temp(heat_pump_2_outlet)
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

    msgs = [
        ("homeassistant/number/solar_temp_powrot", s_t, 0, False),
        ("homeassistant/number/heat_pump_2_inlet_temp", hp2i, 0, False),
        ("homeassistant/number/heat_pump_2_outlet_temp", hp2o, 0, False),
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
