/**
 * pipe_network.js — Interactive Pipe Network System Designer
 * with Orthogonal Routing & Integrated Elbow Bends
 *
 * Key improvements over the previous version:
 *  - Pipes route orthogonally (horizontal-then-vertical or vertical-then-horizontal)
 *  - Elbows are drawn as smooth rounded corners integrated into the pipe path
 *  - Valve nodes render as inline symbols on the pipe (not standalone circles)
 *  - Supports both "schematic" (thin lines) and "industrial" (thick pipes) views
 *  - Explicit elbow nodes act as routing waypoints (no separate bubble)
 */

'use strict';

// ============================================================================
// CONSTANTS
// ============================================================================

const GRID = 50;
const ELBOW_RADIUS = 14;

const MATERIALS = [
  { key: 'commercial_steel', label: 'Commercial Steel  (e = 0.046 mm)' },
  { key: 'galvanised_steel', label: 'Galvanised Steel  (e = 0.150 mm)' },
  { key: 'cast_iron', label: 'Cast Iron         (e = 0.260 mm)' },
  { key: 'pvc', label: 'PVC / Plastic     (e = 0.002 mm)' },
  { key: 'hdpe', label: 'HDPE              (e = 0.007 mm)' },
  { key: 'stainless_steel', label: 'Stainless Steel   (e = 0.015 mm)' },
  { key: 'concrete', label: 'Concrete          (e = 1.000 mm)' },
  { key: 'smooth', label: 'Smooth / Drawn    (e = 0.002 mm)' },
];

const FITTINGS = [
  { key: 'elbow_90_standard', label: '90 Elbow (Standard)', K: 0.90 },
  { key: 'elbow_90_long_radius', label: '90 Elbow (Long Radius)', K: 0.60 },
  { key: 'elbow_45', label: '45 Elbow', K: 0.40 },
  { key: 'gate_valve_open', label: 'Gate Valve (Open)', K: 0.20 },
  { key: 'gate_valve_half', label: 'Gate Valve (50% Open)', K: 5.60 },
  { key: 'globe_valve_open', label: 'Globe Valve (Open)', K: 10.0 },
  { key: 'check_valve_swing', label: 'Check Valve (Swing)', K: 2.50 },
  { key: 'check_valve_ball', label: 'Check Valve (Ball)', K: 4.50 },
  { key: 'ball_valve_open', label: 'Ball Valve (Open)', K: 0.05 },
  { key: 'butterfly_valve_open', label: 'Butterfly Valve (Open)', K: 0.30 },
  { key: 'tee_run_through', label: 'Tee (Run Through)', K: 0.40 },
  { key: 'tee_branch_flow', label: 'Tee (Branch Flow)', K: 1.80 },
  { key: 'entry_sharp', label: 'Pipe Entry (Sharp)', K: 0.50 },
  { key: 'entry_rounded', label: 'Pipe Entry (Rounded)', K: 0.20 },
  { key: 'exit_abrupt', label: 'Pipe Exit (Abrupt)', K: 1.00 },
  { key: 'reducer_gradual', label: 'Reducer (Gradual)', K: 0.10 },
  { key: 'reducer_sudden', label: 'Reducer (Sudden)', K: 0.50 },
  { key: 'expander_gradual', label: 'Expander (Gradual)', K: 0.30 },
];

// ============================================================================
// STATE
// ============================================================================

const state = {
  nodes: [],
  pipes: [],
  selected: null,
  mode: 'select',
  drawingPipe: null,
  nextId: 1,
  pan: { x: 0, y: 0 },
  zoom: 1.0,
  panDrag: null,
  nodeDrag: null,
  viewMode: 'schematic',
};

let svgEl, nodesGroup, pipesGroup, draftPipeLine;

// ============================================================================
// UTILITIES
// ============================================================================

function newId(prefix) { return `${prefix}-${state.nextId++}`; }
function snap(v) { return Math.round(v / GRID) * GRID; }
function findNode(id) { return state.nodes.find(n => n.id === id); }
function findPipe(id) { return state.pipes.find(p => p.id === id); }

function toSVG(e) {
  const r = svgEl.getBoundingClientRect();
  return {
    x: (e.clientX - r.left - state.pan.x) / state.zoom,
    y: (e.clientY - r.top - state.pan.y) / state.zoom,
  };
}

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

/** Radius of the "connection halo" around each node — used to clip pipe ends. */
function getNodeRadius(node, viewMode) {
  if (!node) return 0;
  if (viewMode === 'industrial') {
    switch (node.type) {
      case 'elbow': return 4;
      case 'valve': return 12;
      case 'pump': return 24;
      case 'junction': return 10;
      case 'tank': return 30;
      case 'reservoir': return 40;
      case 'discharge': return 15;
      default: return 0;
    }
  } else {
    switch (node.type) {
      case 'elbow': return 3;
      case 'valve': return 10;
      case 'pump': return 34;
      case 'junction': return 9;
      case 'tank': return 28;
      case 'reservoir': return 40;
      case 'discharge': return 15;
      default: return 0;
    }
  }
}

function defaultNodeProps(type, count) {
  const lbl = `${type.charAt(0).toUpperCase()}${type.slice(1)} ${count + 1}`;
  switch (type) {
    case 'reservoir': return { label: lbl, elevation_m: 0 };
    case 'pump': return { label: lbl, flow_m3h: 10, elevation_m: 0 };
    case 'tank': return { label: lbl, elevation_m: 0 };
    case 'junction': return { label: lbl, elevation_m: 0 };
    case 'discharge': return { label: lbl, elevation_m: 0 };
    case 'valve': return { label: lbl, elevation_m: 0, fitting_key: 'gate_valve_open' };
    case 'elbow': return { label: lbl, elevation_m: 0, fitting_key: 'elbow_90_standard' };
    default: return { label: lbl };
  }
}

function defaultPipeProps(id) {
  return {
    label: id,
    diameter_mm: 100,
    length_m: 10.0,
    material: 'commercial_steel',
    elev_change_m: 0.0,
    fittings: [],
    routing: 'auto',   // 'auto' | 'straight' | 'orthogonal'
  };
}

// ============================================================================
// ORTHOGONAL ROUTING
// ============================================================================

/**
 * Build an SVG path 'd' string for an orthogonal pipe run between two points.
 * Uses horizontal-first routing with a rounded corner.
 */
