#Hydroponic Data Acquisition and Control Unit Software
#A Liebig for PHR&D
#9/29/24

import asyncio
import json
import network
import socket
import time
import machine
import onewire
import gc
import ds18x20
import scd40
import ssd1306
import os
import espnow
import ubinascii
import TSL2591
import I2C_bus_device
import struct
import pros3
import ugit
import statistics
from umqttsimple import MQTTClient
from callbacks import *

try:
    with open("config.json",'r') as f:
        config = json.load(f)
except Exception as error:
    print("failed to locate config... looking for backup")
    with open("configDefault.json",'r') as f:
        config = json.load(f)

time.sleep(1)

try:
    with open("knownNetworks.json",'r') as g:
        knownNets = json.load(g)
except:
    print("no known nets file")
    

UID = ubinascii.hexlify(machine.unique_id())

telemTopic = config["TELEMTOPIC"].format(config["TENANT"],UID.decode())
ccTopic = config["CCTOPIC"].format(config["TENANT"],UID.decode())
logTopic = config["LOGTOPIC"].format(config["TENANT"],UID.decode())
statusTopic = config["STATUSTOPIC"].format(config["TENANT"],UID.decode())
feedbackTopic = config["FEEDBACKTOPIC"].format(config["TENANT"],UID.decode())


client = MQTTClient(ubinascii.hexlify(machine.unique_id()), config["BROKER"], keepalive=240)

fanEnabled = True
#fanEnabled = False
#set up display:

#make a network connection

#set the real time clock
    
#connect to mqtt

#if no internet/mqtt, use ESPNow


#dose pins: 3-6 pwm
#TDS 1 ADC
#pH 2 ADC
#relays 16-18 digital out
#i2c default
#temp bus 9 digital in
#define pins
fanControlPin = machine.Pin(37,machine.Pin.OUT)

'''
if pros3.get_vbus_present():
    fanControlPin.value(0)
    fanEnabled = False
else:
    fanControlPin.value(1)
    fanEnabled = True
'''


#waterSolenoidPin = machine.Pin(13,machine.Pin.OUT)

dosingOneControlPin = machine.Pin(38,machine.Pin.OUT) 
dosingTwoControlPin = machine.Pin(39,machine.Pin.OUT)
dosingThreeControlPin = machine.Pin(40,machine.Pin.OUT) 
dosingFourControlPin = machine.Pin(41,machine.Pin.OUT)

dosingOneControl = machine.PWM(dosingOneControlPin,freq=10,duty=0)
dosingTwoControl = machine.PWM(dosingTwoControlPin,freq=10,duty=0)
dosingThreeControl = machine.PWM(dosingThreeControlPin,freq=10,duty=0)
dosingFourControl = machine.PWM(dosingFourControlPin,freq=10,duty=0)


tempBusPin = machine.Pin(12,machine.Pin.IN) #12
tempProbeBus = ds18x20.DS18X20(onewire.OneWire(tempBusPin))
probeTemps = tempProbeBus.scan()

phProbePowerPin = machine.Pin(4,machine.Pin.OUT) #4
phProbeDataPin = machine.ADC(7) #6
phTempProbePin = machine.Pin(14)

tdsProbePowerPin = machine.Pin(16,machine.Pin.OUT)  #16
tdsProbeDataPin = machine.ADC(6) #7

acRelayOnePin = machine.Pin(1,machine.Pin.OUT,machine.Pin.PULL_DOWN)
acRelayTwoPin = machine.Pin(2,machine.Pin.OUT,machine.Pin.PULL_DOWN)
acRelayThreePin = machine.Pin(21,machine.Pin.OUT,machine.Pin.PULL_DOWN)

#lowWaterSensorPin = machine.ADC(10)
#lowWaterSensorPin = machine.Pin(5,machine.Pin.IN,machine.Pin.PULL_DOWN) #5
lowWaterSensorPin = machine.ADC(3)
#highWaterSensorPin = machine.Pin(3,machine.Pin.IN) #3
highWaterSensorPin = machine.ADC(5)

levelSenseTrigger = 5000
#I2C bus for SCD40 and/or AHT10
sensorBus = machine.I2C(0,scl=machine.Pin(9),sda=machine.Pin(8),freq=100000) #9,8

#display:
try:
    oledDisplay = ssd1306.SSD1306_I2C(128,32,sensorBus)
    oledDisplay.fill(0)
    oledDisplay.show()
    time.sleep(1)
    oledDisplay.text("Booting up...",0,0,1)
    oledDisplay.show()
    time.sleep(2)
