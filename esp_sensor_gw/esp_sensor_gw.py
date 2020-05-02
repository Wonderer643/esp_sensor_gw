#!/usr/bin/env python3

""" Some documentation string"""

#from bluepy.btle import Scanner, DefaultDelegate, ScanEntry
from bluepy.btle import *
import os
import time
import struct
import paho.mqtt.client as mqtt
import json
import os

BLE_DEVICE=int(os.getenv('BLE_DEVICE',0))
SENSOR_NAME=os.getenv('SENSOR_NAME','ESP_S')
SCAN_TIME=float(os.getenv('SCAN_TIME',3.0))
WAIT_NOTIFY_TIME=float(os.getenv('WAIT_NOTIFY_TIME',10.0))
MQTT_HOST=os.getenv('MQTT_HOST','192.168.2.50')
MQTT_PORT=int(os.getenv('MQTT_PORT',1883))
MQTT_TIMEOUT=int(os.getenv('MQTT_TIMEOUT',60))
MQTT_MAIN_TOPIC=os.getenv('MQTT_MAIN_TOPIC','sensors')

esp_sensor_scan_entry=None

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print ("Discovered device", dev.addr)
            if (str(dev.getValueText(9)).startswith(SENSOR_NAME) and dev.connectable):
                print(f"Sensor {dev.getValueText(9)} found at {dev.addr}")
                global esp_sensor_scan_entry
                esp_sensor_scan_entry = dev
        elif isNewData:
            print ("Received new data from", dev.addr)

class NotificationDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        #print(f"Received notification data for {cHandle} formatted {format(cHandle)} with {data} formatted {format(data)}")
        processNotification(cHandle,data)

def processNotification(handle,data):
    jsObj = {}
    jsObj['DeviceName'] = dev_info.name
    jsObj['DeviceAddr'] = str(dev_info.addr)
    jsObj['ServiceUUID'] = str(all_info[handle].serv_uuid)
    jsObj['ServiceName'] = all_info[handle].serv_uuid.getCommonName()
    jsObj['CharacteristicUUID'] = str(all_info[handle].uuid)
    jsObj['CharacteristicName'] = all_info[handle].uuid.getCommonName()

#    print(f"Notification from service {all_info[handle].serv_uuid.getCommonName()} for characteristic {all_info[handle].uuid.getCommonName()}")
    if all_info[handle].uuid == 0x2A19:
#        print(f"Value = {int.from_bytes(data, byteorder='big')}")
        jsObj['Value'] = int.from_bytes(data, byteorder='big')
    else:
        if str(UUID(0x2901)) in all_info[handle].descs.keys():
            user_info = all_info[handle].descs[str(UUID(0x2901))].value
#            print(f"{user_info.decode()} = ", end = '')
            jsObj['UserInformation'] = user_info.decode()
#        else:
#            print("Value = ", end = '')
        if str(UUID(0x2904)) in all_info[handle].descs.keys():
            (m_format, m_exponent, m_unit, m_namespace, m_description) = struct.unpack('=BbHBH',all_info[handle].descs[str(UUID(0x2904))].value)
            #decodedData = decodeData(data,m_format) * 10**m_exponent
            decodedData = decodeData(data,m_format)
            unit_name = AssignedNumbers.getCommonName(UUID(m_unit))
#            print(f"{decodedData} Unit is '{unit_name}'")
            jsObj['Value'] = decodedData
            jsObj['ValueUnitName'] = unit_name
            if m_exponent != 0:
                jsObj['ValueExponenta'] = m_exponent
        else:
#            print(data)
            jsObj['Value'] = data
    topic = MQTT_MAIN_TOPIC + '/' + jsObj['DeviceAddr'] + '/' + jsObj['ServiceUUID'] + '/' + jsObj['CharacteristicUUID']
    jsonStr = json.dumps(jsObj)
    print(jsonStr) 
    mqttc.publish(topic,jsonStr)

def decodeData(data,format):
    switcher = {
        1:lambda:struct.unpack('?',data[:1])[0],                                             #Boolean. Read only first byte in case format is wrong
        2:lambda:struct.unpack('B',data[:1])[0] & 0x03 ,                                     #unsigned 2-bit integer
        3:lambda:struct.unpack('B',data[:1])[0] & 0x0f ,                                     #unsigned 4-bit integer
        4:lambda:struct.unpack('B',data[:1])[0] ,                                            #unsigned 8-bit integer
        5:lambda:struct.unpack('H',data[:2])[0] & 0x0fff,                                    #unsigned 12-bit integer
        6:lambda:struct.unpack('H',data[:2])[0],                                             #unsigned 16-bit integer
        7:lambda:struct.unpack('L',data[:4])[0] & 0x00ffffff,                                #unsigned 24-bit integer
        8:lambda:struct.unpack('L',data[:4])[0],                                             #unsigned 32-bit integer
        9:lambda:struct.unpack('Q',data[:8])[0] & 0xffffffffffff,                            #unsigned 48-bit integer
        10:lambda:struct.unpack('Q',data[:8])[0],                                            #unsigned 64-bit integer
        11:lambda:struct.unpack('Q',data[:8])[0]+(struct.unpack('Q',data[8:16])[0]<<64),     #unsigned 128-bit integer
        12:lambda:struct.unpack('b',data[:1])[0] ,                                           #signed 8-bit integer
        13:lambda:struct.unpack('h',data[:2])[0] & 0x0fff,                                   #signed 12-bit integer
        14:lambda:struct.unpack('h',data[:2])[0],                                            #signed 16-bit integer
        15:lambda:struct.unpack('l',data[:4])[0] & 0x00ffffff,                               #signed 24-bit integer
        16:lambda:struct.unpack('l',data[:4])[0],                                            #signed 32-bit integer
        17:lambda:struct.unpack('q',data[:8])[0] & 0xffffffffffff,                           #signed 48-bit integer
        18:lambda:struct.unpack('q',data[:8])[0],                                            #signed 64-bit integer
        19:lambda:struct.unpack('Q',data[:8])[0]+(struct.unpack('q',data[8:16])[0]<<64),     #signed 128-bit integer
        20:lambda:round(struct.unpack('f',data[:4])[0], 2),                                  #32-bit floating point
        21:lambda:round(struct.unpack('d',data[:8])[0], 2),                                  #64-bit floating point
        25:lambda:data.decode("utf-8"),                                                      #UTF-8 string
        26:lambda:data.decode("utf-16")                                                      #UTF-8 string
    }
     
    func = switcher.get(format,lambda :data)
    return func()

