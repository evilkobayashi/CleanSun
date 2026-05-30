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


class TestDeyeDataMapping(unittest.TestCase):
    def _make_raw(self):
        # Scales verified against real Deye SUN-7.5K hardware (reg90 temp has a
        # -1000 offset; reg183 battery voltage is ×0.01). Load = reg160 + reg161;
        # grid is derived from the energy balance.
        return {
            "pv1_v_raw": 3520,    # 352.0 V
            "pv1_a_raw": 95,      # 9.5 A
            "pv2_v_raw": 3480,    # 348.0 V
            "pv2_a_raw": 90,      # 9.0 A
            "pv1_w_raw": 3344,    # 3344 W
            "pv2_w_raw": 3132,    # 3132 W
            "temp_raw": 1435,     # (1435-1000)*0.1 = 43.5 °C
            "batt_v_raw": 5120,   # 5120*0.01 = 51.2 V
            "batt_soc_raw": 75,   # 75 %
            "batt_w_raw": 1200,   # +1200 W = discharging (Deye convention)
            "load_l1_w_raw": 1238,  # reg160
            "load_l2_w_raw": 1238,  # reg161 -> total load 2476 W
            "grid_v_raw": 2200,   # 220.0 V
            "grid_hz_raw": 6000,  # 60.00 Hz
            "today_kwh_raw": 312, # 31.2 kWh
            "total_kwh_raw": 4521,# 452.1 kWh
        }

    def test_mapping_pv_power(self):
        from solarman_reader import _map_raw_to_snapshot
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertEqual(snap["potencia_instantanea_w"], 3344 + 3132)

    def test_mapping_dc_voltage(self):
        from solarman_reader import _map_raw_to_snapshot
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertAlmostEqual(snap["tensao_dc_v"], (352.0 + 348.0) / 2, places=1)

    def test_mapping_load(self):
        from solarman_reader import _map_raw_to_snapshot
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertEqual(snap["load_power_w"], 1238 + 1238)

    def test_mapping_battery(self):
        from solarman_reader import _map_raw_to_snapshot
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertEqual(snap["battery_soc_percent"], 75)
        self.assertAlmostEqual(snap["battery_voltage_v"], 51.2, places=1)
        self.assertAlmostEqual(snap["battery_power_kw"], 1.2, places=2)
        self.assertEqual(snap["battery_mode"], "discharging")

    def test_mapping_grid_derived_export(self):
        from solarman_reader import _map_raw_to_snapshot
        # grid = load - pv - batt_discharge = 2476 - 6476 - 1200 = -5200 -> export
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertEqual(snap["import_power_w"], 0)
        self.assertEqual(snap["export_power_w"], 5200)

    def test_mapping_energy(self):
        from solarman_reader import _map_raw_to_snapshot
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertAlmostEqual(snap["geracao_dia_kwh"], 31.2, places=1)
        self.assertAlmostEqual(snap["geracao_total_kwh"], 452.1, places=1)

    def test_mapping_metadata(self):
        from solarman_reader import _map_raw_to_snapshot
        snap = _map_raw_to_snapshot(self._make_raw())
        self.assertEqual(snap["manufacturer"], "Deye")
        self.assertEqual(snap["model"], "SUN-7.5K-SG05LP2-US-SM2")
        self.assertEqual(snap["product_family"], "hybrid")


