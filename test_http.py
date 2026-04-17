"""Script de teste do servidor HTTP."""
import asyncio
import sys

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio


async def main():
    from data_processor import DataProcessor
    from http_server import CleanSunHTTPServer
    from modbus_reader import GrowattModbusReader, _FallbackInstrument

    processor = DataProcessor("config.json", "history.csv")
    instrument = _FallbackInstrument(
        weather="parcialmente nublado",
        kwp=5.0,
        inverter_type="hybrid"
    )
    reader = GrowattModbusReader(instrument=instrument)
    server = CleanSunHTTPServer(processor, host="127.0.0.1", port=8080)

    print("Iniciando servidor em 127.0.0.1:8080...")
    await server.start()
    print("Servidor iniciado!")

    try:
        await asyncio.sleep(2)
    except KeyboardInterrupt:
        pass

    snapshot = reader.read_all()
    processor.ingest_snapshot(snapshot)

    print("\nTestando endpoints:")
    print(f"  Status: {processor.status().get('operational_state')}")
    print(f"  Health: {server._health_check().get('status')}")
    print(f"  API Version: {server._serve_metrics().get('api_version')}")

    print("\nServidor funcionando com sucesso!")


if __name__ == "__main__":
    asyncio.run(main())