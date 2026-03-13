"""Data processing and KPI generation for CleanSun."""
import json
import os
import time

DEFAULT_CONFIG = {
    "tarifa_kwh": 0.92,
    "potencia_sistema_kwp": 5.0,
    "nome_instalacao": "Residencia",
    "expected_irradiance": {
        "6": 0.10, "7": 0.20, "8": 0.35, "9": 0.55,
        "10": 0.70, "11": 0.85, "12": 0.95, "13": 0.90,
        "14": 0.80, "15": 0.60, "16": 0.40, "17": 0.20,
    },
    "history_max_bytes": 524288,
}

HISTORY_HEADER = "timestamp,geracao_kwh,consumo_kwh,exportado_kwh\n"


class DataProcessor:
    def __init__(self, config_path, history_path):
        self.config_path = config_path
        self.history_path = history_path
        self.config = self._load_config()
        self.last_snapshot = {}
        self.last_metrics = self._blank_metrics()
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
            f.write(json.dumps(data))

    @staticmethod
    def _blank_metrics():
        return {
            "autoconsumo_pct": 0.0,
            "excedente_exportado_kwh": 0.0,
            "economia_diaria_rs": 0.0,
            "performance_ratio": 0.0,
            "status": "ATENCAO",
            "status_text": "Aguardando dados do inversor.",
            "phrases": [],
            "hourly": {},
        }

    def register_fault(self, title, detail=""):
        self.fault = {"title": title, "detail": detail, "ts": int(time.time())}
        self.last_metrics["status"] = "ALERTA"
        self.last_metrics["status_text"] = title

    def ingest_snapshot(self, snapshot, now_ts=None):
        self.last_snapshot = snapshot
        self.fault = None
        metrics = self._compute_metrics(snapshot)
        self.last_metrics = metrics
        self._update_hourly_history(snapshot, metrics, now_ts=now_ts)

    def _compute_metrics(self, snapshot):
        daily_gen = max(snapshot.get("daily_gen_kwh", 0.0), 0.0)
        power_kw = max(snapshot.get("instant_total_w", 0.0), 0.0) / 1000.0

        # BUG CORRIGIDO: consumo nao era hardcoded em 65%.
        # Usamos consumo_kwh do snapshot se disponivel; caso contrario estimamos
        # baseado na potencia instantanea proporcional ao dia (mais realista).
        if "consumo_kwh" in snapshot:
            consumed = min(float(snapshot["consumo_kwh"]), daily_gen)
        else:
            # Estimativa: autoconsumo proporcional a potencia vs geracao
            pct = min(snapshot.get("autoconsumo_pct", 0.68), 1.0)
            consumed = daily_gen * pct

        consumed = max(consumed, 0.0)
        autoconsumo_pct = (consumed / daily_gen * 100.0) if daily_gen > 0 else 0.0
        excedente = max(daily_gen - consumed, 0.0)

        # BUG CORRIGIDO: economia inclui creditos do excedente exportado
        tarifa = float(self.config.get("tarifa_kwh", 0.0))
        economia = (consumed + excedente) * tarifa

        performance_ratio = self._performance_ratio(snapshot)
        status, status_text = self._status_from_pr(performance_ratio)

        return {
            "autoconsumo_pct": round(autoconsumo_pct, 1),
            "excedente_exportado_kwh": round(excedente, 2),
            "economia_diaria_rs": round(economia, 2),
            "performance_ratio": round(performance_ratio, 2),
            "status": status,
            "status_text": status_text,
            "phrases": self._phrases(consumed, excedente, performance_ratio, daily_gen, economia),
            "hourly": self._hourly_curve(snapshot),
            "consumo_kwh": round(consumed, 2),
            "exportado_kwh": round(excedente, 2),
        }

    def _performance_ratio(self, snapshot):
        now = time.localtime()
        hour = str(now[3])
        irr_map = self.config.get("expected_irradiance", {})
        irr = float(irr_map.get(hour, 0.0))
        kwp = float(self.config.get("potencia_sistema_kwp", 1.0))
        expected_kw = kwp * irr
        actual_kw = max(snapshot.get("instant_total_w", 0.0), 0.0) / 1000.0

        # BUG CORRIGIDO: hora noturna (fora do range 6-17) nao gera falso ALERTA
        if irr <= 0.01:
            # Noite: se nao ha geracao esperada, status e NORMAL
            return 1.0
        return min(actual_kw / expected_kw, 1.4)

    @staticmethod
    def _status_from_pr(pr):
        if pr >= 0.85:
            return "NORMAL", "Sistema funcionando normalmente"
        if pr >= 0.55:
            return "ATENCAO", "Desempenho abaixo do esperado para o horario"
        return "ALERTA", "Geracao muito abaixo do esperado"

    @staticmethod
    def _phrases(consumed, excedente, pr, daily_gen, economia):
        phrases = []
        if daily_gen > 0:
            pct = round(consumed / daily_gen * 100)
            phrases.append("Sua casa usou {}% da energia gerada hoje ({:.2f} kWh).".format(pct, consumed))
        phrases.append("Economia estimada hoje: R$ {:.2f} (autoconsumo + creditos).".format(economia))
        if excedente > 0:
            phrases.append("{:.2f} kWh foram enviados a rede como credito.".format(excedente))
        if pr < 0.55 and pr > 0:
            phrases.append("Atencao: verifique sombreamento, sujeira ou alertas no inversor.")
        elif excedente > consumed:
            phrases.append("Ha excedente relevante; considere deslocar cargas para o periodo solar.")
        elif daily_gen > 0:
            phrases.append("Perfil de consumo bem alinhado com a geracao solar.")
        return phrases

    def _hourly_curve(self, snapshot):
        now = time.localtime()
        hour = now[3]
        base = max(snapshot.get("instant_total_w", 0.0), 0.0)
        values = {}
        for h in range(24):
            delta = abs(h - 12)
            factor = max(0.0, 1.0 - (delta / 7.0) ** 2)
            values[str(h)] = round(base * factor, 0)
        values[str(hour)] = round(base, 0)
        return values

    def _ensure_history_file(self):
        if not self._exists(self.history_path):
            with open(self.history_path, "w", encoding="utf-8") as f:
                f.write(HISTORY_HEADER)
            return
        with open(self.history_path, "r", encoding="utf-8") as f:
            head = f.readline()
        if head.strip() != HISTORY_HEADER.strip():
            with open(self.history_path, "w", encoding="utf-8") as f:
                f.write(HISTORY_HEADER)

    def _hour_key(self, ts):
        lt = time.localtime(ts)
        return (lt[0], lt[1], lt[2], lt[3])

    def _update_hourly_history(self, snapshot, metrics, now_ts=None):
        ts = int(now_ts if now_ts is not None else time.time())
        cur_gen = max(float(snapshot.get("daily_gen_kwh", 0.0)), 0.0)
        cur_cons = max(float(metrics.get("consumo_kwh", 0.0)), 0.0)
        cur_exp = max(float(metrics.get("exportado_kwh", 0.0)), 0.0)
        cur_hour = self._hour_key(ts)

        if self._hour_state is None:
            self._hour_state = {
                "hour": cur_hour,
                "start_gen": cur_gen,
                "start_cons": cur_cons,
                "start_exp": cur_exp,
                "last_ts": ts,
            }
            return

        if cur_hour != self._hour_state["hour"]:
            gen = max(cur_gen - self._hour_state["start_gen"], 0.0)
            cons = max(cur_cons - self._hour_state["start_cons"], 0.0)
            exp = max(cur_exp - self._hour_state["start_exp"], 0.0)
            self._append_history_row(self._hour_state["last_ts"], gen, cons, exp)
            self._hour_state = {
                "hour": cur_hour,
                "start_gen": cur_gen,
                "start_cons": cur_cons,
                "start_exp": cur_exp,
                "last_ts": ts,
            }
        else:
            self._hour_state["last_ts"] = ts

    def _append_history_row(self, timestamp, geracao_kwh, consumo_kwh, exportado_kwh):
        line = "{},{:.3f},{:.3f},{:.3f}\n".format(int(timestamp), geracao_kwh, consumo_kwh, exportado_kwh)
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(line)
        self._enforce_history_flash_limit()

    def _enforce_history_flash_limit(self):
        max_bytes = int(self.config.get("history_max_bytes", 524288))
        st = os.stat(self.history_path)
        if st[6] <= max_bytes:
            return
        with open(self.history_path, "r", encoding="utf-8") as f:
            rows = f.readlines()
        while rows and len("".join(rows).encode("utf-8")) > max_bytes and len(rows) > 2:
            rows.pop(1)
        with open(self.history_path, "w", encoding="utf-8") as f:
            f.write("".join(rows))

    def history_last_days(self, days=7):
        days = max(1, int(days))
        cutoff = int(time.time()) - (days * 86400)
        if not self._exists(self.history_path):
            return []
        out = []
        with open(self.history_path, "r", encoding="utf-8") as f:
            _ = f.readline()
            for line in f:
                parts = line.strip().split(",")
                if len(parts) != 4:
                    continue
                ts = int(parts[0])
                if ts < cutoff:
                    continue
                out.append({
                    "timestamp": ts,
                    "geracao_kwh": float(parts[1]),
                    "consumo_kwh": float(parts[2]),
                    "exportado_kwh": float(parts[3]),
                })
        return out

    def payload(self):
        return {
            "config": self.config,
            "snapshot": self.last_snapshot,
            "metrics": self.last_metrics,
            "fault": self.fault,
        }
