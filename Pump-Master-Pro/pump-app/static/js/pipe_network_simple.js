/**
 * pipe_network_simple.js — Advanced Pipe Network Designer (Dropdown & List Mode)
 *
 * Architecture & Technical Overview:
 * =================================
 * This module delivers a professional, form-driven pipe network calculation workflow
 * for engineers who prefer tabular and dropdown specification over visual canvas drafting.
 *
 * Supported Piping Topologies:
 * ----------------------------
 * 1. Series Network:
 *    - All pipe segments are connected sequentially in an end-to-end continuous line.
 *    - Incompressible continuity: Flow Q is identical across all segments:
 *        Q_1 = Q_2 = ... = Q_k = Q_total
 *    - Total Dynamic Head (TDH) accumulates linearly:
 *        H_total = Σ(h_major + h_minor + Δz_segment) + Static_Elevation
 *
 * 2. Compound Parallel Network:
 *    - Fluid divides across multiple parallel branches between common inlet and outlets.
 *    - Each parallel branch can contain up to FIVE (5) pipe segments in series
 *      (e.g., Header Takeoff -> Main Line -> Reducer -> Vertical Riser).
 *    - Each parallel branch supports its own INDEPENDENT discharge height / elevation (Δz_outlet).
 *    - Solved either via:
 *      a) Auto Hydraulic Balancing: Iteratively solves for flow distribution such that
 *         piezometric manifold heads balance:
 *           H_manifold = Z_discharge_j + Σ h_f,j(Q_j) = constant  for all branches j
 *           Σ Q_j = Q_total
 *      b) Manual Allocation: User specifies percentage flow share per branch (%_j),
 *         and pump head requirement is evaluated as max_j(H_branch_j).
 *
 * Pipe Specification & Standard Catalog Filter Modal:
 * ---------------------------------------------------
 * Provides cascading selection to quickly filter standard pipes by:
 *   Standard (ISO 4427, ASME B36.10M, DIN 8062, EN 545, etc.) ->
 *   Material (Steel, HDPE, PVC, Ductile Iron, Copper) ->
 *   Schedule / SDR (SDR 11, SDR 17, Sch 40, Sch 80, etc.) ->
 *   Nominal Size / Diameter.
 * Displays live physical previews (OD, wall thickness, ID, roughness, pressure rating).
 */

'use strict';

class SimpleNetworkController {
  constructor() {
    // Core state representing the pipe network configuration
    this.state = {
      topology: 'series',               // 'series' or 'parallel'
      parallel_balancing: 'auto',        // 'auto' (hydraulic split) or 'manual' (% allocation)
      flow_rate: 100.0,                  // Operating flow in selected engineering unit
      flow_unit: window.__PMP_UNIT_Q || 'm3h', // e.g. 'm3h', 'ls', 'gpm'
      static_elevation: 10.0,            // Global static lift difference (m) for series
      solver_method: 'ggm',              // Network solver: 'ggm', 'newton_raphson', 'hardy_cross', or 'linear_theory'
      friction_method: 'darcy_weisbach', // 'darcy_weisbach' or 'hazen_williams'
      fluid: {
        type: 'water',
        temp_c: 20,
        sg: 1.00,
        viscosity_cst: 1.004
      },
      pipes: [],                         // Array of pipe segments for Series mode
      parallel_branches: []              // Array of parallel branches (each with up to 5 series pipes)
    };

    // Modal tracking state for Valves & Fittings
    this.modalActiveTarget = null;       // { type: 'series', pipeIdx: 0 } or { type: 'parallel', branchIdx: 0, pipeIdx: 0 }
    this.modalFittingsCopy = {};
    this.modalCustomK = 0.0;

    // Modal tracking state for Pipe Configuration & Standard Catalog Filter
    this.pipeConfigTarget = null;        // { type: 'series'|'parallel', branchIdx: null|0, pipeIdx: 0 }
    this.pipeConfigSelectedStd = 'all';
    this.pipeConfigSelectedMat = 'all';
    this.pipeConfigSelectedSch = 'all';
    this.pipeConfigSelectedId = '';

    // Calculation debounce timer to prevent spamming HTTP requests during typing
    this.debounceTimer = null;
    this.isCalculating = false;
    this.isInitialized = false;
  }

  /**
   * Initializes the controller on page load:
   * - Restores saved session parameters if available
   * - Normalizes series pipes and compound parallel branches
   * - Renders initial tables and triggers the initial calculation
   */
  init() {
    const allowSeries = (typeof window.FEAT_PIPE_SERIES !== 'undefined')
      ? Boolean(window.FEAT_PIPE_SERIES)
      : (document.getElementById('topo-card-series') ? true : false);
    const allowParallel = (typeof window.FEAT_PIPE_PARALLEL !== 'undefined')
      ? Boolean(window.FEAT_PIPE_PARALLEL)
      : (document.getElementById('topo-card-parallel') ? true : false);
    const orgDefaults = window.__PMP_PIPE_NETWORK_DEFAULTS || {};
    const configuredTopo = orgDefaults.pn_topology || 'series';
    const defaultTopo = (configuredTopo === 'parallel' && allowParallel) ? 'parallel' : (allowSeries ? 'series' : (allowParallel ? 'parallel' : 'series'));

    const sess = window.__PMP_SESSION_PIPE_NETWORK;
    if (sess && sess.mode === 'simple') {
      let desiredTopo = sess.topology || defaultTopo;
      if (desiredTopo === 'series' && !allowSeries && allowParallel) desiredTopo = 'parallel';
      if (desiredTopo === 'parallel' && !allowParallel && allowSeries) desiredTopo = 'series';
      this.state.topology = desiredTopo;
      this.state.parallel_balancing = sess.parallel_balancing || 'auto';
      this.state.flow_rate = parseFloat(sess.flow_rate || sess.flow_m3h || 100.0);
      this.state.flow_unit = sess.flow_unit || window.__PMP_UNIT_Q || orgDefaults.unit_q || 'm3h';
      this.state.static_elevation = parseFloat(sess.static_elevation_m || sess.static_head || orgDefaults.pn_default_elev_change_m || 10.0);
      this.state.solver_method = sess.solver_method || orgDefaults.pn_solver_method || 'ggm';
      this.state.friction_method = sess.friction_method || orgDefaults.pn_friction_method || 'darcy_weisbach';
      if (sess.fluid) {
        this.state.fluid = Object.assign({}, this.state.fluid, sess.fluid);
      }

      // Restore Series pipes if present
      if (Array.isArray(sess.pipes) && sess.pipes.length > 0) {
        this.state.pipes = sess.pipes.map(p => this.normalizePipeInput(p));
      } else {
        this.loadPresetData('series');
      }

      // Restore Parallel branches if present
      if (Array.isArray(sess.parallel_branches) && sess.parallel_branches.length > 0) {
        this.state.parallel_branches = sess.parallel_branches.map(b => this.normalizeBranchInput(b));
      } else if (this.state.topology === 'parallel' && Array.isArray(sess.pipes) && sess.pipes.length > 0) {
        // Backward-compatibility: Convert flat parallel pipes into branches with 1 series segment
        this.state.parallel_branches = sess.pipes.map((p, idx) => ({
          id: 'branch_' + (idx + 1),
          label: `Branch ${idx + 1} - ${p.label || 'Line'}`,
          discharge_elevation_m: parseFloat(p.elevation_m || this.state.static_elevation || 10.0),
          flow_pct: parseFloat(p.flow_pct || (100 / sess.pipes.length).toFixed(1)),
          pipes: [this.normalizePipeInput(p)]
        }));
      } else {
        this.loadPresetData('parallel');
      }
    } else {
      // Default clean initialization using Organisation Defaults
      this.loadPresetData('series');
      this.loadPresetData('parallel');
      this.state.topology = defaultTopo;
      if (orgDefaults.pn_solver_method) this.state.solver_method = orgDefaults.pn_solver_method;
      if (orgDefaults.pn_friction_method) this.state.friction_method = orgDefaults.pn_friction_method;
      if (orgDefaults.pn_default_elev_change_m) this.state.static_elevation = parseFloat(orgDefaults.pn_default_elev_change_m);
      if (orgDefaults.unit_q) this.state.flow_unit = orgDefaults.unit_q;
    }

    this.syncControlsFromState();

    // Bidirectional sync with top toolbar flow rate input (pn-global-flow) if present
    const globalFlow = document.getElementById('pn-global-flow');
    const globalUnit = document.getElementById('pn-flow-unit');
    if (globalFlow && !this._globalFlowBound) {
      this._globalFlowBound = true;
      const onFlowChange = () => {
        const val = parseFloat(globalFlow.value);
        if (!isNaN(val) && val > 0) {
          this.state.flow_rate = val;
          const sFlow = document.getElementById('simple-flow-rate');
          if (sFlow) sFlow.value = val;
          if (document.getElementById('pn-simple-mode-wrap')?.style.display !== 'none') {
            this.onInputDebounce();
          }
        }
      };
      globalFlow.addEventListener('input', onFlowChange);
      globalFlow.addEventListener('change', onFlowChange);
    }
    if (globalUnit && !this._globalUnitBound) {
      this._globalUnitBound = true;
      globalUnit.addEventListener('change', () => {
        this.state.flow_unit = globalUnit.value;
        const sUnit = document.getElementById('simple-flow-unit');
        if (sUnit) sUnit.value = globalUnit.value;
        if (document.getElementById('pn-simple-mode-wrap')?.style.display !== 'none') {
          this.calculate();
        }
      });
    }

    // Bidirectional sync with top toolbar solver and friction selectors
    const globalSolver = document.getElementById('pn-solver-method');
    if (globalSolver && !this._globalSolverBound) {
      this._globalSolverBound = true;
      globalSolver.addEventListener('change', () => {
        this.state.solver_method = globalSolver.value;
        if (document.getElementById('pn-simple-mode-wrap')?.style.display !== 'none') {
          this.calculate();
        }
      });
    }

    const globalFriction = document.getElementById('pn-friction-method');
    if (globalFriction && !this._globalFricBound) {
      this._globalFricBound = true;
      globalFriction.addEventListener('change', () => {
        this.state.friction_method = globalFriction.value;
        if (document.getElementById('pn-simple-mode-wrap')?.style.display !== 'none') {
          this.calculate();
        }
      });
    }

    // Bidirectional sync with temperature & SG inputs
    const globalTemp = document.getElementById('pn-temperature');
    if (globalTemp && !this._globalTempBound) {
      this._globalTempBound = true;
      globalTemp.addEventListener('input', () => {
        const t = parseFloat(globalTemp.value);
        if (!isNaN(t)) {
          if (!this.state.fluid) this.state.fluid = {};
          this.state.fluid.temp_c = t;
          if (document.getElementById('pn-simple-mode-wrap')?.style.display !== 'none') {
            this.onInputDebounce();
          }
        }
      });
    }

    const globalSg = document.getElementById('pn-sg');
    if (globalSg && !this._globalSgBound) {
      this._globalSgBound = true;
      globalSg.addEventListener('input', () => {
        const s = parseFloat(globalSg.value);
        if (!isNaN(s) && s > 0) {
          if (!this.state.fluid) this.state.fluid = {};
          this.state.fluid.sg = parseFloat(s.toFixed(2));
          if (document.getElementById('pn-simple-mode-wrap')?.style.display !== 'none') {
            this.onInputDebounce();
          }
        }
      });
    }

    this.renderTable();
    this.calculate();
    this.isInitialized = true;
  }

