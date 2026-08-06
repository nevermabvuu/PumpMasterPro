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

var lastFitResults = null;
var TABLE_INPUT_CLS = 'w-full bg-[#0d1117] border border-[#30363d] rounded-md px-2.5 py-1 text-xs text-[#e6edf3] font-mono tracking-tight shadow-inner focus:border-[#58a6ff] focus:ring-1 focus:ring-[#58a6ff]/40 transition-all focus:outline-none';

/**
 * Beginner Note: Smooth horizontal slide view transitions for Card 1.
 * Standard Details slides totally out to the left (-50% translateX) as Extended Setup slides in from the right.
 */
function slideToExtendedSetup() {
  const slider = document.getElementById('pumpDetailsSlider');
  const btnExt = document.getElementById('btnSlideExtended');
  const btnStd = document.getElementById('btnSlideStandard');
  const title = document.getElementById('pumpDetailsHeaderTitle');
  const extPane = document.getElementById('extendedSetupPane');
  if (!slider) return;

  if (extPane) extPane.style.display = 'block';
  setTimeout(() => {
    slider.style.transform = 'translateX(-50%)';
    if (btnExt) btnExt.classList.add('hidden');
    if (btnStd) btnStd.classList.remove('hidden');
    if (title) title.textContent = 'Extended Setup & Selection Specs';
  }, 10);
}

function slideToStandardDetails() {
  const slider = document.getElementById('pumpDetailsSlider');
  const btnExt = document.getElementById('btnSlideExtended');
  const btnStd = document.getElementById('btnSlideStandard');
  const title = document.getElementById('pumpDetailsHeaderTitle');
  const extPane = document.getElementById('extendedSetupPane');
  if (!slider) return;

  slider.style.transform = 'translateX(0%)';
  if (btnStd) btnStd.classList.add('hidden');
  if (btnExt) btnExt.classList.remove('hidden');
  if (title) title.textContent = 'Pump Details';

  setTimeout(() => {
    if (extPane && (slider.style.transform === 'translateX(0%)' || !slider.style.transform)) {
      extPane.style.display = 'none';
    }
  }, 300);
}

var CONVERSIONS = {
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
  },
  dia: {
    mm: 1.0,
    in: 0.03937007874015748,   // 1 mm = 1/25.4 in
    m: 0.001                  // 1 mm = 0.001 m
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
  if (type === 'dia') {
    if (unitValue === 'mm') return 'mm';
    if (unitValue === 'in') return 'in';
    if (unitValue === 'm') return 'm';
  }
  return unitValue;
}

function updatePlaceholders(type, unit, table) {
  const targetTable = table || document.getElementById('perfTable');
  if (!targetTable) return;
  const inputs = targetTable.querySelectorAll(`tbody tr .col-${type}`);
  const label = getUnitLabel(type, unit);
  inputs.forEach(input => {
    if (type === 'q') {
      input.placeholder = `Q (${label})`;
    } else if (type === 'h') {
      const td = input.parentElement;
      const tr = td ? td.parentElement : null;
      const rowIndex = (tr && tr.parentElement) ? Array.from(tr.parentElement.children).indexOf(tr) : -1;
      if (rowIndex === 0) input.placeholder = `Shutoff (${label})`;
      else if (rowIndex === 2) input.placeholder = `BEP Head (${label})`;
      else if (rowIndex === 5) input.placeholder = `Runout (${label})`;
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
var WATER_FACTOR = 9810 / 3600000; // ρg / (3600 × 1000)  [kW per (m³/h·m·1)]
function calcPowerKW(q_m3h, h_m, eta_pct) {
  if (isNaN(q_m3h) || isNaN(h_m) || isNaN(eta_pct) || eta_pct <= 0) return null;
  return (q_m3h * h_m * WATER_FACTOR) / (eta_pct / 100);
}

function autoUpdatePowerInRow(row) {
  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  const qDisp = parseFloat(row.querySelector('.col-q')?.value);
  const hDisp = parseFloat(row.querySelector('.col-h')?.value);
  const etaDisp = parseFloat(row.querySelector('.col-eta')?.value);
  const powInput = row.querySelector('.col-pow');
  if (!powInput) return;

  // Convert display values back to SI
  const q_SI = isNaN(qDisp) ? NaN : qDisp / CONVERSIONS.q[unitQ];
  const h_SI = isNaN(hDisp) ? NaN : hDisp / CONVERSIONS.h[unitH];

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
      target.classList.contains('col-q') ||
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
    const toUnit = e.target.value;
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
    serializeDataUnits();
  });

  // Set initial labels
  updateOpLabels(sel.value);
}

function initUnitSelectors() {
  const selectors = document.querySelectorAll('.unit-select, #unit-q, #unit-h, #unit-npsh, #unit-pow');
  selectors.forEach(select => {
    select.setAttribute('data-prev', select.value);

    // Initial placeholder setting on page load
    const type = select.id ? select.id.replace('unit-', '') : '';
    if (type) {
      updatePlaceholders(type, select.value, document.getElementById('perfTable'));
    }

    select.addEventListener('change', (e) => {
      const type = e.target.id ? e.target.id.replace('unit-', '') : '';
      if (!type) return;
      const fromUnit = e.target.getAttribute('data-prev') || e.target.value;
      const toUnit = e.target.value;
      if (fromUnit === toUnit) return;

      const inputs = document.querySelectorAll(`#perfTable tbody tr .col-${type}`);
      inputs.forEach(input => {
        const val = parseFloat(input.value);
        if (!isNaN(val)) {
          input.value = convertValue(val, fromUnit, toUnit, type);
        }
      });

      updatePlaceholders(type, toUnit, document.getElementById('perfTable'));
      e.target.setAttribute('data-prev', toUnit);

      // After unit change, recalculate power with new units
      if (type === 'q' || type === 'h' || type === 'pow') {
        recalcAllPowerRows();
      }

      // Persist unit change immediately
      serializeDataUnits();
    });
  });

  initOpRegionUnits();
  initPowerAutoCalc();
  initPreviewUnitSelectors();

  // Main Curve style controls
  const mainStyleModeSel = document.getElementById('main_curve_style_mode');
  if (mainStyleModeSel) {
    mainStyleModeSel.addEventListener('change', (e) => {
      const controls = document.getElementById('main_curve_custom_controls');
      if (controls) {
        if (e.target.value === 'custom') {
          controls.classList.remove('hidden');
          controls.classList.add('inline-flex');
        } else {
          controls.classList.remove('inline-flex');
          controls.classList.add('hidden');
        }
      }
      if (typeof serializeGraphOptions === 'function') serializeGraphOptions();
      refreshMainPreview();
    });
  }

  ['main_curve_color', 'main_curve_weight', 'main_curve_line_style'].forEach(elemId => {
    const el = document.getElementById(elemId);
    if (el) {
      el.addEventListener('input', () => {
        if (typeof serializeGraphOptions === 'function') serializeGraphOptions();
        refreshMainPreview();
      });
      el.addEventListener('change', () => {
        if (typeof serializeGraphOptions === 'function') serializeGraphOptions();
        refreshMainPreview();
      });
    }
  });

  const mainDiaUnitSel = document.getElementById('main_curve_dia_unit');
  if (mainDiaUnitSel) {
    mainDiaUnitSel.setAttribute('data-prev', mainDiaUnitSel.value);
    mainDiaUnitSel.addEventListener('change', (e) => {
      const fromUnit = e.target.getAttribute('data-prev');
      const toUnit = e.target.value;
      if (fromUnit === toUnit) return;

      const inp = document.getElementById('main_curve_dia_mm') || document.querySelector('[name="impeller_dia_mm"]');
      if (inp) {
        const val = parseFloat(inp.value);
        if (!isNaN(val)) {
          inp.value = convertValue(val, fromUnit, toUnit, 'dia');
        }
      }
      e.target.setAttribute('data-prev', toUnit);
    });
  }
}

function initPreviewUnitSelectors() {
  ['q', 'h', 'npsh', 'pow'].forEach(type => {
    const el = document.getElementById(`preview-unit-${type}`);
    if (el) {
      el.addEventListener('change', () => {
        refreshMainPreview();
      });
    }
  });
}

/* ── Serialize current unit preferences to hidden form fields ────────── */
function serializeDataUnits() {
  const uq = document.getElementById('unit-q')?.value || 'm3h';
  const uh = document.getElementById('unit-h')?.value || 'm';
  const unpsh = document.getElementById('unit-npsh')?.value || 'm';
  const upow = document.getElementById('unit-pow')?.value || 'kw';
  const uopq = document.getElementById('unit-op-q')?.value || 'm3h';

  const units = { q: uq, h: uh, npsh: unpsh, pow: upow, op_q: uopq };
  const field = document.getElementById('data_units_field');
  if (field) field.value = JSON.stringify(units);

  if (document.getElementById('unit_q_field')) document.getElementById('unit_q_field').value = uq;
  if (document.getElementById('unit_h_field')) document.getElementById('unit_h_field').value = uh;
  if (document.getElementById('unit_npsh_field')) document.getElementById('unit_npsh_field').value = unpsh;
  if (document.getElementById('unit_pow_field')) document.getElementById('unit_pow_field').value = upow;
  if (document.getElementById('unit_op_q_field')) document.getElementById('unit_op_q_field').value = uopq;
}

/* ── Plotly minimal dark theme ─────────────────────────────────────────────── */
var FORM_LAYOUT = {
  paper_bgcolor: '#1a1d23',
  plot_bgcolor: '#1a1d23',
  font: { color: '#c9d1d9', size: 11 },
  margin: { l: 44, r: 10, t: 28, b: 36 },
  xaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d', title: { font: { size: 11 } } },
  yaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d', title: { font: { size: 11 } } },
};

/* ── Raw table helpers ─────────────────────────────────────────────────────── */

function serializeRawTable() {
  const rows = document.querySelectorAll('#perfTable tbody tr');
  const data = [];
  rows.forEach(row => {
    const q = row.querySelector('.col-q')?.value ?? '';
    const h = row.querySelector('.col-h')?.value ?? '';
    const eta = row.querySelector('.col-eta')?.value ?? '';
    const npsh = row.querySelector('.col-npsh')?.value ?? '';
    const pow = row.querySelector('.col-pow')?.value ?? '';
    data.push([q, h, eta, npsh, pow]);
  });
  const field = document.getElementById('raw_table_json_field');
  if (field) field.value = JSON.stringify(data);
}

function initBlankTable() {
  const tbody = document.querySelector('#perfTable tbody');
  if (tbody) {
    tbody.innerHTML = '';
    for (let i = 0; i < 6; i++) {
      addRow('perfTable');
    }
  }
}

function initTableFromCurves(pumpData) {
  const tbody = document.querySelector('#perfTable tbody');
  if (!tbody || !pumpData) return;
  tbody.innerHTML = '';

  const qMax = pumpData.q_max || 100.0;
  const qBep = pumpData.q_bep || (qMax * 0.6);
  const qSteps = [0, qBep * 0.5, qBep, qBep * 1.25, qMax];

  const a0 = pumpData.hq_a0 || 0, a1 = pumpData.hq_a1 || 0, a2 = pumpData.hq_a2 || 0, a3 = pumpData.hq_a3 || 0;
  const b0 = pumpData.eff_b0 || 0, b1 = pumpData.eff_b1 || 0, b2 = pumpData.eff_b2 || 0, b3 = pumpData.eff_b3 || 0;
  const c0 = pumpData.npsh_c0 || 0, c1 = pumpData.npsh_c1 || 0, c2 = pumpData.npsh_c2 || 0;
  const p0 = pumpData.pow_p0 || 0, p1 = pumpData.pow_p1 || 0, p2 = pumpData.pow_p2 || 0;

  const poly = (coeffs, q) => coeffs.reduce((acc, c, idx) => acc + c * Math.pow(q, idx), 0);

  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  const fQ = CONVERSIONS.q[unitQ] || 1.0;
  const fH = CONVERSIONS.h[unitH] || 1.0;
  const fNpsh = CONVERSIONS.npsh[unitNpsh] || 1.0;
  const fPow = CONVERSIONS.pow[unitPow] || 1.0;

  qSteps.forEach(q => {
    const h = Math.max(0, poly([a0, a1, a2, a3], q));
    const eta = Math.min(100, Math.max(0, poly([b0, b1, b2, b3], q)));
    const npsh = Math.max(0, poly([c0, c1, c2], q));
    const pow = Math.max(0, poly([p0, p1, p2], q));

    const tr = document.createElement('tr');
    tr.className = 'hover:bg-[#1c2330]/50 transition-colors border-b border-[#30363d]/40';
    tr.innerHTML = `
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-q" step="any" value="${(q * fQ).toFixed(2)}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-h" step="any" value="${(h * fH).toFixed(2)}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-eta" step="any" min="0" max="100" value="${eta.toFixed(1)}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-npsh" step="any" value="${(npsh * fNpsh).toFixed(2)}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-pow" step="any" value="${(pow * fPow).toFixed(2)}"></td>
      <td class="p-1.5 text-center"><button type="button" class="text-[#8b949e] hover:text-red-400 hover:bg-red-950/30 p-1.5 rounded transition-colors text-xs font-medium" onclick="removeRow(this)" title="Delete Row"><i class="bi bi-trash text-sm"></i></button></td>`;
    tbody.appendChild(tr);
  });
}

function initExtraCurves(extraCurvesData) {
  const container = document.getElementById('extraCurvesContainer');
  if (container) container.innerHTML = '';
  if (Array.isArray(extraCurvesData)) {
    extraCurvesData.forEach(c => {
      if (typeof addExtraCurveCard === 'function') addExtraCurveCard(c);
    });
  }
}

function restoreRawTable(rawJson) {
  let data;
  if (Array.isArray(rawJson)) {
    data = rawJson;
  } else if (typeof rawJson === 'string' && rawJson.includes(';')) {
    data = rawJson.split(';').map(r => r.split(',').map(s => s.trim()));
  } else if (typeof rawJson === 'object' && rawJson !== null) {
    data = rawJson;
  } else {
    try { data = JSON.parse(rawJson); } catch (e) { return false; }
  }
  if (!Array.isArray(data) || !data.length) return false;

  const validRows = data.filter(r => Array.isArray(r) && r.some(v => v !== undefined && v !== null && String(v).trim() !== ''));
  const rowsToRender = validRows.length > 0 ? validRows : data;

  const tbody = document.querySelector('#perfTable tbody');
  tbody.innerHTML = '';
  rowsToRender.forEach(row => {
    const [q, h, eta, npsh, pow] = row;
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-800/30 transition-colors';
    tr.innerHTML =
      '<td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-q" step="any" value="' + (q !== undefined && q !== null ? q : '') + '"></td>' +
      '<td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-h" step="any" value="' + (h !== undefined && h !== null ? h : '') + '"></td>' +
      '<td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-eta" step="any" min="0" max="100" value="' + (eta !== undefined && eta !== null ? eta : '') + '"></td>' +
      '<td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-npsh" step="any" value="' + (npsh !== undefined && npsh !== null ? npsh : '') + '"></td>' +
      '<td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-pow" step="any" value="' + (pow !== undefined && pow !== null ? pow : '') + '"></td>' +
      '<td class="p-1 text-center"><button type="button" class="text-slate-400 hover:text-rose-400 p-1 text-sm focus:outline-none" onclick="removeRow(this)"><i class="bi bi-trash"></i></button></td>';
    tbody.appendChild(tr);
  });
  return true;
}

/* ── Row management ─────────────────────────────────────────────────────────── */
function addRow(tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  const row = document.createElement('tr');
  row.className = 'hover:bg-slate-800/30 transition-colors';
  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';
  row.innerHTML = `
    <td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-q" step="any" placeholder="Q (${getUnitLabel('q', unitQ)})"></td>
    <td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-h" step="any" placeholder="H (${getUnitLabel('h', unitH)})"></td>
    <td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-eta" step="any" min="0" max="100" placeholder="η %"></td>
    <td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-npsh" step="any" placeholder="NPSHr (${getUnitLabel('npsh', unitNpsh)})"></td>
    <td class="p-1"><input type="number" class="w-full bg-dark-input border border-dark-border rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-500 col-pow" step="any" placeholder="${getUnitLabel('pow', unitPow)} (opt)"></td>
    <td class="p-1 text-center"><button type="button" class="text-slate-400 hover:text-rose-400 p-1 text-sm focus:outline-none" onclick="removeRow(this)"><i class="bi bi-trash"></i></button></td>`;
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
    let q = parseFloat(row.querySelector('.col-q')?.value);
    let h = parseFloat(row.querySelector('.col-h')?.value);
    let eta = parseFloat(row.querySelector('.col-eta')?.value);
    let npsh = parseFloat(row.querySelector('.col-npsh')?.value);
    let pow = parseFloat(row.querySelector('.col-pow')?.value);

    if (toSIUnits) {
      if (!isNaN(q)) q = q / CONVERSIONS.q[unitQ];
      if (!isNaN(h)) h = h / CONVERSIONS.h[unitH];
      if (!isNaN(npsh)) npsh = npsh / CONVERSIONS.npsh[unitNpsh];
      if (!isNaN(pow)) pow = pow / CONVERSIONS.pow[unitPow];
    }

    if (!isNaN(q) && !isNaN(h)) q_h.push([q, h]);
    if (!isNaN(q) && !isNaN(eta)) q_eta.push([q, eta]);
    if (!isNaN(q) && !isNaN(npsh)) q_npsh.push([q, npsh]);
    if (!isNaN(q) && !isNaN(pow)) q_p.push([q, pow]);
  });
  return { q_h, q_eta: q_eta.length >= 3 ? q_eta : null, q_npsh: q_npsh.length >= 2 ? q_npsh : null, q_p: q_p.length >= 2 ? q_p : null };
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
    // Beginners Note: Extract per-curve polynomial order choices for fitting API request
    const poHq = document.getElementById('poly_order_hq')?.value || 3;
    const poEff = document.getElementById('poly_order_eff')?.value || 3;
    const poNpsh = document.getElementById('poly_order_npsh')?.value || 2;
    const poPow = document.getElementById('poly_order_pow')?.value || 2;

    const res = await fetch('/papi/fit-curves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        q_h, q_eta, q_npsh, q_p,
        poly_order_hq: parseInt(poHq),
        poly_order_eff: parseInt(poEff),
        poly_order_npsh: parseInt(poNpsh),
        poly_order_pow: parseInt(poPow),
      }),
    });
    const d = await res.json();

    if (!d.ok) {
      showStatus('error', d.error || 'Fit failed.');
      return;
    }

    lastFitResults = d;

    // Populate hidden coefficient fields
    ['hq_a0', 'hq_a1', 'hq_a2', 'hq_a3', 'hq_a4', 'hq_a5',
      'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3', 'eff_b4', 'eff_b5',
      'npsh_c0', 'npsh_c1', 'npsh_c2', 'npsh_c3', 'npsh_c4', 'npsh_c5',
      'pow_p0', 'pow_p1', 'pow_p2', 'pow_p3', 'pow_p4', 'pow_p5'].forEach(k => setField(k, d[k] ?? 0));

    updatePolynomialUI();

    // Populate derived operating range — convert SI to the op-range display unit
    const opUnit = document.getElementById('unit-op-q')?.value || 'm3h';
    const opFactor = CONVERSIONS.q[opUnit];
    if (d.q_max != null) setField('q_max', (d.q_max * opFactor).toFixed(2));
    if (d.q_bep != null) setField('q_bep', (d.q_bep * opFactor).toFixed(2));

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

    const { q_h: q_h_raw, q_eta: q_eta_raw } = getTableData('perfTable', true);
    buildPreviewCharts(d, q_h_raw, q_eta_raw);

    // Refresh coefficient display
    refreshCoeffDisplay(d);

    // Snapshot the raw table values so they survive a page reload in edit mode
    serializeRawTable();

  } catch (e) {
    showStatus('error', 'Network error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-calculator me-1"></i>Fit & Preview';
  }
}

