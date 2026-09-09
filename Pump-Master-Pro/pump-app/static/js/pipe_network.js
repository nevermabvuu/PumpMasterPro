/**
 * pipe_network.js — Interactive Pipe Network System Designer
 *
 * Implements a drag-and-drop SVG canvas for drawing hydraulic pipe networks.
 * The user places nodes (reservoirs, pumps, tanks, junctions), connects them
 * with pipe segments, assigns properties (diameter, length, material, fittings,
 * elevation change), then sends the network to the Flask API for friction-loss
 * calculations.
 *
 * Architecture
 * ─────────────
 *  State       — mutable data model (nodes, pipes, selection, interaction mode)
 *  Rendering   — SVG DOM manipulation (renderAll → renderNode, renderPipe)
 *  Interaction — mouse / keyboard events (pan, zoom, drag nodes, draw pipes)
 *  Properties  — right-panel form population and change handlers
 *  API         — fetch POST to /api/pipe-network/calculate → display results
 *  Persistence — JSON export / import of the entire network
 */

'use strict';

// ============================================================================
// CONSTANTS
// ============================================================================

/** Grid snap size in SVG user-units */
const GRID = 50;

/** Available pipe materials (keys must match Python PIPE_ROUGHNESS_MM) */
const MATERIALS = [
  { key: 'commercial_steel', label: 'Commercial Steel  (e = 0.046 mm)' },
  { key: 'galvanised_steel', label: 'Galvanised Steel  (e = 0.150 mm)' },
  { key: 'cast_iron',        label: 'Cast Iron         (e = 0.260 mm)' },
  { key: 'pvc',              label: 'PVC / Plastic     (e = 0.002 mm)' },
  { key: 'hdpe',             label: 'HDPE              (e = 0.007 mm)' },
  { key: 'stainless_steel',  label: 'Stainless Steel   (e = 0.015 mm)' },
  { key: 'concrete',         label: 'Concrete          (e = 1.000 mm)' },
  { key: 'smooth',           label: 'Smooth / Drawn    (e = 0.002 mm)' },
];

/** Available pipe fittings (keys must match Python FITTING_K) */
const FITTINGS = [
  { key: 'elbow_90_standard',    label: '90 Elbow (Standard)',     K: 0.90 },
  { key: 'elbow_90_long_radius', label: '90 Elbow (Long Radius)',  K: 0.60 },
  { key: 'elbow_45',             label: '45 Elbow',                K: 0.40 },
  { key: 'gate_valve_open',      label: 'Gate Valve (Open)',       K: 0.20 },
  { key: 'gate_valve_half',      label: 'Gate Valve (50% Open)',   K: 5.60 },
  { key: 'globe_valve_open',     label: 'Globe Valve (Open)',      K: 10.0 },
  { key: 'check_valve_swing',    label: 'Check Valve (Swing)',     K: 2.50 },
  { key: 'check_valve_ball',     label: 'Check Valve (Ball)',      K: 4.50 },
  { key: 'ball_valve_open',      label: 'Ball Valve (Open)',       K: 0.05 },
  { key: 'butterfly_valve_open', label: 'Butterfly Valve (Open)',  K: 0.30 },
  { key: 'tee_run_through',      label: 'Tee (Run Through)',       K: 0.40 },
  { key: 'tee_branch_flow',      label: 'Tee (Branch Flow)',       K: 1.80 },
  { key: 'entry_sharp',          label: 'Pipe Entry (Sharp)',      K: 0.50 },
  { key: 'entry_rounded',        label: 'Pipe Entry (Rounded)',    K: 0.20 },
  { key: 'exit_abrupt',          label: 'Pipe Exit (Abrupt)',      K: 1.00 },
  { key: 'reducer_gradual',      label: 'Reducer (Gradual)',       K: 0.10 },
  { key: 'reducer_sudden',       label: 'Reducer (Sudden)',        K: 0.50 },
  { key: 'expander_gradual',     label: 'Expander (Gradual)',      K: 0.30 },
];

// ============================================================================
// STATE — single mutable object representing the entire network
// ============================================================================
const state = {
  nodes:  [],       // [{ id, type, x, y, props }]
  pipes:  [],       // [{ id, fromNodeId, toNodeId, props }]
  selected: null,   // { kind: 'node'|'pipe', id } or null
  mode: 'select',   // 'select' | 'connect' | 'add-reservoir' | 'add-pump' | ...
  drawingPipe: null, // { fromNodeId, mouseX, mouseY } while drawing
  nextId: 1,
  pan:  { x: 0, y: 0 },
  zoom: 1.0,
  panDrag:  null,   // middle-mouse pan state
  nodeDrag: null,   // node move state
};