  /**
   * Normalizes a pipe segment object with guaranteed safe numeric and string defaults.
   */
  normalizePipeInput(p, defaultLabel = 'Pipe Segment') {
    const orgDefaults = window.__PMP_PIPE_NETWORK_DEFAULTS || {};
    const defMat = orgDefaults.pn_default_material || 'commercial_steel';
    const defDia = parseFloat(orgDefaults.pn_default_diameter_mm) || 102.3;
    const defLen = parseFloat(orgDefaults.pn_default_length_m) || 50.0;
    const defRough = parseFloat(orgDefaults.pn_default_roughness_mm) || 0.046;
    return {
      id: p.id || 'pipe_' + Math.random().toString(36).substring(2, 9),
      label: p.label || defaultLabel,
      catalog_id: p.catalog_id || '',
      diameter_mm: Math.max(1.0, parseFloat(p.diameter_mm || p.diameter || defDia)),
      material: p.material || defMat,
      roughness_mm: Math.max(0.0001, parseFloat(p.roughness_mm || p.roughness || defRough)),
      length_m: Math.max(0.1, parseFloat(p.length_m || p.length || defLen)),
      elevation_m: parseFloat(p.elevation_m || p.elevation || 0.0),
      fittings: (typeof p.fittings === 'object' && p.fittings !== null) ? Object.assign({}, p.fittings) : {},
      custom_k: Math.max(0.0, parseFloat(p.custom_k || 0.0)),
      flow_pct: parseFloat(p.flow_pct || p.flow_share || 0.0)
    };
  }

  /**
   * Normalizes a parallel branch object supporting up to 5 series sub-pipes and independent discharge height.
   */
  normalizeBranchInput(b, idx = 0) {
    const rawPipes = Array.isArray(b.pipes) ? b.pipes : (b.sub_pipes ? b.sub_pipes : []);
    const pipes = rawPipes.slice(0, 5).map((p, pIdx) => this.normalizePipeInput(p, `${idx + 1}.${pIdx + 1} Segment`));
    if (pipes.length === 0) {
      pipes.push(this.normalizePipeInput({}, `${idx + 1}.1 Branch Segment`));
    }
    return {
      id: b.id || 'branch_' + (idx + 1) + '_' + Math.random().toString(36).substring(2, 7),
      label: b.label || `Branch ${idx + 1} - Pipeline`,
      discharge_elevation_m: parseFloat(b.discharge_elevation_m !== undefined ? b.discharge_elevation_m : (b.elevation_m || 10.0)),
      flow_pct: parseFloat(b.flow_pct || 0.0),
      pipes: pipes
    };
  }

  /**
   * Switches network topology between 'series' and 'parallel' and updates visual cards.
   */
  setTopology(topo) {
    const allowSeries = (typeof window.FEAT_PIPE_SERIES !== 'undefined')
      ? Boolean(window.FEAT_PIPE_SERIES)
      : (document.getElementById('topo-card-series') ? true : false);
    const allowParallel = (typeof window.FEAT_PIPE_PARALLEL !== 'undefined')
      ? Boolean(window.FEAT_PIPE_PARALLEL)
      : (document.getElementById('topo-card-parallel') ? true : false);

    if (topo === 'series' && !allowSeries && allowParallel) topo = 'parallel';
    if (topo === 'parallel' && !allowParallel && allowSeries) topo = 'series';

    if (topo !== 'series' && topo !== 'parallel') return;
    this.state.topology = topo;

    const cardSeries = document.getElementById('topo-card-series');
    const cardParallel = document.getElementById('topo-card-parallel');
    const radioSeries = document.getElementById('topo-radio-series');
    const radioParallel = document.getElementById('topo-radio-parallel');
    const parallelWrap = document.getElementById('simple-parallel-mode-wrap');
    const staticElevWrap = document.getElementById('simple-static-head-wrap');

    if (topo === 'series') {
      cardSeries?.classList.add('active');
      cardParallel?.classList.remove('active');
      if (radioSeries) radioSeries.checked = true;
      if (parallelWrap) parallelWrap.style.display = 'none';
      if (staticElevWrap) staticElevWrap.style.display = 'block';
    } else {
      cardParallel?.classList.add('active');
      cardSeries?.classList.remove('active');
      if (radioParallel) radioParallel.checked = true;
      if (parallelWrap) parallelWrap.style.display = 'block';
      // In parallel mode, each pipeline branch has its own discharge height
      if (staticElevWrap) staticElevWrap.style.display = 'none';
    }

    this.renderTable();
    this.calculate();
  }

  /**
   * Toggles parallel balancing mode ('auto' iterative hydraulic split vs 'manual' % flow allocation).
   */
  onBalancingChange(method) {
    this.state.parallel_balancing = method;
    this.renderTable();
    this.calculate();
  }

  /**
   * Synchronizes HTML form controls to match internal state.
   */
  syncControlsFromState() {
    const globalFlow = document.getElementById('pn-global-flow');
    if (globalFlow && this.state.flow_rate !== undefined) globalFlow.value = this.state.flow_rate;
    const globalUnit = document.getElementById('pn-flow-unit');
    if (globalUnit && this.state.flow_unit) globalUnit.value = this.state.flow_unit;

    const flowIn = document.getElementById('simple-flow-rate');
    if (flowIn) flowIn.value = this.state.flow_rate;
    const unitSel = document.getElementById('simple-flow-unit');
    if (unitSel) unitSel.value = this.state.flow_unit;

    const staticIn = document.getElementById('simple-static-head');
    if (staticIn) staticIn.value = this.state.static_elevation;

    const globalSolver = document.getElementById('pn-solver-method');
    if (globalSolver && this.state.solver_method) globalSolver.value = this.state.solver_method;
    const solverSel = document.getElementById('simple-solver-method');
    if (solverSel) solverSel.value = this.state.solver_method || 'ggm';

    const globalFriction = document.getElementById('pn-friction-method');
    if (globalFriction && this.state.friction_method) globalFriction.value = this.state.friction_method;
    const fMethod = document.getElementById('simple-friction-method');
    if (fMethod) fMethod.value = this.state.friction_method;

    const globalTemp = document.getElementById('pn-temperature');
    if (globalTemp && this.state.fluid?.temp_c !== undefined) globalTemp.value = this.state.fluid.temp_c;
    const fTemp = document.getElementById('simple-fluid-temp');
    if (fTemp && this.state.fluid?.temp_c !== undefined) fTemp.value = this.state.fluid.temp_c;

    const globalSg = document.getElementById('pn-sg');
    if (globalSg && this.state.fluid?.sg !== undefined) globalSg.value = Number(this.state.fluid.sg).toFixed(2);
    const fSg = document.getElementById('simple-fluid-sg');
    if (fSg && this.state.fluid?.sg !== undefined) fSg.value = Number(this.state.fluid.sg).toFixed(2);

    const fType = document.getElementById('simple-fluid-type');
    if (fType && this.state.fluid?.type) fType.value = this.state.fluid.type;
    const fVisc = document.getElementById('simple-fluid-viscosity');
    if (fVisc && this.state.fluid?.viscosity_cst) fVisc.value = this.state.fluid.viscosity_cst;

    const balAuto = document.getElementById('radio-balancing-auto');
    const balMan = document.getElementById('radio-balancing-manual');
    if (balAuto && this.state.parallel_balancing === 'auto') balAuto.checked = true;
    if (balMan && this.state.parallel_balancing === 'manual') balMan.checked = true;

    this.setTopology(this.state.topology);
  }

  /**
   * Reads HTML form inputs back into internal state.
   */
  readControlsIntoState() {
    const globalFlowIn = document.getElementById('pn-global-flow');
    const flowIn = document.getElementById('simple-flow-rate');
    if (globalFlowIn && globalFlowIn.value !== '') {
      this.state.flow_rate = Math.max(0.001, parseFloat(globalFlowIn.value) || 0.0);
    } else if (flowIn && flowIn.value !== '') {
      this.state.flow_rate = Math.max(0.001, parseFloat(flowIn.value) || 0.0);
    }

    const globalUnitSel = document.getElementById('pn-flow-unit');
    const unitSel = document.getElementById('simple-flow-unit');
    if (globalUnitSel && globalUnitSel.value) {
      this.state.flow_unit = globalUnitSel.value;
    } else if (unitSel && unitSel.value) {
      this.state.flow_unit = unitSel.value;
    }

    const staticIn = document.getElementById('simple-static-head');
    if (staticIn) this.state.static_elevation = parseFloat(staticIn.value) || 0.0;

    const globalSolver = document.getElementById('pn-solver-method');
    const solverSel = document.getElementById('simple-solver-method');
    if (globalSolver && globalSolver.value) this.state.solver_method = globalSolver.value;
    else if (solverSel && solverSel.value) this.state.solver_method = solverSel.value;

    const globalFriction = document.getElementById('pn-friction-method');
    const fMethod = document.getElementById('simple-friction-method');
    if (globalFriction && globalFriction.value) this.state.friction_method = globalFriction.value;
    else if (fMethod && fMethod.value) this.state.friction_method = fMethod.value;

    const globalTemp = document.getElementById('pn-temperature');
    const fTemp = document.getElementById('simple-fluid-temp');
    if (globalTemp && globalTemp.value !== '') this.state.fluid.temp_c = parseFloat(globalTemp.value) || 20;
    else if (fTemp && fTemp.value !== '') this.state.fluid.temp_c = parseFloat(fTemp.value) || 20;

    const globalSg = document.getElementById('pn-sg');
    const fSg = document.getElementById('simple-fluid-sg');
    if (globalSg && globalSg.value !== '') this.state.fluid.sg = parseFloat(parseFloat(globalSg.value).toFixed(2)) || 1.0;
    else if (fSg && fSg.value !== '') this.state.fluid.sg = parseFloat(parseFloat(fSg.value).toFixed(2)) || 1.0;

    const fType = document.getElementById('simple-fluid-type');
    if (fType) this.state.fluid.type = fType.value;
    const fVisc = document.getElementById('simple-fluid-viscosity');
    if (fVisc) this.state.fluid.viscosity_cst = parseFloat(fVisc.value) || 1.004;
  }

  saveStateToStorage() {
    try {
      localStorage.setItem('pmp_pipe_simple_state', JSON.stringify(this.state));
    } catch (e) {
      console.warn('Could not save simple state to localStorage:', e);
    }
  }