except:
    print("no oled")


#this should be a class
feedbackMessage = {
        "ID":"ACSWITCH1",
        "ENABLED": True,
        "ON": False
    }
    
def addWater(device="ACSWITCH3"):
    print("add water running")
    for item in config["DEVICES"]:
        if item["ID"] == device:
            devNum = config["DEVICES"].index(item)
            tempPin = eval(config["DEVICES"][devNum]["MAPPING"])
            feedbackMessage["ID"] = device
            feedbackMessage["ENABLED"] = config["DEVICES"][devNum]["ENABLED"]
            if config["DEVICES"][devNum]["ENABLED"]:
                if highWaterSensorPin.read_uv() < levelSenseTrigger:
                    tempPin.value(1)
                    feedbackMessage["ON"] = True
                    try:
                        client.publish(feedbackTopic,json.dumps(feedbackMessage.encode()))
                    except:
                        displayStatus("error","unable to send feedback message")
                    while True:
                        print("add water loop running")
                        if highWaterSensorPin.read_uv() < levelSenseTrigger:
                            #await asyncio.sleep(1)
                            
                            time.sleep(1)
                            print("adding water")
                            #status handler and display
                        else:
                            tempPin.value(0)
                            feedbackMessage["ON"] = False
                            try:
                                client.publish(feedbackTopic,json.dumps(feedbackMessage.encode()))
                            except:
                                displayStatus("error","unable to send feedback message")
                            print("closing valve")
                            #status handler and display
                            #await asyncio.sleep(1)
                            time.sleep(1)
                            break
                else:
                    print("water at high level")
            else:
                print("command attempted on disabled hardware")
        else:
            pass
                

def doInjection(device,ammount):
    print("injection command recieved")
    print("inject called")
    #add a call to doCirculation so that water is moving while injectors run
    for item in config["DEVICES"]:
        if item["ID"] == device:
            devNum = config["DEVICES"].index(item)
            feedbackMessage["ID"] = device
            feedbackMessage["ENABLED"] = config["DEVICES"][devNum]["ENABLED"]
            if config["DEVICES"][devNum]["ENABLED"]:
                feedbackMessage["ON"] = True
                try:
                    client.publish(feedbackTopic,json.dumps(feedbackMessage.encode()))
                except:
                    displayStatus("error","unable to send feedback message")
                tempPin = eval(config["DEVICES"][devNum]["MAPPING"])
                #figure out the dosing x pulses/s * y duty cycle * t sec = z mL
                runTime = ammount * 0.5
                #convert ml to run time in seconds
                tempPin.duty(50)
                timeOn = 0.0
                while timeOn < runTime:
                    time.sleep_ms(100)
                    #await asyncio.sleep_ms(100)
                    timeOn += 0.1
                
                tempPin.duty(0)
                feedbackMessage["ON"] = False
                try:
                    client.publish(feedbackTopic,json.dumps(feedbackMessage.encode()))
                except:
                    displayStatus("error","unable to send feedback message")
                print("dispensed " + str(ammount) + "mL of " + config["DEVICES"][devNum]["CHEMICAL"])
                displayStatus("status","dispensed " + str(ammount) + "mL of " + config["DEVICES"][devNum]["CHEMICAL"])
            else:
                print("command attempted on disabled hardware")
                displayStatus("status","command attempted on disabled hardware")
                #await asyncio.sleep(2)
                time.sleep(1)
        else:
            pass

def doCirculation(device,runTime):
    for item in config["DEVICES"]:
        if item["ID"] == device:
            devNum = config["DEVICES"].index(item)
            feedbackMessage["ID"] = device
            feedbackMessage["ENABLED"] = config["DEVICES"][devNum]["ENABLED"]
            
            if config["DEVICES"][devNum]["ENABLED"]:
                tempPin = eval(config["DEVICES"][devNum]["MAPPING"])
                if lowWaterSensorPin.read_uv() > levelSenseTrigger:
                    feedbackMessage["ON"] = True
                    try:
                        client.publish(feedbackTopic,json.dumps(feedbackMessage.encode()))
                    except:
                        displayStatus("error","unable to send feedback message")
                    if runTime == 0:
                        print("warning, manually running until stop")
                        tempPin.value(1)
                    else:
                        timeOn = 0
                        tempPin.value(1)
                        while timeOn < runTime:
                            time.sleep(1)
                            timeOn += 1
                        tempPin.value(0)
                        feedbackMessage["ON"] = False
                        try:
                            client.publish(feedbackTopic,json.dumps(feedbackMessage.encode()))
                        except:
                            displayStatus("error","unable to send feedback message")
                else:
                    print("Water level too low!")
            else:
                print("device is explicitly disabled")
        else:
            pass