// SVG element references (set in init())
let svgEl, nodesGroup, pipesGroup, draftPipeLine;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function newId(prefix) { return `${prefix}-${state.nextId++}`; }
function snap(v) { return Math.round(v / GRID) * GRID; }

/** Convert DOM mouse coords to SVG canvas coords (accounting for pan+zoom) */
function toSVG(e) {
  const r = svgEl.getBoundingClientRect();
  return {
    x: (e.clientX - r.left  - state.pan.x) / state.zoom,
    y: (e.clientY - r.top   - state.pan.y) / state.zoom,
  };
}

function findNode(id) { return state.nodes.find(n => n.id === id); }
function findPipe(id) { return state.pipes.find(p => p.id === id); }

/** Default props for each node type */
function defaultNodeProps(type, count) {
  const lbl = `${type.charAt(0).toUpperCase()}${type.slice(1)} ${count + 1}`;
  switch (type) {
    case 'reservoir': return { label: lbl, elevation_m: 0 };
    case 'pump':      return { label: lbl, flow_m3h: 10, elevation_m: 0 };
    case 'tank':      return { label: lbl, elevation_m: 0 };
    case 'junction':  return { label: lbl, elevation_m: 0 };
    default:          return { label: lbl };
  }
}

/** Default props for a new pipe segment */
function defaultPipeProps(id) {
  return {
    label: id,
    diameter_mm:   100,
    length_m:      10.0,
    material:      'commercial_steel',
    elev_change_m: 0.0,
    fittings:      [],
  };
}

// ============================================================================
// LOCAL STORAGE PERSISTENCE
// ============================================================================

function saveNetworkToStorage() {
  const data = { nodes: state.nodes, pipes: state.pipes, nextId: state.nextId };
  localStorage.setItem('pmpro_pipe_network', JSON.stringify(data));
}

function loadNetworkFromStorage() {
  const saved = localStorage.getItem('pmpro_pipe_network');
  if (saved) {
    try {
      const d = JSON.parse(saved);
      if (d.nodes && d.pipes) {
        state.nodes = d.nodes;
        state.pipes = d.pipes;
        state.nextId = d.nextId || Math.max(0, ...[...d.nodes, ...d.pipes].map(x => parseInt(x.id.split('-')[1]) || 0)) + 1;
        return true;
      }
    } catch (e) { console.error('Failed to load pipe network from storage:', e); }
  }
  return false;
}

// ============================================================================
// RENDERING
// ============================================================================

function renderAll() {
  renderPipes();
  renderNodes();
  updateDraftLine();
  saveNetworkToStorage();
}

/** Rebuild all pipe SVG elements */
function renderPipes() {
  pipesGroup.innerHTML = '';
  state.pipes.forEach(pipe => {
    const fn = findNode(pipe.fromNodeId);
    const tn = findNode(pipe.toNodeId);
    if (!fn || !tn) return;
    const isSel = state.selected?.kind === 'pipe' && state.selected.id === pipe.id;

    const g = svgEl.ownerDocument.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.style.cursor = 'pointer';
    g.addEventListener('click', e => { e.stopPropagation(); selectItem('pipe', pipe.id); });

    // Pipe line
    const ln = mkSVG('line', {
      x1: fn.x, y1: fn.y, x2: tn.x, y2: tn.y,
      stroke: isSel ? '#f59e0b' : '#3b82f6',
      'stroke-width': isSel ? 4 : 3,
      'stroke-linecap': 'round',
      ...(isSel ? { 'stroke-dasharray': '8 4' } : {}),
    });
    g.appendChild(ln);

    // Flow-direction arrow at midpoint
    const mx = (fn.x + tn.x) / 2, my = (fn.y + tn.y) / 2;
    const ang = Math.atan2(tn.y - fn.y, tn.x - fn.x) * 180 / Math.PI;
    const ar = mkSVG('polygon', {
      points: '0,-5 10,0 0,5',
      fill:   isSel ? '#f59e0b' : '#60a5fa',
      transform: `translate(${mx},${my}) rotate(${ang})`,
    });
    g.appendChild(ar);

    // Label
    const t = mkSVG('text', {
      x: mx + 6, y: my - 9,
      'font-size': 10, fill: '#64748b',
      'font-family': 'Inter, sans-serif',
    });
    t.textContent = `${pipe.props.label || pipe.id}  D${pipe.props.diameter_mm}mm`;
    g.appendChild(t);

    // Wide transparent hit target
    g.appendChild(mkSVG('line', {
      x1: fn.x, y1: fn.y, x2: tn.x, y2: tn.y,
      stroke: 'transparent', 'stroke-width': 14,
    }));

    pipesGroup.appendChild(g);
  });
}

