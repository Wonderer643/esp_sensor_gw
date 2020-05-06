# esp_sensor_gw

Python based simlpe BLE->MQTT gateway for scanning the nearby devices and connecct to them in case name pattern match.

On connect get list of characteristics and descriptors, then subscribe to BLE notifications.

On data receive format the data according to the Characteristic Presentation Format descriptor and output to the MQTT broker as JSON data.
MQTT topic is build as "sensor/<Device_Address>/<Service_UUID>/<Characteristic_UUID>"

Run as a standalone script. Also a Dockerfile provide, to run as docker image.

Supports reconnect both to the BLE devices and MQTT broker. 
