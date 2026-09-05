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
        inputEl.value = convertValue(inputEl.value, prevUnit, newUnit, cat);
      }

      sel.dataset.prev = newUnit;
      updateSystemBadge();
    });
  });

  // ── Liquid parameter switching ─────────────────────────────────────────────
  // Beginners Note: Shows/hides the appropriate input fields based on selected liquid type
  const liquidSel = document.getElementById('liquidSel');
  if (liquidSel) {
    function updateLiquidPanels() {
      const liquid = liquidSel.value;
      document.getElementById('waterParams').style.display   = liquid === 'water'   ? '' : 'none';
      document.getElementById('viscousParams').style.display = liquid === 'viscous' ? '' : 'none';
      document.getElementById('slurryParams').style.display  = liquid === 'slurry'  ? '' : 'none';
    }
    liquidSel.addEventListener('change', updateLiquidPanels);
    updateLiquidPanels();
  }

  // ── Dynamic Slurry Calculator ──────────────────────────────────────────────
  // Beginners Note: Enforces exactly 3 independent parameters from (L, S, M, Cv, Cw)
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
      el.value = (val % 1 !== 0) ? val.toFixed(3) : val;
    }
  };

  // 2-way sync for Liquid & Solid density/SG pairs
  function syncPairs(e) {
    if (e.target.id === 'rho_l') setVal('sg_l', getVal('rho_l') / 1000);
    else if (e.target.id === 'sg_l') setVal('rho_l', getVal('sg_l') * 1000);
    else if (e.target.id === 'rho_s') setVal('sg_s', getVal('rho_s') / 1000);
    else if (e.target.id === 'sg_s') setVal('rho_s', getVal('sg_s') * 1000);
    else if (e.target.id === 'rho_m') setVal('sg_m', getVal('rho_m') / 1000);
    else if (e.target.id === 'sg_m') setVal('rho_m', getVal('sg_m') * 1000);
    updateSlurryCalculator();
  }

  slurryInputs.forEach(input => {
    input.addEventListener('input', syncPairs);
  });

  function updateSlurryCalculator() {
    try {
      // Collect active (checked) parameters
      const active = new Set([...slurryCheckboxes].filter(cb => cb.checked).map(cb => cb.dataset.param));
      
      // Read raw inputs
      let L = getVal('sg_l');
      let S = getVal('sg_s');
      let M = getVal('sg_m');
      let Cv = getVal('slurry_cv');
      let Cw = getVal('slurry_cw');

      if (active.size !== 3) return; // Need exactly 3 knowns

      // Solver logic for combinations
      if (active.has('L') && active.has('S') && active.has('M')) {
        Cv = (S - L !== 0) ? (M - L) / (S - L) : 0;
        Cw = M !== 0 ? (S * Cv) / M : 0;
      }
      else if (active.has('L') && active.has('S') && active.has('Cv')) {
        M = L * (1 - Cv) + S * Cv;
        Cw = M !== 0 ? (S * Cv) / M : 0;
      }
      else if (active.has('L') && active.has('S') && active.has('Cw')) {
        const denom = S - Cw * (S - L);
        Cv = denom !== 0 ? (Cw * L) / denom : 0;
        M = L * (1 - Cv) + S * Cv;
      }
      else if (active.has('L') && active.has('M') && active.has('Cv')) {
        S = Cv !== 0 ? (M - L * (1 - Cv)) / Cv : 0;
        Cw = M !== 0 ? (S * Cv) / M : 0;
      }
      else if (active.has('L') && active.has('M') && active.has('Cw')) {
        const denom = L + M * (Cw - 1);
        S = denom !== 0 ? (Cw * M * L) / denom : 0;
        Cv = (S - L !== 0) ? (M - L) / (S - L) : 0;
      }
      else if (active.has('S') && active.has('M') && active.has('Cv')) {
        L = (1 - Cv !== 0) ? (M - S * Cv) / (1 - Cv) : 0;
        Cw = M !== 0 ? (S * Cv) / M : 0;
      }
      else if (active.has('S') && active.has('M') && active.has('Cw')) {
        Cv = S !== 0 ? (Cw * M) / S : 0;
        L = (1 - Cv !== 0) ? (M - S * Cv) / (1 - Cv) : 0;
      }
      else if (active.has('L') && active.has('Cv') && active.has('Cw')) {
        S = (Cv / Cw - Cv !== 0) ? L * (1 - Cv) / (Cv / Cw - Cv) : 0;
        M = L * (1 - Cv) + S * Cv;
      }
      else if (active.has('S') && active.has('Cv') && active.has('Cw')) {
        M = Cw !== 0 ? (S * Cv) / Cw : 0;
        L = (1 - Cv !== 0) ? (M - S * Cv) / (1 - Cv) : 0;
      }
      else if (active.has('M') && active.has('Cv') && active.has('Cw')) {
        S = Cv !== 0 ? (Cw * M) / Cv : 0;
        L = (1 - Cv !== 0) ? (M - S * Cv) / (1 - Cv) : 0;
      }

      // Clamp values
      Cv = Math.max(0, Math.min(Cv, 0.8));
      Cw = Math.max(0, Math.min(Cw, 0.95));

      // Update the UI for calculated properties
      if (!active.has('L')) { setVal('sg_l', L); setVal('rho_l', L * 1000); }
      if (!active.has('S')) { setVal('sg_s', S); setVal('rho_s', S * 1000); }
      if (!active.has('M')) { setVal('sg_m', M); setVal('rho_m', M * 1000); }
      if (!active.has('Cv')) setVal('slurry_cv', Cv);
      if (!active.has('Cw')) setVal('slurry_cw', Cw);
    } catch (e) {
      console.warn('Slurry calculation error:', e);
    }
  }

  // Handle Checkbox Toggles: keep exactly 3 checked
  let checkedOrder = [...slurryCheckboxes].filter(cb => cb.checked);
  
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
      
      // Update readonly state based on checked param
      const active = new Set(checkedOrder.map(c => c.dataset.param));
      
      const elementsToToggle = [
        ['rho_l', 'L'], ['sg_l', 'L'],
        ['rho_s', 'S'], ['sg_s', 'S'],
        ['rho_m', 'M'], ['sg_m', 'M'],
        ['slurry_cv', 'Cv'], ['slurry_cw', 'Cw']
      ];
      
      elementsToToggle.forEach(([elemId, param]) => {
        const el = document.getElementById(elemId);
        if (el) el.readOnly = !active.has(param);
      });
      
      updateSlurryCalculator();
    });
  });

  // Initial update
  if (slurryCheckboxes.length > 0) {
    try {
      updateSlurryCalculator();
    } catch (err) {
      console.warn('Slurry init notice:', err);
    }
  }


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
        const params = selected.map(id => `ids=${id}`).join('&');
        compareLink.href = `/pump-comparison?${params}&liquid=${liquid}&q_duty=${qDuty}&h_duty=${hDuty}`;
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

document.addEventListener('DOMContentLoaded', () => {
  const freqRadio = document.querySelector('input[name="motor_freq_hz"]:checked');
  const freq = freqRadio ? parseInt(freqRadio.value, 10) : 50;
  updatePolesLabels(freq);
  onMotorSelectionModeChange();
  onOperationModeChange();
  onFixedSpeedModeChange();
  onVsdTrimModeChange();
});

