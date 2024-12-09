#callbacks
from hydroLoggerAsync import config

telemTopic = config["TELEMTOPIC"].format(config["TENANT"],UID.decode())
ccTopic = config["CCTOPIC"].format(config["TENANT"],UID.decode())
logTopic = config["LOGTOPIC"].format(config["TENANT"],UID.decode())
statusTopic = config["STATUSTOPIC"].format(config["TENANT"],UID.decode())
feedbackTopic = config["FEEDBACKTOPIC"].format(config["TENANT"],UID.decode())

def sub_cb(topic, msg):
  global config
  global fanEnabled
  global fanOverride
  print((topic, msg))
  if topic.decode() == ccTopic:
    decodedMsg = json.loads(msg.decode())
    subject = decodedMsg.get("subject")
    message = decodedMsg.get("message")
    displayStatus("status","MQTT Incoming",subject)
    #print('Topic: ' + topic + 'Message: ' + msg)
    if subject == "returnSettings":
        '''
        theSettings = {
            "loggingInterval": 25,
            "spectralGain": "16x"
            }
        '''
        print("send the config")
        client.publish(feedbackTopic, json.dumps(config).encode())
        
    elif subject == "command":
        displayStatus("status",str(decodedMsg))
        
        device = decodedMsg.get("device")
        command = decodedMsg.get("command")
        param = decodedMsg.get("param")
        print(device)
        print(command)
        print(param)
        
        if command == "circulate":
            doCirculation(device,param)
        elif command == "inject":
            print("call inject")
            #await doInjection(device,param)
            doInjection(device,param)
            #injectFunc = doInjection(device,param)
            #await asyncio.gather(injectFunc)
            #doInjection(device,param)
            #pass
            #await asyncio.gather(doInjection(device,param))
        else:
            try:
                print(decodedMsg)
            except Exception as error:
                print(error)
        '''
        #enabled = decodedMsg.get("enabled")
        #do the command
        if not enabled:
            client.publish(statusTopic,"recieved command on explicitly disabled hardware")
        else:
            if device == "ACSWITCH1":
                if decodedMsg.get(ManualRun):
                    acRelayOnePin.value(1)
                else:
                    acRelayOnePin.value(0)
            
        client.publish(feedbackTopic,json.dumps(feedbackMessage).encode())
        '''
        
        
    elif subject == "LAUNCHREPL":
        config["LAUNCHREPL"] = True
        with open("config.json",'w') as f:
            json.dump(config,f)
            
        statusHandler("webrepl requested","status","launching repl")
        time.sleep(1)
        machine.reset()
        
    elif subject == "overwriteSettings":
        #decodedMsg is ALREADY A JSON, YOU IDIOT! Simplify!
        #print(decodedMsg)
        try:
            with open("configOverwriteBackup.json",'w') as f:
                json.dump(config, f)
        except:
            try:
                statusHandler("config change","status","could not backup config")
            except:
                print("could not backup config")
        else:
            try:
                os.remove("config.json")
                time.sleep(1)
            except:
                print("unable to delete config file")
            try:
                #newConfig = decodedMsg["configuration"]
                print(decodedMsg)
                print(json.dumps(decodedMsg["configuration"]))
                '''
                try:
                    print(json.dumps(newConfig))
                except Exception as error:
                    print(error)
                '''
                try:
                    with open("config.json",'w') as f:
                        json.dump(decodedMsg["configuration"], f)
                        time.sleep(1)
                except Exception as error:
                    print(error)
            except Exception as error:
                print("error updating config")
                print(error)
                os.rename("configOverwriteBackup.json","config.json")
                time.sleep(1)
            else:
                print("updated config, rebooting")
                machine.reset()
        
    elif subject =="FACTORYRESET":
        statusHandler("factory reset request","status","manual reset request recieved")
        time.sleep(2)
        factoryReset(config["VERSION"])

    elif subject == "changeSetting":
        try:
            if decodedMsg["SETTING"] in locals():
                if isinstance(decodedMsg["VALUE"],type(locals()[decodedMsg["SETTING"]])):
                    locals()[decodedMsg["SETTING"]] = decodedMsg["VALUE"]
                    print(str(decodedMsg["SETTING"]) + " changed to " + str(decodedMsg["VALUE"]))
                    try:
                        statusHandler("remote command","status", str(decodedMsg["SETTING"]) + " changed to " + str(decodedMsg["VALUE"]))
                    except:
                        pass
                else:
                    pass
                    #raise exception for no such setting/invalid value
            elif decodedMsg["SETTING"] in globals():
                if isinstance(decodedMsg["VALUE"],type(globals()[decodedMsg["SETTING"]])):
                    globals()[decodedMsg["SETTING"]] = decodedMsg["VALUE"]
                    print(str(decodedMsg["SETTING"]) + " changed to " + str(decodedMsg["VALUE"]))
                    try:
                        statusHandler("remote command","status", str(decodedMsg["SETTING"]) + " changed to " + str(decodedMsg["VALUE"]))
                    except:
                        pass
                else:
                    pass
                    #raise exception for no such setting/invalid value
            elif decodedMsg["SETTING"] in config.keys():
                with open("configBak.json",'w') as f:
                    json.dump(config,f)
                if isinstance(decodedMsg["VALUE"], type(config[decodedMsg["SETTING"]])):
                    config[decodedMsg["SETTING"]] = decodedMsg["VALUE"]
                    with open("config.json",'w') as f:
                        json.dump(config,f)
                else:
                    pass
                    #raise exception about data type
            else:
                #raise exception for setting not found
                pass    
        except Exception as error:
            print("parsing error: ")
            print(error)
    elif subject == "revertSettings":
        try:
            if "configBak.json" in os.listdir():
                os.remove("config.json")
                with open("configBak.json",'r') as f:
                    config = json.load(f)
                    
                with open("config.json",'w') as f:
                    json.dump(config,f)
            else:
                print("no backup config found")
        except Exception as error:
            print(error)
        
    elif subject == "checkForUpdate":
        try:
            print("call the updater")
            #import ugit
            try:
                config["LASTUPDATECHECK"] = time.mktime(rtClock.datetime())
                with open("config.json", 'w') as f:
                    json.dump(config, f)
            except Exception as error:
                print(error)
            ugit.pull_all(isconnected = True)
            
        except Exception as error:
            #errorHandler("updater pull all", error, traceback.print_stack())
            print(error)
    elif subject == "forceReboot":
        machine.reset()
    elif subject == "forceFileUpdate":
        print("manually update file: " + message)
        try:
            #import ugit
            ugit.pull(message)
        except Exception as error:
            #errorHandler("manual file update", error, traceback.print_stack())
            print(error)
        
    else:
        print('message recieved: ')
        json.dumps(message)
        displayStatus("status","MQTT Message:",message)
        time.sleep(3)