def displayStatus(messageType,message,*addText):
    try:
        oledDisplay.fill(0)
        oledDisplay.show()
        time.sleep(1)
        if messageType == "status":
            #oledDisplay.fill(0)
            #oledDisplay.show()
            oledDisplay.text(messageType,0,0,1)
            oledDisplay.text(message,0,10,1)
            #oledDisplay.show()
        elif messageType == "error":
            oledDisplay.text(messageType,0,0,1)
            oledDisplay.text(message,0,10,1)
        elif messageType == "telem":
            oledDisplay.text(messageType,0,0,1)
            oledDisplay.text(message,0,10,1)
        else:
            oledDisplay.text(messageType,0,0,1)
            oledDisplay.text(message,0,10,1)
        
        oledDisplay.show()
        
        if addText:
            try:
                print(str(addText))
            #pass
            
                for lineNum,line in enumerate(addText):
                    oledDisplay.text(str(line),0,(lineNum+2)*10,1)
                    oledDisplay.show()
                    
                    if len(line) < int(128/8):
                        #oledDisplay.show()
                        pass
                    else:
                        for i in range(len(line)%16):
                            time.sleep(2)
                            oledDisplay.scroll(16,0)
                        #oledDisplay.scroll()
            except Exception as error:
                print("add text problem " + error) 
        else:
            pass
        #oledDisplay.show()
        #return
    except:
        print("no oled")

#encapsulate this in a function for easy reconnect
station = network.WLAN(network.STA_IF)
#mesh = espnow.ESPNow()
#no way to scan ESPNow for peers, must pull down list of mac addresses based on provisioning info
#create local file of known peers to avoid catch 22 of needing remote list

def wiCon():
    #global station
    displayStatus("status","WiFi Connecting")
    #station = network.WLAN(network.STA_IF)
    station.active(True)
    time.sleep(1)

    connAttempt = 0
    if 'knownNets' in locals() or 'knownNets' in globals():
        for net in knownNets:
            for found in network.WLAN().scan():
                if found[0].decode() == net["SSID"]:
                    while not station.isconnected():
                        if connAttempt < 10:
                            try:
                                station.connect(net["SSID"],net["PASS"])
                            except:
                                connAttempt += 1
                                time.sleep(1)
                                continue
                        else:
                            break
                else:
                    pass
    else:
        connAttempt = 0
        while not station.isconnected():
            if connAttempt < 10:
                try:
                    station.connect(config["SSID"],config["WIPASS"])
                except:
                    connAttempt += 1
                    time.sleep(1)
                    continue
            else:
                break

    time.sleep(1)
    if station.isconnected():
        print("wifi working")
        displayStatus("status","WiFi connected",str(station.ifconfig()[0]))
    else:
        print("no wifi")
        displayStatus("status","No Wifi")
        
    time.sleep(2)

try:
    wiCon()
except:
    print("wifi error, local mode")
    displayStatus("status","no net, local mode")
    #look for other units on ESPNOW
    #local mode flag
else:
    pass

#check for update
displayStatus("status","Checking for updates")
#try:
#    ugit.pull_all(isconnected = True)
#except Exception as error:
#    displayStatus("error","unable to check for updates")
time.sleep(1)   


try:
    scd40CO2 = scd40.SCD4X(sensorBus)
    time.sleep(1)
    #await asyncio.sleep(1)
    scd40CO2.start_periodic_measurement()
except Exception as error:
    displayStatus("error","CO2 error")
else:
    displayStatus("status","CO2 Good!")
    
time.sleep(1)

try:
    totalLuxSense = TSL2591.TSL2591(sensorBus)
    time.sleep(1)
    totalLuxSense.gain = TSL2591.GAIN_MED
except Exception as error:
    displayStatus("error","Lux error")
else:
    displayStatus("status","Lux Good!")
    
time.sleep(1)



        

client.set_callback(sub_cb)

disconMsg = "Client " + str(UID) + " has disconnected unexpectedly"
client.set_last_will(statusTopic,disconMsg)

