from backend.models import Snapshot, SolarData, BatteryData, GridData, LoadData, InverterData, EnergyData


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
