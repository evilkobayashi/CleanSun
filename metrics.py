"""Métricas no formato Prometheus para observabilidade do CleanSun."""
import time


class PrometheusMetrics:
    """Coletor de métricas Prometheus."""
    
    def __init__(self):
        self._counters = {}
        self._gauges = {}
        self._histograms = {}
        self._start_time = int(time.time())
        self._request_count = 0
        self._request_errors = 0
        self._bytes_sent = 0
        self._last_request_ts = 0
    
    def inc_counter(self, name, value=1, labels=None):
        """Incrementa um counter."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
    
    def set_gauge(self, name, value, labels=None):
        """Define um gauge."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
    
    def observe_histogram(self, name, value, labels=None):
        """Observa um valor em histograma."""
        key = self._make_key(name, labels)
        bucket = self._histograms.setdefault(key, {"values": [], "sum": 0, "count": 0})
        bucket["values"].append(value)
        bucket["sum"] += value
        bucket["count"] += 1
    
    @staticmethod
    def _make_key(name, labels):
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
        return f"{name}{{{label_str}}}"
    
    def record_request(self, duration_ms, success=True):
        """Registra uma requisição HTTP."""
        self._request_count += 1
        if not success:
            self._request_errors += 1
        self._last_request_ts = int(time.time())
        self.inc_counter("cleansun_http_requests_total", 1, {"status": "success" if success else "error"})
        self.observe_histogram("cleansun_http_request_duration_ms", duration_ms)
    
    def record_connection(self, status):
        """Registra status de conexão."""
        self.inc_counter("cleansun_connections_total", 1, {"status": status})
    
    def record_alert(self, severity, active=True):
        """Registra um alerta."""
        self.inc_counter("cleansun_alerts_total", 1, {"severity": severity, "active": str(active).lower()})
    
    def _format_counter(self, name, value, labels=None):
        key = self._make_key(name, labels)
        return f"# TYPE {name} counter\n{key} {value}\n"
    
    def _format_gauge(self, name, value, labels=None):
        key = self._make_key(name, labels)
        return f"# TYPE {name} gauge\n{key} {value}\n"
    
    def _format_histogram(self, name, bucket):
        key = name
        return f"# TYPE {name} histogram\n{key}_sum {bucket['sum']}\n{key}_count {bucket['count']}\n"
    
    def export(self):
        """Exporta métricas em formato Prometheus."""
        lines = []
        
        lines.append(f"# HELP cleansun_http_requests_total Total de requisições HTTP")
        lines.append(f"# TYPE cleansun_http_requests_total counter")
        lines.append(f"cleansun_http_requests_total {self._request_count}")
        
        lines.append(f"# HELP cleansun_http_request_errors_total Total de erros HTTP")
        lines.append(f"# TYPE cleansun_http_request_errors_total counter")
        lines.append(f"cleansun_http_request_errors_total {self._request_errors}")
        
        lines.append(f"# HELP cleansun_http_request_duration_ms Duração das requisições HTTP (ms)")
        lines.append(f"# TYPE cleansun_http_request_duration_ms histogram")
        for key, bucket in self._histograms.items():
            if "duration" in key:
                lines.append(f"{key}_sum {bucket['sum']}")
                lines.append(f"{key}_count {bucket['count']}")
        
        lines.append(f"# HELP cleansun_uptime_seconds Tempo de atividade do servidor")
        lines.append(f"# TYPE cleansun_uptime_seconds gauge")
        lines.append(f"cleansun_uptime_seconds {int(time.time()) - self._start_time}")
        
        lines.append(f"# HELP cleansun_last_request_timestamp Unix timestamp da última requisição")
        lines.append(f"# TYPE cleansun_last_request_timestamp gauge")
        lines.append(f"cleansun_last_request_timestamp {self._last_request_ts}")
        
        for key, value in self._gauges.items():
            lines.append(f"# TYPE {key} gauge")
            lines.append(f"{key} {value}")
        
        for key, value in self._counters.items():
            if "requests" not in key:
                lines.append(f"# TYPE {key} counter")
                lines.append(f"{key} {value}")
        
        return "\n".join(lines)
    
    def stats(self):
        """Retorna estatísticas简易."""
        return {
            "request_count": self._request_count,
            "request_errors": self._request_errors,
            "uptime_seconds": int(time.time()) - self._start_time,
            "last_request_ts": self._last_request_ts,
        }


DEFAULT_METRICS = PrometheusMetrics()