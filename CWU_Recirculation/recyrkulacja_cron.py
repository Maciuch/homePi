#!/usr/bin/env python

import RPIO
import glob
import time
import datetime
import json

base_dir = '/sys/bus/w1/devices/'
cwu_gora = '28-000003b830ef'
cwu_dol =  '28-000003b81e57'
solar =    '28-000003b7ff50'
pin = 25
RPIO.setup(pin, RPIO.OUT)

def read_temp_raw(device):
    device_folder = glob.glob(base_dir + device)[0]
    device_file = device_folder + '/w1_slave'
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp(device):
    lines = read_temp_raw(device)
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw(device)
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c

def is2ndTariff():
    now = time.localtime()
    return (now.tm_hour >= 13 and now.tm_hour < 15) or (now.tm_hour >= 22 or now.tm_hour < 6)

def main():
        b_g = read_temp(cwu_gora)
        b_d = read_temp(cwu_dol)
        measTime = datetime.datetime.now().strftime("%d/%m/%y %H:%M")
        if is2ndTariff():
            if b_g > 50 and b_d < 45:
                RPIO.output(pin, True)
                pumpState = 'ON'
            elif b_g < 45 or b_d >= 45:
                RPIO.output(pin, False)
                pumpState = 'OFF'
            else:
                pumpState = 'Previous'
        else:
            #add solars handling here
            RPIO.output(pin, False)
            pumpState = 'OFF'

        data = [ { 'date':measTime, 'tempBottom':b_d, 'tempTop':b_g, '2ndTariff':is2ndTariff(), 'waterPump':pumpState } ]
        logFile = open('CWU_logs','a')
        logFile.write(json.dumps(data, sort_keys=True) + '\n')
	logFile.close()

main()

