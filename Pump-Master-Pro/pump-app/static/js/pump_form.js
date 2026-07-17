/**
 * pump_form.js — interactive data entry & curve fitting for the pump form.
 *
 * Workflow:
 *   1. Engineer enters Q, H, η, NPSHr values in the data table.
 *   2. Clicks "Fit & Preview" → POST to /papi/fit-curves.
 *   3. Fitted polynomial coefficients populate the hidden inputs.
 *   4. A small 2-panel Plotly chart previews the fitted curves.
 *   5. Standard form submit stores everything.
 */

let lastFitResults = null;

const CONVERSIONS = {
  q: {
    m3h: 1.0,
    ls: 0.2777777777777778,   // 1 m3h = 1/3.6 L/s
    gpm: 4.402917396,         // 1 m3h = 4.402917 gpm
    lmin: 16.6666666667       // 1 m3h = 16.66667 L/min
  },
  h: {
    m: 1.0,
    ft: 3.280839895
  },
  npsh: {
    m: 1.0,
    ft: 3.280839895
  },
  pow: {
    kw: 1.0,
    hp: 1.34102209
  }
};

function convertValue(val, fromUnit, toUnit, type) {
  if (isNaN(val)) return '';
  const factorA = CONVERSIONS[type][fromUnit];
  const factorB = CONVERSIONS[type][toUnit];
  const baseVal = val / factorA;
  const newVal = baseVal * factorB;
  return Number(newVal.toFixed(2));
}

function getUnitLabel(type, unitValue) {
  if (type === 'q') {
    if (unitValue === 'm3h') return 'm³/h';
    if (unitValue === 'ls') return 'L/s';
    if (unitValue === 'gpm') return 'gpm';
    if (unitValue === 'lmin') return 'L/min';
  }
  if (type === 'h' || type === 'npsh') {
    if (unitValue === 'm') return 'm';
    if (unitValue === 'ft') return 'ft';
  }
  if (type === 'pow') {
    if (unitValue === 'kw') return 'kW';
    if (unitValue === 'hp') return 'hp';
  }
  return unitValue;
}

function updatePlaceholders(type, unit) {
  const inputs = document.querySelectorAll(`#perfTable tbody tr .col-${type}`);
  const label = getUnitLabel(type, unit);
  inputs.forEach(input => {
    if (type === 'q') {
      input.placeholder = `Q (${label})`;
    } else if (type === 'h') {
      const td = input.parentElement;
      const index = Array.from(td.parentElement.parentElement.children).indexOf(td.parentElement);
      if (index === 0) input.placeholder = `Shutoff (${label})`;
      else if (index === 2) input.placeholder = `BEP (${label})`;
      else if (index === 5) input.placeholder = `Runout (${label})`;
      else input.placeholder = `H (${label})`;
    } else if (type === 'npsh') {
      input.placeholder = `NPSHr (${label})`;
    } else if (type === 'pow') {
      input.placeholder = `${label} (opt)`;
    }
  });
}

/* ── Auto-calculate Power from Q, H, η ──────────────────────────────────────
 * Formula (SI): P [kW] = ρ·g·Q·H / (η/100 × 3 600 000)
 *   where Q [m³/h], H [m], ρ = 1000 kg/m³, g = 9.81 m/s²
 * Simplified: P_kW = (Q/3600 × H × 9810) / (η/100) / 1000
 *           = Q × H × 9810 / (η × 3600000) × 100
 *           = Q × H × 2.725 / η   (kW)
 */
const WATER_FACTOR = 9810 / 3600000; // ρg / (3600 × 1000)  [kW per (m³/h·m·1)]

function calcPowerKW(q_m3h, h_m, eta_pct) {
  if (isNaN(q_m3h) || isNaN(h_m) || isNaN(eta_pct) || eta_pct <= 0) return null;
  return (q_m3h * h_m * WATER_FACTOR) / (eta_pct / 100);
}

function autoUpdatePowerInRow(row) {
  const unitQ   = document.getElementById('unit-q')?.value   || 'm3h';
  const unitH   = document.getElementById('unit-h')?.value   || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  const qDisp   = parseFloat(row.querySelector('.col-q')?.value);
  const hDisp   = parseFloat(row.querySelector('.col-h')?.value);
  const etaDisp = parseFloat(row.querySelector('.col-eta')?.value);
  const powInput = row.querySelector('.col-pow');
  if (!powInput) return;

  // Convert display values back to SI
  const q_SI = isNaN(qDisp)   ? NaN : qDisp   / CONVERSIONS.q[unitQ];
  const h_SI = isNaN(hDisp)   ? NaN : hDisp   / CONVERSIONS.h[unitH];

  const p_kw = calcPowerKW(q_SI, h_SI, etaDisp);
  if (p_kw !== null) {
    // Convert kW → display unit
    const p_display = p_kw * CONVERSIONS.pow[unitPow];
    powInput.value = p_display.toFixed(2);
    powInput.classList.add('auto-calc-flash');
    setTimeout(() => powInput.classList.remove('auto-calc-flash'), 600);
  }
}

