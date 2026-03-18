"""Entrypoint do CleanSun para MicroPython e CPython."""
import sys
import time

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio

from data_processor import DataProcessor
from http_server import CleanSunHTTPServer
from modbus_reader import GrowattModbusReader

POLL_SECONDS = 5


async def poll_loop(reader, processor):
    while True:
        try:
            processor.ingest_snapshot(reader.read_all())
        except Exception as exc:
            processor.register_fault("Falha na leitura do inversor", str(exc))
        await asyncio.sleep(POLL_SECONDS)


async def bootstrap():
    processor = DataProcessor("config.json", "history.csv")
    reader = GrowattModbusReader()
    server = CleanSunHTTPServer(processor)
    await server.start()
    await poll_loop(reader, processor)


def run():
    start = int(time.time() * 1000)
    asyncio.run(bootstrap())
    elapsed = int(time.time() * 1000) - start
    if elapsed > 10000:
        print("[WARN] Boot excedeu 10s:", elapsed)


if __name__ == "__main__":
    run()
