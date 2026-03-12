"""Servidor HTTP mínimo (uasyncio) para dashboard e API CleanSun."""
import json

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class CleanSunHTTPServer:
    def __init__(self, processor, host="0.0.0.0", port=80):
        self.processor = processor
        self.host = host
        self.port = port
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)

    async def _handle_client(self, reader, writer):
        req = await reader.readline()
        if not req:
            await writer.wait_closed()
            return

        req_line = req.decode("utf-8", "ignore")
        parts = req_line.split(" ")
        method = parts[0] if len(parts) > 0 else "GET"
        path = parts[1] if len(parts) > 1 else "/"

        while True:
            header = await reader.readline()
            if not header or header in (b"\r\n", b"\n"):
                break

        if method != "GET":
            await self._send(writer, "405 Method Not Allowed", "text/plain", "Method not allowed")
            return

        if path == "/":
            await self._serve_dashboard(writer)
        elif path == "/api/data" or path == "/api/state":
            body = json.dumps(self.processor.payload())
            await self._send(writer, "200 OK", "application/json", body)
        elif path == "/api/events":
            await self._serve_sse(writer)
        else:
            await self._send(writer, "404 Not Found", "text/plain", "rota nao encontrada")

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
            # keep alive + atualização "quase real-time" sem websocket pesado
            while True:
                payload = json.dumps(self.processor.payload())
                msg = "event: update\ndata: {data}\n\n".format(data=payload)
                writer.write(msg.encode("utf-8"))
                await writer.drain()
                await asyncio.sleep(5)
        except Exception:
            pass
        finally:
            await writer.wait_closed()

    async def _send(self, writer, status, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")

        response = (
            "HTTP/1.1 {status}\r\n"
            "Content-Type: {content_type}; charset=utf-8\r\n"
            "Content-Length: {size}\r\n"
            "Connection: close\r\n\r\n"
        ).format(status=status, content_type=content_type, size=len(body)).encode("utf-8")

        writer.write(response)
        writer.write(body)
        await writer.drain()
        await writer.wait_closed()
