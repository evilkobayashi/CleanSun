# Visual Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Visual" tab to `dashboard.html` with light theme, animated energy-flow diagram, battery card, 24h area chart, donut charts, and monthly history — toggling with the existing "Técnico" tab.

**Architecture:** Single-file modification to `dashboard.html`. New CSS scoped under `.tab-visual`, new JS functions prefixed `vis_`. Visual tab is the default; Técnico tab is the existing dark panel. No new server endpoints, no external libraries.

**Tech Stack:** HTML/CSS/JS (vanilla), Canvas 2D API for charts, SVG + CSS `@keyframes` for flow animation.

---

## File Map

| File | Change |
|------|--------|
| `dashboard.html` | All changes — CSS (lines 8), HTML (lines 11–50), JS (lines 54–89) |

All insertions are additive. Existing Técnico code is untouched except: (a) topbar buttons replaced by tab toggle, (b) `setMode` extended to handle `'visual'`.

---

## Task 1: Tab scaffold — CSS + HTML toggle + JS setMode extension

**Files:**
- Modify: `dashboard.html`

Add light-theme CSS variables, tab-scoped `.tab-visual` / `.tab-tech` visibility classes, and the tab toggle buttons in the topbar. Extend `setMode` to handle `'visual'`.

- [ ] **Step 1: Add Visual tab CSS** — insert before `</style>` on line 8:

```css
/* ── Visual tab theme ── */
.tab-visual{background:#f5f7fa;color:#111827}
.tab-visual .vis-card{background:#fff;border-radius:12px;box-shadow:0 1px 6px rgba(0,0,0,.08);padding:16px}
.tab-visual .vis-muted{color:#6b7280}
.tab-visual .vis-label{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#9ca3af}
/* show/hide per tab */
.tab-visual .vis-section{display:block}
.tab-visual .tech-section{display:none!important}
.tab-tech .vis-section{display:none!important}
.tab-tech .tech-section{display:block}
/* tab toggle */
.tab-toggle{display:flex;gap:0;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb}
.tab-toggle button{padding:8px 20px;border:none;background:#f9fafb;color:#6b7280;font:inherit;font-size:13px;cursor:pointer;transition:all .15s}
.tab-toggle button.active{background:#fff;color:#111827;font-weight:600;box-shadow:0 1px 4px rgba(0,0,0,.1)}
```

- [ ] **Step 2: Replace topbar action buttons with tab toggle** — in the HTML, find:

```html
<button class="btn outline" id="btnSimple">Painel simplificado</button>
<button class="btn warn" id="btnTechAccess">Acesso técnico</button>
<button class="btn danger hidden" id="btnTechLogout">Sair do modo técnico</button>
```

Replace with:

```html
<div class="tab-toggle">
  <button id="btnTabVisual" class="active" onclick="setMode('visual')">☀ Visual</button>
  <button id="btnTabTech" onclick="setMode('tech')">⚙ Técnico</button>
</div>
<button class="btn danger hidden" id="btnTechLogout" onclick="logoutTechnical()">Sair do modo técnico</button>
```

- [ ] **Step 3: Wrap existing dark sections in `tech-section` divs** — wrap the existing `<div class="toggle-line"...`, all `<section class="section"...` elements (KPI cards, flow, charts, etc.), and `<section class="section hidden tech-only"...` inside:

```html
<div class="tech-section">
  <!-- all existing dark sections go here unchanged -->
</div>
```

Add an empty Visual tab container after it:

```html
<div class="vis-section" id="visTab"></div>
```

- [ ] **Step 4: Extend `setMode` in JS** — replace existing `setMode` function:

```js
function setMode(next) {
  // tech tab requires auth
  if (next === 'tech' && !authStatus.authenticated) { openTechModal(); return; }
  mode = next;
  const isVis = mode === 'visual';
  const isTech = mode === 'tech';
  document.body.classList.toggle('tab-visual', isVis);
  document.body.classList.toggle('tab-tech', isTech || (!isVis && mode === 'simple'));
  $('btnTabVisual').classList.toggle('active', isVis);
  $('btnTabTech').classList.toggle('active', isTech);
  $('btnTechLogout').classList.toggle('hidden', !authStatus.authenticated);
  // keep existing auth state rendering
  applyAuthState();
  if (isVis) vis_onTabActivated();
}
```

