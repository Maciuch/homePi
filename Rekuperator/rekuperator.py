#!/usr/bin/env python

import RPIO
import glob
import time
import datetime
import paho.mqtt.client as mqtt

mqtt_broker_ip = "192.168.1.49"
mqtt_broker_port = 1883

# True turns on 2nd gear
pin2 = 23
# True turns on 3rd gear
pin3 = 24


def on_connect(mqttc, userdata, flags, rc):
    if rc == 0:
        print("Connected, ret code=", rc)
        mqttc.subscribe("rekuperator/gear", 1)
    else:
        print("Not connected, rc code=", rc)


def on_message(mqttc, userdata, message):
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
    print(mid, granted_qos)


def main():
    RPIO.setup(pin2, RPIO.OUT)
    RPIO.setup(pin3, RPIO.OUT)
    mqttc = mqtt.Client()
    mqttc.username_pw_set("mqttuser", "asdsa11")
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_subscribe = on_subscribe

    # setup initial state, msg 3 - currently meaning gear 1
    RPIO.output(pin2, False)
    RPIO.output(pin3, True)

    mqttc.connect(mqtt_broker_ip, mqtt_broker_port, 60)
    mqttc.loop_forever()


main()
