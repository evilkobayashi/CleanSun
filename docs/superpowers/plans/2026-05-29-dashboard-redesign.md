# Dashboard Full Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild both tabs of `dashboard.html` with a hybrid Solarman/Deye visual style, replace the flow diagram with an animated SVG losango, and add four new sections: Strings/MPPT, Clima+Previsão, Economia R$, and a rebuilt Técnico tab.

**Architecture:** All changes in `dashboard.html` (560 lines). No server changes. Existing functions `applyDashboard()`, `setMode()`, auth functions, `connect()`, `loadDashboard()`, and all event listeners are preserved verbatim. New CSS scoped under `.tab-visual`/`.tab-tech`. New JS functions use `vis_*` (visual) and `tech_*` (technical) prefixes.

**Tech Stack:** Vanilla HTML/CSS/JS, Canvas 2D API, SVG `<animateMotion>`, Open-Meteo API (no key required), browser `navigator.geolocation`.

---

## File Map

| File | Change |
|------|--------|
| `dashboard.html` | All changes — CSS (~lines 8-36), HTML (#visTab lines 82-178, #techTab new), JS (update `vis_renderFlow`, `applyDashboard`; add `vis_loadWeather`, `vis_updateStrings`, `vis_calcSavings`, `tech_*` functions) |

No other files change.

---

## Existing code to preserve unchanged

These functions must not be modified:
- `applyInverterButtons()`, `renderDetectionStatus()`, `configureLayout()`
- `renderAlerts()`, `renderTechAlerts()`, `renderReports()`, `renderRecs()`
- `renderHourChart()`, `renderWeekBars()`, `renderTechnical()`
- `setMiniRows()`, `groupBlock()`, `severityBadge()`, `sortAlerts()`
- `syncInverterType()`, `clearOverride()`, `initializeInverterType()`
- `openTechModal()`, `closeTechModal()`, `loginTechnical()`, `logoutTechnical()`
- `connect()`, `loadDashboard()`
- All `document.querySelectorAll(...)` event listener blocks at bottom of `<script>`

---

## Task 1: New CSS — light theme, cards, grid, losango, dark flow card

**Files:**
- Modify: `dashboard.html` — replace the CSS block (lines 8-35, the `<style>` content)

> **Strategy:** Add the new light-theme rules AFTER the existing CSS block (before `</style>`). Do NOT delete existing CSS — some rules (`.modal-backdrop`, `.modal`, `.input`, `.error`, `.btn`, `.hidden`) are still used.

- [ ] **Step 1: Add new CSS rules before `</style>` tag**

Insert the following block immediately before `</style>` (which appears after the existing `.tech-only` rules around line 35):

```css
/* ── NEW: light theme foundation ── */
:root {
  --cs-bg: #f0f4f8;
  --cs-card: #ffffff;
  --cs-shadow: 0 1px 4px rgba(0,0,0,.08);
  --cs-radius: 12px;
  --cs-amber: #f59e0b;
  --cs-blue: #3b82f6;
  --cs-purple: #8b5cf6;
  --cs-green: #10b981;
  --cs-red: #ef4444;
  --cs-muted: #9ca3af;
  --cs-text: #111827;
  --cs-flow-bg: #0f1b2d;
}

/* Override body background for both tabs */
.tab-visual, .tab-tech {
  background: var(--cs-bg);
  color: var(--cs-text);
  min-height: 100vh;
}

/* Card base */
.cs-card {
  background: var(--cs-card);
  border-radius: var(--cs-radius);
  padding: 14px;
  box-shadow: var(--cs-shadow);
}

/* Card label */
.cs-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--cs-muted);
  margin-bottom: 10px;
}

/* 3-column grid */
.cs-grid { display: grid; gap: 12px; }
.cs-grid-3 { grid-template-columns: repeat(3, 1fr); }
.cs-grid-4 { grid-template-columns: repeat(4, 1fr); }
.cs-span-2 { grid-column: span 2; }
.cs-span-3 { grid-column: span 3; }
.cs-span-4 { grid-column: span 4; }

/* 2/3 + 1/3 splits */
.cs-grid-2-1 { grid-template-columns: 2fr 1fr; }
.cs-grid-1-2 { grid-template-columns: 1fr 2fr; }

/* Flow card dark */
.cs-flow-card {
  background: var(--cs-flow-bg);
  border-radius: var(--cs-radius);
  padding: 14px;
  box-shadow: 0 1px 4px rgba(0,0,0,.25);
}
.cs-flow-card .cs-label { color: #4b6280; }

/* Stats chips */
.cs-stat-value { font-size: 24px; font-weight: 700; line-height: 1.1; }
.cs-stat-sub { font-size: 10px; color: var(--cs-muted); margin-top: 3px; }

/* Battery */
.cs-soc { font-size: 40px; font-weight: 700; text-align: center; }
.cs-progress-wrap { background: #e5e7eb; border-radius: 999px; height: 7px; margin: 8px 0; }
.cs-progress-bar { height: 100%; border-radius: 999px; transition: width .5s, background .5s; }
.cs-batt-mode { font-size: 12px; font-weight: 600; text-align: center; margin-bottom: 8px; }
.cs-batt-row { display: flex; justify-content: space-between; font-size: 11px; color: var(--cs-muted); }

/* Strings */
.cs-string-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0; border-bottom: 1px solid #f3f4f6;
  font-size: 11px;
}
.cs-string-row:last-child { border-bottom: none; }
.cs-string-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cs-string-name { color: #374151; font-weight: 600; width: 54px; }
.cs-string-bar-wrap { flex: 1; background: #f3f4f6; border-radius: 999px; height: 5px; }
.cs-string-bar { height: 100%; border-radius: 999px; background: var(--cs-amber); }
.cs-string-val { width: 46px; text-align: right; color: var(--cs-muted); }
.cs-fault-banner {
  font-size: 10px; color: var(--cs-red); margin-top: 8px;
  padding: 6px 8px; background: #fef2f2; border-radius: 6px;
}

/* Economy */
.cs-eco-big { font-size: 28px; font-weight: 700; color: var(--cs-green); text-align: center; margin: 6px 0 2px; }
.cs-eco-sub { font-size: 10px; color: var(--cs-muted); text-align: center; margin-bottom: 10px; }
.cs-eco-month { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 6px; }
.cs-tariff-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--cs-muted); margin-bottom: 8px; }
.cs-tariff-input {
  width: 64px; padding: 3px 6px; border-radius: 6px;
  border: 1px solid #e5e7eb; font: inherit; font-size: 11px;
  text-align: right; background: #f9fafb;
}
.cs-eco-bars { display: grid; grid-template-columns: repeat(6,1fr); gap: 3px; align-items: end; height: 50px; margin-top: 6px; }
.cs-eco-bar-col { text-align: center; }
.cs-eco-bar { border-radius: 3px 3px 1px 1px; background: var(--cs-green); margin: 0 auto; min-height: 4px; }
.cs-eco-bar-lbl { font-size: 8px; color: var(--cs-muted); margin-top: 2px; }

/* Weather */
.cs-weather-big { font-size: 30px; font-weight: 700; text-align: center; margin: 6px 0; }
.cs-weather-desc { font-size: 11px; color: var(--cs-muted); text-align: center; margin-bottom: 10px; }
.cs-weather-row { display: flex; justify-content: space-between; font-size: 11px; color: #6b7280; padding: 4px 0; border-bottom: 1px solid #f3f4f6; }
.cs-weather-row:last-child { border-bottom: none; }
.cs-forecast-wrap { background: #fffbeb; border-radius: 8px; padding: 8px; margin-bottom: 8px; }
.cs-forecast-label { font-size: 10px; font-weight: 700; color: #d97706; margin-bottom: 6px; }
.cs-forecast-bars { display: flex; gap: 3px; align-items: flex-end; height: 50px; }
.cs-forecast-bar-col { flex: 1; text-align: center; }
.cs-forecast-bar { border-radius: 3px 3px 1px 1px; margin: 0 auto; min-height: 3px; }
.cs-forecast-bar-lbl { font-size: 8px; color: var(--cs-muted); margin-top: 2px; }
.cs-geo-input-row { display: flex; gap: 4px; margin-top: 8px; }
.cs-geo-input { flex: 1; padding: 4px 6px; border-radius: 6px; border: 1px solid #e5e7eb; font-size: 11px; }

/* Tech tab table */
.cs-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.cs-table th { text-align: left; color: var(--cs-muted); font-weight: 600; font-size: 10px; text-transform: uppercase; padding: 4px 6px; border-bottom: 1px solid #f3f4f6; }
.cs-table td { padding: 6px 6px; border-bottom: 1px solid #f9fafb; }
.cs-table tr:last-child td { border-bottom: none; }
.cs-badge { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; }
.cs-badge-ok { background: #ecfdf5; color: #065f46; }
.cs-badge-low { background: #fffbeb; color: #92400e; }
.cs-badge-fail { background: #fef2f2; color: #991b1b; }

/* Topbar restyle */
.cs-topbar {
  background: var(--cs-card);
  border-radius: var(--cs-radius);
  padding: 10px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  box-shadow: var(--cs-shadow);
}
.cs-conn-ok { font-size: 11px; color: var(--cs-green); background: #ecfdf5; padding: 4px 10px; border-radius: 999px; }
.cs-conn-err { font-size: 11px; color: var(--cs-red); background: #fef2f2; padding: 4px 10px; border-radius: 999px; }

/* Tech tab KPI chips (reuse stat styles) */
.cs-kpi-card { background: var(--cs-card); border-radius: var(--cs-radius); padding: 12px 14px; box-shadow: var(--cs-shadow); }

/* Losango flow SVG container */
.cs-losango-wrap { position: relative; width: 100%; }
.cs-losango-svg { width: 100%; display: block; }

/* Hide/show tabs */
.tab-visual #visTab  { display: block; }
.tab-visual #techTab { display: none; }
.tab-tech   #visTab  { display: none; }
.tab-tech   #techTab { display: block; }

/* Mobile */
@media (max-width: 700px) {
  .cs-grid-3, .cs-grid-4 { grid-template-columns: 1fr; }
  .cs-grid-2-1, .cs-grid-1-2 { grid-template-columns: 1fr; }
  .cs-span-2, .cs-span-3, .cs-span-4 { grid-column: span 1; }
}
```

- [ ] **Step 2: Open browser, navigate to the dashboard (run `python main.py` or `python run_dev.py` first), verify page still loads without JS errors**

Open browser devtools console — must show zero errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard.html
git commit -m "style: add light-theme CSS system for dashboard redesign"
```

---

## Task 2: Replace topbar HTML and tab visibility wiring

**Files:**
- Modify: `dashboard.html` — topbar section (lines ~39-62) and body tag

The existing topbar uses inline dark styles. Replace with `cs-topbar` + update `body` class to start as `tab-visual`.

- [ ] **Step 1: Update `<body>` opening tag**

Find:
```html
<body class="tab-visual">
```
It's already `tab-visual` — confirm this is the case. If it reads `<body>`, change it to `<body class="tab-visual">`.

- [ ] **Step 2: Replace topbar div**

Find the existing topbar section (the `<div class="topbar">` block, approximately lines 40-47):
```html
  <div class="topbar">
    <div class="brand"><div class="logo"></div><div><h1 style="margin:0">CleanSun</h1><small id="installName">Residência</small></div></div>
    <div class="top-actions">
      <span class="pill" id="modeBadge">Modo simplificado</span>
      <span class="pill" id="conn">Conectando...</span>
      <span class="timestamp" id="updatedAt">--:--</span>
    </div>
  </div>
```

Replace with:
```html
  <div class="cs-topbar">
    <div class="brand">
      <div class="logo"></div>
      <div><h1 style="margin:0;font-size:18px;color:#111827">CleanSun</h1><small id="installName" style="color:#9ca3af;font-size:11px">Residência</small></div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <span id="modeBadge" style="font-size:11px;color:#9ca3af;padding:4px 10px;background:#f9fafb;border-radius:999px">Modo visual</span>
      <span id="conn" class="cs-conn-ok">● Conectando...</span>
      <span id="updatedAt" style="font-size:11px;color:#9ca3af">--:--</span>
      <div class="tab-toggle">
        <button id="btnTabVisual" class="active" onclick="setMode('visual')">☀ Visual</button>
        <button id="btnTabTech" onclick="setMode('tech')">⚙ Técnico</button>
      </div>
      <button class="btn danger hidden" id="btnTechLogout" onclick="logoutTechnical()">Sair</button>
    </div>
  </div>
```

- [ ] **Step 3: Update `conn` element styling in JS**

Find in `<script>`:
```javascript
$('conn').textContent='Sistema online'
```
Replace ALL occurrences (there are 2) with:
```javascript
$('conn').textContent='● Online';$('conn').className='cs-conn-ok'
```

Find:
```javascript
$('conn').textContent='Falha local'
```
Replace with:
```javascript
$('conn').textContent='● Offline';$('conn').className='cs-conn-err'
```

Find:
```javascript
$('conn').textContent='SSE indisponível'
```
Replace with:
```javascript
$('conn').textContent='● SSE off';$('conn').className='cs-conn-err'
```

- [ ] **Step 4: Verify in browser — topbar shows white card style, tab toggle works**

- [ ] **Step 5: Commit**

```bash
git add dashboard.html
git commit -m "style: restyle topbar with light theme, update conn badge classes"
```

---

## Task 3: Rebuild Visual tab HTML — all 9 sections scaffold

**Files:**
- Modify: `dashboard.html` — replace entire `<div class="vis-section" id="visTab">` block (lines 82-178)

The existing `#visTab` block ends at line 178 (`</div>`). Replace it entirely with the new structure below. All element IDs used by existing JS (`visStat1..4`, `visBattSoc`, `visBattBar`, `visBattMode`, `visBattKw`, `visBattKwh`, `visDonutProd`, `visDonutCons`, `vis24hCanvas`, `visHistCanvas`, `vis24hTooltip`) must be preserved.

- [ ] **Step 1: Replace `#visTab` HTML**

Find (beginning of the vis-section block):
```html
  <div class="vis-section" id="visTab">
```
...and everything until the matching closing `</div>` before `</div></div>` on the last HTML line.

Replace the entire `#visTab` block with:

```html
  <div id="visTab">

    <!-- ① Stats bar -->
    <div class="cs-grid cs-grid-4" style="margin-bottom:12px">
      <div class="cs-card">
        <div class="cs-label">Produção total</div>
        <div id="visStat1" class="cs-stat-value" style="color:#f59e0b">-- kWh</div>
        <div class="cs-stat-sub">desde instalação</div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Injetado na rede</div>
        <div id="visStat2" class="cs-stat-value" style="color:#3b82f6">-- kWh</div>
        <div class="cs-stat-sub">acumulado</div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Dias de operação</div>
        <div id="visStat3" class="cs-stat-value" style="color:#6b7280">--</div>
        <div class="cs-stat-sub">dias ativos</div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Redução CO₂</div>
        <div id="visStat4" class="cs-stat-value" style="color:#10b981">-- T</div>
        <div class="cs-stat-sub">evitadas</div>
      </div>
    </div>

    <!-- ② Losango flow (2/3) + Battery (1/3) -->
    <div class="cs-grid cs-grid-2-1" style="margin-bottom:12px">
      <div class="cs-flow-card">
        <div class="cs-label">Fluxo de energia agora</div>
        <div class="cs-losango-wrap" id="visFlowWrap">
          <svg class="cs-losango-svg" id="visFlowSvg" viewBox="0 0 300 240" preserveAspectRatio="xMidYMid meet" style="height:200px">
            <!-- paths -->
            <path id="vfp-solar"  d="M 60,40  L 150,120" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <path id="vfp-bat"    d="M 60,200 L 150,120" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <path id="vfp-grid"   d="M 150,120 L 240,40"  fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <path id="vfp-load"   d="M 150,120 L 240,200" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <!-- animated dots -->
            <circle id="vfd-solar" r="5" fill="#f59e0b" visibility="hidden">
              <animateMotion dur="1.2s" repeatCount="indefinite"><mpath href="#vfp-solar"/></animateMotion>
            </circle>
            <circle id="vfd-bat" r="5" fill="#3b82f6" visibility="hidden">
              <animateMotion dur="1.4s" repeatCount="indefinite"><mpath href="#vfp-bat"/></animateMotion>
            </circle>
            <circle id="vfd-grid-exp" r="5" fill="#8b5cf6" visibility="hidden">
              <animateMotion dur="1.3s" repeatCount="indefinite"><mpath href="#vfp-grid"/></animateMotion>
            </circle>
            <circle id="vfd-grid-imp" r="5" fill="#8b5cf6" visibility="hidden">
              <animateMotion dur="1.3s" repeatCount="indefinite" keyPoints="1;0" keyTimes="0;1" calcMode="linear"><mpath href="#vfp-grid"/></animateMotion>
            </circle>
            <circle id="vfd-load" r="5" fill="#10b981" visibility="hidden">
              <animateMotion dur="1.1s" repeatCount="indefinite"><mpath href="#vfp-load"/></animateMotion>
            </circle>
            <circle id="vfd-bat-chg" r="5" fill="#3b82f6" visibility="hidden">
              <animateMotion dur="1.4s" repeatCount="indefinite" keyPoints="1;0" keyTimes="0;1" calcMode="linear"><mpath href="#vfp-bat"/></animateMotion>
            </circle>
            <!-- nodes -->
            <g id="vfn-solar" transform="translate(60,40)">
              <circle r="24" fill="rgba(245,158,11,.15)"/>
              <text y="6" text-anchor="middle" font-size="20">☀️</text>
              <text id="vfv-solar" y="42" text-anchor="middle" font-size="10" font-weight="700" fill="#f59e0b">0W</text>
              <text y="54" text-anchor="middle" font-size="9" fill="#4b6280">Solar</text>
            </g>
            <g id="vfn-bat" transform="translate(60,200)">
              <circle r="24" fill="rgba(59,130,246,.15)"/>
              <text y="6" text-anchor="middle" font-size="20">🔋</text>
              <text id="vfv-bat" y="42" text-anchor="middle" font-size="10" font-weight="700" fill="#3b82f6">0W</text>
              <text id="vfl-bat" y="54" text-anchor="middle" font-size="9" fill="#4b6280">Bateria</text>
            </g>
            <g id="vfn-casa" transform="translate(150,120)">
              <circle r="28" fill="rgba(255,255,255,.10)"/>
              <text y="7" text-anchor="middle" font-size="24">🏠</text>
              <text y="40" text-anchor="middle" font-size="9" fill="#4b6280">Casa</text>
            </g>
            <g id="vfn-grid" transform="translate(240,40)">
              <circle r="24" fill="rgba(139,92,246,.15)"/>
              <text y="6" text-anchor="middle" font-size="20">⚡</text>
              <text id="vfv-grid" y="42" text-anchor="middle" font-size="10" font-weight="700" fill="#8b5cf6">0W</text>
              <text id="vfl-grid" y="54" text-anchor="middle" font-size="9" fill="#4b6280">Rede</text>
            </g>
            <g id="vfn-load" transform="translate(240,200)">
              <circle r="24" fill="rgba(16,185,129,.15)"/>
              <text y="6" text-anchor="middle" font-size="20">🏭</text>
              <text id="vfv-load" y="42" text-anchor="middle" font-size="10" font-weight="700" fill="#10b981">0W</text>
              <text y="54" text-anchor="middle" font-size="9" fill="#4b6280">Consumo</text>
            </g>
          </svg>
        </div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Bateria</div>
        <div id="visBattSoc" class="cs-soc">--%</div>
        <div class="cs-progress-wrap">
          <div id="visBattBar" class="cs-progress-bar" style="width:0%;background:#10b981"></div>
        </div>
        <div id="visBattMode" class="cs-batt-mode">--</div>
        <div class="cs-batt-row">
          <span id="visBattKw">-- kW</span>
          <span id="visBattKwh">-- kWh disp.</span>
        </div>
      </div>
    </div>

    <!-- ③ Clima+Previsão (1/3) + Curva 24h (2/3) -->
    <div class="cs-grid cs-grid-1-2" style="margin-bottom:12px">
      <div class="cs-card" id="visWeatherCard">
        <div class="cs-label">Clima atual</div>
        <div id="visWeatherContent">
          <div style="font-size:11px;color:#9ca3af;padding:8px 0">Obtendo localização...</div>
        </div>
      </div>
      <div class="cs-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div class="cs-label" style="margin:0">Curva 24h</div>
          <div style="display:flex;gap:10px;font-size:11px;color:#9ca3af">
            <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#3b82f6;margin-right:3px"></span>Solar</span>
            <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:3px"></span>Consumo</span>
            <span id="vis24hForecastLegend" style="display:none"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#f59e0b;margin-right:3px"></span>Prev.</span>
          </div>
        </div>
        <canvas id="vis24hCanvas" style="width:100%;height:200px"></canvas>
        <div id="vis24hTooltip" style="position:fixed;background:#111827;color:#fff;padding:4px 8px;border-radius:6px;font-size:12px;pointer-events:none;display:none"></div>
      </div>
    </div>

    <!-- ④ Strings (1/3) + Donuts (1/3) + Economia (1/3) -->
    <div class="cs-grid cs-grid-3" style="margin-bottom:12px">
      <div class="cs-card" id="visStringsCard">
        <div class="cs-label">Strings / MPPT</div>
        <div id="visStringsContent"><div style="font-size:11px;color:#9ca3af">Aguardando dados...</div></div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Energia hoje</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;text-align:center">
          <div>
            <div style="font-size:10px;color:#9ca3af;margin-bottom:6px">Produção</div>
            <svg id="visDonutProd" width="120" height="120" viewBox="0 0 120 120" style="display:block;margin:0 auto"></svg>
            <div id="visDonutProdLbl" style="font-size:10px;color:#9ca3af;margin-top:4px"></div>
          </div>
          <div>
            <div style="font-size:10px;color:#9ca3af;margin-bottom:6px">Consumo</div>
            <svg id="visDonutCons" width="120" height="120" viewBox="0 0 120 120" style="display:block;margin:0 auto"></svg>
            <div id="visDonutConsLbl" style="font-size:10px;color:#9ca3af;margin-top:4px"></div>
          </div>
        </div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Economia acumulada</div>
        <div class="cs-tariff-row">
          Tarifa: R$
          <input type="number" id="visTariffInput" class="cs-tariff-input" step="0.01" min="0.01" max="5" value="0.82" title="R$/kWh">
          /kWh
        </div>
        <div id="visEcoBig" class="cs-eco-big">R$ --</div>
        <div id="visEcoSub" class="cs-eco-sub">total acumulado</div>
        <div class="cs-eco-month">
          <span style="color:#6b7280">Este mês</span>
          <span id="visEcoMonth" style="color:#10b981;font-weight:700">R$ --</span>
        </div>
        <div class="cs-eco-bars" id="visEcoBars"></div>
      </div>
    </div>

    <!-- ⑤ Histórico mensal -->
    <div class="cs-card" style="margin-bottom:14px">
      <div style="display:flex;gap:12px;align-items:center;margin-bottom:8px">
        <div class="cs-label" style="margin:0">Histórico mensal</div>
        <div style="display:flex;gap:8px;font-size:11px;color:#9ca3af;margin-left:auto">
          <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#3b82f6;margin-right:3px"></span>Geração</span>
          <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#ef4444;margin-right:3px"></span>Consumo</span>
        </div>
      </div>
      <canvas id="visHistCanvas" style="width:100%;height:220px"></canvas>
    </div>

  </div>
```

- [ ] **Step 2: Verify in browser — Visual tab shows new layout, all placeholder sections visible, no JS errors**

The battery, donuts, and charts should still work (same IDs preserved).

- [ ] **Step 3: Commit**

```bash
git add dashboard.html
git commit -m "feat: rebuild Visual tab HTML with 9-section losango layout"
```

---

## Task 4: Replace `vis_renderFlow()` with losango SVG implementation

**Files:**
- Modify: `dashboard.html` — replace `vis_renderFlow()` and `vis_flowLine()` and `vis_fmtW()` functions in `<script>`

The existing `vis_renderFlow()` function (lines 314-327) uses the old positioned-div approach. Replace with losango SVG control.

- [ ] **Step 1: Replace `vis_fmtW`, `vis_flowLine`, and `vis_renderFlow` functions**

Find the block starting with:
```javascript
function vis_fmtW(w) {
```
...through the end of `vis_renderFlow` (ending at the `}` after `vis_flowLine(svg, 50, 102, 75, 146, '#ef4444', loadW > 50);`).

Replace with:

```javascript
function vis_fmtW(w) {
  const abs = Math.abs(w);
  return abs >= 1000 ? (abs / 1000).toFixed(2) + 'kW' : Math.round(abs) + 'W';
}

function _vfPath(id, color, active) {
  const el = document.getElementById(id);
  if (!el) return;
  el.setAttribute('stroke', active ? color : '#1e3a5f');
  el.setAttribute('stroke-dasharray', active ? 'none' : '5 4');
}

function _vfDot(id, visible) {
  const el = document.getElementById(id);
  if (el) el.setAttribute('visibility', visible ? 'visible' : 'hidden');
}

function _vfText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function vis_renderFlow(snapshot) {
  const pvW    = Number(snapshot.dc_power_w || snapshot.ac_power_w || snapshot.potencia_instantanea_w || 0);
  const batKw  = Number(snapshot.battery_power_kw || (snapshot.battery || {}).power_kw || 0);
  const batW   = batKw * 1000; // positive = discharging in Deye convention
  const expW   = Number(snapshot.export_power_w || 0);
  const impW   = Number(snapshot.import_power_w || 0);
  const gridW  = expW - impW; // positive = exporting
  const loadW  = Number(snapshot.load_power_w || 0);

  const solarOn  = pvW > 50;
  const batDisc  = batW > 50;
  const batChg   = batW < -50;
  const gridExp  = gridW > 50;
  const gridImp  = gridW < -50;
  const loadOn   = loadW > 50;

  // path colors + active state
  _vfPath('vfp-solar', '#f59e0b', solarOn);
  _vfPath('vfp-bat',   '#3b82f6', batDisc || batChg);
  _vfPath('vfp-grid',  '#8b5cf6', gridExp || gridImp);
  _vfPath('vfp-load',  '#10b981', loadOn);

  // dots
  _vfDot('vfd-solar',    solarOn);
  _vfDot('vfd-bat',      batDisc);
  _vfDot('vfd-bat-chg',  batChg);
  _vfDot('vfd-grid-exp', gridExp);
  _vfDot('vfd-grid-imp', gridImp);
  _vfDot('vfd-load',     loadOn);

  // labels
  _vfText('vfv-solar', vis_fmtW(pvW));
  _vfText('vfv-bat',   (batDisc ? '↑ ' : batChg ? '↓ ' : '') + vis_fmtW(Math.abs(batW)));
  _vfText('vfl-bat',   batDisc ? 'Bat ↑' : batChg ? 'Bat ↓' : 'Bateria');
  _vfText('vfv-grid',  (gridExp ? '↑ ' : gridImp ? '↓ ' : '') + vis_fmtW(Math.abs(gridW)));
  _vfText('vfl-grid',  gridExp ? 'Rede ↑' : gridImp ? 'Rede ↓' : 'Rede');
  _vfText('vfv-load',  vis_fmtW(loadW));
}
```

- [ ] **Step 2: Remove the old `vis_onTabActivated` call to `vis_renderFlow` — it's now `vis_renderFlow` (same name, so no change needed)**

Verify `vis_onTabActivated()` and `applyDashboard()` call `vis_renderFlow(data.snapshot || {})` — already the case.

- [ ] **Step 3: Open browser, go to Visual tab, verify losango SVG appears with animated dots and correct labels**

With no live data (demo mode), values will be 0 and dots hidden — this is correct.

- [ ] **Step 4: Commit**

```bash
git add dashboard.html
git commit -m "feat: replace flow diagram with animated losango SVG"
```

---

## Task 5: Add `vis_loadWeather()` — clima + previsão 7 dias

**Files:**
- Modify: `dashboard.html` — add `vis_loadWeather()` after `vis_loadHistory()` in `<script>`

- [ ] **Step 1: Add `vis_loadWeather` after the `vis_loadHistory` function**

Find the line:
```javascript
async function vis_loadHistory() {
```

After the closing `}` of `vis_loadHistory`, insert:

```javascript
let _weatherCache = null, _weatherFetchedAt = 0;

function _visWeatherIcon(cloudcover) {
  if (cloudcover < 20) return '☀️';
  if (cloudcover < 50) return '⛅';
  if (cloudcover < 80) return '🌥️';
  return '☁️';
}

function _visRenderWeather(data) {
  const cur = data.current || {};
  const daily = data.daily || {};
  const temp = Math.round(cur.temperature_2m ?? '--');
  const cloud = Math.round(cur.cloudcover ?? 0);
  const wind = Math.round(cur.windspeed_10m ?? 0);
  const hum = Math.round(cur.relative_humidity_2m ?? 0);

  const icon = _visWeatherIcon(cloud);
  const days = (daily.time || []).slice(0, 7);
  const rads = (daily.shortwave_radiation_sum || []).slice(0, 7);
  const maxRad = Math.max(1, ...rads);

  const DAY_LABELS = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const barsHtml = days.map((dateStr, i) => {
    const d = new Date(dateStr + 'T12:00:00');
    const lbl = DAY_LABELS[d.getDay()];
    const h = Math.max(4, Math.round((rads[i] / maxRad) * 44));
    const isSunny = rads[i] > maxRad * 0.5;
    const color = isSunny ? '#fcd34d' : '#93c5fd';
    return `<div class="cs-forecast-bar-col">
      <div class="cs-forecast-bar" style="height:${h}px;width:14px;background:${color}"></div>
      <div class="cs-forecast-bar-lbl">${lbl}</div>
    </div>`;
  }).join('');

  const html = `
    <div class="cs-weather-big">${icon} ${temp}°C</div>
    <div class="cs-weather-desc">${cloud < 30 ? 'Céu limpo' : cloud < 60 ? 'Parcialmente nublado' : 'Nublado'}</div>
    <div class="cs-forecast-wrap">
      <div class="cs-forecast-label">Irradiância próx. 7 dias (kWh/m²)</div>
      <div class="cs-forecast-bars">${barsHtml}</div>
    </div>
    <div class="cs-weather-row"><span>💨 Vento</span><span>${wind} km/h</span></div>
    <div class="cs-weather-row"><span>💧 Umidade</span><span>${hum}%</span></div>
    <div class="cs-weather-row"><span>☁ Nuvens</span><span>${cloud}%</span></div>
  `;
  const el = $('visWeatherContent');
  if (el) el.innerHTML = html;

  // store for forecast overlay on 24h chart
  _weatherCache = data;
}

function _visShowGeoInput() {
  const el = $('visWeatherContent');
  if (!el) return;
  el.innerHTML = `
    <div style="font-size:11px;color:#9ca3af;margin-bottom:8px">Geolocalização negada. Informe manualmente:</div>
    <div class="cs-geo-input-row">
      <input class="cs-geo-input" id="visGeoLat" placeholder="Latitude (-23.55)" type="number" step="0.0001">
      <input class="cs-geo-input" id="visGeoLon" placeholder="Longitude (-46.63)" type="number" step="0.0001">
      <button class="btn" style="font-size:11px;padding:4px 8px" onclick="vis_fetchWeatherCoords(+$('visGeoLat').value, +$('visGeoLon').value)">OK</button>
    </div>`;
}

async function vis_fetchWeatherCoords(lat, lon) {
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,cloudcover,windspeed_10m,relative_humidity_2m&daily=shortwave_radiation_sum&timezone=auto&forecast_days=7`;
    const r = await fetch(url);
    if (!r.ok) throw new Error('open-meteo error');
    const data = await r.json();
    _weatherFetchedAt = Date.now();
    _weatherCache = data;
    _visRenderWeather(data);
    // re-draw 24h chart with forecast overlay
    if (window.__lastData) {
      vis_drawChart24h(((window.__lastData.dashboard || {}).indicators || {}).hourly || {});
    }
  } catch (e) {
    const el = $('visWeatherContent');
    if (el) el.innerHTML = '<div style="font-size:11px;color:#ef4444">Previsão indisponível.</div>';
  }
}

