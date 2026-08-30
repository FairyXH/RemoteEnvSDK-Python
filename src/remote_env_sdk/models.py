from __future__ import annotations

import base64
import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .exceptions import RemoteEnvValidationError

CANONICAL_DATA_TYPES = ("wifi", "bluetooth", "cell", "gps", "gnss", "sensor", "environment", "other")
ALIASES = {"ble": "bluetooth", "bluetooth_data": "bluetooth", "cellular": "cell", "gnss.route": "gnss", "gps.route": "gps"}
MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def canonical_data_type(value: str) -> str:
    if not isinstance(value, str):
        raise RemoteEnvValidationError("data_type must be a string")
    value = value.strip().lower()
    value = ALIASES.get(value, value)
    if value.startswith("sensor."):
        value = "sensor"
    if value.startswith("gnss."):
        value = "gnss"
    if value not in CANONICAL_DATA_TYPES:
        raise RemoteEnvValidationError(f"unsupported data_type: {value}")
    return value


def _validate_type(name: str, value: Any, expected: type | tuple[type, ...], *, allow_none: bool = True) -> None:
    if value is None and allow_none:
        return
    if isinstance(expected, tuple):
        valid = isinstance(value, expected) and not (isinstance(value, bool) and bool not in expected)
    elif expected is bool:
        valid = isinstance(value, bool)
    else:
        valid = isinstance(value, expected) and not isinstance(value, bool)
    if not valid:
        raise RemoteEnvValidationError(f"{name} must be {expected}")


def _clean(values: dict[str, Any], standard: set[str], custom: dict[str, Any] | None) -> dict[str, Any]:
    if custom is not None and not isinstance(custom, dict):
        raise RemoteEnvValidationError("custom must be a dict")
    conflicts = standard.intersection(custom or {})
    if conflicts:
        key = sorted(conflicts)[0]
        raise RemoteEnvValidationError(f"custom field '{key}' conflicts with standard field '{key}'")
    result = {key: value for key, value in values.items() if value is not None}
    result.update(custom or {})
    return result


def _validate_mac(name: str, value: str | None) -> None:
    if value is not None and not MAC_RE.fullmatch(value):
        raise RemoteEnvValidationError(f"{name} must be a colon-separated MAC address")


