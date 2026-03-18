"""Processamento energético, painel técnico e alarmes estruturados do CleanSun."""
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
            "status": {},
        }

    def register_fault(self, title, detail=""):
        self.fault = {"title": title, "detail": detail, "ts": int(time.time())}

    def ingest_snapshot(self, snapshot, now_ts=None):
        ts = int(now_ts if now_ts is not None else snapshot.get("timestamp", time.time()))
        self.last_snapshot = dict(snapshot)
        self.last_update_ts = ts
        indicators = self._compute_indicators(snapshot)
        technical = self._build_technical(snapshot, indicators)
        self._update_hourly_history(indicators, technical, ts)
        history_rows = self.history_last_days(35)
        alerts = self._build_alerts(snapshot, indicators, technical, history_rows, ts)
        reports = self._build_reports(indicators, history_rows)
        compare = self._build_compare(history_rows)
        profile = self._build_profile(history_rows)
        self.last_dashboard = {
            "indicators": indicators,
            "alerts": alerts,
            "profile": profile,
            "reports": reports,
            "compare": compare,
            "technical": technical,
            "simplified": self._build_simplified(indicators, alerts, reports, profile),
            "history": self._history_views(history_rows),
            "status": self._build_status(snapshot, indicators, alerts, ts),
        }

    def _compute_indicators(self, snapshot):
        generation = max(float(snapshot.get("daily_gen_kwh", 0.0)), 0.0)
        load_kw = max(float(snapshot.get("load_power_w", 0.0)) / 1000.0, 0.0)
        ac_kw = max(float(snapshot.get("ac_power_w", snapshot.get("instant_total_w", 0.0))) / 1000.0, 0.0)
        dc_kw = max(float(snapshot.get("dc_power_w", snapshot.get("instant_total_w", 0.0))) / 1000.0, 0.0)
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
        weekly = self._sum_rows(history_rows[-7 * 24 :])
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
            "diagnostics": {
                "communication_status": snapshot.get("communication_status", "Desconhecido"),
                "grid_status": snapshot.get("grid_status", "Desconhecido"),
                "operational_status": snapshot.get("inverter_status", "Desconhecido"),
                "status_code": snapshot.get("status_code", -1),
            },
        }

    def _add_alarm(self, alarms, code, severity, title, technical_description, user_message, recommended_action, ts, active=True):
        alarms.append({
            "code": code,
            "severity": severity,
            "title": title,
            "technical_description": technical_description,
            "user_message": user_message,
            "recommended_action": recommended_action,
            "timestamp": ts,
            "active": active,
        })

    def _build_alerts(self, snapshot, indicators, technical, history_rows, ts):
        alarms = []
        dc = technical["dc_input"]
        ac = technical["ac_output"]
        grid = technical["grid"]
        inverter = technical["inverter"]
        energy = technical["energy"]
        diag = technical["diagnostics"]

        if indicators["diferenca_geracao_pct"] <= -float(self.config.get("alert_generation_gap_pct", 15)):
            self._add_alarm(alarms, "GEN_LOW", "atencao", "Geração abaixo do esperado", "Geração real abaixo da curva estimada para o horário.", "O sistema está gerando menos energia do que o esperado neste momento.", "Verificar sombreamento, sujeira nos módulos ou condições climáticas.", ts)
        if dc["mppt1_voltage_v"] < 180 or dc["mppt2_voltage_v"] < 180:
            self._add_alarm(alarms, "DC_LOW_VOLT", "atencao", "Tensão DC baixa", "Uma das entradas DC está abaixo da faixa típica de operação.", "Uma das strings solares pode estar com tensão abaixo do ideal.", "Verificar string, conectores e possível sombreamento excessivo.", ts)
        if (dc["mppt1_current_a"] < 0.4 and indicators["geracao_esperada_kw"] > 0.8) or (dc["mppt2_current_a"] < 0.4 and indicators["geracao_esperada_kw"] > 0.8):
            self._add_alarm(alarms, "DC_CURR_ABN", "atencao", "Corrente DC anormal", "Corrente de entrada DC muito baixa em relação ao horário e irradiância estimada.", "O sistema solar não está puxando corrente como deveria.", "Verificar string, cabos DC, fusíveis e sombreamento.", ts)
        if grid["grid_voltage_v"] and (grid["grid_voltage_v"] < 195 or grid["grid_voltage_v"] > 245):
            self._add_alarm(alarms, "AC_VOLT_OUT", "critico", "Tensão AC fora da faixa", "A tensão da rede está fora da faixa operacional esperada.", "A rede elétrica está com tensão inadequada para operação ideal do inversor.", "Verificar a instalação e, se persistir, acionar a concessionária.", ts)
        if grid["frequency_hz"] and abs(grid["frequency_hz"] - 60.0) > 0.3:
            self._add_alarm(alarms, "GRID_FREQ", "atencao", "Frequência da rede fora da faixa", "A frequência medida está fora da faixa usual de 60 Hz.", "A rede pode estar instável neste momento.", "Acompanhar a estabilidade da rede e verificar se o evento persiste.", ts)
        if diag["communication_status"] != "Online" or self.fault is not None:
            self._add_alarm(alarms, "COMM_FAIL", "critico", "Falha de comunicação", "Não houve atualização confiável dos dados ou a comunicação foi perdida.", "Os dados podem estar desatualizados porque o sistema perdeu comunicação.", "Verificar módulo Wi-Fi, cabo serial e alimentação do módulo.", ts)
        if inverter["status"] in ("Falha", "Desconectado"):
            self._add_alarm(alarms, "INV_FAULT", "critico", "Inversor em falha", "O estado operacional do inversor indica falha, standby indevido ou desconexão.", "O inversor não está operando normalmente.", "Verificar o código de falha e reiniciar o equipamento se seguro.", ts)
        if inverter["temperature_c"] >= 62:
            self._add_alarm(alarms, "TEMP_HIGH", "critico", "Temperatura elevada do inversor", "Temperatura interna acima da faixa segura de operação.", "O inversor está aquecido demais.", "Melhorar ventilação, checar obstruções e reduzir exposição térmica se possível.", ts)
        if inverter["efficiency_percent"] and inverter["efficiency_percent"] < 92.0:
            self._add_alarm(alarms, "EFF_LOW", "atencao", "Baixa eficiência do inversor", "Diferença excessiva entre potência DC e potência AC do inversor.", "Parte relevante da energia está se perdendo na conversão.", "Verificar aquecimento, cabos, configurações e eventual limitação do inversor.", ts)
        if (time.localtime(ts).tm_hour >= 19 or time.localtime(ts).tm_hour <= 5) and indicators["importacao_atual_kw"] >= float(self.config.get("alert_night_import_kw", 1.2)):
            self._add_alarm(alarms, "LOAD_NIGHT", "atencao", "Consumo elevado sem geração solar", "Consumo noturno alto com dependência significativa da rede.", "A residência está puxando muita energia da rede fora do período solar.", "Priorizar cargas pesadas no período de maior geração.", ts)
        if indicators["importacao_atual_kw"] > max(indicators["potencia_atual_kw"] * 1.2, 1.5):
            self._add_alarm(alarms, "GRID_IMPORT_HIGH", "atencao", "Importação excessiva da rede", "A potência importada da rede está muito acima da contribuição solar no momento.", "A instalação está consumindo muito mais da concessionária do que do solar.", "Avaliar deslocamento de cargas para o período solar e revisar o perfil de consumo.", ts)
        if indicators["potencia_atual_kw"] > 2.5 and indicators["exportacao_atual_kw"] < 0.1 and indicators["autoconsumo_pct"] < 30:
            self._add_alarm(alarms, "LOW_EXPORT", "atencao", "Exportação anormalmente baixa", "Há alta geração, mas a exportação está muito baixa em relação ao esperado.", "Pode haver limitação, consumo instantâneo elevado ou inconsistência de medição.", "Verificar medição, perfil de consumo e eventual limitação de injeção.", ts)
        if abs(dc["mppt1_power_kw"] - dc["mppt2_power_kw"]) > max(0.7, 0.35 * max(dc["mppt1_power_kw"], dc["mppt2_power_kw"], 0.1)):
            self._add_alarm(alarms, "MPPT_IMBALANCE", "atencao", "Desbalanceamento entre strings", "Diferença significativa entre a potência dos dois MPPTs/strings.", "Uma das entradas solares está rendendo bem menos que a outra.", "Verificar sombreamento, sujeira, conectores ou defeito em uma string.", ts)
        if 8 <= time.localtime(ts).tm_hour <= 15 and indicators["geracao_esperada_kw"] > 1.0 and indicators["potencia_atual_kw"] < 0.05:
            self._add_alarm(alarms, "NO_GEN_DAY", "critico", "Ausência de geração em horário esperado", "O sistema não iniciou geração mesmo em período diurno favorável.", "O sistema deveria estar gerando, mas permanece sem produção.", "Verificar disjuntor, strings, status do inversor e presença de rede.", ts)
        previous_peak = self._peak_from_rows(history_rows)
        if previous_peak["generation_kw"] > 0 and indicators["potencia_atual_kw"] < previous_peak["generation_kw"] * 0.35 and indicators["geracao_esperada_kw"] > 1.5:
            self._add_alarm(alarms, "POWER_DROP", "atencao", "Queda brusca de potência", "A potência atual caiu abruptamente em relação ao comportamento recente.", "A geração caiu rápido demais para o horário atual.", "Investigar nuvens densas, sombreamento súbito ou falha parcial.", ts)
        if indicators["diferenca_geracao_pct"] < -28:
            self._add_alarm(alarms, "SOILING_SHADE", "atencao", "Possível sombreamento ou sujeira", "A produção permanece consistentemente abaixo do esperado.", "Pode haver sombreamento ou sujeira reduzindo a produção solar.", "Inspecionar módulos, árvores, antenas e sujeira acumulada.", ts)
        day_sum = self._sum_period(history_rows, "day")
        if day_sum["geracao_kwh"] and day_sum["geracao_kwh"] < max(self._daily_average(history_rows) * 0.45, 1.0):
            self._add_alarm(alarms, "DAY_LOW_ENERGY", "atencao", "Energia diária muito baixa", "A energia acumulada do dia está incompatível com o histórico recente.", "A produção diária está abaixo do padrão da instalação.", "Comparar clima do dia com dias anteriores e inspecionar o sistema.", ts)
        if grid["grid_status"] == "Indisponível":
            self._add_alarm(alarms, "GRID_DOWN", "critico", "Rede indisponível", "O inversor detectou ausência de rede e não pode injetar energia.", "A rede elétrica está indisponível ou desconectada.", "Verificar disjuntor geral, rede da concessionária e proteções AC.", ts)
        if not alarms:
            self._add_alarm(alarms, "INFO_OK", "informativo", "Operação estável", "Nenhuma condição técnica crítica foi detectada.", "A instalação opera dentro do comportamento esperado.", "Seguir monitorando normalmente.", ts)
        return alarms

    def _build_reports(self, indicators, history_rows):
        week = self._sum_rows(history_rows[-7 * 24 :])
        return {
            "daily": "Hoje o sistema gerou {:.2f} kWh, exportou {:.2f} kWh e a economia estimada foi de R$ {:.2f}.".format(indicators["geracao_kwh"], indicators["exportado_kwh"], indicators["economia_diaria_rs"]),
            "weekly": "Na última semana o sistema gerou {:.2f} kWh, com {:.2f} kWh consumidos diretamente e {:.2f} kWh exportados para a rede.".format(week["geracao_kwh"], week["consumo_kwh"], week["exportado_kwh"]),
        }

    def _build_profile(self, history_rows):
        night_import = 0.0
        for row in history_rows:
            if time.localtime(row["timestamp"]).tm_hour >= 18 or time.localtime(row["timestamp"]).tm_hour <= 5:
                night_import += max(row["consumo_kwh"] - max(row["geracao_kwh"] - row["exportado_kwh"], 0.0), 0.0)
        recs = ["Priorize máquinas, ferro e chuveiro em horários com maior geração solar."]
        if night_import > 4:
            recs.append("Seu perfil de consumo indica maior dependência da rede no período noturno.")
        return {"night_import_kwh": round(night_import, 2), "recommendations": recs}

    def _build_simplified(self, indicators, alerts, reports, profile):
        return {
            "headline": alerts[0]["title"],
            "status_text": indicators["status_text"],
            "messages": [
                "Hoje sua residência aproveitou {:.1f}% da energia produzida pelo sistema solar.".format(indicators["autoconsumo_pct"]),
                "A economia estimada do dia foi de R$ {:.2f}.".format(indicators["economia_diaria_rs"]),
                "Seu consumo noturno continua dependente da rede elétrica." if profile["night_import_kwh"] > 1.0 else "A dependência da rede no período noturno está controlada.",
                "Hoje a geração ficou {:.1f}% abaixo do esperado.".format(abs(indicators["diferenca_geracao_pct"])) if indicators["diferenca_geracao_pct"] < 0 else "A geração está compatível com o esperado para o horário.",
            ],
            "daily_report": reports["daily"],
            "weekly_report": reports["weekly"],
        }

    def _build_compare(self, history_rows):
        return {
            "today_vs_yesterday": self._compare_block(self._sum_period(history_rows, "day"), self._sum_previous_day(history_rows)),
            "week_vs_previous": self._compare_block(self._sum_period(history_rows, "week"), self._sum_previous_week(history_rows)),
            "month_vs_previous": self._compare_block(self._sum_period(history_rows, "month"), self._sum_previous_month(history_rows)),
        }

    def _build_status(self, snapshot, indicators, alerts, ts):
        return {
            "operational_state": snapshot.get("inverter_status", "Desconhecido"),
            "communication_status": snapshot.get("communication_status", "Desconhecido"),
            "grid_status": snapshot.get("grid_status", "Desconhecido"),
            "status_text": indicators["status_text"],
            "active_alarm_count": len([a for a in alerts if a["active"]]),
            "updated_at": ts,
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

    def _daily_average(self, rows):
        daily = self.history_period(14, "daily")
        if not daily:
            return 0.0
        return sum(item["geracao_kwh"] for item in daily) / len(daily)

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

    def payload(self):
        return {"config": self.config, "snapshot": self.last_snapshot, "dashboard": self.last_dashboard, "updated_at": self.last_update_ts, "fault": self.fault}

    def indicators(self):
        return self.last_dashboard.get("indicators", {})

    def alerts(self):
        return self.last_dashboard.get("alerts", [])

    def profile(self):
        return self.last_dashboard.get("profile", {})

    def compare(self):
        return self.last_dashboard.get("compare", {})

    def technical(self):
        return self.last_dashboard.get("technical", {})

    def status(self):
        return self.last_dashboard.get("status", {})

    def summary(self, period="daily"):
        return {"period": period, "text": self.last_dashboard.get("reports", {}).get(period, "Sem dados suficientes.")}

    def dashboard(self, days=7, bucket="daily"):
        data = dict(self.payload())
        data["history_filtered"] = self.history_period(days, bucket)
        return data
