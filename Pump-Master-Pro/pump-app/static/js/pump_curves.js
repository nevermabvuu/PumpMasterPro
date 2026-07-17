/**
 * pump_curves.js — Warman-style pump curve rendering with Plotly
 * Covers: Warman performance map, standalone curves, isoline overlay, comparison helpers
 */

/* ── Plotly dark theme ────────────────────────────────────────────────────── */
const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor:  '#0d1117',
  font:   { color: '#8b949e', size: 11, family: 'system-ui, sans-serif' },
  xaxis:  { gridcolor: '#21262d', zerolinecolor: '#30363d',
             tickfont: { color: '#8b949e' }, titlefont: { color: '#c9d1d9', size: 12 } },
  yaxis:  { gridcolor: '#21262d', zerolinecolor: '#30363d',
             tickfont: { color: '#8b949e' }, titlefont: { color: '#c9d1d9', size: 12 } },
  margin: { l: 58, r: 24, t: 28, b: 52 },
  showlegend: true,
  legend: { bgcolor: 'rgba(22,27,34,0.88)', bordercolor: '#30363d', borderwidth: 1,
            font: { color: '#c9d1d9', size: 10 }, x: 0.01, y: 0.99, xanchor: 'left', yanchor: 'top' },
  hovermode: 'closest',
  hoverlabel: { bgcolor: '#161b22', bordercolor: '#58a6ff', font: { color: '#e6edf3', size: 11 } },
};

const PLOTLY_CONFIG = {
  responsive: true, displayModeBar: true,
  modeBarButtonsToRemove: ['select2d', 'lasso2d'],
  displaylogo: false,
  toImageButtonOptions: { format: 'png', width: 1400, height: 800 }
};

/* ── Diameter family colour palette ──────────────────────────────────────── */
// Blues for H-Q curves (darker = larger diameter)
const DIA_BLUES  = ['#1c6fbf','#2a85d4','#3fa0e8','#58b8ff','#82cdff','#b3e0ff'];
const PUMP_COLORS = ['#58a6ff','#3fb950','#f0c040','#f85149','#bc8cff','#39d3c0'];

// Efficiency isoline palette — warm yellows → greens
function isoColor(eta, etaMin, etaMax) {
  const t = etaMax > etaMin ? (eta - etaMin) / (etaMax - etaMin) : 0.5;
  // lerp: yellow (#f0c040) → green (#3fb950)
  const r = Math.round(240 + t * (63  - 240));
  const g = Math.round(192 + t * (185 - 192));
  const b = Math.round( 64 + t * ( 80 -  64));
  return `rgb(${r},${g},${b})`;
}

/* ── Generic layout builder ──────────────────────────────────────────────── */
function makeLayout(xTitle, yTitle, extra = {}) {
  return Object.assign({}, PLOTLY_LAYOUT_BASE, {
    xaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.xaxis, { title: xTitle }),
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: yTitle }),
  }, extra);
}

