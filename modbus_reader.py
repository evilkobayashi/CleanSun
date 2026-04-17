"""Módulo de leitura Modbus para inversores Growatt e fallback técnico rico."""
import importlib
import importlib.util
import math
import random
import time

_MINIMALMODBUS_SPEC = importlib.util.find_spec("minimalmodbus")
minimalmodbus = importlib.import_module("minimalmodbus") if _MINIMALMODBUS_SPEC is not None else None

REGISTER_MAP = {
    "potencia_instantanea_w": 0x0001,
    "tensao_dc_v": 0x0003,
    "geracao_dia_kwh": 0x0006,
    "geracao_total_kwh": 0x003B,
}


class _FallbackInstrument:
    """Simula operação técnica de um inversor fotovoltaico residencial."""

    DEVICE_PROFILES = {
        "on-grid": {"manufacturer": "Growatt", "brand": "Growatt", "model": "MIN 5000TL-X", "product_family": "grid_tie", "serial_prefix": "GRT", "inverter_mode": "grid_tie", "inverter_capabilities": ["solar", "grid_export", "net_metering"]},
        "off-grid": {"manufacturer": "Growatt", "brand": "Growatt", "model": "SPF 5000 ES", "product_family": "off_grid", "serial_prefix": "GOF", "inverter_mode": "island", "inverter_capabilities": ["solar", "battery", "load_supply"]},
        "hybrid": {"manufacturer": "Growatt", "brand": "Growatt", "model": "SPH5000", "product_family": "hybrid", "serial_prefix": "GHY", "inverter_mode": "hybrid", "inverter_capabilities": ["solar", "battery", "grid_export", "backup"]},
    }

    WEATHER_GAIN = {"céu claro": 1.0, "parcialmente nublado": 0.76, "nublado": 0.52}
    STATUS_MAP = {0: "Standby", 1: "Gerando", 2: "Falha", 3: "Desconectado"}
    RANDOM_SCENARIOS = ["normal", "sombreamento", "sobretensao_rede", "subtensao_rede", "temperatura_alta", "falha_comunicacao", "desbalanceamento_mppt", "sem_geracao_dia", "dc_subtensao", "dc_sobretensao"]

    def __init__(self, weather="parcialmente nublado", kwp=5.0, scenario="auto", random_fault_rate=0.04, inverter_type="hybrid"):
        self.weather = weather
        self.kwp = kwp
        self.scenario = scenario
        self.random_fault_rate = random_fault_rate
        self.inverter_type = inverter_type if inverter_type in self.DEVICE_PROFILES else "hybrid"
        self.daily_kwh = 0.0
        self.total_kwh = 18452.7
        self.peak_power_kw = 0.0
        self._last_tick = time.time()
        self._cache = {}
        self._start_generation_ts = None
        self._end_generation_ts = None
        self._active_random = "normal"
        self._random_until_ts = 0
        self.battery_soc = 62.0
        self.device_profile = dict(self.DEVICE_PROFILES[self.inverter_type])
        self.device_profile["serial_number"] = self.device_profile["serial_prefix"] + "123456789"
        self.device_profile["firmware_version"] = "FW-1.0.{}".format({"on-grid": 3, "off-grid": 7, "hybrid": 9}[self.inverter_type])

    @staticmethod
    def _sun_curve(hour_float):
        return max(0.0, math.sin((hour_float - 6.0) / 12.0 * math.pi))

    @staticmethod
    def _house_load(hour_float):
        base = 0.32 if hour_float < 5 else 0.45
        if 6 <= hour_float <= 8.5:
            base += 0.50
        elif 12 <= hour_float <= 13.5:
            base += 0.22
        elif 18 <= hour_float <= 22.5:
            base += 1.20
        return max(0.18, base + random.uniform(-0.08, 0.16))

    def _current_scenario(self, now):
        if self.scenario != "auto":
            return self.scenario
        if now >= self._random_until_ts:
            if random.random() < self.random_fault_rate:
                self._active_random = random.choice(self.RANDOM_SCENARIOS[1:])
                self._random_until_ts = now + random.randint(45, 180)
            else:
                self._active_random = "normal"
                self._random_until_ts = now + random.randint(20, 60)
        return self._active_random

    def _pick_status(self, generation_kw, grid_available, scenario):
        if scenario in ("falha_inversor",):
            return 2
        if not grid_available:
            return 3 if generation_kw > 0 else 0
        return 1 if generation_kw > 0.05 else 0

    def _scenario_adjustments(self, scenario, generation_kw, temp_c, grid_voltage, grid_freq, mppt1_v, mppt2_v, mppt1_kw, mppt2_kw, sun):
        communication_status = "Online"
        if scenario == "sombreamento":
            generation_kw *= 0.58
            mppt2_kw *= 0.45
        elif scenario == "sobretensao_rede":
            grid_voltage = 252 + random.uniform(1, 7)
        elif scenario == "subtensao_rede":
            grid_voltage = 188 + random.uniform(-4, 4)
        elif scenario == "temperatura_alta":
            temp_c += 19
            generation_kw *= 0.93
        elif scenario == "rede_indisponivel":
            grid_voltage = 0.0
            grid_freq = 0.0
        elif scenario == "falha_comunicacao":
            communication_status = "Offline"
        elif scenario == "desbalanceamento_mppt":
            mppt1_kw *= 1.08
            mppt2_kw *= 0.32
        elif scenario == "sem_geracao_dia" and sun > 0.2:
            generation_kw = 0.0
            mppt1_kw = 0.0
            mppt2_kw = 0.0
        elif scenario == "dc_subtensao":
            mppt1_v = 142 + random.uniform(-4, 4)
            mppt2_v = 150 + random.uniform(-4, 4)
            generation_kw *= 0.62
        elif scenario == "dc_sobretensao":
            mppt1_v = 492 + random.uniform(0, 12)
            mppt2_v = 486 + random.uniform(0, 12)
            generation_kw *= 0.20
        return generation_kw, temp_c, grid_voltage, grid_freq, mppt1_v, mppt2_v, mppt1_kw, mppt2_kw, communication_status

    def _apply_profile_behaviour(self, load_kw, ac_kw, import_kw, export_kw, battery_power_kw, grid_available, scenario):
        if self.inverter_type == "on-grid":
            battery_power_kw = 0.0
            self.battery_soc = 0.0
            import_kw = max(0.0, load_kw - ac_kw)
            export_kw = max(0.0, ac_kw - load_kw)
            grid_available = True if scenario != "rede_indisponivel" else False
        elif self.inverter_type == "off-grid":
            export_kw = 0.0
            import_kw = 0.0
            grid_available = False
            battery_power_kw = max(-3.2, min(3.2, ac_kw - load_kw * 0.92))
            self.battery_soc = max(10.0, min(98.0, self.battery_soc + battery_power_kw * 0.04))
        return import_kw, export_kw, battery_power_kw, grid_available

    def _tick(self):
        now = time.time()
        delta_h = max(0.0, now - self._last_tick) / 3600.0
        self._last_tick = now
        lt = time.localtime(now)
        hour_float = lt.tm_hour + lt.tm_min / 60.0
        sun = self._sun_curve(hour_float)
        weather_gain = self.WEATHER_GAIN.get(self.weather, 0.76)
        scenario = self._current_scenario(now)
        irradiance = int(1000 * sun * weather_gain)
        expected_kw = self.kwp * sun
        generation_kw = max(0.0, expected_kw * weather_gain * (1 + random.uniform(-0.04, 0.04)))
        load_kw = self._house_load(hour_float)
        temp_c = 26 + 15 * sun + random.uniform(-0.8, 1.2)
        battery_voltage = 50.8 + random.uniform(-1.2, 1.2)
        grid_voltage = 220 + random.uniform(-2.5, 2.5)
        grid_freq = 60 + random.uniform(-0.08, 0.08)
        mppt1_v = max(0.0, 180 + 220 * sun + random.uniform(-4, 4))
        mppt2_v = max(0.0, 176 + 214 * sun + random.uniform(-4, 4))
        split = 0.52 + random.uniform(-0.05, 0.05)
        mppt1_kw = generation_kw * split
        mppt2_kw = max(0.0, generation_kw - mppt1_kw)

        generation_kw, temp_c, grid_voltage, grid_freq, mppt1_v, mppt2_v, mppt1_kw, mppt2_kw, communication_status = self._scenario_adjustments(
            scenario, generation_kw, temp_c, grid_voltage, grid_freq, mppt1_v, mppt2_v, mppt1_kw, mppt2_kw, sun
        )
        dc_kw = max(0.0, mppt1_kw + mppt2_kw)
        grid_available = scenario != "rede_indisponivel"
        efficiency = 95.2 + 1.4 * sun + random.uniform(-0.5, 0.4)
        if scenario == "temperatura_alta":
            efficiency -= 3.2
        efficiency = max(88.0, min(efficiency, 98.4))
        ac_kw = dc_kw * efficiency / 100.0 if (grid_available or self.inverter_type in ("off-grid", "hybrid")) else 0.0
        battery_power_kw = max(-2.8, min(2.8, dc_kw - load_kw * 0.82))
        if scenario in ("sem_geracao_dia", "falha_comunicacao"):
            battery_power_kw = -max(0.4, load_kw * 0.65)
        elif scenario == "temperatura_alta":
            battery_power_kw *= 0.8
        import_kw = max(0.0, load_kw - ac_kw)
        export_kw = max(0.0, ac_kw - load_kw)
        import_kw, export_kw, battery_power_kw, grid_available = self._apply_profile_behaviour(load_kw, ac_kw, import_kw, export_kw, battery_power_kw, grid_available, scenario)
        ac_current = (ac_kw * 1000 / max(grid_voltage, 1)) if grid_voltage else 0.0
        power_factor = max(0.88, min(0.995, 0.97 + random.uniform(-0.03, 0.01)))
        apparent_kw = ac_kw / max(power_factor, 0.01) if ac_kw else 0.0
        grid_current = ((import_kw if import_kw > 0 else export_kw) * 1000 / max(grid_voltage, 1)) if grid_voltage else 0.0
        status_code = self._pick_status(ac_kw, grid_available, scenario)
        inverter_status = self.STATUS_MAP[status_code]
        grid_status = "Indisponível" if not grid_available else ("Alarme" if grid_voltage < 195 or grid_voltage > 245 else "Normal")

        mppt1_a = (mppt1_kw * 1000 / max(mppt1_v, 1)) if mppt1_v else 0.0
        mppt2_a = (mppt2_kw * 1000 / max(mppt2_v, 1)) if mppt2_v else 0.0
        if self.inverter_type != "on-grid":
            self.battery_soc = max(8.0, min(98.0, self.battery_soc + battery_power_kw * delta_h * 7.5))
            if self.battery_soc < 18:
                battery_power_kw = min(battery_power_kw, -0.15)
        battery_current_a = (battery_power_kw * 1000 / max(battery_voltage, 1)) if battery_voltage else 0.0
        battery_mode = "charging" if battery_power_kw > 0.12 else "discharging" if battery_power_kw < -0.12 else "idle"
        autonomy_h = (self.battery_soc / 100.0 * 9.6) / max(load_kw, 0.2) if self.inverter_type != "on-grid" else 0.0
        backup_mode_active = self.inverter_type in ("off-grid", "hybrid") and (scenario in ("rede_indisponivel", "sem_geracao_dia") or self.battery_soc < 25)
        if self.inverter_type == "on-grid":
            operating_mode = "grid_tie"
        elif self.inverter_type == "off-grid":
            operating_mode = "island"
        else:
            operating_mode = "backup" if backup_mode_active else "battery_support" if battery_mode == "discharging" else "grid_assist" if import_kw > 0 else "solar_priority"

        if ac_kw > 0.05 and self._start_generation_ts is None:
            self._start_generation_ts = int(now)
        if ac_kw > 0.05:
            self._end_generation_ts = int(now)
        self.daily_kwh += ac_kw * delta_h
        self.total_kwh += ac_kw * delta_h
        self.peak_power_kw = max(self.peak_power_kw, ac_kw)
        generation_time_h = 0.0
        if self._start_generation_ts and self._end_generation_ts:
            generation_time_h = max(0.0, (self._end_generation_ts - self._start_generation_ts) / 3600.0)

        snapshot = {
            "potencia_instantanea_w": int(ac_kw * 1000),
            "tensao_dc_v": round((mppt1_v + mppt2_v) / 2.0, 1),
            "geracao_dia_kwh": round(self.daily_kwh, 3),
            "geracao_total_kwh": round(self.total_kwh, 1),
            "expected_generation_w": int(expected_kw * 1000),
            "load_power_w": int(load_kw * 1000),
            "import_power_w": int(import_kw * 1000),
            "export_power_w": int(export_kw * 1000),
            "temperature_c": round(temp_c, 1),
            "weather_label": self.weather,
            "status_code": status_code,
            "inverter_status": inverter_status,
            "communication_status": communication_status,
            "grid_status": grid_status,
            "irradiance_wm2": irradiance,
            "dc_power_w": int(dc_kw * 1000),
            "ac_power_w": int(ac_kw * 1000),
            "simulation_scenario": scenario,
            "manufacturer": self.device_profile["manufacturer"],
            "brand": self.device_profile["brand"],
            "model": self.device_profile["model"],
            "product_family": self.device_profile["product_family"],
            "firmware_version": self.device_profile["firmware_version"],
            "inverter_mode": self.device_profile["inverter_mode"],
            "serial_number": self.device_profile["serial_number"],
            "inverter_capabilities": list(self.device_profile["inverter_capabilities"]),
            "load_power_kw": round(load_kw, 2),
            "grid_available": grid_available,
            "dc_input": {
                "mppt1_voltage_v": round(mppt1_v, 1),
                "mppt1_current_a": round(mppt1_a, 2),
                "mppt1_power_kw": round(mppt1_kw, 2),
                "mppt2_voltage_v": round(mppt2_v, 1),
                "mppt2_current_a": round(mppt2_a, 2),
                "mppt2_power_kw": round(mppt2_kw, 2),
                "dc_power_kw": round(dc_kw, 2),
            },
            "ac_output": {
                "voltage_v": round(grid_voltage, 1),
                "current_a": round(ac_current, 2),
                "power_kw": round(ac_kw, 2),
                "frequency_hz": round(grid_freq, 2),
                "power_factor": round(power_factor, 3),
            },
            "inverter": {
                "temperature_c": round(temp_c, 1),
                "efficiency_percent": round(efficiency, 2),
                "status": inverter_status,
                "communication_status": communication_status,
                "operational_state": inverter_status,
            },
            "energy": {
                "today_kwh": round(self.daily_kwh, 2),
                "total_kwh": round(self.total_kwh, 1),
                "import_kwh": round(import_kw * 0.083, 3),
                "export_kwh": round(export_kw * 0.083, 3),
                "peak_power_kw": round(self.peak_power_kw, 2),
                "generation_start_time": time.strftime("%H:%M", time.localtime(self._start_generation_ts)) if self._start_generation_ts else "--:--",
                "generation_end_time": time.strftime("%H:%M", time.localtime(self._end_generation_ts)) if self._end_generation_ts else "--:--",
                "generation_duration_h": round(generation_time_h, 2),
                "battery_available_kwh": round(self.battery_soc / 100.0 * 9.6, 2) if self.inverter_type != "on-grid" else 0.0,
                "autonomy_hours": round(autonomy_h, 2),
            },
            "operation": {
                "operating_mode": operating_mode,
                "backup_mode_active": backup_mode_active,
                "grid_available": grid_available,
            },
        }
        if self.inverter_type != "off-grid":
            snapshot["grid"] = {
                "grid_voltage_v": round(grid_voltage, 1),
                "grid_current_a": round(grid_current, 2),
                "grid_status": grid_status,
                "frequency_hz": round(grid_freq, 2),
                "active_power_kw": round(ac_kw, 2),
                "apparent_power_kva": round(apparent_kw, 2),
            }
        if self.inverter_type != "on-grid":
            snapshot.update({
                "battery_soc_percent": round(self.battery_soc, 1),
                "battery_voltage_v": round(battery_voltage, 1),
                "battery_current_a": round(battery_current_a, 2),
                "battery_power_kw": round(battery_power_kw, 2),
                "battery_mode": battery_mode,
                "autonomy_hours": round(autonomy_h, 2),
                "backup_mode_active": backup_mode_active,
                "operating_mode": operating_mode,
                "battery": {
                    "soc_percent": round(self.battery_soc, 1),
                    "voltage_v": round(battery_voltage, 1),
                    "current_a": round(battery_current_a, 2),
                    "power_kw": round(battery_power_kw, 2),
                    "mode": battery_mode,
                    "autonomy_hours": round(autonomy_h, 2),
                    "available_energy_kwh": round(self.battery_soc / 100.0 * 9.6, 2),
                },
            })
        self._cache = snapshot

    def read_register(self, register, number_of_decimals=0, signed=False):
        _ = (number_of_decimals, signed)
        self._tick()
        mapping = {
            0x0001: self._cache["potencia_instantanea_w"],
            0x0003: int(self._cache["tensao_dc_v"]),
            0x0006: int(self._cache["geracao_dia_kwh"] * 10),
            0x003B: int(self._cache["geracao_total_kwh"] * 10),
        }
        return mapping.get(register, 0)

    def snapshot_extras(self):
        return dict(self._cache)


