"""Processamento energético, painel técnico e alarmes estruturados do CleanSun."""
import json
import os
import time

from alarms import AlarmEngine, SEVERITY_ORDER
from inverter_detection import detect_inverter_type, normalize_type

DEFAULT_CONFIG = {
    "tarifa_kwh": 0.92,
    "potencia_sistema_kwp": 5.0,
    "nome_instalacao": "Residência",
    "history_max_bytes": 524288,
    "projection_factor_year": 30,
    "alert_generation_gap_pct": 15,
    "alert_night_import_kw": 1.2,
    "data_stale_seconds": 20,
    "simulation_anomalies_enabled": True,
    "simulation_random_fault_rate": 0.04,
    "manual_override": False,
    "manual_selected_type": None,
    "detected_inverter_type": None,
    "detection_source": "unknown",
    "detection_confidence": 0.0,
    "technical_mode_password": "123456",
    "technical_mode_enabled": True,
    "technical_session_timeout_minutes": 120,
    "simulation_inverter_type": "hybrid",
}

HISTORY_HEADER = "timestamp,geracao_kwh,consumo_kwh,exportado_kwh,solar_generation_kwh,house_consumption_kwh,grid_import_kwh,grid_export_kwh,self_consumption_kwh,estimated_savings_brl,weather_condition,expected_generation_kwh\n"
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


