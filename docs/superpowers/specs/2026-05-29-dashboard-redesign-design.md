# Dashboard Full Redesign — Design Spec

**Date:** 2026-05-29  
**Status:** Approved  
**Scope:** `dashboard.html` only — no server changes

---

## Goal

Rebuild both tabs of `dashboard.html` with a unified hybrid visual style (Solarman dark animated flow + Deye Cloud white cards). Add four new sections to the Visual tab. Rebuild the Técnico tab with the same light style but technical-depth content.

---

## Style System

**Hybrid aesthetic:**
- Background: `#f0f4f8` (light grey, Deye Cloud)
- Cards: `#ffffff` with `box-shadow: 0 1px 4px rgba(0,0,0,.08)`, `border-radius: 12px`
- Flow diagram card: `background: #0f1b2d` (Solarman dark navy) — only this card stays dark
- Accent colors:
  - Solar / amber: `#f59e0b`
  - Battery / blue: `#3b82f6`
  - Grid / purple: `#8b5cf6`
  - Consumption / green: `#10b981`
  - Danger: `#ef4444`
  - Muted text: `#9ca3af`
- Typography: Segoe UI / Arial, card labels 10px uppercase `letter-spacing:.06em`
- Layout: CSS Grid, 3-column desktop (`repeat(3, 1fr)`), 1-column mobile (`max-width: 700px`)

**Tab toggle:** Single toggle in topbar switches `body` class between `.tab-visual` and `.tab-tech`. CSS visibility rules hide/show sections per class. Both tabs share the same topbar and auth panel.

---

## Architecture

**Single file:** All changes in `dashboard.html`. No new server endpoints, no external JS libraries.

**HTML structure:**
```
<body class="tab-visual">
  <div class="wrap"><div class="shell">
    <!-- Topbar (shared) -->
    <!-- Auth panel (shared) -->
    <div id="visTab">   <!-- Visual tab sections --></div>
    <div id="techTab">  <!-- Técnico tab sections --></div>
  </div></div>
</body>
```

**CSS scoping:**
```css
.tab-visual #visTab  { display: block }
.tab-visual #techTab { display: none }
.tab-tech   #visTab  { display: none }
.tab-tech   #techTab { display: block }
```

**JS namespacing:**
- Visual functions: `vis_*` (existing prefix preserved, new: `vis_loadWeather`, `vis_loadStrings`, `vis_calcSavings`, `vis_drawFlow`)
- Técnico functions: `tech_*` (new prefix for rebuilt tech sections)
- Shared: `setMode()`, `applyDashboard()`, `applySnapshot()`

---

## Tab Visual — Layout & Sections

Grid: 3 columns desktop, 1 column mobile. Sections top to bottom:

### ① Stats Bar — `span 3`
Four metric chips in a single row.

| Chip | Color | Data source |
|---|---|---|
| Produção total (kWh) | `#f59e0b` | `snapshot.geracao_total_kwh` |
| Injetado na rede (kWh) | `#3b82f6` | history cumulative `export_kwh` |
| Dias de operação | `#6b7280` | count of days with `geracao_kwh > 0` in `/api/history?days=365&bucket=daily` |
| Redução CO₂ (T) | `#10b981` | `total_kwh * 0.0004` |

### ② Losango Flow — `2/3` + Bateria — `1/3`

**Fluxo (losango):** SVG `viewBox="0 0 300 300"`. Casa node at center. Four outer nodes:
- Top-left: ☀️ Solar (`#f59e0b`) — `snapshot.pv_power_kw`
- Bottom-left: 🔋 Bateria (`#3b82f6`) — `snapshot.battery_power_kw`
- Top-right: ⚡ Rede (`#8b5cf6`) — `snapshot.grid_power_kw`
- Bottom-right: 🏭 Consumo (`#10b981`) — `snapshot.load_power_kw`

Animated dots via `<animateMotion>` along SVG `<path>` elements. Direction and color determined by sign of power value. Zero-flow paths render as `#1e3a5f` (dim), no dots. Dark card background `#0f1b2d`.

**Bateria card:** SOC % large (color: green ≥60%, amber 30–60%, red <30%), progress bar, mode label (Carregando / Descarregando / Parado), power kW + available kWh.

Data: `snapshot.battery_soc_percent`, `snapshot.battery_power_kw`, `snapshot.battery_mode`, `snapshot.battery.available_energy_kwh`.

### ③ Clima + Previsão — `1/3` + Curva 24h — `2/3`

**Clima card:**
- On tab activation: `navigator.geolocation.getCurrentPosition()` → fetch `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,cloudcover,windspeed_10m,relative_humidity_2m&hourly=shortwave_radiation&daily=shortwave_radiation_sum&timezone=auto&forecast_days=7`
- Current: temperature, cloudcover (icon), windspeed, humidity
- 7-day forecast: bar chart of `daily.shortwave_radiation_sum` (kWh/m²/day), colored amber (sunny) vs blue (cloudy, cloudcover >60%)
- Geolocation permission denied: show manual coords input (lat/lng fields)

