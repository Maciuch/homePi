#!/usr/bin/env python

import fcntl
import glob
import time
import datetime
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

mqtt_broker_ip = "192.168.1.49"
mqtt_broker_port = 1883
haauth = {"username": "mqttuser", "password": "asdsa11"}
base_dir = "/sys/bus/w1/devices/"
#bufor_gora = "28-000003b81329"
#bufor_dol  = "28-000003b83a37"
solar               = "28-000003b7ff50"
heat_pump_2_inlet   = "28-00000becad1f"
heat_pump_2_outlet  = "28-00000bec9e52"

# Water heater 300L sensors (read and published in /home/pi/CWU_recyrkulacja/recyrkulacja_cron.py):
water_heater_top_n       = "28-00000bedd00d"  # Point N (1340 mm) - Top
water_heater_upper_mid_j = "28-00000bec9d24"  # Point J (815 mm)  - Upper-Mid
water_heater_lower_mid_e = "28-00000bed4c93"  # Point E (445 mm)  - Lower-Mid
water_heater_bottom_c    = "28-00000bedc62e"  # Point C (275 mm)  - Bottom

def read_temp_raw(device):
    device_folder = glob.glob(base_dir + device)[0]
    device_file = device_folder + "/w1_slave"
    with open(device_file, "r") as f:
        return f.readlines()

def read_temp(device):
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
    b_g = 0
    b_d = 0
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
        {"topic": "homeassistant/number/buffer_bottom_temp", "payload": b_d},
        ("homeassistant/number/buffer_top_temp", b_g, 0, False),
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
