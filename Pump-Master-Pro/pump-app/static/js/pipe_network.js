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

// Grid resolution: 10px allows smooth, precision alignment without jarring jumps
const GRID = 10;
const ELBOW_RADIUS = 14;

// MATERIALS and FITTINGS are now loaded from the database via Jinja template injection.
// The template injects window.__PMP_MATERIALS and window.__PMP_FITTINGS as inline JSON
// before this script runs, providing identical performance to hardcoded constants.
const MATERIALS = window.__PMP_MATERIALS || [
  // Fallback defaults in case DB injection fails (should not happen in normal operation)
  { key: 'commercial_steel', label: 'Commercial Steel  (e = 0.046 mm)' },
  { key: 'pvc', label: 'PVC / Plastic     (e = 0.002 mm)' },
];

const FITTINGS = window.__PMP_FITTINGS || [
  // Fallback defaults
  { key: 'elbow_90_standard', label: '90 Elbow (Standard)', K: 0.90 },
  { key: 'gate_valve_open', label: 'Gate Valve (Open)', K: 0.20 },
];

function generateStandardPipesCatalog() {
  const pipes = [];
  let id = 1;

  // 1. ASME B36.10M Carbon Steel
  const cs = [
    [15, '1/2"', 21.3, [['Sch 40 (STD)', 2.77, 197], ['Sch 80 (XS)', 3.73, 265]]],
    [20, '3/4"', 26.7, [['Sch 40 (STD)', 2.87, 161], ['Sch 80 (XS)', 3.91, 220]]],
    [25, '1"', 33.4, [['Sch 40 (STD)', 3.38, 152], ['Sch 80 (XS)', 4.55, 205]]],
    [32, '1-1/4"', 42.2, [['Sch 40 (STD)', 3.56, 127], ['Sch 80 (XS)', 4.85, 172]]],
    [40, '1-1/2"', 48.3, [['Sch 40 (STD)', 3.68, 114], ['Sch 80 (XS)', 5.08, 158]]],
    [50, '2"', 60.3, [['Sch 10', 2.77, 69], ['Sch 40 (STD)', 3.91, 97], ['Sch 80 (XS)', 5.54, 138], ['Sch 160', 8.74, 217]]],
    [65, '2-1/2"', 73.0, [['Sch 40 (STD)', 5.16, 106], ['Sch 80 (XS)', 7.01, 144]]],
    [80, '3"', 88.9, [['Sch 10', 3.05, 51], ['Sch 40 (STD)', 5.49, 93], ['Sch 80 (XS)', 7.62, 129], ['Sch 160', 11.13, 188]]],
    [100, '4"', 114.3, [['Sch 10', 3.05, 40], ['Sch 40 (STD)', 6.02, 79], ['Sch 80 (XS)', 8.56, 112], ['Sch 120', 11.13, 146], ['Sch 160', 13.49, 177]]],
    [125, '5"', 141.3, [['Sch 40 (STD)', 6.55, 70], ['Sch 80 (XS)', 9.53, 101]]],
    [150, '6"', 168.3, [['Sch 10', 3.40, 30], ['Sch 40 (STD)', 7.11, 63], ['Sch 80 (XS)', 10.97, 98], ['Sch 160', 18.26, 163]]],
    [200, '8"', 219.1, [['Sch 10', 3.76, 26], ['Sch 20', 6.35, 44], ['Sch 40 (STD)', 8.18, 56], ['Sch 80 (XS)', 12.70, 87], ['Sch 120', 18.26, 125], ['Sch 160', 23.01, 158]]],
    [250, '10"', 273.0, [['Sch 20', 6.35, 35], ['Sch 40 (STD)', 9.27, 51], ['Sch 80 (XS)', 15.09, 83], ['Sch 120', 21.44, 118], ['Sch 160', 28.58, 157]]],
    [300, '12"', 323.8, [['Sch 20', 6.35, 29], ['Sch 40 (STD)', 10.31, 48], ['Sch 80 (XS)', 17.48, 81]]],
    [350, '14"', 355.6, [['Sch 30', 9.53, 40], ['Sch 40 (STD)', 11.13, 47], ['Sch 80 (XS)', 19.05, 80]]],
    [400, '16"', 406.4, [['Sch 30', 9.53, 35], ['Sch 40 (STD)', 12.70, 47], ['Sch 80 (XS)', 21.44, 79]]],
    [450, '18"', 457.0, [['Sch 40 (STD)', 14.27, 47], ['Sch 80 (XS)', 23.83, 78]]],
    [500, '20"', 508.0, [['Sch 40 (STD)', 15.09, 45], ['Sch 80 (XS)', 26.19, 77]]],
    [600, '24"', 610.0, [['Sch 40 (STD)', 17.48, 43], ['Sch 80 (XS)', 30.96, 76]]]
  ];
  cs.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, p]) => {
      pipes.push({
        id: id++, standard: 'ASME B36.10M', material: 'Carbon Steel', material_key: 'commercial_steel',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: `PN ${p} bar (${Math.round(p * 14.5038)} psi)`, is_active: true
      });
    });
  });

  // 2. ASME B36.19M Stainless Steel
  const ss = [
    [15, '1/2"', 21.3, [['Sch 10S', 2.11, 148], ['Sch 40S', 2.77, 197], ['Sch 80S', 3.73, 265]]],
    [20, '3/4"', 26.7, [['Sch 10S', 2.11, 118], ['Sch 40S', 2.87, 161], ['Sch 80S', 3.91, 220]]],
    [25, '1"', 33.4, [['Sch 10S', 2.77, 124], ['Sch 40S', 3.38, 152], ['Sch 80S', 4.55, 205]]],
    [32, '1-1/4"', 42.2, [['Sch 10S', 2.77, 98], ['Sch 40S', 3.56, 127], ['Sch 80S', 4.85, 172]]],
    [40, '1-1/2"', 48.3, [['Sch 10S', 2.77, 86], ['Sch 40S', 3.68, 114], ['Sch 80S', 5.08, 158]]],
    [50, '2"', 60.3, [['Sch 10S', 2.77, 69], ['Sch 40S', 3.91, 97], ['Sch 80S', 5.54, 138]]],
    [65, '2-1/2"', 73.0, [['Sch 10S', 3.05, 63], ['Sch 40S', 5.16, 106], ['Sch 80S', 7.01, 144]]],
    [80, '3"', 88.9, [['Sch 10S', 3.05, 51], ['Sch 40S', 5.49, 93], ['Sch 80S', 7.62, 129]]],
    [100, '4"', 114.3, [['Sch 10S', 3.05, 40], ['Sch 40S', 6.02, 79], ['Sch 80S', 8.56, 112]]],
    [150, '6"', 168.3, [['Sch 10S', 3.40, 30], ['Sch 40S', 7.11, 63], ['Sch 80S', 10.97, 98]]],
    [200, '8"', 219.1, [['Sch 10S', 3.76, 26], ['Sch 40S', 8.18, 56], ['Sch 80S', 12.70, 87]]],
    [250, '10"', 273.0, [['Sch 10S', 4.19, 23], ['Sch 40S', 9.27, 51], ['Sch 80S', 12.70, 70]]],
    [300, '12"', 323.8, [['Sch 10S', 4.57, 21], ['Sch 40S', 9.53, 44], ['Sch 80S', 12.70, 59]]]
  ];
  ss.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, p]) => {
      pipes.push({
        id: id++, standard: 'ASME B36.19M', material: 'Stainless Steel', material_key: 'stainless_steel',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: `PN ${p} bar (${Math.round(p * 14.5038)} psi)`, is_active: true
      });
    });
  });

  // 3. ISO 4427 / SANS 4427 HDPE PE100
  const hdpe_sdrs = [
    ['SDR 7.4', 7.4, 'PN 25 (25 bar / 363 psi)'],
    ['SDR 9', 9.0, 'PN 20 (20 bar / 290 psi)'],
    ['SDR 11', 11.0, 'PN 16 (16 bar / 232 psi)'],
    ['SDR 13.6', 13.6, 'PN 12.5 (12.5 bar / 181 psi)'],
    ['SDR 17', 17.0, 'PN 10 (10 bar / 145 psi)'],
    ['SDR 21', 21.0, 'PN 8 (8 bar / 116 psi)'],
    ['SDR 26', 26.0, 'PN 6 (6 bar / 87 psi)'],
  ];
  const hdpe_ods = [
    [25, 20], [32, 25], [40, 32], [50, 40], [63, 50], [75, 65], [90, 80],
    [110, 100], [125, 100], [140, 125], [160, 150], [180, 150], [200, 200],
    [225, 200], [250, 250], [280, 250], [315, 300], [355, 350], [400, 400],
    [450, 450], [500, 500], [560, 500], [630, 600]
  ];
  hdpe_sdrs.forEach(([sch, sdr, rating]) => {
    hdpe_ods.forEach(([od, nb]) => {
      let wall = +(od / sdr).toFixed(2);
      if (wall < 2.0) wall = 2.0;
      const idVal = +(od - 2 * wall).toFixed(2);
      if (idVal > 0) {
        pipes.push({
          id: id++, standard: 'ISO 4427 / SANS 4427', material: 'HDPE (PE100)', material_key: 'plastic_pe',
          schedule_sdr: sch, nb_mm: nb, nb_inch: `${nb}mm`, od_mm: od, wall_thickness_mm: wall,
          id_mm: idVal, sdr: sdr, pressure_rating: rating, is_active: true
        });
      }
    });
  });

  // 4. DIN 8062 / ISO 1452 uPVC Metric
  const pvc_classes = [
    ['Class 6 / SDR 41', 41.0, 'PN 6 (6 bar / 87 psi)'],
    ['Class 9 / SDR 26', 26.0, 'PN 9 (9 bar / 130 psi)'],
    ['Class 12 / SDR 21', 21.0, 'PN 12 (12 bar / 174 psi)'],
    ['Class 16 / SDR 13.5', 13.5, 'PN 16 (16 bar / 232 psi)'],
    ['Class 20 / SDR 11', 11.0, 'PN 20 (20 bar / 290 psi)'],
  ];
  const pvc_ods = [
    [32, 25], [40, 32], [50, 40], [63, 50], [75, 65], [90, 80],
    [110, 100], [125, 100], [140, 125], [160, 150], [200, 200],
    [250, 250], [315, 300], [400, 400], [500, 500]
  ];
  pvc_classes.forEach(([sch, sdr, rating]) => {
    pvc_ods.forEach(([od, nb]) => {
      let wall = +(od / sdr).toFixed(2);
      if (wall < 1.5) wall = 1.5;
      const idVal = +(od - 2 * wall).toFixed(2);
      if (idVal > 0) {
        pipes.push({
          id: id++, standard: 'DIN 8062 / ISO 1452', material: 'uPVC', material_key: 'pvc',
          schedule_sdr: sch, nb_mm: nb, nb_inch: `${nb}mm`, od_mm: od, wall_thickness_mm: wall,
          id_mm: idVal, sdr: sdr, pressure_rating: rating, is_active: true
        });
      }
    });
  });

  // 5. ASTM D1785 PVC IPS
  const pvc_ips = [
    [15, '1/2"', 21.3, [['Sch 40', 2.77, 'PN 41 (600 psi)'], ['Sch 80', 3.73, 'PN 59 (850 psi)']]],
    [20, '3/4"', 26.7, [['Sch 40', 2.87, 'PN 33 (480 psi)'], ['Sch 80', 3.91, 'PN 48 (690 psi)']]],
    [25, '1"', 33.4, [['Sch 40', 3.38, 'PN 31 (450 psi)'], ['Sch 80', 4.55, 'PN 43 (630 psi)']]],
    [32, '1-1/4"', 42.2, [['Sch 40', 3.56, 'PN 25 (370 psi)'], ['Sch 80', 4.85, 'PN 36 (520 psi)']]],
    [40, '1-1/2"', 48.3, [['Sch 40', 3.68, 'PN 23 (330 psi)'], ['Sch 80', 5.08, 'PN 32 (470 psi)']]],
    [50, '2"', 60.3, [['Sch 40', 3.91, 'PN 19 (280 psi)'], ['Sch 80', 5.54, 'PN 28 (400 psi)']]],
    [65, '2-1/2"', 73.0, [['Sch 40', 5.16, 'PN 21 (300 psi)'], ['Sch 80', 7.01, 'PN 29 (420 psi)']]],
    [80, '3"', 88.9, [['Sch 40', 5.49, 'PN 18 (260 psi)'], ['Sch 80', 7.62, 'PN 26 (370 psi)']]],
    [100, '4"', 114.3, [['Sch 40', 6.02, 'PN 15 (220 psi)'], ['Sch 80', 8.56, 'PN 22 (320 psi)']]],
    [150, '6"', 168.3, [['Sch 40', 7.11, 'PN 12 (180 psi)'], ['Sch 80', 10.97, 'PN 19 (280 psi)']]],
    [200, '8"', 219.1, [['Sch 40', 8.18, 'PN 11 (160 psi)'], ['Sch 80', 12.70, 'PN 17 (250 psi)']]],
    [250, '10"', 273.0, [['Sch 40', 9.27, 'PN 10 (140 psi)'], ['Sch 80', 15.09, 'PN 16 (230 psi)']]],
    [300, '12"', 323.8, [['Sch 40', 10.31, 'PN 9 (130 psi)'], ['Sch 80', 17.48, 'PN 16 (230 psi)']]]
  ];
  pvc_ips.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, rating]) => {
      pipes.push({
        id: id++, standard: 'ASTM D1785 (PVC)', material: 'uPVC', material_key: 'pvc',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: rating, is_active: true
      });
    });
  });

  // 6. EN 545 / ISO 2531 Ductile Iron
  const di = [
    [80, '3"', 98.0, [['Class C40', 4.4, 'PN 40 (40 bar)'], ['Class K9', 6.0, 'PN 50 (50 bar)']]],
    [100, '4"', 118.0, [['Class C40', 4.4, 'PN 40 (40 bar)'], ['Class K9', 6.0, 'PN 50 (50 bar)']]],
    [150, '6"', 170.0, [['Class C40', 4.5, 'PN 40 (40 bar)'], ['Class K9', 6.0, 'PN 45 (45 bar)']]],
    [200, '8"', 222.0, [['Class C40', 4.7, 'PN 40 (40 bar)'], ['Class K9', 6.3, 'PN 40 (40 bar)']]],
    [250, '10"', 274.0, [['Class C40', 5.5, 'PN 40 (40 bar)'], ['Class K9', 6.8, 'PN 35 (35 bar)']]],
    [300, '12"', 326.0, [['Class C40', 6.2, 'PN 40 (40 bar)'], ['Class K9', 7.2, 'PN 32 (32 bar)']]],
    [350, '14"', 378.0, [['Class C30', 6.3, 'PN 30 (30 bar)'], ['Class K9', 7.7, 'PN 30 (30 bar)']]],
    [400, '16"', 429.0, [['Class C30', 6.5, 'PN 30 (30 bar)'], ['Class K9', 8.1, 'PN 30 (30 bar)']]],
    [500, '20"', 532.0, [['Class C30', 7.5, 'PN 30 (30 bar)'], ['Class K9', 9.0, 'PN 28 (28 bar)']]],
    [600, '24"', 635.0, [['Class C25', 7.9, 'PN 25 (25 bar)'], ['Class K9', 9.9, 'PN 25 (25 bar)']]]
  ];
  di.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, rating]) => {
      pipes.push({
        id: id++, standard: 'EN 545 / ISO 2531', material: 'Ductile Iron', material_key: 'ductile_iron',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: rating, is_active: true
      });
    });
  });

  // 7. SANS 62 / BS 1387 Galvanised Steel
  const galv = [
    [15, '1/2"', 21.3, [['Medium (Class B)', 2.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 3.25, 'PN 32 (32 bar)']]],
    [20, '3/4"', 26.9, [['Medium (Class B)', 2.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 3.25, 'PN 32 (32 bar)']]],
    [25, '1"', 33.7, [['Medium (Class B)', 3.25, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.05, 'PN 32 (32 bar)']]],
    [32, '1-1/4"', 42.4, [['Medium (Class B)', 3.25, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.05, 'PN 32 (32 bar)']]],
    [40, '1-1/2"', 48.3, [['Medium (Class B)', 3.25, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.05, 'PN 32 (32 bar)']]],
    [50, '2"', 60.3, [['Medium (Class B)', 3.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.50, 'PN 32 (32 bar)']]],
    [65, '2-1/2"', 76.1, [['Medium (Class B)', 3.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.50, 'PN 32 (32 bar)']]],
    [80, '3"', 88.9, [['Medium (Class B)', 4.05, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.85, 'PN 32 (32 bar)']]],
    [100, '4"', 114.3, [['Medium (Class B)', 4.50, 'PN 25 (25 bar)'], ['Heavy (Class C)', 5.40, 'PN 32 (32 bar)']]],
    [150, '6"', 165.1, [['Medium (Class B)', 4.85, 'PN 25 (25 bar)'], ['Heavy (Class C)', 5.40, 'PN 32 (32 bar)']]]
  ];
  galv.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, rating]) => {
      pipes.push({
        id: id++, standard: 'SANS 62 / BS 1387', material: 'Galvanised Steel', material_key: 'galvanized_iron',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: rating, is_active: true
      });
    });
  });

  return pipes;
}

const EMBEDDED_STANDARD_PIPES = generateStandardPipesCatalog();
let STANDARD_PIPES = (Array.isArray(window.__PMP_STANDARD_PIPES) && window.__PMP_STANDARD_PIPES.length > 0)
  ? window.__PMP_STANDARD_PIPES
  : EMBEDDED_STANDARD_PIPES;

// Also fetch from API in background to sync any dynamic database additions
fetch('/api/pipe-network/standard-pipes')
  .then(r => {
    if (!r.ok) return null;
    return r.json();
  })
  .then(d => {
    if (d && d.pipes && d.pipes.length > 0) {
      STANDARD_PIPES = d.pipes;
      if (state.selected && state.selected.kind === 'pipe') {
        const pipe = findPipe(state.selected.id);
        if (pipe) {
          populateStandardPipeFilters(pipe);
          updatePipeDetailsCard(pipe.props);
        }
      }
    }
  })
  .catch(() => {});

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
  viewMode: 'industrial', // 'industrial' (Visual thick 3D pipes) | 'schematic' (Thin 2D single-line)
  lastCalculation: null,
  pendingSelect: null,
};

let svgEl, nodesGroup, pipesGroup, draftPipeLine;
let guideLineX, guideLineY; // Dynamic magnetic alignment guidelines (horizontal & vertical)

// ============================================================================
// UTILITIES
// ============================================================================

function newId(prefix) { return `${prefix}-${state.nextId++}`; }
function snap(v) { return Math.round(v / GRID) * GRID; }
function findNode(id) { return state.nodes.find(n => n.id === id); }
function findPipe(id) { return state.pipes.find(p => p.id === id); }

/**
 * Smart magnetic axis snapping for smooth node movement.
 * Automatically checks if the dragged node is within 14px of the horizontal (Y)
 * or vertical (X) axis of ANY other node on the canvas.
 * When detected, it magnetically locks to that exact coordinate and displays
 * a dashed alignment guideline, making horizontal/vertical alignments effortless.
 */
function getSmartSnappedPosition(draggedNodeId, rawX, rawY) {
  const SNAP_THRESHOLD = 14; // pixels tolerance for magnetic axis lock
  let finalX = Math.round(rawX / GRID) * GRID;
  let finalY = Math.round(rawY / GRID) * GRID;
  let alignedY = null;
  let alignedX = null;

  for (const other of state.nodes) {
    if (other.id === draggedNodeId) continue;
    // Magnetic horizontal axis lock (matching other node's Y coordinate)
    if (Math.abs(rawY - other.y) <= SNAP_THRESHOLD) {
      finalY = other.y;
      alignedY = other.y;
    }
    // Magnetic vertical axis lock (matching other node's X coordinate)
    if (Math.abs(rawX - other.x) <= SNAP_THRESHOLD) {
      finalX = other.x;
      alignedX = other.x;
    }
  }

  // Update visual guideline indicators
  if (guideLineY) {
    if (alignedY !== null) {
      guideLineY.setAttribute('x1', -5000);
      guideLineY.setAttribute('y1', alignedY);
      guideLineY.setAttribute('x2', 5000);
      guideLineY.setAttribute('y2', alignedY);
      guideLineY.style.display = '';
    } else {
      guideLineY.style.display = 'none';
    }
  }

  if (guideLineX) {
    if (alignedX !== null) {
      guideLineX.setAttribute('x1', alignedX);
      guideLineX.setAttribute('y1', -5000);
      guideLineX.setAttribute('x2', alignedX);
      guideLineX.setAttribute('y2', 5000);
      guideLineX.style.display = '';
    } else {
      guideLineX.style.display = 'none';
    }
  }

  return { x: finalX, y: finalY };
}

function hideAlignmentGuides() {
  if (guideLineX) guideLineX.style.display = 'none';
  if (guideLineY) guideLineY.style.display = 'none';
}

/**
 * Synchronizes physical elevation integrity across the entire network.
 * 
 * Physical Law Enforced:
 *   ΔZ_pipe = Z_to - Z_from
 * 
 * Bidirectional Integrity Rules:
 * 1. Node elevation modified (sourceKind === 'node'):
 *    - Updates node.props.elevation_m.
 *    - Recalculates ΔZ on all incoming pipes (Z_node - Z_from) and outgoing pipes (Z_to - Z_node).
 * 2. Pipe elevation change modified (sourceKind === 'pipe'):
 *    - Updates pipe.props.elev_change_m = ΔZ.
 *    - Updates destination node's elevation: Z_to = Z_from + ΔZ.
 *    - Automatically updates ΔZ on any other pipes incident on that destination node.
 * 
 * This ensures that if Sump is at 0m and Suction line has an elevation change of 10m,
 * the Pump's elevation automatically becomes 10m, preserving complete physical consistency.
 */