**Curva 24h canvas:**
- Three series: Solar (blue `#3b82f6`), Consumo (red `#ef4444`), Previsão (amber dashed `#f59e0b`)
- Previsão series: convert `hourly.shortwave_radiation` (W/m²) → estimated kW using `system_peak_kw` from `snapshot` (or config fallback 7.5 kW) × efficiency 0.18
- Canvas 2D API, area fill with 20% opacity under each line
- Tooltip on mousemove showing hour + all three values

### ④ Strings/MPPT — `1/3` + Energia hoje — `1/3` + Economia R$ — `1/3`

**Strings card:**
- One row per string: colored dot (green=OK, amber=low, red=zero/fault), name, horizontal bar (% of max string power), power value
- Alert banner if any string power = 0 while system is generating: "⚠ String N sem geração — verificar conexão"
- Data: `snapshot.strings[]` — each entry `{ name, power_w, voltage_v, current_a, status }`
- If `snapshot.strings` absent or empty: hide card, show placeholder "Dados de string não disponíveis"

**Energia hoje donuts:**
- Two SVG donuts: Produção hoje (kWh, vs expected from forecast) + Consumo (kWh, % of production)
- Data: `snapshot.energy.generation_kwh`, `snapshot.energy.consumption_kwh`

**Economia R$ card:**
- Input field for tarifa (R$/kWh), default 0.82, persisted in `localStorage`
- Total acumulado: `total_kwh * tarifa` in large green text
- Este mês: `month_kwh * tarifa`
- Bar chart: last 6 months `R$` savings from `/api/history?days=180&bucket=monthly`

### ⑤ Histórico Mensal — `span 3`
Canvas 2D bar chart. Two series per month: Geração (amber) vs Consumo (red). Last 12 months. Data: `/api/history?days=365&bucket=monthly`.

---

## Tab Técnico — Layout & Sections

Same light style as Visual tab. Auth panel preserved — technical sections hidden until authenticated.

### ① Configuração do Inversor — `span 3` (auth-gated)
Override manual buttons (On-grid / Off-grid / Híbrido / Limpar). Detected type + source + confidence. Unchanged logic, new visual style.

### ② KPIs Técnicos — 4 chips
Geração hoje (kWh), Performance Ratio (%), Autoconsumo (%), Frequência rede (Hz).

### ③ Losango Flow — `2/3` + Bateria Técnica — `1/3`
Same losango SVG as Visual tab. Values shown in W (not kW) for precision.

**Bateria técnica card:** SOC %, tensão DC (V), corrente (A), temperatura (°C), modo, potência (W).
Data: `snapshot.battery_soc_percent`, `snapshot.battery_voltage_v`, `snapshot.battery_current_a`, `snapshot.battery_temp_c`.

### ④ Strings Detalhe — `span 3` (auth-gated)
Full table: one row per string with columns Name, Status, Voltage (V), Current (A), Power (W), Temp (°C if available). Status badge: OK / Baixo / Falha. Sort by power descending.

### ⑤ Curva Hora a Hora — `2/3` + Gauge Autoconsumo + PR — `1/3`
Existing SVG polyline chart preserved, restyled to white card. Gauge widget for autoconsumo % + PR value with interpretation text.

### ⑥ Alertas Técnicos — `span 3` (auth-gated)
Full alarm list, filter buttons (Todos / Crítico / Warning / Info). Existing `techAlerts` + `techGroups` DOM structure preserved, restyled.

---

## Data Flow

```
applySnapshot(data)
  ├── vis_drawFlow(data.snapshot)        # losango SVG + animateMotion
  ├── vis_updateBattery(data.snapshot)
  ├── vis_updateStrings(data.snapshot)
  ├── vis_calcSavings(data.snapshot)
  ├── tech_drawFlow(data.snapshot)       # same losango, W precision
  ├── tech_updateBatteryDetail(data.snapshot)
  └── tech_updateStrings(data.snapshot)  # full table

vis_onTabActivated('visual')
  ├── vis_loadWeather()                  # geolocation → Open-Meteo
  ├── vis_loadHistory()                  # /api/history stats bar + monthly
  └── vis_draw24h()                      # canvas hourly
```

Weather fetch: one fetch per tab activation, cached in `window._weatherData` for 10 minutes (compare `Date.now()` vs `_weatherFetchedAt`).

---

## Error Handling

- Geolocation denied → show lat/lng manual input in clima card
- Open-Meteo fetch fails → hide previsão bars, show "Previsão indisponível"
- `snapshot.strings` missing → hide strings card entirely
- `snapshot.battery_soc_percent` null → show "--" in battery card, no color coding

---

## What Does Not Change

- `http_server.py`, `data_processor.py`, `alarms.py`, `metrics.py`, `solarman_reader.py`
- `/api/*` endpoints — no new endpoints
- Auth logic (`logoutTechnical`, modal, password check)
- `applyDashboard()` and `applySnapshot()` call signatures