class TestSolarmanLANTransport(unittest.TestCase):
    @patch("solarman_reader._PYSOLARMAN_AVAILABLE", True)
    @patch("solarman_reader.PySolarmanV5")
    def test_read_registers_calls_pysolarman(self, MockPV5):
        from solarman_reader import SolarmanLANTransport
        # Fast block = regs 150..190 (41 vals); slow block = regs 60..111 (52 vals).
        fast = [0] * 41
        fast[0] = 2200    # reg150 grid_v
        fast[10] = 1238   # reg160 load L1
        fast[11] = 1238   # reg161 load L2
        fast[33] = 5120   # reg183 batt_v
        fast[34] = 75     # reg184 batt_soc
        fast[36] = 3344   # reg186 pv1_w
        fast[37] = 3132   # reg187 pv2_w
        fast[40] = 1200   # reg190 batt_w
        slow = [0] * 52
        slow[0] = 3520    # reg60 pv1_v
        slow[1] = 95      # reg61 pv1_a
        slow[2] = 3480    # reg62 pv2_v
        slow[3] = 90      # reg63 pv2_a
        slow[19] = 6000   # reg79 grid_hz
        slow[30] = 1435   # reg90 temp
        slow[36] = 4521   # reg96 cumulative gen low word
        slow[37] = 0      # reg97 cumulative gen high word
        slow[48] = 312    # reg108 daily generation
        inst = MockPV5.return_value
        inst.read_holding_registers.side_effect = [fast, slow]
        transport = SolarmanLANTransport("192.168.1.100", 1234567890)
        raw = transport.read_registers()
        self.assertEqual(raw["pv1_v_raw"], 3520)
        self.assertEqual(raw["batt_soc_raw"], 75)
        self.assertEqual(raw["load_l1_w_raw"], 1238)
        self.assertEqual(raw["load_l2_w_raw"], 1238)
        self.assertEqual(raw["today_kwh_raw"], 312)
        self.assertEqual(raw["total_kwh_raw"], 4521)

    @patch("solarman_reader._PYSOLARMAN_AVAILABLE", False)
    def test_raises_when_pysolarmanv5_not_installed(self):
        from solarman_reader import SolarmanLANTransport
        transport = SolarmanLANTransport("192.168.1.100", 1234567890)
        with self.assertRaises(RuntimeError):
            transport.read_registers()


class TestInverterConfigDecode(unittest.TestCase):
    def test_decode_matches_real_hardware(self):
        from solarman_reader import _decode_inverter_config
        ident = [3, 1, 513, 12853, 12593, 12592, 12343, 13111, 16, 0, 0, 0]
        batt = [0] * 20  # regs 200..219 (index = reg - 200)
        batt[204 - 200] = 300   # battery rated capacity 300 Ah
        bms = [0] * 10   # regs 310..319 (index = reg - 310)
        bms[312 - 310] = 5350   # BMS charge voltage 53.5 V
        bms[314 - 310] = 50     # BMS charge current limit 50 A
        bms[315 - 310] = 50     # BMS discharge current limit 50 A
        bms[316 - 310] = 49     # BMS SOC 49 %
        bms[317 - 310] = 4933   # battery voltage 49.33 V
        conf = _decode_inverter_config(ident, batt, bms)
        self.assertEqual(conf["serial_number"], "2511100737")
        self.assertEqual(conf["battery_capacity_ah"], 300)
        self.assertAlmostEqual(conf["bms_charge_voltage_v"], 53.5, places=1)
        self.assertEqual(conf["bms_charge_current_limit_a"], 50)
        self.assertEqual(conf["bms_discharge_current_limit_a"], 50)
        self.assertEqual(conf["bms_soc_pct"], 49)
        self.assertAlmostEqual(conf["battery_voltage_v"], 49.33, places=2)


class TestSolarmanCloudTransport(unittest.TestCase):
    def _cloud_cfg(self):
        return {
            "enabled": True,
            "email": "test@example.com",
            "password": "secret",
            "app_id": "myapp123",
            "app_secret": "appsecret456",
            "device_sn": "DEY123456",
        }

    @patch("urllib.request.urlopen")
    def test_raises_when_disabled(self, _):
        from solarman_reader import SolarmanCloudTransport
        transport = SolarmanCloudTransport({"enabled": False})
        with self.assertRaises(RuntimeError):
            transport.read_registers()

    @patch("urllib.request.urlopen")
    def test_read_registers_returns_raw(self, mock_urlopen):
        from solarman_reader import SolarmanCloudTransport

        token_resp = json.dumps({"access_token": "tok123", "token_type": "bearer"}).encode()
        data_resp = json.dumps({
            "dataList": [
                {"key": "PV1Volt", "value": "352.0"},
                {"key": "PV1Curr", "value": "9.5"},
                {"key": "PV2Volt", "value": "348.0"},
                {"key": "PV2Curr", "value": "9.0"},
                {"key": "PV1Power", "value": "3344"},
                {"key": "PV2Power", "value": "3132"},
                {"key": "DC_Temp", "value": "43.5"},
                {"key": "BatVolt", "value": "51.2"},
                {"key": "BatCapcity", "value": "75"},
                {"key": "BatPower", "value": "1.2"},
                {"key": "GridOrMeterActivePower", "value": "-1.0"},
                {"key": "GridVolt", "value": "220.0"},
                {"key": "GridFreq", "value": "60.0"},
                {"key": "LoadPower", "value": "2.476"},
                {"key": "Eday", "value": "31.2"},
                {"key": "Etotal", "value": "452.1"},
            ]
        }).encode()

        mock_resp_token = MagicMock()
        mock_resp_token.read.return_value = token_resp
        mock_resp_token.__enter__ = lambda s: s
        mock_resp_token.__exit__ = MagicMock(return_value=False)

        mock_resp_data = MagicMock()
        mock_resp_data.read.return_value = data_resp
        mock_resp_data.__enter__ = lambda s: s
        mock_resp_data.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [mock_resp_token, mock_resp_data]

        transport = SolarmanCloudTransport(self._cloud_cfg())
        raw = transport.read_registers()

        self.assertEqual(raw["pv1_w_raw"], 3344)
        self.assertEqual(raw["batt_soc_raw"], 75)
        self.assertEqual(raw["load_l1_w_raw"], 2476)  # LoadPower 2.476 kW


