import pytest

from remote_env_sdk import (
    Bluetooth_Package, Cell_Package, GPS_Package, GNSS_Package,
    Sensor_Package, Environment_Package, Other_Package, WiFi_Package,
)
from remote_env_sdk.exceptions import RemoteEnvValidationError


def test_wifi_package_builds_multiple_networks_and_custom_fields():
    package = WiFi_Package()
    package.add_wifi(ssid="AP-1", bssid="00:11:22:33:44:55", rssi=-50, custom={"vendor": "x"})
    package.add_wifi(ssid="AP-2", bssid="AA:BB:CC:DD:EE:FF")
    assert len(package) == 2
    assert package.to_dict()["networks"] == [
        {"ssid": "AP-1", "bssid": "00:11:22:33:44:55", "rssi": -50, "vendor": "x"},
        {"ssid": "AP-2", "bssid": "AA:BB:CC:DD:EE:FF"},
    ]


def test_custom_cannot_override_standard_field():
    with pytest.raises(RemoteEnvValidationError, match="conflicts with standard field 'ssid'"):
        WiFi_Package().add_wifi(ssid="safe", custom={"ssid": "bad"})


def test_wifi_optional_none_fields_are_omitted():
    package = WiFi_Package()
    package.add_wifi(ssid="AP", bssid=None, rssi=None)
    assert package.to_dict()["networks"] == [{"ssid": "AP"}]


def test_wifi_connection_validation_and_alias_method():
    package = WiFi_Package(is_connected=True, gateway="192.0.2.1", dns_servers=["192.0.2.53"], ip_address="192.0.2.10")
    package.addwifi(ssid="AP", bssid="00:11:22:33:44:55")
    assert package.to_dict()["is_connected"] is True
    assert len(package) == 1


def test_other_packages_expose_explicit_standard_parameters():
    Bluetooth_Package(technology="ble").add_bluetooth(name="Beacon", address="00:11:22:33:44:55")
    Cell_Package(network_type="LTE").add_cell(radio="LTE", mcc="460", mnc="01", cid=1)
    GPS_Package(latitude=25.0, longitude=121.0)
    GNSS_Package().add_gnss(svid=12, satellite_type="gps")
    Sensor_Package(sensor_type="temperature").add_sensor(timestamp=1, value=23.5)
    Environment_Package().add_reading("temperature", value=23.5, unit="degC")
    Other_Package().add_field("vendor_payload", {"ok": True})