import os

from remote_env_sdk import Bluetooth_Package, Cell_Package, GPS_Package, RemoteEnvSDK, WiFi_Package

SERVER_URL = os.environ.get("REMOTE_ENV_SERVER_URL", "ws://127.0.0.1:8000/ws")
TOKEN = os.environ["REMOTE_ENV_COLLECTOR_TOKEN"]
DEVICE_ID = os.environ.get("REMOTE_ENV_DEVICE_ID", "sdk-example-collector")

sdk = RemoteEnvSDK(SERVER_URL)
sdk.set_collector_token(TOKEN, DEVICE_ID)
sdk.connect_collector()
try:
    wifi = WiFi_Package().add_wifi(ssid="SDK-Example-WiFi", bssid="00:11:22:33:44:55")
    bluetooth = Bluetooth_Package(technology="ble").add_bluetooth(name="SDK-Example-Beacon", address="AA:BB:CC:DD:EE:FF", rssi=-61)
    cell = Cell_Package(network_type="LTE").add_cell(radio="LTE", mcc="460", mnc="01", cid=1001)
    gps = GPS_Package().add_gps(latitude=25.0330, longitude=121.5654, altitude_m=20.0)
    print(sdk.upload(wifi_package=wifi, bluetooth_package=bluetooth, cell_package=cell, gps_package=gps))
finally:
    sdk.disconnect_collector()