try:
    client.connect()
    time.sleep(1)
except Exception as error:
    displayStatus("error","MQTT error")
else:
    displayStatus("status","MQTT Good!")
    #clear the previous last will message
    client.publish(statusTopic,b'',retain=True)
    time.sleep(1)

try:
    client.subscribe(ccTopic)
except:
    print("local mode, mqtt fail")
#Helper Functions:

    
#setup the RTC
NTP_DELTA = 3155673600 + 25200   #Adjust this for time zone
timeHost = "pool.ntp.org"
rtClock = machine.RTC()

def set_time():
    # Get the external time reference
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(timeHost, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    except Exception as error:
        #errorHandler("NTP error", error, traceback.print_stack())
        print("NTP error")
    finally:
        s.close()

    #Set our internal time
    val = struct.unpack("!I", msg[40:44])[0]
    tm = val - NTP_DELTA    
    t = time.gmtime(tm)
    rtClock.datetime((t[0],t[1],t[2],t[6]+1,t[3],t[4],t[5],0))

ntpFail = False

if station.isconnected():
    try:
        set_time()
    except Exception as error:
        print(error)
        displayStatus("error","NTP fail",error)
        rtClock.datetime((2000,1,1,1,1,1,1,0))
    else:
        print("clock set")
        displayStatus("status","NTP Good!")
else:
    ntpFail = True


def logHandler(source, level, message):
    #TODO:add levels
    logEntry = {
        "Time": rtc.dateTime(),
        "Source": source,
        "Level": level,
        "Message": message
        }
    
    try:
        with open('errorLog.txt','a+') as f:
            f.write("\n")
            json.dump(logEntry, f)
    except:
        print("unable to log local error")
        
#log status events:
def statusHandler(source, statusType, message):
    mem = gc.mem_free()
    try:
        statusPayload = {
                            "Source": source,
                            "Message": message,
                            "Time": str(rtClock.datetime()),
                            "Mem": mem
                        }
    except Exception as error:
        print(error)
        statusPayload = {
                            "Source": source,
                            "Message": message,
                            "Time": "RTC/NTP Fail",
                            "Mem": mem
                        }
    try:
        client.publish(statusTopic, json.dumps(statusPayload).encode())
    except Exception as error:
        print(error)
        
    displayStatus(statusType,message)

async def listener():
    try:
        client.check_msg()
    except Exception as error:
        print("message check error")
        print(error)
    await asyncio.sleep_ms(100)

async def hwResponder():
    #send message to update node red every time a command is issued
    pass

async def main():
    #global station
    while True:
        try:
            #client.check_msg()
            asyncio.create_task(listener())
        except Exception as error:
            print(error)
            displayStatus("error","MQTT check msg fail")
            time.sleep(3)
        
        await listener()
            
        displayStatus("status","begin loop...")
        
        tdsProbePowerPin.value(0)
        phProbePowerPin.value(1)
        
        phData = {"PH":0,
                  "TEMP":0}
        
        tdsData = {"TDS":0}
        
        luxData = {"TOTAL":0,
           "IR":0,
           "VIS":0,
           "FULLSPEC":0}
        
        atmosphericData = {
                   "SCD40":
                       {
                        "TEMP":0.0,
                        "HUMIDITY":0.0,
                        "CO2":0.0
                        }
                   }
        
        tempProbeValues = []
        probeData = {"0":0}
        
        
        #tempProbeData = {
                        
        
        co2Wait = 0
        try:
            while not scd40CO2.data_ready:
                print("waiting on CO2 sensor")
                if co2Wait < 20:
                    co2Wait += 1
                    #time.sleep_ms(500)
                    await asyncio.sleep_ms(200)
                else:
                    break
        except Exception as error:
            co2Fail = True
            print(error)
            
        await listener()
        
        try:
            atmosphericData["SCD40"]["TEMP"] = scd40CO2.temperature
            atmosphericData["SCD40"]["HUMIDITY"] = scd40CO2.relative_humidity
            atmosphericData["SCD40"]["CO2"] = scd40CO2.co2
        except Exception as error:
            #errorHandler("SCD40 reading", error, traceback.print_stack())
            atmosphericData["SCD40"]["TEMP"] = 0
            atmosphericData["SCD40"]["HUMIDITY"] = 0
            atmosphericData["SCD40"]["CO2"] = 0
            print(error)
            print("co2 fail")
            displayStatus("error","CO2 fail")
            fanEnabled = True
        else:
            displayStatus("status",str(atmosphericData["SCD40"]["TEMP"]) + "C " + str(atmosphericData["SCD40"]["HUMIDITY"]) + "% " + str(atmosphericData["SCD40"]["CO2"]) + "ppm")
            if atmosphericData["SCD40"]["TEMP"] >= config["FANCUTOFF"]:
                fanEnabled = True
            else:
                fanEnabled = False


        try:
            luxData["TOTAL"] = totalLuxSense.lux
            luxData["IR"] = totalLuxSense.infrared
            luxData["VIS"] = totalLuxSense.visible
            luxData["FULLSPEC"] = totalLuxSense.full_spectrum
        except Exception as error:
            print(error)
            luxData["TOTAL"] = 0
            luxData["IR"] = 0
            luxData["VIS"] = 0
            luxData["FULLSPEC"] = 0
            #errorHandler("lux reading", error, traceback.print_stack())
            displayStatus("error","lux fail")
        else:
            displayStatus("status","Lux:  " + str(luxData["TOTAL"]))
        
        #get temp:
        try:
            tempProbeBus.convert_temp()
        except Exception as error:
            statusHandler("temp probes","error","failed to read start probe(s)")

        else:
            time.sleep(1)
            try:
                for i in probeTemps:
                    tempProbeValues.append(tempProbeBus.read_temp(i))
            except Exception as error:
                statusHandler("temp probes","error","failed to read temp probes")
            else:
                for index, value in enumerate(tempProbeValues):
                    probeData[str(index)] = value
                print(tempProbeValues)
                #displayStatus("status",str(probeData.items()[0][]) + " " + str(probeData.items()[1][]), str(probeData.items()[2][]) + " " + str(probeData.items()[3][]))
                displayStatus("status",str(probeData))
   
           #for index,temp in enumerate(tempProbeValues)
        #    tempProbeData[index] = temp
        await listener()
        #time.sleep(2)
        await asyncio.sleep(2)
        #get pH:
        #tdsProbePowerPin.value(0)
        await asyncio.sleep(2)
        #phProbePowerPin.value(1)
        #time.sleep(5)
        await asyncio.sleep(5)
        await listener()
        
        z = 0
        displayStatus("status","warming up pH probe","0")
        
        while z < 45:
            await listener()
            await asyncio.sleep(1)
            displayStatus("status","warming up pH probe",str(z))
            z += 1
            
        #time.sleep(15)
        
        #phData["PH"] = phProbeDataPin.read_uv() * 3.3 / 1000000
        #multisample:
        t = 0
        phVals = []
        while t < 15:
            phVals.append(7 - (phProbeDataPin.read_uv() * 3.3 / 10000) / 57.14)  #need to calibrate and cure fit to be sure of this value
            await asyncio.sleep_ms(250)
            t += 1
        
        
        phData["PH"] = statistics.mean(phVals)
        
        #phData["PH"] = 7 - phProbeDataPin.read_uv() / 57.14
        #change this to read ph temp probe
        #phData["TEMP"] = 0
        try:
            phData["TEMP"] = statistics.mean(tempProbeValues)
        except:
            phData["TEMP"] = 25.0
        displayStatus("status","pH: " + str(phData["PH"]),"Temp: " + str(phData["TEMP"]))
        
        await asyncio.sleep(1)
        
        print(phData["PH"])
        phProbePowerPin.value(0)
        #gc.collect()
        await listener()
        await asyncio.sleep(1)
            #make sure TDS probe is switched off
            #switch on pH probe, 30 seconds to stabilize
            #take reading
            #switch off pH probe
            
        #get EC/TDS:
        displayStatus("status","warming up TDS probe","0")
        tdsProbePowerPin.value(1)
        #time.sleep(20)
        y=0
        while y < 30:
            await listener()
            await asyncio.sleep(1)
            displayStatus("status","warming up TDS probe",str(y))
            y += 1
        
        tdsVoltageReadings = []
        
        for j in range(0,20):
            tdsVoltageReadings.append(tdsProbeDataPin.read_uv() * 3.3 / 1000000)
            await asyncio.sleep_ms(100)
            j += 1
        
        tdsAverageVoltage = statistics.mean(tdsVoltageReadings)
        #tdsCompensationCoefficient = 1.0 + 0.02*(statistics.mean([25.2,26.9,23.8,24.9]) - 25.0)
        try:
            tdsCompensationCoefficient = 1.0 + 0.02*(statistics.mean(tempProbeValues) - 25.0)
        except:
            print("temp probes absent, assuming 25C")
            tdsCompensationCoefficient = 1.0 + 0.02*(statistics.mean([25.2,26.9,23.8,24.9]) - 25.0)
        
        tdsCompensationVoltage = tdsAverageVoltage / tdsCompensationCoefficient
        tdsData["TDS"] = (133.42*tdsCompensationVoltage*tdsCompensationVoltage*tdsCompensationVoltage - 255.86*tdsCompensationVoltage*tdsCompensationVoltage + 857.39*tdsCompensationVoltage)*0.5
        #tdsData["TDS"] = tdsProbeDataPin.read_uv() * 3.3 / 1000000
        tdsData["EC"] = tdsData["TDS"] * 2 / 1000   #calculated value
        #TODO: double check the math here
        #time.sleep(1)
        await asyncio.sleep(1)
        displayStatus("status","TDS: " + str(tdsData["TDS"]), "EC: " + str(tdsData["EC"]))
        tdsProbePowerPin.value(0)
        #time.sleep(1)
        await asyncio.sleep(1)
        await listener()
            #make sure pH probe is switched off
            #switch on TDS probe, wait 30 seconds to stabilize
            #take reading, do conversion to get EC
            #switch off TDS probe
            
        #AC relay control:
            #poll settings and check schedule
            #match AC 1-3 with purpose and enabled
            
        #lowWater = lowWaterSensorPin.value()
        #highWater = highWaterSensorPin.value()
        lowWater = lowWaterSensorPin.read_uv() 
        await asyncio.sleep_ms(100)
        highWater = highWaterSensorPin.read_uv()
        
        displayStatus("status","Low Water: " + str(lowWater) + " uV","High Water: " + str(highWater) + " uV")
        #interrupts for low water sensor, AC control, and dosing
        
        await listener()
        #if dosePumpControlEnabled:
            #check scheduling and manual input
        try:
            mqttPayload = {
                            "node": config["NAME"],
                            "UID": UID,
                            "CONTEXT": config["CONTEXT"],
                            "LUX": luxData,
                            "ATMOSPHERIC": atmosphericData,
                            "PROBE": probeData,
                            "PH": phData,
                            "TDS": tdsData,
                            "RTCLOCK": rtClock.datetime(),
                            "MEMFREE": gc.mem_free(),
                            "MEMUSED": gc.mem_alloc(),
                            "LOWWATER": lowWater,
                            "LOWWATERRAW": lowWater,
                            "HIGHWATER": highWater,
                            "HIGHWATERRAW": highWater,
                            "FAN": fanEnabled
                           }
        except Exception as error:
            print(error)
            displayStatus("error","payload malformed",error)
        
        print(json.dumps(mqttPayload))
        displayStatus("status","Transmitting...")
        #time.sleep(1)
        await asyncio.sleep(1)
        await listener()
        
        if not station.isconnected():
            reconnectAttempts = 0
            while not station.isconnected():
                if reconnectAttempts < 10:
                    try:
                        reconnectAttempts += 1
                        wiCon()
                        await asyncio.sleep_ms(100)
                    except:
                        continue
                else:
                    machine.reset()
        else:
            pass
        
        try:
            client.publish(telemTopic, json.dumps(mqttPayload).encode())
        except Exception as error:
            print("mqtt error")
            displayStatus("error","MQTT send fail",error)
        else:
            displayStatus("status","Transmission successful")
            
        await asyncio.sleep(2)
        await listener()
        #time.sleep(2)
        
        displayStatus("status","Checking for MQTT messages")
        '''
        try:
            client.check_msg()
        except Exception as error:
            print(error)
            displayStatus("error","MQTT check msg fail")
        '''
        if fanEnabled:
            fanControlPin.value(1)
        else:
            fanControlPin.value(0)
        
        if lowWaterSensorPin.read_uv() < levelSenseTrigger and highWaterSensorPin.read_uv() < levelSenseTrigger:
            print("add water triggered")
            #await addWater()
        else:
            pass
        
        #await addWater()
        
        t=0
        while t < config["LOGINTERVAL"]:
            await listener()
            await asyncio.sleep(1)
            t += 1
        
        gc.collect()
asyncio.run(main())  