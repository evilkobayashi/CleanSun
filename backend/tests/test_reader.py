import time
import pytest
from unittest.mock import MagicMock
from backend.reader import Reader
from backend.models import Snapshot, SolarData, BatteryData, GridData, LoadData, InverterData, EnergyData


def make_snapshot(source="lan") -> Snapshot:
    return Snapshot(
        timestamp=int(time.time()), source=source,
        solar=SolarData(total_w=1000),
        battery=BatteryData(soc_pct=50),
        grid=GridData(status="Normal"),
        load=LoadData(power_w=500),
        inverter=InverterData(temp_c=40.0),
        energy=EnergyData(today_kwh=5.0, total_kwh=1000.0),
    )


def test_reader_uses_lan_primary():
    lan = MagicMock()
    lan.read.return_value = make_snapshot("lan")
    reader = Reader(lan=lan)
    snap = reader.read()
    assert snap.source == "lan"
    assert reader.fail_count == 0


def test_reader_counts_lan_failures():
    lan = MagicMock()
    lan.read.side_effect = ConnectionError("timeout")
    reader = Reader(lan=lan, fail_threshold=3)
    with pytest.raises(ConnectionError):
        reader.read()
    assert reader.fail_count == 1


def test_reader_switches_to_cloud_after_threshold():
    lan = MagicMock()
    lan.read.side_effect = ConnectionError("timeout")
    cloud = MagicMock()
    cloud.read.return_value = make_snapshot("cloud")
    reader = Reader(lan=lan, cloud=cloud, fail_threshold=3)

    for _ in range(2):
        with pytest.raises(ConnectionError):
            reader.read()

    snap = reader.read()
    assert snap.source == "cloud"
    assert reader.source == "cloud"


def test_reader_recovers_to_lan():
    lan = MagicMock()
    cloud = MagicMock()
    cloud.read.return_value = make_snapshot("cloud")

    lan.read.side_effect = [
        ConnectionError(), ConnectionError(), ConnectionError(),
        make_snapshot("lan"),
    ]
    reader = Reader(lan=lan, cloud=cloud, fail_threshold=3)

    for _ in range(2):
        with pytest.raises(ConnectionError):
            reader.read()
    reader.read()  # switches to cloud

    snap = reader.read()  # LAN recovered
    assert snap.source == "lan"
    assert reader.source == "lan"


def test_reader_returns_stale_when_no_cloud():
    lan = MagicMock()
    lan.read.side_effect = [make_snapshot("lan"), ConnectionError()]
    reader = Reader(lan=lan, cloud=None, fail_threshold=1)
    reader.read()  # success — caches snapshot

    snap = reader.read()  # failure, no cloud, returns stale
    assert snap.stale is True
    assert snap.source == "stale"
