"""CleanSun main loop — MicroPython 1.21+ no ESP32/ESP8266 e CPython (testes)."""
import time

try:
    import uasyncio as asyncio
    _MICROPYTHON = True
except ImportError:
    import asyncio
    _MICROPYTHON = False

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
    reader    = GrowattModbusReader()
    server    = CleanSunHTTPServer(processor)

    await server.start()

    # BUG CORRIGIDO: No MicroPython o paralelismo exige create_task explicito.
    # No CPython o server.start() ja registra a task internamente via ensure_future,
    # mas o poll_loop tambem precisa rodar como task para nao bloquear o servidor.
    if _MICROPYTHON:
        asyncio.create_task(poll_loop(reader, processor))
        # No MicroPython o event loop precisa de um loop infinito no bootstrap
        while True:
            await asyncio.sleep(60)
    else:
        await poll_loop(reader, processor)


def run():
    if hasattr(time, "ticks_ms"):
        start = time.ticks_ms()
    else:
        start = int(time.time() * 1000)

    asyncio.run(bootstrap())

    elapsed = (time.ticks_ms() - start) if hasattr(time, "ticks_ms") else int(time.time() * 1000) - start
    if elapsed > 10000:
        print("[WARN] Boot excedeu 10s:", elapsed)


if __name__ == "__main__":
    run()
