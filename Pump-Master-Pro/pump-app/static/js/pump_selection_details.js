let pumpData = null;

async function fetchPumpData() {
  const loadingEl = document.getElementById('chartLoading');
  if (loadingEl) loadingEl.style.display = 'block';

  if (!window.PumpDetailsConfig || !window.PumpDetailsConfig.PUMP_ID) {
    console.warn("window.PumpDetailsConfig is missing or PUMP_ID is undefined:", window.PumpDetailsConfig);
    if (loadingEl) loadingEl.style.display = 'none';
    return;
  }

  const cfg = window.PumpDetailsConfig;
  const params = new URLSearchParams({
    ids: cfg.PUMP_ID,
    liquid: cfg.LIQUID_TYPE || 'water',
    rho: (cfg.RHO !== undefined && cfg.RHO !== null) ? cfg.RHO : 1000,
    viscosity_cSt: (cfg.VISCOSITY !== undefined && cfg.VISCOSITY !== null) ? cfg.VISCOSITY : 1.0,
    slurry_cv: (cfg.SLURRY_CV !== undefined && cfg.SLURRY_CV !== null) ? cfg.SLURRY_CV : 0.0,
    slurry_d50: (cfg.SLURRY_D50 !== undefined && cfg.SLURRY_D50 !== null) ? cfg.SLURRY_D50 : 0.3,
    rho_solid: (cfg.RHO_SOLID !== undefined && cfg.RHO_SOLID !== null) ? cfg.RHO_SOLID : 2650.0,
    operation_mode: cfg.OPERATION_MODE || 'fixed'
  });

  try {
    const res = await fetch(`/papi/compare-pumps?${params.toString()}`);
    const data = await res.json();
    if (data && data.length > 0) {
      pumpData = data[0];
      renderAll();
    }
  } catch (e) {
    console.error("Error fetching pump data:", e);
  } finally {
    document.getElementById('chartLoading').style.display = 'none';
  }
}

// ── Universal Unit Conversion Factors ────────────────────────────────────────
const UNIT_FACTORS = {
  flow: {
    m3h: 1.0, ls: 3.6, lmin: 0.06, gpm: 0.227124707, ukgpm: 0.2727654, cfs: 101.9406, mgd: 157.7255
  },
  head: {
    m: 1.0, ft: 0.3048, kpa: 0.1019716, bar: 10.19716, psi: 0.70307
  },
  power: {
    kw: 1.0, hp: 0.745699872, w: 0.001, mw: 1000.0
  }
};

function normalizeDashStyle(styleStr, fallback = 'solid') {
  if (!styleStr) return fallback;
  const s = String(styleStr).toLowerCase().trim();
  if (s === 'dashed' || s === 'dash') return 'dash';
  if (s === 'dotted' || s === 'dot') return 'dot';
  if (s === 'dashdot') return 'dashdot';
  if (s === 'longdash') return 'longdash';
  if (s === 'solid') return 'solid';
  return fallback;
}

function getDetailsUnitScaleRatio(axisName, pumpObj = {}) {
  if (axisName === 'eff') return 1.0;

  const cfg = window.PumpDetailsConfig || {};
  const unitQ = cfg.UNIT_Q || 'm3h';
  const unitH = cfg.UNIT_H || 'm';
  const unitNpsh = cfg.UNIT_NPSH || 'm';
  const unitPow = cfg.UNIT_POW || 'kw';

  // Standardize pump native units
  const nativeQ = (pumpObj.unit_q || 'm3h').toLowerCase().replace('/', '').replace('³', '3').replace('^', '').replace(' ', '');
  const nativeH = (pumpObj.unit_h || 'm').toLowerCase().replace('/', '').replace(' ', '');
  const nativeNpsh = (pumpObj.unit_npsh || pumpObj.unit_h || 'm').toLowerCase().replace('/', '').replace(' ', '');
  const nativePow = (pumpObj.unit_power || pumpObj.unit_pow || 'kw').toLowerCase().replace('/', '').replace(' ', '');

  const factorNativeQ = UNIT_FACTORS.flow[nativeQ] || 1.0;
  const factorTargetQ = UNIT_FACTORS.flow[unitQ] || 1.0;

  const factorNativeH = UNIT_FACTORS.head[nativeH] || 1.0;
  const factorTargetH = UNIT_FACTORS.head[unitH] || 1.0;

  const factorNativeNpsh = UNIT_FACTORS.head[nativeNpsh] || 1.0;
  const factorTargetNpsh = UNIT_FACTORS.head[unitNpsh] || 1.0;

  const factorNativePow = UNIT_FACTORS.power[nativePow] || 1.0;
  const factorTargetPow = UNIT_FACTORS.power[unitPow] || 1.0;

  // Ratio converts stored axis numbers from pump's native unit into target display unit
  if (axisName === 'flow') {
    return factorNativeQ / factorTargetQ;
  } else if (axisName === 'head') {
    return factorNativeH / factorTargetH;
  } else if (axisName === 'npsh') {
    return factorNativeNpsh / factorTargetNpsh;
  } else if (axisName === 'power') {
    return factorNativePow / factorTargetPow;
  }
  return 1.0;
}

function getCleanAxisScale(rawMin, rawMax, majorDivisions, minorSubticks) {
  if (rawMax === null || rawMax === undefined) {
    return { min: rawMin, max: rawMax, dtick: null, minor: minorSubticks };
  }

  const minVal = (rawMin !== null && rawMin !== undefined) ? Number(rawMin) : 0;
  const maxVal = Number(rawMax);
  const span = maxVal - minVal;

  if (span <= 0) {
    return { min: minVal, max: maxVal, dtick: null, minor: minorSubticks };
  }

  let targetStep = (majorDivisions !== null && majorDivisions !== undefined && Number(majorDivisions) > 0) ? span / Number(majorDivisions) : span / 5.0;

  const multipliers = [1.0, 1.5, 2.0, 2.5, 5.0, 10.0];
  const mag = Math.pow(10, Math.floor(Math.log10(targetStep > 0 ? targetStep : 1.0)));

  let candidates = [];
  [0.1, 1.0, 10.0].forEach(decade => {
    multipliers.forEach(m => {
      candidates.push(m * mag * decade);
    });
  });

  let bestStep = candidates[0];
  let minDiff = Math.abs(bestStep - targetStep);
  candidates.forEach(step => {
    const diff = Math.abs(step - targetStep);
    if (diff < minDiff) {
      minDiff = diff;
      bestStep = step;
    }
  });

  return {
    min: minVal,
    max: maxVal,
    dtick: bestStep,
    minor: minorSubticks
  };
}

function applyAxisScale(axisConfig, axisKey, pumpObj, minorGridColor, axisLineColor) {
  const scaleRatio = getDetailsUnitScaleRatio(axisKey, pumpObj);
  const rawMin = pumpObj[`axis_${axisKey}_min`];
  const rawMax = pumpObj[`axis_${axisKey}_max`];
  const majorDiv = pumpObj[`axis_${axisKey}_major`];
  const minorSub = pumpObj[`axis_${axisKey}_minor`];

  const scaledMin = (rawMin !== null && rawMin !== undefined && rawMin !== '') ? Number(rawMin) * scaleRatio : null;
  const scaledMax = (rawMax !== null && rawMax !== undefined && rawMax !== '') ? Number(rawMax) * scaleRatio : null;

  const clean = getCleanAxisScale(scaledMin, scaledMax, majorDiv, minorSub);

  if (clean.min !== null && clean.max !== null) {
    axisConfig.range = [clean.min, clean.max];
    axisConfig.autorange = false;
  } else {
    axisConfig.rangemode = 'tozero';
    axisConfig.autorange = true;
  }

  if (clean.dtick !== null) {
    axisConfig.dtick = clean.dtick;
  }

  if (clean.minor && Number(clean.minor) > 0) {
    axisConfig.minor = {
      nticks: Number(clean.minor) + 1,
      gridcolor: minorGridColor,
      gridwidth: 1,
      showgrid: true
    };
  }

  axisConfig.showline = true;
  axisConfig.linewidth = 1.5;
  axisConfig.linecolor = axisLineColor;
  axisConfig.mirror = true;
}

/**
 * Constructs Plotly layout shapes for subplot panel borders (including top borders)
 * and/or a single enclosing outer outline border for the entire graph area.
 *
 * @param {string} mode - 'both' | 'panels' | 'outline' | 'none'
 * @param {Array<{key: string, domain: number[]}>} activeDomains - Active subplot domains
 * @param {string} color - Border line color (hex or rgba)
 * @returns {Array} List of Plotly shape objects
 */
function buildBorderShapes(mode, activeDomains, color) {
  if (!activeDomains || activeDomains.length === 0 || mode === 'none') {
    return [];
  }

  const shapes = [];
  const borderColor = color || '#30363d';
  const borderWidth = 1.5;

  // 1. Individual Subplot Panel Borders (crisp top border + complete bounding box for each panel)
  if (mode === 'panels' || mode === 'both') {
    activeDomains.forEach(d => {
      if (d.domain && d.domain.length === 2) {
        shapes.push({
          type: 'rect',
          xref: 'paper',
          yref: 'paper',
          x0: 0,
          x1: 1,
          y0: d.domain[0],
          y1: d.domain[1],
          line: {
            color: borderColor,
            width: borderWidth
          },
          fillcolor: 'rgba(0,0,0,0)',
          layer: 'below'
        });
      }
    });
  }

  // 2. Single Outline Border for the entire Graph Area
  if (mode === 'outline' || mode === 'both') {
    const minY = Math.min(...activeDomains.map(d => d.domain[0]));
    const maxY = Math.max(...activeDomains.map(d => d.domain[1]));
    shapes.push({
      type: 'rect',
      xref: 'paper',
      yref: 'paper',
      x0: 0,
      x1: 1,
      y0: minY,
      y1: maxY,
      line: {
        color: borderColor,
        width: mode === 'outline' ? 2.0 : 1.8
      },
      fillcolor: 'rgba(0,0,0,0)',
      layer: 'below'
    });
  }

  return shapes;
}

