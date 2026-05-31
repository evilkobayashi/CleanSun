# Visual Dashboard — Design Spec
Date: 2026-05-28

## Overview

Add a **Visual** tab to the existing `dashboard.html` that mirrors the Solarman app aesthetic: light background, animated energy-flow diagram, donut charts, area chart, and battery card. The existing **Técnico** tab is preserved unchanged. No new server endpoints. No external dependencies.

---

## Structure

A toggle in the topbar switches between two views within the same `dashboard.html`:

- **Visual** (new, default) — light theme, all 6 visual sections
- **Técnico** (existing) — dark theme, current layout unchanged

The toggle replaces the existing `Painel simplificado / Acesso técnico` controls in the topbar. Technical auth modal is retained and accessible from the Técnico tab.

---

## Layout — Visual Tab (top to bottom)

### ① Stats Bar
Four metric chips in a single row:
- Produção total (kWh, yellow) — `snapshot.geracao_total_kwh`
- Total injetado na rede (kWh, blue) — `snapshot.energy.export_kwh` (today) or cumulative from history
- Dias de operação (integer, grey) — count of distinct days with `geracao_kwh > 0` in `GET /api/history?days=365&bucket=daily`
- Redução de CO₂ (T, green) — `total_kwh * 0.0004` (Brazilian grid emissions factor)

Data source: `snapshot`, `dashboard.indicators`, `/api/history`.

### ② Fluxograma + Bateria (side by side, 2/3 + 1/3)

**Fluxograma (2/3):**
Nodes connected by animated lines showing real-time energy direction:
```
☀️ Solar → 🏠 Casa → ⚡ Rede
                  ↓
              🔋 Bateria → 🏭 Consumo
```
- Each node shows label + current power in W/kW below icon
- Lines are SVG paths; animated dots (CSS `@keyframes`) travel along active paths
- Line color: yellow (solar→casa), green (battery), blue (grid), grey (idle/zero flow)
- When flow = 0 on a path, line is light grey, dots hidden

**Card Bateria (1/3):**
- SOC % large (colored: green ≥60%, yellow 30–60%, red <30%)
- Progress bar
- Mode label (Carregando / Descarregando / Parado)
- Power kW + available energy kWh

Data source: `snapshot.battery_soc_percent`, `snapshot.battery_power_kw`, `snapshot.battery_mode`, `snapshot.battery.available_energy_kwh`.

### ③ Curva 24h (full width)

Area chart with two filled series:
- **Solar** (blue, `#3b82f6`) — `hourly[h].generation_w / 1000`
- **Consumo** (red, `#ef4444`) — `hourly[h].consumption_w / 1000`

Rendered with Canvas 2D API (no library). X-axis: 00h–23h. Y-axis: auto-scaled to max kW. Legend dots. Tooltip on hover showing hour + values.

Data source: `dashboard.indicators.hourly`.

### ④ Donuts + Histórico Mensal (1/3 + 2/3)

**Donuts (1/3):**
Two SVG ring charts stacked vertically:
1. **Produção total** — segments: Para a rede (blue) / Autoconsumo (yellow) / Para bateria (green)
2. **Consumo total** — segments: Da produção (yellow) / Da bateria (green) / Da rede (red)

Center label shows total kWh. Segment labels shown with value outside ring.

Data source: `dashboard.indicators` — `exportado_kwh`, `autoconsumo_pct`, `importado_kwh`, `geracao_kwh`.

**Histórico Mensal (2/3):**
Grouped bar chart (Canvas 2D). One bar pair per day: geração (blue) + consumo (red). X-axis: day number. Y-axis: kWh. Last 30 days from `GET /api/history?days=30&bucket=daily`.

---

## Theme — Visual Tab

```
Background:   #f5f7fa
Cards:        #ffffff, border-radius 12px, box-shadow 0 1px 6px rgba(0,0,0,.08)
Text primary: #111827
Text muted:   #6b7280
Solar yellow: #f59e0b
Grid blue:    #3b82f6
Battery green:#10b981
Load red:     #ef4444
```

Dark theme is preserved only for the Técnico tab (existing CSS variables unchanged).

---

## Data Flow

```
SSE /api/events (5s)
  └── updates: fluxograma nodes, stats bar, bateria card

GET /api/v1/dashboard (on tab load + every 60s)
  └── updates: curva 24h, donuts

GET /api/history?days=30&bucket=daily (on tab load + every 5min)
  └── updates: histórico mensal
```

---

## Implementation Scope

| File | Change |
|------|--------|
| `dashboard.html` | Add Visual tab CSS + HTML sections + JS render functions |
| `http_server.py` | No change |
| `data_processor.py` | No change |

The Visual tab CSS is scoped under `.tab-visual` to avoid leaking into the Técnico tab. All new JS functions are prefixed `vis_`.

---

## Out of Scope

- Weather widget (no weather API wired)
- Date picker for history (fixed 30 days)
- Mobile-specific optimizations beyond basic responsive grid
- CO₂ calculator beyond the simple `total_kwh × 0.0004` estimate
