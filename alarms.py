"""Motor de alarmes e diagnóstico fotovoltaico do CleanSun."""
import time

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


class AlarmEngine:
    """Avalia telemetria e gera alarmes técnicos/simplificados com persistência."""

    def __init__(self, config):
        self.config = config
        self._persistence = {}
        self._last_active = set()
        self.history = []

    def _persist(self, code, condition, minimum_samples=1):
        count = self._persistence.get(code, 0)
        count = count + 1 if condition else 0
        self._persistence[code] = count
        return count >= max(1, minimum_samples)

    @staticmethod
    def _alarm(code, category, severity, title, technical_description, simplified_message, probable_causes,
               recommended_action, timestamp, source, affected_component, active=True):
        return {
            "code": code,
            "category": category,
            "severity": severity,
            "title": title,
            "technical_description": technical_description,
            "simplified_message": simplified_message,
            "probable_causes": probable_causes,
            "recommended_action": recommended_action,
            "timestamp": timestamp,
            "active": active,
            "source": source,
            "affected_component": affected_component,
        }

    def _push(self, alarms, **kwargs):
        alarms.append(self._alarm(**kwargs))

    @staticmethod
    def _avg(values):
        return sum(values) / len(values) if values else 0.0

    def evaluate(self, snapshot, indicators, technical, history_rows, ts, fault=None, updated_at=None):
        alarms = []
        dc = technical.get("dc_input", {})
        ac = technical.get("ac_output", {})
        grid = technical.get("grid", {})
        inverter = technical.get("inverter", {})
        diagnostics = technical.get("diagnostics", {})
        now = int(time.time())
        updated_at = int(updated_at or ts)
        expected_kw = float(indicators.get("geracao_esperada_kw", 0.0))
        power_kw = float(indicators.get("potencia_atual_kw", 0.0))
        import_kw = float(indicators.get("importacao_atual_kw", 0.0))
        export_kw = float(indicators.get("exportacao_atual_kw", 0.0))
        dc_power_kw = float(dc.get("dc_power_kw", 0.0))
        mppt1_kw = float(dc.get("mppt1_power_kw", 0.0))
        mppt2_kw = float(dc.get("mppt2_power_kw", 0.0))
        mppt1_a = float(dc.get("mppt1_current_a", 0.0))
        mppt2_a = float(dc.get("mppt2_current_a", 0.0))
        mppt1_v = float(dc.get("mppt1_voltage_v", 0.0))
        mppt2_v = float(dc.get("mppt2_voltage_v", 0.0))
        inv_temp = float(inverter.get("temperature_c", 0.0))
        efficiency = float(inverter.get("efficiency_percent", 0.0))
        freq = float(grid.get("frequency_hz", 0.0))
        grid_v = float(grid.get("grid_voltage_v", 0.0))
        hour = time.localtime(ts).tm_hour
        day_rows = [r for r in history_rows if time.localtime(r["timestamp"]).tm_mday == time.localtime(ts).tm_mday and time.localtime(r["timestamp"]).tm_mon == time.localtime(ts).tm_mon]
        recent_rows = history_rows[-12:]
        recent_generation = [float(r.get("geracao_kwh", 0.0)) for r in recent_rows]
        recent_consumption = [float(r.get("consumo_kwh", 0.0)) for r in recent_rows]
        daily_generation = sum(float(r.get("geracao_kwh", 0.0)) for r in day_rows)
        daily_avg = self._avg([float(r.get("geracao_kwh", 0.0)) for r in history_rows[-7 * 24:]])

        if self._persist("INV_DC_UNDERVOLTAGE", (mppt1_v < 160 or mppt2_v < 160) and expected_kw > 0.5, 2):
            self._push(alarms, code="INV_DC_UNDERVOLTAGE", category="entrada_dc", severity="warning", title="Subtensão na entrada DC",
                       technical_description="Uma ou mais entradas MPPT estão abaixo da faixa típica de operação para o nível de geração esperado.",
                       simplified_message="Uma parte do sistema solar está recebendo tensão abaixo do normal.",
                       probable_causes=["string com baixo número de módulos ativos", "conector DC com mau contato", "sombreamento acentuado"],
                       recommended_action="Verificar tensão das strings, conectores DC e sombreamento sobre os módulos.",
                       timestamp=ts, source="mppt1" if mppt1_v < mppt2_v else "mppt2", affected_component="string_1" if mppt1_v < mppt2_v else "string_2")

        if self._persist("INV_DC_OVERVOLTAGE", mppt1_v > 480 or mppt2_v > 480, 1):
            self._push(alarms, code="INV_DC_OVERVOLTAGE", category="entrada_dc", severity="critical", title="Sobretensão na entrada DC",
                       technical_description="A tensão DC simulada excedeu a faixa segura de entrada do inversor.",
                       simplified_message="O sistema detectou tensão solar acima do normal e requer atenção.",
                       probable_causes=["string superdimensionada", "falha de medição", "condição de circuito aberto"],
                       recommended_action="Inspecionar dimensionamento da string e integridade da medição DC antes de religar o sistema.",
                       timestamp=ts, source="inverter", affected_component="inversor")

        if self._persist("INV_DC_CURRENT_LOW", ((mppt1_a < 0.6) or (mppt2_a < 0.6)) and expected_kw > 1.0, 2):
            self._push(alarms, code="INV_DC_CURRENT_LOW", category="entrada_dc", severity="warning", title="Corrente DC abaixo do esperado",
                       technical_description="A corrente em uma das entradas DC está baixa para o nível de irradiância e horário simulados.",
                       simplified_message="Os painéis estão entregando menos corrente do que o esperado neste momento.",
                       probable_causes=["sombreamento parcial", "string desconectada", "sujeira", "fusível DC aberto"],
                       recommended_action="Comparar correntes entre strings, verificar conectores, fusíveis e sombreamento.",
                       timestamp=ts, source="mppt1" if mppt1_a < mppt2_a else "mppt2", affected_component="string_1" if mppt1_a < mppt2_a else "string_2")

        imbalance_ratio = abs(mppt1_kw - mppt2_kw) / max(max(mppt1_kw, mppt2_kw), 0.1)
        if self._persist("INV_DC_STRING_IMBALANCE", imbalance_ratio > 0.35 and expected_kw > 1.2, 3):
            self._push(alarms, code="INV_DC_STRING_IMBALANCE", category="entrada_dc", severity="warning", title="Desbalanceamento entre strings",
                       technical_description="Diferença persistente de potência entre MPPT1 e MPPT2 acima do limiar configurado.",
                       simplified_message="Um grupo de painéis está rendendo menos que o outro.",
                       probable_causes=["sombreamento localizado", "mismatch de módulos", "conexão frouxa", "falha em string"],
                       recommended_action="Comparar curvas das strings e inspecionar módulos, cabos e conectores da string menos produtiva.",
                       timestamp=ts, source="generation_model", affected_component="instalação")

        if self._persist("INV_NO_GENERATION_DAYLIGHT", 8 <= hour <= 15 and expected_kw > 1.0 and power_kw < 0.05, 2):
            self._push(alarms, code="INV_NO_GENERATION_DAYLIGHT", category="geração", severity="critical", title="Ausência de geração em horário diurno",
                       technical_description="O inversor não está entregando potência AC em período de geração esperada.",
                       simplified_message="O sistema deveria estar gerando energia agora, mas está parado.",
                       probable_causes=["inversor desligado", "falta de rede", "proteção aberta", "falha interna"],
                       recommended_action="Verificar status do inversor, proteções AC/DC e disponibilidade da rede.",
                       timestamp=ts, source="inverter", affected_component="inversor")

        if self._persist("INV_GENERATION_BELOW_EXPECTED", indicators.get("diferenca_geracao_pct", 0.0) <= -18, 2):
            self._push(alarms, code="INV_GENERATION_BELOW_EXPECTED", category="geração", severity="warning", title="Geração abaixo da curva esperada",
                       technical_description="A potência de saída está abaixo da curva estimada para o horário e condição simulada atual.",
                       simplified_message="O sistema está gerando menos energia do que o esperado neste momento.",
                       probable_causes=["sombreamento parcial", "sujeira nos módulos", "baixa irradiância", "redução de desempenho"],
                       recommended_action="Verificar clima, presença de sombra, sujeira nos módulos e comparação com o histórico recente.",
                       timestamp=ts, source="generation_model", affected_component="instalação")

        avg_recent = self._avg(recent_generation[:-1]) if len(recent_generation) > 1 else 0.0
        if self._persist("INV_POWER_DROP", avg_recent > 0 and power_kw < avg_recent * 0.45 and expected_kw > 1.0, 2):
            self._push(alarms, code="INV_POWER_DROP", category="geração", severity="warning", title="Queda brusca de potência",
                       technical_description="Houve redução acentuada da potência atual em relação às amostras recentes.",
                       simplified_message="A geração caiu rápido demais para o comportamento esperado.",
                       probable_causes=["nuvem densa", "sombras súbitas", "limitação do inversor", "falha parcial de string"],
                       recommended_action="Observar persistência do evento e comparar com tensão, corrente e clima atual.",
                       timestamp=ts, source="inverter", affected_component="instalação")

        if self._persist("INV_LOW_EFFICIENCY", dc_power_kw > 0.6 and efficiency < 92.0, 2):
            self._push(alarms, code="INV_LOW_EFFICIENCY", category="eficiência", severity="warning", title="Baixa eficiência do inversor",
                       technical_description="A relação entre potência DC e potência AC está abaixo da faixa aceitável para a condição atual.",
                       simplified_message="Parte da energia está se perdendo na conversão do inversor.",
                       probable_causes=["aquecimento excessivo", "limitação eletrônica", "cabeamento", "falha de medição"],
                       recommended_action="Comparar potência DC/AC, temperatura interna e ventilação do inversor.",
                       timestamp=ts, source="inverter", affected_component="inversor")

        if self._persist("INV_OVER_TEMPERATURE", inv_temp >= 62.0, 2):
            self._push(alarms, code="INV_OVER_TEMPERATURE", category="temperatura", severity="critical", title="Temperatura elevada do inversor",
                       technical_description="A temperatura interna do inversor excedeu a faixa operacional segura.",
                       simplified_message="O inversor está aquecido demais e pode reduzir desempenho.",
                       probable_causes=["ventilação insuficiente", "sol excessivo sobre o equipamento", "obstrução de dissipação"],
                       recommended_action="Melhorar ventilação, remover obstruções e verificar local de instalação.",
                       timestamp=ts, source="inverter", affected_component="inversor")

        if self._persist("INV_FAULT_STATE", str(inverter.get("status", "")).lower() in ("falha", "fault", "trip", "shutdown", "desconectado", "offline"), 1):
            self._push(alarms, code="INV_FAULT_STATE", category="diagnóstico", severity="critical", title="Inversor em estado de falha",
                       technical_description="O estado operacional reportado pelo inversor indica falha, desligamento ou desconexão.",
                       simplified_message="O inversor informou um estado anormal e pode não estar operando corretamente.",
                       probable_causes=["falha interna", "falta de rede", "proteção acionada", "erro de inicialização"],
                       recommended_action="Consultar código de falha, registrar o evento e inspecionar proteções e estado da rede.",
                       timestamp=ts, source="inverter", affected_component="inversor")

        if self._persist("GRID_UNDERVOLTAGE", 0 < grid_v < 195, 2):
            self._push(alarms, code="GRID_UNDERVOLTAGE", category="rede", severity="warning", title="Subtensão da rede elétrica",
                       technical_description="A tensão da rede está abaixo da faixa operacional ideal para o inversor.",
                       simplified_message="A rede elétrica está com tensão abaixo do normal.",
                       probable_causes=["rede da concessionária instável", "queda de tensão local", "carga elevada na instalação"],
                       recommended_action="Medir tensão em campo e, se persistir, acionar a concessionária.",
                       timestamp=ts, source="grid", affected_component="rede elétrica")

        if self._persist("GRID_OVERVOLTAGE", grid_v > 245, 2):
            self._push(alarms, code="GRID_OVERVOLTAGE", category="rede", severity="critical", title="Sobretensão da rede elétrica",
                       technical_description="A tensão da rede está acima da faixa aceitável e pode provocar limitação ou desligamento do inversor.",
                       simplified_message="A rede elétrica está com tensão acima do normal.",
                       probable_causes=["elevação de tensão pela concessionária", "ajuste inadequado", "medição anômala"],
                       recommended_action="Conferir tensão na saída AC e registrar evidências para análise da concessionária.",
                       timestamp=ts, source="grid", affected_component="rede elétrica")

        if self._persist("GRID_FREQ_OUT_OF_RANGE", freq > 0 and abs(freq - 60.0) > 0.3, 2):
            self._push(alarms, code="GRID_FREQ_OUT_OF_RANGE", category="rede", severity="warning", title="Frequência da rede fora da faixa",
                       technical_description="A frequência medida está fora da janela operacional típica de 60 Hz.",
                       simplified_message="A rede elétrica está oscilando mais do que o normal.",
                       probable_causes=["instabilidade da concessionária", "gerador local", "erro de medição"],
                       recommended_action="Monitorar persistência e correlacionar com eventos de rede no local.",
                       timestamp=ts, source="grid", affected_component="rede elétrica")

        if self._persist("GRID_DISCONNECTED", grid.get("grid_status") == "Indisponível" or (grid_v == 0 and freq == 0), 1):
            self._push(alarms, code="GRID_DISCONNECTED", category="rede", severity="critical", title="Rede indisponível ou desconectada",
                       technical_description="O inversor não detecta presença válida da rede elétrica na entrada AC.",
                       simplified_message="A rede elétrica está indisponível e o sistema não consegue operar normalmente.",
                       probable_causes=["queda de energia", "disjuntor aberto", "cabos AC desconectados"],
                       recommended_action="Verificar alimentação AC, disjuntores e disponibilidade da rede da concessionária.",
                       timestamp=ts, source="grid", affected_component="rede elétrica")

        if self._persist("COMMUNICATION_TIMEOUT", diagnostics.get("communication_status") != "Online" or fault is not None, 1):
            self._push(alarms, code="COMMUNICATION_TIMEOUT", category="comunicação", severity="critical", title="Falha de comunicação",
                       technical_description="A telemetria do inversor ou do servidor local ficou indisponível ou inconsistente.",
                       simplified_message="O sistema perdeu comunicação com a origem dos dados.",
                       probable_causes=["módulo Wi-Fi offline", "serial desconectada", "erro de leitura", "travamento do serviço"],
                       recommended_action="Verificar conectividade, alimentação do módulo e logs do servidor local.",
                       timestamp=ts, source="communication", affected_component="servidor local")

        stale_seconds = max(0, now - updated_at)
        if self._persist("DATA_STALE", stale_seconds > int(self.config.get("data_stale_seconds", 20)), 1):
            self._push(alarms, code="DATA_STALE", category="diagnóstico", severity="warning", title="Dados desatualizados",
                       technical_description="O dashboard está exibindo dados com atraso além do limite configurado.",
                       simplified_message="As leituras exibidas podem estar antigas.",
                       probable_causes=["atraso no polling", "travamento do backend", "falha de comunicação"],
                       recommended_action="Verificar loop de aquisição, SSE e atualização do servidor local.",
                       timestamp=ts, source="server", affected_component="dashboard")

        if self._persist("NIGHT_HIGH_CONSUMPTION", (hour >= 19 or hour <= 5) and import_kw >= float(self.config.get("alert_night_import_kw", 1.2)), 2):
            self._push(alarms, code="NIGHT_HIGH_CONSUMPTION", category="consumo", severity="warning", title="Consumo elevado no período noturno",
                       technical_description="A potência importada da rede no período noturno está acima do padrão desejado.",
                       simplified_message="A casa está consumindo muita energia da rede à noite.",
                       probable_causes=["cargas pesadas fora do período solar", "chuveiro elétrico", "equipamentos permanentes"],
                       recommended_action="Mapear cargas noturnas e priorizar uso de cargas pesadas em horários solares.",
                       timestamp=ts, source="load_profile", affected_component="instalação")

        if self._persist("EXCESSIVE_GRID_IMPORT", import_kw > max(1.5, power_kw * 1.35), 2):
            self._push(alarms, code="EXCESSIVE_GRID_IMPORT", category="consumo", severity="warning", title="Importação excessiva da rede",
                       technical_description="A potência importada está muito acima da contribuição instantânea do sistema FV.",
                       simplified_message="A instalação está dependendo mais da rede do que do solar.",
                       probable_causes=["carga elevada", "baixa geração", "perfil de consumo inadequado"],
                       recommended_action="Avaliar deslocamento de cargas e revisar o perfil de consumo da residência.",
                       timestamp=ts, source="load_profile", affected_component="instalação")

        if self._persist("LOW_GRID_EXPORT_AT_PEAK", expected_kw > 2.5 and power_kw > 2.0 and export_kw < 0.15 and indicators.get("autoconsumo_pct", 0.0) < 35, 2):
            self._push(alarms, code="LOW_GRID_EXPORT_AT_PEAK", category="geração", severity="info", title="Baixa exportação em período de alta geração",
                       technical_description="Há geração significativa, mas pouca energia está sendo exportada para a rede em horário de pico solar.",
                       simplified_message="A maior parte da energia está sendo consumida internamente no pico solar.",
                       probable_causes=["consumo elevado em horário solar", "limitação de injeção", "medição com baixa resolução"],
                       recommended_action="Confirmar perfil de carga e verificar se existe limitação de exportação configurada.",
                       timestamp=ts, source="load_profile", affected_component="medição")

        if self._persist("DAILY_ENERGY_TOO_LOW", daily_generation > 0 and daily_generation < max(0.8, daily_avg * 0.45), 2):
            self._push(alarms, code="DAILY_ENERGY_TOO_LOW", category="geração", severity="warning", title="Energia diária muito abaixo do histórico",
                       technical_description="A energia acumulada do dia está abaixo da referência recente da instalação.",
                       simplified_message="A produção do dia está abaixo do padrão normal.",
                       probable_causes=["clima ruim", "sombreamento", "falha parcial", "sujeira acumulada"],
                       recommended_action="Comparar o dia atual com o histórico recente e inspecionar o campo fotovoltaico.",
                       timestamp=ts, source="generation_model", affected_component="instalação")

        if self._persist("POSSIBLE_SHADING", imbalance_ratio > 0.25 and indicators.get("diferenca_geracao_pct", 0.0) < -20, 3):
            self._push(alarms, code="POSSIBLE_SHADING", category="diagnóstico", severity="warning", title="Possível sombreamento",
                       technical_description="Combinação de baixa geração relativa e assimetria entre strings indica possível sombreamento parcial.",
                       simplified_message="Pode haver sombra sobre parte dos painéis.",
                       probable_causes=["árvores", "antenas", "edificações", "sombreamento sazonal"],
                       recommended_action="Inspecionar o arranjo em diferentes horários para confirmar sombra parcial.",
                       timestamp=ts, source="generation_model", affected_component="instalação")

        if self._persist("POSSIBLE_SOILING", indicators.get("diferenca_geracao_pct", 0.0) < -24 and imbalance_ratio < 0.15 and expected_kw > 1.0, 4):
            self._push(alarms, code="POSSIBLE_SOILING", category="diagnóstico", severity="info", title="Possível sujeira nos módulos",
                       technical_description="Baixa geração persistente sem grande assimetria entre strings sugere perda homogênea por sujeira.",
                       simplified_message="Os painéis podem estar sujos e produzindo menos energia.",
                       probable_causes=["poeira", "folhas", "poluição", "falta de limpeza periódica"],
                       recommended_action="Avaliar necessidade de limpeza dos módulos e comparar desempenho após manutenção.",
                       timestamp=ts, source="generation_model", affected_component="instalação")

        avg_consumption = self._avg(recent_consumption[:-1]) if len(recent_consumption) > 1 else 0.0
        if self._persist("ABNORMAL_LOAD_PROFILE", avg_consumption > 0 and indicators.get("consumo_kwh", 0.0) > avg_consumption * 1.8, 2):
            self._push(alarms, code="ABNORMAL_LOAD_PROFILE", category="consumo", severity="info", title="Perfil de consumo anormal",
                       technical_description="O consumo atual está acima do padrão médio recente para o mesmo sistema.",
                       simplified_message="O consumo da casa subiu além do normal.",
                       probable_causes=["nova carga ligada", "equipamento com defeito", "uso simultâneo de cargas pesadas"],
                       recommended_action="Identificar cargas ativas no momento e revisar rotina de uso da instalação.",
                       timestamp=ts, source="load_profile", affected_component="instalação")

        if self._persist("SERVER_API_FAILURE", fault is not None and "server" in str(fault.get("title", "")).lower(), 1):
            self._push(alarms, code="SERVER_API_FAILURE", category="segurança", severity="critical", title="Erro interno de servidor/API",
                       technical_description="O backend registrou falha interna em serviços de API ou processamento de resposta.",
                       simplified_message="O servidor local encontrou um erro interno e pode responder de forma instável.",
                       probable_causes=["exceção não tratada", "erro de serialização", "falha de recurso local"],
                       recommended_action="Inspecionar logs do servidor, reiniciar o serviço e validar os endpoints locais.",
                       timestamp=ts, source="server", affected_component="servidor local")

        if not alarms:
            self._push(alarms, code="SYSTEM_OK", category="diagnóstico", severity="info", title="Operação estável",
                       technical_description="Nenhuma anomalia técnica persistente foi detectada nas regras avaliadas.",
                       simplified_message="O sistema está operando dentro do comportamento esperado.",
                       probable_causes=["operação normal"],
                       recommended_action="Continuar monitorando normalmente.",
                       timestamp=ts, source="server", affected_component="dashboard")

        alarms.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["timestamp"], item["code"]))
        self._update_history(alarms)
        return alarms

    def _update_history(self, alarms):
        active_codes = {alarm["code"] for alarm in alarms if alarm.get("active")}
        new_codes = active_codes - self._last_active
        for alarm in alarms:
            if alarm["code"] in new_codes:
                self.history.append(dict(alarm))
        self.history = self.history[-200:]
        self._last_active = active_codes

    def diagnostics(self, snapshot, indicators, technical, alerts, updated_at, fault=None):
        return {
            "summary": {
                "updated_at": updated_at,
                "alert_count": len(alerts),
                "critical_count": len([a for a in alerts if a["severity"] == "critical"]),
                "warning_count": len([a for a in alerts if a["severity"] == "warning"]),
                "info_count": len([a for a in alerts if a["severity"] == "info"]),
                "stale_seconds": max(0, int(time.time()) - int(updated_at or 0)),
            },
            "operational_context": {
                "inverter_status": snapshot.get("inverter_status", "Desconhecido"),
                "grid_status": snapshot.get("grid_status", "Desconhecido"),
                "communication_status": snapshot.get("communication_status", "Desconhecido"),
                "performance_ratio": indicators.get("performance_ratio", 0.0),
                "power_kw": indicators.get("potencia_atual_kw", 0.0),
                "expected_kw": indicators.get("geracao_esperada_kw", 0.0),
            },
            "technical_snapshot": technical,
            "fault": fault,
        }