/**
 * Generates background shaded bands for fire operating regions:
 * 1. Churn / Low Flow Zone (0 to 25% Q_duty)
 * 2. Operating Zone (Most Remote to Most Favourable)
 * 3. Overload Zone (>150% Q_duty)
 */
function getFireRegionShapes(domainHead) {
  if (!window.fireProtectionGeometry || !domainHead) return [];
  const geom = window.fireProtectionGeometry;
  const y0 = domainHead[0];
  const y1 = domainHead[1];
  const qDuty = geom.qDuty || 0;
  const qFav = geom.qFav || (qDuty * 1.35);
  const q150 = geom.q150 || (qDuty * 1.5);

  return [
    {
      type: 'rect',
      xref: 'x',
      yref: 'paper',
      x0: 0,
      x1: qDuty * 0.25,
      y0: y0,
      y1: y1,
      fillcolor: 'rgba(239, 68, 68, 0.08)',
      line: { width: 1, dash: 'dot', color: 'rgba(239, 68, 68, 0.3)' },
      layer: 'below'
    },
    {
      type: 'rect',
      xref: 'x',
      yref: 'paper',
      x0: qDuty * 0.85,
      x1: Math.max(qFav, qDuty * 1.25),
      y0: y0,
      y1: y1,
      fillcolor: 'rgba(16, 185, 129, 0.08)',
      line: { width: 1, dash: 'dot', color: 'rgba(16, 185, 129, 0.3)' },
      layer: 'below'
    },
    {
      type: 'rect',
      xref: 'x',
      yref: 'paper',
      x0: q150,
      x1: q150 * 1.35,
      y0: y0,
      y1: y1,
      fillcolor: 'rgba(245, 158, 11, 0.08)',
      line: { width: 1, dash: 'dot', color: 'rgba(245, 158, 11, 0.3)' },
      layer: 'below'
    }
  ];
}

/**
 * Combines plot border shapes and active fire region background shapes.
 */
function getActiveShapes() {
  const mode = window.currentGraphBorderMode || 'both';
  const activeDomains = window.activeGraphDomains || [];
  const color = window.currentAxisLineColor || '#30363d';
  let shapes = buildBorderShapes(mode, activeDomains, color);

  const vis = window.curveVisibility || {};
  if (vis.fire_regions !== false && window.fireProtectionGeometry && activeDomains.length > 0) {
    const headDom = activeDomains.find(d => d.key === 'head');
    if (headDom && headDom.domain) {
      shapes = shapes.concat(getFireRegionShapes(headDom.domain));
    }
  }
  return shapes;
}

/**
 * Updates the graph border mode interactively on the live Plotly chart
 * and persists the user preference in localStorage.
 *
 * @param {string} mode - 'both' | 'panels' | 'outline' | 'none'
 */
window.setGraphBorderMode = function(mode) {
  if (!['both', 'panels', 'outline', 'none'].includes(mode)) {
    mode = 'both';
  }
  try {
    localStorage.setItem('pump_graph_border_mode', mode);
  } catch (e) {}

  window.currentGraphBorderMode = mode;
  const selectEl = document.getElementById('graphBorderOption');
  if (selectEl && selectEl.value !== mode) {
    selectEl.value = mode;
  }

  const chartEl = document.getElementById('chartComp');
  if (chartEl && chartEl.layout && window.activeGraphDomains) {
    Plotly.relayout(chartEl, { shapes: getActiveShapes() });
  }
};

function addLabel(annotations, x, y, yref, text, color, isMid = false, curveGroup = null) {
  if (x && x.length > 0) {
    let idx = isMid ? Math.floor(x.length / 2) : x.length - 1;
    annotations.push({
      x: x[idx],
      y: y[idx],
      xref: 'x', yref: yref,
      text: text,
      showarrow: false,
      xanchor: isMid ? 'center' : 'left',
      yanchor: isMid ? 'bottom' : 'middle',
      font: { color: color, size: 11 },
      xshift: isMid ? 0 : 5,
      yshift: isMid ? 10 : 0,
      curveGroup: curveGroup
    });
  }
}