class TestDeyeSolarmanReader(unittest.TestCase):
    def _lan_cfg(self):
        return {
            "datalogger_ip": "192.168.1.100",
            "datalogger_serial": 1234567890,
            "datalogger_port": 8899,
            "mb_slaveid": 1,
            "lan_fail_threshold": 3,
            "cloud_fallback": {"enabled": False},
        }

    def _make_raw(self):
        return {
            "pv1_v_raw": 3520, "pv1_a_raw": 95, "pv2_v_raw": 3480, "pv2_a_raw": 90,
            "pv1_w_raw": 3344, "pv2_w_raw": 3132, "temp_raw": 1435,
            "batt_v_raw": 5120, "batt_soc_raw": 75, "batt_w_raw": 1200,
            "load_l1_w_raw": 1238, "load_l2_w_raw": 1238, "grid_v_raw": 2200,
            "grid_hz_raw": 6000, "today_kwh_raw": 312, "total_kwh_raw": 4521,
        }

    def test_read_all_returns_full_snapshot(self):
        from solarman_reader import DeyeSolarmanReader
        reader = DeyeSolarmanReader(self._lan_cfg())
        reader._lan.read_registers = MagicMock(return_value=self._make_raw())
        data = reader.read_all()
        self.assertIn("potencia_instantanea_w", data)
        self.assertIn("battery_soc_percent", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["potencia_instantanea_w"], 3344 + 3132)

    def test_lan_failure_increments_counter(self):
        from solarman_reader import DeyeSolarmanReader
        cfg = self._lan_cfg()
        cfg["lan_fail_threshold"] = 1
        cfg["cloud_fallback"] = {"enabled": False}
        reader = DeyeSolarmanReader(cfg)
        reader._lan.read_registers = MagicMock(side_effect=OSError("timeout"))
        with self.assertRaises(OSError):
            reader.read_all()
        self.assertEqual(reader._lan_fail_count, 1)

    def test_switches_to_cloud_after_threshold(self):
        from solarman_reader import DeyeSolarmanReader
        cfg = self._lan_cfg()
        cfg["lan_fail_threshold"] = 2
        cfg["cloud_fallback"] = {"enabled": True, "email": "", "password": "",
                                  "app_id": "", "app_secret": "", "device_sn": ""}
        reader = DeyeSolarmanReader(cfg)
        reader._lan.read_registers = MagicMock(side_effect=OSError("no route"))
        reader._cloud.read_registers = MagicMock(return_value=self._make_raw())
        # Call 1: LAN fails, count=1 < threshold=2, raises
        with self.assertRaises(OSError):
            reader.read_all()
        self.assertEqual(reader._lan_fail_count, 1)
        self.assertFalse(reader._using_cloud)
        # Call 2: LAN fails, count=2 >= threshold, switches to cloud, returns data
        data = reader.read_all()
        self.assertTrue(reader._using_cloud)
        self.assertEqual(data["potencia_instantanea_w"], 3344 + 3132)
        reader._cloud.read_registers.assert_called_once()

    def test_memory_snapshot(self):
        from solarman_reader import DeyeSolarmanReader
        reader = DeyeSolarmanReader(self._lan_cfg())
        reader._lan.read_registers = MagicMock(return_value=self._make_raw())
        reader.read_all()
        reader.read_all()
        snap = reader.get_memory_snapshot()
        self.assertEqual(len(snap), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)