async function vis_loadWeather() {
  // use cache if < 10 minutes old
  if (_weatherCache && Date.now() - _weatherFetchedAt < 10 * 60 * 1000) {
    _visRenderWeather(_weatherCache);
    return;
  }
  if (!navigator.geolocation) { _visShowGeoInput(); return; }
  navigator.geolocation.getCurrentPosition(
    pos => vis_fetchWeatherCoords(pos.coords.latitude, pos.coords.longitude),
    ()  => _visShowGeoInput(),
    { timeout: 8000 }
  );
}
```

- [ ] **Step 2: Call `vis_loadWeather()` from `vis_onTabActivated()`**

Find:
```javascript
function vis_onTabActivated() {
  if (window.__lastData) {
    const d = window.__lastData;
    const ind = (d.dashboard || {}).indicators || {};
    vis_renderStats(d.snapshot || {}, vis_historyRows);
    vis_renderBattery(d.snapshot || {});
    vis_renderFlow(d.snapshot || {});
    vis_drawChart24h(ind.hourly || {});
    vis_renderDonuts(ind);
    vis_drawHistory(vis_historyRows);
  }
  vis_loadHistory();
}
```

Replace with:
```javascript
function vis_onTabActivated() {
  if (window.__lastData) {
    const d = window.__lastData;
    const ind = (d.dashboard || {}).indicators || {};
    vis_renderStats(d.snapshot || {}, vis_historyRows);
    vis_renderBattery(d.snapshot || {});
    vis_renderFlow(d.snapshot || {});
    vis_drawChart24h(ind.hourly || {});
    vis_renderDonuts(ind);
    vis_drawHistory(vis_historyRows);
    vis_updateStrings(d.snapshot || {});
    vis_calcSavings(d.snapshot || {}, vis_historyRows);
  }
  vis_loadHistory();
  vis_loadWeather();
}
```

- [ ] **Step 3: Open browser, go to Visual tab, allow location permission — clima card should show temperature, cloud %, 7-day forecast bars**

If blocked, manual lat/lng inputs appear.

- [ ] **Step 4: Commit**

```bash
git add dashboard.html
git commit -m "feat: add vis_loadWeather with geolocation and Open-Meteo 7-day forecast"
```

---

## Task 6: Add forecast overlay to `vis_drawChart24h()`

**Files:**
- Modify: `dashboard.html` — update `vis_drawChart24h()` in `<script>`

Currently `vis_drawChart24h(hourly)` draws 2 series. Add a 3rd dashed amber series when `_weatherCache` has hourly radiation data.

- [ ] **Step 1: Update `vis_drawChart24h`**

Find the function:
```javascript
function vis_drawChart24h(hourly) {
```

After the two `drawArea(...)` calls and before the axis drawing code (the `ctx.fillStyle = '#9ca3af'` line for x-axis labels), insert:

```javascript
  // Forecast overlay — dashed amber line
  const hourlyRad = (_weatherCache || {}).hourly || {};
  const radVals = (hourlyRad.shortwave_radiation || []).slice(0, 24);
  if (radVals.length === 24) {
    const peakKw = Number((window.__lastData?.snapshot || {}).ac_power_peak_kw || 7.5);
    const efficiency = 0.18;
    const forecastVals = radVals.map(r => Math.min((r * efficiency * peakKw) / 1000, peakKw));
    const newMax = Math.max(maxVal, ...forecastVals);
    // rescale only if forecast exceeds current max (unlikely but safe)
    function yFc(v) { return PAD.top + chartH - (v / Math.max(maxVal, newMax)) * chartH; }
    ctx.beginPath();
    ctx.moveTo(xOf(0), yFc(forecastVals[0]));
    for (let i = 1; i < 24; i++) ctx.lineTo(xOf(i), yFc(forecastVals[i]));
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
    // store for tooltip
    canvas._vis_forecast = forecastVals;
    const leg = $('vis24hForecastLegend');
    if (leg) leg.style.display = '';
  } else {
    canvas._vis_forecast = null;
    const leg = $('vis24hForecastLegend');
    if (leg) leg.style.display = 'none';
  }
```

- [ ] **Step 2: Update the tooltip mousemove handler to include forecast value**

Find in the `attachTooltip` IIFE:
```javascript
tip.textContent = hour + 'h — Solar: ' + canvas._vis_gen[hour].toFixed(2) + ' kW | Consumo: ' + canvas._vis_load[hour].toFixed(2) + ' kW';
```
Replace with:
```javascript
const fc = canvas._vis_forecast ? ' | Prev: ' + canvas._vis_forecast[hour].toFixed(2) + ' kW' : '';
tip.textContent = hour + 'h — Solar: ' + canvas._vis_gen[hour].toFixed(2) + ' kW | Consumo: ' + canvas._vis_load[hour].toFixed(2) + ' kW' + fc;
```

- [ ] **Step 3: Verify forecast line appears on chart after weather loads (dashed amber line)**

- [ ] **Step 4: Commit**

```bash
git add dashboard.html
git commit -m "feat: add irradiance forecast overlay to 24h canvas chart"
```

---

## Task 7: Add `vis_updateStrings()` — strings/MPPT visual card

**Files:**
- Modify: `dashboard.html` — add `vis_updateStrings()` after `vis_loadWeather` block

- [ ] **Step 1: Add `vis_updateStrings` function**

After `vis_loadWeather`'s closing `}`, insert:

```javascript
function vis_updateStrings(snapshot) {
  const el = $('visStringsContent');
  if (!el) return;
  const strings = snapshot.strings || (snapshot.dc_input ? _parseDcInputStrings(snapshot.dc_input) : null);
  if (!strings || strings.length === 0) {
    el.innerHTML = '<div style="font-size:11px;color:#9ca3af">Dados de string não disponíveis.</div>';
    return;
  }
  const maxPower = Math.max(1, ...strings.map(s => Number(s.power_w || 0)));
  const faults = strings.filter(s => Number(s.power_w || 0) === 0 && maxPower > 100);
  const rows = strings.map(s => {
    const pw = Number(s.power_w || 0);
    const pct = Math.max(0, Math.min(100, (pw / maxPower) * 100));
    const ok = pw > maxPower * 0.1;
    const dotColor = ok ? '#10b981' : pw > 0 ? '#f59e0b' : '#ef4444';
    const valColor = ok ? '#6b7280' : '#ef4444';
    const valText = pw >= 1000 ? (pw/1000).toFixed(2)+' kW' : pw+'W';
    return `<div class="cs-string-row">
      <div class="cs-string-dot" style="background:${dotColor}"></div>
      <div class="cs-string-name">${s.name || 'String'}</div>
      <div class="cs-string-bar-wrap"><div class="cs-string-bar" style="width:${pct}%;background:${dotColor}"></div></div>
      <div class="cs-string-val" style="color:${valColor}">${valText}${ok?'':' ⚠'}</div>
    </div>`;
  }).join('');
  const faultBanner = faults.length > 0
    ? `<div class="cs-fault-banner">⚠ ${faults.map(s=>s.name||'String').join(', ')} sem geração — verificar conexão</div>`
    : '';
  el.innerHTML = rows + faultBanner;
}

