"""Simulador Growatt com histórico retroativo e modo contínuo."""
import argparse
import csv
import json
import math
import os
import random
import socket
import struct
import time

DEFAULT_CONFIG = {
    "days": 7,
    "interval_minutes": 15,
    "tarifa_kwh": 0.92,
    "continuous": False,
    "overwrite": False,
    "port": 1502,
    "host": "0.0.0.0",
    "weather": "auto",
    "system_kwp": 5.0,
    "history_file": "history.csv",
    "scenario": "auto",
    "random_fault_rate": 0.05,
    "inverter_type": "hybrid",
}

HISTORY_FIELDS = [
    "timestamp", "geracao_kwh", "consumo_kwh", "exportado_kwh", "solar_generation_kwh", "house_consumption_kwh",
    "grid_import_kwh", "grid_export_kwh", "self_consumption_kwh", "estimated_savings_brl", "weather_condition", "expected_generation_kwh",
]
REGISTER_MAP = {0x0001: 0, 0x0003: 0, 0x0006: 0, 0x003B: 25000}
WEATHER_GAIN = {"ensolarado": 1.0, "parcialmente_nublado": 0.76, "nublado": 0.52}
SCENARIOS = ["auto", "normal", "sombreamento", "dc_subtensao", "dc_sobretensao", "desbalanceamento_mppt", "sobretensao_rede", "sem_geracao_dia", "temperatura_alta", "falha_comunicacao"]
INVERTER_METADATA = {"on-grid": {"manufacturer": "Growatt", "model": "MIN 5000TL-X", "serial_prefix": "GRT", "product_family": "grid_tie"}, "off-grid": {"manufacturer": "Growatt", "model": "SPF 5000 ES", "serial_prefix": "GOF", "product_family": "off_grid"}, "hybrid": {"manufacturer": "Growatt", "model": "SPH5000", "serial_prefix": "GHY", "product_family": "hybrid"}}


def inverter_metadata(inverter_type):
    meta=dict(INVERTER_METADATA.get(inverter_type, INVERTER_METADATA["hybrid"]))
    meta["serial_number"]=meta["serial_prefix"]+"123456789"
    return meta

def load_runtime_config(config_path="config.json"):
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        config["tarifa_kwh"] = loaded.get("tarifa_kwh", config["tarifa_kwh"])
        config["system_kwp"] = loaded.get("potencia_sistema_kwp", config["system_kwp"])
        config["random_fault_rate"] = loaded.get("simulation_random_fault_rate", config["random_fault_rate"])
        config["inverter_type"] = loaded.get("inverter_type", config["inverter_type"])
    return config


def generate_timestamps(days, interval_minutes, end_ts=None):
    end_ts = int(end_ts or time.time())
    step = interval_minutes * 60
    start_ts = end_ts - days * 86400
    return list(range(start_ts, end_ts + 1, step))


def pick_weather_for_day(day_seed, forced="auto"):
    if forced != "auto":
        return forced
    random.seed(day_seed)
    roll = random.random()
    if roll < 0.45:
        return "ensolarado"
    if roll < 0.82:
        return "parcialmente_nublado"
    return "nublado"


def pick_scenario(day_seed, forced="auto", random_fault_rate=0.05):
    if forced != "auto":
        return forced
    random.seed(day_seed * 31)
    return random.choice(SCENARIOS[2:]) if random.random() < random_fault_rate else "normal"


def solar_curve(hour_float):
    return max(0.0, math.sin((hour_float - 6.0) / 12.0 * math.pi))


def expected_generation_kw(hour_float, system_kwp):
    return system_kwp * solar_curve(hour_float)


def actual_generation_kw(hour_float, weather, system_kwp, daily_factor, scenario):
    base = expected_generation_kw(hour_float, system_kwp)
    weather_gain = WEATHER_GAIN.get(weather, 0.76)
    noise = random.uniform(-0.06, 0.06)
    value = max(0.0, base * weather_gain * daily_factor * (1.0 + noise))
    if scenario == "sombreamento":
        value *= 0.55
    elif scenario == "sem_geracao_dia" and 8 <= hour_float <= 15:
        value = 0.0
    elif scenario == "temperatura_alta":
        value *= 0.92
    return value


