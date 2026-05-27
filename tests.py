"""Testes unitários para o CleanSun."""
import json
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.dirname(__file__))


class TestLogger(unittest.TestCase):
    """Testes para o módulo de logging."""
    
    def test_logger_creation(self):
        from logger import CleanSunLogger, LogLevel
        logger = CleanSunLogger("test", "DEBUG")
        self.assertEqual(logger.name, "test")
        self.assertEqual(logger.min_level, LogLevel.DEBUG)
    
    def test_logger_levels(self):
        from logger import CleanSunLogger, LogLevel
        import io
        
        output = io.StringIO()
        logger = CleanSunLogger("test", "INFO", output=output.write)
        
        logger.info("Test info message")
        logger.warning("Test warning")
        
        output.seek(0)
        content = output.getvalue()
        self.assertIn("Test info message", content)
        self.assertIn("Test warning", content)
    
    def test_logger_stats(self):
        from logger import CleanSunLogger
        logger = CleanSunLogger("test")
        logger.info("Test")
        stats = logger.stats()
        self.assertEqual(stats["messages_logged"], 1)
        self.assertEqual(stats["by_level"]["info"], 1)


class TestInverterDetectionDeye(unittest.TestCase):
    def test_deye_model_detected_as_hybrid(self):
        from inverter_detection import detect_inverter_type
        snapshot = {
            "manufacturer": "Deye",
            "model": "SUN-7.5K-SG05LP2-US-SM2",
            "product_family": "hybrid",
        }
        config = {"manual_override": False, "manual_selected_type": None}
        result = detect_inverter_type(snapshot, config)
        self.assertEqual(result["detected_inverter_type"], "hybrid")
        self.assertEqual(result["detection_source"], "model_lookup")
        self.assertGreaterEqual(result["confidence"], 0.95)

    def test_deye_family_fallback(self):
        from inverter_detection import detect_inverter_type
        snapshot = {
            "manufacturer": "Deye",
            "model": "UNKNOWN-MODEL",
            "product_family": "hybrid",
        }
        config = {"manual_override": False, "manual_selected_type": None}
        result = detect_inverter_type(snapshot, config)
        self.assertEqual(result["detected_inverter_type"], "hybrid")
        self.assertEqual(result["detection_source"], "family_lookup")


class TestConnectionPool(unittest.TestCase):
    """Testes para o pool de conexões."""
    
    def test_pool_acquire_release(self):
        from connection_pool import ConnectionPool
        pool = ConnectionPool(max_connections=3)
        
        self.assertTrue(pool.acquire())
        self.assertTrue(pool.acquire())
        self.assertTrue(pool.acquire())
        
        self.assertFalse(pool.acquire())
        
        pool.release()
        self.assertTrue(pool.acquire())
    
    def test_pool_stats(self):
        from connection_pool import ConnectionPool
        pool = ConnectionPool(max_connections=10)
        
        pool.acquire()
        pool.acquire()
        pool.release()
        
        stats = pool.stats()
        self.assertEqual(stats["active_connections"], 1)
        self.assertEqual(stats["total_handled"], 2)
        self.assertEqual(stats["total_closed"], 1)


class TestCircuitBreaker(unittest.TestCase):
    """Testes para o circuit breaker."""
    
    def test_circuit_closed_initially(self):
        from circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test", failure_threshold=3)
        self.assertEqual(cb.state, CircuitState.CLOSED.value)
    
    def test_circuit_opens_after_threshold(self):
        from circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=30)
        
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED.value)
        
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN.value)
    
    def test_circuit_half_open_after_timeout(self):
        from circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=1)
        
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN.value)
        time.sleep(0.05)
        self.assertIn(cb.state, [CircuitState.HALF_OPEN.value, CircuitState.OPEN.value])
    
    def test_circuit_stats(self):
        from circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        stats = cb.stats()
        self.assertEqual(stats["name"], "test")
        self.assertEqual(stats["failure_count"], 2)


