import asyncio
import pytest
import time
from backend.database import Database
from backend.models import Snapshot, SolarData, BatteryData, GridData, LoadData, InverterData, EnergyData


def make_snapshot(ts: int = None, solar_w: int = 1500) -> Snapshot:
    return Snapshot(
        timestamp=ts or int(time.time()),
        source="lan",
        solar=SolarData(pv1_w=solar_w, pv2_w=500, total_w=solar_w + 500),
        battery=BatteryData(soc_pct=75, power_kw=-0.5, mode="charging"),
        grid=GridData(power_kw=0.1, voltage_v=127.0, frequency_hz=60.0, status="Normal"),
        load=LoadData(power_w=600),
        inverter=InverterData(temp_c=40.0, status="Gerando"),
        energy=EnergyData(today_kwh=8.0, total_kwh=1000.0),
    )


@pytest.mark.asyncio
async def test_database_insert_and_history():
    db = Database(":memory:")
    await db.connect()

    now = int(time.time())
    for i in range(5):
        snap = make_snapshot(ts=now - (4 - i) * 3600, solar_w=1000 + i * 100)
        await db.insert_reading(snap)

    rows = await db.get_history(days=1, bucket="hour")
    assert len(rows) >= 1
    assert "ts" in rows[0]
    assert "solar_w" in rows[0]

    await db.close()


@pytest.mark.asyncio
async def test_database_empty_history():
    db = Database(":memory:")
    await db.connect()
    rows = await db.get_history(days=7, bucket="day")
    assert rows == []
    await db.close()
