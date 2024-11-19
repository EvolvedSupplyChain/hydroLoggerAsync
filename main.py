#Version 0.2.1

import json
import machine
import ssd1306
#import os

#fileString = __file__
#version = "0.2.1"
print("version 0.2.1")

sensorBus = machine.I2C(0,scl=machine.Pin(9),sda=machine.Pin(8),freq=100000)

try:
    oledDisplay = ssd1306.SSD1306_I2C(128,32,sensorBus)

    oledDisplay.fill(0)
    oledDisplay.show()
except:
    print("no oled")
    
with open("config.json", 'r') as f:
    config = json.load(f)



if config["MODE"] == "REPL":
    config["MODE"] = "logger"
    with open("config.json",'w') as f:
        json.dump(config, f)
    
    #connect to wifi
    import network
    import time
    import webrepl
    #import machine
    #import _thread
    #import neopixel
    
    station = network.WLAN(network.STA_IF)
    station.active(True)
    
    
    while not station.isconnected():
        station.connect(config["SSID"], config["WIPASS"])
        time.sleep(2)
    
    
    print(station.ifconfig()[0])
    #displayIP()
    #open a VPN connection so that webREPL will be local to azure network
    try:
        webrepl.start(password="2075012")
    except:
        oledDisplay.text("REPL error",0,0,0)
        oledDisplay.text("Power cycle",0,10,0)
    else:
        oledDisplay.text("REPL IP: ",0,0,0)
        oledDisplay.text(str(station.ifconfig()[0]),0,10,0)
        
    #TODO: quite webrepl and reset if button pushed
    #this doesn't work, need to find how to check for connection; os.dupterm()?
    #while not webrepl.connected():
    #displayIP()
    
    
    #launch webrepl
elif config["MODE"] == "diagnostic":
    #launch diagnostic mode
    #import diagnosticMod
    pass
elif config["MODE"] == "calibration":
    #import calibrationMod
    pass
elif config["MODE"] == "factory_reset":
    pass
    
else:
    import hydroLoggerAsync

#interrupt for push button or five way hat