def _validate_timestamp(name: str, value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
        raise RemoteEnvValidationError(f"{name} must be a positive integer")


@dataclass
class Package:
    data_type: ClassVar[str]
    _data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dump(self._data)

    def serialize(self) -> dict[str, Any]:
        return self.to_dict()


@dataclass
class WiFi_Package(Package):
    data_type: ClassVar[str] = "wifi"
    scan_started_at: int | None = None
    scan_finished_at: int | None = None
    interface: str | None = None
    is_connected: bool = False
    gateway: str | None = None
    dns_servers: list[str] = field(default_factory=list)
    ip_address: str | None = None
    networks: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_timestamp("scan_started_at", self.scan_started_at)
        _validate_timestamp("scan_finished_at", self.scan_finished_at)
        _validate_type("is_connected", self.is_connected, bool, allow_none=False)
        for name, value in (("gateway", self.gateway), ("ip_address", self.ip_address)):
            if value is not None:
                try: ipaddress.ip_address(value)
                except ValueError as exc: raise RemoteEnvValidationError(f"{name} must be a valid IP address") from exc
        for value in self.dns_servers:
            try: ipaddress.ip_address(value)
            except ValueError as exc: raise RemoteEnvValidationError("dns_servers must contain valid IP addresses") from exc
        if self.is_connected and (not self.gateway or not self.dns_servers or not self.ip_address):
            raise RemoteEnvValidationError("connected WiFi data requires gateway, dns_servers, and ip_address")
        self._data = _dump({"scan_started_at": self.scan_started_at, "scan_finished_at": self.scan_finished_at, "interface": self.interface, "is_connected": self.is_connected, "gateway": self.gateway, "dns_servers": self.dns_servers, "ip_address": self.ip_address, "networks": self.networks})

    def add_wifi(self, *, ssid: str | None = None, bssid: str | None = None, signal_dbm: float | None = None, rssi: float | None = None, frequency_mhz: float | None = None, channel: int | None = None, band: str | None = None, security: list[str] | None = None, hidden: bool | None = None, timestamp: int | None = None, custom: dict[str, Any] | None = None) -> WiFi_Package:
        if ssid is not None: _validate_type("ssid", ssid, str)
        _validate_type("bssid", bssid, str); _validate_mac("bssid", bssid)
        for name, value in (("signal_dbm", signal_dbm), ("rssi", rssi), ("frequency_mhz", frequency_mhz)):
            _validate_type(name, value, (int, float))
        _validate_type("channel", channel, int); _validate_type("band", band, str); _validate_type("security", security, list); _validate_type("hidden", hidden, bool); _validate_timestamp("timestamp", timestamp)
        item = _clean({"ssid": ssid, "bssid": bssid, "signal_dbm": signal_dbm, "rssi": rssi, "frequency_mhz": frequency_mhz, "channel": channel, "band": band, "security": security, "hidden": hidden, "timestamp": timestamp}, {"ssid", "bssid", "signal_dbm", "rssi", "frequency_mhz", "channel", "band", "security", "hidden", "timestamp"}, custom)
        self.networks.append(item); self._data["networks"] = self.networks; return self

    addwifi = add_wifi

    @property
    def items(self) -> list[dict[str, Any]]: return list(self.networks)
    def __len__(self) -> int: return len(self.networks)


@dataclass
class Bluetooth_Package(Package):
    data_type: ClassVar[str] = "bluetooth"
    scan_started_at: int | None = None
    scan_finished_at: int | None = None
    technology: str = "unknown"
    is_enabled: bool | None = None
    devices: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._data = _dump({"scan_started_at": self.scan_started_at, "scan_finished_at": self.scan_finished_at, "technology": self.technology, "is_enabled": self.is_enabled, "devices": self.devices})

    def add_bluetooth(self, *, address: str | None = None, address_type: str | None = None, name: str | None = None, is_connected: bool | None = None, is_paired: bool | None = None, rssi: float | None = None, tx_power: float | None = None, manufacturer_id: int | None = None, manufacturer_data: str | None = None, service_uuids: list[str] | None = None, service_data: dict[str, str] | None = None, raw: str | None = None, rawHex: str | None = None, rawLength: int | None = None, timestamp: int | None = None, custom: dict[str, Any] | None = None) -> Bluetooth_Package:
        _validate_type("address", address, str); _validate_mac("address", address)
        for name_, value in (("name", name), ("address_type", address_type), ("manufacturer_data", manufacturer_data), ("raw", raw), ("rawHex", rawHex)): _validate_type(name_, value, str)
        for name_, value in (("rssi", rssi), ("tx_power", tx_power)): _validate_type(name_, value, (int, float))
        _validate_type("manufacturer_id", manufacturer_id, int); _validate_type("rawLength", rawLength, int); _validate_timestamp("timestamp", timestamp)
        for name_, value in (("manufacturer_data", manufacturer_data), ("raw", raw)):
            if value is not None:
                try: base64.b64decode(value, validate=True)
                except Exception as exc: raise RemoteEnvValidationError(f"{name_} must be valid Base64") from exc
        if rawHex is not None and (len(rawHex) % 2 or not re.fullmatch(r"[0-9A-Fa-f]*", rawHex)): raise RemoteEnvValidationError("rawHex must be even-length HEX")
        standard = {"address", "address_type", "name", "is_connected", "is_paired", "rssi", "tx_power", "manufacturer_id", "manufacturer_data", "service_uuids", "service_data", "raw", "rawHex", "rawLength", "timestamp"}
        self.devices.append(_clean(locals() | {}, standard, custom))
        for key in ("self", "custom", "standard", "name_", "value"): self.devices[-1].pop(key, None)
        self._data["devices"] = self.devices; return self

    addbluetooth = add_bluetooth
    @property
    def items(self) -> list[dict[str, Any]]: return list(self.devices)
    def __len__(self) -> int: return len(self.devices)


@dataclass
class Cell_Package(Package):
    data_type: ClassVar[str] = "cell"
    observed_at: int | None = None
    network_type: str | None = None
    sim_slot: int | None = None
    is_connected: bool | None = None
    registered: bool | None = None
    serving: dict[str, Any] | None = None
    neighbors: list[dict[str, Any]] = field(default_factory=list)
    def __post_init__(self) -> None: self._data = _dump({"observed_at": self.observed_at, "network_type": self.network_type, "sim_slot": self.sim_slot, "is_connected": self.is_connected, "registered": self.registered, "serving": self.serving, "neighbors": self.neighbors})
    def add_cell(self, *, radio: str | None = None, technology: str | None = None, mcc: str | None = None, mnc: str | None = None, lac: int | None = None, tac: int | None = None, cid: int | None = None, pci: int | None = None, arfcn: int | None = None, rssi: float | None = None, signal_dbm: float | None = None, rsrp: float | None = None, rsrq: float | None = None, asu: float | None = None, custom: dict[str, Any] | None = None) -> Cell_Package:
        item = _clean({k: v for k, v in {"radio": radio, "technology": technology, "mcc": mcc, "mnc": mnc, "lac": lac, "tac": tac, "cid": cid, "pci": pci, "arfcn": arfcn, "rssi": rssi, "signal_dbm": signal_dbm, "rsrp": rsrp, "rsrq": rsrq, "asu": asu}.items()}, {"radio", "technology", "mcc", "mnc", "lac", "tac", "cid", "pci", "arfcn", "rssi", "signal_dbm", "rsrp", "rsrq", "asu"}, custom)
        if self.serving is None: self.serving = item
        else: self.neighbors.append(item)
        self._data = _dump({"observed_at": self.observed_at, "network_type": self.network_type, "sim_slot": self.sim_slot, "is_connected": self.is_connected, "registered": self.registered, "serving": self.serving, "neighbors": self.neighbors}); return self
    addcell = add_cell

@dataclass
class GPS_Package(Package):
    data_type: ClassVar[str] = "gps"
    fix_at: int | None = None; provider: str | None = None; latitude: float | None = None; longitude: float | None = None; altitude_m: float | None = None; accuracy_m: float | None = None; speed_mps: float | None = None; bearing_deg: float | None = None; satellites: int | None = None; fix_quality: str | None = None; mocked: bool | None = None; points: list[dict[str, Any]] = field(default_factory=list)
    def __post_init__(self) -> None:
        if self.latitude is not None and not -90 <= self.latitude <= 90: raise RemoteEnvValidationError("latitude out of range")
        if self.longitude is not None and not -180 <= self.longitude <= 180: raise RemoteEnvValidationError("longitude out of range")
        self._data = _dump({k: v for k, v in self.__dict__.items() if k not in {"_data"}})
    def add_gps(self, *, timestamp: int | None = None, latitude: float, longitude: float, altitude_m: float | None = None, accuracy_m: float | None = None, custom: dict[str, Any] | None = None) -> GPS_Package:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180: raise RemoteEnvValidationError("GPS coordinates out of range")
        self.points.append(_clean({"timestamp": timestamp, "latitude": latitude, "longitude": longitude, "altitude_m": altitude_m, "accuracy_m": accuracy_m}, {"timestamp", "latitude", "longitude", "altitude_m", "accuracy_m"}, custom)); self._data["points"] = self.points; return self
    addgps = add_gps

@dataclass
class GNSS_Package(Package):
    data_type: ClassVar[str] = "gnss"
    fix_at: int | None = None; constellation: str | None = None; satellites: list[dict[str, Any]] = field(default_factory=list)
    def __post_init__(self) -> None: self._data = _dump({"fix_at": self.fix_at, "constellation": self.constellation, "satellites": self.satellites})
    def add_gnss(self, *, svid: int, satellite_type: str = "unknown", azimuth_deg: float | None = None, elevation_deg: float | None = None, frequency_mhz: float | None = None, snr_db: float | None = None, almanac: bool | None = None, ephemeris: bool | None = None, used: bool | None = None, custom: dict[str, Any] | None = None) -> GNSS_Package:
        item = _clean({"type": satellite_type, "svid": svid, "azimuth_deg": azimuth_deg, "elevation_deg": elevation_deg, "frequency_mhz": frequency_mhz, "snr_db": snr_db, "almanac": almanac, "ephemeris": ephemeris, "used": used}, {"type", "svid", "azimuth_deg", "elevation_deg", "frequency_mhz", "snr_db", "almanac", "ephemeris", "used"}, custom); self.satellites.append(item); self._data["satellites"] = self.satellites; return self
    addgnss = add_gnss

@dataclass
class Sensor_Package(Package):
    data_type: ClassVar[str] = "sensor"
    sensor_type: str | None = None; sensor: str | None = None; unit: str | None = None; sampling_hz: float | None = None; timestamp: int | None = None; value: float | None = None; values: list[float] | None = None; samples: list[dict[str, Any]] = field(default_factory=list); readings: list[dict[str, Any]] = field(default_factory=list)
    def __post_init__(self) -> None: self._data = _dump({k: v for k, v in self.__dict__.items() if k != "_data"})
    def add_sensor(self, *, timestamp: int, x: float | None = None, y: float | None = None, z: float | None = None, value: float | None = None, custom: dict[str, Any] | None = None) -> Sensor_Package:
        self.samples.append(_clean({"timestamp": timestamp, "x": x, "y": y, "z": z, "value": value}, {"timestamp", "x", "y", "z", "value"}, custom)); self._data["samples"] = self.samples; return self
    addsensor = add_sensor

@dataclass
class Environment_Package(Package):
    data_type: ClassVar[str] = "environment"
    timestamp: int | None = None
    readings: dict[str, dict[str, Any]] = field(default_factory=dict)
    def __post_init__(self) -> None: self._data = _dump({"timestamp": self.timestamp, "readings": self.readings})
    def add_reading(self, name: str, *, value: float, unit: str, custom: dict[str, Any] | None = None) -> Environment_Package:
        self.readings[name] = _clean({"value": value, "unit": unit}, {"value", "unit"}, custom); self._data["readings"] = self.readings; return self

@dataclass
class Other_Package(Package):
    data_type: ClassVar[str] = "other"
    def add_field(self, name: str, value: Any) -> Other_Package:
        if not isinstance(name, str) or not name: raise RemoteEnvValidationError("field name must be a non-empty string")
        self._data[name] = value; return self


def _dump(value: Any) -> Any:
    if isinstance(value, Package): return value.to_dict()
    if isinstance(value, dict): return {k: _dump(v) for k, v in value.items() if v is not None}
    if isinstance(value, list): return [_dump(v) for v in value]
    return value

PACKAGE_TYPES = {cls.data_type: cls for cls in (WiFi_Package, Bluetooth_Package, Cell_Package, GPS_Package, GNSS_Package, Sensor_Package, Environment_Package, Other_Package)}