class DataProcessor:
    def __init__(self, config_path, history_path):
        self.config_path = config_path
        self.history_path = history_path
        self.config = self._load_config()
        self.alarm_engine = AlarmEngine(self.config)
        self.last_snapshot = {}
        self.last_dashboard = self._blank_dashboard()
        self.last_update_ts = 0
        self.fault = None
        self._hour_state = None
        self.inverter_config = {}
        self._ensure_history_file()

    def _load_config(self):
        if not self._exists(self.config_path):
            self._write_json(self.config_path, DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
        with open(self.config_path, "r", encoding="utf-8") as f:
            loaded = json.loads(f.read())
        merged = dict(DEFAULT_CONFIG)
        merged.update(loaded)
        return merged

    @staticmethod
    def _exists(path):
        try:
            os.stat(path)
            return True
        except OSError:
            return False

    @staticmethod
    def _write_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    @staticmethod
    def _blank_dashboard():
        return {
            "indicators": {},
            "alerts": [],
            "profile": {},
            "reports": {},
            "compare": {},
            "technical": {},
            "simplified": {},
            "history": {"daily": [], "weekly": [], "monthly": []},
            "status": {},
            "diagnostics": {},
            "inverter_detection": {},
        }

    def register_fault(self, title, detail=""):
        self.fault = {"title": title, "detail": detail, "ts": int(time.time())}

    def set_inverter_config(self, cfg):
        if cfg:
            self.inverter_config = dict(cfg)

    def get_inverter_config(self):
        return dict(self.inverter_config)

    def ingest_snapshot(self, snapshot, now_ts=None):
        ts = int(now_ts if now_ts is not None else snapshot.get("timestamp", time.time()))
        self.last_snapshot = dict(snapshot)
        self.last_update_ts = ts
        detection = self._update_detection(snapshot)
        indicators = self._compute_indicators(snapshot)
        technical = self._build_technical(snapshot, indicators)
        self._update_hourly_history(indicators, technical, ts)
        history_rows = self.history_last_days(35)
        alerts = self.alarm_engine.evaluate(snapshot, indicators, technical, history_rows, ts, fault=self.fault, updated_at=self.last_update_ts)
        reports = self._build_reports(indicators, history_rows, alerts)
        compare = self._build_compare(history_rows)
        profile = self._build_profile(history_rows, alerts)
        diagnostics = self.alarm_engine.diagnostics(snapshot, indicators, technical, alerts, self.last_update_ts, fault=self.fault)
        self.last_dashboard = {
            "inverter_detection": detection,
            "indicators": indicators,
            "alerts": alerts,
            "profile": profile,
            "reports": reports,
            "compare": compare,
            "technical": technical,
            "simplified": self._build_simplified(indicators, alerts, reports, profile),
            "history": self._history_views(history_rows),
            "status": self._build_status(snapshot, indicators, alerts, ts),
            "diagnostics": diagnostics,
        }

    def _compute_indicators(self, snapshot):
        generation = max(float(snapshot.get("daily_gen_kwh", 0.0)), 0.0)
        load_kw = max(float(snapshot.get("load_power_w", 0.0)) / 1000.0, 0.0)
        ac_kw = max(float(snapshot.get("ac_power_w", snapshot.get("instant_total_w", 0.0))) / 1000.0, 0.0)
        import_kw = max(float(snapshot.get("import_power_w", 0.0)) / 1000.0, 0.0)
        export_kw = max(float(snapshot.get("export_power_w", 0.0)) / 1000.0, 0.0)
        expected_kw = max(float(snapshot.get("expected_generation_w", 0.0)) / 1000.0, 0.0)
        consumed_direct = max(min(ac_kw, load_kw), 0.0)
        consumo_dia = max(generation * 0.58 + load_kw * 0.35, consumed_direct)
        exportado_dia = max(generation - consumo_dia, 0.0)
        importado_dia = max(consumo_dia - max(generation - exportado_dia, 0.0), 0.0)
        autoconsumo = (consumo_dia / generation * 100.0) if generation > 0 else 0.0
        autossuficiencia = (consumed_direct / load_kw * 100.0) if load_kw > 0 else 0.0
        aproveitamento = (max(generation - exportado_dia, 0.0) / generation * 100.0) if generation > 0 else 0.0
        performance_ratio = (ac_kw / expected_kw) if expected_kw > 0 else (1.0 if ac_kw > 0 else 0.0)
        performance_ratio = min(max(performance_ratio, 0.0), 1.6)
        diff_pct = ((ac_kw - expected_kw) / expected_kw * 100.0) if expected_kw > 0 else 0.0
        economy_daily = consumo_dia * float(self.config.get("tarifa_kwh", 0.92))
        history_rows = self.history_last_days(35)
        weekly = self._sum_rows(history_rows[-7 * 24:])
        monthly = self._sum_period(history_rows, "month")
        yearly = self._sum_period(history_rows, "year")
        peak = self._peak_from_rows(history_rows)
        return {
            "geracao_kwh": round(generation, 2),
            "consumo_kwh": round(consumo_dia, 2),
            "exportado_kwh": round(exportado_dia, 2),
            "importado_kwh": round(importado_dia, 2),
            "autoconsumo_pct": round(autoconsumo, 1),
            "autossuficiencia_pct": round(autossuficiencia, 1),
            "aproveitamento_solar_pct": round(aproveitamento, 1),
            "economia_diaria_rs": round(economy_daily, 2),
            "economia_semanal_rs": round(weekly["consumo_kwh"] * self.config.get("tarifa_kwh", 0.92), 2),
            "economia_mensal_rs": round(monthly["consumo_kwh"] * self.config.get("tarifa_kwh", 0.92), 2),
            "economia_anual_rs": round(yearly["consumo_kwh"] * self.config.get("tarifa_kwh", 0.92), 2),
            "potencia_atual_kw": round(ac_kw, 2),
            "consumo_atual_kw": round(load_kw, 2),
            "importacao_atual_kw": round(import_kw, 2),
            "exportacao_atual_kw": round(export_kw, 2),
            "geracao_esperada_kw": round(expected_kw, 2),
            "diferenca_geracao_pct": round(diff_pct, 1),
            "weather_label": snapshot.get("weather_label", "não informado"),
            "performance_ratio": round(performance_ratio, 2),
            "pico_geracao_kw": round(max(peak["generation_kw"], ac_kw), 2),
            "pico_consumo_kw": round(max(peak["consumption_kw"], load_kw), 2),
            "status": self._status_from_pr(performance_ratio),
            "status_text": self._status_text(performance_ratio),
            "hourly": self._hourly_curve(snapshot),
        }

    @staticmethod
    def _status_from_pr(pr):
        if pr >= 0.85:
            return "NORMAL"
        if pr >= 0.6:
            return "ATENCAO"
        return "CRITICO"

    @staticmethod
    def _status_text(pr):
        if pr >= 0.85:
            return "Sistema funcionando normalmente"
        if pr >= 0.6:
            return "Desempenho abaixo do esperado"
        return "Sistema com falha ou baixo desempenho"

    def _build_technical(self, snapshot, indicators):
        dc_input = snapshot.get("dc_input", {})
        ac_output = snapshot.get("ac_output", {})
        grid = snapshot.get("grid", {})
        inverter = snapshot.get("inverter", {})
        energy = snapshot.get("energy", {})
        battery = snapshot.get("battery", {})
        operation = snapshot.get("operation", {})
        return {
            "dc_input": {
                "mppt1_voltage_v": round(dc_input.get("mppt1_voltage_v", snapshot.get("tensao_dc_v", 0)), 1),
                "mppt1_current_a": round(dc_input.get("mppt1_current_a", 0.0), 2),
                "mppt1_power_kw": round(dc_input.get("mppt1_power_kw", 0.0), 2),
                "mppt2_voltage_v": round(dc_input.get("mppt2_voltage_v", 0.0), 1),
                "mppt2_current_a": round(dc_input.get("mppt2_current_a", 0.0), 2),
                "mppt2_power_kw": round(dc_input.get("mppt2_power_kw", 0.0), 2),
                "dc_power_kw": round(dc_input.get("dc_power_kw", snapshot.get("dc_power_w", 0) / 1000.0), 2),
            },
            "ac_output": {
                "voltage_v": round(ac_output.get("voltage_v", grid.get("grid_voltage_v", 0.0)), 1),
                "current_a": round(ac_output.get("current_a", 0.0), 2),
                "power_kw": round(ac_output.get("power_kw", snapshot.get("ac_power_w", 0) / 1000.0), 2),
                "frequency_hz": round(ac_output.get("frequency_hz", grid.get("frequency_hz", 0.0)), 2),
                "power_factor": round(ac_output.get("power_factor", 0.0), 3),
            },
            "grid": {
                "grid_voltage_v": round(grid.get("grid_voltage_v", 0.0), 1),
                "grid_current_a": round(grid.get("grid_current_a", 0.0), 2),
                "grid_status": grid.get("grid_status", snapshot.get("grid_status", "Desconhecido")),
                "frequency_hz": round(grid.get("frequency_hz", 0.0), 2),
                "active_power_kw": round(grid.get("active_power_kw", 0.0), 2),
                "apparent_power_kva": round(grid.get("apparent_power_kva", 0.0), 2),
            },
            "inverter": {
                "temperature_c": round(inverter.get("temperature_c", snapshot.get("temperature_c", 0.0)), 1),
                "efficiency_percent": round(inverter.get("efficiency_percent", 0.0), 2),
                "status": inverter.get("status", snapshot.get("inverter_status", "Desconhecido")),
                "communication_status": inverter.get("communication_status", snapshot.get("communication_status", "Desconhecido")),
                "operational_state": inverter.get("operational_state", snapshot.get("inverter_status", "Desconhecido")),
            },
            "energy": {
                "today_kwh": round(energy.get("today_kwh", indicators["geracao_kwh"]), 2),
                "total_kwh": round(energy.get("total_kwh", snapshot.get("total_gen_kwh", 0.0)), 1),
                "import_kwh": round(energy.get("import_kwh", indicators["importado_kwh"]), 2),
                "export_kwh": round(energy.get("export_kwh", indicators["exportado_kwh"]), 2),
                "peak_power_kw": round(energy.get("peak_power_kw", indicators["pico_geracao_kw"]), 2),
                "generation_start_time": energy.get("generation_start_time", "--:--"),
                "generation_end_time": energy.get("generation_end_time", "--:--"),
                "generation_duration_h": round(energy.get("generation_duration_h", 0.0), 2),
            },
            "irradiance": {
                "irradiance_wm2": int(snapshot.get("irradiance_wm2", 0)),
                "solar_condition": snapshot.get("weather_label", "não informado"),
            },
            "battery": {
                "soc_percent": round(battery.get("soc_percent", snapshot.get("battery_soc_percent", 0.0)), 1),
                "voltage_v": round(battery.get("voltage_v", snapshot.get("battery_voltage_v", 0.0)), 1),
                "current_a": round(battery.get("current_a", snapshot.get("battery_current_a", 0.0)), 2),
                "power_kw": round(battery.get("power_kw", snapshot.get("battery_power_kw", 0.0)), 2),
                "mode": battery.get("mode", snapshot.get("battery_mode", "idle")),
                "autonomy_hours": round(battery.get("autonomy_hours", snapshot.get("autonomy_hours", 0.0)), 2),
                "available_energy_kwh": round(battery.get("available_energy_kwh", energy.get("battery_available_kwh", 0.0)), 2),
            },
            "operation": {
                "operating_mode": operation.get("operating_mode", snapshot.get("operating_mode", "solar_priority")),
                "backup_mode_active": bool(operation.get("backup_mode_active", snapshot.get("backup_mode_active", False))),
                "grid_available": bool(operation.get("grid_available", snapshot.get("grid_available", True))),
                "load_power_kw": round(snapshot.get("load_power_kw", indicators.get("consumo_atual_kw", 0.0)), 2),
            },
            "diagnostics": {
                "communication_status": snapshot.get("communication_status", "Desconhecido"),
                "grid_status": snapshot.get("grid_status", "Desconhecido"),
                "operational_status": snapshot.get("inverter_status", "Desconhecido"),
                "status_code": snapshot.get("status_code", -1),
                "fault_title": self.fault.get("title") if self.fault else "",
            },
        }

    def _build_reports(self, indicators, history_rows, alerts):
        week = self._sum_rows(history_rows[-7 * 24:])
        critical = [a for a in alerts if a["severity"] == "critical"]
        return {
            "daily": "Hoje o sistema gerou {:.2f} kWh, exportou {:.2f} kWh e a economia estimada foi de R$ {:.2f}.".format(indicators["geracao_kwh"], indicators["exportado_kwh"], indicators["economia_diaria_rs"]),
            "weekly": "Na última semana o sistema gerou {:.2f} kWh, com {:.2f} kWh consumidos diretamente e {:.2f} kWh exportados para a rede.".format(week["geracao_kwh"], week["consumo_kwh"], week["exportado_kwh"]),
            "alerts_focus": critical[0]["title"] if critical else alerts[0]["title"],
        }

    def _build_profile(self, history_rows, alerts):
        night_import = 0.0
        for row in history_rows:
            hour = time.localtime(row["timestamp"]).tm_hour
            if hour >= 18 or hour <= 5:
                night_import += max(row["consumo_kwh"] - max(row["geracao_kwh"] - row["exportado_kwh"], 0.0), 0.0)
        recs = ["Priorize máquinas, ferro e chuveiro em horários com maior geração solar."]
        if night_import > 4:
            recs.append("Seu perfil indica dependência relevante da rede no período noturno.")
        if any(a["code"] == "POSSIBLE_SOILING" for a in alerts):
            recs.append("Vale programar inspeção visual e limpeza dos módulos fotovoltaicos.")
        return {"night_import_kwh": round(night_import, 2), "recommendations": recs}

    def _build_simplified(self, indicators, alerts, reports, profile):
        top = alerts[0]
        important = [a["simplified_message"] for a in alerts[:3]]
        return {
            "headline": top["title"],
            "status_text": indicators["status_text"],
            "messages": important + [
                "Hoje sua residência aproveitou {:.1f}% da energia produzida pelo sistema solar.".format(indicators["autoconsumo_pct"]),
                "A economia estimada do dia foi de R$ {:.2f}.".format(indicators["economia_diaria_rs"]),
                "Seu consumo noturno continua dependente da rede elétrica." if profile["night_import_kwh"] > 1.0 else "A dependência da rede no período noturno está controlada.",
            ],
            "daily_report": reports["daily"],
            "weekly_report": reports["weekly"],
            "primary_action": top["recommended_action"],
        }

    def _build_compare(self, history_rows):
        return {
            "today_vs_yesterday": self._compare_block(self._sum_period(history_rows, "day"), self._sum_previous_day(history_rows)),
            "week_vs_previous": self._compare_block(self._sum_period(history_rows, "week"), self._sum_previous_week(history_rows)),
            "month_vs_previous": self._compare_block(self._sum_period(history_rows, "month"), self._sum_previous_month(history_rows)),
        }

    def _build_status(self, snapshot, indicators, alerts, ts):
        stale_seconds = max(0, int(time.time()) - int(self.last_update_ts or ts))
        return {
            "operational_state": snapshot.get("inverter_status", "Desconhecido"),
            "communication_status": snapshot.get("communication_status", "Desconhecido"),
            "grid_status": snapshot.get("grid_status", "Desconhecido"),
            "status_text": indicators["status_text"],
            "active_alarm_count": len([a for a in alerts if a["active"]]),
            "critical_alarm_count": len([a for a in alerts if a["severity"] == "critical"]),
            "warning_alarm_count": len([a for a in alerts if a["severity"] == "warning"]),
            "updated_at": ts,
            "stale_seconds": stale_seconds,
        }

    def _ensure_history_file(self):
        if not self._exists(self.history_path):
            with open(self.history_path, "w", encoding="utf-8") as f:
                f.write(HISTORY_HEADER)
            return
        with open(self.history_path, "r", encoding="utf-8") as f:
            head = f.readline()
        if not head.startswith("timestamp,"):
            with open(self.history_path, "w", encoding="utf-8") as f:
                f.write(HISTORY_HEADER)

    def _hour_key(self, ts):
        lt = time.localtime(ts)
        return (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour)

    def _update_hourly_history(self, indicators, technical, ts):
        cur_hour = self._hour_key(ts)
        if self._hour_state is None:
            self._hour_state = {"hour": cur_hour, "indicators": indicators, "technical": technical, "last_ts": ts}
            return
        if cur_hour != self._hour_state["hour"]:
            prev = self._hour_state["indicators"]
            self._append_history_row(self._hour_state["last_ts"], prev)
            self._hour_state = {"hour": cur_hour, "indicators": indicators, "technical": technical, "last_ts": ts}
        else:
            self._hour_state.update({"indicators": indicators, "technical": technical, "last_ts": ts})

    def _append_history_row(self, timestamp, indicators):
        importado = max(indicators["consumo_kwh"] - max(indicators["geracao_kwh"] - indicators["exportado_kwh"], 0.0), 0.0)
        autoconsumo = max(indicators["consumo_kwh"] - importado, 0.0)
        economia = autoconsumo * float(self.config.get("tarifa_kwh", 0.92))
        line = "{},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},,{:.3f}\n".format(int(timestamp), indicators["geracao_kwh"], indicators["consumo_kwh"], indicators["exportado_kwh"], indicators["geracao_kwh"], indicators["consumo_kwh"], importado, indicators["exportado_kwh"], autoconsumo, economia, indicators["geracao_kwh"])
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(line)
        self._enforce_history_flash_limit()

    def _enforce_history_flash_limit(self):
        if os.stat(self.history_path).st_size <= int(self.config.get("history_max_bytes", 524288)):
            return
        with open(self.history_path, "r", encoding="utf-8") as f:
            rows = f.readlines()
        while len(rows) > 2 and len("".join(rows).encode("utf-8")) > int(self.config.get("history_max_bytes", 524288)):
            rows.pop(1)
        with open(self.history_path, "w", encoding="utf-8") as f:
            f.write("".join(rows))

    def history_last_days(self, days=7):
        cutoff = int(time.time()) - max(1, int(days)) * 86400
        rows = []
        if not self._exists(self.history_path):
            return rows
        with open(self.history_path, "r", encoding="utf-8") as f:
            _ = f.readline()
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 4:
                    continue
                ts = int(parts[0])
                if ts >= cutoff:
                    rows.append({"timestamp": ts, "geracao_kwh": float(parts[1]), "consumo_kwh": float(parts[2]), "exportado_kwh": float(parts[3])})
        return rows

    def history_period(self, days=7, bucket="hourly"):
        rows = self.history_last_days(days)
        if bucket == "hourly":
            return rows
        buckets = {}
        for row in rows:
            lt = time.localtime(row["timestamp"])
            if bucket == "daily":
                key = (lt.tm_year, lt.tm_mon, lt.tm_mday)
                label = "{:02d}/{:02d}".format(lt.tm_mday, lt.tm_mon)
            elif bucket == "weekly":
                key = time.strftime("%Y-W%W", lt)
                label = key
            else:
                key = (lt.tm_year, lt.tm_mon)
                label = MONTHS[lt.tm_mon - 1]
            block = buckets.setdefault(key, {"label": label, "geracao_kwh": 0.0, "consumo_kwh": 0.0, "exportado_kwh": 0.0})
            block["geracao_kwh"] += row["geracao_kwh"]
            block["consumo_kwh"] += row["consumo_kwh"]
            block["exportado_kwh"] += row["exportado_kwh"]
        return list(buckets.values())

    @staticmethod
    def _sum_rows(rows):
        out = {"geracao_kwh": 0.0, "consumo_kwh": 0.0, "exportado_kwh": 0.0}
        for row in rows:
            out["geracao_kwh"] += row["geracao_kwh"]
            out["consumo_kwh"] += row["consumo_kwh"]
            out["exportado_kwh"] += row["exportado_kwh"]
        return out

    def _sum_period(self, rows, period):
        now = time.localtime()
        selected = []
        for row in rows:
            lt = time.localtime(row["timestamp"])
            if period == "day" and (lt.tm_year, lt.tm_mon, lt.tm_mday) == (now.tm_year, now.tm_mon, now.tm_mday):
                selected.append(row)
            elif period == "week" and time.strftime("%Y-W%W", lt) == time.strftime("%Y-W%W", now):
                selected.append(row)
            elif period == "month" and (lt.tm_year, lt.tm_mon) == (now.tm_year, now.tm_mon):
                selected.append(row)
            elif period == "year" and lt.tm_year == now.tm_year:
                selected.append(row)
        return self._sum_rows(selected)

    def _sum_previous_day(self, rows):
        prev = time.localtime(time.time() - 86400)
        return self._sum_rows([r for r in rows if (time.localtime(r["timestamp"]).tm_year, time.localtime(r["timestamp"]).tm_mon, time.localtime(r["timestamp"]).tm_mday) == (prev.tm_year, prev.tm_mon, prev.tm_mday)])

    def _sum_previous_week(self, rows):
        prev = time.localtime(time.time() - 7 * 86400)
        key = time.strftime("%Y-W%W", prev)
        return self._sum_rows([r for r in rows if time.strftime("%Y-W%W", time.localtime(r["timestamp"])) == key])

    def _sum_previous_month(self, rows):
        now = time.localtime()
        year = now.tm_year if now.tm_mon > 1 else now.tm_year - 1
        month = now.tm_mon - 1 if now.tm_mon > 1 else 12
        return self._sum_rows([r for r in rows if (time.localtime(r["timestamp"]).tm_year, time.localtime(r["timestamp"]).tm_mon) == (year, month)])

    @staticmethod
    def _compare_block(current, previous):
        delta = current["geracao_kwh"] - previous["geracao_kwh"]
        pct = (delta / previous["geracao_kwh"] * 100.0) if previous["geracao_kwh"] > 0 else 0.0
        return {"current_kwh": round(current["geracao_kwh"], 2), "previous_kwh": round(previous["geracao_kwh"], 2), "delta_kwh": round(delta, 2), "delta_pct": round(pct, 1)}

    @staticmethod
    def _peak_from_rows(rows):
        peak_gen = 0.0
        peak_cons = 0.0
        for row in rows[-72:]:
            peak_gen = max(peak_gen, row["geracao_kwh"])
            peak_cons = max(peak_cons, row["consumo_kwh"])
        return {"generation_kw": peak_gen, "consumption_kw": peak_cons}

    def _hourly_curve(self, snapshot):
        pv = max(float(snapshot.get("ac_power_w", snapshot.get("instant_total_w", 0.0))), 0.0)
        load = max(float(snapshot.get("load_power_w", 0.0)), 0.0)
        out = {}
        for h in range(24):
            sun_factor = max(0.0, 1.0 - ((h - 12) / 7.0) ** 2)
            load_factor = 0.55 if 8 <= h <= 17 else 1.05
            out[str(h)] = {"generation_w": round(pv * sun_factor, 0), "consumption_w": round(load * load_factor, 0)}
        return out

    def _history_views(self, rows):
        return {"daily": self.history_period(7, "daily"), "weekly": self.history_period(35, "weekly"), "monthly": self.history_period(365, "monthly")}

    def _update_config(self):
        self._write_json(self.config_path, self.config)

    def update_solarman_config(self, ip: str, serial: int) -> dict:
        ip = str(ip).strip()
        if not ip:
            raise ValueError("IP do datalogger não pode ser vazio.")
        serial = int(serial)
        if serial <= 0:
            raise ValueError("Serial do datalogger inválido.")
        solarman = self.config.setdefault("solarman", {})
        solarman["datalogger_ip"] = ip
        solarman["datalogger_serial"] = serial
        self._update_config()
        return {"datalogger_ip": ip, "datalogger_serial": serial}

    def get_solarman_config(self) -> dict:
        solarman = self.config.get("solarman", {})
        return {
            "datalogger_ip": solarman.get("datalogger_ip", ""),
            "datalogger_serial": solarman.get("datalogger_serial", 0),
        }

    def _update_detection(self, snapshot):
        status = detect_inverter_type(snapshot, self.config)
        new_type = status.get("detected_inverter_type")
        new_source = status.get("detection_source")
        new_conf = status.get("confidence")
        # Only persist config when detection actually changed — avoids a
        # config.json write on every poll (would be 1 write/s at fast polling).
        changed = (
            self.config.get("detected_inverter_type") != new_type
            or self.config.get("detection_source") != new_source
            or self.config.get("detection_confidence") != new_conf
        )
        self.config["detected_inverter_type"] = new_type
        self.config["detection_source"] = new_source
        self.config["detection_confidence"] = new_conf
        if changed:
            self._update_config()
        return status

    def detection_status(self):
        return {
            "detected_inverter_type": normalize_type(self.config.get("detected_inverter_type")),
            "effective_inverter_type": self.effective_inverter_type(),
            "detection_source": self.config.get("detection_source", "unknown"),
            "confidence": round(float(self.config.get("detection_confidence", 0.0)), 2),
            "confidence_label": self.last_dashboard.get("inverter_detection", {}).get("confidence_label", "baixa"),
            "manual_override": bool(self.config.get("manual_override", False)),
            "manual_selected_type": normalize_type(self.config.get("manual_selected_type")),
            "metadata": self.inverter_metadata(),
        }

    def inverter_metadata(self):
        return {key: self.last_snapshot.get(key) for key in ("manufacturer", "brand", "model", "product_family", "firmware_version", "inverter_mode", "serial_number", "inverter_capabilities") if self.last_snapshot.get(key) not in (None, "")}

    def effective_inverter_type(self):
        manual = normalize_type(self.config.get("manual_selected_type"))
        if self.config.get("manual_override") and manual:
            return manual
        detected = normalize_type(self.config.get("detected_inverter_type"))
        return detected or "hybrid"

    def set_manual_override(self, inverter_type):
        normalized = normalize_type(inverter_type)
        if normalized is None:
            raise ValueError("invalid_inverter_type")
        self.config["manual_override"] = True
        self.config["manual_selected_type"] = normalized
        self._update_config()
        return self.detection_status()

    def clear_manual_override(self):
        self.config["manual_override"] = False
        self.config["manual_selected_type"] = None
        self._update_config()
        return self.detection_status()

    def inverter_type(self):
        return self.effective_inverter_type()

    def set_inverter_type(self, inverter_type):
        return self.set_manual_override(inverter_type)

    def _filter_payload_by_inverter_type(self, data, inverter_type=None):
        inverter_type = inverter_type or self.effective_inverter_type()
        dashboard = dict(data.get("dashboard", {})) if isinstance(data, dict) else {}
        indicators = dict(dashboard.get("indicators", {}))
        technical = dict(dashboard.get("technical", {}))
        reports = dict(dashboard.get("reports", {}))
        alerts = list(dashboard.get("alerts", []))
        allowed_categories = {"geração", "entrada_dc", "eficiência", "temperatura", "comunicação", "diagnóstico"}
        if inverter_type == "on-grid":
            technical.pop("battery", None)
            technical.pop("operation", None)
            alerts = [a for a in alerts if a.get("category") != "segurança" or not a.get("code", "").startswith("BATTERY_")]
        elif inverter_type == "off-grid":
            for key in ("exportado_kwh", "importado_kwh", "economia_diaria_rs", "economia_mensal_rs", "economia_anual_rs", "autossuficiencia_pct"):
                indicators.pop(key, None)
            technical.pop("grid", None)
            technical["operation"] = technical.get("operation", {})
            reports["daily"] = reports.get("daily", "").replace("exportou", "entregou às cargas").replace("economia estimada", "energia útil estimada")
            allowed_categories |= {"segurança", "consumo"}
            alerts = [a for a in alerts if a.get("category") in allowed_categories and a.get("code") not in ("GRID_UNDERVOLTAGE", "GRID_OVERVOLTAGE", "GRID_FREQ_OUT_OF_RANGE", "LOW_GRID_EXPORT_AT_PEAK", "EXCESSIVE_GRID_IMPORT")]
        else:
            allowed_categories |= {"rede", "segurança", "consumo"}
            alerts = [a for a in alerts if a.get("category") in allowed_categories]
        dashboard["indicators"] = indicators
        dashboard["technical"] = technical
        dashboard["reports"] = reports
        dashboard["alerts"] = alerts
        dashboard["inverter_type"] = inverter_type
        dashboard["inverter_detection"] = self.detection_status()
        out = dict(data)
        out["dashboard"] = dashboard
        out["inverter_type"] = inverter_type
        out["detection_status"] = self.detection_status()
        return out

    def _filter_alerts(self, items, severity=None, category=None, active=None):
        out = list(items)
        if severity:
            out = [a for a in out if a.get("severity") == severity]
        if category:
            out = [a for a in out if a.get("category") == category]
        if active is not None:
            active_bool = active if isinstance(active, bool) else str(active).lower() in ("1", "true", "yes")
            out = [a for a in out if bool(a.get("active")) == active_bool]
        out.sort(key=lambda item: (SEVERITY_ORDER.get(item.get("severity"), 9), item.get("timestamp", 0), item.get("code", "")))
        return out

    def payload(self):
        base={"config": self.config, "snapshot": self.last_snapshot, "dashboard": self.last_dashboard, "updated_at": self.last_update_ts, "fault": self.fault, "inverter_type": self.effective_inverter_type(), "detection_status": self.detection_status()}
        return self._filter_payload_by_inverter_type(base)

    def indicators(self):
        return self.payload().get("dashboard", {}).get("indicators", {})

    def alerts(self, severity=None, category=None, active=None):
        return self._filter_alerts(self.payload().get("dashboard", {}).get("alerts", []), severity=severity, category=category, active=active)

    def active_alerts(self, severity=None, category=None):
        return self.alerts(severity=severity, category=category, active=True)

    def alert_history(self, severity=None, category=None):
        return self._filter_alerts(self.alarm_engine.history, severity=severity, category=category, active=None)

    def profile(self):
        return self.payload().get("dashboard", {}).get("profile", {})

    def compare(self):
        return self.payload().get("dashboard", {}).get("compare", {})

    def technical(self):
        return self.payload().get("dashboard", {}).get("technical", {})

    def diagnostics(self):
        return self.payload().get("dashboard", {}).get("diagnostics", {})

    def status(self):
        status = dict(self.payload().get("dashboard", {}).get("status", {}))
        status["active_alert_codes"] = [a["code"] for a in self.active_alerts()]
        return status

    def summary(self, period="daily"):
        return {"period": period, "text": self.last_dashboard.get("reports", {}).get(period, "Sem dados suficientes.")}

    def dashboard(self, days=7, bucket="daily"):
        data = dict(self.payload())
        data["history_filtered"] = self.history_period(days, bucket)
        return self._filter_payload_by_inverter_type(data)
