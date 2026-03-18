"""Servidor HTTP local do CleanSun com endpoints consolidados."""
import json
import sys

if sys.implementation.name == "micropython":
    import uasyncio as asyncio
else:
    import asyncio


class CleanSunHTTPServer:
    def __init__(self, processor, host="0.0.0.0", port=80):
        self.processor = processor
        self.host = host
        self.port = port
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)

    @staticmethod
    def _parse_query(path):
        if "?" not in path:
            return path, {}
        base, raw = path.split("?", 1)
        query = {}
        for part in raw.split("&"):
            if not part:
                continue
            if "=" in part:
                key, value = part.split("=", 1)
            else:
                key, value = part, ""
            query[key] = value
        return base, query

    @staticmethod
    async def _read_body(reader, headers):
        content_length = int(headers.get("content-length", "0") or "0")
        return await reader.read(content_length) if content_length > 0 else b""

    def _alerts_response(self, q, source="current"):
        severity = q.get("severity") or None
        category = q.get("category") or None
        active = q.get("active") if "active" in q else None
        if source == "history":
            rows = self.processor.alert_history(severity=severity, category=category)
        elif source == "active":
            rows = self.processor.active_alerts(severity=severity, category=category)
        else:
            rows = self.processor.alerts(severity=severity, category=category, active=active)
        return {"items": rows, "count": len(rows), "filters": {"severity": severity, "category": category, "active": active}, "inverter_type": self.processor.inverter_type()}

    async def _handle_client(self, reader, writer):
        try:
            req = await reader.readline()
            if not req:
                await writer.wait_closed()
                return
            parts = req.decode("utf-8", "ignore").split(" ")
            method = parts[0] if parts else "GET"
            path = parts[1] if len(parts) > 1 else "/"
            path, query = self._parse_query(path)
            headers = {}
            while True:
                header = await reader.readline()
                if not header or header in (b"\r\n", b"\n"):
                    break
                text = header.decode("utf-8", "ignore").strip()
                if ":" in text:
                    key, value = text.split(":", 1)
                    headers[key.lower()] = value.strip()
            body = await self._read_body(reader, headers)

            get_routes = {
                "/api/data": lambda q: self.processor.payload(),
                "/api/dashboard": lambda q: self.processor.dashboard(int(q.get("days", "7")), q.get("bucket", "daily")),
                "/api/indicators": lambda q: self.processor.indicators(),
                "/api/alerts": lambda q: self._alerts_response(q, "current"),
                "/api/alerts/active": lambda q: self._alerts_response(q, "active"),
                "/api/alerts/history": lambda q: self._alerts_response(q, "history"),
                "/api/profile": lambda q: self.processor.profile(),
                "/api/compare": lambda q: self.processor.compare(),
                "/api/technical": lambda q: self.processor.technical(),
                "/api/diagnostics": lambda q: self.processor.diagnostics(),
                "/api/status": lambda q: self.processor.status(),
                "/api/inverter-type": lambda q: {"inverter_type": self.processor.effective_inverter_type()},
                "/api/inverter-metadata": lambda q: self.processor.inverter_metadata(),
                "/api/detection-status": lambda q: self.processor.detection_status(),
                "/api/summary/daily": lambda q: self.processor.summary("daily"),
                "/api/summary/weekly": lambda q: self.processor.summary("weekly"),
                "/api/history": lambda q: {"days": int(q.get("days", "7")), "bucket": q.get("bucket", "hourly"), "rows": self.processor.history_period(int(q.get("days", "7")), q.get("bucket", "hourly"))},
                "/api/state": lambda q: self.processor.payload(),
            }

            if method == "GET":
                if path == "/":
                    await self._serve_dashboard(writer)
                elif path == "/api/events":
                    await self._serve_sse(writer)
                elif path in get_routes:
                    await self._send(writer, "200 OK", "application/json", json.dumps(get_routes[path](query), ensure_ascii=False))
                else:
                    await self._send(writer, "404 Not Found", "application/json", json.dumps({"error": "not_found", "path": path}))
                return

            if method == "POST" and path in ("/api/inverter-type", "/api/inverter-type/override"):
                payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                status = self.processor.set_manual_override(payload.get("inverter_type"))
                await self._send(writer, "200 OK", "application/json", json.dumps(status, ensure_ascii=False))
                return

            if method == "POST" and path == "/api/inverter-type/clear-override":
                status = self.processor.clear_manual_override()
                await self._send(writer, "200 OK", "application/json", json.dumps(status, ensure_ascii=False))
                return

            await self._send(writer, "405 Method Not Allowed", "application/json", json.dumps({"error": "method_not_allowed"}))
        except Exception as exc:
            self.processor.register_fault("server_api_failure", str(exc))
            await self._send(writer, "500 Internal Server Error", "application/json", json.dumps({"error": "server_api_failure", "detail": str(exc)}))

    async def _serve_dashboard(self, writer):
        with open("dashboard.html", "r", encoding="utf-8") as f:
            body = f.read()
        await self._send(writer, "200 OK", "text/html", body)

    async def _serve_sse(self, writer):
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n\r\n"
        )
        writer.write(headers.encode("utf-8"))
        await writer.drain()
        try:
            while True:
                payload = json.dumps(self.processor.dashboard(), ensure_ascii=False)
                writer.write(("event: update\ndata: " + payload + "\n\n").encode("utf-8"))
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
            "Content-Type: {ctype}; charset=utf-8\r\n"
            "Content-Length: {length}\r\n"
            "Connection: close\r\n\r\n"
        ).format(status=status, ctype=content_type, length=len(body)).encode("utf-8")
        writer.write(response)
        writer.write(body)
        await writer.drain()
        await writer.wait_closed()
