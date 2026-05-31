from unittest.mock import MagicMock, patch
from backend.transports.lan import LANTransport
from backend.models import Snapshot


def _make_b60():
    """Simulate reg60-111 block. Index = reg - 60."""
    b = [0] * 52
    b[0]  = 3800   # reg60: PV1 voltage raw (×0.1 = 380.0 V)
    b[1]  = 32     # reg61: PV1 current raw (×0.1 = 3.2 A)
    b[2]  = 3600   # reg62: PV2 voltage raw (×0.1 = 360.0 V)
    b[3]  = 22     # reg63: PV2 current raw (×0.1 = 2.2 A)
    b[19] = 6000   # reg79: grid Hz raw (×0.01 = 60.0 Hz)
    b[30] = 11421  # reg90: temp raw ((11421-1000)*0.1 = 42.1 °C)
    b[48] = 124    # reg108: today kWh raw (×0.1 = 12.4 kWh)
    b[36] = 32100  # reg96: total kWh low word
    b[37] = 0      # reg97: total kWh high word
    return b


def _make_b150():
    """Simulate reg150-190 block. Index = reg - 150."""
    b = [0] * 41
    b[0]  = 1270   # reg150: grid voltage raw (×0.1 = 127.0 V)
    b[10] = 300    # reg160: grid L1 power (positive = import)
    b[11] = 0      # reg161: grid L2 power
    b[33] = 5120   # reg183: battery voltage raw (×0.01 = 51.20 V)
    b[34] = 78     # reg184: battery SOC %
    b[36] = 1200   # reg186: PV1 power W
    b[37] = 800    # reg187: PV2 power W
    b[40] = 65036  # reg190: battery power raw (signed: 65036-65536 = -500 W = charging)
    return b


def test_lan_builds_snapshot():
    with patch("backend.transports.lan.PySolarmanV5") as MockPV5:
        mock_client = MagicMock()
        MockPV5.return_value = mock_client
        mock_client.read_holding_registers.side_effect = [_make_b150(), _make_b60()]

        transport = LANTransport(ip="192.168.3.144", serial=3427615184)
        snapshot = transport.read()

    assert isinstance(snapshot, Snapshot)
    assert snapshot.source == "lan"
    assert snapshot.solar.pv1_w == 1200
    assert snapshot.solar.pv2_w == 800
    assert snapshot.solar.total_w == 2000
    assert snapshot.battery.soc_pct == 78
    assert snapshot.battery.mode == "charging"
    assert snapshot.grid.voltage_v == pytest.approx(127.0, abs=0.1)
    assert snapshot.energy.today_kwh == pytest.approx(12.4, abs=0.01)


def test_lan_drops_client_on_error():
    with patch("backend.transports.lan.PySolarmanV5") as MockPV5:
        mock_client = MagicMock()
        MockPV5.return_value = mock_client
        mock_client.read_holding_registers.side_effect = ConnectionError("timeout")

        transport = LANTransport(ip="192.168.3.144", serial=3427615184)
        try:
            transport.read()
        except ConnectionError:
            pass

        assert transport._client is None


import pytest