function initPowerAutoCalc() {
  // Listen on table body using event delegation
  const tbody = document.querySelector('#perfTable tbody');
  if (!tbody) return;
  tbody.addEventListener('input', (e) => {
    const target = e.target;
    if (target.classList.contains('col-eta') ||
        target.classList.contains('col-q')   ||
        target.classList.contains('col-h')) {
      const row = target.closest('tr');
      if (row) autoUpdatePowerInRow(row);
    }
  });
  // Also trigger when unit changes cause value rewrite (via MutationObserver on value isn't needed;
  // the unit-select change handler will call recalcAllPowerRows)
}

function recalcAllPowerRows() {
  document.querySelectorAll('#perfTable tbody tr').forEach(row => autoUpdatePowerInRow(row));
}

/* ── Operating Region unit selector ─────────────────────────────────────── */
function initOpRegionUnits() {
  const sel = document.getElementById('unit-op-q');
  if (!sel) return;
  sel.setAttribute('data-prev', sel.value);

  // Label config: el = input element, lbl = <label> element
  const LABELS = [
    { el: document.querySelector('[name="q_min"]'), lbl: document.getElementById('lbl-q-min'), name: 'Q<sub>min</sub>' },
    { el: document.querySelector('[name="q_max"]'), lbl: document.getElementById('lbl-q-max'), name: 'Q<sub>max</sub>', required: true },
    { el: document.querySelector('[name="q_bep"]'), lbl: document.getElementById('lbl-q-bep'), name: 'Q<sub>bep</sub>' },
  ];

  function updateOpLabels(unitVal) {
    const unitStr = getUnitLabel('q', unitVal);
    LABELS.forEach(item => {
      if (item.lbl) {
        item.lbl.innerHTML = `${item.name} (${unitStr})${item.required ? ' <span class="text-danger">*</span>' : ''}`;
      }
    });
  }

  sel.addEventListener('change', (e) => {
    const fromUnit = e.target.getAttribute('data-prev');
    const toUnit   = e.target.value;
    if (fromUnit === toUnit) return;

    LABELS.forEach(item => {
      if (!item.el) return;
      const val = parseFloat(item.el.value);
      if (!isNaN(val)) {
        item.el.value = convertValue(val, fromUnit, toUnit, 'q');
      }
    });

    updateOpLabels(toUnit);
    e.target.setAttribute('data-prev', toUnit);
  });

  // Set initial labels
  updateOpLabels(sel.value);
}

function initUnitSelectors() {
  document.querySelectorAll('.unit-select').forEach(select => {
    select.setAttribute('data-prev', select.value);
    select.addEventListener('change', (e) => {
      const type = e.target.id.replace('unit-', '');
      const fromUnit = e.target.getAttribute('data-prev');
      const toUnit = e.target.value;
      if (fromUnit === toUnit) return;
      
      const inputs = document.querySelectorAll(`#perfTable tbody tr .col-${type}`);
      inputs.forEach(input => {
        const val = parseFloat(input.value);
        if (!isNaN(val)) {
          input.value = convertValue(val, fromUnit, toUnit, type);
        }
      });
      
      updatePlaceholders(type, toUnit);
      e.target.setAttribute('data-prev', toUnit);

      // After unit change, recalculate power with new units
      if (type === 'q' || type === 'h' || type === 'pow') {
        recalcAllPowerRows();
      }
      
      const previewEl = document.getElementById('curvePreview');
      if (previewEl && previewEl.style.display !== 'none' && lastFitResults) {
        const { q_h: q_h_raw, q_eta: q_eta_raw } = getTableData('perfTable', false);
        buildPreviewCharts(lastFitResults, q_h_raw, q_eta_raw);
      }
    });
  });

  initOpRegionUnits();
  initPowerAutoCalc();
}

/* ── Plotly minimal dark theme ─────────────────────────────────────────────── */
const FORM_LAYOUT = {
  paper_bgcolor: '#1a1d23',
  plot_bgcolor:  '#1a1d23',
  font: { color: '#c9d1d9', size: 11 },
  margin: { l: 44, r: 10, t: 28, b: 36 },
  xaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d', title: { font: { size: 11 } } },
  yaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d', title: { font: { size: 11 } } },
};

