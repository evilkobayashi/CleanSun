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
_REG_TODAY_KWH   = 108   # ×0.1 kWh, daily generation (resets at midnight)
_REG_TOTAL_KWH   = 96    # ×0.1 kWh, cumulative generation (reg96 low + reg97 high)
_REG_GRID_V      = 150   # ×0.1 V, L1 phase voltage
_REG_LOAD_L1_W   = 160   # ×1 W signed, total load L1 (house consumption)
_REG_LOAD_L2_W   = 161   # ×1 W signed, total load L2 (house consumption)
_REG_BATT_V      = 183   # ×0.01 V
_REG_BATT_SOC    = 184   # ×1 %
_REG_PV1_W       = 186   # ×1 W
_REG_PV2_W       = 187   # ×1 W
_REG_BATT_W      = 190   # ×1 W signed (positive=discharging on Deye SUN-7.5K)


def _signed16(val: int) -> int:
    """Convert unsigned 16-bit Modbus value to signed Python int."""
    return val if val < 0x8000 else val - 0x10000


def _map_raw_to_snapshot(raw: dict, battery_kwh: float = 9.6) -> dict:
    """Map raw register dict to CleanSun telemetry snapshot."""
    _REQUIRED = (
        "pv1_v_raw", "pv1_a_raw", "pv2_v_raw", "pv2_a_raw",
        "pv1_w_raw", "pv2_w_raw", "temp_raw",
        "batt_v_raw", "batt_soc_raw", "batt_w_raw",
        "load_l1_w_raw", "load_l2_w_raw", "grid_v_raw", "grid_hz_raw",
        "today_kwh_raw", "total_kwh_raw",
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
    batt_w = _signed16(raw["batt_w_raw"])  # positive = discharging (Deye convention)
    # reg160+reg161 (L1+L2) = total house consumption — confirmed by AC load test
    # (matched Solarman "consumo" 990W at AC peak). This is the LOAD, not grid.
    load_w = max(0, _signed16(raw["load_l1_w_raw"]) + _signed16(raw["load_l2_w_raw"]))
    grid_v = raw["grid_v_raw"] * 0.1
    grid_hz = raw["grid_hz_raw"] * 0.01
    today_kwh = raw["today_kwh_raw"] * 0.1
    total_kwh = raw["total_kwh_raw"] * 0.1

    dc_kw   = (pv1_w + pv2_w) / 1000.0
    batt_kw = batt_w / 1000.0

    # Deye SUN-7.5K: positive batt_w = discharging, negative = charging
    if batt_w > 30:
        batt_mode = "discharging"
    elif batt_w < -30:
        batt_mode = "charging"
    else:
        batt_mode = "idle"

    # Grid exchange from energy balance: what load needs minus PV minus battery.
    # positive = importing from grid, negative = exporting.
    batt_discharge_w = max(0, batt_w)
    batt_charge_w = max(0, -batt_w)
    grid_w = load_w - (pv1_w + pv2_w) - batt_discharge_w + batt_charge_w
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
# Inverter configuration (static settings) — read on demand, not every poll
# ---------------------------------------------------------------------------

# Settings/identity registers (holding, FC03). Each field below was confirmed
# against the Solarman Smart app on the user's Deye SUN-7.5K SG05LP2-US-SM2:
#   reg3-7   serial "2511100737"
#   reg204   battery rated capacity 300 Ah
#   reg312   BMS charge voltage 53.5 V   (x0.01, unique match)
#   reg314   BMS charge current limit 50 A
#   reg315   BMS discharge current limit 50 A
#   reg316   BMS SOC 49 %                 reg317 battery voltage 49.33 V (x0.01)
_CFG_IDENT_START = 0       # regs 0-11: device type + serial (3-7 ASCII)
_CFG_BATTERY_START = 200   # regs 200-219: battery settings (capacity reg204)
_CFG_BMS_START = 310       # regs 310-319: BMS block


def _ascii_from_regs(regs) -> str:
    """Decode Deye ASCII serial: 2 chars per 16-bit reg, high byte first."""
    out = []
    for r in regs:
        out.append(chr((r >> 8) & 0xFF))
        out.append(chr(r & 0xFF))
    return "".join(out).strip("\x00 ").strip()


def _decode_inverter_config(ident: list, batt: list, bms: list) -> dict:
    """Decode confirmed static inverter settings into a labeled config dict.

    batt = holding block from reg 200 (index = reg-200);
    bms  = holding block from reg 310 (index = reg-310).
    Only fields verified against the Solarman Smart app are returned.
    """
    def b(reg):
        idx = reg - _CFG_BATTERY_START
        return batt[idx] if 0 <= idx < len(batt) else 0

    def m(reg):
        idx = reg - _CFG_BMS_START
        return bms[idx] if 0 <= idx < len(bms) else 0

    serial = _ascii_from_regs(ident[3:8]) if len(ident) >= 8 else ""
    return {
        "serial_number": serial,
        "battery_capacity_ah": b(204),                       # reg204 = 300 Ah
        "bms_charge_voltage_v": round(m(312) * 0.01, 2),     # reg312 = 53.5 V
        "bms_charge_current_limit_a": m(314),                # reg314 = 50 A
        "bms_discharge_current_limit_a": m(315),             # reg315 = 50 A
        "bms_soc_pct": m(316),                               # reg316 = 49 %
        "battery_voltage_v": round(m(317) * 0.01, 2),        # reg317 = 49.33 V
    }


# ---------------------------------------------------------------------------
# LAN Transport
# ---------------------------------------------------------------------------

class SolarmanLANTransport:
    """Reads Deye registers from local SOLARMAN datalogger on port 8899.

    Keeps one persistent Modbus/TCP connection alive across polls and reads
    registers in two blocks for speed:
      - FAST block 150-190 (power/load/battery/PV-watts) — read every poll
      - SLOW block 60-111 (PV V/A, temp, energy counters) — refreshed every
        ``slow_every`` polls, since these change slowly.
    This makes acquisition sub-second instead of reopening a TCP+handshake and
    issuing 6 separate round-trips each poll.
    """

    def __init__(self, ip: str, serial: int, port: int = 8899, mb_slaveid: int = 1,
                 slow_every: int = 5):
        self._ip = ip
        self._serial = serial
        self._port = port
        self._mb_slaveid = mb_slaveid
        self._slow_every = max(1, int(slow_every))
        self._modbus = None
        self._slow_cache = {}
        self._poll_count = 0

    def _client(self):
        if self._modbus is None:
            self._modbus = PySolarmanV5(
                self._ip,
                self._serial,
                port=self._port,
                mb_slaveid=self._mb_slaveid,
                verbose=False,
                auto_reconnect=True,
                socket_timeout=6,
            )
        return self._modbus

    def _drop(self):
        if self._modbus is not None:
            try:
                self._modbus.disconnect()
            except Exception:
                pass
            self._modbus = None

    @staticmethod
    def _extract_slow(b60: list) -> dict:
        # b60 covers regs 60..111 (index = reg - 60)
        return {
            "pv1_v_raw":     b60[0],    # reg60
            "pv1_a_raw":     b60[1],    # reg61
            "pv2_v_raw":     b60[2],    # reg62
            "pv2_a_raw":     b60[3],    # reg63
            "grid_hz_raw":   b60[19],   # reg79
            "temp_raw":      b60[30],   # reg90
            "today_kwh_raw": b60[48],   # reg108 = daily generation (resets midnight)
            "total_kwh_raw": (b60[37] << 16) | b60[36],  # reg97 high + reg96 low = cumulative
        }

    @staticmethod
    def _extract_fast(b150: list) -> dict:
        # b150 covers regs 150..190 (index = reg - 150)
        return {
            "grid_v_raw":    b150[0],    # reg150
            "load_l1_w_raw": b150[10],   # reg160 = total load L1
            "load_l2_w_raw": b150[11],   # reg161 = total load L2
            "batt_v_raw":    b150[33],   # reg183
            "batt_soc_raw":  b150[34],   # reg184
            "pv1_w_raw":     b150[36],   # reg186
            "pv2_w_raw":     b150[37],   # reg187
            "batt_w_raw":    b150[40],   # reg190
        }

    def read_registers(self) -> dict:
        if not _PYSOLARMAN_AVAILABLE:
            raise RuntimeError("pysolarmanv5 not installed. Run: pip install pysolarmanv5")
        modbus = self._client()
        try:
            b150 = modbus.read_holding_registers(_REG_GRID_V, 41)  # 150-190 (fast)
            if not self._slow_cache or self._poll_count % self._slow_every == 0:
                b60 = modbus.read_holding_registers(_REG_PV1_V, 52)  # 60-111 (slow)
                self._slow_cache = self._extract_slow(b60)
            self._poll_count += 1
        except Exception:
            self._drop()  # force fresh connect on next poll
            raise

        out = dict(self._slow_cache)
        out.update(self._extract_fast(b150))
        return out

    def read_config_registers(self) -> dict:
        """Read static identity + settings registers (on demand, not per poll)."""
        if not _PYSOLARMAN_AVAILABLE:
            raise RuntimeError("pysolarmanv5 not installed. Run: pip install pysolarmanv5")
        modbus = self._client()
        try:
            ident = modbus.read_holding_registers(_CFG_IDENT_START, 12)   # 0-11
            batt = modbus.read_holding_registers(_CFG_BATTERY_START, 20)   # 200-219
            bms = modbus.read_holding_registers(_CFG_BMS_START, 10)        # 310-319
        except Exception:
            self._drop()
            raise
        return {"ident": ident, "batt": batt, "bms": bms}


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

        load_kw = _f("LoadPower")
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
            "load_l1_w_raw": int(load_kw * 1000),  # cloud reports single total; put on L1
            "load_l2_w_raw": 0,
            "grid_v_raw":    int(_f("GridVolt") * 10),
            "grid_hz_raw":   int(_f("GridFreq") * 100),
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
            slow_every=int(solarman_cfg.get("slow_refresh_every", 5)),
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

    def read_inverter_config(self) -> dict:
        """Read + decode static inverter settings (serial, sell, TOU, limits).

        Returns {} when running on the cloud transport (no register access).
        """
        if self._using_cloud:
            return {}
        raw = self._lan.read_config_registers()
        cfg = _decode_inverter_config(raw["ident"], raw["batt"], raw["bms"])
        cfg["model"] = "SUN-7.5K-SG05LP2-US-SM2"
        cfg["manufacturer"] = "Deye"
        return cfg

    def get_memory_snapshot(self) -> list:
        return list(self._memory_buffer)

    def poll_and_store_forever(self, interval_seconds: int = 5, on_update=None):
        while True:
            payload = self.read_all()
            if on_update is not None:
                on_update(payload)
            time.sleep(interval_seconds)
