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
  row.innerHTML = `
    <td><input type="number" class="form-control form-control-sm form-control-dark col-q" step="any" placeholder="0"></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-h" step="any" placeholder=""></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-eta" step="any" min="0" max="100" placeholder=""></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-npsh" step="any" placeholder=""></td>
    <td><input type="number" class="form-control form-control-sm form-control-dark col-pow" step="any" placeholder=""></td>
    <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeRow(this)">×</button></td>`;
  tbody.appendChild(row);
}

function removeRow(btn) {
  const row = btn.closest('tr');
  const tbody = row.parentElement;
  if (tbody.rows.length > 1) row.remove();
}

/* ── Extract table data ─────────────────────────────────────────────────────── */
function getTableData(tableId) {
  const rows = document.querySelectorAll(`#${tableId} tbody tr`);
  const q_h = [], q_eta = [], q_npsh = [], q_p = [];
  rows.forEach(row => {
    const q    = parseFloat(row.querySelector('.col-q')?.value);
    const h    = parseFloat(row.querySelector('.col-h')?.value);
    const eta  = parseFloat(row.querySelector('.col-eta')?.value);
    const npsh = parseFloat(row.querySelector('.col-npsh')?.value);
    const pow  = parseFloat(row.querySelector('.col-pow')?.value);
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

  const { q_h, q_eta, q_npsh, q_p } = getTableData('perfTable');

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

    // Populate hidden coefficient fields
    ['hq_a0','hq_a1','hq_a2','hq_a3',
     'eff_b0','eff_b1','eff_b2','eff_b3',
     'npsh_c0','npsh_c1','npsh_c2',
     'pow_p0','pow_p1','pow_p2'].forEach(k => setField(k, d[k] ?? 0));

    // Populate derived operating range
    if (d.q_max) setField('q_max', d.q_max);
    if (d.q_bep) setField('q_bep', d.q_bep);

    showStatus('ok',
      `Fitted: H₀=${d.h_shutoff} m  Q_max=${d.q_max} m³/h  Q_BEP=${d.q_bep} m³/h  η_BEP=${d.eta_bep}% ` +
      ` | R² H-Q=${d.r2_hq}  R² η=${d.r2_eta}`);

    // Build preview charts
    previewEl.style.display = 'block';
    buildPreviewCharts(d, q_h, q_eta);

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

  // H-Q chart
  Plotly.react('previewHQ', [
    { x: q_h_raw.map(r=>r[0]), y: q_h_raw.map(r=>r[1]), mode:'markers', name:'Data', marker:{color:'#f0883e',size:7} },
    { x: q_arr, y: H, mode:'lines', name:'Fitted', line:{color:'#58a6ff',width:2} },
  ], { ...FORM_LAYOUT, title:{text:'H-Q',font:{size:12}}, xaxis:{...FORM_LAYOUT.xaxis,title:'Q (m³/h)'}, yaxis:{...FORM_LAYOUT.yaxis,title:'Head (m)'} }, { responsive: true });

  // Efficiency + Power chart
  Plotly.react('previewEta', [
    { x: q_eta_raw.map(r=>r[0]), y: q_eta_raw.map(r=>r[1]), mode:'markers', name:'η Data', marker:{color:'#f0883e',size:7}, yaxis:'y' },
    { x: q_arr, y: eta, mode:'lines', name:'η Fitted (%)', line:{color:'#3fb950',width:2}, yaxis:'y' },
    { x: q_arr, y: pow, mode:'lines', name:'Power (kW)', line:{color:'#d29922',width:2,dash:'dot'}, yaxis:'y2' },
  ], {
    ...FORM_LAYOUT,
    title:{text:'Efficiency & Power',font:{size:12}},
    xaxis:{...FORM_LAYOUT.xaxis,title:'Q (m³/h)'},
    yaxis:{...FORM_LAYOUT.yaxis,title:'Efficiency (%)'},
    yaxis2:{...FORM_LAYOUT.yaxis,title:'Power (kW)',overlaying:'y',side:'right',showgrid:false},
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
  const suggestions = [
    { q: 0,    hNote: 'Shutoff head', etaNote: '' },
    { q: '',   hNote: '', etaNote: '25% load' },
    { q: '',   hNote: 'BEP', etaNote: 'BEP (peak η)' },
    { q: '',   hNote: '', etaNote: '' },
    { q: '',   hNote: '', etaNote: '' },
    { q: '',   hNote: 'Runout (H≈0)', etaNote: '' },
  ];
  suggestions.forEach(s => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><input type="number" class="form-control form-control-sm form-control-dark col-q" step="any" value="${s.q}" placeholder="Q"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-h" step="any" placeholder="${s.hNote || 'H (m)'}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-eta" step="any" min="0" max="100" placeholder="${s.etaNote || 'η %'}"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-npsh" step="any" placeholder="NPSHr (m)"></td>
      <td><input type="number" class="form-control form-control-sm form-control-dark col-pow" step="any" placeholder="kW (opt)"></td>
      <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeRow(this)">×</button></td>`;
    tbody.appendChild(row);
  });
}
