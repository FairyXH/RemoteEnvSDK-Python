import os

from remote_env_sdk import RemoteEnvSDK, WiFi_Package

SERVER_URL = os.environ.get("REMOTE_ENV_SERVER_URL", "ws://127.0.0.1:8000/ws")
TOKEN = os.environ["REMOTE_ENV_COLLECTOR_TOKEN"]
DEVICE_ID = os.environ.get("REMOTE_ENV_DEVICE_ID", "sdk-example-collector")

sdk = RemoteEnvSDK(SERVER_URL)
sdk.set_collector_token(TOKEN, DEVICE_ID)
sdk.connect_collector()
try:
    wifi = WiFi_Package()
    wifi.add_wifi(ssid="SDK-Example-WiFi", bssid="00:11:22:33:44:55", custom={"source": "collector_basic"})
    print(sdk.upload(wifi_package=wifi))
finally:
    sdk.disconnect_collector()
