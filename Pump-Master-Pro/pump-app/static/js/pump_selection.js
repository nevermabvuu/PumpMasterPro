/**
 * pump_selection.js — Liquid parameter switching, pump comparison logic, and inline SVG sparklines
 */

document.addEventListener('DOMContentLoaded', () => {

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
  
  // Helper to safely parse floats
  const getVal = (id) => parseFloat(document.getElementById(id).value) || 0;
  const setVal = (id, val) => {
    const el = document.getElementById(id);
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
    // Collect active (checked) parameters
    const active = new Set([...slurryCheckboxes].filter(cb => cb.checked).map(cb => cb.dataset.param));
    
    // Read raw inputs
    let L = getVal('sg_l');
    let S = getVal('sg_s');
    let M = getVal('sg_m');
    let Cv = getVal('slurry_cv');
    let Cw = getVal('slurry_cw');

    if (active.size !== 3) return; // Need exactly 3 knowns

    // Solver logic for all 10 combinations of 3 variables
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
      
      document.getElementById('rho_l').readOnly = !active.has('L');
      document.getElementById('sg_l').readOnly = !active.has('L');
      document.getElementById('rho_s').readOnly = !active.has('S');
      document.getElementById('sg_s').readOnly = !active.has('S');
      document.getElementById('rho_m').readOnly = !active.has('M');
      document.getElementById('sg_m').readOnly = !active.has('M');
      document.getElementById('slurry_cv').readOnly = !active.has('Cv');
      document.getElementById('slurry_cw').readOnly = !active.has('Cw');
      
      updateSlurryCalculator();
    });
  });

  // Initial update
  if (slurryCheckboxes.length > 0) {
    updateSlurryCalculator();
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
      if (selected.length >= 2) {
        const liquid = document.getElementById('liquidSel')?.value || 'water';
        const qDuty  = document.querySelector('[name=q_duty]')?.value || '';
        const hDuty  = document.querySelector('[name=h_duty]')?.value || '';
        const params = selected.map(id => `ids=${id}`).join('&');
        compareLink.href = `/pump-comparison?${params}&liquid=${liquid}&q_duty=${qDuty}&h_duty=${hDuty}`;
        compareLink.classList.remove('disabled', 'pointer-events-none', 'opacity-50');
        compareLink.style.background = 'rgba(57,211,192,0.1)';
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
  const sparkContainers = document.querySelectorAll('.sparkline-container');
  sparkContainers.forEach(container => {
    try {
      const dataStr = container.getAttribute('data-chart');
      if (!dataStr) return;
      const chartData = JSON.parse(dataStr);
      renderSparkline(container, chartData);
    } catch (e) {
      console.error('Error rendering sparkline:', e);
      container.innerHTML = '<div class="text-xs text-red-500">Error rendering chart</div>';
    }
  });

});

// ── Filter Panel Toggle ──────────────────────────────────────────────────────
// Beginners Note: Toggles the advanced filter panel open/closed
function toggleFilterPanel() {
  const panel = document.getElementById('filterPanel');
  const chevron = document.getElementById('filterChevron');
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    chevron.style.transform = 'rotate(180deg)';
  } else {
    panel.style.display = 'none';
    chevron.style.transform = 'rotate(0deg)';
  }
}

// ── Sorting Logic ────────────────────────────────────────────────────────────
// Beginners Note: Updates the hidden sort input and resubmits the form
function setSortAndSubmit(sortBy) {
  const input = document.getElementById('sortByInput');
  if (input) {
    input.value = sortBy;
    document.getElementById('selectionForm').submit();
  }
}

// ── SVG Sparkline Renderer ───────────────────────────────────────────────────
// Beginners Note: Draws a simple SVG H-Q envelope without heavy charting libraries
function renderSparkline(container, data) {
  const width = 180;
  const height = 70;
  const padding = { top: 5, right: 5, bottom: 5, left: 5 };
  
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  
  const maxQ = data.q_range[1] || 100;
  const maxH = data.h_range[1] || 100;
  
  // Coordinate mapping functions
  const x = val => padding.left + (val / maxQ) * innerWidth;
  const y = val => padding.top + innerHeight - (val / maxH) * innerHeight;

  // Path generator
  const createPath = (qArr, hArr) => {
    if (!qArr || !hArr || qArr.length === 0 || qArr.length !== hArr.length) return '';
    let d = `M ${x(qArr[0])} ${y(hArr[0])}`;
    for (let i = 1; i < qArr.length; i++) {
      d += ` L ${x(qArr[i])} ${y(hArr[i])}`;
    }
    return d;
  };

  // Build SVG
  let svg = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`;

  // Draw envelope fill area (between max and min curves)
  if (data.q_max && data.q_min && data.q_min.length > 0) {
    let dArea = createPath(data.q_max, data.h_max);
    // Add min curve in reverse order to close the path
    for (let i = data.q_min.length - 1; i >= 0; i--) {
      dArea += ` L ${x(data.q_min[i])} ${y(data.h_min[i])}`;
    }
    dArea += ' Z';
    svg += `<path d="${dArea}" fill="rgba(88,166,255,0.08)" />`;
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
    svg += `<path d="${createPath(data.q_trim, data.h_trim)}" fill="none" stroke="#3fb950" stroke-width="1" stroke-dasharray="1,2" />`;
  }

  // Draw Duty Point (red cross)
  const dx = x(data.q_duty);
  const dy = y(data.h_duty);
  const crossSize = 3;
  svg += `<line x1="${dx - crossSize}" y1="${dy - crossSize}" x2="${dx + crossSize}" y2="${dy + crossSize}" stroke="#f85149" stroke-width="1.5" />`;
  svg += `<line x1="${dx - crossSize}" y1="${dy + crossSize}" x2="${dx + crossSize}" y2="${dy - crossSize}" stroke="#f85149" stroke-width="1.5" />`;

  svg += `</svg>`;
  container.innerHTML = svg;
}