function showStatus(type, msg) {
  const el = document.getElementById('fitStatus');
  if (!el) return;
  if (!msg) {
    el.innerHTML = '';
    el.className = 'mt-2 text-xs font-medium';
    return;
  }
  if (type === 'error') {
    el.className = 'mt-3 p-2.5 rounded bg-[#da3633]/15 border border-[#da3633]/30 text-xs font-semibold text-[#f85149] flex items-center gap-2';
    el.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i><span>${msg}</span>`;
  } else if (type === 'ok') {
    el.className = 'mt-3 p-2.5 rounded bg-[#238636]/15 border border-[#238636]/30 text-xs font-semibold text-[#3fb950] flex items-center gap-2';
    el.innerHTML = `<i class="bi bi-check-circle-fill"></i><span>${msg}</span>`;
  } else {
    el.className = 'mt-2 text-xs text-[#8b949e]';
    el.textContent = msg;
  }
}

var isPreviewEventsBound = false;

function collectGraphOptions() {
  return {
    show_eff_iso: document.getElementById('chkShowEffIso')?.checked !== false,
    eff_levels: document.getElementById('txtEffLevels')?.value || '',
    trim_penalty: document.getElementById('numTrimPenalty')?.value !== '' && document.getElementById('numTrimPenalty')?.value !== undefined ? parseFloat(document.getElementById('numTrimPenalty')?.value) : null,
    show_power_iso: document.getElementById('chkShowPowerIso')?.checked || false,
    power_levels: document.getElementById('txtPowerLevels')?.value || '',
    show_npsh_iso: document.getElementById('chkShowNpshIso')?.checked || false,
    npsh_levels: document.getElementById('txtNpshLevels')?.value || '',
    show_npsh_curve: document.getElementById('chkShowNpshCurve')?.checked || false,
    npsh_yaxis: document.querySelector('input[name="npshYAxisChoice"]:checked')?.value || 'y2',
    show_speed_lines: document.getElementById('chkSpeedLines')?.checked || false,
    speed_line_values: document.getElementById('txtSpeedLineValues')?.value || '',
    show_rpm_overlay: document.getElementById('chkRpmOverlay')?.checked || false,
    rpm_values: document.getElementById('txtRpmValues')?.value || '',
    show_dia_overlay: document.getElementById('chkDiaOverlay')?.checked || false,
    dia_overlay_values: document.getElementById('txtDiaOverlayValues')?.value || '',
    show_hq: document.getElementById('chkShowHQ')?.checked !== false,
    show_other: document.getElementById('chkShowOther')?.checked !== false,
    show_eff: document.getElementById('chkShowEff')?.checked !== false,
    show_power: document.getElementById('chkShowPower')?.checked !== false,
    show_npsh: document.getElementById('chkShowNpsh')?.checked !== false,
    combine_eff_power: document.getElementById('chkCombineEffPower')?.checked !== false,
    trim_model: document.querySelector('input[name="trimModelChoice"]:checked')?.value || 'fit',
    unit_max_imp: document.querySelector('select[name="unit_max_imp"]')?.value || 'mm',
    graph_unit_q: document.getElementById('preview-unit-q')?.value || '',
    graph_unit_h: document.getElementById('preview-unit-h')?.value || '',
    graph_unit_npsh: document.getElementById('preview-unit-npsh')?.value || '',
    graph_unit_pow: document.getElementById('preview-unit-pow')?.value || '',
    legend_mode: document.getElementById('selLegendMode')?.value || 'each',
    curve_label_flow_pct: parseFloat(document.getElementById('txtCurveLabelFlowPct')?.value) || 100,
    curve_label_vpos: document.getElementById('selCurveLabelVPos')?.value || 'top',
    curve_label_pos: document.getElementById('selCurveLabelPos')?.value || 'middle-top',

    // Graph Curve Styling Options (Head, Efficiency, Power, NPSH)
    head_color: document.getElementById('clrHeadColor')?.value || '#58a6ff',
    head_weight: parseFloat(document.getElementById('selHeadWeight')?.value) || 2.0,
    head_style: document.getElementById('selHeadStyle')?.value || 'solid',

    eff_color: document.getElementById('clrEffColor')?.value || '#3fb950',
    eff_weight: parseFloat(document.getElementById('selEffWeight')?.value) || 1.5,
    eff_style: document.getElementById('selEffStyle')?.value || 'dot',

    pow_color: document.getElementById('clrPowColor')?.value || '#f85149',
    pow_weight: parseFloat(document.getElementById('selPowWeight')?.value) || 1.5,
    pow_style: document.getElementById('selPowStyle')?.value || 'longdash',

    npsh_color: document.getElementById('clrNpshColor')?.value || '#39d3c0',
    npsh_weight: parseFloat(document.getElementById('selNpshWeight')?.value) || 1.5,
    npsh_style: document.getElementById('selNpshStyle')?.value || 'dashdot'
  };
}

function applyGraphOptions(opts) {
  if (!opts || typeof opts !== 'object') return;
  if (opts.show_eff_iso !== undefined && document.getElementById('chkShowEffIso')) document.getElementById('chkShowEffIso').checked = opts.show_eff_iso;
  if (opts.eff_levels !== undefined && document.getElementById('txtEffLevels')) document.getElementById('txtEffLevels').value = opts.eff_levels;
  if (opts.trim_penalty !== undefined && opts.trim_penalty !== null && document.getElementById('numTrimPenalty')) document.getElementById('numTrimPenalty').value = opts.trim_penalty;

  if (opts.show_power_iso !== undefined && document.getElementById('chkShowPowerIso')) {
    document.getElementById('chkShowPowerIso').checked = opts.show_power_iso;
    const g = document.getElementById('groupPowerLevels');
    if (g) g.style.display = opts.show_power_iso ? '' : 'none';
  }
  if (opts.power_levels !== undefined && document.getElementById('txtPowerLevels')) document.getElementById('txtPowerLevels').value = opts.power_levels;

  if (opts.show_npsh_iso !== undefined && document.getElementById('chkShowNpshIso')) {
    document.getElementById('chkShowNpshIso').checked = opts.show_npsh_iso;
    const g = document.getElementById('groupNpshLevels');
    if (g) g.style.display = opts.show_npsh_iso ? '' : 'none';
  }
  if (opts.npsh_levels !== undefined && document.getElementById('txtNpshLevels')) document.getElementById('txtNpshLevels').value = opts.npsh_levels;

  if (opts.show_npsh_curve !== undefined && document.getElementById('chkShowNpshCurve')) {
    document.getElementById('chkShowNpshCurve').checked = opts.show_npsh_curve;
    const g = document.getElementById('groupNpshYAxis');
    if (g) g.style.display = opts.show_npsh_curve ? '' : 'none';
  }
  if (opts.npsh_yaxis && document.querySelector(`input[name="npshYAxisChoice"][value="${opts.npsh_yaxis}"]`)) {
    document.querySelector(`input[name="npshYAxisChoice"][value="${opts.npsh_yaxis}"]`).checked = true;
  }
  if (opts.show_speed_lines !== undefined && document.getElementById('chkSpeedLines')) document.getElementById('chkSpeedLines').checked = opts.show_speed_lines;
  if (opts.speed_line_values !== undefined && document.getElementById('txtSpeedLineValues')) document.getElementById('txtSpeedLineValues').value = opts.speed_line_values;
  if (opts.show_rpm_overlay !== undefined && document.getElementById('chkRpmOverlay')) {
    document.getElementById('chkRpmOverlay').checked = opts.show_rpm_overlay;
    const w = document.getElementById('wrapRpmOverlay');
    if (w) w.style.display = opts.show_rpm_overlay ? '' : 'none';
  }
  if (opts.rpm_values !== undefined && document.getElementById('txtRpmValues')) document.getElementById('txtRpmValues').value = opts.rpm_values;
  if (opts.show_dia_overlay !== undefined && document.getElementById('chkDiaOverlay')) {
    document.getElementById('chkDiaOverlay').checked = opts.show_dia_overlay;
    const w = document.getElementById('wrapDiaOverlay');
    if (w) w.style.display = opts.show_dia_overlay ? '' : 'none';
  }
  if (opts.dia_overlay_values !== undefined && document.getElementById('txtDiaOverlayValues')) document.getElementById('txtDiaOverlayValues').value = opts.dia_overlay_values;
  if (opts.show_hq !== undefined && document.getElementById('chkShowHQ')) document.getElementById('chkShowHQ').checked = opts.show_hq;
  if (opts.show_other !== undefined && document.getElementById('chkShowOther')) document.getElementById('chkShowOther').checked = opts.show_other;
  if (opts.show_eff !== undefined && document.getElementById('chkShowEff')) document.getElementById('chkShowEff').checked = opts.show_eff;
  if (opts.show_power !== undefined && document.getElementById('chkShowPower')) document.getElementById('chkShowPower').checked = opts.show_power;
  if (opts.show_npsh !== undefined && document.getElementById('chkShowNpsh')) document.getElementById('chkShowNpsh').checked = opts.show_npsh;
  if (opts.combine_eff_power !== undefined && document.getElementById('chkCombineEffPower')) document.getElementById('chkCombineEffPower').checked = opts.combine_eff_power;
  if (opts.trim_model && document.querySelector(`input[name="trimModelChoice"][value="${opts.trim_model}"]`)) {
    document.querySelector(`input[name="trimModelChoice"][value="${opts.trim_model}"]`).checked = true;
  }
  if (opts.legend_mode && document.getElementById('selLegendMode')) {
    document.getElementById('selLegendMode').value = opts.legend_mode;
    const g = document.getElementById('groupCurveLabelPos');
    if (g) g.style.display = opts.legend_mode === 'curve_labels' ? '' : 'none';
  }
  if (opts.curve_label_flow_pct !== undefined && document.getElementById('txtCurveLabelFlowPct')) {
    document.getElementById('txtCurveLabelFlowPct').value = opts.curve_label_flow_pct;
  }
  if (opts.curve_label_vpos && document.getElementById('selCurveLabelVPos')) {
    document.getElementById('selCurveLabelVPos').value = opts.curve_label_vpos;
  }
  if (opts.curve_label_pos && document.getElementById('selCurveLabelPos')) {
    document.getElementById('selCurveLabelPos').value = opts.curve_label_pos;
  }
  if (opts.custom_label_pos && typeof opts.custom_label_pos === 'object') {
    customLabelPositions = Object.assign({}, opts.custom_label_pos);
  }

  // Restore Curve Style Inputs
  if (opts.head_color && document.getElementById('clrHeadColor')) document.getElementById('clrHeadColor').value = opts.head_color;
  if (opts.head_weight && document.getElementById('selHeadWeight')) document.getElementById('selHeadWeight').value = opts.head_weight;
  if (opts.head_style && document.getElementById('selHeadStyle')) document.getElementById('selHeadStyle').value = opts.head_style;

  if (opts.eff_color && document.getElementById('clrEffColor')) document.getElementById('clrEffColor').value = opts.eff_color;
  if (opts.eff_weight && document.getElementById('selEffWeight')) document.getElementById('selEffWeight').value = opts.eff_weight;
  if (opts.eff_style && document.getElementById('selEffStyle')) document.getElementById('selEffStyle').value = opts.eff_style;

  if (opts.pow_color && document.getElementById('clrPowColor')) document.getElementById('clrPowColor').value = opts.pow_color;
  if (opts.pow_weight && document.getElementById('selPowWeight')) document.getElementById('selPowWeight').value = opts.pow_weight;
  if (opts.pow_style && document.getElementById('selPowStyle')) document.getElementById('selPowStyle').value = opts.pow_style;

  if (opts.npsh_color && document.getElementById('clrNpshColor')) document.getElementById('clrNpshColor').value = opts.npsh_color;
  if (opts.npsh_weight && document.getElementById('selNpshWeight')) document.getElementById('selNpshWeight').value = opts.npsh_weight;
  if (opts.npsh_style && document.getElementById('selNpshStyle')) document.getElementById('selNpshStyle').value = opts.npsh_style;
}

function serializeGraphOptions() {
  const opts = typeof collectGraphOptions === 'function' ? collectGraphOptions() : {};
  opts.custom_label_pos = customLabelPositions;
  const jsonStr = JSON.stringify(opts);
  const fields = document.querySelectorAll('input[name="graph_options_json"]');
  if (fields && fields.length > 0) {
    fields.forEach(f => { f.value = jsonStr; });
  } else {
    let hdn = document.createElement('input');
    hdn.type = 'hidden';
    hdn.name = 'graph_options_json';
    hdn.id = 'hdnGraphOptionsJson';
    hdn.value = jsonStr;
    const form = document.getElementById('pumpForm');
    if (form) form.appendChild(hdn);
  }

  // Persist formatted curve styles (color;weight,lineStyle) to hidden fields
  const headColor = document.getElementById('clrHeadColor')?.value || '#58a6ff';
  const headWeight = document.getElementById('selHeadWeight')?.value || '2.0';
  const headStyle = document.getElementById('selHeadStyle')?.value || 'solid';
  const fHead = document.getElementById('head_curve_style_field');
  if (fHead) fHead.value = `${headColor};${headWeight},${headStyle}`;

  const effColor = document.getElementById('clrEffColor')?.value || '#3fb950';
  const effWeight = document.getElementById('selEffWeight')?.value || '1.5';
  const effStyle = document.getElementById('selEffStyle')?.value || 'dot';
  const fEff = document.getElementById('eff_curve_style_field');
  if (fEff) fEff.value = `${effColor};${effWeight},${effStyle}`;

  const powColor = document.getElementById('clrPowColor')?.value || '#f85149';
  const powWeight = document.getElementById('selPowWeight')?.value || '1.5';
  const powStyle = document.getElementById('selPowStyle')?.value || 'longdash';
  const fPow = document.getElementById('power_curve_style_field');
  if (fPow) fPow.value = `${powColor};${powWeight},${powStyle}`;

  const npshColor = document.getElementById('clrNpshColor')?.value || '#39d3c0';
  const npshWeight = document.getElementById('selNpshWeight')?.value || '1.5';
  const npshStyle = document.getElementById('selNpshStyle')?.value || 'dashdot';
  const fNpsh = document.getElementById('npsh_curve_style_field');
  if (fNpsh) fNpsh.value = `${npshColor};${npshWeight},${npshStyle}`;

  const mainStyleMode = document.getElementById('main_curve_style_mode')?.value || 'graph';
  const mainColor = document.getElementById('main_curve_color')?.value || '#58a6ff';
  const mainWeight = document.getElementById('main_curve_weight')?.value || '2.0';
  const mainLineStyle = document.getElementById('main_curve_line_style')?.value || 'solid';
  const fMain = document.getElementById('main_curve_style_field');
  if (fMain) fMain.value = mainStyleMode === 'custom' ? `custom;${mainColor};${mainWeight},${mainLineStyle}` : 'graph';
}

function getPumpFormData() {
  const data = {};
  const fields = [
    'speed_rpm', 'impeller_dia_mm', 'q_min', 'q_max', 'q_bep',
    'hq_a0', 'hq_a1', 'hq_a2', 'hq_a3', 'hq_a4', 'hq_a5',
    'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3', 'eff_b4', 'eff_b5',
    'npsh_c0', 'npsh_c1', 'npsh_c2', 'npsh_c3', 'npsh_c4', 'npsh_c5',
    'pow_p0', 'pow_p1', 'pow_p2', 'pow_p3', 'pow_p4', 'pow_p5',
    'hr', 'qr', 'er', 'impeller_diameters'
  ];

  fields.forEach(f => {
    const el = document.querySelector(`[name="${f}"]`);
    if (el) {
      if (f === 'impeller_diameters') {
        const val = el.value.trim();
        if (val) {
          data[f] = val.split(/[;,]/).map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
        } else {
          data[f] = [];
        }
      } else {
        data[f] = el.value ? parseFloat(el.value) : 0.0;
      }
    }
  });

  data['family_type'] = document.getElementById('selFamilyType')?.value || 'trimmed_impeller';

  const gOpts = collectGraphOptions();
  data['eff_levels'] = gOpts.eff_levels;
  data['trim_penalty'] = gOpts.trim_penalty;
  data['power_levels'] = gOpts.power_levels;
  data['npsh_levels'] = gOpts.npsh_levels;
  data['force_affinity'] = gOpts.trim_model;

  const payload = serializeExtraCurves();
  serializeGraphOptions();
  data['extra_curves'] = payload;

  data['main_curve_style'] = document.getElementById('main_curve_style_field')?.value || 'graph';
  data['head_curve_style'] = document.getElementById('head_curve_style_field')?.value || '';
  data['eff_curve_style'] = document.getElementById('eff_curve_style_field')?.value || '';
  data['power_curve_style'] = document.getElementById('power_curve_style_field')?.value || '';
  data['npsh_curve_style'] = document.getElementById('npsh_curve_style_field')?.value || '';

  // Beginners Note: Extract 20 custom axis scale settings (min, max, major, minor) for preview rendering
  ['flow', 'head', 'eff', 'power', 'npsh'].forEach(axis => {
    ['min', 'max', 'major'].forEach(prop => {
      const fieldName = `axis_${axis}_${prop}`;
      const el = document.getElementById(fieldName);
      data[fieldName] = (el && el.value.trim() !== '') ? parseFloat(el.value.trim()) : null;
    });
    const minorField = `axis_${axis}_minor`;
    const minorEl = document.getElementById(minorField);
    data[minorField] = (minorEl && minorEl.value.trim() !== '') ? parseInt(minorEl.value.trim(), 10) : null;
  });

  // Beginners Note: Extract per-curve polynomial fitting orders (1 to 5) for preview rendering
  ['poly_order_hq', 'poly_order_eff', 'poly_order_npsh', 'poly_order_pow'].forEach(key => {
    const el = document.getElementById(key);
    if (el) data[key] = parseInt(el.value) || 3;
  });

  return data;
}

function convertUnitCurveData(data, qUnit, hUnit, npshUnit, powUnit) {
  const converted = JSON.parse(JSON.stringify(data));
  const qFactor = CONVERSIONS.q[qUnit] || 1.0;
  const hFactor = CONVERSIONS.h[hUnit] || 1.0;
  const npshFactor = CONVERSIONS.npsh[npshUnit] || 1.0;
  const powFactor = CONVERSIONS.pow[powUnit] || 1.0;

  if (converted.q) converted.q = converted.q.map(v => v * qFactor);
  if (converted.h) converted.h = converted.h.map(v => v * hFactor);
  if (converted.eta) converted.eta = converted.eta.map(v => v);
  if (converted.power) converted.power = converted.power.map(v => v * powFactor);
  if (converted.npsh) converted.npsh = converted.npsh.map(v => v * npshFactor);

  if (converted.h_clean) converted.h_clean = converted.h_clean.map(v => v * hFactor);
  if (converted.eta_clean) converted.eta_clean = converted.eta_clean.map(v => v);
  if (converted.power_clean) converted.power_clean = converted.power_clean.map(v => v * powFactor);

  if (converted.bep) {
    converted.bep.q = converted.bep.q * qFactor;
    converted.bep.h = converted.bep.h * hFactor;
    converted.bep.power = converted.bep.power * powFactor;
  }
  if (converted.system_h) converted.system_h = converted.system_h.map(v => v * hFactor);

  return converted;
}

function convertUnitWarmanData(data, qUnit, hUnit, npshUnit, powUnit) {
  const converted = JSON.parse(JSON.stringify(data));
  const qFactor = CONVERSIONS.q[qUnit] || 1.0;
  const hFactor = CONVERSIONS.h[hUnit] || 1.0;
  const npshFactor = CONVERSIONS.npsh[npshUnit] || 1.0;
  const powFactor = CONVERSIONS.pow[powUnit] || 1.0;

  if (converted.family) {
    converted.family.forEach(d => {
      d.q = d.q.map(v => v * qFactor);
      d.h = d.h.map(v => v * hFactor);
      d.eta = d.eta.map(v => v);
      d.power = d.power.map(v => v * powFactor);
      d.npsh = d.npsh.map(v => v * npshFactor);
      if (d.bep) {
        d.bep.q = d.bep.q * qFactor;
        d.bep.h = d.bep.h * hFactor;
      }
    });
  }

  if (converted.isolines) {
    converted.isolines.forEach(iso => {
      iso.q = iso.q.map(v => v * qFactor);
      iso.h = iso.h.map(v => v * hFactor);
      iso.label_q = iso.label_q * qFactor;
      iso.label_h = iso.label_h * hFactor;
    });
  }

  if (converted.power_isolines) {
    converted.power_isolines.forEach(iso => {
      iso.q = iso.q.map(v => v * qFactor);
      iso.h = iso.h.map(v => v * hFactor);
      iso.label_q = iso.label_q * qFactor;
      iso.label_h = iso.label_h * hFactor;
    });
  }

  if (converted.npsh_isolines) {
    converted.npsh_isolines.forEach(iso => {
      iso.q = iso.q.map(v => v * qFactor);
      iso.h = iso.h.map(v => v * hFactor);
      iso.label_q = iso.label_q * qFactor;
      iso.label_h = iso.label_h * hFactor;
    });
  }

  if (converted.speed_lines) {
    converted.speed_lines.forEach(sl => {
      sl.q = sl.q.map(v => v * qFactor);
      sl.h = sl.h.map(v => v * hFactor);
      if (sl.power) sl.power = sl.power.map(v => v * powFactor);
      if (sl.npsh) sl.npsh = sl.npsh.map(v => v * npshFactor);
      if (sl.bep) {
        sl.bep.q = sl.bep.q * qFactor;
        sl.bep.h = sl.bep.h * hFactor;
        if (sl.bep.power) sl.bep.power = sl.bep.power * powFactor;
        if (sl.bep.npsh) sl.bep.npsh = sl.bep.npsh * npshFactor;
      }
    });
  }

  if (converted.bep) {
    converted.bep.q = converted.bep.q * qFactor;
    converted.bep.h = converted.bep.h * hFactor;
  }

  if (converted.system_q) converted.system_q = converted.system_q.map(v => v * qFactor);
  if (converted.system_h) converted.system_h = converted.system_h.map(v => v * hFactor);

  return converted;
}

function bindPreviewEvents() {
  if (isPreviewEventsBound) return;
  isPreviewEventsBound = true;

  const ids = ['chkShowEffIso', 'chkShowPowerIso', 'chkShowNpshIso', 'chkShowNpshCurve', 'chkSpeedLines', 'txtSpeedLineValues', 'chkShowOther', 'selLegendMode', 'txtCurveLabelFlowPct', 'selCurveLabelVPos', 'selCurveLabelPos'];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => {
        if (id === 'selLegendMode') {
          const g = document.getElementById('groupCurveLabelPos');
          if (g) g.style.display = el.value === 'curve_labels' ? '' : 'none';
        }
        refreshPreviewCharts();
      });
      if (id === 'txtCurveLabelFlowPct' || id === 'txtSpeedLineValues') {
        el.addEventListener('input', () => refreshPreviewCharts());
        el.addEventListener('keyup', () => refreshPreviewCharts());
      }
    }
  });

  const txtIds = ['txtEffLevels', 'txtPowerLevels', 'txtNpshLevels'];
  txtIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => refreshPreviewCharts());
      el.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          refreshPreviewCharts();
        }
      });
    }
  });

  document.querySelectorAll('input[name="otherGraphsLayout"], input[name="npshYAxisChoice"], input[name="trimModelChoice"]').forEach(radio => {
    radio.addEventListener('change', () => refreshPreviewCharts());
  });

  ['preview-unit-q', 'preview-unit-h', 'preview-unit-npsh', 'preview-unit-pow'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => refreshPreviewCharts());
  });

  // Beginners Note: Bind change and input listeners to axis scale input fields for instant live preview updates
  document.querySelectorAll('.axis-scale-input').forEach(input => {
    input.addEventListener('change', () => refreshPreviewCharts());
    input.addEventListener('input', () => refreshPreviewCharts());
  });

  // Beginners Note: Bind change listener on per-curve polynomial order dropdowns to automatically refit & preview
  document.querySelectorAll('.poly-order-select').forEach(select => {
    if (!select._hasFitListener) {
      select._hasFitListener = true;
      select.addEventListener('change', onPolyOrderChange);
    }
  });
}

function formatPolyEquation(coeffLetter, depName, degree, suffix = '') {
  const superscripts = ['₀', '₁', '₂', '₃', '₄', '₅'];
  const expMap = ['²', '³', '⁴', '⁵'];
  let terms = [];
  for (let i = 0; i <= degree; i++) {
    const coeffSymbol = `${coeffLetter}${superscripts[i]}`;
    if (i === 0) {
      terms.push(coeffSymbol);
    } else if (i === 1) {
      terms.push(`${coeffSymbol}Q`);
    } else {
      terms.push(`${coeffSymbol}Q${expMap[i - 2]}`);
    }
  }
  return `${depName ? depName + ' = ' : ''}${terms.join(' + ')}${suffix}`;
}

function updatePolynomialUI() {
  const poHq = parseInt(document.getElementById('poly_order_hq')?.value) || 3;
  const poEff = parseInt(document.getElementById('poly_order_eff')?.value) || 3;
  const poNpsh = parseInt(document.getElementById('poly_order_npsh')?.value) || 2;
  const poPow = parseInt(document.getElementById('poly_order_pow')?.value) || 2;

  // Beginners Note: Dynamically update equation header title according to set polynomial degree
  const eqHq = document.getElementById('eq_title_hq');
  if (eqHq) eqHq.innerHTML = `<i class="bi bi-graph-down-arrow me-1"></i>H-Q ${formatPolyEquation('a', 'H', poHq)}`;

  const eqEff = document.getElementById('eq_title_eff');
  if (eqEff) eqEff.innerHTML = `<i class="bi bi-speedometer2 me-1"></i>Efficiency ${formatPolyEquation('b', 'η', poEff)}`;

  const eqNpsh = document.getElementById('eq_title_npsh');
  if (eqNpsh) eqNpsh.innerHTML = `<i class="bi bi-arrow-up-right me-1"></i>NPSHr ${formatPolyEquation('c', '', poNpsh)}`;

  const eqPow = document.getElementById('eq_title_pow');
  if (eqPow) eqPow.innerHTML = `<i class="bi bi-lightning-charge me-1"></i>Shaft Power ${formatPolyEquation('p', 'P', poPow, ' (kW)')}`;

  // Beginners Note: Show/hide individual coefficient input fields representative of selected polynomial degree
  const curves = [
    { prefix: 'hq_a', order: poHq },
    { prefix: 'eff_b', order: poEff },
    { prefix: 'npsh_c', order: poNpsh },
    { prefix: 'pow_p', order: poPow }
  ];

  curves.forEach(c => {
    for (let i = 0; i <= 5; i++) {
      const wrap = document.getElementById(`wrap_${c.prefix}${i}`);
      const input = document.getElementById(`${c.prefix}${i}`);
      if (wrap) {
        if (i <= c.order) {
          wrap.style.display = '';
        } else {
          wrap.style.display = 'none';
          if (input) input.value = 0;
        }
      }
    }
  });

  // Beginners Note: Also update dynamic polynomial equations & coefficient visibility for all additional curves
  if (typeof extraCurves !== 'undefined' && Array.isArray(extraCurves)) {
    extraCurves.forEach(c => updateExtraPolynomialUI(c.id));
  }
}

// Beginners Note: Updates dynamic mathematical equations & shows/hides coefficient fields for an additional curve card
function updateExtraPolynomialUI(curveId) {
  const entry = document.getElementById(`extra-entry-${curveId}`);
  if (!entry) return;

  const poHq = parseInt(document.getElementById('poly_order_hq')?.value) || 3;
  const poEff = parseInt(document.getElementById('poly_order_eff')?.value) || 3;
  const poNpsh = parseInt(document.getElementById('poly_order_npsh')?.value) || 2;
  const poPow = parseInt(document.getElementById('poly_order_pow')?.value) || 2;

  // Beginners Note: Dynamic equation headers on extra curve card
  const eqHq = entry.querySelector(`.extra-eq-title-hq`);
  if (eqHq) eqHq.innerHTML = `<i class="bi bi-graph-down-arrow me-1"></i>H-Q ${formatPolyEquation('a', 'H', poHq)}`;

  const eqEff = entry.querySelector(`.extra-eq-title-eff`);
  if (eqEff) eqEff.innerHTML = `<i class="bi bi-speedometer2 me-1"></i>Efficiency ${formatPolyEquation('b', 'η', poEff)}`;

  const eqNpsh = entry.querySelector(`.extra-eq-title-npsh`);
  if (eqNpsh) eqNpsh.innerHTML = `<i class="bi bi-arrow-up-right me-1"></i>NPSHr ${formatPolyEquation('c', '', poNpsh)}`;

  const eqPow = entry.querySelector(`.extra-eq-title-pow`);
  if (eqPow) eqPow.innerHTML = `<i class="bi bi-lightning-charge me-1"></i>Shaft Power ${formatPolyEquation('p', 'P', poPow, ' (kW)')}`;

  // Beginners Note: Show/hide coefficient inputs up to selected degree for extra curve card
  const curves = [
    { prefix: 'hq_a', order: poHq },
    { prefix: 'eff_b', order: poEff },
    { prefix: 'npsh_c', order: poNpsh },
    { prefix: 'pow_p', order: poPow }
  ];

  curves.forEach(c => {
    for (let i = 0; i <= 5; i++) {
      const wrap = entry.querySelector(`#extra-wrap-${c.prefix}${i}-${curveId}`);
      const input = entry.querySelector(`.extra-cf-${c.prefix}${i}`);
      if (wrap) {
        if (i <= c.order) {
          wrap.style.display = '';
        } else {
          wrap.style.display = 'none';
          if (input) input.value = 0;
        }
      }
    }
  });
}

