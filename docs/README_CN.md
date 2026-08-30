# RemoteEnvSDK 中文开发者使用手册

> 版本：RemoteEnvSDK 0.2.0
>
> 本手册以当前 SDK 源码、测试和 `RemoteEnvServer/docs/api.md` 为准。示例中的服务器地址、Token 和设备 ID 均为占位值。请勿把真实 Token 写入源码、文档、测试、日志或 Git。

## 目录

1. [SDK 简介](#1-sdk-简介)
2. [工作原理](#2-工作原理)
3. [安装](#3-安装)
4. [快速开始](#4-快速开始)
5. [SDK 初始化](#5-sdk-初始化)
6. [Collector 采集端](#6-collector-采集端)
7. [Client 客户端](#7-client-客户端)
8. [Package 体系](#8-package-体系)
9. [WiFi 数据](#9-wifi-数据)
10. [Bluetooth 数据](#10-bluetooth-数据)
11. [Cell 数据](#11-cell-数据)
12. [GPS 数据](#12-gps-数据)
13. [GNSS、Sensor、Environment 和 Other](#13-gnsssensorenvironment-和-other)
14. [自定义字段 custom](#14-自定义字段-custom)
15. [多条数据](#15-多条数据)
16. [数据上传](#16-数据上传)
17. [获取设备列表](#17-获取设备列表)
18. [数据订阅](#18-数据订阅)
19. [获取数据](#19-获取数据)
20. [timeout](#20-timeout)
21. [数据缓存](#21-数据缓存)
22. [callback](#22-callback)
23. [连接状态、心跳和生命周期](#23-连接状态心跳和生命周期)
24. [自动重连](#24-自动重连)
25. [异常处理](#25-异常处理)
26. [关闭连接](#26-关闭连接)
27. [完整 Collector 示例](#27-完整-collector-示例)
28. [完整 Client 示例](#28-完整-client-示例)
29. [Collector 与 Client 联调](#29-collector-与-client-联调)
30. [API 参考](#30-api-参考)
31. [常见问题](#31-常见问题)
32. [最佳实践](#32-最佳实践)

---

## 1. SDK 简介

RemoteEnvSDK 是 RemoteEnvServer 的 Python 客户端 SDK，用于：

- 让采集程序向 RemoteEnvServer 上传环境数据；
- 让客户端程序发现可访问设备并订阅数据；
- 用 Python Package、函数参数和对象属性替代手写 JSON；
- 处理 WebSocket 连接、认证、上传确认、缓存、回调、心跳和断线恢复。

典型拓扑如下：

```text
采集设备/采集程序
        │
        │ Collector Token
        │ Collector
        ▼
RemoteEnvServer
        ▲
        │ Client Token
        │ Client / Consumer
        │
用户程序
```

RemoteEnvSDK 不负责数据库、GUI、命令行管理或管理员 HTTP API。Token 的创建、授权和撤销由 RemoteEnvServer 管理端完成。

### 为什么不直接写 JSON

服务端内部使用 WebSocket JSON Envelope，例如 `data_type`、`device_id`、`sequence`、`timestamp` 和 `data`。SDK 对这些协议字段进行封装，用户通常只需创建 Package：

```python
from remote_env_sdk import RemoteEnvSDK, WiFi_Package

sdk = RemoteEnvSDK("wss://example.invalid/envser/ws")
sdk.set_collector_token("YOUR_COLLECTOR_TOKEN", "example-collector")
sdk.connect_collector()

wifi = WiFi_Package()
wifi.addwifi(
    ssid="Example-WiFi",
    bssid="00:11:22:33:44:55",
)

sdk.upload(wifi_package=wifi)
```

用户不需要手动构造 `environment_data` Envelope，也不需要手动填写协议序列号。

---

## 2. 工作原理

### Collector

Collector 负责：

1. 使用 `device` 类型 Token 认证；
2. 绑定一个稳定的 `device_id`；
3. 上传一个或多个数据 Package；
4. 等待服务器返回 `data_result`。

### Client

Client 在服务端协议中使用 `consumer` WebSocket 角色，负责：

1. 使用 `consumer` 类型 Token 认证；
2. 获取当前有权限访问的设备列表；
3. 订阅某个 Collector 的一种或多种数据类型；
4. 接收缓存回放和实时 `environment_data`；
5. 通过 `get_data()` 读取已经反序列化的 Package。

### 用户需要理解的几个概念

| 概念 | 说明 |
|---|---|
| Token | WebSocket 身份凭据。Collector 使用 device Token，Client 使用 consumer Token。 |
| `device_id` | 设备稳定标识。Collector Token 必须绑定对应 ID；Client 的 ID 可由服务端首次连接时生成或绑定。 |
| `data_type` | 数据类型。SDK 使用 8 个 canonical 值：`wifi`、`bluetooth`、`cell`、`gps`、`gnss`、`sensor`、`environment`、`other`。 |
| `timestamp` | 数据采集或协议事件的 Unix epoch 毫秒时间。上传时由 SDK 自动生成 Envelope 时间。 |
| `sequence` | 同一设备、同一数据类型的上传顺序。SDK 自动生成并持久化。 |
| cached | Client 收到的数据是否来自服务端最新缓存。`True` 表示缓存回放，不代表新采样。 |

---

## 3. 安装

项目当前通过 `pyproject.toml` 定义，包名为 `remote-env-sdk`，Python 要求为 3.10 或更高版本，运行依赖为 `websocket-client>=1.8`。

### 从源码安装

在 SDK 根目录执行：

```powershell
python -m pip install .
```

开发模式安装：

```powershell
python -m pip install -e .
```

安装测试依赖：

```powershell
python -m pip install -e ".[test]"
```

### 不安装时运行源码

```powershell
$env:PYTHONPATH = "src"
python examples/package_offline.py
```

---

## 4. 快速开始

下面示例展示最小 Collector 流程。它需要通过环境变量提供真实 Token：

```python
import os

from remote_env_sdk import RemoteEnvSDK, WiFi_Package

server_url = os.environ.get(
    "REMOTE_ENV_SERVER_URL",
    "ws://127.0.0.1:8000/ws",
)
collector_token = os.environ["REMOTE_ENV_COLLECTOR_TOKEN"]
device_id = os.environ.get("REMOTE_ENV_DEVICE_ID", "example-collector")

sdk = RemoteEnvSDK(server_url)
sdk.set_collector_token(collector_token, device_id)
sdk.connect_collector()

try:
    wifi = WiFi_Package()
    wifi.addwifi(
        ssid="Example-WiFi",
        bssid="00:11:22:33:44:55",
    )
    result = sdk.upload(wifi_package=wifi)
    print(result)
finally:
    sdk.disconnect_collector()
```

网络示例位于：

```text
examples/collector_basic.py
```

---

## 5. SDK 初始化

### 构造函数

```python
RemoteEnvSDK(
    server_url,
    *,
    sequence_path=None,
    transport_factory=None,
    connect_timeout=10.0,
    heartbeat_interval=15.0,
    ssl_verify=True,
)
```

参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `server_url` | `str` | 无 | RemoteEnvServer WebSocket 地址，例如 `wss://example.invalid/envser/ws`。 |
| `sequence_path` | `str | None` | `None` | sequence 持久化文件。未指定时使用用户目录下的 `.remote_env_sdk_sequences.json`。 |
| `transport_factory` | callable | None | `None` | 高级测试参数，用于注入 Fake Transport。普通用户不需要设置。 |
| `connect_timeout` | `float` | `10.0` | 认证和订阅等待的默认超时时间。 |
| `heartbeat_interval` | `float` | `15.0` | 应用层 heartbeat 发送间隔，单位为秒。 |

推荐把服务器地址也放在环境变量中：

```python
server_url = os.environ.get(
    "REMOTE_ENV_SERVER_URL",
    "wss://example.invalid/envser/ws",
)
sdk = RemoteEnvSDK(server_url)
```

---

## 6. Collector 采集端

### 配置 Token 和设备 ID

```python
sdk.set_collector_token(
    token,
    device_id,
)
```

真实签名：

```python
set_collector_token(self, token: str, device_id: str) -> RemoteEnvSDK
```

`device_id` 必须是非空、长度不超过 128 个字符的字符串。该方法返回 SDK 自身，因此可以链式调用：

```python
sdk.set_collector_token(token, "example-collector")
```

### 连接 Collector

```python
sdk.connect_collector()
```

SDK 会发送 Collector 认证所需的设备元数据。当前实现使用：

- `name`：配置的 `device_id`；
- `device_type`：`python`；
- `capabilities`：`["environment_data"]`。

连接失败、Token 无效或认证超时时会抛出 SDK 异常。

### 断开 Collector

```python
sdk.disconnect_collector()
```

当前版本没有统一的 `sdk.close()` 方法。请使用角色对应的断开方法。

---

## 7. Client 客户端

### 配置 Client Token

```python
sdk.set_client_token(token)
```

真实签名：

```python
set_client_token(self, token: str) -> RemoteEnvSDK
```

### 连接 Client

```python
sdk.connect_client()
```

当前 SDK 调用 Consumer 认证时不主动传入 `device_id` 和 `device`，服务端会按照协议生成或绑定 Consumer 身份。

### 完整调用链

```python
sdk.set_client_token(client_token)
sdk.connect_client()
devices = sdk.get_device_list()
sdk.subscribe("example-collector", "wifi")
data = sdk.get_data("example-collector", "wifi", timeout=10)
```

---

## 8. Package 体系

当前公开导出的 Package 与服务端 8 个 canonical 数据类型一一对应：

| Python 类型 | `data_type` |
|---|---|
| `WiFi_Package` | `wifi` |
| `Bluetooth_Package` | `bluetooth` |
| `Cell_Package` | `cell` |
| `GPS_Package` | `gps` |
| `GNSS_Package` | `gnss` |
| `Sensor_Package` | `sensor` |
| `Environment_Package` | `environment` |
| `Other_Package` | `other` |

所有 Package 都支持：

```python
package.to_dict()
package.serialize()
```

`to_dict()` 是高级检查接口。正常上传时直接把 Package 传给 `sdk.upload()`。

### Package 的通用行为

- 标准字段通过显式函数参数传入；
- 扩展字段通过 `custom` 传入；
- `None` 字段在序列化时省略；
- 多条同类型记录保存在同一个 Package 内；
- Package 不负责 WebSocket 连接；
- `len(package)` 对 WiFi、Bluetooth 返回记录数量；
- `package.items` 对 WiFi、Bluetooth 返回记录字典列表。

注意：当前 Package 使用 dataclass 实现，其构造签名中包含内部 `_data` 参数。普通用户不要直接填写 `_data`，请使用公开字段和 `add_*` 方法。

---

## 9. WiFi 数据

### 创建 Package

```python
wifi = WiFi_Package()
```

构造函数实际支持的字段：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `scan_started_at` | `int | None` | `None` | 扫描开始时间，Unix epoch 毫秒。 |
| `scan_finished_at` | `int | None` | `None` | 扫描结束时间，Unix epoch 毫秒。 |
| `interface` | `str | None` | `None` | 扫描接口名称。 |
| `is_connected` | `bool` | `False` | 当前是否连接 Wi-Fi。为 `True` 时必须提供连接详情。 |
| `gateway` | `str | None` | `None` | IPv4 或 IPv6 网关地址。 |
| `dns_servers` | `list[str]` | `[]` | DNS 地址列表。 |
| `ip_address` | `str | None` | `None` | 当前接口 IP 地址。 |

### 添加 Wi-Fi observation

实际签名：

```python
wifi.add_wifi(
    *,
    ssid: str | None = None,
    bssid: str | None = None,
    signal_dbm: float | None = None,
    rssi: float | None = None,
    frequency_mhz: float | None = None,
    channel: int | None = None,
    band: str | None = None,
    security: list[str] | None = None,
    hidden: bool | None = None,
    timestamp: int | None = None,
    custom: dict[str, Any] | None = None,
) -> WiFi_Package
```

字段说明：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `ssid` | `str | None` | 否 | Wi-Fi 名称。隐藏网络可以省略或传 `None`。 |
| `bssid` | `str | None` | 否 | 冒号分隔的 MAC 地址。 |
| `signal_dbm` | `float | None` | 否 | 信号强度的 dBm 表示。 |
| `rssi` | `float | None` | 否 | RSSI 数值。 |
| `frequency_mhz` | `float | None` | 否 | 频率，单位 MHz。 |
| `channel` | `int | None` | 否 | 信道号。 |
| `band` | `str | None` | 否 | 频段标识。服务端运行模型允许扩展值。 |
| `security` | `list[str] | None` | 否 | 安全方式列表，例如 `WPA2-PSK`。 |
| `hidden` | `bool | None` | 否 | 是否隐藏网络。 |
| `timestamp` | `int | None` | 否 | 单条 AP 记录时间，Unix epoch 毫秒。 |
| `custom` | `dict[str, Any] | None` | 否 | 自定义扩展字段。 |

兼容别名：

```python
wifi.addwifi(...)
```

推荐使用统一的 snake_case 方法名 `add_wifi()`。

### 基础示例

```python
wifi = WiFi_Package()
wifi.add_wifi(
    ssid="HomeWiFi",
    bssid="AA:BB:CC:DD:EE:FF",
    rssi=-50,
    frequency_mhz=2412,
    channel=1,
    security=["WPA2-PSK"],
    hidden=False,
)
```

### 已连接 Wi-Fi

```python
wifi = WiFi_Package(
    is_connected=True,
    gateway="192.0.2.1",
    dns_servers=["192.0.2.53"],
    ip_address="192.0.2.10",
)
```

当 `is_connected=True` 时，`gateway`、`dns_servers` 和 `ip_address` 必须同时存在，且地址必须是合法 IPv4/IPv6 字符串。

---

## 10. Bluetooth 数据

### 创建和添加数据

```python
bluetooth = Bluetooth_Package(
    technology="ble",
    is_enabled=True,
)

bluetooth.add_bluetooth(
    name="Example-Beacon",
    address="00:11:22:33:44:55",
    address_type="public",
    rssi=-61,
    tx_power=-4,
    manufacturer_id=76,
)
```

实际构造字段：

- `scan_started_at: int | None`
- `scan_finished_at: int | None`
- `technology: str`，默认 `unknown`
- `is_enabled: bool | None`

实际 `add_bluetooth()` 参数：

```python
add_bluetooth(
    *,
    address=None,
    address_type=None,
    name=None,
    is_connected=None,
    is_paired=None,
    rssi=None,
    tx_power=None,
    manufacturer_id=None,
    manufacturer_data=None,
    service_uuids=None,
    service_data=None,
    raw=None,
    rawHex=None,
    rawLength=None,
    timestamp=None,
    custom=None,
)
```

字段说明：

| 参数 | 类型 | 说明 |
|---|---|---|
| `address` | `str | None` | Bluetooth MAC 或匿名地址。 |
| `address_type` | `str | None` | `public`、`random`、`static_random` 或其他服务端允许值。 |
| `name` | `str | None` | 广播名称。 |
| `is_connected` | `bool | None` | 具体远端设备连接状态。 |
| `is_paired` | `bool | None` | 具体远端设备配对状态。 |
| `rssi` | `float | None` | 接收信号强度。 |
| `tx_power` | `float | None` | 发射功率。 |
| `manufacturer_id` | `int | None` | Bluetooth SIG 公司 ID。 |
| `manufacturer_data` | `str | None` | Base64 厂商数据。 |
| `service_uuids` | `list[str] | None` | Service UUID 列表。 |
| `service_data` | `dict[str, str] | None` | UUID 到 Base64 数据的映射。 |
| `raw` | `str | None` | Base64 原始数据。 |
| `rawHex` | `str | None` | 偶数长度 HEX 字符串，不带 `0x`。 |
| `rawLength` | `int | None` | 原始数据长度。 |
| `timestamp` | `int | None` | 单条记录时间。 |
| `custom` | `dict[str, Any] | None` | 自定义字段。 |

兼容别名：`addbluetooth()`。

当前实现会校验 MAC、Base64 和 HEX 的基本格式。

---

## 11. Cell 数据

### 创建和添加数据

```python
cell = Cell_Package(
    observed_at=1760000000000,
    network_type="LTE",
    sim_slot=0,
    registered=True,
)

cell.add_cell(
    radio="LTE",
    mcc="460",
    mnc="01",
    tac=12345,
    cid=268435457,
    pci=101,
    arfcn=1650,
    rssi=-82,
    rsrp=-95,
    rsrq=-12,
)
```

构造字段：

- `observed_at: int | None`
- `network_type: str | None`
- `sim_slot: int | None`
- `is_connected: bool | None`
- `registered: bool | None`
- `serving: dict[str, Any] | None`
- `neighbors: list[dict[str, Any]]`

`add_cell()` 参数：

```python
add_cell(
    *,
    radio=None,
    technology=None,
    mcc=None,
    mnc=None,
    lac=None,
    tac=None,
    cid=None,
    pci=None,
    arfcn=None,
    rssi=None,
    signal_dbm=None,
    rsrp=None,
    rsrq=None,
    asu=None,
    custom=None,
)
```

第一次调用 `add_cell()` 的 observation 会放入 `serving`；之后调用的 observation 会依次放入 `neighbors`。例如：

```python
cell = Cell_Package(network_type="LTE")
cell.add_cell(radio="LTE", mcc="460", mnc="01", tac=1, cid=100)
cell.add_cell(radio="LTE", mcc="460", mnc="01", tac=1, cid=101)

payload = cell.to_dict()
# payload["serving"] 是第一条
# payload["neighbors"] 是第二条及后续记录
```

`mcc` 和 `mnc` 推荐使用字符串，以保留前导零，例如 `"01"`。兼容别名：`addcell()`。

---

## 12. GPS 数据

### 创建定位结果

```python
gps = GPS_Package(
    fix_at=1760000000000,
    provider="gps",
    latitude=25.0330,
    longitude=121.5654,
    altitude_m=20.0,
    accuracy_m=5.8,
    speed_mps=1.2,
    bearing_deg=90.0,
    satellites=18,
    fix_quality="3d",
    mocked=False,
)
```

构造字段：

- `fix_at: int | None`
- `provider: str | None`
- `latitude: float | None`
- `longitude: float | None`
- `altitude_m: float | None`
- `accuracy_m: float | None`
- `speed_mps: float | None`
- `bearing_deg: float | None`
- `satellites: int | None`
- `fix_quality: str | None`
- `mocked: bool | None`
- `points: list[dict[str, Any]]`

### 添加轨迹点

```python
gps = GPS_Package()
gps.add_gps(
    timestamp=1760000000000,
    latitude=25.0330,
    longitude=121.5654,
    altitude_m=20.0,
    accuracy_m=5.8,
)
```

`add_gps()` 的 `latitude` 和 `longitude` 是必填参数：

```python
add_gps(
    *,
    timestamp: int | None = None,
    latitude: float,
    longitude: float,
    altitude_m: float | None = None,
    accuracy_m: float | None = None,
    custom: dict[str, Any] | None = None,
)
```

当前实现会校验纬度 `-90..90` 和经度 `-180..180`。兼容别名：`addgps()`。

---

## 13. GNSS、Sensor、Environment 和 Other

### GNSS

```python
gnss = GNSS_Package(
    fix_at=1760000000000,
    constellation="gps",
)
gnss.add_gnss(
    svid=12,
    satellite_type="gps",
    azimuth_deg=123.4,
    elevation_deg=45.6,
    frequency_mhz=1575.42,
    snr_db=35.5,
    almanac=True,
    ephemeris=True,
    used=True,
)
```

`add_gnss()` 参数：

```python
add_gnss(
    *,
    svid: int,
    satellite_type: str = "unknown",
    azimuth_deg=None,
    elevation_deg=None,
    frequency_mhz=None,
    snr_db=None,
    almanac=None,
    ephemeris=None,
    used=None,
    custom=None,
)
```

兼容别名：`addgnss()`。

### Sensor

```python
sensor = Sensor_Package(
    sensor_type="accelerometer",
    unit="m/s2",
    sampling_hz=50.0,
)
sensor.add_sensor(
    timestamp=1760000000000,
    x=0.01,
    y=9.80,
    z=0.12,
)
```

构造字段：`sensor_type`、`sensor`、`unit`、`sampling_hz`、`timestamp`、`value`、`values`、`samples`、`readings`。

`add_sensor()` 参数：

```python
add_sensor(
    *,
    timestamp: int,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    value: float | None = None,
    custom: dict[str, Any] | None = None,
)
```

`timestamp` 必填。兼容别名：`addsensor()`。

### Environment

```python
environment = Environment_Package(timestamp=1760000000000)
environment.add_reading(
    "temperature",
    value=25.4,
    unit="degC",
)
environment.add_reading(
    "humidity",
    value=62.1,
    unit="percent",
)
```

`unit` 当前服务端文档规定的常用值包括：`degC`、`percent`、`hPa`、`ppm`、`ug/m3`、`lux`、`dBA`。

### Other

```python
other = Other_Package()
other.add_field("vendor_payload", {"ok": True})
```

`Other_Package` 用于无法归入其他 7 种类型的 JSON 对象字段。

---

## 14. 自定义字段 custom

标准字段必须通过显式参数传入；自定义字段通过 `custom` 传入：

```python
wifi = WiFi_Package()
wifi.add_wifi(
    ssid="Example-WiFi",
    bssid="00:11:22:33:44:55",
    custom={
        "vendor": "Example",
        "scanner": "custom-scanner",
        "extra_value": 123,
        "nested": {"enabled": True},
    },
)
```

SDK 会把标准字段和 `custom` 合并，未知扩展字段会随数据发送给服务器。

### custom 不得覆盖标准字段

下面的写法会抛出 `RemoteEnvValidationError`：

```python
wifi.add_wifi(
    ssid="safe",
    custom={"ssid": "unexpected"},
)
```

当前策略不是静默覆盖，而是拒绝冲突，错误信息类似：

```text
custom field 'ssid' conflicts with standard field 'ssid'
```

### None 的处理

`None` 字段默认不进入 Package 的序列化结果：

```python
wifi = WiFi_Package()
wifi.add_wifi(ssid="Example", bssid=None, rssi=None)

assert wifi.to_dict()["networks"] == [{"ssid": "Example"}]
```

空集合是否保留取决于 Package 的标准结构。例如 Wi-Fi 的 `networks`、Bluetooth 的 `devices` 和 Cell 的 `neighbors` 默认保留为空列表。

---

## 15. 多条数据

一个 Package 可以包含多条同类型 observation：

```python
wifi = WiFi_Package()

wifi.addwifi(
    ssid="AP-1",
    bssid="00:11:22:33:44:55",
)
wifi.addwifi(
    ssid="AP-2",
    bssid="AA:BB:CC:DD:EE:FF",
)
wifi.addwifi(
    ssid="AP-3",
    bssid="11:22:33:44:55:66",
)

print(len(wifi))
print(wifi.items)
```

`len(wifi)` 返回 3。上传时这些 Wi-Fi 记录作为一个 `wifi` Package 的 `networks` 数组发送，而不是要求用户手工构造列表。

完整示例：

```python
sdk.upload(wifi_package=wifi)
```

---

## 16. 数据上传

### upload 签名

```python
sdk.upload(
    *,
    wifi_package=None,
    bluetooth_package=None,
    cell_package=None,
    gps_package=None,
    gnss_package=None,
    sensor_package=None,
    environment_package=None,
    other_package=None,
    timeout=10.0,
)
```

返回值：

```python
list[dict[str, Any]]
```

列表中的每一项是对应 Package 的服务器 `data_result`，例如：

```python
[
    {
        "type": "data_result",
        "success": True,
        "device_id": "example-collector",
        "data_type": "wifi",
        "sequence": 1760000000000,
    }
]
```

### 多种 Package 一次上传

```python
wifi = WiFi_Package().add_wifi(
    ssid="Example-WiFi",
    bssid="00:11:22:33:44:55",
)
bluetooth = Bluetooth_Package(technology="ble").add_bluetooth(
    name="Example-Beacon",
    address="AA:BB:CC:DD:EE:FF",
)
cell = Cell_Package(network_type="LTE").add_cell(
    radio="LTE",
    mcc="460",
    mnc="01",
    cid=1001,
)
gps = GPS_Package().add_gps(
    latitude=25.0330,
    longitude=121.5654,
)

results = sdk.upload(
    wifi_package=wifi,
    bluetooth_package=bluetooth,
    cell_package=cell,
    gps_package=gps,
)
```

SDK 会把这次调用拆成 4 个 `environment_data` 消息，并等待 4 个对应的 `data_result`。用户不需要关心消息拆分。

### 上传前提

- 必须先成功调用 `set_collector_token()`；
- 必须先成功调用 `connect_collector()`；
- 至少传入一个 Package；
- 每个上传参数必须是 `Package` 实例；
- 同一设备、同一数据类型的 sequence 必须持续递增。

---

## 17. 获取设备列表

```python
devices = sdk.get_device_list()
```

当前返回值真实类型是：

```python
list[dict[str, Any]]
```

不是专门的 `Device` 对象。典型设备字典可能包含：

```python
{
    "device_id": "example-collector",
    "name": "Example Collector",
    "device_type": "generic",
    "online": True,
    "role": "collector",
}
```

读取方式：

```python
for device in devices:
    print(device.get("device_id"))
    print(device.get("name"))
    print(device.get("online"))
```

Consumer 只能看到服务端授权范围内的 Collector。设备列表不是授权依据的替代品；服务端仍会在订阅和广播时重新检查权限。

---

## 18. 数据订阅

### subscribe

```python
sdk.subscribe(
    device_id="example-collector",
    data_type="wifi",
)
```

真实签名：

```python
subscribe(
    self,
    device_id: str,
    data_type: str | list[str] | None = None,
) -> dict[str, Any]
```

单类型订阅：

```python
sdk.subscribe("example-collector", "wifi")
```

多类型订阅：

```python
sdk.subscribe(
    "example-collector",
    ["wifi", "bluetooth", "gps"],
)
```

SDK 会把别名归一化为 canonical 类型，例如 `ble` 会转换为 `bluetooth`。

服务端成功响应会被原样作为字典返回：

```python
{
    "type": "subscription_result",
    "success": True,
    "device_id": "example-collector",
    "data_types": ["wifi"],
}
```

### unsubscribe

```python
sdk.unsubscribe(
    device_id="example-collector",
    data_type="wifi",
)
```

签名与 `subscribe()` 相同。当前 SDK 将等待服务端的 `subscription_result`，并返回该字典。

### 订阅限制

RemoteEnvServer 当前限制单次订阅的数据类型最多 32 个、单会话不同设备最多 500 个。无权限订阅会映射为 `RemoteEnvSubscriptionError`。

---

## 19. 获取数据

```python
data = sdk.get_data(
    device_id="example-collector",
    data_type="wifi",
    timeout=10,
)
```

返回值是对应的 Package，而不是原始 Envelope 字典：

```python
print(type(data).__name__)
print(data.items)
```

对于 `wifi`，返回 `WiFi_Package`；对于 `bluetooth`，返回 `Bluetooth_Package`，以此类推。

当前 Package 的嵌套 observation 仍以字典形式暴露：

```python
for network in data.items:
    print(network.get("ssid"))
    print(network.get("bssid"))
```

`get_data()` 必须先建立 Client 连接。通常还应先订阅目标设备和数据类型。

---

## 20. timeout

`get_data()` 当前签名：

```python
get_data(
    self,
    device_id: str,
    data_type: str,
    timeout: float | None = 10,
    fresh: bool = False,
) -> Package
```

### `timeout=0`

只检查本地缓存，不等待网络：

```python
try:
    data = sdk.get_data(
        "example-collector",
        "wifi",
        timeout=0,
    )
except RemoteEnvTimeoutError:
    print("当前没有缓存数据")
```

### `timeout=10`

最多等待 10 秒：

```python
try:
    data = sdk.get_data(
        "example-collector",
        "wifi",
        timeout=10,
    )
except RemoteEnvTimeoutError:
    print("10 秒内没有收到数据")
```

### `timeout=None`

无限等待：

```python
data = sdk.get_data(
    "example-collector",
    "wifi",
    timeout=None,
)
```

无限等待适合常驻进程，但退出程序时必须确保调用对应的断开方法或由外层线程控制生命周期。

---

## 21. 数据缓存

收到 Consumer `environment_data` 后，SDK 会：

1. 按 `(device_id, data_type)` 更新本地缓存；
2. 记录缓存中的 sequence；
3. 转换为对应 Package；
4. 调用 callback；
5. 唤醒等待中的 `get_data()`。

### `fresh=False`

默认优先使用现有缓存：

```python
data = sdk.get_data(
    "example-collector",
    "wifi",
    timeout=10,
    fresh=False,
)
```

### `fresh=True`

要求等待 sequence 更高的新消息：

```python
data = sdk.get_data(
    "example-collector",
    "wifi",
    timeout=10,
    fresh=True,
)
```

服务端 `subscribe` 的首次缓存回放带有 `cached=true`。该消息可以立即填充 SDK 本地缓存，但它不代表 Collector 刚刚重新采样。

---

## 22. callback

注册回调：

```python
def on_data(package):
    print("received:", type(package).__name__)
    print(package.to_dict())

sdk.on_data(on_data)
```

真实签名：

```python
on_data(
    self,
    callback: Callable[[Package], None],
) -> RemoteEnvSDK
```

### 触发时机

当接收线程收到 `environment_data` 后触发。回调参数是反序列化后的 Package：

- `wifi` → `WiFi_Package`
- `bluetooth` → `Bluetooth_Package`
- 其他类型同理。

### 多个 callback

当前实现允许注册多个 callback：

```python
sdk.on_data(callback_a)
sdk.on_data(callback_b)
```

### callback 异常

当前实现会捕获单个 callback 的异常，使异常不会直接终止接收循环。但建议回调内部仍自行处理业务异常，不要执行长时间阻塞操作。

### 回调线程

callback 由 WebSocket 接收线程调用，不是主线程。不要在 callback 中直接操作只允许主线程访问的 GUI 控件。需要更新 GUI 时，应把事件投递到 GUI 主线程队列。

---

## 23. 连接状态、心跳和生命周期

### 当前没有独立状态查询 API

当前公开 `RemoteEnvSDK` 没有以下方法：

```python
sdk.is_connected()
sdk.is_connection_alive()
sdk.close()
```

因此文档不提供这些不存在的调用。业务代码应通过：

- `connect_collector()` / `connect_client()` 是否成功；
- `upload()`、`subscribe()`、`get_data()` 是否抛出连接异常；
- 角色对应的断开方法；
- callback 或业务日志；

来判断当前使用状态。

底层 `WebSocketTransport` 有内部 `connected` 属性，但它不是当前 SDK 的公开门面 API，不建议第三方程序依赖内部 `_collector`、`_consumer` 或 `_ws` 属性。

### 心跳

连接成功后，SDK 会在后台线程按 `heartbeat_interval` 发送：

```json
{"type":"heartbeat","timestamp":<positive epoch milliseconds>}
```

服务器返回 `pong`。默认间隔为 15 秒，可在构造时调整：

```python
sdk = RemoteEnvSDK(
    server_url,
    heartbeat_interval=20.0,
)
```

心跳用于保持应用层活动状态；仅仅看到底层 socket 对象存在，不等于服务端业务仍然可用。

### 角色断开

```python
sdk.disconnect_collector()
sdk.disconnect_client()
```

请使用 `try/finally` 确保长期程序退出时释放连接。

---

## 24. 自动重连

当前实现对非主动 WebSocket 断开提供后台重连逻辑：

```text
断线
  ↓
指数退避
  ↓
重新建立 WebSocket
  ↓
重新发送 auth
  ↓
恢复 Consumer 已记录的订阅
  ↓
继续接收数据
```

重连延迟从约 0.5 秒开始，失败后逐步增加，最大约 30 秒。

### 注意事项

- 重连不会替服务器保存尚未确认的上传队列；
- `upload()` 只有收到 `data_result` 才代表服务器已接受；
- Token 被禁用、撤销或绑定错误时，不能靠重连解决；
- Consumer 订阅恢复依赖当前 SDK 进程中保存的订阅记录；
- 当前版本没有公开的重连回调或状态枚举；
- 生产程序应在业务层记录连接异常，并对不可恢复认证错误报警。

RemoteEnvServer 要求重连后重新认证，这与 SDK 的实现一致。

---

## 25. 异常处理

### 异常层次

当前 SDK 导出的异常类型：

```python
from remote_env_sdk.exceptions import (
    RemoteEnvError,
    RemoteEnvConnectionError,
    RemoteEnvAuthenticationError,
    RemoteEnvTimeoutError,
    RemoteEnvProtocolError,
    RemoteEnvUploadError,
    RemoteEnvSubscriptionError,
    RemoteEnvServerError,
    RemoteEnvValidationError,
)
```

| 异常 | 常见原因 |
|---|---|
| `RemoteEnvError` | 所有 SDK 异常的基类。 |
| `RemoteEnvConnectionError` | 建连失败、发送时未连接、认证等待失败。 |
| `RemoteEnvAuthenticationError` | Token 无效、角色不匹配、设备身份不匹配。 |
| `RemoteEnvTimeoutError` | `get_data()`、ACK 或订阅等待超时。 |
| `RemoteEnvProtocolError` | 服务端拒绝消息格式或协议类型。 |
| `RemoteEnvUploadError` | 上传失败、sequence 被拒绝、上传频率受限。 |
| `RemoteEnvSubscriptionError` | 订阅无权限或超过订阅限制。 |
| `RemoteEnvServerError` | 未细分的服务端错误。 |
| `RemoteEnvValidationError` | Package 字段、类型、MAC、IP、Base64、HEX 或 custom 冲突错误。 |

### 推荐处理方式

```python
from remote_env_sdk.exceptions import (
    RemoteEnvAuthenticationError,
    RemoteEnvConnectionError,
    RemoteEnvTimeoutError,
    RemoteEnvValidationError,
)

try:
    sdk.connect_client()
except RemoteEnvAuthenticationError:
    print("Token 无效、被禁用，或 Token 类型不匹配")
except RemoteEnvConnectionError:
    print("服务器地址不可达或 WebSocket 连接失败")
```

上传和读取：

```python
try:
    result = sdk.upload(wifi_package=wifi)
except RemoteEnvValidationError as error:
    print("本地数据格式错误:", error)
except RemoteEnvUploadError as error:
    print("服务器拒绝上传:", error)
except RemoteEnvConnectionError as error:
    print("连接不可用:", error)
```

不要对 `RemoteEnvAuthenticationError` 和 `RemoteEnvValidationError` 做无条件无限重试。应先修正 Token、设备 ID 或输入数据。

---

## 26. 关闭连接

当前 SDK 没有统一 `close()`。使用角色对应的方法：

```python
sdk.disconnect_collector()
sdk.disconnect_client()
```

推荐模式：

```python
sdk.connect_collector()
try:
    # 采集和上传
    pass
finally:
    sdk.disconnect_collector()
```

Client 同理：

```python
sdk.connect_client()
try:
    # 订阅和读取
    pass
finally:
    sdk.disconnect_client()
```

---

## 27. 完整 Collector 示例

文件：`examples/collector_basic.py`。

```python
import os

from remote_env_sdk import RemoteEnvSDK, WiFi_Package

SERVER_URL = os.environ.get(
    "REMOTE_ENV_SERVER_URL",
    "ws://127.0.0.1:8000/ws",
)
COLLECTOR_TOKEN = os.environ["REMOTE_ENV_COLLECTOR_TOKEN"]
DEVICE_ID = os.environ.get(
    "REMOTE_ENV_DEVICE_ID",
    "sdk-example-collector",
)

sdk = RemoteEnvSDK(SERVER_URL)
sdk.set_collector_token(COLLECTOR_TOKEN, DEVICE_ID)
sdk.connect_collector()

try:
    wifi = WiFi_Package()
    wifi.addwifi(
        ssid="SDK-Example-WiFi",
        bssid="00:11:22:33:44:55",
        custom={"source": "collector_basic"},
    )

    result = sdk.upload(wifi_package=wifi)
    print(result)
finally:
    sdk.disconnect_collector()
```

运行前设置环境变量：

```powershell
$env:REMOTE_ENV_SERVER_URL = "wss://example.invalid/envser/ws"
$env:REMOTE_ENV_COLLECTOR_TOKEN = "YOUR_COLLECTOR_TOKEN"
$env:REMOTE_ENV_DEVICE_ID = "sdk-example-collector"
$env:PYTHONPATH = "src"
python examples/collector_basic.py
```

上面的 `YOUR_COLLECTOR_TOKEN` 只是占位符，不能直接用于认证。

---

## 28. 完整 Client 示例

文件：`examples/client_basic.py`。

```python
import os

from remote_env_sdk import RemoteEnvSDK
from remote_env_sdk.exceptions import RemoteEnvTimeoutError

SERVER_URL = os.environ.get(
    "REMOTE_ENV_SERVER_URL",
    "ws://127.0.0.1:8000/ws",
)
CLIENT_TOKEN = os.environ["REMOTE_ENV_CLIENT_TOKEN"]
DEVICE_ID = os.environ.get(
    "REMOTE_ENV_DEVICE_ID",
    "sdk-example-collector",
)

client = RemoteEnvSDK(SERVER_URL)
client.set_client_token(CLIENT_TOKEN)
client.connect_client()

try:
    devices = client.get_device_list()
    print("devices:", devices)

    client.subscribe(DEVICE_ID, "wifi")

    try:
        data = client.get_data(
            DEVICE_ID,
            "wifi",
            timeout=10,
        )
    except RemoteEnvTimeoutError:
        print("10 秒内没有收到 Wi-Fi 数据")
    else:
        print("wifi:", data.items)
finally:
    client.disconnect_client()
```

运行前需要：

1. Client Token 已由服务端管理员创建；
2. Client Token 已获得目标 Collector 的访问权限；
3. `REMOTE_ENV_DEVICE_ID` 与实际 Collector 的 `device_id` 一致；
4. Collector 已经上传过数据，或者 Client 会等待后续数据。

---

## 29. Collector 与 Client 联调

### Collector 程序

```python
# collector.py
import os

from remote_env_sdk import RemoteEnvSDK, WiFi_Package

sdk = RemoteEnvSDK(os.environ["REMOTE_ENV_SERVER_URL"])
sdk.set_collector_token(
    os.environ["REMOTE_ENV_COLLECTOR_TOKEN"],
    os.environ.get("REMOTE_ENV_DEVICE_ID", "sdk-example-collector"),
)
sdk.connect_collector()

try:
    wifi = WiFi_Package()
    wifi.add_wifi(
        ssid="SDK-Test-1",
        bssid="00:11:22:33:44:55",
        custom={"sdk_test": True},
    )
    wifi.add_wifi(
        ssid="SDK-Test-2",
        bssid="AA:BB:CC:DD:EE:FF",
    )
    print(sdk.upload(wifi_package=wifi))
finally:
    sdk.disconnect_collector()
```

### Client 程序

```python
# client.py
import os

from remote_env_sdk import RemoteEnvSDK

server_url = os.environ["REMOTE_ENV_SERVER_URL"]
device_id = os.environ.get("REMOTE_ENV_DEVICE_ID", "sdk-example-collector")

client = RemoteEnvSDK(server_url)
client.set_client_token(os.environ["REMOTE_ENV_CLIENT_TOKEN"])
client.connect_client()

try:
    print(client.get_device_list())
    client.subscribe(device_id, "wifi")
    package = client.get_data(device_id, "wifi", timeout=10)
    for item in package.items:
        print(item.get("ssid"), item.get("bssid"))
finally:
    client.disconnect_client()
```

### 联调顺序

```text
服务端创建 Collector device Token
        ↓
Collector 连接并上传
        ↓
服务端创建 Client consumer Token
        ↓
管理员授权 Client 访问 Collector
        ↓
Client 连接
        ↓
Client 获取 device_list
        ↓
Client subscribe
        ↓
Client get_data
```

---

## 30. API 参考

### `RemoteEnvSDK`

#### `__init__`

```python
RemoteEnvSDK(
    server_url: str,
    *,
    sequence_path: str | None = None,
    transport_factory=None,
    connect_timeout: float = 10.0,
    heartbeat_interval: float = 15.0,
    ssl_verify: bool = True,
)
```

#### `ssl_verify`

```python
ssl_verify(enabled: bool) -> RemoteEnvSDK
```

设置后续新建 WebSocket 连接是否验证 TLS 证书和主机名。默认启用；`False` 仅建议用于受控测试环境。

#### `set_collector_token`

```python
set_collector_token(token: str, device_id: str) -> RemoteEnvSDK
```

设置 Collector Token 和绑定设备 ID。可能抛出 `RemoteEnvValidationError`。

#### `connect_collector`

```python
connect_collector() -> None
```

建立 Collector WebSocket 并完成认证。可能抛出 `RemoteEnvAuthenticationError` 或 `RemoteEnvConnectionError`。

#### `disconnect_collector`

```python
disconnect_collector() -> None
```

关闭 Collector 连接。

#### `upload`

```python
upload(
    *,
    wifi_package: Package | None = None,
    bluetooth_package: Package | None = None,
    cell_package: Package | None = None,
    gps_package: Package | None = None,
    gnss_package: Package | None = None,
    sensor_package: Package | None = None,
    environment_package: Package | None = None,
    other_package: Package | None = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]]
```

至少传入一个 Package。每种 Package 发送一个服务端 `environment_data`。可能抛出 `RemoteEnvConnectionError`、`RemoteEnvUploadError`、`RemoteEnvTimeoutError`、`RemoteEnvValidationError`。

#### `set_client_token`

```python
set_client_token(token: str) -> RemoteEnvSDK
```

设置 Client Token。

#### `connect_client`

```python
connect_client() -> None
```

建立 Consumer WebSocket 并完成认证。

#### `disconnect_client`

```python
disconnect_client() -> None
```

关闭 Client 连接。

#### `get_device_list`

```python
get_device_list() -> list[dict[str, Any]]
```

返回当前本地保存的设备列表。当前不是网络请求式的额外查询，而是统一 Receiver 收到 `device_list` 后更新的列表。

#### `subscribe`

```python
subscribe(
    device_id: str,
    data_type: str | list[str] | None = None,
) -> dict[str, Any]
```

订阅一个设备的一种或多种数据类型。

#### `unsubscribe`

```python
unsubscribe(
    device_id: str,
    data_type: str | list[str] | None = None,
) -> dict[str, Any]
```

取消订阅。

#### `get_data`

```python
get_data(
    device_id: str,
    data_type: str,
    timeout: float | None = 10,
    fresh: bool = False,
) -> Package
```

返回对应 Package。无缓存且超时会抛出 `RemoteEnvTimeoutError`。

#### `on_data`

```python
on_data(callback: Callable[[Package], None]) -> RemoteEnvSDK
```

注册数据回调。回调在接收线程执行，异常会被隔离。

### Package API

#### `WiFi_Package`

```python
WiFi_Package(
    scan_started_at=None,
    scan_finished_at=None,
    interface=None,
    is_connected=False,
    gateway=None,
    dns_servers=[],
    ip_address=None,
    networks=[],
)
```

方法：`add_wifi()`、`addwifi()`、`to_dict()`、`serialize()`、`items`、`len()`。

#### `Bluetooth_Package`

```python
Bluetooth_Package(
    scan_started_at=None,
    scan_finished_at=None,
    technology="unknown",
    is_enabled=None,
    devices=[],
)
```

方法：`add_bluetooth()`、`addbluetooth()`、`to_dict()`、`serialize()`、`items`、`len()`。

#### `Cell_Package`

```python
Cell_Package(
    observed_at=None,
    network_type=None,
    sim_slot=None,
    is_connected=None,
    registered=None,
    serving=None,
    neighbors=[],
)
```

方法：`add_cell()`、`addcell()`、`to_dict()`、`serialize()`。

#### `GPS_Package`

构造函数字段见 [第 12 章](#12-gps-数据)。方法：`add_gps()`、`addgps()`、`to_dict()`、`serialize()`。

#### `GNSS_Package`

构造字段：`fix_at`、`constellation`、`satellites`。方法：`add_gnss()`、`addgnss()`、`to_dict()`、`serialize()`。

#### `Sensor_Package`

构造字段：`sensor_type`、`sensor`、`unit`、`sampling_hz`、`timestamp`、`value`、`values`、`samples`、`readings`。方法：`add_sensor()`、`addsensor()`、`to_dict()`、`serialize()`。

#### `Environment_Package`

构造字段：`timestamp`、`readings`。方法：`add_reading()`、`to_dict()`、`serialize()`。

#### `Other_Package`

方法：`add_field(name, value)`、`to_dict()`、`serialize()`。

---

## 31. 常见问题

### 31.1 `ssid=123` 为什么失败？

标准字段有明确类型。应传字符串：

```python
wifi.add_wifi(ssid="123")
```

当前实现会对常见字段做基本验证，错误通常是 `RemoteEnvValidationError`。

### 31.2 BSSID 必须是什么格式？

当前 SDK 要求冒号分隔的 6 组十六进制 MAC 格式：

```text
AA:BB:CC:DD:EE:FF
```

### 31.3 为什么 `custom` 中不能写 `ssid`？

`ssid` 已经是标准字段。为避免扩展字段静默覆盖标准数据，SDK 会拒绝同名 custom 字段。

### 31.4 为什么 `get_data(timeout=0)` 没有返回数据？

`timeout=0` 只读取本地缓存，不会等待服务器。请先订阅，或者使用大于 0 的 timeout 等待后续消息。

### 31.5 为什么已经订阅却收到的是旧数据？

`subscribe` 会回放服务端最新缓存。缓存回放的语义是“当前可用快照”，不是 Collector 立即重新采样。需要等待后续消息时使用 `fresh=True`。

### 31.6 为什么 Client 看不到设备？

检查：

1. Client Token 是否是 `consumer` 类型；
2. 管理端是否已授权目标 Collector；
3. Collector 是否成功认证；
4. `device_id` 大小写是否一致；
5. 是否读取的是最新的 `device_list`。

### 31.7 为什么上传失败但 sequence 文件已经变化？

当前 SDK 在发送前生成并保存 sequence，服务器未确认时也不会回滚本地 sequence。这是为了避免重启或重连时重复使用旧 sequence。下次上传会继续使用更大的值。

### 31.8 可以使用 `sdk.close()` 吗？

当前版本没有该公开 API。请使用：

```python
sdk.disconnect_collector()
sdk.disconnect_client()
```

### 31.9 可以使用 `sdk.is_connection_alive()` 吗？

当前版本没有该公开 API。不要依赖内部 `_collector`、`_consumer` 或 Transport 对象判断业务状态；应捕获 SDK 异常并使用实际操作验证。

### 31.10 网络断开后是否自动重连？

当前实现会对非主动断开启动指数退避重连，并重新认证。认证错误、Token 撤销和权限错误不能通过重连修复。

### 31.11 为什么真实示例不能直接运行？

网络示例需要真实环境变量：

```text
REMOTE_ENV_SERVER_URL
REMOTE_ENV_COLLECTOR_TOKEN
REMOTE_ENV_CLIENT_TOKEN
REMOTE_ENV_DEVICE_ID
```

文档和源码不包含真实凭据。

---

## 32. 最佳实践

### 1. Token 使用环境变量

不要把真实凭据写入源码：

```python
sdk.set_client_token(os.environ["REMOTE_ENV_CLIENT_TOKEN"])
```

推荐：

```python
import os

sdk.set_client_token(os.environ["REMOTE_ENV_CLIENT_TOKEN"])
```

### 2. 不要重复创建 SDK

推荐一个长期连接：

```python
sdk = RemoteEnvSDK(server_url)
sdk.set_collector_token(token, device_id)
sdk.connect_collector()

try:
    while True:
        # 采集、构造 Package、上传
        pass
finally:
    sdk.disconnect_collector()
```

不要在高频循环中反复建连。

### 3. 先收集，再上传

把采集逻辑和传输逻辑分开：

```python
wifi = WiFi_Package()

# 采集阶段
wifi.add_wifi(ssid="AP-1", bssid="00:11:22:33:44:55")
wifi.add_wifi(ssid="AP-2", bssid="AA:BB:CC:DD:EE:FF")

# 传输阶段
sdk.upload(wifi_package=wifi)
```

### 4. 使用稳定的 Device ID

不要每次启动随机生成 Collector ID。服务端 Token 与 Collector Device ID 绑定，进程重启后必须继续使用同一 ID。

### 5. 不要自行管理 sequence

不要在业务代码中传 `sequence`，当前公开 upload API 也不接受该参数。SDK 会使用持久化 sequence 文件。

### 6. 上传后检查返回结果

只有收到 `data_result` 才代表服务器已经接受并保存数据：

```python
results = sdk.upload(wifi_package=wifi)
for result in results:
    if not result.get("success"):
        raise RuntimeError(result)
```

### 7. 对 timeout 做显式处理

```python
try:
    package = client.get_data(
        device_id,
        "wifi",
        timeout=10,
    )
except RemoteEnvTimeoutError:
    # 记录一次可诊断的超时，不要把它当成空数据吞掉
    pass
```

### 8. callback 中不要执行重任务

callback 运行在接收线程。复杂解析、数据库写入或 GUI 更新应投递到自己的队列或工作线程。

### 9. 不要把缓存当作实时数据

如果业务需要新数据，使用：

```python
client.get_data(
    device_id,
    "wifi",
    timeout=10,
    fresh=True,
)
```

同时注意服务端只保存每个设备和数据类型的一份最新快照，不是历史数据查询接口。

### 10. 文档和日志脱敏

不要记录：

- Token 原文；
- Cookie；
- 私钥或密码；
- 完整的敏感原始采集数据。

日志中使用设备 ID、数据类型和结果状态即可。

---

## 当前版本边界

以下内容在当前 SDK 中尚未作为公开 API 提供：

- 统一 `close()`；
- 公开连接状态枚举或 `is_connection_alive()`；
- 结构化 `Device` 返回对象；
- HTTP 管理端 API；
- 运行时修改重连策略；
- 公开的重连事件回调；
- 对所有嵌套 observation 的独立 Python 类型对象。

这些限制已在本手册中按实际源码明确标注，不能根据 RemoteEnvServer 协议文档自行假设 SDK 已提供对应功能。