function renderAll() {
  if (!pumpData) return;
  const fam = pumpData.family;
  const maxCurve = pumpData.curves;
  const pumpObj = pumpData.pump || {};
  if (!maxCurve || !maxCurve.q) return;

  const cfg = window.PumpDetailsConfig;
  const org = cfg.ORG_STYLES || {};

  const hqColor = org.hq_color || '#58a6ff';
  const hqWidth = parseFloat(org.hq_width) || 2.5;
  const hqStyle = normalizeDashStyle(org.hq_style, 'solid');

  const etaColor = org.eta_color || '#3fb950';
  const etaWidth = parseFloat(org.eta_width) || 2.5;
  const etaStyle = normalizeDashStyle(org.eta_style, 'solid');

  const powColor = org.pow_color || '#f0c040';
  const powWidth = parseFloat(org.pow_width) || 2.5;
  const powStyle = normalizeDashStyle(org.pow_style, 'solid');

  const npshColor = org.npsh_color || '#bc8cff';
  const npshWidth = parseFloat(org.npsh_width) || 2.5;
  const npshStyle = normalizeDashStyle(org.npsh_style, 'solid');

  const ratedColor = org.rated_marker_color || '#f85149';
  const trimWidth = parseFloat(org.trim_curve_width) || 2.5;
  const trimStyle = normalizeDashStyle(org.trim_curve_style, 'dash');

  const sysColor = org.system_curve_color || '#8b949e';
  const sysStyle = normalizeDashStyle(org.system_curve_style, 'dot');

  const fontFamily = org.font_family || 'Inter, sans-serif';
  const majorGridColor = org.major_grid_color || '#30363d';
  const minorGridColor = org.minor_grid_color || '#21262d';
  const axisLineColor = org.axis_line_color || '#30363d';

  const unitQ = cfg.UNIT_Q || 'm3h';
  const unitH = cfg.UNIT_H || 'm';
  const unitPow = cfg.UNIT_POW || 'kw';
  const unitNpsh = cfg.UNIT_NPSH || 'm';

  const multQ = 1.0 / (UNIT_FACTORS.flow[unitQ] || 1.0);
  const multH = 1.0 / (UNIT_FACTORS.head[unitH] || 1.0);
  const multPow = 1.0 / (UNIT_FACTORS.power[unitPow] || 1.0);
  const multNpsh = 1.0 / (UNIT_FACTORS.head[unitNpsh] || 1.0);

  const unitLabels = {
    m3h: 'm³/h', ls: 'l/s', lmin: 'l/min', gpm: 'US gpm', ukgpm: 'UK gpm', cfs: 'ft³/s', mgd: 'MGD',
    m: 'm', ft: 'ft', kpa: 'kPa', bar: 'bar', psi: 'psi',
    kw: 'kW', hp: 'hp', w: 'W', mw: 'MW'
  };
  const lblQ = unitLabels[unitQ] || unitQ;
  const lblH = unitLabels[unitH] || unitH;
  const lblPow = unitLabels[unitPow] || unitPow;
  const lblNpsh = unitLabels[unitNpsh] || unitNpsh;

  let traces = [];
  let annotations = [];

  const scaledMaxQ = maxCurve.q.map(q => q * multQ);
  const scaledMaxH = maxCurve.h.map(h => h * multH);
  const scaledMaxPow = maxCurve.power.map(p => p * multPow);
  const scaledMaxNpsh = maxCurve.npsh ? maxCurve.npsh.map(n => n * multNpsh) : [];

  // Compute hasNpsh early — before any trace loop — from ALL available curve sources.
  // The backend returns npsh: null when the pump has no NPSH polynomial, so we check
  // both the single base curve (maxCurve.npsh) and any family curves (fam[*].npsh).
  // We also reject all-zero arrays (1e-4 tolerance) in case of stale cached data.
  const _npshHasValues = arr => Array.isArray(arr) && arr.some(v => Math.abs(v) > 1e-4);
  const hasNpsh = _npshHasValues(maxCurve.npsh) ||
    (fam && fam.some(c => _npshHasValues(c.npsh)));

  // ── Multi-Pump Arrangement Detection ──
  // When multiple pumps operate in parallel or series, curves and operating markers are needed for both:
  // 1) The individual pump (1 of N) to evaluate operating flow, head, absorbed power, efficiency, and NPSHr.
  // 2) The combined station total delivery (N pumps combined: N*Q in parallel, N*H in series).
  const stationN = parseInt(cfg.PUMPS_OPERATING) || 1;
  const isMultiPump = stationN > 1 && (cfg.PUMP_ARRANGEMENT === 'parallel' || cfg.PUMP_ARRANGEMENT === 'series');
  const isParallel = (cfg.PUMP_ARRANGEMENT === 'parallel' && stationN > 1);
  const isSeries = (cfg.PUMP_ARRANGEMENT === 'series' && stationN > 1);

  const dutyScaleRatio = cfg.COMPOSITE_RATIO || cfg.TRIM_RATIO || 1.0;
  const qDutyCurve = scaledMaxQ.map(q => q * dutyScaleRatio);
  const hDutyCurve = scaledMaxH.map(h => h * Math.pow(dutyScaleRatio, 2));
  const pDutyCurve = scaledMaxPow.map(p => p * Math.pow(dutyScaleRatio, 3));
  const npshDutyCurve = scaledMaxNpsh.length ? scaledMaxNpsh.map(n => n * Math.pow(dutyScaleRatio, 2)) : [];

  if (fam && fam.length > 0) {
    fam.forEach((c, idx) => {
      let lbl = cfg.IS_VSD ? `${c.rpm || c.val} RPM` : `Ø ${c.dia} mm`;
      let isMax = idx === fam.length - 1;
      let curveWidth = isMax ? hqWidth : Math.max(1.2, hqWidth * 0.7);

      const scQ = c.q.map(q => q * multQ);
      const scH = c.h.map(h => h * multH);
      const scPow = c.power.map(p => p * multPow);
      const scNpsh = c.npsh ? c.npsh.map(n => n * multNpsh) : [];

      let cdata = scQ.map((q, i) => [
        scH[i] != null ? scH[i].toFixed(1) : 'N/A',
        c.eta[i] != null ? c.eta[i].toFixed(1) : 'N/A',
        scPow[i] != null ? scPow[i].toFixed(1) : 'N/A',
        (scNpsh && scNpsh[i] != null) ? scNpsh[i].toFixed(1) : 'N/A'
      ]);
      let hoverTmpl = `<b>${lbl}</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{customdata[0]} ${lblH}<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} ${lblPow}<br>NPSHr: %{customdata[3]} ${lblNpsh}<extra></extra>`;

      traces.push({ x: scQ, y: scH, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: { color: hqColor, width: curveWidth, dash: hqStyle }, yaxis: 'y4', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'hq', legendgroup: 'hq' });
      addLabel(annotations, scQ, scH, 'y4', lbl, hqColor, false, 'hq');

      traces.push({ x: scQ, y: c.eta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: { color: etaColor, width: isMax ? etaWidth : Math.max(1.2, etaWidth * 0.7), dash: etaStyle }, yaxis: 'y3', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'eta', legendgroup: 'eta' });
      addLabel(annotations, scQ, c.eta, 'y3', lbl, etaColor, false, 'eta');

      traces.push({ x: scQ, y: scPow, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: { color: powColor, width: isMax ? powWidth : Math.max(1.2, powWidth * 0.7), dash: powStyle }, yaxis: 'y2', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'pow', legendgroup: 'pow' });
      addLabel(annotations, scQ, scPow, 'y2', lbl, powColor, false, 'pow');

      if (hasNpsh && scNpsh && scNpsh.length) {
        traces.push({ x: scQ, y: scNpsh, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: { color: npshColor, width: isMax ? npshWidth : Math.max(1.2, npshWidth * 0.7), dash: npshStyle }, yaxis: 'y', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'npsh', legendgroup: 'npsh' });
        addLabel(annotations, scQ, scNpsh, 'y', lbl, npshColor, false, 'npsh');
      }
    });
  } else {
    let lbl = 'Max';
    let cdata = scaledMaxQ.map((q, i) => [
      scaledMaxH[i] != null ? scaledMaxH[i].toFixed(1) : 'N/A',
      maxCurve.eta[i] != null ? maxCurve.eta[i].toFixed(1) : 'N/A',
      scaledMaxPow[i] != null ? scaledMaxPow[i].toFixed(1) : 'N/A',
      (scaledMaxNpsh && scaledMaxNpsh[i] != null) ? scaledMaxNpsh[i].toFixed(1) : 'N/A'
    ]);
    let hoverTmpl = `<b>${lbl}</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{customdata[0]} ${lblH}<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} ${lblPow}<br>NPSHr: %{customdata[3]} ${lblNpsh}<extra></extra>`;

    traces.push({ x: scaledMaxQ, y: scaledMaxH, name: isMultiPump ? 'Pump Head (Max Ø/RPM)' : 'Head (Max)', type: 'scatter', mode: 'lines', line: { color: hqColor, width: hqWidth, dash: hqStyle }, yaxis: 'y4', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'hq', legendgroup: 'hq' });
    addLabel(annotations, scaledMaxQ, scaledMaxH, 'y4', 'Max', hqColor, false, 'hq');

    traces.push({ x: scaledMaxQ, y: maxCurve.eta, name: 'Eff (Max)', type: 'scatter', mode: 'lines', line: { color: etaColor, width: etaWidth, dash: etaStyle }, yaxis: 'y3', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'eta', legendgroup: 'eta' });
    addLabel(annotations, scaledMaxQ, maxCurve.eta, 'y3', 'Max', etaColor, false, 'eta');

    traces.push({ x: scaledMaxQ, y: scaledMaxPow, name: 'Power (Max)', type: 'scatter', mode: 'lines', line: { color: powColor, width: powWidth, dash: powStyle }, yaxis: 'y2', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'pow', legendgroup: 'pow' });
    addLabel(annotations, scaledMaxQ, scaledMaxPow, 'y2', 'Max', powColor, false, 'pow');

    if (scaledMaxNpsh.length) {
      traces.push({ x: scaledMaxQ, y: scaledMaxNpsh, name: 'NPSHr (Max)', type: 'scatter', mode: 'lines', line: { color: npshColor, width: npshWidth, dash: npshStyle }, yaxis: 'y', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'npsh', legendgroup: 'npsh' });
      addLabel(annotations, scaledMaxQ, scaledMaxNpsh, 'y', 'Max', npshColor, false, 'npsh');
    }
  }

  // ── Rated Curve Legend Label ──
  let ratedLegendName = isMultiPump ? `1x Pump Curve (1 of ${stationN})` : 'Rated Curve';
  if (cfg.IS_VSD) {
    const spdStr = `${cfg.RATED_SPEED || Math.round(cfg.PUMP_SPEED * cfg.TRIM_RATIO)} RPM`;
    const trimStr = (cfg.VSD_TRIM_MODE && cfg.VSD_TRIM_MODE !== 'auto' && cfg.RATED_TRIM) ? `, Ø${cfg.RATED_TRIM}mm` : '';
    ratedLegendName = isMultiPump ? `1x Pump Curve (${spdStr}${trimStr})` : `VSD Curve (${spdStr}${trimStr})`;
  } else if (cfg.FIXED_SPEED_MODE === 'auto') {
    ratedLegendName = isMultiPump ? `1x Pump Curve (${cfg.RATED_SPEED || Math.round(cfg.PUMP_SPEED * cfg.TRIM_RATIO)} RPM)` : `Calculated Speed (${cfg.RATED_SPEED || Math.round(cfg.PUMP_SPEED * cfg.TRIM_RATIO)} RPM)`;
  } else if (cfg.FIXED_SPEED_MODE === 'manual') {
    const spdStr = `${cfg.RATED_SPEED || cfg.MANUAL_SPEED_RPM} RPM`;
    const trimStr = (cfg.TRIM_RATIO < 0.995 && cfg.RATED_TRIM) ? `, Ø${cfg.RATED_TRIM}mm` : '';
    ratedLegendName = isMultiPump ? `1x Pump Curve (${spdStr}${trimStr})` : `Manual Speed (${spdStr}${trimStr})`;
  } else if (cfg.FIXED_SPEED_MODE === 'range') {
    const spdStr = `${cfg.RATED_SPEED} RPM`;
    const trimStr = (cfg.TRIM_RATIO < 0.995 && cfg.RATED_TRIM) ? `, Ø${cfg.RATED_TRIM}mm` : '';
    ratedLegendName = isMultiPump ? `1x Pump Curve (${spdStr}${trimStr})` : `Range Speed (${spdStr}${trimStr})`;
  } else if (cfg.TRIM_RATIO < 1.0) {
    ratedLegendName = isMultiPump ? `1x Pump Curve (Ø ${cfg.RATED_TRIM} mm)` : `Rated Curve (Ø ${cfg.RATED_TRIM} mm)`;
  }

  // ── Individual Rated Performance Curves (1x Pump) ──
  let active1xQ = scaledMaxQ;
  let active1xH = scaledMaxH;

  if (dutyScaleRatio < 0.999 || cfg.IS_VSD || cfg.FIXED_SPEED_MODE === 'auto' || cfg.FIXED_SPEED_MODE === 'manual' || cfg.FIXED_SPEED_MODE === 'range' || cfg.TRIM_RATIO < 1.0) {
    let lbl = cfg.IS_VSD ? `VSD (${cfg.RATED_SPEED} RPM${(cfg.VSD_TRIM_MODE && cfg.VSD_TRIM_MODE !== 'auto' && cfg.RATED_TRIM) ? ', Ø ' + cfg.RATED_TRIM + ' mm' : ''})` :
              (cfg.FIXED_SPEED_MODE === 'auto' ? `Calculated (${cfg.RATED_SPEED} RPM)` :
              (cfg.FIXED_SPEED_MODE === 'manual' ? `Manual (${cfg.RATED_SPEED || cfg.MANUAL_SPEED_RPM} RPM${cfg.RATED_TRIM ? ', Ø ' + cfg.RATED_TRIM + ' mm' : ''})` :
              (cfg.FIXED_SPEED_MODE === 'range' ? `Rated (${cfg.RATED_SPEED} RPM${cfg.RATED_TRIM ? ', Ø ' + cfg.RATED_TRIM + ' mm' : ''})` :
              `Rated (Ø ${cfg.RATED_TRIM} mm)`)));

    if (isMultiPump) {
      lbl = `1x Pump (${lbl})`;
    }

    // Filter all points where head is non-negative (H >= 0).
    // Beginners Note: Do NOT arbitrarily slice by dutyScaleRatio! Slicing cuts off the right-hand
    // operating range and prevents the curve from reaching the rated duty point.
    const ratedQ = [];
    const ratedH = [];
    const ratedEta = [];
    const ratedPow = [];
    const ratedNpsh = [];
    const cdataRated = [];

    for (let i = 0; i < qDutyCurve.length; i++) {
      const qVal = qDutyCurve[i];
      const hVal = hDutyCurve[i];
      if (hVal != null && hVal >= 0) {
        ratedQ.push(qVal);
        ratedH.push(hVal);
        const etaVal = maxCurve.eta ? maxCurve.eta[i] : null;
        const powVal = pDutyCurve ? pDutyCurve[i] : null;
        const npshVal = (npshDutyCurve && npshDutyCurve.length) ? npshDutyCurve[i] : null;
        if (etaVal != null) ratedEta.push(etaVal);
        if (powVal != null) ratedPow.push(powVal);
        if (npshVal != null) ratedNpsh.push(npshVal);

        cdataRated.push([
          hVal.toFixed(1),
          etaVal != null ? etaVal.toFixed(1) : 'N/A',
          powVal != null ? powVal.toFixed(1) : 'N/A',
          npshVal != null ? npshVal.toFixed(1) : 'N/A'
        ]);
      }
    }

    // Beginners Note: Safety extension to ensure the rated curve always reaches and passes
    // cleanly through the duty point, even when speed reduction or trim lowers the maximum
    // flow below the target operating point.
    const targetDutyQ = isMultiPump ? (isParallel ? (cfg.Q_DUTY / stationN) : cfg.Q_DUTY) : cfg.Q_DUTY;
    const targetDutyH = isMultiPump ? (isSeries ? ((cfg.EVAL_H_DUTY != null && cfg.EVAL_H_DUTY !== '') ? cfg.EVAL_H_DUTY : (cfg.H_DUTY / stationN)) : cfg.H_DUTY) : cfg.H_DUTY;
    if (targetDutyQ && targetDutyH && ratedQ.length > 0 && ratedQ[ratedQ.length - 1] < targetDutyQ) {
      const lastQ = ratedQ[ratedQ.length - 1];
      const lastH = ratedH[ratedH.length - 1];
      const slope = (targetDutyH - lastH) / (targetDutyQ - lastQ);
      ratedQ.push(targetDutyQ);
      ratedH.push(targetDutyH);
      cdataRated.push([
        targetDutyH.toFixed(1),
        cfg.OP_ETA ? cfg.OP_ETA.toFixed(1) : 'N/A',
        cfg.OP_POWER_KW ? cfg.OP_POWER_KW.toFixed(1) : 'N/A',
        'N/A'
      ]);
      const postQ = targetDutyQ * 1.06;
      const postH = targetDutyH + slope * (postQ - targetDutyQ);
      if (postH >= 0) {
        ratedQ.push(postQ);
        ratedH.push(postH);
        cdataRated.push([
          postH.toFixed(1),
          cfg.OP_ETA ? cfg.OP_ETA.toFixed(1) : 'N/A',
          cfg.OP_POWER_KW ? cfg.OP_POWER_KW.toFixed(1) : 'N/A',
          'N/A'
        ]);
      }
    }

    active1xQ = ratedQ;
    active1xH = ratedH;

    const hoverTmplRated = `<b>${lbl}</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{customdata[0]} ${lblH}<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} ${lblPow}<br>NPSHr: %{customdata[3]} ${lblNpsh}<extra></extra>`;

    traces.push({
      x: ratedQ, y: ratedH, name: `Head ${lbl}`, type: 'scatter', mode: 'lines',
      line: { color: ratedColor, width: trimWidth, dash: trimStyle },
      yaxis: 'y4', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated,
      curveGroup: 'rated', legendgroup: 'rated'
    });
    addLabel(annotations, ratedQ, ratedH, 'y4', isMultiPump ? '1x Rated' : 'Rated', ratedColor, false, 'rated');

    traces.push({
      x: ratedQ, y: ratedEta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines',
      line: { color: ratedColor, width: trimWidth, dash: trimStyle },
      yaxis: 'y3', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated,
      curveGroup: 'rated', legendgroup: 'rated'
    });
    traces.push({
      x: ratedQ, y: ratedPow, name: `Power ${lbl}`, type: 'scatter', mode: 'lines',
      line: { color: ratedColor, width: trimWidth, dash: trimStyle },
      yaxis: 'y2', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated,
      curveGroup: 'rated', legendgroup: 'rated'
    });
    if (hasNpsh && ratedNpsh.length) {
      traces.push({
        x: ratedQ, y: ratedNpsh, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines',
        line: { color: ratedColor, width: trimWidth, dash: trimStyle },
        yaxis: 'y', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated,
        curveGroup: 'rated', legendgroup: 'rated'
      });
    }
  }

  // ── Multi-Pump Combined Station Curve (Parallel or Series) ──
  // Evaluates and plots the combined station curve for multiple pumps:
  // - In Parallel: Total Flow is shared (N * Q_pump at Head H)
  // - In Series: Total Head is shared (Flow Q at N * H_pump)
  // Note: Only plot points where head is non-negative and within valid operating range.
  if (isParallel) {
    const stationQ = active1xQ.map(q => q * stationN);
    const stationH = active1xH;
    const hoverTmplStation = `<b>Combined Station (${stationN}x Parallel)</b><br>Station Total Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<extra></extra>`;
    traces.push({
      x: stationQ,
      y: stationH,
      name: `Combined Station (${stationN}x Parallel)`,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#22c55e', width: Math.max(2.8, trimWidth + 0.8), dash: 'solid' },
      yaxis: 'y4',
      showlegend: false,
      hovertemplate: hoverTmplStation,
      curveGroup: 'station',
      legendgroup: 'station'
    });
    addLabel(annotations, stationQ, stationH, 'y4', `${stationN}x Parallel`, '#22c55e', false, 'station');
  } else if (isSeries) {
    const stationQ = [];
    const stationH = [];
    for (let i = 0; i < active1xQ.length; i++) {
      const qVal = active1xQ[i];
      const hVal = active1xH[i] * stationN;
      if (hVal >= 0) {
        stationQ.push(qVal);
        stationH.push(hVal);
      }
    }
    const hoverTmplStation = `<b>Combined Station (${stationN}x Series)</b><br>Flow: %{x:.1f} ${lblQ}<br>Station Total Head: %{y:.1f} ${lblH}<extra></extra>`;
    traces.push({
      x: stationQ,
      y: stationH,
      name: `Combined Station (${stationN}x Series)`,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#a855f7', width: Math.max(2.8, trimWidth + 0.8), dash: 'solid' },
      yaxis: 'y4',
      showlegend: false,
      hovertemplate: hoverTmplStation,
      curveGroup: 'station',
      legendgroup: 'station'
    });
    addLabel(annotations, stationQ, stationH, 'y4', `${stationN}x Series`, '#a855f7', false, 'station');
  }

  // ── System Head Curve ──
  // Beginners Note: The system curve (H = k * Q²) intersects the duty point. We bound
  // limitH so the curve extends pleasantly past the operating point without breaking off
  // the top or side border of the chart.
  if (cfg.Q_DUTY && cfg.H_DUTY) {
    const k = cfg.H_DUTY / Math.pow(cfg.Q_DUTY, 2);
    const maxPumpH = Math.max(...scaledMaxH);
    const stationPeakH = isSeries ? (maxPumpH * stationN) : maxPumpH;
    const limitH = Math.max(cfg.H_DUTY * 1.25, Math.min(stationPeakH * 1.05, cfg.H_DUTY * 1.6));

    // Use extended flow range in parallel mode so system curve covers total station flow
    const baseFlowArr = isParallel ? scaledMaxQ.map(q => q * stationN) : scaledMaxQ;

    const sysQ = [];
    const sysH = [];
    for (let i = 0; i < baseFlowArr.length; i++) {
      const q = baseFlowArr[i];
      const h = k * Math.pow(q, 2);
      if (h <= limitH) {
        sysQ.push(q);
        sysH.push(h);
      }
    }
    if (sysQ.length === 0 || sysQ[sysQ.length - 1] < cfg.Q_DUTY) {
      sysQ.push(cfg.Q_DUTY);
      sysH.push(cfg.H_DUTY);
    }
    let hoverTmplSys = `<b>System Curve</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<extra></extra>`;
    traces.push({ x: sysQ, y: sysH, name: 'System Curve', type: 'scatter', mode: 'lines', line: { color: sysColor, width: 2.2, dash: sysStyle }, yaxis: 'y4', showlegend: false, hovertemplate: hoverTmplSys, curveGroup: 'system', legendgroup: 'system' });
  }

  // ── Interactive Legend Proxies ──
  // Beginners Note: Each curve group has a distinct entry on the Plotly legend.
  // Clicking an item toggles its entire curve group across all subplots simultaneously!
  traces.push({ x: [null], y: [null], name: isMultiPump ? 'Pump Head (Max Ø/RPM)' : 'Head (Max)', type: 'scatter', mode: 'lines', line: { color: hqColor, width: hqWidth, dash: hqStyle }, showlegend: true, curveGroup: 'hq', legendgroup: 'hq' });
  traces.push({ x: [null], y: [null], name: 'Efficiency (Max)', type: 'scatter', mode: 'lines', line: { color: etaColor, width: etaWidth, dash: etaStyle }, showlegend: true, curveGroup: 'eta', legendgroup: 'eta' });
  traces.push({ x: [null], y: [null], name: 'Power (Max)', type: 'scatter', mode: 'lines', line: { color: powColor, width: powWidth, dash: powStyle }, showlegend: true, curveGroup: 'pow', legendgroup: 'pow' });
  if (hasNpsh) {
    traces.push({ x: [null], y: [null], name: 'NPSHr (Max)', type: 'scatter', mode: 'lines', line: { color: npshColor, width: npshWidth, dash: npshStyle }, showlegend: true, curveGroup: 'npsh', legendgroup: 'npsh' });
  }

  traces.push({ x: [null], y: [null], name: ratedLegendName, type: 'scatter', mode: 'lines', line: { color: ratedColor, width: trimWidth, dash: trimStyle }, showlegend: true, curveGroup: 'rated', legendgroup: 'rated' });

  if (isMultiPump) {
    traces.push({ x: [null], y: [null], name: isParallel ? `Combined Station (${stationN}x Parallel)` : `Combined Station (${stationN}x Series)`, type: 'scatter', mode: 'lines', line: { color: isParallel ? '#22c55e' : '#a855f7', width: 2.8, dash: 'solid' }, showlegend: true, curveGroup: 'station', legendgroup: 'station' });
  }

  traces.push({ x: [null], y: [null], name: 'System Curve', type: 'scatter', mode: 'lines', line: { color: sysColor, width: 2.2, dash: sysStyle }, showlegend: true, curveGroup: 'system', legendgroup: 'system' });

  const isFireSelection = Boolean(
    cfg.IS_FIRE_PUMP
    || (pumpObj.app_modules && pumpObj.app_modules.toLowerCase().includes('fire'))
    || (cfg.APPLICATION && cfg.APPLICATION.toLowerCase().includes('fire'))
    || (window.location.search && window.location.search.toLowerCase().includes('app=fire'))
  );

  if (cfg.Q_DUTY && cfg.H_DUTY) {
    if (isFireSelection) {
      // Fire Protection Legend Proxies
      traces.push({ x: [null], y: [null], name: 'Most Remote Duty (100% Q)', type: 'scatter', mode: 'markers', marker: { color: '#ef4444', size: 12, symbol: 'star' }, showlegend: true, curveGroup: 'fire_remote', legendgroup: 'fire_remote' });
      traces.push({ x: [null], y: [null], name: 'Shutoff / Churn Point (0% Q)', type: 'scatter', mode: 'markers', marker: { color: '#f59e0b', size: 11, symbol: 'circle' }, showlegend: true, curveGroup: 'fire_churn', legendgroup: 'fire_churn' });
      traces.push({ x: [null], y: [null], name: 'Most Favourable Point', type: 'scatter', mode: 'markers', marker: { color: '#06b6d4', size: 12, symbol: 'diamond' }, showlegend: true, curveGroup: 'fire_fav', legendgroup: 'fire_fav' });
      traces.push({ x: [null], y: [null], name: '150% Overload Test Point', type: 'scatter', mode: 'markers', marker: { color: '#8b5cf6', size: 11, symbol: 'square' }, showlegend: true, curveGroup: 'fire_overload', legendgroup: 'fire_overload' });
      traces.push({ x: [null], y: [null], name: 'NFPA 20 Code Envelope', type: 'scatter', mode: 'lines', line: { color: '#f43f5e', width: 2.2, dash: 'dash' }, showlegend: true, curveGroup: 'fire_envelope', legendgroup: 'fire_envelope' });
      traces.push({ x: [null], y: [null], name: 'Most Favourable Curve', type: 'scatter', mode: 'lines', line: { color: '#06b6d4', width: 2.2, dash: 'dot' }, showlegend: true, curveGroup: 'fav_curve', legendgroup: 'fav_curve' });
    } else if (isMultiPump) {
      traces.push({ x: [null], y: [null], name: '1x Pump Duty Point', type: 'scatter', mode: 'markers', marker: { color: ratedColor, size: 10, symbol: 'star' }, showlegend: true, curveGroup: 'duty_ind', legendgroup: 'duty_ind' });
      traces.push({ x: [null], y: [null], name: `Station Total Duty (${stationN}x)`, type: 'scatter', mode: 'markers', marker: { color: isParallel ? '#22c55e' : '#a855f7', size: 11, symbol: 'diamond' }, showlegend: true, curveGroup: 'duty_station', legendgroup: 'duty_station' });
    } else {
      traces.push({ x: [null], y: [null], name: 'Operating Duty Point', type: 'scatter', mode: 'markers', marker: { color: ratedColor, size: 11, symbol: 'star' }, showlegend: true, curveGroup: 'duty', legendgroup: 'duty' });
    }
  }

  // ── Operating Duty Points (Geometry & Annotations) ──
  if (cfg.Q_DUTY && cfg.H_DUTY) {
    if (isFireSelection) {
      const qDuty = cfg.Q_DUTY;
      const hDuty = cfg.H_DUTY;

      // 1. Churn head (0% flow)
      const hChurn = (pumpObj.hq_a0 ? pumpObj.hq_a0 * multH * Math.pow(dutyScaleRatio, 2) : (active1xH[0] || hDuty * 1.15));
      const maxChurnLimit = hDuty * 1.40;

      // 2. Overload head at 150% flow
      const q150 = qDuty * 1.50;
      let h150 = 0.0;
      for (let i = 0; i < active1xQ.length - 1; i++) {
        if (active1xQ[i] <= q150 && active1xQ[i + 1] >= q150) {
          const t = (q150 - active1xQ[i]) / (active1xQ[i + 1] - active1xQ[i]);
          h150 = active1xH[i] + t * (active1xH[i + 1] - active1xH[i]);
          break;
        }
      }
      if (h150 <= 0 && active1xH.length > 0) {
        h150 = Math.max(0, active1xH[active1xH.length - 1]);
      }
      const minOverloadLimit = hDuty * 0.65;

      // 3. Most Favourable Operating Point (Closest Sprinklers / Lowest Resistance)
      const hStatic = (cfg.STATIC_HEAD != null ? cfg.STATIC_HEAD : (hDuty * 0.25)) * multH;
      const hStaticFav = Math.max(2.0 * multH, hStatic * 0.20);
      const kRemote = (hDuty > hStatic) ? ((hDuty - hStatic) / Math.pow(qDuty, 2)) : (0.75 * hDuty / Math.pow(qDuty, 2));
      const kFav = kRemote * 0.42;

      const favSysQ = [];
      const favSysH = [];
      const maxFavQ = Math.max(q150 * 1.05, Math.max(...active1xQ));
      const favPtsCount = 40;
      for (let i = 0; i <= favPtsCount; i++) {
        const qVal = (i / favPtsCount) * maxFavQ;
        const hVal = hStaticFav + kFav * Math.pow(qVal, 2);
        if (hVal <= Math.max(...active1xH) * 1.25) {
          favSysQ.push(qVal);
          favSysH.push(hVal);
        }
      }

      let qFav = qDuty * 1.30;
      let hFav = hDuty * 0.85;
      for (let i = 0; i < active1xQ.length - 1; i++) {
        const qA = active1xQ[i];
        const qB = active1xQ[i + 1];
        if (qB > qDuty) {
          const hPumpA = active1xH[i];
          const hPumpB = active1xH[i + 1];
          const hFavA = hStaticFav + kFav * Math.pow(qA, 2);
          const hFavB = hStaticFav + kFav * Math.pow(qB, 2);
          const diffA = hPumpA - hFavA;
          const diffB = hPumpB - hFavB;
          if (diffA >= 0 && diffB <= 0) {
            const t = diffA / (diffA - diffB);
            qFav = qA + t * (qB - qA);
            hFav = hPumpA + t * (hPumpB - hPumpA);
            break;
          }
        }
      }

      // Most Remote Operating Duty Point
      traces.push({
        x: [qDuty], y: [hDuty], name: 'Most Remote Duty (100% Q)',
        type: 'scatter', mode: 'markers',
        marker: { color: '#ef4444', size: 14, symbol: 'star', line: { color: '#ffffff', width: 1.5 } },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fire_remote', legendgroup: 'fire_remote',
        hovertemplate: `<b>Most Remote Operating Point (100% Demand)</b><br>Flow: %{x:.1f} ${lblQ}<br>Required Head: %{y:.1f} ${lblH}<br>Status: Certified Design Point<extra></extra>`
      });
      // Most Remote Operating Duty Point ([B])
      traces.push({
        x: [qDuty], y: [hDuty], name: '[B] Rated Duty (100% Q)',
        type: 'scatter', mode: 'markers',
        marker: { color: '#ef4444', size: 14, symbol: 'circle', line: { color: '#ffffff', width: 2 } },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fire_remote', legendgroup: 'fire_remote',
        hovertemplate: `<b>[B] Rated Duty Point (100% Demand)</b><br>Flow: %{x:.1f} ${lblQ}<br>Required Head: %{y:.1f} ${lblH}<br>Status: Certified Design Point<extra></extra>`
      });
      annotations.push({
        x: qDuty, y: hDuty, xref: 'x', yref: 'y4',
        text: '<b>B</b>', showarrow: true, arrowcolor: '#ef4444',
        ax: -20, ay: -20, font: { color: '#ffffff', size: 11, weight: 'bold' },
        bgcolor: '#ef4444', bordercolor: '#ffffff', borderwidth: 1.5, borderpad: 3,
        curveGroup: 'fire_remote'
      });

      // Shutoff / Churn Point (0% Q) ([A])
      traces.push({
        x: [0], y: [hChurn], name: '[A] Shutoff / Churn Point (0% Q)',
        type: 'scatter', mode: 'markers',
        marker: { color: '#ef4444', size: 13, symbol: 'circle', line: { color: '#ffffff', width: 2 } },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fire_churn', legendgroup: 'fire_churn',
        hovertemplate: `<b>[A] Shutoff / Churn Point (0% Flow)</b><br>Churn Head: %{y:.1f} ${lblH}<br>NFPA 20 Limit: ≤ ${maxChurnLimit.toFixed(1)} ${lblH} (140%)<br>Actual Churn: ${((hChurn / hDuty) * 100).toFixed(1)}%<extra></extra>`
      });
      annotations.push({
        x: 0, y: hChurn, xref: 'x', yref: 'y4',
        text: '<b>A</b>', showarrow: true, arrowcolor: '#ef4444',
        ax: 24, ay: -18, font: { color: '#ffffff', size: 11, weight: 'bold' },
        bgcolor: '#ef4444', bordercolor: '#ffffff', borderwidth: 1.5, borderpad: 3,
        curveGroup: 'fire_churn'
      });

      // Operating Point ([C])
      traces.push({
        x: [qFav], y: [hFav], name: '[C] Operating Point',
        type: 'scatter', mode: 'markers',
        marker: { color: '#16a34a', size: 14, symbol: 'circle', line: { color: '#ffffff', width: 2 } },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fire_fav', legendgroup: 'fire_fav',
        hovertemplate: `<b>[C] Operating Point (System Intersection)</b><br>Flow: %{x:.1f} ${lblQ} (${((qFav / qDuty) * 100).toFixed(0)}% Q)<br>Head: %{y:.1f} ${lblH}<br>Zone: Operating Intersection<extra></extra>`
      });
      annotations.push({
        x: qFav, y: hFav, xref: 'x', yref: 'y4',
        text: '<b>C</b>', showarrow: true, arrowcolor: '#16a34a',
        ax: 20, ay: -20, font: { color: '#ffffff', size: 11, weight: 'bold' },
        bgcolor: '#16a34a', bordercolor: '#ffffff', borderwidth: 1.5, borderpad: 3,
        curveGroup: 'fire_fav'
      });

      // 150% Overload Test Point ([D])
      traces.push({
        x: [q150], y: [h150], name: '[D] 150% Overload Test Point',
        type: 'scatter', mode: 'markers',
        marker: { color: '#ef4444', size: 13, symbol: 'circle', line: { color: '#ffffff', width: 2 } },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fire_overload', legendgroup: 'fire_overload',
        hovertemplate: `<b>[D] 150% Overload Test Point (NFPA 20)</b><br>Test Flow: %{x:.1f} ${lblQ} (150%)<br>Pump Head: %{y:.1f} ${lblH}<br>NFPA 20 Minimum: ≥ ${minOverloadLimit.toFixed(1)} ${lblH} (65%)<br>Actual Ratio: ${((h150 / hDuty) * 100).toFixed(1)}%<extra></extra>`
      });
      annotations.push({
        x: q150, y: h150, xref: 'x', yref: 'y4',
        text: '<b>D</b>', showarrow: true, arrowcolor: '#ef4444',
        ax: 20, ay: 18, font: { color: '#ffffff', size: 11, weight: 'bold' },
        bgcolor: '#ef4444', bordercolor: '#ffffff', borderwidth: 1.5, borderpad: 3,
        curveGroup: 'fire_overload'
      });

      // NFPA 20 Code Limit Envelope (Dashed Boundary with Letters E, F, G)
      const envQ = [0, qDuty, q150];
      const envH = [maxChurnLimit, hDuty, minOverloadLimit];
      traces.push({
        x: envQ, y: envH, name: 'NFPA 20 Limits [E, F, G]',
        type: 'scatter', mode: 'lines+markers',
        line: { color: '#f43f5e', width: 2.2, dash: 'dash' },
        marker: { color: '#f43f5e', size: 7, symbol: 'circle' },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fire_envelope', legendgroup: 'fire_envelope',
        hovertemplate: `<b>NFPA 20 Limit Boundary</b><br>Flow: %{x:.1f} ${lblQ}<br>Code Limit Head: %{y:.1f} ${lblH}<extra></extra>`
      });

      // System Curve (Green Dashed)
      traces.push({
        x: favSysQ, y: favSysH, name: 'System Curve',
        type: 'scatter', mode: 'lines',
        line: { color: '#16a34a', width: 2.2, dash: 'dash' },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'fav_curve', legendgroup: 'fav_curve',
        hovertemplate: `<b>System Curve</b><br>Flow: %{x:.1f} ${lblQ}<br>System Head: %{y:.1f} ${lblH}<extra></extra>`
      });

      // Store Fire Geometry for dynamic shape rendering
      window.fireProtectionGeometry = {
        qDuty: qDuty,
        hDuty: hDuty,
        qFav: qFav,
        hFav: hFav,
        q150: q150,
        h150: h150,
        hChurn: hChurn,
        maxH: Math.max(...active1xH) * 1.15
      };

    } else if (isParallel) {
      const perQ = (cfg.EVAL_Q_DUTY != null && cfg.EVAL_Q_DUTY !== '') ? cfg.EVAL_Q_DUTY : (cfg.Q_DUTY / stationN);
      const perH = cfg.H_DUTY;

      // 1. Single Pump Operating Duty Point
      traces.push({
        x: [perQ], y: [perH], name: '1x Pump Duty Point',
        type: 'scatter', mode: 'markers',
        marker: { color: ratedColor, size: 12, symbol: 'star' },
        yaxis: 'y4', showlegend: false, curveGroup: 'duty_ind', legendgroup: 'duty_ind',
        hovertemplate: `<b>Per-Pump Duty Point (1 of ${stationN})</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<br>Absorbed Power: ${(cfg.OP_POWER_KW || 0).toFixed(1)} ${lblPow}<br>Efficiency: ${(cfg.OP_ETA || 0).toFixed(1)} %<extra></extra>`
      });
      annotations.push({
        x: perQ, y: perH, xref: 'x', yref: 'y4',
        text: '1x Duty', showarrow: true, arrowcolor: ratedColor,
        ax: 20, ay: -20, font: { color: ratedColor, size: 10 },
        curveGroup: 'duty_ind'
      });

      // 2. Station Total Duty Point
      traces.push({
        x: [cfg.Q_DUTY], y: [cfg.H_DUTY], name: `Station Total Duty (${stationN}x)`,
        type: 'scatter', mode: 'markers',
        marker: { color: '#22c55e', size: 13, symbol: 'diamond' },
        yaxis: 'y4', showlegend: false, curveGroup: 'duty_station', legendgroup: 'duty_station',
        hovertemplate: `<b>Station Total Duty (${stationN}x Parallel)</b><br>Total Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<br>Combined Station Power: ${(cfg.DISP_STATION_POWER || (cfg.OP_POWER_KW * stationN) || 0).toFixed(1)} ${lblPow}<extra></extra>`
      });
      annotations.push({
        x: cfg.Q_DUTY, y: cfg.H_DUTY, xref: 'x', yref: 'y4',
        text: `Station (${stationN}x)`, showarrow: true, arrowcolor: '#22c55e',
        ax: 25, ay: -25, font: { color: '#22c55e', size: 11 },
        curveGroup: 'duty_station'
      });

    } else if (isSeries) {
      const perQ = cfg.Q_DUTY;
      const perH = (cfg.EVAL_H_DUTY != null && cfg.EVAL_H_DUTY !== '') ? cfg.EVAL_H_DUTY : (cfg.H_DUTY / stationN);

      // 1. Single Pump Operating Duty Point
      traces.push({
        x: [perQ], y: [perH], name: '1x Pump Duty Point',
        type: 'scatter', mode: 'markers',
        marker: { color: ratedColor, size: 12, symbol: 'star' },
        yaxis: 'y4', showlegend: false, curveGroup: 'duty_ind', legendgroup: 'duty_ind',
        hovertemplate: `<b>Per-Pump Duty Point (1 of ${stationN})</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<br>Absorbed Power: ${(cfg.OP_POWER_KW || 0).toFixed(1)} ${lblPow}<br>Efficiency: ${(cfg.OP_ETA || 0).toFixed(1)} %<extra></extra>`
      });
      annotations.push({
        x: perQ, y: perH, xref: 'x', yref: 'y4',
        text: '1x Duty', showarrow: true, arrowcolor: ratedColor,
        ax: 20, ay: -20, font: { color: ratedColor, size: 10 },
        curveGroup: 'duty_ind'
      });

      // 2. Station Total Duty Point
      traces.push({
        x: [cfg.Q_DUTY], y: [cfg.H_DUTY], name: `Station Total Duty (${stationN}x)`,
        type: 'scatter', mode: 'markers',
        marker: { color: '#a855f7', size: 13, symbol: 'diamond' },
        yaxis: 'y4', showlegend: false, curveGroup: 'duty_station', legendgroup: 'duty_station',
        hovertemplate: `<b>Station Total Duty (${stationN}x Series)</b><br>Flow: %{x:.1f} ${lblQ}<br>Total Head: %{y:.1f} ${lblH}<extra></extra>`
      });
      annotations.push({
        x: cfg.Q_DUTY, y: cfg.H_DUTY, xref: 'x', yref: 'y4',
        text: `Station (${stationN}x)`, showarrow: true, arrowcolor: '#a855f7',
        ax: 25, ay: -25, font: { color: '#a855f7', size: 11 },
        curveGroup: 'duty_station'
      });

    } else {
      // Standard single pump duty point
      traces.push({
        x: [cfg.Q_DUTY], y: [cfg.H_DUTY], name: 'Operating Duty Point',
        type: 'scatter', mode: 'markers',
        marker: { color: ratedColor, size: 12, symbol: 'star' },
        yaxis: 'y4', showlegend: false,
        curveGroup: 'duty', legendgroup: 'duty',
        hovertemplate: `<b>Duty Point</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<extra></extra>`
      });
      annotations.push({
        x: cfg.Q_DUTY, y: cfg.H_DUTY,
        xref: 'x', yref: 'y4',
        text: 'Duty',
        showarrow: true,
        arrowcolor: ratedColor,
        ax: 20, ay: -20,
        font: { color: ratedColor, size: 11 },
        curveGroup: 'duty'
      });
    }
  }

  // ── Y-axis domain layout & Active Subplot Domains ──
  // When the pump has NPSH data, the chart is split into four vertical sub-plots:
  //   y  (NPSH)  0.00-0.20  |  y2 (Power) 0.25-0.45  |  y3 (Eff) 0.50-0.70  |  y4 (Head) 0.75-1.0
  // When there is no NPSH data the bottom 20 % is reclaimed and shared equally among
  // the three remaining sub-plots so the chart does not have wasted white space.
  const domainNpsh = hasNpsh ? [0.00, 0.20] : null;
  const domainPow = hasNpsh ? [0.25, 0.45] : [0.00, 0.32];
  const domainEff = hasNpsh ? [0.50, 0.70] : [0.36, 0.65];
  const domainHead = hasNpsh ? [0.75, 1.00] : [0.69, 1.00];

  const activeDomains = [
    { key: 'head', domain: domainHead },
    { key: 'eff', domain: domainEff },
    { key: 'power', domain: domainPow }
  ];
  if (hasNpsh && domainNpsh) {
    activeDomains.push({ key: 'npsh', domain: domainNpsh });
  }

  let preferredBorderMode = 'both';
  try {
    preferredBorderMode = localStorage.getItem('pump_graph_border_mode') || org.border_outline_mode || 'both';
  } catch (e) {
    preferredBorderMode = org.border_outline_mode || 'both';
  }

  window.currentGraphBorderMode = preferredBorderMode;
  window.activeGraphDomains = activeDomains;
  window.currentAxisLineColor = axisLineColor;

  const borderSelectEl = document.getElementById('graphBorderOption');
  if (borderSelectEl) {
    borderSelectEl.value = preferredBorderMode;
  }

  const initialShapes = getActiveShapes();

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#8b949e', family: fontFamily },
    margin: { t: 95, r: 80, l: 60, b: 40 },
    hovermode: 'closest',
    xaxis: {
      title: `Flow (${lblQ})`,
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    // NPSH sub-plot: hidden (visible:false) when there is no NPSH data so it occupies no space.
    yaxis: hasNpsh ? {
      title: `NPSHr (${lblNpsh})`, domain: domainNpsh,
      titlefont: { color: npshColor }, tickfont: { color: npshColor },
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    } : { visible: false, domain: [0.0, 0.0] },
    yaxis2: {
      title: `Power (${lblPow})`, domain: domainPow,
      titlefont: { color: powColor }, tickfont: { color: powColor },
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    yaxis3: {
      title: 'Eff (%)', domain: domainEff,
      titlefont: { color: etaColor }, tickfont: { color: etaColor },
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    yaxis4: {
      title: `Head (${lblH})`, domain: domainHead,
      titlefont: { color: hqColor }, tickfont: { color: hqColor },
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    // Beginners Note: yanchor: 'bottom' and y: 1.02 place the baseline of the legend just above
    // the top border of the plot. Additional wrapped lines stack upwards into the 95px top margin,
    // completely preventing the legend from spilling into the Head graph subplot.
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.02,
      xanchor: 'left',
      x: 0,
      font: { size: 11, color: '#8b949e' }
    },
    height: 900,
    annotations: annotations,
    shapes: initialShapes
  };

  applyAxisScale(layout.xaxis, 'flow', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis4, 'head', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis3, 'eff', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis2, 'power', pumpObj, minorGridColor, axisLineColor);
  // Only scale the NPSH axis when it is actually shown.
  if (hasNpsh) applyAxisScale(layout.yaxis, 'npsh', pumpObj, minorGridColor, axisLineColor);

  // ── Dynamic Multi-Pump Axis Scale Expansion ──
  // Beginners Note:
  // In parallel operation, flow is multiplied by N, so layout.xaxis needs expansion to fit
  // total station flow and the station duty point. In series operation, head is multiplied by N,
  // so layout.yaxis4 needs expansion to fit the series shutoff head and station duty point
  // without breaking off the top border.
  if (isParallel) {
    const stationTrace = traces.find(t => t.curveGroup === 'station');
    const peakQ = (stationTrace && stationTrace.x && stationTrace.x.length) ? Math.max(...stationTrace.x) : 0;
    const reqQ = Math.max((cfg.Q_DUTY || 0) * 1.25, peakQ * 1.08);
    if (layout.xaxis.range && layout.xaxis.range[1] < reqQ) {
      const cleanQ = getCleanAxisScale(0, reqQ, pumpObj.axis_flow_major, pumpObj.axis_flow_minor);
      layout.xaxis.range = [0, cleanQ.max];
      if (cleanQ.dtick) layout.xaxis.dtick = cleanQ.dtick;
    }
  } else if (isSeries) {
    const stationTrace = traces.find(t => t.curveGroup === 'station');
    const peakH = (stationTrace && stationTrace.y && stationTrace.y.length) ? Math.max(...stationTrace.y) : 0;
    const reqH = Math.max((cfg.H_DUTY || 0) * 1.25, peakH * 1.08);
    if (layout.yaxis4.range && layout.yaxis4.range[1] < reqH) {
      const cleanH = getCleanAxisScale(0, reqH, pumpObj.axis_head_major, pumpObj.axis_head_minor);
      layout.yaxis4.range = [0, cleanH.max];
      if (cleanH.dtick) layout.yaxis4.dtick = cleanH.dtick;
    }
  }

  // ── Final safety net: strip NPSH traces from the render list when hasNpsh is false.
  // Even though the fam loop already guards NPSH traces with hasNpsh, this filter
  // ensures that no NPSH trace can reach Plotly with a collapsed/invisible axis.
  const renderTraces = hasNpsh ? traces : traces.filter(t => t.curveGroup !== 'npsh');

  // Render Chart
  document.getElementById('chartComp').style.height = '900px';
  document.getElementById('singleChartPanel').style.display = 'block';
  Plotly.newPlot('chartComp', renderTraces, layout, { responsive: true });

  // ── Interactive Legend & Curve Visibility Synchronization ──
  // Beginners Note: Global visibility state object reflecting which curves are currently toggled on/off.
  // We initialize the visibility state for all individual and combined curves.
  window.allChartAnnotations = annotations.slice();

  window.curveVisibility = {
    hq: true,
    eta: true,
    pow: true,
    npsh: hasNpsh,   // false when pump has no NPSH – keeps toggle logic consistent
    rated: true,
    station: true,
    system: true,
    duty_ind: true,
    duty_station: true,
    duty: true,
    fire_remote: true,
    fire_churn: true,
    fire_fav: true,
    fire_150: true,
    fire_envelope: true,
    fav_curve: true,
    fire_regions: true
  };

  const chartEl = document.getElementById('chartComp');

  // Beginners Note: When clicking a category on the Plotly legend, toggle all matching curve traces
  // across all subplots, synchronize annotation labels, and update report parameters.
  chartEl.on('plotly_legendclick', function (data) {
    const clickedTrace = data.data[data.curveNumber];
    const group = clickedTrace ? clickedTrace.curveGroup : null;
    if (!group) return true;

    // Toggle visibility for this curve group
    window.toggleCurveGroup(group);

    return false; // Prevent Plotly's default single-trace toggle behavior
  });

  // Initial UI button state and report links synchronization
  updateToolbarButtonsState();
  updateReportLinks();
}

/**
 * Filter and update chart annotations according to the current curve visibility state.
 * Prevents floating duty point badges and curve labels when the underlying curve is hidden.
 */
function updateChartAnnotations() {
  const chartEl = document.getElementById('chartComp');
  if (!chartEl || !window.allChartAnnotations) return;
  const vis = window.curveVisibility || {};
  const activeAnnotations = window.allChartAnnotations.filter(a => {
    if (!a.curveGroup) return true;
    return vis[a.curveGroup] !== false;
  });
  Plotly.relayout(chartEl, { annotations: activeAnnotations });
}

/**
 * Set the visibility of all traces belonging to a specific curve group.
 * Legend proxy traces (showlegend: true) use 'legendonly' when hidden so they stay in the legend,
 * while actual plotted lines and points (showlegend: false) use false so they disappear completely.
 */
function setGroupVisibility(group, isVisible) {
  const chartEl = document.getElementById('chartComp');
  if (!chartEl || !chartEl.data) return;
  if (!window.curveVisibility) window.curveVisibility = {};
  window.curveVisibility[group] = isVisible;

  const legendIndices = [];
  const plotIndices = [];
  chartEl.data.forEach((t, idx) => {
    if (t.curveGroup === group) {
      if (t.showlegend) legendIndices.push(idx);
      else plotIndices.push(idx);
    }
  });

  if (legendIndices.length > 0) {
    Plotly.restyle(chartEl, { visible: isVisible ? true : 'legendonly' }, legendIndices);
  }
  if (plotIndices.length > 0) {
    Plotly.restyle(chartEl, { visible: isVisible ? true : false }, plotIndices);
  }
}

/**
 * Toggles an individual curve group on/off.
 * Called directly from the Plotly legend click handler or from toolbar buttons.
 * @param {string} group - Curve group name ('rated', 'station', 'system', 'hq', 'eta', 'pow', 'npsh', etc.)
 */
window.toggleCurveGroup = function (group) {
  if (!window.curveVisibility) window.curveVisibility = {};
  const current = window.curveVisibility[group] !== false;
  setGroupVisibility(group, !current);
  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Toggles all operating duty points simultaneously (individual pump, station total, or single pump duty).
 */
window.toggleDutyPoints = function () {
  const vis = window.curveVisibility || {};
  const isAnyVisible = (vis.duty !== false) || (vis.duty_ind !== false) || (vis.duty_station !== false);
  const targetState = !isAnyVisible;

  ['duty', 'duty_ind', 'duty_station'].forEach(grp => {
    setGroupVisibility(grp, targetState);
  });
  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Toggles baseline maximum diameter/speed curves (Head, Eff, Power, NPSHr).
 */
window.toggleMaxCurves = function () {
  const vis = window.curveVisibility || {};
  const isAnyVisible = (vis.hq !== false) || (vis.eta !== false) || (vis.pow !== false) || (vis.npsh !== false);
  const targetState = !isAnyVisible;

  ['hq', 'eta', 'pow', 'npsh'].forEach(grp => {
    setGroupVisibility(grp, targetState);
  });
  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Toggles all fire operating points simultaneously (Most Remote, Churn, Most Favourable, 150% Overload).
 */
window.toggleFirePoints = function () {
  const vis = window.curveVisibility || {};
  const anyVisible = (vis.fire_remote !== false) || (vis.fire_churn !== false) || (vis.fire_fav !== false) || (vis.fire_150 !== false);
  const target = !anyVisible;

  ['fire_remote', 'fire_churn', 'fire_fav', 'fire_150'].forEach(grp => {
    setGroupVisibility(grp, target);
  });
  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Toggles fire operating regions (NFPA 20 code limit envelope and background operating zone bands).
 */
window.toggleFireRegions = function () {
  const vis = window.curveVisibility || {};
  const anyVisible = (vis.fire_envelope !== false) || (vis.fire_regions !== false);
  const target = !anyVisible;

  setGroupVisibility('fire_envelope', target);
  vis.fire_regions = target;

  const chartEl = document.getElementById('chartComp');
  if (chartEl && chartEl.layout) {
    Plotly.relayout(chartEl, { shapes: getActiveShapes() });
  }

  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Toggles the Hydraulically Most Favourable system curve.
 */
window.toggleFavCurve = function () {
  const vis = window.curveVisibility || {};
  const current = vis.fav_curve !== false;
  setGroupVisibility('fav_curve', !current);
  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Toggles individual fire item from the dropdown menu checkboxes.
 */
window.toggleIndividualFireItem = function (itemKey, isChecked) {
  const vis = window.curveVisibility || {};
  const keyMap = {
    remote: 'fire_remote',
    churn: 'fire_churn',
    fav: 'fire_fav',
    overload: 'fire_150',
    fav_curve: 'fav_curve',
    envelope: 'fire_envelope',
    zones: 'fire_regions'
  };

  const grp = keyMap[itemKey];
  if (!grp) return;

  if (grp === 'fire_regions') {
    vis.fire_regions = isChecked;
    const chartEl = document.getElementById('chartComp');
    if (chartEl && chartEl.layout) {
      Plotly.relayout(chartEl, { shapes: getActiveShapes() });
    }
  } else {
    setGroupVisibility(grp, isChecked);
  }

  updateChartAnnotations();
  updateToolbarButtonsState();
  updateReportLinks();
};

/**
 * Updates the visual active/inactive states of the curve toggle buttons above the chart.
 */
function updateToolbarButtonsState() {
  const vis = window.curveVisibility || {};

  function setBtnState(id, isActive) {
    const btn = document.getElementById(id);
    if (!btn) return;
    if (isActive) {
      btn.classList.add('active');
      btn.style.opacity = '1';
      btn.style.borderColor = '#58a6ff';
      btn.style.color = '#ffffff';
    } else {
      btn.classList.remove('active');
      btn.style.opacity = '0.45';
      btn.style.borderColor = '#30363d';
      btn.style.color = '#8b949e';
    }
  }

  setBtnState('btn-toggle-rated', vis.rated !== false);
  setBtnState('btn-toggle-station', vis.station !== false);
  setBtnState('btn-toggle-system', vis.system !== false);

  const dutyActive = (vis.duty !== false) && (vis.duty_ind !== false) && (vis.duty_station !== false);
  setBtnState('btn-toggle-duty', dutyActive);

  const maxActive = (vis.hq !== false) || (vis.eta !== false) || (vis.pow !== false);
  setBtnState('btn-toggle-max', maxActive);

  // Fire buttons & dropdown checkboxes
  const firePtsActive = (vis.fire_remote !== false) || (vis.fire_churn !== false) || (vis.fire_fav !== false) || (vis.fire_150 !== false);
  setBtnState('btn-toggle-fire-points', firePtsActive);

  const fireRegActive = (vis.fire_envelope !== false) || (vis.fire_regions !== false);
  setBtnState('btn-toggle-fire-regions', fireRegActive);

  setBtnState('btn-toggle-fav-curve', vis.fav_curve !== false);

  const chkRemote = document.getElementById('chk-fire-remote');
  if (chkRemote) chkRemote.checked = (vis.fire_remote !== false);
  const chkChurn = document.getElementById('chk-fire-churn');
  if (chkChurn) chkChurn.checked = (vis.fire_churn !== false);
  const chkFav = document.getElementById('chk-fire-fav');
  if (chkFav) chkFav.checked = (vis.fire_fav !== false);
  const chkOverload = document.getElementById('chk-fire-overload');
  if (chkOverload) chkOverload.checked = (vis.fire_150 !== false);
  const chkFavCurve = document.getElementById('chk-fire-fav-curve');
  if (chkFavCurve) chkFavCurve.checked = (vis.fav_curve !== false);
  const chkEnv = document.getElementById('chk-fire-envelope');
  if (chkEnv) chkEnv.checked = (vis.fire_envelope !== false);
  const chkZones = document.getElementById('chk-fire-zones');
  if (chkZones) chkZones.checked = (vis.fire_regions !== false);
}

// Beginners Note: Opens the report with a 100% clean URL (/reports/view) with zero parameters.
// Stores the active report ID and curve visibility toggles into server session['active_selection'].
window.openSessionReport = function (event, reportId) {
  if (event) event.preventDefault();

  const vis = window.curveVisibility || {};
  const hidden = [];
  if (vis.hq === false) hidden.push('hq');
  if (vis.eta === false) hidden.push('eta');
  if (vis.pow === false) hidden.push('pow');
  if (vis.npsh === false) hidden.push('npsh');
  if (vis.rated === false) hidden.push('rated');
  if (vis.station === false) hidden.push('station');
  if (vis.system === false) hidden.push('system');
  if (vis.duty === false) hidden.push('duty');
  if (vis.duty_ind === false) hidden.push('duty_ind');
  if (vis.duty_station === false) hidden.push('duty_station');
  if (vis.fire_remote === false) hidden.push('fire_remote');
  if (vis.fire_churn === false) hidden.push('fire_churn');
  if (vis.fire_fav === false) hidden.push('fire_fav');
  if (vis.fire_150 === false) hidden.push('fire_150');
  if (vis.fire_envelope === false) hidden.push('fire_envelope');
  if (vis.fav_curve === false) hidden.push('fav_curve');
  if (vis.fire_regions === false) hidden.push('fire_regions');

  const params = {
    show_hq: (vis.hq !== false) ? '1' : '0',
    show_eta: (vis.eta !== false) ? '1' : '0',
    show_pow: (vis.pow !== false) ? '1' : '0',
    show_npsh: (vis.npsh !== false) ? '1' : '0',
    show_rated: (vis.rated !== false) ? '1' : '0',
    show_station: (vis.station !== false) ? '1' : '0',
    show_sys: (vis.system !== false) ? '1' : '0',
    show_duty: (vis.duty !== false) ? '1' : '0',
    show_duty_ind: (vis.duty_ind !== false) ? '1' : '0',
    show_duty_station: (vis.duty_station !== false) ? '1' : '0',
    show_fire_remote: (vis.fire_remote !== false) ? '1' : '0',
    show_fire_churn: (vis.fire_churn !== false) ? '1' : '0',
    show_fire_fav: (vis.fire_fav !== false) ? '1' : '0',
    show_fire_150: (vis.fire_150 !== false) ? '1' : '0',
    show_fire_envelope: (vis.fire_envelope !== false) ? '1' : '0',
    show_fav_curve: (vis.fav_curve !== false) ? '1' : '0',
    show_fire_regions: (vis.fire_regions !== false) ? '1' : '0',
    hidden_curves: hidden.join(',')
  };

  fetch('/reports/api/set-active-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_id: reportId, params: params })
  }).then(res => res.json()).then(data => {
    window.open('/reports/view', '_blank');
  }).catch(err => {
    console.error("Error setting active report:", err);
    window.open('/reports/view', '_blank');
  });

  return false;
};

function updateReportLinks() {
  // Sync state whenever legend items or toolbar buttons are toggled
  const vis = window.curveVisibility || {};
  const hidden = [];
  if (vis.hq === false) hidden.push('hq');
  if (vis.eta === false) hidden.push('eta');
  if (vis.pow === false) hidden.push('pow');
  if (vis.npsh === false) hidden.push('npsh');
  if (vis.rated === false) hidden.push('rated');
  if (vis.station === false) hidden.push('station');
  if (vis.system === false) hidden.push('system');
  if (vis.duty === false) hidden.push('duty');
  if (vis.duty_ind === false) hidden.push('duty_ind');
  if (vis.duty_station === false) hidden.push('duty_station');
  if (vis.fire_remote === false) hidden.push('fire_remote');
  if (vis.fire_churn === false) hidden.push('fire_churn');
  if (vis.fire_fav === false) hidden.push('fire_fav');
  if (vis.fire_150 === false) hidden.push('fire_150');
  if (vis.fire_envelope === false) hidden.push('fire_envelope');
  if (vis.fav_curve === false) hidden.push('fav_curve');
  if (vis.fire_regions === false) hidden.push('fire_regions');

  const params = {
    show_hq: (vis.hq !== false) ? '1' : '0',
    show_eta: (vis.eta !== false) ? '1' : '0',
    show_pow: (vis.pow !== false) ? '1' : '0',
    show_npsh: (vis.npsh !== false) ? '1' : '0',
    show_rated: (vis.rated !== false) ? '1' : '0',
    show_station: (vis.station !== false) ? '1' : '0',
    show_sys: (vis.system !== false) ? '1' : '0',
    show_duty: (vis.duty !== false) ? '1' : '0',
    show_duty_ind: (vis.duty_ind !== false) ? '1' : '0',
    show_duty_station: (vis.duty_station !== false) ? '1' : '0',
    show_fire_remote: (vis.fire_remote !== false) ? '1' : '0',
    show_fire_churn: (vis.fire_churn !== false) ? '1' : '0',
    show_fire_fav: (vis.fire_fav !== false) ? '1' : '0',
    show_fire_150: (vis.fire_150 !== false) ? '1' : '0',
    show_fire_envelope: (vis.fire_envelope !== false) ? '1' : '0',
    show_fav_curve: (vis.fav_curve !== false) ? '1' : '0',
    show_fire_regions: (vis.fire_regions !== false) ? '1' : '0',
    hidden_curves: hidden.join(',')
  };

  fetch('/reports/api/set-active-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ params: params })
  }).catch(() => { });
}

// Load data on page load
document.addEventListener('DOMContentLoaded', fetchPumpData);
