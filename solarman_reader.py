"""Leitor Solarman/Deye para CleanSun — substitui modbus_reader.py."""
import hashlib
import json
import time
import urllib.request
import urllib.error

try:
    from pysolarmanv5 import PySolarmanV5, V5FrameError
    _PYSOLARMAN_AVAILABLE = True
except ImportError:
    _PYSOLARMAN_AVAILABLE = False

from logger import CleanSunLogger

_log = CleanSunLogger("cleansun.solarman", "INFO")

# ---------------------------------------------------------------------------
# Register map — Holding Registers (Function Code 03)
# Deye SUN-7.5K-SG05LP2-US-SM2 uses FC03, not FC04
# ---------------------------------------------------------------------------

_REG_PV1_V       = 60    # ×0.1 V (no-signal at night: ~65429, treated as 0)
_REG_PV1_A       = 61    # ×0.1 A
_REG_PV2_V       = 62    # ×0.1 V
_REG_PV2_A       = 63    # ×0.1 A
_REG_GRID_HZ     = 79    # ×0.01 Hz
_REG_TEMP        = 90    # (value − 1000) × 0.1 °C
_REG_TODAY_KWH   = 109   # ×0.1 kWh
_REG_TOTAL_KWH   = 111   # ×0.1 kWh
_REG_GRID_V      = 150   # ×0.1 V, L1 phase voltage
_REG_GRID_W      = 169   # ×1 W signed (positive=importing)
_REG_LOAD_W      = 175   # ×1 W signed-negative (abs for load W)
_REG_BATT_V      = 183   # ×0.01 V
_REG_BATT_SOC    = 184   # ×1 %
_REG_PV1_W       = 186   # ×1 W
_REG_PV2_W       = 187   # ×1 W
_REG_BATT_W      = 190   # ×1 W signed (positive=charging)


def _signed16(val: int) -> int:
    """Convert unsigned 16-bit Modbus value to signed Python int."""
    return val if val < 0x8000 else val - 0x10000