- [ ] **Step 5: Change default mode in `connect()`** — find `setMode('simple')` and change to `setMode('visual')`.

- [ ] **Step 6: Stub `vis_onTabActivated`** — add before `connect()`:

```js
function vis_onTabActivated() { /* populated in later tasks */ }
```

- [ ] **Step 7: Open browser at http://localhost:9191** — verify two tab buttons appear in topbar. Clicking "⚙ Técnico" should show existing dark panel. Clicking "☀ Visual" shows empty white page. No console errors.

- [ ] **Step 8: Commit**

```bash
git add dashboard.html
git commit -m "feat: add Visual/Técnico tab scaffold to dashboard"
```

---

## Task 2: Stats Bar

**Files:**
- Modify: `dashboard.html`

Four metric chips in a row at the top of the Visual tab.

- [ ] **Step 1: Add stats bar HTML** — inside `<div id="visTab">`, add:

```html
<div class="vis-section" id="visTab">
  <!-- ① Stats bar -->
  <div id="visStats" style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">
    <div class="vis-card" style="flex:1;min-width:140px">
      <div class="vis-label">Produção total</div>
      <div id="visStat1" style="font-size:26px;font-weight:700;color:#f59e0b">-- kWh</div>
    </div>
    <div class="vis-card" style="flex:1;min-width:140px">
      <div class="vis-label">Injetado na rede</div>
      <div id="visStat2" style="font-size:26px;font-weight:700;color:#3b82f6">-- kWh</div>
    </div>
    <div class="vis-card" style="flex:1;min-width:140px">
      <div class="vis-label">Dias de operação</div>
      <div id="visStat3" style="font-size:26px;font-weight:700;color:#6b7280">--</div>
    </div>
    <div class="vis-card" style="flex:1;min-width:140px">
      <div class="vis-label">Redução CO₂</div>
      <div id="visStat4" style="font-size:26px;font-weight:700;color:#10b981">-- T</div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add `vis_renderStats` JS function**:

```js
function vis_renderStats(snapshot, historyRows) {
  const totalKwh = Number(snapshot.geracao_total_kwh || 0);
  const exportKwh = Number((snapshot.energy || {}).export_kwh || snapshot.export_power_w / 1000 || 0);
  const co2T = (totalKwh * 0.0004).toFixed(2);
  const activeDays = (historyRows || []).filter(r => Number(r.geracao_kwh || 0) > 0).length;
  $('visStat1').textContent = totalKwh.toFixed(1) + ' kWh';
  $('visStat2').textContent = exportKwh.toFixed(1) + ' kWh';
  $('visStat3').textContent = activeDays || '--';
  $('visStat4').textContent = co2T + ' T';
}
```

- [ ] **Step 3: Declare `vis_historyRows` at top of script** — add alongside other state vars:

```js
let vis_historyRows = [];
```

- [ ] **Step 4: Call `vis_renderStats` from `applyDashboard`** — at the end of `applyDashboard`:

```js
if (mode === 'visual') vis_renderStats(data.snapshot || {}, vis_historyRows);
```

- [ ] **Step 5: Verify in browser** — switch to Visual tab. Stats bar shows 4 cards with real values from inverter. No console errors.

- [ ] **Step 6: Commit**

```bash
git add dashboard.html
git commit -m "feat: add stats bar to Visual tab"
```

---

## Task 3: Battery Card

**Files:**
- Modify: `dashboard.html`

1/3-width card showing SOC, progress bar, mode, power, available energy.

- [ ] **Step 1: Add battery card HTML** — add inside `#visTab` after the stats bar div, as a grid container that will also hold the flow diagram:

```html
  <!-- ② Flow + Battery row -->
  <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:16px">
    <div class="vis-card" id="visFlow">
      <div class="vis-label" style="margin-bottom:12px">Fluxo de energia</div>
      <!-- populated in Task 4 -->
    </div>
    <div class="vis-card" id="visBattCard">
      <div class="vis-label" style="margin-bottom:8px">Bateria</div>
      <div id="visBattSoc" style="font-size:42px;font-weight:700;text-align:center;margin:8px 0">--%</div>
      <div style="background:#e5e7eb;border-radius:999px;height:8px;margin-bottom:10px">
        <div id="visBattBar" style="height:100%;border-radius:999px;background:#10b981;width:0%;transition:width .5s"></div>
      </div>
      <div id="visBattMode" style="font-size:13px;font-weight:600;text-align:center;margin-bottom:6px">--</div>
      <div style="display:flex;justify-content:space-between;font-size:12px;color:#6b7280">
        <span id="visBattKw">-- kW</span>
        <span id="visBattKwh">-- kWh disp.</span>
      </div>
    </div>
  </div>
```

