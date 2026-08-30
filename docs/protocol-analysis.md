# RemoteEnvServer Protocol Analysis

Source: `RemoteEnvServer/docs/api.md` (2016 lines), cross-checked with `remote_env_server/models.py`.

## Canonical data types

New messages use exactly: `wifi`, `bluetooth`, `cell`, `gps`, `gnss`, `sensor`, `environment`, `other`.
Aliases accepted by the server but not emitted by this SDK: `ble`, `bluetooth_data` -> `bluetooth`; `cellular` -> `cell`; `gnss.route` -> `gnss`; `gps.route` -> `gps`; `sensor.*` -> `sensor`. Unknown historical values normalize to `other` only when reading legacy data.

## Data models and standard fields

- `wifi`: envelope data fields `scan_started_at:int?`, `scan_finished_at:int?`, `interface:str?`, `is_connected:bool=False`, `gateway:str?`, `dns_servers:list[str]`, `ip_address:str?`, `networks:list[WiFiNetwork]`. Network fields: `ssid:str?`, `bssid:str?` MAC, `signal_dbm:float?`, `rssi:float?`, `frequency_mhz:float?`, `channel:int?`, `band:2_4ghz|5ghz|6ghz|unknown?`, `security:list[str]?`, `hidden:bool?`, `timestamp:int?`.
- `bluetooth`: `scan_started_at:int?`, `scan_finished_at:int?`, `technology:ble|bluetooth_classic|unknown`, `is_enabled:bool?`, `devices:list[BluetoothDevice]`. Device fields: `address:str?`, `address_type:public|random|static_random|unknown?`, `name:str?`, `is_connected:bool?`, `is_paired:bool?`, `rssi:float?`, `tx_power:float?`, `manufacturer_id:int?`, `manufacturer_data:Base64?`, `service_uuids:list[str]?`, `service_data:dict[str,Base64]?`, `raw:Base64?`, `rawHex:HEX?`, `rawLength:int?`, `timestamp:int?`.
- `cell`: `observed_at:int?`, `network_type:str?`, `sim_slot:int?`, `is_connected:bool?`, `registered:bool?`, `serving:CellObservation?`, `neighbors:list[CellObservation]`. Cell fields: `radio:str?`, `technology:str?`, `mcc:str?`, `mnc:str?`, `lac:int?`, `tac:int?`, `cid:int?`, `pci:int?`, `arfcn:int?`, `rssi:float?`, `signal_dbm:float?`, `rsrp:float?`, `rsrq:float?`, `asu:float?`.
- `gps`: `fix_at:int?`, `provider:str?`, `latitude:float?`, `longitude:float?`, `altitude_m:float?`, `accuracy_m:float?`, `speed_mps:float?`, `bearing_deg:float?`, `satellites:int?`, `fix_quality:str?`, `mocked:bool?`, `points:list[GPSPoint]`. Point fields: `timestamp:int?`, `latitude:float`, `longitude:float`, `altitude_m:float?`, `accuracy_m:float?`.
- `gnss`: `fix_at:int?`, `constellation:str?`, `satellites:list[GNSSSatellite]`. Satellite required fields: `type:gps|glonass|galileo|beidou|qzss|navic|sbas|unknown`, `svid:int`; optional `azimuth_deg`, `elevation_deg`, `frequency_mhz`, `snr_db`, `almanac`, `ephemeris`, `used`.
- `sensor`: `sensor_type:str?`, `sensor:str?`, `unit:str?`, `sampling_hz:float?`, `timestamp:int?`, `value:float?`, `values:list[float]?`, `samples:list[SensorSample]`, `readings:list[SensorSample]`. Sample required `timestamp:int`, optional `x`, `y`, `z`, `value`.
- `environment`: `timestamp:int?`, `readings:dict[str, EnvironmentReading]`; reading requires `value:float` and unit `degC|percent|hPa|ppm|ug/m3|lux|dBA`.
- `other`: arbitrary JSON object with no standard fields.

Server model is `extra=allow` for all environment data and nested observation models. `None` is allowed by the model; SDK omits `None` by default to keep payloads compact. Standard fields are explicit keyword-only parameters; `custom` is merged and conflicts raise `RemoteEnvValidationError`.

## Envelope

Collector sends one `environment_data` Text Frame per canonical data type, even when one `upload()` call contains multiple packages. Required fields: `type=environment_data`, `version=1`, configured `device_id`, canonical `data_type`, positive epoch-millisecond `timestamp`, nonnegative strictly increasing `sequence` per `(device_id,data_type)`, and object `data`. Envelope extras are allowed by the server but SDK does not expose protocol construction as the normal API.

## Auth and lifecycle

First frame must be `auth`. Collector auth requires `role=collector`, token, device_id, and device `{name,device_type,capabilities}`. Consumer auth accepts optional device_id/device; SDK supplies stable defaults. Success emits `auth_result`, then `device_list`. Consumer subscription uses `subscribe`/`refresh`/`unsubscribe` with `data_types:list[str]`, max 32; the SDK accepts one type or an iterable and emits canonical values.

## Receiver and ACK

A single receiver dispatches `auth_result`, `device_list`, `data_result`, `environment_data`, `subscription_result`, `pong`, and `error`. Collector upload waits for matching `data_result`; a server error maps to SDK exceptions. Consumer `environment_data` updates a `(device_id,data_type)` cache, notifies waiters, and invokes callbacks outside locks. `cached=true` is replay, not fresh data; `refresh=true` is a cache replay marker.

## Heartbeat, reconnect, limits

SDK sends application `heartbeat` with positive epoch milliseconds on a background thread and also supports server `pong`. Reconnect reopens the socket, re-authenticates, waits for `device_list`, and restores consumer subscriptions. Sequence uses a durable JSON file (configurable) and `max(now_ms,last+1)`; no reset on reconnect or process restart. The server limits frames to 1 MiB, 60 uploads/minute/device, 500 sessions, 500 devices/session, and 100 queued sends.

## Documented/runtime discrepancy

`api.md` documents `rssi`, while the server model also accepts `signal_dbm`; `frequency_mhz` and some signal fields are typed as strict floats in the current model despite examples using integers. The SDK follows the runtime model where validation matters and preserves extensions. `mcc`/`mnc` are strings in the runtime model to retain leading zeroes, although the prose permits integer/string.