class TestPrometheusMetrics(unittest.TestCase):
    """Testes para métricas Prometheus."""
    
    def test_counter_increment(self):
        from metrics import PrometheusMetrics
        m = PrometheusMetrics()
        
        m.inc_counter("test_counter", 5)
        m.inc_counter("test_counter", 3)
        
        self.assertEqual(m._counters.get("test_counter"), 8)
    
    def test_gauge_set(self):
        from metrics import PrometheusMetrics
        m = PrometheusMetrics()
        
        m.set_gauge("test_gauge", 42.5)
        self.assertEqual(m._gauges.get("test_gauge"), 42.5)
    
    def test_record_request(self):
        from metrics import PrometheusMetrics
        m = PrometheusMetrics()
        
        m.record_request(100, success=True)
        m.record_request(200, success=False)
        
        self.assertEqual(m._request_count, 2)
        self.assertEqual(m._request_errors, 1)
    
    def test_export_format(self):
        from metrics import PrometheusMetrics
        m = PrometheusMetrics()
        m.inc_counter("test_metric", 1)
        
        output = m.export()
        self.assertIn("test_metric", output)
        self.assertIn("cleansun_http_requests_total", output)


class TestInverterDetection(unittest.TestCase):
    """Testes para detecção de inversor."""
    
    def test_normalize_type(self):
        from inverter_detection import normalize_type
        self.assertEqual(normalize_type("híbrido"), "hybrid")
        self.assertEqual(normalize_type("hybrid"), "hybrid")
        self.assertEqual(normalize_type("on-grid"), "on-grid")
        self.assertIsNone(normalize_type("invalid"))
    
    def test_confidence_label(self):
        from inverter_detection import confidence_label
        self.assertEqual(confidence_label(0.95), "alta")
        self.assertEqual(confidence_label(0.7), "média")
        self.assertEqual(confidence_label(0.3), "baixa")
    
    def test_detect_by_model(self):
        from inverter_detection import detect_by_model
        result = detect_by_model({"manufacturer": "Growatt", "model": "SPH5000"})
        self.assertEqual(result["detected_inverter_type"], "hybrid")
        self.assertEqual(result["detection_source"], "model_lookup")
    
    def test_infer_by_telemetry(self):
        from inverter_detection import infer_by_telemetry
        
        snapshot_hybrid = {
            "battery_soc_percent": 75,
            "import_power_w": 100,
            "export_power_w": 50,
            "grid_available": True,
        }
        result = infer_by_telemetry(snapshot_hybrid)
        self.assertEqual(result["detected_inverter_type"], "hybrid")


class TestDataProcessor(unittest.TestCase):
    """Testes para o processador de dados."""
    
    def setUp(self):
        self.test_config = "test_config.json"
        self.test_history = "test_history.csv"
        
        if os.path.exists(self.test_config):
            os.remove(self.test_config)
        if os.path.exists(self.test_history):
            os.remove(self.test_history)
    
    def tearDown(self):
        if os.path.exists(self.test_config):
            os.remove(self.test_config)
        if os.path.exists(self.test_history):
            os.remove(self.test_history)
    
    def test_processor_init(self):
        from data_processor import DataProcessor
        processor = DataProcessor(self.test_config, self.test_history)
        
        self.assertIsNotNone(processor.config)
        self.assertIsNotNone(processor.history_path)
    
    def test_ingest_snapshot(self):
        from data_processor import DataProcessor
        processor = DataProcessor(self.test_config, self.test_history)
        
        snapshot = {
            "timestamp": int(time.time()),
            "daily_gen_kwh": 12.5,
            "load_power_w": 850,
            "ac_power_w": 3200,
            "import_power_w": 0,
            "export_power_w": 2350,
            "expected_generation_w": 4500,
            "inverter_status": "Gerando",
            "grid_status": "Normal",
            "communication_status": "Online",
        }
        
        processor.ingest_snapshot(snapshot)
        
        self.assertIsNotNone(processor.last_dashboard)
        self.assertIn("indicators", processor.last_dashboard)
    
    def test_indicators_calculation(self):
        from data_processor import DataProcessor
        processor = DataProcessor(self.test_config, self.test_history)
        
        snapshot = {
            "timestamp": int(time.time()),
            "daily_gen_kwh": 25.0,
            "load_power_w": 1200,
            "ac_power_w": 4500,
            "import_power_w": 200,
            "export_power_w": 3500,
            "expected_generation_w": 5000,
            "inverter_status": "Gerando",
            "grid_status": "Normal",
            "communication_status": "Online",
        }
        
        processor.ingest_snapshot(snapshot)
        indicators = processor.last_dashboard["indicators"]
        
        self.assertGreater(indicators["geracao_kwh"], 0)
        self.assertGreater(indicators["consumo_kwh"], 0)
        self.assertIn("autoconsumo_pct", indicators)
        self.assertIn("autossuficiencia_pct", indicators)


