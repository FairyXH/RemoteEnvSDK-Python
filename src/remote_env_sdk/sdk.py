from __future__ import annotations

import threading
from typing import Any, Callable

from .constants import SequenceStore, now_ms, validate_identifier
from .exceptions import (
    RemoteEnvAuthenticationError, RemoteEnvConnectionError, RemoteEnvProtocolError,
    RemoteEnvServerError, RemoteEnvSubscriptionError, RemoteEnvTimeoutError,
    RemoteEnvUploadError,
)
from .models import PACKAGE_TYPES, Package, canonical_data_type
from .transport import WebSocketTransport


ERROR_MAP = {
    "invalid_token": RemoteEnvAuthenticationError,
    "unauthorized": RemoteEnvAuthenticationError,
    "access_denied": RemoteEnvSubscriptionError,
    "subscription_limit": RemoteEnvSubscriptionError,
    "sequence_rejected": RemoteEnvUploadError,
    "rate_limited": RemoteEnvUploadError,
}


class _Client:
    def __init__(self, sdk: "RemoteEnvSDK", role: str):
        self.sdk, self.role = sdk, role
        self.transport: WebSocketTransport | None = None
        self.ready = threading.Event()
        self.disconnected = threading.Event()
        self.lock = threading.RLock()
        self.device_list: list[dict[str, Any]] = []
        self.pending: dict[str, list[tuple[threading.Event, dict[str, Any] | None]]] = {}
        self.cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.cache_version: dict[tuple[str, str], int] = {}
        self.callbacks: list[Callable[[Any], None]] = []
        self.subscriptions: dict[str, set[str]] = {}
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def connect(self, token: str, device_id: str | None, device: dict[str, Any] | None) -> None:
        self.transport = self.sdk._transport_factory(self.sdk.server_url)
        self.transport.connect(self._on_message, self._on_disconnect)
        auth: dict[str, Any] = {"type": "auth", "role": self.role, "token": token}
        if device_id: auth["device_id"] = device_id
        if device: auth["device"] = device
        self.transport.send(auth)
        if not self.ready.wait(self.sdk.connect_timeout):
            self.transport.close(); raise RemoteEnvConnectionError("authentication timed out")
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def close(self) -> None:
        self._heartbeat_stop.set()
        if self.transport: self.transport.close()
        self.ready.clear()

    def send(self, payload: dict[str, Any]) -> None:
        if not self.transport or not self.transport.connected:
            raise RemoteEnvConnectionError("client is not connected")
        self.transport.send(payload)

    def prepare_waiter(self, key: str) -> threading.Event:
        event = threading.Event()
        with self.lock:
            self.pending.setdefault(key, []).append((event, {}))
        return event

    def wait_for(self, key: str, timeout: float | None, event: threading.Event | None = None) -> dict[str, Any]:
        event = event or self.prepare_waiter(key)
        if not event.wait(timeout):
            with self.lock:
                self.pending[key] = [(e, p) for e, p in self.pending.get(key, []) if e is not event]
            raise RemoteEnvTimeoutError(f"timeout waiting for {key}")
        with self.lock:
            items = self.pending.get(key, [])
            payload = next((p for e, p in items if e is event), None)
            self.pending[key] = [(e, p) for e, p in items if e is not event]
        return payload or {}

    def _resolve(self, key: str, payload: dict[str, Any]) -> None:
        with self.lock:
            for event, holder in self.pending.get(key, []):
                holder.update(payload); event.set(); return

    def _on_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "auth_result": self.ready.set(); return
        if message_type == "device_list":
            with self.lock: self.device_list = list(message.get("devices", []))
            return
        if message_type == "error":
            self.sdk._last_error(message)
            code = str(message.get("code", "server_error"))
            self._resolve("error", message)
            return
        if message_type == "data_result":
            self._resolve(f"ack:{message.get('data_type')}:{message.get('sequence')}", message); return
        if message_type == "subscription_result":
            self._resolve(f"sub:{message.get('device_id')}", message); return
        if message_type == "environment_data": self._handle_data(message); return
        if message_type == "pong": return

    def _handle_data(self, message: dict[str, Any]) -> None:
        device_id, data_type = message.get("device_id"), canonical_data_type(message.get("data_type", ""))
        key = (device_id, data_type)
        with self.lock:
            self.cache[key] = message
            self.cache_version[key] = int(message.get("sequence", 0))
        package_class = PACKAGE_TYPES[data_type]
        package = package_class(**message.get("data", {}))
        for callback in list(self.callbacks):
            try: callback(package)
            except Exception: pass
        self._resolve(f"data:{device_id}:{data_type}", message)

    def _on_disconnect(self, _error: BaseException | None) -> None:
        self.disconnected.set(); self.ready.clear()

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self.sdk.heartbeat_interval):
            try: self.send({"type": "heartbeat", "timestamp": now_ms()})
            except RemoteEnvConnectionError: return