  onSolverChange() {
    this.readControlsIntoState();
    this.calculate();
  }

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
    const globalUnitSel = document.getElementById('pn-flow-unit');
    if (globalUnitSel && this.state.flow_unit) {
      globalUnitSel.value = this.state.flow_unit;
    }
    this.calculate();
  }

  onInputDebounce() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.readControlsIntoState();
      const globalFlowIn = document.getElementById('pn-global-flow');
      if (globalFlowIn && this.state.flow_rate) {
        globalFlowIn.value = this.state.flow_rate;
      }
      this.calculate();
    }, 300);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SERIES PIPELINE MANAGEMENT
  // ─────────────────────────────────────────────────────────────────────────

  addPipe() {
    const idx = this.state.pipes.length + 1;
    const def = this.getDefaultPipeSpec();
    const defLen = parseFloat(window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_default_length_m) || 50.0;
    this.state.pipes.push({
      id: 'pipe_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      label: `Pipe ${idx} - Segment`,
      catalog_id: def.catalog_id,
      diameter_mm: def.diameter_mm,
      material: def.material,
      roughness_mm: def.roughness_mm,
      length_m: defLen,
      elevation_m: 0.0,
      fittings: {},
      custom_k: 0.0,
      flow_pct: 0
    });
    this.renderTable();
    this.calculate();
  }

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

  removePipe(idx) {
    if (this.state.pipes.length <= 1) {
      alert('The series pipeline requires at least one pipe segment.');
      return;
    }
    this.state.pipes.splice(idx, 1);
    this.renderTable();
    this.calculate();
  }

  clearPipes() {
    if (this.state.topology === 'parallel') {
      if (!confirm('Reset parallel pipelines to default configuration?')) return;
      this.loadPresetData('parallel');
    } else {
      if (!confirm('Clear all series pipeline segments and start fresh?')) return;
      const def = this.getDefaultPipeSpec();
      const defLen = parseFloat(window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_default_length_m) || 50.0;
      this.state.pipes = [{
        id: 'pipe_' + Date.now(),
        label: 'Pipeline Main',
        catalog_id: def.catalog_id,
        diameter_mm: def.diameter_mm,
        material: def.material,
        roughness_mm: def.roughness_mm,
        length_m: defLen,
        elevation_m: 0.0,
        fittings: {},
        custom_k: 0.0,
        flow_pct: 0
      }];
    }
    this.renderTable();
    this.calculate();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // COMPOUND PARALLEL PIPELINE MANAGEMENT (UP TO 5 SERIES PIPES PER BRANCH)
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Adds a new parallel pipeline branch with 1 starter pipe segment.
   */
  addParallelBranch() {
    const bNum = this.state.parallel_branches.length + 1;
    const defaultFlowPct = +(100 / bNum).toFixed(1);
    const def = this.getDefaultPipeSpec();
    const defLen = parseFloat(window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_default_length_m) || 50.0;
    this.state.parallel_branches.push({
      id: 'branch_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      label: `Branch ${bNum} - Pipeline`,
      discharge_elevation_m: +(this.state.static_elevation || 10.0),
      flow_pct: defaultFlowPct,
      pipes: [
        {
          id: 'subpipe_' + Date.now() + '_1',
          label: `${bNum}.1 Branch Segment`,
          catalog_id: def.catalog_id,
          diameter_mm: def.diameter_mm,
          material: def.material,
          roughness_mm: def.roughness_mm,
          length_m: defLen,
          elevation_m: 0.0,
          fittings: {},
          custom_k: 0.0
        }
      ]
    });
    this.renderTable();
    this.calculate();
  }

  /**
   * Duplicates a parallel branch including all of its series sub-pipes.
   */
  duplicateParallelBranch(bIdx) {
    const src = this.state.parallel_branches[bIdx];
    if (!src) return;
    const copy = JSON.parse(JSON.stringify(src));
    copy.id = 'branch_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
    copy.label = src.label + ' (Copy)';
    copy.pipes.forEach((p, i) => {
      p.id = 'subpipe_' + Date.now() + '_' + (i + 1);
    });
    this.state.parallel_branches.splice(bIdx + 1, 0, copy);
    this.renderTable();
    this.calculate();
  }

  /**
   * Removes a parallel branch.
   */
  removeParallelBranch(bIdx) {
    if (this.state.parallel_branches.length <= 1) {
      alert('The parallel network requires at least one pipeline branch.');
      return;
    }
    this.state.parallel_branches.splice(bIdx, 1);
    this.renderTable();
    this.calculate();
  }

  /**
   * Adds a series pipe segment to a parallel branch (ENFORCING MAX 5 PIPES CONSTRAINT).
   */
  addSubPipeToBranch(bIdx) {
    const branch = this.state.parallel_branches[bIdx];
    if (!branch) return;
    if (branch.pipes.length >= 5) {
      alert('⚠️ Maximum Limit Reached: Each parallel pipeline can have up to 5 pipes in series.');
      return;
    }
    const pNum = branch.pipes.length + 1;
    const def = this.getDefaultPipeSpec();
    const defLen = parseFloat(window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_default_length_m) || 30.0;
    branch.pipes.push({
      id: 'subpipe_' + Date.now() + '_' + pNum,
      label: `${bIdx + 1}.${pNum} Sub-Pipe`,
      catalog_id: def.catalog_id,
      diameter_mm: def.diameter_mm,
      material: def.material,
      roughness_mm: def.roughness_mm,
      length_m: defLen,
      elevation_m: 0.0,
      fittings: {},
      custom_k: 0.0
    });
    this.renderTable();
    this.calculate();
  }

  /**
   * Removes a series sub-pipe segment from a parallel branch.
   */
  removeSubPipeFromBranch(bIdx, pIdx) {
    const branch = this.state.parallel_branches[bIdx];
    if (!branch) return;
    if (branch.pipes.length <= 1) {
      alert('Each parallel pipeline must contain at least one pipe segment.');
      return;
    }
    branch.pipes.splice(pIdx, 1);
    this.renderTable();
    this.calculate();
  }

  updateBranchProp(bIdx, prop, val) {
    const branch = this.state.parallel_branches[bIdx];
    if (!branch) return;
    branch[prop] = val;
    this.calculate();
  }

  updateSubPipeProp(bIdx, pIdx, prop, val) {
    const branch = this.state.parallel_branches[bIdx];
    if (!branch || !branch.pipes[pIdx]) return;
    branch.pipes[pIdx][prop] = val;
    this.calculate();
  }

  updatePipeProp(idx, prop, val) {
    if (!this.state.pipes[idx]) return;
    this.state.pipes[idx][prop] = val;
    this.calculate();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PRESET DATA LOADERS
  // ─────────────────────────────────────────────────────────────────────────

  loadPreset(presetName) {
    if (!confirm(`Load ${presetName === 'series' ? 'Series' : 'Parallel'} sample pipeline configuration? Existing entries will be replaced.`)) {
      return;
    }
    this.loadPresetData(presetName);
    this.syncControlsFromState();
    this.renderTable();
    this.calculate();
  }

  loadPresetData(presetName) {
    const def = this.getDefaultPipeSpec();
    const catalog = this.getStandardPipesList();

    // Helper to find standard pipe of similar standard/material for suction (larger) and riser (smaller)
    const findSizedPipe = (targetNb) => {
      let match = catalog.find(p => p.standard === def.standard && p.schedule_sdr === def.schedule_sdr && p.nb_mm === targetNb);
      if (!match && def.material) {
        match = catalog.find(p => p.material_key === def.material && p.nb_mm === targetNb);
      }
      return match;
    };

    const p150 = findSizedPipe(150);
    const dia150 = p150 ? (p150.id_mm || p150.od_mm - 2 * p150.wall_thickness_mm) : 154.1;
    const p80 = findSizedPipe(80);
    const dia80 = p80 ? (p80.id_mm || p80.od_mm - 2 * p80.wall_thickness_mm) : 77.9;

    if (presetName === 'parallel') {
      this.state.topology = 'parallel';
      this.state.parallel_balancing = 'auto';
      this.state.flow_rate = 160.0;
      this.state.flow_unit = 'm3h';
      this.state.friction_method = window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_friction_method || 'darcy_weisbach';
      this.state.fluid = { type: 'water', temp_c: 20, sg: 1.0, viscosity_cst: 1.004 };

      // Multi-branch system with multiple series pipes per branch and independent discharge heights:
      this.state.parallel_branches = [
        {
          id: 'branch_1',
          label: 'Branch 1 - High Reservoir Delivery',
          discharge_elevation_m: 16.0,   // Independent discharge height
          flow_pct: 55.0,
          pipes: [
            {
              id: 'p_1_1',
              label: `1.1 Manifold Takeoff (${p150 ? (p150.nb_inch || '150mm') : '150mm'} ${def.material.replace('_', ' ')})`,
              catalog_id: p150 ? String(p150.id) : '',
              diameter_mm: +parseFloat(dia150).toFixed(1),
              material: def.material,
              roughness_mm: def.roughness_mm,
              length_m: 12.0,
              elevation_m: 0.0,
              fittings: { 'gate_valve_open': 1, 'elbow_90_standard': 1 },
              custom_k: 0.0
            },
            {
              id: 'p_1_2',
              label: `1.2 Overland Main (${def.pipe ? (def.pipe.nb_inch || def.pipe.nb_mm + 'mm') : def.diameter_mm + 'mm'} Default Pipe)`,
              catalog_id: def.catalog_id,
              diameter_mm: def.diameter_mm,
              material: def.material,
              roughness_mm: def.roughness_mm,
              length_m: 120.0,
              elevation_m: 4.0,
              fittings: { 'swing_check_open': 1, 'elbow_90_standard': 2 },
              custom_k: 0.0
            },
            {
              id: 'p_1_3',
              label: `1.3 Tank Terminal Riser (${p80 ? (p80.nb_inch || '80mm') : '80mm'} ${def.material.replace('_', ' ')})`,
              catalog_id: p80 ? String(p80.id) : '',
              diameter_mm: +parseFloat(dia80).toFixed(1),
              material: def.material,
              roughness_mm: def.roughness_mm,
              length_m: 25.0,
              elevation_m: 12.0,
              fittings: { 'butterfly_valve_open': 1, 'elbow_90_standard': 2 },
              custom_k: 0.0
            }
          ]
        },
        {
          id: 'branch_2',
          label: 'Branch 2 - Low Storage Bypass',
          discharge_elevation_m: 8.0,    // Independent discharge height
          flow_pct: 45.0,
          pipes: [
            {
              id: 'p_2_1',
              label: `2.1 Bypass Takeoff (${def.pipe ? (def.pipe.nb_inch || def.pipe.nb_mm + 'mm') : def.diameter_mm + 'mm'} Default Pipe)`,
              catalog_id: def.catalog_id,
              diameter_mm: def.diameter_mm,
              material: def.material,
              roughness_mm: def.roughness_mm,
              length_m: 15.0,
              elevation_m: 0.0,
              fittings: { 'gate_valve_open': 1, 'elbow_90_standard': 1 },
              custom_k: 0.0
            },
            {
              id: 'p_2_2',
              label: `2.2 Discharge Line (${p80 ? (p80.nb_inch || '80mm') : '80mm'} Branch Line)`,
              catalog_id: p80 ? String(p80.id) : '',
              diameter_mm: +parseFloat(dia80).toFixed(1),
              material: def.material,
              roughness_mm: def.roughness_mm,
              length_m: 95.0,
              elevation_m: 8.0,
              fittings: { 'swing_check_open': 1, 'elbow_90_standard': 3 },
              custom_k: 0.0
            }
          ]
        }
      ];
    } else {
      // Series sample: Suction Line + Discharge Main + Vertical Riser
      this.state.topology = 'series';
      this.state.parallel_balancing = 'auto';
      this.state.flow_rate = 120.0;
      this.state.flow_unit = 'm3h';
      this.state.static_elevation = parseFloat(window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_default_elev_change_m) || 18.0;
      this.state.friction_method = window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_friction_method || 'darcy_weisbach';
      this.state.fluid = { type: 'water', temp_c: 20, sg: 1.0, viscosity_cst: 1.004 };
      this.state.pipes = [
        {
          id: 'pipe_suction',
          label: `1. Suction Line (${p150 ? (p150.nb_inch || '150mm') : '150mm'} ${def.material.replace('_', ' ')})`,
          catalog_id: p150 ? String(p150.id) : '',
          diameter_mm: +parseFloat(dia150).toFixed(1),
          material: def.material,
          roughness_mm: def.roughness_mm,
          length_m: 12.0,
          elevation_m: -1.5,
          fittings: { 'foot_valve_strainer': 1, 'elbow_90_long_radius': 1 },
          custom_k: 0.0,
          flow_pct: 0
        },
        {
          id: 'pipe_discharge',
          label: `2. Discharge Overland Main (${def.pipe ? (def.pipe.nb_inch || def.pipe.nb_mm + 'mm') : def.diameter_mm + 'mm'} Default Pipe)`,
          catalog_id: def.catalog_id,
          diameter_mm: def.diameter_mm,
          material: def.material,
          roughness_mm: def.roughness_mm,
          length_m: parseFloat(window.__PMP_PIPE_NETWORK_DEFAULTS?.pn_default_length_m) || 140.0,
          elevation_m: 4.5,
          fittings: { 'swing_check_open': 1, 'gate_valve_open': 1, 'elbow_90_standard': 3 },
          custom_k: 0.0,
          flow_pct: 0
        },
        {
          id: 'pipe_riser',
          label: `3. Vertical Riser to Storage Tank (${p80 ? (p80.nb_inch || '80mm') : '80mm'} ${def.material.replace('_', ' ')})`,
          catalog_id: p80 ? String(p80.id) : '',
          diameter_mm: +parseFloat(dia80).toFixed(1),
          material: def.material,
          roughness_mm: def.roughness_mm,
          length_m: 35.0,
          elevation_m: 15.0,
          fittings: { 'elbow_90_standard': 2, 'butterfly_valve_open': 1 },
          custom_k: 0.0,
          flow_pct: 0
        }
      ];
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOOKUP & HELPER METHODS
  // ─────────────────────────────────────────────────────────────────────────

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
    return [
      { key: 'commercial_steel', label: 'Commercial Steel (ε=0.046mm)', roughness_mm: 0.046 },
      { key: 'hdpe', label: 'HDPE / PE100 (ε=0.007mm)', roughness_mm: 0.007 },
      { key: 'pvc', label: 'uPVC / PVC-U (ε=0.0015mm)', roughness_mm: 0.0015 },
      { key: 'ductile_iron', label: 'Ductile Iron (ε=0.12mm)', roughness_mm: 0.12 },
      { key: 'copper', label: 'Copper / Brass (ε=0.0015mm)', roughness_mm: 0.0015 },
      { key: 'cast_iron', label: 'Cast Iron (ε=0.26mm)', roughness_mm: 0.26 },
      { key: 'stainless_steel', label: 'Stainless Steel (ε=0.015mm)', roughness_mm: 0.015 }
    ];
  }

  /**
   * Generates a concise summary label for a pipe's catalog item or custom size.
   */
  getPipeSpecBadge(pipe) {
    if (pipe.catalog_id) {
      const catalog = this.getStandardPipesList();
      const item = catalog.find(x => String(x.id) === String(pipe.catalog_id));
      if (item) {
        const std = item.standard || '';
        const sch = item.schedule_sdr ? ` • ${item.schedule_sdr}` : '';
        const nb = item.nb_mm ? `DN${item.nb_mm}` : (item.od_mm ? `OD ${item.od_mm}mm` : '');
        return `${std} ${nb}${sch} (ID ${pipe.diameter_mm}mm)`;
      }
    }
    return `Custom ID ${pipe.diameter_mm}mm`;
  }

  /**
   * Retrieves the active organisation's corporate default standard pipe specification.
   * Resolves catalog pipe item, inside diameter, wall roughness, and Hazen-Williams C.
   */
  getDefaultPipeSpec() {
    const orgDefaults = window.__PMP_PIPE_NETWORK_DEFAULTS || {};
    const catalog = this.getStandardPipesList();

    let pipe = null;
    // 1. Match by explicit catalog ID if saved
    if (orgDefaults.pn_default_pipe_id) {
      pipe = catalog.find(p => String(p.id) === String(orgDefaults.pn_default_pipe_id));
    }
    // 2. Match by standard, schedule, and nominal size (or diameter)
    if (!pipe && orgDefaults.pn_default_standard) {
      pipe = catalog.find(p =>
        p.standard === orgDefaults.pn_default_standard &&
        (!orgDefaults.pn_default_schedule_sdr || p.schedule_sdr === orgDefaults.pn_default_schedule_sdr) &&
        (!orgDefaults.pn_default_nb_mm || String(p.nb_mm) === String(orgDefaults.pn_default_nb_mm))
      );
      if (!pipe) {
        pipe = catalog.find(p => p.standard === orgDefaults.pn_default_standard && (!orgDefaults.pn_default_schedule_sdr || p.schedule_sdr === orgDefaults.pn_default_schedule_sdr));
      }
    }
    // 3. Fallback to material match
    if (!pipe && orgDefaults.pn_default_material) {
      pipe = catalog.find(p => p.material_key === orgDefaults.pn_default_material && (p.nb_mm === 100 || (p.od_mm >= 110 && p.od_mm <= 125)));
    }
    // 4. Default fallback to 100mm carbon steel
    if (!pipe) {
      pipe = catalog.find(p => p.standard && p.standard.includes('B36.10M') && p.nb_mm === 100 && p.schedule_sdr && p.schedule_sdr.includes('40'))
        || catalog.find(p => p.nb_mm === 100)
        || catalog[0];
    }

    const mat = orgDefaults.pn_default_material || (pipe ? pipe.material_key : 'commercial_steel');
    let dia = pipe ? (pipe.id_mm || (pipe.od_mm - 2 * (pipe.wall_thickness_mm || 0))) : (parseFloat(orgDefaults.pn_default_diameter_mm) || 102.3);
    dia = Math.round(dia * 10) / 10;

    let rough = parseFloat(orgDefaults.pn_default_roughness_mm);
    if (!rough || isNaN(rough)) {
      if (mat === 'hdpe') rough = 0.007;
      else if (mat === 'pvc') rough = 0.0015;
      else if (mat === 'stainless_steel') rough = 0.015;
      else if (mat === 'ductile_iron') rough = 0.12;
      else if (mat === 'galvanised_steel') rough = 0.15;
      else rough = 0.046;
    }

    const hw_c = parseFloat(orgDefaults.pn_default_hw_c) || (mat === 'commercial_steel' ? 140 : 150);

    return {
      catalog_id: pipe ? String(pipe.id) : (orgDefaults.pn_default_pipe_id || ''),
      standard: pipe ? pipe.standard : (orgDefaults.pn_default_standard || 'ASME B36.10M'),
      material: mat,
      schedule_sdr: pipe ? pipe.schedule_sdr : (orgDefaults.pn_default_schedule_sdr || 'Sch 40 (STD)'),
      diameter_mm: dia,
      roughness_mm: rough,
      hw_c: hw_c,
      nb_mm: pipe ? pipe.nb_mm : (parseInt(orgDefaults.pn_default_nb_mm) || 100),
      pipe: pipe
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // UI RENDERING: SERIES TABLE & PARALLEL BRANCH CARDS
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Primary render dispatcher: selects between Series table view and Parallel branch cards view.
   */
  renderTable() {
    const isSeries = (this.state.topology === 'series');
    const seriesContainer = document.getElementById('simple-series-container');
    const parallelContainer = document.getElementById('simple-parallel-container');
    const badge = document.getElementById('simple-pipe-count-badge');
    const title = document.getElementById('simple-spec-title');
    const btnAddPipe = document.getElementById('btn-simple-add-pipe');

    if (isSeries) {
      if (seriesContainer) seriesContainer.style.display = 'block';
      if (parallelContainer) parallelContainer.style.display = 'none';
      if (title) title.textContent = '3. Pipeline Segments Specification (Series Chain)';
      if (btnAddPipe) {
        btnAddPipe.innerHTML = '<i class="bi bi-plus-lg"></i> Add Pipeline Segment';
        btnAddPipe.setAttribute('onclick', 'simpleController.addPipe()');
      }
      if (badge) {
        const n = this.state.pipes.length;
        badge.textContent = `${n} Segment${n === 1 ? '' : 's'}`;
      }
      this.renderSeriesTable();
    } else {
      if (seriesContainer) seriesContainer.style.display = 'none';
      if (parallelContainer) parallelContainer.style.display = 'block';
      if (title) title.textContent = '3. Parallel Pipelines Specification (Multi-Branch System)';
      if (btnAddPipe) {
        btnAddPipe.innerHTML = '<i class="bi bi-plus-lg"></i> Add Parallel Pipeline';
        btnAddPipe.setAttribute('onclick', 'simpleController.addParallelBranch()');
      }
      if (badge) {
        const n = this.state.parallel_branches.length;
        badge.textContent = `${n} Parallel Pipeline${n === 1 ? '' : 's'}`;
      }
      this.renderParallelBranches();
    }
  }

  /**
   * Renders the Series pipeline table.
   */
  renderSeriesTable() {
    const tbody = document.getElementById('simple-pipes-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const materials = this.getMaterialsList();

    this.state.pipes.forEach((p, idx) => {
      const tr = document.createElement('tr');
      tr.style.cssText = 'border-bottom:1px solid #21262d;';

      // 1. Index
      const tdIdx = document.createElement('td');
      tdIdx.style.cssText = 'text-align:center;font-weight:700;color:#64748b;';
      tdIdx.textContent = idx + 1;
      tr.appendChild(tdIdx);

      // 2. Tag / Label
      const tdLabel = document.createElement('td');
      tdLabel.innerHTML = `<input type="text" class="pn-input-cell" value="${p.label.replace(/"/g, '&quot;')}" onchange="simpleController.updatePipeProp(${idx}, 'label', this.value)" placeholder="Segment name" style="font-weight:600;">`;
      tr.appendChild(tdLabel);

      // 3. Pipe Specification & Catalog Modal Button
      const tdCat = document.createElement('td');
      const badgeText = this.getPipeSpecBadge(p);
      tdCat.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
          <span style="font-size:11.5px;color:#38bdf8;font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;" title="${badgeText}">
            ${badgeText}
          </span>
          <button type="button" class="pn-btn" onclick="simpleController.openPipeConfigModal(${idx})" style="font-size:11px;padding:3px 8px;border-color:rgba(56,189,248,0.4);color:#38bdf8;white-space:nowrap;" title="Configure standard pipe catalog, SDR, and dimensions">
            <i class="bi bi-gear-fill"></i> Configure
          </button>
        </div>
      `;
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

      // 8. Fittings Button
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

      // 9. Actions
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
   * Renders the Compound Parallel Pipeline branches:
   * Each branch is displayed as an individual pipeline card with its own discharge elevation,
   * manual flow share % (if enabled), and an embedded table of up to 5 series sub-pipes.
   */
  renderParallelBranches() {
    const container = document.getElementById('simple-parallel-branches-list');
    if (!container) return;
    container.innerHTML = '';

    const isManual = (this.state.parallel_balancing === 'manual');
    const materials = this.getMaterialsList();

    this.state.parallel_branches.forEach((b, bIdx) => {
      const card = document.createElement('div');
      card.className = 'pn-branch-card';
      card.style.cssText = 'background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;margin-bottom:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3);';

      const numPipes = b.pipes.length;
      const isMaxPipes = (numPipes >= 5);

      // 1. Branch Header Bar
      const header = document.createElement('div');
      header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #21262d;padding-bottom:10px;margin-bottom:12px;flex-wrap:wrap;gap:10px;';
      
      header.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:240px;">
          <div style="width:26px;height:26px;border-radius:6px;background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.3);display:flex;align-items:center;justify-content:center;color:#22c55e;font-weight:800;font-size:12px;">
            ${bIdx + 1}
          </div>
          <input type="text" class="pn-input-cell" value="${b.label.replace(/"/g, '&quot;')}" onchange="simpleController.updateBranchProp(${bIdx}, 'label', this.value)" style="font-size:13px;font-weight:700;color:#f0f6fc;flex:1;max-width:320px;" placeholder="Branch Name">
          <span style="font-size:11px;background:#21262d;color:#94a3b8;padding:2px 8px;border-radius:10px;font-weight:600;">
            ${numPipes} of max 5 pipes in series
          </span>
        </div>

        <!-- Branch Discharge Height & Flow Share Controls -->
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          
          <!-- Individual Discharge Height -->
          <div style="display:flex;align-items:center;gap:6px;background:#0d1117;border:1px solid rgba(192,132,252,0.4);border-radius:6px;padding:4px 8px;">
            <label style="font-size:11px;color:#c084fc;font-weight:600;margin:0;white-space:nowrap;">
              <i class="bi bi-arrow-up-right-square"></i> Discharge Height (&Delta;z<sub>out</sub>):
            </label>
            <input type="number" step="0.1" class="pn-input-cell" value="${b.discharge_elevation_m !== undefined ? b.discharge_elevation_m : 10.0}" onchange="simpleController.updateBranchProp(${bIdx}, 'discharge_elevation_m', parseFloat(this.value))" style="width:65px;text-align:right;font-weight:700;color:#c084fc;font-family:monospace;padding:2px 4px;">
            <span style="font-size:11px;color:#94a3b8;">m</span>
          </div>

          <!-- Flow Share % (If Manual Allocation) -->
          ${isManual ? `
            <div style="display:flex;align-items:center;gap:6px;background:#0d1117;border:1px solid rgba(34,197,94,0.4);border-radius:6px;padding:4px 8px;">
              <label style="font-size:11px;color:#22c55e;font-weight:600;margin:0;white-space:nowrap;">
                Flow Share:
              </label>
              <input type="number" step="1" min="0" max="100" class="pn-input-cell" value="${b.flow_pct || 0}" onchange="simpleController.updateBranchProp(${bIdx}, 'flow_pct', parseFloat(this.value))" style="width:55px;text-align:right;font-weight:700;color:#22c55e;font-family:monospace;padding:2px 4px;">
              <span style="font-size:11px;color:#94a3b8;">%</span>
            </div>
          ` : ''}

          <!-- Branch actions -->
          <div style="display:flex;align-items:center;gap:6px;">
            <button type="button" class="pn-btn ${isMaxPipes ? 'disabled' : 'pn-btn-success'}" onclick="simpleController.addSubPipeToBranch(${bIdx})" ${isMaxPipes ? 'disabled' : ''} style="font-size:11px;padding:4px 10px;" title="${isMaxPipes ? 'Maximum of 5 series pipes reached' : 'Add series pipe to this parallel branch'}">
              <i class="bi bi-plus-lg"></i> Add Series Pipe ${isMaxPipes ? '(Max 5)' : ''}
            </button>
            <button type="button" class="pn-btn" onclick="simpleController.duplicateParallelBranch(${bIdx})" style="padding:4px 8px;font-size:11px;" title="Duplicate branch">
              <i class="bi bi-copy"></i>
            </button>
            <button type="button" class="pn-btn" onclick="simpleController.removeParallelBranch(${bIdx})" style="padding:4px 8px;font-size:11px;color:#ef4444;" title="Delete branch">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </div>
      `;
      card.appendChild(header);

      // 2. Sub-pipes Series Table
      const tableWrap = document.createElement('div');
      tableWrap.style.cssText = 'overflow-x:auto;border:1px solid #21262d;border-radius:6px;background:#0d1117;';

      const table = document.createElement('table');
      table.className = 'pn-simple-table';
      table.innerHTML = `
        <thead>
          <tr style="background:#161b22;">
            <th style="width:36px;text-align:center;">#</th>
            <th style="min-width:140px;">Sub-Pipe Tag / Label</th>
            <th style="min-width:240px;">Standard Pipe &amp; SDR</th>
            <th style="width:105px;">Inner Dia (mm)</th>
            <th style="min-width:160px;">Material &amp; Roughness</th>
            <th style="width:95px;">Length (m)</th>
            <th style="width:95px;">Elev &Delta;z (m)</th>
            <th style="min-width:150px;">Valves &amp; Fittings</th>
            <th style="width:50px;text-align:center;">Delete</th>
          </tr>
        </thead>
        <tbody></tbody>
      `;

      const tbody = table.querySelector('tbody');

      b.pipes.forEach((p, pIdx) => {
        const tr = document.createElement('tr');
        tr.style.cssText = 'border-bottom:1px solid #21262d;';

        // 1. Index
        const tdIdx = document.createElement('td');
        tdIdx.style.cssText = 'text-align:center;font-weight:700;color:#64748b;';
        tdIdx.textContent = `${bIdx + 1}.${pIdx + 1}`;
        tr.appendChild(tdIdx);

        // 2. Sub-Pipe Label
        const tdLabel = document.createElement('td');
        tdLabel.innerHTML = `<input type="text" class="pn-input-cell" value="${p.label.replace(/"/g, '&quot;')}" onchange="simpleController.updateSubPipeProp(${bIdx}, ${pIdx}, 'label', this.value)" placeholder="Sub-pipe label" style="font-weight:600;">`;
        tr.appendChild(tdLabel);

        // 3. Pipe Specification & Catalog Modal Button
        const tdCat = document.createElement('td');
        const badgeText = this.getPipeSpecBadge(p);
        tdCat.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
            <span style="font-size:11.5px;color:#38bdf8;font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;" title="${badgeText}">
              ${badgeText}
            </span>
            <button type="button" class="pn-btn" onclick="simpleController.openPipeConfigModal(${pIdx}, ${bIdx})" style="font-size:11px;padding:2px 7px;border-color:rgba(56,189,248,0.4);color:#38bdf8;white-space:nowrap;" title="Configure standard pipe catalog, SDR, and dimensions">
              <i class="bi bi-gear-fill"></i> Configure
            </button>
          </div>
        `;
        tr.appendChild(tdCat);

        // 4. Inner Diameter (mm)
        const tdDiam = document.createElement('td');
        tdDiam.innerHTML = `<input type="number" step="0.1" min="1" class="pn-input-cell" value="${p.diameter_mm}" onchange="simpleController.updateSubPipeProp(${bIdx}, ${pIdx}, 'diameter_mm', parseFloat(this.value))" style="text-align:right;font-family:monospace;font-weight:600;color:#38bdf8;">`;
        tr.appendChild(tdDiam);

        // 5. Material Dropdown
        const tdMat = document.createElement('td');
        const matSelect = document.createElement('select');
        matSelect.className = 'pn-input-cell';
        matSelect.style.cssText = 'width:140px;font-size:11px;';
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
          this.updateSubPipeProp(bIdx, pIdx, 'material', selectedKey);
          this.updateSubPipeProp(bIdx, pIdx, 'roughness_mm', rough);
        });
        tdMat.appendChild(matSelect);
        tr.appendChild(tdMat);

        // 6. Length (m)
        const tdLen = document.createElement('td');
        tdLen.innerHTML = `<input type="number" step="0.1" min="0.1" class="pn-input-cell" value="${p.length_m}" onchange="simpleController.updateSubPipeProp(${bIdx}, ${pIdx}, 'length_m', parseFloat(this.value))" style="text-align:right;font-family:monospace;">`;
        tr.appendChild(tdLen);

        // 7. Elevation Lift (m)
        const tdElev = document.createElement('td');
        tdElev.innerHTML = `<input type="number" step="0.1" class="pn-input-cell" value="${p.elevation_m}" onchange="simpleController.updateSubPipeProp(${bIdx}, ${pIdx}, 'elevation_m', parseFloat(this.value))" style="text-align:right;font-family:monospace;color:#c084fc;">`;
        tr.appendChild(tdElev);

        // 8. Fittings Button
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
          <button type="button" class="pn-btn" onclick="simpleController.openFittingsModal(${pIdx}, ${bIdx})" style="width:100%;font-size:11px;padding:3px 6px;display:flex;align-items:center;justify-content:space-between;border-color:rgba(251,191,36,0.3);color:${fitBtnColor};">
            <span><i class="bi bi-tools" style="margin-right:4px;"></i>${fitLabel}</span>
            <i class="bi bi-pencil" style="font-size:9px;opacity:0.7;"></i>
          </button>
        `;
        tr.appendChild(tdFit);

        // 9. Actions
        const tdAct = document.createElement('td');
        tdAct.style.cssText = 'text-align:center;';
        tdAct.innerHTML = `
          <button type="button" class="pn-btn" onclick="simpleController.removeSubPipeFromBranch(${bIdx}, ${pIdx})" style="padding:2px 6px;font-size:11px;color:#ef4444;" title="Delete sub-pipe">
            <i class="bi bi-trash"></i>
          </button>
        `;
        tr.appendChild(tdAct);

        tbody.appendChild(tr);
      });

      tableWrap.appendChild(table);
      card.appendChild(tableWrap);
      container.appendChild(card);
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PIPE CONFIGURATION & STANDARD PIPE CATALOG / SDR FILTER MODAL
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Opens the Pipe Configuration & SDR Filter modal for a target pipe:
   * @param {number} pipeIdx - Index of pipe segment.
   * @param {number|null} branchIdx - Branch index if in parallel mode, or null for series.
   */
  openPipeConfigModal(pipeIdx, branchIdx = null) {
    this.pipeConfigTarget = {
      type: (branchIdx !== null) ? 'parallel' : 'series',
      branchIdx: branchIdx,
      pipeIdx: pipeIdx
    };

    const pipe = (branchIdx !== null)
      ? this.state.parallel_branches[branchIdx].pipes[pipeIdx]
      : this.state.pipes[pipeIdx];

    if (!pipe) return;

    const modal = document.getElementById('pn-simple-pipe-modal');
    const titleSpan = document.getElementById('modal-pipe-cfg-title');
    if (titleSpan) titleSpan.textContent = pipe.label;

    // Prefill direct inputs
    const labelIn = document.getElementById('modal-cfg-pipe-label');
    if (labelIn) labelIn.value = pipe.label;
    const diaIn = document.getElementById('modal-cfg-pipe-diameter');
    if (diaIn) diaIn.value = pipe.diameter_mm;
    const lenIn = document.getElementById('modal-cfg-pipe-length');
    if (lenIn) lenIn.value = pipe.length_m;
    const elevIn = document.getElementById('modal-cfg-pipe-elevation');
    if (elevIn) elevIn.value = pipe.elevation_m;

    // Populate materials dropdown
    const matSel = document.getElementById('modal-cfg-pipe-material');
    if (matSel) {
      matSel.innerHTML = '';
      this.getMaterialsList().forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.key;
        opt.textContent = m.label;
        if (m.key === pipe.material) opt.selected = true;
        matSel.appendChild(opt);
      });
    }

    // Determine initial standard filter values based on pipe's current catalog_id
    const catalog = this.getStandardPipesList();
    const currentItem = catalog.find(x => String(x.id) === String(pipe.catalog_id));

    this.pipeConfigSelectedStd = currentItem ? currentItem.standard : 'all';
    this.pipeConfigSelectedMat = currentItem ? (currentItem.material || 'all') : 'all';
    this.pipeConfigSelectedSch = currentItem ? (currentItem.schedule_sdr || 'all') : 'all';
    this.pipeConfigSelectedId = currentItem ? String(currentItem.id) : '';

    this.populateModalFilters();
    this.updateModalPipePreview(currentItem);

    if (modal) {
      if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
      }
      modal.style.display = 'flex';
    }
  }

  closePipeConfigModal() {
    const modal = document.getElementById('pn-simple-pipe-modal');
    if (modal) modal.style.display = 'none';
    this.pipeConfigTarget = null;
  }

  /**
   * Populates cascading Standard, Material, Schedule/SDR, and Size dropdowns.
   */
  populateModalFilters() {
    const catalog = this.getStandardPipesList();

    // 1. Populate Standards Dropdown
    const stdSel = document.getElementById('modal-cfg-filter-standard');
    if (stdSel) {
      const standards = Array.from(new Set(catalog.map(p => p.standard).filter(Boolean))).sort();
      stdSel.innerHTML = '<option value="all">— All Pipe Standards —</option>';
      standards.forEach(std => {
        const opt = document.createElement('option');
        opt.value = std;
        opt.textContent = std;
        if (std === this.pipeConfigSelectedStd) opt.selected = true;
        stdSel.appendChild(opt);
      });
    }

    // 2. Populate Materials Dropdown (filtered by selected standard)
    const matSel = document.getElementById('modal-cfg-filter-material');
    if (matSel) {
      const filteredByStd = (this.pipeConfigSelectedStd === 'all')
        ? catalog
        : catalog.filter(p => p.standard === this.pipeConfigSelectedStd);
      const materials = Array.from(new Set(filteredByStd.map(p => p.material).filter(Boolean))).sort();
      matSel.innerHTML = '<option value="all">— All Materials —</option>';
      materials.forEach(mat => {
        const opt = document.createElement('option');
        opt.value = mat;
        opt.textContent = mat;
        if (mat === this.pipeConfigSelectedMat) opt.selected = true;
        matSel.appendChild(opt);
      });
    }

    // 3. Populate Schedule / SDR Dropdown (filtered by standard and material)
    const schSel = document.getElementById('modal-cfg-filter-schedule');
    if (schSel) {
      const filtered = catalog.filter(p => {
        const matchStd = (this.pipeConfigSelectedStd === 'all' || p.standard === this.pipeConfigSelectedStd);
        const matchMat = (this.pipeConfigSelectedMat === 'all' || p.material === this.pipeConfigSelectedMat);
        return matchStd && matchMat;
      });
      const schedules = Array.from(new Set(filtered.map(p => p.schedule_sdr).filter(Boolean))).sort();
      schSel.innerHTML = '<option value="all">— All Schedules / SDRs —</option>';
      schedules.forEach(sch => {
        const opt = document.createElement('option');
        opt.value = sch;
        opt.textContent = sch;
        if (sch === this.pipeConfigSelectedSch) opt.selected = true;
        schSel.appendChild(opt);
      });
    }

    // 4. Populate Pipe Item Selector Dropdown
    this.populateModalPipesList();
  }

  populateModalPipesList() {
    const catalog = this.getStandardPipesList();
    const pipeSel = document.getElementById('modal-cfg-filter-pipe');
    if (!pipeSel) return;

    const filtered = catalog.filter(p => {
      const matchStd = (this.pipeConfigSelectedStd === 'all' || p.standard === this.pipeConfigSelectedStd);
      const matchMat = (this.pipeConfigSelectedMat === 'all' || p.material === this.pipeConfigSelectedMat);
      const matchSch = (this.pipeConfigSelectedSch === 'all' || p.schedule_sdr === this.pipeConfigSelectedSch);
      return matchStd && matchMat && matchSch;
    }).sort((a, b) => (a.od_mm || a.nb_mm || 0) - (b.od_mm || b.nb_mm || 0));

    pipeSel.innerHTML = '';
    const optNone = document.createElement('option');
    optNone.value = '';
    optNone.textContent = `— Select Standard Pipe Size (${filtered.length} available) —`;
    pipeSel.appendChild(optNone);

    filtered.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.id;
      opt.textContent = this.formatCatalogOptionText(item);
      if (String(item.id) === String(this.pipeConfigSelectedId)) {
        opt.selected = true;
      }
      pipeSel.appendChild(opt);
    });
  }

  onModalStandardChange(stdVal) {
    this.pipeConfigSelectedStd = stdVal;
    this.pipeConfigSelectedMat = 'all';
    this.pipeConfigSelectedSch = 'all';
    this.pipeConfigSelectedId = '';
    this.populateModalFilters();
    this.updateModalPipePreview(null);
  }

  onModalMaterialChange(matVal) {
    this.pipeConfigSelectedMat = matVal;
    this.pipeConfigSelectedSch = 'all';
    this.pipeConfigSelectedId = '';
    this.populateModalFilters();
    this.updateModalPipePreview(null);
  }

  onModalScheduleChange(schVal) {
    this.pipeConfigSelectedSch = schVal;
    this.pipeConfigSelectedId = '';
    this.populateModalPipesList();
    this.updateModalPipePreview(null);
  }

  onModalPipeSelect(pipeId) {
    this.pipeConfigSelectedId = pipeId;
    const catalog = this.getStandardPipesList();
    const item = catalog.find(x => String(x.id) === String(pipeId));
    this.updateModalPipePreview(item);

    if (item) {
      // Automatically prefill the Inner Diameter input and Material
      const diaIn = document.getElementById('modal-cfg-pipe-diameter');
      let innerDia = item.id_mm || item.inner_dia_mm;
      if (!innerDia && item.od_mm && item.wall_thickness_mm) {
        innerDia = item.od_mm - 2 * item.wall_thickness_mm;
      }
      if (diaIn && innerDia) {
        diaIn.value = (+parseFloat(innerDia).toFixed(1));
      }

      const matSel = document.getElementById('modal-cfg-pipe-material');
      if (matSel) {
        const mKey = (item.material_key || item.material || '').toLowerCase();
        if (mKey.includes('steel')) matSel.value = 'commercial_steel';
        else if (mKey.includes('pvc')) matSel.value = 'pvc';
        else if (mKey.includes('hdpe')) matSel.value = 'hdpe';
        else if (mKey.includes('iron')) matSel.value = 'ductile_iron';
        else if (mKey.includes('copper')) matSel.value = 'copper';
      }
    }
  }

  updateModalPipePreview(item) {
    const card = document.getElementById('modal-pipe-preview-card');
    if (!card) return;

    if (!item) {
      card.innerHTML = `
        <div style="font-size:11px;color:#64748b;text-align:center;padding:8px 0;">
          Select a standard pipe above to view detailed dimensions (OD, Wall Thickness, ID, Working Pressure).
        </div>
      `;
      return;
    }

    let innerDia = item.id_mm || item.inner_dia_mm;
    if (!innerDia && item.od_mm && item.wall_thickness_mm) {
      innerDia = item.od_mm - 2 * item.wall_thickness_mm;
    }

    card.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:8px;">
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;">
          <div style="font-size:10px;color:#94a3b8;font-weight:700;">OUTSIDE DIAMETER (OD)</div>
          <div style="font-size:14px;font-weight:800;color:#38bdf8;font-family:monospace;margin-top:2px;">
            ${item.od_mm ? item.od_mm + ' mm' : '—'}
          </div>
        </div>
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;">
          <div style="font-size:10px;color:#94a3b8;font-weight:700;">WALL THICKNESS (t)</div>
          <div style="font-size:14px;font-weight:800;color:#facc15;font-family:monospace;margin-top:2px;">
            ${item.wall_thickness_mm ? item.wall_thickness_mm + ' mm' : '—'}
          </div>
        </div>
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;">
          <div style="font-size:10px;color:#94a3b8;font-weight:700;">INSIDE DIAMETER (ID)</div>
          <div style="font-size:14px;font-weight:800;color:#22c55e;font-family:monospace;margin-top:2px;">
            ${innerDia ? (+parseFloat(innerDia).toFixed(1)) + ' mm' : '—'}
          </div>
        </div>
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;">
          <div style="font-size:10px;color:#94a3b8;font-weight:700;">PRESSURE CLASS / RATING</div>
          <div style="font-size:12px;font-weight:700;color:#e6edf3;margin-top:4px;">
            ${item.pressure_rating || item.schedule_sdr || 'Standard'}
          </div>
        </div>
      </div>
      <div style="margin-top:6px;font-size:11px;color:#8b949e;display:flex;justify-content:space-between;">
        <span><strong style="color:#c9d1d9;">Standard:</strong> ${item.standard || '—'}</span>
        <span><strong style="color:#c9d1d9;">Material:</strong> ${item.material || '—'}</span>
        <span><strong style="color:#c9d1d9;">Schedule / SDR:</strong> ${item.schedule_sdr || '—'}</span>
      </div>
    `;
  }

  applyModalPipeConfig() {
    if (!this.pipeConfigTarget) return;

    const targetPipe = (this.pipeConfigTarget.type === 'parallel')
      ? this.state.parallel_branches[this.pipeConfigTarget.branchIdx].pipes[this.pipeConfigTarget.pipeIdx]
      : this.state.pipes[this.pipeConfigTarget.pipeIdx];

    if (!targetPipe) return;

    const labelIn = document.getElementById('modal-cfg-pipe-label');
    if (labelIn && labelIn.value.trim()) targetPipe.label = labelIn.value.trim();

    const diaIn = document.getElementById('modal-cfg-pipe-diameter');
    if (diaIn && parseFloat(diaIn.value) > 0) targetPipe.diameter_mm = parseFloat(diaIn.value);

    const matSel = document.getElementById('modal-cfg-pipe-material');
    if (matSel) {
      targetPipe.material = matSel.value;
      const materials = this.getMaterialsList();
      const matObj = materials.find(m => m.key === targetPipe.material);
      if (matObj && matObj.roughness_mm) {
        targetPipe.roughness_mm = matObj.roughness_mm;
      }
    }

    const lenIn = document.getElementById('modal-cfg-pipe-length');
    if (lenIn && parseFloat(lenIn.value) > 0) targetPipe.length_m = parseFloat(lenIn.value);

    const elevIn = document.getElementById('modal-cfg-pipe-elevation');
    if (elevIn) targetPipe.elevation_m = parseFloat(elevIn.value) || 0.0;

    targetPipe.catalog_id = this.pipeConfigSelectedId || '';

    this.closePipeConfigModal();
    this.renderTable();
    this.calculate();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // VALVES & FITTINGS MODAL (SUPPORTS BOTH SERIES AND PARALLEL SUB-PIPES)
  // ─────────────────────────────────────────────────────────────────────────

  openFittingsModal(pipeIdx, branchIdx = null) {
    this.modalActiveTarget = {
      type: (branchIdx !== null) ? 'parallel' : 'series',
      branchIdx: branchIdx,
      pipeIdx: pipeIdx
    };

    const pipe = (branchIdx !== null)
      ? this.state.parallel_branches[branchIdx].pipes[pipeIdx]
      : this.state.pipes[pipeIdx];

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

    if (modal) {
      if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
      }
      modal.style.display = 'flex';
    }
  }

  renderModalFittingsList() {
    const container = document.getElementById('modal-fittings-list');
    if (!container) return;
    container.innerHTML = '';

    const fittings = window.__PMP_FITTINGS || (typeof FITTINGS !== 'undefined' ? FITTINGS : []);
    
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
    if (this.modalActiveTarget) {
      const pipe = (this.modalActiveTarget.type === 'parallel')
        ? this.state.parallel_branches[this.modalActiveTarget.branchIdx].pipes[this.modalActiveTarget.pipeIdx]
        : this.state.pipes[this.modalActiveTarget.pipeIdx];

      if (pipe) {
        pipe.fittings = Object.assign({}, this.modalFittingsCopy);
        pipe.custom_k = this.modalCustomK;
      }
    }

    const modal = document.getElementById('pn-simple-fittings-modal');
    if (modal) modal.style.display = 'none';

    this.modalActiveTarget = null;
    this.renderTable();
    this.calculate();
  }

  formatCatalogOptionText(item) {
    if (!item) return '';
    let innerDia = item.id_mm || item.inner_dia_mm;
    if (!innerDia && item.od_mm && item.wall_thickness_mm) {
      innerDia = item.od_mm - 2 * item.wall_thickness_mm;
    }
    const innerDiaFormatted = (typeof innerDia === 'number' && !isNaN(innerDia))
      ? innerDia.toFixed(1)
      : (innerDia || '—');

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

  // ─────────────────────────────────────────────────────────────────────────
  // HYDRAULIC CALCULATION & RESULTS RENDERING
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Packages network configuration and dispatches calculation to `/api/pipe-network/simple-calculate`.
   * @param {boolean} applyToSelection - If true, syncs calculated Duty Point into active pump selection.
   */
  async calculate(applyToSelection = false) {
    if (this.isCalculating && !applyToSelection) return;
    this.isCalculating = true;

    // Explicitly keep the visual canvas diagram results section hidden in simple mode
    const canvasResultsSec = document.getElementById('pn-results-section');
    if (canvasResultsSec) canvasResultsSec.style.display = 'none';

    const payload = {
      topology: this.state.topology,
      parallel_balancing: this.state.parallel_balancing,
      solver_method: this.state.solver_method || 'ggm',
      flow_rate: this.state.flow_rate,
      flow_unit: this.state.flow_unit,
      static_elevation_m: this.state.static_elevation,
      friction_method: this.state.friction_method,
      fluid: this.state.fluid
    };

    if (this.state.topology === 'parallel') {
      payload.parallel_branches = this.state.parallel_branches.map(b => ({
        id: b.id,
        label: b.label,
        discharge_elevation_m: b.discharge_elevation_m,
        flow_pct: b.flow_pct,
        pipes: b.pipes.map(p => ({
          id: p.id,
          label: p.label,
          catalog_id: p.catalog_id,
          diameter_mm: p.diameter_mm,
          material: p.material,
          roughness_mm: p.roughness_mm,
          length_m: p.length_m,
          elevation_m: p.elevation_m,
          fittings: p.fittings,
          custom_k: p.custom_k
        }))
      }));
      // ALSO provide flattened pipes so backend validators always receive pipe segments
      payload.pipes = this.state.parallel_branches.flatMap(b => b.pipes.map(p => ({
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
        branch_id: b.id,
        branch_label: b.label
      })));
    } else {
      payload.pipes = this.state.pipes.map(p => ({
        id: p.id,
        label: p.label,
        catalog_id: p.catalog_id,
        diameter_mm: p.diameter_mm,
        material: p.material,
        roughness_mm: p.roughness_mm,
        length_m: p.length_m,
        elevation_m: p.elevation_m,
        fittings: p.fittings,
        custom_k: p.custom_k
      }));
    }

    try {
      const url = `/api/pipe-network/simple-calculate${applyToSelection ? '?apply_to_selection=true' : ''}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Server responded with status ${res.status}`);
      }

      const data = await res.json();
      this.renderResults(data);

      if (applyToSelection && data.applied_to_selection) {
        // Direct synchronization into Pump Selection duty point form
        if (typeof window.applyDutyPointToPumpSelection === 'function' && document.getElementById('input_q_duty')) {
          const npshVal = (data.npsha_m !== undefined && data.npsha_m !== null)
            ? data.npsha_m
            : (data.summary?.npsha_m !== undefined ? data.summary.npsha_m : null);

          window.applyDutyPointToPumpSelection({
            flow_m3h: data.flow_m3h,
            flow_user_unit: data.flow_user_unit,
            head_m: data.total_system_head_m,
            total_system_head_user_unit: data.total_system_head_user_unit,
            static_head_m: data.static_elevation_m !== undefined ? data.static_elevation_m : this.state.static_elevation,
            npsha_m: npshVal,
            temperature_c: this.state.fluid?.temp_c,
            liquid: this.state.fluid?.type || 'water',
            fluid_type: this.state.fluid?.type || 'water',
            specific_gravity: this.state.fluid?.sg || 1.0,
            viscosity_cSt: this.state.fluid?.viscosity_cst || 1.0,
          });
          return;
        }

        // Fallback for standalone /pipe-network page: notify and offer navigation
        const unitQ = data.unit_q || 'm³/h';
        const unitH = data.unit_h || 'm';
        if (confirm(`✅ Duty Point successfully saved to session!\n\nFlow Rate: ${data.flow_user_unit} ${unitQ}\nTotal Head (TDH): ${data.total_system_head_user_unit} ${unitH}\n\nNavigate to Pump Selection now to view matching pumps?`)) {
          window.location.href = '/pump-selection';
        }
      }
    } catch (err) {
      console.warn('Backend calculation error, utilizing client-side fallback:', err);
      this.calculateClientSideFallback();
      if (applyToSelection && typeof window.applyDutyPointToPumpSelection === 'function' && document.getElementById('input_q_duty')) {
        window.applyDutyPointToPumpSelection({
          flow_m3h: this.state.flow_rate,
          head_m: this.state.lastCalculatedHead || 0.0,
          static_head_m: this.state.static_elevation,
          npsha_m: (this.state.lastNpsha_m !== undefined && this.state.lastNpsha_m !== null) ? this.state.lastNpsha_m : null,
          temperature_c: this.state.fluid?.temp_c,
          liquid: this.state.fluid?.type || 'water',
          fluid_type: this.state.fluid?.type || 'water',
          specific_gravity: this.state.fluid?.sg || 1.0,
          viscosity_cSt: this.state.fluid?.viscosity_cst || 1.0,
        });
      }
    } finally {
      this.isCalculating = false;
    }
  }

  /**
   * Renders KPI cards and granular hydraulic breakdown results.
   */
  renderResults(data) {
    // Save last calculated head and NPSHa for client-side state
    if (data && data.total_system_head_m !== undefined) {
      this.state.lastCalculatedHead = data.total_system_head_m;
    }
    const npshM = (data.npsha_m !== undefined && data.npsha_m !== null)
      ? data.npsha_m
      : (data.summary?.npsha_m !== undefined ? data.summary.npsha_m : null);
    if (npshM !== null) {
      this.state.lastNpsha_m = npshM;
    }

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
    const npshaEl = document.getElementById('simple-res-npsha');
    const npshaSubEl = document.getElementById('simple-res-npsha-sub');

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
    if (npshaEl) {
      if (npshM !== null && !isNaN(npshM)) {
        npshaEl.textContent = `${Number(npshM).toFixed(2)} m`;
        const npshFt = data.npsha_ft !== undefined
          ? data.npsha_ft
          : (data.summary?.npsha_ft !== undefined ? data.summary.npsha_ft : (npshM * 3.28084).toFixed(2));
        if (npshaSubEl) npshaSubEl.textContent = `${npshFt} ft`;
      } else {
        npshaEl.textContent = '— m';
        if (npshaSubEl) npshaSubEl.textContent = '— ft';
      }
    }

    // 2. Render Branch Summary Cards (if parallel mode)
    const branchSummarySec = document.getElementById('simple-branch-summary-section');
    if (branchSummarySec) {
      if (data.topology === 'parallel' && Array.isArray(data.branch_summaries) && data.branch_summaries.length > 0) {
        branchSummarySec.style.display = 'block';
        const bCardsWrap = document.getElementById('simple-branch-summary-cards');
        if (bCardsWrap) {
          bCardsWrap.innerHTML = '';
          data.branch_summaries.forEach((b, idx) => {
            const bCard = document.createElement('div');
            bCard.style.cssText = 'background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 12px;flex:1;min-width:200px;';
            bCard.innerHTML = `
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-size:12px;font-weight:700;color:#f0f6fc;">${b.label}</span>
                <span style="font-size:11px;font-weight:700;color:#22c55e;">${b.flow_share_pct}% Flow</span>
              </div>
              <div style="font-size:13px;font-weight:800;color:#38bdf8;font-family:monospace;">
                ${b.flow_m3h} m³/h <span style="font-size:10px;color:#94a3b8;font-weight:normal;">(${(b.flow_m3h / 3.6).toFixed(2)} L/s)</span>
              </div>
              <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:10.5px;color:#8b949e;">
                <span>Discharge Height: <strong style="color:#c084fc;">${b.discharge_elevation_m}m</strong></span>
                <span>Branch Head: <strong style="color:#fbbf24;">${b.total_branch_head_m}m</strong></span>
              </div>
            `;
            bCardsWrap.appendChild(bCard);
          });
        }
      } else {
        branchSummarySec.style.display = 'none';
      }
    }

    // 3. Per-pipe breakdown table
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
        velHint = 'Excessive velocity (>3.5 m/s) - high erosion and pipe wear';
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
        <td style="font-weight:600;color:#e6edf3;">
          ${p.branch_label ? `<span style="font-size:10px;color:#22c55e;display:block;">${p.branch_label}</span>` : ''}
          ${p.label || p.id}
        </td>
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
   * Client-side fallback calculation in case network backend is temporarily unavailable.
   */
  calculateClientSideFallback() {
    const g = 9.80665;
    const q_m3h = this.state.flow_rate;
    const nu = (this.state.fluid.viscosity_cst || 1.004) * 1e-6;
    const rho = (this.state.fluid.sg || 1.0) * 1000.0;

    let totalMajor = 0.0;
    let totalMinor = 0.0;
    const pipesRes = [];
    const branchSummaries = [];
    let tdh = 0.0;

    if (this.state.topology === 'parallel') {
      const branches = this.state.parallel_branches;
      const numBranches = Math.max(1, branches.length);
      const isManual = (this.state.parallel_balancing === 'manual');

      // Calculate branch flow shares
      const branchFlows = [];
      if (isManual) {
        const sumPct = branches.reduce((acc, b) => acc + (parseFloat(b.flow_pct) || 0), 0);
        const norm = sumPct > 0 ? (100.0 / sumPct) : (1.0 / numBranches);
        branches.forEach(b => {
          const pct = (parseFloat(b.flow_pct) || 0) * (sumPct > 0 ? norm : (100.0 / numBranches));
          branchFlows.push((pct / 100.0) * q_m3h);
        });
      } else {
        // Equal flow split fallback
        branches.forEach(() => branchFlows.push(q_m3h / numBranches));
      }

      let maxBranchHead = 0.0;

      branches.forEach((b, bIdx) => {
        const q_b_m3h = branchFlows[bIdx];
        const q_b_m3s = q_b_m3h / 3600.0;
        let bMajor = 0.0;
        let bMinor = 0.0;

        b.pipes.forEach(p => {
          const d_m = p.diameter_mm / 1000.0;
          const area = Math.PI * (d_m ** 2) / 4.0;
          const vel = area > 0 ? (q_b_m3s / area) : 0.0;
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
          const dz = p.elevation_m || 0.0;

          bMajor += hf;
          bMinor += hm;

          pipesRes.push({
            id: p.id,
            label: p.label,
            branch_id: b.id,
            branch_label: b.label,
            diameter_mm: p.diameter_mm,
            flow_m3h: +(q_b_m3h.toFixed(2)),
            velocity_m_s: +(vel.toFixed(2)),
            reynolds: Math.round(Re),
            flow_regime: Re < 2300 ? 'Laminar' : (Re < 4000 ? 'Transitional' : 'Turbulent'),
            friction_factor: +(f.toFixed(4)),
            hf_major_m: +(hf.toFixed(2)),
            hf_minor_m: +(hm.toFixed(2)),
            hf_elevation_m: +(dz.toFixed(2)),
            total_segment_head_m: +((hf + hm + dz).toFixed(2)),
            k_total: kTot,
            resistance_R: q_b_m3h > 0 ? +(((hf + hm) / (q_b_m3h ** 2)).toExponential(3)) : 0
          });
        });

        const bFric = bMajor + bMinor;
        const bDisElev = parseFloat(b.discharge_elevation_m) || 0.0;
        const bTotalHead = bDisElev + bFric;
        if (bTotalHead > maxBranchHead) maxBranchHead = bTotalHead;

        totalMajor += bMajor;
        totalMinor += bMinor;

        branchSummaries.push({
          id: b.id,
          label: b.label,
          flow_m3h: +(q_b_m3h.toFixed(2)),
          flow_share_pct: +(((q_b_m3h / q_m3h) * 100.0).toFixed(1)),
          discharge_elevation_m: bDisElev,
          total_branch_head_m: +(bTotalHead.toFixed(2)),
          friction_head_m: +(bFric.toFixed(2)),
          num_sub_pipes: b.pipes.length
        });
      });

      tdh = maxBranchHead;
    } else {
      // Series mode
      const q_m3s = q_m3h / 3600.0;
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
        const dz = p.elevation_m || 0.0;

        totalMajor += hf;
        totalMinor += hm;

        pipesRes.push({
          id: p.id,
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

      tdh = totalMajor + totalMinor + this.state.static_elevation;
    }

    const q_m3s = q_m3h / 3600.0;
    const pKw = (rho * g * q_m3s * tdh) / 1000.0;

    // Fallback NPSHa calculation:
    // NPSHa = h_atm - h_vp + z_suct - hf_suct + v_s^2 / (2g)
    const pAtm = 101325.0; // Pa
    const tempC = this.state.fluid?.temp_c || 20.0;
    const pVap = 610.78 * Math.exp((17.27 * tempC) / (tempC + 237.3));
    const hAtm = pAtm / (rho * g);
    const hVp = pVap / (rho * g);

    let zSuct = 0.0;
    let hfSuct = 0.0;
    let vsSuct = 0.0;

    const suctionPipe = this.state.pipes.find(p => p.label && p.label.toLowerCase().includes('suct')) || this.state.pipes[0];
    if (suctionPipe) {
      const d_m = suctionPipe.diameter_mm / 1000.0;
      const area = Math.PI * (d_m ** 2) / 4.0;
      vsSuct = area > 0 ? (q_m3s / area) : 0.0;
      zSuct = suctionPipe.elevation_m || 0.0;
      const pRes = pipesRes.find(pr => pr.id === suctionPipe.id);
      if (pRes) {
        hfSuct = (pRes.hf_major_m || 0.0) + (pRes.hf_minor_m || 0.0);
      }
    }
    const velHeadSuct = (vsSuct ** 2) / (2.0 * g);
    const fallbackNpsha = Math.max(0.0, +(hAtm - hVp + zSuct - hfSuct + velHeadSuct).toFixed(2));
    this.state.lastNpsha_m = fallbackNpsha;

    this.renderResults({
      topology: this.state.topology,
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
      npsha_m: fallbackNpsha,
      npsha_ft: +((fallbackNpsha * 3.28084).toFixed(2)),
      branch_summaries: branchSummaries,
      pipes: pipesRes
    });
  }

  applyToPumpSelection() {
    this.calculate(true);
  }
}

// Global controller instance
window.simpleController = new SimpleNetworkController();

/**
 * Toggles the Pipe Network Designer view between:
 *  - 'canvas': Interactive visual canvas designer
 *  - 'simple': Form and dropdown-driven simple network list
 */
function setDesignerMode(mode) {
  const canvasBtn = document.getElementById('btn-mode-canvas');
  const simpleBtn = document.getElementById('btn-mode-simple');
  const toolbar = document.getElementById('pn-toolbar');
  const mainRow = document.getElementById('pn-main-row');
  const simpleWrap = document.getElementById('pn-simple-mode-wrap');
  const resultsSec = document.getElementById('pn-results-section');
  const pnOuter = document.getElementById('pn-outer');

  const topCanvasBtn = document.getElementById('btn-top-mode-canvas');
  const topSimpleBtn = document.getElementById('btn-top-mode-simple');
  const canvasOnlyEls = document.querySelectorAll('.pn-canvas-only');

  const allowCanvas = (typeof window.FEAT_PIPE_CANVAS !== 'undefined')
    ? Boolean(window.FEAT_PIPE_CANVAS)
    : Boolean(topCanvasBtn);

  if (mode === 'canvas' && !allowCanvas) {
    mode = 'simple';
  }

  if (mode === 'simple') {
    canvasBtn?.classList.remove('active-tool');
    simpleBtn?.classList.add('active-tool');
    topCanvasBtn?.classList.remove('active-tool');
    topSimpleBtn?.classList.add('active-tool');
    if (topSimpleBtn) { topSimpleBtn.style.background = '#22c55e'; topSimpleBtn.style.color = '#000'; }
    if (topCanvasBtn) { topCanvasBtn.style.background = 'transparent'; topCanvasBtn.style.color = '#8b949e'; }

    // In Simple Mode: Keep toolbar visible, hide only canvas-specific tools
    if (toolbar) toolbar.style.display = 'flex';
    canvasOnlyEls.forEach(el => el.style.display = 'none');

    if (mainRow) mainRow.style.display = 'none';
    if (resultsSec) resultsSec.style.display = 'none';

    if (simpleWrap) simpleWrap.style.display = 'flex';
    if (pnOuter) pnOuter.style.height = 'auto'; // allow natural height for form mode

    if (!window.simpleController?.isInitialized) {
      window.simpleController?.init();
    } else {
      window.simpleController?.syncControlsFromState();
      window.simpleController?.calculate();
    }

    try { localStorage.setItem('pmp_pipe_designer_mode', 'simple'); } catch (e) {}

  } else {
    canvasBtn?.classList.add('active-tool');
    simpleBtn?.classList.remove('active-tool');
    topCanvasBtn?.classList.add('active-tool');
    topSimpleBtn?.classList.remove('active-tool');
    if (topCanvasBtn) { topCanvasBtn.style.background = '#38bdf8'; topCanvasBtn.style.color = '#000'; }
    if (topSimpleBtn) { topSimpleBtn.style.background = 'transparent'; topSimpleBtn.style.color = '#22c55e'; }

    // In Canvas Mode: Show visual toolbar, main row and restore CAD height
    if (toolbar) toolbar.style.display = 'flex';
    canvasOnlyEls.forEach(el => el.style.display = '');

    if (simpleWrap) simpleWrap.style.display = 'none';
    if (mainRow) mainRow.style.display = 'flex';
    if (pnOuter) pnOuter.style.height = '680px'; // fixed CAD height for canvas

    // If results were previously calculated in visual mode, re-show results section
    if (typeof state !== 'undefined' && state.lastCalculation && resultsSec) {
      resultsSec.style.display = '';
    }

    try { localStorage.setItem('pmp_pipe_designer_mode', 'canvas'); } catch (e) {}

    if (typeof scheduleDraw === 'function') scheduleDraw();
    if (typeof applyTransform === 'function') applyTransform();
    if (typeof renderAll === 'function') renderAll();
  }
}