/* ── Duty point marker ───────────────────────────────────────────────────── */
function dutyTrace(q, h) {
  return {
    type: 'scatter', mode: 'markers', name: 'Duty Point',
    x: [q], y: [h],
    marker: { size: 14, color: '#ffffff', symbol: 'cross-open', line: { color: '#ff4444', width: 2.5 } },
    hovertemplate: `Duty<br>Q = ${q} m³/h<br>H = ${h} m<extra></extra>`,
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   WARMAN PERFORMANCE MAP
   ══════════════════════════════════════════════════════════════════════════ */

/* ── Speed-line colour palette — warm oranges ────────────────────────────── */
const SPD_COLORS = ['#664400','#995500','#cc7700','#ff9900'];  // 70%→80%→90%→100%

function buildWarmanChart(data, opts = {}) {
  const { showIsolines = true, showPowerIso = false, showSpeedLines = false, dutyQ, dutyH } = opts;
  const traces = [];
  const family     = data.family      || [];
  const isolines   = data.isolines    || [];
  const pwr_iso    = data.power_isolines || [];
  const spd_lines  = data.speed_lines || [];

  const nDia = family.length;

  /* ── H-Q curves (one per diameter) ──── */
  family.forEach((d, i) => {
    const col = DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)];
    const lw  = d.is_max ? 2.5 : 1.8;
    traces.push({
      type: 'scatter', mode: 'lines',
      name: `Ø${d.dia} mm`,
      x: d.q, y: d.h,
      line: { color: col, width: lw },
      hovertemplate: `Ø${d.dia} mm<br>Q=%{x:.1f} m³/h<br>H=%{y:.2f} m<extra></extra>`,
    });

    /* BEP star on each curve */
    if (d.bep) {
      traces.push({
        type: 'scatter', mode: 'markers',
        name: `BEP Ø${d.dia}`,
        x: [d.bep.q], y: [d.bep.h],
        marker: { size: d.is_max ? 10 : 7, color: col, symbol: 'star',
                  line: { color: '#fff', width: 1 } },
        showlegend: false,
        hovertemplate: `BEP Ø${d.dia}<br>Q=${d.bep.q}<br>H=${d.bep.h}<br>η=${d.bep.eta}%<extra></extra>`,
      });
    }
  });

  /* ── Efficiency isolines ──── */
  if (showIsolines && isolines.length > 0) {
    const etaVals = isolines.map(l => l.eta);
    const etaMin  = Math.min(...etaVals);
    const etaMax  = Math.max(...etaVals);

    isolines.forEach(iso => {
      const col = isoColor(iso.eta, etaMin, etaMax);
      traces.push({
        type: 'scatter', mode: 'lines',
        name: `η = ${iso.eta}%`,
        x: iso.q, y: iso.h,
        line: { color: col, width: 1.4, dash: 'dot' },
        fill: 'none',
        hovertemplate: `η = ${iso.eta}%<br>Q=%{x:.1f}<br>H=%{y:.2f}<extra></extra>`,
        showlegend: false,
      });

      /* Efficiency label annotation handled via scatter text */
      traces.push({
        type: 'scatter', mode: 'text',
        x: [iso.label_q], y: [iso.label_h],
        text: [`${iso.eta}%`],
        textfont: { color: col, size: 9.5 },
        showlegend: false, hoverinfo: 'skip',
      });
    });
  }

  /* ── Power isolines ──── */
  if (showPowerIso && pwr_iso.length > 0) {
    pwr_iso.forEach(pl => {
      traces.push({
        type: 'scatter', mode: 'lines',
        name: `P = ${pl.power} kW`,
        x: pl.q, y: pl.h,
        line: { color: '#f85149', width: 1.2, dash: 'longdash' },
        showlegend: false,
        hovertemplate: `P = ${pl.power} kW<br>Q=%{x:.1f}<br>H=%{y:.2f}<extra></extra>`,
      });
      if (pl.q.length > 0) {
        const mi = Math.floor(pl.q.length / 2);
        traces.push({
          type: 'scatter', mode: 'text',
          x: [pl.q[mi]], y: [pl.h[mi]],
          text: [`${pl.power}kW`],
          textfont: { color: '#f85149', size: 9 },
          showlegend: false, hoverinfo: 'skip',
        });
      }
    });
  }

  /* ── Speed lines ──── */
  if (showSpeedLines && spd_lines.length > 0) {
    spd_lines.forEach((sl, i) => {
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lw  = sl.speed_ratio === 1.0 ? 2.2 : 1.5;
      traces.push({
        type: 'scatter', mode: 'lines',
        name: `${sl.speed_rpm} rpm (${Math.round(sl.speed_ratio * 100)}%)`,
        x: sl.q, y: sl.h,
        line: { color: col, width: lw, dash: sl.speed_ratio === 1.0 ? 'solid' : 'dot' },
        hovertemplate: `${sl.speed_rpm} rpm<br>Q=%{x:.1f} m³/h<br>H=%{y:.2f} m<extra></extra>`,
      });
      /* BEP tick on speed line */
      if (sl.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `BEP ${sl.speed_rpm}rpm`,
          x: [sl.bep.q], y: [sl.bep.h],
          marker: { size: 6, color: col, symbol: 'diamond',
                    line: { color: '#fff', width: 0.8 } },
          showlegend: false,
          hovertemplate: `BEP ${sl.speed_rpm}rpm<br>Q=${sl.bep.q}<br>H=${sl.bep.h}<extra></extra>`,
        });
      }
    });
  }

  /* ── System curve ──── */
  if (data.system_q && data.system_h) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'System Curve',
      x: data.system_q, y: data.system_h,
      line: { color: '#bc8cff', width: 2, dash: 'dash' },
      hovertemplate: 'System<br>Q=%{x:.1f}<br>H_sys=%{y:.2f} m<extra></extra>',
    });
  }

  /* ── Duty point ──── */
  if (dutyQ && dutyH) traces.push(dutyTrace(dutyQ, dutyH));

  const layout = makeLayout('Flow Q (m³/h)', 'Head H (m)', {
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: 'Head H (m)', rangemode: 'tozero' }),
  });

  return { traces, layout };
}