function _parseDcInputStrings(dc) {
  // fallback: try to build string list from dc_input.mppt1/mppt2 keys
  const result = [];
  ['mppt1','mppt2','mppt3','mppt4'].forEach((k, i) => {
    const pw = dc[k+'_power_kw'];
    if (pw !== undefined) result.push({ name: 'MPPT '+(i+1), power_w: Math.round(Number(pw)*1000), voltage_v: dc[k+'_voltage_v'], current_a: dc[k+'_current_a'] });
  });
  return result;
}
```

- [ ] **Step 2: Add call to `vis_updateStrings` in `applyDashboard()`**

Find in `applyDashboard()`:
```javascript
if(mode==='visual'){vis_renderStats(data.snapshot||{},vis_historyRows);vis_renderBattery(data.snapshot||{});vis_renderFlow(data.snapshot||{});vis_drawChart24h(ind.hourly||{});vis_renderDonuts(ind);vis_drawHistory(vis_historyRows);}
```

Replace with:
```javascript
if(mode==='visual'){vis_renderStats(data.snapshot||{},vis_historyRows);vis_renderBattery(data.snapshot||{});vis_renderFlow(data.snapshot||{});vis_drawChart24h(ind.hourly||{});vis_renderDonuts(ind);vis_drawHistory(vis_historyRows);vis_updateStrings(data.snapshot||{});vis_calcSavings(data.snapshot||{},vis_historyRows);}
```

(Note: `vis_calcSavings` will be added in the next task — add the call now, define the function in Task 8.)

- [ ] **Step 3: Verify strings card shows MPPT rows or "não disponível" message**

- [ ] **Step 4: Commit**

```bash
git add dashboard.html
git commit -m "feat: add vis_updateStrings with fault detection for strings/MPPT card"
```

---

## Task 8: Add `vis_calcSavings()` — economia R$ card

**Files:**
- Modify: `dashboard.html` — add `vis_calcSavings()` function and tariff input wiring

- [ ] **Step 1: Add `vis_calcSavings` function after `vis_updateStrings`**

```javascript
function vis_calcSavings(snapshot, historyRows) {
  const tariffEl = $('visTariffInput');
  const tariff = parseFloat(tariffEl ? tariffEl.value : '0.82') || 0.82;
  const totalKwh = Number(snapshot.geracao_total_kwh || 0);
  const totalSaved = totalKwh * tariff;

  // month kWh from current month rows
  const now = new Date();
  const monthRows = (historyRows || []).filter(r => {
    const d = new Date(r.date || r.label || 0);
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  });
  const monthKwh = monthRows.reduce((s, r) => s + Number(r.geracao_kwh || 0), 0);
  const monthSaved = monthKwh * tariff;

  const el = $('visEcoBig');
  if (el) el.textContent = 'R$ ' + totalSaved.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});
  const subEl = $('visEcoSub');
  if (subEl) subEl.textContent = totalKwh.toFixed(1) + ' kWh × R$ ' + tariff.toFixed(2) + '/kWh';
  const monEl = $('visEcoMonth');
  if (monEl) monEl.textContent = 'R$ ' + monthSaved.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});

  // last 6 months bar chart
  const barsEl = $('visEcoBars');
  if (!barsEl) return;
  const last6 = (historyRows || []).slice(-180); // daily rows ~6 months
  // group by month
  const byMonth = {};
  last6.forEach(r => {
    const d = new Date(r.date || r.label || 0);
    if (isNaN(d)) return;
    const key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0');
    byMonth[key] = (byMonth[key] || 0) + Number(r.geracao_kwh || 0);
  });
  const monthKeys = Object.keys(byMonth).sort().slice(-6);
  const maxKwh = Math.max(1, ...monthKeys.map(k => byMonth[k]));
  const MON = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  barsEl.innerHTML = monthKeys.map(k => {
    const h = Math.max(4, Math.round((byMonth[k] / maxKwh) * 44));
    const [y, m] = k.split('-');
    const isCurrentMonth = parseInt(y) === now.getFullYear() && parseInt(m)-1 === now.getMonth();
    const color = isCurrentMonth ? '#059669' : '#10b981';
    return `<div class="cs-eco-bar-col">
      <div class="cs-eco-bar" style="height:${h}px;width:16px;background:${color}"></div>
      <div class="cs-eco-bar-lbl">${MON[parseInt(m)-1]}</div>
    </div>`;
  }).join('');
}
```

- [ ] **Step 2: Wire tariff input to recalculate on change**

Find the large event listener block near end of `<script>` (starts with `document.querySelectorAll('[data-days]')`). Before it, add:

```javascript
document.addEventListener('DOMContentLoaded', () => {
  const ti = $('visTariffInput');
  if (ti) {
    const saved = localStorage.getItem('cs_tariff');
    if (saved) ti.value = saved;
    ti.addEventListener('change', () => {
      localStorage.setItem('cs_tariff', ti.value);
      if (window.__lastData) vis_calcSavings(window.__lastData.snapshot || {}, vis_historyRows);
    });
  }
});
```

- [ ] **Step 3: Verify economia card shows R$ total, this month, and 6-month bars**

- [ ] **Step 4: Commit**

```bash
git add dashboard.html
git commit -m "feat: add vis_calcSavings with configurable tariff and 6-month R$ chart"
```

---

## Task 9: Rebuild Técnico tab HTML

**Files:**
- Modify: `dashboard.html` — replace `.tech-section` div (lines ~71-81) with new `#techTab`

