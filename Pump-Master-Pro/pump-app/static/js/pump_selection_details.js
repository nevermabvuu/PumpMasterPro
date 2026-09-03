let pumpData = null;

async function fetchPumpData() {
  document.getElementById('chartLoading').style.display = 'block';

  const params = new URLSearchParams({
    ids: window.PumpDetailsConfig.PUMP_ID,
    liquid: window.PumpDetailsConfig.LIQUID_TYPE,
    rho: window.PumpDetailsConfig.RHO,
    viscosity_cSt: window.PumpDetailsConfig.VISCOSITY,
    slurry_cv: window.PumpDetailsConfig.SLURRY_CV,
    slurry_d50: window.PumpDetailsConfig.SLURRY_D50,
    rho_solid: window.PumpDetailsConfig.RHO_SOLID,
    operation_mode: window.PumpDetailsConfig.OPERATION_MODE
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

function addLabel(annotations, x, y, yref, text, color, isMid = false) {
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
      yshift: isMid ? 10 : 0
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

  const qDutyCurve = scaledMaxQ.map(q => q * cfg.TRIM_RATIO);
  const hDutyCurve = scaledMaxH.map(h => h * Math.pow(cfg.TRIM_RATIO, 2));
  const pDutyCurve = scaledMaxPow.map(p => p * Math.pow(cfg.TRIM_RATIO, 3));
  const npshDutyCurve = scaledMaxNpsh.length ? scaledMaxNpsh.map(n => n * Math.pow(cfg.TRIM_RATIO, 2)) : [];

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

      traces.push({ x: scQ, y: scH, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: { color: hqColor, width: curveWidth, dash: hqStyle }, yaxis: 'y4', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'hq' });
      addLabel(annotations, scQ, scH, 'y4', lbl, hqColor);

      traces.push({ x: scQ, y: c.eta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: { color: etaColor, width: isMax ? etaWidth : Math.max(1.2, etaWidth * 0.7), dash: etaStyle }, yaxis: 'y3', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'eta' });
      addLabel(annotations, scQ, c.eta, 'y3', lbl, etaColor);

      traces.push({ x: scQ, y: scPow, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: { color: powColor, width: isMax ? powWidth : Math.max(1.2, powWidth * 0.7), dash: powStyle }, yaxis: 'y2', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'pow' });
      addLabel(annotations, scQ, scPow, 'y2', lbl, powColor);

      // Only add NPSH traces when the pump actually has NPSH data (guarded by hasNpsh
      // computed above). Without this guard, traces on the hidden 'y' axis bleed into
      // adjacent sub-plots (e.g., efficiency) when the axis domain is collapsed.
      if (hasNpsh && scNpsh && scNpsh.length) {
        traces.push({ x: scQ, y: scNpsh, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: { color: npshColor, width: isMax ? npshWidth : Math.max(1.2, npshWidth * 0.7), dash: npshStyle }, yaxis: 'y', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'npsh' });
        addLabel(annotations, scQ, scNpsh, 'y', lbl, npshColor);
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

    traces.push({ x: scaledMaxQ, y: scaledMaxH, name: 'Head (Max)', type: 'scatter', mode: 'lines', line: { color: hqColor, width: hqWidth, dash: hqStyle }, yaxis: 'y4', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'hq' });
    addLabel(annotations, scaledMaxQ, scaledMaxH, 'y4', 'Max', hqColor);

    traces.push({ x: scaledMaxQ, y: maxCurve.eta, name: 'Eff (Max)', type: 'scatter', mode: 'lines', line: { color: etaColor, width: etaWidth, dash: etaStyle }, yaxis: 'y3', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'eta' });
    addLabel(annotations, scaledMaxQ, maxCurve.eta, 'y3', 'Max', etaColor);

    traces.push({ x: scaledMaxQ, y: scaledMaxPow, name: 'Power (Max)', type: 'scatter', mode: 'lines', line: { color: powColor, width: powWidth, dash: powStyle }, yaxis: 'y2', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'pow' });
    addLabel(annotations, scaledMaxQ, scaledMaxPow, 'y2', 'Max', powColor);

    if (scaledMaxNpsh.length) {
      traces.push({ x: scaledMaxQ, y: scaledMaxNpsh, name: 'NPSHr (Max)', type: 'scatter', mode: 'lines', line: { color: npshColor, width: npshWidth, dash: npshStyle }, yaxis: 'y', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'npsh' });
      addLabel(annotations, scaledMaxQ, scaledMaxNpsh, 'y', 'Max', npshColor);
    }
  }

  if (cfg.TRIM_RATIO < 1.0) {
    let lbl = cfg.IS_VSD ? `Rated (${cfg.RATED_SPEED} RPM)` : `Rated (Ø ${cfg.RATED_TRIM} mm)`;
    let cdataRated = qDutyCurve.map((q, i) => [
      hDutyCurve[i] != null ? hDutyCurve[i].toFixed(1) : 'N/A',
      maxCurve.eta[i] != null ? maxCurve.eta[i].toFixed(1) : 'N/A',
      pDutyCurve[i] != null ? pDutyCurve[i].toFixed(1) : 'N/A',
      (npshDutyCurve && npshDutyCurve[i] != null) ? npshDutyCurve[i].toFixed(1) : 'N/A'
    ]);
    let hoverTmplRated = `<b>${lbl}</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{customdata[0]} ${lblH}<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} ${lblPow}<br>NPSHr: %{customdata[3]} ${lblNpsh}<extra></extra>`;

    // Rated (trimmed/VSD) curves on each sub-plot.
    // All values are affinity-law scaled: x[i]=Q_max[i]*r, y_H[i]=H_max[i]*r², y_P[i]=P_max[i]*r³
    // Efficiency: by affinity law, efficiency is the same curve but over a shorter Q range.
    //   scaledMaxQ is evenly spaced 0..Q_max (N points).
    //   The rated Q range is 0..Q_max*r, which corresponds to the FIRST ~N*r indices of
    //   the max-dia arrays.  Using ALL N eta values compressed into N*r x-positions
    //   made the post-BEP efficiency drop crowd near the right end (flat-looking tail).
    //   Fix: slice to ratedN = round(N * TRIM_RATIO) so the x-y pairing is correct.
    const ratedN = Math.max(2, Math.round(scaledMaxQ.length * cfg.TRIM_RATIO));
    const ratedQ = qDutyCurve.slice(0, ratedN);
    const ratedH = hDutyCurve.slice(0, ratedN);
    // Eta: interpolate the max-dia curve at the rated Q positions so the shape is identical
    // to the max-dia efficiency bell, simply cut off at the rated flow.
    const ratedEta = maxCurve.eta.slice(0, ratedN);
    const ratedPow = pDutyCurve.slice(0, ratedN);


    traces.push({ x: ratedQ, y: ratedH, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: { color: ratedColor, width: trimWidth, dash: trimStyle }, yaxis: 'y4', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated' });
    traces.push({ x: ratedQ, y: ratedEta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: { color: ratedColor, width: trimWidth, dash: trimStyle }, yaxis: 'y3', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated' });
    traces.push({ x: ratedQ, y: ratedPow, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: { color: ratedColor, width: trimWidth, dash: trimStyle }, yaxis: 'y2', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated' });
    if (hasNpsh && npshDutyCurve && npshDutyCurve.length) {
      const ratedNpsh = npshDutyCurve.slice(0, ratedN);
      traces.push({ x: ratedQ, y: ratedNpsh, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: { color: ratedColor, width: trimWidth, dash: trimStyle }, yaxis: 'y', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated' });
    }


  }

  if (cfg.Q_DUTY && cfg.H_DUTY) {
    const k = cfg.H_DUTY / Math.pow(cfg.Q_DUTY, 2);
    const maxPumpH = Math.max(...scaledMaxH);
    const limitH = maxPumpH * 1.25;

    const sysQ = [];
    const sysH = [];
    for (let i = 0; i < scaledMaxQ.length; i++) {
      const q = scaledMaxQ[i];
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
    traces.push({ x: sysQ, y: sysH, name: 'System Curve', type: 'scatter', mode: 'lines', line: { color: sysColor, width: 2.2, dash: sysStyle }, yaxis: 'y4', showlegend: false, hovertemplate: hoverTmplSys, curveGroup: 'system' });
  }

  // Determine once whether this pump has any NPSH data at all.
  // (hasNpsh was computed early above from all curve sources.)
  // As a final safety net, also strip any NPSH-group traces from the legend
  // and the render array so a collapsed/invisible axis cannot cause them to
  // bleed into adjacent sub-plots (efficiency, power, etc.).
  traces.push({ x: [null], y: [null], name: 'Head', type: 'scatter', mode: 'lines', line: { color: hqColor, width: hqWidth, dash: hqStyle }, showlegend: true, curveGroup: 'hq' });
  traces.push({ x: [null], y: [null], name: 'Efficiency', type: 'scatter', mode: 'lines', line: { color: etaColor, width: etaWidth, dash: etaStyle }, showlegend: true, curveGroup: 'eta' });
  traces.push({ x: [null], y: [null], name: 'Power', type: 'scatter', mode: 'lines', line: { color: powColor, width: powWidth, dash: powStyle }, showlegend: true, curveGroup: 'pow' });
  // Only add the NPSHr legend entry when there is actual NPSH data to show.
  if (hasNpsh) {
    traces.push({ x: [null], y: [null], name: 'NPSHr', type: 'scatter', mode: 'lines', line: { color: npshColor, width: npshWidth, dash: npshStyle }, showlegend: true, curveGroup: 'npsh' });
  }

  let ratedLegendName = 'Rated Curve';
  if (cfg.IS_VSD) {
    ratedLegendName = `Rated Curve (${cfg.RATED_SPEED || Math.round(cfg.PUMP_SPEED * cfg.TRIM_RATIO)} RPM)`;
  } else if (cfg.FIXED_SPEED_MODE === 'auto') {
    ratedLegendName = `Calculated Speed (${cfg.RATED_SPEED || Math.round(cfg.PUMP_SPEED * cfg.TRIM_RATIO)} RPM)`;
  } else if (cfg.FIXED_SPEED_MODE === 'manual') {
    ratedLegendName = `Manual Speed (${cfg.RATED_SPEED || cfg.MANUAL_SPEED_RPM} RPM)`;
    if (cfg.TRIM_RATIO < 0.995 && cfg.RATED_TRIM) {
      ratedLegendName += ` (Ø${cfg.RATED_TRIM}mm)`;
    }
  } else if (cfg.TRIM_RATIO < 1.0) {
    ratedLegendName = `Rated Curve (Ø ${cfg.RATED_TRIM} mm)`;
  }
  traces.push({ x: [null], y: [null], name: ratedLegendName, type: 'scatter', mode: 'lines', line: { color: ratedColor, width: trimWidth, dash: trimStyle }, showlegend: true, curveGroup: 'rated' });
  traces.push({ x: [null], y: [null], name: 'System Curve', type: 'scatter', mode: 'lines', line: { color: sysColor, width: 2.2, dash: sysStyle }, showlegend: true, curveGroup: 'system' });

  if (cfg.Q_DUTY && cfg.H_DUTY) {
    traces.push({
      x: [cfg.Q_DUTY], y: [cfg.H_DUTY], name: 'Duty Point',
      type: 'scatter', mode: 'markers',
      marker: { color: ratedColor, size: 12, symbol: 'star' },
      yaxis: 'y4',
      showlegend: true,
      curveGroup: 'duty',
      hovertemplate: `<b>Duty Point</b><br>Flow: %{x:.1f} ${lblQ}<br>Head: %{y:.1f} ${lblH}<extra></extra>`
    });
    annotations.push({
      x: cfg.Q_DUTY, y: cfg.H_DUTY,
      xref: 'x', yref: 'y4',
      text: 'Duty',
      showarrow: true,
      arrowcolor: ratedColor,
      ax: 20, ay: -20,
      font: { color: ratedColor, size: 11 }
    });
  }

  // ── Y-axis domain layout ──
  // When the pump has NPSH data, the chart is split into four vertical sub-plots:
  //   y  (NPSH)  0.00-0.20  |  y2 (Power) 0.25-0.45  |  y3 (Eff) 0.50-0.70  |  y4 (Head) 0.75-1.0
  // When there is no NPSH data the bottom 20 % is reclaimed and shared equally among
  // the three remaining sub-plots so the chart does not have wasted white space.
  const domainNpsh = hasNpsh ? [0.00, 0.20] : null;
  const domainPow = hasNpsh ? [0.25, 0.45] : [0.00, 0.32];
  const domainEff = hasNpsh ? [0.50, 0.70] : [0.36, 0.65];
  const domainHead = hasNpsh ? [0.75, 1.00] : [0.69, 1.00];

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#8b949e', family: fontFamily },
    margin: { t: 40, r: 80, l: 60, b: 40 },
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
    legend: { orientation: 'h', y: 1.05, x: 0 },
    height: 900,
    annotations: annotations
  };

  applyAxisScale(layout.xaxis, 'flow', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis4, 'head', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis3, 'eff', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis2, 'power', pumpObj, minorGridColor, axisLineColor);
  // Only scale the NPSH axis when it is actually shown.
  if (hasNpsh) applyAxisScale(layout.yaxis, 'npsh', pumpObj, minorGridColor, axisLineColor);

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
  // npsh is only relevant when the pump actually has NPSH data; default it to false otherwise
  // so that any visibility-toggle logic that checks window.curveVisibility.npsh behaves correctly.
  window.curveVisibility = {
    hq: true,
    eta: true,
    pow: true,
    npsh: hasNpsh,   // false when pump has no NPSH – keeps toggle logic consistent
    rated: true,
    system: true,
    duty: true
  };

  const chartEl = document.getElementById('chartComp');

  // Beginners Note: When clicking a category on the Plotly legend, toggle all matching curve traces
  // and update report URLs so that Proposal reports generated will exactly mirror the visible curves on screen.
  chartEl.on('plotly_legendclick', function (data) {
    const clickedTrace = data.data[data.curveNumber];
    const group = clickedTrace ? clickedTrace.curveGroup : null;
    if (!group) return true;

    // Invert the visibility state of the chosen curve group
    const isVisible = (window.curveVisibility[group] !== false);
    const newVis = !isVisible;
    window.curveVisibility[group] = newVis;

    // Find all trace indices belonging to this group
    const targetIndices = [];
    data.data.forEach((t, idx) => {
      if (t.curveGroup === group) {
        targetIndices.push(idx);
      }
    });

    // Update Plotly trace visibility (true for visible, 'legendonly' to hide trace while keeping legend item)
    const targetVal = newVis ? true : 'legendonly';
    Plotly.restyle(chartEl, { visible: targetVal }, targetIndices);

    // Sync all report links on the page immediately
    updateReportLinks();

    return false; // Prevent default single-trace toggle behavior
  });

  // Initial report links synchronization
  updateReportLinks();
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
  if (vis.system === false) hidden.push('system');
  if (vis.duty === false) hidden.push('duty');

  const params = {
    show_hq: (vis.hq !== false) ? '1' : '0',
    show_eta: (vis.eta !== false) ? '1' : '0',
    show_pow: (vis.pow !== false) ? '1' : '0',
    show_npsh: (vis.npsh !== false) ? '1' : '0',
    show_rated: (vis.rated !== false) ? '1' : '0',
    show_sys: (vis.system !== false) ? '1' : '0',
    show_duty: (vis.duty !== false) ? '1' : '0',
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
  // Sync state whenever legend items are toggled
  const vis = window.curveVisibility || {};
  const hidden = [];
  if (vis.hq === false) hidden.push('hq');
  if (vis.eta === false) hidden.push('eta');
  if (vis.pow === false) hidden.push('pow');
  if (vis.npsh === false) hidden.push('npsh');
  if (vis.rated === false) hidden.push('rated');
  if (vis.system === false) hidden.push('system');
  if (vis.duty === false) hidden.push('duty');

  const params = {
    show_hq: (vis.hq !== false) ? '1' : '0',
    show_eta: (vis.eta !== false) ? '1' : '0',
    show_pow: (vis.pow !== false) ? '1' : '0',
    show_npsh: (vis.npsh !== false) ? '1' : '0',
    show_rated: (vis.rated !== false) ? '1' : '0',
    show_sys: (vis.system !== false) ? '1' : '0',
    show_duty: (vis.duty !== false) ? '1' : '0',
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