def _map_raw_to_snapshot(raw: dict, battery_kwh: float = 9.6) -> dict:
    """Map raw register dict to CleanSun telemetry snapshot."""
    _REQUIRED = (
        "pv1_v_raw", "pv1_a_raw", "pv2_v_raw", "pv2_a_raw",
        "pv1_w_raw", "pv2_w_raw", "temp_raw",
        "batt_v_raw", "batt_soc_raw", "batt_w_raw",
        "grid_w_raw", "grid_v_raw", "grid_hz_raw",
        "load_w_raw", "today_kwh_raw", "total_kwh_raw",
    )
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        raise ValueError("Raw dict missing keys: {}".format(missing))
    pv1_v  = max(0.0, _signed16(raw["pv1_v_raw"]) * 0.1)
    pv1_a  = max(0.0, _signed16(raw["pv1_a_raw"]) * 0.1)
    pv2_v  = max(0.0, _signed16(raw["pv2_v_raw"]) * 0.1)
    pv2_a  = max(0.0, _signed16(raw["pv2_a_raw"]) * 0.1)
    pv1_w  = raw["pv1_w_raw"]
    pv2_w  = raw["pv2_w_raw"]
    temp   = (raw["temp_raw"] - 1000) * 0.1
    batt_v = raw["batt_v_raw"] * 0.01
    batt_soc = raw["batt_soc_raw"]
    batt_w = _signed16(raw["batt_w_raw"])
    grid_w = _signed16(raw["grid_w_raw"])
    grid_v = raw["grid_v_raw"] * 0.1
    grid_hz = raw["grid_hz_raw"] * 0.01
    load_w = abs(_signed16(raw["load_w_raw"]))
    today_kwh = raw["today_kwh_raw"] * 0.1
    total_kwh = raw["total_kwh_raw"] * 0.1

    dc_kw   = (pv1_w + pv2_w) / 1000.0
    batt_kw = batt_w / 1000.0

    if batt_w > 120:
        batt_mode = "charging"
    elif batt_w < -120:
        batt_mode = "discharging"
    else:
        batt_mode = "idle"

    import_w = max(0, grid_w)
    export_w = max(0, -grid_w)

    if grid_v < 1.0:
        grid_status = "Indisponível"
    elif not (115.0 <= grid_v <= 140.0):
        grid_status = "Alarme"
    else:
        grid_status = "Normal"

    return {
        # Core legacy fields (used by DataProcessor)
        "potencia_instantanea_w": pv1_w + pv2_w,
        "tensao_dc_v": round((pv1_v + pv2_v) / 2.0, 1),
        "geracao_dia_kwh": round(today_kwh, 3),
        "geracao_total_kwh": round(total_kwh, 1),
        "instant_total_w": pv1_w + pv2_w,
        "daily_gen_kwh": round(today_kwh, 3),
        "total_gen_kwh": round(total_kwh, 1),
        "timestamp": int(time.time()),
        # Power
        "load_power_w": load_w,
        "load_power_kw": round(load_w / 1000.0, 2),
        "import_power_w": import_w,
        "export_power_w": export_w,
        "dc_power_w": pv1_w + pv2_w,
        "ac_power_w": pv1_w + pv2_w,
        "expected_generation_w": pv1_w + pv2_w,
        # Inverter state
        "temperature_c": round(temp, 1),
        "status_code": 1,
        "inverter_status": "Gerando" if (pv1_w + pv2_w) > 50 else ("Fornecendo" if batt_w < -50 else "Standby"),
        "communication_status": raw.get("_comm_status", "Online"),
        "grid_status": grid_status,
        "grid_available": grid_v > 1.0,
        "irradiance_wm2": 0,
        "weather_label": "não informado",
        "simulation_scenario": "hardware",
        # Battery
        "battery_soc_percent": round(batt_soc, 1),
        "battery_voltage_v": round(batt_v, 1),
        "battery_current_a": round(batt_w / max(batt_v, 1.0), 2),
        "battery_power_kw": round(batt_kw, 2),
        "battery_mode": batt_mode,
        "backup_mode_active": False,
        "operating_mode": "hybrid",
        "autonomy_hours": 0.0,
        # Device metadata
        "manufacturer": "Deye",
        "brand": "Deye",
        "model": "SUN-7.5K-SG05LP2-US-SM2",
        "product_family": "hybrid",
        "firmware_version": "unknown",
        "inverter_mode": "hybrid",
        "serial_number": raw.get("_serial_number", ""),
        "inverter_capabilities": ["solar", "battery", "grid_export", "backup"],
        # Nested structures
        "dc_input": {
            "mppt1_voltage_v": round(pv1_v, 1),
            "mppt1_current_a": round(pv1_a, 2),
            "mppt1_power_kw": round(pv1_w / 1000.0, 2),
            "mppt2_voltage_v": round(pv2_v, 1),
            "mppt2_current_a": round(pv2_a, 2),
            "mppt2_power_kw": round(pv2_w / 1000.0, 2),
            "dc_power_kw": round(dc_kw, 2),
        },
        "ac_output": {
            "voltage_v": round(grid_v, 1),
            "current_a": round((pv1_w + pv2_w) / max(grid_v, 1.0), 2),
            "power_kw": round(dc_kw, 2),
            "frequency_hz": round(grid_hz, 2),
            "power_factor": 0.99,
        },
        "grid": {
            "grid_voltage_v": round(grid_v, 1),
            "grid_current_a": round(abs(grid_w) / max(grid_v, 1.0), 2),
            "grid_status": grid_status,
            "frequency_hz": round(grid_hz, 2),
            "active_power_kw": round(grid_w / 1000.0, 2),
            "apparent_power_kva": round(abs(grid_w) / 1000.0, 2),
        },
        "battery": {
            "soc_percent": round(batt_soc, 1),
            "voltage_v": round(batt_v, 1),
            "current_a": round(batt_w / max(batt_v, 1.0), 2),
            "power_kw": round(batt_kw, 2),
            "mode": batt_mode,
            "autonomy_hours": 0.0,
            "available_energy_kwh": round(batt_soc / 100.0 * battery_kwh, 2),
        },
        "inverter": {
            "temperature_c": round(temp, 1),
            "efficiency_percent": 97.0,
            "status": "Gerando" if (pv1_w + pv2_w) > 50 else ("Fornecendo" if batt_w < -50 else "Standby"),
            "communication_status": raw.get("_comm_status", "Online"),
            "operational_state": "Gerando" if (pv1_w + pv2_w) > 50 else ("Fornecendo" if batt_w < -50 else "Standby"),
        },
        "energy": {
            "today_kwh": round(today_kwh, 2),
            "total_kwh": round(total_kwh, 1),
            "import_kwh": round(import_w / 1000.0 * (5.0 / 3600.0), 3),
            "export_kwh": round(export_w / 1000.0 * (5.0 / 3600.0), 3),
            "peak_power_kw": round(dc_kw, 2),
            "generation_start_time": "--:--",
            "generation_end_time": "--:--",
            "generation_duration_h": 0.0,
            "battery_available_kwh": round(batt_soc / 100.0 * battery_kwh, 2),
            "autonomy_hours": 0.0,
        },
        "operation": {
            "operating_mode": "hybrid",
            "backup_mode_active": False,
            "grid_available": grid_v > 1.0,
        },
    }