The existing `.tech-section` div wraps the dark dark KPI cards, hour chart, gauges, etc. Replace entirely with a new light-style `#techTab`. **Important:** preserve inner element IDs that `configureLayout()`, `renderHourChart()`, `renderWeekBars()`, `renderTechnical()`, `renderAlerts()`, `renderTechAlerts()` rely on.

Required IDs to preserve inside `#techTab`:
`card1Title`, `card1Value`, `card1Strong`, `card2Title`, `card2Value`, `card2Strong`, `card2Sub`, `card3Title`, `card3Value`, `card3Strong`, `headline`, `subline`, `pvNow`, `loadNow`, `flowMidLabel`, `flowEndLabel`, `gridNow`, `flowIconMid`, `flowIconEnd`, `miniTitle1`, `gaugeValue`, `gaugeLabel`, `gauge`, `miniRows1`, `miniTitle2`, `prValue`, `diffExp`, `prStatus`, `miniRows2`, `axisY`, `genLine`, `loadLine`, `axisX`, `weekBars`, `alerts`, `reports`, `recs`, `simplePanel`, `techPanel`, `techGroups`, `techAlerts`, `techAuthBadge`

Also preserve: inverter config section IDs `inverterDesc`, `detectionInfo`, `btnClearOverride`.

- [ ] **Step 1: Find and replace the `.tech-section` div block**

