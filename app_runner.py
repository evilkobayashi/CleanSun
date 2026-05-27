"""Helpers para iniciar o CleanSun com DeyeSolarmanReader."""
import json
import sys
import time

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio

from data_processor import DataProcessor
from http_server import CleanSunHTTPServer
from solarman_reader import DeyeSolarmanReader

POLL_SECONDS = 5


async def poll_loop(reader, processor, poll_seconds=POLL_SECONDS):
    while True:
        try:
            processor.ingest_snapshot(reader.read_all())
        except Exception as exc:
            processor.register_fault("Falha na leitura do inversor", str(exc))
        await asyncio.sleep(poll_seconds)


async def bootstrap(config_path="config.json", history_path="history.csv",
                    host="0.0.0.0", port=80):
    processor = DataProcessor(config_path, history_path)
    solarman_cfg = processor.config.get("solarman", {})
    if not solarman_cfg.get("datalogger_ip"):
        raise RuntimeError(
            "config.json missing solarman.datalogger_ip — "
            "set the IP address of your SOLARMAN Wi-Fi datalogger"
        )
    reader = DeyeSolarmanReader(solarman_cfg)
    server = CleanSunHTTPServer(processor, host=host, port=port)
    await server.start()
    await poll_loop(reader, processor)


def run_app(config_path="config.json", history_path="history.csv",
            host="0.0.0.0", port=80):
    start = int(time.time() * 1000)
    try:
        asyncio.run(bootstrap(config_path=config_path,
                               history_path=history_path,
                               host=host, port=port))
    except KeyboardInterrupt:
        pass
    elapsed = int(time.time() * 1000) - start
    if elapsed > 10000:
        print("[WARN] Boot excedeu 10s:", elapsed)