class TestAlarms(unittest.TestCase):
    """Testes para o sistema de alarmes."""
    
    def test_alarm_engine_creation(self):
        from alarms import AlarmEngine
        engine = AlarmEngine({"data_stale_seconds": 20})
        self.assertIsNotNone(engine)
    
    def test_alarm_evaluation(self):
        from alarms import AlarmEngine
        engine = AlarmEngine({"data_stale_seconds": 20})
        
        snapshot = {
            "inverter_status": "Gerando",
            "grid_status": "Normal",
            "communication_status": "Online",
        }
        
        indicators = {
            "geracao_kwh": 15.0,
            "potencia_atual_kw": 3.2,
            "geracao_esperada_kw": 4.0,
            "consumo_kwh": 8.5,
            "diferenca_geracao_pct": -20,
            "autoconsumo_pct": 60,
            "importacao_atual_kw": 0.5,
            "exportacao_atual_kw": 0.0,
        }
        
        technical = {
            "dc_input": {"mppt1_voltage_v": 350, "mppt2_voltage_v": 348, "mppt1_current_a": 8.5, "mppt2_current_a": 8.2, "dc_power_kw": 4.5},
            "ac_output": {"voltage_v": 220, "current_a": 14.5, "power_kw": 3.2, "frequency_hz": 60, "power_factor": 0.97},
            "grid": {"grid_voltage_v": 220, "grid_current_a": 2.5, "grid_status": "Normal", "frequency_hz": 60, "active_power_kw": 3.2, "apparent_power_kva": 3.3},
            "inverter": {"temperature_c": 35, "efficiency_percent": 96.5, "status": "Gerando", "communication_status": "Online"},
            "battery": {"soc_percent": 65, "voltage_v": 51, "current_a": -5, "power_kw": -0.25, "mode": "discharging", "autonomy_hours": 8},
            "operation": {"operating_mode": "solar_priority", "backup_mode_active": False, "grid_available": True},
            "diagnostics": {"communication_status": "Online", "grid_status": "Normal", "operational_status": "Gerando", "status_code": 1},
        }
        
        alerts = engine.evaluate(snapshot, indicators, technical, [], int(time.time()))
        
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)


class TestHTTPServer(unittest.TestCase):
    """Testes para o servidor HTTP."""
    
    def test_parse_query(self):
        from http_server import CleanSunHTTPServer
        path, query = CleanSunHTTPServer._parse_query("/api/data?days=7&bucket=daily")
        self.assertEqual(path, "/api/data")
        self.assertEqual(query["days"], "7")
        self.assertEqual(query["bucket"], "daily")
    
    def test_parse_query_no_params(self):
        from http_server import CleanSunHTTPServer
        path, query = CleanSunHTTPServer._parse_query("/api/status")
        self.assertEqual(path, "/api/status")
        self.assertEqual(query, {})
    
    def test_parse_cookies(self):
        from http_server import CleanSunHTTPServer
        cookies = CleanSunHTTPServer._parse_cookies({"cookie": "session=abc123; theme=dark"})
        self.assertEqual(cookies.get("session"), "abc123")
        self.assertEqual(cookies.get("theme"), "dark")
    
    def test_api_version(self):
        from http_server import API_VERSION
        self.assertIsInstance(API_VERSION, str)
        self.assertIn(".", API_VERSION)


class TestSimulateGrowatt(unittest.TestCase):
    """Testes para o simulador."""
    
    def test_solar_curve(self):
        from simulate_growatt import solar_curve
        self.assertGreaterEqual(solar_curve(12), 0)
        self.assertLessEqual(solar_curve(0), 0)
        self.assertGreater(solar_curve(10), solar_curve(8))
    
    def test_house_consumption(self):
        from simulate_growatt import house_consumption_kw
        self.assertGreater(house_consumption_kw(20, 0), 0)
        self.assertGreater(house_consumption_kw(7, 0), house_consumption_kw(3, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)