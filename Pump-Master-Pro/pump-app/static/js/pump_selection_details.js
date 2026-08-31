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

  const convMap = {
    q: { m3h: 1.0, ls: 0.2777777777777778, gpm: 4.402917396, lmin: 16.6666666667 },
    h: { m: 1.0, ft: 3.280839895 },
    npsh: { m: 1.0, ft: 3.280839895 },
    pow: { kw: 1.0, hp: 1.34102209 }
  };

  let typeKey = 'q';
  let baseUnit = pumpObj.unit_q || 'm3h';

  if (axisName === 'head') {
    typeKey = 'h';
    baseUnit = pumpObj.unit_h || 'm';
  } else if (axisName === 'npsh') {
    typeKey = 'npsh';
    baseUnit = pumpObj.unit_npsh || 'm';
  } else if (axisName === 'power') {
    typeKey = 'pow';
    baseUnit = pumpObj.unit_pow || pumpObj.unit_power || 'kw';
  }

  const factorBase = convMap[typeKey]?.[baseUnit] || 1.0;
  // Details view renders in standard SI units (m3h, m, kw)
  const factorDisplay = 1.0;

  return factorDisplay / factorBase;
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

  // Calculate target step from major divisions
  let targetStep;
  if (majorDivisions !== null && majorDivisions !== undefined && Number(majorDivisions) > 0) {
    targetStep = span / Number(majorDivisions);
  } else {
    targetStep = span / 5.0;
  }

  // Standard clean multipliers across decades: 1, 1.5, 2, 2.5, 5, 10
  const multipliers = [1.0, 1.5, 2.0, 2.5, 5.0, 10.0];
  const mag = Math.pow(10, Math.floor(Math.log10(targetStep > 0 ? targetStep : 1.0)));

  let candidates = [];
  [0.1, 1.0, 10.0].forEach(decade => {
    multipliers.forEach(m => {
      const c = m * mag * decade;
      if (c > 0) candidates.push(Math.round(c * 1000000) / 1000000);
    });
  });

  candidates = Array.from(new Set(candidates)).sort((a, b) => a - b);
  let reasonable = candidates.filter(c => (span / c) >= 2.5 && (span / c) <= 12.0);
  if (reasonable.length === 0) reasonable = candidates;

  // Pick candidate step with MINIMAL change from targetStep
  let cleanStep = reasonable[0];
  let minDiff = Math.abs(cleanStep - targetStep);
  for (let i = 1; i < reasonable.length; i++) {
    const diff = Math.abs(reasonable[i] - targetStep);
    if (diff < minDiff) {
      minDiff = diff;
      cleanStep = reasonable[i];
    }
  }

  // Clean max: ceil to nearest multiple of cleanStep so all data fits and ends on clean round number (e.g. 110, 120, 150)
  const numSteps = Math.ceil((maxVal - minVal) / cleanStep - 1e-5);
  const cleanMax = minVal + numSteps * cleanStep;

  return {
    min: minVal,
    max: cleanMax,
    dtick: cleanStep,
    minor: minorSubticks
  };
}

function applyAxisScale(axisObj, axisName, pumpObj, minorGridColor, axisLineColor) {
  if (!pumpObj) return;

  const rawMin = pumpObj[`axis_${axisName}_min`];
  const rawMax = pumpObj[`axis_${axisName}_max`];
  const majorVal = pumpObj[`axis_${axisName}_major`];
  const minorVal = pumpObj[`axis_${axisName}_minor`];

  const unitRatio = getDetailsUnitScaleRatio(axisName, pumpObj);

  // 1. Custom Min & Max Range Bounds
  const hasMin = rawMin !== null && rawMin !== undefined && rawMin !== '';
  const hasMax = rawMax !== null && rawMax !== undefined && rawMax !== '';

  if (hasMin || hasMax) {
    const currentMin = hasMin ? parseFloat(rawMin) * unitRatio : 0;
    const currentMax = hasMax ? parseFloat(rawMax) * unitRatio : 100;

    const clean = getCleanAxisScale(currentMin, currentMax, majorVal, minorVal);

    axisObj.range = [clean.min, clean.max];
    axisObj.autorange = false;
    delete axisObj.rangemode;

    if (clean.dtick !== null && clean.dtick > 0) {
      axisObj.dtick = clean.dtick;
      axisObj.tickmode = 'linear';
    }
  } else if (majorVal !== null && majorVal > 0) {
    axisObj.nticks = Math.round(majorVal) + 1;
  }

  // 3. Minor Subticks
  if (minorVal !== null && minorVal !== undefined && minorVal !== '' && parseInt(minorVal, 10) > 0) {
    axisObj.minor = {
      nticks: parseInt(minorVal, 10) + 1,
      showgrid: true,
      gridcolor: minorGridColor || '#21262d',
      gridwidth: 1,
      ticks: 'inside',
      ticklen: 4,
      tickcolor: axisLineColor || '#30363d'
    };
  }
}

