"""CleanSun main loop for MicroPython 1.21+ on ESP32/ESP8266."""
import time
try:
    import uasyncio as asyncio
except ImportError:  # fallback for desktop tests
    import asyncio

from modbus_reader import GrowattModbusReader
from data_processor import DataProcessor
from http_server import CleanSunHTTPServer

POLL_SECONDS = 5


async def poll_loop(reader, processor):
    while True:
        try:
            snapshot = reader.read_all()
            processor.ingest_snapshot(snapshot)
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
    start = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
    asyncio.run(bootstrap())
    elapsed = (time.ticks_ms() - start) if hasattr(time, "ticks_ms") else int(time.time() * 1000) - start
    if elapsed > 10000:
        print("[WARN] Boot excedeu 10s:", elapsed)


if __name__ == "__main__":
    run()
