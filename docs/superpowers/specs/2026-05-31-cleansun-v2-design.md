# CleanSun v2 — Design Spec
**Date:** 2026-05-31  
**Status:** Approved

---

## 1. Objetivo

Reescrever o CleanSun do zero com arquitetura limpa, dados confiáveis via API oficial Deye Cloud + fallback LAN, e dashboard moderno e interativo para uso familiar.

Motivação: projeto atual usa pysolarmanv5 + servidor HTTP artesanal + registros Modbus manuais — frágil, difícil de manter, UI insatisfatória.

---

## 2. Escopo

- **Monitoramento apenas** — sem controle do inversor nesta versão
- **Usuários:** família (pequeno grupo, sem sistema de contas)
- **Deploy inicial:** servidor local Windows; preparado para VPS/home server + VPN futuramente
- **Frontend v1** funcional; melhorias de UI serão iteradas em versão posterior

---

## 3. Arquitetura

```
cleansun/
├── backend/
│   ├── main.py                  # FastAPI app + lifespan (start poller)
│   ├── config.py                # Settings via pydantic-settings (config.json)
│   ├── database.py              # SQLite setup com aiosqlite
│   ├── transports/
│   │   ├── lan.py               # pysolarmanv5 LAN reader
│   │   └── cloud.py             # Deye Cloud API client (Bearer token)
│   ├── reader.py                # Orchestrator: LAN → Cloud fallback
│   ├── poller.py                # Background task: poll + store no SQLite
│   └── api/
│       ├── routes.py            # Endpoints REST
│       └── sse.py               # GET /api/events (SSE stream)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── PowerFlow.tsx    # Diagrama animado solar→bateria→grid→casa
│   │   │   ├── BatteryCard.tsx  # SOC gauge circular + modo + energia disponível
│   │   │   ├── StatsBar.tsx     # kWh hoje, total, temperatura inversor
│   │   │   ├── HistoryChart.tsx # Recharts ComposedChart diário/semanal/mensal
│   │   │   ├── AlertsList.tsx   # Alertas ativos via Deye Cloud
│   │   │   └── PVDetail.tsx     # PV1/PV2 tensão, corrente, potência
│   │   └── hooks/
│   │       └── useSSE.ts        # SSE hook com exponential backoff reconnect
│   └── vite.config.ts
│
├── config.json                  # Configuração (não commitado)
└── history.db                   # SQLite gerado automaticamente
```

**Fluxo de dados:**
```
pysolarmanv5 (LAN) ─┐
                     ├─► reader.py ─► poller.py ─► SQLite
Deye Cloud API ──────┘       │
                             └─► SSE ─► React (useSSE) ─► UI
```

---

## 4. Fontes de Dados

### 4.1 LAN (primária)
- **Protocolo:** SOLARMAN v5 via `pysolarmanv5`
- **IP:** `192.168.3.144`
- **Serial datalogger:** `3427615184`
- **Porta:** `8899`
- **Poll interval:** 5 segundos
- **Registros:** mesma lógica de `solarman_reader.py` atual (reg60-111, 150-190)

### 4.2 Deye Cloud API (fallback)
- **Base URL:** `https://us1-developer.deyecloud.com`
- **Auth:** `POST /v1.0/account/token` → Bearer token (SHA256 password)
- **Dados:** `POST /v1.0/device/latest` (batch, max 10 devices)
- **Alertas:** `POST /v1.0/device/alertList`
- **Histórico:** `POST /v1.0/device/history`
- **Fallback trigger:** 3 falhas LAN consecutivas
- **Poll interval em cloud:** 300 segundos (limite da API)
- **Token refresh:** automático antes de cada request

### 4.3 Lógica de fallback
```
LAN falha 3x consecutivas
  → switch para Deye Cloud
  → log evento com timestamp
LAN volta (próximo poll bem-sucedido)
  → switch de volta para LAN
  → log recuperação
```

---

## 5. Modelo de Dados

### Snapshot (payload em tempo real)
```json
{
  "timestamp": 1748650000,
  "source": "lan",
  "solar": {
    "pv1_w": 1200, "pv2_w": 800, "total_w": 2000,
    "pv1_v": 380.0, "pv1_a": 3.2,
    "pv2_v": 360.0, "pv2_a": 2.2
  },
  "battery": {
    "soc_pct": 78, "power_kw": -1.2,
    "mode": "charging", "voltage_v": 51.2,
    "available_kwh": 7.5
  },
  "grid": {
    "power_kw": 0.3, "voltage_v": 127.0,
    "frequency_hz": 60.0, "status": "Normal"
  },
  "load": { "power_w": 850 },
  "inverter": { "temp_c": 42.1, "status": "Gerando" },
  "energy": { "today_kwh": 12.4, "total_kwh": 3210.0 },
  "alerts": []
}
```