function syncElevationIntegrity(sourceKind, sourceId, newValue) {
  const numVal = parseFloat(newValue) || 0;

  if (sourceKind === 'node') {
    const node = findNode(sourceId);
    if (!node) return;
    node.props.elevation_m = parseFloat(numVal.toFixed(3));

    // Maintain ΔZ = Z_to - Z_from across all connected pipes
    state.pipes.forEach(p => {
      if (p.fromNodeId === node.id || p.toNodeId === node.id) {
        const fn = findNode(p.fromNodeId);
        const tn = findNode(p.toNodeId);
        if (fn && tn) {
          p.props.elev_change_m = parseFloat(((tn.props.elevation_m || 0) - (fn.props.elevation_m || 0)).toFixed(3));
        }
      }
    });
  } else if (sourceKind === 'pipe') {
    const pipe = findPipe(sourceId);
    if (!pipe) return;
    pipe.props.elev_change_m = parseFloat(numVal.toFixed(3));

    const fn = findNode(pipe.fromNodeId);
    const tn = findNode(pipe.toNodeId);
    if (fn && tn) {
      // Destination node elevation = Source node elevation + ΔZ
      const fromElev = fn.props.elevation_m || 0;
      const newToElev = parseFloat((fromElev + pipe.props.elev_change_m).toFixed(3));
      tn.props.elevation_m = newToElev;

      // Propagate elevation update to all other pipes connected to the modified destination node
      state.pipes.forEach(otherPipe => {
        if (otherPipe.id !== pipe.id && (otherPipe.fromNodeId === tn.id || otherPipe.toNodeId === tn.id)) {
          const ofn = findNode(otherPipe.fromNodeId);
          const otn = findNode(otherPipe.toNodeId);
          if (ofn && otn) {
            otherPipe.props.elev_change_m = parseFloat(((otn.props.elevation_m || 0) - (ofn.props.elevation_m || 0)).toFixed(3));
          }
        }
      });
    }
  }

  // Refresh open inspector UI inputs if visible
  if (state.selected?.kind === 'node') {
    const selNode = findNode(state.selected.id);
    if (selNode) {
      setVal('np-elev', selNode.props.elevation_m ?? 0);
      const popElev = document.getElementById('pop-node-elev');
      if (popElev && popElev !== document.activeElement) popElev.value = selNode.props.elevation_m ?? 0;
    }
  } else if (state.selected?.kind === 'pipe') {
    const selPipe = findPipe(state.selected.id);
    if (selPipe) {
      const ppElev = document.getElementById('pp-elev-change');
      if (ppElev && ppElev !== document.activeElement) ppElev.value = selPipe.props.elev_change_m ?? 0;
      updatePipeElevationLabels(selPipe);
    }
  }

  renderLegend();
  saveNetworkToStorage();

  // If calculation results are visible, recalculate to reflect updated elevation head
  if (state.lastCalculation && document.getElementById('pn-results-section')?.style.display !== 'none') {
    runCalculation();
  }
}

function updatePipeElevationLabels(pipe) {
  if (!pipe) return;
  const fn = findNode(pipe.fromNodeId);
  const tn = findNode(pipe.toNodeId);
  const fromEl = document.getElementById('pp-elev-from-val');
  const toEl = document.getElementById('pp-elev-to-val');
  if (fromEl) fromEl.textContent = fn ? `${(fn.props.elevation_m || 0).toFixed(1)} m` : '--';
  if (toEl) toEl.textContent = tn ? `${(tn.props.elevation_m || 0).toFixed(1)} m` : '--';
}

function reconcileAllPipesElevation() {
  state.pipes.forEach(p => {
    const fn = findNode(p.fromNodeId);
    const tn = findNode(p.toNodeId);
    if (fn && tn) {
      p.props.elev_change_m = parseFloat(((tn.props.elevation_m || 0) - (fn.props.elevation_m || 0)).toFixed(3));
    }
  });
}

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
      case 'tee': return 14;
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
      case 'tee': return 12;
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
    case 'tank': return { label: lbl, elevation_m: 0 };
    case 'junction': return { label: lbl, elevation_m: 0 };
    case 'discharge': return { label: lbl, elevation_m: 0 };
    case 'tee': return { label: lbl, elevation_m: 0, fitting_key: 'tee_run_through', rotation_deg: 0, custom_k: null, is_custom_k: false };
    case 'valve': return { label: lbl, elevation_m: 0, fitting_key: 'gate_valve_open', custom_k: null, is_custom_k: false };
    case 'elbow': return { label: lbl, elevation_m: 0, fitting_key: 'elbow_90_standard', custom_k: null, is_custom_k: false };
    case 'pump': return { label: lbl, flow_m3h: 10, elevation_m: 0, pump_config: 'end_suction' };
    default: return { label: lbl };
  }
}

function defaultPipeProps(id) {
  let defStd = null;
  if (Array.isArray(STANDARD_PIPES) && STANDARD_PIPES.length > 0) {
    defStd = STANDARD_PIPES.find(p => p.standard.includes('B36.10M') && p.nb_mm === 100 && p.schedule_sdr.includes('40'))
      || STANDARD_PIPES.find(p => p.nb_mm === 100)
      || STANDARD_PIPES[0];
  }
  return {
    label: id,
    dimension_mode: 'standard', // 'standard' | 'custom'
    standard_pipe_id: defStd ? defStd.id : null,
    standard: defStd ? defStd.standard : 'ASME B36.10M',
    schedule_sdr: defStd ? defStd.schedule_sdr : 'Sch 40 (STD)',
    nb_mm: defStd ? defStd.nb_mm : 100,
    nb_inch: defStd ? defStd.nb_inch : '4"',
    od_mm: defStd ? defStd.od_mm : 114.3,
    wall_thickness_mm: defStd ? defStd.wall_thickness_mm : 6.02,
    id_mm: defStd ? defStd.id_mm : 102.26,
    pressure_rating: defStd ? defStd.pressure_rating : 'PN 79 bar (1145 psi)',
    diameter_mm: defStd ? defStd.id_mm : 100,
    length_m: 10.0,
    material: defStd ? defStd.material_key : 'commercial_steel',
    elev_change_m: 0.0,
    fittings: [],
    custom_k: 0.0,
    routing: 'auto',   // 'auto' | 'straight' | 'orthogonal'
  };
}
/**
 * Return the maximum number of pipes that can connect to a node.
 * If the node has a `pump_config` (for pumps), the suction / discharge
 * counts override the defaults.
 *
 * Also returns `sideLimits` — how many pipes each arm of the fitting can take.
 */
function getNodePortLimits(node) {
  switch (node.type) {
    // ── Fittings ─────────────────────────────────────────────────────
    case 'elbow':
      return { total: 2, perArm: { A: 1, B: 1 }, arms: ['A', 'B'] };
    case 'valve':
      return { total: 2, perArm: { A: 1, B: 1 }, arms: ['A', 'B'] };
    case 'tee':
      return { total: 3, perArm: { runA: 1, runB: 1, branch: 1 }, arms: ['runA', 'runB', 'branch'] };

    // ── Pump: varies by configuration ────────────────────────────────
    case 'pump': {
      const cfg = node.props.pump_config || 'end_suction';
      switch (cfg) {
        case 'double_suction':
          // 2 suction + 1 discharge
          return { total: 3, sides: { suction: 2, discharge: 1 } };
        case 'double_discharge':
          // 1 suction + 2 discharge
          return { total: 3, sides: { suction: 1, discharge: 2 } };
        case 'double_both':
          // 2 suction + 2 discharge
          return { total: 4, sides: { suction: 2, discharge: 2 } };
        case 'inline':
          // Inline pump: 1 in, 1 out
          return { total: 2, sides: { suction: 1, discharge: 1 } };
        case 'end_suction':
        default:
          // Standard end-suction: 1 suction + 1 discharge
          return { total: 2, sides: { suction: 1, discharge: 1 } };
      }
    }

    // ── Simple terminal nodes: 1 pipe ────────────────────────────────
    case 'discharge':
      return { total: 1 };

    // ── Manifold-style nodes: up to 6 pipes ──────────────────────────
    case 'junction':
      return { total: 6 };   // a tee is 3, but junctions can act as manifolds
    case 'reservoir':
      return { total: 4 };   // inlet + outlet + spares
    case 'tank':
      return { total: 4 };

    default:
      return { total: 2 };
  }
}

/**
 * Count how many pipes are connected to a node, optionally filtered by side.
 * For pumps, we classify each pipe as suction/discharge based on geometry:
 *   - if the pipe comes from the left/above of the pump, it's suction
 *   - if from the right/below, it's discharge
 */
function countNodeConnections(nodeId, nodeType, sideFilter) {
  const node = findNode(nodeId);
  if (!node) return 0;

  const pipes = state.pipes.filter(p =>
    p.fromNodeId === nodeId || p.toNodeId === nodeId
  );

  if (!sideFilter) return pipes.length;

  // Classify each pipe by direction for pumps
  if (nodeType === 'pump') {
    const suctionPipes = pipes.filter(p => {
      const other = otherNode(p, node);
      if (!other) return false;
      const ang = Math.atan2(other.y - node.y, other.x - node.x);
      // Suction side: left half of circle (angle between 90° and 270°)
      return Math.abs(normalizeAngle(ang)) > Math.PI / 2;
    }).length;

    const dischargePipes = pipes.length - suctionPipes;

    if (sideFilter === 'suction') return suctionPipes;
    if (sideFilter === 'discharge') return dischargePipes;
  }

  return pipes.length;
}

/**
 * Count how many pipes connect to a specific arm of an elbow/valve/tee.
 */
function countArmConnections(nodeId, armKey) {
  const node = findNode(nodeId);
  if (!node) return 0;

  if (node.type === 'tee') {
    const arms = getTeeArms(node);
    let armAng = arms.angA;
    if (armKey === 'runB') armAng = arms.angB;
    else if (armKey === 'branch') armAng = arms.angC;

    return state.pipes.filter(p => {
      if (p.fromNodeId !== nodeId && p.toNodeId !== nodeId) return false;
      const other = otherNode(p, node);
      if (!other) return false;
      const toOther = Math.atan2(other.y - node.y, other.x - node.x);
      const diff = Math.abs(normalizeAngle(toOther - armAng));
      return diff < Math.PI / 4;   // within ±45° of the arm
    }).length;
  }

  const arms = node.type === 'elbow' ? getElbowArms(node) : getValveArms(node);
  const armAng = armKey === 'A' ? arms.angA : arms.angB;

  return state.pipes.filter(p => {
    if (p.fromNodeId !== nodeId && p.toNodeId !== nodeId) return false;
    const other = otherNode(p, node);
    if (!other) return false;

    // Check if the other node is roughly along this arm's direction
    const toOther = Math.atan2(other.y - node.y, other.x - node.x);
    const diff = Math.abs(normalizeAngle(toOther - armAng));
    return diff < Math.PI / 4;   // within ±45° of the arm
  }).length;
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

function updateSaveIndicator(status = 'saved') {
  const el = document.getElementById('pn-save-indicator');
  if (!el) return;
  if (status === 'saved') {
    el.innerHTML = '<i class="bi bi-check2-circle" style="color:#22c55e;"></i> <span style="color:#22c55e;">Auto-saved</span>';
  } else if (status === 'saving') {
    el.innerHTML = '<i class="bi bi-arrow-repeat" style="color:#38bdf8;"></i> <span style="color:#38bdf8;">Saving...</span>';
  } else if (status === 'error') {
    el.innerHTML = '<i class="bi bi-exclamation-circle" style="color:#f87171;"></i> <span style="color:#f87171;">Save error</span>';
  }
}

let _saveServerTimeout = null;
function saveNetworkToServer(data, immediate = false) {
  if (_saveServerTimeout) {
    clearTimeout(_saveServerTimeout);
    _saveServerTimeout = null;
  }
  const doSave = async () => {
    try {
      const res = await fetch('/api/pipe-network/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        const respData = await res.json();
        if (respData.active_selection) {
          window.__PMP_ACTIVE_SELECTION = respData.active_selection;
          window.__PMP_SESSION_PIPE_NETWORK = respData.active_selection.pipe_network;
        }
        updateSaveIndicator('saved');
      }
    } catch (err) {
      console.warn('Could not sync pipe network to session:', err);
    }
  };

  if (immediate) {
    return doSave();
  } else {
    _saveServerTimeout = setTimeout(doSave, 300);
  }
}

function getNetworkPayload(extra = {}) {
  const flowEl = document.getElementById('pn-global-flow');
  const globalFlow = flowEl ? (parseFloat(flowEl.value) || 20) : 20;
  const solverEl = document.getElementById('pn-solver-method');
  const solverMethod = solverEl ? (solverEl.value || 'ggm') : 'ggm';
  const methodEl = document.getElementById('pn-friction-method');
  const frictionMethod = methodEl ? (methodEl.value || 'darcy_weisbach') : 'darcy_weisbach';

  return {
    version: 3,
    nodes: state.nodes,
    pipes: state.pipes,
    nextId: state.nextId,
    globalFlow: globalFlow,
    solverMethod: solverMethod,
    frictionMethod: frictionMethod,
    lastCalculation: state.lastCalculation || null,
    pan: state.pan,
    zoom: state.zoom,
    selected: state.selected ? { kind: state.selected.kind, id: state.selected.id } : null,
    savedAt: new Date().toISOString(),
    ...extra
  };
}

function saveNetworkToStorage(extra = {}) {
  const data = getNetworkPayload(extra);

  try {
    localStorage.setItem('pmpro_pipe_network', JSON.stringify(data));
    updateSaveIndicator('saved');
  } catch (e) {
    console.error('Failed to save pipe network to localStorage:', e);
    updateSaveIndicator('error');
  }

  // Also auto-sync to server session['active_selection']
  saveNetworkToServer(data, false);
}

async function saveNetwork() {
  updateSaveIndicator('saving');
  const data = getNetworkPayload();
  try {
    localStorage.setItem('pmpro_pipe_network', JSON.stringify(data));
  } catch (e) { }

  try {
    const res = await fetch('/api/pipe-network/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.ok) {
      const respData = await res.json();
      if (respData.active_selection) {
        window.__PMP_ACTIVE_SELECTION = respData.active_selection;
        window.__PMP_SESSION_PIPE_NETWORK = respData.active_selection.pipe_network;
      }
      updateSaveIndicator('saved');
      toast('Saved to session active_selection!', 'success');
      return;
    }
  } catch (e) {
    console.warn('Server session save failed:', e);
  }
  toast('Network saved locally', 'info');
}

function loadNetworkFromStorage() {
  let d = null;

  // 1. First priority: Server session active_selection
  if (window.__PMP_SESSION_PIPE_NETWORK && typeof window.__PMP_SESSION_PIPE_NETWORK === 'object') {
    if (Array.isArray(window.__PMP_SESSION_PIPE_NETWORK.nodes) && (window.__PMP_SESSION_PIPE_NETWORK.nodes.length > 0 || window.__PMP_SESSION_PIPE_NETWORK.explicitClear)) {
      d = window.__PMP_SESSION_PIPE_NETWORK;
    }
  }

  // 2. Second priority: LocalStorage
  if (!d) {
    const saved = localStorage.getItem('pmpro_pipe_network');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed.nodes) && (parsed.nodes.length > 0 || parsed.explicitClear)) {
          d = parsed;
        }
      } catch (e) {
        console.error('Failed to load pipe network from localStorage:', e);
      }
    }
  }

  // 3. Fallback check for session with empty network
  if (!d && window.__PMP_SESSION_PIPE_NETWORK && Array.isArray(window.__PMP_SESSION_PIPE_NETWORK.nodes)) {
    d = window.__PMP_SESSION_PIPE_NETWORK;
  }

  if (!d || !Array.isArray(d.nodes) || !Array.isArray(d.pipes)) {
    return false;
  }

  // If stored network is older demo layout with Tee junction, return false to load new simple demo
  const isOldDemo = d.nodes && d.nodes.some(n => n.type === 'junction' && n.props?.label === 'Tee')
    && d.nodes.some(n => n.type === 'tank' && n.props?.label === 'Overhead Tank');
  if (isOldDemo || (d.nodes.length === 0 && d.pipes.length === 0 && !d.explicitClear)) {
    return false;
  }

  state.nodes = d.nodes;
  state.pipes = d.pipes;

  // Reconcile pipe elevation changes with node elevations (Delta Z = Z_to - Z_from)
  reconcileAllPipesElevation();

  // Restore network solver algorithm
  const savedSolver = d.solverMethod || localStorage.getItem('pmpro_solver_method');
  if (savedSolver) {
    const solverEl = document.getElementById('pn-solver-method');
    if (solverEl) solverEl.value = savedSolver;
  }

  // Restore calculation / friction method
  const savedMethod = d.frictionMethod || localStorage.getItem('pmpro_calc_method');
  if (savedMethod) {
    const methodEl = document.getElementById('pn-friction-method');
    if (methodEl) methodEl.value = savedMethod;
  }

  // Migrate pipes created before routing was introduced
  state.pipes.forEach(p => {
    if (p.props && !p.props.routing) p.props.routing = 'auto';
  });

  const maxIdFromElements = Math.max(
    0,
    ...[...d.nodes, ...d.pipes].map(x => {
      const parts = (x.id || '').split('-');
      return parseInt(parts[1], 10) || 0;
    })
  );
  state.nextId = (typeof d.nextId === 'number' && !isNaN(d.nextId))
    ? Math.max(d.nextId, maxIdFromElements + 1)
    : maxIdFromElements + 1;

  if (d.globalFlow) {
    const flowInput = document.getElementById('pn-global-flow');
    if (flowInput) flowInput.value = d.globalFlow;
  }

  if (d.pan && typeof d.pan.x === 'number' && typeof d.pan.y === 'number') {
    state.pan = { x: d.pan.x, y: d.pan.y };
  }
  if (d.zoom && typeof d.zoom === 'number' && !isNaN(d.zoom)) {
    state.zoom = Math.min(3, Math.max(0.2, d.zoom));
  }

  if (d.lastCalculation && d.lastCalculation.summary && d.lastCalculation.results) {
    state.lastCalculation = d.lastCalculation;
    displayResults(d.lastCalculation);
  }

  if (d.selected && d.selected.kind && d.selected.id) {
    state.pendingSelect = d.selected;
  }

  // Reconcile continuous pipe runs across inline fitting nodes upon loading
  reconcilePipeRuns();

  updateSaveIndicator('saved');
  return true;
}

// ============================================================================
// VIEW MODE & RENDERING
// ============================================================================

/**
 * Switch view mode between 'industrial' (Visual realistic 3D thick pipes)
 * and 'schematic' (Thin 2D single-line CAD blueprint diagram).
 * 
 * Behavior:
 *  - Updates state.viewMode.
 *  - Toggles active-tool styling on #btn-view-industrial and #btn-view-schematic buttons.
 *  - Persists user selection in localStorage ('pmp_pipe_view_mode') to survive page reloads.
 *  - Re-renders all pipes, nodes, and legend with the new view styling.
 * 
 * @param {'schematic'|'industrial'} mode
 */
function setViewMode(mode) {
  state.viewMode = mode;
  const btnSchematic = document.getElementById('btn-view-schematic');
  const btnIndustrial = document.getElementById('btn-view-industrial');
  if (btnSchematic && btnIndustrial) {
    if (mode === 'industrial') {
      btnIndustrial.classList.add('active-tool');
      btnSchematic.classList.remove('active-tool');
    } else {
      btnSchematic.classList.add('active-tool');
      btnIndustrial.classList.remove('active-tool');
    }
  }
  localStorage.setItem('pmp_pipe_view_mode', mode);
  renderAll();
}

/**
 * Dynamically renders the Legend Overlay based strictly on elements present in the active network.
 * 
 * Behavior:
 *  - Scans state.pipes for distinct pipe diameters present on canvas.
 *  - Scans state.nodes for active node types (pumps, tanks, reservoirs, junctions, valves, elbows, faucets).
 *  - Scans state.pipes for inline fittings (check valves, strainers, etc.).
 *  - If the canvas is empty, displays a clean "No elements on canvas" placeholder.
 *  - Excludes all element types that are not currently part of the network diagram.
 */
