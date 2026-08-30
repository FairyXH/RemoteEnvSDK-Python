# RemoteEnvSDK

Typed Python client for RemoteEnvServer. Application code uses Python packages; JSON Envelope and WebSocket details remain internal.

## Collector

```python
from remote_env_sdk import RemoteEnvSDK, WiFi_Package

sdk = RemoteEnvSDK("wss://example.invalid/envser/ws")
sdk.set_collector_token(collector_token, "SDKTest")
sdk.connect_collector()

wifi = WiFi_Package()
wifi.add_wifi(
    ssid="SDK-Test-1",
    bssid="00:11:22:33:44:55",
    custom={"sdk_test": True},
)
wifi.add_wifi(ssid="SDK-Test-2", bssid="AA:BB:CC:DD:EE:FF")

result = sdk.upload(wifi_package=wifi)
print(result)
```

`upload()` accepts multiple packages and automatically sends one `environment_data` frame per package:

```python
sdk.upload(
    wifi_package=wifi,
    bluetooth_package=bluetooth,
    cell_package=cell,
    gps_package=gps,
)
```

The SDK creates `timestamp`, `device_id`, and a durable per-type `sequence`. `custom` fields are preserved; a custom key that conflicts with a standard field raises `RemoteEnvValidationError`. `None` fields are omitted.

## Consumer

```python
from remote_env_sdk import RemoteEnvSDK

client = RemoteEnvSDK("wss://example.invalid/envser/ws")
client.set_client_token(client_token)
client.connect_client()

print(client.get_device_list())
client.subscribe("SDKTest", "wifi")
data = client.get_data("SDKTest", "wifi", timeout=10)
print(data.items)
```

`get_data(..., timeout=0)` returns current cache or raises `RemoteEnvTimeoutError`; `timeout=None` waits indefinitely; `fresh=True` waits for a newer sequence. Register callbacks with `client.on_data(callback)`. Callback failures are isolated from the receiver.

## Packages

Public packages map directly to the eight canonical server types: `WiFi_Package`, `Bluetooth_Package`, `Cell_Package`, `GPS_Package`, `GNSS_Package`, `Sensor_Package`, `Environment_Package`, and `Other_Package`.

All standard fields are explicit keyword-only parameters in package constructors/add methods. Package serialization is available through `to_dict()` for advanced use.

## Protocol behavior

- Canonical types: `wifi`, `bluetooth`, `cell`, `gps`, `gnss`, `sensor`, `environment`, `other`.
- Consumer subscription uses server-required `data_types` arrays.
- The receiver handles auth results, device lists, ACKs, data, errors, and pong messages.
- Heartbeats use the documented application `heartbeat` message.
- Unexpected disconnects trigger exponential reconnect and restore Consumer subscriptions.
- Tokens are never stored in source or logged by this SDK.

Protocol analysis and the documented/runtime differences are recorded in `docs/protocol-analysis.md`.

## Development

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m compileall -q src tests
```

Real-server integration is intentionally not run without `REMOTE_ENV_COLLECTOR_TOKEN` and `REMOTE_ENV_CLIENT_TOKEN` supplied by the operator. No credentials are included in this repository.
