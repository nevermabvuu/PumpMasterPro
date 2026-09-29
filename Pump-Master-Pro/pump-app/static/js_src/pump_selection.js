// ── Universal Unit Conversion System ─────────────────────────────────────────
// Beginners Note: Exact multipliers to convert 1.0 unit TO the SI base unit
const UNIT_FACTORS = {
  flow: {
    m3h: 1.0,
    ls: 3.6,
    lmin: 0.06,
    gpm: 0.227124707,
    ukgpm: 0.2727654,
    cfs: 101.9406,
    mgd: 157.7255
  },
  head: {
    m: 1.0,
    ft: 0.3048,
    kpa: 0.1019716,
    bar: 10.19716,
    psi: 0.70307
  },
  power: {
    kw: 1.0,
    hp: 0.745699872,
    w: 0.001,
    mw: 1000.0
  },
  density: {
    kgm3: 1.0,
    sg: 1000.0,
    lbft3: 16.018463
  },
  size: {
    mm: 1.0,
    um: 0.001,
    in: 25.4
  },
  density_rate: {
    mm_min: 1.0,
    gpm_ft2: 40.7458
  },
  area: {
    m2: 1.0,
    ft2: 0.092903
  }
};

/**
 * Converts a numerical value from one unit to another within the same category.
 */
function convertValue(val, fromUnit, toUnit, cat) {
  if (val === null || val === undefined || val === '' || isNaN(Number(val))) return '';
  const num = Number(val);
  if (fromUnit === toUnit) return num;
  const table = UNIT_FACTORS[cat] || {};
  const fFrom = table[fromUnit] !== undefined ? table[fromUnit] : 1.0;
  const fTo = table[toUnit] !== undefined ? table[toUnit] : 1.0;
  const base = num * fFrom;
  const converted = fTo !== 0 ? (base / fTo) : base;
  
  if (Math.abs(converted) >= 100) return Number(converted.toFixed(1));
  if (Math.abs(converted) >= 10) return Number(converted.toFixed(2));
  if (Math.abs(converted) >= 1) return Number(converted.toFixed(3));
  return Number(converted.toFixed(4));
}

/**
 * Batch applies a complete Metric (SI) or Imperial (US) preset to all input fields.
 */