/** Rebuild all node SVG elements */
function renderNodes() {
  nodesGroup.innerHTML = '';
  state.nodes.forEach(node => {
    const isSel = state.selected?.kind === 'node' && state.selected.id === node.id;
    nodesGroup.appendChild(buildNodeSVG(node, isSel));
  });
}

/** Build the SVG <g> for a node */
function buildNodeSVG(node, isSel) {
  const g = mkSVG('g', { transform: `translate(${node.x},${node.y})` });
  g.style.cursor = 'move';
  g.addEventListener('mousedown', e => onNodeDown(e, node.id));
  g.addEventListener('click', e => { e.stopPropagation(); selectItem('node', node.id); });

  // Shape
  switch (node.type) {
    case 'reservoir': drawReservoir(g, isSel); break;
    case 'pump':      drawPump(g, isSel);      break;
    case 'tank':      drawTank(g, isSel);      break;
    case 'junction':  drawJunction(g, isSel);  break;
  }

  // Label text below node
  const lbl = mkSVG('text', {
    x: 0, y: 50,
    'text-anchor': 'middle', 'font-size': 11,
    fill: isSel ? '#f59e0b' : '#94a3b8',
    'font-family': 'Inter, sans-serif',
  });
  lbl.textContent = node.props.label || node.id;
  g.appendChild(lbl);

  // Selection ring
  if (isSel) {
    g.appendChild(mkSVG('circle', {
      r: 46, fill: 'none',
      stroke: '#f59e0b', 'stroke-width': 2,
      'stroke-dasharray': '6 3', opacity: 0.6,
    }));
  }

  // Connection port (shown in connect mode)
  const portR = 7;
  const portFill = state.mode === 'connect' ? '#22c55e' : 'transparent';
  const portStroke = state.mode === 'connect' ? '#22c55e' : '#334155';
  const port = mkSVG('circle', {
    r: portR, fill: portFill, stroke: portStroke, 'stroke-width': 2,
  });
  port.style.cursor = 'crosshair';
  port.addEventListener('click', e => { e.stopPropagation(); onPortClick(node.id); });
  g.appendChild(port);

  return g;
}

// Node shape drawing helpers ─────────────────────────────────────────────────

function drawReservoir(g, sel) {
  g.appendChild(mkSVG('rect', {
    x: -40, y: -30, width: 80, height: 60, rx: 6,
    fill: sel ? '#1e3a5f' : '#0f2744',
    stroke: sel ? '#60a5fa' : '#3b82f6', 'stroke-width': 2.5,
  }));
  // Water waves
  for (let i = 0; i < 2; i++) {
    const wp = mkSVG('path', {
      d: `M-28,${-6+i*12} Q-14,${-13+i*12} 0,${-6+i*12} Q14,${1+i*12} 28,${-6+i*12}`,
      stroke: '#7dd3fc', 'stroke-width': 1.5, fill: 'none', opacity: 0.8,
    });
    g.appendChild(wp);
  }
  g.appendChild(svgText(0, -16, 'R', 18, '#93c5fd', 'bold'));
}

function drawPump(g, sel) {
  g.appendChild(mkSVG('circle', {
    r: 34, fill: sel ? '#4c1d95' : '#2e1065',
    stroke: sel ? '#c084fc' : '#a855f7', 'stroke-width': 2.5,
  }));
  // Three impeller spokes
  for (let i = 0; i < 3; i++) {
    const a = (i * 120 - 90) * Math.PI / 180;
    g.appendChild(mkSVG('line', {
      x1: 0, y1: 0,
      x2: Math.cos(a) * 20, y2: Math.sin(a) * 20,
      stroke: '#d8b4fe', 'stroke-width': 3, 'stroke-linecap': 'round',
    }));
  }
  g.appendChild(mkSVG('circle', { r: 6, fill: '#c084fc' }));
  g.appendChild(svgText(0, -18, 'P', 13, '#e9d5ff', 'bold'));
}

