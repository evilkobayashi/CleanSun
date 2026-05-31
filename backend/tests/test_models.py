import json, tempfile, os
from backend.models import Snapshot, SolarData, BatteryData, GridData, LoadData, InverterData, EnergyData
from backend.config import Settings


def test_snapshot_defaults():
    s = Snapshot(
        timestamp=1000,
        source="lan",
        solar=SolarData(),
        battery=BatteryData(),
        grid=GridData(),
        load=LoadData(),
        inverter=InverterData(),
        energy=EnergyData(),
    )
    assert s.source == "lan"
    assert s.stale is False
    assert s.alerts == []


def test_snapshot_json_roundtrip():
    s = Snapshot(
        timestamp=1748650000,
        source="cloud",
        solar=SolarData(pv1_w=1200, pv2_w=800, total_w=2000),
        battery=BatteryData(soc_pct=78, power_kw=-1.2, mode="charging"),
        grid=GridData(power_kw=0.3, voltage_v=127.0, frequency_hz=60.0, status="Normal"),
        load=LoadData(power_w=850),
        inverter=InverterData(temp_c=42.1, status="Gerando"),
        energy=EnergyData(today_kwh=12.4, total_kwh=3210.0),
    )
    data = s.model_dump()
    assert data["solar"]["total_w"] == 2000
    assert data["battery"]["mode"] == "charging"
    assert data["stale"] is False


def test_settings_from_file():
    cfg_data = {
        "lan": {
            "datalogger_ip": "192.168.1.10",
            "datalogger_serial": 12345678,
            "port": 8899,
            "poll_seconds": 5,
            "fail_threshold": 3,
            "battery_kwh": 9.6
        },
        "cloud": {"enabled": False},
        "server": {"host": "0.0.0.0", "port": 8080, "db_path": "test.db"}
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cfg_data, f)
        path = f.name
    try:
        s = Settings.from_file(path)
        assert s.lan.datalogger_ip == "192.168.1.10"
        assert s.lan.datalogger_serial == 12345678
        assert s.cloud.enabled is False
        assert s.server.port == 8080
    finally:
        os.unlink(path)
