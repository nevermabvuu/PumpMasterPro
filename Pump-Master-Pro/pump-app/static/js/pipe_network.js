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
  viewMode: 'industrial', // 'schematic' | 'industrial'
  canvasTheme: 'dark',    // 'dark' | 'light'
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

function getNodeRadius(node, viewMode) {
  if (!node) return 0;
  if (viewMode === 'industrial') {
    switch (node.type) {
      case 'elbow': return 18;
      case 'valve': return 22;
      case 'pump':  return 24;
      case 'junction': return 16;
      case 'tank': return 30;
      case 'reservoir': return 36;
      case 'discharge': return 16;
      default: return 0;
    }
  } else {
    switch (node.type) {
      case 'elbow': return 16;
      case 'valve': return 18;
      case 'pump':  return 34;
      case 'junction': return 14;
      case 'tank': return 28;
      case 'reservoir': return 40;
      case 'discharge': return 15;
      default: return 0;
    }
  }
}

/** Proportional visual thickness for pipes matching water distribution systems */
function getPipeVisualThickness(diameter_mm) {
  const d = diameter_mm || 25;
  if (d <= 16) return 8;       // 1/2" branch pipe
  if (d <= 22) return 12;      // 3/4" distribution pipe
  if (d <= 32) return 16;      // 1" main pipe
  if (d <= 45) return 20;      // 1 1/4" - 1 1/2"
  if (d <= 65) return 24;      // 2"
  return Math.min(36, Math.round(24 + (d - 65) * 0.12));
}

/** Formatted trade size callout (e.g. 1", 3/4", 1/2") */
function formatPipeSizeLabel(pipe) {
  const d = pipe.props.diameter_mm || 25;
  let sizeStr = '';
  if (d >= 13 && d <= 17) sizeStr = '1/2"';
  else if (d >= 18 && d <= 23) sizeStr = '3/4"';
  else if (d >= 24 && d <= 30) sizeStr = '1"';
  else if (d >= 31 && d <= 38) sizeStr = '1¼"';
  else if (d >= 39 && d <= 45) sizeStr = '1½"';
  else if (d >= 48 && d <= 58) sizeStr = '2"';
  else if (d >= 60 && d <= 73) sizeStr = '2½"';
  else if (d >= 74 && d <= 88) sizeStr = '3"';
  else if (d >= 90 && d <= 110) sizeStr = '4"';
  else sizeStr = `D${d}mm`;

  const lbl = pipe.props.label || pipe.id;
  return `${sizeStr} (${lbl})`;
}

/** Default props for each node type */
function defaultNodeProps(type, count) {
  const lbl = type === 'discharge' ? `Faucet ${count + 1}` : `${type.charAt(0).toUpperCase()}${type.slice(1)} ${count + 1}`;
  switch (type) {
    case 'reservoir': return { label: lbl, elevation_m: 0 };
    case 'pump':      return { label: lbl, flow_m3h: 10, elevation_m: 0 };
    case 'tank':      return { label: lbl, elevation_m: 0 };
    case 'junction':  return { label: lbl, elevation_m: 0 };
    case 'discharge': return { label: lbl, elevation_m: 0 };
    case 'valve':     return { label: lbl, elevation_m: 0, fitting_key: 'ball_valve_open' };
    case 'elbow':     return { label: lbl, elevation_m: 0, fitting_key: 'elbow_90_standard' };
    default:          return { label: lbl };
  }
}

/** Default props for a new pipe segment */
function defaultPipeProps(id) {
  return {
    label: id,
    diameter_mm:   25,
    length_m:      5.0,
    material:      'pvc',
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

    const fnRadius = getNodeRadius(fn, state.viewMode);
    const tnRadius = getNodeRadius(tn, state.viewMode);
    
    const dx = tn.x - fn.x;
    const dy = tn.y - fn.y;
    const fullDist = Math.hypot(dx, dy);
    
    // Prevent overlapping if nodes are placed too close
    const safeFnRadius = Math.min(fnRadius, Math.max(0, fullDist / 2 - 2));
    const safeTnRadius = Math.min(tnRadius, Math.max(0, fullDist / 2 - 2));
    
    const ux = dx / (fullDist || 1);
    const uy = dy / (fullDist || 1);
    
    const px1 = fn.x + ux * safeFnRadius;
    const py1 = fn.y + uy * safeFnRadius;
    
    const px2 = tn.x - ux * safeTnRadius;
    const py2 = tn.y - uy * safeTnRadius;
    
    const mx = (px1 + px2) / 2, my = (py1 + py2) / 2;
    const ang = Math.atan2(py2 - py1, px2 - px1) * 180 / Math.PI;
    const dist = Math.hypot(px2 - px1, py2 - py1);

    if (state.viewMode === 'industrial') {
      const thickness = getPipeVisualThickness(pipe.props.diameter_mm);
      
      let fillUrl = 'url(#grad-water-pipe)';
      if (pipe.props.material === 'commercial_steel' || pipe.props.material === 'stainless_steel') {
        fillUrl = 'url(#grad-steel)';
      } else if (pipe.props.material === 'hdpe') {
        fillUrl = 'url(#grad-hdpe)';
      } else if (pipe.props.material === 'cast_iron' || pipe.props.material === 'copper') {
        fillUrl = 'url(#grad-iron)';
      }
      
      // Draw rotated rect for pipe body
      const pipeRect = mkSVG('rect', {
        x: px1, y: py1 - thickness/2,
        width: Math.max(1, dist), height: thickness,
        fill: fillUrl,
        stroke: isSel ? '#f59e0b' : '#0369a1',
        'stroke-width': isSel ? 3 : 1,
        rx: 1,
        transform: `rotate(${ang}, ${px1}, ${py1})`
      });
      g.appendChild(pipeRect);

    } else {
      // Schematic Mode
      const ln = mkSVG('line', {
        x1: px1, y1: py1, x2: px2, y2: py2,
        stroke: isSel ? '#f59e0b' : '#3b82f6',
        'stroke-width': isSel ? 4 : 3,
        'stroke-linecap': 'round',
        ...(isSel ? { 'stroke-dasharray': '8 4' } : {}),
      });
      g.appendChild(ln);

      // Flow-direction arrow at midpoint
      const ar = mkSVG('polygon', {
        points: '0,-5 10,0 0,5',
        fill:   isSel ? '#f59e0b' : '#60a5fa',
        transform: `translate(${mx},${my}) rotate(${ang})`,
      });
      g.appendChild(ar);
    }

    // Label
    const thickness = state.viewMode === 'industrial' ? getPipeVisualThickness(pipe.props.diameter_mm) : 4;
    const t = mkSVG('text', {
      x: mx, y: my - (state.viewMode === 'industrial' ? (thickness / 2 + 7) : 9),
      'font-size': 10,
      fill: isSel ? '#f59e0b' : (state.canvasTheme === 'light' ? '#1e293b' : '#94a3b8'),
      'font-family': 'Inter, sans-serif',
      'font-weight': '600',
      'text-anchor': 'middle'
    });
    t.textContent = formatPipeSizeLabel(pipe);
    g.appendChild(t);

    // Wide transparent hit target
    g.appendChild(mkSVG('line', {
      x1: px1, y1: py1, x2: px2, y2: py2,
      stroke: 'transparent', 'stroke-width': state.viewMode === 'industrial' ? 36 : 14,
    }));

    pipesGroup.appendChild(g);
  });
}