/* ── NPSH family chart ───────────────────────────────────────────────────── */
function buildNpshFamilyChart(family) {
  const traces = family.map((d, i) => ({
    type: 'scatter', mode: 'lines',
    name: `Ø${d.dia} mm`,
    x: d.q, y: d.npsh,
    line: { color: DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)], width: 1.8 },
    hovertemplate: `Ø${d.dia}<br>Q=%{x:.1f}<br>NPSHr=%{y:.2f} m<extra></extra>`,
  }));
  return { traces, layout: makeLayout('Flow Q (m³/h)', 'NPSHr (m)',
    { yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { rangemode: 'tozero' }) }) };
}

/* ── Power family chart ──────────────────────────────────────────────────── */
function buildPowerFamilyChart(family) {
  const traces = family.map((d, i) => ({
    type: 'scatter', mode: 'lines',
    name: `Ø${d.dia} mm`,
    x: d.q, y: d.power,
    line: { color: DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)], width: 1.8 },
    hovertemplate: `Ø${d.dia}<br>Q=%{x:.1f}<br>P=%{y:.2f} kW<extra></extra>`,
  }));
  return { traces, layout: makeLayout('Flow Q (m³/h)', 'Shaft Power P (kW)',
    { yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { rangemode: 'tozero' }) }) };
}

/* ══════════════════════════════════════════════════════════════════════════
   STANDALONE SINGLE-DIAMETER CURVES (max impeller)
   ══════════════════════════════════════════════════════════════════════════ */

function buildHQChart(data, showSystem, showClean) {
  const traces = [];
  traces.push({
    type: 'scatter', mode: 'lines',
    name: 'H-Q ' + (data.liquid !== 'water' ? `(${data.liquid})` : ''),
    x: data.q, y: data.h,
    line: { color: '#58a6ff', width: 2.5 },
    hovertemplate: 'Q=%{x:.1f} m³/h<br>H=%{y:.2f} m<extra></extra>',
  });
  if (showClean && data.h_clean) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'H-Q (water ref)',
      x: data.q, y: data.h_clean,
      line: { color: '#58a6ff', width: 1.5, dash: 'dot' }, opacity: 0.45, showlegend: true,
      hovertemplate: 'Q=%{x:.1f}<br>H(clean)=%{y:.2f}<extra></extra>' });
  }
  if (showSystem && data.system_h) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'System Curve',
      x: data.q, y: data.system_h, line: { color: '#bc8cff', width: 2, dash: 'dash' },
      hovertemplate: 'Q=%{x:.1f}<br>H_sys=%{y:.2f}<extra></extra>' });
  }
  if (data.bep) {
    traces.push({ type: 'scatter', mode: 'markers', name: 'BEP',
      x: [data.bep.q], y: [data.bep.h],
      marker: { size: 10, color: '#3fb950', symbol: 'star', line: { color: '#fff', width: 1 } },
      hovertemplate: `BEP<br>Q=${data.bep.q}<br>H=${data.bep.h}<extra></extra>` });
  }
  const layout = makeLayout('Flow Q (m³/h)', 'Head H (m)');
  layout.yaxis.rangemode = 'tozero';
  return { traces, layout };
}

