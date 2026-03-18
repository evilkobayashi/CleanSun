"""Processamento energético, indicadores, alertas e relatórios do CleanSun."""
import json
import os
import time

DEFAULT_CONFIG = {
    "tarifa_kwh": 0.92,
    "potencia_sistema_kwp": 5.0,
    "nome_instalacao": "Residência",
    "history_max_bytes": 524288,
    "projection_factor_year": 30,
    "alert_generation_gap_pct": 15,
    "alert_night_import_kw": 1.2,
}

HISTORY_HEADER = "timestamp,geracao_kwh,consumo_kwh,exportado_kwh,solar_generation_kwh,house_consumption_kwh,grid_import_kwh,grid_export_kwh,self_consumption_kwh,estimated_savings_brl,weather_condition,expected_generation_kwh\n"
WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


class DataProcessor:
    def __init__(self, config_path, history_path):
        self.config_path = config_path
        self.history_path = history_path
        self.config = self._load_config()
        self.last_snapshot = {}
        self.last_dashboard = self._blank_dashboard()
        self.last_update_ts = 0
        self.fault = None
        self._hour_state = None
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
        }

    def register_fault(self, title, detail=""):
        self.fault = {"title": title, "detail": detail, "ts": int(time.time())}

    def ingest_snapshot(self, snapshot, now_ts=None):
        ts = int(now_ts if now_ts is not None else snapshot.get("timestamp", time.time()))
        self.last_snapshot = dict(snapshot)
        self.last_update_ts = ts
        self.fault = None
        indicators = self._compute_indicators(snapshot, ts)
        self._update_hourly_history(indicators, ts)
        history_rows = self.history_last_days(35)
        history_views = self._history_views(history_rows)
        alerts = self._build_alerts(indicators, ts)
        reports = self._build_reports(indicators, history_rows)
        compare = self._build_compare(history_rows)
        profile = self._build_profile(indicators, history_rows)
        simplified = self._build_simplified(indicators, alerts, reports, profile)
        technical = self._build_technical(indicators, snapshot)
        self.last_dashboard = {
            "indicators": indicators,
            "alerts": alerts,
            "profile": profile,
            "reports": reports,
            "compare": compare,
            "technical": technical,
            "simplified": simplified,
            "history": history_views,
        }

    def _compute_indicators(self, snapshot, ts):
        generation = max(float(snapshot.get("daily_gen_kwh", 0.0)), 0.0)
        load_kw = max(float(snapshot.get("load_power_w", 0.0)) / 1000.0, 0.0)
        pv_kw = max(float(snapshot.get("instant_total_w", 0.0)) / 1000.0, 0.0)
        export_kw = max(float(snapshot.get("export_power_w", 0.0)) / 1000.0, 0.0)
        import_kw = max(float(snapshot.get("import_power_w", 0.0)) / 1000.0, 0.0)
        expected_kw = max(float(snapshot.get("expected_generation_w", 0.0)) / 1000.0, 0.0)

        consumed_direct = max(min(pv_kw, load_kw), 0.0)
        consumo_dia = max(generation * 0.55 + load_kw * 0.35, consumed_direct)
        exportado_dia = max(generation - consumo_dia, 0.0)
        importado_dia = max(consumo_dia + exportado_dia - generation, 0.0)
        autoconsumo = (consumo_dia / generation * 100.0) if generation > 0 else 0.0
        autossuficiencia = (consumed_direct / load_kw * 100.0) if load_kw > 0 else 0.0
        aproveitamento = (max(generation - exportado_dia, 0.0) / generation * 100.0) if generation > 0 else 0.0
        performance_ratio = (pv_kw / expected_kw) if expected_kw > 0 else (1.0 if pv_kw > 0 else 0.0)
        performance_ratio = min(max(performance_ratio, 0.0), 1.6)
        diff_pct = ((pv_kw - expected_kw) / expected_kw * 100.0) if expected_kw > 0 else 0.0
        economy_daily = consumo_dia * float(self.config.get("tarifa_kwh", 0.92))

        history_rows = self.history_last_days(35)
        sums7 = self._sum_rows(history_rows[-7 * 24 :])
        current_month = self._sum_period(history_rows, "month")
        current_year = self._sum_period(history_rows, "year")
        economy_week = sums7["consumo_kwh"] * float(self.config.get("tarifa_kwh", 0.92))
        economy_month = current_month["consumo_kwh"] * float(self.config.get("tarifa_kwh", 0.92))
        economy_year = current_year["consumo_kwh"] * float(self.config.get("tarifa_kwh", 0.92))
        projected = economy_month * max(int(self.config.get("projection_factor_year", 30)), 1)

        peaks = self._peak_from_rows(history_rows)
        return {
            "timestamp": ts,
            "weather_label": snapshot.get("weather_label", "não informado"),
            "geracao_kwh": round(generation, 2),
            "consumo_kwh": round(consumo_dia, 2),
            "exportado_kwh": round(exportado_dia, 2),
            "importado_kwh": round(importado_dia, 2),
            "autoconsumo_pct": round(autoconsumo, 1),
            "autossuficiencia_pct": round(autossuficiencia, 1),
            "aproveitamento_solar_pct": round(aproveitamento, 1),
            "economia_diaria_rs": round(economy_daily, 2),
            "economia_semanal_rs": round(economy_week, 2),
            "economia_mensal_rs": round(economy_month, 2),
            "economia_anual_rs": round(economy_year, 2),
            "projecao_economia_rs": round(projected, 2),
            "potencia_atual_kw": round(pv_kw, 2),
            "consumo_atual_kw": round(load_kw, 2),
            "importacao_atual_kw": round(import_kw, 2),
            "exportacao_atual_kw": round(export_kw, 2),
            "geracao_esperada_kw": round(expected_kw, 2),
            "diferenca_geracao_pct": round(diff_pct, 1),
            "performance_ratio": round(performance_ratio, 2),
            "pico_geracao_kw": round(max(peaks["generation_kw"], pv_kw), 2),
            "pico_consumo_kw": round(max(peaks["consumption_kw"], load_kw), 2),
            "status": self._status_from_pr(performance_ratio),
            "hourly": self._hourly_curve(snapshot),
            "status_text": self._status_text(performance_ratio, diff_pct),
        }

    @staticmethod
    def _status_from_pr(pr):
        if pr >= 0.85:
            return "NORMAL"
        if pr >= 0.6:
            return "ATENCAO"
        return "CRITICO"

    @staticmethod
    def _status_text(pr, diff_pct):
        if pr >= 0.85:
            return "Sistema funcionando normalmente"
        if pr >= 0.6:
            return "Sistema com desempenho abaixo do esperado"
        return "Sistema exige atenção imediata"

    def _build_alerts(self, indicators, ts):
        alerts = []
        if indicators["diferenca_geracao_pct"] <= -float(self.config.get("alert_generation_gap_pct", 15)):
            alerts.append({
                "severity": "atencao",
                "title": "Geração abaixo do esperado",
                "message": "A geração de hoje está abaixo do esperado para o horário atual.",
            })
        hour = time.localtime(ts).tm_hour
        if (hour >= 19 or hour <= 5) and indicators["importacao_atual_kw"] >= float(self.config.get("alert_night_import_kw", 1.2)):
            alerts.append({
                "severity": "atencao",
                "title": "Consumo noturno elevado",
                "message": "O consumo noturno está alto e depende bastante da rede elétrica.",
            })
        if self.last_update_ts and ts - self.last_update_ts > 20:
            alerts.append({
                "severity": "critico",
                "title": "Sem atualização recente",
                "message": "Não houve atualização recente dos dados. Verifique a comunicação do sistema.",
            })
        if self.fault is not None:
            alerts.append({
                "severity": "critico",
                "title": self.fault["title"],
                "message": self.fault.get("detail", "Falha de comunicação com o sistema."),
            })
        if indicators["potencia_atual_kw"] < 0.05 and indicators["geracao_esperada_kw"] > 0.8:
            alerts.append({
                "severity": "critico",
                "title": "Comportamento anormal",
                "message": "Havia expectativa de geração, mas a potência medida está muito baixa.",
            })
        if not alerts:
            alerts.append({
                "severity": "informativo",
                "title": "Operação estável",
                "message": "Nenhum alerta crítico foi identificado neste momento.",
            })
        return alerts

    def _build_reports(self, indicators, history_rows):
        last7 = self._sum_rows(history_rows[-7 * 24 :])
        daily = (
            "Hoje o sistema gerou {g:.2f} kWh. Desse total, {c:.2f} kWh foram aproveitados pela residência, "
            "{e:.2f} kWh foram exportados para a rede e a economia estimada chegou a R$ {rs:.2f}."
        ).format(
            g=indicators["geracao_kwh"],
            c=indicators["consumo_kwh"],
            e=indicators["exportado_kwh"],
            rs=indicators["economia_diaria_rs"],
        )
        weekly = (
            "Na última semana, o sistema fotovoltaico gerou {g:.2f} kWh. Desse total, {c:.2f} kWh foram consumidos "
            "diretamente pela residência, enquanto {e:.2f} kWh foram exportados para a rede. A economia estimada no período foi de R$ {rs:.2f}."
        ).format(
            g=last7["geracao_kwh"],
            c=last7["consumo_kwh"],
            e=last7["exportado_kwh"],
            rs=last7["consumo_kwh"] * float(self.config.get("tarifa_kwh", 0.92)),
        )
        return {"daily": daily, "weekly": weekly}

    def _build_compare(self, history_rows):
        today = self._sum_period(history_rows, "day")
        yesterday = self._sum_previous_day(history_rows)
        this_week = self._sum_period(history_rows, "week")
        last_week = self._sum_previous_week(history_rows)
        this_month = self._sum_period(history_rows, "month")
        last_month = self._sum_previous_month(history_rows)
        return {
            "today_vs_yesterday": self._compare_block(today, yesterday),
            "week_vs_previous": self._compare_block(this_week, last_week),
            "month_vs_previous": self._compare_block(this_month, last_month),
        }

    def _build_profile(self, indicators, history_rows):
        night_import = 0.0
        solar_use = 0.0
        for row in history_rows:
            hour = time.localtime(row["timestamp"]).tm_hour
            imported = max(row["consumo_kwh"] - max(row["geracao_kwh"] - row["exportado_kwh"], 0.0), 0.0)
            if hour >= 18 or hour <= 5:
                night_import += imported
            if 9 <= hour <= 16:
                solar_use += min(row["consumo_kwh"], row["geracao_kwh"])
        recommendations = []
        if night_import > solar_use * 0.55:
            recommendations.append("Priorize o uso de máquinas, ferro e chuveiro em horários com maior geração solar.")
        else:
            recommendations.append("Seu perfil de consumo já aproveita bem o período de maior geração solar.")
        recommendations.append("Seu perfil de consumo indica maior dependência da rede no período noturno." if night_import > 1.0 else "A dependência da rede no período noturno está sob controle.")
        label = "Maior consumo à noite" if night_import > solar_use else "Boa aderência ao período solar"
        return {
            "label": label,
            "night_import_kwh": round(night_import, 2),
            "solar_use_kwh": round(solar_use, 2),
            "recommendations": recommendations,
            "summary": "O perfil residencial mostra {}.".format(label.lower()),
        }

    def _build_simplified(self, indicators, alerts, reports, profile):
        messages = [
            "Hoje sua residência aproveitou {:.1f}% da energia produzida pelo sistema solar.".format(indicators["autoconsumo_pct"]),
            "Seu consumo noturno continua dependente da rede elétrica." if profile["night_import_kwh"] > 1.0 else "A dependência da rede durante a noite está moderada.",
            "A economia estimada do dia foi de R$ {:.2f}.".format(indicators["economia_diaria_rs"]),
            "Hoje a geração ficou {:.1f}% abaixo do esperado.".format(abs(indicators["diferenca_geracao_pct"])) if indicators["diferenca_geracao_pct"] < 0 else "O sistema teve desempenho compatível com a geração esperada.",
        ]
        return {
            "headline": alerts[0]["title"],
            "status_text": indicators["status_text"],
            "messages": messages,
            "daily_report": reports["daily"],
            "weekly_report": reports["weekly"],
        }

    def _build_technical(self, indicators, snapshot):
        return {
            "dc_voltage_v": snapshot.get("tensao_dc_v", 0),
            "pv_power_w": snapshot.get("potencia_instantanea_w", 0),
            "load_power_w": snapshot.get("load_power_w", 0),
            "import_power_w": snapshot.get("import_power_w", 0),
            "export_power_w": snapshot.get("export_power_w", 0),
            "performance_ratio": indicators["performance_ratio"],
            "weather": indicators["weather_label"],
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

    def _update_hourly_history(self, indicators, ts):
        cur_hour = self._hour_key(ts)
        if self._hour_state is None:
            self._hour_state = {"hour": cur_hour, "data": indicators, "last_ts": ts}
            return
        if cur_hour != self._hour_state["hour"]:
            prev = self._hour_state["data"]
            self._append_history_row(self._hour_state["last_ts"], prev["geracao_kwh"], prev["consumo_kwh"], prev["exportado_kwh"])
            self._hour_state = {"hour": cur_hour, "data": indicators, "last_ts": ts}
        else:
            self._hour_state["data"] = indicators
            self._hour_state["last_ts"] = ts

    def _append_history_row(self, timestamp, geracao_kwh, consumo_kwh, exportado_kwh):
        importado = max(consumo_kwh - max(geracao_kwh - exportado_kwh, 0.0), 0.0)
        autoconsumo = max(consumo_kwh - importado, 0.0)
        economia = autoconsumo * float(self.config.get("tarifa_kwh", 0.92))
        expected = geracao_kwh
        line = "{},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},,{:.3f}\n".format(int(timestamp), geracao_kwh, consumo_kwh, exportado_kwh, geracao_kwh, consumo_kwh, importado, exportado_kwh, autoconsumo, economia, expected)
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(line)
        self._enforce_history_flash_limit()

    def _enforce_history_flash_limit(self):
        max_bytes = int(self.config.get("history_max_bytes", 524288))
        if os.stat(self.history_path).st_size <= max_bytes:
            return
        with open(self.history_path, "r", encoding="utf-8") as f:
            rows = f.readlines()
        while len(rows) > 2 and len("".join(rows).encode("utf-8")) > max_bytes:
            rows.pop(1)
        with open(self.history_path, "w", encoding="utf-8") as f:
            f.write("".join(rows))

    def history_last_days(self, days=7):
        days = max(1, int(days))
        cutoff = int(time.time()) - days * 86400
        if not self._exists(self.history_path):
            return []
        rows = []
        with open(self.history_path, "r", encoding="utf-8") as f:
            _ = f.readline()
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 4:
                    continue
                ts = int(parts[0])
                if ts >= cutoff:
                    rows.append({
                        "timestamp": ts,
                        "geracao_kwh": float(parts[1]),
                        "consumo_kwh": float(parts[2]),
                        "exportado_kwh": float(parts[3]),
                    })
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
                year_week = time.strftime("%Y-W%W", lt)
                key = year_week
                label = year_week
            else:
                key = (lt.tm_year, lt.tm_mon)
                label = MONTHS[lt.tm_mon - 1]
            block = buckets.setdefault(key, {"label": label, "geracao_kwh": 0.0, "consumo_kwh": 0.0, "exportado_kwh": 0.0})
            block["geracao_kwh"] += row["geracao_kwh"]
            block["consumo_kwh"] += row["consumo_kwh"]
            block["exportado_kwh"] += row["exportado_kwh"]
        return list(buckets.values())

    def _sum_rows(self, rows):
        total = {"geracao_kwh": 0.0, "consumo_kwh": 0.0, "exportado_kwh": 0.0}
        for row in rows:
            total["geracao_kwh"] += row["geracao_kwh"]
            total["consumo_kwh"] += row["consumo_kwh"]
            total["exportado_kwh"] += row["exportado_kwh"]
        return total

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
        now = time.localtime(time.time() - 86400)
        return self._sum_rows([r for r in rows if (time.localtime(r["timestamp"]).tm_year, time.localtime(r["timestamp"]).tm_mon, time.localtime(r["timestamp"]).tm_mday) == (now.tm_year, now.tm_mon, now.tm_mday)])

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
        current_gen = current["geracao_kwh"]
        previous_gen = previous["geracao_kwh"]
        delta = current_gen - previous_gen
        pct = (delta / previous_gen * 100.0) if previous_gen > 0 else 0.0
        return {
            "current_kwh": round(current_gen, 2),
            "previous_kwh": round(previous_gen, 2),
            "delta_kwh": round(delta, 2),
            "delta_pct": round(pct, 1),
        }

    def _peak_from_rows(self, rows):
        peak_gen = 0.0
        peak_cons = 0.0
        for row in rows[-48:]:
            peak_gen = max(peak_gen, row["geracao_kwh"])
            peak_cons = max(peak_cons, row["consumo_kwh"])
        return {"generation_kw": peak_gen, "consumption_kw": peak_cons}

    def _hourly_curve(self, snapshot):
        pv = max(snapshot.get("instant_total_w", 0.0), 0.0)
        load = max(snapshot.get("load_power_w", 0.0), 0.0)
        values = {}
        for h in range(24):
            sun_factor = max(0.0, 1.0 - ((h - 12) / 7.0) ** 2)
            load_factor = 0.55 if 8 <= h <= 17 else 1.1
            values[str(h)] = {
                "generation_w": round(pv * sun_factor, 0),
                "consumption_w": round(load * load_factor, 0),
            }
        return values

    def _history_views(self, rows):
        return {
            "daily": self.history_period(7, "daily"),
            "weekly": self.history_period(35, "weekly"),
            "monthly": self.history_period(365, "monthly"),
            "raw": rows[-24 * 7 :],
        }

    def payload(self):
        return {
            "config": self.config,
            "snapshot": self.last_snapshot,
            "dashboard": self.last_dashboard,
            "fault": self.fault,
            "updated_at": self.last_update_ts,
        }

    def summary(self, period="daily"):
        return {"period": period, "text": self.last_dashboard.get("reports", {}).get(period, "Sem dados suficientes.")}

    def indicators(self):
        return self.last_dashboard.get("indicators", {})

    def alerts(self):
        return self.last_dashboard.get("alerts", [])

    def profile(self):
        return self.last_dashboard.get("profile", {})

    def compare(self):
        return self.last_dashboard.get("compare", {})

    def dashboard(self, days=7, bucket="daily"):
        data = dict(self.payload())
        data["history_filtered"] = self.history_period(days, bucket)
        return data
