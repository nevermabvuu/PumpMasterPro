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

  // ── Auto-calculate slurry density ──────────────────────────────────────────
  // Beginners Note: Calculates effective slurry density from volume concentration and solid density
  function calcSlurryDensity() {
    const cv       = parseFloat(document.querySelector('[name=slurry_cv]')?.value || 0);
    const rhoSolid = parseFloat(document.querySelector('[name=rho_solid]')?.value || 2650);
    const rhoSlurry = 1000 * (1 - cv) + rhoSolid * cv;
    const el = document.getElementById('rhoSlurryCalc');
    if (el) el.value = rhoSlurry.toFixed(0);
  }

  document.querySelector('[name=slurry_cv]')?.addEventListener('input', calcSlurryDensity);
  document.querySelector('[name=rho_solid]')?.addEventListener('input', calcSlurryDensity);
  calcSlurryDensity();

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