function drawTank(g, sel) {
  g.appendChild(mkSVG('rect', {
    x: -28, y: -44, width: 56, height: 88, rx: 4,
    fill: sel ? '#1f3a1f' : '#14291e',
    stroke: sel ? '#4ade80' : '#22c55e', 'stroke-width': 2,
  }));
  g.appendChild(mkSVG('rect', {
    x: -24, y: 4, width: 48, height: 34, rx: 3,
    fill: '#166534', opacity: 0.85,
  }));
  g.appendChild(svgText(0, -22, 'T', 16, '#86efac', 'bold'));
}

function drawJunction(g, sel) {
  g.appendChild(mkSVG('circle', {
    r: 14, fill: sel ? '#334155' : '#1e293b',
    stroke: sel ? '#f59e0b' : '#64748b', 'stroke-width': 2,
  }));
  g.appendChild(svgText(0, 4, 'J', 11, '#94a3b8', 'bold'));
}

// SVG element factories ───────────────────────────────────────────────────────

/** Create an SVG element with a map of attributes */
function mkSVG(tag, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}

function svgText(x, y, text, size, fill, weight) {
  const el = mkSVG('text', {
    x, y, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
    'font-size': size, fill, 'font-family': 'Inter, sans-serif',
    ...(weight ? { 'font-weight': weight } : {}),
  });
  el.textContent = text;
  return el;
}

/** Show/hide the rubber-band line while drawing a pipe */
function updateDraftLine() {
  if (!draftPipeLine) return;
  if (state.drawingPipe) {
    const fn = findNode(state.drawingPipe.fromNodeId);
    if (!fn) { draftPipeLine.style.display = 'none'; return; }
    draftPipeLine.setAttribute('x1', fn.x);
    draftPipeLine.setAttribute('y1', fn.y);
    draftPipeLine.setAttribute('x2', state.drawingPipe.mouseX);
    draftPipeLine.setAttribute('y2', state.drawingPipe.mouseY);
    draftPipeLine.style.display = '';
  } else {
    draftPipeLine.style.display = 'none';
  }
}

// ============================================================================
// CANVAS TRANSFORM
// ============================================================================

function applyTransform() {
  const w = svgEl.clientWidth  || 900;
  const h = svgEl.clientHeight || 560;
  const vbW = w / state.zoom;
  const vbH = h / state.zoom;
  const vbX = -state.pan.x / state.zoom;
  const vbY = -state.pan.y / state.zoom;
  svgEl.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================

/** Canvas background click */
function onCanvasClick(e) {
  if (state.mode === 'select') { selectItem(null); return; }
  if (state.mode.startsWith('add-')) {
    const type = state.mode.replace('add-', '');
    const pos  = toSVG(e);
    addNode(type, snap(pos.x), snap(pos.y));
    setMode('select');
  }
}

/** Node mousedown — start drag or connect */
function onNodeDown(e, nodeId) {
  e.stopPropagation();
  if (state.mode === 'connect') { onPortClick(nodeId); return; }
  const pos  = toSVG(e);
  const node = findNode(nodeId);
  if (!node) return;
  state.nodeDrag = { nodeId, offsetX: pos.x - node.x, offsetY: pos.y - node.y };
}

/** Port (or node centre in connect mode) click — start/finish pipe drawing */
function onPortClick(nodeId) {
  if (state.mode !== 'connect') return;
  if (!state.drawingPipe) {
    state.drawingPipe = { fromNodeId: nodeId, mouseX: 0, mouseY: 0 };
    toast('Click a destination node to complete the pipe.');
  } else {
    const fromId = state.drawingPipe.fromNodeId;
    if (fromId === nodeId) {
      toast('Cannot connect a node to itself.', 'warn');
      return;
    }
    const dup = state.pipes.some(
      p => (p.fromNodeId === fromId && p.toNodeId === nodeId) ||
           (p.fromNodeId === nodeId && p.toNodeId === fromId)
    );
    if (dup) {
      toast('A pipe already connects these two nodes.', 'warn');
      state.drawingPipe = null; updateDraftLine(); return;
    }
    addPipe(fromId, nodeId);
    state.drawingPipe = null;
    updateDraftLine();
    setMode('select');
  }
}

// ============================================================================
// CRUD
// ============================================================================

function addNode(type, x, y) {
  const id    = newId('N');
  const count = state.nodes.filter(n => n.type === type).length;
  const node  = { id, type, x, y, props: defaultNodeProps(type, count) };
  state.nodes.push(node);
  renderAll();
  selectItem('node', id);
}

function addPipe(fromNodeId, toNodeId) {
  const id   = newId('P');
  const pipe = { id, fromNodeId, toNodeId, props: defaultPipeProps(id) };
  state.pipes.push(pipe);
  renderAll();
  selectItem('pipe', id);
}

function deleteSelected() {
  if (!state.selected) return;
  if (state.selected.kind === 'node') {
    const nid = state.selected.id;
    state.nodes = state.nodes.filter(n => n.id !== nid);
    state.pipes = state.pipes.filter(p => p.fromNodeId !== nid && p.toNodeId !== nid);
  } else {
    state.pipes = state.pipes.filter(p => p.id !== state.selected.id);
  }
  selectItem(null);
  renderAll();
}

// ============================================================================
// SELECTION & PROPERTIES PANEL
// ============================================================================

function selectItem(kind, id) {
  state.selected = kind ? { kind, id } : null;
  if (kind === 'node') showNodeProps(findNode(id));
  else if (kind === 'pipe') showPipeProps(findPipe(id));
  else showPropsPanel('none');
  renderAll();
}

function showPropsPanel(which) {
  document.getElementById('pn-props-node').style.display  = which === 'node'  ? '' : 'none';
  document.getElementById('pn-props-pipe').style.display  = which === 'pipe'  ? '' : 'none';
  document.getElementById('pn-props-empty').style.display = which === 'none'  ? '' : 'none';
}

function showNodeProps(node) {
  if (!node) return;
  showPropsPanel('node');
  setVal('np-id',    node.id);
  setVal('np-type',  node.type);
  setVal('np-label', node.props.label || '');
  setVal('np-elev',  node.props.elevation_m ?? 0);
  const pumpDiv = document.getElementById('np-pump-fields');
  pumpDiv.style.display = node.type === 'pump' ? '' : 'none';
  if (node.type === 'pump') setVal('np-flow', node.props.flow_m3h ?? 10);
}

function showPipeProps(pipe) {
  if (!pipe) return;
  showPropsPanel('pipe');
  setVal('pp-id',         pipe.id);
  setVal('pp-from',       pipe.fromNodeId);
  setVal('pp-to',         pipe.toNodeId);
  setVal('pp-label',      pipe.props.label || '');
  setVal('pp-diameter',   pipe.props.diameter_mm);
  setVal('pp-length',     pipe.props.length_m);
  setVal('pp-elev-change',pipe.props.elev_change_m);
  setVal('pp-material',   pipe.props.material);
  document.querySelectorAll('.pp-fitting-cb').forEach(cb => {
    cb.checked = (pipe.props.fittings || []).includes(cb.value);
  });
  refreshKTotal(pipe.props.fittings || []);
}

/** Helper to set value on both inputs and spans */
function setVal(id, v) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.tagName === 'INPUT' || el.tagName === 'SELECT') el.value = v;
  else el.textContent = v;
}