def house_consumption_kw(hour_float, weekday):
    base = 0.28 if hour_float < 5 else 0.42
    if 6 <= hour_float <= 8.5:
        base += 0.55
    elif 11.5 <= hour_float <= 13.5:
        base += 0.25
    elif 18 <= hour_float <= 22.5:
        base += 1.15
    elif 23 <= hour_float <= 24:
        base += 0.22
    if weekday >= 5:
        base += 0.18
    return max(0.18, base + random.uniform(-0.10, 0.16))


def build_record(ts, interval_minutes, weather, tariff_kwh, system_kwp, total_generation_kwh, scenario):
    lt = time.localtime(ts)
    hour_float = lt.tm_hour + lt.tm_min / 60.0
    weekday = lt.tm_wday
    day_factor = 0.96 + random.uniform(-0.05, 0.05)
    expected_kw = expected_generation_kw(hour_float, system_kwp)
    generation_kw = actual_generation_kw(hour_float, weather, system_kwp, day_factor, scenario)
    consumption_kw = house_consumption_kw(hour_float, weekday)
    interval_h = interval_minutes / 60.0
    generation_kwh = generation_kw * interval_h
    consumption_kwh = consumption_kw * interval_h
    self_consumption_kwh = min(generation_kwh, consumption_kwh)
    grid_export_kwh = max(0.0, generation_kwh - consumption_kwh)
    grid_import_kwh = max(0.0, consumption_kwh - generation_kwh)
    expected_generation_kwh = expected_kw * interval_h
    savings = self_consumption_kwh * tariff_kwh
    total_generation_kwh += generation_kwh
    dc_voltage = 180 + 220 * solar_curve(hour_float)
    if scenario == "dc_subtensao":
        dc_voltage = 145
    elif scenario == "dc_sobretensao":
        dc_voltage = 490
    REGISTER_MAP[0x0001] = int(generation_kw * 1000)
    REGISTER_MAP[0x0003] = int(dc_voltage)
    REGISTER_MAP[0x0006] = int(total_generation_kwh * 10)
    REGISTER_MAP[0x003B] += int(generation_kwh * 10)
    record = {
        "timestamp": int(ts),
        "geracao_kwh": round(generation_kwh, 4),
        "consumo_kwh": round(consumption_kwh, 4),
        "exportado_kwh": round(grid_export_kwh, 4),
        "solar_generation_kwh": round(generation_kwh, 4),
        "house_consumption_kwh": round(consumption_kwh, 4),
        "grid_import_kwh": round(grid_import_kwh, 4),
        "grid_export_kwh": round(grid_export_kwh, 4),
        "self_consumption_kwh": round(self_consumption_kwh, 4),
        "estimated_savings_brl": round(savings, 4),
        "weather_condition": weather if scenario == "normal" else f"{weather}:{scenario}",
        "expected_generation_kwh": round(expected_generation_kwh, 4),
    }
    return record, total_generation_kwh


