/**
 * pump_comparison.js — Side-by-side pump comparison charts & detailed shortlisted list management.
 */

document.addEventListener('DOMContentLoaded', () => {

  let compData = [];
  let activeChart = 'hq';
  let activePlottedIds = Array.isArray(INITIAL_IDS) ? [...INITIAL_IDS] : [];

  const COLORS = ['#58a6ff', '#3fb950', '#f0c040', '#f85149', '#bc8cff', '#39d3c0'];

  // ── Pagination & View State for Detailed Shortlist ──────────────────────────
  let currentPage = 1;
  let pageSize = 25;
  let currentRatingFilter = 'all';
  let currentViewMode = 'cards'; // 'cards' | 'table'

  /* ── Fetch comparison data for explicit IDs ────────────────────── */
  async function fetchComparisonForIds(ids) {
    activePlottedIds = Array.isArray(ids) ? ids.map(Number) : [];
    updatePlottedUI();

    if (activePlottedIds.length === 0) {
      compData = [];
      clearCharts();
      return;
    }

    if (activePlottedIds.length > 4) {
      alert('Maximum 4 pumps can be compared on the curves simultaneously. Please uncheck one before adding another.');
      return;
    }

    const liquid = document.getElementById('compLiquid')?.value || 'water';
    const loading = document.getElementById('compLoading');
    if (loading) loading.style.display = 'block';

    const params = activePlottedIds.map(id => `ids=${id}`).join('&') + `&liquid=${liquid}`;
    try {
      const res = await fetch(`/papi/compare-pumps?${params}`);
      compData = await res.json();
      renderAll();
    } catch (e) {
      console.error('Error fetching comparison curves:', e);
    } finally {
      if (loading) loading.style.display = 'none';
    }
  }

  /* ── Update Plotted Status on Cards, Table Rows, and Header Badges ─ */
  function updatePlottedUI() {
    const countEl = document.getElementById('plottedCount');
    if (countEl) countEl.textContent = activePlottedIds.length;

    // Synchronize all checkboxes across cards and table
    document.querySelectorAll('.comp-plot-cb').forEach(cb => {
      const id = Number(cb.value);
      const isChecked = activePlottedIds.includes(id);
      cb.checked = isChecked;

      // Update card visual state
      const card = document.getElementById(`det-card-${id}`);
      if (card) {
        card.dataset.plotted = isChecked ? 'true' : 'false';
        if (isChecked) {
          card.classList.add('border-[#58a6ff]', 'bg-[#1c2330]/80');
          card.classList.remove('border-[#30363d]', 'bg-[#161b22]/90');
        } else {
          card.classList.remove('border-[#58a6ff]', 'bg-[#1c2330]/80');
          card.classList.add('border-[#30363d]', 'bg-[#161b22]/90');
        }
      }

      // Update table row visual state
      const row = document.getElementById(`det-row-${id}`);
      if (row) {
        row.dataset.plotted = isChecked ? 'true' : 'false';
        if (isChecked) {
          row.classList.add('bg-[#1c2330]/50');
        } else {
          row.classList.remove('bg-[#1c2330]/50');
        }
      }
    });

    // Synchronize fallback multi-select
    const selector = document.getElementById('pumpSelector');
    if (selector) {
      [...selector.options].forEach(opt => {
        opt.selected = activePlottedIds.includes(Number(opt.value));
      });
    }
  }

  /* ── Toggle pump plotting from checkbox ───────────────────────── */
  window.togglePumpPlot = function(pumpId, isChecked) {
    pumpId = Number(pumpId);
    if (isChecked) {
      if (activePlottedIds.length >= 4) {
        alert('Maximum 4 pumps can be overlaid on the curves simultaneously. Please uncheck a pump first.');
        const cb = document.getElementById(`cb-plot-${pumpId}`);
        if (cb) cb.checked = false;
        return;
      }
      if (!activePlottedIds.includes(pumpId)) {
        activePlottedIds.push(pumpId);
      }
    } else {
      activePlottedIds = activePlottedIds.filter(id => id !== pumpId);
    }
    fetchComparisonForIds(activePlottedIds);
  };

  /* ── Plot top N shortlisted pumps ────────────────────────────── */
  window.plotTopShortlisted = function(n = 3) {
    const cards = document.querySelectorAll('.detailed-pump-card');
    const ids = [];
    for (let i = 0; i < cards.length && ids.length < n; i++) {
      const id = Number(cards[i].dataset.id);
      if (id && !isNaN(id)) ids.push(id);
    }
    fetchComparisonForIds(ids);
  };

  /* ── Clear chart plotted selection ───────────────────────────── */
  window.clearPlotSelection = function() {
    fetchComparisonForIds([]);
  };

  /* ── Toggle Comparison Settings Card ─────────────────────────── */
  window.toggleCompSettings = function() {
    const card = document.getElementById('compSettingsCard');
    const chevron = document.getElementById('compSettingsChevron');
    if (!card) return;
    if (card.style.display === 'none') {
      card.style.display = 'block';
      if (chevron) chevron.style.transform = 'rotate(180deg)';
    } else {
      card.style.display = 'none';
      if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
  };

  /* ── Switch Shortlist View (Cards vs Table) ───────────────────── */
  window.switchShortlistView = function(mode) {
    currentViewMode = mode;
    const cardsContainer = document.getElementById('detailedCardsContainer');
    const tableContainer = document.getElementById('detailedTableContainer');
    const btnCards = document.getElementById('btnViewCards');
    const btnTable = document.getElementById('btnViewTable');

    if (mode === 'cards') {
      if (cardsContainer) cardsContainer.style.display = 'block';
      if (tableContainer) tableContainer.style.display = 'none';
      if (btnCards) {
        btnCards.classList.add('bg-[#21262d]', 'text-[#58a6ff]');
        btnCards.classList.remove('text-[#8b949e]');
      }
      if (btnTable) {
        btnTable.classList.remove('bg-[#21262d]', 'text-[#58a6ff]');
        btnTable.classList.add('text-[#8b949e]');
      }
    } else {
      if (cardsContainer) cardsContainer.style.display = 'none';
      if (tableContainer) tableContainer.style.display = 'block';
      if (btnTable) {
        btnTable.classList.add('bg-[#21262d]', 'text-[#58a6ff]');
        btnTable.classList.remove('text-[#8b949e]');
      }
      if (btnCards) {
        btnCards.classList.remove('bg-[#21262d]', 'text-[#58a6ff]');
        btnCards.classList.add('text-[#8b949e]');
      }
    }
    paginateDetailedList();
  };

  /* ── Filter & Search Detailed List ───────────────────────────── */
  window.applyCompRatingFilter = function(cat, btn) {
    currentRatingFilter = cat;
    document.querySelectorAll('.comp-rf-pill').forEach(b => {
      b.classList.remove('bg-[#21262d]', 'text-[#58a6ff]');
      b.classList.add('text-[#8b949e]');
    });
    if (btn) {
      btn.classList.add('bg-[#21262d]', 'text-[#58a6ff]');
      btn.classList.remove('text-[#8b949e]');
    }
    currentPage = 1;
    filterDetailedList();
  };

  window.filterDetailedList = function() {
    const query = (document.getElementById('compDetailedSearch')?.value || '').toLowerCase().trim();
    const cards = document.querySelectorAll('.detailed-pump-card');
    const rows  = document.querySelectorAll('#detailedTableBody tr');

    let visibleCards = [];
    let visibleRows = [];

    // Filter cards
    cards.forEach(card => {
      const name = card.dataset.name || '';
      const mfr = card.dataset.mfr || '';
      const size = card.dataset.size || '';
      const cat = card.dataset.ratingCat || '';
      const isPlotted = card.dataset.plotted === 'true';

      const matchQ = !query || name.includes(query) || mfr.includes(query) || size.includes(query);
      let matchCat = true;
      if (currentRatingFilter === 'plotted') {
        matchCat = isPlotted;
      } else if (currentRatingFilter !== 'all') {
        matchCat = (cat === currentRatingFilter);
      }

      if (matchQ && matchCat) {
        visibleCards.push(card);
      } else {
        card.style.display = 'none';
      }
    });

    // Filter table rows
    rows.forEach(row => {
      const name = row.dataset.name || '';
      const mfr = row.dataset.mfr || '';
      const size = row.dataset.size || '';
      const cat = row.dataset.ratingCat || '';
      const isPlotted = row.dataset.plotted === 'true';

      const matchQ = !query || name.includes(query) || mfr.includes(query) || size.includes(query);
      let matchCat = true;
      if (currentRatingFilter === 'plotted') {
        matchCat = isPlotted;
      } else if (currentRatingFilter !== 'all') {
        matchCat = (cat === currentRatingFilter);
      }

      if (matchQ && matchCat) {
        visibleRows.push(row);
      } else {
        row.style.display = 'none';
      }
    });

    const totalFiltered = visibleCards.length;
    const countDisplay = document.getElementById('detailedCountDisplay');
    if (countDisplay) countDisplay.textContent = totalFiltered;
    const countFiltered = document.getElementById('filteredTotalCount');
    if (countFiltered) countFiltered.textContent = totalFiltered;

    paginateItems(visibleCards, visibleRows);
  };

  /* ── Sort Detailed List ──────────────────────────────────────── */
  window.sortDetailedList = function(sortBy) {
    const cardsContainer = document.getElementById('detailedCardsContainer');
    const tableBody = document.getElementById('detailedTableBody');
    if (!cardsContainer || !tableBody) return;

    const cards = [...cardsContainer.querySelectorAll('.detailed-pump-card')];
    const rows  = [...tableBody.querySelectorAll('tr')];

    const comparator = (a, b) => {
      let valA, valB;
      switch (sortBy) {
        case 'rating_desc':
          return (Number(b.dataset.rating) || 0) - (Number(a.dataset.rating) || 0);
        case 'eff_desc':
          return (Number(b.dataset.eff) || 0) - (Number(a.dataset.eff) || 0);
        case 'power_asc':
          return (Number(a.dataset.power) || 0) - (Number(b.dataset.power) || 0);
        case 'head_desc':
          return (Number(b.dataset.head) || 0) - (Number(a.dataset.head) || 0);
        case 'name_asc':
          return (a.dataset.name || '').localeCompare(b.dataset.name || '');
        default:
          return 0;
      }
    };

    cards.sort(comparator).forEach(card => cardsContainer.appendChild(card));
    rows.sort(comparator).forEach(row => tableBody.appendChild(row));

    currentPage = 1;
    filterDetailedList();
  };

  /* ── Pagination Logic ────────────────────────────────────────── */
  window.changePageSize = function(size) {
    pageSize = (size === 'all') ? Infinity : Number(size);
    currentPage = 1;
    filterDetailedList();
  };

  window.goToPage = function(pageNum) {
    currentPage = pageNum;
    filterDetailedList();
  };

  function paginateItems(visibleCards, visibleRows) {
    const total = visibleCards.length;
    const start = (currentPage - 1) * pageSize;
    const end = (pageSize === Infinity) ? total : Math.min(start + pageSize, total);

    visibleCards.forEach((card, idx) => {
      card.style.display = (idx >= start && idx < end) ? '' : 'none';
    });

    visibleRows.forEach((row, idx) => {
      row.style.display = (idx >= start && idx < end) ? '' : 'none';
    });

    const showingCount = document.getElementById('pageShowingCount');
    if (showingCount) {
      showingCount.textContent = total > 0 ? (end - start) : 0;
    }

    renderPaginationControls(total);
  }

  function renderPaginationControls(total) {
    const container = document.getElementById('paginationControls');
    if (!container) return;

    if (pageSize === Infinity || total <= pageSize) {
      container.innerHTML = '';
      return;
    }

    const totalPages = Math.ceil(total / pageSize);
    let html = '';

    // Prev
    html += `<button type="button" onclick="goToPage(${Math.max(1, currentPage - 1)})"
                     class="px-2 py-1 rounded bg-[#161b22] border border-[#30363d] text-xs hover:text-white ${currentPage === 1 ? 'opacity-40 pointer-events-none' : ''}">
              &laquo;
             </button>`;

    // Pages
    for (let p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || (p >= currentPage - 1 && p <= currentPage + 1)) {
        html += `<button type="button" onclick="goToPage(${p})"
                         class="px-2.5 py-1 rounded text-xs font-mono font-semibold ${p === currentPage ? 'bg-[#58a6ff] text-[#0d1117]' : 'bg-[#161b22] border border-[#30363d] text-[#8b949e] hover:text-white'}">
                  ${p}
                 </button>`;
      } else if (p === currentPage - 2 || p === currentPage + 2) {
        html += `<span class="px-1 text-[#8b949e]">…</span>`;
      }
    }

    // Next
    html += `<button type="button" onclick="goToPage(${Math.min(totalPages, currentPage + 1)})"
                     class="px-2 py-1 rounded bg-[#161b22] border border-[#30363d] text-xs hover:text-white ${currentPage === totalPages ? 'opacity-40 pointer-events-none' : ''}">
              &raquo;
             </button>`;

    container.innerHTML = html;
  }

  /* ── Clear charts on empty selection ───────────────────────────── */
  function clearCharts() {
    ['chartComp', 'chartAll_hq', 'chartAll_eff', 'chartAll_power', 'chartAll_npsh'].forEach(id => {
      const el = document.getElementById(id);
      if (el) Plotly.purge(el);
    });
  }

  /* ── Build traces for each curve type ──────────────────────────── */
  function buildTraces(curveType) {
    const traces = [];
    const q_duty = parseFloat(document.getElementById('compQDuty')?.value) || (typeof INITIAL_Q_DUTY !== 'undefined' ? INITIAL_Q_DUTY : null);
    const h_duty = parseFloat(document.getElementById('compHDuty')?.value) || (typeof INITIAL_H_DUTY !== 'undefined' ? INITIAL_H_DUTY : null);

    compData.forEach((item, i) => {
      const c = COLORS[i % COLORS.length];
      const name = item.pump.name;
      const curves = item.curves;

      let y, yLabel, yTitle;
      switch (curveType) {
        case 'hq':    y = curves.h;     yLabel = 'H'; yTitle = 'Head H (m)'; break;
        case 'eff':   y = curves.eta;   yLabel = 'η'; yTitle = 'Efficiency η (%)'; break;
        case 'power': y = curves.power; yLabel = 'P'; yTitle = 'Shaft Power P (kW)'; break;
        case 'npsh':  y = curves.npsh;  yLabel = 'NPSHr'; yTitle = 'NPSHr (m)'; break;
      }

      traces.push({
        type: 'scatter', mode: 'lines',
        name: name,
        x: curves.q, y,
        line: { color: c, width: 2.5 },
        hovertemplate: `<b>${name}</b><br>Q: %{x:.1f} m³/h<br>${yLabel}: %{y:.2f}<extra></extra>`
      });

      // BEP marker for H-Q
      if (curveType === 'hq' && item.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `${name} BEP`,
          x: [item.bep.q], y: [item.bep.h],
          marker: { size: 9, color: c, symbol: 'star', line: { color: '#fff', width: 1 } },
          showlegend: false,
          hovertemplate: `<b>${name} BEP</b><br>Q: ${item.bep.q} m³/h<br>H: ${item.bep.h} m<extra></extra>`
        });
      }
    });

    // Duty point on H-Q
    if (curveType === 'hq' && q_duty && h_duty) {
      traces.push({
        type: 'scatter', mode: 'markers',
        name: 'Duty Point',
        x: [q_duty], y: [h_duty],
        marker: { size: 12, color: '#fff', symbol: 'cross', line: { color: '#ff0000', width: 2.5 } },
        hovertemplate: `<b>Duty Point</b><br>Q: ${q_duty}<br>H: ${h_duty}<extra></extra>`
      });
    }

    return traces;
  }

  function getYTitle(curveType) {
    return { hq: 'Head H (m)', eff: 'Efficiency η (%)', power: 'Shaft Power P (kW)', npsh: 'NPSHr (m)' }[curveType] || '';
  }

  function makeCompLayout(yTitle, extra = {}) {
    return Object.assign({}, PLOTLY_LAYOUT_BASE, {
      xaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.xaxis, { title: 'Flow Q (m³/h)' }),
      yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: yTitle, rangemode: 'tozero' }),
      legend: Object.assign({}, PLOTLY_LAYOUT_BASE.legend, { orientation: 'h', x: 0, y: -0.15, xanchor: 'left', yanchor: 'top' })
    }, extra);
  }

  /* ── Render single chart ────────────────────────────────────────── */
  function renderSingleChart(curveType) {
    const traces = buildTraces(curveType);
    const layout = makeCompLayout(getYTitle(curveType));
    Plotly.react('chartComp', traces, layout, PLOTLY_CONFIG);
  }

  /* ── Render all 4 charts ────────────────────────────────────────── */
  function renderAllCharts() {
    ['hq', 'eff', 'power', 'npsh'].forEach(ct => {
      const traces = buildTraces(ct);
      const layout = makeCompLayout(getYTitle(ct));
      Plotly.react(`chartAll_${ct}`, traces, layout, PLOTLY_CONFIG);
    });
  }

  /* ── Orchestrate renders ────────────────────────────────────────── */
  function renderAll() {
    const singlePanel = document.getElementById('singleChartPanel');
    const allPanel    = document.getElementById('allChartPanel');

    if (activeChart === 'all') {
      if (singlePanel) singlePanel.style.display = 'none';
      if (allPanel) allPanel.style.display = '';
      renderAllCharts();
    } else {
      if (singlePanel) singlePanel.style.display = '';
      if (allPanel) allPanel.style.display = 'none';
      renderSingleChart(activeChart);
    }
  }

  /* ── Chart button event listeners ───────────────────────────────── */
  document.querySelectorAll('.comp-chart-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.comp-chart-btn').forEach(b => {
        b.classList.remove('comp-active');
        b.style.background = 'transparent';
        b.style.color = '#8b949e';
      });
      btn.classList.add('comp-active');
      btn.style.background = 'rgba(88,166,255,0.15)';
      btn.style.color = '#58a6ff';
      activeChart = btn.dataset.chart;
      if (compData.length) renderAll();
    });
  });

  const btnCompare = document.getElementById('btnCompare');
  if (btnCompare) {
    btnCompare.addEventListener('click', () => {
      const selector = document.getElementById('pumpSelector');
      if (selector) {
        const selected = [...selector.selectedOptions].map(o => Number(o.value));
        fetchComparisonForIds(selected);
      }
    });
  }

  /* ── Initial Load ───────────────────────────────────────────────── */
  filterDetailedList();

  if (activePlottedIds && activePlottedIds.length > 0) {
    fetchComparisonForIds(activePlottedIds);
  }
});
