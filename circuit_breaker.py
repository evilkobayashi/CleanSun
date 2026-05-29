"""Circuit breaker para resiliência do CleanSun."""
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker para proteção contra falhas em cascata."""
    
    def __init__(self, name, failure_threshold=5, success_threshold=2, 
                 timeout_seconds=30, half_open_max_calls=3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._opened_at = 0
        self._half_open_calls = 0
        self._total_opens = 0
        self._total_closes = 0
    
    @property
    def state(self):
        now = time.time()
        
        if self._state == CircuitState.OPEN:
            if self.timeout_seconds <= 0 or now - self._opened_at >= self.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        elif self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                self._opened_at = now
                self._state = CircuitState.OPEN
                self._total_opens += 1
        
        return self._state.value
    
    def can_execute(self):
        """Verifica se pode executar."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False
    
    def record_success(self):
        """Registra sucesso."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self._total_closes += 1
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0
    
    def record_failure(self):
        """Registra falha."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            self._opened_at = time.time()
            self._state = CircuitState.OPEN
            self._total_opens += 1
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.time()
                self._state = CircuitState.OPEN
                self._total_opens += 1
    
    def execute(self, func, *args, **kwargs):
        """Executa função com circuit breaker."""
        if not self.can_execute():
            raise CircuitBreakerOpenError(f"Circuit {self.name} is open")
        
        try:
            self._half_open_calls += 1
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise exc
    
    def stats(self):
        """Estatísticas do circuit breaker."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_opens": self._total_opens,
            "total_closes": self._total_closes,
            "last_failure_ts": self._last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Exceção quando circuit breaker está aberto."""
    pass


class CircuitBreakerManager:
    """Gerenciador de circuit breakers."""
    
    def __init__(self):
        self._breakers = {}
    
    def get_or_create(self, name, **kwargs):
        """Obtém ou cria um circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, **kwargs)
        return self._breakers[name]
    
    def stats(self):
        """Estatísticas de todos os breakers."""
        return {name: breaker.stats() for name, breaker in self._breakers.items()}


DEFAULT_CIRCUIT_BREAKER = CircuitBreakerManager()