# ---------------------------------------------------------------------------
# LAN Transport
# ---------------------------------------------------------------------------

class SolarmanLANTransport:
    """Reads Deye registers from local SOLARMAN datalogger on port 8899."""

    def __init__(self, ip: str, serial: int, port: int = 8899, mb_slaveid: int = 1):
        self._ip = ip
        self._serial = serial
        self._port = port
        self._mb_slaveid = mb_slaveid

    def read_registers(self) -> dict:
        if not _PYSOLARMAN_AVAILABLE:
            raise RuntimeError("pysolarmanv5 not installed. Run: pip install pysolarmanv5")
        modbus = PySolarmanV5(
            self._ip,
            self._serial,
            port=self._port,
            mb_slaveid=self._mb_slaveid,
            verbose=False,
            auto_reconnect=True,
        )
        try:
            b60   = modbus.read_holding_registers(_REG_PV1_V, 4)      # 60-63
            b79   = modbus.read_holding_registers(_REG_GRID_HZ, 1)    # 79
            b90   = modbus.read_holding_registers(_REG_TEMP, 1)        # 90
            b109  = modbus.read_holding_registers(_REG_TODAY_KWH, 3)  # 109-111
            b150  = modbus.read_holding_registers(_REG_GRID_V, 20)    # 150-169
            b175  = modbus.read_holding_registers(_REG_LOAD_W, 1)     # 175
            b183  = modbus.read_holding_registers(_REG_BATT_V, 8)     # 183-190
        finally:
            try:
                modbus.disconnect()
            except Exception:
                pass

        return {
            "pv1_v_raw":     b60[0],
            "pv1_a_raw":     b60[1],
            "pv2_v_raw":     b60[2],
            "pv2_a_raw":     b60[3],
            "grid_hz_raw":   b79[0],
            "temp_raw":      b90[0],
            "today_kwh_raw": b109[0],
            "total_kwh_raw": b109[2],
            "grid_v_raw":    b150[0],   # reg150
            "grid_w_raw":    b150[19],  # reg169 = 150+19
            "load_w_raw":    b175[0],
            "batt_v_raw":    b183[0],
            "batt_soc_raw":  b183[1],
            "pv1_w_raw":     b183[3],
            "pv2_w_raw":     b183[4],
            "batt_w_raw":    b183[7],
        }


# ---------------------------------------------------------------------------
# Cloud Transport
# ---------------------------------------------------------------------------

_CLOUD_BASE = "https://globalapi.solarmanpv.com"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _post_json(url: str, payload: dict, token: str = "") -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "bearer " + token)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


class SolarmanCloudTransport:
    """Reads Deye data from Solarman Cloud API (Business API v2)."""

    def __init__(self, cfg: dict):
        self._cfg = cfg

    def _get_token(self) -> str:
        url = "{}/account/v1.0/token?appId={}&language=en".format(
            _CLOUD_BASE, self._cfg["app_id"]
        )
        body = {
            "appSecret": _md5(self._cfg["app_id"] + self._cfg["app_secret"]),
            "email": self._cfg["email"],
            "password": _md5(self._cfg["password"]),
        }
        resp = _post_json(url, body)
        return resp["access_token"]

    def _fetch_device_data(self, token: str) -> list:
        url = "{}/device/v1.0/currentData?appId={}&language=en".format(
            _CLOUD_BASE, self._cfg["app_id"]
        )
        resp = _post_json(url, {"deviceSn": self._cfg["device_sn"]}, token=token)
        return resp.get("dataList", [])

    @staticmethod
    def _kv(data_list: list) -> dict:
        return {item["key"]: item["value"] for item in data_list if "key" in item}

    def read_registers(self) -> dict:
        if not self._cfg.get("enabled", False):
            raise RuntimeError("Solarman cloud fallback is disabled in config")
        token = self._get_token()
        data_list = self._fetch_device_data(token)
        kv = self._kv(data_list)

        def _f(key, default=0.0):
            try:
                return float(kv.get(key, default))
            except (ValueError, TypeError):
                return float(default)

        grid_kw = _f("GridOrMeterActivePower")
        batt_kw = _f("BatPower")

        return {
            "pv1_v_raw":     int(_f("PV1Volt") * 10),
            "pv1_a_raw":     int(_f("PV1Curr") * 10),
            "pv2_v_raw":     int(_f("PV2Volt") * 10),
            "pv2_a_raw":     int(_f("PV2Curr") * 10),
            "pv1_w_raw":     int(_f("PV1Power")),
            "pv2_w_raw":     int(_f("PV2Power")),
            "temp_raw":      int(_f("DC_Temp") * 10) + 1000,
            "batt_v_raw":    int(_f("BatVolt") * 100),
            "batt_soc_raw":  int(_f("BatCapcity")),
            "batt_w_raw":    int(batt_kw * 1000),
            "grid_w_raw":    int(grid_kw * 1000),
            "grid_v_raw":    int(_f("GridVolt") * 10),
            "grid_hz_raw":   int(_f("GridFreq") * 100),
            "load_w_raw":    int(_f("LoadPower") * 1000),
            "today_kwh_raw": int(_f("Eday") * 10),
            "total_kwh_raw": int(_f("Etotal") * 10),
            "_comm_status": "Cloud",
        }