/* ── Row management ─────────────────────────────────────────────────────────── */
function addRow(tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  const row = document.createElement('tr');
  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';
  row.innerHTML = `
    <td><input type="number" class="form-control form-control-sm form-control-dark col-q" step="any" placeholder="Q (${getUnitLabel('q', unitQ)})"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-h" step="any" placeholder="H (${getUnitLabel('h', unitH)})"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-eta" step="any" min="0" max="100" placeholder="η %"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-npsh" step="any" placeholder="NPSHr (${getUnitLabel('npsh', unitNpsh)})"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-pow" step="any" placeholder="${getUnitLabel('pow', unitPow)} (opt)"></td>
    <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeRow(this)">×</button></td>`;
  tbody.appendChild(row);
}

function removeRow(btn) {
  const row = btn.closest('tr');
  const tbody = row.parentElement;
  if (tbody.rows.length > 1) row.remove();
}

/* ── Extract table data ─────────────────────────────────────────────────────── */
function getTableData(tableId, toSIUnits = false) {
  const rows = document.querySelectorAll(`#${tableId} tbody tr`);
  const q_h = [], q_eta = [], q_npsh = [], q_p = [];
  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  rows.forEach(row => {
    let q    = parseFloat(row.querySelector('.col-q')?.value);
    let h    = parseFloat(row.querySelector('.col-h')?.value);
    let eta  = parseFloat(row.querySelector('.col-eta')?.value);
    let npsh = parseFloat(row.querySelector('.col-npsh')?.value);
    let pow  = parseFloat(row.querySelector('.col-pow')?.value);

    if (toSIUnits) {
      if (!isNaN(q)) q = q / CONVERSIONS.q[unitQ];
      if (!isNaN(h)) h = h / CONVERSIONS.h[unitH];
      if (!isNaN(npsh)) npsh = npsh / CONVERSIONS.npsh[unitNpsh];
      if (!isNaN(pow)) pow = pow / CONVERSIONS.pow[unitPow];
    }

    if (!isNaN(q) && !isNaN(h))   q_h.push([q, h]);
    if (!isNaN(q) && !isNaN(eta)) q_eta.push([q, eta]);
    if (!isNaN(q) && !isNaN(npsh)) q_npsh.push([q, npsh]);
    if (!isNaN(q) && !isNaN(pow)) q_p.push([q, pow]);
  });
  return { q_h, q_eta, q_npsh: q_npsh.length >= 2 ? q_npsh : null, q_p: q_p.length >= 3 ? q_p : null };
}

/* ── Set field values ───────────────────────────────────────────────────────── */
function setField(name, value) {
  const el = document.querySelector(`[name="${name}"]`);
  if (el) el.value = value;
}