class GrowattModbusReader:
    """Leitor Modbus RTU com fallback local para simulação técnica."""

    def __init__(self, port="COM3", slave_id=1, baudrate=9600, bytesize=8, parity="N", stopbits=1, timeout=0.4, instrument=None, memory_size=1024):
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
        return raw_value / 10.0 if register in (0x0006, 0x003B) else float(raw_value)

    def _estimated_extras(self, data):
        pv_kw = data["potencia_instantanea_w"] / 1000.0
        grid_voltage = 220.0
        load_kw = max(0.3, pv_kw * 0.8 + 0.4)
        export_kw = max(0.0, pv_kw - load_kw)
        import_kw = max(0.0, load_kw - pv_kw)
        ac_current = pv_kw * 1000 / grid_voltage if grid_voltage else 0.0
        return {
            "load_power_w": int(load_kw * 1000),
            "import_power_w": int(import_kw * 1000),
            "export_power_w": int(export_kw * 1000),
            "expected_generation_w": int(pv_kw * 1000),
            "temperature_c": 32.0,
            "weather_label": "não informado",
            "status_code": 1,
            "inverter_status": "Gerando",
            "communication_status": "Online",
            "grid_status": "Normal",
            "irradiance_wm2": 700,
            "dc_power_w": int(pv_kw * 1030),
            "ac_power_w": int(pv_kw * 1000),
            "simulation_scenario": "hardware",
            "manufacturer": "Growatt",
            "brand": "Growatt",
            "model": "SPH5000",
            "product_family": "hybrid",
            "firmware_version": "FW-1.0.9",
            "inverter_mode": "hybrid",
            "serial_number": "GHY123456789",
            "inverter_capabilities": ["solar", "battery", "grid_export", "backup"],
            "battery_soc_percent": 68.0,
            "battery_voltage_v": 51.2,
            "battery_current_a": -8.6,
            "battery_power_kw": -0.44,
            "battery_mode": "discharging",
            "autonomy_hours": 7.8,
            "backup_mode_active": False,
            "operating_mode": "grid_assist",
            "load_power_kw": round(load_kw, 2),
            "grid_available": True,
            "dc_input": {"mppt1_voltage_v": 320.0, "mppt1_current_a": 4.8, "mppt1_power_kw": round(pv_kw / 2, 2), "mppt2_voltage_v": 318.0, "mppt2_current_a": 4.7, "mppt2_power_kw": round(pv_kw / 2, 2), "dc_power_kw": round(pv_kw * 1.03, 2)},
            "ac_output": {"voltage_v": 220.0, "current_a": round(ac_current, 2), "power_kw": round(pv_kw, 2), "frequency_hz": 60.0, "power_factor": 0.98},
            "grid": {"grid_voltage_v": 220.0, "grid_current_a": round(ac_current, 2), "grid_status": "Normal", "frequency_hz": 60.0, "active_power_kw": round(pv_kw, 2), "apparent_power_kva": round(pv_kw / 0.98, 2)},
            "inverter": {"temperature_c": 32.0, "efficiency_percent": 96.0, "status": "Gerando", "communication_status": "Online", "operational_state": "Gerando"},
            "energy": {"today_kwh": data["geracao_dia_kwh"], "total_kwh": data["geracao_total_kwh"], "import_kwh": round(import_kw * 0.08, 3), "export_kwh": round(export_kw * 0.08, 3), "peak_power_kw": round(pv_kw, 2), "generation_start_time": "08:00", "generation_end_time": "17:40", "generation_duration_h": 9.67, "battery_available_kwh": 6.53, "autonomy_hours": 7.8},
            "battery": {"soc_percent": 68.0, "voltage_v": 51.2, "current_a": -8.6, "power_kw": -0.44, "mode": "discharging", "autonomy_hours": 7.8, "available_energy_kwh": 6.53},
            "operation": {"operating_mode": "grid_assist", "backup_mode_active": False, "grid_available": True},
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
