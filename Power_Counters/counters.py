#!/usr/bin/python

import RPIO
import datetime
import json
import time
import rpyc

PIN_CWU_HEATER = 14
PIN_CO_HEATER = 23
PIN_POWER_SUPPLY = 15
PIN_HEAT_PUMP = 25

counter1 = 0
counter2 = 0
counter3 = 0
counter4 = 0
prevTime1 = datetime.datetime.min
prevTime2 = datetime.datetime.min
prevTime3 = datetime.datetime.min
prevTime4 = datetime.datetime.min
currentCons = 0

class MyService(rpyc.Service):
    def exposed_getCurrentCons(self):
        global currentCons
        return currentCons

    def exposed_getCounter(self, n):
        global counter1
        global counter2
        global counter3
        global counter4
        if n == 1:
           return counter1
        elif n == 2:
           return counter2
        elif n == 3:
           return counter3
        elif n == 4:
           return counter4



# start the rpyc server
from rpyc.utils.server import ThreadedServer
from threading import Thread
server = ThreadedServer(MyService, port = 12345)
t = Thread(target = server.start)
t.daemon = True
t.start()


def is2ndTariff():
   now = time.localtime()
   return (now.tm_hour >= 13 and now.tm_hour < 15) or (now.tm_hour >= 22 or now.tm_hour < 6) 


def writeCurrentConsumption(currTime, prevTime): 
   deltaTime = currTime - prevTime
   #write current consumption (1000 ticks/kWh) & daily cost
   global currentCons
   currentCons = 3600 / (1000 * deltaTime.total_seconds())
   data = [ currTime.strftime("%d/%m %H:%M:%S:%f"), currentCons ]
#   currConsFile = open('currentConsumption', w)
#   currConsFile.write(json.dumps(data))
#   currConsFile.close()
 

def writeData(fileName, prevTime, kWh):
   logFile = open(fileName, 'a')
   data = [ prevTime.strftime("%d/%m %H"), kWh ]
   logFile.write(json.dumps(data) + '\n')
   
#   print(data)
   #check & rotate file
   logFile.close()
 

def counterTick(gpio_pin, value):
   #write Time to right file
   prevTime = datetime.datetime.min
   measTime = datetime.datetime.now()#.strftime("%d/%m/%y %H:%M:%S:%f")
   if gpio_pin == PIN_CWU_HEATER:
      logFile = 'counter_CWU_HEATER_logs'
      global prevTime1
      global counter1
      prevTime = prevTime1
      prevTime1 = measTime
      if measTime.hour != prevTime.hour:
         kWh = counter1 / float(1000)
         counter1 = 0
         writeData(logFile, prevTime, kWh)
      counter1 += 1
   elif gpio_pin == PIN_CO_HEATER:
      logFile = 'counter_CO_HEATER_logs'
      global prevTime2
      global counter2
      prevTime = prevTime2
      prevTime2 = measTime
      if measTime.hour != prevTime.hour:
         kWh = counter2 / float(1000)
         counter2 = 0
         writeData(logFile, prevTime, kWh)
      counter2 += 1
   elif gpio_pin == PIN_POWER_SUPPLY:
      logFile = 'counter_POWER_SUPPLY_logs'
      global prevTime3
      global counter3
      prevTime = prevTime3
      prevTime3 = measTime
      writeCurrentConsumption(measTime, prevTime)
      if measTime.hour != prevTime.hour:
         kWh = counter3 / float(1000)
         counter3 = 0
         writeData(logFile, prevTime, kWh)
      counter3 += 1
   elif gpio_pin == PIN_HEAT_PUMP:
      logFile = 'counter_HEAT_PUMP_logs'
      global prevTime4
      global counter4
      prevTime = prevTime4
      prevTime4 = measTime
      if measTime.hour != prevTime.hour:
         kWh = counter4 / float(1000)
         counter4 = 0
         writeData(logFile, prevTime, kWh)
      counter4 += 1



   #write current consumption (1000 ticks/kWh) & daily cost
#   consumption = 3600 / (1000 * deltaTime.total_seconds())
#   cash = 0
#   data = [ measTime.strftime("%d/%m %H:%M:%S:%f"), consumption, cash ]
#   data = [ prevTime.strftime("%d/%m %H"), kWh ]
#   logFile.write(json.dumps(data) + '\n')
   
#   print(data)
   #check & rotate file
#   logFile.close()


#while True:
#   time.sleep(2)
#   counterTick(14,1)

RPIO.add_interrupt_callback(PIN_CWU_HEATER, counterTick, edge='falling', pull_up_down=RPIO.PUD_OFF, threaded_callback=True, debounce_timeout_ms=None)
RPIO.add_interrupt_callback(PIN_CO_HEATER, counterTick, edge='falling', pull_up_down=RPIO.PUD_OFF, threaded_callback=True, debounce_timeout_ms=None)
RPIO.add_interrupt_callback(PIN_HEAT_PUMP, counterTick, edge='falling', pull_up_down=RPIO.PUD_OFF, threaded_callback=True, debounce_timeout_ms=None)
RPIO.add_interrupt_callback(PIN_POWER_SUPPLY, counterTick, edge='falling', pull_up_down=RPIO.PUD_OFF, threaded_callback=True, debounce_timeout_ms=None)

while True:
   RPIO.wait_for_interrupts()
