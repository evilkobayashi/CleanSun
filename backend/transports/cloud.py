"""Deye Cloud API transport — fallback when LAN unavailable."""
from __future__ import annotations
import hashlib
import json
import time
import urllib.request
from backend.models import (
    Alert, Snapshot, SolarData, BatteryData, GridData,
    LoadData, InverterData, EnergyData,
)

_BASE = "https://us1-developer.deyecloud.com"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _post(url: str, payload: dict, token: str = "") -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


class CloudTransport:
    """Reads inverter data from Deye Cloud API v1.0."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        email: str,
        password: str,
        device_sn: str,
        battery_kwh: float = 9.6,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._email = email
        self._password = password
        self._device_sn = device_sn
        self._battery_kwh = battery_kwh
        self._token: str = ""
        self._token_expiry: float = 0.0

    def _ensure_token(self) -> None:
        if time.time() < self._token_expiry - 60:
            return
        resp = _post(
            f"{_BASE}/v1.0/account/token?appId={self._app_id}",
            {
                "appSecret": self._app_secret,
                "email": self._email,
                "password": _sha256(self._password),
            },
        )
        if not resp.get("success"):
            raise RuntimeError(f"Deye auth failed: {resp.get('msg')}")
        self._token = resp["data"]["accessToken"]
        self._token_expiry = time.time() + 3600

    def read(self) -> Snapshot:
        self._ensure_token()
        resp = _post(
            f"{_BASE}/v1.0/device/latest",
            {"deviceSn": [self._device_sn]},
            token=self._token,
        )
        if not resp.get("success"):
            raise RuntimeError(f"Deye device/latest failed: {resp.get('msg')}")

        device = resp.get("data", [{}])[0]
        kv: dict[str, float] = {}
        for item in device.get("dataList", []):
            try:
                kv[item["key"]] = float(item.get("value") or 0)
            except (ValueError, KeyError):
                pass

        def f(key: str, default: float = 0.0) -> float:
            return kv.get(key, default)

        pv1_w  = int(f("PV1Power"))
        pv2_w  = int(f("PV2Power"))
        batt_kw = f("BatPower")
        grid_kw = f("GridOrMeterActivePower")
        batt_soc = int(f("BatCapcity"))
        batt_v = f("BatVolt")
        grid_v = f("GridVolt")
        grid_hz = f("GridFreq")
        temp = f("DC_Temp")
        today_kwh = f("Eday")
        total_kwh = f("Etotal")

        batt_mode = (
            "discharging" if batt_kw > 0.03
            else "charging" if batt_kw < -0.03
            else "idle"
        )
        load_w = max(0, int(pv1_w + pv2_w + grid_kw * 1000 + batt_kw * 1000))

        if grid_v < 1.0:
            grid_status = "Indisponível"
        elif not (115.0 <= grid_v <= 140.0):
            grid_status = "Alarme"
        else:
            grid_status = "Normal"

        inv_status = (
            "Gerando" if (pv1_w + pv2_w) > 50
            else "Fornecendo" if batt_kw < -0.05
            else "Standby"
        )

        return Snapshot(
            timestamp=int(time.time()),
            source="cloud",
            solar=SolarData(
                pv1_w=pv1_w, pv2_w=pv2_w, total_w=pv1_w + pv2_w,
                pv1_v=round(f("PV1Volt"), 1), pv1_a=round(f("PV1Curr"), 2),
                pv2_v=round(f("PV2Volt"), 1), pv2_a=round(f("PV2Curr"), 2),
            ),
            battery=BatteryData(
                soc_pct=batt_soc,
                power_kw=round(batt_kw, 2),
                mode=batt_mode,
                voltage_v=round(batt_v, 1),
                available_kwh=round(batt_soc / 100.0 * self._battery_kwh, 2),
            ),
            grid=GridData(
                power_kw=round(grid_kw, 2),
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

    def get_alerts(self, start_ts: int, end_ts: int) -> list[Alert]:
        self._ensure_token()
        resp = _post(
            f"{_BASE}/v1.0/device/alertList",
            {"deviceSn": self._device_sn, "startTime": start_ts, "endTime": end_ts},
            token=self._token,
        )
        alerts = []
        for item in resp.get("data", {}).get("records", []):
            alerts.append(Alert(
                code=str(item.get("alarmCode", "")),
                msg=item.get("alarmName", ""),
                severity="warn",
            ))
        return alerts
