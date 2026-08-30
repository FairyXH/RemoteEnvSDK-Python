import os

from remote_env_sdk import RemoteEnvSDK
from remote_env_sdk.exceptions import RemoteEnvTimeoutError

SERVER_URL = os.environ.get("REMOTE_ENV_SERVER_URL", "ws://127.0.0.1:8000/ws")
TOKEN = os.environ["REMOTE_ENV_CLIENT_TOKEN"]
DEVICE_ID = os.environ.get("REMOTE_ENV_DEVICE_ID", "sdk-example-collector")

client = RemoteEnvSDK(SERVER_URL)
client.set_client_token(TOKEN)
client.connect_client()
try:
    print("devices:", client.get_device_list())
    client.subscribe(DEVICE_ID, "wifi")
    try:
        data = client.get_data(DEVICE_ID, "wifi", timeout=10)
    except RemoteEnvTimeoutError:
        print("10 秒内没有收到数据")
    else:
        print("wifi:", data.items)
finally:
    client.disconnect_client()