function buildOrthogonalPath(x1, y1, x2, y2, radius) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const adx = Math.abs(dx);
  const ady = Math.abs(dy);

  // Nearly aligned → straight line
  if (adx < 2 || ady < 2) {
    return `M ${x1},${y1} L ${x2},${y2}`;
  }

  // Horizontal-first: go H to (x2, y1), then V to (x2, y2)
  const r = Math.min(radius, adx / 2, ady / 2);
  const signX = Math.sign(dx);
  const signY = Math.sign(dy);

  const cx = x2 - signX * r;   // corner start x
  const cy = y1;                // corner start y
  const ex = x2;                // corner end x
  const ey = y1 + signY * r;    // corner end y

  // Sweep flag: for horizontal-first routing, arc is clockwise if signX===signY
  const sweep = (signX === signY) ? 1 : 0;

  return `M ${x1},${y1} L ${cx},${cy} A ${r},${r} 0 0 ${sweep} ${ex},${ey} L ${x2},${y2}`;
}

/**
 * Same as buildOrthogonalPath but routes vertical-first (used when the
 * destination is directly below/above with an offset in X).
 */
function buildOrthogonalPathV(x1, y1, x2, y2, radius) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const adx = Math.abs(dx);
  const ady = Math.abs(dy);

  if (adx < 2 || ady < 2) {
    return `M ${x1},${y1} L ${x2},${y2}`;
  }

  const r = Math.min(radius, adx / 2, ady / 2);
  const signX = Math.sign(dx);
  const signY = Math.sign(dy);

  const cx = x1;
  const cy = y2 - signY * r;
  const ex = x1 + signX * r;
  const ey = y2;

  const sweep = (signX === signY) ? 0 : 1;

  return `M ${x1},${y1} L ${cx},${cy} A ${r},${r} 0 0 ${sweep} ${ex},${ey} L ${x2},${y2}`;
}

/**
 * Compute midpoint coordinates along an orthogonal path (used for labels/arrows).
 */
function orthogonalMidpoint(x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const adx = Math.abs(dx);
  const ady = Math.abs(dy);

  if (adx < 2 || ady < 2) {
    return { x: (x1 + x2) / 2, y: (y1 + y2) / 2, angle: Math.atan2(dy, dx) * 180 / Math.PI };
  }

  // Total path length ≈ |dx| + |dy|
  const totalLen = adx + ady;
  const half = totalLen / 2;

  if (half <= adx) {
    // Midpoint is on the horizontal segment
    const signX = Math.sign(dx);
    return { x: x1 + signX * half, y: y1, angle: signX > 0 ? 0 : 180 };
  } else {
    // Midpoint is on the vertical segment
    const rem = half - adx;
    const signY = Math.sign(dy);
    return { x: x2, y: y1 + signY * rem, angle: signY > 0 ? 90 : -90 };
  }
}

// ============================================================================
// LOCAL STORAGE
// ============================================================================

function saveNetworkToStorage() {
  const data = { nodes: state.nodes, pipes: state.pipes, nextId: state.nextId };
  try { localStorage.setItem('pmpro_pipe_network', JSON.stringify(data)); } catch (e) { }
}

