from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .exceptions import RemoteEnvValidationError


def now_ms() -> int:
    return time.time_ns() // 1_000_000


class SequenceStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".remote_env_sdk_sequences.json"
        self._lock = threading.Lock()
        self._values: dict[str, int] = {}
        self._load()

    def next(self, device_id: str, data_type: str) -> int:
        key = f"{device_id}\u0000{data_type}"
        with self._lock:
            value = max(now_ms(), self._values.get(key, 0) + 1)
            self._values[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._values, separators=(",", ":")), encoding="utf-8")
            tmp.replace(self.path)
            return value

    def _load(self) -> None:
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(values, dict):
                self._values = {str(k): int(v) for k, v in values.items()}
        except (OSError, ValueError, TypeError):
            self._values = {}


def validate_identifier(name: str, value: str, maximum: int = 128) -> None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RemoteEnvValidationError(f"{name} must be a non-empty string of at most {maximum} characters")
