"""Módulo de leitura Modbus para inversores Growatt e fallback local rico."""
import importlib.util
import math
import random
import time

_MINIMALMODBUS_SPEC = importlib.util.find_spec("minimalmodbus")
if _MINIMALMODBUS_SPEC is not None:
    minimalmodbus = importlib.import_module("minimalmodbus")
else:
    minimalmodbus = None

REGISTER_MAP = {
    "potencia_instantanea_w": 0x0001,
    "tensao_dc_v": 0x0003,
    "geracao_dia_kwh": 0x0006,
    "geracao_total_kwh": 0x003B,
}


class _FallbackInstrument:
    """Gera dados coerentes de geração/consumo para uso local sem hardware."""

    WEATHER_GAIN = {
        "céu claro": 1.0,
        "parcialmente nublado": 0.72,
        "nublado": 0.48,
    }

    def __init__(self, weather="parcialmente nublado", kwp=5.0):
        self.weather = weather
        self.kwp = kwp
        self.daily_kwh = 0.0
        self.total_kwh = 1842.3
        self._last_tick = time.time()
        self._cache = {}

    def _sun_curve(self, hour_float):
        return max(0.0, math.sin((hour_float - 6.0) / 12.0 * math.pi))

    def _house_load(self, hour_float):
        morning = 0.35 if 6 <= hour_float <= 8.5 else 0.0
        lunch = 0.25 if 11.5 <= hour_float <= 13.5 else 0.0
        evening = 1.1 if 18 <= hour_float <= 22.5 else 0.0
        base = 0.38 + morning + lunch + evening
        return max(0.18, base + random.uniform(-0.08, 0.12))

    def _tick(self):
        now = time.time()
        delta_h = max(0.0, now - self._last_tick) / 3600.0
        self._last_tick = now
        lt = time.localtime(now)
        hour_float = lt.tm_hour + lt.tm_min / 60.0
        sun = self._sun_curve(hour_float)
        weather_gain = self.WEATHER_GAIN.get(self.weather, 0.72)
        pv_kw = max(0.0, self.kwp * sun * (weather_gain + random.uniform(-0.05, 0.05)))
        load_kw = self._house_load(hour_float)
        export_kw = max(0.0, pv_kw - load_kw)
        import_kw = max(0.0, load_kw - pv_kw)
        self.daily_kwh += pv_kw * delta_h
        self.total_kwh += pv_kw * delta_h
        expected_kw = self.kwp * sun
        dc_v = 160 + 260 * sun
        self._cache = {
            "potencia_instantanea_w": int(pv_kw * 1000),
            "tensao_dc_v": int(dc_v),
            "geracao_dia_kwh": round(self.daily_kwh, 3),
            "geracao_total_kwh": round(self.total_kwh, 1),
            "load_power_w": int(load_kw * 1000),
            "import_power_w": int(import_kw * 1000),
            "export_power_w": int(export_kw * 1000),
            "expected_generation_w": int(expected_kw * 1000),
            "weather_label": self.weather,
            "temperature_c": round(24 + 13 * sun + random.uniform(-1.2, 1.2), 1),
            "status_code": 1,
        }

    def read_register(self, register, number_of_decimals=0, signed=False):
        _ = (number_of_decimals, signed)
        self._tick()
        mapping = {
            0x0001: self._cache["potencia_instantanea_w"],
            0x0003: self._cache["tensao_dc_v"],
            0x0006: int(self._cache["geracao_dia_kwh"] * 10),
            0x003B: int(self._cache["geracao_total_kwh"] * 10),
        }
        return mapping.get(register, 0)

    def snapshot_extras(self):
        return dict(self._cache)


class GrowattModbusReader:
    """Leitor Modbus RTU com fallback local para simulação."""

    def __init__(
        self,
        port="COM3",
        slave_id=1,
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0.4,
        instrument=None,
        memory_size=1024,
    ):
        self.memory_size = memory_size
        self.memory_buffer = []
        self.last_payload = {}

        if instrument is not None:
            self.instrument = instrument
        elif minimalmodbus is None:
            self.instrument = _FallbackInstrument()
        else:
            inst = minimalmodbus.Instrument(port, slave_id)
            inst.serial.baudrate = baudrate
            inst.serial.bytesize = bytesize
            inst.serial.parity = parity
            inst.serial.stopbits = stopbits
            inst.serial.timeout = timeout
            inst.mode = minimalmodbus.MODE_RTU
            self.instrument = inst

    @staticmethod
    def _scale(register, raw_value):
        if register in (0x0006, 0x003B):
            return raw_value / 10.0
        return float(raw_value)

    def _estimated_extras(self, data):
        generation_w = data["potencia_instantanea_w"]
        hour = time.localtime().tm_hour
        base_load_w = 450 if 8 <= hour <= 17 else 950
        load_w = max(base_load_w, int(base_load_w + random.uniform(-120, 260)))
        export_w = max(0, int(generation_w - load_w))
        import_w = max(0, int(load_w - generation_w))
        return {
            "load_power_w": load_w,
            "import_power_w": import_w,
            "export_power_w": export_w,
            "expected_generation_w": generation_w,
            "weather_label": "não informado",
            "temperature_c": 28.0,
            "status_code": 1,
        }

    def read_all(self):
        data = {}
        for name, register in REGISTER_MAP.items():
            raw = self.instrument.read_register(register, 0, False)
            data[name] = self._scale(register, raw)

        extras = self.instrument.snapshot_extras() if hasattr(self.instrument, "snapshot_extras") else self._estimated_extras(data)
        data.update(extras)
        data["instant_total_w"] = data["potencia_instantanea_w"]
        data["daily_gen_kwh"] = data["geracao_dia_kwh"]
        data["total_gen_kwh"] = data["geracao_total_kwh"]
        data["timestamp"] = int(time.time())
        self.last_payload = data
        self.memory_buffer.append(data)
        if len(self.memory_buffer) > self.memory_size:
            self.memory_buffer.pop(0)
        return data

    def poll_and_store_forever(self, interval_seconds=5, on_update=None):
        while True:
            payload = self.read_all()
            if on_update is not None:
                on_update(payload)
            time.sleep(interval_seconds)

    def get_memory_snapshot(self):
        return list(self.memory_buffer)
