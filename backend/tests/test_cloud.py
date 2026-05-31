import pytest
from unittest.mock import patch, MagicMock
from backend.transports.cloud import CloudTransport
from backend.models import Snapshot


def _mock_token_resp():
    return {"success": True, "data": {"accessToken": "tok_abc123"}}


def _mock_device_latest_resp():
    return {
        "success": True,
        "data": [
            {
                "deviceSn": "TEST001",
                "dataList": [
                    {"key": "PV1Power",              "value": "1200"},
                    {"key": "PV2Power",              "value": "800"},
                    {"key": "PV1Volt",               "value": "380.0"},
                    {"key": "PV1Curr",               "value": "3.2"},
                    {"key": "PV2Volt",               "value": "360.0"},
                    {"key": "PV2Curr",               "value": "2.2"},
                    {"key": "BatCapcity",            "value": "78"},
                    {"key": "BatPower",              "value": "-0.5"},
                    {"key": "BatVolt",               "value": "51.2"},
                    {"key": "GridOrMeterActivePower","value": "0.3"},
                    {"key": "GridVolt",              "value": "127.0"},
                    {"key": "GridFreq",              "value": "60.0"},
                    {"key": "DC_Temp",               "value": "42.1"},
                    {"key": "Eday",                  "value": "12.4"},
                    {"key": "Etotal",                "value": "3210.0"},
                ],
            }
        ],
    }


def test_cloud_builds_snapshot():
    transport = CloudTransport(
        app_id="app1", app_secret="sec1",
        email="test@test.com", password="pass",
        device_sn="TEST001",
    )
    with patch("backend.transports.cloud._post") as mock_post:
        mock_post.side_effect = [_mock_token_resp(), _mock_device_latest_resp()]
        snapshot = transport.read()

    assert isinstance(snapshot, Snapshot)
    assert snapshot.source == "cloud"
    assert snapshot.solar.pv1_w == 1200
    assert snapshot.solar.pv2_w == 800
    assert snapshot.battery.soc_pct == 78
    assert snapshot.battery.mode == "charging"
    assert snapshot.energy.today_kwh == pytest.approx(12.4, abs=0.01)


def test_cloud_token_cached():
    transport = CloudTransport(
        app_id="app1", app_secret="sec1",
        email="test@test.com", password="pass",
        device_sn="TEST001",
    )
    with patch("backend.transports.cloud._post") as mock_post:
        mock_post.side_effect = [
            _mock_token_resp(), _mock_device_latest_resp(),
            _mock_device_latest_resp(),  # second read, no new token call
        ]
        transport.read()
        transport.read()
    # Token fetched only once (first call)
    assert mock_post.call_count == 3