Find:
```html
  <div class="tech-section">
```
...through its matching `</div>` (which is the last `</div>` before `</div></div>` near `</div></div></div>` at end of body HTML).

Replace the entire block with:

```html
  <div id="techTab">

    <!-- Inverter config (auth-gated) -->
    <div class="cs-card tech-only hidden" id="technicalAccessPanelNew" style="margin-bottom:12px">
      <div class="cs-label">Configuração do inversor</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px">
        <button class="btn" data-inverter="on-grid">On-grid</button>
        <button class="btn" data-inverter="off-grid">Off-grid</button>
        <button class="btn" data-inverter="hybrid">Híbrido</button>
        <button class="btn" id="btnClearOverride">Limpar override</button>
      </div>
      <div style="font-size:12px;color:#6b7280" id="inverterDesc"></div>
      <div style="font-size:11px;color:#9ca3af;margin-top:4px" id="detectionInfo"></div>
    </div>

    <!-- Range selector -->
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button class="btn active" data-days="1">Hoje</button>
      <button class="btn" data-days="7">7 dias</button>
      <button class="btn" data-days="30">30 dias</button>
    </div>

    <!-- KPI cards (4 chips) -->
    <div class="cs-grid cs-grid-4" style="margin-bottom:12px">
      <div class="cs-kpi-card">
        <div class="cs-label" id="card1Title">Geração do dia</div>
        <div class="cs-stat-value" id="card1Value" style="color:#f59e0b">0,00</div>
        <div style="font-size:12px;font-weight:600;margin-top:4px" id="card1Strong">--</div>
        <div style="font-size:12px;color:#9ca3af" id="headline">Aguardando dados</div>
      </div>
      <div class="cs-kpi-card">
        <div class="cs-label" id="card2Title">Economia do dia</div>
        <div class="cs-stat-value" id="card2Value" style="color:#10b981">0,00</div>
        <div style="font-size:12px;font-weight:600;margin-top:4px" id="card2Strong">--</div>
        <div style="font-size:12px;color:#9ca3af" id="card2Sub">--</div>
      </div>
      <div class="cs-kpi-card">
        <div class="cs-label" id="card3Title">Enviado à rede</div>
        <div class="cs-stat-value" id="card3Value" style="color:#3b82f6">0,00</div>
        <div style="font-size:12px;font-weight:600;margin-top:4px" id="card3Strong">--</div>
        <div style="font-size:12px;color:#9ca3af" id="subline">Aguardando primeira leitura.</div>
      </div>
      <div class="cs-kpi-card">
        <div class="cs-label">Fluxo agora</div>
        <div style="display:flex;justify-content:space-around;margin-top:6px">
          <div style="text-align:center">
            <div style="font-size:11px;color:#9ca3af">☀️</div>
            <div style="font-size:12px;font-weight:700;color:#f59e0b" id="pvNow">0,00 kW</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:11px;color:#9ca3af" id="flowIconMid">⌂</div>
            <div style="font-size:12px;font-weight:700" id="loadNow">0,00 kW</div>
            <div style="font-size:9px;color:#9ca3af" id="flowMidLabel">Carga</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:11px;color:#9ca3af" id="flowIconEnd">↯</div>
            <div style="font-size:12px;font-weight:700;color:#3b82f6" id="gridNow">0,00 kW</div>
            <div style="font-size:9px;color:#9ca3af" id="flowEndLabel">Rede</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Losango flow (2/3) + Battery technical (1/3) -->
    <div class="cs-grid cs-grid-2-1" style="margin-bottom:12px">
      <div class="cs-flow-card">
        <div class="cs-label">Fluxo técnico</div>
        <div class="cs-losango-wrap">
          <svg class="cs-losango-svg" id="techFlowSvg" viewBox="0 0 300 240" preserveAspectRatio="xMidYMid meet" style="height:180px">
            <path id="tfp-solar" d="M 60,40  L 150,120" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <path id="tfp-bat"   d="M 60,200 L 150,120" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <path id="tfp-grid"  d="M 150,120 L 240,40"  fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <path id="tfp-load"  d="M 150,120 L 240,200" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-dasharray="5 4"/>
            <circle id="tfd-solar" r="5" fill="#f59e0b" visibility="hidden"><animateMotion dur="1.2s" repeatCount="indefinite"><mpath href="#tfp-solar"/></animateMotion></circle>
            <circle id="tfd-bat"   r="5" fill="#3b82f6" visibility="hidden"><animateMotion dur="1.4s" repeatCount="indefinite"><mpath href="#tfp-bat"/></animateMotion></circle>
            <circle id="tfd-bat-chg" r="5" fill="#3b82f6" visibility="hidden"><animateMotion dur="1.4s" repeatCount="indefinite" keyPoints="1;0" keyTimes="0;1" calcMode="linear"><mpath href="#tfp-bat"/></animateMotion></circle>
            <circle id="tfd-grid-exp" r="5" fill="#8b5cf6" visibility="hidden"><animateMotion dur="1.3s" repeatCount="indefinite"><mpath href="#tfp-grid"/></animateMotion></circle>
            <circle id="tfd-grid-imp" r="5" fill="#8b5cf6" visibility="hidden"><animateMotion dur="1.3s" repeatCount="indefinite" keyPoints="1;0" keyTimes="0;1" calcMode="linear"><mpath href="#tfp-grid"/></animateMotion></circle>
            <circle id="tfd-load"  r="5" fill="#10b981" visibility="hidden"><animateMotion dur="1.1s" repeatCount="indefinite"><mpath href="#tfp-load"/></animateMotion></circle>
            <g transform="translate(60,40)"><circle r="24" fill="rgba(245,158,11,.15)"/><text y="6" text-anchor="middle" font-size="18">☀️</text><text id="tfv-solar" y="42" text-anchor="middle" font-size="9" font-weight="700" fill="#f59e0b">0W</text><text y="54" text-anchor="middle" font-size="8" fill="#4b6280">Solar</text></g>
            <g transform="translate(60,200)"><circle r="24" fill="rgba(59,130,246,.15)"/><text y="6" text-anchor="middle" font-size="18">🔋</text><text id="tfv-bat" y="42" text-anchor="middle" font-size="9" font-weight="700" fill="#3b82f6">0W</text><text id="tfl-bat" y="54" text-anchor="middle" font-size="8" fill="#4b6280">Bateria</text></g>
            <g transform="translate(150,120)"><circle r="28" fill="rgba(255,255,255,.10)"/><text y="7" text-anchor="middle" font-size="22">🏠</text><text y="40" text-anchor="middle" font-size="8" fill="#4b6280">Casa</text></g>
            <g transform="translate(240,40)"><circle r="24" fill="rgba(139,92,246,.15)"/><text y="6" text-anchor="middle" font-size="18">⚡</text><text id="tfv-grid" y="42" text-anchor="middle" font-size="9" font-weight="700" fill="#8b5cf6">0W</text><text id="tfl-grid" y="54" text-anchor="middle" font-size="8" fill="#4b6280">Rede</text></g>
            <g transform="translate(240,200)"><circle r="24" fill="rgba(16,185,129,.15)"/><text y="6" text-anchor="middle" font-size="18">🏭</text><text id="tfv-load" y="42" text-anchor="middle" font-size="9" font-weight="700" fill="#10b981">0W</text><text y="54" text-anchor="middle" font-size="8" fill="#4b6280">Consumo</text></g>
          </svg>
        </div>
      </div>
      <div class="cs-card">
        <div class="cs-label">Bateria — detalhe</div>
        <div id="techBattSoc" class="cs-soc">--%</div>
        <div class="cs-progress-wrap"><div id="techBattBar" class="cs-progress-bar" style="width:0%;background:#10b981"></div></div>
        <div id="techBattMode" class="cs-batt-mode">--</div>
        <table style="width:100%;font-size:11px;color:#374151;border-collapse:collapse">
          <tr><td style="color:#9ca3af;padding:2px 0">Tensão</td><td id="techBattV" style="text-align:right;font-weight:600">-- V</td></tr>
          <tr><td style="color:#9ca3af;padding:2px 0">Corrente</td><td id="techBattA" style="text-align:right;font-weight:600">-- A</td></tr>
          <tr><td style="color:#9ca3af;padding:2px 0">Potência</td><td id="techBattW" style="text-align:right;font-weight:600">-- W</td></tr>
          <tr><td style="color:#9ca3af;padding:2px 0">Temperatura</td><td id="techBattTemp" style="text-align:right;font-weight:600">-- °C</td></tr>
          <tr><td style="color:#9ca3af;padding:2px 0">Disponível</td><td id="techBattKwh" style="text-align:right;font-weight:600">-- kWh</td></tr>
        </table>
      </div>
    </div>

    <!-- Strings detail table (auth-gated) -->
    <div class="cs-card tech-only hidden" id="techStringsCard" style="margin-bottom:12px">
      <div class="cs-label">Strings / MPPT — detalhe</div>
      <div id="techStringsContent"><div style="font-size:11px;color:#9ca3af">Aguardando dados...</div></div>
    </div>

    <!-- Hora a hora (2/3) + Gauges (1/3) -->
    <div class="cs-grid cs-grid-2-1" style="margin-bottom:12px">
      <div class="cs-card">
        <div class="cs-label">Geração hora a hora (kW)</div>
        <div style="position:relative;height:220px;background:#f9fafb;border-radius:10px;padding:16px">
          <div class="axis-y" id="axisY"></div>
          <div class="chart-grid"></div>
          <svg class="line-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
            <polyline id="genLine" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline id="loadLine" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div class="axis-x" id="axisX"></div>
        </div>
        <div class="legend" style="margin-top:8px">
          <span><i style="background:#f59e0b"></i>Geração</span>
          <span><i style="background:#3b82f6"></i><span id="legendLoad">Consumo</span></span>
        </div>
      </div>
      <div>
        <div class="cs-card" style="margin-bottom:12px">
          <div class="cs-label" id="miniTitle1">Autoconsumo</div>
          <div class="gauge-card">
            <div style="position:relative;width:100px">
              <div class="gauge" id="gauge" style="--gauge:0%;width:100px;height:100px"></div>
              <div class="gauge-center"><div><strong id="gaugeValue" style="font-size:20px">0%</strong><br><span id="gaugeLabel" style="font-size:10px;color:#9ca3af">Solar</span></div></div>
            </div>
            <div class="metric-stack" id="miniRows1"></div>
          </div>
        </div>
        <div class="cs-card">
          <div class="cs-label" id="miniTitle2">Performance ratio</div>
          <div class="kpi-value" id="prValue" style="font-size:26px">0,00</div>
          <div style="margin-top:4px"><strong id="diffExp" style="font-size:12px">0%</strong><br><span id="prStatus" style="font-size:12px;color:#9ca3af">Sem interpretação</span></div>
          <div class="metric-stack" style="margin-top:8px" id="miniRows2"></div>
        </div>
      </div>
    </div>

    <!-- Weekly history -->
    <div class="cs-card" style="margin-bottom:12px">
      <div class="cs-label">Histórico semanal (kWh)</div>
      <div class="bars" id="weekBars" style="height:180px"></div>
    </div>

    <!-- Alerts (simple) -->
    <div class="cs-card" id="simplePanel" style="margin-bottom:12px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
        <div class="cs-label" style="margin:0;flex:1">Alertas e orientações</div>
        <button class="btn active" data-sev="all">Todos</button>
        <button class="btn" data-sev="critical">Crítico</button>
        <button class="btn" data-sev="warning">Warning</button>
        <button class="btn" data-sev="info">Info</button>
      </div>
      <div class="list" id="alerts"></div>
      <div class="list" id="reports" style="margin-top:10px"></div>
      <div class="list" id="recs" style="margin-top:10px"></div>
    </div>

    <!-- Tech alerts (auth-gated) -->
    <div class="cs-card hidden tech-only" id="techPanel" style="margin-bottom:12px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
        <div class="cs-label" style="margin:0;flex:1">Painel técnico</div>
        <span class="success-chip" id="techAuthBadge">Técnico autenticado</span>
        <button class="btn active" data-tech-sev="all">Todos</button>
        <button class="btn" data-tech-sev="critical">Crítico</button>
        <button class="btn" data-tech-sev="warning">Warning</button>
        <button class="btn" data-tech-sev="info">Info</button>
      </div>
      <div class="tech-panel" id="techGroups"></div>
      <div class="list alarm-tech" id="techAlerts" style="margin-top:12px"></div>
    </div>

  </div>
```

