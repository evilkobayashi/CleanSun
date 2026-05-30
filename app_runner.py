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

POLL_SECONDS = 1.0  # local LAN polls ~0.3s; updates far faster than Solarman cloud (~300s)


CONFIG_REFRESH_EVERY = 300  # re-read static inverter settings every N polls


async def poll_loop(reader, processor, poll_seconds=POLL_SECONDS):
    # On CPython, run the blocking Modbus read in a thread so the asyncio event
    # loop stays free to serve HTTP/SSE while we wait on the datalogger socket.
    use_executor = sys.implementation.name != "micropython"
    loop = asyncio.get_event_loop() if use_executor else None

    async def _call(fn):
        if use_executor:
            return await loop.run_in_executor(None, fn)
        return fn()

    n = 0
    while True:
        try:
            snapshot = await _call(reader.read_all)
            processor.ingest_snapshot(snapshot)
            n += 1
            if n % CONFIG_REFRESH_EVERY == 0:
                try:
                    processor.set_inverter_config(await _call(reader.read_inverter_config))
                except Exception:
                    pass
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
    try:
        processor.set_inverter_config(reader.read_inverter_config())
    except Exception:
        pass  # config card will stay empty until first periodic refresh succeeds
    poll_seconds = float(solarman_cfg.get("poll_seconds", POLL_SECONDS))
    await poll_loop(reader, processor, poll_seconds=poll_seconds)


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