# ---------------------------------------------------------------------------
# Reader (public interface — drop-in replacement for GrowattModbusReader)
# ---------------------------------------------------------------------------

class DeyeSolarmanReader:
    """
    Reads Deye inverter via SOLARMAN LAN protocol with optional cloud fallback.
    Same interface as the retired GrowattModbusReader.
    """

    def __init__(self, solarman_cfg: dict, memory_size: int = 1024):
        self._cfg = solarman_cfg
        self._memory_size = memory_size
        self._battery_kwh = float(solarman_cfg.get("battery_capacity_kwh", 9.6))
        self._memory_buffer: list = []
        self.last_payload: dict = {}
        self._lan_fail_count: int = 0
        self._using_cloud: bool = False

        self._threshold: int = int(solarman_cfg.get("lan_fail_threshold", 3))
        if not solarman_cfg.get("datalogger_ip"):
            raise ValueError(
                "solarman config missing 'datalogger_ip' — "
                "set the IP of your SOLARMAN Wi-Fi datalogger in config.json"
            )
        if not solarman_cfg.get("datalogger_serial"):
            raise ValueError(
                "solarman config missing 'datalogger_serial' — "
                "set the serial number from your datalogger sticker in config.json"
            )

        self._lan = SolarmanLANTransport(
            ip=solarman_cfg["datalogger_ip"],
            serial=int(solarman_cfg["datalogger_serial"]),
            port=int(solarman_cfg.get("datalogger_port", 8899)),
            mb_slaveid=int(solarman_cfg.get("mb_slaveid", 1)),
        )
        self._cloud = SolarmanCloudTransport(
            solarman_cfg.get("cloud_fallback", {"enabled": False})
        )

    def _read_raw(self) -> dict:
        if self._using_cloud:
            try:
                raw = self._lan.read_registers()
                self._lan_fail_count = 0
                self._using_cloud = False
                _log.info("LAN transport recovered — switching back from cloud")
                return raw
            except Exception:
                return self._cloud.read_registers()

        try:
            raw = self._lan.read_registers()
            self._lan_fail_count = 0
            return raw
        except Exception as exc:
            self._lan_fail_count += 1
            _log.warning("LAN read failed ({}/{}): {}".format(
                self._lan_fail_count, self._threshold, exc))
            if self._lan_fail_count >= self._threshold:
                cloud_cfg = self._cfg.get("cloud_fallback", {})
                if cloud_cfg.get("enabled", False):
                    _log.warning("Switching to Solarman cloud fallback")
                    self._using_cloud = True
                    return self._cloud.read_registers()
            raise

    def read_all(self) -> dict:
        raw = self._read_raw()
        data = _map_raw_to_snapshot(raw, battery_kwh=self._battery_kwh)
        self.last_payload = data
        self._memory_buffer.append(data)
        if len(self._memory_buffer) > self._memory_size:
            self._memory_buffer.pop(0)
        return data

    def get_memory_snapshot(self) -> list:
        return list(self._memory_buffer)

    def poll_and_store_forever(self, interval_seconds: int = 5, on_update=None):
        while True:
            payload = self.read_all()
            if on_update is not None:
                on_update(payload)
            time.sleep(interval_seconds)
