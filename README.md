homePi
======

Raspberry Pi based boiler-room steering.

R-Pi revision B together with Gertboard I/O and relay sets
DS18B20 1-wire temperature sensors
DHT11 temperature and humidity sensor
Orno power sensors with impulsator outputs (1000 impulses/kWh)


./startup.txt
Description What needs to be intalled on a clean system to make things work.
Based on Rasbpian OS.


./CWU_Recirculation/
Steering of recirculation pump in order to:
- maximize the night tariff cheaper energy
- facilitate operation based on user entering the bathroom - TBD

./Power_Counters/
Stats from power counters:
- main for entire house
- water heater
- house heater
- heat pump
