import json
from pathlib import Path

import pytest

from remote_env_sdk import RemoteEnvSDK, WiFi_Package
from remote_env_sdk.exceptions import RemoteEnvTimeoutError


class FakeTransport:
    instances = []

    def __init__(self, url):
        self.url = url
        self.connected = False
        self.sent = []
        self.on_message = None
        self.on_disconnect = None
        FakeTransport.instances.append(self)

    def connect(self, on_message, on_disconnect):
        self.on_message, self.on_disconnect = on_message, on_disconnect
        self.connected = True
        on_message({"type": "auth_result", "success": True, "role": "collector"})
        on_message({"type": "device_list", "devices": []})

    def send(self, raw):
        message = raw if isinstance(raw, dict) else json.loads(raw)
        self.sent.append(message)
        if message["type"] == "environment_data":
            self.on_message({"type": "data_result", "success": True, "device_id": message["device_id"], "data_type": message["data_type"], "sequence": message["sequence"]})
        elif message["type"] == "heartbeat":
            self.on_message({"type": "pong"})

    def close(self):
        self.connected = False


def test_upload_registers_ack_before_send(tmp_path):
    sdk = RemoteEnvSDK("ws://test", sequence_path=tmp_path / "seq.json", transport_factory=FakeTransport)
    sdk.set_collector_token("token", "device-1")
    sdk.connect_collector()
    result = sdk.upload(wifi_package=WiFi_Package().add_wifi(ssid="x"))
    assert result[0]["success"] is True
    sent_data = [item for item in FakeTransport.instances[-1].sent if item["type"] == "environment_data"][0]
    assert sent_data["data"]["networks"][0]["ssid"] == "x"


def test_sequence_is_durable(tmp_path):
    path = tmp_path / "seq.json"
    first = RemoteEnvSDK("ws://test", sequence_path=path, transport_factory=FakeTransport)
    first.set_collector_token("token", "device-1").connect_collector()
    first.upload(wifi_package=WiFi_Package().add_wifi(ssid="one"))
    first_value = [item for item in FakeTransport.instances[-1].sent if item["type"] == "environment_data"][0]["sequence"]
    second = RemoteEnvSDK("ws://test", sequence_path=path, transport_factory=FakeTransport)
    second.set_collector_token("token", "device-1").connect_collector()
    second.upload(wifi_package=WiFi_Package().add_wifi(ssid="two"))
    second_value = [item for item in FakeTransport.instances[-1].sent if item["type"] == "environment_data"][0]["sequence"]
    assert second_value > first_value


def test_timeout_zero_without_cache(tmp_path):
    sdk = RemoteEnvSDK("ws://test", sequence_path=tmp_path / "seq.json", transport_factory=FakeTransport)
    sdk.set_client_token("token").connect_client()
    with pytest.raises(RemoteEnvTimeoutError):
        sdk.get_data("device-1", "wifi", timeout=0)