/* ── Fit & Preview ──────────────────────────────────────────────────────────── */
async function fitAndPreview() {
  const btn = document.getElementById('fitBtn');
  const statusEl = document.getElementById('fitStatus');
  const previewEl = document.getElementById('curvePreview');

  const { q_h, q_eta, q_npsh, q_p } = getTableData('perfTable', true);

  if (q_h.length < 3) {
    showStatus('error', 'Need at least 3 flow-head (Q, H) data points.');
    return;
  }
  if (q_eta.length < 3) {
    showStatus('error', 'Need at least 3 flow-efficiency (Q, η) data points.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Fitting…';
  showStatus('', '');

  try {
    const res = await fetch('/papi/fit-curves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q_h, q_eta, q_npsh, q_p }),
    });
    const d = await res.json();

    if (!d.ok) {
      showStatus('error', d.error || 'Fit failed.');
      return;
    }

    lastFitResults = d;

    // Populate hidden coefficient fields
    ['hq_a0','hq_a1','hq_a2','hq_a3',
     'eff_b0','eff_b1','eff_b2','eff_b3',
     'npsh_c0','npsh_c1','npsh_c2',
     'pow_p0','pow_p1','pow_p2'].forEach(k => setField(k, d[k] ?? 0));

    // Populate derived operating range
    if (d.q_max) setField('q_max', d.q_max);
    if (d.q_bep) setField('q_bep', d.q_bep);

    const unitQ = document.getElementById('unit-q')?.value || 'm3h';
    const unitH = document.getElementById('unit-h')?.value || 'm';

    const displayHShutoff = (d.h_shutoff * CONVERSIONS.h[unitH]).toFixed(1);
    const displayQMax = (d.q_max * CONVERSIONS.q[unitQ]).toFixed(1);
    const displayQBep = (d.q_bep * CONVERSIONS.q[unitQ]).toFixed(1);

    showStatus('ok',
      `Fitted: H₀=${displayHShutoff} ${getUnitLabel('h', unitH)}  Q_max=${displayQMax} ${getUnitLabel('q', unitQ)}  Q_BEP=${displayQBep} ${getUnitLabel('q', unitQ)}  η_BEP=${d.eta_bep}% ` +
      ` | R² H-Q=${d.r2_hq}  R² η=${d.r2_eta}`);

    // Build preview charts
    previewEl.style.display = 'block';

    const { q_h: q_h_raw, q_eta: q_eta_raw } = getTableData('perfTable', false);
    buildPreviewCharts(d, q_h_raw, q_eta_raw);

    // Refresh coefficient display
    refreshCoeffDisplay(d);

  } catch (e) {
    showStatus('error', 'Network error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-calculator me-1"></i>Fit & Preview';
  }
}

function showStatus(type, msg) {
  const el = document.getElementById('fitStatus');
  el.className = 'mt-2 small ' + (type === 'error' ? 'text-danger' : type === 'ok' ? 'text-success' : '');
  el.textContent = msg;
}

function buildPreviewCharts(d, q_h_raw, q_eta_raw) {
  const q_max = d.q_max;
  const q_arr = Array.from({ length: 80 }, (_, i) => (i / 79) * q_max);

  const a = [d.hq_a0, d.hq_a1, d.hq_a2, d.hq_a3];
  const b = [d.eff_b0, d.eff_b1, d.eff_b2, d.eff_b3];
  const pp = [d.pow_p0, d.pow_p1, d.pow_p2];

  const evalP = (coeffs, q) => coeffs.reduce((s, c, i) => s + c * Math.pow(q, i), 0);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  const H   = q_arr.map(q => clamp(evalP(a, q), 0, Infinity));
  const eta = q_arr.map(q => clamp(evalP(b, q), 0, 100));
  const pow = q_arr.map(q => clamp(evalP(pp, q), 0, Infinity));

  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  const labelQ = getUnitLabel('q', unitQ);
  const labelH = getUnitLabel('h', unitH);
  const labelPow = getUnitLabel('pow', unitPow);

  const q_arr_selected = q_arr.map(q => q * CONVERSIONS.q[unitQ]);
  const H_selected     = H.map(h => h * CONVERSIONS.h[unitH]);
  const pow_selected   = pow.map(p => p * CONVERSIONS.pow[unitPow]);

  // H-Q chart
  Plotly.react('previewHQ', [
    { x: q_h_raw.map(r=>r[0]), y: q_h_raw.map(r=>r[1]), mode:'markers', name:'Data', marker:{color:'#f0883e',size:7} },
    { x: q_arr_selected, y: H_selected, mode:'lines', name:'Fitted', line:{color:'#58a6ff',width:2} },
  ], { 
    ...FORM_LAYOUT, 
    title:{text:'H-Q',font:{size:12}}, 
    xaxis:{...FORM_LAYOUT.xaxis,title:`Q (${labelQ})`}, 
    yaxis:{...FORM_LAYOUT.yaxis,title:`Head (${labelH})`} 
  }, { responsive: true });

  // Efficiency + Power chart
  Plotly.react('previewEta', [
    { x: q_eta_raw.map(r=>r[0]), y: q_eta_raw.map(r=>r[1]), mode:'markers', name:'η Data', marker:{color:'#f0883e',size:7}, yaxis:'y' },
    { x: q_arr_selected, y: eta, mode:'lines', name:'η Fitted (%)', line:{color:'#3fb950',width:2}, yaxis:'y' },
    { x: q_arr_selected, y: pow_selected, mode:'lines', name:`Power (${labelPow})`, line:{color:'#d29922',width:2,dash:'dot'}, yaxis:'y2' },
  ], {
    ...FORM_LAYOUT,
    title:{text:'Efficiency & Power',font:{size:12}},
    xaxis:{...FORM_LAYOUT.xaxis,title:`Q (${labelQ})`},
    yaxis:{...FORM_LAYOUT.yaxis,title:'Efficiency (%)'},
    yaxis2:{...FORM_LAYOUT.yaxis,title:`Power (${labelPow})`,overlaying:'y',side:'right',showgrid:false},
    legend:{x:0.02,y:0.98,bgcolor:'rgba(0,0,0,0)'},
  }, { responsive: true });
}

function refreshCoeffDisplay(d) {
  const fields = ['hq_a0','hq_a1','hq_a2','hq_a3',
                  'eff_b0','eff_b1','eff_b2','eff_b3',
                  'npsh_c0','npsh_c1','npsh_c2',
                  'pow_p0','pow_p1','pow_p2'];
  fields.forEach(k => {
    const el = document.getElementById('disp_' + k);
    if (el) el.textContent = (d[k] !== undefined ? Number(d[k]).toPrecision(5) : '—');
  });
}

/* ── Initialise table from existing pump data (edit mode) ───────────────────── */
function initTableFromCurves(pumpData) {
  if (!pumpData) return;
  const qMax = pumpData.q_max || 100;
  const qBep = pumpData.q_bep || qMax * 0.55;

  // Evaluate polynomials at 6 representative flow points
  const a  = [pumpData.hq_a0, pumpData.hq_a1, pumpData.hq_a2, pumpData.hq_a3];
  const b  = [pumpData.eff_b0, pumpData.eff_b1, pumpData.eff_b2, pumpData.eff_b3];
  const c  = [pumpData.npsh_c0, pumpData.npsh_c1, pumpData.npsh_c2];
  const pp = [pumpData.pow_p0, pumpData.pow_p1, pumpData.pow_p2];

  const evalP = (coeffs, q) => coeffs.reduce((s, cv, i) => s + cv * Math.pow(q, i), 0);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  const flowPts = [0, qMax*0.25, qBep*0.7, qBep, qMax*0.8, qMax].map(q => Math.round(q * 10) / 10);
  const tbody = document.querySelector('#perfTable tbody');
  tbody.innerHTML = '';

  flowPts.forEach(q => {
    const H    = Math.max(0, evalP(a, q));
    const eta  = clamp(evalP(b, q), 0, 100);
    const npsh = Math.max(0, evalP(c, q));
    const pow  = Math.max(0, evalP(pp, q));
    const row  = document.createElement('tr');
    row.innerHTML = `
      <td><input type="number" class="form-control form-control-sm form-control-dark col-q" step="any" value="${q}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-h" step="any" value="${H > 0 ? H.toFixed(2) : ''}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-eta" step="any" min="0" max="100" value="${eta > 0 ? eta.toFixed(1) : ''}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-npsh" step="any" value="${npsh > 0 ? npsh.toFixed(2) : ''}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-pow" step="any" value="${pow > 0 ? pow.toFixed(2) : ''}"></td>
      <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeRow(this)">×</button></td>`;
    tbody.appendChild(row);
  });
}

/* ── Init blank table for new pump ─────────────────────────────────────────── */
function initBlankTable() {
  const tbody = document.querySelector('#perfTable tbody');
  tbody.innerHTML = '';
  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  const labelQ = getUnitLabel('q', unitQ);
  const labelH = getUnitLabel('h', unitH);
  const labelNpsh = getUnitLabel('npsh', unitNpsh);
  const labelPow = getUnitLabel('pow', unitPow);

  const suggestions = [
    { q: 0,    hNote: `Shutoff (${labelH})`, etaNote: '' },
    { q: '',   hNote: `H (${labelH})`, etaNote: '25% load' },
    { q: '',   hNote: `BEP (${labelH})`, etaNote: 'BEP (peak η)' },
    { q: '',   hNote: `H (${labelH})`, etaNote: '' },
    { q: '',   hNote: `H (${labelH})`, etaNote: '' },
    { q: '',   hNote: `Runout (${labelH})`, etaNote: '' },
  ];
  suggestions.forEach(s => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><input type="number" class="form-control form-control-sm form-control-dark col-q" step="any" value="${s.q}" placeholder="Q (${labelQ})"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-h" step="any" placeholder="${s.hNote}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-eta" step="any" min="0" max="100" placeholder="${s.etaNote || 'η %'}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-npsh" step="any" placeholder="NPSHr (${labelNpsh})"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-pow" step="any" placeholder="${labelPow} (opt)"></td>
      <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeRow(this)">×</button></td>`;
    tbody.appendChild(row);
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   EXTRA CURVES MODULE
   Each additional curve is a self-contained mini performance table with
   its own Fit & Preview, label, color, and power auto-calc.
   All fitted curves are serialised to JSON in a hidden form field on submit.
   ══════════════════════════════════════════════════════════════════════════ */

const EXTRA_CURVE_COLORS = [
  '#58a6ff','#3fb950','#f0c040','#f85149','#bc8cff','#39d3c0','#ff9900','#e879f9'
];

let _extraCurveIdCounter = 0;
let extraCurves = [];   // [{id, label, color, fitted, coeffs}]

/* ── Serialise all extra curves to the hidden form field ─────────────────── */
function serializeExtraCurves() {
  const payload = extraCurves
    .filter(c => c.fitted && c.coeffs)
    .map(c => ({ label: c.label, color: c.color, ...c.coeffs }));
  const field = document.getElementById('extra_curves_json_field');
  if (field) field.value = JSON.stringify(payload);
}

/* ── Update badge count ──────────────────────────────────────────────────── */
function updateExtraBadge() {
  const badge = document.getElementById('extraCurveBadge');
  if (!badge) return;
  const n = extraCurves.length;
  badge.textContent = n;
  badge.style.display = n > 0 ? '' : 'none';
}

/* ── Extract data from an extra curve table ──────────────────────────────── */
function getExtraTableData(tableId) {
  const rows = document.querySelectorAll(`#${tableId} tbody tr`);
  const q_h = [], q_eta = [], q_p = [];
  rows.forEach(row => {
    const q   = parseFloat(row.querySelector('.col-q')?.value);
    const h   = parseFloat(row.querySelector('.col-h')?.value);
    const eta = parseFloat(row.querySelector('.col-eta')?.value);
    const pow = parseFloat(row.querySelector('.col-pow')?.value);
    if (!isNaN(q) && !isNaN(h)) q_h.push([q, h]);
    if (!isNaN(q) && !isNaN(eta)) q_eta.push([q, eta]);
    if (!isNaN(q) && !isNaN(pow)) q_p.push([q, pow]);
  });
  return {
    q_h,
    q_eta: q_eta.length >= 3 ? q_eta : null,
    q_p:   q_p.length  >= 3 ? q_p   : null,
  };
}

/* ── Build an HTML table row for an extra curve table ────────────────────── */
function _extraRow() {
  return `<tr>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-q" step="any" placeholder="Q"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-h" step="any" placeholder="H"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-eta" step="any" min="0" max="100" placeholder="η %"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-npsh" step="any" placeholder="NPSHr"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-pow" step="any" placeholder="kW (opt)"></td>
    <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeRow(this)">×</button></td>
  </tr>`;
}

/* ── Wire power auto-calc on a single row ────────────────────────────────── */
function _wireExtraRow(row) {
  ['col-q','col-h','col-eta'].forEach(cls => {
    const inp = row.querySelector(`.${cls}`);
    if (inp) inp.addEventListener('input', () => autoUpdatePowerInRow(row));
  });
}

/* ── Fit an extra curve via /papi/fit-curves ─────────────────────────────── */
async function fitExtraCurve(curveId) {
  const curve  = extraCurves.find(c => c.id === curveId);
  if (!curve) return;
  const entry    = document.getElementById(`extra-entry-${curveId}`);
  const statusEl = entry.querySelector('.extra-curve-status');
  const fitBtn   = entry.querySelector('.btn-extra-fit');
  const { q_h, q_eta, q_p } = getExtraTableData(`extraTable-${curveId}`);

  if (q_h.length < 3) {
    statusEl.className = 'extra-curve-status error';
    statusEl.textContent = '\u2717 Need at least 3 Q, H points';
    return;
  }

  statusEl.className = 'extra-curve-status busy';
  statusEl.textContent = '\u27f3 Fitting\u2026';
  fitBtn.disabled = true;

  const payload = {
    q_h,
    q_eta: q_eta || q_h.map(([q]) => [q, 70]),
    q_npsh: null,
    q_p: q_p || null,
  };

  try {
    const res = await fetch('/papi/fit-curves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await res.json();
    if (!d.ok) {
      statusEl.className = 'extra-curve-status error';
      statusEl.textContent = `\u2717 ${d.error || 'Fit failed'}`;
      return;
    }

    curve.fitted = true;
    curve.coeffs = {
      hq_a0: d.hq_a0, hq_a1: d.hq_a1, hq_a2: d.hq_a2, hq_a3: d.hq_a3,
      eff_b0: d.eff_b0, eff_b1: d.eff_b1, eff_b2: d.eff_b2, eff_b3: d.eff_b3,
      npsh_c0: d.npsh_c0, npsh_c1: d.npsh_c1, npsh_c2: d.npsh_c2,
      pow_p0: d.pow_p0, pow_p1: d.pow_p1, pow_p2: d.pow_p2,
      q_max: d.q_max, q_bep: d.q_bep,
    };

    statusEl.className = 'extra-curve-status ok';
    statusEl.textContent =
      `\u2713 Fitted \u2014 H\u2080=${d.hq_a0.toFixed(1)} m, Q_max=${d.q_max.toFixed(1)}, \u03b7_BEP=${d.eta_bep}%, R\u00b2=${d.r2_hq}`;

    _drawExtraPreview(curveId, d, curve.color);
    serializeExtraCurves();

  } catch(e) {
    statusEl.className = 'extra-curve-status error';
    statusEl.textContent = `\u2717 Network error: ${e.message}`;
  } finally {
    fitBtn.disabled = false;
  }
}

/* ── Draw compact Plotly preview inside an extra curve card ──────────────── */
function _drawExtraPreview(curveId, d, color) {
  const previewEl = document.getElementById(`extra-preview-${curveId}`);
  if (!previewEl) return;
  previewEl.style.display = '';

  const qMax = d.q_max;
  const qArr = Array.from({ length: 60 }, (_, i) => (i / 59) * qMax);
  const evalP = (coeffs, q) => coeffs.reduce((s, c, i) => s + c * Math.pow(q, i), 0);
  const a = [d.hq_a0, d.hq_a1, d.hq_a2, d.hq_a3];
  const b = [d.eff_b0, d.eff_b1, d.eff_b2, d.eff_b3];
  const H   = qArr.map(q => Math.max(0, evalP(a, q)));
  const eta = qArr.map(q => Math.max(0, Math.min(100, evalP(b, q))));

  const base = {
    paper_bgcolor: '#1a1d23', plot_bgcolor: '#1a1d23',
    font: { color: '#c9d1d9', size: 10 },
    margin: { l: 40, r: 8, t: 22, b: 32 },
    xaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d', title: 'Q (m\u00b3/h)' },
    yaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d' },
    showlegend: false,
  };

  Plotly.react(`extra-previewHQ-${curveId}`, [
    { x: qArr, y: H, mode: 'lines', line: { color, width: 2 } },
  ], { ...base, title: { text: 'H-Q', font: { size: 11 } },
       yaxis: { ...base.yaxis, title: 'H (m)' } }, { responsive: true });

  Plotly.react(`extra-previewEta-${curveId}`, [
    { x: qArr, y: eta, mode: 'lines', line: { color: '#f0c040', width: 2 } },
  ], { ...base, title: { text: '\u03b7', font: { size: 11 } },
       yaxis: { ...base.yaxis, title: '\u03b7 (%)', range: [0, 100] } }, { responsive: true });
}

/* ── Add a new extra curve card (optionally pre-filled with existingData) ── */
function addExtraCurveCard(existingData) {
  const id    = ++_extraCurveIdCounter;
  const color = existingData?.color || EXTRA_CURVE_COLORS[(id - 1) % EXTRA_CURVE_COLORS.length];
  const label = existingData?.label || `Curve ${id}`;

  extraCurves.push({ id, label, color, fitted: !!existingData, coeffs: existingData || null });

  const list = document.getElementById('extraCurvesList');
  const div  = document.createElement('div');
  div.className = 'custom-curve-entry mb-3';
  div.id = `extra-entry-${id}`;

  const swatches = EXTRA_CURVE_COLORS.map(c =>
    `<span class="curve-color-swatch ${c === color ? 'active' : ''}"
          style="background:${c}" data-color="${c}" data-eid="${id}"></span>`
  ).join('');

  const blankRows = Array.from({ length: 6 }, _extraRow).join('');

  div.innerHTML = `
    <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
      <span class="curve-color-dot"
            style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${color}"></span>
      <input type="text" class="form-control form-control-sm form-control-dark extra-label-input"
             value="${label}" placeholder="Curve label"
             style="max-width:180px;font-weight:600" data-eid="${id}">
      <span class="text-muted small">Color:</span>
      <div class="d-flex gap-1 flex-wrap">${swatches}</div>
      <button type="button" class="btn btn-sm btn-outline-danger ms-auto py-0 px-2 btn-extra-remove"
              data-eid="${id}">&#x2715; Remove</button>
    </div>

    <div class="table-responsive mb-2">
      <table class="table table-sm table-dark mb-0 align-middle" id="extraTable-${id}" style="font-size:0.83rem">
        <thead>
          <tr style="background:#21262d">
            <th style="width:110px">Flow Q<br><span class="fw-normal text-muted small">(m\u00b3/h)</span></th>
            <th style="width:95px">Head H<br><span class="fw-normal text-muted small">(m)</span></th>
            <th style="width:80px">Effic. \u03b7<br><span class="fw-normal text-muted small">(%)</span></th>
            <th style="width:100px">NPSHr<br><span class="fw-normal text-muted small">(m, opt.)</span></th>
            <th style="width:105px">Power<br><span class="fw-normal text-muted small">(kW, opt.)</span></th>
            <th style="width:30px"></th>
          </tr>
        </thead>
        <tbody>${blankRows}</tbody>
      </table>
    </div>

    <div class="d-flex gap-2 align-items-center mb-2">
      <button type="button" class="btn btn-sm btn-outline-secondary btn-extra-add-row" data-eid="${id}">
        <i class="bi bi-plus-lg me-1"></i>Add Row
      </button>
      <button type="button" class="btn btn-sm btn-primary ms-auto btn-extra-fit" data-eid="${id}">
        <i class="bi bi-calculator me-1"></i>Fit &amp; Preview
      </button>
    </div>

    <div class="extra-curve-status mb-2" id="extra-status-${id}"></div>

    <div id="extra-preview-${id}" style="display:none">
      <div class="row g-2">
        <div class="col-6"><div id="extra-previewHQ-${id}" style="height:160px"></div></div>
        <div class="col-6"><div id="extra-previewEta-${id}" style="height:160px"></div></div>
      </div>
    </div>`;

  list.appendChild(div);

  // If pre-loading saved data, show status + preview
  if (existingData) {
    const statusEl = div.querySelector('.extra-curve-status');
    statusEl.className = 'extra-curve-status ok';
    statusEl.textContent = `\u2713 Saved \u2014 Q_max=${existingData.q_max?.toFixed(1) ?? '?'}`;
    _drawExtraPreview(id, {
      hq_a0: existingData.hq_a0, hq_a1: existingData.hq_a1,
      hq_a2: existingData.hq_a2, hq_a3: existingData.hq_a3,
      eff_b0: existingData.eff_b0, eff_b1: existingData.eff_b1,
      eff_b2: existingData.eff_b2, eff_b3: existingData.eff_b3,
      q_max: existingData.q_max, eta_bep: 0, r2_hq: 0,
    }, color);
  }

  // Events: color swatches
  div.querySelectorAll('.curve-color-swatch').forEach(swatch => {
    swatch.addEventListener('click', () => {
      const eid = parseInt(swatch.dataset.eid);
      const newColor = swatch.dataset.color;
      const curve = extraCurves.find(c => c.id === eid);
      if (!curve) return;
      curve.color = newColor;
      div.querySelectorAll('.curve-color-swatch').forEach(s => s.classList.remove('active'));
      swatch.classList.add('active');
      div.querySelector('.curve-color-dot').style.background = newColor;
      serializeExtraCurves();
    });
  });

  // Events: label
  div.querySelector('.extra-label-input').addEventListener('input', e => {
    const curve = extraCurves.find(c => c.id === parseInt(e.target.dataset.eid));
    if (curve) { curve.label = e.target.value || `Curve ${curve.id}`; serializeExtraCurves(); }
  });

  // Events: add row
  div.querySelector('.btn-extra-add-row').addEventListener('click', e => {
    const eid = parseInt(e.currentTarget.dataset.eid);
    const tbody = document.querySelector(`#extraTable-${eid} tbody`);
    const row = document.createElement('tr');
    row.innerHTML = _extraRow();
    tbody.appendChild(row);
    _wireExtraRow(row);
  });

  // Events: fit
  div.querySelector('.btn-extra-fit').addEventListener('click', e => {
    fitExtraCurve(parseInt(e.currentTarget.dataset.eid));
  });

  // Events: remove
  div.querySelector('.btn-extra-remove').addEventListener('click', e => {
    const eid = parseInt(e.currentTarget.dataset.eid);
    extraCurves = extraCurves.filter(c => c.id !== eid);
    document.getElementById(`extra-entry-${eid}`)?.remove();
    updateExtraBadge();
    serializeExtraCurves();
  });

  // Power auto-calc for all initial rows
  div.querySelectorAll(`#extraTable-${id} tbody tr`).forEach(_wireExtraRow);

  updateExtraBadge();

  // Auto-open the collapse panel
  const body = document.getElementById('extraCurvesBody');
  if (body && !body.classList.contains('show')) {
    new bootstrap.Collapse(body, { toggle: true });
  }
}

/* ── Entry point: initialise extra curves (called from inline script) ─────── */
function initExtraCurves(curvesArray) {
  extraCurves = [];
  _extraCurveIdCounter = 0;

  // Wire the Add Curve Table button
  const addBtn = document.getElementById('btnAddExtraCurve');
  if (addBtn) addBtn.addEventListener('click', () => addExtraCurveCard());

  // Wire form submit to serialise before POST
  const form = document.getElementById('pumpForm');
  if (form) form.addEventListener('submit', serializeExtraCurves);

  // Load existing saved curves (edit mode)
  const data = Array.isArray(curvesArray) ? curvesArray :
               (typeof curvesArray === 'string' ? JSON.parse(curvesArray || '[]') : []);
  data.forEach(c => addExtraCurveCard(c));
}
