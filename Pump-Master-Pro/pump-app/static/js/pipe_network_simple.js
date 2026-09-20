/**
 * pipe_network_simple.js — Simple Pipe Network Designer (Dropdown & List Mode)
 *
 * Overview:
 *   This script provides a streamlined, form-driven calculation mode for piping
 *   systems where networks do not need to be graphically drawn. Instead, users
 *   specify pipeline segments directly via dropdowns (standard pipe catalogs,
 *   materials, nominal sizes, schedules, fittings, and elevations).
 *
 * Supported Configurations:
 *   1. Series Network:
 *      - All pipe segments are connected in a continuous end-to-end chain.
 *      - Flow rate Q is identical across all segments (Q_1 = Q_2 = ... = Q_total).
 *      - Total head loss accumulates sequentially:
 *          H_total = Σ(h_major + h_minor + Δz) + Static_Head
 *
 *   2. Parallel Network:
 *      - Flow divides across multiple parallel pipe branches between common manifolds.
 *      - Branch head losses balance equally:
 *          H_branch1 = H_branch2 = ...
 *      - Total flow equals the sum of branch flows:
 *          Q_total = Σ(Q_branch_i)
 *      - Flow distribution is determined either automatically via iterative
 *        hydraulic resistance balancing (Q_i ∝ 1 / √R_i) or via manual % allocation.
 *
 * Integration:
 *   - Supports instant synchronization of calculated Duty Point (Flow Q, Head H)
 *     to the active Pump Selection session or form inputs.
 */

'use strict';

class SimpleNetworkController {
  constructor() {
    // Internal state representing the simple network configuration
    this.state = {
      topology: 'series',               // 'series' or 'parallel'
      parallel_balancing: 'auto',        // 'auto' (hydraulic split) or 'manual' (% allocation)
      flow_rate: 100.0,                  // Operating flow in selected engineering unit
      flow_unit: window.__PMP_UNIT_Q || 'm3h', // e.g. 'm3h', 'ls', 'gpm'
      static_elevation: 10.0,            // Total static lift difference (m)
      solver_method: 'ggm',              // Network solver: 'ggm', 'newton_raphson', 'hardy_cross', or 'linear_theory'
      friction_method: 'darcy_weisbach', // 'darcy_weisbach' or 'hazen_williams'
      fluid: {
        type: 'water',
        temp_c: 20,
        sg: 1.00,
        viscosity_cst: 1.004
      },
      pipes: []                          // Array of pipe segment objects
    };

    // Modal tracking state for valves and fittings editing
    this.modalActivePipeIdx = null;
    this.modalFittingsCopy = {};
    this.modalCustomK = 0.0;

    // Debounce timer for smooth typing without spamming network requests
    this.debounceTimer = null;
    this.isCalculating = false;
    this.isInitialized = false;
  }

  /**
   * Initializes the controller on first load:
   * - Checks for saved pipe network session data
   * - Sets initial form values and populates the table
   * - Executes the initial hydraulic calculation
   */
  init() {
    const sess = window.__PMP_SESSION_PIPE_NETWORK;
    if (sess && sess.mode === 'simple' && Array.isArray(sess.pipes) && sess.pipes.length > 0) {
      this.state.topology = sess.topology || 'series';
      this.state.parallel_balancing = sess.parallel_balancing || 'auto';
      this.state.flow_rate = parseFloat(sess.flow_rate || sess.flow_m3h || 100.0);
      this.state.flow_unit = sess.flow_unit || window.__PMP_UNIT_Q || 'm3h';
      this.state.static_elevation = parseFloat(sess.static_elevation_m || sess.static_head || 10.0);
      this.state.solver_method = sess.solver_method || 'ggm';
      this.state.friction_method = sess.friction_method || 'darcy_weisbach';
      if (sess.fluid) {
        this.state.fluid = Object.assign({}, this.state.fluid, sess.fluid);
      }
      this.state.pipes = sess.pipes.map(p => this.normalizePipeInput(p));
    } else {
      // Load clean default 3-segment Series sample
      this.loadPresetData('series');
    }

    this.syncControlsFromState();
    this.renderTable();
    this.calculate();
    this.isInitialized = true;
  }

  /**
   * Ensures pipe object attributes are normalized and typed correctly.
   */
  normalizePipeInput(p) {
    return {
      id: p.id || 'pipe_' + Math.random().toString(36).substring(2, 9),
      label: p.label || 'Pipe Segment',
      catalog_id: p.catalog_id || '',
      diameter_mm: parseFloat(p.diameter_mm || p.diameter || 102.3),
      material: p.material || 'commercial_steel',
      roughness_mm: parseFloat(p.roughness_mm || p.roughness || 0.046),
      length_m: parseFloat(p.length_m || p.length || 50.0),
      elevation_m: parseFloat(p.elevation_m || p.elevation || 0.0),
      fittings: (typeof p.fittings === 'object' && p.fittings !== null) ? Object.assign({}, p.fittings) : {},
      custom_k: parseFloat(p.custom_k || 0.0),
      flow_pct: parseFloat(p.flow_pct || p.flow_share || 0.0)
    };
  }

  /**
   * Switches topology between 'series' and 'parallel' and refreshes UI.
   */
  setTopology(topo) {
    if (topo !== 'series' && topo !== 'parallel') return;
    this.state.topology = topo;

    // Update active highlight classes on cards
    const cardSeries = document.getElementById('topo-card-series');
    const cardParallel = document.getElementById('topo-card-parallel');
    const radioSeries = document.getElementById('topo-radio-series');
    const radioParallel = document.getElementById('topo-radio-parallel');
    const parallelWrap = document.getElementById('simple-parallel-mode-wrap');
    const thFlowShare = document.getElementById('th-simple-flow-share');

    if (topo === 'series') {
      cardSeries?.classList.add('active');
      cardParallel?.classList.remove('active');
      if (radioSeries) radioSeries.checked = true;
      if (parallelWrap) parallelWrap.style.display = 'none';
      if (thFlowShare) thFlowShare.style.display = 'none';
    } else {
      cardParallel?.classList.add('active');
      cardSeries?.classList.remove('active');
      if (radioParallel) radioParallel.checked = true;
      if (parallelWrap) parallelWrap.style.display = 'block';
      if (thFlowShare) {
        thFlowShare.style.display = (this.state.parallel_balancing === 'manual') ? '' : 'none';
      }
    }

    this.renderTable();
    this.calculate();
  }

