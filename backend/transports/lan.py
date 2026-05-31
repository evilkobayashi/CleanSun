"""SOLARMAN LAN transport for Deye SUN-7.5K via pysolarmanv5."""
from __future__ import annotations
import time
from pysolarmanv5 import PySolarmanV5
from backend.models import (
    Snapshot, SolarData, BatteryData, GridData,
    LoadData, InverterData, EnergyData,
)


def _s16(val: int) -> int:
    """Unsigned 16-bit Modbus register → signed Python int."""
    return val if val < 0x8000 else val - 0x10000


class LANTransport:
    """Reads Deye registers via SOLARMAN v5 protocol on port 8899.

    Uses two register blocks:
    - FAST (reg150-190): power/battery values, polled every read
    - SLOW (reg60-111): PV V/A, temp, energy, polled every 5 reads
    """

    def __init__(
        self,
        ip: str,
        serial: int,
        port: int = 8899,
        mb_slaveid: int = 1,
        battery_kwh: float = 9.6,
    ) -> None:
        self._ip = ip
        self._serial = serial
        self._port = port
        self._mb_slaveid = mb_slaveid
        self._battery_kwh = battery_kwh
        self._client: PySolarmanV5 | None = None
        self._slow_cache: dict = {}
        self._poll_count: int = 0

    def _get_client(self) -> PySolarmanV5:
        if self._client is None:
            self._client = PySolarmanV5(
                self._ip,
                self._serial,
                port=self._port,
                mb_slaveid=self._mb_slaveid,
                verbose=False,
                auto_reconnect=True,
                socket_timeout=6,
            )
        return self._client

    def _drop_client(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def read(self) -> Snapshot:
        client = self._get_client()
        try:
            b150 = client.read_holding_registers(150, 41)
            if not self._slow_cache or self._poll_count % 5 == 0:
                b60 = client.read_holding_registers(60, 52)
                self._slow_cache = self._parse_slow(b60)
            self._poll_count += 1
        except Exception:
            self._drop_client()
            raise
        return self._build_snapshot({**self._slow_cache, **self._parse_fast(b150)})

    @staticmethod
    def _parse_slow(b: list) -> dict:
        return {
            "pv1_v_raw":     b[0],                          # reg60
            "pv1_a_raw":     b[1],                          # reg61
            "pv2_v_raw":     b[2],                          # reg62
            "pv2_a_raw":     b[3],                          # reg63
            "grid_hz_raw":   b[19],                         # reg79
            "temp_raw":      b[30],                         # reg90
            "today_kwh_raw": b[48],                         # reg108
            "total_kwh_raw": (b[37] << 16) | b[36],        # reg97 high + reg96 low
        }

    @staticmethod
    def _parse_fast(b: list) -> dict:
        return {
            "grid_v_raw":    b[0],   # reg150
            "grid_l1_w_raw": b[10],  # reg160
            "grid_l2_w_raw": b[11],  # reg161
            "batt_v_raw":    b[33],  # reg183
            "batt_soc_raw":  b[34],  # reg184
            "pv1_w_raw":     b[36],  # reg186
            "pv2_w_raw":     b[37],  # reg187
            "batt_w_raw":    b[40],  # reg190
        }

    def _build_snapshot(self, r: dict) -> Snapshot:
        pv1_v  = max(0.0, _s16(r["pv1_v_raw"]) * 0.1)
        pv1_a  = max(0.0, _s16(r["pv1_a_raw"]) * 0.1)
        pv2_v  = max(0.0, _s16(r["pv2_v_raw"]) * 0.1)
        pv2_a  = max(0.0, _s16(r["pv2_a_raw"]) * 0.1)
        pv1_w  = r["pv1_w_raw"]
        pv2_w  = r["pv2_w_raw"]
        batt_v = r["batt_v_raw"] * 0.01
        batt_soc = r["batt_soc_raw"]
        batt_w = _s16(r["batt_w_raw"])
        grid_w = _s16(r["grid_l1_w_raw"]) + _s16(r["grid_l2_w_raw"])
        grid_v = r["grid_v_raw"] * 0.1
        grid_hz = r["grid_hz_raw"] * 0.01
        temp = (r["temp_raw"] - 1000) * 0.1
        today_kwh = r["today_kwh_raw"] * 0.1
        total_kwh = r["total_kwh_raw"] * 0.1

        load_w = max(0, pv1_w + pv2_w + grid_w + batt_w)
        batt_mode = (
            "discharging" if batt_w > 30
            else "charging" if batt_w < -30
            else "idle"
        )
        if grid_v < 1.0:
            grid_status = "Indisponível"
        elif not (115.0 <= grid_v <= 140.0):
            grid_status = "Alarme"
        else:
            grid_status = "Normal"
        inv_status = (
            "Gerando" if (pv1_w + pv2_w) > 50
            else "Fornecendo" if batt_w < -50
            else "Standby"
        )

        return Snapshot(
            timestamp=int(time.time()),
            source="lan",
            solar=SolarData(
                pv1_w=pv1_w, pv2_w=pv2_w, total_w=pv1_w + pv2_w,
                pv1_v=round(pv1_v, 1), pv1_a=round(pv1_a, 2),
                pv2_v=round(pv2_v, 1), pv2_a=round(pv2_a, 2),
            ),
            battery=BatteryData(
                soc_pct=batt_soc,
                power_kw=round(batt_w / 1000.0, 2),
                mode=batt_mode,
                voltage_v=round(batt_v, 1),
                available_kwh=round(batt_soc / 100.0 * self._battery_kwh, 2),
            ),
            grid=GridData(
                power_kw=round(grid_w / 1000.0, 2),
                voltage_v=round(grid_v, 1),
                frequency_hz=round(grid_hz, 2),
                status=grid_status,
            ),
            load=LoadData(power_w=load_w),
            inverter=InverterData(temp_c=round(temp, 1), status=inv_status),
            energy=EnergyData(
                today_kwh=round(today_kwh, 2),
                total_kwh=round(total_kwh, 1),
            ),
        )
