#!/usr/bin/python

import rpyc

conn = rpyc.connect("localhost", 12345)
c = conn.root

# do stuff over rpyc

print c.getCurrentCons()
print c.getCounter(3)




