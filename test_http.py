"""Script de teste do servidor HTTP."""
import asyncio
import sys
from unittest.mock import MagicMock

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio


async def main():
    from data_processor import DataProcessor
    from http_server import CleanSunHTTPServer
    from solarman_reader import DeyeSolarmanReader

    processor = DataProcessor("config.json", "history.csv")

    solarman_cfg = {
        "datalogger_ip": "127.0.0.1",
        "datalogger_serial": 9999999999,
        "datalogger_port": 8899,
        "mb_slaveid": 1,
        "lan_fail_threshold": 3,
        "cloud_fallback": {"enabled": False},
    }
    reader = DeyeSolarmanReader(solarman_cfg)
    reader._lan.read_registers = MagicMock(return_value={
        "pv1_v_raw": 3500, "pv1_a_raw": 90, "pv2_v_raw": 3480, "pv2_a_raw": 85,
        "pv1_w_raw": 3150, "pv2_w_raw": 2960, "temp_raw": 420,
        "batt_v_raw": 510, "batt_soc_raw": 80, "batt_w_raw": 1000,
        "grid_w_raw": 64536, "grid_v_raw": 2200, "grid_hz_raw": 6000,
        "load_w_raw": 2100, "today_kwh_raw": 280, "total_kwh_raw": 4500,
    })

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