- [ ] **Step 2: Add `vis_renderBattery` JS function**:

```js
function vis_renderBattery(snapshot) {
  const batt = snapshot.battery || {};
  const soc = Number(batt.soc_percent || snapshot.battery_soc_percent || 0);
  const kw = Number(batt.power_kw || snapshot.battery_power_kw || 0);
  const kwh = Number(batt.available_energy_kwh || 0);
  const mode = batt.mode || snapshot.battery_mode || 'idle';
  const modeMap = { charging: 'Carregando', discharging: 'Descarregando', idle: 'Parado' };
  const color = soc >= 60 ? '#10b981' : soc >= 30 ? '#f59e0b' : '#ef4444';
  $('visBattSoc').textContent = soc.toFixed(0) + '%';
  $('visBattSoc').style.color = color;
  $('visBattBar').style.width = soc + '%';
  $('visBattBar').style.background = color;
  $('visBattMode').textContent = modeMap[mode] || mode;
  $('visBattMode').style.color = color;
  $('visBattKw').textContent = Math.abs(kw).toFixed(2) + ' kW';
  $('visBattKwh').textContent = kwh.toFixed(1) + ' kWh disp.';
}
```

- [ ] **Step 3: Call from `applyDashboard`** — append to the `if (mode === 'visual')` block:

```js
if (mode === 'visual') {
  vis_renderStats(data.snapshot || {}, vis_historyRows);
  vis_renderBattery(data.snapshot || {});
}
```

- [ ] **Step 4: Verify in browser** — battery card shows SOC, progress bar, mode and power from real inverter data.

- [ ] **Step 5: Commit**

```bash
git add dashboard.html
git commit -m "feat: add battery card to Visual tab"
```

---

## Task 4: Fluxograma animado

**Files:**
- Modify: `dashboard.html`

SVG-based energy flow diagram with animated dots on active paths.

- [ ] **Step 1: Add flow diagram CSS** — append to the `<style>` block:

```css
/* ── Flow diagram ── */
.vis-flow-wrap{position:relative;width:100%;height:200px}
.vis-node{position:absolute;text-align:center;width:64px;transform:translateX(-50%)}
.vis-node-icon{font-size:28px;line-height:1}
.vis-node-val{font-size:12px;font-weight:700;margin-top:2px}
.vis-node-lbl{font-size:10px;color:#9ca3af}
.vis-flow-svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
@keyframes vis-dot-move{to{offset-distance:100%}}
.vis-dot{position:absolute;width:8px;height:8px;border-radius:50%;offset-distance:0%;animation:vis-dot-move 1.8s linear infinite}
```

- [ ] **Step 2: Add flow diagram HTML** — replace the `<!-- populated in Task 4 -->` comment inside `#visFlow`:

```html
<div class="vis-flow-wrap" id="visFlowWrap">
  <!-- SVG lines drawn by vis_renderFlow -->
  <svg class="vis-flow-svg" id="visFlowSvg"></svg>
  <!-- Nodes -->
  <div class="vis-node" id="vfSolar" style="left:12%;top:20px">
    <div class="vis-node-icon">☀️</div>
    <div class="vis-node-val" id="vfSolarVal" style="color:#f59e0b">0W</div>
    <div class="vis-node-lbl">Solar</div>
  </div>
  <div class="vis-node" id="vfCasa" style="left:50%;top:70px">
    <div class="vis-node-icon">🏠</div>
    <div class="vis-node-val" style="color:#374151">Casa</div>
  </div>
  <div class="vis-node" id="vfBatt" style="left:25%;top:130px">
    <div class="vis-node-icon">🔋</div>
    <div class="vis-node-val" id="vfBattVal" style="color:#10b981">0W</div>
    <div class="vis-node-lbl">Bateria</div>
  </div>
  <div class="vis-node" id="vfRede" style="left:75%;top:20px">
    <div class="vis-node-icon">⚡</div>
    <div class="vis-node-val" id="vfRedeVal" style="color:#3b82f6">0W</div>
    <div class="vis-node-lbl">Rede</div>
  </div>
  <div class="vis-node" id="vfLoad" style="left:75%;top:130px">
    <div class="vis-node-icon">🏭</div>
    <div class="vis-node-val" id="vfLoadVal" style="color:#ef4444">0W</div>
    <div class="vis-node-lbl">Consumo</div>
  </div>
</div>
```