function refreshKTotal(fittings) {
  const kMap = Object.fromEntries(FITTINGS.map(f => [f.key, f.K]));
  const total = fittings.reduce((s, k) => s + (kMap[k] || 0), 0);
  setVal('pp-ktotal', total.toFixed(2));
}

// ============================================================================
// MODE CONTROL
// ============================================================================

function setMode(mode) {
  state.mode = mode;
  state.drawingPipe = null;
  updateDraftLine();

  document.querySelectorAll('[data-mode]').forEach(btn =>
    btn.classList.toggle('active-tool', btn.dataset.mode === mode)
  );

  const labels = {
    'select':          'Select / Move nodes',
    'connect':         'Draw Pipe — click source node, then destination node',
    'add-reservoir':   'Place Reservoir — click on canvas',
    'add-pump':        'Place Pump — click on canvas',
    'add-tank':        'Place Tank — click on canvas',
    'add-junction':    'Place Junction (Tee) — click on canvas',
  };
  setVal('pn-status', labels[mode] || mode);

  const cursors = { 'select': 'default', 'connect': 'crosshair' };
  svgEl.style.cursor = cursors[mode] || 'cell';
}

// ============================================================================
// PROPERTY CHANGE HANDLERS
// ============================================================================

function onNodeLabelChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node) { node.props.label = document.getElementById('np-label').value; renderAll(); }
}
function onNodeElevChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node) node.props.elevation_m = parseFloat(document.getElementById('np-elev').value) || 0;
}
function onPumpFlowChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node && node.type === 'pump')
    node.props.flow_m3h = parseFloat(document.getElementById('np-flow').value) || 10;
}