- [ ] **Step 2: Remove the now-redundant old `#technicalAccessPanel` section**

Find:
```html
  <section class="section inverter-config tech-only hidden" id="technicalAccessPanel">
    <h2 class="section-title">Configuração do inversor</h2>
    <div class="selector"><strong>Override manual</strong><button class="btn" data-inverter="on-grid">On-grid</button><button class="btn" data-inverter="off-grid">Off-grid</button><button class="btn" data-inverter="hybrid">Híbrido</button><button class="btn" id="btnClearOverride">Limpar override</button></div>
    <div class="selector-desc" id="inverterDesc">...</div>
    <div class="selector-desc" id="detectionInfo">...</div>
  </section>
```
Remove this entire section (it is now replaced by `technicalAccessPanelNew` inside `#techTab`).

- [ ] **Step 3: Update `applyAuthState()` to reference `technicalAccessPanelNew` instead of `technicalAccessPanel`**

Find in `applyAuthState()`:
```javascript
$('technicalAccessPanel').classList.toggle('hidden',!authStatus.authenticated||mode!=='tech');
```
Replace with:
```javascript
const tap = $('technicalAccessPanelNew') || $('technicalAccessPanel');
if (tap) tap.classList.toggle('hidden', !authStatus.authenticated || mode !== 'tech');
```

