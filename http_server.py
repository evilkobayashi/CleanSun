"""Servidor HTTP minimo para dashboard e API CleanSun.

Compativel com CPython asyncio E MicroPython uasyncio 1.21+.
"""
import json

try:
    import uasyncio as asyncio
    _MICROPYTHON = True
except ImportError:
    import asyncio
    _MICROPYTHON = False

# Header CORS reutilizado em todas as respostas JSON
_CORS = "Access-Control-Allow-Origin: *\r\n"


class CleanSunHTTPServer:
    def __init__(self, processor, host="0.0.0.0", port=80):
        self.processor = processor
        self.host = host
        self.port = port

    async def start(self):
        # BUG CORRIGIDO: No MicroPython, asyncio.start_server nao retorna coroutine
        # e nao precisa de 'await'. No CPython precisa. Usamos create_task para
        # iniciar o servidor sem bloquear o event loop em ambos os ambientes.
        if _MICROPYTHON:
            asyncio.start_server(self._handle_client, self.host, self.port)
        else:
            server = await asyncio.start_server(self._handle_client, self.host, self.port)
            asyncio.ensure_future(server.serve_forever())

    @staticmethod
    def _parse_query(path):
        if "?" not in path:
            return path, {}
        base, raw = path.split("?", 1)
        query = {}
        for p in raw.split("&"):
            if not p:
                continue
            k, v = (p.split("=", 1) if "=" in p else (p, ""))
            query[k] = v
        return base, query

    async def _handle_client(self, reader, writer):
        try:
            req = await reader.readline()
            if not req:
                return

            req_line = req.decode("utf-8", "ignore")
            parts = req_line.split(" ")
            method = parts[0] if len(parts) > 0 else "GET"
            path   = parts[1] if len(parts) > 1 else "/"
            path, query = self._parse_query(path)

            # Consumir headers restantes
            while True:
                header = await reader.readline()
                if not header or header in (b"\r\n", b"\n"):
                    break

            if method != "GET":
                await self._send(writer, "405 Method Not Allowed", "text/plain", "Method not allowed")
                return

            if path == "/":
                await self._serve_dashboard(writer)
            elif path in ("/api/data", "/api/state"):
                body = json.dumps(self.processor.payload())
                await self._send(writer, "200 OK", "application/json", body)
            elif path == "/api/history":
                days = query.get("days", "7")
                try:
                    days = int(days)
                except ValueError:
                    days = 7
                body = json.dumps({"days": days, "rows": self.processor.history_last_days(days)})
                await self._send(writer, "200 OK", "application/json", body)
            elif path == "/api/events":
                await self._serve_sse(writer)
            else:
                await self._send(writer, "404 Not Found", "text/plain", "rota nao encontrada")
        except Exception:
            pass
        finally:
            # BUG CORRIGIDO: writer.wait_closed() nao existe no MicroPython.
            # Usamos writer.close() com fallback seguro.
            try:
                writer.close()
                if not _MICROPYTHON:
                    await writer.wait_closed()
            except Exception:
                pass

    async def _serve_dashboard(self, writer):
        try:
            with open("dashboard.html", "r", encoding="utf-8") as f:
                body = f.read()
            await self._send(writer, "200 OK", "text/html", body)
        except OSError:
            await self._send(writer, "404 Not Found", "text/plain", "dashboard.html nao encontrado")

    async def _serve_sse(self, writer):
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            "Access-Control-Allow-Origin: *\r\n\r\n"
        )
        writer.write(headers.encode("utf-8"))
        await writer.drain()
        try:
            while True:
                payload = json.dumps(self.processor.payload())
                msg = "event: update\ndata: {}\n\n".format(payload)
                writer.write(msg.encode("utf-8"))
                await writer.drain()
                await asyncio.sleep(5)
        except Exception:
            pass
        finally:
            try:
                writer.close()
                if not _MICROPYTHON:
                    await writer.wait_closed()
            except Exception:
                pass

    async def _send(self, writer, status, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")

        # BUG CORRIGIDO: adicionado CORS em todas as respostas JSON/HTML
        response = (
            "HTTP/1.1 {status}\r\n"
            "Content-Type: {ct}; charset=utf-8\r\n"
            "Content-Length: {size}\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n\r\n"
        ).format(status=status, ct=content_type, size=len(body)).encode("utf-8")

        writer.write(response)
        writer.write(body)
        await writer.drain()