function loadNetworkFromStorage() {
  const saved = localStorage.getItem('pmpro_pipe_network');
  if (saved) {
    try {
      const d = JSON.parse(saved);
      if (d.nodes && d.pipes) {
        state.nodes = d.nodes;
        state.pipes = d.pipes;
        // Migrate pipes created before routing was introduced
        state.pipes.forEach(p => {
          if (p.props && !p.props.routing) p.props.routing = 'auto';
        });
        state.nextId = d.nextId || Math.max(0, ...[...d.nodes, ...d.pipes].map(x => parseInt(x.id.split('-')[1]) || 0)) + 1;
        return true;
      }
    } catch (e) { console.error('Failed to load pipe network:', e); }
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

/** Clip a line endpoint to a circle boundary (so pipe ends at node edge, not center) */
function clipToCircle(cx, cy, r, tx, ty) {
  const dx = tx - cx;
  const dy = ty - cy;
  const dist = Math.hypot(dx, dy);
  if (dist < 1) return { x: cx, y: cy };
  return { x: cx + (dx / dist) * r, y: cy + (dy / dist) * r };
}

function renderPipes() {
  pipesGroup.innerHTML = '';
  state.pipes.forEach(pipe => {
    const fn = findNode(pipe.fromNodeId);
    const tn = findNode(pipe.toNodeId);
    if (!fn || !tn) return;
    const isSel = state.selected?.kind === 'pipe' && state.selected.id === pipe.id;

    const g = mkSVG('g', {});
    g.style.cursor = 'pointer';
    g.addEventListener('click', e => { e.stopPropagation(); selectItem('pipe', pipe.id); });

    // Resolve endpoints (with direction constraints from fittings)
    const fromPt = resolveEndpoint(fn, tn);
    const toPt = resolveEndpoint(tn, fn);

    // Build the pipe path respecting any fitting-arm directions
    const pathD = buildPipePath(fromPt, toPt, pipe.props.routing || 'auto');

    // Midpoint for label placement
    const mid = pipeMidpoint(fromPt, toPt, pathD);

    const D_mm = pipe.props.diameter_mm || 100;
    const thickness = state.viewMode === 'industrial'
      ? Math.max(6, Math.min(28, D_mm / 12))
      : (isSel ? 4 : 3);

    if (state.viewMode === 'industrial') {
      let fillColor = '#94a3b8';
      if (pipe.props.material === 'pvc') fillColor = '#e2e8f0';
      else if (pipe.props.material === 'hdpe') fillColor = '#334155';
      else if (pipe.props.material === 'cast_iron') fillColor = '#78350f';

      g.appendChild(mkSVG('path', {
        d: pathD, fill: 'none',
        stroke: isSel ? '#f59e0b' : '#0f172a',
        'stroke-width': thickness + 4,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      }));
      g.appendChild(mkSVG('path', {
        d: pathD, fill: 'none',
        stroke: fillColor,
        'stroke-width': thickness,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      }));
    } else {
      g.appendChild(mkSVG('path', {
        d: pathD, fill: 'none',
        stroke: isSel ? '#f59e0b' : '#3b82f6',
        'stroke-width': isSel ? 4 : 3,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round',
        ...(isSel ? { 'stroke-dasharray': '8 4' } : {}),
      }));
    }

    // Label
    const lbl = mkSVG('text', {
      x: mid.x, y: mid.y - (state.viewMode === 'industrial' ? 22 : 10),
      'font-size': 10, fill: '#8b949e',
      'font-family': 'Inter, sans-serif',
      'text-anchor': 'middle', 'pointer-events': 'none',
    });
    lbl.textContent = `${pipe.props.label || pipe.id}  D${pipe.props.diameter_mm}mm`;
    g.appendChild(lbl);

    // Hit target
    g.appendChild(mkSVG('path', {
      d: pathD, fill: 'none', stroke: 'transparent',
      'stroke-width': state.viewMode === 'industrial' ? 40 : 16,
    }));

    pipesGroup.appendChild(g);
  });
}

/**
 * Build the pipe path from one endpoint to another, respecting fitting
 * direction constraints at each end.
 *
 * If BOTH ends have direction constraints, we try to honour them by
 * extending along each direction and meeting at an intersection point.
 * If only one end is constrained, we go straight from the other end to it.
 * Otherwise: honour routing mode (straight / orthogonal / auto).
 */
function buildPipePath(fromPt, toPt, routingMode) {
  const hasDirA = fromPt.dirAngle !== null && fromPt.dirAngle !== undefined;
  const hasDirB = toPt.dirAngle !== null && toPt.dirAngle !== undefined;

  // Case 1: both ends are fittings with direction constraints.
  // Extend each arm along its direction and find the intersection.
  if (hasDirA && hasDirB) {
    const uA = { x: Math.cos(fromPt.dirAngle), y: Math.sin(fromPt.dirAngle) };
    const uB = { x: Math.cos(toPt.dirAngle), y: Math.sin(toPt.dirAngle) };

    // Solve: fromPt + s*uA = toPt + t*uB  for intersection (s, t > 0)
    const inter = rayIntersect(fromPt.x, fromPt.y, uA.x, uA.y,
      toPt.x, toPt.y, -uB.x, -uB.y);
    if (inter && inter.t1 > 0 && inter.t2 > 0) {
      // Simple L-shape or single-corner route
      return `M ${fromPt.x},${fromPt.y} L ${inter.x},${inter.y} L ${toPt.x},${toPt.y}`;
    }
    // Arms don't intersect in forward direction — fall back to elbow path
    return buildElbowJoin(fromPt, toPt);
  }

  // Case 2: only one end has direction constraint — go straight.
  if (hasDirA || hasDirB) {
    return `M ${fromPt.x},${fromPt.y} L ${toPt.x},${toPt.y}`;
  }

  // Case 3: no constraints — honour routing mode.
  if (routingMode === 'straight') {
    return `M ${fromPt.x},${fromPt.y} L ${toPt.x},${toPt.y}`;
  }
  if (routingMode === 'orthogonal') {
    return buildOrthogonalPath(fromPt.x, fromPt.y, toPt.x, toPt.y, ELBOW_RADIUS);
  }
  // 'auto' → straight
  return `M ${fromPt.x},${fromPt.y} L ${toPt.x},${toPt.y}`;
}

/**
 * Build a path between two endpoints, using two segments that meet at a
 * rounded corner. Used when both ends have direction constraints that
 * don't produce a clean intersection.
 */
function buildElbowJoin(fromPt, toPt) {
  // Simple fallback: straight line with rounded corner at the midpoint
  return buildOrthogonalPath(fromPt.x, fromPt.y, toPt.x, toPt.y, ELBOW_RADIUS);
}

/** Intersection of two rays: r1 + s*d1  and  r2 + t*d2. Returns {x,y,t1,t2} or null. */
function rayIntersect(x1, y1, dx1, dy1, x2, y2, dx2, dy2) {
  const denom = dx1 * dy2 - dy1 * dx2;
  if (Math.abs(denom) < 1e-6) return null;
  const t1 = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / denom;
  const t2 = ((x2 - x1) * dy1 - (y2 - y1) * dx1) / denom;
  return { x: x1 + t1 * dx1, y: y1 + t1 * dy1, t1, t2 };
}

/** Approximate midpoint for label placement (works for straight/simple paths). */
function pipeMidpoint(fromPt, toPt, pathD) {
  const dx = toPt.x - fromPt.x;
  const dy = toPt.y - fromPt.y;
  const mx = (fromPt.x + toPt.x) / 2;
  const my = (fromPt.y + toPt.y) / 2;
  const ang = Math.atan2(dy, dx) * 180 / Math.PI;
  return { x: mx, y: my, angle: ang };
}

/**
 * Resolve the actual connection point for a pipe endpoint.
 * For most node types this is the node boundary.
 * For elbow nodes it's the tip of the arm facing the other node.
 */
/**
 * Resolve the connection point for a pipe endpoint.
 *
 * Returns { x, y, dirAngle, isFitting }
 *   dirAngle: the direction (radians) the pipe must travel *away* from the
 *             fitting, i.e. along the fitting arm. null for regular nodes.
 */
function resolveEndpoint(node, otherNode) {
  // ── Elbow: pick the arm whose direction best matches the other node ──
  if (node.type === 'elbow') {
    const arms = getElbowArms(node);
    const dx = otherNode.x - node.x;
    const dy = otherNode.y - node.y;
    const targetAng = Math.atan2(dy, dx);

    const diffA = Math.abs(normalizeAngle(targetAng - arms.angA));
    const diffB = Math.abs(normalizeAngle(targetAng - arms.angB));
    const useA = diffA <= diffB;

    const chosenArm = useA ? arms.armA : arms.armB;
    const chosenAng = useA ? arms.angA : arms.angB;

    return {
      x: chosenArm.x,
      y: chosenArm.y,
      isElbow: true,
      isFitting: true,
      dirAngle: chosenAng,   // pipe must leave along this direction
    };
  }

  // ── Valve: pipe must travel along the valve's axis ──
  if (node.type === 'valve') {
    const arms = getValveArms(node);
    const dx = otherNode.x - node.x;
    const dy = otherNode.y - node.y;
    const targetAng = Math.atan2(dy, dx);

    const diffA = Math.abs(normalizeAngle(targetAng - arms.angA));
    const diffB = Math.abs(normalizeAngle(targetAng - arms.angB));
    const useA = diffA <= diffB;

    const chosenArm = useA ? arms.armA : arms.armB;
    const chosenAng = useA ? arms.angA : arms.angB;

    return {
      x: chosenArm.x,
      y: chosenArm.y,
      isValve: true,
      isFitting: true,
      dirAngle: chosenAng,
    };
  }

  // ── Regular node: clip to boundary, no direction constraint ──
  const r = getNodeRadius(node, state.viewMode);
  const dx = otherNode.x - node.x;
  const dy = otherNode.y - node.y;
  const dist = Math.hypot(dx, dy) || 1;
  return {
    x: node.x + (dx / dist) * r,
    y: node.y + (dy / dist) * r,
    isElbow: false,
    isFitting: false,
    dirAngle: null,
  };
}

/** Same as resolveEndpoint but for a target point (used during draft drawing). */
function resolveEndpointFacing(node, tx, ty) {
  if (node.type === 'elbow') {
    const arms = getElbowArms(node);
    const dx = tx - node.x;
    const dy = ty - node.y;
    const targetAng = Math.atan2(dy, dx);
    const diffA = Math.abs(normalizeAngle(targetAng - arms.angA));
    const diffB = Math.abs(normalizeAngle(targetAng - arms.angB));
    const useA = diffA <= diffB;
    const chosenArm = useA ? arms.armA : arms.armB;
    const chosenAng = useA ? arms.angA : arms.angB;
    return { x: chosenArm.x, y: chosenArm.y, dirAngle: chosenAng, isElbow: true };
  }
  if (node.type === 'valve') {
    const arms = getValveArms(node);
    const dx = tx - node.x;
    const dy = ty - node.y;
    const targetAng = Math.atan2(dy, dx);
    const diffA = Math.abs(normalizeAngle(targetAng - arms.angA));
    const diffB = Math.abs(normalizeAngle(targetAng - arms.angB));
    const useA = diffA <= diffB;
    const chosenArm = useA ? arms.armA : arms.armB;
    const chosenAng = useA ? arms.angA : arms.angB;
    return { x: chosenArm.x, y: chosenArm.y, dirAngle: chosenAng, isValve: true };
  }
  // Regular node
  const r = getNodeRadius(node, state.viewMode);
  const dx = tx - node.x;
  const dy = ty - node.y;
  const dist = Math.hypot(dx, dy) || 1;
  return {
    x: node.x + (dx / dist) * r,
    y: node.y + (dy / dist) * r,
    dirAngle: null,
  };
}
function getValveArms(node) {
  // Valve defaults to horizontal axis (arms left & right)
  const orientation = (node.props.orientation || 0) * Math.PI / 180;
  const armLength = 16;
  const angA = orientation + Math.PI;        // left of the valve
  const angB = orientation;                   // right of the valve

  return {
    angA, angB,
    armA: {
      x: node.x + Math.cos(angA) * armLength,
      y: node.y + Math.sin(angA) * armLength,
    },
    armB: {
      x: node.x + Math.cos(angB) * armLength,
      y: node.y + Math.sin(angB) * armLength,
    },
    armLength,
  };
}
function renderNodes() {
  nodesGroup.innerHTML = '';
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

function buildNodeSVG(node, isSel, minElev) {
  const g = mkSVG('g', { transform: `translate(${node.x},${node.y})` });
  g.style.cursor = 'move';
  g.addEventListener('mousedown', e => onNodeDown(e, node.id));
  g.addEventListener('click', e => { e.stopPropagation(); selectItem('node', node.id); });

  switch (node.type) {
    case 'reservoir': drawReservoir(g, isSel, node); break;
    case 'pump': drawPump(g, isSel, node); break;
    case 'tank': drawTank(g, isSel, node); break;
    case 'junction': drawJunction(g, isSel, node); break;
    case 'discharge': drawDischarge(g, isSel, node); break;
    case 'valve': drawValveNode(g, isSel, node); break;
    case 'elbow': drawElbowNode(g, isSel, node); break;
  }

  // Label below node (hide for elbow waypoints)
  if (node.type !== 'elbow') {
    const lbl = mkSVG('text', {
      x: 0, y: 50,
      'text-anchor': 'middle', 'font-size': 11,
      fill: isSel ? '#f59e0b' : '#94a3b8',
      'font-family': 'Inter, sans-serif',
      'pointer-events': 'none',
    });
    lbl.textContent = node.props.label || node.id;
    g.appendChild(lbl);

    const z = node.props.elevation_m || 0;
    const relZ = z - minElev;
    const elevLbl = mkSVG('text', {
      x: 0, y: 64,
      'text-anchor': 'middle', 'font-size': 9,
      fill: '#64748b', 'font-family': 'Inter, sans-serif',
      'pointer-events': 'none',
    });
    elevLbl.textContent = `Z: ${z}m (ΔH: +${relZ.toFixed(1)}m)`;
    g.appendChild(elevLbl);
  }

  // Selection ring
  if (isSel) {
    const ring = mkSVG('circle', {
      r: 46, fill: 'none',
      stroke: '#f59e0b', 'stroke-width': 2,
      'stroke-dasharray': '6 3', opacity: 0.6,
      'pointer-events': 'none',
    });
    g.appendChild(ring);
  }

  // Connection port (only visible in connect mode)
  if (state.mode === 'connect') {
    const port = mkSVG('circle', {
      r: 7, fill: '#22c55e', stroke: '#22c55e', 'stroke-width': 2,
      opacity: 0.9,
    });
    port.style.cursor = 'crosshair';
    port.addEventListener('click', e => { e.stopPropagation(); onPortClick(node.id); });
    g.appendChild(port);
  }

  return g;
}

// ── Node shape drawing helpers ───────────────────────────────────────────────

function drawReservoir(g, sel) {
  if (state.viewMode === 'industrial') {
    g.appendChild(mkSVG('path', { d: 'M-50,-10 L-40,20 L40,20 L50,-10 Z', fill: '#94a3b8', stroke: '#475569', 'stroke-width': 2 }));
    g.appendChild(mkSVG('path', { d: 'M-40,15 L40,15 L45,0 L-45,0 Z', fill: '#38bdf8', opacity: 0.6 }));
    g.appendChild(svgText(0, 5, 'RES', 9, '#1e293b', 'bold'));
  } else {
    g.appendChild(mkSVG('rect', {
      x: -40, y: -30, width: 80, height: 60, rx: 6,
      fill: sel ? '#1e3a5f' : '#0f2744',
      stroke: sel ? '#60a5fa' : '#3b82f6', 'stroke-width': 2.5,
    }));
    for (let i = 0; i < 2; i++) {
      g.appendChild(mkSVG('path', {
        d: `M-28,${-6 + i * 12} Q-14,${-13 + i * 12} 0,${-6 + i * 12} Q14,${1 + i * 12} 28,${-6 + i * 12}`,
        stroke: '#7dd3fc', 'stroke-width': 1.5, fill: 'none', opacity: 0.8,
      }));
    }
    g.appendChild(svgText(0, -16, 'R', 18, '#93c5fd', 'bold'));
  }
}

function drawPump(g, sel) {
  if (state.viewMode === 'industrial') {
    g.appendChild(mkSVG('circle', { r: 24, fill: '#94a3b8', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 2 }));
    g.appendChild(mkSVG('circle', { r: 12, fill: '#1e293b' }));
    g.appendChild(mkSVG('rect', { x: -30, y: 20, width: 60, height: 8, fill: '#475569', rx: 2 }));
    g.appendChild(mkSVG('rect', { x: 20, y: -16, width: 30, height: 32, fill: '#94a3b8', stroke: '#334155', rx: 4 }));
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
    g.appendChild(mkSVG('rect', {
      x: -30, y: -50, width: 60, height: 100, rx: 8,
      fill: '#94a3b8', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 2,
    }));
    g.appendChild(mkSVG('rect', { x: -30, y: -30, width: 60, height: 4, fill: '#475569' }));
    g.appendChild(mkSVG('rect', { x: -30, y: 20, width: 60, height: 4, fill: '#475569' }));
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

function drawJunction(g, sel) {
  if (state.viewMode === 'industrial') {
    g.appendChild(mkSVG('circle', { r: 10, fill: '#94a3b8', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 2 }));
    g.appendChild(mkSVG('circle', { r: 4, fill: '#64748b' }));
  } else {
    g.appendChild(mkSVG('circle', {
      r: 9, fill: sel ? '#334155' : '#1e293b',
      stroke: sel ? '#f59e0b' : '#64748b', 'stroke-width': 2,
    }));
    g.appendChild(svgText(0, 3, 'J', 10, '#94a3b8', 'bold'));
  }
}

function drawDischarge(g, sel) {
  if (state.viewMode === 'industrial') {
    g.appendChild(mkSVG('polygon', { points: '-20,-15 10,-15 15,15 -25,15', fill: '#64748b', stroke: '#1e293b', 'stroke-width': 2 }));
    g.appendChild(mkSVG('path', { d: 'M15,0 Q25,20 35,0', stroke: '#38bdf8', 'stroke-width': 3, fill: 'none' }));
    g.appendChild(mkSVG('path', { d: 'M10,-5 Q30,15 45,-5', stroke: '#7dd3fc', 'stroke-width': 2, fill: 'none' }));
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

/**
 * Valve node — drawn as an inline symbol (butterfly/gate) that sits ON the pipe.
 * The visual footprint is small so it blends into the pipe run.
 */
function drawValveNode(g, sel) {
  const color = sel ? '#fca5a5' : '#ef4444';
  const fill = sel ? '#7f1d1d' : '#450a0a';

  if (state.viewMode === 'industrial') {
    // Valve body: two trapezoids meeting in the middle (butterfly)
    g.appendChild(mkSVG('polygon', {
      points: '-16,-10 0,0 -16,10 16,-10 0,0 16,10',
      fill: '#94a3b8', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 1.5,
    }));
    // Stem
    g.appendChild(mkSVG('rect', { x: -2, y: -22, width: 4, height: 12, fill: '#cbd5e1' }));
    // Handwheel
    g.appendChild(mkSVG('rect', { x: -12, y: -28, width: 24, height: 5, rx: 2.5, fill: '#ef4444', stroke: '#7f1d1d' }));
  } else {
    // Bowtie shape (classic valve symbol)
    g.appendChild(mkSVG('polygon', {
      points: '-14,-10 0,0 -14,10 14,-10 0,0 14,10',
      fill: fill, stroke: color, 'stroke-width': 2,
      'stroke-linejoin': 'round',
    }));
  }
}

/**
 * Elbow node — draws a proper curved pipe bend.
 * The angle comes from the node's fitting_key:
 *   elbow_90_standard    → 90°
 *   elbow_90_long_radius → 90° (larger radius)
 *   elbow_45             → 45°
 *
 * Orientation: auto-detected from the two connected pipes.
 * If not connected, falls back to a default 90° bend pointing down-right.
 */
/**
 * Elbow node — draws a proper curved pipe bend, in LOCAL coordinates
 * (the parent <g> is already translated to the node position).
 */
/**
/**
 * Elbow node — draws a clean 90° (or 45°) curved pipe bend.
 * Renders as a single smooth curve between two arm endpoints.
 *
 * CRITICAL: the two arm endpoints are exposed via getElbowArms() so that
 * renderPipes() can connect straight pipe segments to them WITHOUT adding
 * its own bend.
 */
function getElbowArms(node) {
  const fittingKey = node.props.fitting_key || 'elbow_90_standard';

  // ── Fitting-specific parameters ────────────────────────────────────
  // Short-radius 90° elbow: tight bend  (r / D ≈ 1)
  // Long-radius 90° elbow:  gentle bend (r / D ≈ 1.5)
  // 45° elbow:              half the bend angle, medium radius
  // ───────────────────────────────────────────────────────────────────
  let bendAngleDeg = 90;
  let bendRadius = 12;    // short radius 90° — tight corner
  if (fittingKey === 'elbow_90_long_radius') {
    bendAngleDeg = 90;
    bendRadius = 26;      // long radius 90° — visibly gentler curve
  } else if (fittingKey === 'elbow_45') {
    bendAngleDeg = 45;
    bendRadius = 18;      // 45° elbow — medium radius
  }

  const connected = state.pipes.filter(p =>
    p.fromNodeId === node.id || p.toNodeId === node.id
  );

  // Default orientation: arm A left, arm B down (L-bend)
  let angA = Math.PI;             // 180° → left
  let angB = Math.PI / 2;         //  90° → down

  if (connected.length >= 2) {
    const o1 = otherNode(connected[0], node);
    const o2 = otherNode(connected[1], node);
    if (o1 && o2) {
      angA = Math.atan2(o1.y - node.y, o1.x - node.x);
      const rawB = Math.atan2(o2.y - node.y, o2.x - node.x);
      const sign = normalizeAngle(rawB - angA) >= 0 ? 1 : -1;
      angB = angA + sign * (bendAngleDeg * Math.PI / 180);
    }
  } else if (connected.length === 1) {
    const o1 = otherNode(connected[0], node);
    if (o1) {
      angA = Math.atan2(o1.y - node.y, o1.x - node.x);
      angB = angA + (bendAngleDeg * Math.PI / 180);
    }
  }

  // Manual override
  if (typeof node.props.orientation === 'number') {
    const baseRad = node.props.orientation * Math.PI / 180;
    angA = baseRad + Math.PI;
    angB = baseRad - bendAngleDeg * Math.PI / 180;
  }

  // Arm length scales with bend radius so that long-radius elbows
  // don't look cramped and short-radius elbows don't look stretched.
  const armLength = Math.max(22, bendRadius + 14);

  const armA = {
    x: node.x + Math.cos(angA) * armLength,
    y: node.y + Math.sin(angA) * armLength,
  };
  const armB = {
    x: node.x + Math.cos(angB) * armLength,
    y: node.y + Math.sin(angB) * armLength,
  };

  return {
    armA, armB,
    angA, angB,
    bendAngleDeg, bendRadius, armLength,
    fittingKey,
    thickness: 4,
  };
}
function drawElbowNode(g, sel, node) {
  const arms = getElbowArms(node);
  const { armLength, bendRadius, bendAngleDeg } = arms;

  // Local coords (parent <g> already translated to node position)
  const a1 = { x: arms.armA.x - node.x, y: arms.armA.y - node.y };
  const a2 = { x: arms.armB.x - node.x, y: arms.armB.y - node.y };

  // Unit vectors pointing OUTWARD along each arm
  const u1 = { x: Math.cos(arms.angA), y: Math.sin(arms.angA) };
  const u2 = { x: Math.cos(arms.angB), y: Math.sin(arms.angB) };

  // Half-angle between arms
  const theta = Math.abs(normalizeAngle(arms.angB - arms.angA));
  const halfTheta = theta / 2;

  // Tangent distance from corner along each arm
  const tangentDist = bendRadius * Math.tan(halfTheta);

  // Tangent points (in the SAME direction as each arm)
  const t1 = { x: u1.x * tangentDist, y: u1.y * tangentDist };
  const t2 = { x: u2.x * tangentDist, y: u2.y * tangentDist };

  // Build the elbow path with a quadratic Bézier through the origin.
  const pathD = [
    `M ${a1.x},${a1.y}`,
    `L ${t1.x},${t1.y}`,
    `Q 0,0 ${t2.x},${t2.y}`,
    `L ${a2.x},${a2.y}`,
  ].join(' ');

  // Colors & thickness
  const baseColor = state.viewMode === 'industrial' ? '#94a3b8' : '#3b82f6';
  const edgeColor = sel ? '#f59e0b'
    : (state.viewMode === 'industrial' ? '#0f172a' : '#1e40af');

  const D_mm = state.pipes.find(p =>
    p.fromNodeId === node.id || p.toNodeId === node.id
  )?.props?.diameter_mm || 100;
  const strokeW = state.viewMode === 'industrial'
    ? Math.max(10, Math.min(28, D_mm / 12))
    : 4;

  // ── Outer edge (dark outline) ──────────────────────────────────────
  g.appendChild(mkSVG('path', {
    d: pathD, fill: 'none',
    stroke: edgeColor,
    'stroke-width': strokeW + 3,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'pointer-events': 'none',
  }));

  // ── Main pipe body ─────────────────────────────────────────────────
  g.appendChild(mkSVG('path', {
    d: pathD, fill: 'none',
    stroke: sel ? '#fbbf24' : baseColor,
    'stroke-width': strokeW,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'pointer-events': 'none',
  }));

  // ── Inner highlight (industrial only) ──────────────────────────────
  if (state.viewMode === 'industrial' && strokeW > 8) {
    g.appendChild(mkSVG('path', {
      d: pathD, fill: 'none',
      stroke: 'rgba(255,255,255,0.35)',
      'stroke-width': Math.max(1, strokeW * 0.22),
      'stroke-linecap': 'round',
      'pointer-events': 'none',
    }));
  }

  // ── Fitting-type badge (small label near the corner) ───────────────
  // Only shows when selected, so it doesn't clutter the canvas.
  if (sel) {
    let badgeText = '90°';
    if (bendAngleDeg === 45) badgeText = '45°';
    else if (bendAngleDeg === 90 && bendRadius >= 22) badgeText = '90° LR';
    else badgeText = '90° SR';

    // Position badge on the outer side of the bend, away from the arms
    const bisX = (u1.x + u2.x);
    const bisY = (u1.y + u2.y);
    const bisLen = Math.hypot(bisX, bisY) || 1;
    const badgeX = -(bisX / bisLen) * (bendRadius + 18);
    const badgeY = -(bisY / bisLen) * (bendRadius + 18);

    const badgeBg = mkSVG('rect', {
      x: badgeX - 22, y: badgeY - 9,
      width: 44, height: 18, rx: 4,
      fill: '#1e293b',
      stroke: '#f59e0b', 'stroke-width': 1,
      'pointer-events': 'none',
    });
    g.appendChild(badgeBg);

    const badge = mkSVG('text', {
      x: badgeX, y: badgeY,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      'font-size': 10, 'font-weight': 600,
      fill: '#fbbf24',
      'font-family': 'Inter, sans-serif',
      'pointer-events': 'none',
    });
    badge.textContent = badgeText;
    g.appendChild(badge);
  }

  // ── Invisible hit area ─────────────────────────────────────────────
  g.appendChild(mkSVG('circle', {
    cx: 0, cy: 0,
    r: Math.max(armLength, strokeW + 20),
    fill: 'transparent',
    'pointer-events': 'all',
  }));
}

/** Intersection of two 2D lines, or null if parallel. */
function lineIntersection(x1, y1, dx1, dy1, x2, y2, dx2, dy2) {
  const denom = dx1 * dy2 - dy1 * dx2;
  if (Math.abs(denom) < 1e-6) return null;
  const t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / denom;
  return { x: x1 + t * dx1, y: y1 + t * dy1 };
}

/** Fallback if we can't compute a proper arc: just draw a small square corner. */
function drawElbowFallback(g, sel, a1, a2, radius) {
  const pathD = `M ${a1.x},${a1.y} L 0,0 L ${a2.x},${a2.y}`;
  const baseColor = state.viewMode === 'industrial' ? '#94a3b8' : '#3b82f6';
  const edgeColor = sel ? '#f59e0b' : (state.viewMode === 'industrial' ? '#0f172a' : '#1e40af');
  g.appendChild(mkSVG('path', {
    d: pathD, fill: 'none',
    stroke: edgeColor, 'stroke-width': 7,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    'pointer-events': 'none',
  }));
  g.appendChild(mkSVG('path', {
    d: pathD, fill: 'none',
    stroke: sel ? '#fbbf24' : baseColor, 'stroke-width': 4,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    'pointer-events': 'none',
  }));
  g.appendChild(mkSVG('circle', {
    cx: 0, cy: 0, r: 40, fill: 'transparent', 'pointer-events': 'all',
  }));
}
/** Return the other node of a pipe relative to the given node. */
function otherNode(pipe, node) {
  if (pipe.fromNodeId === node.id) return findNode(pipe.toNodeId);
  if (pipe.toNodeId === node.id) return findNode(pipe.fromNodeId);
  return null;
}

/** Normalize angle to (-π, π] */
function normalizeAngle(a) {
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a <= -Math.PI) a += 2 * Math.PI;
  return a;
}

/** Rubber-band preview line while drawing a pipe */
function updateDraftLine() {
  if (!draftPipeLine) return;
  if (state.drawingPipe) {
    const fn = findNode(state.drawingPipe.fromNodeId);
    if (!fn) { draftPipeLine.style.display = 'none'; return; }

    // Starting point: if source is an elbow, use the arm tip facing the mouse
    const mx = state.drawingPipe.mouseX;
    const my = state.drawingPipe.mouseY;
    const startPt = resolveEndpointFacing(fn, mx, my);
    const endPt = { x: mx, y: my };

    // Straight dashed line always
    draftPipeLine.setAttribute('d', `M ${startPt.x},${startPt.y} L ${endPt.x},${endPt.y}`);
    draftPipeLine.style.display = '';
  } else {
    draftPipeLine.style.display = 'none';
  }
}

// ============================================================================
// CANVAS TRANSFORM
// ============================================================================

function applyTransform() {
  const w = svgEl.clientWidth || 900;
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

function onCanvasClick(e) {
  if (state.mode === 'select') { selectItem(null); return; }
  if (state.mode.startsWith('add-')) {
    const type = state.mode.replace('add-', '');
    const pos = toSVG(e);
    addNode(type, snap(pos.x), snap(pos.y));
    setMode('select');
  }
}

function onNodeDown(e, nodeId) {
  e.stopPropagation();
  if (state.mode === 'connect') { onPortClick(nodeId); return; }
  const pos = toSVG(e);
  const node = findNode(nodeId);
  if (!node) return;
  state.nodeDrag = { nodeId, offsetX: pos.x - node.x, offsetY: pos.y - node.y };
}

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
  const id = newId('N');
  const count = state.nodes.filter(n => n.type === type).length;
  const node = { id, type, x, y, props: defaultNodeProps(type, count) };
  state.nodes.push(node);
  renderAll();
  selectItem('node', id);
}

function addPipe(fromNodeId, toNodeId) {
  const id = newId('P');
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
  const elNode = document.getElementById('pn-props-node');
  const elPipe = document.getElementById('pn-props-pipe');
  const elEmpty = document.getElementById('pn-props-empty');
  if (elNode) elNode.style.display = which === 'node' ? '' : 'none';
  if (elPipe) elPipe.style.display = which === 'pipe' ? '' : 'none';
  if (elEmpty) elEmpty.style.display = which === 'none' ? '' : 'none';
}

function showNodeProps(node) {
  if (!node) return;
  showPropsPanel('node');
  setVal('np-id', node.id);
  setVal('np-type', node.type);
  setVal('np-label', node.props.label || '');
  setVal('np-elev', node.props.elevation_m ?? 0);

  const pumpDiv = document.getElementById('np-pump-fields');
  if (pumpDiv) {
    pumpDiv.style.display = node.type === 'pump' ? '' : 'none';
    if (node.type === 'pump') setVal('np-flow', node.props.flow_m3h ?? 10);
  }

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
  setVal('pp-id', pipe.id);
  setVal('pp-from', pipe.fromNodeId);
  setVal('pp-to', pipe.toNodeId);
  setVal('pp-label', pipe.props.label || '');
  setVal('pp-diameter', pipe.props.diameter_mm);
  setVal('pp-length', pipe.props.length_m);
  setVal('pp-elev-change', pipe.props.elev_change_m);
  setVal('pp-material', pipe.props.material);
  setVal('pp-routing', pipe.props.routing || 'auto');
  document.querySelectorAll('.pp-fitting-cb').forEach(cb => {
    cb.checked = (pipe.props.fittings || []).includes(cb.value);
  });
  refreshKTotal(pipe.props.fittings || []);
}

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
    'select': 'Select / Move nodes',
    'connect': 'Draw Pipe — click source node, then destination node',
    'add-reservoir': 'Place Reservoir — click on canvas',
    'add-pump': 'Place Pump — click on canvas',
    'add-tank': 'Place Tank — click on canvas',
    'add-junction': 'Place Junction (Tee) — click on canvas',
    'add-discharge': 'Place Open Discharge — click on canvas',
    'add-valve': 'Place Valve — click on canvas',
    'add-elbow': 'Place Elbow waypoint — click on canvas',
  };
  setVal('pn-status', labels[mode] || mode);

  const cursors = { 'select': 'default', 'connect': 'crosshair' };
  svgEl.style.cursor = cursors[mode] || 'cell';
  renderNodes();
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
  pipe.props.label = document.getElementById('pp-label').value;
  pipe.props.diameter_mm = parseFloat(document.getElementById('pp-diameter').value) || 100;
  pipe.props.length_m = parseFloat(document.getElementById('pp-length').value) || 10;
  pipe.props.elev_change_m = parseFloat(document.getElementById('pp-elev-change').value) || 0;
  pipe.props.material = document.getElementById('pp-material').value;
  pipe.props.routing = document.getElementById('pp-routing').value;
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
      const allFittings = [...(pipe.props.fittings || [])];
      const toNode = findNode(pipe.toNodeId);
      if (toNode && toNode.props.fitting_key) allFittings.push(toNode.props.fitting_key);
      return {
        id: pipe.id,
        label: pipe.props.label || pipe.id,
        diameter_mm: pipe.props.diameter_mm,
        length_m: pipe.props.length_m,
        material: pipe.props.material,
        elev_change_m: pipe.props.elev_change_m,
        fittings: allFittings,
      };
    }),
  };

  const btn = document.getElementById('pn-calc-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Calculating...';
  }

  try {
    const resp = await fetch('/api/pipe-network/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) { const e = await resp.json(); toast(`Error: ${e.error}`, 'error'); return; }
    const data = await resp.json();
    displayResults(data);
    document.getElementById('pn-results-section')?.scrollIntoView({ behavior: 'smooth' });
    toast('Calculation complete!', 'success');
  } catch (err) {
    toast(`Network error: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-calculator"></i> Calculate Losses';
    }
  }
}

function displayResults(data) {
  const sec = document.getElementById('pn-results-section');
  if (sec) sec.style.display = '';
  const s = data.summary;
  setVal('res-major', s.total_hf_major_m.toFixed(3));
  setVal('res-minor', s.total_hf_minor_m.toFixed(3));
  setVal('res-elev', s.total_elevation_m.toFixed(3));
  setVal('res-total', s.total_system_head_m.toFixed(3));
  setVal('res-count', s.pipe_count);

  const tbody = document.getElementById('res-table-body');
  if (!tbody) return;
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
      state.nodes = d.nodes;
      state.pipes = d.pipes;
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
  const sec = document.getElementById('pn-results-section');
  if (sec) sec.style.display = 'none';
  selectItem(null); renderAll();
  toast('Canvas cleared.', 'info');
}

// ============================================================================
// TOAST
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
// INIT
// ============================================================================

function init() {
  svgEl = document.getElementById('pn-svg');
  nodesGroup = document.getElementById('pn-nodes');
  pipesGroup = document.getElementById('pn-pipes');
  if (!svgEl || !nodesGroup || !pipesGroup) {
    console.warn('[pipe_network] Required SVG elements not found on this page.');
    return;
  }

  // Draft rubber-band path (uses orthogonal routing)
  draftPipeLine = mkSVG('path', {
    fill: 'none', stroke: '#22c55e',
    'stroke-width': 2, 'stroke-dasharray': '8 4',
  });
  draftPipeLine.style.display = 'none';
  draftPipeLine.style.pointerEvents = 'none';
  svgEl.appendChild(draftPipeLine);

  // Gradients (kept for compatibility with industrial view)
  const defs = mkSVG('defs', {});
  defs.innerHTML = `
    <linearGradient id="grad-steel" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#94a3b8"/>
      <stop offset="20%" stop-color="#cbd5e1"/>
      <stop offset="50%" stop-color="#64748b"/>
      <stop offset="80%" stop-color="#334155"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <linearGradient id="grad-pvc" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#e2e8f0"/>
      <stop offset="40%" stop-color="#ffffff"/>
      <stop offset="70%" stop-color="#cbd5e1"/>
      <stop offset="100%" stop-color="#94a3b8"/>
    </linearGradient>
    <linearGradient id="grad-hdpe" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#334155"/>
      <stop offset="30%" stop-color="#475569"/>
      <stop offset="80%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>
    <linearGradient id="grad-iron" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#78350f"/>
      <stop offset="30%" stop-color="#b45309"/>
      <stop offset="70%" stop-color="#451a03"/>
      <stop offset="100%" stop-color="#210800"/>
    </linearGradient>
  `;
  svgEl.appendChild(defs);

  // Canvas events
  svgEl.addEventListener('click', onCanvasClick);

  svgEl.addEventListener('mousemove', e => {
    if (state.drawingPipe) {
      const pos = toSVG(e);
      state.drawingPipe.mouseX = pos.x;
      state.drawingPipe.mouseY = pos.y;
      updateDraftLine();
    }
    if (state.nodeDrag) {
      const pos = toSVG(e);
      const node = findNode(state.nodeDrag.nodeId);
      if (node) {
        node.x = snap(pos.x - state.nodeDrag.offsetX);
        node.y = snap(pos.y - state.nodeDrag.offsetY);
        renderAll();
      }
    }
    if (state.panDrag) {
      state.pan.x = state.panDrag.startPanX + (e.clientX - state.panDrag.startX);
      state.pan.y = state.panDrag.startPanY + (e.clientY - state.panDrag.startY);
      applyTransform();
    }
  });

  svgEl.addEventListener('mouseup', () => { state.nodeDrag = null; state.panDrag = null; });

  svgEl.addEventListener('mousedown', e => {
    if (e.button === 1) {
      state.panDrag = {
        startX: e.clientX, startY: e.clientY,
        startPanX: state.pan.x, startPanY: state.pan.y
      };
      e.preventDefault();
    }
  });

  svgEl.addEventListener('wheel', e => {
    e.preventDefault();
    state.zoom = Math.min(3, Math.max(0.2, state.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
    applyTransform();
  }, { passive: false });

  // Keyboard
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.key === 'Escape') setMode('select');
    if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
    if (e.key === 's' || e.key === 'S') setMode('select');
    if (e.key === 'c' || e.key === 'C') setMode('connect');
  });

  // Toolbar
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

  // View toggle
  document.getElementById('btn-view-schematic')?.addEventListener('click', () => {
    state.viewMode = 'schematic';
    document.getElementById('btn-view-schematic').classList.add('active-tool');
    document.getElementById('btn-view-industrial').classList.remove('active-tool');
    renderAll();
  });
  document.getElementById('btn-view-industrial')?.addEventListener('click', () => {
    state.viewMode = 'industrial';
    document.getElementById('btn-view-industrial').classList.add('active-tool');
    document.getElementById('btn-view-schematic').classList.remove('active-tool');
    renderAll();
  });

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

  // Property inputs
  document.getElementById('np-label')?.addEventListener('input', onNodeLabelChange);
  document.getElementById('np-elev')?.addEventListener('change', onNodeElevChange);
  document.getElementById('np-flow')?.addEventListener('change', onPumpFlowChange);
  document.getElementById('np-fitting-key')?.addEventListener('change', onNodeFittingChange);

  // Pipe property inputs (includes pp-routing now)
  ['pp-label', 'pp-diameter', 'pp-length', 'pp-elev-change', 'pp-material', 'pp-routing'].forEach(id =>
    document.getElementById(id)?.addEventListener('change', onPipePropChange)
  );
  document.getElementById('pp-fittings-list')?.addEventListener('change', onPipePropChange);

  // Populate materials
  const matSel = document.getElementById('pp-material');
  if (matSel) {
    MATERIALS.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.key; opt.textContent = m.label;
      matSel.appendChild(opt);
    });
  }

  // Populate fittings
  const fList = document.getElementById('pp-fittings-list');
  const nFitSel = document.getElementById('np-fitting-key');
  FITTINGS.forEach(f => {
    if (fList) {
      const lbl = document.createElement('label');
      lbl.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:5px;cursor:pointer;font-size:12px;color:#94a3b8;';
      lbl.innerHTML = `<input type="checkbox" class="pp-fitting-cb" value="${f.key}" style="accent-color:#58a6ff;cursor:pointer;flex-shrink:0;">
        <span>${f.label} <span style="color:#475569">(K=${f.K})</span></span>`;
      fList.appendChild(lbl);
    }
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

  if (!loadNetworkFromStorage()) {
    loadDemoNetwork();
  } else {
    renderAll();
  }
}

/** Demo: reservoir -> pump -> junction -> tank, matching the reference layout */
/** Demo: reservoir -> pump -> junction -> tank, matching the reference layout */
function loadDemoNetwork() {
  state.nodes = [
    {
      id: 'N-1', type: 'reservoir', x: 100, y: 350,
      props: { label: 'Sump', elevation_m: 0 }
    },
    {
      id: 'N-2', type: 'pump', x: 300, y: 350,
      props: { label: 'Pump 1', flow_m3h: 15, elevation_m: 0 }
    },
    {
      id: 'N-3', type: 'junction', x: 500, y: 350,
      props: { label: 'Tee', elevation_m: 2 }
    },
    {
      id: 'N-4', type: 'tank', x: 700, y: 150,
      props: { label: 'Overhead Tank', elevation_m: 12 }
    },
  ];
  state.pipes = [
    {
      id: 'P-1', fromNodeId: 'N-1', toNodeId: 'N-2',
      props: {
        label: 'Suction', diameter_mm: 150, length_m: 4,
        material: 'commercial_steel', elev_change_m: 0,
        fittings: ['entry_sharp', 'gate_valve_open'],
        routing: 'straight'
      }
    },
    {
      id: 'P-2', fromNodeId: 'N-2', toNodeId: 'N-3',
      props: {
        label: 'Discharge', diameter_mm: 100, length_m: 18,
        material: 'commercial_steel', elev_change_m: 2,
        fittings: ['check_valve_swing', 'elbow_90_standard'],
        routing: 'straight'
      }
    },
    {
      id: 'P-3', fromNodeId: 'N-3', toNodeId: 'N-4',
      props: {
        label: 'Riser', diameter_mm: 80, length_m: 14,
        material: 'commercial_steel', elev_change_m: 10,
        fittings: ['elbow_90_standard', 'exit_abrupt'],
        routing: 'straight'
      }
    },
  ];
  state.nextId = 10;
  renderAll();
}

document.addEventListener('DOMContentLoaded', init);