- [ ] **Step 3: Add `vis_renderFlow` JS function**:

```js
function vis_fmtW(w) {
  const abs = Math.abs(w);
  return abs >= 1000 ? (abs/1000).toFixed(1)+'kW' : abs+'W';
}

function vis_flowLine(svg, x1pct, y1, x2pct, y2, color, active) {
  const wrap = $('visFlowWrap');
  const W = wrap.offsetWidth || 300;
  const x1 = W * x1pct / 100, x2 = W * x2pct / 100;
  const id = 'vfl_' + x1pct+'_'+y1+'_'+x2pct+'_'+y2;
  let path = svg.querySelector('#'+id);
  if (!path) {
    path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.id = id;
    path.setAttribute('fill','none');
    path.setAttribute('stroke-width','2');
    svg.appendChild(path);
  }
  // cubic bezier
  const cx = (x1+x2)/2;
  path.setAttribute('d', `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`);
  path.setAttribute('stroke', active ? color : '#e5e7eb');
  path.setAttribute('stroke-dasharray', active ? 'none' : '4 4');

  // animated dot
  const dotId = 'vfd_'+id;
  let dot = document.getElementById(dotId);
  if (active) {
    if (!dot) {
      dot = document.createElement('div');
      dot.id = dotId;
      dot.className = 'vis-dot';
      dot.style.background = color;
      dot.style.offsetPath = `path("M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}")`;
      $('visFlowWrap').appendChild(dot);
    } else {
      dot.style.offsetPath = `path("M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}")`;
      dot.style.display = '';
    }
  } else if (dot) {
    dot.style.display = 'none';
  }
}

function vis_renderFlow(snapshot) {
  const pvW = Number(snapshot.dc_power_w || 0);
  const battW = Number(snapshot.battery_power_kw || 0) * 1000; // + = charging
  const gridW = Number(snapshot.import_power_w || 0) - Number(snapshot.export_power_w || 0); // + = import
  const loadW = Number(snapshot.load_power_w || 0);

  $('vfSolarVal').textContent = vis_fmtW(pvW);
  $('vfBattVal').textContent = (battW > 0 ? '+' : '') + vis_fmtW(battW);
  $('vfRedeVal').textContent = (gridW > 0 ? '+' : '') + vis_fmtW(gridW);
  $('vfLoadVal').textContent = vis_fmtW(loadW);

  const svg = $('visFlowSvg');
  // Solar → Casa (left to center top)
  vis_flowLine(svg, 12, 56, 50, 86, '#f59e0b', pvW > 50);
  // Bateria ↔ Casa
  vis_flowLine(svg, 25, 146, 50, 102, '#10b981', Math.abs(battW) > 50);
  // Casa → Rede (export) or Rede → Casa (import)
  vis_flowLine(svg, 50, 86, 75, 56, gridW < -50 ? '#3b82f6' : '#94a3b8', Math.abs(gridW) > 50);
  // Casa → Consumo
  vis_flowLine(svg, 50, 102, 75, 146, '#ef4444', loadW > 50);
}
```

- [ ] **Step 4: Call from `applyDashboard`** — extend the `if (mode === 'visual')` block:

```js
if (mode === 'visual') {
  vis_renderStats(data.snapshot || {}, vis_historyRows);
  vis_renderBattery(data.snapshot || {});
  vis_renderFlow(data.snapshot || {});
}
```

- [ ] **Step 5: Verify in browser** — flow diagram shows nodes connected by lines. When battery is charging, animated dot moves from battery to house. Solar → Casa line is animated when PV > 50W.

- [ ] **Step 6: Commit**

```bash
git add dashboard.html
git commit -m "feat: add animated energy flow diagram to Visual tab"
```

---

