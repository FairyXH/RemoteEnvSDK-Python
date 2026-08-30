from __future__ import annotations

import json
import ssl
import threading
from typing import Any, Callable

from .exceptions import RemoteEnvConnectionError


class WebSocketTransport:
    def __init__(self, url: str, *, websocket_factory: Callable[..., Any] | None = None, timeout: float = 10.0, ssl_verify: bool = True):
        self.url = url
        self.timeout = timeout
        self.ssl_verify = ssl_verify
        self._factory = websocket_factory
        self._ws: Any = None
        self._receiver: threading.Thread | None = None
        self._stop = threading.Event()
        self._send_lock = threading.Lock()
        self._on_message: Callable[[dict[str, Any]], None] | None = None
        self._on_disconnect: Callable[[BaseException | None], None] | None = None

    def connect(self, on_message: Callable[[dict[str, Any]], None], on_disconnect: Callable[[BaseException | None], None]) -> None:
        try:
            if self._factory is None:
                from websocket import create_connection
                self._factory = create_connection
            options = {"cert_reqs": ssl.CERT_REQUIRED if self.ssl_verify else ssl.CERT_NONE}
            if not self.ssl_verify:
                options["check_hostname"] = False
            self._ws = self._factory(self.url, timeout=self.timeout, sslopt=options)
        except Exception as exc:
            raise RemoteEnvConnectionError(f"websocket connection failed: {exc}") from exc
        self._on_message, self._on_disconnect = on_message, on_disconnect
        self._stop.clear()
        self._receiver = threading.Thread(target=self._receive_loop, name="remote-env-receiver", daemon=True)
        self._receiver.start()

    def send(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            raise RemoteEnvConnectionError("websocket is not connected")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            with self._send_lock:
                self._ws.send(raw)
        except Exception as exc:
            raise RemoteEnvConnectionError(f"websocket send failed: {exc}") from exc

    def close(self) -> None:
        self._stop.set()
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._stop.is_set()

    def _receive_loop(self) -> None:
        error: BaseException | None = None
        try:
            while not self._stop.is_set():
                raw = self._ws.recv()
                if raw is None:
                    break
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                message = json.loads(raw)
                if not isinstance(message, dict):
                    continue
                if self._on_message:
                    self._on_message(message)
        except Exception as exc:
            if not self._stop.is_set():
                error = exc
        finally:
            self._ws = None
            if self._on_disconnect:
                self._on_disconnect(error)
