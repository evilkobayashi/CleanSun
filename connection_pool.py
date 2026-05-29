"""Connection pool para gerenciar conexões TCP de entrada."""
import asyncio
import time
from collections import deque


class ConnectionPool:
    """Pool de conexões TCP inbound com limite e recycle."""
    
    def __init__(self, max_connections=50, max_idle_seconds=60):
        self.max_connections = max_connections
        self.max_idle_seconds = max_idle_seconds
        self._active = 0
        self._total_handled = 0
        self._total_closed = 0
        self._rejected = 0
        self._last_cleanup = time.time()
        self._connections = deque()
    
    def acquire(self):
        """Registra uma nova conexão."""
        if self._active >= self.max_connections:
            self._rejected += 1
            return False
        self._active += 1
        self._total_handled += 1
        return True
    
    def release(self):
        """Libera uma conexão."""
        self._active -= 1
        self._total_closed += 1
    
    def cleanup_idle(self):
        """Remove conexões ociosas periodicamente."""
        now = time.time()
        if now - self._last_cleanup > self.max_idle_seconds:
            self._last_cleanup = now
    
    def stats(self):
        """Retorna estatísticas do pool."""
        return {
            "active_connections": self._active,
            "max_connections": self.max_connections,
            "total_handled": self._total_handled,
            "total_closed": self._total_closed,
            "rejected": self._rejected,
            "utilization_pct": round(self._active / max(1, self.max_connections) * 100, 1),
        }


class TCPConnectionPool:
    """Wrapper async para pool de conexões TCP."""
    
    def __init__(self, max_connections=50, max_idle_seconds=60):
        self.pool = ConnectionPool(max_connections, max_idle_seconds)
        self._requests_handled = 0
        self._requests_failed = 0
        self._bytes_sent = 0
        self._bytes_received = 0
    
    async def handle_client(self, reader, writer, handler):
        """Processa um cliente com pool."""
        if not self.pool.acquire():
            writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return {"status": "rejected", "reason": "pool_exhausted"}
        
        client_addr = writer.get_extra_info("peername")
        start_time = time.time()
        
        try:
            result = await handler(reader, writer)
            self._requests_handled += 1
            return {"status": "success", "client": str(client_addr), "duration_ms": int((time.time() - start_time) * 1000)}
        except Exception as exc:
            self._requests_failed += 1
            return {"status": "error", "client": str(client_addr), "error": str(exc)}
        finally:
            self.pool.release()
            self.pool.cleanup_idle()
    
    def stats(self):
        """Estatísticas do pool HTTP."""
        return {
            **self.pool.stats(),
            "requests_handled": self._requests_handled,
            "requests_failed": self._requests_failed,
            "bytes_sent": self._bytes_sent,
            "bytes_received": self._bytes_received,
        }


DEFAULT_POOL = TCPConnectionPool()