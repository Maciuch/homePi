#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Heat-Recovery Ventilation (Rekuperator) Gear Control Daemon.

Runs continuously as a background service started from /etc/rc.local.
Subscribes to the MQTT topic 'rekuperator/gear' on the Home Assistant broker
and switches two GPIO relay outputs (pin2 = GPIO 23, pin3 = GPIO 24) to select
the desired ventilation fan speed gear ("1", "2", or "3").
"""

import RPIO
import glob
import time
import datetime
import paho.mqtt.client as mqtt

mqtt_broker_ip = "192.168.1.49"
mqtt_broker_port = 1883

# True turns on 2nd gear relay
pin2 = 23
# True turns on 3rd gear relay
pin3 = 24


def on_connect(mqttc, userdata, flags, rc):
    """
    MQTT callback invoked when the client connects to the broker.
    Subscribes to 'rekuperator/gear' (QoS 1) upon successful connection.

    Args:
        mqttc (mqtt.Client): The MQTT client instance.
        userdata: User-defined data passed to callbacks.
        flags (dict): Response flags sent by the broker.
        rc (int): Connection result code (0 indicates success).
    """
    if rc == 0:
        print("Connected, ret code=", rc)
        mqttc.subscribe("rekuperator/gear", 1)
    else:
        print("Not connected, rc code=", rc)


def on_message(mqttc, userdata, message):
    """
    MQTT callback invoked when a gear command payload is received on
    'rekuperator/gear'. Switches GPIO 23 and GPIO 24 relays accordingly:
    - "1": pin2 = LOW,  pin3 = LOW
    - "2": pin3 = LOW,  pin2 = HIGH
    - "3": pin2 = LOW,  pin3 = HIGH

    Args:
        mqttc (mqtt.Client): The MQTT client instance.
        userdata: User-defined data passed to callbacks.
        message (mqtt.MQTTMessage): Incoming MQTT message containing topic and payload.
    """
    msg = message.payload.decode("utf-8")
    print("Received: " + msg)
    if msg == "1":
        RPIO.output(pin2, False)
        RPIO.output(pin3, False)
    elif msg == "2":
        RPIO.output(pin3, False)
        RPIO.output(pin2, True)
    elif msg == "3":
        RPIO.output(pin2, False)
        RPIO.output(pin3, True)
    else:
        print("unsupported value")


def on_subscribe(client, userdata, mid, granted_qos):
    """
    MQTT callback invoked when the broker acknowledges the topic subscription.

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata: User-defined data passed to callbacks.
        mid (int): Message ID of the subscribe request.
        granted_qos (tuple): QoS levels granted by the broker.
    """
    print(mid, granted_qos)


def main():
    """
    Initialize GPIO 23 and GPIO 24 as outputs, set the default fan speed,
    connect to the Home Assistant MQTT broker, and enter the blocking MQTT
    network loop.
    """
    RPIO.setup(pin2, RPIO.OUT)
    RPIO.setup(pin3, RPIO.OUT)
    mqttc = mqtt.Client()
    mqttc.username_pw_set("mqttuser", "asdsa11")
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_subscribe = on_subscribe

    # Setup initial state, msg 3 - currently meaning gear 1
    RPIO.output(pin2, False)
    RPIO.output(pin3, True)

    mqttc.connect(mqtt_broker_ip, mqtt_broker_port, 60)
    mqttc.loop_forever()


main()