/** Rebuild all node SVG elements */
function renderNodes() {
  nodesGroup.innerHTML = '';
  // Find minimum elevation to act as "suction/datum" point
  let minElev = 0;
  if (state.nodes.length > 0) {
    const elevs = state.nodes.map(n => n.props.elevation_m || 0);
    minElev = Math.min(...elevs);
  }

  state.nodes.forEach(node => {
    const isSel = state.selected?.kind === 'node' && state.selected.id === node.id;
    nodesGroup.appendChild(buildNodeSVG(node, isSel, minElev));
  });
}

/** Build the SVG <g> for a node */
function buildNodeSVG(node, isSel, minElev) {
  const g = mkSVG('g', { transform: `translate(${node.x},${node.y})` });
  g.style.cursor = 'move';
  g.addEventListener('mousedown', e => onNodeDown(e, node.id));
  g.addEventListener('click', e => { e.stopPropagation(); selectItem('node', node.id); });

  // Shape
  switch (node.type) {
    case 'reservoir': drawReservoir(g, isSel, node); break;
    case 'pump':      drawPump(g, isSel, node);      break;
    case 'tank':      drawTank(g, isSel, node);      break;
    case 'junction':  drawJunction(g, isSel, node);  break;
    case 'discharge': drawDischarge(g, isSel, node); break;
    case 'valve':     drawValveNode(g, isSel, node); break;
    case 'elbow':     drawElbowNode(g, isSel, node); break;
  }

  // Label text below node
  const lblY = (node.type === 'tank' ? 62 : 46);
  const lbl = mkSVG('text', {
    x: 0, y: lblY,
    'text-anchor': 'middle', 'font-size': 11,
    fill: isSel ? '#f59e0b' : (state.canvasTheme === 'light' ? '#0f172a' : '#cbd5e1'),
    'font-family': 'Inter, sans-serif',
    'font-weight': '600'
  });
  lbl.textContent = node.props.label || node.id;
  g.appendChild(lbl);

  // Elevation text
  const z = node.props.elevation_m || 0;
  const relZ = z - minElev;
  const elevLbl = mkSVG('text', {
    x: 0, y: lblY + 14,
    'text-anchor': 'middle', 'font-size': 9,
    fill: state.canvasTheme === 'light' ? '#64748b' : '#94a3b8',
    'font-family': 'Inter, sans-serif',
  });
  elevLbl.textContent = `Z: ${z}m (ΔH: +${relZ.toFixed(1)}m)`;
  g.appendChild(elevLbl);

  // Selection ring
  if (isSel) {
    g.appendChild(mkSVG('circle', {
      r: (node.type === 'tank' ? 52 : 44), fill: 'none',
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
  if (state.viewMode === 'industrial') {
    // Sump / Reservoir basin
    g.appendChild(mkSVG('path', {
      d: 'M -46,-12 L -38,20 L 38,20 L 46,-12 Z',
      fill: '#475569', stroke: sel ? '#f59e0b' : '#1e293b', 'stroke-width': 2
    }));
    // Water surface
    g.appendChild(mkSVG('path', {
      d: 'M -38,15 L 38,15 L 42,-2 L -42,-2 Z',
      fill: 'url(#grad-water-pipe)', opacity: 0.85
    }));
    // Wave lines
    g.appendChild(mkSVG('path', {
      d: 'M -25,5 Q -12,0 0,5 Q 12,10 25,5',
      stroke: '#e0f2fe', 'stroke-width': 1.5, fill: 'none', opacity: 0.7
    }));
    g.appendChild(svgText(0, -4, 'RESERVOIR', 8, '#ffffff', 'bold'));
  } else {
    g.appendChild(mkSVG('rect', {
      x: -40, y: -30, width: 80, height: 60, rx: 6,
      fill: sel ? '#1e3a5f' : '#0f2744',
      stroke: sel ? '#60a5fa' : '#3b82f6', 'stroke-width': 2.5,
    }));
    for (let i = 0; i < 2; i++) {
      g.appendChild(mkSVG('path', {
        d: `M-28,${-6+i*12} Q-14,${-13+i*12} 0,${-6+i*12} Q14,${1+i*12} 28,${-6+i*12}`,
        stroke: '#7dd3fc', 'stroke-width': 1.5, fill: 'none', opacity: 0.8,
      }));
    }
    g.appendChild(svgText(0, -16, 'R', 18, '#93c5fd', 'bold'));
  }
}

function drawPump(g, sel) {
  if (state.viewMode === 'industrial') {
    // Volute casing (centrifugal pump in industrial blue)
    g.appendChild(mkSVG('circle', {
      r: 22, fill: 'url(#grad-water-pipe)', stroke: sel ? '#f59e0b' : '#0369a1', 'stroke-width': 2
    }));
    g.appendChild(mkSVG('circle', {
      r: 10, fill: '#0f172a', stroke: '#38bdf8', 'stroke-width': 1.5
    }));
    // Base mounting plate
    g.appendChild(mkSVG('rect', {
      x: -28, y: 18, width: 56, height: 8, rx: 2,
      fill: '#334155', stroke: '#1e293b', 'stroke-width': 1.5
    }));
    // Electric motor block
    g.appendChild(mkSVG('rect', {
      x: 18, y: -14, width: 28, height: 28, rx: 3,
      fill: 'url(#grad-steel)', stroke: '#334155', 'stroke-width': 1.5
    }));
    // Motor cooling fins
    for (let fy = -10; fy <= 10; fy += 5) {
      g.appendChild(mkSVG('line', {
        x1: 22, y1: fy, x2: 42, y2: fy,
        stroke: '#64748b', 'stroke-width': 2
      }));
    }
    // Terminal box
    g.appendChild(mkSVG('rect', {
      x: 24, y: -19, width: 16, height: 5, rx: 1.5,
      fill: '#1e293b', stroke: '#475569', 'stroke-width': 1
    }));
  } else {
    g.appendChild(mkSVG('circle', {
      r: 34, fill: sel ? '#4c1d95' : '#2e1065',
      stroke: sel ? '#c084fc' : '#a855f7', 'stroke-width': 2.5,
    }));
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
}

function drawTank(g, sel) {
  if (state.viewMode === 'industrial') {
    // Structural stand / platform (brown timber/metal stand)
    g.appendChild(mkSVG('rect', {
      x: -28, y: 25, width: 56, height: 7, rx: 1.5,
      fill: '#854d0e', stroke: '#713f12', 'stroke-width': 1.5
    }));
    g.appendChild(mkSVG('line', { x1: -22, y1: 32, x2: -22, y2: 44, stroke: '#854d0e', 'stroke-width': 4 }));
    g.appendChild(mkSVG('line', { x1: 22, y1: 32, x2: 22, y2: 44, stroke: '#854d0e', 'stroke-width': 4 }));
    g.appendChild(mkSVG('line', { x1: -22, y1: 42, x2: 22, y2: 42, stroke: '#854d0e', 'stroke-width': 2.5 }));
    
    // Poly tank cylinder in tan/sand
    g.appendChild(mkSVG('rect', {
      x: -25, y: -35, width: 50, height: 60, rx: 4,
      fill: 'url(#grad-tank)', stroke: sel ? '#f59e0b' : '#b45309', 'stroke-width': 2
    }));
    
    // Horizontal reinforcement hoop rings
    [-20, -6, 8].forEach(yPos => {
      g.appendChild(mkSVG('line', {
        x1: -25, y1: yPos, x2: 25, y2: yPos,
        stroke: '#b45309', 'stroke-width': 1.5, opacity: 0.5
      }));
    });
    
    // Conical roof
    g.appendChild(mkSVG('path', {
      d: 'M -25,-35 Q 0,-48 25,-35 Z',
      fill: 'url(#grad-tank)', stroke: sel ? '#f59e0b' : '#b45309', 'stroke-width': 2
    }));
    
    // Inspection cap / manhole lid
    g.appendChild(mkSVG('ellipse', {
      cx: 0, cy: -45, rx: 11, ry: 4,
      fill: '#92400e', stroke: '#78350f', 'stroke-width': 1.5
    }));
    
    // Bottom outlet connection stub
    g.appendChild(mkSVG('rect', {
      x: 23, y: 12, width: 8, height: 10, rx: 1.5,
      fill: '#475569', stroke: '#334155', 'stroke-width': 1
    }));
  } else {
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
}

function drawJunction(g, sel, node) {
  if (state.viewMode === 'industrial') {
    const connected = state.pipes.filter(p => p.fromNodeId === node.id || p.toNodeId === node.id);
    const d_mm = connected.length > 0 ? Math.max(...connected.map(p => p.props.diameter_mm || 25)) : 25;
    const thickness = getPipeVisualThickness(d_mm);
    const collarThick = thickness + 6;
    const collarLen = 8;
    const r = 16;
    
    // Central hub body
    g.appendChild(mkSVG('circle', {
      r: thickness/2 + 3,
      fill: 'url(#grad-fitting)',
      stroke: sel ? '#f59e0b' : '#475569',
      'stroke-width': 1.5
    }));
    
    if (connected.length >= 2) {
      connected.forEach(pipe => {
        const other = pipe.fromNodeId === node.id ? findNode(pipe.toNodeId) : findNode(pipe.fromNodeId);
        if (!other) return;
        const ang = Math.atan2(other.y - node.y, other.x - node.x);
        const bx = Math.cos(ang) * r;
        const by = Math.sin(ang) * r;
        
        // Branch pipe nub
        g.appendChild(mkSVG('line', {
          x1: 0, y1: 0, x2: bx, y2: by,
          stroke: 'url(#grad-fitting)',
          'stroke-width': thickness,
          'stroke-linecap': 'butt'
        }));
        
        // Socket collar at tip
        const col = mkSVG('rect', {
          x: bx - collarLen/2, y: by - collarThick/2,
          width: collarLen, height: collarThick,
          rx: 2,
          fill: 'url(#grad-fitting)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.5,
          transform: `rotate(${ang * 180 / Math.PI}, ${bx}, ${by})`
        });
        g.appendChild(col);
      });
    } else {
      // Standalone Tee representation: horizontal run + branch down
      g.appendChild(mkSVG('line', { x1: -r, y1: 0, x2: r, y2: 0, stroke: 'url(#grad-fitting)', 'stroke-width': thickness }));
      g.appendChild(mkSVG('line', { x1: 0, y1: 0, x2: 0, y2: r, stroke: 'url(#grad-fitting)', 'stroke-width': thickness }));
      g.appendChild(mkSVG('rect', { x: -r - 4, y: -collarThick/2, width: 6, height: collarThick, rx: 1.5, fill: 'url(#grad-fitting)', stroke: '#475569', 'stroke-width': 1.2 }));
      g.appendChild(mkSVG('rect', { x: r - 2, y: -collarThick/2, width: 6, height: collarThick, rx: 1.5, fill: 'url(#grad-fitting)', stroke: '#475569', 'stroke-width': 1.2 }));
      g.appendChild(mkSVG('rect', { x: -collarThick/2, y: r - 2, width: collarThick, height: 6, rx: 1.5, fill: 'url(#grad-fitting)', stroke: '#475569', 'stroke-width': 1.2 }));
    }
  } else {
    g.appendChild(mkSVG('circle', {
      r: 14, fill: sel ? '#334155' : '#1e293b',
      stroke: sel ? '#f59e0b' : '#64748b', 'stroke-width': 2,
    }));
    g.appendChild(svgText(0, 4, 'J', 11, '#94a3b8', 'bold'));
  }
}

function drawDischarge(g, sel) {
  if (state.viewMode === 'industrial') {
    // Bibcock Faucet with chrome body, red lever handle, and blue water droplet
    // Wall mount / inlet connection
    g.appendChild(mkSVG('rect', {
      x: -16, y: -7, width: 6, height: 14, rx: 1.5,
      fill: '#64748b', stroke: '#334155', 'stroke-width': 1
    }));
    // Tap body
    g.appendChild(mkSVG('rect', {
      x: -10, y: -5, width: 16, height: 10, rx: 2,
      fill: 'url(#grad-faucet)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.5
    }));
    // Vertical bonnet / stem
    g.appendChild(mkSVG('rect', {
      x: -2, y: -13, width: 5, height: 8, rx: 1,
      fill: '#64748b', stroke: '#334155', 'stroke-width': 1
    }));
    // Red lever handle on top
    g.appendChild(mkSVG('rect', {
      x: -14, y: -16, width: 22, height: 4, rx: 2,
      fill: '#ef4444', stroke: '#991b1b', 'stroke-width': 1
    }));
    g.appendChild(mkSVG('circle', { cx: 0, cy: -14, r: 2, fill: '#cbd5e1' }));
    // Downward curving spout
    g.appendChild(mkSVG('path', {
      d: 'M 4,-2 Q 10,2 10,12 L 5,12 Q 5,4 2,2 Z',
      fill: 'url(#grad-faucet)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.2
    }));
    // Aerator nozzle tip
    g.appendChild(mkSVG('rect', {
      x: 4.5, y: 11, width: 6, height: 3, rx: 1,
      fill: '#94a3b8', stroke: '#475569', 'stroke-width': 1
    }));
    // Falling blue water droplet (💧)
    g.appendChild(mkSVG('path', {
      d: 'M 7.5,18 C 5,23 4,26 4,28 A 3.5,3.5 0 0,0 11,28 C 11,26 10,23 7.5,18 Z',
      fill: 'url(#grad-droplet)', stroke: '#0284c7', 'stroke-width': 0.8
    }));
  } else {
    g.appendChild(mkSVG('polygon', {
      points: '-15,-10 15,-10 20,15 -20,15',
      fill: sel ? '#164e63' : '#083344',
      stroke: sel ? '#67e8f9' : '#06b6d4', 'stroke-width': 2,
    }));
    g.appendChild(mkSVG('path', { d: 'M-10,15 Q0,25 10,15', stroke: '#38bdf8', 'stroke-width': 2, fill: 'none' }));
    g.appendChild(mkSVG('path', { d: 'M-5,15 Q0,30 5,15', stroke: '#7dd3fc', 'stroke-width': 2, fill: 'none' }));
    g.appendChild(svgText(0, -18, 'D', 13, '#cffafe', 'bold'));
  }
}

function drawValveNode(g, sel) {
  if (state.viewMode === 'industrial') {
    // Ball Valve: dark cylindrical body with blue lever handle
    // Valve body
    g.appendChild(mkSVG('rect', {
      x: -16, y: -8, width: 32, height: 16, rx: 3,
      fill: '#1e293b', stroke: sel ? '#f59e0b' : '#0f172a', 'stroke-width': 1.5
    }));
    // Central ball housing
    g.appendChild(mkSVG('circle', {
      r: 9, fill: '#0f172a', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 1.5
    }));
    // Connection collars on both ends
    g.appendChild(mkSVG('rect', {
      x: -20, y: -10, width: 5, height: 20, rx: 1.5,
      fill: '#334155', stroke: '#1e293b', 'stroke-width': 1
    }));
    g.appendChild(mkSVG('rect', {
      x: 15, y: -10, width: 5, height: 20, rx: 1.5,
      fill: '#334155', stroke: '#1e293b', 'stroke-width': 1
    }));
    // Upright stem
    g.appendChild(mkSVG('rect', {
      x: -3, y: -17, width: 6, height: 9, rx: 1,
      fill: '#475569', stroke: '#1e293b', 'stroke-width': 1
    }));
    // Blue lever handle
    g.appendChild(mkSVG('path', {
      d: 'M -4,-17 L 22,-22 L 24,-18 L -2,-14 Z',
      fill: 'url(#grad-valve-lever)', stroke: '#1d4ed8', 'stroke-width': 1
    }));
    // Grip tip on lever
    g.appendChild(mkSVG('circle', {
      cx: 23, cy: -20, r: 3.5,
      fill: '#0284c7', stroke: '#1e40af', 'stroke-width': 1
    }));
    // Center pivot bolt
    g.appendChild(mkSVG('circle', {
      cx: 0, cy: -15.5, r: 2.5,
      fill: '#cbd5e1', stroke: '#475569', 'stroke-width': 1
    }));
  } else {
    g.appendChild(mkSVG('polygon', {
      points: '-18,-15 18,15 18,-15 -18,15',
      fill: sel ? '#7f1d1d' : '#450a0a',
      stroke: sel ? '#fca5a5' : '#ef4444', 'stroke-width': 2.5,
    }));
    g.appendChild(mkSVG('circle', { r: 6, fill: '#ef4444' }));
  }
}

function drawElbowNode(g, sel, node) {
  const connected = state.pipes.filter(p => p.fromNodeId === node.id || p.toNodeId === node.id);
  
  if (state.viewMode === 'industrial') {
    if (connected.length === 2) {
      const p1 = connected[0];
      const p2 = connected[1];
      const o1 = p1.fromNodeId === node.id ? findNode(p1.toNodeId) : findNode(p1.fromNodeId);
      const o2 = p2.fromNodeId === node.id ? findNode(p2.toNodeId) : findNode(p2.fromNodeId);
      
      if (o1 && o2) {
        const a1 = Math.atan2(o1.y - node.y, o1.x - node.x);
        const a2 = Math.atan2(o2.y - node.y, o2.x - node.x);
        const r = 18;
        const x1 = Math.cos(a1) * r;
        const y1 = Math.sin(a1) * r;
        const x2 = Math.cos(a2) * r;
        const y2 = Math.sin(a2) * r;
        
        const d_mm = Math.max(p1.props.diameter_mm || 25, p2.props.diameter_mm || 25);
        const thickness = getPipeVisualThickness(d_mm);
        const collarThick = thickness + 6;
        const collarLen = 8;
        
        // Arc sweep
        const cp = (x1 * y2) - (x2 * y1);
        const sweep = cp > 0 ? 1 : 0;
        const d = `M ${x1},${y1} A ${r},${r} 0 0,${sweep} ${x2},${y2}`;
        
        // Fitting body
        g.appendChild(mkSVG('path', {
          d, fill: 'none', stroke: sel ? '#f59e0b' : '#475569',
          'stroke-width': thickness + 2, 'stroke-linecap': 'round'
        }));
        g.appendChild(mkSVG('path', {
          d, fill: 'none', stroke: 'url(#grad-fitting)',
          'stroke-width': thickness, 'stroke-linecap': 'round'
        }));
        
        // Socket Collar 1
        const col1 = mkSVG('rect', {
          x: x1 - collarLen/2, y: y1 - collarThick/2,
          width: collarLen, height: collarThick,
          rx: 2,
          fill: 'url(#grad-fitting)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.5,
          transform: `rotate(${a1 * 180 / Math.PI}, ${x1}, ${y1})`
        });
        g.appendChild(col1);
        
        // Socket Collar 2
        const col2 = mkSVG('rect', {
          x: x2 - collarLen/2, y: y2 - collarThick/2,
          width: collarLen, height: collarThick,
          rx: 2,
          fill: 'url(#grad-fitting)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.5,
          transform: `rotate(${a2 * 180 / Math.PI}, ${x2}, ${y2})`
        });
        g.appendChild(col2);
        return;
      }
    }
    
    // Standalone / default 90° slip elbow
    const r = 18;
    const thickness = 14;
    const collarThick = thickness + 6;
    const d = `M 0,-18 A 18,18 0 0,1 18,0`;
    g.appendChild(mkSVG('path', {
      d, fill: 'none', stroke: sel ? '#f59e0b' : '#475569',
      'stroke-width': thickness + 2, 'stroke-linecap': 'round'
    }));
    g.appendChild(mkSVG('path', {
      d, fill: 'none', stroke: 'url(#grad-fitting)',
      'stroke-width': thickness, 'stroke-linecap': 'round'
    }));
    // Collars
    g.appendChild(mkSVG('rect', {
      x: -collarThick/2, y: -22, width: collarThick, height: 8, rx: 2,
      fill: 'url(#grad-fitting)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.5
    }));
    g.appendChild(mkSVG('rect', {
      x: 14, y: -collarThick/2, width: 8, height: collarThick, rx: 2,
      fill: 'url(#grad-fitting)', stroke: sel ? '#f59e0b' : '#475569', 'stroke-width': 1.5
    }));
  } else {
    // Schematic mode
    if (connected.length === 2) {
      const p1 = connected[0];
      const p2 = connected[1];
      const o1 = p1.fromNodeId === node.id ? findNode(p1.toNodeId) : findNode(p1.fromNodeId);
      const o2 = p2.fromNodeId === node.id ? findNode(p2.toNodeId) : findNode(p2.fromNodeId);
      if (o1 && o2) {
        const a1 = Math.atan2(o1.y - node.y, o1.x - node.x);
        const a2 = Math.atan2(o2.y - node.y, o2.x - node.x);
        const r = 16;
        const x1 = Math.cos(a1) * r;
        const y1 = Math.sin(a1) * r;
        const x2 = Math.cos(a2) * r;
        const y2 = Math.sin(a2) * r;
        const cp = (x1 * y2) - (x2 * y1);
        const sweep = cp > 0 ? 1 : 0;
        const d = `M ${x1},${y1} A ${r},${r} 0 0,${sweep} ${x2},${y2}`;
        g.appendChild(mkSVG('path', { d, fill: 'none', stroke: sel ? '#f9a8d4' : '#ec4899', 'stroke-width': 4, 'stroke-linecap': 'round' }));
      }
    } else {
      g.appendChild(mkSVG('circle', {
        r: 16, fill: 'none', stroke: sel ? '#f9a8d4' : '#ec4899', 'stroke-width': 4,
        'stroke-dasharray': '50 100'
      }));
    }
    g.appendChild(svgText(0, 4, 'E', 11, '#fbcfe8', 'bold'));
  }
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
  
  const fittingDiv = document.getElementById('np-fitting-fields');
  if (fittingDiv) {
    fittingDiv.style.display = (node.type === 'valve' || node.type === 'elbow') ? '' : 'none';
    if (node.type === 'valve' || node.type === 'elbow') {
      setVal('np-fitting-key', node.props.fitting_key);
    }
  }
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
    'add-discharge':   'Place Faucet / Discharge — click on canvas',
    'add-valve':       'Place Ball Valve — click on canvas',
    'add-elbow':       'Place 90° Elbow Fitting — click on canvas',
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
function onNodeFittingChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node && (node.type === 'valve' || node.type === 'elbow')) {
    node.props.fitting_key = document.getElementById('np-fitting-key').value;
  }
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
    pipes: state.pipes.map(pipe => {
      // Collect fittings from the pipe and the adjacent nodes (valves, elbows)
      const allFittings = [...(pipe.props.fittings || [])];
      
      const toNode = findNode(pipe.toNodeId);
      if (toNode && toNode.props.fitting_key) {
        allFittings.push(toNode.props.fitting_key);
      }
      
      const fromNode = findNode(pipe.fromNodeId);
      // Optional: also grab fitting from start node if it's a fitting (though normally flow goes into it, we don't want to double count).
      // If we only count the destination node, it prevents double counting when pipes are chained: NodeA -> Elbow -> NodeB
      // The elbow applies to the pipe arriving at it.
      
      return {
        id:            pipe.id,
        label:         pipe.props.label || pipe.id,
        diameter_mm:   pipe.props.diameter_mm,
        length_m:      pipe.props.length_m,
        material:      pipe.props.material,
        elev_change_m: pipe.props.elev_change_m,
        fittings:      allFittings,
      };
    }),
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

  // Inject Gradients for Industrial View
  const defs = mkSVG('defs', {});
  defs.innerHTML = `
    <!-- Water Pipe Gradient (Vibrant Blue with 3D cylindrical specular highlight) -->
    <linearGradient id="grad-water-pipe" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="25%" stop-color="#0ea5e9" />
      <stop offset="60%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>
    <!-- PVC / PPR Slip Fitting Gradient (Clean Grey Fitting) -->
    <linearGradient id="grad-fitting" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#f8fafc" />
      <stop offset="25%" stop-color="#e2e8f0" />
      <stop offset="65%" stop-color="#cbd5e1" />
      <stop offset="100%" stop-color="#94a3b8" />
    </linearGradient>
    <!-- Poly Water Tank Gradient (Tan / Sand Poly) -->
    <linearGradient id="grad-tank" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#d4b996" />
      <stop offset="20%" stop-color="#fdf4e3" />
      <stop offset="55%" stop-color="#ecdcc2" />
      <stop offset="100%" stop-color="#c4a57b" />
    </linearGradient>
    <!-- Ball Valve Blue Lever Handle -->
    <linearGradient id="grad-valve-lever" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="45%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>
    <!-- Chrome Faucet Tap Body -->
    <linearGradient id="grad-faucet" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="35%" stop-color="#e2e8f0" />
      <stop offset="70%" stop-color="#94a3b8" />
      <stop offset="100%" stop-color="#64748b" />
    </linearGradient>
    <!-- Falling Blue Water Droplet -->
    <radialGradient id="grad-droplet" cx="35%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#bae6fd" />
      <stop offset="50%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#0284c7" />
    </radialGradient>
    <!-- Steel Pipe Gradient -->
    <linearGradient id="grad-steel" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#94a3b8" />
      <stop offset="20%" stop-color="#cbd5e1" />
      <stop offset="50%" stop-color="#64748b" />
      <stop offset="80%" stop-color="#334155" />
      <stop offset="100%" stop-color="#1e293b" />
    </linearGradient>
    <!-- PVC White Gradient -->
    <linearGradient id="grad-pvc" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#f8fafc" />
      <stop offset="30%" stop-color="#ffffff" />
      <stop offset="70%" stop-color="#e2e8f0" />
      <stop offset="100%" stop-color="#cbd5e1" />
    </linearGradient>
    <!-- HDPE Pipe Gradient -->
    <linearGradient id="grad-hdpe" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#334155" />
      <stop offset="30%" stop-color="#475569" />
      <stop offset="80%" stop-color="#0f172a" />
      <stop offset="100%" stop-color="#020617" />
    </linearGradient>
    <!-- Copper/Cast Iron Gradient -->
    <linearGradient id="grad-iron" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#78350f" />
      <stop offset="30%" stop-color="#b45309" />
      <stop offset="70%" stop-color="#451a03" />
      <stop offset="100%" stop-color="#210800" />
    </linearGradient>
  `;
  svgEl.appendChild(defs);

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
  document.getElementById('btn-select')?.addEventListener('click', () => setMode('select'));
  document.getElementById('btn-connect')?.addEventListener('click', () => setMode('connect'));
  document.getElementById('btn-add-reservoir')?.addEventListener('click', () => setMode('add-reservoir'));
  document.getElementById('btn-add-pump')?.addEventListener('click', () => setMode('add-pump'));
  document.getElementById('btn-add-tank')?.addEventListener('click', () => setMode('add-tank'));
  document.getElementById('btn-add-junction')?.addEventListener('click', () => setMode('add-junction'));
  document.getElementById('btn-add-discharge')?.addEventListener('click', () => setMode('add-discharge'));
  document.getElementById('btn-add-valve')?.addEventListener('click', () => setMode('add-valve'));
  document.getElementById('btn-add-elbow')?.addEventListener('click', () => setMode('add-elbow'));
  document.getElementById('btn-delete')?.addEventListener('click', deleteSelected);
  document.getElementById('btn-clear')?.addEventListener('click', clearCanvas);
  document.getElementById('btn-export')?.addEventListener('click', exportNetwork);
  
  // View Toggle
  document.getElementById('btn-view-schematic')?.addEventListener('click', () => {
    state.viewMode = 'schematic';
    localStorage.setItem('pmpro_view_mode', 'schematic');
    document.getElementById('btn-view-schematic')?.classList.add('active-tool');
    document.getElementById('btn-view-industrial')?.classList.remove('active-tool');
    renderAll();
  });
  document.getElementById('btn-view-industrial')?.addEventListener('click', () => {
    state.viewMode = 'industrial';
    localStorage.setItem('pmpro_view_mode', 'industrial');
    document.getElementById('btn-view-industrial')?.classList.add('active-tool');
    document.getElementById('btn-view-schematic')?.classList.remove('active-tool');
    renderAll();
  });

  // Canvas Theme Toggle (Dark / Light CAD)
  document.getElementById('btn-theme-toggle')?.addEventListener('click', () => {
    state.canvasTheme = state.canvasTheme === 'light' ? 'dark' : 'light';
    localStorage.setItem('pmpro_canvas_theme', state.canvasTheme);
    const wrap = document.getElementById('pn-canvas-wrap');
    if (state.canvasTheme === 'light') {
      wrap?.classList.add('pn-light-theme');
      document.getElementById('btn-theme-toggle')?.classList.add('active-tool');
    } else {
      wrap?.classList.remove('pn-light-theme');
      document.getElementById('btn-theme-toggle')?.classList.remove('active-tool');
    }
    renderAll();
  });

  // Toggle Legend
  document.getElementById('btn-toggle-legend')?.addEventListener('click', () => {
    const leg = document.getElementById('pn-legend-overlay');
    if (leg) {
      const isHidden = leg.style.display === 'none';
      leg.style.display = isHidden ? 'block' : 'none';
      document.getElementById('btn-toggle-legend')?.classList.toggle('active-tool', isHidden);
    }
  });

  // Restore saved theme & viewMode
  const savedTheme = localStorage.getItem('pmpro_canvas_theme') || 'dark';
  state.canvasTheme = savedTheme;
  if (savedTheme === 'light') {
    document.getElementById('pn-canvas-wrap')?.classList.add('pn-light-theme');
    document.getElementById('btn-theme-toggle')?.classList.add('active-tool');
  }
  const savedViewMode = localStorage.getItem('pmpro_view_mode') || 'industrial';
  state.viewMode = savedViewMode;
  if (state.viewMode === 'industrial') {
    document.getElementById('btn-view-industrial')?.classList.add('active-tool');
    document.getElementById('btn-view-schematic')?.classList.remove('active-tool');
  } else {
    document.getElementById('btn-view-schematic')?.classList.add('active-tool');
    document.getElementById('btn-view-industrial')?.classList.remove('active-tool');
  }
  
  const importInput = document.getElementById('import-file-input');
  document.getElementById('btn-import')?.addEventListener('click', () => importInput?.click());
  importInput?.addEventListener('change', e => {
    if (e.target.files[0]) importNetwork(e.target.files[0]);
    e.target.value = '';
  });
  
  document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
    state.zoom = Math.min(3, state.zoom * 1.2); applyTransform();
  });
  document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
    state.zoom = Math.max(0.2, state.zoom / 1.2); applyTransform();
  });
  document.getElementById('btn-zoom-reset')?.addEventListener('click', () => {
    state.zoom = 1; state.pan = { x: 0, y: 0 }; applyTransform();
  });

  document.getElementById('pn-calc-btn')?.addEventListener('click', runCalculation);

  // Node property inputs
  document.getElementById('np-label')?.addEventListener('input', onNodeLabelChange);
  document.getElementById('np-elev')?.addEventListener('change', onNodeElevChange);
  document.getElementById('np-flow')?.addEventListener('change', onPumpFlowChange);
  document.getElementById('np-fitting-key')?.addEventListener('change', onNodeFittingChange);

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
  const nFitSel = document.getElementById('np-fitting-key');
  FITTINGS.forEach(f => {
    // For pipe checkbox list
    if (fList) {
      const lbl = document.createElement('label');
      lbl.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:5px;cursor:pointer;font-size:12px;color:#94a3b8;';
      lbl.innerHTML = `<input type="checkbox" class="pp-fitting-cb" value="${f.key}" style="accent-color:#58a6ff;cursor:pointer;flex-shrink:0;">
        <span>${f.label} <span style="color:#475569">(K=${f.K})</span></span>`;
      fList.appendChild(lbl);
    }
    
    // For node fitting select dropdown
    if (nFitSel) {
      const opt = document.createElement('option');
      opt.value = f.key; opt.textContent = `${f.label} (K=${f.K})`;
      nFitSel.appendChild(opt);
    }
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

/** Pre-load a comprehensive demo: Water Distribution System matching the reference diagram */
function loadDemoNetwork() {
  // ── Nodes ──────────────────────────────────────────────────────────────
  //
  //  Tank → Pump → Elbow → vertical rise → Elbow → horizontal main
  //  Main splits via Tees into left and right branches with elbows,
  //  valves, and faucet endpoints at different pipe sizes.
  //
  state.nodes = [
    // Source
    { id: 'N-1',  type: 'tank',      x: 150,  y: 550,  props: { label: 'Water Tank',    elevation_m: 0 } },
    { id: 'N-2',  type: 'pump',      x: 350,  y: 550,  props: { label: 'Pump 1',        flow_m3h: 15, elevation_m: 0 } },
    // Vertical rise
    { id: 'N-3',  type: 'elbow',     x: 500,  y: 550,  props: { label: 'E1',  elevation_m: 0,  fitting_key: 'elbow_90_standard' } },
    { id: 'N-4',  type: 'elbow',     x: 500,  y: 200,  props: { label: 'E2',  elevation_m: 7,  fitting_key: 'elbow_90_standard' } },
    // Horizontal main tee
    { id: 'N-5',  type: 'junction',  x: 650,  y: 200,  props: { label: 'Main Tee',      elevation_m: 7 } },
    // ── Left branch ──
    { id: 'N-6',  type: 'elbow',     x: 650,  y: 350,  props: { label: 'E3',  elevation_m: 4,  fitting_key: 'elbow_90_standard' } },
    { id: 'N-7',  type: 'junction',  x: 450,  y: 350,  props: { label: 'Tee L1',        elevation_m: 4 } },
    { id: 'N-8',  type: 'valve',     x: 300,  y: 350,  props: { label: 'Valve L1',      elevation_m: 4, fitting_key: 'ball_valve_open' } },
    { id: 'N-9',  type: 'discharge', x: 200,  y: 350,  props: { label: 'Faucet L1',     elevation_m: 4 } },
    { id: 'N-10', type: 'elbow',     x: 450,  y: 450,  props: { label: 'E4',  elevation_m: 2,  fitting_key: 'elbow_90_standard' } },
    { id: 'N-11', type: 'valve',     x: 300,  y: 450,  props: { label: 'Valve L2',      elevation_m: 2, fitting_key: 'ball_valve_open' } },
    { id: 'N-12', type: 'discharge', x: 200,  y: 450,  props: { label: 'Faucet L2',     elevation_m: 2 } },
    // ── Right branch ──
    { id: 'N-13', type: 'elbow',     x: 850,  y: 200,  props: { label: 'E5',  elevation_m: 7,  fitting_key: 'elbow_90_standard' } },
    { id: 'N-14', type: 'junction',  x: 850,  y: 350,  props: { label: 'Tee R1',        elevation_m: 4 } },
    { id: 'N-15', type: 'valve',     x: 1000, y: 350,  props: { label: 'Valve R1',      elevation_m: 4, fitting_key: 'ball_valve_open' } },
    { id: 'N-16', type: 'discharge', x: 1100, y: 350,  props: { label: 'Faucet R1',     elevation_m: 4 } },
    { id: 'N-17', type: 'elbow',     x: 850,  y: 450,  props: { label: 'E6',  elevation_m: 2,  fitting_key: 'elbow_90_standard' } },
    { id: 'N-18', type: 'valve',     x: 1000, y: 450,  props: { label: 'Valve R2',      elevation_m: 2, fitting_key: 'ball_valve_open' } },
    { id: 'N-19', type: 'discharge', x: 1100, y: 450,  props: { label: 'Faucet R2',     elevation_m: 2 } },
  ];

  // ── Pipes ──────────────────────────────────────────────────────────────
  state.pipes = [
    // Tank → Pump (1" main)
    { id: 'P-1',  fromNodeId: 'N-1',  toNodeId: 'N-2',
      props: { label: 'Suction',       diameter_mm: 25, length_m: 4,
               material: 'pvc', elev_change_m: 0,
               fittings: ['entry_rounded'] } },
    // Pump → Elbow E1 (1" main)
    { id: 'P-2',  fromNodeId: 'N-2',  toNodeId: 'N-3',
      props: { label: 'Discharge',     diameter_mm: 25, length_m: 3,
               material: 'pvc', elev_change_m: 0,
               fittings: ['check_valve_swing'] } },
    // E1 → E2 vertical riser (1" main)
    { id: 'P-3',  fromNodeId: 'N-3',  toNodeId: 'N-4',
      props: { label: 'Riser',         diameter_mm: 25, length_m: 7,
               material: 'pvc', elev_change_m: 7,
               fittings: [] } },
    // E2 → Main Tee (1" main)
    { id: 'P-4',  fromNodeId: 'N-4',  toNodeId: 'N-5',
      props: { label: 'Main Horiz',    diameter_mm: 25, length_m: 3,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },

    // ── Left branch ──
    // Main Tee → Elbow E3 down (3/4" distribution)
    { id: 'P-5',  fromNodeId: 'N-5',  toNodeId: 'N-6',
      props: { label: 'Left Drop',     diameter_mm: 20, length_m: 3,
               material: 'pvc', elev_change_m: -3,
               fittings: ['reducer_gradual'] } },
    // E3 → Tee L1 left (3/4" distribution)
    { id: 'P-6',  fromNodeId: 'N-6',  toNodeId: 'N-7',
      props: { label: 'Left Dist',     diameter_mm: 20, length_m: 4,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },
    // Tee L1 → Valve L1 (1/2" branch)
    { id: 'P-7',  fromNodeId: 'N-7',  toNodeId: 'N-8',
      props: { label: 'Branch L1',     diameter_mm: 15, length_m: 3,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },
    // Valve L1 → Faucet L1 (1/2" branch)
    { id: 'P-8',  fromNodeId: 'N-8',  toNodeId: 'N-9',
      props: { label: 'To Faucet L1',  diameter_mm: 15, length_m: 2,
               material: 'pvc', elev_change_m: 0,
               fittings: ['exit_abrupt'] } },
    // Tee L1 → E4 down (3/4" distribution)
    { id: 'P-9',  fromNodeId: 'N-7',  toNodeId: 'N-10',
      props: { label: 'Left Dist 2',   diameter_mm: 20, length_m: 2,
               material: 'pvc', elev_change_m: -2,
               fittings: [] } },
    // E4 → Valve L2 (1/2" branch)
    { id: 'P-10', fromNodeId: 'N-10', toNodeId: 'N-11',
      props: { label: 'Branch L2',     diameter_mm: 15, length_m: 3,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },
    // Valve L2 → Faucet L2 (1/2" branch)
    { id: 'P-11', fromNodeId: 'N-11', toNodeId: 'N-12',
      props: { label: 'To Faucet L2',  diameter_mm: 15, length_m: 2,
               material: 'pvc', elev_change_m: 0,
               fittings: ['exit_abrupt'] } },

    // ── Right branch ──
    // Main Tee → Elbow E5 right (3/4" distribution)
    { id: 'P-12', fromNodeId: 'N-5',  toNodeId: 'N-13',
      props: { label: 'Right Horiz',   diameter_mm: 20, length_m: 4,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },
    // E5 → Tee R1 down (3/4" distribution)
    { id: 'P-13', fromNodeId: 'N-13', toNodeId: 'N-14',
      props: { label: 'Right Drop',    diameter_mm: 20, length_m: 3,
               material: 'pvc', elev_change_m: -3,
               fittings: [] } },
    // Tee R1 → Valve R1 (1/2" branch)
    { id: 'P-14', fromNodeId: 'N-14', toNodeId: 'N-15',
      props: { label: 'Branch R1',     diameter_mm: 15, length_m: 3,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },
    // Valve R1 → Faucet R1 (1/2" branch)
    { id: 'P-15', fromNodeId: 'N-15', toNodeId: 'N-16',
      props: { label: 'To Faucet R1',  diameter_mm: 15, length_m: 2,
               material: 'pvc', elev_change_m: 0,
               fittings: ['exit_abrupt'] } },
    // Tee R1 → E6 down (3/4" distribution)
    { id: 'P-16', fromNodeId: 'N-14', toNodeId: 'N-17',
      props: { label: 'Right Dist 2',  diameter_mm: 20, length_m: 2,
               material: 'pvc', elev_change_m: -2,
               fittings: [] } },
    // E6 → Valve R2 (1/2" branch)
    { id: 'P-17', fromNodeId: 'N-17', toNodeId: 'N-18',
      props: { label: 'Branch R2',     diameter_mm: 15, length_m: 3,
               material: 'pvc', elev_change_m: 0,
               fittings: [] } },
    // Valve R2 → Faucet R2 (1/2" branch)
    { id: 'P-18', fromNodeId: 'N-18', toNodeId: 'N-19',
      props: { label: 'To Faucet R2',  diameter_mm: 15, length_m: 2,
               material: 'pvc', elev_change_m: 0,
               fittings: ['exit_abrupt'] } },
  ];

  state.nextId = 30;
  renderAll();
}

document.addEventListener('DOMContentLoaded', init);
