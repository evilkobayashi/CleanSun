"""Servidor HTTP local do CleanSun com endpoints consolidados."""
import json
import secrets
import sys
import time

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
        self._technical_sessions = {}

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
    def _parse_cookies(headers):
        raw = headers.get("cookie", "")
        cookies = {}
        for item in raw.split(";"):
            item = item.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()
        return cookies

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

    def _technical_mode_enabled(self):
        return bool(self.processor.config.get("technical_mode_enabled", True))

    def _technical_session_ttl_seconds(self):
        minutes = max(1, int(self.processor.config.get("technical_session_timeout_minutes", 120) or 120))
        return minutes * 60

    def _cleanup_sessions(self):
        now = time.time()
        expired = [token for token, expiry in self._technical_sessions.items() if expiry <= now]
        for token in expired:
            self._technical_sessions.pop(token, None)

    def _is_technical_authenticated(self, headers):
        self._cleanup_sessions()
        cookies = self._parse_cookies(headers)
        token = cookies.get("technical_session")
        if not token:
            return False
        expiry = self._technical_sessions.get(token)
        if not expiry or expiry <= time.time():
            self._technical_sessions.pop(token, None)
            return False
        self._technical_sessions[token] = time.time() + self._technical_session_ttl_seconds()
        return True

    def _technical_status_payload(self, authenticated=False):
        return {
            "technical_mode_enabled": self._technical_mode_enabled(),
            "authenticated": bool(authenticated and self._technical_mode_enabled()),
            "session_timeout_minutes": int(self.processor.config.get("technical_session_timeout_minutes", 120) or 120),
        }

    def _require_technical_auth(self, headers):
        if not self._technical_mode_enabled():
            return False, ("403 Forbidden", {"error": "technical_mode_disabled", "message": "O modo técnico está desabilitado nesta instalação."}, [])
        if not self._is_technical_authenticated(headers):
            return False, ("401 Unauthorized", {"error": "technical_auth_required", "message": "Faça login técnico para alterar configurações do inversor."}, [])
        return True, None

    async def _handle_client(self, reader, writer):
        try:
            req = await reader.readline()
            if not req:
                writer.close()
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
            authenticated = self._is_technical_authenticated(headers)

            get_routes = {
                "/api/data": lambda q: self.processor.payload(),
                "/api/dashboard": lambda q: self.processor.dashboard(int(q.get("days", "7")), q.get("bucket", "daily")),
                "/api/indicators": lambda q: self.processor.indicators(),
                "/api/alerts": lambda q: self._alerts_response(q, "current"),
                "/api/alerts/active": lambda q: self._alerts_response(q, "active"),
                "/api/alerts/history": lambda q: self._alerts_response(q, "history"),
                "/api/profile": lambda q: self.processor.profile(),
                "/api/compare": lambda q: self.processor.compare(),
                "/api/technical": lambda q: self.processor.technical() if authenticated else {"error": "technical_auth_required"},
                "/api/diagnostics": lambda q: self.processor.diagnostics() if authenticated else {"error": "technical_auth_required"},
                "/api/status": lambda q: self.processor.status(),
                "/api/inverter-type": lambda q: {"inverter_type": self.processor.effective_inverter_type()},
                "/api/inverter-metadata": lambda q: self.processor.inverter_metadata() if authenticated else {"error": "technical_auth_required"},
                "/api/detection-status": lambda q: self.processor.detection_status(),
                "/api/summary/daily": lambda q: self.processor.summary("daily"),
                "/api/summary/weekly": lambda q: self.processor.summary("weekly"),
                "/api/history": lambda q: {"days": int(q.get("days", "7")), "bucket": q.get("bucket", "hourly"), "rows": self.processor.history_period(int(q.get("days", "7")), q.get("bucket", "hourly"))},
                "/api/state": lambda q: self.processor.payload(),
                "/api/auth/technical-status": lambda q: self._technical_status_payload(authenticated),
                "/api/v1/auth/technical-status": lambda q: self._technical_status_payload(authenticated),
                "/api/metrics": lambda q: self._serve_metrics(),
                "/api/v1/metrics": lambda q: self._serve_metrics(),
                "/api/health": lambda q: self._health_check(),
                "/api/v1/health": lambda q: self._health_check(),
                "/api/config/solarman": lambda q: self.processor.get_solarman_config() if authenticated else {"error": "technical_auth_required"},
                "/api/v1/config/solarman": lambda q: self.processor.get_solarman_config() if authenticated else {"error": "technical_auth_required"},
            }

            if method == "GET":
                if path == "/":
                    await self._serve_dashboard(writer)
                elif path == "/api/events":
                    await self._serve_sse(writer)
                elif path in get_routes:
                    status = "200 OK"
                    payload = get_routes[path](query)
                    if isinstance(payload, dict) and payload.get("error") == "technical_auth_required":
                        status = "401 Unauthorized"
                    await self._send(writer, status, "application/json", json.dumps(payload, ensure_ascii=False))
                else:
                    await self._send(writer, "404 Not Found", "application/json", json.dumps({"error": "not_found", "path": path}))
                return

            if method == "POST" and path == "/api/auth/technical-login":
                if not self._technical_mode_enabled():
                    await self._send(writer, "403 Forbidden", "application/json", json.dumps({"error": "technical_mode_disabled", "message": "Modo técnico desabilitado."}, ensure_ascii=False))
                    return
                payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                password = str(payload.get("password") or "")
                expected = str(self.processor.config.get("technical_mode_password", "123456"))
                if password != expected:
                    await self._send(writer, "401 Unauthorized", "application/json", json.dumps({"authenticated": False, "message": "Senha incorreta. Tente novamente."}, ensure_ascii=False))
                    return
                token = secrets.token_hex(16)
                self._technical_sessions[token] = time.time() + self._technical_session_ttl_seconds()
                await self._send(
                    writer,
                    "200 OK",
                    "application/json",
                    json.dumps({"authenticated": True, "message": "Acesso técnico liberado.", **self._technical_status_payload(True)}, ensure_ascii=False),
                    extra_headers=[("Set-Cookie", "technical_session={}; Path=/; HttpOnly; SameSite=Lax".format(token))],
                )
                return

            if method == "POST" and path == "/api/auth/technical-logout":
                cookies = self._parse_cookies(headers)
                token = cookies.get("technical_session")
                if token:
                    self._technical_sessions.pop(token, None)
                await self._send(
                    writer,
                    "200 OK",
                    "application/json",
                    json.dumps({"authenticated": False, "message": "Modo técnico encerrado.", **self._technical_status_payload(False)}, ensure_ascii=False),
                    extra_headers=[("Set-Cookie", "technical_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")],
                )
                return

            if method == "POST" and path in ("/api/inverter-type", "/api/inverter-type/override"):
                allowed, error = self._require_technical_auth(headers)
                if not allowed:
                    status, payload, extra_headers = error
                    await self._send(writer, status, "application/json", json.dumps(payload, ensure_ascii=False), extra_headers=extra_headers)
                    return
                payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                status = self.processor.set_manual_override(payload.get("inverter_type"))
                await self._send(writer, "200 OK", "application/json", json.dumps(status, ensure_ascii=False))
                return

            if method == "POST" and path == "/api/inverter-type/clear-override":
                allowed, error = self._require_technical_auth(headers)
                if not allowed:
                    status, payload, extra_headers = error
                    await self._send(writer, status, "application/json", json.dumps(payload, ensure_ascii=False), extra_headers=extra_headers)
                    return
                status = self.processor.clear_manual_override()
                await self._send(writer, "200 OK", "application/json", json.dumps(status, ensure_ascii=False))
                return

            if method == "POST" and path in ("/api/config/solarman", "/api/v1/config/solarman"):
                allowed, error = self._require_technical_auth(headers)
                if not allowed:
                    status, payload, extra_headers = error
                    await self._send(writer, status, "application/json", json.dumps(payload, ensure_ascii=False), extra_headers=extra_headers)
                    return
                try:
                    payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                    result = self.processor.update_solarman_config(payload.get("datalogger_ip", ""), payload.get("datalogger_serial", 0))
                    await self._send(writer, "200 OK", "application/json", json.dumps({"ok": True, **result}, ensure_ascii=False))
                except (ValueError, TypeError) as exc:
                    await self._send(writer, "400 Bad Request", "application/json", json.dumps({"error": "invalid_input", "message": str(exc)}, ensure_ascii=False))
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
            writer.close()
            await writer.wait_closed()

    async def _send(self, writer, status, content_type, body, extra_headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = [
            ("Content-Type", "{}; charset=utf-8".format(content_type)),
            ("Content-Length", str(len(body))),
            ("Connection", "close"),
        ]
        if extra_headers:
            headers.extend(extra_headers)
        header_text = "".join("{}: {}\r\n".format(key, value) for key, value in headers)
        response = "HTTP/1.1 {}\r\n{}\r\n".format(status, header_text).encode("utf-8")
        writer.write(response)
        writer.write(body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