  /**
   * Toggles parallel balancing method: 'auto' (hydraulic split) vs 'manual' (% allocation)
   */
  onBalancingChange(method) {
    this.state.parallel_balancing = method;
    const thFlowShare = document.getElementById('th-simple-flow-share');
    if (thFlowShare) {
      thFlowShare.style.display = (method === 'manual' && this.state.topology === 'parallel') ? '' : 'none';
    }
    this.renderTable();
    this.calculate();
  }

  /**
   * Synchronizes HTML form inputs to match internal controller state.
   */
  syncControlsFromState() {
    const flowIn = document.getElementById('simple-flow-rate');
    if (flowIn) flowIn.value = this.state.flow_rate;
    const unitSel = document.getElementById('simple-flow-unit');
    if (unitSel) unitSel.value = this.state.flow_unit;

    const staticIn = document.getElementById('simple-static-head');
    if (staticIn) staticIn.value = this.state.static_elevation;

    const solverSel = document.getElementById('simple-solver-method');
    if (solverSel) solverSel.value = this.state.solver_method || 'ggm';

    const fMethod = document.getElementById('simple-friction-method');
    if (fMethod) fMethod.value = this.state.friction_method;

    const fType = document.getElementById('simple-fluid-type');
    if (fType) fType.value = this.state.fluid.type;
    const fTemp = document.getElementById('simple-fluid-temp');
    if (fTemp) fTemp.value = this.state.fluid.temp_c;
    const fSg = document.getElementById('simple-fluid-sg');
    if (fSg) fSg.value = this.state.fluid.sg;
    const fVisc = document.getElementById('simple-fluid-viscosity');
    if (fVisc) fVisc.value = this.state.fluid.viscosity_cst;

    this.setTopology(this.state.topology);
  }

  /**
   * Reads HTML form inputs into internal controller state.
   */
  readControlsIntoState() {
    const flowIn = document.getElementById('simple-flow-rate');
    if (flowIn) this.state.flow_rate = parseFloat(flowIn.value) || 0.0;
    const unitSel = document.getElementById('simple-flow-unit');
    if (unitSel) this.state.flow_unit = unitSel.value;
    const staticIn = document.getElementById('simple-static-head');
    if (staticIn) this.state.static_elevation = parseFloat(staticIn.value) || 0.0;
    const solverSel = document.getElementById('simple-solver-method');
    if (solverSel) this.state.solver_method = solverSel.value;
    const fMethod = document.getElementById('simple-friction-method');
    if (fMethod) this.state.friction_method = fMethod.value;

    const fType = document.getElementById('simple-fluid-type');
    if (fType) this.state.fluid.type = fType.value;
    const fTemp = document.getElementById('simple-fluid-temp');
    if (fTemp) this.state.fluid.temp_c = parseFloat(fTemp.value) || 20;
    const fSg = document.getElementById('simple-fluid-sg');
    if (fSg) this.state.fluid.sg = parseFloat(fSg.value) || 1.0;
    const fVisc = document.getElementById('simple-fluid-viscosity');
    if (fVisc) this.state.fluid.viscosity_cst = parseFloat(fVisc.value) || 1.004;
  }

  /**
   * Called when user changes the hydraulic network solver method (GGM, NR, Hardy Cross, Linear Theory).
   */
  onSolverChange() {
    this.readControlsIntoState();
    this.calculate();
  }

  /**
   * Handles fluid dropdown preset selection (typical density/viscosity defaults).
   */
  onFluidChange() {
    const fType = document.getElementById('simple-fluid-type')?.value;
    const fSg = document.getElementById('simple-fluid-sg');
    const fVisc = document.getElementById('simple-fluid-viscosity');
    const fTemp = document.getElementById('simple-fluid-temp');

    if (fType === 'water') {
      if (fSg) fSg.value = '1.00';
      if (fVisc) fVisc.value = '1.004';
      if (fTemp) fTemp.value = '20';
    } else if (fType === 'slurry') {
      if (fSg) fSg.value = '1.25';
      if (fVisc) fVisc.value = '2.50';
    } else if (fType === 'oil') {
      if (fSg) fSg.value = '0.88';
      if (fVisc) fVisc.value = '32.0';
    }
    this.readControlsIntoState();
    this.calculate();
  }

  onUnitChange() {
    this.readControlsIntoState();
    this.calculate();
  }