function addLabel(annotations, x, y, yref, text, color, isMid=false) {
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
      font: {color: color, size: 11},
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

  // Theme & Styles from Organisation Defaults
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

  let traces = [];
  let annotations = [];

  // Calculate duty (rated) curves using affinity laws from max curve
  const qDutyCurve = maxCurve.q.map(q => q * cfg.TRIM_RATIO);
  const hDutyCurve = maxCurve.h.map(h => h * Math.pow(cfg.TRIM_RATIO, 2));
  const pDutyCurve = maxCurve.power.map(p => p * Math.pow(cfg.TRIM_RATIO, 3));
  const npshDutyCurve = maxCurve.npsh ? maxCurve.npsh.map(n => n * Math.pow(cfg.TRIM_RATIO, 2)) : [];

  if (fam && fam.length > 0) {
    fam.forEach((c, idx) => {
      let lbl = cfg.IS_VSD ? `${c.rpm || c.val} RPM` : `Ø ${c.dia} mm`;
      let isMax = idx === fam.length - 1; 
      let curveWidth = isMax ? hqWidth : Math.max(1.2, hqWidth * 0.7);
      
      let cdata = c.q.map((q, i) => [
        c.h[i] != null ? c.h[i].toFixed(1) : 'N/A',
        c.eta[i] != null ? c.eta[i].toFixed(1) : 'N/A',
        c.power[i] != null ? c.power[i].toFixed(1) : 'N/A',
        (c.npsh && c.npsh[i] != null) ? c.npsh[i].toFixed(1) : 'N/A'
      ]);
      let hoverTmpl = `<b>${lbl}</b><br>Flow: %{x:.1f} m³/h<br>Head: %{customdata[0]} m<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} kW<br>NPSHr: %{customdata[3]} m<extra></extra>`;
      
      // Head
      traces.push({x: c.q, y: c.h, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: {color: hqColor, width: curveWidth, dash: hqStyle}, yaxis: 'y4', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'hq'});
      addLabel(annotations, c.q, c.h, 'y4', lbl, hqColor);
      
      // Eff
      traces.push({x: c.q, y: c.eta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: {color: etaColor, width: isMax ? etaWidth : Math.max(1.2, etaWidth * 0.7), dash: etaStyle}, yaxis: 'y3', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'eta'});
      addLabel(annotations, c.q, c.eta, 'y3', lbl, etaColor);

      // Power
      traces.push({x: c.q, y: c.power, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: {color: powColor, width: isMax ? powWidth : Math.max(1.2, powWidth * 0.7), dash: powStyle}, yaxis: 'y2', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'pow'});
      addLabel(annotations, c.q, c.power, 'y2', lbl, powColor);

      // NPSHr
      if (c.npsh && c.npsh.length) {
        traces.push({x: c.q, y: c.npsh, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: {color: npshColor, width: isMax ? npshWidth : Math.max(1.2, npshWidth * 0.7), dash: npshStyle}, yaxis: 'y', opacity: isMax ? 1 : 0.55, showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'npsh'});
        addLabel(annotations, c.q, c.npsh, 'y', lbl, npshColor);
      }
    });
  } else {
    let lbl = 'Max';
    let cdata = maxCurve.q.map((q, i) => [
      maxCurve.h[i] != null ? maxCurve.h[i].toFixed(1) : 'N/A',
      maxCurve.eta[i] != null ? maxCurve.eta[i].toFixed(1) : 'N/A',
      maxCurve.power[i] != null ? maxCurve.power[i].toFixed(1) : 'N/A',
      (maxCurve.npsh && maxCurve.npsh[i] != null) ? maxCurve.npsh[i].toFixed(1) : 'N/A'
    ]);
    let hoverTmpl = `<b>${lbl}</b><br>Flow: %{x:.1f} m³/h<br>Head: %{customdata[0]} m<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} kW<br>NPSHr: %{customdata[3]} m<extra></extra>`;

    traces.push({x: maxCurve.q, y: maxCurve.h, name: 'Head (Max)', type: 'scatter', mode: 'lines', line: {color: hqColor, width: hqWidth, dash: hqStyle}, yaxis: 'y4', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'hq'});
    addLabel(annotations, maxCurve.q, maxCurve.h, 'y4', 'Max', hqColor);
    
    traces.push({x: maxCurve.q, y: maxCurve.eta, name: 'Eff (Max)', type: 'scatter', mode: 'lines', line: {color: etaColor, width: etaWidth, dash: etaStyle}, yaxis: 'y3', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'eta'});
    addLabel(annotations, maxCurve.q, maxCurve.eta, 'y3', 'Max', etaColor);
    
    traces.push({x: maxCurve.q, y: maxCurve.power, name: 'Power (Max)', type: 'scatter', mode: 'lines', line: {color: powColor, width: powWidth, dash: powStyle}, yaxis: 'y2', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'pow'});
    addLabel(annotations, maxCurve.q, maxCurve.power, 'y2', 'Max', powColor);
    
    if (maxCurve.npsh) {
      traces.push({x: maxCurve.q, y: maxCurve.npsh, name: 'NPSHr (Max)', type: 'scatter', mode: 'lines', line: {color: npshColor, width: npshWidth, dash: npshStyle}, yaxis: 'y', showlegend: false, customdata: cdata, hovertemplate: hoverTmpl, curveGroup: 'npsh'});
      addLabel(annotations, maxCurve.q, maxCurve.npsh, 'y', 'Max', npshColor);
    }
  }

  // Add Rated Curves
  if (cfg.TRIM_RATIO < 1.0) {
    let lbl = cfg.IS_VSD ? `Rated (${cfg.RATED_SPEED} RPM)` : `Rated (Ø ${cfg.RATED_TRIM} mm)`;
    let cdataRated = qDutyCurve.map((q, i) => [
      hDutyCurve[i] != null ? hDutyCurve[i].toFixed(1) : 'N/A',
      maxCurve.eta[i] != null ? maxCurve.eta[i].toFixed(1) : 'N/A',
      pDutyCurve[i] != null ? pDutyCurve[i].toFixed(1) : 'N/A',
      (npshDutyCurve && npshDutyCurve[i] != null) ? npshDutyCurve[i].toFixed(1) : 'N/A'
    ]);
    let hoverTmplRated = `<b>${lbl}</b><br>Flow: %{x:.1f} m³/h<br>Head: %{customdata[0]} m<br>Eff: %{customdata[1]} %<br>Power: %{customdata[2]} kW<br>NPSHr: %{customdata[3]} m<extra></extra>`;

    traces.push({x: qDutyCurve, y: hDutyCurve, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: {color: ratedColor, width: trimWidth, dash: trimStyle}, yaxis: 'y4', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated'});

    traces.push({x: qDutyCurve, y: maxCurve.eta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: {color: ratedColor, width: trimWidth, dash: trimStyle}, yaxis: 'y3', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated'});
    
    traces.push({x: qDutyCurve, y: pDutyCurve, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: {color: ratedColor, width: trimWidth, dash: trimStyle}, yaxis: 'y2', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated'});
    
    if (npshDutyCurve && npshDutyCurve.length) {
      traces.push({x: qDutyCurve, y: npshDutyCurve, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: {color: ratedColor, width: trimWidth, dash: trimStyle}, yaxis: 'y', showlegend: false, customdata: cdataRated, hovertemplate: hoverTmplRated, curveGroup: 'rated'});
    }
  }

  // System Curve
  if (cfg.Q_DUTY && cfg.H_DUTY) {
    const k = cfg.H_DUTY / Math.pow(cfg.Q_DUTY, 2);
    const maxPumpH = Math.max(...maxCurve.h);
    const limitH = maxPumpH * 1.25;
    
    const sysQ = [];
    const sysH = [];
    for (let i = 0; i < maxCurve.q.length; i++) {
        const q = maxCurve.q[i];
        const h = k * Math.pow(q, 2);
        if (h <= limitH) {
            sysQ.push(q);
            sysH.push(h);
        }
    }
    
    // Ensure it goes at least up to the duty point
    if (sysQ.length === 0 || sysQ[sysQ.length - 1] < cfg.Q_DUTY) {
        sysQ.push(cfg.Q_DUTY);
        sysH.push(cfg.H_DUTY);
    }

    let hoverTmplSys = `<b>System Curve</b><br>Flow: %{x:.1f} m³/h<br>Head: %{y:.1f} m<extra></extra>`;
    traces.push({x: sysQ, y: sysH, name: 'System Curve', type: 'scatter', mode: 'lines', line: {color: sysColor, width: 2.2, dash: sysStyle}, yaxis: 'y4', showlegend: false, hovertemplate: hoverTmplSys, curveGroup: 'system'});
  }

  // Custom Clean Legend Items (Interactive Group Headers)
  traces.push({x: [null], y: [null], name: 'Head', type: 'scatter', mode: 'lines', line: {color: hqColor, width: hqWidth, dash: hqStyle}, showlegend: true, curveGroup: 'hq'});
  traces.push({x: [null], y: [null], name: 'Efficiency', type: 'scatter', mode: 'lines', line: {color: etaColor, width: etaWidth, dash: etaStyle}, showlegend: true, curveGroup: 'eta'});
  traces.push({x: [null], y: [null], name: 'Power', type: 'scatter', mode: 'lines', line: {color: powColor, width: powWidth, dash: powStyle}, showlegend: true, curveGroup: 'pow'});
  traces.push({x: [null], y: [null], name: 'NPSHr', type: 'scatter', mode: 'lines', line: {color: npshColor, width: npshWidth, dash: npshStyle}, showlegend: true, curveGroup: 'npsh'});
  
  let ratedLegendName = cfg.TRIM_RATIO < 1.0 
    ? (cfg.IS_VSD ? `Rated Curve (${cfg.RATED_SPEED} RPM)` : `Rated Curve (Ø ${cfg.RATED_TRIM} mm)`)
    : 'Rated Curve';
  traces.push({x: [null], y: [null], name: ratedLegendName, type: 'scatter', mode: 'lines', line: {color: ratedColor, width: trimWidth, dash: trimStyle}, showlegend: true, curveGroup: 'rated'});
  traces.push({x: [null], y: [null], name: 'System Curve', type: 'scatter', mode: 'lines', line: {color: sysColor, width: 2.2, dash: sysStyle}, showlegend: true, curveGroup: 'system'});

  // Duty Point
  if (cfg.Q_DUTY && cfg.H_DUTY) {
    traces.push({
      x: [cfg.Q_DUTY], y: [cfg.H_DUTY], name: 'Duty Point',
      type: 'scatter', mode: 'markers',
      marker: { color: ratedColor, size: 12, symbol: 'star' },
      yaxis: 'y4',
      showlegend: true,
      curveGroup: 'duty',
      hovertemplate: `<b>Duty Point</b><br>Flow: %{x:.1f} m³/h<br>Head: %{y:.1f} m<extra></extra>`
    });
    annotations.push({
      x: cfg.Q_DUTY, y: cfg.H_DUTY,
      xref: 'x', yref: 'y4',
      text: 'Duty',
      showarrow: true,
      arrowcolor: ratedColor,
      ax: 20, ay: -20,
      font: {color: ratedColor, size: 11}
    });
  }

  // Base Layout Structure
  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#8b949e', family: fontFamily },
    margin: { t: 40, r: 80, l: 60, b: 40 },
    hovermode: 'closest',
    // Shared X axis (Flow)
    xaxis: { 
      title: 'Flow (m³/h)', 
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    // NPSHr (Bottom: 0% - 20%)
    yaxis: { 
      title: 'NPSHr (m)', domain: [0.0, 0.20],
      titlefont: {color: npshColor}, tickfont: {color: npshColor},
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    // Power (25% - 45%)
    yaxis2: { 
      title: 'Power (kW)', domain: [0.25, 0.45],
      titlefont: {color: powColor}, tickfont: {color: powColor},
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    // Efficiency (50% - 70%)
    yaxis3: { 
      title: 'Eff (%)', domain: [0.50, 0.70],
      titlefont: {color: etaColor}, tickfont: {color: etaColor},
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    // Head (Top: 75% - 100%)
    yaxis4: { 
      title: 'Head (m)', domain: [0.75, 1.0],
      titlefont: {color: hqColor}, tickfont: {color: hqColor},
      gridcolor: majorGridColor, zerolinecolor: axisLineColor, rangemode: 'tozero'
    },
    legend: { orientation: 'h', y: 1.05, x: 0 },
    height: 900,
    annotations: annotations
  };

  // ── Apply Custom Axis Scaling and Bounds from Pump-Data ──────────────────
  applyAxisScale(layout.xaxis, 'flow', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis4, 'head', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis3, 'eff', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis2, 'power', pumpObj, minorGridColor, axisLineColor);
  applyAxisScale(layout.yaxis, 'npsh', pumpObj, minorGridColor, axisLineColor);

  // Render Chart
  document.getElementById('chartComp').style.height = '900px';
  document.getElementById('singleChartPanel').style.display = 'block';
  Plotly.newPlot('chartComp', traces, layout, {responsive: true});

  // ── Interactive Legend & Curve Visibility Synchronization ──
  // Beginners Note: Global visibility state object reflecting which curves are currently toggled on/off.
  window.curveVisibility = {
    hq: true,
    eta: true,
    pow: true,
    npsh: true,
    rated: true,
    system: true,
    duty: true
  };

  const chartEl = document.getElementById('chartComp');

  // Beginners Note: When clicking a category on the Plotly legend, toggle all matching curve traces
  // and update report URLs so that Proposal reports generated will exactly mirror the visible curves on screen.
  chartEl.on('plotly_legendclick', function(data) {
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
window.openSessionReport = function(event, reportId) {
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
  }).catch(() => {});
}

// Load data on page load
document.addEventListener('DOMContentLoaded', fetchPumpData);
