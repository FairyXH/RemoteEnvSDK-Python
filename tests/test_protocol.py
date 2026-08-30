import json
import ssl
from pathlib import Path

import pytest

from remote_env_sdk import RemoteEnvSDK, WiFi_Package
from remote_env_sdk.exceptions import RemoteEnvTimeoutError
from remote_env_sdk.transport import WebSocketTransport


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
        elif message["type"] == "subscribe" or message["type"] == "unsubscribe":
            self.on_message({"type": "subscription_result", "success": True, "device_id": message["device_id"], "data_types": message["data_types"]})

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
def test_consumer_cache_callback_and_fresh(tmp_path):
    sdk = RemoteEnvSDK("ws://test", sequence_path=tmp_path / "seq.json", transport_factory=FakeTransport)
    received = []
    sdk.on_data(received.append)
    sdk.set_client_token("token").connect_client()
    assert sdk.subscribe("device-1", "wifi")["success"] is True
    transport = FakeTransport.instances[-1]
    transport.on_message({"type": "environment_data", "device_id": "device-1", "data_type": "wifi", "sequence": 1, "timestamp": 1, "data": {"networks": [{"ssid": "cached"}]}, "cached": True})
    data = sdk.get_data("device-1", "wifi", timeout=0)
    assert data.items[0]["ssid"] == "cached"
    assert len(received) == 1


def test_ssl_verify_configures_websocket_ssl_options():
    calls = []

    class FakeWebSocket:
        def send(self, _raw):
            pass

        def recv(self):
            return None

        def close(self):
            pass

    def factory(url, **kwargs):
        calls.append((url, kwargs))
        return FakeWebSocket()

    transport = WebSocketTransport(
        "wss://example.invalid/ws",
        websocket_factory=factory,
        ssl_verify=False,
    )
    transport.connect(lambda _message: None, lambda _error: None)
    transport.close()

    assert calls[0][1]["sslopt"]["cert_reqs"] == ssl.CERT_NONE


def test_sdk_ssl_verify_is_chainable_and_validates_bool(tmp_path):
    sdk = RemoteEnvSDK("wss://example.invalid/ws", sequence_path=tmp_path / "seq.json")
    assert sdk.ssl_verify(False) is sdk
    assert sdk.ssl_verify_enabled is False
    with pytest.raises(TypeError, match="enabled must be a bool"):
        sdk.ssl_verify(0)