// Beginners Note: Handler when any per-curve polynomial order dropdown is changed
function onPolyOrderChange() {
  updatePolynomialUI();

  const { q_h } = getTableData('perfTable', true);
  if (q_h && q_h.length >= 3) {
    // If tabular points exist, refit with the newly selected per-curve polynomial orders
    fitAndPreview();
  } else {
    refreshPreviewCharts();
  }
}

async function refreshPreviewCharts() {
  updatePolynomialUI();
  bindPreviewEvents();

  const formData = getPumpFormData();
  const showEffIso = document.getElementById('chkShowEffIso')?.checked || false;
  const showPowerIso = document.getElementById('chkShowPowerIso')?.checked || false;
  const showNpshIso = document.getElementById('chkShowNpshIso')?.checked || false;
  const showNpshCurve = document.getElementById('chkShowNpshCurve')?.checked || false;
  const showSpeedLines = document.getElementById('chkSpeedLines')?.checked || false;
  const showOther = document.getElementById('chkShowOther')?.checked || false;
  const npshYAxis = document.querySelector('input[name="npshYAxisChoice"]:checked')?.value || 'y2';

  // Toggle inputs visibility safely
  const gEff = document.getElementById('groupEffLevels');
  if (gEff) { gEff.style.display = showEffIso ? '' : 'none'; gEff.classList.toggle('hidden', !showEffIso); }
  const gPow = document.getElementById('groupPowerLevels');
  if (gPow) { gPow.style.display = showPowerIso ? '' : 'none'; gPow.classList.toggle('hidden', !showPowerIso); }
  const gNpsh = document.getElementById('groupNpshLevels');
  if (gNpsh) { gNpsh.style.display = showNpshIso ? '' : 'none'; gNpsh.classList.toggle('hidden', !showNpshIso); }
  const gNpshY = document.getElementById('groupNpshYAxis');
  if (gNpshY) { gNpshY.style.display = showNpshCurve ? '' : 'none'; gNpshY.classList.toggle('hidden', !showNpshCurve); }
  const sPanels = document.getElementById('standalonePanels');
  if (sPanels) sPanels.style.display = showOther ? '' : 'none';
  const oOpts = document.getElementById('otherGraphsOptions');
  if (oOpts) oOpts.style.display = showOther ? '' : 'none';

  const body = {
    ...formData,
    eff_levels: showEffIso ? document.getElementById('txtEffLevels')?.value : null,
    trim_penalty: document.getElementById('numTrimPenalty')?.value !== '' && document.getElementById('numTrimPenalty')?.value !== undefined ? parseFloat(document.getElementById('numTrimPenalty')?.value) : null,
    power_levels: showPowerIso ? document.getElementById('txtPowerLevels')?.value : null,
    npsh_levels: showNpshIso ? document.getElementById('txtNpshLevels')?.value : null,
    graph_speed_line_values: document.getElementById('txtSpeedLineValues')?.value || '',
    graph_rpm_values: document.getElementById('txtRpmValues')?.value || '',
    graph_dia_overlay_values: document.getElementById('txtDiaOverlayValues')?.value || '',
  };

  try {
    const [warmanRes, curveRes] = await Promise.all([
      fetch('/papi/preview-warman-chart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).then(r => r.json()),
      fetch('/papi/preview-curve-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).then(r => r.json())
    ]);

    const unitQ = document.getElementById('preview-unit-q')?.value || 'm3h';
    const unitH = document.getElementById('preview-unit-h')?.value || 'm';
    const unitNpsh = document.getElementById('preview-unit-npsh')?.value || 'm';
    const unitPow = document.getElementById('preview-unit-pow')?.value || 'kw';

    if (warmanRes && warmanRes.default_trim_penalty !== undefined) {
      const numTP = document.getElementById('numTrimPenalty');
      if (numTP) numTP.placeholder = `Auto (${warmanRes.default_trim_penalty}%)`;
    }

    const convertedWarman = convertUnitWarmanData(warmanRes, unitQ, unitH, unitNpsh, unitPow);
    const convertedCurves = convertUnitCurveData(curveRes, unitQ, unitH, unitNpsh, unitPow);

    renderPreviewChartsData(convertedWarman, convertedCurves);
  } catch (err) {
    console.error("Preview failed:", err);
  }
}

function renderPreviewChartsData(warmanData, curveData) {
  const showHQ = document.getElementById('chkShowHQ')?.checked !== false;
  const showEffIso = document.getElementById('chkShowEffIso')?.checked || false;
  const showPowerIso = document.getElementById('chkShowPowerIso')?.checked || false;
  const showNpshIso = document.getElementById('chkShowNpshIso')?.checked || false;
  const showNpshCurve = document.getElementById('chkShowNpshCurve')?.checked || false;
  const showSpeedLines = (document.getElementById('chkRpmOverlay')?.checked || document.getElementById('chkSpeedLines')?.checked) || false;
  const showDiaOverlay = document.getElementById('chkDiaOverlay')?.checked || false;
  const npshYAxis = document.querySelector('input[name="npshYAxisChoice"]:checked')?.value || 'y2';

  const PLOTLY_CONFIG = {
    responsive: true, displayModeBar: true,
    modeBarButtonsToRemove: ['select2d', 'lasso2d'],
    displaylogo: false
  };

  const wc = buildWarmanChart(warmanData, {
    showIsolines: showEffIso,
    showPowerIso: showPowerIso,
    showNpshIso: showNpshIso,
    showSpeedLines: showSpeedLines,
    showDiaOverlay: showDiaOverlay,
    showNpshCurve: showNpshCurve,
    npshYAxis: npshYAxis
  });

  const unitQ = document.getElementById('preview-unit-q')?.value || 'm3h';
  const unitH = document.getElementById('preview-unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('preview-unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('preview-unit-pow')?.value || 'kw';

  const labelQ = getUnitLabel('q', unitQ);
  const labelH = getUnitLabel('h', unitH);
  const labelNpsh = getUnitLabel('npsh', unitNpsh);
  const labelPow = getUnitLabel('pow', unitPow);

  wc.layout.xaxis.title = `Flow Q (${labelQ})`;
  wc.layout.yaxis.title = `Head H (${labelH})`;
  if (wc.layout.yaxis2) {
    wc.layout.yaxis2.title = `NPSHr (${labelNpsh})`;
  }

  // Helper to safely toggle element visibility (removing Tailwind 'hidden' class + setting inline style)
  function setVis(el, show, dispStyle = 'block') {
    if (!el) return;
    if (show) {
      el.classList.remove('hidden');
      el.style.display = dispStyle;
    } else {
      el.classList.add('hidden');
      el.style.display = 'none';
    }
  }

  // Toggle main Performance Map Preview card display
  const panelWarmanPreview = document.getElementById('panelWarmanPreview');
  if (panelWarmanPreview) {
    setVis(panelWarmanPreview, showHQ);
  }
  Plotly.react('chartWarman', wc.traces, wc.layout, PLOTLY_CONFIG);
  Plotly.Plots.resize('chartWarman');
  if (wc.layout.annotations && wc.layout.annotations.length > 0) {
    const _pumpId = parseInt(document.getElementById('pump-init-data')?.dataset?.pumpId) || 0;
    makeAnnotationsDraggable('chartWarman', wc.layout.annotations, _pumpId);
  }

  const showOther = document.getElementById('chkShowOther')?.checked || false;
  setVis(document.getElementById('standalonePanels'), showOther);
  setVis(document.getElementById('otherGraphsOptions'), showOther);

  if (showOther && curveData) {
    const showEff = document.getElementById('chkShowEff')?.checked || false;
    const showPower = document.getElementById('chkShowPower')?.checked || false;
    const showNpsh = document.getElementById('chkShowNpsh')?.checked || false;
    const combineEffPower = document.getElementById('chkCombineEffPower')?.checked || false;

    const showClean = curveData.liquid !== 'water';

    // Toggle panels
    setVis(document.getElementById('panelEffPower'), showEff && showPower && combineEffPower);
    setVis(document.getElementById('panelEff'), showEff && (!showPower || !combineEffPower));
    setVis(document.getElementById('panelPower'), showPower && (!showEff || !combineEffPower));
    setVis(document.getElementById('panelNpsh'), showNpsh);

    // Check pump ID so we know which pump's label positions to save in database
    const currentPumpId = parseInt(document.getElementById('pump-init-data')?.dataset?.pumpId) || 0;

    if (showEff && showPower && combineEffPower) {
      const effPow = buildEffPowerChart(warmanData, curveData, showClean);
      effPow.layout.xaxis.title = `Flow Q (${labelQ})`;
      effPow.layout.yaxis.title = 'Efficiency (%)';
      effPow.layout.yaxis2.title = `Shaft Power P (${labelPow})`;
      Plotly.react('chartEffPower', effPow.traces, effPow.layout, PLOTLY_CONFIG);
      Plotly.Plots.resize('chartEffPower');

      if (effPow.layout.annotations && effPow.layout.annotations.length > 0) {
        makeAnnotationsDraggable('chartEffPower', effPow.layout.annotations, currentPumpId);
      }
    } else {
      if (showEff) {
        const eff = buildEffChart(warmanData, curveData, showClean);
        eff.layout.xaxis.title = `Flow Q (${labelQ})`;
        eff.layout.yaxis.title = 'Efficiency (%)';
        Plotly.react('chartEff', eff.traces, eff.layout, PLOTLY_CONFIG);
        Plotly.Plots.resize('chartEff');

        if (eff.layout.annotations && eff.layout.annotations.length > 0) {
          makeAnnotationsDraggable('chartEff', eff.layout.annotations, currentPumpId);
        }
      }
      if (showPower) {
        const power = buildPowerChart(warmanData, curveData, showClean);
        power.layout.xaxis.title = `Flow Q (${labelQ})`;
        power.layout.yaxis.title = `Shaft Power P (${labelPow})`;
        Plotly.react('chartPower', power.traces, power.layout, PLOTLY_CONFIG);
        Plotly.Plots.resize('chartPower');

        if (power.layout.annotations && power.layout.annotations.length > 0) {
          makeAnnotationsDraggable('chartPower', power.layout.annotations, currentPumpId);
        }
      }
    }

    if (showNpsh) {
      const npsh = buildNpshChart(warmanData, curveData);
      npsh.layout.xaxis.title = `Flow Q (${labelQ})`;
      npsh.layout.yaxis.title = `NPSHr (${labelNpsh})`;
      Plotly.react('chartNpsh', npsh.traces, npsh.layout, PLOTLY_CONFIG);
      Plotly.Plots.resize('chartNpsh');

      if (npsh.layout.annotations && npsh.layout.annotations.length > 0) {
        makeAnnotationsDraggable('chartNpsh', npsh.layout.annotations, currentPumpId);
      }
    }
  }
}

function buildPreviewCharts(d, q_h_si, q_eta_si, q_npsh_si) {
  if (d) lastFitResults = d;
  refreshPreviewCharts();
}

function refreshCoeffDisplay(d) {
  const fields = ['hq_a0', 'hq_a1', 'hq_a2', 'hq_a3',
    'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3',
    'npsh_c0', 'npsh_c1', 'npsh_c2',
    'pow_p0', 'pow_p1', 'pow_p2'];
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

  // Evaluate polynomials at 6 representative flow points (SI units)
  const a = [pumpData.hq_a0, pumpData.hq_a1, pumpData.hq_a2, pumpData.hq_a3];
  const b = [pumpData.eff_b0, pumpData.eff_b1, pumpData.eff_b2, pumpData.eff_b3];
  const c = [pumpData.npsh_c0, pumpData.npsh_c1, pumpData.npsh_c2];
  const pp = [pumpData.pow_p0, pumpData.pow_p1, pumpData.pow_p2];

  const evalP = (coeffs, q) => coeffs.reduce((s, cv, i) => s + cv * Math.pow(q, i), 0);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  const flowPts = [0, qMax * 0.25, qBep * 0.7, qBep, qMax * 0.8, qMax].map(q => Math.round(q * 10) / 10);
  const tbody = document.querySelector('#perfTable tbody');
  tbody.innerHTML = '';

  // Read current display units (already pre-selected by server-side template)
  const unitQ = document.getElementById('unit-q')?.value || 'm3h';
  const unitH = document.getElementById('unit-h')?.value || 'm';
  const unitNpsh = document.getElementById('unit-npsh')?.value || 'm';
  const unitPow = document.getElementById('unit-pow')?.value || 'kw';

  const fQ = CONVERSIONS.q[unitQ];
  const fH = CONVERSIONS.h[unitH];
  const fNpsh = CONVERSIONS.npsh[unitNpsh];
  const fPow = CONVERSIONS.pow[unitPow];

  flowPts.forEach(q => {
    const H = Math.max(0, evalP(a, q));
    const eta = clamp(evalP(b, q), 0, 100);
    const npsh = Math.max(0, evalP(c, q));
    const pow = Math.max(0, evalP(pp, q));
    const row = document.createElement('tr');
    row.className = 'hover:bg-[#1c2330]/50 transition-colors border-b border-[#30363d]/40';
    // Display values are converted from SI to the selected unit
    row.innerHTML = `
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-q" step="any" value="${(q * fQ).toFixed(3)}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-h" step="any" value="${H > 0 ? (H * fH).toFixed(3) : ''}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-eta" step="any" min="0" max="100" value="${eta > 0 ? eta.toFixed(1) : ''}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-npsh" step="any" value="${npsh > 0 ? (npsh * fNpsh).toFixed(3) : ''}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-pow" step="any" value="${pow > 0 ? (pow * fPow).toFixed(3) : ''}"></td>
      <td class="p-1.5 text-center"><button type="button" class="text-[#8b949e] hover:text-red-400 hover:bg-red-950/30 p-1.5 rounded transition-colors text-xs font-medium" onclick="removeRow(this)" title="Delete Row"><i class="bi bi-trash text-sm"></i></button></td>`;
    tbody.appendChild(row);
  });

  // Populate op-range inputs with values already stored in selected op-range unit
  const unitOpQ = document.getElementById('unit-op-q')?.value || 'm3h';
  const fOpQ = CONVERSIONS.q[unitOpQ];
  const opQMinEl = document.querySelector('[name="q_min"]');
  const opQMaxEl = document.querySelector('[name="q_max"]');
  const opQBepEl = document.querySelector('[name="q_bep"]');
  if (opQMinEl && pumpData.q_min != null) opQMinEl.value = (pumpData.q_min * fOpQ).toFixed(2);
  if (opQMaxEl && pumpData.q_max != null) opQMaxEl.value = (pumpData.q_max * fOpQ).toFixed(2);
  if (opQBepEl && pumpData.q_bep != null) opQBepEl.value = (pumpData.q_bep * fOpQ).toFixed(2);
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
    { q: 0, hNote: `Shutoff (${labelH})`, etaNote: '' },
    { q: '', hNote: `H (${labelH})`, etaNote: '25% load' },
    { q: '', hNote: `BEP (${labelH})`, etaNote: 'BEP (peak η)' },
    { q: '', hNote: `H (${labelH})`, etaNote: '' },
    { q: '', hNote: `H (${labelH})`, etaNote: '' },
    { q: '', hNote: `Runout (${labelH})`, etaNote: '' },
  ];
  suggestions.forEach(s => {
    const row = document.createElement('tr');
    row.className = 'hover:bg-[#1c2330]/50 transition-colors border-b border-[#30363d]/40';
    row.innerHTML = `
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-q" step="any" value="${s.q}" placeholder="Q (${labelQ})"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-h" step="any" placeholder="${s.hNote}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-eta" step="any" min="0" max="100" placeholder="${s.etaNote || 'η %'}"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-npsh" step="any" placeholder="NPSHr (${labelNpsh})"></td>
      <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-pow" step="any" placeholder="${labelPow} (opt)"></td>
      <td class="p-1.5 text-center"><button type="button" class="text-[#8b949e] hover:text-red-400 hover:bg-red-950/30 p-1.5 rounded transition-colors text-xs font-medium" onclick="removeRow(this)" title="Delete Row"><i class="bi bi-trash text-sm"></i></button></td>`;
    tbody.appendChild(row);
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   EXTRA CURVES MODULE
   Each additional curve is a self-contained mini performance table with
   its own Fit & Preview, label, color, and power auto-calc.
   All fitted curves are serialised to JSON in a hidden form field on submit.
   ══════════════════════════════════════════════════════════════════════════ */

var EXTRA_CURVE_COLORS = [
  '#58a6ff', '#3fb950', '#f0c040', '#f85149', '#bc8cff', '#39d3c0', '#ff9900', '#e879f9'
];

var _extraCurveIdCounter = 0;
var extraCurves = [];   // [{id, label, color, fitted, coeffs}]

function sanitizeHexColor(val, fallback = '#3fb950') {
  if (!val || typeof val !== 'string') return fallback;
  if (val.includes(';')) {
    const parts = val.split(';');
    for (const p of parts) {
      const trimmed = p.trim();
      if (trimmed.startsWith('#')) {
        val = trimmed;
        break;
      }
    }
  }
  val = val.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(val)) return val;
  if (/^[0-9a-fA-F]{6}$/.test(val)) return '#' + val;
  return fallback;
}

/* ── Serialise all extra curves to hidden form fields ─────────────────── */
function serializeExtraCurves() {
  const cardEntries = document.querySelectorAll('#extraCurvesList .custom-curve-entry');

  // Group separated curve columns
  const mainLblInp = document.getElementById('main_curve_label');
  const mainLbl = mainLblInp && mainLblInp.value.trim() ? mainLblInp.value.trim() : 'Curve 1';

  const mainDiaInp = document.getElementById('main_curve_dia_mm') || document.querySelector('[name="impeller_dia_val"]') || document.querySelector('[name="impeller_dia_mm"]');
  const mainDia = mainDiaInp && mainDiaInp.value ? mainDiaInp.value.trim() : (mainDiaInp?.placeholder || '');

  const labels = [mainLbl];
  const mainDiaUnit = document.getElementById('main_curve_dia_unit')?.value || 'mm';
  const diasUnits = [mainDia ? `${mainDia};${mainDiaUnit}` : `;${mainDiaUnit}`];
  const colors = ['#58a6ff'];
  const modes = ['fit'];
  const unitsList = [`${document.getElementById('unit-q')?.value || 'm3h'},${document.getElementById('unit-h')?.value || 'm'},${document.getElementById('unit-npsh')?.value || 'm'},${document.getElementById('unit-pow')?.value || 'kw'}`];

  // Main raw table
  const mainRows = document.querySelectorAll('#perfTable tbody tr');
  const mainRaw = [];
  mainRows.forEach(r => {
    const q = r.querySelector('.col-q')?.value ?? '';
    const h = r.querySelector('.col-h')?.value ?? '';
    const eta = r.querySelector('.col-eta')?.value ?? '';
    const npsh = r.querySelector('.col-npsh')?.value ?? '';
    const pow = r.querySelector('.col-pow')?.value ?? '';
    mainRaw.push(`${q},${h},${eta},${npsh},${pow}`);
  });
  const rawTables = [mainRaw.join(';')];

  // Main coeffs (24 terms: a0..a5, b0..b5, c0..c5, p0..p5, q_max, q_bep)
  const getF = n => document.querySelector(`[name="${n}"]`)?.value || '0';
  const mainCoeffsStr = `${getF('hq_a0')},${getF('hq_a1')},${getF('hq_a2')},${getF('hq_a3')},${getF('hq_a4')},${getF('hq_a5')},${getF('eff_b0')},${getF('eff_b1')},${getF('eff_b2')},${getF('eff_b3')},${getF('eff_b4')},${getF('eff_b5')},${getF('npsh_c0')},${getF('npsh_c1')},${getF('npsh_c2')},${getF('npsh_c3')},${getF('npsh_c4')},${getF('npsh_c5')},${getF('pow_p0')},${getF('pow_p1')},${getF('pow_p2')},${getF('pow_p3')},${getF('pow_p4')},${getF('pow_p5')},${getF('q_max')},${getF('q_bep')}`;
  const coeffsList = [mainCoeffsStr];

  const payload = [];

  cardEntries.forEach((entry, idx) => {
    const eid = entry.id ? entry.id.replace('extra-entry-', '') : '';
    const inMemCurve = extraCurves.find(c => String(c.id) === String(eid)) || {};

    const labelInp = entry.querySelector('.extra-label-input');
    const label = labelInp && labelInp.value.trim() !== '' ? labelInp.value.trim() : (inMemCurve.label || `Curve ${idx + 2}`);

    const diaInp = entry.querySelector('.extra-dia-input');
    const diameter = diaInp && diaInp.value.trim() !== '' ? diaInp.value.trim() : (inMemCurve.diameter ?? '');

    const unitDia = entry.querySelector('.unit-select-dia')?.value || inMemCurve.unit_dia || 'mm';
    const curveMode = entry.querySelector('.unit-select-mode')?.value || inMemCurve.curve_mode || 'fit';
    const unitQ = entry.querySelector('.unit-select-q')?.value || inMemCurve.unit_q || 'm3h';
    const unitH = entry.querySelector('.unit-select-h')?.value || inMemCurve.unit_h || 'm';
    const unitNpsh = entry.querySelector('.unit-select-npsh')?.value || inMemCurve.unit_npsh || 'm';
    const unitPow = entry.querySelector('.unit-select-pow')?.value || inMemCurve.unit_pow || 'kw';

    const styleMode = entry.querySelector('.unit-select-style-mode')?.value || inMemCurve.style_mode || 'graph';
    const useCustomStyle = styleMode === 'custom';
    const colorPickerVal = entry.querySelector('.extra-color-picker')?.value;
    const activeSwatch = entry.querySelector('.curve-color-swatch.active');
    const colorDot = entry.querySelector('.curve-color-dot');
    const rawColor = colorPickerVal || activeSwatch?.dataset?.color || colorDot?.style?.backgroundColor || inMemCurve.color;
    const color = sanitizeHexColor(rawColor, '#3fb950');
    const weight = parseFloat(entry.querySelector('.extra-weight-select')?.value) || inMemCurve.weight || 2.0;
    const style = entry.querySelector('.extra-line-style-select')?.value || inMemCurve.style || 'solid';

    const tableRows = entry.querySelectorAll('table tbody tr');
    const raw_table = [];
    tableRows.forEach(tr => {
      const q = tr.querySelector('.col-q')?.value ?? '';
      const h = tr.querySelector('.col-h')?.value ?? '';
      const eta = tr.querySelector('.col-eta')?.value ?? '';
      const npsh = tr.querySelector('.col-npsh')?.value ?? '';
      const pow = tr.querySelector('.col-pow')?.value ?? '';
      if (q !== '' || h !== '' || eta !== '' || npsh !== '' || pow !== '') {
        raw_table.push([q, h, eta, npsh, pow]);
      }
    });

    // Update in-memory curve object properties
    inMemCurve.label = label;
    inMemCurve.diameter = diameter;
    inMemCurve.unit_dia = unitDia;
    inMemCurve.unit_q = unitQ;
    inMemCurve.unit_h = unitH;
    inMemCurve.unit_npsh = unitNpsh;
    inMemCurve.unit_pow = unitPow;
    inMemCurve.curve_mode = curveMode;
    inMemCurve.style_mode = styleMode;
    inMemCurve.use_custom_style = useCustomStyle;
    inMemCurve.color = color;
    inMemCurve.weight = weight;
    inMemCurve.style = style;
    if (raw_table.length > 0) inMemCurve.raw_table = raw_table;

    labels.push(label);
    diasUnits.push(`${diameter};${unitDia}`);
    colors.push(sanitizeHexColor(color, '#3fb950'));
    modes.push(curveMode);
    unitsList.push(`${unitQ},${unitH},${unitNpsh},${unitPow}`);
    rawTables.push(raw_table.map(r => r.join(',')).join(';'));

    const getCF = f => {
      const el = entry.querySelector(`.extra-cf-${f}`);
      return el && el.value.trim() !== '' ? el.value.trim() : (inMemCurve.coeffs?.[f] ?? '0');
    };
    const cCoeffsStr = `${getCF('hq_a0')},${getCF('hq_a1')},${getCF('hq_a2')},${getCF('hq_a3')},${getCF('hq_a4')},${getCF('hq_a5')},${getCF('eff_b0')},${getCF('eff_b1')},${getCF('eff_b2')},${getCF('eff_b3')},${getCF('eff_b4')},${getCF('eff_b5')},${getCF('npsh_c0')},${getCF('npsh_c1')},${getCF('npsh_c2')},${getCF('npsh_c3')},${getCF('npsh_c4')},${getCF('npsh_c5')},${getCF('pow_p0')},${getCF('pow_p1')},${getCF('pow_p2')},${getCF('pow_p3')},${getCF('pow_p4')},${getCF('pow_p5')},${getCF('q_max')},${getCF('q_bep')}`;
    coeffsList.push(cCoeffsStr);

    payload.push({
      label, color, diameter, unit_dia: unitDia, curve_mode: curveMode,
      unit_q: unitQ, unit_h: unitH, unit_npsh: unitNpsh, unit_pow: unitPow,
      style_mode: styleMode, use_custom_style: useCustomStyle, weight, style,
      raw_table: raw_table.length > 0 ? raw_table : (inMemCurve.raw_table || [])
    });
  });

  if (document.getElementById('curve_labels_field')) document.getElementById('curve_labels_field').value = labels.join(';');
  if (document.getElementById('curve_diameters_field')) document.getElementById('curve_diameters_field').value = diasUnits.join('|');
  if (document.getElementById('curve_colors_field')) document.getElementById('curve_colors_field').value = colors.join(';');
  if (document.getElementById('curve_modes_field')) document.getElementById('curve_modes_field').value = modes.join(';');
  if (document.getElementById('curve_units_field')) document.getElementById('curve_units_field').value = unitsList.join('|');
  if (document.getElementById('curve_raw_tables_field')) document.getElementById('curve_raw_tables_field').value = rawTables.join('|');
  if (document.getElementById('curve_coeffs_field')) document.getElementById('curve_coeffs_field').value = coeffsList.join('|');

  const jsonStr = JSON.stringify(payload);
  let hdnJson = document.getElementById('extra_curves_json_field');
  if (!hdnJson) {
    hdnJson = document.createElement('input');
    hdnJson.type = 'hidden';
    hdnJson.name = 'extra_curves_json';
    hdnJson.id = 'extra_curves_json_field';
    const form = document.getElementById('pumpForm');
    if (form) form.appendChild(hdnJson);
  }
  hdnJson.value = jsonStr;

  return payload;
}

/* ── Update badge count ──────────────────────────────────────────────────── */
function updateExtraBadge() {
  const badge = document.getElementById('extraCurveBadge');
  if (!badge) return;
  const n = extraCurves.length;
  badge.textContent = n;
  if (n > 0) {
    badge.classList.remove('hidden');
    badge.style.display = 'inline-block';
  } else {
    badge.classList.add('hidden');
    badge.style.display = 'none';
  }
}

/* ── Extract data from an extra curve table ──────────────────────────────── */
function getExtraTableData(tableId, curveId) {
  const rows = document.querySelectorAll(`#${tableId} tbody tr`);
  const q_h = [], q_eta = [], q_p = [];
  const entry = document.getElementById(`extra-entry-${curveId}`);
  const unitQ = entry?.querySelector(`.unit-select-q`)?.value || 'm3h';
  const unitH = entry?.querySelector(`.unit-select-h`)?.value || 'm';
  const unitPow = entry?.querySelector(`.unit-select-pow`)?.value || 'kw';

  rows.forEach(row => {
    let q = parseFloat(row.querySelector('.col-q')?.value);
    let h = parseFloat(row.querySelector('.col-h')?.value);
    let eta = parseFloat(row.querySelector('.col-eta')?.value);
    let pow = parseFloat(row.querySelector('.col-pow')?.value);

    // Convert display values back to SI (m3h, m, kW)
    if (!isNaN(q)) q = q / CONVERSIONS.q[unitQ];
    if (!isNaN(h)) h = h / CONVERSIONS.h[unitH];
    if (!isNaN(pow)) pow = pow / CONVERSIONS.pow[unitPow];

    if (!isNaN(q) && !isNaN(h)) q_h.push([q, h]);
    if (!isNaN(q) && !isNaN(eta)) q_eta.push([q, eta]);
    if (!isNaN(q) && !isNaN(pow)) q_p.push([q, pow]);
  });
  return {
    q_h,
    q_eta: q_eta.length >= 3 ? q_eta : null,
    q_p: q_p.length >= 3 ? q_p : null,
  };
}

/* ── Build an HTML table row for an extra curve table ────────────────────── */
function _extraRow(qUnit, hUnit, npshUnit, powUnit) {
  const lblQ = getUnitLabel('q', qUnit);
  const lblH = getUnitLabel('h', hUnit);
  const lblNpsh = getUnitLabel('npsh', npshUnit);
  const lblPow = getUnitLabel('pow', powUnit);

  return `<tr class="hover:bg-[#1c2330]/50 transition-colors border-b border-[#30363d]/40">
    <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-q" step="any" placeholder="Q (${lblQ})"></td>
    <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-h" step="any" placeholder="H (${lblH})"></td>
    <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-eta" step="any" min="0" max="100" placeholder="η %"></td>
    <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-npsh" step="any" placeholder="NPSHr (${lblNpsh})"></td>
    <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-pow" step="any" placeholder="${lblPow} (opt)"></td>
    <td class="p-1.5 text-center"><button type="button" class="text-[#8b949e] hover:text-red-400 hover:bg-red-950/30 p-1.5 rounded transition-colors text-xs font-medium" onclick="removeRow(this)" title="Delete Row"><i class="bi bi-trash text-sm"></i></button></td>
  </tr>`;
}

function _autoUpdateExtraPowerInRow(row, curveId) {
  const entry = document.getElementById(`extra-entry-${curveId}`);
  if (!entry) return;
  const unitQ = entry.querySelector(`.unit-select-q`)?.value || 'm3h';
  const unitH = entry.querySelector(`.unit-select-h`)?.value || 'm';
  const unitPow = entry.querySelector(`.unit-select-pow`)?.value || 'kw';

  const qDisp = parseFloat(row.querySelector('.col-q')?.value);
  const hDisp = parseFloat(row.querySelector('.col-h')?.value);
  const etaDisp = parseFloat(row.querySelector('.col-eta')?.value);
  const powInput = row.querySelector('.col-pow');
  if (!powInput) return;

  // Convert display values back to SI
  const q_SI = isNaN(qDisp) ? NaN : qDisp / CONVERSIONS.q[unitQ];
  const h_SI = isNaN(hDisp) ? NaN : hDisp / CONVERSIONS.h[unitH];

  const p_kw = calcPowerKW(q_SI, h_SI, etaDisp);
  if (p_kw !== null) {
    // Convert kW → display unit
    const p_display = p_kw * CONVERSIONS.pow[unitPow];
    powInput.value = p_display.toFixed(2);
    powInput.classList.add('auto-calc-flash');
    setTimeout(() => powInput.classList.remove('auto-calc-flash'), 600);
  }
}

/* ── Wire power auto-calc on a single row ────────────────────────────────── */
function _wireExtraRow(row, curveId) {
  ['col-q', 'col-h', 'col-eta'].forEach(cls => {
    const inp = row.querySelector(`.${cls}`);
    if (inp) inp.addEventListener('input', () => _autoUpdateExtraPowerInRow(row, curveId));
  });
}

/* ── Fit an extra curve via /papi/fit-curves ─────────────────────────────── */
async function fitExtraCurve(curveId) {
  const curve = extraCurves.find(c => c.id === curveId);
  if (!curve) return;
  const entry = document.getElementById(`extra-entry-${curveId}`);
  const statusEl = entry.querySelector('.extra-curve-status');
  const fitBtn = entry.querySelector('.btn-extra-fit');
  const { q_h, q_eta, q_p } = getExtraTableData(`extraTable-${curveId}`, curveId);

  if (q_h.length < 3) {
    statusEl.className = 'extra-curve-status error';
    statusEl.textContent = '\u2717 Need at least 3 Q, H points';
    return;
  }

  statusEl.className = 'extra-curve-status busy';
  statusEl.textContent = '\u27f3 Fitting\u2026';
  fitBtn.disabled = true;

  // Beginners Note: Extract per-curve polynomial fitting order choices for extra curve fitting
  const poHq = document.getElementById('poly_order_hq')?.value || 3;
  const poEff = document.getElementById('poly_order_eff')?.value || 3;
  const poNpsh = document.getElementById('poly_order_npsh')?.value || 2;
  const poPow = document.getElementById('poly_order_pow')?.value || 2;

  const payload = {
    q_h,
    q_eta: q_eta || q_h.map(([q]) => [q, 70]),
    q_npsh: null,
    q_p: q_p || null,
    poly_order_hq: parseInt(poHq),
    poly_order_eff: parseInt(poEff),
    poly_order_npsh: parseInt(poNpsh),
    poly_order_pow: parseInt(poPow),
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
      hq_a0: d.hq_a0, hq_a1: d.hq_a1, hq_a2: d.hq_a2, hq_a3: d.hq_a3, hq_a4: d.hq_a4, hq_a5: d.hq_a5,
      eff_b0: d.eff_b0, eff_b1: d.eff_b1, eff_b2: d.eff_b2, eff_b3: d.eff_b3, eff_b4: d.eff_b4, eff_b5: d.eff_b5,
      npsh_c0: d.npsh_c0, npsh_c1: d.npsh_c1, npsh_c2: d.npsh_c2, npsh_c3: d.npsh_c3, npsh_c4: d.npsh_c4, npsh_c5: d.npsh_c5,
      pow_p0: d.pow_p0, pow_p1: d.pow_p1, pow_p2: d.pow_p2, pow_p3: d.pow_p3, pow_p4: d.pow_p4, pow_p5: d.pow_p5,
      q_max: d.q_max, q_bep: d.q_bep,
    };

    // Update DOM inputs inside the card's polynomial coefficients accordion
    const setCF = (f, val) => {
      const el = entry.querySelector(`.extra-cf-${f}`);
      if (el && val !== undefined) el.value = val;
    };
    setCF('hq_a0', d.hq_a0); setCF('hq_a1', d.hq_a1); setCF('hq_a2', d.hq_a2); setCF('hq_a3', d.hq_a3); setCF('hq_a4', d.hq_a4); setCF('hq_a5', d.hq_a5);
    setCF('eff_b0', d.eff_b0); setCF('eff_b1', d.eff_b1); setCF('eff_b2', d.eff_b2); setCF('eff_b3', d.eff_b3); setCF('eff_b4', d.eff_b4); setCF('eff_b5', d.eff_b5);
    setCF('npsh_c0', d.npsh_c0); setCF('npsh_c1', d.npsh_c1); setCF('npsh_c2', d.npsh_c2); setCF('npsh_c3', d.npsh_c3); setCF('npsh_c4', d.npsh_c4); setCF('npsh_c5', d.npsh_c5);
    setCF('pow_p0', d.pow_p0); setCF('pow_p1', d.pow_p1); setCF('pow_p2', d.pow_p2); setCF('pow_p3', d.pow_p3); setCF('pow_p4', d.pow_p4); setCF('pow_p5', d.pow_p5);

    updateExtraPolynomialUI(curveId);

    statusEl.className = 'extra-curve-status ok';
    statusEl.textContent =
      `\u2713 Fitted \u2014 H\u2080=${d.hq_a0.toFixed(1)} m, Q_max=${d.q_max.toFixed(1)}, \u03b7_BEP=${d.eta_bep}%`;

    // Make main preview visible and refresh it
    document.getElementById('curvePreview').style.display = 'block';
    refreshMainPreview();

    // Widen operating range if this curve's q_max exceeds current op q_max
    const opUnit = document.getElementById('unit-op-q')?.value || 'm3h';
    const opFactor = CONVERSIONS.q[opUnit];
    const opQMaxEl = document.querySelector('[name="q_max"]');
    if (opQMaxEl) {
      const currentQMax = parseFloat(opQMaxEl.value) || 0;
      const newQMaxDisplay = d.q_max * opFactor;
      if (newQMaxDisplay > currentQMax) {
        opQMaxEl.value = newQMaxDisplay.toFixed(2);
      }
    }

    serializeExtraCurves();

  } catch (e) {
    statusEl.className = 'extra-curve-status error';
    statusEl.textContent = `\u2717 Network error: ${e.message}`;
  } finally {
    fitBtn.disabled = false;
  }
}

function refreshMainPreview() {
  if (typeof refreshPreviewCharts === 'function') {
    refreshPreviewCharts();
  }
}

function _updateExtraPlaceholders(div, type, unit) {
  const inputs = div.querySelectorAll(`.col-${type}`);
  const label = getUnitLabel(type, unit);
  inputs.forEach(input => {
    if (type === 'q') {
      input.placeholder = `Q (${label})`;
    } else if (type === 'h') {
      const td = input.parentElement;
      const tr = td ? td.parentElement : null;
      const rowIndex = (tr && tr.parentElement) ? Array.from(tr.parentElement.children).indexOf(tr) : -1;
      if (rowIndex === 0) input.placeholder = `Shutoff (${label})`;
      else if (rowIndex === 2) input.placeholder = `BEP Head (${label})`;
      else if (rowIndex === 5) input.placeholder = `Runout (${label})`;
      else input.placeholder = `H (${label})`;
    } else if (type === 'npsh') {
      input.placeholder = `NPSHr (${label})`;
    } else if (type === 'pow') {
      input.placeholder = `${label} (opt)`;
    }
  });
}

/* ── Add a new extra curve card (optionally pre-filled with existingData) ── */
function addExtraCurveCard(existingData) {
  const id = ++_extraCurveIdCounter;
  const rawColor = existingData?.color || EXTRA_CURVE_COLORS[(id - 1) % EXTRA_CURVE_COLORS.length];
  const color = sanitizeHexColor(rawColor, EXTRA_CURVE_COLORS[(id - 1) % EXTRA_CURVE_COLORS.length]);
  const label = existingData?.label || `Curve ${id}`;
  const diameter = existingData?.diameter || '';
  const diaUnit = existingData?.unit_dia || 'mm';
  const curveMode = existingData?.curve_mode || 'fit';
  const styleMode = existingData?.style_mode || (existingData?.use_custom_style ? 'custom' : 'graph');
  const weight = existingData?.weight || 2.0;
  const style = existingData?.style || 'solid';

  const qUnit = existingData?.unit_q || document.getElementById('unit-q')?.value || 'm3h';
  const hUnit = existingData?.unit_h || document.getElementById('unit-h')?.value || 'm';
  const npshUnit = existingData?.unit_npsh || document.getElementById('unit-npsh')?.value || 'm';
  const powUnit = existingData?.unit_pow || document.getElementById('unit-pow')?.value || 'kw';

  extraCurves.push({
    id,
    label,
    color,
    diameter,
    unit_dia: diaUnit,
    curve_mode: curveMode,
    style_mode: styleMode,
    use_custom_style: styleMode === 'custom',
    weight,
    style,
    unit_q: qUnit,
    unit_h: hUnit,
    unit_npsh: npshUnit,
    unit_pow: powUnit,
    fitted: !!existingData,
    coeffs: existingData || null
  });

  const list = document.getElementById('extraCurvesList');
  const div = document.createElement('div');
  div.className = 'custom-curve-entry mb-4 bg-[#161b22] border border-[#30363d] rounded-lg shadow-sm overflow-hidden';
  div.id = `extra-entry-${id}`;

  let tableRowsHtml = '';
  if (existingData && Array.isArray(existingData.raw_table) && existingData.raw_table.length > 0) {
    const validRows = existingData.raw_table.filter(r => Array.isArray(r) && r.some(v => v !== undefined && v !== null && String(v).trim() !== ''));
    const rowsToRender = validRows.length > 0 ? validRows : existingData.raw_table;
    tableRowsHtml = rowsToRender.map(row => {
      const [q, h, eta, npsh, pow] = row;
      return `<tr class="hover:bg-[#1c2330]/50 transition-colors border-b border-[#30363d]/40">
        <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-q" step="any" placeholder="Q (${getUnitLabel('q', qUnit)})" value="${q !== undefined && q !== null ? q : ''}"></td>
        <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-h" step="any" placeholder="H (${getUnitLabel('h', hUnit)})" value="${h !== undefined && h !== null ? h : ''}"></td>
        <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-eta" step="any" min="0" max="100" placeholder="η %" value="${eta !== undefined && eta !== null ? eta : ''}"></td>
        <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-npsh" step="any" placeholder="NPSHr (${getUnitLabel('npsh', npshUnit)})" value="${npsh !== undefined && npsh !== null ? npsh : ''}"></td>
        <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-pow" step="any" placeholder="${getUnitLabel('pow', powUnit)} (opt)" value="${pow !== undefined && pow !== null ? pow : ''}"></td>
        <td class="p-1.5 text-center"><button type="button" class="text-[#8b949e] hover:text-red-400 hover:bg-red-950/30 p-1.5 rounded transition-colors text-xs font-medium" onclick="removeRow(this)" title="Delete Row"><i class="bi bi-trash text-sm"></i></button></td>
      </tr>`;
    }).join('');
  } else {
    tableRowsHtml = Array.from({ length: 6 }, () => _extraRow(qUnit, hUnit, npshUnit, powUnit)).join('');
  }

  const famType = document.getElementById('selFamilyType')?.value || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');

  div.innerHTML = `
    <div onclick="toggleCard('extraCardBody-${id}', 'extraCardChevron-${id}')"
         class="px-4 py-3 bg-[#1c2330] border-b border-[#30363d] cursor-pointer select-none hover:bg-slate-800/60 transition-colors space-y-2.5">
      <!-- Row 1: Title, Identity Fields, Remove Button, and Far-Right Chevron -->
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-2 font-semibold text-[#e6edf3] text-sm">
          <span class="curve-color-dot inline-block w-3 h-3 rounded-full" style="background:${color}"></span>
          <span>Additional Curve</span>
        </div>

        <div class="flex items-center gap-2 text-xs ml-auto">
          <div class="flex items-center gap-2" onclick="event.stopPropagation()">
            <span class="text-[#8b949e] font-medium">Label:</span>
            <input type="text" class="bg-[#0d1117] border border-[#30363d] rounded px-2.5 py-1 text-xs text-[#e6edf3] font-semibold w-36 focus:outline-none focus:border-[#58a6ff] extra-label-input"
                   value="${label}" placeholder="Curve label" data-eid="${id}">
            <span class="text-[#8b949e] font-medium ms-1 extra-dia-label">${isVarSpeed ? 'Speed:' : 'Dia:'}</span>
            <input type="number" class="bg-[#0d1117] border border-[#30363d] rounded px-2.5 py-1 text-xs text-[#e6edf3] w-24 focus:outline-none focus:border-[#58a6ff] extra-dia-input" step="any"
                   value="${diameter}" placeholder="${isVarSpeed ? 'e.g. 1200' : 'e.g. 280'}" data-eid="${id}">
            <select class="header-unit-select unit-select-dia bg-[#0d1117] border border-[#30363d] text-[#c9d1d9] text-[11px] rounded px-1.5 py-1 focus:outline-none" data-eid="${id}">
              ${isVarSpeed
                ? `<option value="rpm" ${diaUnit === 'rpm' || diaUnit === 'mm' ? 'selected' : ''}>RPM</option><option value="hz" ${diaUnit === 'hz' ? 'selected' : ''}>Hz</option><option value="percent" ${diaUnit === 'percent' ? 'selected' : ''}>%</option>`
                : `<option value="mm" ${diaUnit === 'mm' ? 'selected' : ''}>mm</option><option value="in" ${diaUnit === 'in' ? 'selected' : ''}>in</option><option value="m" ${diaUnit === 'm' ? 'selected' : ''}>m</option>`
              }
            </select>
            <button type="button" class="btn-extra-remove extra-btn-remove inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs border border-red-700/40 text-red-400 hover:bg-red-900/20 transition-colors ms-1" data-eid="${id}">
              <i class="bi bi-trash text-xs"></i>Remove
            </button>
          </div>
          <i class="bi bi-chevron-down text-[#8b949e] hover:text-white transition-transform duration-200 ms-2 p-1 cursor-pointer"
             id="extraCardChevron-${id}"
             onclick="toggleCard('extraCardBody-${id}', 'extraCardChevron-${id}'); event.stopPropagation();"
             style="transform: rotate(180deg)"></i>
        </div>
      </div>

      <!-- Row 2: Custom Curve Line Style Bar (Below Row 1) -->
      <div class="flex items-center gap-2 text-xs pt-2 border-t border-[#30363d]/60" onclick="event.stopPropagation()">
        <span class="text-[#8b949e] font-medium flex items-center gap-1">
          <i class="bi bi-palette text-[#58a6ff]"></i>Line Style:
        </span>
        <select class="header-unit-select unit-select-style-mode bg-[#0d1117] border border-[#30363d] text-[#c9d1d9] text-[11px] rounded px-2 py-1 focus:outline-none" data-eid="${id}">
          <option value="graph" ${styleMode === 'graph' ? 'selected' : ''}>Default Palette</option>
          <option value="custom" ${styleMode === 'custom' ? 'selected' : ''}>Custom Style</option>
        </select>
        <div id="extra-custom-controls-${id}" class="extra-custom-controls items-center gap-2 bg-[#0d1117] border border-[#30363d] px-2 py-0.5 rounded ${styleMode === 'custom' ? 'inline-flex' : 'hidden'}">
          <input type="color" class="extra-color-picker bg-transparent h-5 w-6 p-0 border-0 cursor-pointer rounded" value="${color}" data-eid="${id}" title="Curve Color">
          <select class="extra-weight-select bg-[#161b22] border border-[#30363d] text-[#c9d1d9] text-[11px] rounded px-1.5 py-0.5 focus:outline-none" data-eid="${id}" title="Line Weight">
            <option value="1" ${String(weight) === '1' ? 'selected' : ''}>1 px</option>
            <option value="1.5" ${String(weight) === '1.5' ? 'selected' : ''}>1.5 px</option>
            <option value="2" ${String(weight) === '2' ? 'selected' : ''}>2 px</option>
            <option value="2.5" ${String(weight) === '2.5' ? 'selected' : ''}>2.5 px</option>
            <option value="3" ${String(weight) === '3' ? 'selected' : ''}>3 px</option>
            <option value="4" ${String(weight) === '4' ? 'selected' : ''}>4 px</option>
          </select>
          <select class="extra-line-style-select bg-[#161b22] border border-[#30363d] text-[#c9d1d9] text-[11px] rounded px-1.5 py-0.5 focus:outline-none" data-eid="${id}" title="Line Style">
            <option value="solid" ${style === 'solid' ? 'selected' : ''}>Solid</option>
            <option value="dash" ${style === 'dash' ? 'selected' : ''}>Dashed</option>
            <option value="dot" ${style === 'dot' ? 'selected' : ''}>Dotted</option>
            <option value="dashdot" ${style === 'dashdot' ? 'selected' : ''}>DashDot</option>
            <option value="longdash" ${style === 'longdash' ? 'selected' : ''}>LongDash</option>
          </select>
        </div>
      </div>
    </div>

      <div class="p-4" id="extraCardBody-${id}">
        <select class="unit-select-mode" data-eid="${id}" style="display:none">
          <option value="fit" ${curveMode === 'fit' ? 'selected' : ''}>Fitted</option>
          <option value="affinity" ${curveMode === 'affinity' ? 'selected' : ''}>Affinity</option>
          <option value="both" ${curveMode === 'both' ? 'selected' : ''}>Both</option>
        </select>

        <div class="overflow-x-auto mb-3 rounded-lg border border-[#30363d] bg-[#0d1117]">
          <table class="w-full text-xs text-[#c9d1d9] border-collapse" id="extraTable-${id}">
            <thead>
              <tr class="bg-[#161b22] text-[#8b949e] border-b border-[#30363d] font-semibold text-[11px] tracking-wide">
                <th class="p-2.5 text-left w-32">
                  <div class="flex items-center justify-between gap-1">
                    <span>Flow Q</span>
                    <select class="header-unit-select unit-select-q bg-[#0d1117] border border-[#30363d] text-[#58a6ff] text-[11px] font-semibold rounded px-1.5 py-0.5 focus:outline-none focus:border-[#58a6ff]" data-eid="${id}">
                      <option value="m3h" ${qUnit === 'm3h' ? 'selected' : ''}>m³/h</option>
                      <option value="ls" ${qUnit === 'ls' ? 'selected' : ''}>L/s</option>
                      <option value="gpm" ${qUnit === 'gpm' ? 'selected' : ''}>gpm</option>
                      <option value="lmin" ${qUnit === 'lmin' ? 'selected' : ''}>L/min</option>
                    </select>
                  </div>
                </th>
                <th class="p-2.5 text-left w-28">
                  <div class="flex items-center justify-between gap-1">
                    <span>Head H</span>
                    <select class="header-unit-select unit-select-h bg-[#0d1117] border border-[#30363d] text-[#58a6ff] text-[11px] font-semibold rounded px-1.5 py-0.5 focus:outline-none focus:border-[#58a6ff]" data-eid="${id}">
                      <option value="m" ${hUnit === 'm' ? 'selected' : ''}>m</option>
                      <option value="ft" ${hUnit === 'ft' ? 'selected' : ''}>ft</option>
                    </select>
                  </div>
                </th>
                <th class="p-2.5 text-left w-24">
                  <span>Effic. η (%)</span>
                </th>
                <th class="p-2.5 text-left w-28">
                  <div class="flex items-center justify-between gap-1">
                    <span>NPSHr</span>
                    <select class="header-unit-select unit-select-npsh bg-[#0d1117] border border-[#30363d] text-[#58a6ff] text-[11px] font-semibold rounded px-1.5 py-0.5 focus:outline-none focus:border-[#58a6ff]" data-eid="${id}">
                      <option value="m" ${npshUnit === 'm' ? 'selected' : ''}>m</option>
                      <option value="ft" ${npshUnit === 'ft' ? 'selected' : ''}>ft</option>
                    </select>
                  </div>
                </th>
                <th class="p-2.5 text-left w-28">
                  <div class="flex items-center justify-between gap-1">
                    <span>Power</span>
                    <select class="header-unit-select unit-select-pow bg-[#0d1117] border border-[#30363d] text-[#58a6ff] text-[11px] font-semibold rounded px-1.5 py-0.5 focus:outline-none focus:border-[#58a6ff]" data-eid="${id}">
                      <option value="kw" ${powUnit === 'kw' ? 'selected' : ''}>kW</option>
                      <option value="hp" ${powUnit === 'hp' ? 'selected' : ''}>hp</option>
                    </select>
                  </div>
                </th>
                <th class="p-2.5 text-center w-8"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#30363d]/50">${tableRowsHtml}</tbody>
      </table>
    </div>

    <div class="flex gap-2 items-center mb-2 flex-wrap">
      <button type="button" class="extra-btn-add-row btn-extra-add-row inline-flex items-center gap-1 px-2 py-1 rounded text-xs border border-[#30363d] text-[#c9d1d9] hover:bg-slate-800 transition-colors" data-eid="${id}">
        <i class="bi bi-plus-lg mr-1"></i>Add Row
      </button>
      <button type="button" class="extra-btn-import btn-extra-import-file inline-flex items-center gap-1 px-2 py-1 rounded text-xs border border-[#58a6ff]/40 text-[#58a6ff] hover:bg-[#58a6ff]/10 transition-colors" data-eid="${id}">
        <i class="bi bi-file-earmark-arrow-up mr-1"></i>Import File
      </button>
      <input type="file" class="extra-file-input-${id}" style="display:none" accept=".csv,.txt,.dat">
      
      <!-- Inline Calculation Mode Radio Group -->
      <div class="inline-flex items-center gap-2 ml-auto p-1 px-2 rounded border border-[#30363d]" style="font-size:0.78rem;background:#161b22">
        <span class="text-[#58a6ff] font-semibold">Method:</span>
        <label class="inline-flex items-center gap-1 text-xs cursor-pointer text-[#c9d1d9]" style="margin-bottom:0;">
          <input class="extra-mode-radio" type="radio" name="extra_mode_${id}" id="extra_mode_fit_${id}" value="fit" ${curveMode === 'fit' ? 'checked' : ''} data-eid="${id}" style="accent-color:#58a6ff;">
          <span>Fitted</span>
        </label>
        <label class="inline-flex items-center gap-1 text-xs cursor-pointer text-[#c9d1d9]" style="margin-bottom:0;">
          <input class="extra-mode-radio" type="radio" name="extra_mode_${id}" id="extra_mode_affinity_${id}" value="affinity" ${curveMode === 'affinity' ? 'checked' : ''} data-eid="${id}" style="accent-color:#58a6ff;">
          <span>Affinity</span>
        </label>
        <label class="inline-flex items-center gap-1 text-xs cursor-pointer text-[#c9d1d9]" style="margin-bottom:0;">
          <input class="extra-mode-radio" type="radio" name="extra_mode_${id}" id="extra_mode_both_${id}" value="both" ${curveMode === 'both' ? 'checked' : ''} data-eid="${id}" style="accent-color:#58a6ff;">
          <span>Both</span>
        </label>
      </div>

      <button type="button" class="extra-btn-fit btn-extra-fit inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-semibold transition-colors" style="background:#58a6ff;color:#0d1117;" data-eid="${id}">
        <i class="bi bi-calculator mr-1"></i>Fit &amp; Preview
      </button>
    </div>

    <div class="extra-curve-status mb-2" id="extra-status-${id}"></div>

    <!-- Polynomial Coefficients Accordion -->
    <div class="card-dark border border-[#30363d] mt-2 rounded">
      <div class="flex justify-between items-center py-1 px-2 bg-[#1c2330] border-b border-[#30363d] cursor-pointer hover:bg-slate-800/60 transition-colors" style="cursor:pointer" onclick="this.nextElementSibling.classList.toggle('hidden')">
        <span class="text-xs font-semibold"><i class="bi bi-chevron-down mr-1"></i>Polynomial Coefficients <span class="text-[#8b949e] font-normal">(auto-filled by Fit or entered manually)</span></span>
        <span style="font-size:0.7rem;background:rgba(88,166,255,0.15);color:#58a6ff;padding:1px 6px;border-radius:4px;">Polynomials</span>
      </div>
      <div class="hidden" id="extraCoeffPanel_${id}">
        <div class="p-2" style="font-size:0.8rem">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            <!-- H-Q -->
            <div>
              <div class="p-1 px-2 rounded" style="background:#161b22;border:1px solid #30363d">
                <div class="text-[#58a6ff] font-semibold mb-1 extra-eq-title-hq" style="font-size:0.75rem"><i class="bi bi-graph-down-arrow mr-1"></i>H-Q: H = a₀ + a₁Q + a₂Q² + a₃Q³</div>
                <div class="grid grid-cols-3 gap-1">
                  <div id="extra-wrap-hq_a0-${id}"><label class="block text-[10px] text-[#8b949e]">a₀</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-hq_a0" data-eid="${id}" step="any" value="${existingData?.hq_a0 ?? 0}"></div>
                  <div id="extra-wrap-hq_a1-${id}"><label class="block text-[10px] text-[#8b949e]">a₁</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-hq_a1" data-eid="${id}" step="any" value="${existingData?.hq_a1 ?? 0}"></div>
                  <div id="extra-wrap-hq_a2-${id}"><label class="block text-[10px] text-[#8b949e]">a₂</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-hq_a2" data-eid="${id}" step="any" value="${existingData?.hq_a2 ?? 0}"></div>
                  <div id="extra-wrap-hq_a3-${id}"><label class="block text-[10px] text-[#8b949e]">a₃</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-hq_a3" data-eid="${id}" step="any" value="${existingData?.hq_a3 ?? 0}"></div>
                  <div id="extra-wrap-hq_a4-${id}"><label class="block text-[10px] text-[#8b949e]">a₄</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-hq_a4" data-eid="${id}" step="any" value="${existingData?.hq_a4 ?? 0}"></div>
                  <div id="extra-wrap-hq_a5-${id}"><label class="block text-[10px] text-[#8b949e]">a₅</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-hq_a5" data-eid="${id}" step="any" value="${existingData?.hq_a5 ?? 0}"></div>
                </div>
              </div>
            </div>
            <!-- Efficiency -->
            <div>
              <div class="p-1 px-2 rounded" style="background:#161b22;border:1px solid #30363d">
                <div class="text-[#3fb950] font-semibold mb-1 extra-eq-title-eff" style="font-size:0.75rem"><i class="bi bi-speedometer2 mr-1"></i>Efficiency: η = b₀ + b₁Q + b₂Q² + b₃Q³</div>
                <div class="grid grid-cols-3 gap-1">
                  <div id="extra-wrap-eff_b0-${id}"><label class="block text-[10px] text-[#8b949e]">b₀</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-eff_b0" data-eid="${id}" step="any" value="${existingData?.eff_b0 ?? 0}"></div>
                  <div id="extra-wrap-eff_b1-${id}"><label class="block text-[10px] text-[#8b949e]">b₁</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-eff_b1" data-eid="${id}" step="any" value="${existingData?.eff_b1 ?? 0}"></div>
                  <div id="extra-wrap-eff_b2-${id}"><label class="block text-[10px] text-[#8b949e]">b₂</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-eff_b2" data-eid="${id}" step="any" value="${existingData?.eff_b2 ?? 0}"></div>
                  <div id="extra-wrap-eff_b3-${id}"><label class="block text-[10px] text-[#8b949e]">b₃</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-eff_b3" data-eid="${id}" step="any" value="${existingData?.eff_b3 ?? 0}"></div>
                  <div id="extra-wrap-eff_b4-${id}"><label class="block text-[10px] text-[#8b949e]">b₄</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-eff_b4" data-eid="${id}" step="any" value="${existingData?.eff_b4 ?? 0}"></div>
                  <div id="extra-wrap-eff_b5-${id}"><label class="block text-[10px] text-[#8b949e]">b₅</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-eff_b5" data-eid="${id}" step="any" value="${existingData?.eff_b5 ?? 0}"></div>
                </div>
              </div>
            </div>
            <!-- NPSH -->
            <div>
              <div class="p-1 px-2 rounded" style="background:#161b22;border:1px solid #30363d">
                <div class="text-[#ff9900] font-semibold mb-1 extra-eq-title-npsh" style="font-size:0.75rem"><i class="bi bi-arrow-up-right mr-1"></i>NPSHr: c₀ + c₁Q + c₂Q²</div>
                <div class="grid grid-cols-3 gap-1">
                  <div id="extra-wrap-npsh_c0-${id}"><label class="block text-[10px] text-[#8b949e]">c₀</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-npsh_c0" data-eid="${id}" step="any" value="${existingData?.npsh_c0 ?? 0}"></div>
                  <div id="extra-wrap-npsh_c1-${id}"><label class="block text-[10px] text-[#8b949e]">c₁</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-npsh_c1" data-eid="${id}" step="any" value="${existingData?.npsh_c1 ?? 0}"></div>
                  <div id="extra-wrap-npsh_c2-${id}"><label class="block text-[10px] text-[#8b949e]">c₂</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-npsh_c2" data-eid="${id}" step="any" value="${existingData?.npsh_c2 ?? 0}"></div>
                  <div id="extra-wrap-npsh_c3-${id}"><label class="block text-[10px] text-[#8b949e]">c₃</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-npsh_c3" data-eid="${id}" step="any" value="${existingData?.npsh_c3 ?? 0}"></div>
                  <div id="extra-wrap-npsh_c4-${id}"><label class="block text-[10px] text-[#8b949e]">c₄</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-npsh_c4" data-eid="${id}" step="any" value="${existingData?.npsh_c4 ?? 0}"></div>
                  <div id="extra-wrap-npsh_c5-${id}"><label class="block text-[10px] text-[#8b949e]">c₅</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-npsh_c5" data-eid="${id}" step="any" value="${existingData?.npsh_c5 ?? 0}"></div>
                </div>
              </div>
            </div>
            <!-- Power -->
            <div>
              <div class="p-1 px-2 rounded" style="background:#161b22;border:1px solid #30363d">
                <div class="text-[#f85149] font-semibold mb-1 extra-eq-title-pow" style="font-size:0.75rem"><i class="bi bi-lightning-charge mr-1"></i>Shaft Power: P = p₀ + p₁Q + p₂Q² (kW)</div>
                <div class="grid grid-cols-3 gap-1">
                  <div id="extra-wrap-pow_p0-${id}"><label class="block text-[10px] text-[#8b949e]">p₀</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-pow_p0" data-eid="${id}" step="any" value="${existingData?.pow_p0 ?? 0}"></div>
                  <div id="extra-wrap-pow_p1-${id}"><label class="block text-[10px] text-[#8b949e]">p₁</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-pow_p1" data-eid="${id}" step="any" value="${existingData?.pow_p1 ?? 0}"></div>
                  <div id="extra-wrap-pow_p2-${id}"><label class="block text-[10px] text-[#8b949e]">p₂</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-pow_p2" data-eid="${id}" step="any" value="${existingData?.pow_p2 ?? 0}"></div>
                  <div id="extra-wrap-pow_p3-${id}"><label class="block text-[10px] text-[#8b949e]">p₃</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-pow_p3" data-eid="${id}" step="any" value="${existingData?.pow_p3 ?? 0}"></div>
                  <div id="extra-wrap-pow_p4-${id}"><label class="block text-[10px] text-[#8b949e]">p₄</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-pow_p4" data-eid="${id}" step="any" value="${existingData?.pow_p4 ?? 0}"></div>
                  <div id="extra-wrap-pow_p5-${id}"><label class="block text-[10px] text-[#8b949e]">p₅</label><input type="number" class="w-full bg-[#0d1117] border border-[#30363d] rounded px-1.5 py-0.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] extra-cf-pow_p5" data-eid="${id}" step="any" value="${existingData?.pow_p5 ?? 0}"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>`;

  list.appendChild(div);

  // Wire radio buttons for curve mode
  div.querySelectorAll(`.extra-mode-radio`).forEach(radio => {
    radio.addEventListener('change', (e) => {
      const modeVal = e.target.value;
      const selectEl = div.querySelector(`.unit-select-mode`);
      if (selectEl) selectEl.value = modeVal;
      const curve = extraCurves.find(c => c.id === id);
      if (curve) {
        curve.curve_mode = modeVal;
        if (curve.coeffs) {
          curve.coeffs.curve_mode = modeVal;
        }
      }

      // Check if table has 3+ data points entered
      const rows = div.querySelectorAll(`#extraTable-${id} tbody tr`);
      let validPts = 0;
      rows.forEach(r => {
        const q = parseFloat(r.querySelector('.col-q')?.value);
        const h = parseFloat(r.querySelector('.col-h')?.value);
        if (!isNaN(q) && !isNaN(h)) validPts++;
      });

      if (validPts >= 3 && modeVal !== 'affinity') {
        fitExtraCurve(id);
      } else {
        serializeExtraCurves();
        refreshMainPreview();
      }
    });
  });

  // If pre-loading saved data, show status
  if (existingData) {
    const statusEl = div.querySelector('.extra-curve-status');
    statusEl.className = 'extra-curve-status ok';
    statusEl.textContent = `\u2713 Saved \u2014 Q_max=${existingData.q_max?.toFixed(1) ?? '?'}`;
  }

  // Helper to convert inputs on unit change
  const initExtraUnitSelectors = () => {
    ['q', 'h', 'npsh', 'pow', 'dia', 'mode'].forEach(type => {
      const select = div.querySelector(`.unit-select-${type}`);
      if (!select) return;
      select.setAttribute('data-prev', select.value);
      select.addEventListener('change', (e) => {
        const fromUnit = e.target.getAttribute('data-prev');
        const toUnit = e.target.value;
        if (fromUnit === toUnit) return;

        if (type === 'mode') {
          const curve = extraCurves.find(c => c.id === id);
          if (curve) curve.curve_mode = toUnit;
          refreshMainPreview();
        } else if (type === 'dia') {
          const diaInp = div.querySelector('.extra-dia-input');
          if (diaInp) {
            const val = parseFloat(diaInp.value);
            if (!isNaN(val)) {
              diaInp.value = convertValue(val, fromUnit, toUnit, 'dia');
            }
          }
          const curve = extraCurves.find(c => c.id === id);
          if (curve) curve.unit_dia = toUnit;
          refreshMainPreview();
        } else {
          const inputs = div.querySelectorAll(`.col-${type}`);
          inputs.forEach(input => {
            const val = parseFloat(input.value);
            if (!isNaN(val)) {
              input.value = convertValue(val, fromUnit, toUnit, type);
            }
          });

          // Update curve object in extraCurves array
          const curve = extraCurves.find(c => c.id === id);
          if (curve) {
            if (type === 'q') curve.unit_q = toUnit;
            if (type === 'h') curve.unit_h = toUnit;
            if (type === 'npsh') curve.unit_npsh = toUnit;
            if (type === 'pow') curve.unit_pow = toUnit;
          }

          // Update placeholders
          _updateExtraPlaceholders(div, type, toUnit);

          // Recalculate power in the table rows if needed
          if (type === 'q' || type === 'h' || type === 'pow') {
            div.querySelectorAll(`tbody tr`).forEach(row => _autoUpdateExtraPowerInRow(row, id));
          }

          // Unit selector changes convert numbers in the table without forcing graph refresh
        }

        e.target.setAttribute('data-prev', toUnit);
        serializeExtraCurves();
      });

      // Initial placeholder initialization on card creation
      if (type !== 'dia' && type !== 'mode') {
        _updateExtraPlaceholders(div, type, select.value);
      }
    });
  };
  initExtraUnitSelectors();

  // Events: style mode select
  const styleModeSel = div.querySelector('.unit-select-style-mode');
  if (styleModeSel) {
    styleModeSel.addEventListener('change', e => {
      const mode = e.target.value;
      const controlsDiv = div.querySelector(`#extra-custom-controls-${id}`);
      if (controlsDiv) {
        if (mode === 'custom') {
          controlsDiv.classList.remove('hidden');
          controlsDiv.classList.add('inline-flex');
        } else {
          controlsDiv.classList.remove('inline-flex');
          controlsDiv.classList.add('hidden');
        }
      }
      serializeExtraCurves();
      refreshMainPreview();
    });
  }

  // Events: color picker
  const colorPicker = div.querySelector('.extra-color-picker');
  if (colorPicker) {
    ['input', 'change'].forEach(evt => {
      colorPicker.addEventListener(evt, e => {
        const newColor = sanitizeHexColor(e.target.value, '#3fb950');
        const curve = extraCurves.find(c => c.id === id);
        if (curve) curve.color = newColor;
        const dot = div.querySelector('.curve-color-dot');
        if (dot) dot.style.background = newColor;
        serializeExtraCurves();
        refreshPreviewCharts();
      });
    });
  }

  // Events: weight & line style select
  div.querySelectorAll('.extra-weight-select, .extra-line-style-select').forEach(sel => {
    sel.addEventListener('change', () => {
      serializeExtraCurves();
      refreshMainPreview();
    });
  });

  // Events: label
  div.querySelector('.extra-label-input')?.addEventListener('input', e => {
    const curve = extraCurves.find(c => c.id === parseInt(e.target.dataset.eid));
    if (curve) {
      curve.label = e.target.value || `Curve ${curve.id}`;
      refreshMainPreview();
      serializeExtraCurves();
    }
  });

  // Events: diameter
  div.querySelector('.extra-dia-input')?.addEventListener('input', e => {
    const curve = extraCurves.find(c => c.id === id);
    if (curve) {
      curve.diameter = e.target.value.trim() !== '' ? parseFloat(e.target.value) : '';
      serializeExtraCurves();
    }
  });

  // Events: add row
  div.querySelector('.btn-extra-add-row')?.addEventListener('click', e => {
    const eid = parseInt(e.currentTarget.dataset.eid);
    const tbody = document.querySelector(`#extraTable-${eid} tbody`);
    const row = document.createElement('tr');

    const currentQUnit = div.querySelector('.unit-select-q')?.value || 'm3h';
    const currentHUnit = div.querySelector('.unit-select-h')?.value || 'm';
    const currentNpshUnit = div.querySelector('.unit-select-npsh')?.value || 'm';
    const currentPowUnit = div.querySelector('.unit-select-pow')?.value || 'kw';

    row.innerHTML = _extraRow(currentQUnit, currentHUnit, currentNpshUnit, currentPowUnit);
    tbody?.appendChild(row);
    _wireExtraRow(row, eid);
  });

  // Events: fit
  div.querySelector('.btn-extra-fit')?.addEventListener('click', e => {
    fitExtraCurve(parseInt(e.currentTarget.dataset.eid));
    serializeDataUnits();
  });

  // Events: remove
  div.querySelector('.btn-extra-remove')?.addEventListener('click', e => {
    const eid = parseInt(e.currentTarget.dataset.eid);
    extraCurves = extraCurves.filter(c => c.id !== eid);
    document.getElementById(`extra-entry-${eid}`)?.remove();
    updateExtraBadge();
    refreshMainPreview();
    serializeExtraCurves();
  });

  // Power auto-calc for all initial rows
  div.querySelectorAll(`#extraTable-${id} tbody tr`).forEach(row => _wireExtraRow(row, id));

  // Events: import file
  const cardFileInp = div.querySelector(`.extra-file-input-${id}`);
  div.querySelector('.btn-extra-import-file')?.addEventListener('click', () => {
    cardFileInp?.click();
  });
  cardFileInp?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (evt) {
      const text = evt.target.result;
      const parsedRows = parseCSVOrTXT(text);
      if (parsedRows.length < 3) {
        alert("Invalid file: found fewer than 3 valid data points (each point must have at least Q and H separated by comma, space, tab or semicolon).");
        return;
      }

      const tbody = div.querySelector(`#extraTable-${id} tbody`);
      tbody.innerHTML = '';
      const qUnit = div.querySelector('.unit-select-q')?.value || 'm3h';
      const hUnit = div.querySelector('.unit-select-h')?.value || 'm';
      const npshUnit = div.querySelector('.unit-select-npsh')?.value || 'm';
      const powUnit = div.querySelector('.unit-select-pow')?.value || 'kw';

      parsedRows.forEach(row => {
        const [q, h, eta, npsh, pow] = row;
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-[#1c2330]/50 transition-colors border-b border-[#30363d]/40';
        tr.innerHTML = `
          <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-q" step="any" placeholder="Q (${getUnitLabel('q', qUnit)})" value="${q}"></td>
          <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-h" step="any" placeholder="H (${getUnitLabel('h', hUnit)})" value="${h}"></td>
          <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-eta" step="any" min="0" max="100" placeholder="η %" value="${eta}"></td>
          <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-npsh" step="any" placeholder="NPSHr (${getUnitLabel('npsh', npshUnit)})" value="${npsh}"></td>
          <td class="p-1.5"><input type="number" class="${TABLE_INPUT_CLS} col-pow" step="any" placeholder="${getUnitLabel('pow', powUnit)} (opt)" value="${pow}"></td>
          <td class="p-1.5 text-center"><button type="button" class="text-[#8b949e] hover:text-red-400 hover:bg-red-950/30 p-1.5 rounded transition-colors text-xs font-medium" onclick="removeRow(this)" title="Delete Row"><i class="bi bi-trash text-sm"></i></button></td>`;
        tbody.appendChild(tr);
        _wireExtraRow(tr, id);
      });

      fitExtraCurve(id);
    };
    reader.readAsText(file);
    e.target.value = '';
  });

  updateExtraBadge();

  // Auto-open the collapse panel (Tailwind)
  const body = document.getElementById('extraCurvesBody');
  const chevron = document.getElementById('extraCurvesChevron');
  if (body) {
    body.classList.remove('hidden');
    if (chevron) chevron.style.transform = 'rotate(180deg)';
  }
  updateExtraPolynomialUI(id);
}

/* ── Entry point: initialise extra curves (called from inline script) ─────── */
function initExtraCurves(curvesArray) {
  extraCurves = [];
  _extraCurveIdCounter = 0;

  // Restore saved graph options if present
  const savedOptsField = document.querySelector('input[name="graph_options_json"]');
  if (savedOptsField && savedOptsField.value) {
    try {
      applyGraphOptions(JSON.parse(savedOptsField.value));
    } catch (e) { }
  }

  // Max Impeller Unit auto-conversion
  const unitMaxImp = document.querySelector('select[name="unit_max_imp"]');
  if (unitMaxImp) {
    unitMaxImp.addEventListener('change', function (e) {
      const oldUnit = this.dataset.prevUnit || 'mm';
      const newUnit = this.value;
      this.dataset.prevUnit = newUnit;

      const valInp = document.querySelector('input[name="impeller_dia_val"]');
      if (valInp && valInp.value) {
        let val = parseFloat(valInp.value);
        if (!isNaN(val)) {
          if (oldUnit === 'mm' && newUnit === 'in') {
            valInp.value = (val / 25.4).toFixed(3).replace(/\.?0+$/, '');
          } else if (oldUnit === 'in' && newUnit === 'mm') {
            valInp.value = (val * 25.4).toFixed(2).replace(/\.?0+$/, '');
          }
        }
      }
    });
    unitMaxImp.dataset.prevUnit = unitMaxImp.value;
  }

  // Wire the Add Curve Table button
  const addBtn = document.getElementById('btnAddExtraCurve');
  if (addBtn) addBtn.addEventListener('click', (e) => {
    e.preventDefault();
    addExtraCurveCard();
  });

  // Wire form submit is handled in pump_form.html

  // Load existing saved curves (edit mode)
  const data = Array.isArray(curvesArray) ? curvesArray :
    (typeof curvesArray === 'string' ? JSON.parse(curvesArray || '[]') : []);

  const initEl = document.getElementById('pump-init-data');
  const curveLabelsStr = initEl?.dataset?.curveLabels;
  const curveDiasStr = initEl?.dataset?.curveDiameters;
  const curveColorsStr = initEl?.dataset?.curveColors;
  const curveModesStr = initEl?.dataset?.curveModes;
  const curveUnitsStr = initEl?.dataset?.curveUnits;
  const curveRawTablesStr = initEl?.dataset?.curveRawTables;
  const curveCoeffsStr = initEl?.dataset?.curveCoeffs;

  if (curveLabelsStr || curveDiasStr || curveColorsStr || curveRawTablesStr) {
    const lblParts = (curveLabelsStr || '').split(';').map(s => s.trim());
    const diaEntries = (curveDiasStr || '').split('|').map(s => s.trim());
    const colParts = (curveColorsStr || '').split(';').map(s => s.trim());
    const modeParts = (curveModesStr || '').split(';').map(s => s.trim());
    const unitEntries = (curveUnitsStr || '').split('|').map(s => s.trim());
    const rawTableEntries = (curveRawTablesStr || '').split('|');
    const coeffEntries = (curveCoeffsStr || '').split('|');

    if (lblParts.length > 0) {
      const mainLblInp = document.getElementById('main_curve_label');
      if (mainLblInp && !mainLblInp.value) {
        mainLblInp.value = lblParts[0];
      }
    }

    if (diaEntries.length > 0) {
      const mainPair = diaEntries[0].split(';');
      if (mainPair.length > 0) {
        const mainDiaInp = document.getElementById('main_curve_dia_mm');
        if (mainDiaInp && !mainDiaInp.value) {
          mainDiaInp.value = mainPair[0];
        }
      }
    }

    const maxExtraCount = Math.max(
      data.length,
      lblParts.length > 0 ? lblParts.length - 1 : 0,
      diaEntries.length > 0 ? diaEntries.length - 1 : 0,
      rawTableEntries.length > 0 ? rawTableEntries.length - 1 : 0
    );

    for (let idx = 0; idx < maxExtraCount; idx++) {
      if (!data[idx]) data[idx] = {};
      const c = data[idx];
      const lIdx = idx + 1;

      if (lIdx < lblParts.length) c.label = lblParts[lIdx];
      if (lIdx < diaEntries.length) {
        const pair = diaEntries[lIdx].split(';');
        if (pair.length > 0 && pair[0]) c.diameter = pair[0];
        if (pair.length > 1 && pair[1]) c.unit_dia = pair[1];
      }
      if (lIdx < colParts.length && colParts[lIdx]) {
        const rawCol = colParts[lIdx];
        if (rawCol.startsWith('custom;') || rawCol.startsWith('graph;')) {
          const parts = rawCol.split(';');
          if (!c.style_mode) c.style_mode = parts[0];
          if (c.use_custom_style === undefined) c.use_custom_style = (parts[0] === 'custom');
          if (!c.color) c.color = sanitizeHexColor(parts[1], '#3fb950');
          if (parts[2]) {
            const sub = parts[2].split(',');
            if (sub[0] && c.weight === undefined) c.weight = parseFloat(sub[0]);
            if (sub[1] && !c.style) c.style = sub[1];
          }
        } else if (!c.color) {
          c.color = sanitizeHexColor(rawCol, '#3fb950');
        }
      }
      c.color = sanitizeHexColor(c.color, '#3fb950');
      if (lIdx < modeParts.length) c.curve_mode = modeParts[lIdx];
      if (lIdx < unitEntries.length) {
        const uParts = unitEntries[lIdx].split(',').map(s => s.trim());
        if (uParts.length >= 4) {
          c.unit_q = uParts[0]; c.unit_h = uParts[1];
          c.unit_npsh = uParts[2]; c.unit_pow = uParts[3];
        }
      }
      if (lIdx < rawTableEntries.length && rawTableEntries[lIdx].trim()) {
        c.raw_table = rawTableEntries[lIdx].split(';').map(r => r.split(',').map(s => s.trim()));
      }
      if (lIdx < coeffEntries.length && coeffEntries[lIdx].trim()) {
        const cfs = coeffEntries[lIdx].split(',').map(s => parseFloat(s.trim()));
        if (cfs.length >= 16) {
          c.hq_a0 = cfs[0]; c.hq_a1 = cfs[1]; c.hq_a2 = cfs[2]; c.hq_a3 = cfs[3];
          c.eff_b0 = cfs[4]; c.eff_b1 = cfs[5]; c.eff_b2 = cfs[6]; c.eff_b3 = cfs[7];
          c.npsh_c0 = cfs[8]; c.npsh_c1 = cfs[9]; c.npsh_c2 = cfs[10];
          c.pow_p0 = cfs[11]; c.pow_p1 = cfs[12]; c.pow_p2 = cfs[13];
          c.q_max = cfs[14]; c.q_bep = cfs[15];
        }
      }
    }
  }

  data.forEach(c => addExtraCurveCard(c));
}

function updateFamilyTypeUI(isUserChange = false) {
  const famType = document.getElementById('selFamilyType')?.value || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');

  // Requirement 3: Overlay defaults based on Test Basis
  const chkRpm = document.getElementById('chkRpmOverlay');
  const chkDia = document.getElementById('chkDiaOverlay');
  const wrapRpm = document.getElementById('wrapRpmOverlay');
  const wrapDia = document.getElementById('wrapDiaOverlay');

  if (isVarSpeed) {
    if (chkRpm) chkRpm.checked = true;
    if (chkDia) chkDia.checked = false;
    if (wrapRpm) wrapRpm.style.display = '';
    if (wrapDia) wrapDia.style.display = 'none';
  } else {
    if (chkDia) chkDia.checked = true;
    if (chkRpm) chkRpm.checked = false;
    if (wrapDia) wrapDia.style.display = '';
    if (wrapRpm) wrapRpm.style.display = 'none';
  }

  // Update Main Curve Property Label & Unit Selector in Card 3 Header
  const lblMainProp = document.getElementById('lblMainCurveProperty');
  if (lblMainProp) {
    lblMainProp.textContent = isVarSpeed ? 'Speed:' : 'Dia:';
  }

  const mainDiaInp = document.getElementById('main_curve_dia_mm');
  if (mainDiaInp) {
    mainDiaInp.placeholder = isVarSpeed ? '1450' : '300';
  }

  const mainUnitSel = document.getElementById('main_curve_dia_unit');
  if (mainUnitSel) {
    const curVal = mainUnitSel.value;
    if (isVarSpeed) {
      mainUnitSel.innerHTML = `<option value="rpm" ${curVal === 'rpm' || curVal === 'mm' ? 'selected' : ''}>RPM</option><option value="hz" ${curVal === 'hz' ? 'selected' : ''}>Hz</option><option value="percent" ${curVal === 'percent' ? 'selected' : ''}>%</option>`;
    } else {
      mainUnitSel.innerHTML = `<option value="mm" ${curVal === 'mm' || curVal === 'rpm' ? 'selected' : ''}>mm</option><option value="in" ${curVal === 'in' ? 'selected' : ''}>in</option><option value="m" ${curVal === 'm' ? 'selected' : ''}>m</option>`;
    }
  }

  // Update Card 1 Labels
  const lblSpeedRpm = document.getElementById('lblSpeedRpm');
  if (lblSpeedRpm) {
    lblSpeedRpm.textContent = isVarSpeed ? 'Max Speed (rpm)' : 'Speed (rpm)';
  }
  const lblMaxImp = document.getElementById('lblMaxImp');
  if (lblMaxImp) {
    lblMaxImp.textContent = isVarSpeed ? 'Impeller Dia' : 'Max Imp.';
  }

  // Update Speed Lines / Impeller Curves Checkbox Label & Inputs
  const lblSpeedLines = document.getElementById('lblSpeedLines');
  const lblSpeedLineValues = document.getElementById('lblSpeedLineValues');
  const txtSpeedLineValues = document.getElementById('txtSpeedLineValues');

  if (lblSpeedLines) {
    lblSpeedLines.textContent = isVarSpeed ? 'Show Impeller Trim Curves' : 'Show Speed Lines';
  }
  if (lblSpeedLineValues) {
    lblSpeedLineValues.textContent = isVarSpeed ? 'Impeller Sizes to Generate (mm):' : 'Speed Lines to Generate (RPM):';
  }
  if (txtSpeedLineValues) {
    txtSpeedLineValues.placeholder = isVarSpeed ? 'e.g. 480, 440, 400, 360' : 'e.g. 1000, 900, 800, 700';
  }

  // Update additional curve card labels & units
  document.querySelectorAll('.extra-dia-label').forEach(lbl => {
    lbl.textContent = isVarSpeed ? 'Speed:' : 'Dia:';
  });

  document.querySelectorAll('.unit-select-dia').forEach(select => {
    const curVal = select.value;
    if (isVarSpeed) {
      select.innerHTML = `<option value="rpm" ${curVal === 'rpm' || curVal === 'mm' ? 'selected' : ''}>RPM</option><option value="hz" ${curVal === 'hz' ? 'selected' : ''}>Hz</option><option value="percent" ${curVal === 'percent' ? 'selected' : ''}>%</option>`;
    } else {
      select.innerHTML = `<option value="mm" ${curVal === 'mm' || curVal === 'rpm' ? 'selected' : ''}>mm</option><option value="in" ${curVal === 'in' ? 'selected' : ''}>in</option><option value="m" ${curVal === 'm' ? 'selected' : ''}>m</option>`;
    }
  });

  if (typeof refreshPreviewCharts === 'function') {
    refreshPreviewCharts();
  }
}

// Add listener to selFamilyType dropdown
document.addEventListener('DOMContentLoaded', () => {
  const selFam = document.getElementById('selFamilyType');
  if (selFam) {
    selFam.addEventListener('change', () => updateFamilyTypeUI(true));
    updateFamilyTypeUI(false);
  }

  const btnGenerateAffinity = document.getElementById('btnGenerateAffinity');
  if (btnGenerateAffinity) {
    btnGenerateAffinity.addEventListener('click', generateAffinityCurve);
  }

  const affTypeRadios = document.querySelectorAll('input[name="affinityType"]');
  affTypeRadios.forEach(r => r.addEventListener('change', (e) => {
    const label = document.getElementById('affinityValueLabel');
    if (e.target.value === 'diameter') {
      label.textContent = 'Target Diameter (mm)';
    } else {
      label.textContent = 'Target Rotational Speed (RPM)';
    }
  }));

  // Bind uploader + preview options + per-curve polynomial order listeners
  initExtraCurveFileLoader();
  bindPreviewOptions();
  bindPreviewEvents();
});

function generateAffinityCurve() {
  const affinityType = document.querySelector('input[name="affinityType"]:checked').value;
  const targetValue = parseFloat(document.getElementById('affinityValue').value);
  if (isNaN(targetValue) || targetValue <= 0) {
    alert("Please enter a valid target value.");
    return;
  }

  const baseTableData = getTableData('perfTable', false);
  const q_h = baseTableData.q_h, q_eta = baseTableData.q_eta, q_npsh = baseTableData.q_npsh, q_p = baseTableData.q_p;

  if (q_h.length === 0) {
    alert("Please enter base curve data first.");
    return;
  }

  let ratio = 1.0;
  let labelSuffix = '';
  let dia_mm = null;
  let speed = null;

  if (affinityType === 'diameter') {
    const mainCurveDiaEl = document.getElementById('main_curve_dia_mm');
    const impellerDiaEl = document.querySelector('[name="impeller_dia_mm"]');
    const baseDia = parseFloat(mainCurveDiaEl?.value) || parseFloat(impellerDiaEl?.value) || parseFloat(mainCurveDiaEl?.placeholder) || 300.0;
    if (isNaN(baseDia)) {
      alert("Please specify the base diameter in the pump details first.");
      return;
    }
    ratio = targetValue / baseDia;
    labelSuffix = `Dia: ${targetValue}mm`;
    dia_mm = targetValue;
  } else {
    const baseSpeed = parseFloat(document.querySelector('[name="speed_rpm"]')?.value);
    if (isNaN(baseSpeed)) {
      alert("Please specify the base speed in the pump details first.");
      return;
    }
    ratio = targetValue / baseSpeed;
    labelSuffix = `Speed: ${targetValue} RPM`;
    speed = targetValue;
  }

  const etaMap = new Map(); q_eta.forEach(p => etaMap.set(p[0], p[1]));
  const npshMap = new Map(); q_npsh.forEach(p => npshMap.set(p[0], p[1]));
  const powMap = new Map(); q_p.forEach(p => powMap.set(p[0], p[1]));

  const newCurveData = [];
  q_h.forEach(p => {
    const q1 = p[0];
    const h1 = p[1];

    const q2 = q1 * ratio;
    const h2 = h1 * Math.pow(ratio, 2);

    let eta2 = etaMap.has(q1) ? etaMap.get(q1) : '';
    if (eta2 !== '' && affinityType === 'diameter') {
      const penalty = 40.0 * (1.0 - ratio);
      eta2 = Math.max(0, Math.min(100, eta2 - penalty)).toFixed(1);
    } else if (eta2 !== '') {
      eta2 = parseFloat(eta2).toFixed(1);
    }

    let npsh2 = npshMap.has(q1) ? npshMap.get(q1) * Math.pow(ratio, 2) : '';
    if (npsh2 !== '') npsh2 = parseFloat(npsh2).toFixed(2);

    let p2 = powMap.has(q1) ? powMap.get(q1) * Math.pow(ratio, 3) : '';
    if (p2 !== '') p2 = parseFloat(p2).toFixed(2);

    newCurveData.push([q2.toFixed(1), h2.toFixed(2), eta2, npsh2, p2]);
  });

  const curveObj = {
    label: `Affinity ${labelSuffix}`,
    diameter: dia_mm || '',
    curve_mode: 'affinity',
    raw_table: newCurveData
  };

  addExtraCurveCard(curveObj);

  const newId = _extraCurveIdCounter;
  fitExtraCurve(newId);

  if (typeof closeAffinityModal === 'function') {
    closeAffinityModal();
  } else {
    document.getElementById('affinityModal')?.classList.remove('open');
  }
}

function initExtraCurveFileLoader() {
  const btnLoad = document.getElementById('btnLoadExtraCurve');
  const fileInp = document.getElementById('extraCurveFileInp');
  if (!btnLoad || !fileInp) return;

  btnLoad.addEventListener('click', (e) => {
    e.preventDefault();
    fileInp.click();
  });

  fileInp.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (evt) {
      const text = evt.target.result;
      const parsedRows = parseCSVOrTXT(text);
      if (parsedRows.length < 3) {
        alert("Invalid file: found fewer than 3 valid data points (each point must have at least Q and H separated by comma, space, tab or semicolon).");
        return;
      }

      const defaultLabel = file.name.replace(/\.[^/.]+$/, "");
      const label = prompt("Enter a label for this loaded curve:", defaultLabel) || defaultLabel;
      const diameterStr = prompt("Enter the impeller diameter (mm) for this curve (optional):", "");
      const diameter = parseFloat(diameterStr) || '';

      const curveObj = {
        label: label,
        diameter: diameter,
        raw_table: parsedRows
      };

      addExtraCurveCard(curveObj);
      const newId = _extraCurveIdCounter;
      fitExtraCurve(newId);
    };
    reader.readAsText(file);
    e.target.value = '';
  });
}

