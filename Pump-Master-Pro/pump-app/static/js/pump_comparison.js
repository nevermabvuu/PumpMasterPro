/**
 * pump_comparison.js — Side-by-side pump comparison charts
 */

document.addEventListener('DOMContentLoaded', () => {

  let compData = [];
  let activeChart = 'hq';

  const COLORS = ['#58a6ff', '#3fb950', '#f0c040', '#f85149', '#bc8cff', '#39d3c0'];

  /* ── Fetch comparison data ──────────────────────────────────────── */
  async function fetchComparison() {
    const selector = document.getElementById('pumpSelector');
    const selected = [...selector.selectedOptions].map(o => o.value);
    if (selected.length === 0) {
      compData = [];
      clearCharts();
      return;
    }
    if (selected.length > 4) {
      alert('Please select at most 4 pumps for comparison.');
      return;
    }

    const liquid  = document.getElementById('compLiquid').value;
    const loading = document.getElementById('compLoading');
    loading.style.display = 'block';

    const params = selected.map(id => `ids=${id}`).join('&') + `&liquid=${liquid}`;
    try {
      const res = await fetch(`/papi/compare-pumps?${params}`);
      compData = await res.json();
      renderAll();
      buildBepTable();
    } catch (e) {
      console.error(e);
    } finally {
      loading.style.display = 'none';
    }
  }

  /* ── Clear charts on empty selection ───────────────────────────── */
  function clearCharts() {
    ['chartComp', 'chartAll_hq', 'chartAll_eff', 'chartAll_power', 'chartAll_npsh'].forEach(id => {
      const el = document.getElementById(id);
      if (el) Plotly.purge(el);
    });
    document.getElementById('compTable').style.display = 'none';
  }

  /* ── Build traces for each curve type ──────────────────────────── */
  function buildTraces(curveType) {
    const traces = [];
    const q_duty = parseFloat(document.getElementById('compQDuty').value) || null;
    const h_duty = parseFloat(document.getElementById('compHDuty').value) || null;

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
        hovertemplate: `${name}<br>Q=%{x:.1f}<br>${yLabel}=%{y:.2f}<extra></extra>`
      });

      // BEP marker for H-Q
      if (curveType === 'hq' && item.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `${name} BEP`,
          x: [item.bep.q], y: [item.bep.h],
          marker: { size: 9, color: c, symbol: 'star', line: { color: '#fff', width: 1 } },
          showlegend: false,
          hovertemplate: `${name} BEP<br>Q=${item.bep.q}<br>H=${item.bep.h}<extra></extra>`
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
        hovertemplate: `Duty Q=${q_duty} H=${h_duty}<extra></extra>`
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
      legend: Object.assign({}, PLOTLY_LAYOUT_BASE.legend, { orientation: 'h', x: 0, y: -0.12, xanchor: 'left', yanchor: 'top' })
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

  /* ── BEP table ──────────────────────────────────────────────────── */
  function buildBepTable() {
    const tbody = document.getElementById('bepTableBody');
    const table = document.getElementById('compTable');
    if (!tbody || !compData.length) { if (table) table.style.display = 'none'; return; }

    tbody.innerHTML = compData.map((item, i) => {
      const c = COLORS[i % COLORS.length];
      const bep = item.bep;
      const p = item.pump;
      return `<tr>
        <td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c};margin-right:8px;"></span><strong>${p.name}</strong><div class="text-muted small">${p.manufacturer} · ${p.size}</div></td>
        <td class="text-center">${p.speed_rpm}</td>
        <td class="text-center">${p.impeller_dia_mm}</td>
        <td class="text-center fw-semibold">${bep.q}</td>
        <td class="text-center">${bep.h}</td>
        <td class="text-center text-warning fw-semibold">${bep.eta}%</td>
        <td class="text-center">${bep.power}</td>
      </tr>`;
    }).join('');
    table.style.display = '';
  }

  /* ── Orchestrate renders ────────────────────────────────────────── */
  function renderAll() {
    const singlePanel = document.getElementById('singleChartPanel');
    const allPanel    = document.getElementById('allChartPanel');

    if (activeChart === 'all') {
      singlePanel.style.display = 'none';
      allPanel.style.display    = '';
      renderAllCharts();
    } else {
      singlePanel.style.display = '';
      allPanel.style.display    = 'none';
      renderSingleChart(activeChart);
    }
  }

  /* ── Event listeners ────────────────────────────────────────────── */
  document.getElementById('btnCompare').addEventListener('click', fetchComparison);

  document.querySelectorAll('.comp-chart-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.comp-chart-btn').forEach(b => {
        b.classList.remove('btn-primary', 'active');
        b.classList.add('btn-outline-secondary');
      });
      btn.classList.remove('btn-outline-secondary');
      btn.classList.add('btn-primary', 'active');
      activeChart = btn.dataset.chart;
      if (compData.length) renderAll();
    });
  });

  /* ── Auto-load if pump IDs were pre-selected ────────────────────── */
  if (typeof INITIAL_IDS !== 'undefined' && INITIAL_IDS.length > 0) {
    const sel = document.getElementById('pumpSelector');
    [...sel.options].forEach(opt => {
      opt.selected = INITIAL_IDS.includes(parseInt(opt.value));
    });
    if (typeof INITIAL_Q_DUTY !== 'undefined' && INITIAL_Q_DUTY) {
      document.getElementById('compQDuty').value = INITIAL_Q_DUTY;
    }
    if (typeof INITIAL_H_DUTY !== 'undefined' && INITIAL_H_DUTY) {
      document.getElementById('compHDuty').value = INITIAL_H_DUTY;
    }
    fetchComparison();
  }
});
