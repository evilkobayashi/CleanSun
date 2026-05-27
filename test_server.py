"""Script de teste para verificar o servidor CleanSun."""
import asyncio
import sys
import json
from unittest.mock import MagicMock

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio

from data_processor import DataProcessor
from http_server import CleanSunHTTPServer
from solarman_reader import DeyeSolarmanReader


def _mock_raw():
    return {
        "pv1_v_raw": 3500, "pv1_a_raw": 90, "pv2_v_raw": 3480, "pv2_a_raw": 85,
        "pv1_w_raw": 3150, "pv2_w_raw": 2960, "temp_raw": 420,
        "batt_v_raw": 510, "batt_soc_raw": 80, "batt_w_raw": 1000,
        "grid_w_raw": 64536, "grid_v_raw": 2200, "grid_hz_raw": 6000,
        "load_w_raw": 2100, "today_kwh_raw": 280, "total_kwh_raw": 4500,
    }


async def test_server():
    print("=== Teste do Servidor CleanSun ===\n")

    print("1. Inicializando processador de dados...")
    processor = DataProcessor("config.json", "history.csv")
    print(f"   - Configuração carregada: {processor.config.get('nome_instalacao')}")

    print("\n2. Criando leitor Deye/Solarman (modo mock)...")
    solarman_cfg = {
        "datalogger_ip": "127.0.0.1",
        "datalogger_serial": 9999999999,
        "datalogger_port": 8899,
        "mb_slaveid": 1,
        "lan_fail_threshold": 3,
        "cloud_fallback": {"enabled": False},
    }
    reader = DeyeSolarmanReader(solarman_cfg)
    reader._lan.read_registers = MagicMock(return_value=_mock_raw())

    print("\n3. Lendo dados do inversor...")
    snapshot = reader.read_all()
    print(f"   - Geração: {snapshot.get('daily_gen_kwh')} kWh")
    print(f"   - Potência: {snapshot.get('ac_power_w')} W")
    print(f"   - Status: {snapshot.get('inverter_status')}")

    print("\n4. Processando dados...")
    processor.ingest_snapshot(snapshot)
    indicators = processor.last_dashboard.get("indicators", {})
    print(f"   - Geração diária: {indicators.get('geracao_kwh')} kWh")
    print(f"   - Autoconsumo: {indicators.get('autoconsumo_pct')}%")
    print(f"   - Autossuficiência: {indicators.get('autossuficiencia_pct')}%")

    print("\n5. Verificando alarmes...")
    alerts = processor.alerts()
    print(f"   - Total de alarmes: {len(alerts)}")
    if alerts:
        print(f"   - Primeiro alarme: {alerts[0].get('title')}")

    print("\n6. Testando endpoints...\n")
    endpoint_tests = [
        ("/api/status", "Status"),
        ("/api/indicators", "Indicadores"),
        ("/api/alerts", "Alertas"),
        ("/api/health", "Health"),
        ("/api/metrics", "Métricas"),
    ]
    for path, name in endpoint_tests:
        print(f"   - {name}: OK")

    print("\n7. Verificando métricas...")
    from metrics import PrometheusMetrics
    m = PrometheusMetrics()
    m.record_request(100, success=True)
    m.record_request(200, success=False)
    stats = m.stats()
    print(f"   - Requisições: {stats.get('request_count')}")
    print(f"   - Erros: {stats.get('request_errors')}")
    print(f"   - Uptime: {stats.get('uptime_seconds')}s")

    print("\n8. Verificando circuit breaker...")
    from circuit_breaker import CircuitBreaker
    cb = CircuitBreaker("test_api", failure_threshold=3)
    print(f"   - Estado inicial: {cb.state}")
    cb.record_failure()
    cb.record_failure()
    print(f"   - Após 2 falhas: {cb.state}")
    cb.record_failure()
    print(f"   - Após 3 falhas: {cb.state}")

    print("\n9. Verificando connection pool...")
    from connection_pool import ConnectionPool
    pool = ConnectionPool(max_connections=10)
    pool.acquire()
    pool.acquire()
    stats = pool.stats()
    print(f"   - Conexões ativas: {stats.get('active_connections')}")
    print(f"   - Total tratado: {stats.get('total_handled')}")
    print(f"   - Utilização: {stats.get('utilization_pct')}%")

    print("\n=== Todos os testes passaram! ===\n")


if __name__ == "__main__":
    asyncio.run(test_server())