class RemoteEnvSDK:
    def __init__(self, server_url: str, *, sequence_path: str | None = None, transport_factory: Callable[[str], WebSocketTransport] | None = None, connect_timeout: float = 10.0, heartbeat_interval: float = 15.0):
        self.server_url = server_url
        self.connect_timeout = connect_timeout
        self.heartbeat_interval = heartbeat_interval
        self._transport_factory = transport_factory or (lambda url: WebSocketTransport(url))
        self._sequence = SequenceStore(sequence_path)
        self._collector_token: str | None = None; self._collector_device_id: str | None = None
        self._client_token: str | None = None; self._collector: _Client | None = None; self._consumer: _Client | None = None
        self._last_error_message: dict[str, Any] | None = None

    def set_collector_token(self, token: str, device_id: str) -> "RemoteEnvSDK":
        validate_identifier("device_id", device_id); self._collector_token, self._collector_device_id = token, device_id; return self

    def connect_collector(self) -> None:
        if not self._collector_token or not self._collector_device_id: raise RemoteEnvAuthenticationError("collector token and device_id are required")
        self._collector = _Client(self, "collector")
        self._collector.connect(self._collector_token, self._collector_device_id, {"name": self._collector_device_id, "device_type": "python", "capabilities": ["environment_data"]})

    def disconnect_collector(self) -> None:
        if self._collector: self._collector.close()

    def upload(self, *, wifi_package: Package | None = None, bluetooth_package: Package | None = None, cell_package: Package | None = None, gps_package: Package | None = None, gnss_package: Package | None = None, sensor_package: Package | None = None, environment_package: Package | None = None, other_package: Package | None = None, timeout: float = 10.0) -> list[dict[str, Any]]:
        if not self._collector or not self._collector.ready.is_set(): raise RemoteEnvConnectionError("collector is not connected")
        packages = [p for p in (wifi_package, bluetooth_package, cell_package, gps_package, gnss_package, sensor_package, environment_package, other_package) if p is not None]
        if not packages: raise RemoteEnvUploadError("at least one package is required")
        results = []
        for package in packages:
            if not isinstance(package, Package): raise RemoteEnvUploadError("upload arguments must be Package instances")
            data_type = package.data_type; sequence = self._sequence.next(self._collector_device_id, data_type)
            payload = {"type": "environment_data", "version": 1, "device_id": self._collector_device_id, "data_type": data_type, "timestamp": now_ms(), "sequence": sequence, "data": package.to_dict()}
            waiter = self._collector.prepare_waiter(f"ack:{data_type}:{sequence}")
            self._collector.send(payload)
            results.append(self._collector.wait_for(f"ack:{data_type}:{sequence}", timeout, waiter))
        return results

    def set_client_token(self, token: str) -> "RemoteEnvSDK":
        self._client_token = token; return self

    def connect_client(self) -> None:
        if not self._client_token: raise RemoteEnvAuthenticationError("client token is required")
        self._consumer = _Client(self, "consumer")
        self._consumer.connect(self._client_token, None, None)

    def disconnect_client(self) -> None:
        if self._consumer: self._consumer.close()

    def get_device_list(self) -> list[dict[str, Any]]:
        if not self._consumer: raise RemoteEnvConnectionError("consumer is not connected")
        with self._consumer.lock: return list(self._consumer.device_list)

    def subscribe(self, device_id: str, data_type: str | list[str] | None = None) -> dict[str, Any]:
        if not self._consumer: raise RemoteEnvConnectionError("consumer is not connected")
        types = [canonical_data_type(data_type)] if isinstance(data_type, str) else [canonical_data_type(v) for v in (data_type or [])]
        self._consumer.subscriptions.setdefault(device_id, set()).update(types)
        waiter = self._consumer.prepare_waiter(f"sub:{device_id}")
        self._consumer.send({"type": "subscribe", "device_id": device_id, "data_types": types})
        return self._consumer.wait_for(f"sub:{device_id}", self.connect_timeout, waiter)

    def unsubscribe(self, device_id: str, data_type: str | list[str] | None = None) -> dict[str, Any]:
        if not self._consumer: raise RemoteEnvConnectionError("consumer is not connected")
        types = [canonical_data_type(data_type)] if isinstance(data_type, str) else [canonical_data_type(v) for v in (data_type or [])]
        waiter = self._consumer.prepare_waiter(f"sub:{device_id}")
        self._consumer.send({"type": "unsubscribe", "device_id": device_id, "data_types": types})
        return self._consumer.wait_for(f"sub:{device_id}", self.connect_timeout, waiter)

    def get_data(self, device_id: str, data_type: str, timeout: float | None = 10, fresh: bool = False) -> Package:
        if not self._consumer: raise RemoteEnvConnectionError("consumer is not connected")
        data_type = canonical_data_type(data_type); key = (device_id, data_type)
        with self._consumer.lock:
            cached = self._consumer.cache.get(key)
            version = self._consumer.cache_version.get(key, -1)
        if cached and not fresh: return PACKAGE_TYPES[data_type](**cached.get("data", {}))
        if timeout == 0: raise RemoteEnvTimeoutError("no cached data available")
        start = time.monotonic()
        while True:
            remaining = None if timeout is None else max(0, timeout - (time.monotonic() - start))
            message = self._consumer.wait_for(f"data:{device_id}:{data_type}", remaining)
            if not fresh or int(message.get("sequence", -1)) != version: return PACKAGE_TYPES[data_type](**message.get("data", {}))

    def on_data(self, callback: Callable[[Package], None]) -> "RemoteEnvSDK":
        if self._consumer is None: self._consumer = _Client(self, "consumer")
        self._consumer.callbacks.append(callback); return self

    def _last_error(self, message: dict[str, Any]) -> None: self._last_error_message = message
