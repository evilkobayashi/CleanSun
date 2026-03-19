"""Helpers para iniciar o CleanSun com perfis de simulação específicos."""
import json
import sys
import time

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio

from data_processor import DataProcessor
from http_server import CleanSunHTTPServer
from modbus_reader import GrowattModbusReader, _FallbackInstrument

POLL_SECONDS = 5

PROFILE_OVERRIDES = {
    "on-grid": {
        "nome_instalacao": "Residência On-grid",
        "manual_override": False,
        "manual_selected_type": None,
        "detected_inverter_type": None,
        "detection_source": "unknown",
        "detection_confidence": 0.0,
    },
    "off-grid": {
        "nome_instalacao": "Residência Off-grid",
        "manual_override": False,
        "manual_selected_type": None,
        "detected_inverter_type": None,
        "detection_source": "unknown",
        "detection_confidence": 0.0,
    },
    "hybrid": {
        "nome_instalacao": "Residência Híbrida",
        "manual_override": False,
        "manual_selected_type": None,
        "detected_inverter_type": None,
        "detection_source": "unknown",
        "detection_confidence": 0.0,
    },
}


def write_profile_config(config_path, inverter_type):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config.update(PROFILE_OVERRIDES.get(inverter_type, {}))
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")


async def poll_loop(reader, processor, poll_seconds=POLL_SECONDS):
    while True:
        try:
            processor.ingest_snapshot(reader.read_all())
        except Exception as exc:
            processor.register_fault("Falha na leitura do inversor", str(exc))
        await asyncio.sleep(poll_seconds)


async def bootstrap(config_path="config.json", history_path="history.csv", inverter_type=None, host="0.0.0.0", port=80):
    processor = DataProcessor(config_path, history_path)
    config_inverter_type = inverter_type or processor.config.get("simulation_inverter_type") or "hybrid"
    processor.config["simulation_inverter_type"] = config_inverter_type
    processor._write_json(processor.config_path, processor.config)
    instrument = _FallbackInstrument(
        weather=processor.config.get("weather_mode", "parcialmente nublado"),
        kwp=float(processor.config.get("potencia_sistema_kwp", 5.0)),
        scenario=processor.config.get("simulation_scenario", "auto"),
        random_fault_rate=float(processor.config.get("simulation_random_fault_rate", 0.04)),
        inverter_type=config_inverter_type,
    )
    reader = GrowattModbusReader(instrument=instrument)
    server = CleanSunHTTPServer(processor, host=host, port=port)
    await server.start()
    await poll_loop(reader, processor)


def run_app(config_path="config.json", history_path="history.csv", inverter_type=None, host="0.0.0.0", port=80):
    start = int(time.time() * 1000)
    if inverter_type:
        write_profile_config(config_path, inverter_type)
    asyncio.run(bootstrap(config_path=config_path, history_path=history_path, inverter_type=inverter_type, host=host, port=port))
    elapsed = int(time.time() * 1000) - start
    if elapsed > 10000:
        print("[WARN] Boot excedeu 10s:", elapsed)