## Task 5: Curva 24h (Canvas)

**Files:**
- Modify: `dashboard.html`

Full-width Canvas 2D area chart showing solar generation vs consumption hour by hour.

- [ ] **Step 1: Add chart HTML** — inside `#visTab` after the flow+battery grid div:

```html
  <!-- ③ Curva 24h -->
  <div class="vis-card" style="margin-bottom:16px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <div class="vis-label">Curva 24h</div>
      <div style="display:flex;gap:12px;font-size:12px;color:#6b7280">
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#3b82f6;margin-right:4px"></span>Solar</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:4px"></span>Consumo</span>
      </div>
    </div>
    <canvas id="vis24hCanvas" style="width:100%;height:200px"></canvas>
    <div id="vis24hTooltip" style="position:fixed;background:#111827;color:#fff;padding:4px 8px;border-radius:6px;font-size:12px;pointer-events:none;display:none"></div>
  </div>
```

- [ ] **Step 2: Add `vis_drawChart24h` JS function**:

```js
function vis_drawChart24h(hourly) {
  const canvas = $('vis24hCanvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = canvas.offsetHeight * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = canvas.offsetWidth, H = canvas.offsetHeight;
  const PAD = { top: 10, right: 10, bottom: 24, left: 36 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  const genVals = [], loadVals = [];
  for (let i = 0; i < 24; i++) {
    const h = (hourly || {})[String(i)] || {};
    genVals.push(Number(h.generation_w || 0) / 1000);
    loadVals.push(Number(h.consumption_w || 0) / 1000);
  }
  const maxVal = Math.max(0.5, ...genVals, ...loadVals);

  function xOf(i) { return PAD.left + (i / 23) * chartW; }
  function yOf(v) { return PAD.top + chartH - (v / maxVal) * chartH; }

  ctx.clearRect(0, 0, W, H);

  // grid lines
  ctx.strokeStyle = '#f3f4f6'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = PAD.top + (chartH / 4) * i;
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(W - PAD.right, y); ctx.stroke();
  }

  // draw filled area for each series
  function drawArea(vals, lineColor, fillColor) {
    ctx.beginPath();
    ctx.moveTo(xOf(0), yOf(vals[0]));
    for (let i = 1; i < 24; i++) ctx.lineTo(xOf(i), yOf(vals[i]));
    ctx.lineTo(xOf(23), PAD.top + chartH);
    ctx.lineTo(xOf(0), PAD.top + chartH);
    ctx.closePath();
    ctx.fillStyle = fillColor; ctx.fill();
    ctx.beginPath();
    ctx.moveTo(xOf(0), yOf(vals[0]));
    for (let i = 1; i < 24; i++) ctx.lineTo(xOf(i), yOf(vals[i]));
    ctx.strokeStyle = lineColor; ctx.lineWidth = 2; ctx.stroke();
  }

  drawArea(loadVals, '#ef4444', 'rgba(239,68,68,.12)');
  drawArea(genVals, '#3b82f6', 'rgba(59,130,246,.15)');

  // x-axis labels
  ctx.fillStyle = '#9ca3af'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
  [0, 4, 8, 12, 16, 20, 23].forEach(i => {
    ctx.fillText(i + 'h', xOf(i), H - 4);
  });

  // y-axis labels
  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const v = maxVal * (1 - i / 4);
    const y = PAD.top + (chartH / 4) * i;
    ctx.fillText(v.toFixed(1), PAD.left - 4, y + 3);
  }

  // store for tooltip
  canvas._vis_gen = genVals; canvas._vis_load = loadVals; canvas._vis_maxVal = maxVal;
  canvas._vis_PAD = PAD; canvas._vis_chartW = chartW; canvas._vis_chartH = chartH;
}
```

- [ ] **Step 3: Add tooltip hover handler** — add after `vis_drawChart24h` definition:

```js
(function() {
  const canvas = document.getElementById('vis24hCanvas');
  if (!canvas) return;
  canvas.addEventListener('mousemove', e => {
    if (!canvas._vis_gen) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const PAD = canvas._vis_PAD, chartW = canvas._vis_chartW;
    const hour = Math.round((x - PAD.left) / chartW * 23);
    if (hour < 0 || hour > 23) { $('vis24hTooltip').style.display='none'; return; }
    const tip = $('vis24hTooltip');
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 10) + 'px';
    tip.style.top = (e.clientY - 28) + 'px';
    tip.textContent = hour + 'h — Solar: ' + canvas._vis_gen[hour].toFixed(2) + ' kW | Consumo: ' + canvas._vis_load[hour].toFixed(2) + ' kW';
  });
  canvas.addEventListener('mouseleave', () => { $('vis24hTooltip').style.display='none'; });
})();
```