def write_history(records, history_file, overwrite=False):
    mode = "w" if overwrite or not os.path.exists(history_file) else "a"
    write_header = mode == "w" or os.path.getsize(history_file) == 0
    with open(history_file, mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if write_header:
            writer.writeheader()
        for record in records:
            writer.writerow(record)


def generate_history(days, interval_minutes, tariff_kwh, system_kwp, weather_mode="auto", scenario="auto", random_fault_rate=0.05, inverter_type="hybrid", end_ts=None):
    timestamps = generate_timestamps(days, interval_minutes, end_ts=end_ts)
    daily_weather, daily_scenario, records, total_generation = {}, {}, [], 0.0
    for ts in timestamps:
        lt = time.localtime(ts)
        day_key = (lt.tm_year, lt.tm_mon, lt.tm_mday)
        if day_key not in daily_weather:
            daily_weather[day_key] = pick_weather_for_day(sum(day_key), weather_mode)
            daily_scenario[day_key] = pick_scenario(sum(day_key), scenario, random_fault_rate=random_fault_rate)
        record, total_generation = build_record(ts, interval_minutes, daily_weather[day_key], tariff_kwh, system_kwp, total_generation, daily_scenario[day_key])
        records.append(record)
    return records, total_generation, inverter_metadata(inverter_type)


class ContinuousSimulator:
    def __init__(self, host, port, interval_minutes, tariff_kwh, system_kwp, weather_mode, history_file, start_total, scenario, random_fault_rate):
        self.host = host
        self.port = port
        self.interval_minutes = interval_minutes
        self.tariff_kwh = tariff_kwh
        self.system_kwp = system_kwp
        self.weather_mode = weather_mode
        self.history_file = history_file
        self.total_generation = start_total
        self.scenario = scenario
        self.random_fault_rate = random_fault_rate
        self.current_weather = pick_weather_for_day(int(time.time()) // 86400, self.weather_mode)
        self.current_scenario = pick_scenario(int(time.time()) // 86400, self.scenario, self.random_fault_rate)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.sock.settimeout(1)

    def _refresh_context(self, ts):
        day_seed = int(ts) // 86400
        self.current_weather = pick_weather_for_day(day_seed, self.weather_mode)
        self.current_scenario = pick_scenario(day_seed, self.scenario, self.random_fault_rate)

    def _append_current_record(self):
        ts = int(time.time())
        self._refresh_context(ts)
        record, self.total_generation = build_record(ts, self.interval_minutes, self.current_weather, self.tariff_kwh, self.system_kwp, self.total_generation, self.current_scenario)
        write_history([record], self.history_file, overwrite=False)
        print("[contínuo] ts={ts} clima={weather} cenário={scenario} geração={gen:.3f}kWh consumo={cons:.3f}kWh".format(ts=record["timestamp"], weather=self.current_weather, scenario=self.current_scenario, gen=record["solar_generation_kwh"], cons=record["house_consumption_kwh"]))

    def _handle_modbus(self):
        try:
            conn, _addr = self.sock.accept()
        except socket.timeout:
            return
        with conn:
            req = conn.recv(260)
            if len(req) < 12:
                return
            tx_id, proto_id, _length, unit_id, func, start, qty = struct.unpack(">HHHBBHH", req[:12])
            if proto_id != 0 or func != 3:
                return
            words = [REGISTER_MAP.get(start + i, 0) & 0xFFFF for i in range(qty)]
            payload = b"".join(struct.pack(">H", w) for w in words)
            pdu = struct.pack(">BBB", unit_id, func, len(payload)) + payload
            mbap = struct.pack(">HHH", tx_id, 0, len(pdu))
            conn.sendall(mbap + pdu)

    def run(self):
        print("Modo contínuo ativo em {}:{}".format(self.host, self.port))
        next_tick = 0.0
        while True:
            now = time.time()
            if now >= next_tick:
                self._append_current_record()
                next_tick = now + self.interval_minutes * 60
            self._handle_modbus()


def parse_args():
    config = load_runtime_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, choices=[7, 30, 90], default=config["days"])
    parser.add_argument("--interval-minutes", type=int, default=config["interval_minutes"])
    parser.add_argument("--tariff", type=float, default=config["tarifa_kwh"])
    parser.add_argument("--continuous", action="store_true", default=config["continuous"])
    parser.add_argument("--overwrite", action="store_true", default=config["overwrite"])
    parser.add_argument("--weather", choices=["auto", "ensolarado", "parcialmente_nublado", "nublado"], default=config["weather"])
    parser.add_argument("--scenario", choices=SCENARIOS, default=config["scenario"])
    parser.add_argument("--random-fault-rate", type=float, default=config["random_fault_rate"])
    parser.add_argument("--inverter-type", choices=["on-grid", "off-grid", "hybrid"], default=config["inverter_type"])
    parser.add_argument("--host", default=config["host"])
    parser.add_argument("--port", type=int, default=config["port"])
    parser.add_argument("--history-file", default=config["history_file"])
    parser.add_argument("--system-kwp", type=float, default=config["system_kwp"])
    return parser.parse_args()


def main():
    args = parse_args()
    records, total_generation, metadata = generate_history(days=args.days, interval_minutes=args.interval_minutes, tariff_kwh=args.tariff, system_kwp=args.system_kwp, weather_mode=args.weather, scenario=args.scenario, random_fault_rate=args.random_fault_rate, inverter_type=args.inverter_type)
    write_history(records, args.history_file, overwrite=args.overwrite)
    print("Histórico gerado: {days} dias, {count} registros, intervalo de {interval} min em {file} | inversor={model} serial={serial}".format(days=args.days, count=len(records), interval=args.interval_minutes, file=args.history_file, model=metadata["model"], serial=metadata["serial_number"]))
    if args.continuous:
        ContinuousSimulator(host=args.host, port=args.port, interval_minutes=args.interval_minutes, tariff_kwh=args.tariff, system_kwp=args.system_kwp, weather_mode=args.weather, history_file=args.history_file, start_total=total_generation, scenario=args.scenario, random_fault_rate=args.random_fault_rate).run()


if __name__ == "__main__":
    main()
