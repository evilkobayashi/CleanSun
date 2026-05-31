from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class SolarData(BaseModel):
    pv1_w: int = 0
    pv2_w: int = 0
    total_w: int = 0
    pv1_v: float = 0.0
    pv1_a: float = 0.0
    pv2_v: float = 0.0
    pv2_a: float = 0.0


class BatteryData(BaseModel):
    soc_pct: int = 0
    power_kw: float = 0.0
    mode: Literal["charging", "discharging", "idle"] = "idle"
    voltage_v: float = 0.0
    available_kwh: float = 0.0


class GridData(BaseModel):
    power_kw: float = 0.0
    voltage_v: float = 0.0
    frequency_hz: float = 0.0
    status: str = "Unknown"


class LoadData(BaseModel):
    power_w: int = 0


class InverterData(BaseModel):
    temp_c: float = 0.0
    status: str = "Unknown"


class EnergyData(BaseModel):
    today_kwh: float = 0.0
    total_kwh: float = 0.0


class Alert(BaseModel):
    code: str
    msg: str
    severity: str = "warn"


class Snapshot(BaseModel):
    timestamp: int
    source: Literal["lan", "cloud", "stale"]
    solar: SolarData
    battery: BatteryData
    grid: GridData
    load: LoadData
    inverter: InverterData
    energy: EnergyData
    alerts: list[Alert] = Field(default_factory=list)
    stale: bool = False