- [ ] **Step 4: Call from `applyDashboard`** — extend the `if (mode === 'visual')` block:

```js
if (mode === 'visual') {
  vis_renderStats(data.snapshot || {}, vis_historyRows);
  vis_renderBattery(data.snapshot || {});
  vis_renderFlow(data.snapshot || {});
  vis_drawChart24h((data.dashboard || {}).indicators?.hourly || {});
}
```

- [ ] **Step 5: Verify in browser** — 24h area chart shows two filled curves. Hover shows tooltip with solar + consumption values.

- [ ] **Step 6: Commit**

```bash
git add dashboard.html
git commit -m "feat: add 24h area chart to Visual tab"
```

---

## Task 6: Donut charts (SVG)

**Files:**
- Modify: `dashboard.html`

Two stacked SVG ring charts: Produção breakdown and Consumo breakdown.

- [ ] **Step 1: Add donuts + history row HTML** — inside `#visTab` after the 24h card:

```html
  <!-- ④ Donuts + Histórico -->
  <div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;margin-bottom:16px">
    <div class="vis-card">
      <div class="vis-label" style="margin-bottom:10px">Energia hoje</div>
      <!-- Produção donut -->
      <div style="text-align:center;margin-bottom:12px">
        <div style="font-size:11px;color:#6b7280;margin-bottom:4px">Produção</div>
        <svg id="visDonutProd" width="120" height="120" viewBox="0 0 120 120" style="display:block;margin:0 auto"></svg>
        <div id="visDonutProdLbl" style="font-size:11px;color:#6b7280;margin-top:4px"></div>
      </div>
      <!-- Consumo donut -->
      <div style="text-align:center">
        <div style="font-size:11px;color:#6b7280;margin-bottom:4px">Consumo</div>
        <svg id="visDonutCons" width="120" height="120" viewBox="0 0 120 120" style="display:block;margin:0 auto"></svg>
        <div id="visDonutConsLbl" style="font-size:11px;color:#6b7280;margin-top:4px"></div>
      </div>
    </div>
    <div class="vis-card">
      <div class="vis-label" style="margin-bottom:8px">Histórico mensal</div>
      <canvas id="visHistCanvas" style="width:100%;height:220px"></canvas>
    </div>
  </div>
```

- [ ] **Step 2: Add `vis_drawDonut` and `vis_renderDonuts` JS functions**:

```js
function vis_drawDonut(svgEl, segments, centerLabel) {
  // segments: [{value, color, label}]
  const R = 44, r = 28, cx = 60, cy = 60;
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  let angle = -Math.PI / 2;
  svgEl.innerHTML = '';

  segments.forEach(seg => {
    const frac = seg.value / total;
    const sweep = frac * 2 * Math.PI;
    const x1 = cx + R * Math.cos(angle), y1 = cy + R * Math.sin(angle);
    const x2 = cx + R * Math.cos(angle + sweep), y2 = cy + R * Math.sin(angle + sweep);
    const xi1 = cx + r * Math.cos(angle), yi1 = cy + r * Math.sin(angle);
    const xi2 = cx + r * Math.cos(angle + sweep), yi2 = cy + r * Math.sin(angle + sweep);
    const large = sweep > Math.PI ? 1 : 0;
    if (frac < 0.001) { angle += sweep; return; }
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${x1},${y1} A${R},${R} 0 ${large},1 ${x2},${y2} L${xi2},${yi2} A${r},${r} 0 ${large},0 ${xi1},${yi1} Z`);
    path.setAttribute('fill', seg.color);
    svgEl.appendChild(path);
    angle += sweep;
  });

  // center label
  const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text.setAttribute('x', cx); text.setAttribute('y', cy + 5);
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('font-size', '13'); text.setAttribute('font-weight', '700');
  text.setAttribute('fill', '#111827');
  text.textContent = centerLabel;
  svgEl.appendChild(text);
}