def charDescs(chara,all_descs):
    charaDescriptors = {}

    for desc in all_descs:
        if desc.handle > chara.valHandle:
            if desc.uuid in (0x2800, 0x2801, 0x2803):
                break
            desc.value = desc.read()
            charaDescriptors[str(desc.uuid)] = desc
    return charaDescriptors
            

def enable_notify(chara):
    setup_data = b"\x01\x00"
    
    if str(UUID(0x2902)) in chara.descs.keys():
        print(f"Enabling notifications for characteristic {chara.uuid}")
        try:
            chara.descs[str(UUID(0x2902))].write(setup_data, withResponse=True)
        except BTLEException as e:
            print(f"Error enabling notification for characteristic {chara.uuid} with descriptor {chara.descs[str(UUID(0x2902))].uuid}")
    else:
        print(f"No descriptor 0x2902 for notification enabling. Skipping this characteristic {chara.uuid}")


def cache_all(dev):
    global all_info

    all_info = {}
 
    global dev_info
    dev_info = dev

    print("Caching all services") 
    try:
        all_srv = dev.getServices()
    except BTLEException as e:
        print(f"Error getting services list for {dev}")
        dev.disconnect()
        return
    print(f"Total {len(all_srv)} services")

    print("Caching all characterists")
    try:
        all_chars = dev.getCharacteristics()
    except BTLEException as e:
        print(f"Error getting all characteristis for {dev}")
        dev.disconnect()
        return
    print(f"Total {len(all_chars)} characteristics")

    print("Caching all descriptors")
    try:
        all_descs = dev.getDescriptors()
    except BTLEException as e:
        print(f"Error getting all descriptors for {dev}")
        dev.disconnect()
        return
    print(f"Total {len(all_descs)} descriptors")
    
    print("Building unified dictionary with descriptor values")
    for char in all_chars:
        charHandle = char.getHandle()
        for serv in all_srv:
            if charHandle > serv.hndStart and charHandle < serv.hndEnd:
                char.serv_uuid = serv.uuid
                if serv.uuid == AssignedNumbers.genericAccess and char.uuid == AssignedNumbers.deviceName:
                    dev_info.name = char.read().decode()
                break
        char.descs = charDescs(char,all_descs)
        all_info[charHandle] = char 

def read_services(dev):

    cache_all(dev)

    print("Registering for Notifications")

    print("Subscribe to notifications for all supported characteristics")
    for char in all_info.values():
        if (char.uuid == UUID(0x1800) or char.uuid == UUID(0x1801)):
            continue
        if (char.properties & Characteristic.props["NOTIFY"] and char.properties & Characteristic.props["READ"]):
            enable_notify(char)

    print("Start reading for notifications")
    dev.setDelegate(NotificationDelegate())

    while True:
        if dev.waitForNotifications(WAIT_NOTIFY_TIME):
            continue
        else:
           print(f"Seems no new data received in {WAIT_NOTIFY_TIME} seconds. Retarting the connection")
           break

    dev.disconnect()

os.system('hciconfig hci0 down')
os.system('hciconfig hci0 up')

print(f"Connecting to MQTT broker {MQTT_HOST}:{MQTT_PORT}")
mqttc = mqtt.Client()
mqttc.connect(MQTT_HOST, MQTT_PORT, MQTT_TIMEOUT)
mqttc.loop_start()

scanner = Scanner(BLE_DEVICE).withDelegate(ScanDelegate())
while True:
    while (not esp_sensor_scan_entry):
        print("New scan cycle")
        try:
            devices = scanner.scan(SCAN_TIME)
        except BTLEException as e:
            print("Error while scanning for BLE devices")
            break

    if esp_sensor_scan_entry:
        try:
            print(f'Connecting to {esp_sensor_scan_entry.addr}')
            esp_sensor_device = Peripheral(esp_sensor_scan_entry.addr, esp_sensor_scan_entry.addrType, esp_sensor_scan_entry.iface)
        except BTLEException as e:
           print(f"Error while connecting to BLE device {esp_sensor_scan_entry.addr}")
           print(e)
           esp_sensor_scan_entry = None
           break
        try:
            read_services(esp_sensor_device)
        except BTLEDisconnectError as e:
            print("Device disconnected. Restarting scan")
        esp_sensor_scan_entry = None
     
          