function renderLegend() {
  const itemsContainer = document.getElementById('pn-legend-items');
  if (!itemsContainer) return;

  const rows = [];

  // 1. Group pipes by diameter
  const diameterCounts = {};
  state.pipes.forEach(p => {
    const d = p.props.diameter_mm || 100;
    diameterCounts[d] = (diameterCounts[d] || 0) + 1;
  });

  const sortedDiameters = Object.keys(diameterCounts).map(Number).sort((a, b) => b - a);
  sortedDiameters.forEach(d => {
    const count = diameterCounts[d];
    let label = `${d}mm Pipe`;
    if (d >= 150) label = `${d}mm Main Pipe`;
    else if (d >= 80) label = `${d}mm Distribution Pipe`;
    else label = `${d}mm Branch Pipe`;

    const thickness = Math.max(2, Math.min(6, Math.round(d / 30)));
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <div style="width:18px;height:${thickness}px;background:#0284c7;border-radius:1px;"></div>
        </div>
        <span>${label}${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  });

  // 2. Count nodes by type
  const nodeCounts = {};
  state.nodes.forEach(n => {
    nodeCounts[n.type] = (nodeCounts[n.type] || 0) + 1;
  });

  // Reservoir / Sump
  if (nodeCounts.reservoir) {
    const count = nodeCounts.reservoir;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <rect x="2" y="3" width="12" height="8" rx="1.5" fill="#0369a1" stroke="#38bdf8" stroke-width="1" />
            <line x1="4" y1="6" x2="12" y2="6" stroke="#bae6fd" stroke-width="1" />
          </svg>
        </div>
        <span>Reservoir / Sump${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // Pump
  if (nodeCounts.pump) {
    const count = nodeCounts.pump;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <circle cx="8" cy="7" r="5" fill="#0284c7" stroke="#38bdf8" stroke-width="1.5" />
            <polygon points="6,7 10,4.5 10,9.5" fill="#ffffff" />
          </svg>
        </div>
        <span>Pump${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // Water Tank
  if (nodeCounts.tank) {
    const count = nodeCounts.tank;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <rect x="3" y="2" width="10" height="10" rx="2" fill="#1e293b" stroke="#f59e0b" stroke-width="1.2" />
            <ellipse cx="8" cy="2" rx="3.5" ry="1.5" fill="#f59e0b" />
          </svg>
        </div>
        <span>Water Tank${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // Manifold Junction
  if (nodeCounts.junction) {
    const count = nodeCounts.junction;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <circle cx="8" cy="7" r="5" fill="#64748b" stroke="#f59e0b" stroke-width="1.5" />
          </svg>
        </div>
        <span>Manifold Junction${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // 3-Way Pipe Tee
  if (nodeCounts.tee) {
    const count = nodeCounts.tee;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <line x1="2" y1="4" x2="14" y2="4" stroke="#f97316" stroke-width="2.5" />
            <line x1="8" y1="4" x2="8" y2="12" stroke="#f97316" stroke-width="2.5" />
          </svg>
        </div>
        <span>Pipe Tee Fitting${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // Valve nodes
  if (nodeCounts.valve) {
    const count = nodeCounts.valve;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <polygon points="2,3 8,7 2,11" fill="#ef4444" />
            <polygon points="14,3 8,7 14,11" fill="#ef4444" />
            <line x1="8" y1="2" x2="8" y2="7" stroke="#ef4444" stroke-width="1.5" />
          </svg>
        </div>
        <span>Ball / Gate Valve${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // Elbow nodes
  if (nodeCounts.elbow) {
    const count = nodeCounts.elbow;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <path d="M 2,12 L 2,4 A 4,4 0 0,1 6,0 L 14,0" fill="none" stroke="#3b82f6" stroke-width="2.5" />
            <circle cx="2" cy="12" r="2" fill="#94a3b8" />
            <circle cx="14" cy="0" r="2" fill="#94a3b8" />
          </svg>
        </div>
        <span>Elbow Fitting${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // Discharge / Faucet
  if (nodeCounts.discharge) {
    const count = nodeCounts.discharge;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <path d="M 2,5 L 10,5 L 10,10 L 8,10" fill="none" stroke="#94a3b8" stroke-width="2" />
            <line x1="6" y1="2" x2="14" y2="2" stroke="#ef4444" stroke-width="2" />
            <circle cx="9" cy="12" r="1.5" fill="#0284c7" />
          </svg>
        </div>
        <span>Faucet / Tap${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  }

  // 3. Inline pipe fittings attached to pipes
  const pipeFittingCounts = {};
  state.pipes.forEach(p => {
    (p.props.fittings || []).forEach(fKey => {
      pipeFittingCounts[fKey] = (pipeFittingCounts[fKey] || 0) + 1;
    });
  });

  Object.entries(pipeFittingCounts).forEach(([fKey, count]) => {
    const fitObj = FITTINGS.find(f => f.key === fKey);
    const label = fitObj ? fitObj.label : fKey;
    rows.push(`
      <div class="pn-legend-row">
        <div class="pn-legend-swatch">
          <svg width="16" height="14" viewBox="0 0 16 14">
            <circle cx="8" cy="7" r="4.5" fill="#334155" stroke="#a78bfa" stroke-width="1.5" />
            <circle cx="8" cy="7" r="1.5" fill="#a78bfa" />
          </svg>
        </div>
        <span>${label}${count > 1 ? ` (${count})` : ''}</span>
      </div>
    `);
  });

  // Render or show placeholder
  if (rows.length === 0) {
    itemsContainer.innerHTML = `<div style="color:#64748b;font-size:11px;font-style:italic;padding:4px 0;">No elements on canvas</div>`;
  } else {
    itemsContainer.innerHTML = rows.join('');
  }
}

function renderAll() {
  renderPipes();
  renderNodes();
  renderLegend();
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
    const isFittingTool = state.mode && state.mode.startsWith('add-') && ['valve', 'elbow', 'tee'].includes(state.mode.replace('add-', ''));
    const isSel = state.selected?.kind === 'pipe' && state.selected.id === pipe.id;

    const g = mkSVG('g', {});
    g.style.cursor = isFittingTool ? 'crosshair' : 'pointer';
    g.addEventListener('click', e => {
      e.stopPropagation();
      // If user has a fitting placement tool active, clicking on the pipe inserts the fitting into the pipe!
      if (state.mode && state.mode.startsWith('add-')) {
        const type = state.mode.replace('add-', '');
        if (['valve', 'elbow', 'tee'].includes(type)) {
          const pos = toSVG(e);
          insertFittingOnPipe(pipe, type, pos);
          return;
        }
      }
      selectItem('pipe', pipe.id);
    });

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

    // Label: Displays the continuous Pipe ID/label (e.g. P-15) and diameter.
    // Suppress text on very short connector segments (<42px) to keep canvas clean between close fittings.
    const segDistance = Math.hypot(toPt.x - fromPt.x, toPt.y - fromPt.y);
    if (segDistance >= 42) {
      const lbl = mkSVG('text', {
        x: mid.x, y: mid.y - (state.viewMode === 'industrial' ? 22 : 10),
        'font-size': 10, fill: '#8b949e',
        'font-family': 'Inter, sans-serif',
        'text-anchor': 'middle', 'pointer-events': 'none',
      });
      lbl.textContent = `${pipe.props.label || pipe.id}  D${pipe.props.diameter_mm}mm`;
      g.appendChild(lbl);
    }

    // Hit target (expanded width makes clicking on pipes to insert fittings or select easy)
    g.appendChild(mkSVG('path', {
      d: pathD, fill: 'none', stroke: 'transparent',
      'stroke-width': state.viewMode === 'industrial' ? 44 : 22,
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

  // ── Tee: pick the arm (runA, runB, or branch) closest to the other node ──
  if (node.type === 'tee') {
    const arms = getTeeArms(node);
    const candidateArms = [
      { pt: arms.runA, ang: arms.angA },
      { pt: arms.runB, ang: arms.angB },
      { pt: arms.branch, ang: arms.angC }
    ];
    let best = candidateArms[0];
    let bestDist = Math.hypot(otherNode.x - best.pt.x, otherNode.y - best.pt.y);
    for (let i = 1; i < candidateArms.length; i++) {
      const d = Math.hypot(otherNode.x - candidateArms[i].pt.x, otherNode.y - candidateArms[i].pt.y);
      if (d < bestDist) {
        bestDist = d;
        best = candidateArms[i];
      }
    }
    return {
      x: best.pt.x,
      y: best.pt.y,
      isTee: true,
      isFitting: true,
      dirAngle: best.ang,
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
  if (node.type === 'tee') {
    const arms = getTeeArms(node);
    const candidateArms = [
      { pt: arms.runA, ang: arms.angA },
      { pt: arms.runB, ang: arms.angB },
      { pt: arms.branch, ang: arms.angC }
    ];
    let best = candidateArms[0];
    let bestDist = Math.hypot(tx - best.pt.x, ty - best.pt.y);
    for (let i = 1; i < candidateArms.length; i++) {
      const d = Math.hypot(tx - candidateArms[i].pt.x, ty - candidateArms[i].pt.y);
      if (d < bestDist) {
        bestDist = d;
        best = candidateArms[i];
      }
    }
    return { x: best.pt.x, y: best.pt.y, dirAngle: best.ang, isTee: true };
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

function getTeeArms(node) {
  const rotationDeg = node.props.rotation_deg || 0;
  const rad = (rotationDeg * Math.PI) / 180;
  const armLength = 24;

  // Run A = 180° + rad (Left), Run B = 0° + rad (Right), Branch = 90° + rad (Down)
  const angA = normalizeAngle(Math.PI + rad);
  const angB = normalizeAngle(rad);
  const angC = normalizeAngle(Math.PI / 2 + rad);

  return {
    angA, angB, angC,
    runA: {
      x: node.x + Math.cos(angA) * armLength,
      y: node.y + Math.sin(angA) * armLength,
    },
    runB: {
      x: node.x + Math.cos(angB) * armLength,
      y: node.y + Math.sin(angB) * armLength,
    },
    branch: {
      x: node.x + Math.cos(angC) * armLength,
      y: node.y + Math.sin(angC) * armLength,
    },
    armLength,
    rotationDeg,
  };
}

/**
 * Return current effective K-factor for any fitting node (valve, elbow, tee).
 * Respects custom K override when node.props.is_custom_k is true.
 */
function getNodeKFactor(node) {
  if (!node) return 0;
  if (node.props.is_custom_k && node.props.custom_k !== null && node.props.custom_k !== undefined && !isNaN(Number(node.props.custom_k))) {
    return Number(node.props.custom_k);
  }
  const key = node.props.fitting_key;
  if (key) {
    const found = FITTINGS.find(f => f.key === key);
    if (found && typeof found.K === 'number') return found.K;
  }
  const defaults = {
    'tee_run_through': 0.40,
    'tee_branch_flow': 1.80,
    'elbow_90_standard': 0.90,
    'elbow_90_long_radius': 0.60,
    'elbow_45': 0.40,
    'gate_valve_open': 0.20,
    'gate_valve_half': 5.60,
    'globe_valve_open': 10.0,
    'ball_valve_open': 0.05,
    'butterfly_valve_open': 0.30,
    'check_valve_swing': 2.50,
    'check_valve_ball': 4.50,
  };
  return defaults[key] || 0;
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
    case 'tee': drawTeeNode(g, isSel, node); break;
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
  // Connection port + fitting arm hints (only in connect mode)
  if (state.mode === 'connect') {
    const limits = getNodePortLimits(node);
    const used = countNodeConnections(node.id, node.type);
    const isFull = used >= limits.total;

    // Port circle: green if free, red if full
    const port = mkSVG('circle', {
      r: 7,
      fill: isFull ? '#ef4444' : '#22c55e',
      stroke: isFull ? '#ef4444' : '#22c55e',
      'stroke-width': 2,
      opacity: isFull ? 0.5 : 0.9,
    });
    port.style.cursor = isFull ? 'not-allowed' : 'crosshair';
    port.addEventListener('click', e => { e.stopPropagation(); onPortClick(node.id); });
    g.appendChild(port);

    // Small badge with port count for pumps
    if (node.type === 'pump') {
      const badge = mkSVG('text', {
        x: 0, y: -14,
        'text-anchor': 'middle',
        'font-size': 9, fill: isFull ? '#ef4444' : '#22c55e',
        'font-family': 'Inter, sans-serif', 'font-weight': 700,
        'pointer-events': 'none',
      });
      badge.textContent = `${used}/${limits.total}`;
      g.appendChild(badge);
    }
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
 * Valve node — drawn as an inline symbol that sits ON the pipe.
 * Renders distinct shapes according to valve type (ball, gate, globe, butterfly, check).
 */
function drawValveNode(g, sel, node) {
  const fKey = node?.props?.fitting_key || 'gate_valve_open';
  const kVal = getNodeKFactor(node);
  const isCustom = Boolean(node?.props?.is_custom_k);
  const color = sel ? '#fca5a5' : '#ef4444';
  const fill = sel ? '#7f1d1d' : '#450a0a';

  if (state.viewMode === 'industrial') {
    if (fKey.startsWith('ball_valve')) {
      // Ball valve: spherical body with quarter-turn handle
      g.appendChild(mkSVG('circle', { r: 11, fill: '#64748b', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 2 }));
      g.appendChild(mkSVG('circle', { r: 5, fill: '#38bdf8', opacity: 0.85 }));
      // Flanges
      g.appendChild(mkSVG('rect', { x: -16, y: -7, width: 4, height: 14, rx: 1, fill: '#475569', stroke: '#1e293b' }));
      g.appendChild(mkSVG('rect', { x: 12, y: -7, width: 4, height: 14, rx: 1, fill: '#475569', stroke: '#1e293b' }));
      // Quarter-turn handle
      g.appendChild(mkSVG('rect', { x: -2, y: -16, width: 4, height: 7, fill: '#cbd5e1' }));
      g.appendChild(mkSVG('rect', { x: -2, y: -20, width: 16, height: 5, rx: 2.5, fill: '#3b82f6', stroke: '#1d4ed8' }));
    } else if (fKey.startsWith('check_valve')) {
      // Check valve: directional body with internal diode arrow
      g.appendChild(mkSVG('rect', { x: -14, y: -10, width: 28, height: 20, rx: 4, fill: '#475569', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 1.5 }));
      g.appendChild(mkSVG('polygon', { points: '-6,-7 6,0 -6,7', fill: '#22c55e' }));
      g.appendChild(mkSVG('line', { x1: 6, y1: -7, x2: 6, y2: 7, stroke: '#22c55e', 'stroke-width': 2 }));
    } else if (fKey.startsWith('globe_valve')) {
      // Globe valve: bowtie with circular globe cavity & handwheel
      g.appendChild(mkSVG('polygon', { points: '-16,-10 0,0 -16,10 16,-10 0,0 16,10', fill: '#64748b', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 1.5 }));
      g.appendChild(mkSVG('circle', { r: 5, fill: '#94a3b8', stroke: '#334155', 'stroke-width': 1 }));
      g.appendChild(mkSVG('rect', { x: -2, y: -22, width: 4, height: 12, fill: '#cbd5e1' }));
      g.appendChild(mkSVG('circle', { cx: 0, cy: -24, r: 8, fill: 'none', stroke: '#ef4444', 'stroke-width': 2.5 }));
    } else if (fKey.startsWith('butterfly_valve')) {
      // Butterfly valve: slim body with circular throttle disc
      g.appendChild(mkSVG('circle', { r: 12, fill: '#475569', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 2 }));
      g.appendChild(mkSVG('line', { x1: -7, y1: -7, x2: 7, y2: 7, stroke: '#f59e0b', 'stroke-width': 3, 'stroke-linecap': 'round' }));
      g.appendChild(mkSVG('rect', { x: -2, y: -22, width: 4, height: 11, fill: '#cbd5e1' }));
      g.appendChild(mkSVG('rect', { x: -10, y: -26, width: 20, height: 5, rx: 2.5, fill: '#f59e0b' }));
    } else {
      // Gate valve: standard bowtie body with vertical spindle & handwheel
      g.appendChild(mkSVG('polygon', {
        points: '-16,-10 0,0 -16,10 16,-10 0,0 16,10',
        fill: '#94a3b8', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 1.5,
      }));
      g.appendChild(mkSVG('rect', { x: -2, y: -22, width: 4, height: 12, fill: '#cbd5e1' }));
      g.appendChild(mkSVG('rect', { x: -12, y: -28, width: 24, height: 5, rx: 2.5, fill: fKey.includes('half') ? '#f59e0b' : '#ef4444', stroke: '#7f1d1d' }));
      if (fKey.includes('half')) {
        g.appendChild(mkSVG('line', { x1: 0, y1: -4, x2: 0, y2: 4, stroke: '#f59e0b', 'stroke-width': 2.5 }));
      }
    }
  } else {
    // Schematic view (symbolic ANSI standard)
    if (fKey.startsWith('ball_valve')) {
      g.appendChild(mkSVG('polygon', { points: '-14,-9 0,0 -14,9 14,-9 0,0 14,9', fill: fill, stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round' }));
      g.appendChild(mkSVG('circle', { cx: 0, cy: 0, r: 4, fill: '#38bdf8' }));
    } else if (fKey.startsWith('check_valve')) {
      g.appendChild(mkSVG('polygon', { points: '-12,-8 6,0 -12,8', fill: 'none', stroke: color, 'stroke-width': 2 }));
      g.appendChild(mkSVG('line', { x1: 6, y1: -8, x2: 6, y2: 8, stroke: color, 'stroke-width': 2 }));
    } else if (fKey.startsWith('globe_valve')) {
      g.appendChild(mkSVG('polygon', { points: '-14,-9 0,0 -14,9 14,-9 0,0 14,9', fill: fill, stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round' }));
      g.appendChild(mkSVG('circle', { cx: 0, cy: 0, r: 4, fill: color }));
    } else {
      g.appendChild(mkSVG('polygon', {
        points: '-14,-9 0,0 -14,9 14,-9 0,0 14,9',
        fill: fill, stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round',
      }));
      g.appendChild(mkSVG('line', { x1: 0, y1: 0, x2: 0, y2: -14, stroke: color, 'stroke-width': 1.5 }));
      g.appendChild(mkSVG('line', { x1: -7, y1: -14, x2: 7, y2: -14, stroke: color, 'stroke-width': 2 }));
    }
  }

  // K-factor badge below valve
  const badgeText = `K=${kVal.toFixed(2)}${isCustom ? '*' : ''}`;
  const badgeY = 22;
  const badgeW = Math.max(46, badgeText.length * 6.5 + 8);
  const badgeBg = mkSVG('rect', {
    x: -badgeW / 2, y: badgeY - 8, width: badgeW, height: 15, rx: 3.5,
    fill: '#0f172a', stroke: isCustom ? '#f59e0b' : '#ef4444', 'stroke-width': 1, opacity: 0.95,
  });
  g.appendChild(badgeBg);
  const badgeTxt = mkSVG('text', {
    x: 0, y: badgeY + 3, 'text-anchor': 'middle', 'font-size': 9, 'font-weight': 700,
    fill: isCustom ? '#fbbf24' : '#fca5a5', 'font-family': 'Inter, monospace', 'pointer-events': 'none',
  });
  badgeTxt.textContent = badgeText;
  g.appendChild(badgeTxt);

  // Hit area
  g.appendChild(mkSVG('circle', { cx: 0, cy: 0, r: 24, fill: 'transparent', 'pointer-events': 'all' }));
}

/**
 * Tee fitting node — renders a proper 3-way piping tee with run and branch arms.
 * Renders metallic cylindrical bodies with collars and flow arrows in industrial view,
 * and standard ANSI 3-way symbols in schematic view.
 */
function drawTeeNode(g, sel, node) {
  const rot = node.props.rotation_deg || 0;
  const isBranch = node.props.fitting_key === 'tee_branch_flow';
  const kVal = getNodeKFactor(node);
  const isCustom = Boolean(node.props.is_custom_k);

  // Group with branch orientation rotation applied
  const tg = mkSVG('g', { transform: `rotate(${rot})` });

  if (state.viewMode === 'industrial') {
    // Outer outline (dark contour)
    tg.appendChild(mkSVG('path', {
      d: 'M -22,-9 L 22,-9 L 22,9 L 9,9 L 9,22 L -9,22 L -9,9 L -22,9 Z',
      fill: '#0f172a', stroke: sel ? '#f59e0b' : '#334155', 'stroke-width': 2,
    }));
    // Inner metallic tee pipe body
    tg.appendChild(mkSVG('path', {
      d: 'M -20,-7 L 20,-7 L 20,7 L 7,7 L 7,20 L -7,20 L -7,7 L -20,7 Z',
      fill: '#94a3b8',
    }));
    // Flanged end collars at the three ports
    tg.appendChild(mkSVG('rect', { x: -24, y: -10, width: 4, height: 20, rx: 1.5, fill: '#64748b', stroke: '#334155', 'stroke-width': 1 }));
    tg.appendChild(mkSVG('rect', { x: 20, y: -10, width: 4, height: 20, rx: 1.5, fill: '#64748b', stroke: '#334155', 'stroke-width': 1 }));
    tg.appendChild(mkSVG('rect', { x: -10, y: 18, width: 20, height: 4, rx: 1.5, fill: '#64748b', stroke: '#334155', 'stroke-width': 1 }));

    // Shading highlight on pipe crown
    tg.appendChild(mkSVG('line', { x1: -18, y1: -2, x2: 18, y2: -2, stroke: 'rgba(255,255,255,0.4)', 'stroke-width': 2 }));
    tg.appendChild(mkSVG('line', { x1: 0, y1: -2, x2: 0, y2: 18, stroke: 'rgba(255,255,255,0.3)', 'stroke-width': 2 }));

    // Flow indicator path (orange accent)
    if (isBranch) {
      // Curved 90° diversion arrow from left run into branch
      tg.appendChild(mkSVG('path', {
        d: 'M -14,0 Q 0,0 0,14', fill: 'none', stroke: '#f97316', 'stroke-width': 2.5, 'stroke-linecap': 'round',
      }));
      tg.appendChild(mkSVG('polygon', { points: '-3,11 0,16 3,11', fill: '#f97316' }));
    } else {
      // Straight through run arrow
      tg.appendChild(mkSVG('line', {
        x1: -14, y1: 0, x2: 12, y2: 0, stroke: '#38bdf8', 'stroke-width': 2.5, 'stroke-linecap': 'round',
      }));
      tg.appendChild(mkSVG('polygon', { points: '10,-3 15,0 10,3', fill: '#38bdf8' }));
    }
  } else {
    // Schematic view (single-line blueprint)
    const color = sel ? '#f59e0b' : '#38bdf8';
    tg.appendChild(mkSVG('line', { x1: -20, y1: 0, x2: 20, y2: 0, stroke: color, 'stroke-width': 3, 'stroke-linecap': 'round' }));
    tg.appendChild(mkSVG('line', { x1: 0, y1: 0, x2: 0, y2: 20, stroke: color, 'stroke-width': 3, 'stroke-linecap': 'round' }));
    tg.appendChild(mkSVG('circle', { cx: 0, cy: 0, r: 3.5, fill: color }));
    // Terminal ticks
    tg.appendChild(mkSVG('line', { x1: -20, y1: -4, x2: -20, y2: 4, stroke: color, 'stroke-width': 1.5 }));
    tg.appendChild(mkSVG('line', { x1: 20, y1: -4, x2: 20, y2: 4, stroke: color, 'stroke-width': 1.5 }));
    tg.appendChild(mkSVG('line', { x1: -4, y1: 20, x2: 4, y2: 20, stroke: color, 'stroke-width': 1.5 }));
  }
  g.appendChild(tg);

  // K-factor badge (always horizontal for readability)
  const badgeText = `K=${kVal.toFixed(2)}${isCustom ? '*' : ''}`;
  const badgeY = -22;
  const badgeW = Math.max(48, badgeText.length * 6.5 + 10);
  const badgeBg = mkSVG('rect', {
    x: -badgeW / 2, y: badgeY - 8, width: badgeW, height: 16, rx: 4,
    fill: '#0f172a', stroke: isCustom ? '#f59e0b' : '#38bdf8', 'stroke-width': 1, opacity: 0.95,
  });
  g.appendChild(badgeBg);
  const badgeTxt = mkSVG('text', {
    x: 0, y: badgeY + 3.5, 'text-anchor': 'middle', 'font-size': 9.5, 'font-weight': 700,
    fill: isCustom ? '#fbbf24' : '#7dd3fc', 'font-family': 'Inter, monospace', 'pointer-events': 'none',
  });
  badgeTxt.textContent = badgeText;
  g.appendChild(badgeTxt);

  // Hit area
  g.appendChild(mkSVG('circle', { cx: 0, cy: 0, r: 28, fill: 'transparent', 'pointer-events': 'all' }));
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
  updateContextPopoverPosition();
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================

function onCanvasClick(e) {
  if (state.mode === 'select') { selectItem(null); return; }
  if (state.mode.startsWith('add-')) {
    const type = state.mode.replace('add-', '');
    const pos = toSVG(e);

    // If placing an inline fitting (valve, elbow, tee) and clicked near an existing pipe,
    // insert it directly into the middle of that pipe!
    if (['valve', 'elbow', 'tee'].includes(type)) {
      const targetPipe = findPipeNearPoint(pos.x, pos.y, 25);
      if (targetPipe) {
        insertFittingOnPipe(targetPipe, type, pos);
        return;
      }
    }

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
    // ── First click: check the SOURCE node has a free port ─────────
    const srcNode = findNode(nodeId);
    if (!srcNode) return;

    const limits = getNodePortLimits(srcNode);
    const used = countNodeConnections(nodeId, srcNode.type);
    if (used >= limits.total) {
      toast(`Cannot start pipe — ${srcNode.type} already has ${used}/${limits.total} connections.`, 'warn');
      return;
    }

    state.drawingPipe = { fromNodeId: nodeId, mouseX: 0, mouseY: 0 };
    toast('Click a destination node to complete the pipe.');
    return;
  }

  // ── Second click: check BOTH ends ─────────────────────────────
  const fromId = state.drawingPipe.fromNodeId;
  const toId = nodeId;

  if (fromId === nodeId) {
    toast('Cannot connect a node to itself.', 'warn');
    return;
  }

  const srcNode = findNode(fromId);
  const dstNode = findNode(toId);
  if (!srcNode || !dstNode) return;

  // Duplicate check
  const dup = state.pipes.some(
    p => (p.fromNodeId === fromId && p.toNodeId === toId) ||
      (p.fromNodeId === toId && p.toNodeId === fromId)
  );
  if (dup) {
    toast('A pipe already connects these two nodes.', 'warn');
    state.drawingPipe = null; updateDraftLine(); return;
  }

  // ── SOURCE validation ────────────────────────────────────────
  if (!canConnect(srcNode, dstNode, fromId, toId)) {
    state.drawingPipe = null; updateDraftLine(); return;
  }
  // ── DESTINATION validation ───────────────────────────────────
  if (!canConnect(dstNode, srcNode, toId, fromId)) {
    state.drawingPipe = null; updateDraftLine(); return;
  }

  addPipe(fromId, toId);
  state.drawingPipe = null;
  updateDraftLine();
  setMode('select');
}

/**
 * Validate that `node` can accept one more pipe coming from `otherNode`.
 * Returns true if OK; shows a toast and returns false otherwise.
 */
function canConnect(node, otherNode, nodeId, otherNodeId) {
  const limits = getNodePortLimits(node);

  // 1. Total connection count
  const totalUsed = countNodeConnections(nodeId, node.type);
  if (totalUsed >= limits.total) {
    toast(`Cannot connect — ${node.type} already has ${totalUsed}/${limits.total} pipes.`, 'warn');
    return false;
  }

  // 2. Fitting arm-specific checks (elbow / valve / tee)
  if (node.type === 'elbow' || node.type === 'valve') {
    // Determine which arm the new pipe will use
    const arms = node.type === 'elbow' ? getElbowArms(node) : getValveArms(node);
    const toOther = Math.atan2(otherNode.y - node.y, otherNode.x - node.x);
    const diffA = Math.abs(normalizeAngle(toOther - arms.angA));
    const diffB = Math.abs(normalizeAngle(toOther - arms.angB));
    const chosenArm = diffA <= diffB ? 'A' : 'B';

    const armUsed = countArmConnections(nodeId, chosenArm);
    if (armUsed >= 1) {
      toast(`Cannot connect — ${node.type} arm ${chosenArm} is already occupied.`, 'warn');
      return false;
    }
  } else if (node.type === 'tee') {
    const arms = getTeeArms(node);
    const toOther = Math.atan2(otherNode.y - node.y, otherNode.x - node.x);
    const diffA = Math.abs(normalizeAngle(toOther - arms.angA));
    const diffB = Math.abs(normalizeAngle(toOther - arms.angB));
    const diffC = Math.abs(normalizeAngle(toOther - arms.angC));
    let chosenArm = 'runA';
    let minDiff = diffA;
    if (diffB < minDiff) { minDiff = diffB; chosenArm = 'runB'; }
    if (diffC < minDiff) { minDiff = diffC; chosenArm = 'branch'; }

    const armUsed = countArmConnections(nodeId, chosenArm);
    if (armUsed >= 1) {
      toast(`Cannot connect — Tee arm ${chosenArm} is already occupied.`, 'warn');
      return false;
    }
  }

  // 3. Pump side-specific checks
  if (node.type === 'pump') {
    const cfg = node.props.pump_config || 'end_suction';
    const sideLimits = {
      end_suction: { suction: 1, discharge: 1 },
      double_suction: { suction: 2, discharge: 1 },
      double_discharge: { suction: 1, discharge: 2 },
      double_both: { suction: 2, discharge: 2 },
      inline: { suction: 1, discharge: 1 },
    }[cfg] || { suction: 1, discharge: 1 };

    // Determine the side this new pipe would attach to
    const toOther = Math.atan2(otherNode.y - node.y, otherNode.x - node.x);
    const isSuction = Math.abs(normalizeAngle(toOther)) > Math.PI / 2;
    const side = isSuction ? 'suction' : 'discharge';

    const used = countNodeConnections(nodeId, 'pump', side);
    if (used >= sideLimits[side]) {
      toast(`Cannot connect — pump ${side} side is full (${used}/${sideLimits[side]}).`, 'warn');
      return false;
    }
  }

  return true;
}

// ============================================================================
// CONTINUOUS PIPE RUNS & INLINE FITTING ARCHITECTURE
// ============================================================================

/**
 * Check if two pipe segments share identical hydraulic characteristics.
 * If both segments share the same diameter, material, and schedule/SDR,
 * they belong to the SAME continuous pipe run and do not warrant a split.
 * If either diameter or material differs, this is a genuine physical split!
 */
function pipesMatchCharacteristics(p1, p2) {
  if (!p1 || !p2 || !p1.props || !p2.props) return false;
  const d1 = parseFloat(p1.props.id_mm || p1.props.diameter_mm || 0);
  const d2 = parseFloat(p2.props.id_mm || p2.props.diameter_mm || 0);
  if (Math.abs(d1 - d2) > 0.1) return false;

  const m1 = p1.props.material || p1.props.material_key || '';
  const m2 = p2.props.material || p2.props.material_key || '';
  if (m1 && m2 && m1 !== m2) return false;

  return true;
}

/**
 * ============================================================================
 * CONTINUOUS PIPE RUN RECONCILIATION ENGINE
 * ============================================================================
 * 
 * Reconciles continuous pipe runs across inline degree-2 fitting nodes:
 * 
 * 1. FITTINGS AS ATTRIBUTES (UNIFIED PIPE RUN):
 *    When an inline fitting node (valve, elbow, inline tee) connects two pipe
 *    segments with MATCHING diameter and material, both segments belong to the
 *    SAME continuous pipe run and share the same Pipe ID / label (e.g. 'P-1').
 *    Neither segment gets an unwanted extra ID.
 * 
 * 2. AUTOMATIC SPLITTING ON CHARACTERISTIC TRANSITION:
 *    If the user modifies any segment characteristic (such as diameter or
 *    material) on one side of an inline fitting, that transition is a genuine
 *    physical split (e.g. pipe reducer/expander or material joint).
 *    The engine automatically assigns a new distinct Pipe ID (e.g. 'P-2') to
 *    the differing segment.
 * 
 * 3. STABILITY & CLICK IMMUNITY:
 *    Clicking, selecting, or inspecting another pipe will NEVER reset or corrupt
 *    segment characteristics or overwrite split IDs back to the same name.
 * 
 * 4. AUTOMATIC RE-MERGING:
 *    If the user changes differing segment characteristics back so that they
 *    match again, the system automatically re-unifies both segments under
 *    the primary continuous pipe ID (unless the user explicitly split them).
 * 
 * 5. MANUAL SPLIT RESPECT:
 *    If a user explicitly clicks "Split Segment" or assigns a custom label,
 *    `pipe.props.manual_split` is marked true, preventing automatic re-merging.
 */
function reconcilePipeRuns() {
  if (!state.pipes || state.pipes.length === 0) return false;

  let anyModified = false;
  let pass = 0;
  let passModified = true;

  // Multi-pass propagation loop: ensures ID changes propagate across multi-segment continuous runs
  while (passModified && pass < 10) {
    passModified = false;
    pass++;

    state.nodes.forEach(node => {
      // Only examine inline fitting nodes (valves, elbows, inline tees)
      if (!['valve', 'elbow', 'tee'].includes(node.type)) return;

      // An inline fitting connects exactly 2 pipe segments (degree == 2)
      const incident = state.pipes.filter(p => p.fromNodeId === node.id || p.toNodeId === node.id);
      if (incident.length !== 2) return;

      // Determine upstream (pIn) and downstream (pOut) relative to node orientation
      let pIn, pOut;
      const inPipes = state.pipes.filter(p => p.toNodeId === node.id);
      const outPipes = state.pipes.filter(p => p.fromNodeId === node.id);

      if (inPipes.length === 1 && outPipes.length === 1) {
        // Standard directional flow: pipeA -> node -> pipeB
        pIn = inPipes[0];
        pOut = outPipes[0];
      } else {
        // Tolerates arbitrary user drawing order (both drawn into or away from fitting)
        pIn = incident[0];
        pOut = incident[1];
      }

      // Check if hydraulic characteristics (internal diameter, material) match
      const match = pipesMatchCharacteristics(pIn, pOut);

      if (match) {
        // Characteristics match:
        // Respect manual user splits (if user explicitly split or renamed the segment)
        if (pOut.props.manual_split || pIn.props.manual_split) {
          // Keep distinct pipe IDs as requested by user
          return;
        }

        // Both belong to the same continuous pipe run: unify under upstream label
        const unifiedLabel = pIn.props.label || pIn.pipeRunId || pIn.id;
        if (pOut.props.label !== unifiedLabel) {
          pOut.props.label = unifiedLabel;
          pOut.pipeRunId = unifiedLabel;
          passModified = true;
          anyModified = true;
        }
      } else {
        // Characteristics differ: genuine physical split warranted!
        // If both segments currently still have the same label, split downstream to a new distinct ID
        if (pOut.props.label === pIn.props.label) {
          const newName = newId('P');
          pOut.props.label = newName;
          pOut.pipeRunId = newName;
          delete pOut.props.manual_split;
          passModified = true;
          anyModified = true;
          toast(`Pipe automatically split at ${node.props.label || node.id} due to diameter/material transition (${pIn.props.label} -> ${newName}).`, 'info');
        }
      }
    });
  }

  return anyModified;
}

/**
 * Calculate squared Euclidean distance from point (px, py) to line segment (x1, y1) -> (x2, y2).
 */
function distToSegmentSquared(px, py, x1, y1, x2, y2) {
  const l2 = (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1);
  if (l2 === 0) return (px - x1) * (px - x1) + (py - y1) * (py - y1);
  let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
  t = Math.max(0, Math.min(1, t));
  const projX = x1 + t * (x2 - x1);
  const projY = y1 + t * (y2 - y1);
  return (px - projX) * (px - projX) + (py - projY) * (py - projY);
}

/**
 * Find any pipe that passes close to the given canvas coordinate (x, y).
 */
function findPipeNearPoint(x, y, maxDist = 25) {
  const maxD2 = maxDist * maxDist;
  let bestPipe = null;
  let bestDist2 = Infinity;

  state.pipes.forEach(pipe => {
    const fn = findNode(pipe.fromNodeId);
    const tn = findNode(pipe.toNodeId);
    if (!fn || !tn) return;

    const routing = pipe.props.routing || 'auto';
    if (routing === 'orthogonal') {
      const midX = (fn.x + tn.x) / 2;
      const d1 = distToSegmentSquared(x, y, fn.x, fn.y, midX, fn.y);
      const d2 = distToSegmentSquared(x, y, midX, fn.y, midX, tn.y);
      const d3 = distToSegmentSquared(x, y, midX, tn.y, tn.x, tn.y);
      const minD = Math.min(d1, d2, d3);
      if (minD < maxD2 && minD < bestDist2) {
        bestDist2 = minD;
        bestPipe = pipe;
      }
    } else {
      const d = distToSegmentSquared(x, y, fn.x, fn.y, tn.x, tn.y);
      if (d < maxD2 && d < bestDist2) {
        bestDist2 = d;
        bestPipe = pipe;
      }
    }
  });

  return bestPipe;
}

/**
 * Insert an inline fitting (valve, elbow, tee) directly in the middle of an existing pipe.
 *
 * Slices the pipe into two collinear segments of the SAME continuous pipe run:
 * - Upstream segment (fromNode -> new fitting node)
 * - Downstream segment (new fitting node -> toNode)
 * Both segments share the exact same pipe label, diameter, material, and standard pipe specs!
 */
function insertFittingOnPipe(pipe, type, clickPos) {
  const fn = findNode(pipe.fromNodeId);
  const tn = findNode(pipe.toNodeId);
  if (!fn || !tn) return;

  // 1. Calculate projected insertion point on the pipe line
  const dx = tn.x - fn.x;
  const dy = tn.y - fn.y;
  const lenSq = dx * dx + dy * dy;
  let t = lenSq > 0 ? ((clickPos.x - fn.x) * dx + (clickPos.y - fn.y) * dy) / lenSq : 0.5;
  // Constrain t between 0.15 and 0.85 so fitting doesn't collide with endpoint halos
  t = Math.max(0.15, Math.min(0.85, t));

  const insertX = snap(fn.x + t * dx);
  const insertY = snap(fn.y + t * dy);

  // 2. Create the fitting node at the projected coordinate
  const nodeId = newId('N');
  const count = state.nodes.filter(n => n.type === type).length;
  const nodeProps = defaultNodeProps(type, count);

  // Interpolate elevation smoothly between fn and tn
  const elevA = fn.props.elevation_m || 0;
  const elevB = tn.props.elevation_m || 0;
  nodeProps.elevation_m = +(elevA + t * (elevB - elevA)).toFixed(1);

  const newNode = { id: nodeId, type, x: insertX, y: insertY, props: nodeProps };
  state.nodes.push(newNode);

  // 3. Splice the pipe into two connected segments of the SAME continuous pipe run
  const originalToNodeId = pipe.toNodeId;
  const totalLength = pipe.props.length_m || 10;
  const len1 = Math.max(1, +(totalLength * t).toFixed(1));
  const len2 = Math.max(1, +(totalLength - len1).toFixed(1));

  // The base unified pipe run identity (e.g. 'P-15')
  const basePipeLabel = pipe.props.label || pipe.id;
  const basePipeRunId = pipe.pipeRunId || basePipeLabel;

  // Upstream segment: fn -> newNode
  pipe.toNodeId = nodeId;
  pipe.pipeRunId = basePipeRunId;
  pipe.props.label = basePipeLabel;
  pipe.props.length_m = len1;

  // Downstream segment: newNode -> originalToNodeId (inherits identical properties and pipe identity!)
  const newPipeId = newId('P');
  const downstreamPipe = {
    id: newPipeId,
    pipeRunId: basePipeRunId,
    fromNodeId: nodeId,
    toNodeId: originalToNodeId,
    props: {
      ...JSON.parse(JSON.stringify(pipe.props)),
      label: basePipeLabel,   // SHARES THE SAME PIPE ID/LABEL!
      length_m: len2,
      fittings: [],
    }
  };
  state.pipes.push(downstreamPipe);

  // 4. Reconcile pipe runs to ensure seamless continuous labeling
  reconcilePipeRuns();

  // 5. Select the newly inserted fitting node and render
  setMode('select');
  selectItem('node', nodeId);
  renderAll();
  saveNetworkToStorage();
  toast(`Inserted ${type.toUpperCase()} in the middle of Pipe ${basePipeLabel}.`, 'success');
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
  saveNetworkToStorage();
}

function addPipe(fromNodeId, toNodeId) {
  const srcNode = findNode(fromNodeId);
  const dstNode = findNode(toNodeId);

  // Check if either end is an inline fitting that already belongs to an existing pipe run
  let inheritedProps = null;
  let inheritedLabel = null;
  let inheritedRunId = null;

  // Continuing from an inline fitting node (e.g. Valve 1) that already has an incoming pipe
  if (srcNode && ['valve', 'elbow', 'tee'].includes(srcNode.type)) {
    const incomingPipe = state.pipes.find(p => p.toNodeId === fromNodeId);
    if (incomingPipe) {
      inheritedProps = JSON.parse(JSON.stringify(incomingPipe.props));
      inheritedLabel = incomingPipe.props.label || incomingPipe.id;
      inheritedRunId = incomingPipe.pipeRunId || inheritedLabel;
    }
  }

  // Connecting into an inline fitting node that already has an outgoing pipe
  if (!inheritedProps && dstNode && ['valve', 'elbow', 'tee'].includes(dstNode.type)) {
    const outgoingPipe = state.pipes.find(p => p.fromNodeId === toNodeId);
    if (outgoingPipe) {
      inheritedProps = JSON.parse(JSON.stringify(outgoingPipe.props));
      inheritedLabel = outgoingPipe.props.label || outgoingPipe.id;
      inheritedRunId = outgoingPipe.pipeRunId || inheritedLabel;
    }
  }

  const id = newId('P');
  const props = inheritedProps ? {
    ...inheritedProps,
    label: inheritedLabel, // Retain the same pipe run identity!
    fittings: [],
  } : defaultPipeProps(id);

  const pipe = {
    id,
    pipeRunId: inheritedRunId || props.label || id,
    fromNodeId,
    toNodeId,
    props,
  };
  state.pipes.push(pipe);

  reconcilePipeRuns();
  renderAll();
  selectItem('pipe', id);
  saveNetworkToStorage();
}

function deleteSelected() {
  if (!state.selected) return;
  if (state.selected.kind === 'node') {
    const nid = state.selected.id;
    const node = findNode(nid);
    // If deleting an inline fitting between two pipes, heal the continuous pipe!
    if (node && ['valve', 'elbow', 'tee'].includes(node.type)) {
      const inPipes = state.pipes.filter(p => p.toNodeId === nid);
      const outPipes = state.pipes.filter(p => p.fromNodeId === nid);
      if (inPipes.length === 1 && outPipes.length === 1) {
        const pIn = inPipes[0];
        const pOut = outPipes[0];
        pIn.toNodeId = pOut.toNodeId;
        pIn.props.length_m = +(pIn.props.length_m + pOut.props.length_m).toFixed(1);
        state.pipes = state.pipes.filter(p => p.id !== pOut.id);
        state.nodes = state.nodes.filter(n => n.id !== nid);
        selectItem(null);
        reconcilePipeRuns();
        renderAll();
        saveNetworkToStorage();
        toast(`Removed ${node.props.label || node.id} and joined continuous pipe.`, 'info');
        return;
      }
    }
    state.nodes = state.nodes.filter(n => n.id !== nid);
    state.pipes = state.pipes.filter(p => p.fromNodeId !== nid && p.toNodeId !== nid);
  } else {
    state.pipes = state.pipes.filter(p => p.id !== state.selected.id);
  }
  selectItem(null);
  reconcilePipeRuns();
  renderAll();
  saveNetworkToStorage();
}

// ============================================================================
// CONTEXTUAL CONFIGURATION POPOVER
// ============================================================================

function hideContextPopover() {
  const pop = document.getElementById('pn-context-popover');
  if (pop) {
    pop.style.display = 'none';
    pop.innerHTML = '';
  }
}

function updateContextPopoverPosition() {
  const pop = document.getElementById('pn-context-popover');
  if (!pop || pop.style.display === 'none' || !state.selected) return;

  const canvasWrap = document.getElementById('pn-canvas-wrap');
  if (!canvasWrap) return;

  let targetX = 0;
  let targetY = 0;

  if (state.selected.kind === 'node') {
    const node = findNode(state.selected.id);
    if (!node) { hideContextPopover(); return; }
    targetX = (node.x * state.zoom) + state.pan.x;
    targetY = (node.y * state.zoom) + state.pan.y;
  } else if (state.selected.kind === 'pipe') {
    const pipe = findPipe(state.selected.id);
    if (!pipe) { hideContextPopover(); return; }
    const fn = findNode(pipe.fromNodeId);
    const tn = findNode(pipe.toNodeId);
    if (!fn || !tn) { hideContextPopover(); return; }
    targetX = (((fn.x + tn.x) / 2) * state.zoom) + state.pan.x;
    targetY = (((fn.y + tn.y) / 2) * state.zoom) + state.pan.y;
  } else {
    hideContextPopover();
    return;
  }

  // Positioning: place next to the element, offset by 35px
  let left = targetX + 35;
  let top = targetY - 40;

  const popW = pop.offsetWidth || 260;
  const popH = pop.offsetHeight || 220;
  const maxLeft = canvasWrap.clientWidth - popW - 15;
  const maxTop = canvasWrap.clientHeight - popH - 15;

  if (left > maxLeft) {
    left = targetX - popW - 35;
  }
  if (left < 15) left = 15;
  if (top > maxTop) top = maxTop;
  if (top < 15) top = 15;

  pop.style.left = `${Math.round(left)}px`;
  pop.style.top = `${Math.round(top)}px`;
}

function showContextPopover(kind, id) {
  const pop = document.getElementById('pn-context-popover');
  if (!pop) return;

  pop.onclick = (e) => e.stopPropagation();

  if (kind === 'node') {
    const node = findNode(id);
    if (!node) { hideContextPopover(); return; }

    if (node.type === 'valve') {
      renderPopoverNodeValve(node, pop);
    } else if (node.type === 'tee') {
      renderPopoverNodeTee(node, pop);
    } else if (node.type === 'elbow') {
      renderPopoverNodeElbow(node, pop);
    } else if (node.type === 'pump') {
      renderPopoverNodePump(node, pop);
    } else {
      renderPopoverNodeDefault(node, pop);
    }
  } else if (kind === 'pipe') {
    const pipe = findPipe(id);
    if (!pipe) { hideContextPopover(); return; }
    renderPopoverPipe(pipe, pop);
  } else {
    hideContextPopover();
    return;
  }

  pop.style.display = 'block';
  requestAnimationFrame(updateContextPopoverPosition);
}

function renderPopoverNodeValve(node, pop) {
  const currentKey = node.props.fitting_key || 'gate_valve_open';
  const isCustom = Boolean(node.props.is_custom_k);
  const currentK = getNodeKFactor(node);

  const valveOptions = [
    { key: 'ball_valve_open', label: 'Ball Valve (Full Bore)', K: 0.05, icon: 'bi-record-circle' },
    { key: 'gate_valve_open', label: 'Gate Valve (Open)', K: 0.20, icon: 'bi-door-open' },
    { key: 'butterfly_valve_open', label: 'Butterfly Valve', K: 0.30, icon: 'bi-slash-circle' },
    { key: 'check_valve_swing', label: 'Swing Check Valve', K: 2.50, icon: 'bi-arrow-right-circle' },
    { key: 'check_valve_ball', label: 'Ball Check Valve', K: 4.50, icon: 'bi-arrow-right-circle-fill' },
    { key: 'gate_valve_half', label: 'Gate Valve (50% Open)', K: 5.60, icon: 'bi-door-closed' },
    { key: 'globe_valve_open', label: 'Globe Valve (Open)', K: 10.0, icon: 'bi-disc' },
  ];

  let optionsHtml = '';
  valveOptions.forEach(opt => {
    const isSelected = !isCustom && currentKey === opt.key;
    optionsHtml += `
      <div class="pn-popover-option ${isSelected ? 'active' : ''}" data-val="${opt.key}">
        <div style="display:flex;align-items:center;gap:7px;">
          <i class="bi ${opt.icon}" style="color:${isSelected ? '#38bdf8' : '#94a3b8'};"></i>
          <span>${opt.label}</span>
        </div>
        <span class="pn-popover-badge">K=${opt.K}</span>
      </div>
    `;
  });

  pop.innerHTML = `
    <div class="pn-popover-header">
      <div style="display:flex;align-items:center;gap:6px;">
        <i class="bi bi-funnel" style="color:#ef4444;"></i>
        <span class="pn-popover-title">Valve: ${node.props.label || node.id}</span>
      </div>
      <button class="pn-popover-close" title="Close"><i class="bi bi-x"></i></button>
    </div>
    <div class="pn-popover-body">
      <div class="pn-popover-section-label">Select Valve Type</div>
      <div class="pn-popover-list" id="pop-valve-list">
        ${optionsHtml}
      </div>

      <div class="pn-popover-section-label" style="margin-top:10px;">Custom K-Factor</div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;color:#cbd5e1;margin:0;">
          <input type="checkbox" id="pop-is-custom-k" ${isCustom ? 'checked' : ''} style="accent-color:#f59e0b;cursor:pointer;">
          <span>Custom K Value</span>
        </label>
        <span style="font-size:11px;font-weight:700;color:${isCustom ? '#f59e0b' : '#38bdf8'};">
          Active K = ${currentK.toFixed(2)}
        </span>
      </div>
      <div id="pop-custom-k-wrap" style="display:${isCustom ? 'flex' : 'none'};align-items:center;gap:6px;">
        <input type="number" id="pop-custom-k" class="pn-popover-input" step="0.05" min="0" value="${node.props.custom_k ?? currentK}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;width:100px;">
        <span style="font-size:10px;color:#94a3b8;">(loss = K·V²/2g)</span>
      </div>
    </div>
  `;

  pop.querySelector('.pn-popover-close').onclick = hideContextPopover;

  pop.querySelectorAll('#pop-valve-list .pn-popover-option').forEach(el => {
    el.onclick = () => {
      node.props.fitting_key = el.dataset.val;
      node.props.is_custom_k = false;
      renderAll();
      showNodeProps(node);
      showContextPopover('node', node.id);
      saveNetworkToStorage();
    };
  });

  const isCustomCb = pop.querySelector('#pop-is-custom-k');
  const customKIn = pop.querySelector('#pop-custom-k');

  isCustomCb.onchange = (e) => {
    node.props.is_custom_k = e.target.checked;
    if (node.props.is_custom_k && (node.props.custom_k === null || node.props.custom_k === undefined)) {
      node.props.custom_k = getNodeKFactor(node);
    }
    renderAll();
    showNodeProps(node);
    showContextPopover('node', node.id);
    saveNetworkToStorage();
  };

  if (customKIn) {
    const onCustomK = (e) => {
      node.props.custom_k = parseFloat(e.target.value) || 0;
      renderAll();
      showNodeProps(node);
      updateKDisplay(node);
      saveNetworkToStorage();
    };
    customKIn.oninput = onCustomK;
    customKIn.onchange = onCustomK;
  }
}

function renderPopoverNodeTee(node, pop) {
  const currentKey = node.props.fitting_key || 'tee_run_through';
  const isCustom = Boolean(node.props.is_custom_k);
  const currentK = getNodeKFactor(node);
  const rot = node.props.rotation_deg || 0;

  const teeOptions = [
    { key: 'tee_run_through', label: 'Run Through (Straight Flow)', K: 0.40, desc: 'Flow continues straight through the header' },
    { key: 'tee_branch_flow', label: 'Branch Flow (90° Divert / Combine)', K: 1.80, desc: 'Flow turns into or out of 90° branch' },
  ];

  let optionsHtml = '';
  teeOptions.forEach(opt => {
    const isSelected = !isCustom && currentKey === opt.key;
    optionsHtml += `
      <div class="pn-popover-option ${isSelected ? 'active' : ''}" data-val="${opt.key}">
        <div>
          <div style="font-weight:600;">${opt.label}</div>
          <div style="font-size:10px;color:#64748b;margin-top:2px;">${opt.desc}</div>
        </div>
        <span class="pn-popover-badge">K=${opt.K}</span>
      </div>
    `;
  });

  pop.innerHTML = `
    <div class="pn-popover-header">
      <div style="display:flex;align-items:center;gap:6px;">
        <i class="bi bi-diagram-3" style="color:#38bdf8;"></i>
        <span class="pn-popover-title">Tee: ${node.props.label || node.id}</span>
      </div>
      <button class="pn-popover-close" title="Close"><i class="bi bi-x"></i></button>
    </div>
    <div class="pn-popover-body">
      <div class="pn-popover-section-label">Flow Path & Hydraulic Loss</div>
      <div class="pn-popover-list" id="pop-tee-list">
        ${optionsHtml}
      </div>

      <div class="pn-popover-section-label" style="margin-top:10px;">Branch Orientation</div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <button id="pop-btn-rotate-tee" class="pn-btn" style="flex:1;padding:5px 8px;font-size:11px;">
          <i class="bi bi-arrow-clockwise"></i> Rotate Branch 90°
        </button>
        <span style="font-family:monospace;font-size:12px;color:#38bdf8;font-weight:700;padding:4px 8px;background:#0d1117;border:1px solid #30363d;border-radius:4px;">
          ${rot}°
        </span>
      </div>

      <div class="pn-popover-section-label" style="margin-top:10px;">Custom K-Factor</div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;color:#cbd5e1;margin:0;">
          <input type="checkbox" id="pop-is-custom-k" ${isCustom ? 'checked' : ''} style="accent-color:#f59e0b;cursor:pointer;">
          <span>Custom K Value</span>
        </label>
        <span style="font-size:11px;font-weight:700;color:${isCustom ? '#f59e0b' : '#38bdf8'};">
          Active K = ${currentK.toFixed(2)}
        </span>
      </div>
      <div id="pop-custom-k-wrap" style="display:${isCustom ? 'flex' : 'none'};align-items:center;gap:6px;">
        <input type="number" id="pop-custom-k" class="pn-popover-input" step="0.05" min="0" value="${node.props.custom_k ?? currentK}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;width:100px;">
        <span style="font-size:10px;color:#94a3b8;">(loss = K·V²/2g)</span>
      </div>
    </div>
  `;

  pop.querySelector('.pn-popover-close').onclick = hideContextPopover;

  pop.querySelectorAll('#pop-tee-list .pn-popover-option').forEach(el => {
    el.onclick = () => {
      node.props.fitting_key = el.dataset.val;
      node.props.is_custom_k = false;
      renderAll();
      showNodeProps(node);
      showContextPopover('node', node.id);
      saveNetworkToStorage();
    };
  });

  pop.querySelector('#pop-btn-rotate-tee').onclick = () => {
    node.props.rotation_deg = ((node.props.rotation_deg || 0) + 90) % 360;
    renderAll();
    showNodeProps(node);
    showContextPopover('node', node.id);
    saveNetworkToStorage();
  };

  const isCustomCb = pop.querySelector('#pop-is-custom-k');
  const customKIn = pop.querySelector('#pop-custom-k');

  isCustomCb.onchange = (e) => {
    node.props.is_custom_k = e.target.checked;
    if (node.props.is_custom_k && (node.props.custom_k === null || node.props.custom_k === undefined)) {
      node.props.custom_k = getNodeKFactor(node);
    }
    renderAll();
    showNodeProps(node);
    showContextPopover('node', node.id);
    saveNetworkToStorage();
  };

  if (customKIn) {
    const onCustomK = (e) => {
      node.props.custom_k = parseFloat(e.target.value) || 0;
      renderAll();
      showNodeProps(node);
      updateKDisplay(node);
      saveNetworkToStorage();
    };
    customKIn.oninput = onCustomK;
    customKIn.onchange = onCustomK;
  }
}

function renderPopoverNodeElbow(node, pop) {
  const currentKey = node.props.fitting_key || 'elbow_90_standard';
  const isCustom = Boolean(node.props.is_custom_k);
  const currentK = getNodeKFactor(node);

  const elbowOptions = [
    { key: 'elbow_90_standard', label: '90° Standard Elbow', K: 0.90, desc: 'Short radius standard bend' },
    { key: 'elbow_90_long_radius', label: '90° Long Radius Elbow', K: 0.60, desc: 'Smooth radius, lower resistance' },
    { key: 'elbow_45', label: '45° Elbow Bend', K: 0.40, desc: 'Gentle 45-degree redirection' },
  ];

  let optionsHtml = '';
  elbowOptions.forEach(opt => {
    const isSelected = !isCustom && currentKey === opt.key;
    optionsHtml += `
      <div class="pn-popover-option ${isSelected ? 'active' : ''}" data-val="${opt.key}">
        <div>
          <div style="font-weight:600;">${opt.label}</div>
          <div style="font-size:10px;color:#64748b;margin-top:2px;">${opt.desc}</div>
        </div>
        <span class="pn-popover-badge">K=${opt.K}</span>
      </div>
    `;
  });

  pop.innerHTML = `
    <div class="pn-popover-header">
      <div style="display:flex;align-items:center;gap:6px;">
        <i class="bi bi-arrow-return-right" style="color:#60a5fa;"></i>
        <span class="pn-popover-title">Elbow: ${node.props.label || node.id}</span>
      </div>
      <button class="pn-popover-close" title="Close"><i class="bi bi-x"></i></button>
    </div>
    <div class="pn-popover-body">
      <div class="pn-popover-section-label">Elbow Bend Type</div>
      <div class="pn-popover-list" id="pop-elbow-list">
        ${optionsHtml}
      </div>

      <div class="pn-popover-section-label" style="margin-top:10px;">Custom K-Factor</div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;color:#cbd5e1;margin:0;">
          <input type="checkbox" id="pop-is-custom-k" ${isCustom ? 'checked' : ''} style="accent-color:#f59e0b;cursor:pointer;">
          <span>Custom K Value</span>
        </label>
        <span style="font-size:11px;font-weight:700;color:${isCustom ? '#f59e0b' : '#38bdf8'};">
          Active K = ${currentK.toFixed(2)}
        </span>
      </div>
      <div id="pop-custom-k-wrap" style="display:${isCustom ? 'flex' : 'none'};align-items:center;gap:6px;">
        <input type="number" id="pop-custom-k" class="pn-popover-input" step="0.05" min="0" value="${node.props.custom_k ?? currentK}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;width:100px;">
        <span style="font-size:10px;color:#94a3b8;">(loss = K·V²/2g)</span>
      </div>
    </div>
  `;

  pop.querySelector('.pn-popover-close').onclick = hideContextPopover;

  pop.querySelectorAll('#pop-elbow-list .pn-popover-option').forEach(el => {
    el.onclick = () => {
      node.props.fitting_key = el.dataset.val;
      node.props.is_custom_k = false;
      renderAll();
      showNodeProps(node);
      showContextPopover('node', node.id);
      saveNetworkToStorage();
    };
  });

  const isCustomCb = pop.querySelector('#pop-is-custom-k');
  const customKIn = pop.querySelector('#pop-custom-k');

  isCustomCb.onchange = (e) => {
    node.props.is_custom_k = e.target.checked;
    if (node.props.is_custom_k && (node.props.custom_k === null || node.props.custom_k === undefined)) {
      node.props.custom_k = getNodeKFactor(node);
    }
    renderAll();
    showNodeProps(node);
    showContextPopover('node', node.id);
    saveNetworkToStorage();
  };

  if (customKIn) {
    const onCustomK = (e) => {
      node.props.custom_k = parseFloat(e.target.value) || 0;
      renderAll();
      showNodeProps(node);
      updateKDisplay(node);
      saveNetworkToStorage();
    };
    customKIn.oninput = onCustomK;
    customKIn.onchange = onCustomK;
  }
}

function renderPopoverNodePump(node, pop) {
  const currentCfg = node.props.pump_config || 'end_suction';
  const pumpConfigs = [
    { key: 'end_suction', label: 'End-Suction', desc: '1 suction (axial) + 1 discharge (top)' },
    { key: 'double_suction', label: 'Double Suction', desc: '2 suction inlets + 1 discharge' },
    { key: 'double_discharge', label: 'Double Discharge', desc: '1 suction inlet + 2 discharges' },
    { key: 'double_both', label: '2 In / 2 Out', desc: '2 suction + 2 discharge ports' },
    { key: 'inline', label: 'Inline Booster', desc: '1 inline in + 1 inline out' },
  ];

  let cfgHtml = '';
  pumpConfigs.forEach(cfg => {
    const isSelected = currentCfg === cfg.key;
    cfgHtml += `
      <div class="pn-popover-option ${isSelected ? 'active' : ''}" data-val="${cfg.key}">
        <div>
          <div style="font-weight:600;">${cfg.label}</div>
          <div style="font-size:10px;color:#64748b;">${cfg.desc}</div>
        </div>
      </div>
    `;
  });

  pop.innerHTML = `
    <div class="pn-popover-header">
      <div style="display:flex;align-items:center;gap:6px;">
        <i class="bi bi-gear-wide-connected" style="color:#a855f7;"></i>
        <span class="pn-popover-title">Pump: ${node.props.label || node.id}</span>
      </div>
      <button class="pn-popover-close" title="Close"><i class="bi bi-x"></i></button>
    </div>
    <div class="pn-popover-body">
      <div class="pn-popover-section-label">Pump Configuration</div>
      <div class="pn-popover-list" id="pop-pump-cfg-list">
        ${cfgHtml}
      </div>

      <div class="pn-popover-section-label" style="margin-top:10px;">Elevation (Z, meters)</div>
      <input type="number" id="pop-node-elev" class="pn-popover-input" step="0.5" value="${node.props.elevation_m ?? 0}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;">

      <div class="pn-popover-section-label" style="margin-top:10px;">Flow Rate (m³/h)</div>
      <input type="number" id="pop-pump-flow" class="pn-popover-input" step="1" min="0" value="${node.props.flow_m3h ?? 10}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;">
    </div>
  `;

  pop.querySelector('.pn-popover-close').onclick = hideContextPopover;

  const pElevIn = pop.querySelector('#pop-node-elev');
  if (pElevIn) {
    pElevIn.oninput = (e) => {
      syncElevationIntegrity('node', node.id, e.target.value);
      renderAll();
      showNodeProps(node);
    };
  }

  pop.querySelectorAll('#pop-pump-cfg-list .pn-popover-option').forEach(el => {
    el.onclick = () => {
      node.props.pump_config = el.dataset.val;
      renderAll();
      showNodeProps(node);
      showContextPopover('node', node.id);
      saveNetworkToStorage();
    };
  });

  const flowIn = pop.querySelector('#pop-pump-flow');
  if (flowIn) {
    const onFlow = (e) => {
      node.props.flow_m3h = parseFloat(e.target.value) || 10;
      showNodeProps(node);
      saveNetworkToStorage();
    };
    flowIn.oninput = onFlow;
    flowIn.onchange = onFlow;
  }
}

function renderPopoverNodeDefault(node, pop) {
  pop.innerHTML = `
    <div class="pn-popover-header">
      <div style="display:flex;align-items:center;gap:6px;">
        <i class="bi bi-geo-alt" style="color:#38bdf8;"></i>
        <span class="pn-popover-title">${node.type.toUpperCase()}: ${node.props.label || node.id}</span>
      </div>
      <button class="pn-popover-close" title="Close"><i class="bi bi-x"></i></button>
    </div>
    <div class="pn-popover-body">
      <div class="pn-popover-section-label">Node Label</div>
      <input type="text" id="pop-node-label" class="pn-popover-input" value="${node.props.label || ''}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;">

      <div class="pn-popover-section-label" style="margin-top:8px;">Elevation (Z, meters)</div>
      <input type="number" id="pop-node-elev" class="pn-popover-input" step="0.5" value="${node.props.elevation_m ?? 0}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 9px;font-size:12px;">
    </div>
  `;

  pop.querySelector('.pn-popover-close').onclick = hideContextPopover;

  const lblIn = pop.querySelector('#pop-node-label');
  if (lblIn) {
    lblIn.oninput = (e) => {
      node.props.label = e.target.value;
      renderAll();
      showNodeProps(node);
      saveNetworkToStorage();
    };
  }
  const elevIn = pop.querySelector('#pop-node-elev');
  if (elevIn) {
    elevIn.oninput = (e) => {
      syncElevationIntegrity('node', node.id, e.target.value);
      renderAll();
      showNodeProps(node);
    };
  }
}

function renderPopoverPipe(pipe, pop) {
  if (!Array.isArray(STANDARD_PIPES) || STANDARD_PIPES.length === 0) {
    STANDARD_PIPES = EMBEDDED_STANDARD_PIPES;
  }

  const curRouting = pipe.props.routing || 'auto';
  const curCustK = pipe.props.custom_k || 0;
  const curD = pipe.props.id_mm || pipe.props.diameter_mm || 100;
  const curStd = pipe.props.standard || 'ASME B36.10M';
  const curSch = pipe.props.schedule_sdr || 'Sch 40 (STD)';

  // Build spec summary card
  const specCardHtml = `
    <div style="background:#090d16;border:1px solid #334155;border-radius:6px;padding:8px 9px;margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <span style="font-size:11px;font-weight:700;color:#38bdf8;display:flex;align-items:center;gap:4px;">
          <i class="bi bi-shield-check"></i> ${pipe.props.standard || curStd}
        </span>
        <span style="font-size:9.5px;font-family:monospace;color:#38bdf8;background:rgba(56,189,248,0.15);padding:1px 6px;border-radius:4px;border:1px solid rgba(56,189,248,0.3);font-weight:600;">
          ${pipe.props.pressure_rating || 'PN --'}
        </span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:11px;">
        <div style="background:#0f172a;padding:4px 6px;border-radius:4px;border:1px solid #1e293b;">
          <span style="color:#94a3b8;font-size:9.5px;display:block;">Inner Dia (ID):</span>
          <strong style="color:#34d399;font-size:12px;">${(pipe.props.id_mm || pipe.props.diameter_mm || 100).toFixed(1)} mm</strong>
        </div>
        <div style="background:#0f172a;padding:4px 6px;border-radius:4px;border:1px solid #1e293b;">
          <span style="color:#94a3b8;font-size:9.5px;display:block;">Outer Dia (OD):</span>
          <strong style="color:#f8fafc;font-size:12px;">${pipe.props.od_mm ? pipe.props.od_mm.toFixed(1) + ' mm' : '--'}</strong>
        </div>
        <div style="background:#0f172a;padding:4px 6px;border-radius:4px;border:1px solid #1e293b;">
          <span style="color:#94a3b8;font-size:9.5px;display:block;">Nominal Bore:</span>
          <strong style="color:#cbd5e1;font-size:11px;">${pipe.props.nb_mm ? 'DN ' + pipe.props.nb_mm + (pipe.props.nb_inch ? ' (' + pipe.props.nb_inch + ')' : '') : '--'}</strong>
        </div>
        <div style="background:#0f172a;padding:4px 6px;border-radius:4px;border:1px solid #1e293b;">
          <span style="color:#94a3b8;font-size:9.5px;display:block;">Schedule / SDR:</span>
          <strong style="color:#cbd5e1;font-size:11px;">${pipe.props.schedule_sdr || curSch}</strong>
        </div>
      </div>
    </div>
  `;

  // Candidate pipes in current standard
  let sizeOptions = '';
  const currentStdPipes = Array.isArray(STANDARD_PIPES) ? STANDARD_PIPES.filter(p => p.standard === curStd && p.schedule_sdr === curSch) : [];
  const candidatePipes = currentStdPipes.length > 0 ? currentStdPipes : (Array.isArray(STANDARD_PIPES) ? STANDARD_PIPES.filter(p => p.standard === curStd) : []);
  const listToUse = candidatePipes.length > 0 ? candidatePipes : (Array.isArray(STANDARD_PIPES) ? STANDARD_PIPES.slice(0, 30) : []);

  listToUse.forEach(p => {
    const isAct = p.id === pipe.props.standard_pipe_id || Math.abs(p.id_mm - curD) < 1.0;
    const label = formatStandardPipeLabel(p, false);
    sizeOptions += `<option value="${p.id}" ${isAct ? 'selected' : ''}>${label}</option>`;
  });

  // Detect inline fittings along this continuous pipe run
  const activeLabel = pipe.props.label || pipe.id;
  const inlineFittingsOnRun = [];
  state.nodes.forEach(n => {
    if (!['valve', 'elbow', 'tee'].includes(n.type)) return;
    const connectedPipes = state.pipes.filter(p => p.fromNodeId === n.id || p.toNodeId === n.id);
    if (connectedPipes.some(p => (p.props.label || p.id) === activeLabel)) {
      const k = getNodeKFactor(n);
      inlineFittingsOnRun.push({ id: n.id, label: n.props.label || n.id, type: n.type, k: k });
    }
  });

  const fittingsInfoHtml = inlineFittingsOnRun.length > 0 ? `
    <div class="pn-popover-section-label" style="margin-top:6px;">Inline Fittings on Pipe (${inlineFittingsOnRun.length})</div>
    <div style="background:#090d16;border:1px solid #1e293b;border-radius:5px;padding:5px 8px;margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px;">
      ${inlineFittingsOnRun.map(f => `<span style="background:#0f172a;border:1px solid #334155;border-radius:4px;padding:2px 6px;font-size:10px;color:#38bdf8;"><i class="bi bi-diagram-2"></i> ${f.label} (K=${f.k.toFixed(2)})</span>`).join('')}
    </div>
  ` : '';

  pop.innerHTML = `
    <div class="pn-popover-header">
      <div style="display:flex;align-items:center;gap:6px;">
        <i class="bi bi-water" style="color:#0284c7;"></i>
        <span class="pn-popover-title">Pipe: ${pipe.props.label || pipe.id}</span>
      </div>
      <button class="pn-popover-close" title="Close"><i class="bi bi-x"></i></button>
    </div>
    <div class="pn-popover-body">
      <div class="pn-popover-section-label">Pipe Specifications</div>
      ${specCardHtml}

      <div class="pn-popover-section-label">Standard Pipe Size</div>
      <select id="pop-pipe-size-select" class="pn-popover-select" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:6px 8px;font-size:11.5px;margin-bottom:8px;">
        ${sizeOptions || '<option value="">No pipes available</option>'}
      </select>

      ${fittingsInfoHtml}

      <div class="pn-popover-section-label" style="margin-top:6px;">Routing Mode</div>
      <div style="display:flex;gap:4px;margin-bottom:8px;">
        <button class="pn-btn pop-route-btn ${curRouting === 'auto' ? 'active-tool' : ''}" data-route="auto" style="flex:1;padding:4px;font-size:10px;">Auto</button>
        <button class="pn-btn pop-route-btn ${curRouting === 'orthogonal' ? 'active-tool' : ''}" data-route="orthogonal" style="flex:1;padding:4px;font-size:10px;">Orthogonal</button>
        <button class="pn-btn pop-route-btn ${curRouting === 'straight' ? 'active-tool' : ''}" data-route="straight" style="flex:1;padding:4px;font-size:10px;">Straight</button>
      </div>

      <div class="pn-popover-section-label">Elevation Change &Delta;Z (m)</div>
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <input type="number" id="pop-pipe-elev" class="pn-popover-input" step="0.5" value="${pipe.props.elev_change_m ?? 0}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:5px 8px;font-size:11px;width:90px;">
        <span style="font-size:9.5px;color:#94a3b8;">Inlet &rarr; Outlet</span>
      </div>

      <div class="pn-popover-section-label">Additive Minor Loss (Custom K)</div>
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <input type="number" id="pop-pipe-custom-k" class="pn-popover-input" step="0.05" min="0" value="${curCustK}" style="background:#090d16 !important;color:#ffffff !important;border:1px solid #334155 !important;border-radius:6px;padding:5px 8px;font-size:11px;width:90px;">
        <span style="font-size:10px;color:#94a3b8;">(extra minor loss)</span>
      </div>

      <button id="pop-split-pipe-btn" class="pn-btn" style="width:100%;font-size:10px;padding:4px 8px;background:#0f172a;border:1px solid #334155;color:#94a3b8;border-radius:4px;" title="Assign a distinct pipe ID to this segment">
        <i class="bi bi-scissors"></i> Split Segment (Assign New Pipe ID)
      </button>
    </div>
  `;

  pop.querySelector('.pn-popover-close').onclick = hideContextPopover;

  const splitBtn = pop.querySelector('#pop-split-pipe-btn');
  if (splitBtn) {
    splitBtn.onclick = () => {
      const newPipeName = newId('P');
      pipe.props.label = newPipeName;
      pipe.pipeRunId = newPipeName;
      pipe.props.manual_split = true; // Mark as explicit user manual split
      renderAll();
      showPipeProps(pipe);
      showContextPopover('pipe', pipe.id);
      saveNetworkToStorage();
      toast(`Segment split into distinct pipe: ${newPipeName}`, 'info');
    };
  }

  const sizeSel = pop.querySelector('#pop-pipe-size-select');
  if (sizeSel) {
    sizeSel.onchange = (e) => {
      const stdId = parseInt(e.target.value, 10);
      const stdPipe = Array.isArray(STANDARD_PIPES) ? STANDARD_PIPES.find(p => p.id === stdId) : null;
      if (stdPipe) {
        pipe.props.dimension_mode = 'standard';
        pipe.props.standard_pipe_id = stdPipe.id;
        pipe.props.standard = stdPipe.standard;
        pipe.props.schedule_sdr = stdPipe.schedule_sdr;
        pipe.props.nb_mm = stdPipe.nb_mm;
        pipe.props.nb_inch = stdPipe.nb_inch;
        pipe.props.od_mm = stdPipe.od_mm;
        pipe.props.wall_thickness_mm = stdPipe.wall_thickness_mm;
        pipe.props.id_mm = stdPipe.id_mm;
        pipe.props.sdr = stdPipe.sdr;
        pipe.props.pressure_rating = stdPipe.pressure_rating;
        pipe.props.material_key = stdPipe.material_key;
        pipe.props.material = stdPipe.material_key;
        pipe.props.diameter_mm = stdPipe.id_mm;

        // Automatically split into separate pipe ID if this change differs from adjacent segment!
        reconcilePipeRuns();

        renderAll();
        showPipeProps(pipe);
        showContextPopover('pipe', pipe.id);
        saveNetworkToStorage();
      }
    };
  }

  pop.querySelectorAll('.pop-route-btn').forEach(btn => {
    btn.onclick = () => {
      pipe.props.routing = btn.dataset.route;
      renderAll();
      showPipeProps(pipe);
      showContextPopover('pipe', pipe.id);
      saveNetworkToStorage();
    };
  });

  const pipeElevIn = pop.querySelector('#pop-pipe-elev');
  if (pipeElevIn) {
    pipeElevIn.oninput = (e) => {
      syncElevationIntegrity('pipe', pipe.id, e.target.value);
      renderAll();
      showPipeProps(pipe);
    };
  }

  const pipeCustK = pop.querySelector('#pop-pipe-custom-k');
  if (pipeCustK) {
    const onPipeK = (e) => {
      pipe.props.custom_k = parseFloat(e.target.value) || 0;
      refreshKTotal(pipe.props.fittings || [], pipe.props.custom_k);
      renderAll();
      showPipeProps(pipe);
      saveNetworkToStorage();
    };
    pipeCustK.oninput = onPipeK;
    pipeCustK.onchange = onPipeK;
  }
}

// ============================================================================
// SELECTION & PROPERTIES PANEL
// ============================================================================

function selectItem(kind, id) {
  state.selected = kind ? { kind, id } : null;
  if (kind === 'node') showNodeProps(findNode(id));
  else if (kind === 'pipe') showPipeProps(findPipe(id));
  else showPropsPanel('none');

  if (kind && id) {
    showContextPopover(kind, id);
  } else {
    hideContextPopover();
  }

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

function populateFittingOptions(nodeType, currentKey) {
  const nFitSel = document.getElementById('np-fitting-key');
  if (!nFitSel) return;
  nFitSel.innerHTML = '';

  let candidates = [];
  if (nodeType === 'tee') {
    candidates = FITTINGS.filter(f => f.key.startsWith('tee_') || f.category === 'tee');
    if (candidates.length === 0) {
      candidates = [
        { key: 'tee_run_through', label: 'Tee (Run Through)', K: 0.40 },
        { key: 'tee_branch_flow', label: 'Tee (Branch Flow)', K: 1.80 },
      ];
    }
  } else if (nodeType === 'valve') {
    candidates = FITTINGS.filter(f => f.key.includes('valve') || f.category === 'valve');
  } else if (nodeType === 'elbow') {
    candidates = FITTINGS.filter(f => f.key.startsWith('elbow') || f.category === 'elbow');
  } else {
    candidates = FITTINGS;
  }

  candidates.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f.key;
    opt.textContent = `${f.label} (K=${f.K})`;
    nFitSel.appendChild(opt);
  });

  if (currentKey) {
    nFitSel.value = currentKey;
  }
}

function updateKDisplay(node) {
  const el = document.getElementById('np-k-display');
  if (!el || !node) return;
  const kVal = getNodeKFactor(node);
  const isCustom = Boolean(node.props.is_custom_k);
  el.textContent = `K = ${kVal.toFixed(2)}${isCustom ? ' (Custom)' : ''}`;
  el.style.color = isCustom ? '#f59e0b' : '#38bdf8';
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
    if (node.type === 'pump') {
      setVal('np-flow', node.props.flow_m3h ?? 10);
      setVal('np-pump-config', node.props.pump_config || 'end_suction');
    }
  }

  const isFitting = (node.type === 'valve' || node.type === 'elbow' || node.type === 'tee');
  const fittingDiv = document.getElementById('np-fitting-fields');
  if (fittingDiv) {
    fittingDiv.style.display = isFitting ? '' : 'none';
    if (isFitting) {
      populateFittingOptions(node.type, node.props.fitting_key);
    }
  }

  const teeRotGroup = document.getElementById('np-tee-rotation-group');
  if (teeRotGroup) {
    teeRotGroup.style.display = node.type === 'tee' ? '' : 'none';
    setVal('np-tee-rotation', `${node.props.rotation_deg || 0}°`);
  }

  const customKGroup = document.getElementById('np-custom-k-group');
  if (customKGroup) {
    customKGroup.style.display = isFitting ? '' : 'none';
    const isCustom = Boolean(node.props.is_custom_k);
    const cb = document.getElementById('np-is-custom-k');
    if (cb) cb.checked = isCustom;
    const valGroup = document.getElementById('np-custom-k-val-group');
    if (valGroup) valGroup.style.display = isCustom ? '' : 'none';
    setVal('np-custom-k', node.props.custom_k ?? '');
    updateKDisplay(node);
  }
}

// ============================================================================
// STANDARD PIPE SPECIFICATION & FILTERING HELPERS
// ============================================================================

/**
 * Toggle between 'standard' (catalog-based) and 'custom' (manual diameter/roughness) dimension modes.
 * 
 * IMPORTANT: When called during pipe inspection/selection from showPipeProps(), `save` is false.
 * In display mode (save === false), this function ONLY toggles the active button classes and
 * container visibility. It NEVER mutates pipe properties or triggers cascading change handlers,
 * preventing accidental overwrites when clicking different pipes.
 */
function setPipeDimensionMode(mode, save = true) {
  const stdBtn = document.getElementById('pp-mode-std');
  const custBtn = document.getElementById('pp-mode-custom');
  const stdGrp = document.getElementById('pp-std-dim-group');
  const custGrp = document.getElementById('pp-custom-dim-group');

  if (mode === 'standard') {
    stdBtn?.classList.add('active-tool');
    custBtn?.classList.remove('active-tool');
    if (stdGrp) stdGrp.style.display = '';
    if (custGrp) custGrp.style.display = 'none';
  } else {
    custBtn?.classList.add('active-tool');
    stdBtn?.classList.remove('active-tool');
    if (stdGrp) stdGrp.style.display = 'none';
    if (custGrp) custGrp.style.display = '';
  }

  // Only mutate pipe models if explicitly triggered by the user (save === true)
  if (save && state.selected?.kind === 'pipe') {
    const pipe = findPipe(state.selected.id);
    if (pipe) {
      pipe.props.dimension_mode = mode;
      if (mode === 'standard') {
        populateStandardPipeFilters(pipe);
      } else {
        const diaInput = document.getElementById('pp-diameter');
        if (diaInput) {
          diaInput.value = pipe.props.diameter_mm || 100;
        }
        pipe.props.id_mm = pipe.props.diameter_mm || 100;
        updatePipeDetailsCard(pipe.props);
      }
      renderAll();
      saveNetworkToStorage();
    }
  }
}

function getAvailableStandards() {
  if (!Array.isArray(STANDARD_PIPES)) return [];
  const set = new Set();
  STANDARD_PIPES.forEach(p => { if (p.standard) set.add(p.standard); });
  return Array.from(set);
}

function getAvailableMaterialsForStandard(std) {
  if (!Array.isArray(STANDARD_PIPES)) return [];
  const set = new Set();
  STANDARD_PIPES.forEach(p => {
    if (!std || std === 'all' || p.standard === std) {
      if (p.material) set.add(p.material);
    }
  });
  return Array.from(set);
}

function getAvailableSchedulesForFilters(std, mat) {
  if (!Array.isArray(STANDARD_PIPES)) return [];
  const set = new Set();
  STANDARD_PIPES.forEach(p => {
    const stdMatch = !std || std === 'all' || p.standard === std;
    const matMatch = !mat || mat === 'all' || p.material === mat;
    if (stdMatch && matMatch && p.schedule_sdr) {
      set.add(p.schedule_sdr);
    }
  });
  return Array.from(set);
}

function getFilteredStandardPipes(std, mat, sch) {
  if (!Array.isArray(STANDARD_PIPES)) return [];
  return STANDARD_PIPES.filter(p => {
    if (std && std !== 'all' && p.standard !== std) return false;
    if (mat && mat !== 'all' && p.material !== mat) return false;
    if (sch && sch !== 'all' && p.schedule_sdr !== sch) return false;
    return true;
  }).sort((a, b) => (a.nb_mm || a.od_mm || 0) - (b.nb_mm || b.od_mm || 0));
}

function formatStandardPipeLabel(p, includeStandard = false) {
  let sizeLabel = '';
  // ISO 4427 HDPE and DIN 8062 Metric uPVC are commercially specified by Outside Diameter (OD)
  const isMetricOD = p.standard && (p.standard.includes('4427') || p.standard.includes('8062'));

  if (isMetricOD) {
    const nbPart = p.nb_mm ? ` (DN ${p.nb_mm})` : '';
    sizeLabel = `OD ${p.od_mm}mm${nbPart}`;
  } else if (p.nb_inch && !p.nb_inch.includes('mm') && !p.standard.includes('EN 545')) {
    // Imperial nominal bore pipes (ASME B36.10M, B36.19M, ASTM D1785 PVC IPS, SANS 62 Galv):
    sizeLabel = `${p.nb_inch} (DN ${p.nb_mm})`;
  } else {
    // European metric nominal bore pipes (EN 545 Ductile Iron):
    sizeLabel = `DN ${p.nb_mm}`;
  }

  const schStr = p.schedule_sdr ? ` • ${p.schedule_sdr}` : '';
  const stdPrefix = includeStandard ? `[${p.material || p.standard}] ` : '';
  return `${stdPrefix}${sizeLabel}${schStr} — OD ${p.od_mm}mm | ID ${p.id_mm}mm`;
}

function populateStandardPipeFilters(pipe) {
  const stdSel = document.getElementById('pp-filter-standard');
  const matSel = document.getElementById('pp-filter-material');
  const schSel = document.getElementById('pp-filter-schedule');
  const pipeSel = document.getElementById('pp-standard-pipe-select');

  if (!stdSel || !pipeSel) return;

  // Guarantee catalog is present
  if (!Array.isArray(STANDARD_PIPES) || STANDARD_PIPES.length === 0) {
    STANDARD_PIPES = EMBEDDED_STANDARD_PIPES;
  }

  // Determine current active standard pipe or auto-detect from pipe properties
  let activePipe = null;
  if (pipe?.props?.standard_pipe_id) {
    activePipe = STANDARD_PIPES.find(p => p.id === pipe.props.standard_pipe_id);
  }
  if (!activePipe && pipe?.props?.standard) {
    activePipe = STANDARD_PIPES.find(p =>
      p.standard === pipe.props.standard &&
      (!pipe.props.schedule_sdr || p.schedule_sdr === pipe.props.schedule_sdr) &&
      (!pipe.props.nb_mm || p.nb_mm === pipe.props.nb_mm)
    );
  }
  if (!activePipe) {
    // If not yet standard pipe, pick closest match for standard diameter and material
    const targetD = pipe?.props?.id_mm || pipe?.props?.diameter_mm || 100;
    const targetMat = pipe?.props?.material || 'commercial_steel';
    const matPool = STANDARD_PIPES.filter(p => p.material_key === targetMat);
    const pool = matPool.length > 0 ? matPool : STANDARD_PIPES;
    activePipe = pool.reduce((closest, p) => {
      if (!closest) return p;
      return Math.abs(p.id_mm - targetD) < Math.abs(closest.id_mm - targetD) ? p : closest;
    }, null) || STANDARD_PIPES[0];
  }

  // Only sync standard pipe specs onto pipe model if pipe is in 'standard' mode
  if (activePipe && pipe && pipe.props.dimension_mode === 'standard') {
    pipe.props.standard_pipe_id = activePipe.id;
    pipe.props.standard = activePipe.standard;
    pipe.props.schedule_sdr = activePipe.schedule_sdr;
    pipe.props.nb_mm = activePipe.nb_mm;
    pipe.props.nb_inch = activePipe.nb_inch;
    pipe.props.od_mm = activePipe.od_mm;
    pipe.props.wall_thickness_mm = activePipe.wall_thickness_mm;
    pipe.props.id_mm = activePipe.id_mm;
    pipe.props.sdr = activePipe.sdr;
    pipe.props.pressure_rating = activePipe.pressure_rating;
    pipe.props.material_key = activePipe.material_key;
    pipe.props.material = activePipe.material_key;
    pipe.props.diameter_mm = activePipe.id_mm;
  }

  const standards = getAvailableStandards();
  const currentStd = activePipe?.standard || standards[0] || 'all';

  // 1. Standards dropdown
  stdSel.innerHTML = '<option value="all">All Standards</option>';
  standards.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    stdSel.appendChild(opt);
  });
  stdSel.value = standards.includes(currentStd) ? currentStd : 'all';

  // 2. Materials dropdown
  const materials = getAvailableMaterialsForStandard(stdSel.value);
  const currentMat = activePipe?.material || 'all';
  matSel.innerHTML = '<option value="all">All Materials</option>';
  materials.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    matSel.appendChild(opt);
  });
  matSel.value = materials.includes(currentMat) ? currentMat : 'all';

  // 3. Schedules dropdown
  const schedules = getAvailableSchedulesForFilters(stdSel.value, matSel.value);
  const currentSch = activePipe?.schedule_sdr || 'all';
  schSel.innerHTML = '<option value="all">All Schedules / SDRs</option>';
  schedules.forEach(sc => {
    const opt = document.createElement('option');
    opt.value = sc;
    opt.textContent = sc;
    schSel.appendChild(opt);
  });
  schSel.value = schedules.includes(currentSch) ? currentSch : 'all';

  // 4. Pipe sizes dropdown
  updatePipeSizeSelect(pipe);
}

function updatePipeSizeSelect(pipe) {
  const stdSel = document.getElementById('pp-filter-standard');
  const matSel = document.getElementById('pp-filter-material');
  const schSel = document.getElementById('pp-filter-schedule');
  const pipeSel = document.getElementById('pp-standard-pipe-select');
  const countEl = document.getElementById('pp-filter-match-count');

  if (!pipeSel) return;

  const std = stdSel ? stdSel.value : 'all';
  const mat = matSel ? matSel.value : 'all';
  const sch = schSel ? schSel.value : 'all';

  let matches = getFilteredStandardPipes(std, mat, sch);

  // Fallback gracefully if combination has no pipes
  if (matches.length === 0 && sch !== 'all') {
    if (schSel) schSel.value = 'all';
    matches = getFilteredStandardPipes(std, mat, 'all');
  }
  if (matches.length === 0 && mat !== 'all') {
    if (matSel) matSel.value = 'all';
    matches = getFilteredStandardPipes(std, 'all', 'all');
  }
  if (matches.length === 0 && std !== 'all') {
    if (stdSel) stdSel.value = 'all';
    matches = getFilteredStandardPipes('all', 'all', 'all');
  }

  if (countEl) countEl.textContent = `${matches.length} sizes`;

  pipeSel.innerHTML = '';
  if (matches.length === 0) {
    pipeSel.innerHTML = '<option value="">No pipes match filters</option>';
    return;
  }

  let matchedOption = null;
  const targetId = pipe?.props?.standard_pipe_id;
  const targetD = pipe?.props?.id_mm || pipe?.props?.diameter_mm;
  const targetNB = pipe?.props?.nb_mm;

  // When viewing all standards or all materials, group by Standard & Material
  if (std === 'all' || mat === 'all') {
    const groups = {};
    matches.forEach(p => {
      const gKey = `${p.standard} — ${p.material || 'Standard'}`;
      if (!groups[gKey]) groups[gKey] = [];
      groups[gKey].push(p);
    });

    Object.entries(groups).forEach(([groupName, groupPipes]) => {
      const optGroup = document.createElement('optgroup');
      optGroup.label = groupName;
      groupPipes.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = formatStandardPipeLabel(p, false);

        if (targetId && p.id === targetId) {
          opt.selected = true;
          matchedOption = opt;
        } else if (!matchedOption && targetNB && p.nb_mm === targetNB) {
          opt.selected = true;
          matchedOption = opt;
        } else if (!matchedOption && targetD && Math.abs(p.id_mm - targetD) < 5.0) {
          opt.selected = true;
          matchedOption = opt;
        }
        optGroup.appendChild(opt);
      });
      pipeSel.appendChild(optGroup);
    });
  } else {
    matches.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = formatStandardPipeLabel(p, false);

      if (targetId && p.id === targetId) {
        opt.selected = true;
        matchedOption = opt;
      } else if (!matchedOption && targetNB && p.nb_mm === targetNB) {
        opt.selected = true;
        matchedOption = opt;
      } else if (!matchedOption && targetD && Math.abs(p.id_mm - targetD) < 5.0) {
        opt.selected = true;
        matchedOption = opt;
      }
      pipeSel.appendChild(opt);
    });
  }

  if (!matchedOption && pipeSel.options.length > 0) {
    pipeSel.selectedIndex = 0;
  }

  // Note: updatePipeSizeSelect only configures the DOM options to display the current pipe.
  // It NEVER mutates the pipe model or overwrites properties, ensuring that simply clicking
  // or inspecting another pipe on canvas never modifies its diameter or triggers reconciliation.
  updatePipeDetailsCard(pipe?.props);
}

function onStandardPipeFilterChange(changedField) {
  const stdSel = document.getElementById('pp-filter-standard');
  const matSel = document.getElementById('pp-filter-material');
  const schSel = document.getElementById('pp-filter-schedule');
  const pipe = state.selected?.kind === 'pipe' ? findPipe(state.selected.id) : null;

  if (changedField === 'standard') {
    const materials = getAvailableMaterialsForStandard(stdSel.value);
    matSel.innerHTML = '<option value="all">All Materials</option>';
    materials.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      matSel.appendChild(opt);
    });
    if (materials.length === 1) {
      matSel.value = materials[0];
    } else {
      matSel.value = 'all';
    }

    const schedules = getAvailableSchedulesForFilters(stdSel.value, matSel.value);
    schSel.innerHTML = '<option value="all">All Schedules / SDRs</option>';
    schedules.forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc; opt.textContent = sc;
      schSel.appendChild(opt);
    });
    schSel.value = 'all';
  } else if (changedField === 'material') {
    const schedules = getAvailableSchedulesForFilters(stdSel.value, matSel.value);
    schSel.innerHTML = '<option value="all">All Schedules / SDRs</option>';
    schedules.forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc; opt.textContent = sc;
      schSel.appendChild(opt);
    });
    schSel.value = 'all';
  }

  updatePipeSizeSelect(pipe);
  onStandardPipeSelectChange();
}

function onStandardPipeSelectChange() {
  const pipeSel = document.getElementById('pp-standard-pipe-select');
  if (!pipeSel || !pipeSel.value) return;

  const stdId = parseInt(pipeSel.value, 10);
  const stdPipe = Array.isArray(STANDARD_PIPES) ? STANDARD_PIPES.find(p => p.id === stdId) : null;
  if (!stdPipe) return;

  const pipe = state.selected?.kind === 'pipe' ? findPipe(state.selected.id) : null;
  if (!pipe) return;

  pipe.props.dimension_mode = 'standard';
  pipe.props.standard_pipe_id = stdPipe.id;
  pipe.props.standard = stdPipe.standard;
  pipe.props.schedule_sdr = stdPipe.schedule_sdr;
  pipe.props.nb_mm = stdPipe.nb_mm;
  pipe.props.nb_inch = stdPipe.nb_inch;
  pipe.props.od_mm = stdPipe.od_mm;
  pipe.props.wall_thickness_mm = stdPipe.wall_thickness_mm;
  pipe.props.id_mm = stdPipe.id_mm;
  pipe.props.sdr = stdPipe.sdr;
  pipe.props.pressure_rating = stdPipe.pressure_rating;
  pipe.props.material_key = stdPipe.material_key;
  pipe.props.material = stdPipe.material_key;
  // Hydraulic Darcy friction requires internal diameter:
  pipe.props.diameter_mm = stdPipe.id_mm;

  // Sync custom controls to match
  const diaInput = document.getElementById('pp-diameter');
  if (diaInput) diaInput.value = stdPipe.id_mm;
  const matInput = document.getElementById('pp-material');
  if (matInput) matInput.value = stdPipe.material_key;

  updatePipeDetailsCard(pipe.props);
  // Automatically split or merge continuous pipe run based on standard pipe size selection
  reconcilePipeRuns();
  renderAll();
  saveNetworkToStorage();

  // If popover is currently open, re-render it
  const pop = document.getElementById('pn-context-popover');
  if (pop && pop.style.display !== 'none' && state.selected?.kind === 'pipe') {
    renderPopoverPipe(pipe, pop);
  }
}

function updatePipeDetailsCard(props) {
  if (!props) return;
  const titleEl = document.getElementById('pspec-title');
  const ratingEl = document.getElementById('pspec-rating');
  const idEl = document.getElementById('pspec-id');
  const odEl = document.getElementById('pspec-od');
  const nbEl = document.getElementById('pspec-nb');
  const wallEl = document.getElementById('pspec-wall');
  const schEl = document.getElementById('pspec-sch');
  const roughEl = document.getElementById('pspec-rough');

  if (titleEl) {
    if (props.standard) {
      titleEl.textContent = `${props.standard} (${props.schedule_sdr || ''})`;
    } else {
      titleEl.textContent = 'Custom Pipe Dimensions';
    }
  }

  if (ratingEl) {
    ratingEl.textContent = props.pressure_rating || 'PN --';
  }

  if (idEl) {
    const val = props.id_mm || props.diameter_mm;
    idEl.textContent = val ? `${val.toFixed(2)} mm` : '--';
  }

  if (odEl) {
    odEl.textContent = props.od_mm ? `${props.od_mm.toFixed(2)} mm` : (props.diameter_mm ? `${(props.diameter_mm * 1.1).toFixed(1)} mm (approx)` : '--');
  }

  if (nbEl) {
    if (props.nb_mm) {
      nbEl.textContent = `DN ${props.nb_mm}${props.nb_inch ? ' (' + props.nb_inch + ')' : ''}`;
    } else if (props.diameter_mm) {
      nbEl.textContent = `~DN ${Math.round(props.diameter_mm)}`;
    } else {
      nbEl.textContent = '--';
    }
  }

  if (wallEl) {
    wallEl.textContent = props.wall_thickness_mm ? `${props.wall_thickness_mm.toFixed(2)} mm` : '--';
  }

  if (schEl) {
    schEl.textContent = props.schedule_sdr || (props.sdr ? `SDR ${props.sdr}` : 'Standard / Custom');
  }

  if (roughEl) {
    const matObj = MATERIALS.find(m => m.key === props.material);
    if (matObj) {
      roughEl.textContent = matObj.label;
    } else {
      roughEl.textContent = props.material || '--';
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
  updatePipeElevationLabels(pipe);
  setVal('pp-material', pipe.props.material);
  setVal('pp-routing', pipe.props.routing || 'auto');
  setVal('pp-custom-k', pipe.props.custom_k ?? 0);
  document.querySelectorAll('.pp-fitting-cb').forEach(cb => {
    cb.checked = (pipe.props.fittings || []).includes(cb.value);
  });
  refreshKTotal(pipe.props.fittings || [], pipe.props.custom_k || 0);

  // Set dimension mode and populate standard pipe dropdowns and details card
  const dimMode = pipe.props.dimension_mode || 'standard';
  setPipeDimensionMode(dimMode, false);
  populateStandardPipeFilters(pipe);
  updatePipeDetailsCard(pipe.props);
}

function setVal(id, v) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.tagName === 'INPUT' || el.tagName === 'SELECT') el.value = v;
  else el.textContent = v;
}

function refreshKTotal(fittings, customK = 0) {
  const kMap = Object.fromEntries(FITTINGS.map(f => [f.key, f.K]));
  const fittingsK = (fittings || []).reduce((s, item) => {
    if (typeof item === 'object' && item !== null) {
      const k = item.k !== undefined ? parseFloat(item.k) : (kMap[item.key || item.type] || 0);
      return s + (k * (item.count || 1));
    }
    return s + (kMap[item] || 0);
  }, 0);
  const total = fittingsK + (parseFloat(customK) || 0);
  setVal('pp-ktotal', total.toFixed(2));
  return total;
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
    'add-junction': 'Place Junction — click on canvas',
    'add-tee': 'Place Pipe Tee Fitting — click on canvas',
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
  if (node) {
    node.props.label = document.getElementById('np-label').value;
    renderAll();
    saveNetworkToStorage();
  }
}
function onNodeElevChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node) {
    const val = document.getElementById('np-elev').value;
    syncElevationIntegrity('node', node.id, val);
  }
}
function onPumpFlowChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node && node.type === 'pump') {
    node.props.flow_m3h = parseFloat(document.getElementById('np-flow').value) || 10;
    saveNetworkToStorage();
  }
}

function onPumpConfigChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node && node.type === 'pump') {
    const el = document.getElementById('np-pump-config');
    if (el) node.props.pump_config = el.value;
    renderAll();
    saveNetworkToStorage();
  }
}
function onNodeFittingChange() {
  const node = state.selected?.kind === 'node' ? findNode(state.selected.id) : null;
  if (node && (node.type === 'valve' || node.type === 'elbow' || node.type === 'tee')) {
    node.props.fitting_key = document.getElementById('np-fitting-key').value;
    updateKDisplay(node);
    renderAll();
    saveNetworkToStorage();
    if (state.selected?.kind === 'node' && state.selected.id === node.id) {
      showContextPopover('node', node.id);
    }
  }
}

function onGlobalFlowChange() {
  saveNetworkToStorage();
}

/**
 * Handles changes made in the Pipe Segment Properties panel (Sidebar).
 * Automatically triggers graph reconciliation:
 * - If diameter or material is changed, reconcilePipeRuns() detects the physical
 *   mismatch and splits the adjacent segment into a new distinct pipe ID.
 * - If characteristics are changed back to match, the segments re-unify under
 *   one continuous pipe run.
 */
function onPipePropChange() {
  const pipe = state.selected?.kind === 'pipe' ? findPipe(state.selected.id) : null;
  if (!pipe) return;

  const newLabel = (document.getElementById('pp-label').value || '').trim();
  if (newLabel && newLabel !== pipe.props.label) {
    pipe.props.label = newLabel;
    pipe.pipeRunId = newLabel;
    pipe.props.manual_split = true; // Explicit manual label set by user
  }

  if (pipe.props.dimension_mode === 'custom') {
    pipe.props.diameter_mm = parseFloat(document.getElementById('pp-diameter').value) || 100;
    pipe.props.id_mm = pipe.props.diameter_mm;
    pipe.props.material = document.getElementById('pp-material').value;
    pipe.props.material_key = pipe.props.material;
  }
  pipe.props.length_m = parseFloat(document.getElementById('pp-length').value) || 10;
  const newElevVal = document.getElementById('pp-elev-change').value;
  syncElevationIntegrity('pipe', pipe.id, newElevVal);
  pipe.props.routing = document.getElementById('pp-routing').value;
  const ppCustK = document.getElementById('pp-custom-k');
  if (ppCustK) pipe.props.custom_k = parseFloat(ppCustK.value) || 0;
  pipe.props.fittings = [];
  document.querySelectorAll('.pp-fitting-cb:checked').forEach(cb =>
    pipe.props.fittings.push(cb.value)
  );
  refreshKTotal(pipe.props.fittings, pipe.props.custom_k);
  updatePipeDetailsCard(pipe.props);

  // Automatically split into separate pipe IDs if characteristics differ across an inline fitting,
  // or re-merge if properties now match!
  reconcilePipeRuns();

  renderAll();
  saveNetworkToStorage();
  if (state.selected?.kind === 'pipe' && state.selected.id === pipe.id) {
    showContextPopover('pipe', pipe.id);
  }
}

// ============================================================================
// API INTEGRATION
// ============================================================================

async function runCalculation() {
  if (state.pipes.length === 0) {
    toast('Add at least one pipe segment before calculating.', 'warn'); return;
  }
  const globalFlow = parseFloat(document.getElementById('pn-global-flow').value) || 10;
  const solverMethod = document.getElementById('pn-solver-method')?.value || 'ggm';
  const frictionMethod = document.getElementById('pn-friction-method')?.value || 'darcy_weisbach';

  const payload = {
    flow_m3h: globalFlow,
    solver_method: solverMethod,
    friction_method: frictionMethod,
    nodes: state.nodes.map(node => ({
      id: node.id,
      type: node.type,
      props: node.props || {},
      x: node.x,
      y: node.y,
    })),
    pipes: state.pipes.map(pipe => {
      const allFittings = [...(pipe.props.fittings || [])];
      const toNode = findNode(pipe.toNodeId);
      if (toNode && toNode.props.fitting_key) {
        if (toNode.props.is_custom_k && toNode.props.custom_k !== null && toNode.props.custom_k !== undefined) {
          allFittings.push({
            id: `fit_${toNode.id}`,
            key: toNode.props.fitting_key,
            k: parseFloat(toNode.props.custom_k) || 0,
            label: `${toNode.props.label || toNode.id} (Custom K=${toNode.props.custom_k})`
          });
        } else {
          allFittings.push({
            id: `fit_${toNode.id}`,
            key: toNode.props.fitting_key,
            label: toNode.props.label || toNode.id,
          });
        }
      }
      return {
        id: pipe.id,
        from_node: pipe.fromNodeId,
        to_node: pipe.toNodeId,
        label: pipe.props.label || pipe.id,
        diameter_mm: pipe.props.diameter_mm,
        length_m: pipe.props.length_m,
        material: pipe.props.material,
        elev_change_m: pipe.props.elev_change_m,
        fittings: allFittings,
        custom_k: parseFloat(pipe.props.custom_k) || 0.0,
        standard: pipe.props.standard,
        schedule_sdr: pipe.props.schedule_sdr,
        nb_mm: pipe.props.nb_mm,
        od_mm: pipe.props.od_mm,
        id_mm: pipe.props.id_mm,
        pressure_rating: pipe.props.pressure_rating,
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
    state.lastCalculation = data;
    saveNetworkToStorage();
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
  setVal('res-r-sys', s.total_system_R !== undefined ? s.total_system_R.toFixed(2) : '—');
  setVal('res-method-label', s.friction_method === 'hazen_williams' ? 'Hazen-Williams' : 'Darcy-Weisbach');

  // Populate solver summary card
  const solverStatusEl = document.getElementById('res-solver-status');
  if (solverStatusEl) {
    const iterCount = s.iterations || 1;
    const iterText = ` (${iterCount} iter${iterCount > 1 ? 's' : ''})`;
    solverStatusEl.textContent = s.converged ? `Converged${iterText}` : `Iterating${iterText}`;
    solverStatusEl.style.color = s.converged ? '#22c55e' : '#f59e0b';
  }
  const solverNameEl = document.getElementById('res-solver-name');
  if (solverNameEl) {
    const solverShortNames = {
      'ggm': 'GGM (EPANET)',
      'newton_raphson': 'Newton-Raphson',
      'hardy_cross': 'Hardy Cross',
      'linear_theory': 'Linear Theory'
    };
    solverNameEl.textContent = s.solver_name || solverShortNames[s.solver_method] || (s.solver_method ? s.solver_method.toUpperCase() : 'GGM');
  }

  const thFric = document.getElementById('th-friction-factor');
  if (thFric) {
    thFric.textContent = s.friction_method === 'hazen_williams' ? 'HW C / f' : 'Friction f';
  }

  const formulaRef = document.getElementById('pn-formula-reference');
  if (formulaRef) {
    const solverDescriptions = {
      'ggm': 'Global Gradient Method (Todini &amp; Pilati EPANET Standard &mdash; simultaneous node heads &amp; pipe flows)',
      'newton_raphson': 'Newton-Raphson Method (Node Head Formulation &mdash; quadratic Jacobian convergence)',
      'hardy_cross': 'Hardy Cross Method (Fundamental Loop Balancing &mdash; successive loop corrections &Delta;Q)',
      'linear_theory': 'Linear Theory Method (Isaacs &amp; Mills &mdash; linearized pipe resistance matrix &amp; under-relaxation)'
    };
    const activeSolverDesc = solverDescriptions[s.solver_method] || (s.solver_name || 'Global Gradient Method (GGM)');
    const frictionDesc = s.friction_method === 'hazen_williams'
      ? `Major friction: <code style="color:#38bdf8;">hf = 10.67 &times; L &times; C<sup>-1.852</sup> &times; D<sup>-4.87</sup> &times; Q<sup>1.852</sup></code> (Hazen-Williams, n=1.852)`
      : `Major friction: <code style="color:#58a6ff;">hf = f &times; (L/D) &times; V&sup2;/2g</code> (Colebrook-White / Swamee-Jain, n=2.000)`;

    formulaRef.innerHTML = `
      <div style="margin-bottom:4px;"><strong style="color:#c084fc;">Network Solver:</strong> <span style="color:#f8fafc;">${activeSolverDesc}</span></div>
      <div><strong style="color:#8b949e;">Friction Formulation:</strong> ${frictionDesc} &mdash;
      Minor losses: <code style="color:#58a6ff;">hm = K &times; V&sup2;/2g</code> (Crane TP-410) &mdash;
      Fluid: <code style="color:#58a6ff;">Water @ 20&deg;C</code></div>
    `;
  }

  const tbody = document.getElementById('res-table-body');
  if (tbody) {
    tbody.innerHTML = '';
    data.results.forEach(r => {
      const rc = r.regime === 'Laminar' ? '#22c55e' : r.regime === 'Transitional' ? '#f59e0b' : '#60a5fa';
      const vc = r.velocity_status === 'OK' ? '#22c55e' : r.velocity_status === 'Too slow' ? '#94a3b8' : '#f87171';
      const fricCell = s.friction_method === 'hazen_williams'
        ? `<span style="color:#38bdf8;font-weight:600;">C=${r.hazen_williams_c || 120}</span><br><span style="font-size:9.5px;color:#64748b;">(f=${r.friction_factor})</span>`
        : `<span style="font-family:monospace;">${r.friction_factor}</span>`;

      tbody.innerHTML += `
        <tr style="border-bottom:1px solid #21262d" onmouseover="this.style.background='#1c2330'" onmouseout="this.style.background=''">
          <td style="padding:6px 10px;font-family:monospace;color:#58a6ff">${r.id}</td>
          <td style="padding:6px 10px;color:#e6edf3">
            ${r.label}
            ${r.schedule_sdr ? `<div style="font-size:10px;color:#94a3b8;">${r.standard || ''} ${r.schedule_sdr}</div>` : ''}
          </td>
          <td style="padding:6px 10px;text-align:right">
            ${r.diameter_mm}
            ${r.od_mm ? `<div style="font-size:10px;color:#64748b;">OD ${r.od_mm}</div>` : ''}
          </td>
          <td style="padding:6px 10px;text-align:right">${r.length_m}</td>
          <td style="padding:6px 10px;text-align:right">${r.velocity_ms}
            <span style="font-size:10px;color:${vc}"> ${r.velocity_status}</span></td>
          <td style="padding:6px 10px;text-align:center">
            <span style="color:${rc};font-size:11px">${r.regime}</span><br>
            <span style="color:#64748b;font-size:10px">Re ${r.reynolds.toLocaleString()}</span></td>
          <td style="padding:6px 10px;text-align:right">${fricCell}</td>
          <td style="padding:6px 10px;text-align:right;color:#e2e8f0;font-weight:600">${r.K_total !== undefined ? r.K_total.toFixed(2) : '—'}</td>
          <td style="padding:6px 10px;text-align:right;color:#f87171">${r.hf_major_m}</td>
          <td style="padding:6px 10px;text-align:right;color:#fb923c">${r.hf_minor_m}</td>
          <td style="padding:6px 10px;text-align:right;color:#a78bfa">${r.hf_elevation_m}</td>
          <td style="padding:6px 10px;text-align:right;font-weight:700;color:#fbbf24">${r.h_total_m}</td>
          <td style="padding:6px 10px;text-align:right;font-family:monospace;color:#38bdf8">${r.resistance_R !== undefined ? r.resistance_R.toFixed(1) : '—'}</td>
          <td style="padding:6px 10px;text-align:right;font-family:monospace;color:#94a3b8">${r.flow_exponent_n !== undefined ? r.flow_exponent_n.toFixed(3) : (s.friction_method === 'hazen_williams' ? '1.852' : '2.000')}</td>
        </tr>`;
    });
    (data.errors || []).forEach(err => {
      tbody.innerHTML += `<tr><td colspan="14" style="padding:6px 10px;color:#f85149">Error in ${err.id}: ${err.error}</td></tr>`;
    });
  }

  // Populate Node Hydraulic Grade Line (HGL) & Pressures table
  const nodeTbody = document.getElementById('res-node-table-body');
  if (nodeTbody && Array.isArray(data.node_results)) {
    nodeTbody.innerHTML = '';
    const nodeTableHasDemand = (document.getElementById('pn-node-results-table')?.querySelectorAll('th').length || 0) >= 8;
    data.node_results.forEach(n => {
      const typeBadgeColors = {
        'reservoir': 'background:rgba(59,130,246,0.15);color:#60a5fa;border:1px solid rgba(59,130,246,0.4)',
        'pump': 'background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.4)',
        'tank': 'background:rgba(34,197,94,0.15);color:#4ade80;border:1px solid rgba(34,197,94,0.4)',
        'junction': 'background:rgba(245,158,11,0.15);color:#fbbf24;border:1px solid rgba(245,158,11,0.4)',
        'discharge': 'background:rgba(2,132,199,0.15);color:#38bdf8;border:1px solid rgba(2,132,199,0.4)',
        'tee': 'background:rgba(249,115,22,0.15);color:#fb923c;border:1px solid rgba(249,115,22,0.4)',
        'valve': 'background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.4)',
        'elbow': 'background:rgba(236,72,153,0.15);color:#f472b6;border:1px solid rgba(236,72,153,0.4)'
      };
      const badgeStyle = typeBadgeColors[n.node_type] || 'background:rgba(148,163,184,0.15);color:#cbd5e1;border:1px solid rgba(148,163,184,0.4)';
      const pVal = n.pressure_kpa !== undefined ? n.pressure_kpa : 0;
      const pColor = pVal >= 0 ? '#4ade80' : '#f87171';

      nodeTbody.innerHTML += `
        <tr style="border-bottom:1px solid #21262d" onmouseover="this.style.background='#1c2330'" onmouseout="this.style.background=''">
          <td style="padding:6px 10px;font-family:monospace;color:#c084fc;font-weight:600;">${n.node_id}</td>
          <td style="padding:6px 10px;color:#e6edf3;">${n.label || n.node_id}</td>
          <td style="padding:6px 10px;">
            <span style="font-size:10px;padding:2px 6px;border-radius:4px;text-transform:capitalize;${badgeStyle}">
              ${n.node_type}
            </span>
          </td>
          <td style="padding:6px 10px;text-align:right;font-family:monospace;color:#a78bfa;">${n.elevation_m !== undefined ? n.elevation_m.toFixed(2) : '0.00'}</td>
          <td style="padding:6px 10px;text-align:right;font-family:monospace;font-weight:700;color:#fbbf24;">${n.head_m !== undefined ? n.head_m.toFixed(2) : '—'}</td>
          <td style="padding:6px 10px;text-align:right;font-family:monospace;color:${pColor};">${n.pressure_head_m !== undefined ? n.pressure_head_m.toFixed(2) : '—'}</td>
          <td style="padding:6px 10px;text-align:right;font-family:monospace;font-weight:600;color:${pColor};">${n.pressure_kpa !== undefined ? n.pressure_kpa.toFixed(1) : '—'}</td>
          ${nodeTableHasDemand ? `<td style="padding:6px 10px;text-align:right;font-family:monospace;color:#94a3b8;">${(n.demand_m3h || 0).toFixed(1)}</td>` : ''}
        </tr>`;
    });
  }
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
      reconcilePipeRuns();
      reconcileAllPipesElevation();
      selectItem(null); renderAll();
      toast('Network loaded!', 'success');
    } catch (err) { toast(`Import failed: ${err.message}`, 'error'); }
  };
  reader.readAsText(file);
}

function clearCanvas() {
  if (!state.nodes.length && !state.pipes.length) return;
  if (!confirm('Clear the entire network? This cannot be undone.')) return;
  state.nodes = [];
  state.pipes = [];
  state.lastCalculation = null;
  const sec = document.getElementById('pn-results-section');
  if (sec) sec.style.display = 'none';
  selectItem(null);
  renderAll();
  saveNetworkToStorage({ explicitClear: true });
  toast('Canvas cleared.', 'info');
}

function resetToDemo() {
  if (state.nodes.length || state.pipes.length) {
    if (!confirm('Replace current network with the demo layout?')) return;
  }
  loadDemoNetwork();
  toast('Demo network loaded.', 'info');
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
// THEME & LEGEND CONTROLS
// ============================================================================

/**
 * Toggle between Dark theme (default CAD dark blueprint) and Light CAD theme on the canvas wrap.
 * 
 * Behavior:
 *  - Adds/removes the 'pn-light-theme' CSS class on #pn-canvas-wrap.
 *  - Updates the Theme button icon (Sun vs. Moon) and active highlight state.
 *  - Saves the user's preference to localStorage ('pmp_pipe_canvas_theme') to persist across page reloads.
 * 
 * @param {'light'|'dark'} [forceTheme] - Optional explicit theme mode to apply.
 */
function toggleTheme(forceTheme) {
  const canvasWrap = document.getElementById('pn-canvas-wrap');
  const themeBtn = document.getElementById('btn-theme-toggle');
  if (!canvasWrap || !themeBtn) return;

  const isCurrentLight = canvasWrap.classList.contains('pn-light-theme');
  const shouldBeLight = forceTheme !== undefined ? forceTheme === 'light' : !isCurrentLight;

  if (shouldBeLight) {
    canvasWrap.classList.add('pn-light-theme');
    themeBtn.classList.add('active-tool');
    themeBtn.innerHTML = '<i class="bi bi-moon"></i> Theme';
    themeBtn.setAttribute('title', 'Switch to Dark CAD Theme');
    localStorage.setItem('pmp_pipe_canvas_theme', 'light');
  } else {
    canvasWrap.classList.remove('pn-light-theme');
    themeBtn.classList.remove('active-tool');
    themeBtn.innerHTML = '<i class="bi bi-sun"></i> Theme';
    themeBtn.setAttribute('title', 'Switch to Light CAD Theme');
    localStorage.setItem('pmp_pipe_canvas_theme', 'dark');
  }
}

/**
 * Toggle the visibility of the canvas Legend Overlay (showing pipes, fittings, valves).
 * 
 * Behavior:
 *  - Shows or hides the #pn-legend-overlay DOM element.
 *  - Updates the active-tool visual state of the #btn-toggle-legend toolbar button.
 *  - Saves the user's preference to localStorage ('pmp_pipe_legend_visible') to persist across page reloads.
 * 
 * @param {boolean} [forceVisible] - Optional explicit boolean to show (true) or hide (false) the legend.
 */
function toggleLegend(forceVisible) {
  const legendEl = document.getElementById('pn-legend-overlay');
  const legendBtn = document.getElementById('btn-toggle-legend');
  if (!legendEl || !legendBtn) return;

  const isVisible = legendEl.style.display !== 'none';
  const shouldShow = forceVisible !== undefined ? forceVisible : !isVisible;

  if (shouldShow) {
    legendEl.style.display = 'block';
    legendBtn.classList.add('active-tool');
    localStorage.setItem('pmp_pipe_legend_visible', 'true');
  } else {
    legendEl.style.display = 'none';
    legendBtn.classList.remove('active-tool');
    localStorage.setItem('pmp_pipe_legend_visible', 'false');
  }
}

// Expose on window object so HTML inline event handlers (e.g. close buttons) can invoke them
window.toggleTheme = toggleTheme;
window.toggleLegend = toggleLegend;
window.setViewMode = setViewMode;
window.renderLegend = renderLegend;

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

  // Dynamic magnetic alignment guidelines (dashed cyan guides)
  guideLineX = mkSVG('line', {
    stroke: '#38bdf8', 'stroke-width': 1.2, 'stroke-dasharray': '5 4', opacity: 0.85
  });
  guideLineX.style.display = 'none';
  guideLineX.style.pointerEvents = 'none';
  svgEl.appendChild(guideLineX);

  guideLineY = mkSVG('line', {
    stroke: '#38bdf8', 'stroke-width': 1.2, 'stroke-dasharray': '5 4', opacity: 0.85
  });
  guideLineY.style.display = 'none';
  guideLineY.style.pointerEvents = 'none';
  svgEl.appendChild(guideLineY);

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
      const srcNode = findNode(state.drawingPipe.fromNodeId);
      let mx = pos.x;
      let my = pos.y;

      // Smart horizontal & vertical snap to source node while drawing pipe
      if (srcNode) {
        if (Math.abs(my - srcNode.y) <= 14) {
          my = srcNode.y;
        }
        if (Math.abs(mx - srcNode.x) <= 14) {
          mx = srcNode.x;
        }
      }

      state.drawingPipe.mouseX = mx;
      state.drawingPipe.mouseY = my;
      updateDraftLine();
    }
    if (state.nodeDrag) {
      const pos = toSVG(e);
      const node = findNode(state.nodeDrag.nodeId);
      if (node) {
        const rawX = pos.x - state.nodeDrag.offsetX;
        const rawY = pos.y - state.nodeDrag.offsetY;
        const snapped = getSmartSnappedPosition(node.id, rawX, rawY);
        node.x = snapped.x;
        node.y = snapped.y;
        renderAll();
        updateContextPopoverPosition();
      }
    }
    if (state.panDrag) {
      state.pan.x = state.panDrag.startPanX + (e.clientX - state.panDrag.startX);
      state.pan.y = state.panDrag.startPanY + (e.clientY - state.panDrag.startY);
      applyTransform();
    }
  });

  svgEl.addEventListener('mouseup', () => {
    hideAlignmentGuides();
    if (state.nodeDrag || state.panDrag) {
      saveNetworkToStorage();
    }
    state.nodeDrag = null;
    state.panDrag = null;
  });

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
    saveNetworkToStorage();
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
  document.getElementById('btn-add-tee')?.addEventListener('click', () => setMode('add-tee'));
  document.getElementById('btn-add-discharge')?.addEventListener('click', () => setMode('add-discharge'));
  document.getElementById('btn-add-valve')?.addEventListener('click', () => setMode('add-valve'));
  document.getElementById('btn-add-elbow')?.addEventListener('click', () => setMode('add-elbow'));
  document.getElementById('btn-delete')?.addEventListener('click', deleteSelected);
  document.getElementById('btn-save')?.addEventListener('click', saveNetwork);
  document.getElementById('btn-load-demo')?.addEventListener('click', resetToDemo);
  document.getElementById('btn-clear')?.addEventListener('click', clearCanvas);
  document.getElementById('btn-export')?.addEventListener('click', exportNetwork);

  // View mode toggle (Industrial/Visual vs. Schematic)
  document.getElementById('btn-view-schematic')?.addEventListener('click', () => setViewMode('schematic'));
  document.getElementById('btn-view-industrial')?.addEventListener('click', () => setViewMode('industrial'));

  // Restore saved view mode preference (defaults to 'industrial' / Visual mode)
  const savedViewMode = localStorage.getItem('pmp_pipe_view_mode') || 'industrial';
  setViewMode(savedViewMode);

  // Canvas Theme toggle (Dark CAD blueprint vs. Light CAD mode)
  document.getElementById('btn-theme-toggle')?.addEventListener('click', () => toggleTheme());

  // Legend Overlay toggle (Show / Hide schematic installation symbols)
  document.getElementById('btn-toggle-legend')?.addEventListener('click', () => toggleLegend());

  // Restore saved Theme & Legend preferences from localStorage
  const savedTheme = localStorage.getItem('pmp_pipe_canvas_theme');
  if (savedTheme === 'light') {
    toggleTheme('light');
  }

  const savedLegend = localStorage.getItem('pmp_pipe_legend_visible');
  if (savedLegend === 'false') {
    toggleLegend(false);
  }

  const importInput = document.getElementById('import-file-input');
  document.getElementById('btn-import')?.addEventListener('click', () => importInput?.click());
  importInput?.addEventListener('change', e => {
    if (e.target.files[0]) importNetwork(e.target.files[0]);
    e.target.value = '';
  });

  document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
    state.zoom = Math.min(3, state.zoom * 1.2); applyTransform(); saveNetworkToStorage();
  });
  document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
    state.zoom = Math.max(0.2, state.zoom / 1.2); applyTransform(); saveNetworkToStorage();
  });
  document.getElementById('btn-zoom-reset')?.addEventListener('click', () => {
    state.zoom = 1; state.pan = { x: 0, y: 0 }; applyTransform(); saveNetworkToStorage();
  });

  document.getElementById('pn-calc-btn')?.addEventListener('click', runCalculation);

  // Network Analysis / Solver Method selection
  const solverSelect = document.getElementById('pn-solver-method');
  solverSelect?.addEventListener('change', () => {
    const selectedSolver = solverSelect.value;
    localStorage.setItem('pmpro_solver_method', selectedSolver);
    saveNetworkToStorage();
    if (state.lastCalculation && document.getElementById('pn-results-section')?.style.display !== 'none') {
      runCalculation();
    }
    const solverNames = {
      'ggm': 'Global Gradient Method (GGM)',
      'newton_raphson': 'Newton-Raphson (NR)',
      'hardy_cross': 'Hardy Cross Method',
      'linear_theory': 'Linear Theory Method'
    };
    toast(`Network solver: ${solverNames[selectedSolver] || selectedSolver}`, 'info');
  });

  // Calculation / Friction Method selection
  const methodSelect = document.getElementById('pn-friction-method');
  methodSelect?.addEventListener('change', () => {
    const selectedMethod = methodSelect.value;
    localStorage.setItem('pmpro_calc_method', selectedMethod);
    saveNetworkToStorage();
    if (state.lastCalculation && document.getElementById('pn-results-section')?.style.display !== 'none') {
      runCalculation();
    }
    toast(`Friction formulation: ${selectedMethod === 'hazen_williams' ? 'Hazen-Williams (C-Factor)' : 'Darcy-Weisbach (Moody)'}`, 'info');
  });

  // Global flow rate
  document.getElementById('pn-global-flow')?.addEventListener('input', onGlobalFlowChange);
  document.getElementById('pn-global-flow')?.addEventListener('change', onGlobalFlowChange);

  // Property inputs (handle both input and change events for real-time saving)
  const npLabel = document.getElementById('np-label');
  npLabel?.addEventListener('input', onNodeLabelChange);
  npLabel?.addEventListener('change', onNodeLabelChange);

  const npElev = document.getElementById('np-elev');
  npElev?.addEventListener('input', onNodeElevChange);
  npElev?.addEventListener('change', onNodeElevChange);

  const npFlow = document.getElementById('np-flow');
  npFlow?.addEventListener('input', onPumpFlowChange);
  npFlow?.addEventListener('change', onPumpFlowChange);

  document.getElementById('np-fitting-key')?.addEventListener('change', onNodeFittingChange);
  document.getElementById('np-pump-config')?.addEventListener('change', onPumpConfigChange);

  // Tee rotation button in properties panel
  document.getElementById('btn-rotate-tee')?.addEventListener('click', () => {
    if (state.selected?.kind === 'node') {
      const node = findNode(state.selected.id);
      if (node && node.type === 'tee') {
        node.props.rotation_deg = ((node.props.rotation_deg || 0) + 90) % 360;
        renderAll();
        showNodeProps(node);
        showContextPopover('node', node.id);
        saveNetworkToStorage();
      }
    }
  });

  // Custom K checkbox in properties panel
  document.getElementById('np-is-custom-k')?.addEventListener('change', e => {
    if (state.selected?.kind === 'node') {
      const node = findNode(state.selected.id);
      if (node) {
        node.props.is_custom_k = e.target.checked;
        const valGroup = document.getElementById('np-custom-k-val-group');
        if (valGroup) valGroup.style.display = node.props.is_custom_k ? '' : 'none';
        if (node.props.is_custom_k && (node.props.custom_k === null || node.props.custom_k === undefined)) {
          node.props.custom_k = getNodeKFactor(node);
          setVal('np-custom-k', node.props.custom_k);
        }
        updateKDisplay(node);
        renderAll();
        showContextPopover('node', node.id);
        saveNetworkToStorage();
      }
    }
  });

  // Custom K value input in properties panel
  const npCustomK = document.getElementById('np-custom-k');
  const onCustomKInput = () => {
    if (state.selected?.kind === 'node') {
      const node = findNode(state.selected.id);
      if (node) {
        node.props.custom_k = parseFloat(npCustomK.value) || 0;
        updateKDisplay(node);
        renderAll();
        showContextPopover('node', node.id);
        saveNetworkToStorage();
      }
    }
  };
  npCustomK?.addEventListener('input', onCustomKInput);
  npCustomK?.addEventListener('change', onCustomKInput);

  // Pipe additive custom K input in properties panel
  const ppCustomK = document.getElementById('pp-custom-k');
  const onPipeCustomK = () => {
    if (state.selected?.kind === 'pipe') {
      const pipe = findPipe(state.selected.id);
      if (pipe) {
        pipe.props.custom_k = parseFloat(ppCustomK.value) || 0;
        refreshKTotal(pipe.props.fittings || [], pipe.props.custom_k);
        renderAll();
        showContextPopover('pipe', pipe.id);
        saveNetworkToStorage();
      }
    }
  };
  ppCustomK?.addEventListener('input', onPipeCustomK);
  ppCustomK?.addEventListener('change', onPipeCustomK);

  // Pipe property inputs (includes pp-routing now)
  ['pp-label', 'pp-diameter', 'pp-length', 'pp-elev-change', 'pp-material', 'pp-routing'].forEach(id => {
    const el = document.getElementById(id);
    el?.addEventListener('input', onPipePropChange);
    el?.addEventListener('change', onPipePropChange);
  });
  document.getElementById('pp-fittings-list')?.addEventListener('change', onPipePropChange);

  // Standard pipe filter listeners
  document.getElementById('pp-filter-standard')?.addEventListener('change', () => onStandardPipeFilterChange('standard'));
  document.getElementById('pp-filter-material')?.addEventListener('change', () => onStandardPipeFilterChange('material'));
  document.getElementById('pp-filter-schedule')?.addEventListener('change', () => onStandardPipeFilterChange('schedule'));
  document.getElementById('pp-standard-pipe-select')?.addEventListener('change', onStandardPipeSelectChange);
  document.getElementById('pp-mode-std')?.addEventListener('click', () => setPipeDimensionMode('standard'));
  document.getElementById('pp-mode-custom')?.addEventListener('click', () => setPipeDimensionMode('custom'));

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

  // Ensure state is flushed to storage on tab unload or visibility hidden
  window.addEventListener('beforeunload', () => {
    const payload = getNetworkPayload();
    try {
      localStorage.setItem('pmpro_pipe_network', JSON.stringify(payload));
      if (navigator.sendBeacon) {
        const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
        navigator.sendBeacon('/api/pipe-network/save', blob);
      }
    } catch (e) { }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      saveNetworkToStorage();
    }
  });

  // Initial state
  setMode('select');
  showPropsPanel('none');

  if (!loadNetworkFromStorage()) {
    loadDemoNetwork();
  } else {
    renderAll();
    if (state.pendingSelect) {
      selectItem(state.pendingSelect.kind, state.pendingSelect.id);
      delete state.pendingSelect;
    }
  }
  applyTransform();
}

/**
 * Demo Network:
 * Simple pumping circuit consisting of:
 * - Sump (Reservoir)
 * - Suction Pipe
 * - Pump (Centrifugal)
 * - Continuous Discharge Pipe with an Inline Gate Valve
 * - Discharge Point (Free outlet)
 * 
 * Both segments of the discharge pipe share the same pipe identity ('Discharge Pipe')
 * and identical hydraulic parameters, visually and structurally proving the continuous
 * pipe architecture with fittings as attributes.
 */
function loadDemoNetwork() {
  state.nodes = [
    {
      id: 'N-1', type: 'reservoir', x: 120, y: 320,
      props: { label: 'Sump', elevation_m: 0 }
    },
    {
      id: 'N-2', type: 'pump', x: 340, y: 320,
      props: { label: 'Pump 1', flow_m3h: 20, elevation_m: 0, pump_config: 'end_suction' }
    },
    {
      id: 'N-3', type: 'valve', x: 540, y: 320,
      props: { label: 'Gate Valve', elevation_m: 2, fitting_key: 'gate_valve_open' }
    },
    {
      id: 'N-4', type: 'discharge', x: 760, y: 320,
      props: { label: 'Discharge', elevation_m: 10 }
    },
  ];

  state.pipes = [
    {
      id: 'P-1', fromNodeId: 'N-1', toNodeId: 'N-2',
      pipeRunId: 'Suction Pipe',
      props: {
        label: 'Suction Pipe',
        dimension_mode: 'standard',
        standard: 'ASME B36.10M',
        schedule_sdr: 'Sch 40 (STD)',
        nb_mm: 125,
        nb_inch: '5"',
        od_mm: 141.3,
        wall_thickness_mm: 6.55,
        id_mm: 128.2,
        pressure_rating: 'PN 63 bar (915 psi)',
        diameter_mm: 128.2,
        length_m: 4,
        material: 'commercial_steel',
        elev_change_m: 0,
        fittings: ['entry_bellmouth'],
        routing: 'straight'
      }
    },
    {
      id: 'P-2', fromNodeId: 'N-2', toNodeId: 'N-3',
      pipeRunId: 'Discharge Pipe',
      props: {
        label: 'Discharge Pipe',
        dimension_mode: 'standard',
        standard: 'ASME B36.10M',
        schedule_sdr: 'Sch 40 (STD)',
        nb_mm: 100,
        nb_inch: '4"',
        od_mm: 114.3,
        wall_thickness_mm: 6.02,
        id_mm: 102.26,
        pressure_rating: 'PN 79 bar (1145 psi)',
        diameter_mm: 102.26,
        length_m: 12,
        material: 'commercial_steel',
        elev_change_m: 2,
        fittings: ['check_valve_swing'],
        routing: 'straight'
      }
    },
    {
      id: 'P-3', fromNodeId: 'N-3', toNodeId: 'N-4',
      pipeRunId: 'Discharge Pipe',
      props: {
        label: 'Discharge Pipe',
        dimension_mode: 'standard',
        standard: 'ASME B36.10M',
        schedule_sdr: 'Sch 40 (STD)',
        nb_mm: 100,
        nb_inch: '4"',
        od_mm: 114.3,
        wall_thickness_mm: 6.02,
        id_mm: 102.26,
        pressure_rating: 'PN 79 bar (1145 psi)',
        diameter_mm: 102.26,
        length_m: 20,
        material: 'commercial_steel',
        elev_change_m: 8,
        fittings: ['exit_abrupt'],
        routing: 'straight'
      }
    },
  ];
  state.nextId = 10;
  state.lastCalculation = null;
  state.pan = { x: 0, y: 0 };
  state.zoom = 1.0;
  const flowEl = document.getElementById('pn-global-flow');
  if (flowEl) flowEl.value = 20;
  const sec = document.getElementById('pn-results-section');
  if (sec) sec.style.display = 'none';
  reconcilePipeRuns();
  reconcileAllPipesElevation();
  renderAll();
  applyTransform();
  saveNetworkToStorage();
}

document.addEventListener('DOMContentLoaded', init);