function buildEffChart(data, showClean) {
  const traces = [{ type: 'scatter', mode: 'lines',
    name: 'Efficiency', x: data.q, y: data.eta,
    line: { color: '#f0c040', width: 2.5 },
    fill: 'tozeroy', fillcolor: 'rgba(240,192,64,0.07)',
    hovertemplate: 'Q=%{x:.1f}<br>η=%{y:.1f}%<extra></extra>' }];
  if (showClean && data.eta_clean) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'η (water ref)',
      x: data.q, y: data.eta_clean,
      line: { color: '#f0c040', width: 1.5, dash: 'dot' }, opacity: 0.45,
      hovertemplate: 'Q=%{x:.1f}<br>η(clean)=%{y:.1f}%<extra></extra>' });
  }
  if (data.bep) {
    traces.push({ type: 'scatter', mode: 'markers', name: 'BEP',
      x: [data.bep.q], y: [data.bep.eta],
      marker: { size: 10, color: '#3fb950', symbol: 'star', line: { color: '#fff', width: 1 } },
      hovertemplate: `BEP η=${data.bep.eta}%<extra></extra>` });
  }
  const layout = makeLayout('Flow Q (m³/h)', 'Efficiency η (%)');
  layout.yaxis = Object.assign({}, layout.yaxis, { range: [0, 100] });
  return { traces, layout };
}

function buildPowerChart(data, showClean) {
  const traces = [{ type: 'scatter', mode: 'lines', name: 'Power',
    x: data.q, y: data.power, line: { color: '#f85149', width: 2.5 },
    hovertemplate: 'Q=%{x:.1f}<br>P=%{y:.2f} kW<extra></extra>' }];
  if (showClean && data.power_clean) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'Power (water ref)',
      x: data.q, y: data.power_clean,
      line: { color: '#f85149', width: 1.5, dash: 'dot' }, opacity: 0.45,
      hovertemplate: 'Q=%{x:.1f}<br>P(clean)=%{y:.2f}<extra></extra>' });
  }
  const layout = makeLayout('Flow Q (m³/h)', 'Shaft Power P (kW)');
  layout.yaxis.rangemode = 'tozero';
  return { traces, layout };
}

function buildNpshChart(data) {
  const traces = [{ type: 'scatter', mode: 'lines', name: 'NPSHr',
    x: data.q, y: data.npsh, line: { color: '#39d3c0', width: 2.5 },
    hovertemplate: 'Q=%{x:.1f}<br>NPSHr=%{y:.2f} m<extra></extra>' }];
  const layout = makeLayout('Flow Q (m³/h)', 'NPSHr (m)');
  layout.yaxis.rangemode = 'tozero';
  return { traces, layout };
}

function buildOverlayChart(data, showEff, showPower, showNpsh) {
  const traces = [];
  traces.push({ type: 'scatter', mode: 'lines', name: 'H-Q',
    x: data.q, y: data.h, line: { color: '#58a6ff', width: 3 },
    hovertemplate: 'Q=%{x:.1f}<br>H=%{y:.2f} m<extra></extra>' });
  if (data.system_h) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'System Curve',
      x: data.q, y: data.system_h, line: { color: '#bc8cff', width: 2, dash: 'dash' },
      hovertemplate: 'Q=%{x:.1f}<br>H_sys=%{y:.2f}<extra></extra>' });
  }
  if (showEff) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'η (%)', yaxis: 'y2',
      x: data.q, y: data.eta, line: { color: '#f0c040', width: 2, dash: 'longdash' },
      hovertemplate: 'η=%{y:.1f}%<extra></extra>' });
  }
  if (showPower && data.power) {
    const pMax = Math.max(...data.power), hMax = Math.max(...data.h);
    const sc = pMax > 0 ? hMax / pMax * 0.55 : 1;
    traces.push({ type: 'scatter', mode: 'lines', name: 'Power (scaled)',
      x: data.q, y: data.power.map(p => p * sc),
      line: { color: '#f85149', width: 1.5, dash: 'dot' },
      customdata: data.power,
      hovertemplate: 'P=%{customdata:.2f} kW<extra></extra>' });
  }
  if (showNpsh) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'NPSHr',
      x: data.q, y: data.npsh, line: { color: '#39d3c0', width: 2, dash: 'dashdot' },
      hovertemplate: 'NPSHr=%{y:.2f} m<extra></extra>' });
  }
  if (data.bep) {
    traces.push({ type: 'scatter', mode: 'markers', name: 'BEP',
      x: [data.bep.q], y: [data.bep.h],
      marker: { size: 10, color: '#3fb950', symbol: 'star', line: { color: '#fff', width: 1 } },
      hovertemplate: `BEP Q=${data.bep.q} H=${data.bep.h}<extra></extra>` });
  }
  const layout = Object.assign({}, PLOTLY_LAYOUT_BASE, {
    xaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.xaxis, { title: 'Flow Q (m³/h)' }),
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: 'Head H (m)', rangemode: 'tozero' }),
    yaxis2: { title: 'Efficiency η (%)', overlaying: 'y', side: 'right',
              range: [0, 105], showgrid: false,
              titlefont: { color: '#f0c040', size: 12 }, tickfont: { color: '#f0c040' },
              ticksuffix: '%' },
  });
  return { traces, layout };
}