  onInputDebounce() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.readControlsIntoState();
      this.calculate();
    }, 350);
  }

  /**
   * Adds a new pipeline segment.
   */
  addPipe() {
    const idx = this.state.pipes.length + 1;
    const newPipe = {
      id: 'pipe_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      label: `Pipe ${idx} - Segment`,
      catalog_id: '',
      diameter_mm: 102.3,
      material: 'commercial_steel',
      roughness_mm: 0.046,
      length_m: 50.0,
      elevation_m: 0.0,
      fittings: {},
      custom_k: 0.0,
      flow_pct: (this.state.topology === 'parallel' && this.state.pipes.length > 0) ? +(100 / (idx)).toFixed(1) : 0
    };

    this.state.pipes.push(newPipe);
    this.renderTable();
    this.calculate();
  }

  /**
   * Duplicates an existing pipeline segment.
   */
  duplicatePipe(idx) {
    if (idx < 0 || idx >= this.state.pipes.length) return;
    const src = this.state.pipes[idx];
    const copy = Object.assign({}, src, {
      id: 'pipe_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      label: src.label + ' (Copy)',
      fittings: Object.assign({}, src.fittings)
    });
    this.state.pipes.splice(idx + 1, 0, copy);
    this.renderTable();
    this.calculate();
  }

  /**
   * Removes a pipeline segment.
   */
  removePipe(idx) {
    if (this.state.pipes.length <= 1) {
      alert('The network requires at least one pipeline segment.');
      return;
    }
    this.state.pipes.splice(idx, 1);
    this.renderTable();
    this.calculate();
  }

  /**
   * Clears all pipeline segments and adds a clean starter segment.
   */
  clearPipes() {
    if (!confirm('Clear all pipeline segments and start fresh?')) return;
    this.state.pipes = [{
      id: 'pipe_' + Date.now(),
      label: 'Pipeline Main',
      catalog_id: '',
      diameter_mm: 102.3,
      material: 'commercial_steel',
      roughness_mm: 0.046,
      length_m: 50.0,
      elevation_m: 0.0,
      fittings: {},
      custom_k: 0.0,
      flow_pct: 100.0
    }];
    this.renderTable();
    this.calculate();
  }

  /**
   * Loads preset networks (Series or Parallel sample).
   */
  loadPreset(presetName) {
    if (this.state.pipes.length > 0) {
      if (!confirm(`Load ${presetName === 'series' ? 'Series' : 'Parallel'} sample pipeline configuration? Existing segment entries will be replaced.`)) {
        return;
      }
    }
    this.loadPresetData(presetName);
    this.syncControlsFromState();
    this.renderTable();
    this.calculate();
  }

  /**
   * Populates preset data structures.
   */
  loadPresetData(presetName) {
    if (presetName === 'parallel') {
      // Parallel sample: Dual pumping branches splitting flow into Branch 1 (100mm) and Branch 2 (80mm)
      this.state.topology = 'parallel';
      this.state.parallel_balancing = 'auto';
      this.state.flow_rate = 160.0;
      this.state.flow_unit = 'm3h';
      this.state.static_elevation = 8.0;
      this.state.friction_method = 'darcy_weisbach';
      this.state.fluid = { type: 'water', temp_c: 20, sg: 1.0, viscosity_cst: 1.004 };
      this.state.pipes = [
        {
          id: 'branch_1',
          label: 'Branch 1 - Primary Delivery (100mm)',
          catalog_id: '',
          diameter_mm: 102.3,
          material: 'commercial_steel',
          roughness_mm: 0.046,
          length_m: 80.0,
          elevation_m: 4.0,
          fittings: { 'elbow_90_standard': 2, 'gate_valve_open': 1, 'swing_check_open': 1 },
          custom_k: 0.0,
          flow_pct: 0
        },
        {
          id: 'branch_2',
          label: 'Branch 2 - Secondary Bypass (80mm)',
          catalog_id: '',
          diameter_mm: 77.9,
          material: 'commercial_steel',
          roughness_mm: 0.046,
          length_m: 95.0,
          elevation_m: 4.0,
          fittings: { 'elbow_90_standard': 3, 'butterfly_valve_open': 1, 'swing_check_open': 1 },
          custom_k: 0.0,
          flow_pct: 0
        }
      ];
    } else {
      // Series sample: Suction Line + Discharge Main + Vertical Riser
      this.state.topology = 'series';
      this.state.parallel_balancing = 'auto';
      this.state.flow_rate = 120.0;
      this.state.flow_unit = 'm3h';
      this.state.static_elevation = 18.0;
      this.state.friction_method = 'darcy_weisbach';
      this.state.fluid = { type: 'water', temp_c: 20, sg: 1.0, viscosity_cst: 1.004 };
      this.state.pipes = [
        {
          id: 'pipe_suction',
          label: '1. Suction Line (150mm / 6")',
          catalog_id: '',
          diameter_mm: 154.1,
          material: 'commercial_steel',
          roughness_mm: 0.046,
          length_m: 12.0,
          elevation_m: -1.5,
          fittings: { 'foot_valve_strainer': 1, 'elbow_90_long_radius': 1 },
          custom_k: 0.0,
          flow_pct: 0
        },
        {
          id: 'pipe_discharge',
          label: '2. Discharge Overland Main (100mm / 4")',
          catalog_id: '',
          diameter_mm: 102.3,
          material: 'commercial_steel',
          roughness_mm: 0.046,
          length_m: 140.0,
          elevation_m: 4.5,
          fittings: { 'swing_check_open': 1, 'gate_valve_open': 1, 'elbow_90_standard': 3 },
          custom_k: 0.0,
          flow_pct: 0
        },
        {
          id: 'pipe_riser',
          label: '3. Vertical Riser to Storage Tank (80mm / 3")',
          catalog_id: '',
          diameter_mm: 77.9,
          material: 'commercial_steel',
          roughness_mm: 0.046,
          length_m: 35.0,
          elevation_m: 15.0,
          fittings: { 'elbow_90_standard': 2, 'butterfly_valve_open': 1 },
          custom_k: 0.0,
          flow_pct: 0
        }
      ];
    }
  }

  /**
   * Calculates total K-factor accumulated on a pipe from fittings and custom K.
   */
  calculatePipeTotalK(pipe) {
    let totalK = parseFloat(pipe.custom_k) || 0.0;
    const fittingsMap = this.getFittingsLookup();
    if (pipe.fittings && typeof pipe.fittings === 'object') {
      Object.entries(pipe.fittings).forEach(([key, qty]) => {
        const count = parseInt(qty) || 0;
        if (count > 0 && fittingsMap[key]) {
          totalK += count * (fittingsMap[key].K || 0.0);
        }
      });
    }
    return +(totalK.toFixed(3));
  }

  getFittingsLookup() {
    const list = window.__PMP_FITTINGS || (typeof FITTINGS !== 'undefined' ? FITTINGS : []);
    const dict = {};
    list.forEach(f => { dict[f.key] = f; });
    return dict;
  }

  getStandardPipesList() {
    if (Array.isArray(window.__PMP_STANDARD_PIPES) && window.__PMP_STANDARD_PIPES.length > 0) {
      return window.__PMP_STANDARD_PIPES;
    }
    if (typeof STANDARD_PIPES !== 'undefined' && Array.isArray(STANDARD_PIPES) && STANDARD_PIPES.length > 0) {
      return STANDARD_PIPES;
    }
    return [];
  }

  getMaterialsList() {
    if (Array.isArray(window.__PMP_MATERIALS) && window.__PMP_MATERIALS.length > 0) {
      return window.__PMP_MATERIALS;
    }
    if (typeof MATERIALS !== 'undefined' && Array.isArray(MATERIALS) && MATERIALS.length > 0) {
      return MATERIALS;
    }
    return [];
  }

  /**
   * Renders the interactive table of pipeline segments.
   */
  renderTable() {
    const tbody = document.getElementById('simple-pipes-tbody');
    const badge = document.getElementById('simple-pipe-count-badge');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (badge) {
      const n = this.state.pipes.length;
      badge.textContent = `${n} Segment${n === 1 ? '' : 's'}`;
    }

    const catalog = this.getStandardPipesList();
    const materials = this.getMaterialsList();
    const isParallelManual = (this.state.topology === 'parallel' && this.state.parallel_balancing === 'manual');

    this.state.pipes.forEach((p, idx) => {
      const tr = document.createElement('tr');
      tr.style.cssText = 'border-bottom:1px solid #21262d;';

      // 1. Pipe index
      const tdIdx = document.createElement('td');
      tdIdx.style.cssText = 'text-align:center;font-weight:700;color:#64748b;';
      tdIdx.textContent = idx + 1;
      tr.appendChild(tdIdx);

      // 2. Label
      const tdLabel = document.createElement('td');
      tdLabel.innerHTML = `<input type="text" class="pn-input-cell" value="${p.label.replace(/"/g, '&quot;')}" onchange="simpleController.updatePipeProp(${idx}, 'label', this.value)" placeholder="Segment name" style="font-weight:600;">`;
      tr.appendChild(tdLabel);

      // 3. Standard Pipe Catalog Dropdown
      const tdCat = document.createElement('td');
      const catSelect = document.createElement('select');
      catSelect.className = 'pn-input-cell';
      catSelect.style.cssText = 'width:180px;font-size:11.5px;';
      
      const optCustom = document.createElement('option');
      optCustom.value = '';
      optCustom.textContent = '— Custom Dimensions —';
      catSelect.appendChild(optCustom);

      catalog.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.id;
        opt.textContent = this.formatCatalogOptionText(item);
        if (p.catalog_id && String(p.catalog_id) === String(item.id)) {
          opt.selected = true;
        }
        catSelect.appendChild(opt);
      });

      catSelect.addEventListener('change', (e) => {
        const selId = e.target.value;
        this.updatePipeFromCatalog(idx, selId);
      });
      tdCat.appendChild(catSelect);
      tr.appendChild(tdCat);

      // 4. Inner Diameter (mm)
      const tdDiam = document.createElement('td');
      tdDiam.innerHTML = `<input type="number" step="0.1" min="1" class="pn-input-cell" value="${p.diameter_mm}" onchange="simpleController.updatePipeProp(${idx}, 'diameter_mm', parseFloat(this.value))" style="text-align:right;font-family:monospace;font-weight:600;color:#38bdf8;">`;
      tr.appendChild(tdDiam);

      // 5. Material Dropdown
      const tdMat = document.createElement('td');
      const matSelect = document.createElement('select');
      matSelect.className = 'pn-input-cell';
      matSelect.style.cssText = 'width:150px;font-size:11.5px;';
      materials.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.key;
        opt.textContent = m.label;
        if (p.material === m.key) opt.selected = true;
        matSelect.appendChild(opt);
      });
      matSelect.addEventListener('change', (e) => {
        const selectedKey = e.target.value;
        const matObj = materials.find(m => m.key === selectedKey);
        const rough = (matObj && matObj.roughness_mm) ? matObj.roughness_mm : 0.046;
        this.updatePipeProp(idx, 'material', selectedKey);
        this.updatePipeProp(idx, 'roughness_mm', rough);
      });
      tdMat.appendChild(matSelect);
      tr.appendChild(tdMat);

      // 6. Length (m)
      const tdLen = document.createElement('td');
      tdLen.innerHTML = `<input type="number" step="0.1" min="0.1" class="pn-input-cell" value="${p.length_m}" onchange="simpleController.updatePipeProp(${idx}, 'length_m', parseFloat(this.value))" style="text-align:right;font-family:monospace;">`;
      tr.appendChild(tdLen);

      // 7. Elevation Lift (m)
      const tdElev = document.createElement('td');
      tdElev.innerHTML = `<input type="number" step="0.1" class="pn-input-cell" value="${p.elevation_m}" onchange="simpleController.updatePipeProp(${idx}, 'elevation_m', parseFloat(this.value))" style="text-align:right;font-family:monospace;color:#c084fc;">`;
      tr.appendChild(tdElev);

      // 8. Fittings Button (shows total count and accumulated K)
      const tdFit = document.createElement('td');
      const kTotal = this.calculatePipeTotalK(p);
      let fitCount = 0;
      if (p.fittings) {
        Object.values(p.fittings).forEach(v => { fitCount += (parseInt(v) || 0); });
      }
      const fitLabel = fitCount > 0 
        ? `${fitCount} item${fitCount === 1 ? '' : 's'} (K=${kTotal})`
        : (kTotal > 0 ? `Custom K=${kTotal}` : 'None (K=0)');
      const fitBtnColor = (fitCount > 0 || kTotal > 0) ? '#fbbf24' : '#8b949e';

      tdFit.innerHTML = `
        <button type="button" class="pn-btn" onclick="simpleController.openFittingsModal(${idx})" style="width:100%;font-size:11px;padding:3px 8px;display:flex;align-items:center;justify-content:space-between;border-color:rgba(251,191,36,0.3);color:${fitBtnColor};">
          <span><i class="bi bi-tools" style="margin-right:4px;"></i>${fitLabel}</span>
          <i class="bi bi-pencil" style="font-size:10px;opacity:0.7;"></i>
        </button>
      `;
      tr.appendChild(tdFit);

      // 9. Flow Share % (Only relevant for manual parallel networks)
      if (isParallelManual) {
        const tdShare = document.createElement('td');
        tdShare.innerHTML = `<input type="number" step="1" min="0" max="100" class="pn-input-cell" value="${p.flow_pct || 0}" onchange="simpleController.updatePipeProp(${idx}, 'flow_pct', parseFloat(this.value))" style="text-align:right;color:#22c55e;font-weight:700;">`;
        tr.appendChild(tdShare);
      }

      // 10. Actions (Duplicate, Delete)
      const tdActions = document.createElement('td');
      tdActions.style.cssText = 'text-align:center;white-space:nowrap;';
      tdActions.innerHTML = `
        <div style="display:inline-flex;gap:4px;">
          <button type="button" class="pn-btn" onclick="simpleController.duplicatePipe(${idx})" style="padding:3px 6px;font-size:11px;" title="Duplicate segment">
            <i class="bi bi-copy"></i>
          </button>
          <button type="button" class="pn-btn" onclick="simpleController.removePipe(${idx})" style="padding:3px 6px;font-size:11px;color:#ef4444;" title="Delete segment">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      `;
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  }

  /**
   * Updates an attribute of a pipe segment and triggers recalculation.
   */
  updatePipeProp(idx, prop, val) {
    if (!this.state.pipes[idx]) return;
    this.state.pipes[idx][prop] = val;
    this.calculate();
  }

  /**
   * Generates a descriptive, human-readable label for standard pipe catalog options.
   * Format: Standard: Nominal/OD size • Schedule/SDR (ID XX.Xmm)
   * Ensures no undefined or NaN values appear in the dropdown.
   */
  formatCatalogOptionText(item) {
    if (!item) return '';
    // Determine inner diameter in mm:
    let innerDia = item.id_mm;
    if (innerDia === undefined || innerDia === null || isNaN(innerDia)) {
      innerDia = item.inner_dia_mm;
    }
    if ((innerDia === undefined || innerDia === null || isNaN(innerDia)) && item.od_mm) {
      innerDia = item.od_mm - 2 * (item.wall_thickness_mm || 0);
    }
    const innerDiaFormatted = (typeof innerDia === 'number' && !isNaN(innerDia))
      ? innerDia.toFixed(1)
      : (innerDia || '—');

    // Nominal diameter/size label:
    let sizeLabel = '';
    const isMetricOD = item.standard && (item.standard.includes('4427') || item.standard.includes('8062'));
    if (isMetricOD) {
      const nbPart = item.nb_mm ? ` (DN${item.nb_mm})` : '';
      sizeLabel = `OD ${item.od_mm}mm${nbPart}`;
    } else if (item.nb_inch && !String(item.nb_inch).includes('mm') && !String(item.standard || '').includes('EN 545')) {
      sizeLabel = `${item.nb_inch} (DN${item.nb_mm})`;
    } else if (item.nb_mm) {
      sizeLabel = `DN${item.nb_mm}`;
    } else if (item.od_mm) {
      sizeLabel = `OD ${item.od_mm}mm`;
    } else {
      sizeLabel = item.size_label || 'Standard';
    }

    const schStr = item.schedule_sdr ? ` • ${item.schedule_sdr}` : '';
    const stdName = item.standard || item.material || 'Standard';
    return `${stdName}: ${sizeLabel}${schStr} (ID ${innerDiaFormatted}mm)`;
  }

  /**
   * Updates a pipe segment from a selected standard catalog item.
   */
  updatePipeFromCatalog(idx, catalogId) {
    const pipe = this.state.pipes[idx];
    if (!pipe) return;

    if (!catalogId) {
      pipe.catalog_id = '';
      this.renderTable();
      this.calculate();
      return;
    }

    const catalog = this.getStandardPipesList();
    const item = catalog.find(x => String(x.id) === String(catalogId));
    if (item) {
      pipe.catalog_id = item.id;
      let innerDia = item.id_mm;
      if (innerDia === undefined || innerDia === null || isNaN(innerDia)) {
        innerDia = item.inner_dia_mm;
      }
      if ((innerDia === undefined || innerDia === null || isNaN(innerDia)) && item.od_mm) {
        innerDia = item.od_mm - 2 * (item.wall_thickness_mm || 0);
      }
      if (innerDia && parseFloat(innerDia) > 0) {
        pipe.diameter_mm = +(parseFloat(innerDia).toFixed(1));
      }

      const mKey = (item.material_key || item.material || '').toLowerCase();
      if (mKey.includes('steel')) pipe.material = 'commercial_steel';
      else if (mKey.includes('pvc') || mKey.includes('plastic')) pipe.material = 'pvc';
      else if (mKey.includes('hdpe')) pipe.material = 'hdpe';
      else if (mKey.includes('iron') || mKey.includes('ductile')) pipe.material = 'ductile_iron';
      else if (mKey.includes('copper')) pipe.material = 'copper';

      // Update roughness to match selected material
      const materials = this.getMaterialsList();
      const matEntry = materials.find(m => m.key === pipe.material);
      if (matEntry && matEntry.roughness_mm) {
        pipe.roughness_mm = matEntry.roughness_mm;
      }
    }

    this.renderTable();
    this.calculate();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FITTINGS & VALVES MODAL
  // ─────────────────────────────────────────────────────────────────────────

  openFittingsModal(pipeIdx) {
    this.modalActivePipeIdx = pipeIdx;
    const pipe = this.state.pipes[pipeIdx];
    if (!pipe) return;

    this.modalFittingsCopy = Object.assign({}, pipe.fittings);
    this.modalCustomK = parseFloat(pipe.custom_k) || 0.0;

    const modal = document.getElementById('pn-simple-fittings-modal');
    const labelSpan = document.getElementById('modal-pipe-label');
    const customKInput = document.getElementById('modal-custom-k');

    if (labelSpan) labelSpan.textContent = pipe.label;
    if (customKInput) customKInput.value = this.modalCustomK.toFixed(2);

    this.renderModalFittingsList();
    this.updateModalKDisplay();

    if (modal) modal.style.display = 'block';
  }

  renderModalFittingsList() {
    const container = document.getElementById('modal-fittings-list');
    if (!container) return;
    container.innerHTML = '';

    const fittings = window.__PMP_FITTINGS || (typeof FITTINGS !== 'undefined' ? FITTINGS : []);
    
    // Group by category if present, or display alphabetically
    fittings.forEach(f => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,0.02);border:1px solid #30363d;border-radius:6px;padding:6px 10px;';

      const infoDiv = document.createElement('div');
      infoDiv.innerHTML = `
        <div style="font-size:12px;font-weight:600;color:#e6edf3;">${f.label}</div>
        <div style="font-size:10px;color:#8b949e;">Resistance K = <span style="color:#fbbf24;font-family:monospace;">${f.K}</span> each</div>
      `;
      row.appendChild(infoDiv);

      const qty = parseInt(this.modalFittingsCopy[f.key]) || 0;

      const ctrlDiv = document.createElement('div');
      ctrlDiv.style.cssText = 'display:flex;align-items:center;gap:6px;';
      ctrlDiv.innerHTML = `
        <button type="button" class="pn-btn" onclick="simpleController.stepModalFittingQty('${f.key}', -1)" style="padding:2px 8px;font-size:12px;line-height:1;">-</button>
        <input type="number" min="0" step="1" value="${qty}" onchange="simpleController.setModalFittingQty('${f.key}', parseInt(this.value) || 0)" class="pn-input-cell" style="width:48px;text-align:center;padding:2px 4px;font-weight:700;font-size:12px;color:#38bdf8;">
        <button type="button" class="pn-btn" onclick="simpleController.stepModalFittingQty('${f.key}', 1)" style="padding:2px 8px;font-size:12px;line-height:1;">+</button>
      `;
      row.appendChild(ctrlDiv);

      container.appendChild(row);
    });
  }

  stepModalFittingQty(key, delta) {
    const cur = parseInt(this.modalFittingsCopy[key]) || 0;
    const next = Math.max(0, cur + delta);
    this.setModalFittingQty(key, next);
  }

  setModalFittingQty(key, qty) {
    if (qty <= 0) {
      delete this.modalFittingsCopy[key];
    } else {
      this.modalFittingsCopy[key] = qty;
    }
    this.renderModalFittingsList();
    this.updateModalKDisplay();
  }

  onModalCustomKChange() {
    const customKInput = document.getElementById('modal-custom-k');
    this.modalCustomK = Math.max(0, parseFloat(customKInput?.value) || 0.0);
    this.updateModalKDisplay();
  }

  updateModalKDisplay() {
    let totalK = this.modalCustomK;
    const fittingsMap = this.getFittingsLookup();
    Object.entries(this.modalFittingsCopy).forEach(([k, qty]) => {
      const count = parseInt(qty) || 0;
      if (count > 0 && fittingsMap[k]) {
        totalK += count * (fittingsMap[k].K || 0.0);
      }
    });
    const displayEl = document.getElementById('modal-k-total-display');
    if (displayEl) displayEl.textContent = totalK.toFixed(3);
  }

  clearModalFittings() {
    this.modalFittingsCopy = {};
    this.modalCustomK = 0.0;
    const customKInput = document.getElementById('modal-custom-k');
    if (customKInput) customKInput.value = '0.00';
    this.renderModalFittingsList();
    this.updateModalKDisplay();
  }

  closeFittingsModal() {
    if (this.modalActivePipeIdx !== null && this.state.pipes[this.modalActivePipeIdx]) {
      const pipe = this.state.pipes[this.modalActivePipeIdx];
      pipe.fittings = Object.assign({}, this.modalFittingsCopy);
      pipe.custom_k = this.modalCustomK;
    }
    const modal = document.getElementById('pn-simple-fittings-modal');
    if (modal) modal.style.display = 'none';

    this.modalActivePipeIdx = null;
    this.renderTable();
    this.calculate();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HYDRAULIC CALCULATION & RESULTS RENDERING
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Dispatches hydraulic calculation to the backend API.
   * If applyToSelection is true, saves Duty Point into session and syncs to pump selection.
   */
  async calculate(applyToSelection = false) {
    if (this.isCalculating && !applyToSelection) return;
    this.isCalculating = true;

    const payload = {
      topology: this.state.topology,
      parallel_balancing: this.state.parallel_balancing,
      solver_method: this.state.solver_method || 'ggm',
      flow_rate: this.state.flow_rate,
      flow_unit: this.state.flow_unit,
      static_elevation_m: this.state.static_elevation,
      friction_method: this.state.friction_method,
      fluid: this.state.fluid,
      pipes: this.state.pipes.map(p => ({
        id: p.id,
        label: p.label,
        catalog_id: p.catalog_id,
        diameter_mm: p.diameter_mm,
        material: p.material,
        roughness_mm: p.roughness_mm,
        length_m: p.length_m,
        elevation_m: p.elevation_m,
        fittings: p.fittings,
        custom_k: p.custom_k,
        flow_pct: p.flow_pct
      }))
    };

    try {
      const url = `/api/pipe-network/simple-calculate${applyToSelection ? '?apply_to_selection=true' : ''}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Server responded with ${res.status}`);
      }

      const data = await res.json();
      this.renderResults(data);

      if (applyToSelection && data.applied_to_selection) {
        const unitQ = data.unit_q || 'm³/h';
        const unitH = data.unit_h || 'm';

        // 1. If inside pump_selection.html, directly populate inputs and switch back to tab 1
        const opFlow = document.getElementById('operatingFlow');
        const opHead = document.getElementById('operatingHead');
        if (opFlow && opHead) {
          opFlow.value = data.flow_user_unit;
          opHead.value = data.total_system_head_user_unit;
          opFlow.dispatchEvent(new Event('input', { bubbles: true }));
          opHead.dispatchEvent(new Event('input', { bubbles: true }));
          
          if (typeof switchSelectionTab === 'function') {
            switchSelectionTab('selection');
          }
          alert(`✅ Duty Point successfully applied to Pump Selection!\n\nFlow Rate (Q): ${data.flow_user_unit} ${unitQ}\nTotal Head (TDH): ${data.total_system_head_user_unit} ${unitH}`);
          return;
        }

        // 2. Standalone page redirect option
        if (confirm(`✅ Duty Point successfully saved to session!\n\nFlow Rate: ${data.flow_user_unit} ${unitQ}\nTotal Head (TDH): ${data.total_system_head_user_unit} ${unitH}\n\nWould you like to navigate to Pump Selection to view matched pumps?`)) {
          window.location.href = '/pump-selection';
        }
      }
    } catch (err) {
      console.warn('Backend calculation unavailable, using client-side fallback:', err);
      this.calculateClientSideFallback();
    } finally {
      this.isCalculating = false;
    }
  }

  /**
   * Updates KPI summary cards and per-pipe hydraulic results table.
   */
  renderResults(data) {
    // 1. KPI Cards
    const tdhEl = document.getElementById('simple-res-tdh');
    const tdhFtEl = document.getElementById('simple-res-tdh-ft');
    const flowEl = document.getElementById('simple-res-flow');
    const flowSubEl = document.getElementById('simple-res-flow-sub');
    const fricEl = document.getElementById('simple-res-friction');
    const fricBreakdownEl = document.getElementById('simple-res-friction-breakdown');
    const staticEl = document.getElementById('simple-res-static');
    const powerEl = document.getElementById('simple-res-power');
    const powerHpEl = document.getElementById('simple-res-power-hp');
    const rsysEl = document.getElementById('simple-res-rsys');

    if (tdhEl) tdhEl.textContent = `${data.total_system_head_m} m`;
    if (tdhFtEl) tdhFtEl.textContent = `${data.total_system_head_ft} ft`;
    if (flowEl) flowEl.textContent = `${data.flow_m3h} m³/h`;
    if (flowSubEl) flowSubEl.textContent = `${(data.flow_m3h / 3.6).toFixed(2)} L/s (${data.flow_user_unit} ${data.unit_q})`;
    if (fricEl) fricEl.textContent = `${data.total_friction_loss_m} m`;
    if (fricBreakdownEl && Array.isArray(data.pipes)) {
      const totMaj = data.pipes.reduce((acc, p) => acc + (p.hf_major_m || 0), 0);
      const totMin = data.pipes.reduce((acc, p) => acc + (p.hf_minor_m || 0), 0);
      fricBreakdownEl.textContent = `Major: ${totMaj.toFixed(2)} m | Minor: ${totMin.toFixed(2)} m`;
    }
    if (staticEl) staticEl.textContent = `${data.static_elevation_m} m`;
    if (powerEl) powerEl.textContent = `${data.hydraulic_power_kw} kW`;
    if (powerHpEl) powerHpEl.textContent = `${data.hydraulic_power_hp} HP`;
    if (rsysEl) rsysEl.textContent = data.equivalent_system_R ? data.equivalent_system_R.toExponential(3) : '—';

    // 2. Per-pipe breakdown table
    const tbody = document.getElementById('simple-results-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    (data.pipes || []).forEach(p => {
      const tr = document.createElement('tr');
      tr.style.cssText = 'border-bottom:1px solid #21262d;';

      const v = typeof p.velocity_m_s === 'number' ? p.velocity_m_s : (typeof p.velocity_ms === 'number' ? p.velocity_ms : 0.0);
      let velBadgeClass = 'pn-badge-vel-opt';
      let velHint = 'Optimal velocity';
      if (v < 0.9) {
        velBadgeClass = 'pn-badge-vel-low';
        velHint = 'Low velocity (<0.9 m/s) - risk of solid sedimentation';
      } else if (v > 3.5) {
        velBadgeClass = 'pn-badge-vel-excess';
        velHint = 'Excessive velocity (>3.5 m/s) - high erosion, surge and pipe wear';
      } else if (v > 2.5) {
        velBadgeClass = 'pn-badge-vel-high';
        velHint = 'Elevated velocity (2.5 - 3.5 m/s) - higher friction losses';
      }

      const reynolds = Math.round(p.reynolds || 0).toLocaleString();
      const regime = p.flow_regime || p.regime || 'Turbulent';
      const fFactor = p.friction_factor !== undefined ? p.friction_factor : '—';
      const kTotal = p.k_total !== undefined ? p.k_total : (p.K_total !== undefined ? p.K_total : 0.0);
      const hfMaj = typeof p.hf_major_m === 'number' ? p.hf_major_m.toFixed(3) : (p.hf_major_m || 0);
      const hfMin = typeof p.hf_minor_m === 'number' ? p.hf_minor_m.toFixed(3) : (p.hf_minor_m || 0);
      const hfElev = typeof p.hf_elevation_m === 'number' ? p.hf_elevation_m.toFixed(3) : (p.hf_elevation_m || 0);
      const segHead = p.total_segment_head_m !== undefined ? p.total_segment_head_m : (p.h_total_m !== undefined ? p.h_total_m : (parseFloat(hfMaj) + parseFloat(hfMin) + parseFloat(hfElev)));
      const segHeadFmt = typeof segHead === 'number' ? segHead.toFixed(3) : segHead;

      tr.innerHTML = `
        <td style="font-weight:600;color:#e6edf3;">${p.label || p.id}</td>
        <td style="font-family:monospace;color:#94a3b8;font-size:11.5px;">ID ${p.diameter_mm} mm</td>
        <td style="text-align:right;font-family:monospace;font-weight:700;color:#38bdf8;">${p.flow_m3h} m³/h</td>
        <td style="text-align:center;">
          <span class="pn-badge-velocity ${velBadgeClass}" title="${velHint}">
            ${typeof v === 'number' ? v.toFixed(2) : v} m/s
          </span>
        </td>
        <td style="text-align:center;font-family:monospace;color:#cbd5e1;">${reynolds}</td>
        <td style="text-align:center;font-size:11px;color:#8b949e;">${regime}</td>
        <td style="text-align:right;font-family:monospace;color:#a78bfa;">${fFactor}</td>
        <td style="text-align:right;font-family:monospace;">${hfMaj} m</td>
        <td style="text-align:right;font-family:monospace;">${hfMin} m <span style="font-size:10px;color:#64748b;">(K=${kTotal})</span></td>
        <td style="text-align:right;font-family:monospace;color:#c084fc;">${hfElev} m</td>
        <td style="text-align:right;font-family:monospace;font-weight:700;color:#fbbf24;">${segHeadFmt} m</td>
        <td style="text-align:right;font-family:monospace;font-size:11px;color:#64748b;">${p.resistance_R ? p.resistance_R.toExponential(2) : '—'}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  /**
   * Pure client-side calculation fallback in case network API is temporarily unreachable.
   */
  calculateClientSideFallback() {
    const g = 9.80665;
    const q_m3h = this.state.flow_rate;
    const q_m3s = q_m3h / 3600.0;
    const nu = (this.state.fluid.viscosity_cst || 1.004) * 1e-6;
    const rho = (this.state.fluid.sg || 1.0) * 1000.0;

    let totalMajor = 0.0;
    let totalMinor = 0.0;
    const pipesRes = [];

    this.state.pipes.forEach(p => {
      const d_m = p.diameter_mm / 1000.0;
      const area = Math.PI * (d_m ** 2) / 4.0;
      const vel = area > 0 ? (q_m3s / area) : 0.0;
      const Re = (vel * d_m) / nu;
      
      const eps_d = (p.roughness_mm / 1000.0) / d_m;
      let f = 0.02;
      if (Re < 2300) {
        f = 64.0 / (Re || 1);
      } else {
        f = 0.25 / Math.pow(Math.log10(eps_d / 3.7 + 5.74 / Math.pow(Re, 0.9)), 2);
      }

      const hf = f * (p.length_m / d_m) * (vel ** 2) / (2.0 * g);
      const kTot = this.calculatePipeTotalK(p);
      const hm = kTot * (vel ** 2) / (2.0 * g);
      const dz = p.elevation_m;

      totalMajor += hf;
      totalMinor += hm;

      pipesRes.push({
        label: p.label,
        diameter_mm: p.diameter_mm,
        flow_m3h: +(q_m3h.toFixed(2)),
        velocity_m_s: +(vel.toFixed(2)),
        reynolds: Math.round(Re),
        flow_regime: Re < 2300 ? 'Laminar' : (Re < 4000 ? 'Transitional' : 'Turbulent'),
        friction_factor: +(f.toFixed(4)),
        hf_major_m: +(hf.toFixed(2)),
        hf_minor_m: +(hm.toFixed(2)),
        hf_elevation_m: +(dz.toFixed(2)),
        total_segment_head_m: +((hf + hm + dz).toFixed(2)),
        k_total: kTot,
        resistance_R: q_m3h > 0 ? +(((hf + hm) / (q_m3h ** 2)).toExponential(3)) : 0
      });
    });

    const tdh = totalMajor + totalMinor + this.state.static_elevation;
    const pKw = (rho * g * q_m3s * tdh) / 1000.0;

    this.renderResults({
      total_system_head_m: +(tdh.toFixed(2)),
      total_system_head_ft: +((tdh * 3.28084).toFixed(2)),
      flow_m3h: +(q_m3h.toFixed(2)),
      flow_user_unit: +(q_m3h.toFixed(2)),
      unit_q: this.state.flow_unit,
      unit_h: 'm',
      total_friction_loss_m: +((totalMajor + totalMinor).toFixed(2)),
      static_elevation_m: +(this.state.static_elevation.toFixed(2)),
      hydraulic_power_kw: +(pKw.toFixed(2)),
      hydraulic_power_hp: +((pKw * 1.34102).toFixed(2)),
      equivalent_system_R: q_m3h > 0 ? ((totalMajor + totalMinor) / (q_m3h ** 2)) : 0,
      pipes: pipesRes
    });
  }

  applyToPumpSelection() {
    this.calculate(true);
  }
}

// Instantiate global singleton instance
window.simpleController = new SimpleNetworkController();

/**
 * Toggles the Pipe Network Designer view between:
 *  - 'canvas': Interactive SVG visual layout canvas
 *  - 'simple': Form and dropdown-driven simple network list
 */
function setDesignerMode(mode) {
  const canvasBtn = document.getElementById('btn-mode-canvas');
  const simpleBtn = document.getElementById('btn-mode-simple');
  const mainRow = document.getElementById('pn-main-row');
  const simpleWrap = document.getElementById('pn-simple-mode-wrap');
  const canvasTools1 = document.getElementById('pn-canvas-tools-group-1');
  const resultsSec = document.getElementById('pn-results-section');

  const topCanvasBtn = document.getElementById('btn-top-mode-canvas');
  const topSimpleBtn = document.getElementById('btn-top-mode-simple');

  if (mode === 'simple') {
    // 1. Update toolbar and top switcher button highlights
    canvasBtn?.classList.remove('active-tool');
    simpleBtn?.classList.add('active-tool');
    topCanvasBtn?.classList.remove('active-tool');
    topSimpleBtn?.classList.add('active-tool');
    if (topSimpleBtn) { topSimpleBtn.style.background = '#22c55e'; topSimpleBtn.style.color = '#000'; }
    if (topCanvasBtn) { topCanvasBtn.style.background = 'transparent'; topCanvasBtn.style.color = '#8b949e'; }

    // 2. Hide visual canvas elements
    if (mainRow) mainRow.style.display = 'none';
    if (canvasTools1) canvasTools1.style.display = 'none';
    if (resultsSec) resultsSec.style.display = 'none';

    // 3. Show simple mode container
    if (simpleWrap) simpleWrap.style.display = 'flex';

    // 4. Initialize simple controller
    if (!window.simpleController.isInitialized) {
      window.simpleController.init();
    } else {
      window.simpleController.calculate();
    }

    try { localStorage.setItem('pmp_pipe_designer_mode', 'simple'); } catch (e) {}

  } else {
    // Canvas Mode
    canvasBtn?.classList.add('active-tool');
    simpleBtn?.classList.remove('active-tool');
    topCanvasBtn?.classList.add('active-tool');
    topSimpleBtn?.classList.remove('active-tool');
    if (topCanvasBtn) { topCanvasBtn.style.background = '#38bdf8'; topCanvasBtn.style.color = '#000'; }
    if (topSimpleBtn) { topSimpleBtn.style.background = 'transparent'; topSimpleBtn.style.color = '#22c55e'; }

    if (simpleWrap) simpleWrap.style.display = 'none';
    if (mainRow) mainRow.style.display = 'flex';
    if (canvasTools1) canvasTools1.style.display = 'inline-flex';

    try { localStorage.setItem('pmp_pipe_designer_mode', 'canvas'); } catch (e) {}

    // Trigger redraw of canvas if available
    if (typeof scheduleDraw === 'function') scheduleDraw();
  }
}
