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
    rho_solid: window.PumpDetailsConfig.RHO_SOLID
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

function buildTrace(x, y, name, color, yaxis='y', dash='solid') {
  return {
    x: x, y: y, name: name, type: 'scatter', mode: 'lines',
    line: { color: color, width: 2.5, dash: dash },
    yaxis: yaxis
  };
}

function buildDutyTrace(q, h, name) {
  if (!q || !h) return null;
  return {
    x: [q], y: [h], name: name,
    type: 'scatter', mode: 'markers',
    marker: { color: '#f85149', size: 12, symbol: 'star' },
    yaxis: 'y4'
  };
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
  if (!maxCurve || !maxCurve.q) return;

  const cfg = window.PumpDetailsConfig;

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
      
      // Head
      traces.push({x: c.q, y: c.h, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#58a6ff', width: isMax ? 2.5 : 1.5}, yaxis: 'y4', opacity: isMax ? 1 : 0.5, showlegend: false});
      addLabel(annotations, c.q, c.h, 'y4', lbl, '#58a6ff');
      
      // Eff
      traces.push({x: c.q, y: c.eta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#3fb950', width: isMax ? 2.5 : 1.5}, yaxis: 'y3', opacity: isMax ? 1 : 0.5, showlegend: false});
      addLabel(annotations, c.q, c.eta, 'y3', lbl, '#3fb950');

      // Power
      traces.push({x: c.q, y: c.power, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#f0c040', width: isMax ? 2.5 : 1.5}, yaxis: 'y2', opacity: isMax ? 1 : 0.5, showlegend: false});
      addLabel(annotations, c.q, c.power, 'y2', lbl, '#f0c040');

      // NPSHr
      if (c.npsh && c.npsh.length) {
        traces.push({x: c.q, y: c.npsh, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#bc8cff', width: isMax ? 2.5 : 1.5}, yaxis: 'y', opacity: isMax ? 1 : 0.5, showlegend: false});
        addLabel(annotations, c.q, c.npsh, 'y', lbl, '#bc8cff');
      }
    });
  } else {
    // Fallback if family data is missing
    traces.push({x: maxCurve.q, y: maxCurve.h, name: 'Head (Max)', type: 'scatter', mode: 'lines', line: {color: '#58a6ff', width: 2.5}, yaxis: 'y4', showlegend: false});
    addLabel(annotations, maxCurve.q, maxCurve.h, 'y4', 'Max', '#58a6ff');
    
    traces.push({x: maxCurve.q, y: maxCurve.eta, name: 'Eff (Max)', type: 'scatter', mode: 'lines', line: {color: '#3fb950', width: 2.5}, yaxis: 'y3', showlegend: false});
    addLabel(annotations, maxCurve.q, maxCurve.eta, 'y3', 'Max', '#3fb950');
    
    traces.push({x: maxCurve.q, y: maxCurve.power, name: 'Power (Max)', type: 'scatter', mode: 'lines', line: {color: '#f0c040', width: 2.5}, yaxis: 'y2', showlegend: false});
    addLabel(annotations, maxCurve.q, maxCurve.power, 'y2', 'Max', '#f0c040');
    
    if (maxCurve.npsh) {
      traces.push({x: maxCurve.q, y: maxCurve.npsh, name: 'NPSHr (Max)', type: 'scatter', mode: 'lines', line: {color: '#bc8cff', width: 2.5}, yaxis: 'y', showlegend: false});
      addLabel(annotations, maxCurve.q, maxCurve.npsh, 'y', 'Max', '#bc8cff');
    }
  }

  // Add Rated Curves
  if (cfg.TRIM_RATIO < 1.0) {
    let lbl = cfg.IS_VSD ? `Rated (${cfg.RATED_SPEED} RPM)` : `Rated (Ø ${cfg.RATED_TRIM} mm)`;

    traces.push({x: qDutyCurve, y: hDutyCurve, name: `Head ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#f85149', width: 2.5, dash: 'dash'}, yaxis: 'y4', showlegend: false});
    addLabel(annotations, qDutyCurve, hDutyCurve, 'y4', lbl, '#f85149', true);

    traces.push({x: qDutyCurve, y: maxCurve.eta, name: `Eff ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#f85149', width: 2.5, dash: 'dash'}, yaxis: 'y3', showlegend: false});
    addLabel(annotations, qDutyCurve, maxCurve.eta, 'y3', lbl, '#f85149', true);
    
    traces.push({x: qDutyCurve, y: pDutyCurve, name: `Power ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#f85149', width: 2.5, dash: 'dash'}, yaxis: 'y2', showlegend: false});
    addLabel(annotations, qDutyCurve, pDutyCurve, 'y2', lbl, '#f85149', true);
    
    if (maxCurve.npsh && maxCurve.npsh.length) {
      traces.push({x: qDutyCurve, y: npshDutyCurve, name: `NPSHr ${lbl}`, type: 'scatter', mode: 'lines', line: {color: '#f85149', width: 2.5, dash: 'dash'}, yaxis: 'y', showlegend: false});
      addLabel(annotations, qDutyCurve, npshDutyCurve, 'y', lbl, '#f85149', true);
    }
  }

  // System Curve
  if (cfg.Q_DUTY && cfg.H_DUTY) {
    const k = cfg.H_DUTY / Math.pow(cfg.Q_DUTY, 2);
    const sysH = maxCurve.q.map(q => k * Math.pow(q, 2));
    traces.push({x: maxCurve.q, y: sysH, name: 'System Curve', type: 'scatter', mode: 'lines', line: {color: '#8b949e', width: 2.5, dash: 'dot'}, yaxis: 'y4', showlegend: false});
  }

  // Custom Clean Legend Items
  traces.push({x: [null], y: [null], name: 'Head', type: 'scatter', mode: 'lines', line: {color: '#58a6ff', width: 2.5}, showlegend: true});
  traces.push({x: [null], y: [null], name: 'Efficiency', type: 'scatter', mode: 'lines', line: {color: '#3fb950', width: 2.5}, showlegend: true});
  traces.push({x: [null], y: [null], name: 'Power', type: 'scatter', mode: 'lines', line: {color: '#f0c040', width: 2.5}, showlegend: true});
  traces.push({x: [null], y: [null], name: 'NPSHr', type: 'scatter', mode: 'lines', line: {color: '#bc8cff', width: 2.5}, showlegend: true});
  traces.push({x: [null], y: [null], name: 'Rated Curve', type: 'scatter', mode: 'lines', line: {color: '#f85149', width: 2.5, dash: 'dash'}, showlegend: true});
  traces.push({x: [null], y: [null], name: 'System Curve', type: 'scatter', mode: 'lines', line: {color: '#8b949e', width: 2.5, dash: 'dot'}, showlegend: true});

  // Duty Point
  if (cfg.Q_DUTY && cfg.H_DUTY) {
    traces.push({
      x: [cfg.Q_DUTY], y: [cfg.H_DUTY], name: 'Duty Point',
      type: 'scatter', mode: 'markers',
      marker: { color: '#f85149', size: 12, symbol: 'star' },
      yaxis: 'y4',
      showlegend: true
    });
    annotations.push({
      x: cfg.Q_DUTY, y: cfg.H_DUTY,
      xref: 'x', yref: 'y4',
      text: 'Duty',
      showarrow: true,
      arrowcolor: '#f85149',
      ax: 20, ay: -20,
      font: {color: '#f85149', size: 11}
    });
  }

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#8b949e', family: 'Inter, sans-serif' },
    margin: { t: 40, r: 80, l: 60, b: 40 },
    hovermode: 'x unified',
    // Shared X axis
    xaxis: { 
      title: 'Flow (m³/h)', 
      gridcolor: '#30363d', zerolinecolor: '#30363d', rangemode: 'tozero'
    },
    // NPSHr (Bottom)
    yaxis: { 
      title: 'NPSHr (m)', domain: [0.0, 0.20],
      titlefont: {color: '#bc8cff'}, tickfont: {color: '#bc8cff'},
      gridcolor: '#30363d', zerolinecolor: '#30363d', rangemode: 'tozero'
    },
    // Power
    yaxis2: {
      title: 'Power (kW)', domain: [0.25, 0.45],
      titlefont: {color: '#f0c040'}, tickfont: {color: '#f0c040'},
      gridcolor: '#30363d', zerolinecolor: '#30363d', rangemode: 'tozero'
    },
    // Efficiency
    yaxis3: {
      title: 'Eff (%)', domain: [0.50, 0.70],
      titlefont: {color: '#3fb950'}, tickfont: {color: '#3fb950'},
      gridcolor: '#30363d', zerolinecolor: '#30363d', rangemode: 'tozero'
    },
    // Head (Top)
    yaxis4: {
      title: 'Head (m)', domain: [0.75, 1.0],
      titlefont: {color: '#58a6ff'}, tickfont: {color: '#58a6ff'},
      gridcolor: '#30363d', zerolinecolor: '#30363d', rangemode: 'tozero'
    },
    legend: { orientation: 'h', y: 1.15, x: 0 },
    height: 900,
    annotations: annotations
  };

  // Need to adjust the container height
  document.getElementById('chartComp').style.height = '900px';
  document.getElementById('singleChartPanel').style.display = 'block';
  Plotly.newPlot('chartComp', traces, layout, {responsive: true});
}

// Load data on page load
document.addEventListener('DOMContentLoaded', fetchPumpData);