- [ ] **Step 4: Remove orphaned auth panel section from HTML (the shared `<section class="auth-panel">` block)**

The auth-panel section in the HTML (with `authSummary`, `authHint`, `techLockState`, the tab-toggle buttons) — verify it still exists and IDs `authSummary`, `authHint`, `techLockState`, `btnTabVisual`, `btnTabTech` still work. Do not remove it.

- [ ] **Step 5: Verify in browser — Técnico tab renders with light style, all existing functionality works (day filter, severity filter, auth flow)**

- [ ] **Step 6: Commit**

```bash
git add dashboard.html
git commit -m "feat: rebuild Técnico tab with light theme keeping all existing function wiring"
```

---

## Task 10: Add `tech_renderFlow()` and `tech_updateBatteryDetail()`

**Files:**
- Modify: `dashboard.html` — add tech_ functions to `<script>`

- [ ] **Step 1: Add `tech_renderFlow` and `tech_updateBatteryDetail` after `vis_calcSavings`**

```javascript
function tech_renderFlow(snapshot) {
  const pvW   = Number(snapshot.dc_power_w || snapshot.ac_power_w || snapshot.potencia_instantanea_w || 0);
  const batKw = Number(snapshot.battery_power_kw || (snapshot.battery || {}).power_kw || 0);
  const batW  = batKw * 1000;
  const expW  = Number(snapshot.export_power_w || 0);
  const impW  = Number(snapshot.import_power_w || 0);
  const gridW = expW - impW;
  const loadW = Number(snapshot.load_power_w || 0);

  const solarOn = pvW > 50, batDisc = batW > 50, batChg = batW < -50;
  const gridExp = gridW > 50, gridImp = gridW < -50, loadOn = loadW > 50;

  function tp(id, color, active) {
    const el = document.getElementById(id);
    if (!el) return;
    el.setAttribute('stroke', active ? color : '#1e3a5f');
    el.setAttribute('stroke-dasharray', active ? 'none' : '5 4');
  }
  function td(id, vis) {
    const el = document.getElementById(id);
    if (el) el.setAttribute('visibility', vis ? 'visible' : 'hidden');
  }
  function tv(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  tp('tfp-solar', '#f59e0b', solarOn);
  tp('tfp-bat',   '#3b82f6', batDisc || batChg);
  tp('tfp-grid',  '#8b5cf6', gridExp || gridImp);
  tp('tfp-load',  '#10b981', loadOn);

  td('tfd-solar',    solarOn);
  td('tfd-bat',      batDisc);
  td('tfd-bat-chg',  batChg);
  td('tfd-grid-exp', gridExp);
  td('tfd-grid-imp', gridImp);
  td('tfd-load',     loadOn);

  // Show W (not kW) for precision
  function fmtWExact(w) { return Math.abs(w) >= 1000 ? (Math.abs(w)/1000).toFixed(3)+'kW' : Math.round(Math.abs(w))+'W'; }
  tv('tfv-solar', fmtWExact(pvW));
  tv('tfv-bat',   (batDisc?'↑ ':batChg?'↓ ':'')+fmtWExact(Math.abs(batW)));
  tv('tfl-bat',   batDisc?'Bat ↑':batChg?'Bat ↓':'Bateria');
  tv('tfv-grid',  (gridExp?'↑ ':gridImp?'↓ ':'')+fmtWExact(Math.abs(gridW)));
  tv('tfl-grid',  gridExp?'Rede ↑':gridImp?'Rede ↓':'Rede');
  tv('tfv-load',  fmtWExact(loadW));
}

function tech_updateBatteryDetail(snapshot) {
  const batt = snapshot.battery || {};
  const soc  = Number(batt.soc_percent || snapshot.battery_soc_percent || 0);
  const kw   = Number(batt.power_kw || snapshot.battery_power_kw || 0);
  const v    = Number(batt.voltage_v || snapshot.battery_voltage_v || 0);
  const a    = Number(batt.current_a || snapshot.battery_current_a || 0);
  const temp = batt.temp_c ?? batt.temperature_c ?? null;
  const kwh  = Number(batt.available_energy_kwh || 0);
  const bmode= batt.mode || snapshot.battery_mode || 'idle';
  const modeMap = { charging: '⬆ Carregando', discharging: '⬇ Descarregando', idle: '— Parado' };
  const color = soc >= 60 ? '#10b981' : soc >= 30 ? '#f59e0b' : '#ef4444';

  const socEl = $('techBattSoc'); if (socEl) { socEl.textContent = soc.toFixed(0) + '%'; socEl.style.color = color; }
  const barEl = $('techBattBar'); if (barEl) { barEl.style.width = soc + '%'; barEl.style.background = color; }
  const modeEl = $('techBattMode'); if (modeEl) { modeEl.textContent = modeMap[bmode] || bmode; modeEl.style.color = color; }
  const setTd = (id, val) => { const e = $(id); if (e) e.textContent = val; };
  setTd('techBattV',    v ? v.toFixed(1) + ' V' : '-- V');
  setTd('techBattA',    a ? a.toFixed(1) + ' A' : '-- A');
  setTd('techBattW',    kw ? Math.round(kw * 1000) + ' W' : '-- W');
  setTd('techBattTemp', temp !== null ? temp.toFixed(1) + ' °C' : '-- °C');
  setTd('techBattKwh',  kwh ? kwh.toFixed(2) + ' kWh' : '-- kWh');
}

function tech_updateStrings(snapshot) {
  const el = $('techStringsContent');
  if (!el) return;
  const strings = snapshot.strings || (snapshot.dc_input ? _parseDcInputStrings(snapshot.dc_input) : null);
  if (!strings || strings.length === 0) {
    el.innerHTML = '<div style="font-size:11px;color:#9ca3af">Dados de string não disponíveis.</div>';
    return;
  }
  const header = `<table class="cs-table">
    <thead><tr>
      <th>String</th><th>Status</th><th>Tensão</th><th>Corrente</th><th>Potência</th><th>Temp.</th>
    </tr></thead><tbody>`;
  const maxPower = Math.max(1, ...strings.map(s => Number(s.power_w || 0)));
  const rows = strings.map(s => {
    const pw = Number(s.power_w || 0);
    const ok = pw > maxPower * 0.1;
    const statusClass = pw > 50 ? 'cs-badge-ok' : pw > 0 ? 'cs-badge-low' : 'cs-badge-fail';
    const statusText  = pw > 50 ? 'OK' : pw > 0 ? 'Baixo' : 'Falha';
    const temp = s.temp_c ?? s.temperature_c;
    return `<tr>
      <td style="font-weight:600">${s.name || 'String'}</td>
      <td><span class="cs-badge ${statusClass}">${statusText}</span></td>
      <td>${s.voltage_v != null ? Number(s.voltage_v).toFixed(1)+' V' : '--'}</td>
      <td>${s.current_a != null ? Number(s.current_a).toFixed(2)+' A' : '--'}</td>
      <td style="font-weight:600">${pw >= 1000 ? (pw/1000).toFixed(2)+' kW' : pw+'W'}</td>
      <td>${temp != null ? Number(temp).toFixed(1)+' °C' : '--'}</td>
    </tr>`;
  }).join('');
  el.innerHTML = header + rows + '</tbody></table>';
}
```