function parseCSVOrTXT(text) {
  const lines = text.split('\n');
  const parsedRows = [];
  lines.forEach(line => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    const parts = trimmed.split(/[\s,;]+/).map(Number);
    if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      const q = parts[0];
      const h = parts[1];
      const eta = (parts.length >= 3 && !isNaN(parts[2])) ? parts[2] : '';
      const npsh = (parts.length >= 4 && !isNaN(parts[3])) ? parts[3] : '';
      const pow = (parts.length >= 5 && !isNaN(parts[4])) ? parts[4] : '';
      parsedRows.push([q, h, eta, npsh, pow]);
    }
  });
  return parsedRows;
}

function bindPreviewOptions() {
  ['chkShowHQ', 'chkShowEffIso', 'chkShowPowerIso', 'chkShowNpshIso', 'chkShowNpshCurve', 'chkSpeedLines', 'txtSpeedLineValues',
    'chkRpmOverlay', 'txtRpmValues', 'chkDiaOverlay', 'txtDiaOverlayValues', 'chkShowOther',
    'chkShowEff', 'chkShowPower', 'chkShowNpsh', 'chkCombineEffPower', 'selLegendMode',
    'txtEffLevels', 'txtPowerLevels', 'txtNpshLevels', 'numTrimPenalty',
    'clrHeadColor', 'selHeadWeight', 'selHeadStyle',
    'clrEffColor', 'selEffWeight', 'selEffStyle',
    'clrPowColor', 'selPowWeight', 'selPowStyle',
    'clrNpshColor', 'selNpshWeight', 'selNpshStyle'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        const evtTypes = el.type === 'color' || el.tagName === 'INPUT' && el.type !== 'checkbox' ? ['input', 'change'] : ['change'];
        evtTypes.forEach(evtType => {
          el.addEventListener(evtType, () => {
            if (id === 'chkShowEffIso') {
              const g = document.getElementById('groupEffLevels');
              if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
            }
            if (id === 'chkShowPowerIso') {
              const g = document.getElementById('groupPowerLevels');
              if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
            }
            if (id === 'chkShowNpshIso') {
              const g = document.getElementById('groupNpshLevels');
              if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
            }
            if (id === 'chkShowNpshCurve') {
              const g = document.getElementById('groupNpshYAxis');
              if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
            }
            if (id === 'selLegendMode') {
              const g = document.getElementById('groupCurveLabelPos');
              if (g) g.style.display = el.value === 'curve_labels' ? '' : 'none';
            }
            if (id === 'chkRpmOverlay') {
              const w = document.getElementById('wrapRpmOverlay');
              if (w) w.style.display = el.checked ? '' : 'none';
            }
            if (id === 'chkDiaOverlay') {
              const w = document.getElementById('wrapDiaOverlay');
              if (w) w.style.display = el.checked ? '' : 'none';
            }
            if (typeof serializeGraphOptions === 'function') serializeGraphOptions();
            refreshMainPreview();
          });
        });
      }
    });

  document.querySelectorAll('input[name="npshYAxisChoice"]').forEach(input => {
    input.addEventListener('change', refreshMainPreview);
  });

  const resetPosBtn = document.getElementById('btnResetLabelPos');
  if (resetPosBtn) {
    resetPosBtn.addEventListener('click', () => {
      customLabelPositions = {};
      refreshPreviewCharts();
    });
  }
}

// serializeGraphOptions is defined above (line ~572)
