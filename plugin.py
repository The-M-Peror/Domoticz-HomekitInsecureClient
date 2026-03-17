# Connect to Homekit Device in Insecure mode
#
# Author: MacJL
#
"""
<plugin key="HomekitInsecureClient" name="Homekit Insecure Client" author="MacJL" version="2.1" wikilink="http://www.domoticz.com/wiki/plugins" externallink="https://github.com/macjl/Domoticz-HomekitInsecureClient">
    <description>
        Control Homekit Devices which are set in insecure mode (eg : Homebridge, HAA, etc...)
    </description>
    <params>
        <param field="Address" label="IP Address of homekit device or bridge" width="200px" required="true" default="127.0.0.1"/>
        <param field="Port" label="PORT of homekit device or bridge" width="50px" required="true" default="54821"/>
        <param field="Password" label="Authorization key" width="80px" required="true" default="031-45-154" password="true"/>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Plugin Debug" value="2"/>
                <option label="All" value="-1"/>      
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import json

if False==True: # Hack: get rid of the not found warnings in the IDE.
    Domoticz = {}
    Parameters = {}
    Devices = {}

class BasePlugin:
    enabled = False
    httpConnGet = None
    Timeout = 60000
    GetSent = 0
    headers = { 'Content-Type': 'Application/json'}
    deviceData = {}

    def __init__(self):
        return

    def onStart(self):
        Domoticz.Debugging(int(Parameters["Mode6"]))
        Domoticz.Debug("Plugin set in Debug Mode")
        DumpConfigToLog()

        Domoticz.Log("Initializing Homekit Insecure Client Plugin")

        Domoticz.Debug("Creating Connection object")
        self.headers = { 'Content-Type': 'Application/json', 'Authorization': Parameters["Password"], 'Host': Parameters["Address"]+":"+Parameters["Port"] }
        self.httpConnGet = Domoticz.Connection(Name="httpGET", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])

        Domoticz.Log("Connecting to Homekit Device at address http://" + Parameters["Address"] + ":" + Parameters["Port"] )
        self.httpConnGet.Connect(Timeout=self.Timeout)

    def onStop(self):
        self.httpConnGet.Disconnect()
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        if (Status == 0):
            Domoticz.Debug("Connection successfull")
        else:
            Domoticz.Error("Failed to connect ("+str(Status)+") to: "+Parameters["Address"]+":"+Parameters["Port"]+" with error: "+Description)

    def onTimeout(self, Connection):
        Domoticz.Log("Timeout on Connection")
        Connection.Disconnect()

    def onMessage(self, Connection, Data):
        Domoticz.Debug("Data received")
        
        try:
            Status = int(Data["Status"])
        except:
            Domoticz.Error("Invalid Data : No status")
            Connection.Disconnect()
            return

        if (Status == 204):
            Domoticz.Debug( "Command sent")
            return
        elif (Status == 207):
            Domoticz.Debug( "Command mixed response")
            Domoticz.Debug( Data["Data"].decode("utf-8", "ignore") )
            return
        elif (Status != 200):
            Domoticz.Error("Invalid Data received. Status=" + str( Status) )
            Connection.Disconnect()
            return

        # Get Accessories as a dict variable
        self.GetSent=0
        Domoticz.Debug( Data["Data"].decode("utf-8", "ignore") )
        accessories = json.loads( Data["Data"].decode("utf-8", "ignore") )["accessories"]
        for accessory in accessories:
            hkaid = accessory["aid"]
            supported = 0
            hkName="No Name"
            # Find if accessory is provided by eDomoticz and global name
            for service in accessory["services"]:
                if( service["type"] == "3E" ):
                    #Domoticz.Debug(str( service["characteristics"] ) )
                    for characteristic in service["characteristics"]:
                        if ( characteristic["type"] == "20" ):
                            hkManufacturer = characteristic["value"]
                        if ( characteristic["type"] == "23" ):
                            hkName = characteristic["value"]
            # If accessory is not provided by eDomoticz
            if ( hkManufacturer != "eDomoticz" ):
                for service in accessory["services"]:
                    # Service of type Smart Plug
                    if( service["type"] == "47" or service["type"] == "49" or service["type"] == "D0" ):
                        Domoticz.Debug(str( service["characteristics"] ) )
                        hkName="NoName"
                        for characteristic in service["characteristics"]:
                            if ( characteristic["type"] == "23" ):
                                hkName = characteristic["value"]
                            if ( characteristic["type"] == "25" or characteristic["type"] == "B0" ):
                                hkiid = characteristic["iid"]
                                hkValue = characteristic["value"]
                                if ( hkValue == True ): hkValue = 1
                                if ( hkValue == False ): hkValue = 0
                        deviceID = service["type"] + "-" + str( hkaid ) + "-" + str( hkiid )
                        domoticzID = GetIDFromDevID( deviceID )
                        Domoticz.Debug( hkManufacturer + " : " + hkName + " - DeviceID=" + deviceID + " - DomoticzID=" + str( domoticzID ) + " - Current Value=" + str (hkValue) )

                        if ( domoticzID == -1 ):
                            nextUnit = GetNextUnit()
                            Domoticz.Debug("Create domoticz device :\"" + hkName + "\" with ID=" + str( nextUnit ) + " and DeviceID=" + deviceID + " of type Switch")
                            Domoticz.Device(Name=hkName, Unit=nextUnit, TypeName="Switch", DeviceID=deviceID ).Create()
                            domoticzID = GetIDFromDevID( deviceID )
                            Domoticz.Log("Device created: " + hkName + " - DeviceID=" + deviceID )
                        IDX = Devices[domoticzID].ID
                        if ( hkValue != Devices[domoticzID].nValue ):
                            if ( hkValue == 1 ):
                                Domoticz.Status("Set ON  to Device " + hkName + " - IDX=" + str( IDX ) + " - DeviceID=" + deviceID + " - DomoticzID=" + str( domoticzID ) )
                                Devices[domoticzID].Update(nValue=1,sValue="On")
                            elif ( hkValue == 0 ):
                                Domoticz.Status("Set OFF to Device " + hkName + " - IDX=" + str( IDX ) + " - DeviceID=" + deviceID + " - DomoticzID=" + str( domoticzID ) )
                                Devices[domoticzID].Update(nValue=0,sValue="Off")
                            else:
                                Domoticz.Error("Invalid Homekit Data")
                    
                    # Service of type Blinds (Window Covering)
                    elif( service["type"] == "8C" ):
                        Domoticz.Debug(str( service["characteristics"] ) )
                        hkName="NoName"
                        hkCurrentPosition = None
                        hkTargetPosition = None
                        hkiid = None
                        for characteristic in service["characteristics"]:
                            if ( characteristic["type"] == "23" ):
                                hkName = characteristic["value"]
                            if ( characteristic["type"] == "6D" ):
                                hkCurrentPosition = characteristic["value"]
                                hkiid = characteristic["iid"]
                            if ( characteristic["type"] == "7C" ):
                                hkTargetPosition = characteristic["value"]
                                hkTargetPositionIid = characteristic["iid"]
                        deviceID = service["type"] + "-" + str( hkaid ) + "-" + str( hkiid )
                        domoticzID = GetIDFromDevID( deviceID )
                        Domoticz.Debug( hkManufacturer + " : " + hkName + " - DeviceID=" + deviceID + " - DomoticzID=" + str( domoticzID ) + " - Current Position=" + str (hkCurrentPosition) )

                        if ( domoticzID == -1 ):
                            nextUnit = GetNextUnit()
                            Domoticz.Debug("Create domoticz device :\"" + hkName + "\" with ID=" + str( nextUnit ) + " and DeviceID=" + deviceID + " of type Blinds")
                            Domoticz.Device(Name=hkName, Unit=nextUnit, TypeName="BlindsPercentage", DeviceID=deviceID ).Create()
                            domoticzID = GetIDFromDevID( deviceID )
                            Domoticz.Log("Device created: " + hkName + " - DeviceID=" + deviceID )
                        IDX = Devices[domoticzID].ID
                        Domoticz.Debug("Device " + hkName + " - IDX=" + str( IDX ) + " - DeviceID=" + deviceID + " - DomoticzID=" + str( domoticzID ) + " - nValue: " + str(Devices[domoticzID].nValue)  )
                        # Store TargetPosition IID for future use
                        if (domoticzID in self.deviceData):
                            self.deviceData[domoticzID]["hkTargetPositionIid"] = str(hkTargetPositionIid)
                        else:
                            self.deviceData[domoticzID] = {
                                "hkTargetPositionIid": str(hkTargetPositionIid)
                            }
                        # Update position if changed
                        if (hkCurrentPosition is not None):
                            self.setDomoStatusBlinds( Devices[domoticzID], hkCurrentPosition )
                    
                    # Service of type Motion Sensor
                    elif( service["type"] == "85" ):        # https://developers.homebridge.io/#/service/MotionSensor
                        hkName = "NoName"
                        motionDetected = None
                        hkiid = None
                        for characteristic in service["characteristics"]:
                            if ( characteristic["type"] == "23" ):      # https://developers.homebridge.io/#/characteristic/Name
                                hkName = characteristic["value"]
                            if ( characteristic["type"] == "22" ):      # https://developers.homebridge.io/#/characteristic/MotionDetected
                                motionDetected = characteristic["value"] 
                                hkiid = characteristic["iid"]
                        deviceID = service["type"] + "-" + str(hkaid) + "-" + str(hkiid)
                        domoticzID = GetIDFromDevID(deviceID)
                        Domoticz.Debug(hkManufacturer + " : " + hkName + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID) + " - Motion Detected=" + str(motionDetected))

                        if (domoticzID == -1):
                            nextUnit = GetNextUnit()
                            Domoticz.Debug("Create domoticz device :\"" + hkName + "\" with ID=" + str(nextUnit) + " and DeviceID=" + deviceID + " of type Motion Sensor")
                            Domoticz.Device(Name=hkName, Unit=nextUnit, TypeName="Motion", DeviceID=deviceID).Create()
                            domoticzID = GetIDFromDevID(deviceID)
                            Domoticz.Log("Device created: " + hkName + " - DeviceID=" + deviceID)
                        IDX = Devices[domoticzID].ID
                        # Update status if changed
                        nValue = 1 if motionDetected else 0
                        if (Devices[domoticzID].nValue != nValue):
                            Domoticz.Status("Set Motion to " + ("ON" if nValue else "OFF") + " for Device " + hkName + " - IDX=" + str(IDX) + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID))
                            Devices[domoticzID].Update(nValue=nValue, sValue="On" if nValue else "Off")
                    
                    # Service of type Doorbell
                    elif( service["type"] == "121" ):        # https://developers.homebridge.io/#/service/Doorbell
                        hkName = "NoName"
                        programmableSwitchEvent = None
                        hkiid = None
                        for characteristic in service["characteristics"]:
                            if ( characteristic["type"] == "23" ):      # Name
                                hkName = characteristic["value"]
                            if ( characteristic["type"] == "73" ):      # ProgrammableSwitchEvent
                                programmableSwitchEvent = characteristic["value"]
                                hkiid = characteristic["iid"]
                        deviceID = service["type"] + "-" + str(hkaid) + "-" + str(hkiid)
                        domoticzID = GetIDFromDevID(deviceID)
                        Domoticz.Debug(hkManufacturer + " : " + hkName + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID) + " - Doorbell Event=" + str(programmableSwitchEvent))

                        if (domoticzID == -1):
                            nextUnit = GetNextUnit()
                            Domoticz.Debug("Create domoticz device :\"" + hkName + "\" with ID=" + str(nextUnit) + " and DeviceID=" + deviceID + " of type Doorbell")
                            Domoticz.Device(Name=hkName, Unit=nextUnit, Type=244, Subtype=73, Switchtype=1, DeviceID=deviceID).Create()
                            domoticzID = GetIDFromDevID(deviceID)
                            Domoticz.Log("Device created: " + hkName + " - DeviceID=" + deviceID)
                        IDX = Devices[domoticzID].ID
                        # Update status if event detected
                        # ProgrammableSwitchEvent: 0=single press, 1=double press, 2=long press
                        # For doorbell, treat any event as "pressed"
                        if programmableSwitchEvent is not None:
                            Domoticz.Status("Doorbell pressed for Device " + hkName + " - IDX=" + str(IDX) + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID))
                            Devices[domoticzID].Update(nValue=1, sValue="Pressed")

                    # Service of type Temperature Sensor
                    elif( service["type"] == "8A" ):        # https://developers.homebridge.io/#/service/TemperatureSensor
                        hkName = "NoName"
                        currentTemperature = None
                        hkiid = None
                        for characteristic in service["characteristics"]:
                            if ( characteristic["type"] == "23" ):      # Name
                                hkName = characteristic["value"]
                            if ( characteristic["type"] == "11" ):      # Current Temperature
                                currentTemperature = characteristic["value"] 
                                hkiid = characteristic["iid"]
                        deviceID = service["type"] + "-" + str(hkaid) + "-" + str(hkiid)
                        domoticzID = GetIDFromDevID(deviceID)
                        Domoticz.Debug(hkManufacturer + " : " + hkName + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID) + " - Current Temperature=" + str(currentTemperature))

                        if (domoticzID == -1):
                            nextUnit = GetNextUnit()
                            Domoticz.Debug("Create domoticz device :\"" + hkName + "\" with ID=" + str(nextUnit) + " and DeviceID=" + deviceID + " of type Temperature Sensor")
                            Domoticz.Device(Name=hkName, Unit=nextUnit, TypeName="Temperature", DeviceID=deviceID).Create()
                            domoticzID = GetIDFromDevID(deviceID)
                            Domoticz.Log("Device created: " + hkName + " - DeviceID=" + deviceID)
                        IDX = Devices[domoticzID].ID
                        # Update temperature if changed
                        if currentTemperature is not None:
                            sValue = str(currentTemperature)
                            if (Devices[domoticzID].sValue != sValue):
                                Domoticz.Status("Set Temperature to " + sValue + " for Device " + hkName + " - IDX=" + str(IDX) + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID))
                                Devices[domoticzID].Update(nValue=0, sValue=sValue)

                    # Service of type Heater Cooler
                    elif( service["type"] == "BC" ):        # https://developers.homebridge.io/#/service/HeaterCooler
                        hkName = "NoName"
                        active = None
                        currentState = None
                        activeIid = None
                        stateIid = None
                        for characteristic in service["characteristics"]:
                            if ( characteristic["type"] == "23" ):      # Name
                                hkName = characteristic["value"]
                            elif ( characteristic["type"] == "B0" ):      # Active
                                active = characteristic["value"]
                                activeIid = characteristic["iid"]
                            elif ( characteristic["type"] == "F0" ):      # Current Heater Cooler State
                                currentState = characteristic["value"]
                                stateIid = characteristic["iid"]

                        # Handle Active switch
                        if activeIid is not None:
                            deviceID = service["type"] + "-" + str(hkaid) + "-" + str(activeIid)
                            domoticzID = GetIDFromDevID(deviceID)
                            Domoticz.Debug(hkManufacturer + " : " + hkName + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID) + " - Active=" + str(active))

                            if (domoticzID == -1):
                                nextUnit = GetNextUnit()
                                Domoticz.Debug("Create domoticz device :\"" + hkName + "\" with ID=" + str(nextUnit) + " and DeviceID=" + deviceID + " of type Switch")
                                Domoticz.Device(Name=hkName, Unit=nextUnit, TypeName="Switch", DeviceID=deviceID).Create()
                                domoticzID = GetIDFromDevID(deviceID)
                                Domoticz.Log("Device created: " + hkName + " - DeviceID=" + deviceID)
                            IDX = Devices[domoticzID].ID
                            # Update status if changed
                            hkValue = 1 if active else 0
                            if (Devices[domoticzID].nValue != hkValue):
                                Domoticz.Status("Set " + ("ON" if hkValue else "OFF") + " for Device " + hkName + " - IDX=" + str(IDX) + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID))
                                Devices[domoticzID].Update(nValue=hkValue, sValue="On" if hkValue else "Off")

                        # Handle Current Heater Cooler State selector
                        if stateIid is not None:
                            deviceID = service["type"] + "-State-" + str(hkaid) + "-" + str(stateIid)
                            domoticzID = GetIDFromDevID(deviceID)
                            Domoticz.Debug(hkManufacturer + " : " + hkName + " State - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID) + " - Current State=" + str(currentState))

                            if (domoticzID == -1):
                                nextUnit = GetNextUnit()
                                Domoticz.Debug("Create domoticz device :\"" + hkName + " State\" with ID=" + str(nextUnit) + " and DeviceID=" + deviceID + " of type Selector")
                                options = {"LevelNames": "Inactive|Idle|Heating|Cooling", "LevelOffHidden": "false", "SelectorStyle": "0"}
                                Domoticz.Device(Name=hkName + " State", Unit=nextUnit, Type=244, Subtype=62, Switchtype=18, DeviceID=deviceID, Options=options).Create()
                                domoticzID = GetIDFromDevID(deviceID)
                                Domoticz.Log("Device created: " + hkName + " State - DeviceID=" + deviceID)
                            IDX = Devices[domoticzID].ID
                            # Update state if changed
                            if currentState is not None:
                                stateNames = ["Inactive", "Idle", "Heating", "Cooling"]
                                nValue = currentState * 10
                                sValue = stateNames[currentState] if currentState < len(stateNames) else "Unknown"
                                if (Devices[domoticzID].nValue != nValue):
                                    Domoticz.Status("Set State to " + sValue + " for Device " + hkName + " State - IDX=" + str(IDX) + " - DeviceID=" + deviceID + " - DomoticzID=" + str(domoticzID))
                                    Devices[domoticzID].Update(nValue=nValue, sValue=sValue)

                    elif( service["type"] == "3E"):
                        pass

                    else:
                        Domoticz.Debug("Device " + hkManufacturer + " - AID=" + str( hkaid ) + " - Type of Service=" + service["type"] + " - Not supported yet")

    def onCommand(self, Unit, Command, Level, Hue):
        if ( Devices[Unit].sValue != Command ):
            if str(Command) == "On":
                Devices[Unit].Update(nValue=1,sValue="On")
                nValue = "1"
            if str(Command) == "Off":
                Devices[Unit].Update(nValue=0,sValue="Off")
                nValue = "0"

            deviceIDsplitted = Devices[Unit].DeviceID.split("-")
            aid = deviceIDsplitted[1]
            iid = deviceIDsplitted[2]   

            # Detect device type
            if deviceIDsplitted[0] == "8C":
                # Blinds
                # We need the iid for targetposition for _setting_ a position. The iid from above is that of currentposition (for _getting_ the position).
                hkTargetPositionIid = self.deviceData[Unit]["hkTargetPositionIid"] if Unit in self.deviceData else None
                if (hkTargetPositionIid is None):
                    Domoticz.Error("Target position IID unknown, can not set.")
                    return
                iid = hkTargetPositionIid

                if Command == "Off" or Command == "Close":
                    self.setHkPositionBlinds(aid, iid, 0)
                elif Command == "On" or Command == "Open":
                    self.setHkPositionBlinds(aid, iid, 100)
                elif Command == "Set Level":
                    self.setHkPositionBlinds(aid, iid, Level)
                elif Command == "Stop":
                    Domoticz.Log("STOP command not supported in Somfy HomeKit integration.")  
                    # https://community.home-assistant.io/t/somfy-connectivity-kit-support-for-overkiz-and-or-homekit/392569/16
                    # Should be https://developers.homebridge.io/#/characteristic/HoldPosition I assume? 
            
            else:
                # Assume simple on/off switch
                Domoticz.Status("Command called for Unit=" + str(Unit) + " and DeviceID=" + Devices[Unit].DeviceID + ": Parameter '" + str(Command) + "'")
                data = "{\"characteristics\":[{\"aid\":" + aid + ",\"iid\":" + iid + ",\"value\":" + nValue + "}]}"
                Domoticz.Debug(data)

                try:
                    self.httpConnGet.Send({'Verb':'PUT', 'URL':'/characteristics', 'Headers': self.headers, 'Data': data})
                except Exception:
                    Domoticz.Error("Problem sending command to accessory : " + data)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug("Connection " + Connection.Name + " disconnected")
        self.GetSent=0

    def onHeartbeat(self):
        Domoticz.Debug("Refreshing Accessories Status")
        if ( self.GetSent == 1 ):
            Domoticz.Debug("No Data received since last heartbeat. Disconnecting")
            self.httpConnGet.Disconnect()
            self.GetSent=0
        elif (self.httpConnGet != None and ( self.httpConnGet.Connected() )):
            Domoticz.Debug("Connection is alive. Sending /accessories command")
            self.httpConnGet.Send({'Verb':'GET', 'URL':'/accessories', 'Headers': self.headers})
            self.GetSent=1
        else:
            Domoticz.Log("Connection Lost. Reconnecting.")
            self.httpConnGet.Connect(Timeout=self.Timeout)

    def setDomoStatusBlinds(self, device, hkCurrentPosition):
        # hkCurrentPosition is a uint between 0 and 100 where 0 is closed and 100 is open - "open" being the _window_ is open (the cover is rolled up in the case)
        sValue = str(hkCurrentPosition)
        nValue = 2
        if hkCurrentPosition == 0:
            nValue = 0
        elif hkCurrentPosition == 100:
            nValue = 1
        if (device.sValue != sValue):
            Domoticz.Status("Set Position from '"+device.sValue+"' to '" + sValue + "' for Device " + device.Name + " (" + str( device.ID ) + " )")
            device.Update(nValue=nValue, sValue=sValue)
            return True
        else:
            return False

    def setHkPositionBlinds(self, aid, iid, value):
        data = "{\"characteristics\":[{\"aid\":" + aid + ",\"iid\":" + iid + ",\"value\":" + str(value) + "}]}"
        Domoticz.Debug(data)
        try:
            Domoticz.Status("Command called for aid=" + str(aid) + " iid=" + str(iid) + ": Value '" + str(value) + "'")
            self.httpConnGet.Send({'Verb':'PUT', 'URL':'/characteristics', 'Headers': self.headers, 'Data': data})
        except Exception:
            Domoticz.Error("Problem sending command to accessory : " + data)


global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onTimeout(Connection):
    global _plugin
    _plugin.onTimeout(Connection)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions

def GetIDFromDevID(devid):
    for Device in Devices:
        if ( devid == Devices[Device].DeviceID ):
            return Device
    return -1

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
        Domoticz.Debug("Device DeviceID : " + str(Devices[x].DeviceID))
    return

def DumpHTTPResponseToLog(httpResp, level=0):
    if (level==0): Domoticz.Debug("HTTP Details ("+str(len(httpResp))+"):")
    indentStr = ""
    for x in range(level):
        indentStr += "----"
    if isinstance(httpResp, dict):
        for x in httpResp:
            if not isinstance(httpResp[x], dict) and not isinstance(httpResp[x], list):
                Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")
            else:
                Domoticz.Debug(indentStr + ">'" + x + "':")
                DumpHTTPResponseToLog(httpResp[x], level+1)
    elif isinstance(httpResp, list):
        for x in httpResp:
            Domoticz.Debug(indentStr + "['" + x + "']")
    else:
        Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")


def GetNextUnit():
    if not Devices:
        return 1
    return max(Devices.keys()) + 1