- [ ] **Step 2: Call tech functions from `applyDashboard()`**

In `applyDashboard()`, after the existing `if(mode==='visual'){...}` block, add:

```javascript
if(mode==='tech'){tech_renderFlow(data.snapshot||{});tech_updateBatteryDetail(data.snapshot||{});tech_updateStrings(data.snapshot||{});}
```

- [ ] **Step 3: Verify in browser — switch to Técnico tab, tech flow SVG animates, battery detail table populates, strings table appears when authenticated**

- [ ] **Step 4: Commit**

```bash
git add dashboard.html
git commit -m "feat: add tech_renderFlow, tech_updateBatteryDetail, tech_updateStrings for Técnico tab"
```

---

## Task 11: Update `setMode()` to trigger tech functions and wire auth panel

**Files:**
- Modify: `dashboard.html` — update `setMode()` and `applyAuthState()`

Currently `setMode('tech')` doesn't call tech_ functions. Fix.

- [ ] **Step 1: Update `setMode()`**

Find:
```javascript
function setMode(next) {
  // tech tab requires auth
  if (next === 'tech' && !authStatus.authenticated) { openTechModal(); return; }
  mode = next;
  const isVis = mode === 'visual';
  const isTech = mode === 'tech';
  document.body.classList.toggle('tab-visual', isVis);
  document.body.classList.toggle('tab-tech', isTech);
  $('btnTabVisual').classList.toggle('active', isVis);
  $('btnTabTech').classList.toggle('active', isTech);
  $('btnTechLogout').classList.toggle('hidden', !authStatus.authenticated);
  // keep existing auth state rendering
  applyAuthState();
  if ($('simplePanel')) $('simplePanel').classList.toggle('hidden', mode === 'tech' && !!authStatus.authenticated);
  if (isVis) vis_onTabActivated();
}
```

Replace with:
```javascript
function setMode(next) {
  if (next === 'tech' && !authStatus.authenticated) { openTechModal(); return; }
  mode = next;
  const isVis = mode === 'visual';
  const isTech = mode === 'tech';
  document.body.classList.toggle('tab-visual', isVis);
  document.body.classList.toggle('tab-tech', isTech);
  $('btnTabVisual').classList.toggle('active', isVis);
  $('btnTabTech').classList.toggle('active', isTech);
  $('btnTechLogout').classList.toggle('hidden', !authStatus.authenticated);
  applyAuthState();
  if ($('simplePanel')) $('simplePanel').classList.toggle('hidden', isTech && !!authStatus.authenticated);
  if (isVis) vis_onTabActivated();
  if (isTech && window.__lastData) {
    const d = window.__lastData;
    tech_renderFlow(d.snapshot || {});
    tech_updateBatteryDetail(d.snapshot || {});
    tech_updateStrings(d.snapshot || {});
    renderHourChart(((d.dashboard || {}).indicators || {}).hourly || {});
    renderWeekBars(d.history_filtered || []);
  }
}
```

- [ ] **Step 2: Verify switching from Visual → Técnico correctly renders all tech sections**

- [ ] **Step 3: Commit**

```bash
git add dashboard.html
git commit -m "feat: update setMode to trigger tech tab render functions on activation"
```

---

## Task 12: Mobile responsive fixes and final polish

**Files:**
- Modify: `dashboard.html` — CSS media query adjustments, visual polish

- [ ] **Step 1: Verify mobile layout at 375px width**

Open browser devtools → toggle device toolbar → set to 375px wide. Check:
- Stats bar chips: should be 2×2 grid (not 4 in one row)
- Losango flow: should be full width, readable node labels
- Clima + 24h chart: should stack vertically

- [ ] **Step 2: Fix stats bar to 2-column on mobile**

Add to the CSS block (after the `@media (max-width: 700px)` rule):
```css
@media (max-width: 500px) {
  .cs-grid-4 { grid-template-columns: repeat(2, 1fr); }
  .cs-span-4 { grid-column: span 2; }
}
```

- [ ] **Step 3: Verify losango SVG scales correctly on mobile**

The SVG uses `viewBox="0 0 300 240"` with `width:100%` — it should scale. If nodes appear cut off, add to CSS:
```css
.cs-losango-svg { overflow: visible; }
```

- [ ] **Step 4: Remove obsolete dark-theme CSS rules that now conflict**

The old CSS block had `.tab-visual{background:#f5f7fa;...}` already. Verify the new `:root`/`.tab-visual`/`.tab-tech` rules from Task 1 take precedence. If there are `!important` conflicts, remove the old `.tab-visual` rule:

Find in the old CSS (around lines 9-10):
```css
/* ── Visual tab theme ── */
.tab-visual{background:#f5f7fa;color:#111827;min-height:100vh}
.tab-visual .vis-card{...}
```
Remove these lines since they are superseded by the new CSS from Task 1.

- [ ] **Step 5: Run existing Python tests to confirm server is unchanged**

```bash
python -m pytest tests.py test_http.py -v
```
Expected: all tests pass (server code unchanged).

- [ ] **Step 6: Final browser check — both tabs at desktop (1280px) and mobile (375px)**

Checklist:
- [ ] Visual tab: stats, losango flow, battery, weather, 24h chart, strings, donuts, economy, history — all render
- [ ] Visual tab: switching to Técnico with wrong password → modal appears
- [ ] Técnico tab: KPI cards, tech losango, battery detail, hora-a-hora chart, gauge — all render
- [ ] Técnico tab: login → strings table, tech alerts, inverter config appear
- [ ] Both tabs: mobile layout is readable, no overflow

- [ ] **Step 7: Commit**

```bash
git add dashboard.html
git commit -m "fix: mobile responsive grid for stats bar and losango SVG; remove obsolete dark CSS"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Style system: light bg, white cards, dark flow card, amber/blue/purple/green/red accents — Task 1
- ✅ Tab toggle: same HTML, CSS visibility — Task 1+2
- ✅ Stats bar (4 chips): visStat1-4 — Task 3
- ✅ Losango flow + animateMotion: Task 3+4
- ✅ Battery card (visual): visBattSoc etc — Task 3
- ✅ Clima + Previsão 7d Open-Meteo geolocation: Task 5
- ✅ Forecast overlay on 24h chart: Task 6
- ✅ Strings/MPPT visual: Task 7
- ✅ Donuts (existing): IDs preserved in Task 3
- ✅ Economia R$ + tarifa + 6-month bars: Task 8
- ✅ Histórico mensal (existing canvas): ID preserved in Task 3
- ✅ Tech tab HTML rebuild: Task 9
- ✅ Tech KPI chips: Task 9
- ✅ Tech losango flow (W precision): Task 10
- ✅ Tech battery detail (V/A/W/temp): Task 10
- ✅ Tech strings table (V/A/W/temp/status): Task 10
- ✅ Tech hora-a-hora (existing SVG): IDs preserved in Task 9
- ✅ Tech gauge autoconsumo + PR: IDs preserved in Task 9
- ✅ Tech alerts (existing): IDs preserved in Task 9
- ✅ Inverter config (auth-gated): Task 9
- ✅ Mobile responsive: Task 12
- ✅ No server changes: confirmed — no Python files touched

**Type consistency check:**
- `vis_renderFlow` called with `(snapshot)` throughout ✅
- `vis_updateStrings` / `tech_updateStrings` both call `_parseDcInputStrings(snapshot.dc_input)` ✅
- `_parseDcInputStrings` defined once before first use ✅
- `tech_renderFlow` uses `tfp-*`/`tfd-*`/`tfv-*` IDs matching Task 9 SVG ✅
- `vis_renderFlow` uses `vfp-*`/`vfd-*`/`vfv-*` IDs matching Task 3 SVG ✅

**Placeholder scan:** No TBD or TODO in plan ✅