function applyUnitPreset(preset) {
  const isImperial = preset === 'imperial';
  const targets = {
    select_unit_q: isImperial ? 'gpm' : 'm3h',
    select_unit_h: isImperial ? 'ft' : 'm',
    select_unit_npsh: isImperial ? 'ft' : 'm',
    select_unit_static_head: isImperial ? 'ft' : 'm',
    select_unit_rho: isImperial ? 'lbft3' : 'kgm3',
    select_unit_d50: isImperial ? 'in' : 'mm'
  };

  // Convert every input field and update dropdown
  Object.keys(targets).forEach(selectId => {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const targetUnit = targets[selectId];
    const prevUnit = sel.dataset.prev || sel.value;
    const cat = sel.dataset.unitCat || 'flow';
    const targetInputId = sel.dataset.target;
    const inputEl = document.getElementById(targetInputId);

    if (inputEl && inputEl.value !== '') {
      inputEl.value = convertValue(inputEl.value, prevUnit, targetUnit, cat);
    }

    sel.value = targetUnit;
    sel.dataset.prev = targetUnit;
  });

  // Update hidden field & badge
  const sysInput = document.getElementById('unitSystemInput');
  if (sysInput) sysInput.value = preset;

  const badge = document.getElementById('unitSystemBadge');
  if (badge) {
    badge.textContent = isImperial ? 'Imperial (US)' : 'Metric (SI)';
  }

  // Update preset button styles
  const btnMetric = document.getElementById('btnPresetMetric');
  const btnImp = document.getElementById('btnPresetImperial');
  if (btnMetric && btnImp) {
    if (isImperial) {
      btnImp.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all bg-[#21262d] text-[#58a6ff] shadow-sm';
      btnMetric.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all text-[#8b949e] hover:text-white';
    } else {
      btnMetric.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all bg-[#21262d] text-[#58a6ff] shadow-sm';
      btnImp.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all text-[#8b949e] hover:text-white';
    }
  }

  // Broadcast updated unit configuration to Pipe Network
  if (typeof syncPumpSelectionUnitsToPipeNetwork === 'function') {
    syncPumpSelectionUnitsToPipeNetwork();
  }

  // Synchronize Fire Protection Panel units with selected preset
  if (typeof setFireUnitSystem === 'function') {
    setFireUnitSystem(preset, true);
  }
}

/**
 * Evaluates current dropdown states to update system badge (Metric / Imperial / Custom Mixed)
 */
function updateSystemBadge() {
  const unitQ = document.getElementById('select_unit_q')?.value;
  const unitH = document.getElementById('select_unit_h')?.value;
  const badge = document.getElementById('unitSystemBadge');
  const btnMetric = document.getElementById('btnPresetMetric');
  const btnImp = document.getElementById('btnPresetImperial');
  const sysInput = document.getElementById('unitSystemInput');

  const isMetric = (unitQ === 'm3h' || unitQ === 'ls' || unitQ === 'lmin') && (unitH === 'm' || unitH === 'kpa' || unitH === 'bar');
  const isImperial = (unitQ === 'gpm' || unitQ === 'ukgpm' || unitQ === 'cfs' || unitQ === 'mgd') && (unitH === 'ft' || unitH === 'psi');

  if (isImperial && !isMetric) {
    if (badge) badge.textContent = 'Imperial (US)';
    if (sysInput) sysInput.value = 'imperial';
    if (btnImp) btnImp.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all bg-[#21262d] text-[#58a6ff] shadow-sm';
    if (btnMetric) btnMetric.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all text-[#8b949e] hover:text-white';
  } else if (isMetric && !isImperial) {
    if (badge) badge.textContent = 'Metric (SI)';
    if (sysInput) sysInput.value = 'metric';
    if (btnMetric) btnMetric.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all bg-[#21262d] text-[#58a6ff] shadow-sm';
    if (btnImp) btnImp.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all text-[#8b949e] hover:text-white';
  } else {
    if (badge) badge.textContent = 'Custom (Mixed)';
    if (sysInput) sysInput.value = 'custom';
    if (btnMetric) btnMetric.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all text-[#8b949e] hover:text-white';
    if (btnImp) btnImp.className = 'px-2.5 py-1 text-xs font-semibold rounded-md transition-all text-[#8b949e] hover:text-white';
  }
}

document.addEventListener('DOMContentLoaded', () => {

  // ── Render SVG Sparklines Immediately ─────────────────────────────────────
  // Beginners Note: Renders inline SVG tombstone curves at the earliest point in DOM ready
  try {
    initSparklines();
  } catch (err) {
    console.error('Initial sparkline error:', err);
  }

  // ── Individual Unit Selector Dropdown Event Listeners ────────────────────────
  // Beginners Note: Auto-converts the value in the input field when the unit changes
  const unitSelects = document.querySelectorAll('.unit-select');
  unitSelects.forEach(sel => {
    // Initialize data-prev if not set
    if (!sel.dataset.prev) sel.dataset.prev = sel.value;

    sel.addEventListener('change', () => {
      const prevUnit = sel.dataset.prev || sel.value;
      const newUnit = sel.value;
      const cat = sel.dataset.unitCat || 'flow';
      const targetInputId = sel.dataset.target;
      const inputEl = document.getElementById(targetInputId);

      if (inputEl && inputEl.value !== '') {
        let valToConvert = inputEl.value;
        if (cat === 'density') {
          const numV = parseFloat(valToConvert);
          if (prevUnit === 'sg' && numV > 50) {
            valToConvert = numV / 1000.0;
          } else if (prevUnit === 'kgm3' && numV < 50) {
            valToConvert = numV * 1000.0;
          }
        }
        inputEl.value = convertValue(valToConvert, prevUnit, newUnit, cat);
      }

      sel.dataset.prev = newUnit;
      updateSystemBadge();
      // Synchronize unit change with Pipe Network
      if (typeof syncPumpSelectionUnitsToPipeNetwork === 'function') {
        syncPumpSelectionUnitsToPipeNetwork();
      }
    });
  });

  // ── Liquid parameter switching ─────────────────────────────────────────────
  // Beginners Note: Shows/hides the appropriate input fields based on selected liquid type
  const liquidSel = document.getElementById('liquidSel');
  if (liquidSel) {
    function updateLiquidPanels() {
      // Defensive fallback: If no valid option is selected or value is empty, select the first available option
      if (liquidSel.options.length > 0 && (liquidSel.selectedIndex < 0 || !liquidSel.value)) {
        liquidSel.selectedIndex = 0;
      }
      const liquid = liquidSel.value || (liquidSel.options.length > 0 ? liquidSel.options[0].value : 'water');
      const wP = document.getElementById('waterParams');
      const vP = document.getElementById('viscousParams');
      const sP = document.getElementById('slurryParams');
      if (wP) wP.style.display = liquid === 'water'   ? '' : 'none';
      if (vP) vP.style.display = liquid === 'viscous' ? '' : 'none';
      if (sP) sP.style.display = liquid === 'slurry'  ? '' : 'none';
    }
    liquidSel.addEventListener('change', updateLiquidPanels);
    updateLiquidPanels();
  }

  // ── Dynamic Slurry Calculator ──────────────────────────────────────────────
  // Beginners Note: Enforces exactly 3 independent parameters from (L, S, M, Cv, Cw)
  // Physics & Engineering Bounds:
  //   - Liquid SG (Sl): 0.5 to 2.5 (water = 1.0)
  //   - Solid SG (Ss): Must be > Sl, typical minerals 2.0 to 7.5 (silica = 2.65, tailings = 2.8, magnetite = 5.0)
  //   - Slurry SG (Sm): Must be bounded between Sl and Ss (Sm = Sl*(1-Cv) + Ss*Cv)
  //   - Volumetric concentration (Cv): 0.0 to 0.65 (maximum loose random packing limit)
  //   - Weight concentration (Cw): 0.0 to 0.90
  const slurryCheckboxes = document.querySelectorAll('.slurry-cb');
  const slurryInputs = document.querySelectorAll('.slurry-input');
  
  // Helper to safely parse floats with null-checks
  const getVal = (id) => {
    const el = document.getElementById(id);
    return el ? (parseFloat(el.value) || 0) : 0;
  };

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (document.activeElement !== el && !isNaN(val) && isFinite(val)) {
      if (id === 'sg_l' || id === 'sg_s' || id === 'sg_m') {
        el.value = Number(val).toFixed(2);
      } else if (id === 'slurry_cv' || id === 'slurry_cw') {
        el.value = Number(val).toFixed(3);
      } else {
        el.value = (val % 1 !== 0) ? parseFloat(val.toFixed(3)) : val;
      }
    }
  };

  function onSlurryInputChange() {
    updateSlurryCalculator();
    syncPumpSelectionSgToStorage();
  }

  slurryInputs.forEach(input => {
    input.addEventListener('input', onSlurryInputChange);
    input.addEventListener('change', onSlurryInputChange);
  });

  function updateSlurryCalculator() {
    try {
      // Collect active (checked) parameters
      const active = new Set([...slurryCheckboxes].filter(cb => cb.checked).map(cb => cb.dataset.param));
      
      // Read raw inputs and apply minimum baseline sanitization
      let L = Math.max(0.5, getVal('sg_l') || 1.0);
      let S = Math.max(1.05, getVal('sg_s') || 2.65);
      let M = Math.max(0.5, getVal('sg_m') || 1.33);
      let Cv = Math.max(0.0, Math.min(0.65, getVal('slurry_cv')));
      let Cw = Math.max(0.0, Math.min(0.90, getVal('slurry_cw')));

      if (active.size !== 3) return; // Need exactly 3 knowns

      // Solver logic for all 10 combinations of 3 variables out of 5 (L, S, M, Cv, Cw)
      // Every branch guarantees non-negative, physically realistic engineering values.
      if (active.has('L') && active.has('S') && active.has('M')) {
        // Enforce S > L
        if (S <= L) S = L + 0.1;
        // Clamp M between L and S
        M = Math.max(L, Math.min(S, M));
        Cv = (S - L > 0.001) ? (M - L) / (S - L) : 0;
        Cw = M > 0.001 ? (S * Cv) / M : 0;
      }
      else if (active.has('L') && active.has('S') && active.has('Cv')) {
        if (S <= L) S = L + 0.1;
        M = L * (1 - Cv) + S * Cv;
        Cw = M > 0.001 ? (S * Cv) / M : 0;
      }
      else if (active.has('L') && active.has('S') && active.has('Cw')) {
        if (S <= L) S = L + 0.1;
        const denom = S - Cw * (S - L);
        Cv = (denom > 0.001) ? (Cw * L) / denom : 0;
        Cv = Math.max(0.0, Math.min(0.65, Cv));
        M = L * (1 - Cv) + S * Cv;
      }
      else if (active.has('L') && active.has('M') && active.has('Cv')) {
        // M = L*(1-Cv) + S*Cv  =>  S = (M - L*(1-Cv)) / Cv
        if (Cv < 0.005) {
          S = 2.65;
          M = L;
        } else {
          const lPart = L * (1 - Cv);
          if (M < lPart) M = lPart + 0.01;
          S = (M - lPart) / Cv;
          S = Math.max(L + 0.05, Math.min(10.0, S));
        }
        Cw = M > 0.001 ? (S * Cv) / M : 0;
      }
      else if (active.has('L') && active.has('M') && active.has('Cw')) {
        // Cv = (M - L)/(S - L) and S = Cw*M*L / (L + M*(Cw - 1))
        const denom = L + M * (Cw - 1);
        if (denom > 0.001 && Cw > 0.005) {
          S = (Cw * M * L) / denom;
          S = Math.max(L + 0.05, Math.min(10.0, S));
        } else {
          S = Math.max(L + 0.1, 2.65);
        }
        Cv = (S - L > 0.001) ? Math.max(0.0, (M - L) / (S - L)) : 0;
      }
      else if (active.has('S') && active.has('M') && active.has('Cv')) {
        // L = (M - S*Cv)/(1 - Cv)
        if (Cv >= 0.99) Cv = 0.65;
        const sPart = S * Cv;
        if (M < sPart) {
          // If mixture SG is smaller than solid contribution alone, adjust L safely
          L = 1.0;
          M = L * (1 - Cv) + S * Cv;
        } else {
          L = (M - sPart) / (1 - Cv);
          L = Math.max(0.5, Math.min(2.5, L));
        }
        Cw = M > 0.001 ? (S * Cv) / M : 0;
      }
      else if (active.has('S') && active.has('M') && active.has('Cw')) {
        // Cv = (Cw * M) / S
        Cv = (S > 0.001) ? (Cw * M) / S : 0;
        Cv = Math.max(0.0, Math.min(0.65, Cv));
        const sPart = S * Cv;
        L = (Cv < 0.99 && M > sPart) ? (M - sPart) / (1 - Cv) : 1.0;
        L = Math.max(0.5, Math.min(2.5, L));
      }
      else if (active.has('L') && active.has('Cv') && active.has('Cw')) {
        // S = L*(1-Cv) / (Cv/Cw - Cv)
        if (Cw > 0.001 && Cv > 0.001 && (Cv / Cw - Cv) > 0.001) {
          S = (L * (1 - Cv)) / (Cv / Cw - Cv);
          S = Math.max(L + 0.05, Math.min(10.0, S));
        } else {
          S = 2.65;
        }
        M = L * (1 - Cv) + S * Cv;
      }
      else if (active.has('S') && active.has('Cv') && active.has('Cw')) {
        // M = (S * Cv) / Cw
        M = (Cw > 0.001) ? (S * Cv) / Cw : S;
        M = Math.max(0.5, Math.min(S, M));
        const sPart = S * Cv;
        L = (Cv < 0.99 && M > sPart) ? (M - sPart) / (1 - Cv) : 1.0;
        L = Math.max(0.5, Math.min(2.5, L));
      }
      else if (active.has('M') && active.has('Cv') && active.has('Cw')) {
        // S = (Cw * M) / Cv
        S = (Cv > 0.001) ? (Cw * M) / Cv : 2.65;
        S = Math.max(1.05, Math.min(10.0, S));
        const sPart = S * Cv;
        L = (Cv < 0.99 && M > sPart) ? (M - sPart) / (1 - Cv) : 1.0;
        L = Math.max(0.5, Math.min(2.5, L));
      }

      // Final sanitization clamp
      L = Math.max(0.5, Math.min(2.5, L));
      S = Math.max(L + 0.05, Math.min(10.0, S));
      Cv = Math.max(0.0, Math.min(0.65, Cv));
      Cw = Math.max(0.0, Math.min(0.90, Cw));
      M = Math.max(L, Math.min(S, M));

      // Update the UI for calculated properties with clean decimal precision
      if (!active.has('L')) setVal('sg_l', parseFloat(L.toFixed(2)));
      if (!active.has('S')) setVal('sg_s', parseFloat(S.toFixed(2)));
      if (!active.has('M')) setVal('sg_m', parseFloat(M.toFixed(2)));
      if (!active.has('Cv')) setVal('slurry_cv', parseFloat(Cv.toFixed(3)));
      if (!active.has('Cw')) setVal('slurry_cw', parseFloat(Cw.toFixed(3)));
    } catch (e) {
      console.warn('Slurry calculation error:', e);
    }
  }

  // Handle Checkbox Toggles: keep exactly 3 checked
  let checkedOrder = [...slurryCheckboxes].filter(cb => cb.checked);
  
  function syncPumpSelectionSlurryReadOnlyState() {
    const active = new Set(checkedOrder.map(c => c.dataset.param));
    const elementsToToggle = [
      ['sg_l', 'L'],
      ['sg_s', 'S'],
      ['sg_m', 'M'],
      ['slurry_cv', 'Cv'],
      ['slurry_cw', 'Cw']
    ];
    elementsToToggle.forEach(([elemId, param]) => {
      const el = document.getElementById(elemId);
      if (el) {
        el.readOnly = !active.has(param);
        el.style.opacity = active.has(param) ? '1' : '0.75';
      }
    });
  }

  slurryCheckboxes.forEach(cb => {
    cb.addEventListener('change', (e) => {
      if (e.target.checked) {
        checkedOrder.push(e.target);
        // If we exceed 3, uncheck the oldest checked box
        if (checkedOrder.length > 3) {
          const oldest = checkedOrder.shift();
          oldest.checked = false;
        }
      } else {
        // Prevent unchecking if it brings us below 3
        e.target.checked = true;
      }
      
      syncPumpSelectionSlurryReadOnlyState();
      updateSlurryCalculator();
      syncPumpSelectionSgToStorage();
    });
  });

  // Initial update
  if (slurryCheckboxes.length > 0) {
    try {
      syncPumpSelectionSlurryReadOnlyState();
      updateSlurryCalculator();
    } catch (err) {
      console.warn('Slurry init notice:', err);
    }
  }

  // ── Bidirectional Units, Flow Rate, Temperature & SG Synchronization with Pipe Network ──

  // Flow unit conversion dictionary to m3/h
  const FLOW_UNIT_TO_M3H = {
    'm3h': 1.0,
    'ls': 3.6,
    'lpm': 0.06,
    'usgpm': 0.2271247,
    'ukgpm': 0.272765,
    'cfs': 101.9406,
    'm3s': 3600.0,
  };

  /**
   * getPumpSelectionFlowM3h()
   * Returns current flow rate from Pump Selection converted to standard m3/h
   */
  function getPumpSelectionFlowM3h() {
    const rawQ = parseFloat(document.getElementById('input_q_duty')?.value) || 0;
    const unitQ = document.getElementById('select_unit_q')?.value || 'm3h';
    const factor = FLOW_UNIT_TO_M3H[unitQ] || 1.0;
    return rawQ * factor;
  }

  /**
   * setPumpSelectionFlowFromM3h(m3h)
   * Converts standard m3/h flow into the active Pump Selection unit and updates input
   */
  function setPumpSelectionFlowFromM3h(m3h) {
    if (isNaN(m3h) || m3h <= 0) return;
    const unitQ = document.getElementById('select_unit_q')?.value || 'm3h';
    const factor = FLOW_UNIT_TO_M3H[unitQ] || 1.0;
    const convertedQ = m3h / factor;
    const qInp = document.getElementById('input_q_duty');
    if (qInp && document.activeElement !== qInp) {
      qInp.value = (convertedQ % 1 !== 0) ? parseFloat(convertedQ.toFixed(2)) : convertedQ;
    }
  }

  function getPumpSelectionTemperature() {
    return parseFloat(document.getElementById('input_temperature_c')?.value) || 20.0;
  }

  function getPumpSelectionSg() {
    const liquid = document.getElementById('liquidSel')?.value || 'water';
    if (liquid === 'water') {
      const rhoRaw = parseFloat(document.getElementById('input_rho_water')?.value) || 1000;
      const uRho = document.getElementById('select_unit_rho')?.value || 'kgm3';
      const rhoKgM3 = Number(convertValue(rhoRaw, uRho, 'kgm3', 'density')) || 1000;
      return Math.max(0.5, Math.min(3.0, rhoKgM3 / 1000.0));
    } else if (liquid === 'viscous') {
      const rho = parseFloat(document.getElementById('input_rho_viscous')?.value || document.querySelector('#viscousParams input[name="rho"]')?.value) || 1000;
      return Math.max(0.5, Math.min(3.0, rho / 1000.0));
    } else if (liquid === 'slurry') {
      const sm = getVal('sg_m');
      if (sm > 0.1) return Math.max(0.5, Math.min(5.0, sm));
      const sl = parseFloat(document.getElementById('sg_l')?.value || 1.0) || 1.0;
      const ss = parseFloat(document.getElementById('sg_s')?.value || 2.65) || 2.65;
      const cv = parseFloat(document.getElementById('slurry_cv')?.value || 0.20) || 0.20;
      const calcSm = sl * (1 - cv) + ss * cv;
      return Math.max(0.5, Math.min(5.0, calcSm > 0 ? calcSm : 1.0));
    }
    return 1.0;
  }

  /**
   * getPumpSelectionFluidDetails()
   * Extracts all fluid parameters currently specified on the Pump Selection page.
   * Handles Clean Water, Viscous fluids (viscosity in cSt, density, pH, concentration, hazard/flammability flags),
   * and Slurries (liquid SG, solid SG, mixture SG, Cv volume concentration, Cw weight concentration, d50 particle size).
   *
   * Engineering Rationale:
   * When sizing pump systems and their connected piping networks, hydraulic calculations
   * (friction factor, head loss, slurry settling velocities) must stay strictly consistent
   * between the pump selection duty point and the network hydraulics solver.
   */
  function getPumpSelectionFluidDetails() {
    let liquid = document.getElementById('liquidSel')?.value || 'water';
    // Fallback: detect active fluid accordion if container is visible
    const slurryParamsEl = document.getElementById('slurryParams');
    const viscousParamsEl = document.getElementById('viscousParams');
    if (slurryParamsEl && slurryParamsEl.style.display !== 'none') {
      liquid = 'slurry';
    } else if (viscousParamsEl && viscousParamsEl.style.display !== 'none') {
      liquid = 'viscous';
    }

    const tempC = getPumpSelectionTemperature();
    const sg = getPumpSelectionSg();
    
    const details = {
      liquid: liquid,
      fluid_type: liquid,
      temperature_c: tempC,
      sg: sg,
      is_viscous: liquid === 'viscous',
      is_slurry: liquid === 'slurry',
    };

    if (liquid === 'water') {
      const rhoRaw = parseFloat(document.getElementById('input_rho_water')?.value) || 1000.0;
      const uRho = document.getElementById('select_unit_rho')?.value || 'kgm3';
      const rhoKgM3 = Number(convertValue(rhoRaw, uRho, 'kgm3', 'density')) || 1000.0;
      details.rho = rhoKgM3;
      details.viscosity_cSt = 1.0;
    } else if (liquid === 'viscous') {
      const rho = parseFloat(document.getElementById('input_rho_viscous')?.value || document.querySelector('#viscousParams input[name="rho"]')?.value) || (sg * 1000.0);
      const visc = parseFloat(document.querySelector('input[name="viscosity_cSt"]')?.value || document.querySelector('#viscousParams input[name="viscosity"]')?.value) || 1.0;
      const ph = parseFloat(document.getElementById('input_fluid_ph')?.value || document.querySelector('#viscousParams input[name="fluid_ph"]')?.value) || 7.0;
      const conc = (document.getElementById('input_fluid_concentration')?.value || document.querySelector('#viscousParams input[name="fluid_concentration"]')?.value || '').trim();
      const isHaz = !!(document.querySelector('input[name="is_hazardous"]')?.checked);
      const isFlam = !!(document.querySelector('input[name="is_flammable"]')?.checked);

      details.rho = rho;
      details.viscosity_cSt = visc;
      details.fluid_ph = ph;
      details.fluid_concentration = conc;
      details.is_hazardous = isHaz;
      details.is_flammable = isFlam;
    } else if (liquid === 'slurry') {
      const sl = parseFloat(document.getElementById('sg_l')?.value) || 1.0;
      const ss = parseFloat(document.getElementById('sg_s')?.value) || 2.65;
      const sm = parseFloat(document.getElementById('sg_m')?.value) || sg;
      const cv = parseFloat(document.getElementById('slurry_cv')?.value) || 0.20;
      const cw = parseFloat(document.getElementById('slurry_cw')?.value) || 0.40;
      const d50 = parseFloat(document.getElementById('input_slurry_d50')?.value) || 0.3;
      const d50Unit = document.getElementById('select_unit_d50')?.value || 'mm';
      // Normalize d50 to mm for hydraulic engine calculations
      const d50Mm = d50Unit === 'um' ? d50 / 1000.0 : (d50Unit === 'm' ? d50 * 1000.0 : d50);

      details.slurry_liquid_sg = sl;
      details.slurry_solid_sg = ss;
      details.slurry_sg = sm;
      details.slurry_c_volume = cv;
      details.slurry_c_weight = cw;
      details.slurry_d50 = d50;
      details.slurry_d50_unit = d50Unit;
      details.slurry_d50_mm = d50Mm;
      details.rho = sm * 1000.0;
    }

    return details;
  }

  /**
   * syncPumpSelectionToPipeNetwork()
   * Propagates flow rate (converted to m3/h), units (flow, head, system), temperature (°C), SG,
   * and comprehensive fluid properties (viscous viscosity/density, slurry mixture properties) into Pipe Network.
   */
  function syncPumpSelectionToPipeNetwork() {
    // 1. Specific Gravity, Fluid Details, and Engineering Units
    syncPumpSelectionSgToStorage();
    syncPumpSelectionFluidDetailsToStorage();
    syncPumpSelectionUnitsToPipeNetwork();

    // 2. Flow Rate (normalized to m3/h)
    const flowM3h = getPumpSelectionFlowM3h();
    if (flowM3h > 0) {
      if (typeof window.__pn_set_flow === 'function') {
        window.__pn_set_flow(flowM3h);
      } else {
        const pnFlow = document.getElementById('pn-global-flow');
        const pnFlowUnit = document.getElementById('pn-flow-unit')?.value || 'm3h';
        const factor = FLOW_UNIT_TO_M3H[pnFlowUnit] || 1.0;
        const convFlow = flowM3h / factor;
        if (pnFlow && document.activeElement !== pnFlow) {
          pnFlow.value = (convFlow % 1 !== 0) ? parseFloat(convFlow.toFixed(2)) : convFlow;
        }
      }
    }

    // 3. Temperature
    const tempC = getPumpSelectionTemperature();
    const pnTemp = document.getElementById('pn-temperature');
    if (pnTemp && document.activeElement !== pnTemp) {
      pnTemp.value = tempC;
    }
    if (typeof window.__pn_set_temperature === 'function') {
      window.__pn_set_temperature(tempC);
    }
  }

  /**
   * syncPumpSelectionUnitsToPipeNetwork()
   * Broadcasts active pump selection engineering units (Flow Q, Head H, NPSH, Static Head, Unit System)
   * into localStorage and directly notifies Pipe Network instance.
   *
   * Engineering Rationale:
   * Sizing pump curves and pipe network hydraulics requires strict dimensional consistency.
   * If a user selects US gpm / ft on Pump Selection, Pipe Network automatically inherits
   * those units for toolbar flow, node elevations, friction losses, and canvas annotations.
   */
  function syncPumpSelectionUnitsToPipeNetwork() {
    const unitQ = document.getElementById('select_unit_q')?.value || 'm3h';
    const unitH = document.getElementById('select_unit_h')?.value || 'm';
    const unitSystem = document.getElementById('unitSystemInput')?.value || (unitQ === 'gpm' || unitH === 'ft' ? 'imperial' : 'metric');
    const unitNpsh = document.getElementById('select_unit_npsh')?.value || unitH;
    const unitStatic = document.getElementById('select_unit_static_head')?.value || unitH;

    const units = {
      flow: unitQ,
      head: unitH,
      system: unitSystem,
      npsh: unitNpsh,
      static_head: unitStatic,
      diameter: unitSystem === 'imperial' ? 'in' : 'mm',
      length: unitSystem === 'imperial' ? 'ft' : 'm',
      pressure: unitSystem === 'imperial' ? 'psi' : 'kpa',
      velocity: unitSystem === 'imperial' ? 'ft/s' : 'm/s',
      source: 'pump_selection',
      timestamp: Date.now()
    };

    try {
      localStorage.setItem('pmpro_shared_units', JSON.stringify(units));
    } catch (e) {
      console.warn('Could not save shared units to localStorage:', e);
    }

    if (typeof window.__pn_set_units === 'function') {
      window.__pn_set_units(units);
    }
  }

  function syncPumpSelectionSgToStorage() {
    const sg = getPumpSelectionSg();
    if (!isNaN(sg) && sg > 0) {
      localStorage.setItem('pmpro_shared_fluid_sg', sg.toFixed(2));
      // Update badge in Pump Selection panel
      const badge = document.getElementById('ps_calculated_sg_badge');
      if (badge) badge.textContent = sg.toFixed(2);
      // Sync into Pipe Network SG input and state if present on page
      const pnSg = document.getElementById('pn-sg');
      if (pnSg && document.activeElement !== pnSg) {
        pnSg.value = sg.toFixed(2);
      }
      if (typeof window.__pn_set_sg === 'function') {
        window.__pn_set_sg(sg);
      }
    }
  }

  /**
   * syncPumpSelectionFluidDetailsToStorage()
   * Persists detailed fluid configuration (viscous properties, slurry concentrations and particle sizes)
   * to localStorage and directly notifies Pipe Network instance if active in memory.
   */
  function syncPumpSelectionFluidDetailsToStorage() {
    const details = getPumpSelectionFluidDetails();
    try {
      localStorage.setItem('pmpro_shared_fluid_details', JSON.stringify(details));
    } catch (e) {
      console.warn('Could not save fluid details to localStorage:', e);
    }
    if (typeof window.__pn_set_fluid_details === 'function') {
      window.__pn_set_fluid_details(details);
    }
  }

  function applyExternalSgToPumpSelection(newSgVal) {
    if (!newSgVal || isNaN(parseFloat(newSgVal))) return;
    const sg = Math.max(0.5, Math.min(5.0, parseFloat(newSgVal)));
    const liquid = document.getElementById('liquidSel')?.value || 'water';
    if (liquid === 'water') {
      const r = document.getElementById('input_rho_water');
      if (r && document.activeElement !== r) {
        const uRho = document.getElementById('select_unit_rho')?.value || 'kgm3';
        r.value = convertValue(sg * 1000.0, 'kgm3', uRho, 'density');
      }
    } else if (liquid === 'viscous') {
      const r = document.getElementById('input_rho_viscous') || document.querySelector('#viscousParams input[name="rho"]');
      if (r && document.activeElement !== r) {
        r.value = (sg * 1000).toFixed(1);
      }
    } else if (liquid === 'slurry') {
      const smEl = document.getElementById('sg_m');
      if (smEl && document.activeElement !== smEl) {
        smEl.value = sg.toFixed(2);
      }
      const sl = parseFloat(document.getElementById('sg_l')?.value || 1.0) || 1.0;
      const ss = parseFloat(document.getElementById('sg_s')?.value || 2.65) || 2.65;
      if (ss > sl) {
        let newCv = (sg - sl) / (ss - sl);
        newCv = Math.max(0.0, Math.min(0.65, newCv));
        const cvEl = document.getElementById('slurry_cv');
        if (cvEl && document.activeElement !== cvEl) {
          cvEl.value = newCv.toFixed(3);
        }
      }
      updateSlurryCalculator();
    }
    const badge = document.getElementById('ps_calculated_sg_badge');
    if (badge) badge.textContent = sg.toFixed(2);
  }

  /**
   * applyExternalUnitsToPumpSelection(units)
   * Receives unit updates from Pipe Network and synchronizes Pump Selection dropdowns and inputs.
   */
  function applyExternalUnitsToPumpSelection(units) {
    if (!units) return;
    let changed = false;
    if (units.flow) {
      const selQ = document.getElementById('select_unit_q');
      if (selQ && selQ.value !== units.flow) {
        const prev = selQ.value;
        selQ.value = units.flow;
        selQ.dataset.prev = units.flow;
        const qInp = document.getElementById('input_q_duty');
        if (qInp && qInp.value !== '') {
          qInp.value = convertValue(qInp.value, prev, units.flow, 'flow');
        }
        changed = true;
      }
    }
    if (units.head) {
      const selH = document.getElementById('select_unit_h');
      if (selH && selH.value !== units.head) {
        const prev = selH.value;
        selH.value = units.head;
        selH.dataset.prev = units.head;
        const hInp = document.getElementById('input_h_duty');
        if (hInp && hInp.value !== '') {
          hInp.value = convertValue(hInp.value, prev, units.head, 'head');
        }
        changed = true;
      }
    }
    if (changed) {
      updateSystemBadge();
    }
  }

  function syncPipeNetworkToPumpSelection() {
    // 1. SG
    const pnSg = document.getElementById('pn-sg');
    if (pnSg) {
      const val = parseFloat(pnSg.value);
      if (!isNaN(val) && val > 0) {
        applyExternalSgToPumpSelection(val);
      }
    }

    // 2. Flow Rate (respecting active flow unit on Pipe Network)
    let flowM3h = null;
    if (typeof window.__pn_get_flow_m3h === 'function') {
      flowM3h = window.__pn_get_flow_m3h();
    } else {
      const pnFlow = document.getElementById('pn-global-flow');
      const pnFlowUnit = document.getElementById('pn-flow-unit')?.value || 'm3h';
      if (pnFlow) {
        const rawVal = parseFloat(pnFlow.value);
        if (!isNaN(rawVal) && rawVal > 0) {
          const factor = FLOW_UNIT_TO_M3H[pnFlowUnit] || 1.0;
          flowM3h = rawVal * factor;
        }
      }
    }
    if (flowM3h !== null && flowM3h > 0) {
      setPumpSelectionFlowFromM3h(flowM3h);
    }

    // 3. Units from Pipe Network
    if (typeof window.__pn_get_units === 'function') {
      const pnUnits = window.__pn_get_units();
      applyExternalUnitsToPumpSelection(pnUnits);
    }

    // 4. Temperature
    const pnTemp = document.getElementById('pn-temperature');
    if (pnTemp) {
      const tempC = parseFloat(pnTemp.value);
      if (!isNaN(tempC)) {
        const tInp = document.getElementById('input_temperature_c');
        if (tInp && document.activeElement !== tInp) {
          tInp.value = tempC;
        }
      }
    }
  }

  /**
   * showDutyPointAppliedToast(displayQ, displayH, displayStatic, displayNpsh)
   * Renders a modern floating confirmation toast when pipe network results are applied.
   */
  function showDutyPointAppliedToast(displayQ, displayH, displayStatic, displayNpsh) {
    const existing = document.getElementById('pmpro-duty-toast');
    if (existing) existing.remove();

    const toastEl = document.createElement('div');
    toastEl.id = 'pmpro-duty-toast';
    toastEl.style.cssText = `
      position: fixed;
      bottom: 28px;
      right: 28px;
      z-index: 10050;
      background: #161b22;
      border: 1px solid #22c55e;
      border-radius: 10px;
      padding: 14px 18px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.6), 0 0 15px rgba(34,197,94,0.25);
      color: #f0f6fc;
      font-size: 12.5px;
      line-height: 1.5;
      min-width: 280px;
      animation: popoverFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    `;
    toastEl.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;border-bottom:1px solid #30363d;padding-bottom:6px;">
        <span style="font-weight:700;color:#22c55e;display:flex;align-items:center;gap:6px;">
          <i class="bi bi-check-circle-fill"></i> Duty Point Applied to Selection!
        </span>
        <button type="button" onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px;line-height:1;padding:0 2px;">&times;</button>
      </div>
      <div style="font-family:monospace;font-size:12px;display:flex;flex-direction:column;gap:3px;color:#cbd5e1;">
        ${displayQ ? `<div>Flow Rate (Q): <strong style="color:#38bdf8;">${displayQ}</strong></div>` : ''}
        ${displayH ? `<div>Total Head (H): <strong style="color:#fbbf24;">${displayH}</strong></div>` : ''}
        ${displayStatic ? `<div>Static Head (Hs): <strong style="color:#c084fc;">${displayStatic}</strong></div>` : ''}
        ${displayNpsh ? `<div>NPSH Available: <strong style="color:#2dd4bf;">${displayNpsh}</strong></div>` : ''}
      </div>
    `;
    document.body.appendChild(toastEl);
    setTimeout(() => {
      if (toastEl.parentElement) {
        toastEl.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        toastEl.style.opacity = '0';
        toastEl.style.transform = 'translateY(10px)';
        setTimeout(() => toastEl.remove(), 400);
      }
    }, 5500);
  }

  /**
   * applyDutyPointToPumpSelection(data)
   *
   * Core bridge transferring calculated pipe network hydraulics into Pump Selection form fields:
   *  1. Flow Rate (Q)           -> #input_q_duty (converted to active select_unit_q)
   *  2. Total Dynamic Head (TDH) -> #input_h_duty (converted to active select_unit_h)
   *  3. Static Elevation (Hs)   -> #input_static_head (converted to active select_unit_static_head)
   *  4. NPSH Available (NPSHa)  -> #input_npsh_avail (converted to active select_unit_npsh)
   *  5. Fluid & Site Properties  -> temperature, fluid type, density/SG, viscosity, slurry
   *
   * Triggers 'input' and 'change' events across all inputs, switches active tab to 'selection',
   * pulses the Duty Point card with an emerald highlight, and notifies the user with a summary toast.
   *
   * @param {Object} data - Hydraulic calculation summary
   */
  function applyDutyPointToPumpSelection(data) {
    if (!data) return;

    // 1. Flow Rate Q
    const qInp = document.getElementById('input_q_duty');
    const unitQSel = document.getElementById('select_unit_q');
    const unitQ = unitQSel?.value || 'm3h';
    let displayQ = '';
    if (data.flow_m3h !== undefined && data.flow_m3h !== null && !isNaN(Number(data.flow_m3h))) {
      const qVal = convertValue(data.flow_m3h, 'm3h', unitQ, 'flow');
      if (qInp) {
        qInp.value = qVal;
        displayQ = `${qVal} ${unitQSel?.options[unitQSel.selectedIndex]?.text || unitQ}`;
      }
    } else if (data.flow_user_unit !== undefined && qInp) {
      qInp.value = data.flow_user_unit;
      displayQ = `${data.flow_user_unit} ${unitQ}`;
    }

    // 2. Total Dynamic Head H (TDH)
    const hInp = document.getElementById('input_h_duty');
    const unitHSel = document.getElementById('select_unit_h');
    const unitH = unitHSel?.value || 'm';
    let displayH = '';
    if (data.head_m !== undefined && data.head_m !== null && !isNaN(Number(data.head_m))) {
      const hVal = convertValue(data.head_m, 'm', unitH, 'head');
      if (hInp) {
        hInp.value = hVal;
        displayH = `${hVal} ${unitHSel?.options[unitHSel.selectedIndex]?.text || unitH}`;
      }
    } else if (data.total_system_head_user_unit !== undefined && hInp) {
      hInp.value = data.total_system_head_user_unit;
      displayH = `${data.total_system_head_user_unit} ${unitH}`;
    }

    // 3. Static Elevation Head Hs
    const staticInp = document.getElementById('input_static_head');
    const unitStaticSel = document.getElementById('select_unit_static_head');
    const unitStatic = unitStaticSel?.value || 'm';
    let displayStatic = '';
    if (data.static_head_m !== undefined && data.static_head_m !== null && !isNaN(Number(data.static_head_m))) {
      const staticVal = convertValue(data.static_head_m, 'm', unitStatic, 'head');
      if (staticInp) {
        staticInp.value = staticVal;
        displayStatic = `${staticVal} ${unitStaticSel?.options[unitStaticSel.selectedIndex]?.text || unitStatic}`;
      }
    }

    // 4. Net Positive Suction Head Available (NPSHa)
    const npshInp = document.getElementById('input_npsh_avail');
    const unitNpshSel = document.getElementById('select_unit_npsh');
    const unitNpsh = unitNpshSel?.value || 'm';
    let displayNpsh = '';
    if (data.npsha_m !== undefined && data.npsha_m !== null && !isNaN(Number(data.npsha_m)) && Number(data.npsha_m) > 0) {
      const npshVal = convertValue(data.npsha_m, 'm', unitNpsh, 'head');
      if (npshInp) {
        npshInp.value = npshVal;
        displayNpsh = `${npshVal} ${unitNpshSel?.options[unitNpshSel.selectedIndex]?.text || unitNpsh}`;
      }
    }

    // 5. Environmental & Fluid Conditions
    if (data.temperature_c !== undefined && data.temperature_c !== null) {
      const tInp = document.getElementById('input_temperature_c');
      if (tInp) tInp.value = data.temperature_c;
    }

    const fluidType = data.liquid || data.fluid_type || 'water';
    const liquidSel = document.getElementById('liquidSel');
    if (liquidSel && liquidSel.value !== fluidType) {
      // Validate that the requested fluid exists in permitted options before setting it
      const hasOption = Array.from(liquidSel.options).some(o => o.value === fluidType);
      if (hasOption) {
        liquidSel.value = fluidType;
      } else if (liquidSel.options.length > 0) {
        liquidSel.selectedIndex = 0;
      }
      liquidSel.dispatchEvent(new Event('change', { bubbles: true }));
    }

    const sgVal = data.specific_gravity || (data.density_kg_m3 ? data.density_kg_m3 / 1000.0 : null);
    if (sgVal) {
      applyExternalSgToPumpSelection(sgVal);
    }

    if (data.viscosity_cSt !== undefined && data.viscosity_cSt !== null) {
      const viscInp = document.querySelector('#viscousParams input[name="viscosity_cSt"]');
      if (viscInp) viscInp.value = data.viscosity_cSt;
    }
    if (data.fluid_ph !== undefined && data.fluid_ph !== null) {
      const phInp = document.getElementById('input_fluid_ph');
      if (phInp) phInp.value = data.fluid_ph;
    }
    if (data.fluid_concentration !== undefined && data.fluid_concentration !== null) {
      const concInp = document.getElementById('input_fluid_concentration');
      if (concInp) concInp.value = data.fluid_concentration;
    }

    // Slurry properties if applicable
    if (fluidType === 'slurry') {
      if (data.slurry_liquid_sg) { const el = document.getElementById('sg_l'); if (el) el.value = data.slurry_liquid_sg; }
      if (data.slurry_solids_sg) { const el = document.getElementById('sg_s'); if (el) el.value = data.slurry_solids_sg; }
      if (data.slurry_c_weight)  { const el = document.getElementById('slurry_cw'); if (el) el.value = data.slurry_c_weight; }
      if (data.slurry_d50_mm)    { const el = document.getElementById('input_slurry_d50'); if (el) el.value = data.slurry_d50_mm; }
    }

    // 5b. Pump Arrangement (single, parallel, series)
    if (data.pump_arrangement || data.arrangement) {
      const arr = data.pump_arrangement || data.arrangement;
      const radio = document.getElementById(`arr_${arr}`);
      if (radio) {
        radio.checked = true;
        if (data.pumps_operating) {
          const opInp = document.getElementById('pumps_operating');
          if (opInp) opInp.value = data.pumps_operating;
        }
        if (data.pumps_standby !== undefined) {
          const stbyInp = document.getElementById('pumps_standby');
          if (stbyInp) stbyInp.value = data.pumps_standby;
        }
        if (typeof window.onPumpArrangementChange === 'function') {
          window.onPumpArrangementChange(arr);
        } else if (typeof window.updateMultiPumpCalculations === 'function') {
          window.updateMultiPumpCalculations();
        }
      }
    }

    // 6. Trigger reactive input & change events
    [qInp, hInp, staticInp, npshInp].forEach(el => {
      if (el) {
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    // 7. Switch active tab to Pump Selection
    if (typeof window.switchSelectionTab === 'function') {
      window.switchSelectionTab('selection');
    }

    // 8. Visual feedback: scroll to Duty Point card and pulse glow
    const dutyCard = qInp?.closest('.card-dark');
    if (dutyCard) {
      dutyCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      dutyCard.classList.remove('duty-applied-pulse');
      void dutyCard.offsetWidth; // Trigger CSS DOM reflow
      dutyCard.classList.add('duty-applied-pulse');
      setTimeout(() => dutyCard.classList.remove('duty-applied-pulse'), 3000);
    }

    // 9. Display confirmation toast notification
    showDutyPointAppliedToast(displayQ, displayH, displayStatic, displayNpsh);
  }

  // Window exports for cross-component access
  window.getPumpSelectionFlowM3h = getPumpSelectionFlowM3h;
  window.setPumpSelectionFlowFromM3h = setPumpSelectionFlowFromM3h;
  window.getPumpSelectionTemperature = getPumpSelectionTemperature;
  window.getPumpSelectionSg = getPumpSelectionSg;
  window.getPumpSelectionFluidDetails = getPumpSelectionFluidDetails;
  window.syncPumpSelectionToPipeNetwork = syncPumpSelectionToPipeNetwork;
  window.syncPipeNetworkToPumpSelection = syncPipeNetworkToPumpSelection;
  window.syncPumpSelectionSgToPipeNetwork = syncPumpSelectionToPipeNetwork;
  window.syncPumpSelectionFluidDetailsToStorage = syncPumpSelectionFluidDetailsToStorage;
  window.syncPipeNetworkSgToPumpSelection = syncPipeNetworkToPumpSelection;
  window.syncPumpSelectionUnitsToPipeNetwork = syncPumpSelectionUnitsToPipeNetwork;
  window.applyExternalUnitsToPumpSelection = applyExternalUnitsToPumpSelection;
  window.applyDutyPointToPumpSelection = applyDutyPointToPumpSelection;

  // Attach input listeners for live Flow, Temp, Units, Fluid Type, and Fluid Properties sync
  ['input_q_duty', 'select_unit_q', 'select_unit_h', 'select_unit_npsh', 'select_unit_static_head', 'input_temperature_c', 'input_rho_water', 'liquidSel', 'input_rho_viscous', 'input_fluid_ph', 'input_fluid_concentration', 'sg_l', 'sg_s', 'sg_m', 'slurry_cv', 'slurry_cw', 'input_slurry_d50', 'select_unit_d50'].forEach(id => {
    const el = document.getElementById(id);
    el?.addEventListener('input', syncPumpSelectionToPipeNetwork);
    el?.addEventListener('change', syncPumpSelectionToPipeNetwork);
  });
  document.querySelectorAll('#viscousParams input, #viscousParams select').forEach(inp => {
    inp.addEventListener('input', syncPumpSelectionToPipeNetwork);
    inp.addEventListener('change', syncPumpSelectionToPipeNetwork);
  });
  slurryInputs.forEach(inp => {
    inp.addEventListener('input', syncPumpSelectionToPipeNetwork);
    inp.addEventListener('change', syncPumpSelectionToPipeNetwork);
  });

  window.addEventListener('storage', (e) => {
    if (e.key === 'pmpro_shared_fluid_sg' && e.newValue) {
      applyExternalSgToPumpSelection(e.newValue);
    }
    if (e.key === 'pmpro_shared_units' && e.newValue) {
      try {
        const u = JSON.parse(e.newValue);
        if (u && u.source === 'pipe_network') {
          applyExternalUnitsToPumpSelection(u);
        }
      } catch (err) {}
    }
  });

  syncPumpSelectionSgToStorage();
  syncPumpSelectionFluidDetailsToStorage();
  syncPumpSelectionUnitsToPipeNetwork();


  // ── Pump comparison checkbox logic ─────────────────────────────────────────
  // Beginners Note: Builds a comparison URL when multiple pumps are selected via checkboxes
  const compareLink  = document.getElementById('compareLink');
  const compareCount = document.getElementById('compareCount');
  const checkboxes   = document.querySelectorAll('.pump-compare-cb');

  function updateCompareLink() {
    const selected = [...document.querySelectorAll('.pump-compare-cb:checked')].map(cb => cb.value);
    if (compareCount) compareCount.textContent = selected.length;
    if (compareLink) {
      if (selected.length >= 1) {
        const liquid = document.getElementById('liquidSel')?.value || 'water';
        const qDuty  = document.querySelector('[name=q_duty]')?.value || '';
        const hDuty  = document.querySelector('[name=h_duty]')?.value || '';
        const arrRadio = document.querySelector('input[name="pump_arrangement"]:checked');
        const pumpArr = arrRadio ? arrRadio.value : 'single';
        const pumpsOp = document.getElementById('pumps_operating')?.value || '1';
        const pumpsStby = document.getElementById('pumps_standby')?.value || '0';
        compareLink.href = `/pump-comparison?${params}&liquid=${liquid}&q_duty=${qDuty}&h_duty=${hDuty}&pump_arrangement=${pumpArr}&pumps_operating=${pumpsOp}&pumps_standby=${pumpsStby}`;
        compareLink.classList.remove('disabled', 'pointer-events-none', 'opacity-50');
        compareLink.style.background = 'rgba(57,211,192,0.15)';
      } else {
        compareLink.classList.add('disabled', 'pointer-events-none', 'opacity-50');
        compareLink.style.background = 'transparent';
        compareLink.href = '#';
      }
    }
  }

  checkboxes.forEach(cb => cb.addEventListener('change', updateCompareLink));
  updateCompareLink();

  // ── Render SVG Sparklines ──────────────────────────────────────────────────
  // Beginners Note: Finds all container divs with 'data-chart' attribute and draws an inline SVG
  initSparklines();

});

// ── SVG Sparkline Initialization ─────────────────────────────────────────────
// Beginners Note: Scans DOM for .sparkline-container and renders tombstone curves
function initSparklines() {
  const sparkContainers = document.querySelectorAll('.sparkline-container');
  sparkContainers.forEach(container => {
    try {
      if (container.querySelector('svg')) return; // Already rendered
      const dataStr = container.getAttribute('data-chart');
      if (!dataStr) return;
      const chartData = JSON.parse(dataStr);
      renderSparkline(container, chartData);
    } catch (e) {
      console.error('Error rendering sparkline:', e);
      container.innerHTML = '<div class="text-[9px] text-red-400">Chart err</div>';
    }
  });
}

// Expose globally so external scripts and HTML templates can trigger anytime
window.initSparklines = initSparklines;

// If DOM is already parsed when this script executes, run sparkline rendering immediately
if (document.readyState === 'interactive' || document.readyState === 'complete') {
  try {
    initSparklines();
  } catch (err) {
    console.warn('Immediate sparkline render notice:', err);
  }
}

// ── Attribute Panel Toggle ──────────────────────────────────────────────────
function toggleAttrPanel() {
  const panel = document.getElementById('attrPanel');
  const chevron = document.getElementById('attrChevron');
  if (!panel) return;
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    if (chevron) chevron.style.transform = 'rotate(180deg)';
  } else {
    panel.style.display = 'none';
    if (chevron) chevron.style.transform = 'rotate(0deg)';
  }
}

// ── Client-side Live Search & Rating Filter for Minimal Shortlist ────────────
let currentRatingFilter = 'all';

function applyRatingFilter(cat, btn) {
  currentRatingFilter = cat;
  document.querySelectorAll('.rating-filter-pill').forEach(b => {
    b.classList.remove('bg-[#21262d]', 'text-[#58a6ff]');
    b.classList.add('text-[#8b949e]');
  });
  if (btn) {
    btn.classList.add('bg-[#21262d]', 'text-[#58a6ff]');
    btn.classList.remove('text-[#8b949e]');
  }
  filterShortlistItems();
}

function filterShortlistItems() {
  const query = (document.getElementById('shortlistSearch')?.value || '').toLowerCase().trim();
  const items = document.querySelectorAll('.sel-mini-card');
  let visibleCount = 0;

  items.forEach(card => {
    const name = card.dataset.name || '';
    const size = card.dataset.size || '';
    const ratingCat = card.dataset.ratingCat || '';

    const matchesQuery = !query || name.includes(query) || size.includes(query);
    const matchesRating = currentRatingFilter === 'all' || ratingCat === currentRatingFilter;

    if (matchesQuery && matchesRating) {
      card.style.display = '';
      visibleCount++;
    } else {
      card.style.display = 'none';
    }
  });

  const countDisplay = document.getElementById('shortlistCountDisplay');
  if (countDisplay) {
    countDisplay.textContent = visibleCount;
  }

  const notice = document.getElementById('noFilterMatchesNotice');
  if (notice) {
    notice.style.display = (visibleCount === 0 && items.length > 0) ? 'block' : 'none';
  }
}

function clearShortlistFilter() {
  const searchInput = document.getElementById('shortlistSearch');
  if (searchInput) searchInput.value = '';
  const allBtn = document.querySelector('.rating-filter-pill[data-filter="all"]');
  applyRatingFilter('all', allBtn);
}

// ── Combined Filter Panel Toggle ─────────────────────────────────────────────
// Beginners Note: Toggles the unified specifications and catalogue filter panel open/closed
function toggleFilterPanel() {
  const panel = document.getElementById('filterPanel');
  const chevron = document.getElementById('filterChevron');
  if (!panel) return;
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    if (chevron) chevron.style.transform = 'rotate(180deg)';
  } else {
    panel.style.display = 'none';
    if (chevron) chevron.style.transform = 'rotate(0deg)';
  }
}

// ── Clear All Filters ────────────────────────────────────────────────────────
// Beginners Note: Resets all filter dropdowns and text inputs (both standard catalogue filters
// and organisation custom PumpAttributes) back to blank/default, then automatically resubmits.
function clearAllFilters() {
  const panel = document.getElementById('filterPanel');
  if (panel) {
    const selects = panel.querySelectorAll('select');
    selects.forEach(s => s.value = '');
    const inputs = panel.querySelectorAll('input[type="text"], input[type="number"]');
    inputs.forEach(i => i.value = '');
  }

  const form = document.getElementById('selectionForm');
  if (form) {
    form.submit();
  }
}

// ── Client-side Instant Sorting Logic (No Page Reload) ───────────────────────
// Beginners Note:
// Re-orders the shortlisted pump cards in the DOM immediately without sending
// an HTTP POST/GET request or reloading the entire webpage.
// Supports both Ascending (Low to High) and Descending (High to Low) sorting.
let currentSortKey = 'rating';
let currentSortDirection = 'desc'; // 'desc' (high to low) or 'asc' (low to high)

function toggleSortDirection() {
  currentSortDirection = (currentSortDirection === 'desc') ? 'asc' : 'desc';
  const icon = document.getElementById('sortDirectionIcon');
  const btn = document.getElementById('btnSortDirection');
  if (icon) {
    if (currentSortDirection === 'asc') {
      icon.className = 'bi bi-sort-up';
      if (btn) btn.title = 'Order: Ascending (Low to High). Click to switch to Descending.';
    } else {
      icon.className = 'bi bi-sort-down';
      if (btn) btn.title = 'Order: Descending (High to Low). Click to switch to Ascending.';
    }
  }
  applyClientSort();
}

function applyClientSort() {
  const select = document.getElementById('clientSortSel');
  if (select) {
    currentSortKey = select.value;
  }

  const container = document.getElementById('shortlistItemsContainer');
  if (!container) return;

  const cards = Array.from(container.querySelectorAll('.sel-mini-card'));
  if (cards.length === 0) return;

  cards.sort((a, b) => {
    let valA, valB;
    if (currentSortKey === 'name') {
      valA = a.dataset.name || '';
      valB = b.dataset.name || '';
      const comp = valA.localeCompare(valB);
      return (currentSortDirection === 'asc') ? comp : -comp;
    } else if (currentSortKey === 'efficiency') {
      valA = parseFloat(a.dataset.efficiency) || 0;
      valB = parseFloat(b.dataset.efficiency) || 0;
    } else if (currentSortKey === 'power') {
      valA = parseFloat(a.dataset.power) || 0;
      valB = parseFloat(b.dataset.power) || 0;
    } else if (currentSortKey === 'bep') {
      valA = parseFloat(a.dataset.bep) || 0;
      valB = parseFloat(b.dataset.bep) || 0;
    } else {
      // Default: rating
      valA = parseFloat(a.dataset.rating) || 0;
      valB = parseFloat(b.dataset.rating) || 0;
    }

    return (currentSortDirection === 'asc') ? (valA - valB) : (valB - valA);
  });

  // Re-append sorted cards into container without destroying rendered inner elements
  const notice = document.getElementById('noFilterMatchesNotice');
  cards.forEach(card => container.appendChild(card));
  if (notice) container.appendChild(notice);

  // Ensure any sparklines that need rendering are drawn
  initSparklines();
}

// ── SVG Tombstone Sparkline Renderer ─────────────────────────────────────────
// Beginners Note:
// Draws a compact SVG H-Q envelope curve (max impeller, min impeller trim bounds,
// optimal trim curve, and operating duty point crosshair) for instant visual recognition.
function renderSparkline(container, data) {
  const width = 130;
  const height = 50;
  const padding = { top: 4, right: 6, bottom: 6, left: 6 };
  
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  
  const maxQ = Math.max(1, (data.q_range && data.q_range[1] > 0) ? data.q_range[1] : (data.q_max && data.q_max.length > 0 ? Math.max(...data.q_max) * 1.05 : 100));
  const maxH = Math.max(1, (data.h_range && data.h_range[1] > 0) ? data.h_range[1] : (data.h_max && data.h_max.length > 0 ? Math.max(...data.h_max) * 1.05 : 100));
  
  // Coordinate mapping functions
  const x = val => padding.left + (val / maxQ) * innerWidth;
  const y = val => padding.top + innerHeight - (val / maxH) * innerHeight;

  // Path generator
  const createPath = (qArr, hArr) => {
    if (!qArr || !hArr || qArr.length === 0 || qArr.length !== hArr.length) return '';
    let d = `M ${x(qArr[0]).toFixed(1)} ${y(hArr[0]).toFixed(1)}`;
    for (let i = 1; i < qArr.length; i++) {
      d += ` L ${x(qArr[i]).toFixed(1)} ${y(hArr[i]).toFixed(1)}`;
    }
    return d;
  };

  // Build SVG with 100% width/height to fill the container responsively
  let svg = `<svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" class="block overflow-visible">`;

  // Subtle axis lines (baseline & left axis)
  svg += `<line x1="${padding.left}" y1="${padding.top + innerHeight}" x2="${padding.left + innerWidth}" y2="${padding.top + innerHeight}" stroke="#30363d" stroke-width="1" />`;
  svg += `<line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${padding.top + innerHeight}" stroke="#30363d" stroke-width="1" />`;

  // Draw envelope fill area
  if (data.q_max && data.q_min && data.q_min.length > 0) {
    let dArea = createPath(data.q_max, data.h_max);
    for (let i = data.q_min.length - 1; i >= 0; i--) {
      dArea += ` L ${x(data.q_min[i]).toFixed(1)} ${y(data.h_min[i]).toFixed(1)}`;
    }
    dArea += ' Z';
    svg += `<path d="${dArea}" fill="rgba(88,166,255,0.18)" />`;
  } else if (data.q_max && data.q_max.length > 0) {
    // Fill from max curve down to baseline
    let dArea = createPath(data.q_max, data.h_max);
    dArea += ` L ${x(data.q_max[data.q_max.length - 1]).toFixed(1)} ${(padding.top + innerHeight).toFixed(1)}`;
    dArea += ` L ${x(data.q_max[0]).toFixed(1)} ${(padding.top + innerHeight).toFixed(1)} Z`;
    svg += `<path d="${dArea}" fill="rgba(88,166,255,0.15)" />`;
  }

  // Draw Max curve (solid blue)
  if (data.q_max && data.q_max.length > 0) {
    svg += `<path d="${createPath(data.q_max, data.h_max)}" fill="none" stroke="#58a6ff" stroke-width="1.5" />`;
  }

  // Draw Min curve (dashed blue)
  if (data.q_min && data.q_min.length > 0) {
    svg += `<path d="${createPath(data.q_min, data.h_min)}" fill="none" stroke="#58a6ff" stroke-width="1" stroke-dasharray="2,2" opacity="0.6" />`;
  }

  // Draw Optimal Trim curve (dotted green)
  if (data.q_trim && data.q_trim.length > 0) {
    svg += `<path d="${createPath(data.q_trim, data.h_trim)}" fill="none" stroke="#3fb950" stroke-width="1.2" stroke-dasharray="2,2" />`;
  }

  // Draw Duty Point (red target point + crosshair)
  if (data.q_duty !== undefined && data.h_duty !== undefined) {
    const dx = x(data.q_duty);
    const dy = y(data.h_duty);
    const crossSize = 3.5;
    svg += `<line x1="${(dx - crossSize).toFixed(1)}" y1="${dy.toFixed(1)}" x2="${(dx + crossSize).toFixed(1)}" y2="${dy.toFixed(1)}" stroke="#f85149" stroke-width="1.5" />`;
    svg += `<line x1="${dx.toFixed(1)}" y1="${(dy - crossSize).toFixed(1)}" x2="${dx.toFixed(1)}" y2="${(dy + crossSize).toFixed(1)}" stroke="#f85149" stroke-width="1.5" />`;
    svg += `<circle cx="${dx.toFixed(1)}" cy="${dy.toFixed(1)}" r="2" fill="#f85149" stroke="#ffffff" stroke-width="0.8" />`;
  }

  // Small watermark badge
  svg += `<text x="${(width - padding.right).toFixed(1)}" y="${(padding.top + 7).toFixed(1)}" text-anchor="end" font-size="7" fill="#8b949e" font-family="monospace">H-Q</text>`;

  svg += `</svg>`;
  container.innerHTML = svg;
}
window.renderSparkline = renderSparkline;

// ── Operation Mode & Motor/Drive Arrangement Handlers ───────────────────────
// Beginners Note:
// 1. Toggles between Fixed Speed options (auto calculation vs manual speed) and VSD frequency limits bounds
// 2. Toggles manual motor dropdown when switching between Automatic and Manual motor selection
// 3. Asynchronously fetches available motors from /papi/motors-by-spec when Frequency or Poles change
function onOperationModeChange() {
  const isVsd = document.getElementById('opModeVsd')?.checked;
  const vsdFreqGroup = document.getElementById('vsdFrequencyLimitsGroup');
  const vsdOptionsGroup = document.getElementById('vsdOptionsGroup');
  const fixedSpeedGroup = document.getElementById('fixedSpeedOptionsGroup');
  if (vsdFreqGroup) {
    vsdFreqGroup.style.display = isVsd ? 'block' : 'none';
  }
  if (vsdOptionsGroup) {
    vsdOptionsGroup.style.display = isVsd ? 'block' : 'none';
  }
  if (fixedSpeedGroup) {
    fixedSpeedGroup.style.display = isVsd ? 'none' : 'block';
  }
}

// Fixed speed sub-option: Toggle manual pump speed vs min-max speed range inputs
function onFixedSpeedModeChange() {
  const isManual = document.getElementById('fixedSpeedManual')?.checked;
  const isRange = document.getElementById('fixedSpeedRange')?.checked;

  const manualGroup = document.getElementById('manualPumpSpeedGroup');
  if (manualGroup) {
    manualGroup.style.display = isManual ? 'block' : 'none';
    const input = document.getElementById('manualPumpSpeedRpm');
    if (isManual && input && !input.value) {
      input.focus();
    }
  }

  const rangeGroup = document.getElementById('fixedSpeedRangeGroup');
  if (rangeGroup) {
    rangeGroup.style.display = isRange ? 'block' : 'none';
    const minInput = document.getElementById('fixedSpeedMinRpm');
    if (isRange && minInput && !minInput.value) {
      minInput.focus();
    }
  }
}

// Variable speed drive (VSD) sub-option: Toggle impeller trimming mode inputs
function onVsdTrimModeChange() {
  const trimMode = document.querySelector('input[name="vsd_trim_mode"]:checked')?.value || 'auto';

  const manualMmGroup = document.getElementById('vsdManualMmGroup');
  const rangeMmGroup = document.getElementById('vsdRangeMmGroup');
  const rangePctGroup = document.getElementById('vsdRangePctGroup');

  if (manualMmGroup) {
    manualMmGroup.style.display = (trimMode === 'manual_mm') ? 'block' : 'none';
    if (trimMode === 'manual_mm') {
      const input = document.getElementById('vsdTrimDiaMm');
      if (input && !input.value) input.focus();
    }
  }

  if (rangeMmGroup) {
    rangeMmGroup.style.display = (trimMode === 'range_mm') ? 'block' : 'none';
    if (trimMode === 'range_mm') {
      const input = document.getElementById('vsdTrimMinMm');
      if (input && !input.value) input.focus();
    }
  }

  if (rangePctGroup) {
    rangePctGroup.style.display = (trimMode === 'range_pct') ? 'block' : 'none';
    if (trimMode === 'range_pct') {
      const input = document.getElementById('vsdTrimMinPct');
      if (input && !input.value) input.focus();
    }
  }
}

function updatePolesLabels(freq) {
  const polesSelect = document.getElementById('motorPolesSel');
  if (!polesSelect) return;
  const speeds50 = { '2': '~3000 RPM', '4': '~1500 RPM', '6': '~1000 RPM', '8': '~750 RPM' };
  const speeds60 = { '2': '~3600 RPM', '4': '~1800 RPM', '6': '~1200 RPM', '8': '~900 RPM' };
  const speeds = (freq === 60) ? speeds60 : speeds50;

  Array.from(polesSelect.options).forEach(opt => {
    const p = opt.value;
    if (speeds[p]) {
      opt.textContent = `${p} Poles (${speeds[p]})`;
    }
  });
}

function onMotorSelectionModeChange() {
  const isManual = document.getElementById('motorSelectManual')?.checked;
  const manualGroup = document.getElementById('manualMotorGroup');
  if (manualGroup) {
    manualGroup.style.display = isManual ? 'block' : 'none';
    const input = document.getElementById('manualMotorSpeedRpm');
    if (isManual && input && !input.value) {
      input.focus();
    }
  }
}

async function onMotorSpecChange() {
  const freqRadio = document.querySelector('input[name="motor_freq_hz"]:checked');
  const freq = freqRadio ? parseInt(freqRadio.value, 10) : 50;

  // 1. Dynamically update suggested speed in Poles dropdown options
  updatePolesLabels(freq);

  // 2. Auto-adjust default max VSD frequency if it matches standard mains
  const maxFreqInput = document.getElementById('inputVsdFMax');
  if (maxFreqInput) {
    const curVal = parseFloat(maxFreqInput.value);
    if (freq === 60 && curVal === 50) {
      maxFreqInput.value = '60.0';
    } else if (freq === 50 && curVal === 60) {
      maxFreqInput.value = '50.0';
    }
  }
}

// ── Quick Application / Pump Type Filter & Fire Protection Calculator ──

/**
 * syncDutyInputsLocation(isFire)
 * Moves usualDutyInputsCard between #fp_custom_duty_slot (in Fire Mode)
 * and #non_fire_duty_slot (in Standard / Non-Fire Mode).
 */
function syncDutyInputsLocation(isFire) {
  const usualCard = document.getElementById('usualDutyInputsCard');
  const fireSlot = document.getElementById('fp_custom_duty_slot');
  const nonFireSlot = document.getElementById('non_fire_duty_slot');
  if (!usualCard || !fireSlot || !nonFireSlot) return;

  if (isFire) {
    if (usualCard.parentNode !== fireSlot) {
      fireSlot.appendChild(usualCard);
    }
    nonFireSlot.style.display = 'none';
  } else {
    if (usualCard.parentNode !== nonFireSlot) {
      nonFireSlot.appendChild(usualCard);
    }
    nonFireSlot.style.display = '';
  }
}



/**
 * setQuickPumpType(typeVal)
 * Handles clicking the quick segmented buttons:
 *   '' => All Types
 *   'centrifugal' => Clean water centrifugal
 *   'slurry' => Slurry pumps
 *   'fire pump' => Fire pumps
 */
function setQuickPumpType(typeVal) {
  const normVal = (typeVal || '').trim().toLowerCase();
  const filterSelect = document.getElementById('filter_pump_type');
  if (filterSelect) {
    let found = false;
    for (let i = 0; i < filterSelect.options.length; i++) {
      const optVal = filterSelect.options[i].value.toLowerCase();
      if ((normVal === 'fire pump' && (optVal === 'fire pump' || optVal === 'fire' || optVal === 'fire_pump')) ||
          (normVal === optVal)) {
        filterSelect.selectedIndex = i;
        found = true;
        break;
      }
    }
    if (!found && normVal === '') {
      filterSelect.value = '';
    }
  }

  // Update segmented button active styles
  updateQuickPumpTypeUI(normVal);

  // Toggle Fire Protection Calculator Panel and Right Card
  const fpPanel = document.getElementById('fireProtectionPanel');
  const fpRightCard = document.getElementById('fireDesignPointCard');
  const fireNotice = document.getElementById('quickPtFireNotice');
  const ptLabel = document.getElementById('quickPtLabel');

  const isFire = (normVal === 'fire' || normVal === 'fire pump' || normVal === 'fire_pump');
  if (fpPanel) {
    fpPanel.style.display = isFire ? '' : 'none';
  }
  if (fpRightCard) {
    fpRightCard.style.display = isFire ? '' : 'none';
  }
  if (fireNotice) {
    fireNotice.classList.toggle('hidden', !isFire);
  }
  if (ptLabel) {
    ptLabel.textContent = isFire ? 'Fire Pump' : (normVal === 'slurry' ? 'Slurry' : (normVal === 'centrifugal' ? 'Centrifugal' : 'All Types'));
  }

  const firePrompt = document.getElementById('fireInitialPrompt');
  const selPrompt = document.getElementById('selectionInitialPrompt');
  if (firePrompt && selPrompt) {
    firePrompt.style.display = isFire ? '' : 'none';
    selPrompt.style.display = isFire ? 'none' : '';
  }

  // Synchronize placement of duty inputs and Fire Mode UI (header banner & liquid type)
  syncDutyInputsLocation(isFire);
  syncFireModeUI(isFire);

  if (isFire) {
    calculateFireDemand();
  }
}

/**
 * syncFireModeUI(isFire)
 * Synchronizes header banner and liquid selector restrictions for Fire Mode.
 * - In Fire Mode: displays fire header, shows Dedicated View link, disables slurry option and defaults liquid to clean water (NFPA 20).
 * - In Standard Mode: displays standard header, hides Dedicated View link, re-enables slurry option.
 */
function syncFireModeUI(isFire) {
  // Page Header toggle
  const defaultHdr = document.getElementById('defaultPageHeader');
  const fireHdr = document.getElementById('firePageHeader');
  const fireDedBtn = document.getElementById('fireDedicatedViewBtn');
  if (defaultHdr) defaultHdr.classList.toggle('hidden', isFire);
  if (fireHdr) fireHdr.classList.toggle('hidden', !isFire);
  if (fireDedBtn) fireDedBtn.classList.toggle('hidden', !isFire);

  // Liquid Selection: In fire mode disable slurry and default to clean water
  const liquidSel = document.getElementById('liquidSel');
  const fireNotice = document.getElementById('fireLiquidNotice');
  if (liquidSel) {
    const slurryOpt = liquidSel.querySelector('option[value="slurry"]');
    if (isFire) {
      if (slurryOpt) slurryOpt.disabled = true;
      if (liquidSel.value === 'slurry') {
        liquidSel.value = 'water';
        liquidSel.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (fireNotice) fireNotice.classList.remove('hidden');
    } else {
      if (slurryOpt) slurryOpt.disabled = false;
      if (fireNotice) fireNotice.classList.add('hidden');
    }
  }
}

/**
 * onPumpTypeFilterChange(typeVal)
 * Invoked when user changes the Pump Type dropdown inside the Filter Panel.
 */
function onPumpTypeFilterChange(typeVal) {
  const normVal = (typeVal || '').trim().toLowerCase();
  updateQuickPumpTypeUI(normVal);

  const fpPanel = document.getElementById('fireProtectionPanel');
  const fpRightCard = document.getElementById('fireDesignPointCard');
  const fireNotice = document.getElementById('quickPtFireNotice');
  const ptLabel = document.getElementById('quickPtLabel');

  const isFire = (normVal === 'fire' || normVal === 'fire pump' || normVal === 'fire_pump');
  if (fpPanel) {
    fpPanel.style.display = isFire ? '' : 'none';
  }
  if (fpRightCard) {
    fpRightCard.style.display = isFire ? '' : 'none';
  }
  if (fireNotice) {
    fireNotice.classList.toggle('hidden', !isFire);
  }
  if (ptLabel) {
    ptLabel.textContent = isFire ? 'Fire Pump' : (normVal === 'slurry' ? 'Slurry' : (normVal === 'centrifugal' ? 'Centrifugal' : 'All Types'));
  }

  const firePrompt = document.getElementById('fireInitialPrompt');
  const selPrompt = document.getElementById('selectionInitialPrompt');
  if (firePrompt && selPrompt) {
    firePrompt.style.display = isFire ? '' : 'none';
    selPrompt.style.display = isFire ? 'none' : '';
  }

  // Synchronize placement of duty inputs and Fire Mode UI
  syncDutyInputsLocation(isFire);
  syncFireModeUI(isFire);

  if (isFire) {
    calculateFireDemand();
  }
}

function updateQuickPumpTypeUI(normVal) {
  const btnAll = document.getElementById('qpt-all');
  const btnCentrif = document.getElementById('qpt-centrifugal');
  const btnSlurry = document.getElementById('qpt-slurry');
  const btnFire = document.getElementById('qpt-fire');

  const activeDefaultClass = 'px-1.5 py-1 text-[11px] font-medium rounded text-center transition-all bg-[#21262d] text-white shadow-sm font-semibold border border-[#30363d]';
  const inactiveDefaultClass = 'px-1.5 py-1 text-[11px] font-medium rounded text-center transition-all text-[#8b949e] hover:text-white';
  const activeBlueClass = 'px-1.5 py-1 text-[11px] font-medium rounded text-center transition-all bg-[#21262d] text-[#58a6ff] shadow-sm font-semibold border border-[#30363d]';
  const activeYellowClass = 'px-1.5 py-1 text-[11px] font-medium rounded text-center transition-all bg-[#21262d] text-[#e3b341] shadow-sm font-semibold border border-[#30363d]';
  const activeFireClass = 'px-1.5 py-1 text-[11px] font-medium rounded text-center transition-all flex items-center justify-center gap-1 bg-[#f85149]/20 text-[#ff7b72] border border-[#f85149]/40 shadow-sm font-bold';
  const inactiveFireClass = 'px-1.5 py-1 text-[11px] font-medium rounded text-center transition-all flex items-center justify-center gap-1 text-[#8b949e] hover:text-[#ff7b72]';

  if (btnAll) btnAll.className = (!normVal || normVal === '') ? activeDefaultClass : inactiveDefaultClass;
  if (btnCentrif) btnCentrif.className = (normVal === 'centrifugal') ? activeBlueClass : inactiveDefaultClass;
  if (btnSlurry) btnSlurry.className = (normVal === 'slurry') ? activeYellowClass : inactiveDefaultClass;
  if (btnFire) btnFire.className = (normVal === 'fire' || normVal === 'fire pump' || normVal === 'fire_pump') ? activeFireClass : inactiveFireClass;
}

/**
 * ── Fire Protection Hydraulic Sizing & NFPA 20 Evaluation Engine ─────────
 * Standards: NFPA 20, NFPA 13, NFPA 14, EN 12845, AS 2941
 */
let currentFireStandard = 'nfpa13';
let currentFireUnitSystem = (window.__PMP_UNIT_SYSTEM === 'imperial' ? 'imperial' : 'metric');
let fireCalcDebounceTimer = null;

/**
 * selectFireStandardTab(stdKey)
 * Switches active fire standard tab and displays relevant parameters.
 */
function selectFireStandardTab(stdKey) {
  currentFireStandard = stdKey;
  const stdInput = document.getElementById('fire_standard');
  if (stdInput) stdInput.value = stdKey;
  try {
    localStorage.setItem('pmpro_fire_standard', stdKey);
  } catch (e) {}

  // Toggle Radio buttons and Radio card styles
  const allTabs = ['nfpa13', 'nfpa14', 'en12845', 'as2941', 'custom'];
  const activeClass = 'fp-std-radio-card flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-all border border-[#f85149]/40 bg-[#f85149]/15 text-[#ff7b72]';
  const activeCustomClass = 'fp-std-radio-card col-span-2 flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-all border border-[#f85149]/40 bg-[#f85149]/15 text-[#ff7b72]';
  const inactiveClass = 'fp-std-radio-card flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-all border border-[#30363d] bg-[#161b22] text-[#8b949e] hover:text-white hover:border-[#30363d]';
  const inactiveCustomClass = 'fp-std-radio-card col-span-2 flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-all border border-[#30363d] bg-[#161b22] text-[#8b949e] hover:text-white hover:border-[#30363d]';

  allTabs.forEach(t => {
    const radio = document.getElementById(`fp_radio_${t}`);
    const card = document.getElementById(`fp_opt_${t}`);
    const isCustom = (t === 'custom');
    if (radio) {
      radio.checked = (t === stdKey);
    }
    if (card) {
      if (t === stdKey) {
        card.className = isCustom ? activeCustomClass : activeClass;
      } else {
        card.className = isCustom ? inactiveCustomClass : inactiveClass;
      }
    }
  });

  // Update Standard Badge
  const badgeEl = document.getElementById('fp_badge_flow_standard');
  if (badgeEl) {
    badgeEl.textContent = (stdKey === 'as2941' ? 'AS 2941' : (stdKey === 'en12845' ? 'EN 12845' : (stdKey === 'custom' ? 'CUSTOM' : stdKey.toUpperCase())));
  }

  // Toggle visible sections based on standard
  const hazardSec = document.getElementById('fp_section_hazard');
  const codeParamsSec = document.getElementById('fp_section_code_params');
  const hydraulicsSec = document.getElementById('fp_section_hydraulics');
  const customDutySec = document.getElementById('fp_section_custom_duty');
  const densityAreaRow = document.getElementById('fp_row_density_area');
  const standpipeRow = document.getElementById('fp_row_standpipe_risers');
  const hoseStreamRow = document.getElementById('fp_row_hose_stream');
  const lblTitle = document.getElementById('fp_lbl_params_title');

  if (stdKey === 'custom') {
    if (hazardSec) hazardSec.classList.add('hidden');
    if (codeParamsSec) codeParamsSec.classList.add('hidden');
    if (hydraulicsSec) hydraulicsSec.classList.add('hidden');
    if (customDutySec) customDutySec.classList.remove('hidden');
  } else {
    if (customDutySec) customDutySec.classList.add('hidden');
    if (hazardSec) hazardSec.classList.remove('hidden');
    if (codeParamsSec) codeParamsSec.classList.remove('hidden');
    if (hydraulicsSec) hydraulicsSec.classList.remove('hidden');

    if (stdKey === 'nfpa14') {
      if (densityAreaRow) densityAreaRow.classList.add('hidden');
      if (standpipeRow) standpipeRow.classList.remove('hidden');
      if (hoseStreamRow) hoseStreamRow.classList.add('hidden');
      if (lblTitle) lblTitle.textContent = 'Standpipe Riser Demands (NFPA 14)';
    } else if (stdKey === 'as2941') {
      if (densityAreaRow) densityAreaRow.classList.add('hidden');
      if (standpipeRow) standpipeRow.classList.add('hidden');
      if (hoseStreamRow) hoseStreamRow.classList.add('hidden');
      if (lblTitle) lblTitle.textContent = 'Installation Sizing Criteria (AS 2941)';
    } else if (stdKey === 'en12845') {
      if (densityAreaRow) densityAreaRow.classList.remove('hidden');
      if (standpipeRow) standpipeRow.classList.add('hidden');
      if (hoseStreamRow) hoseStreamRow.classList.add('hidden');
      if (lblTitle) lblTitle.textContent = 'EN 12845 Hydraulic Sprinkler Demand';
    } else {
      // NFPA 13
      if (densityAreaRow) densityAreaRow.classList.remove('hidden');
      if (standpipeRow) standpipeRow.classList.add('hidden');
      if (hoseStreamRow) hoseStreamRow.classList.remove('hidden');
      if (lblTitle) lblTitle.textContent = 'Hydraulic Demand Parameters (NFPA 13)';
    }
    populateFireHazardDropdown(stdKey);
  }

  calculateFireDemand();
}

/**
 * populateFireHazardDropdown(stdKey)
 * Fills the hazard classification select based on selected standard.
 */
function populateFireHazardDropdown(stdKey) {
  const sel = document.getElementById('fp_select_hazard');
  const standardsData = window.__PMP_FIRE_STANDARDS || {};
  if (!sel || !standardsData) return;

  sel.innerHTML = '';
  let profiles = {};
  if (stdKey === 'nfpa13') profiles = standardsData.nfpa13 || {};
  else if (stdKey === 'nfpa14') profiles = standardsData.nfpa14 || {};
  else if (stdKey === 'en12845') profiles = standardsData.en12845 || {};
  else if (stdKey === 'as2941') profiles = standardsData.as2941 || {};

  Object.entries(profiles).forEach(([k, v]) => {
    const opt = document.createElement('option');
    opt.value = k;
    opt.textContent = v.name || k;
    sel.appendChild(opt);
  });

  if (sel.options.length > 0) {
    sel.selectedIndex = 0;
  }
  onFireHazardChange();
}

/**
 * onFireHazardChange()
 * Updates defaults when user changes hazard class within the active standard.
 */
function onFireHazardChange() {
  const std = currentFireStandard || 'nfpa13';
  const sel = document.getElementById('fp_select_hazard');
  const descEl = document.getElementById('fp_hazard_description');
  const standardsData = window.__PMP_FIRE_STANDARDS || {};
  if (!sel || !standardsData) return;

  const key = sel.value;
  let profile = null;
  if (std === 'nfpa13') profile = (standardsData.nfpa13 || {})[key];
  else if (std === 'nfpa14') profile = (standardsData.nfpa14 || {})[key];
  else if (std === 'en12845') profile = (standardsData.en12845 || {})[key];
  else if (std === 'as2941') profile = (standardsData.as2941 || {})[key];

  if (!profile) return;

  if (descEl) descEl.textContent = profile.description || '';

  // Get current unit selections for inputs
  const unitDens = document.getElementById('fp_unit_density')?.value || 'gpm_ft2';
  const unitArea = document.getElementById('fp_unit_area')?.value || 'ft2';
  const unitHose = document.getElementById('fp_unit_hose')?.value || 'gpm';
  const unitResidual = document.getElementById('fp_unit_residual')?.value || 'psi';

  const densityInput = document.getElementById('fp_density');
  const areaInput = document.getElementById('fp_area');
  const hoseInput = document.getElementById('fp_hose_stream');
  const durInput = document.getElementById('fp_duration');
  const resInput = document.getElementById('fp_residual');

  if (std === 'nfpa13') {
    if (densityInput) {
      densityInput.value = (unitDens === 'mm_min' ? (profile.density_mm_min || 6.1) : (profile.density_gpm_ft2 || 0.15));
    }
    if (areaInput) {
      areaInput.value = (unitArea === 'm2' ? (profile.area_m2 || 139.35) : (profile.area_ft2 || 1500));
    }
    if (hoseInput) {
      hoseInput.value = convertValue(profile.hose_stream_gpm || 250, 'gpm', unitHose, 'flow');
    }
    if (durInput) durInput.value = profile.duration_min || 60;
    if (resInput) {
      resInput.value = convertValue(profile.min_residual_psi || 10.0, 'psi', unitResidual, 'head');
    }
  } else if (std === 'en12845') {
    if (densityInput) {
      densityInput.value = (unitDens === 'gpm_ft2' ? ((profile.design_density_mm_min || 5.0) / 40.7458).toFixed(3) : (profile.design_density_mm_min || 5.0));
    }
    if (areaInput) {
      areaInput.value = (unitArea === 'ft2' ? Math.round((profile.design_area_m2 || 144) * 10.7639) : (profile.design_area_m2 || 144));
    }
    if (hoseInput) hoseInput.value = 0;
    if (durInput) durInput.value = profile.duration_min || 60;
    if (resInput) {
      resInput.value = convertValue(profile.nominal_head_bar || 1.5, 'bar', unitResidual, 'head');
    }
  } else if (std === 'nfpa14') {
    if (durInput) durInput.value = 30;
    if (resInput) {
      resInput.value = convertValue(profile.min_residual_psi || 100.0, 'psi', unitResidual, 'head');
    }
  } else if (std === 'as2941') {
    if (durInput) durInput.value = profile.duration_min || 60;
    if (resInput) {
      const barVal = (profile.head_kpa ? profile.head_kpa / 100.0 : 6.0);
      resInput.value = convertValue(barVal, 'bar', unitResidual, 'head');
    }
  }

  calculateFireDemand();
}

/**
 * setFireUnitSystem(u, triggerCalc = true)
 * Toggles fire panel between metric and imperial unit presets.
 */
function setFireUnitSystem(u, triggerCalc = true) {
  currentFireUnitSystem = u;
  const isImp = (u === 'imperial');

  // Update Fire Unit Button Styles
  const btnMetric = document.getElementById('btnFireUnitMetric');
  const btnImp = document.getElementById('btnFireUnitImperial');
  if (btnMetric && btnImp) {
    if (isImp) {
      btnImp.className = 'px-2 py-0.5 rounded transition-all bg-[#21262d] text-[#58a6ff] shadow-sm';
      btnMetric.className = 'px-2 py-0.5 rounded transition-all text-[#8b949e] hover:text-white';
    } else {
      btnMetric.className = 'px-2 py-0.5 rounded transition-all bg-[#21262d] text-[#58a6ff] shadow-sm';
      btnImp.className = 'px-2 py-0.5 rounded transition-all text-[#8b949e] hover:text-white';
    }
  }

  // Target units for all fire parameters
  const targets = {
    fp_unit_density: isImp ? 'gpm_ft2' : 'mm_min',
    fp_unit_area: isImp ? 'ft2' : 'm2',
    fp_unit_hose: isImp ? 'gpm' : 'm3h',
    fp_custom_unit_residual: isImp ? 'psi' : 'bar',
    fp_unit_static_z: isImp ? 'ft' : 'm',
    fp_unit_friction: isImp ? 'psi' : 'm',
    fp_unit_residual: isImp ? 'psi' : 'bar'
  };

  Object.entries(targets).forEach(([selectId, targetUnit]) => {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const prevUnit = sel.dataset.prev || sel.value;
    const cat = sel.dataset.unitCat || 'flow';
    const targetInputId = sel.dataset.target;
    const inputEl = document.getElementById(targetInputId);

    if (inputEl && inputEl.value !== '' && prevUnit !== targetUnit) {
      inputEl.value = convertValue(inputEl.value, prevUnit, targetUnit, cat);
    }
    sel.value = targetUnit;
    sel.dataset.prev = targetUnit;
  });

  if (triggerCalc) {
    calculateFireDemand();
  }
}

/**
 * onFireParamUnitChange(sel)
 * Converts input value when user changes any individual unit selector.
 */
function onFireParamUnitChange(sel) {
  if (!sel) return;
  const targetId = sel.dataset.target;
  const prevUnit = sel.dataset.prev || sel.value;
  const targetUnit = sel.value;
  const cat = sel.dataset.unitCat || 'flow';
  const inputEl = document.getElementById(targetId);

  if (inputEl && inputEl.value !== '' && prevUnit !== targetUnit) {
    inputEl.value = convertValue(inputEl.value, prevUnit, targetUnit, cat);
  }
  sel.dataset.prev = targetUnit;
  calculateFireDemand();
}

/**
 * triggerFireRecalculate()
 * Debounced recalculation of fire hydraulic demand.
 */
function triggerFireRecalculate() {
  clearTimeout(fireCalcDebounceTimer);
  fireCalcDebounceTimer = setTimeout(calculateFireDemand, 120);
}

/**
 * calculateFireDemand()
 * Performs complete code-compliant NFPA 20 / NFPA 13 / NFPA 14 / EN 12845 / AS 2941 calculations.
 */
function calculateFireDemand() {
  const std = currentFireStandard || 'nfpa13';
  const standardsData = window.__PMP_FIRE_STANDARDS || {};

  let flowGpm = 500.0;
  let durationMin = 60;
  let residualPsi = 65.0;

  // 1. Flow Calculations
  if (std === 'nfpa13') {
    const rawDens = parseFloat(document.getElementById('fp_density')?.value) || 0.15;
    const unitDens = document.getElementById('fp_unit_density')?.value || 'gpm_ft2';
    const densGpmFt2 = (unitDens === 'mm_min' ? (rawDens / 40.7458) : rawDens);

    const rawArea = parseFloat(document.getElementById('fp_area')?.value) || 1500.0;
    const unitArea = document.getElementById('fp_unit_area')?.value || 'ft2';
    const areaFt2 = (unitArea === 'm2' ? (rawArea * 10.7639) : rawArea);

    const rawHose = parseFloat(document.getElementById('fp_hose_stream')?.value) || 250.0;
    const unitHose = document.getElementById('fp_unit_hose')?.value || 'gpm';
    const hoseGpm = Number(convertValue(rawHose, unitHose, 'gpm', 'flow')) || 250.0;

    durationMin = parseFloat(document.getElementById('fp_duration')?.value) || 60;
    flowGpm = (densGpmFt2 * areaFt2) + hoseGpm;

    const rawRes = parseFloat(document.getElementById('fp_residual')?.value) || 10.0;
    const unitRes = document.getElementById('fp_unit_residual')?.value || 'psi';
    residualPsi = Number(convertValue(rawRes, unitRes, 'psi', 'head')) || 10.0;

  } else if (std === 'nfpa14') {
    const sel = document.getElementById('fp_select_hazard');
    const stKey = sel ? sel.value : 'class_1';
    const risers = parseInt(document.getElementById('fp_risers_count')?.value) || 1;
    const sprinklered = document.getElementById('fp_sprinklered')?.checked ?? true;

    if (stKey === 'class_2') {
      flowGpm = 100.0;
      residualPsi = 65.0;
    } else {
      const calcGpm = 500.0 + Math.max(0, risers - 1) * 250.0;
      const maxGpm = sprinklered ? 1250.0 : 1000.0;
      flowGpm = Math.min(calcGpm, maxGpm);
      residualPsi = 100.0;
    }
    durationMin = 30;

    const rawRes = parseFloat(document.getElementById('fp_residual')?.value);
    if (!isNaN(rawRes) && rawRes > 0) {
      const unitRes = document.getElementById('fp_unit_residual')?.value || 'psi';
      residualPsi = Number(convertValue(rawRes, unitRes, 'psi', 'head')) || residualPsi;
    }

  } else if (std === 'en12845') {
    const sel = document.getElementById('fp_select_hazard');
    const enKey = sel ? sel.value : 'en_oh1';
    const en = standardsData.en12845 ? standardsData.en12845[enKey] : null;

    if (en) {
      const nomM3h = en.nominal_flow_m3h || 60.0;
      flowGpm = nomM3h * 4.402867;
      durationMin = en.duration_min || 60;
      residualPsi = (en.nominal_head_bar || 1.5) * 14.5038;
    }

    const rawRes = parseFloat(document.getElementById('fp_residual')?.value);
    if (!isNaN(rawRes) && rawRes > 0) {
      const unitRes = document.getElementById('fp_unit_residual')?.value || 'bar';
      residualPsi = Number(convertValue(rawRes, unitRes, 'psi', 'head')) || residualPsi;
    }

  } else if (std === 'as2941') {
    const sel = document.getElementById('fp_select_hazard');
    const asKey = sel ? sel.value : 'as_sprinkler_ordinary';
    const asCrit = standardsData.as2941 ? standardsData.as2941[asKey] : null;

    if (asCrit) {
      const flowM3h = asCrit.flow_m3h || 90.0;
      flowGpm = flowM3h * 4.402867;
      durationMin = asCrit.duration_min || 60;
      residualPsi = ((asCrit.head_kpa || 600.0) / 100.0) * 14.5038;
    }

    const rawRes = parseFloat(document.getElementById('fp_residual')?.value);
    if (!isNaN(rawRes) && rawRes > 0) {
      const unitRes = document.getElementById('fp_unit_residual')?.value || 'psi';
      residualPsi = Number(convertValue(rawRes, unitRes, 'psi', 'head')) || residualPsi;
    }

  } else if (std === 'custom') {
    // Read directly from usual input: Flow Q
    const rawQ = parseFloat(document.getElementById('input_q_duty')?.value);
    const unitQ = document.getElementById('select_unit_q')?.value || 'm3h';
    if (!isNaN(rawQ) && rawQ > 0) {
      flowGpm = Number(convertValue(rawQ, unitQ, 'gpm', 'flow')) || 500.0;
    } else {
      flowGpm = 500.0;
    }

    // Residual nozzle operation pressure
    const rawRes = parseFloat(document.getElementById('fp_custom_residual')?.value);
    if (!isNaN(rawRes) && rawRes > 0) {
      const unitRes = document.getElementById('fp_custom_unit_residual')?.value || 'psi';
      residualPsi = Number(convertValue(rawRes, unitRes, 'psi', 'head')) || 65.0;
    } else {
      residualPsi = 65.0;
    }

    // Required fire protection supply duration
    durationMin = parseFloat(document.getElementById('fp_custom_duration')?.value) || 60;
  }

  // 2. Elevation, Piping Friction & Total Head Calculations
  const rawZ = parseFloat(document.getElementById('fp_static_z')?.value) || 0.0;
  const unitZ = document.getElementById('fp_unit_static_z')?.value || 'ft';
  const zFeet = Number(convertValue(rawZ, unitZ, 'ft', 'head')) || 0.0;
  const zPsi = zFeet * 0.4335;

  const rawFric = parseFloat(document.getElementById('fp_friction')?.value) || 0.0;
  const unitFric = document.getElementById('fp_unit_friction')?.value || 'psi';
  const frictionPsi = Number(convertValue(rawFric, unitFric, 'psi', 'head')) || 0.0;

  let totalHeadPsi = zPsi + frictionPsi + residualPsi;
  if (std === 'custom') {
    const rawH = parseFloat(document.getElementById('input_h_duty')?.value);
    const unitH = document.getElementById('select_unit_h')?.value || 'm';
    if (!isNaN(rawH) && rawH > 0) {
      totalHeadPsi = Number(convertValue(rawH, unitH, 'psi', 'head')) || 100.0;
    } else {
      totalHeadPsi = (zPsi + frictionPsi > 0) ? (zPsi + frictionPsi + residualPsi) : 100.0;
    }
  }

  const flowM3h = flowGpm * 0.227124707;
  const totalHeadM = totalHeadPsi * 0.703069578;
  const totalHeadFt = totalHeadM * 3.28084;
  const totalHeadBar = totalHeadM * 0.0980665;

  // Sync calculated fire demand into usual duty inputs when on a code-calculated standard
  if (std !== 'custom') {
    const curUnitQ = document.getElementById('select_unit_q')?.value || 'm3h';
    const curUnitH = document.getElementById('select_unit_h')?.value || 'm';
    const qInput = document.getElementById('input_q_duty');
    const hInput = document.getElementById('input_h_duty');
    if (qInput && document.activeElement !== qInput) {
      qInput.value = parseFloat(Number(convertValue(flowGpm, 'gpm', curUnitQ, 'flow')).toFixed(2));
    }
    if (hInput && document.activeElement !== hInput) {
      hInput.value = parseFloat(Number(convertValue(totalHeadM, 'm', curUnitH, 'head')).toFixed(2));
    }
  }

  // 3. NFPA 20 Characteristic Limits Breakdown
  const maxChurnHeadPsi = totalHeadPsi * 1.40;
  const maxChurnHeadM = totalHeadM * 1.40;
  const overloadFlowGpm = flowGpm * 1.50;
  const overloadFlowM3h = flowM3h * 1.50;
  const minOverloadHeadPsi = totalHeadPsi * 0.65;
  const minOverloadHeadM = totalHeadM * 0.65;

  // Driver Power Sizing (Hydraulic + 15% non-overload margin, assuming typical 70% efficiency)
  const hydPowerKw = (1000.0 * 9.80665 * (flowM3h / 3600.0) * totalHeadM) / 1000.0;
  const shaftPowerKw = hydPowerKw / 0.70;
  const driverPowerKw = Math.ceil(shaftPowerKw * 1.15);
  const driverPowerHp = Math.ceil(driverPowerKw * 1.34102);

  // 4. Auxiliaries: Jockey Pump & Water Storage Tank
  const jockeyGpm = Math.max(5, Math.round(flowGpm * 0.01 * 10) / 10);
  const jockeyHeadPsi = Math.round(totalHeadPsi * 1.10);
  const jockeyStartPsi = Math.round(totalHeadPsi - 5);
  const jockeyStopPsi = Math.round(totalHeadPsi + 5);

  const tankGallons = Math.round(flowGpm * durationMin);
  const tankM3 = Math.round((flowM3h * (durationMin / 60.0)) * 10) / 10;

  // 5. NFPA 20 Table 4.27 Pipe Sizing Schedule
  let suctionIn = 5, suctionMm = 125;
  let dischargeIn = 5, dischargeMm = 125;
  let meterIn = 5, reliefIn = 3;

  if (flowGpm <= 250) {
    suctionIn = 3.5; suctionMm = 90; dischargeIn = 3; dischargeMm = 80; meterIn = 3.5; reliefIn = 2;
  } else if (flowGpm <= 500) {
    suctionIn = 5; suctionMm = 125; dischargeIn = 5; dischargeMm = 125; meterIn = 5; reliefIn = 3;
  } else if (flowGpm <= 750) {
    suctionIn = 6; suctionMm = 150; dischargeIn = 6; dischargeMm = 150; meterIn = 6; reliefIn = 4;
  } else if (flowGpm <= 1000) {
    suctionIn = 8; suctionMm = 200; dischargeIn = 6; dischargeMm = 150; meterIn = 6; reliefIn = 4;
  } else if (flowGpm <= 1500) {
    suctionIn = 8; suctionMm = 200; dischargeIn = 8; dischargeMm = 200; meterIn = 8; reliefIn = 6;
  } else if (flowGpm <= 2000) {
    suctionIn = 10; suctionMm = 250; dischargeIn = 10; dischargeMm = 250; meterIn = 8; reliefIn = 6;
  } else {
    suctionIn = 10; suctionMm = 250; dischargeIn = 10; dischargeMm = 250; meterIn = 8; reliefIn = 8;
  }

  // 6. Update UI Metrics
  const isImp = (currentFireUnitSystem === 'imperial');

  const elFlowPrim = document.getElementById('fp_res_flow_primary');
  const elFlowSec = document.getElementById('fp_res_flow_secondary');
  const elHeadPrim = document.getElementById('fp_res_head_primary');
  const elHeadSec = document.getElementById('fp_res_head_secondary');

  if (isImp) {
    if (elFlowPrim) elFlowPrim.textContent = `${Math.round(flowGpm)} GPM`;
    if (elFlowSec) elFlowSec.textContent = `${flowM3h.toFixed(1)} m³/h`;
    if (elHeadPrim) elHeadPrim.textContent = `${Math.round(totalHeadPsi)} PSI (${Math.round(totalHeadFt)} ft)`;
    if (elHeadSec) elHeadSec.textContent = `${totalHeadM.toFixed(1)} m (${totalHeadBar.toFixed(1)} bar)`;
  } else {
    if (elFlowPrim) elFlowPrim.textContent = `${flowM3h.toFixed(1)} m³/h`;
    if (elFlowSec) elFlowSec.textContent = `${Math.round(flowGpm)} GPM`;
    if (elHeadPrim) elHeadPrim.textContent = `${totalHeadM.toFixed(1)} m (${totalHeadBar.toFixed(1)} bar)`;
    if (elHeadSec) elHeadSec.textContent = `${Math.round(totalHeadPsi)} PSI (${Math.round(totalHeadFt)} ft)`;
  }

  // Limits
  const elChurn = document.getElementById('fp_res_max_churn');
  const elOverFlow = document.getElementById('fp_res_overload_flow');
  const elOverHead = document.getElementById('fp_res_min_overload_head');
  const elDriver = document.getElementById('fp_res_driver_power');

  if (elChurn) elChurn.textContent = `≤ ${Math.round(maxChurnHeadPsi)} PSI (${maxChurnHeadM.toFixed(1)} m)`;
  if (elOverFlow) elOverFlow.textContent = `${Math.round(overloadFlowGpm)} GPM (${overloadFlowM3h.toFixed(1)} m³/h)`;
  if (elOverHead) elOverHead.textContent = `≥ ${Math.round(minOverloadHeadPsi)} PSI (${minOverloadHeadM.toFixed(1)} m)`;
  if (elDriver) elDriver.textContent = `${driverPowerKw} kW (${driverPowerHp} HP)`;

  // Jockey
  const elJockDuty = document.getElementById('fp_res_jockey_duty');
  const elJockStart = document.getElementById('fp_res_jockey_start');
  const elJockStop = document.getElementById('fp_res_jockey_stop');

  if (elJockDuty) elJockDuty.textContent = `${jockeyGpm} GPM @ ${jockeyHeadPsi} PSI`;
  if (elJockStart) elJockStart.textContent = `${jockeyStartPsi} PSI`;
  if (elJockStop) elJockStop.textContent = `${jockeyStopPsi} PSI`;

  // Tank
  const elTankM3 = document.getElementById('fp_res_tank_vol_m3');
  const elTankGal = document.getElementById('fp_res_tank_vol_gal');
  const elTankDur = document.getElementById('fp_res_tank_duration');

  if (elTankM3) elTankM3.textContent = `${tankM3} m³`;
  if (elTankGal) elTankGal.textContent = `${tankGallons.toLocaleString()} US Gal`;
  if (elTankDur) elTankDur.textContent = `${durationMin} min`;

  // Pipes
  const elPipes = document.getElementById('fp_res_pipe_sizes');
  if (elPipes) {
    elPipes.textContent = `Suction: ${suctionIn}" (${suctionMm}mm) | Discharge: ${dischargeIn}" (${dischargeMm}mm)`;
  }

  // Store in panel dataset for retrieval
  const panel = document.getElementById('fireProtectionPanel');
  if (panel) {
    panel.dataset.flowGpm = flowGpm.toFixed(1);
    panel.dataset.flowM3h = flowM3h.toFixed(2);
    panel.dataset.headPsi = totalHeadPsi.toFixed(1);
    panel.dataset.headM = totalHeadM.toFixed(2);
    panel.dataset.headFt = totalHeadFt.toFixed(1);
    panel.dataset.headBar = totalHeadBar.toFixed(2);
  }
}

/**
 * applyFireDutyToSelection()
 * Copies sized fire flow and head directly into the main duty inputs and submits the form.
 */
function applyFireDutyToSelection() {
  const panel = document.getElementById('fireProtectionPanel');
  if (!panel) return;

  calculateFireDemand();

  const curUnitQ = document.getElementById('select_unit_q')?.value || 'm3h';
  const curUnitH = document.getElementById('select_unit_h')?.value || 'm';

  const qInput = document.getElementById('input_q_duty');
  const hInput = document.getElementById('input_h_duty');

  const flowGpm = parseFloat(panel.dataset.flowGpm) || 500.0;
  const headM = parseFloat(panel.dataset.headM) || 70.0;

  if (qInput) {
    qInput.value = convertValue(flowGpm, 'gpm', curUnitQ, 'flow');
  }

  if (hInput) {
    hInput.value = convertValue(headM, 'm', curUnitH, 'head');
  }

  const filterSelect = document.getElementById('filter_pump_type');
  if (filterSelect) {
    filterSelect.value = 'fire pump';
  }

  const form = document.getElementById('selectionForm');
  if (form) {
    form.submit();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const freqRadio = document.querySelector('input[name="motor_freq_hz"]:checked');
  const freq = freqRadio ? parseInt(freqRadio.value, 10) : 50;
  updatePolesLabels(freq);
  onMotorSelectionModeChange();
  onOperationModeChange();
  onFixedSpeedModeChange();
  onVsdTrimModeChange();

  // Synchronize initial fire unit system with current application preset
  if (typeof setFireUnitSystem === 'function') {
    setFireUnitSystem(currentFireUnitSystem, false);
  }

  // Initialize Quick Pump Type and Fire Protection UI if active
  const curPt = (document.getElementById('filter_pump_type')?.value || '').trim().toLowerCase();
  const isFire = (curPt === 'fire' || curPt === 'fire pump' || curPt === 'fire_pump');
  syncDutyInputsLocation(isFire);
  syncFireModeUI(isFire);

  if (isFire) {
    setQuickPumpType('fire pump');
  } else if (curPt) {
    updateQuickPumpTypeUI(curPt);
  }

  // Restore Fire Protection Standard selection (stored in form_data or localStorage)
  let savedFireStd = 'nfpa13';
  const formFireStd = document.getElementById('fire_standard')?.value;
  if (formFireStd && ['nfpa13', 'nfpa14', 'en12845', 'as2941', 'custom'].includes(formFireStd)) {
    savedFireStd = formFireStd;
  } else {
    try {
      const lsStd = localStorage.getItem('pmpro_fire_standard');
      if (lsStd && ['nfpa13', 'nfpa14', 'en12845', 'as2941', 'custom'].includes(lsStd)) {
        savedFireStd = lsStd;
      }
    } catch (e) {}
  }
  selectFireStandardTab(savedFireStd);

  // Sanitize initial water density input against unit mismatch (e.g. 998 loaded into SG unit)
  const rInp = document.getElementById('input_rho_water');
  const uRhoSel = document.getElementById('select_unit_rho');
  if (rInp && uRhoSel) {
    const u = uRhoSel.value;
    const v = parseFloat(rInp.value);
    if (!isNaN(v) && v > 0) {
      if (u === 'sg' && v > 50) {
        rInp.value = Number(convertValue(v, 'kgm3', 'sg', 'density'));
      } else if (u === 'kgm3' && v < 50) {
        rInp.value = Number(convertValue(v, 'sg', 'kgm3', 'density'));
      }
    }
  }

  // Wire input listeners for Fire Mode live calculation
  ['input_q_duty', 'input_h_duty'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', () => {
        const pt = (document.getElementById('filter_pump_type')?.value || '').trim().toLowerCase();
        const fireActive = (pt === 'fire' || pt === 'fire pump' || pt === 'fire_pump');
        if (fireActive) {
          if (currentFireStandard !== 'custom') {
            selectFireStandardTab('custom');
          } else {
            triggerFireRecalculate();
          }
        }
      });
    }
  });

  ['select_unit_q', 'select_unit_h'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => {
        const pt = (document.getElementById('filter_pump_type')?.value || '').trim().toLowerCase();
        const fireActive = (pt === 'fire' || pt === 'fire pump' || pt === 'fire_pump');
        if (fireActive) {
          triggerFireRecalculate();
        }
      });
    }
  });
});


