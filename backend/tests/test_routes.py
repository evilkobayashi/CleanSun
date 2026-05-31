# backend/tests/test_routes.py
import time
import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from backend.api.routes import create_router
from backend.models import Snapshot, SolarData, BatteryData, GridData, LoadData, InverterData, EnergyData


def make_snapshot() -> Snapshot:
    return Snapshot(
        timestamp=int(time.time()), source="lan",
        solar=SolarData(total_w=2000),
        battery=BatteryData(soc_pct=80, mode="charging"),
        grid=GridData(status="Normal"),
        load=LoadData(power_w=800),
        inverter=InverterData(temp_c=42.0, status="Gerando"),
        energy=EnergyData(today_kwh=10.0, total_kwh=3000.0),
    )


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(create_router(), prefix="/api")

    mock_poller = MagicMock()
    mock_poller.latest = make_snapshot()
    mock_poller.last_read_ts = time.time()
    mock_reader = MagicMock()
    mock_reader.source = "lan"
    mock_reader.fail_count = 0
    mock_db = AsyncMock()
    mock_db.get_history = AsyncMock(return_value=[])

    app.state.poller = mock_poller
    app.state.reader = mock_reader
    app.state.db = mock_db
    return app


@pytest.mark.asyncio
async def test_get_snapshot(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "lan"
    assert data["solar"]["total_w"] == 2000


@pytest.mark.asyncio
async def test_get_snapshot_no_data(test_app):
    test_app.state.poller.latest = None
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/snapshot")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_history(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/history?days=7&bucket=hour")
    assert resp.status_code == 200
    assert resp.json()["bucket"] == "hour"


@pytest.mark.asyncio
async def test_get_status(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "lan"
    assert data["has_data"] is True