function vis_renderDonuts(indicators) {
  const gen = Number(indicators.geracao_kwh || 0);
  const exp = Number(indicators.exportado_kwh || 0);
  const imp = Number(indicators.importado_kwh || 0);
  const selfConsumption = Math.max(0, gen - exp);
  const battCharge = 0; // not directly available from indicators, use 0

  vis_drawDonut($('visDonutProd'), [
    { value: exp, color: '#3b82f6', label: 'Rede' },
    { value: selfConsumption, color: '#f59e0b', label: 'Autoconsumo' },
    { value: battCharge, color: '#10b981', label: 'Bateria' }
  ], gen.toFixed(1) + '\nkWh');

  $('visDonutProdLbl').innerHTML =
    `<span style="color:#3b82f6">▪</span> Rede: ${exp.toFixed(1)} kWh&nbsp;&nbsp;` +
    `<span style="color:#f59e0b">▪</span> Auto: ${selfConsumption.toFixed(1)} kWh`;

  const cons = Number(indicators.consumo_kwh || (selfConsumption + imp));
  vis_drawDonut($('visDonutCons'), [
    { value: selfConsumption, color: '#f59e0b', label: 'Solar' },
    { value: imp, color: '#ef4444', label: 'Rede' }
  ], cons.toFixed(1) + '\nkWh');

  $('visDonutConsLbl').innerHTML =
    `<span style="color:#f59e0b">▪</span> Solar: ${selfConsumption.toFixed(1)} kWh&nbsp;&nbsp;` +
    `<span style="color:#ef4444">▪</span> Rede: ${imp.toFixed(1)} kWh`;
}
```

- [ ] **Step 3: Call from `applyDashboard`** — extend the `if (mode === 'visual')` block:

```js
if (mode === 'visual') {
  const ind = (data.dashboard || {}).indicators || {};
  vis_renderStats(data.snapshot || {}, vis_historyRows);
  vis_renderBattery(data.snapshot || {});
  vis_renderFlow(data.snapshot || {});
  vis_drawChart24h(ind.hourly || {});
  vis_renderDonuts(ind);
}
```

- [ ] **Step 4: Verify in browser** — two donut rings appear. Produção shows rede vs autoconsumo segments. Colors match spec.

- [ ] **Step 5: Commit**

```bash
git add dashboard.html
git commit -m "feat: add donut charts to Visual tab"
```

---

## Task 7: Histórico mensal (Canvas)

**Files:**
- Modify: `dashboard.html`

Grouped bar chart of daily generation vs consumption for the last 30 days.

- [ ] **Step 1: Add `vis_drawHistory` JS function**:

```js
function vis_drawHistory(rows) {
  const canvas = $('visHistCanvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = canvas.offsetHeight * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = canvas.offsetWidth, H = canvas.offsetHeight;
  const PAD = { top: 10, right: 10, bottom: 28, left: 36 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  const data = (rows || []).slice(-30);
  if (!data.length) return;
  const maxVal = Math.max(0.5, ...data.map(r => Math.max(Number(r.geracao_kwh || 0), Number(r.consumo_kwh || 0))));
  const n = data.length;
  const barGroupW = chartW / n;
  const barW = Math.max(2, barGroupW * 0.35);

  ctx.clearRect(0, 0, W, H);

  // grid
  ctx.strokeStyle = '#f3f4f6'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = PAD.top + (chartH / 4) * i;
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(W - PAD.right, y); ctx.stroke();
  }

  data.forEach((row, i) => {
    const gen = Number(row.geracao_kwh || 0);
    const cons = Number(row.consumo_kwh || 0);
    const x = PAD.left + i * barGroupW + barGroupW / 2;
    const genH = (gen / maxVal) * chartH;
    const consH = (cons / maxVal) * chartH;
    // generation bar (blue)
    ctx.fillStyle = '#3b82f6';
    ctx.fillRect(x - barW - 1, PAD.top + chartH - genH, barW, genH);
    // consumption bar (red)
    ctx.fillStyle = '#ef4444';
    ctx.fillRect(x + 1, PAD.top + chartH - consH, barW, consH);
    // x label (every 5 days)
    if (i % 5 === 0 || i === n - 1) {
      ctx.fillStyle = '#9ca3af'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText(row.label || (i + 1), x, H - 4);
    }
  });

  // y-axis labels
  ctx.fillStyle = '#9ca3af'; ctx.font = '9px sans-serif'; ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const v = maxVal * (1 - i / 4);
    const y = PAD.top + (chartH / 4) * i;
    ctx.fillText(v.toFixed(1), PAD.left - 4, y + 3);
  }
}
```

- [ ] **Step 2: Add `vis_loadHistory` function and call on tab activation**:

```js
async function vis_loadHistory() {
  try {
    const r = await fetch('/api/history?days=30&bucket=daily', { credentials: 'same-origin' });
    const data = await r.json();
    vis_historyRows = data.rows || [];
    vis_drawHistory(vis_historyRows);
    vis_renderStats(window.__lastData?.snapshot || {}, vis_historyRows);
  } catch (e) { /* silent */ }
}
```

- [ ] **Step 3: Update `vis_onTabActivated`** — replace the stub:

```js
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