function onPipePropChange() {
  const pipe = state.selected?.kind === 'pipe' ? findPipe(state.selected.id) : null;
  if (!pipe) return;
  pipe.props.label          = document.getElementById('pp-label').value;
  pipe.props.diameter_mm    = parseFloat(document.getElementById('pp-diameter').value) || 100;
  pipe.props.length_m       = parseFloat(document.getElementById('pp-length').value) || 10;
  pipe.props.elev_change_m  = parseFloat(document.getElementById('pp-elev-change').value) || 0;
  pipe.props.material       = document.getElementById('pp-material').value;
  pipe.props.fittings = [];
  document.querySelectorAll('.pp-fitting-cb:checked').forEach(cb =>
    pipe.props.fittings.push(cb.value)
  );
  refreshKTotal(pipe.props.fittings);
  renderAll();
}

// ============================================================================
// API INTEGRATION
// ============================================================================

async function runCalculation() {
  if (state.pipes.length === 0) {
    toast('Add at least one pipe segment before calculating.', 'warn'); return;
  }
  const globalFlow = parseFloat(document.getElementById('pn-global-flow').value) || 10;
  const payload = {
    flow_m3h: globalFlow,
    pipes: state.pipes.map(pipe => ({
      id:            pipe.id,
      label:         pipe.props.label || pipe.id,
      diameter_mm:   pipe.props.diameter_mm,
      length_m:      pipe.props.length_m,
      material:      pipe.props.material,
      elev_change_m: pipe.props.elev_change_m,
      fittings:      pipe.props.fittings || [],
    })),
  };

  const btn = document.getElementById('pn-calc-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Calculating...';

  try {
    const resp = await fetch('/api/pipe-network/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) { const e = await resp.json(); toast(`Error: ${e.error}`, 'error'); return; }
    const data = await resp.json();
    displayResults(data);
    document.getElementById('pn-results-section').scrollIntoView({ behavior: 'smooth' });
    toast('Calculation complete!', 'success');
  } catch (err) {
    toast(`Network error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-calculator"></i> Calculate Losses';
  }
}

function displayResults(data) {
  document.getElementById('pn-results-section').style.display = '';
  const s = data.summary;
  setVal('res-major', s.total_hf_major_m.toFixed(3));
  setVal('res-minor', s.total_hf_minor_m.toFixed(3));
  setVal('res-elev',  s.total_elevation_m.toFixed(3));
  setVal('res-total', s.total_system_head_m.toFixed(3));
  setVal('res-count', s.pipe_count);

  const tbody = document.getElementById('res-table-body');
  tbody.innerHTML = '';
  data.results.forEach(r => {
    const rc = r.regime === 'Laminar' ? '#22c55e' : r.regime === 'Transitional' ? '#f59e0b' : '#60a5fa';
    const vc = r.velocity_status === 'OK' ? '#22c55e' : r.velocity_status === 'Too slow' ? '#94a3b8' : '#f87171';
    tbody.innerHTML += `
      <tr style="border-bottom:1px solid #21262d" onmouseover="this.style.background='#1c2330'" onmouseout="this.style.background=''">
        <td style="padding:6px 10px;font-family:monospace;color:#58a6ff">${r.id}</td>
        <td style="padding:6px 10px;color:#e6edf3">${r.label}</td>
        <td style="padding:6px 10px;text-align:right">${r.diameter_mm}</td>
        <td style="padding:6px 10px;text-align:right">${r.length_m}</td>
        <td style="padding:6px 10px;text-align:right">${r.velocity_ms}
          <span style="font-size:10px;color:${vc}"> ${r.velocity_status}</span></td>
        <td style="padding:6px 10px;text-align:center">
          <span style="color:${rc};font-size:11px">${r.regime}</span><br>
          <span style="color:#64748b;font-size:10px">Re ${r.reynolds.toLocaleString()}</span></td>
        <td style="padding:6px 10px;text-align:right">${r.friction_factor}</td>
        <td style="padding:6px 10px;text-align:right;color:#f87171">${r.hf_major_m}</td>
        <td style="padding:6px 10px;text-align:right;color:#fb923c">${r.hf_minor_m}</td>
        <td style="padding:6px 10px;text-align:right;color:#a78bfa">${r.hf_elevation_m}</td>
        <td style="padding:6px 10px;text-align:right;font-weight:700;color:#fbbf24">${r.h_total_m}</td>
      </tr>`;
  });
  (data.errors || []).forEach(err => {
    tbody.innerHTML += `<tr><td colspan="11" style="padding:6px 10px;color:#f85149">Error in ${err.id}: ${err.error}</td></tr>`;
  });
}

// ============================================================================
// EXPORT / IMPORT / CLEAR
// ============================================================================

function exportNetwork() {
  const blob = new Blob([JSON.stringify({ nodes: state.nodes, pipes: state.pipes }, null, 2)],
    { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'pipe-network.json';
  a.click();
}

function importNetwork(file) {
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const d = JSON.parse(e.target.result);
      if (!d.nodes || !d.pipes) throw new Error('Invalid file');
      state.nodes  = d.nodes;
      state.pipes  = d.pipes;
      state.nextId = Math.max(0, ...[...d.nodes, ...d.pipes].map(x =>
        parseInt(x.id.split('-')[1]) || 0)) + 1;
      selectItem(null); renderAll();
      toast('Network loaded!', 'success');
    } catch (err) { toast(`Import failed: ${err.message}`, 'error'); }
  };
  reader.readAsText(file);
}

function clearCanvas() {
  if (!state.nodes.length && !state.pipes.length) return;
  if (!confirm('Clear the entire network? This cannot be undone.')) return;
  state.nodes = []; state.pipes = [];
  document.getElementById('pn-results-section').style.display = 'none';
  selectItem(null); renderAll();
  toast('Canvas cleared.', 'info');
}

// ============================================================================
// TOAST NOTIFICATIONS
// ============================================================================

function toast(msg, type = 'info') {
  const colors = { info: '#58a6ff', success: '#22c55e', warn: '#f59e0b', error: '#f87171' };
  const el = document.createElement('div');
  el.style.cssText = `
    position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
    background:#1e293b;border:1px solid ${colors[type]};color:${colors[type]};
    padding:8px 22px;border-radius:8px;font-size:13px;z-index:9999;
    box-shadow:0 4px 24px rgba(0,0,0,0.5);pointer-events:none;`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ============================================================================
// INITIALISATION
// ============================================================================

function init() {
  svgEl      = document.getElementById('pn-svg');
  nodesGroup = document.getElementById('pn-nodes');
  pipesGroup = document.getElementById('pn-pipes');

  // Draft rubber-band line for pipe drawing
  draftPipeLine = mkSVG('line', {
    stroke: '#22c55e', 'stroke-width': 2, 'stroke-dasharray': '8 4',
  });
  draftPipeLine.style.display = 'none';
  draftPipeLine.style.pointerEvents = 'none';
  svgEl.appendChild(draftPipeLine);

  // Canvas mouse events
  svgEl.addEventListener('click', onCanvasClick);

  svgEl.addEventListener('mousemove', e => {
    // Update draft pipe preview endpoint
    if (state.drawingPipe) {
      const pos = toSVG(e);
      state.drawingPipe.mouseX = pos.x;
      state.drawingPipe.mouseY = pos.y;
      updateDraftLine();
    }
    // Drag selected node
    if (state.nodeDrag) {
      const pos  = toSVG(e);
      const node = findNode(state.nodeDrag.nodeId);
      if (node) {
        node.x = snap(pos.x - state.nodeDrag.offsetX);
        node.y = snap(pos.y - state.nodeDrag.offsetY);
        renderAll();
      }
    }
    // Pan canvas (middle mouse)
    if (state.panDrag) {
      state.pan.x = state.panDrag.startPanX + (e.clientX - state.panDrag.startX);
      state.pan.y = state.panDrag.startPanY + (e.clientY - state.panDrag.startY);
      applyTransform();
    }
  });

  svgEl.addEventListener('mouseup', () => { state.nodeDrag = null; state.panDrag = null; });

  // Middle-mouse pan
  svgEl.addEventListener('mousedown', e => {
    if (e.button === 1) {
      state.panDrag = { startX: e.clientX, startY: e.clientY,
                        startPanX: state.pan.x, startPanY: state.pan.y };
      e.preventDefault();
    }
  });

  // Scroll to zoom
  svgEl.addEventListener('wheel', e => {
    e.preventDefault();
    state.zoom = Math.min(3, Math.max(0.2, state.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
    applyTransform();
  }, { passive: false });

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.key === 'Escape')  setMode('select');
    if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
    if (e.key === 's') setMode('select');
    if (e.key === 'c') setMode('connect');
  });

  // Toolbar buttons
  document.getElementById('btn-select').addEventListener('click', () => setMode('select'));
  document.getElementById('btn-connect').addEventListener('click', () => setMode('connect'));
  document.getElementById('btn-add-reservoir').addEventListener('click', () => setMode('add-reservoir'));
  document.getElementById('btn-add-pump').addEventListener('click', () => setMode('add-pump'));
  document.getElementById('btn-add-tank').addEventListener('click', () => setMode('add-tank'));
  document.getElementById('btn-add-junction').addEventListener('click', () => setMode('add-junction'));
  document.getElementById('btn-delete').addEventListener('click', deleteSelected);
  document.getElementById('btn-clear').addEventListener('click', clearCanvas);
  document.getElementById('btn-export').addEventListener('click', exportNetwork);
  document.getElementById('btn-import').addEventListener('click', () =>
    document.getElementById('import-file-input').click());
  document.getElementById('import-file-input').addEventListener('change', e => {
    if (e.target.files[0]) importNetwork(e.target.files[0]);
    e.target.value = '';
  });
  document.getElementById('btn-zoom-in').addEventListener('click', () => {
    state.zoom = Math.min(3, state.zoom * 1.2); applyTransform();
  });
  document.getElementById('btn-zoom-out').addEventListener('click', () => {
    state.zoom = Math.max(0.2, state.zoom / 1.2); applyTransform();
  });
  document.getElementById('btn-zoom-reset').addEventListener('click', () => {
    state.zoom = 1; state.pan = { x: 0, y: 0 }; applyTransform();
  });

  document.getElementById('pn-calc-btn').addEventListener('click', runCalculation);

  // Node property inputs
  document.getElementById('np-label').addEventListener('input', onNodeLabelChange);
  document.getElementById('np-elev').addEventListener('change', onNodeElevChange);
  document.getElementById('np-flow').addEventListener('change', onPumpFlowChange);

  // Pipe property inputs — all trigger the same handler
  ['pp-label','pp-diameter','pp-length','pp-elev-change','pp-material'].forEach(id =>
    document.getElementById(id).addEventListener('change', onPipePropChange)
  );
  document.getElementById('pp-fittings-list').addEventListener('change', onPipePropChange);

  // Populate material dropdown
  const matSel = document.getElementById('pp-material');
  MATERIALS.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.key; opt.textContent = m.label;
    matSel.appendChild(opt);
  });

  // Build fitting checkboxes dynamically
  const fList = document.getElementById('pp-fittings-list');
  FITTINGS.forEach(f => {
    const lbl = document.createElement('label');
    lbl.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:5px;cursor:pointer;font-size:12px;color:#94a3b8;';
    lbl.innerHTML = `<input type="checkbox" class="pp-fitting-cb" value="${f.key}" style="accent-color:#58a6ff;cursor:pointer;flex-shrink:0;">
      <span>${f.label} <span style="color:#475569">(K=${f.K})</span></span>`;
    fList.appendChild(lbl);
  });

  // Initial state
  setMode('select');
  showPropsPanel('none');
  applyTransform();
  
  // Load from local storage, or fall back to demo network
  if (!loadNetworkFromStorage()) {
    loadDemoNetwork();
  } else {
    renderAll();
  }
}

/** Pre-load a simple demo network: Reservoir -> Pump -> Junction -> Tank */
function loadDemoNetwork() {
  state.nodes = [
    { id: 'N-1', type: 'reservoir', x: 150, y: 280,
      props: { label: 'Sump',          elevation_m: 0 } },
    { id: 'N-2', type: 'pump',      x: 350, y: 280,
      props: { label: 'Pump 1',        flow_m3h: 15,  elevation_m: 0 } },
    { id: 'N-3', type: 'junction',  x: 530, y: 280,
      props: { label: 'Tee',           elevation_m: 2 } },
    { id: 'N-4', type: 'tank',      x: 700, y: 160,
      props: { label: 'Overhead Tank', elevation_m: 12 } },
  ];
  state.pipes = [
    { id: 'P-1', fromNodeId: 'N-1', toNodeId: 'N-2',
      props: { label: 'Suction',   diameter_mm: 150, length_m: 4,
               material: 'commercial_steel', elev_change_m: 0,
               fittings: ['entry_sharp', 'gate_valve_open'] } },
    { id: 'P-2', fromNodeId: 'N-2', toNodeId: 'N-3',
      props: { label: 'Discharge', diameter_mm: 100, length_m: 18,
               material: 'commercial_steel', elev_change_m: 2,
               fittings: ['check_valve_swing', 'elbow_90_standard'] } },
    { id: 'P-3', fromNodeId: 'N-3', toNodeId: 'N-4',
      props: { label: 'Riser',     diameter_mm: 80,  length_m: 14,
               material: 'commercial_steel', elev_change_m: 10,
               fittings: ['elbow_90_standard', 'exit_abrupt'] } },
  ];
  state.nextId = 10;
  renderAll();
}

document.addEventListener('DOMContentLoaded', init);