### SQLite — tabela `readings`
```sql
CREATE TABLE readings (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,
  source      TEXT,
  solar_w     INTEGER,
  battery_soc INTEGER,
  battery_kw  REAL,
  grid_kw     REAL,
  load_w      INTEGER,
  temp_c      REAL,
  today_kwh   REAL,
  total_kwh   REAL
);
CREATE INDEX idx_ts ON readings(ts);
```

---

## 6. API Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Serve React build (index.html) |
| `GET` | `/api/snapshot` | Último snapshot |
| `GET` | `/api/events` | SSE stream (push a cada 5s) |
| `GET` | `/api/history?days=7&bucket=hour` | Histórico agregado (hour/day/month) |
| `GET` | `/api/alerts` | Alertas ativos via Deye Cloud |
| `GET` | `/api/status` | Saúde: fonte atual, última leitura, falhas |

---

## 7. Frontend

**Stack:** React 18 + TypeScript + Tailwind CSS + Recharts + Vite

**Layout (dark theme, responsivo):**
```
┌──────────────────────────────────────────────────────┐
│  ☀ CleanSun         [LAN ●]  42°C  última: 3s atrás  │
├──────────────────────────────────────────────────────┤
│                                                      │
│   ┌─────────────── PowerFlow ────────────────────┐   │
│   │  [PV 2.0kW] ──→ [INVERSOR] ──→ [CASA 0.8kW] │   │
│   │                     ↕              ↑         │   │
│   │            [BAT 78% ↓1.2kW]  [GRID 0.3kW]   │   │
│   └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ Hoje     │ │ Bateria  │ │ PV1/PV2  │ │Alertas │  │
│  │ 12.4 kWh │ │78%  7.5h │ │ V / A / W│ │  none  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘  │
│                                                      │
│  ┌─────────────── Histórico ────────────────────┐    │
│  │  [Hoje] [7 dias] [Mês] [Ano]                │    │
│  │  Recharts ComposedChart + brush + tooltip    │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

**Componentes-chave:**
- `PowerFlow` — setas animadas CSS proporcionais à potência, hover com valores
- `BatteryCard` — gauge circular animado, cor por SOC (verde/amarelo/vermelho)
- `HistoryChart` — zoom, brush para selecionar período, tooltip customizado
- `useSSE` — reconecta com exponential backoff se SSE cair

**Frontend em prod:** `npm run build` → `backend/static/` → servido pelo FastAPI via `StaticFiles`

---

## 8. Configuração

**`config.json` (não commitado, gitignore):**
```json
{
  "lan": {
    "datalogger_ip": "192.168.3.144",
    "datalogger_serial": 3427615184,
    "port": 8899,
    "poll_seconds": 5,
    "fail_threshold": 3
  },
  "cloud": {
    "enabled": true,
    "app_id": "",
    "app_secret": "",
    "email": "",
    "password": "",
    "station_id": ""
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  }
}
```

---

## 9. Resiliência & Erros

| Cenário | Comportamento |
|---------|--------------|
| LAN timeout | Retry, conta falha; após 3 → cloud |
| Cloud token expirado | Renovação automática |
| SSE cliente desconecta | Servidor descarta silenciosamente |
| SQLite write falha | Log + skip, polling continua |
| Cloud indisponível (sem LAN) | Retorna último snapshot com flag `stale: true` |

---

## 10. Deploy

```bash
# Backend
pip install fastapi uvicorn pysolarmanv5 aiosqlite pydantic-settings

uvicorn backend.main:app --host 0.0.0.0 --port 8080

# Frontend (prod)
cd frontend && npm install && npm run build
# build vai para backend/static/ — servido automaticamente pelo FastAPI
```

**Futuro VPS/home server:** mesmo setup, nginx como reverse proxy na frente, VPN para acesso externo.

---

## 11. Fora de escopo (v1)

- Controle do inversor (TOU, work mode, limites)
- Autenticação de usuários
- Notificações push/email
- Multi-instalação