- [ ] **Step 4: Set up history polling** — add inside `connect()`, after the SSE setup:

```js
// Refresh history every 5 minutes when on Visual tab
setInterval(() => { if (mode === 'visual') vis_loadHistory(); }, 5 * 60 * 1000);
```

- [ ] **Step 5: Verify in browser** — monthly bar chart shows blue (geração) and red (consumo) paired bars per day. Refreshes when switching to Visual tab.

- [ ] **Step 6: Commit**

```bash
git add dashboard.html
git commit -m "feat: add monthly history bar chart to Visual tab"
```

---

## Task 8: Final polish + responsive + integration smoke test

**Files:**
- Modify: `dashboard.html`

- [ ] **Step 1: Add responsive grid fallback CSS** — append to `<style>`:

```css
@media(max-width:700px){
  #visTab [style*="grid-template-columns:2fr 1fr"],
  #visTab [style*="grid-template-columns:1fr 2fr"]{grid-template-columns:1fr!important}
  .vis-flow-wrap{height:260px}
}
```

- [ ] **Step 2: Add canvas resize handler** — add before `connect()`:

```js
window.addEventListener('resize', () => {
  if (mode !== 'visual' || !window.__lastData) return;
  const d = window.__lastData;
  vis_drawChart24h(((d.dashboard || {}).indicators || {}).hourly || {});
  vis_drawHistory(vis_historyRows);
});
```

- [ ] **Step 3: Smoke test checklist** — open http://localhost:9191 and verify:
  - [ ] Default view is Visual tab (white background)
  - [ ] Stats bar shows real values (Produção total > 0)
  - [ ] Fluxo diagram: 5 nodes visible, lines connect them
  - [ ] Battery card: SOC % matches `/api/health` data, progress bar colored correctly
  - [ ] 24h chart: two area series visible, tooltip appears on hover
  - [ ] Donuts: two rings render with correct colors
  - [ ] History: bar pairs visible for available days
  - [ ] Click "⚙ Técnico" → dark panel appears (existing layout unchanged)
  - [ ] Click "☀ Visual" → white panel returns, no data loss
  - [ ] Resize window → layout adjusts, charts redraw
  - [ ] No console errors

- [ ] **Step 4: Push to remote**

```bash
git add dashboard.html
git commit -m "feat: complete Visual tab — responsive polish and resize handler"
git push origin feat/solarman-deye-integration:codex/fix-high-priority-bug-in-http_server.py
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| Visual tab toggle | Task 1 |
| Light theme CSS scoped to `.tab-visual` | Task 1 |
| Técnico tab preserved | Task 1 |
| Stats bar (4 metrics) | Task 2 |
| Fluxograma animado (CSS dots) | Task 4 |
| Bateria card (SOC, bar, mode, kW) | Task 3 |
| Curva 24h Canvas (area, tooltip) | Task 5 |
| Donuts SVG (produção + consumo) | Task 6 |
| Histórico mensal Canvas | Task 7 |
| SSE real-time → fluxo+stats+bateria | Task 7 `vis_onTabActivated` + `applyDashboard` |
| `/api/v1/dashboard` → curva+donuts | Task 5–6 |
| `/api/history?days=30` → histórico | Task 7 |
| No external deps | All tasks — Canvas API + SVG only |
| `vis_` prefix for new JS | All tasks |
