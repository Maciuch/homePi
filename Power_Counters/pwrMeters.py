#!/usr/bin/env python
"""
Impulse Electricity Meter Daemon (pwrMeters.py).

Runs continuously as a background daemon started from /etc/rc.local.
Listens for falling-edge GPIO interrupts from 4 impulse electricity meters
(Orno / DIN-rail counters) and computes instantaneous active power (kW) from
the time elapsed between consecutive pulses:
- 1000 imp/kWh meters (Water Heater, Master House, Heat Pump 1):
    P [kW] = 3600 [s/h] / (1000 [imp/kWh] * delta_t [s]) = 3.6 / delta_t
- 800 imp/kWh meter (Solar PV):
    P [kW] = 3600 [s/h] / (800 [imp/kWh] * delta_t [s])  = 4.5 / delta_t

If no pulse is received within the timeout window (60s for loads, 120s for
solar PV), the daemon publishes 0 kW to reset the sensor in Home Assistant.
"""

import RPIO
import glob
import time
import datetime
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

mqtt_broker_ip = "192.168.1.49"
mqtt_broker_port = 1883
haauth = {"username": "mqttuser", "password": "asdsa11"}

# BCM GPIO pin assignments for impulse inputs
pinWaterHeater = 14  # 3 kW Water Heater electric element meter (1000 imp/kWh)
pinMasterPower = 15  # Main house electricity meter (1000 imp/kWh)
pinHeatPump    = 17  # Heat Pump 1 electricity meter (1000 imp/kWh)
pinSolar       = 7   # Solar PV inverter generation meter (800 imp/kWh)

# Timestamps of the most recent pulse on each channel
p1 = datetime.datetime.now()
p2 = datetime.datetime.now()
p3 = datetime.datetime.now()
p4 = datetime.datetime.now()


def gpio_callback(gpio_id, value):
    """
    GPIO falling-edge interrupt callback triggered each time an electricity
    meter emits an impulse.

    Calculates instantaneous power in kW from the inter-pulse interval (delta),
    filters out spurious contact-bounce spikes above the circuit breaker rating,
    and publishes the reading to Home Assistant via MQTT.

    Args:
        gpio_id (int): BCM GPIO pin number that triggered the interrupt.
        value (int): Pin logic level after the edge (0 for falling edge).
    """
    global p1, p2, p3, p4
    now = datetime.datetime.now()
    if gpio_id == pinWaterHeater:
        delta = now - p1
        cPwr = 3.6 / delta.total_seconds()
        p1 = now
        if cPwr < 5:
            try:
                publish.single(
                    "homeassistant/number/water_heater_power",
                    cPwr,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )
            except Exception:
                pass

    elif gpio_id == pinMasterPower:
        delta = now - p2
        cPwr = 3.6 / delta.total_seconds()
        p2 = now
        if cPwr < 20:
            try:
                publish.single(
                    "homeassistant/number/house_power_consumption",
                    cPwr,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )
            except Exception:
                pass

    elif gpio_id == pinHeatPump:
        delta = now - p3
        cPwr = 3.6 / delta.total_seconds()
        p3 = now
        if cPwr < 3:
            try:
                publish.single(
                    "homeassistant/number/heat_pump_1_power",
                    cPwr,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )
            except Exception:
                pass

    elif gpio_id == pinSolar:
        delta = now - p4
        cPwr = 4.5 / delta.total_seconds()  # 800 imp/kWh counter
        p4 = now
        if cPwr < 20:
            try:
                publish.single(
                    "homeassistant/number/solar_power",
                    cPwr,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )
            except Exception:
                pass


try:
    # Register falling-edge interrupt callbacks with internal pull-ups and 1 ms debounce
    RPIO.add_interrupt_callback(14, gpio_callback, edge="falling", threaded_callback=True, pull_up_down=RPIO.PUD_UP, debounce_timeout_ms=1)
    RPIO.add_interrupt_callback(15, gpio_callback, edge="falling", threaded_callback=True, pull_up_down=RPIO.PUD_UP, debounce_timeout_ms=1)
    RPIO.add_interrupt_callback(17, gpio_callback, edge="falling", threaded_callback=True, pull_up_down=RPIO.PUD_UP, debounce_timeout_ms=1)
    RPIO.add_interrupt_callback(7, gpio_callback, edge="falling", threaded_callback=True, pull_up_down=RPIO.PUD_UP, debounce_timeout_ms=1)

    RPIO.wait_for_interrupts(threaded=True)

    # Watchdog loop: zero out power readings in MQTT when no pulses arrive within timeout
    while True:
        time.sleep(10)
        now = datetime.datetime.now()
        try:
            if (now - p1).total_seconds() > 60:
                p1 = now
                publish.single(
                    "homeassistant/number/water_heater_power",
                    0,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )

            if (now - p2).total_seconds() > 60:
                p2 = now
                publish.single(
                    "homeassistant/number/house_power_consumption",
                    0,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )

            if (now - p3).total_seconds() > 60:
                p3 = now
                publish.single(
                    "homeassistant/number/heat_pump_1_power",
                    0,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )

            if (now - p4).total_seconds() > 120:
                p4 = now
                publish.single(
                    "homeassistant/number/solar_power",
                    0,
                    hostname=mqtt_broker_ip,
                    port=mqtt_broker_port,
                    client_id="",
                    keepalive=60,
                    will=None,
                    auth=haauth,
                    tls=None,
                    protocol=mqtt.MQTTv311,
                )
        except Exception:
            pass

except Exception:
    print("something went wrong")

finally:
    RPIO.cleanup()