/* ── Performance summary table ───────────────────────────────────────────── */
function renderPerfSummary(warmanData, containerId) {
  const family = warmanData.family || [];
  if (!family.length) { document.getElementById(containerId).innerHTML = '<p class="text-muted">No data.</p>'; return; }

  const rows = family.map((d, i) => {
    const b = d.bep || {};
    const col = DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)];
    return `<tr>
      <td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${col};margin-right:6px;"></span>
        <strong>Ø${d.dia} mm</strong>${d.is_max ? ' <span class="badge bg-secondary ms-1" style="font-size:0.65rem">BASE</span>' : ''}</td>
      <td class="text-center">${(d.ratio * 100).toFixed(1)}%</td>
      <td class="text-center fw-semibold">${b.q ?? '—'}</td>
      <td class="text-center">${b.h ?? '—'}</td>
      <td class="text-center text-warning fw-semibold">${b.eta ?? '—'}%</td>
      <td class="text-center">${b.power ?? '—'}</td>
    </tr>`;
  }).join('');

  document.getElementById(containerId).innerHTML = `
    <div class="table-responsive">
      <table class="table table-dark table-hover align-middle mb-0" style="font-size:0.88rem">
        <thead><tr>
          <th>Impeller</th>
          <th class="text-center">Trim %</th>
          <th class="text-center">Q<sub>BEP</sub> (m³/h)</th>
          <th class="text-center">H<sub>BEP</sub> (m)</th>
          <th class="text-center">η<sub>BEP</sub></th>
          <th class="text-center">P<sub>BEP</sub> (kW)</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   PUMP CURVE PAGE CONTROLLER
   ══════════════════════════════════════════════════════════════════════════ */

if (typeof PUMP_ID !== 'undefined') {

  let currentData    = null;   // Warman chart data (family + isolines)
  let singleData     = null;   // Single-dia curve data (max impeller)
  let viewMode       = 'warman';

  /* ── Query params ──── */
  function getParams() {
    const liquid = document.getElementById('liquidSelect').value;
    const p = new URLSearchParams({ liquid });
    if (liquid === 'viscous') p.set('viscosity_cSt', document.getElementById('viscosity').value);
    if (liquid === 'slurry') {
      p.set('slurry_cv',  document.getElementById('slurryCv').value);
      p.set('slurry_d50', document.getElementById('slurryD50').value);
      p.set('rho_solid',  document.getElementById('rhoSolid').value);
    }
    const sh = document.getElementById('staticHead').value;
    const pk = document.getElementById('pipeK').value;
    if (parseFloat(sh) || parseFloat(pk)) {
      p.set('static_head', sh || 0);
      p.set('pipe_k', pk || 0);
    }
    return p;
  }

  function getDuty() {
    return {
      q: parseFloat(document.getElementById('dutyQ').value) || null,
      h: parseFloat(document.getElementById('dutyH').value) || null,
    };
  }

  /* ── Liquid param panels ──── */
  function updateLiquidPanels() {
    const liquid = document.getElementById('liquidSelect').value;
    document.querySelectorAll('.liquid-param').forEach(el => {
      el.style.display = el.classList.contains(liquid) ? '' : 'none';
    });
  }

  /* ── Render all charts for current view mode ──── */
  function renderAll() {
    const duty = getDuty();

    if (viewMode === 'warman') {
      if (!currentData) return;
      const showIso  = document.getElementById('chkIsolines').checked;
      const showPwrI = document.getElementById('chkPowerIso').checked;
      const showNpshF= document.getElementById('chkNpshFamily').checked;

      const showSpdL  = document.getElementById('chkSpeedLines').checked;

      const wc = buildWarmanChart(currentData, {
        showIsolines: showIso, showPowerIso: showPwrI,
        showSpeedLines: showSpdL,
        dutyQ: duty.q, dutyH: duty.h
      });
      Plotly.react('chartWarman', wc.traces, wc.layout, PLOTLY_CONFIG);

      // NPSH family
      document.getElementById('npshFamilyPanel').style.display = showNpshF ? '' : 'none';
      if (showNpshF) {
        const nc = buildNpshFamilyChart(currentData.family);
        Plotly.react('chartNpshFamily', nc.traces, nc.layout, PLOTLY_CONFIG);
      }

      // Power family (show when power iso is on)
      document.getElementById('powerFamilyPanel').style.display = showPwrI ? '' : 'none';
      if (showPwrI) {
        const pc = buildPowerFamilyChart(currentData.family);
        Plotly.react('chartPowerFamily', pc.traces, pc.layout, PLOTLY_CONFIG);
      }

      renderPerfSummary(currentData, 'perfSummary');

    } else if (viewMode === 'standalone') {
      if (!singleData) return;
      const showClean  = singleData.liquid !== 'water';
      const showSystem = !!singleData.system_h;
      const showEff    = document.getElementById('chkEff').checked;
      const showPow    = document.getElementById('chkPower').checked;
      const showNpsh   = document.getElementById('chkNpsh').checked;

      const hq    = buildHQChart(singleData, showSystem, showClean);
      const eff   = buildEffChart(singleData, showClean);
      const power = buildPowerChart(singleData, showClean);
      const npsh  = buildNpshChart(singleData);

      Plotly.react('chartHQ',    hq.traces,    hq.layout,    PLOTLY_CONFIG);
      Plotly.react('chartEff',   eff.traces,   eff.layout,   PLOTLY_CONFIG);
      Plotly.react('chartPower', power.traces, power.layout, PLOTLY_CONFIG);
      Plotly.react('chartNpsh',  npsh.traces,  npsh.layout,  PLOTLY_CONFIG);

      document.getElementById('panelEff').style.display   = showEff   ? '' : 'none';
      document.getElementById('panelPower').style.display = showPow   ? '' : 'none';
      document.getElementById('panelNpsh').style.display  = showNpsh  ? '' : 'none';

    } else if (viewMode === 'overlay') {
      if (!singleData) return;
      const showEff  = document.getElementById('chkEff').checked;
      const showPow  = document.getElementById('chkPower').checked;
      const showNpsh = document.getElementById('chkNpsh').checked;
      const ov = buildOverlayChart(singleData, showEff, showPow, showNpsh);
      Plotly.react('chartOverlay', ov.traces, ov.layout, PLOTLY_CONFIG);
    }
  }

  /* ── Fetch both endpoints in parallel ──── */
  async function fetchAndRender() {
    const params = getParams();
    const btn = document.getElementById('btnUpdate');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading…';

    try {
      const [warmanRes, singleRes] = await Promise.all([
        fetch(`/papi/warman-chart/${PUMP_ID}?${params}`),
        fetch(`/papi/curve-data/${PUMP_ID}?${params}`)
      ]);
      currentData = await warmanRes.json();
      singleData  = await singleRes.json();
      renderAll();
    } catch (e) {
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Update';
    }
  }

  /* ── View mode switching ──── */
  function switchPanels() {
    document.getElementById('warmanPanel').style.display    = viewMode === 'warman'     ? '' : 'none';
    document.getElementById('standalonePanels').style.display = viewMode === 'standalone' ? '' : 'none';
    document.getElementById('overlayPanel').style.display   = viewMode === 'overlay'    ? '' : 'none';

    document.getElementById('warmanToggles').style.display    = viewMode === 'warman'     ? '' : 'none';
    document.getElementById('standaloneToggles').style.display = viewMode !== 'warman'    ? '' : 'none';
  }

  document.querySelectorAll('input[name="viewMode"]').forEach(radio => {
    radio.addEventListener('change', () => {
      viewMode = radio.value;
      switchPanels();
      renderAll();
    });
  });

  document.getElementById('liquidSelect').addEventListener('change', updateLiquidPanels);
  document.getElementById('btnUpdate').addEventListener('click', fetchAndRender);

  ['chkIsolines','chkPowerIso','chkSpeedLines','chkNpshFamily','chkEff','chkPower','chkNpsh'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', renderAll);
  });

  // Initial setup
  updateLiquidPanels();
  switchPanels();
  fetchAndRender();
}
