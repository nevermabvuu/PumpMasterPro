/**
 * pump_curves.js — Warman-style pump curve rendering with Plotly
 * Covers: Warman performance map, standalone curves, isoline overlay, comparison helpers
 */

/* ── Plotly dark theme ────────────────────────────────────────────────────── */
const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: '#0d1117',
  font: { color: '#8b949e', size: 11, family: 'system-ui, sans-serif' },
  xaxis: {
    gridcolor: '#21262d', zerolinecolor: '#30363d',
    tickfont: { color: '#8b949e' }, titlefont: { color: '#c9d1d9', size: 12 }
  },
  yaxis: {
    gridcolor: '#21262d', zerolinecolor: '#30363d',
    tickfont: { color: '#8b949e' }, titlefont: { color: '#c9d1d9', size: 12 }
  },
  margin: { l: 58, r: 24, t: 28, b: 52 },
  showlegend: true,
  legend: {
    bgcolor: 'rgba(22,27,34,0.88)', bordercolor: '#30363d', borderwidth: 1,
    font: { color: '#c9d1d9', size: 10 }, x: 0.01, y: 0.99, xanchor: 'left', yanchor: 'top'
  },
  hovermode: 'closest',
  hoverlabel: { bgcolor: '#161b22', bordercolor: '#58a6ff', font: { color: '#e6edf3', size: 11 } },
};

const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: true,
  editable: true,
  edits: {
    annotationPosition: true,
    annotationText: false,
    annotationTail: false,
    axisTitleText: false,
    colorbarPosition: false,
    colorbarTitleText: false,
    legendPosition: false,
    titleText: false,
    shapePosition: false
  },
  modeBarButtonsToRemove: ['select2d', 'lasso2d'],
  displaylogo: false,
  toImageButtonOptions: { format: 'png', width: 1400, height: 800 }
};

/* ── Diameter family colour palette ──────────────────────────────────────── */
// Blues for H-Q curves (darker = larger diameter)
const DIA_BLUES = ['#1c6fbf', '#2a85d4', '#3fa0e8', '#58b8ff', '#82cdff', '#b3e0ff'];
const PUMP_COLORS = ['#58a6ff', '#3fb950', '#f0c040', '#f85149', '#bc8cff', '#39d3c0'];

// Efficiency isoline palette — warm yellows → greens
function isoColor(eta, etaMin, etaMax) {
  const t = etaMax > etaMin ? (eta - etaMin) / (etaMax - etaMin) : 0.5;
  // lerp: yellow (#f0c040) → green (#3fb950)
  const r = Math.round(240 + t * (63 - 240));
  const g = Math.round(192 + t * (185 - 192));
  const b = Math.round(64 + t * (80 - 64));
  return `rgb(${r},${g},${b})`;
}

/* ── Generic layout builder ──────────────────────────────────────────────── */
/**
 * Beginners Note: Applies custom scale settings (Min, Max, Major Intervals, Minor Intervals)
 * to a Plotly layout axis object (e.g. layout.xaxis or layout.yaxis).
 *
 * @param {Object} axisObj - The Plotly axis object to configure (e.g. layout.xaxis)
 * @param {string} axisName - The axis name identifier ('flow', 'head', 'eff', 'power', 'npsh')
 * @param {Object} [pumpObj] - Optional pump data dictionary containing axis scale values
 */
function applyAxisScaleSettings(axisObj, axisName, pumpObj = {}) {
  if (!axisObj) return axisObj;

  const getScaleVal = (prop, isInt = false) => {
    const fieldId = `axis_${axisName}_${prop}`;
    const domEl = document.getElementById(fieldId);
    if (domEl && domEl.value !== undefined && domEl.value.trim() !== '') {
      const parsed = isInt ? parseInt(domEl.value.trim(), 10) : parseFloat(domEl.value.trim());
      if (!isNaN(parsed)) return parsed;
    }
    const propKey = `axis_${axisName}_${prop}`;
    if (pumpObj && pumpObj[propKey] !== undefined && pumpObj[propKey] !== null) {
      const parsed = isInt ? parseInt(pumpObj[propKey], 10) : parseFloat(pumpObj[propKey]);
      if (!isNaN(parsed)) return parsed;
    }
    return null;
  };

  const minVal = getScaleVal('min');
  const maxVal = getScaleVal('max');
  const majorVal = getScaleVal('major');
  const minorVal = getScaleVal('minor', true);

  // 1. Min & Max Range Bounds
  if (minVal !== null || maxVal !== null) {
    const currentMin = minVal !== null ? minVal : (axisObj.range ? axisObj.range[0] : 0);
    const currentMax = maxVal !== null ? maxVal : (axisObj.range ? axisObj.range[1] : 100);
    axisObj.range = [currentMin, currentMax];
    axisObj.autorange = false;
  }

  // 2. Major Division Intervals / Ticks
  if (majorVal !== null && majorVal > 0) {
    if (minVal !== null && maxVal !== null && maxVal > minVal) {
      axisObj.dtick = (maxVal - minVal) / majorVal;
      axisObj.tickmode = 'linear';
    } else {
      axisObj.nticks = Math.round(majorVal) + 1;
    }
  }

  // 3. Minor Subticks
  if (minorVal !== null && minorVal > 0) {
    axisObj.minor = {
      nticks: minorVal + 1,
      showgrid: true,
      gridcolor: '#21262d',
      gridwidth: 1,
      ticks: 'inside',
      ticklen: 4,
      tickcolor: '#30363d'
    };
  }

  return axisObj;
}

function makeLayout(xTitle, yTitle, extra = {}, pumpObj = {}) {
  const layout = Object.assign({}, PLOTLY_LAYOUT_BASE, {
    xaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.xaxis, { title: xTitle }),
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: yTitle }),
  }, extra);

  applyAxisScaleSettings(layout.xaxis, 'flow', pumpObj);

  const yLower = (typeof yTitle === 'string' ? yTitle : (yTitle.text || '')).toLowerCase();
  if (yLower.includes('head')) applyAxisScaleSettings(layout.yaxis, 'head', pumpObj);
  else if (yLower.includes('eff')) applyAxisScaleSettings(layout.yaxis, 'eff', pumpObj);
  else if (yLower.includes('power')) applyAxisScaleSettings(layout.yaxis, 'power', pumpObj);
  else if (yLower.includes('npsh')) applyAxisScaleSettings(layout.yaxis, 'npsh', pumpObj);

  if (layout.yaxis2) {
    const y2Lower = (typeof layout.yaxis2.title === 'string' ? layout.yaxis2.title : (layout.yaxis2.title?.text || '')).toLowerCase();
    if (y2Lower.includes('eff')) applyAxisScaleSettings(layout.yaxis2, 'eff', pumpObj);
    else if (y2Lower.includes('power')) applyAxisScaleSettings(layout.yaxis2, 'power', pumpObj);
    else if (y2Lower.includes('npsh')) applyAxisScaleSettings(layout.yaxis2, 'npsh', pumpObj);
  }

  return layout;
}

/* ── Duty point marker ───────────────────────────────────────────────────── */
function dutyTrace(q, h) {
  return {
    type: 'scatter', mode: 'markers', name: 'Duty Point',
    x: [q], y: [h],
    marker: { size: 14, color: '#ffffff', symbol: 'cross-open', line: { color: '#ff4444', width: 2.5 } },
    hovertemplate: `Duty<br>Q = ${q} m³/h<br>H = ${h} m<extra></extra>`,
  };
}

let customLabelPositions = {};

function _parseStyleField(fieldId, fallbackColor, fallbackWeight, fallbackStyle) {
  const val = document.getElementById(fieldId)?.value;
  if (val && val.includes(';') && val.includes(',')) {
    try {
      const parts = val.split(';');
      const color = parts[0].trim() || fallbackColor;
      const subparts = (parts[1] || '').split(',');
      const weight = parseFloat(subparts[0]) || fallbackWeight;
      const style = (subparts[1] || '').trim() || fallbackStyle;
      return { color, weight, style };
    } catch (e) {}
  }
  return { color: fallbackColor, weight: fallbackWeight, style: fallbackStyle };
}

function getGraphDisplayUnits() {
  const getStyleObj = (colorId, weightId, styleId, fieldId, defColor, defWeight, defStyle) => {
    const colorEl = document.getElementById(colorId);
    const weightEl = document.getElementById(weightId);
    const styleEl = document.getElementById(styleId);

    if (colorEl || weightEl || styleEl) {
      return {
        color: colorEl?.value || defColor,
        weight: parseFloat(weightEl?.value) || defWeight,
        style: styleEl?.value || defStyle
      };
    }
    return _parseStyleField(fieldId, defColor, defWeight, defStyle);
  };

  const headStyleObj = getStyleObj('clrHeadColor', 'selHeadWeight', 'selHeadStyle', 'head_curve_style_field', '#58a6ff', 2.0, 'solid');
  const effStyleObj = getStyleObj('clrEffColor', 'selEffWeight', 'selEffStyle', 'eff_curve_style_field', '#3fb950', 1.5, 'dot');
  const powStyleObj = getStyleObj('clrPowColor', 'selPowWeight', 'selPowStyle', 'power_curve_style_field', '#f85149', 1.5, 'longdash');
  const npshStyleObj = getStyleObj('clrNpshColor', 'selNpshWeight', 'selNpshStyle', 'npsh_curve_style_field', '#39d3c0', 1.5, 'dashdot');

  return {
    q: document.getElementById('preview-unit-q')?.value || 'm3h',
    h: document.getElementById('preview-unit-h')?.value || 'm',
    npsh: document.getElementById('preview-unit-npsh')?.value || 'm',
    pow: document.getElementById('preview-unit-pow')?.value || 'kw',
    legendMode: document.getElementById('selLegendMode')?.value || 'each',
    labelFormat: document.getElementById('selLabelFormat')?.value || 'percent',

    headColor: headStyleObj.color,
    headWeight: headStyleObj.weight,
    headStyle: headStyleObj.style,

    effColor: effStyleObj.color,
    effWeight: effStyleObj.weight,
    effStyle: effStyleObj.style,

    powColor: powStyleObj.color,
    powWeight: powStyleObj.weight,
    powStyle: powStyleObj.style,

    npshColor: npshStyleObj.color,
    npshWeight: npshStyleObj.weight,
    npshStyle: npshStyleObj.style
  };
}

function formatCurveLabel(val, ratio, isVarSpeed, labelFormat, baseDia, baseRpm) {
  const dVal = val ? Math.round(val) : (ratio ? Math.round((isVarSpeed ? (baseRpm || 1450) : (baseDia || 300)) * ratio) : 0);
  if (labelFormat === 'simple') {
    return isVarSpeed ? `${dVal} RPM` : `${dVal} mm`;
  }
  const pct = Math.round((ratio || 1.0) * 100);
  if (isVarSpeed) {
    return `${dVal} RPM (${pct}%)`;
  } else {
    return `Ø${dVal} mm (${pct}%)`;
  }
}

/* ── Annotation Move, Drag & Keyboard Helper ──────────────────────────────── */
// Beginner Note: This function makes all graph label badges (like Ø228 mm or 78%) interactive!
// It allows users to:
if (!window._globalLabelSelectionManager) {
  window._globalLabelSelectionManager = {
    activeState: null,
    select(state) {
      if (this.activeState && this.activeState !== state) {
        this.deselect();
      }
      this.activeState = state;
    },
    deselect() {
      if (!this.activeState) return;
      const st = this.activeState;
      this.activeState = null;
      try {
        st.showToast('');
        if (st.container) st.container.style.cursor = '';
        if (st.gElement) {
          const rect = st.gElement.querySelector('rect') || st.gElement.querySelector('path');
          if (rect) {
            if (st.gElement._origStroke !== undefined) rect.setAttribute('stroke', st.gElement._origStroke);
            if (st.gElement._origFill !== undefined) rect.setAttribute('fill', st.gElement._origFill);
            rect.setAttribute('stroke-width', '1.5');
          }
        }
      } catch (e) {}
    }
  };

  document.addEventListener('keydown', (e) => {
    const st = window._globalLabelSelectionManager.activeState;
    if (!st || !st.annObj) return;

    if (e.key === 'Escape') {
      window._globalLabelSelectionManager.deselect();
      return;
    }

    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
      e.preventDefault();

      const container = st.container;
      const selectedAnn = st.annObj;
      const fullLayout = container._fullLayout;
      const xDomain = (fullLayout?.xaxis?.range) ? Math.abs(fullLayout.xaxis.range[1] - fullLayout.xaxis.range[0]) : 100;
      const yDomain = (fullLayout?.yaxis?.range) ? Math.abs(fullLayout.yaxis.range[1] - fullLayout.yaxis.range[0]) : 50;

      const stepMult = e.shiftKey ? 5 : 1;
      const stepX = (xDomain / 200) * stepMult;
      const stepY = (yDomain / 200) * stepMult;

      let newX = selectedAnn.x;
      let newY = selectedAnn.y;

      if (e.key === 'ArrowLeft')  newX = Math.max(0, newX - stepX);
      if (e.key === 'ArrowRight') newX = newX + stepX;
      if (e.key === 'ArrowDown')  newY = Math.max(0, newY - stepY);
      if (e.key === 'ArrowUp')    newY = newY + stepY;

      newX = Math.round(newX * 100) / 100;
      newY = Math.round(newY * 100) / 100;

      selectedAnn.x = newX;
      selectedAnn.y = newY;
      selectedAnn.xanchor = 'center';
      selectedAnn.yanchor = 'middle';
      selectedAnn.xshift = 0;
      selectedAnn.yshift = 0;

      if (container && container.layout && Array.isArray(container.layout.annotations)) {
        const match = container.layout.annotations.find(a => (a.name && a.name === selectedAnn.name) || (a.text && a.text === selectedAnn.text));
        if (match) {
          match.x = newX;
          match.y = newY;
          match.xanchor = 'center';
          match.yanchor = 'middle';
          match.xshift = 0;
          match.yshift = 0;
        }
      }

      st.savePosition(selectedAnn.name, newX, newY);
      const liveAnnotations = container.layout?.annotations ? [...container.layout.annotations] : st.annotations;
      if (typeof Plotly.relayout === 'function') {
        Plotly.relayout(container, { annotations: liveAnnotations }).then(() => {
          if (typeof st.setupSvgEvents === 'function') st.setupSvgEvents();
        });
      }
    }
  });

  document.addEventListener('mousedown', (e) => {
    const isAnn = e.target.closest('.annotation-text, [class*="annotation"]');
    if (!isAnn && window._globalLabelSelectionManager.activeState) {
      window._globalLabelSelectionManager.deselect();
    }
  });
}

// Beginner Note: Enables dragging and keyboard arrow tuning for labels on any graph.
function makeAnnotationsDraggable(chartId, annotations, pumpId) {
  const container = document.getElementById(chartId);
  if (!container) return;

  if (container.layout) {
    container.layout.annotations = annotations;
  }

  // Cleanup old listeners if re-initializing
  if (container._annCleanups) {
    container._annCleanups.forEach(fn => { try { fn(); } catch(e){} });
  }
  container._annCleanups = [];

  function screenToDataCoords(e) {
    const fullLayout = container._fullLayout;
    if (!fullLayout || !fullLayout.xaxis || !fullLayout.yaxis) return null;
    const xaxis = fullLayout.xaxis;
    const yaxis = fullLayout.yaxis;
    const containerRect = container.getBoundingClientRect();

    const relX = e.clientX - containerRect.left - xaxis._offset;
    const relY = e.clientY - containerRect.top - yaxis._offset;

    const clampedRelX = Math.max(0, Math.min(xaxis._length || 9999, relX));
    const clampedRelY = Math.max(0, Math.min(yaxis._length || 9999, relY));

    const dataX = Math.max(0, Math.round(xaxis.p2c(clampedRelX) * 100) / 100);
    const dataY = Math.max(0, Math.round(yaxis.p2c(clampedRelY) * 100) / 100);
    return { x: dataX, y: dataY };
  }

  let toast = container.querySelector('._ann-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = '_ann-toast';
    toast.style.cssText = [
      'position:absolute', 'top:8px', 'left:50%', 'transform:translateX(-50%)',
      'background:rgba(22, 27, 34, 0.95)', 'color:#58a6ff', 'padding:6px 16px',
      'border:1px solid #30363d', 'border-radius:6px', 'font-size:12px', 'font-weight:600',
      'z-index:9999', 'pointer-events:none', 'display:none', 'white-space:nowrap',
      'box-shadow:0 4px 12px rgba(0,0,0,0.5)'
    ].join(';');
    container.style.position = 'relative';
    container.appendChild(toast);
  }

  const showToast = (msg) => { toast.innerHTML = msg; toast.style.display = msg ? 'block' : 'none'; };

  let saveTimer = null;
  function savePosition(annName, xVal, yVal) {
    if (!customLabelPositions[annName]) customLabelPositions[annName] = {};
    customLabelPositions[annName].x = xVal;
    customLabelPositions[annName].y = yVal;

    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (!pumpId) return;
      fetch(`/papi/pump/${pumpId}/label-pos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [annName]: { x: xVal, y: yVal } })
      }).catch(() => {});
    }, 150);
  }

  function selectAnnotation(ann, gElement) {
    if (!ann) return;
    if (window._globalLabelSelectionManager.activeState && window._globalLabelSelectionManager.activeState.annObj !== ann) {
      window._globalLabelSelectionManager.deselect();
    }

    const currentState = { chartId, container, annotations, annObj: ann, gElement, savePosition, showToast, setupSvgEvents };
    window._globalLabelSelectionManager.select(currentState);

    showToast(`<strong>"${ann.name}"</strong> selected &mdash; Drag mouse or use Arrow keys (&larr; &uarr; &rarr; &darr;) to adjust`);

    if (gElement) {
      const rect = gElement.querySelector('rect') || gElement.querySelector('path');
      if (rect) {
        if (!gElement._origStroke) gElement._origStroke = rect.getAttribute('stroke') || '';
        if (!gElement._origFill) gElement._origFill = rect.getAttribute('fill') || '';
        rect.setAttribute('stroke', '#58a6ff');
        rect.setAttribute('stroke-width', '2.5');
        rect.setAttribute('fill', 'rgba(88,166,255,0.35)');
      }
    }
  }

  function deselectAnnotation() {
    window._globalLabelSelectionManager.deselect();
  }

  function cleanStr(s) {
    return (s || '').replace(/<[^>]*>/g, '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  }

  const setupSvgEvents = () => {
    const annElements = container.querySelectorAll('.annotation-text, [class*="annotation"]');
    annElements.forEach(el => {
      let g = el.closest('g.annotation') || el.closest('g');
      if (!g || g._dragBound) return;

      const textEl = g.querySelector('text');
      if (!textEl) return;
      const rawText = textEl.textContent.trim();
      const cleanRaw = cleanStr(rawText);
      const numRaw = rawText.replace(/[^0-9.]/g, '');

      // Beginner Note: Match SVG DOM text elements with annotation data objects across HQ, Efficiency, Power, and NPSH graphs
      const candidates = annotations.filter(a => {
        if (!a || !a.name) return false;
        if (a.name === rawText) return true;
        const cleanName = cleanStr(a.name);
        const cleanText = cleanStr(a.text);
        if (cleanName === cleanRaw || cleanText === cleanRaw) return true;
        if (a.name.startsWith('eta_') || a.name.startsWith('pow_') || a.name.startsWith('npsh_') || a.name.startsWith('spd_') || a.name.startsWith('dia_')) {
          const numName = a.name.replace(/[^0-9.]/g, '');
          if (numRaw && numName && numRaw === numName) return true;
          const trimmedCleanText = cleanText.replace(/^(p|eta|npsh|h)/, '');
          const trimmedCleanRaw = cleanRaw.replace(/^(p|eta|npsh|h)/, '');
          if (trimmedCleanText && (trimmedCleanText === trimmedCleanRaw || cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) return true;
        }
        return false;
      });

      let annObj = candidates[0];
      if (candidates.length > 1) {
        let minDist = Infinity;
        const elRect = textEl.getBoundingClientRect();
        const coords = screenToDataCoords({ clientX: elRect.left + elRect.width / 2, clientY: elRect.top + elRect.height / 2 });
        if (coords) {
          candidates.forEach(cand => {
            const dist = Math.hypot(cand.x - coords.x, cand.y - coords.y);
            if (dist < minDist) {
              minDist = dist;
              annObj = cand;
            }
          });
        }
      }

      if (!annObj || !annObj.name) return;

      g._dragBound = true;
      g.style.cursor = 'grab';

      let isDragging = false;
      let startX = 0, startY = 0;

      const onMouseDown = (e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();

        isDragging = false;
        startX = e.clientX;
        startY = e.clientY;

        g.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';

        selectAnnotation(annObj, g);

        const onMouseMove = (me) => {
          const dx = me.clientX - startX;
          const dy = me.clientY - startY;
          if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
            isDragging = true;
            g.style.transform = `translate(${dx}px, ${dy}px)`;
          }
        };

        const onMouseUp = (ue) => {
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
          g.style.cursor = 'grab';
          g.style.transform = '';
          document.body.style.userSelect = '';

          if (isDragging) {
            const coords = screenToDataCoords(ue);
            if (coords) {
              annObj.x = coords.x;
              annObj.y = coords.y;
              annObj.xanchor = 'center';
              annObj.yanchor = 'middle';
              annObj.xshift = 0;
              annObj.yshift = 0;

              if (container && container.layout && Array.isArray(container.layout.annotations)) {
                const match = container.layout.annotations.find(a => (a.name && a.name === annObj.name) || (a.text && a.text === annObj.text));
                if (match) {
                  match.x = coords.x;
                  match.y = coords.y;
                  match.xanchor = 'center';
                  match.yanchor = 'middle';
                  match.xshift = 0;
                  match.yshift = 0;
                }
              }

              savePosition(annObj.name, coords.x, coords.y);
              const liveAnnotations = container.layout?.annotations ? [...container.layout.annotations] : annotations;
              Plotly.relayout(container, { annotations: liveAnnotations }).then(() => {
                deselectAnnotation();
                setupSvgEvents();
              });
            }
          }
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      };

      g.addEventListener('mousedown', onMouseDown);
    });
  };

  if (container.on) {
    try {
      container.removeListener?.('plotly_afterplot', setupSvgEvents);
      container.on('plotly_afterplot', setupSvgEvents);
    } catch (e) {}
  }

  setTimeout(() => {
    setupSvgEvents();
  }, 250);
}



/* ══════════════════════════════════════════════════════════════════════════
   WARMAN PERFORMANCE MAP
   ══════════════════════════════════════════════════════════════════════════ */

/* ── Speed-line colour palette — warm oranges ────────────────────────────── */
const SPD_COLORS = ['#664400', '#995500', '#cc7700', '#ff9900'];  // 70%→80%→90%→100%

function buildWarmanChart(data, opts = {}) {
  const { showIsolines = true, showPowerIso = false, showNpshIso = false, showSpeedLines = false, showDiaOverlay = false, showNpshCurve = false, npshYAxis = 'y2', dutyQ, dutyH } = opts;
  const units = getGraphDisplayUnits();
  const lblQ = typeof getUnitLabel === 'function' ? getUnitLabel('q', units.q) : units.q;
  const lblH = typeof getUnitLabel === 'function' ? getUnitLabel('h', units.h) : units.h;
  const lblNpsh = typeof getUnitLabel === 'function' ? getUnitLabel('npsh', units.npsh) : units.npsh;
  const lblPow = typeof getUnitLabel === 'function' ? getUnitLabel('pow', units.pow) : units.pow;

  const traces = [];
  const annotations = [];
  const family = data.family || [];
  const famType = data.pump?.family_type || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');
  const formatFamLabel = (val) => isVarSpeed ? `${val} RPM` : `Ø${val} mm`;
  const isolines = data.isolines || [];
  const pwr_iso = data.power_isolines || [];
  const npsh_iso = data.npsh_isolines || [];
  const chkRpmEl = typeof document !== 'undefined' ? document.getElementById('chkRpmOverlay') : null;
  const chkDiaEl = typeof document !== 'undefined' ? document.getElementById('chkDiaOverlay') : null;
  const chkRpm = chkRpmEl ? chkRpmEl.checked : isVarSpeed;
  const chkDia = chkDiaEl ? chkDiaEl.checked : !isVarSpeed;
  const showFamily = isVarSpeed ? (chkRpm || (!chkRpm && !chkDia)) : (chkDia || (!chkRpm && !chkDia));

  const spd_lines = getActiveOverlayLines(data);
  const dia_overlay = data.dia_overlay || [];

  const legendMode = units.legendMode || 'each';
  const labelPos = units.labelPos || 'middle-top';

  const headColor = units.headColor || '#58a6ff';
  const headWeight = units.headWeight || 2.0;
  const headStyle = units.headStyle || 'solid';

  const effColor = units.effColor || '#3fb950';
  const effWeight = units.effWeight || 1.5;
  const effStyle = units.effStyle || 'dot';

  const powColor = units.powColor || '#f85149';
  const powWeight = units.powWeight || 1.5;
  const powStyle = units.powStyle || 'longdash';

  const npshColor = units.npshColor || '#39d3c0';
  const npshWeight = units.npshWeight || 1.5;
  const npshStyle = units.npshStyle || 'dashdot';

  const nDia = family.length;

  /* ── H-Q curves (one per diameter / speed) ──── */
  if (showFamily) {
    family.forEach((d, i) => {
      const tag = d.label_tag || (d.curve_mode === 'fit' ? ' (Fitted)' : '');
      const useCustom = d.use_custom_style || d.style_mode === 'custom';
      const col = (useCustom && d.color) ? d.color : headColor;
      const lw = (useCustom && d.weight) ? d.weight : (d.is_max ? headWeight : Math.max(1.0, headWeight - 0.5));
      const dash = (useCustom && d.style) ? d.style : (d.label_tag ? 'dash' : headStyle);

      const lblText = formatFamLabel(d.dia);
      const showInLegend = (legendMode === 'curve_labels') ? false : (legendMode !== 'curve_labels');
      const traceName = `${lblText}${tag}`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: traceName,
        x: d.q, y: d.h,
        line: { color: col, width: lw, dash: dash },
        showlegend: showInLegend,
        hovertemplate: `${lblText}${tag}<br>Q=%{x:.1f} ${lblQ}<br>H=%{y:.2f} ${lblH}<extra></extra>`,
      });

      /* BEP star on each curve */
      if (d.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `BEP ${lblText}${tag}`,
          x: [d.bep.q], y: [d.bep.h],
          marker: {
            size: d.is_max ? 10 : 7, color: col, symbol: 'star',
            line: { color: '#fff', width: 1 }
          },
          showlegend: false,
          hovertemplate: `BEP ${lblText}${tag}<br>Q=${d.bep.q} ${lblQ}<br>H=${d.bep.h} ${lblH}<br>η=${d.bep.eta}%<extra></extra>`,
        });
      }
    });
  }

  /* ── Direct Impeller Curve Labels (if Mode 3: curve_labels) ──── */
  const drawnBadgeKeysHQ = new Set();
  const baseRpm = data.pump?.speed_rpm || 1450;
  const baseDia = data.pump?.impeller_dia_mm || 300;

  if (legendMode === 'curve_labels' && showFamily) {
    family.forEach((d, i) => {
      if (!d.q || d.q.length === 0 || !d.dia || d.dia <= 0) return;
      const col = d.color || headColor;
      const tag = d.label_tag || (d.curve_mode === 'fit' ? ' (Fitted)' : '');
      const vKey = (isVarSpeed ? 'rpm_' : 'dia_') + Math.round(d.dia);
      drawnBadgeKeysHQ.add(vKey);
      const lblText = formatCurveLabel(d.dia, d.ratio, isVarSpeed, units.labelFormat, baseDia, baseRpm);
      if (!lblText) return;
      const curveKey = `${lblText}${tag}`;

      let targetQ = 0;
      let targetH = 0;
      let xanchor = 'center';
      let yanchor = 'middle';
      let xshift = 0;
      let yshift = 0;

      const annName = (isVarSpeed ? 'spd_lbl_' : 'dia_lbl_') + i;
      const candidateKeys = [annName, `dia_lbl_${i}`, curveKey, lblText, `dia_${Math.round(d.dia)}`];
      let pos = null;
      if (customLabelPositions && typeof customLabelPositions === 'object') {
        for (const k of candidateKeys) {
          if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
            pos = customLabelPositions[k]; break;
          }
        }
      }

      if (pos) {
        targetQ = pos.x;
        targetH = pos.y;
        xanchor = 'center';
        yanchor = 'middle';
        xshift = 0;
        yshift = 0;
      } else {
        // Initial default placement at tail end of curve line
        const lastIdx = d.q.length - 1;
        targetQ = d.q[lastIdx];
        targetH = d.h[lastIdx];
        xanchor = 'left';
        xshift = 4;
        yanchor = 'bottom';
        yshift = 4;
      }

      annotations.push({
        x: targetQ,
        y: targetH,
        text: `<b>${curveKey}</b>`,
        showarrow: false,
        captureevents: true,
        font: { color: '#ffffff', size: 10, family: 'Arial, sans-serif' },
        bgcolor: 'rgba(22, 27, 34, 0.92)',
        bordercolor: col,
        borderwidth: 1.5,
        borderpad: 4,
        xanchor: xanchor,
        yanchor: yanchor,
        xshift: xshift,
        yshift: yshift,
        name: annName
      });
    });
  }

  /* ── Efficiency isolines ──── */
  if (showIsolines && isolines.length > 0) {
    const etaVals = isolines.map(l => l.eta);
    const etaMin = Math.min(...etaVals);
    const etaMax = Math.max(...etaVals);

    isolines.forEach((iso, idx) => {
      const showInLegend = (legendMode === 'curve_labels') ? (idx === 0) : false;
      const traceName = (legendMode === 'curve_labels') ? 'Efficiency η' : `η = ${iso.eta}%`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: traceName,
        x: iso.q, y: iso.h,
        line: { color: effColor, width: effWeight, dash: effStyle },
        fill: 'none',
        hovertemplate: `η = ${iso.eta}%<br>Q=%{x:.1f} ${lblQ}<br>H=%{y:.2f} ${lblH}<extra></extra>`,
        showlegend: showInLegend,
      });

      /* Non-clashing Efficiency Label Badge Annotation */
      if (iso.label_q !== undefined && iso.label_h !== undefined) {
        const branchKey = iso.branch ? `_${iso.branch}` : `_${idx}`;
        const key = `eta_${iso.eta}${branchKey}`;
        const legacyKey = `eta_${iso.eta}`;

        let targetQ = iso.label_q;
        let targetH = iso.label_h;

        if (customLabelPositions && customLabelPositions[key]) {
          targetQ = customLabelPositions[key].x;
          targetH = customLabelPositions[key].y;
        } else if (idx === 0 && customLabelPositions && customLabelPositions[legacyKey]) {
          targetQ = customLabelPositions[legacyKey].x;
          targetH = customLabelPositions[legacyKey].y;
        }

        annotations.push({
          x: targetQ, y: targetH,
          text: `<b>${iso.label_text || `${iso.eta}%`}</b>`,
          showarrow: false,
          captureevents: true,
          font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.92)',
          bordercolor: effColor,
          borderwidth: 1,
          borderpad: 3,
          xanchor: 'center',
          yanchor: 'middle',
          name: key
        });
      }
    });
  }

  /* ── Power isolines ──── */
  if (showPowerIso && pwr_iso.length > 0) {
    pwr_iso.forEach((pl, idx) => {
      const showInLegend = (legendMode === 'curve_labels') ? (idx === 0) : false;
      const traceName = (legendMode === 'curve_labels') ? 'Power P' : `P = ${pl.power} ${lblPow}`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: traceName,
        x: pl.q, y: pl.h,
        line: { color: powColor, width: powWeight, dash: powStyle },
        showlegend: showInLegend,
        hovertemplate: `P = ${pl.power} ${lblPow}<br>Q=%{x:.1f} ${lblQ}<br>H=%{y:.2f} ${lblH}<extra></extra>`,
      });
      if (pl.q.length > 0) {
        const branchKey = pl.branch ? `_${pl.branch}` : `_${idx}`;
        const key = `pow_${pl.power}${branchKey}`;
        let targetQ = 0;
        let targetH = 0;
        if (customLabelPositions && customLabelPositions[key]) {
          targetQ = customLabelPositions[key].x;
          targetH = customLabelPositions[key].y;
        } else {
          const mi = Math.floor(pl.q.length / 2);
          targetQ = pl.q[mi];
          targetH = pl.h[mi];
        }
        annotations.push({
          x: targetQ, y: targetH,
          text: `<b>${pl.power}${lblPow}</b>`,
          showarrow: false,
          captureevents: true,
          font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.92)',
          bordercolor: '#f85149',
          borderwidth: 1,
          borderpad: 3,
          xanchor: 'center',
          yanchor: 'middle',
          name: key
        });
      }
    });
  }

  /* ── NPSH isolines ──── */
  if (showNpshIso && npsh_iso.length > 0) {
    npsh_iso.forEach((nl, idx) => {
      const showInLegend = (legendMode === 'curve_labels') ? (idx === 0) : false;
      const traceName = (legendMode === 'curve_labels') ? 'NPSHr' : `NPSHr = ${nl.npsh} ${lblNpsh}`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: traceName,
        x: nl.q, y: nl.h,
        line: { color: npshColor, width: npshWeight, dash: npshStyle },
        showlegend: showInLegend,
        hovertemplate: `NPSHr = ${nl.npsh} ${lblNpsh}<br>Q=%{x:.1f} ${lblQ}<br>H=%{y:.2f} ${lblH}<extra></extra>`,
      });
      if (nl.q.length > 0) {
        const branchKey = nl.branch ? `_${nl.branch}` : `_${idx}`;
        const key = `npsh_${nl.npsh}${branchKey}`;
        let targetQ = 0;
        let targetH = 0;
        if (customLabelPositions && customLabelPositions[key]) {
          targetQ = customLabelPositions[key].x;
          targetH = customLabelPositions[key].y;
        } else {
          const mi = Math.floor(nl.q.length / 2);
          targetQ = nl.q[mi];
          targetH = nl.h[mi];
        }
        annotations.push({
          x: targetQ, y: targetH,
          text: `<b>${nl.npsh}${lblNpsh}</b>`,
          showarrow: false,
          captureevents: true,
          font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.92)',
          bordercolor: '#39d3c0',
          borderwidth: 1,
          borderpad: 3,
          xanchor: 'center',
          yanchor: 'middle',
          name: key
        });
      }
    });
  }

  /* ── Representative Legend Traces for Mode 2 (hq_only) ──── */
  if (legendMode === 'hq_only') {
    if (showIsolines && isolines.length > 0) {
      traces.push({
        type: 'scatter', mode: 'lines', name: 'Efficiency Isolines (%)',
        x: [null], y: [null],
        line: { color: '#e3b341', width: 1.8, dash: 'dot' },
        showlegend: true
      });
    }
    if (showPowerIso && pwr_iso.length > 0) {
      traces.push({
        type: 'scatter', mode: 'lines', name: `Power Isolines (${lblPow})`,
        x: [null], y: [null],
        line: { color: '#f85149', width: 1.8, dash: 'longdash' },
        showlegend: true
      });
    }
    if (showNpshIso && npsh_iso.length > 0) {
      traces.push({
        type: 'scatter', mode: 'lines', name: `NPSH Isolines (${lblNpsh})`,
        x: [null], y: [null],
        line: { color: '#39d3c0', width: 1.8, dash: 'dashdot' },
        showlegend: true
      });
    }
  }

  /* ── Speed / Impeller Overlay Lines ──── */
  if (spd_lines.length > 0) {
    spd_lines.forEach((sl, i) => {
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lw = sl.speed_ratio === 1.0 ? 2.2 : 1.5;
      const baseRpm = data.pump?.speed_rpm || 1450;
      const baseDia = data.pump?.impeller_dia_mm || 300;
      const isRpm = (sl.speed_rpm !== undefined) || (sl.is_rpm === true) || (sl.type === 'rpm') || (sl.label && sl.label.toLowerCase().includes('rpm')) || (!sl.dia && sl.val && sl.val > 100);
      const lineLabel = sl.label || (isRpm 
        ? (sl.val ? `${Math.round(sl.val)} rpm (${Math.round((sl.val / baseRpm) * 100)}%)` : `${sl.speed_rpm || Math.round(baseRpm * sl.speed_ratio)} rpm (${Math.round(sl.speed_ratio * 100)}%)`)
        : (sl.val ? `Ø${Math.round(sl.val)} mm (${Math.round((sl.val / baseDia) * 100)}%)` : `Ø${Math.round(baseDia * (sl.ratio || sl.speed_ratio || 1.0))} mm (${Math.round((sl.ratio || sl.speed_ratio || 1.0) * 100)}%)`));

      traces.push({
        type: 'scatter', mode: 'lines',
        name: lineLabel,
        x: sl.q, y: sl.h,
        line: { color: col, width: lw, dash: sl.speed_ratio === 1.0 ? 'solid' : 'dot' },
        showlegend: legendMode !== 'curve_labels',
        hovertemplate: `${lineLabel}<br>Q=%{x:.1f} ${lblQ}<br>H=%{y:.2f} ${lblH}<extra></extra>`,
      });
      /* BEP tick on overlay line */
      if (sl.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `BEP ${lineLabel}`,
          x: [sl.bep.q], y: [sl.bep.h],
          marker: {
            size: 6, color: col, symbol: 'diamond',
            line: { color: '#fff', width: 0.8 }
          },
          showlegend: false,
          hovertemplate: `BEP ${lineLabel}<br>Q=${sl.bep.q} ${lblQ}<br>H=${sl.bep.h} ${lblH}<extra></extra>`,
        });
      }

      /* Direct label badge on each overlay curve */
      if (legendMode === 'curve_labels' && sl.q && sl.q.length > 0 && sl.h && sl.h.length > 0) {
        const isRpm = (sl.speed_rpm !== undefined) || (sl.label && sl.label.toLowerCase().includes('rpm')) || (sl.val && sl.val > 100);
        const slVal = Math.round(sl.val || sl.speed_rpm || sl.dia || (sl.speed_ratio ? (isRpm ? baseRpm * sl.speed_ratio : baseDia * sl.speed_ratio) : 0));
        if (slVal > 0) {
          const vKey = (isRpm ? 'rpm_' : 'dia_') + slVal;
          if (!drawnBadgeKeysHQ.has(vKey)) {
            drawnBadgeKeysHQ.add(vKey);
            const lineLabel = formatCurveLabel(sl.val || sl.speed_rpm || sl.dia, sl.speed_ratio || sl.ratio, isRpm, units.labelFormat, baseDia, baseRpm);
            if (lineLabel) {
              const lastIdx = Math.floor(sl.q.length * 0.90);
              annotations.push({
                x: sl.q[lastIdx], y: sl.h[lastIdx],
                text: `<b>${lineLabel}</b>`,
                showarrow: false, captureevents: true,
                font: { color: '#ffffff', size: 9, family: 'Arial, sans-serif' },
                bgcolor: 'rgba(15, 23, 42, 0.90)',
                bordercolor: col, borderwidth: 1, borderpad: 2,
                xanchor: 'center', yanchor: 'middle',
                name: `spd_lbl_${i}`
              });
            }
          }
        }
      }
    });
  }

  /* ── Diameter Overlay Lines ──── */
  if (showDiaOverlay && dia_overlay.length > 0) {
    dia_overlay.forEach((dl, i) => {
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lw = 1.5;
      const lineLabel = dl.label || `Ø${dl.dia} mm`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: lineLabel,
        x: dl.q, y: dl.h,
        line: { color: col, width: lw, dash: 'dash' },
        showlegend: legendMode !== 'curve_labels',
        hovertemplate: `${lineLabel}<br>Q=%{x:.1f} ${lblQ}<br>H=%{y:.2f} ${lblH}<extra></extra>`,
      });

      /* Direct label badge on each overlay curve */
      if (legendMode === 'curve_labels' && dl.q && dl.q.length > 0 && dl.h && dl.h.length > 0) {
        const dlVal = Math.round(dl.dia || dl.val || 0);
        if (dlVal > 0) {
          const vKey = 'dia_' + dlVal;
          if (!drawnBadgeKeysHQ.has(vKey)) {
            drawnBadgeKeysHQ.add(vKey);
            const lineLabel = formatCurveLabel(dl.dia, dl.ratio, isVarSpeed, units.labelFormat, baseDia, baseRpm);
            if (lineLabel) {
              const lastIdx = Math.floor(dl.q.length * 0.90);
              annotations.push({
                x: dl.q[lastIdx], y: dl.h[lastIdx],
                text: `<b>${lineLabel}</b>`,
                showarrow: false, captureevents: true,
                font: { color: '#ffffff', size: 9, family: 'Arial, sans-serif' },
                bgcolor: 'rgba(15, 23, 42, 0.90)',
                bordercolor: col, borderwidth: 1, borderpad: 2,
                xanchor: 'center', yanchor: 'middle',
                name: `dia_lbl_${i}`
              });
            }
          }
        }
      }
    });
  }

  /* ── NPSH standard curves (secondary or same axis) ── */
  if (showNpshCurve) {
    family.forEach((d, i) => {
      traces.push({
        type: 'scatter', mode: 'lines',
        name: `NPSHr Ø${d.dia} mm`,
        x: d.q, y: d.npsh,
        line: { color: DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)], width: 1.5, dash: 'dashdot' },
        yaxis: npshYAxis,
        showlegend: legendMode === 'hq_only',
        hovertemplate: `Ø${d.dia} mm NPSHr<br>Q=%{x:.1f} ${lblQ}<br>NPSHr=%{y:.2f} ${lblNpsh}<extra></extra>`
      });
    });
  }

  /* ── System curve ──── */
  if (data.system_q && data.system_h) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'System Curve',
      x: data.system_q, y: data.system_h,
      line: { color: '#bc8cff', width: 2, dash: 'dash' },
      showlegend: legendMode !== 'curve_labels',
      hovertemplate: `System<br>Q=%{x:.1f} ${lblQ}<br>H_sys=%{y:.2f} ${lblH}<extra></extra>`,
    });
  }

  /* ── Duty point ──── */
  if (dutyQ && dutyH) traces.push(dutyTrace(dutyQ, dutyH));

  const layout = makeLayout('Flow Q (m³/h)', 'Head H (m)', {
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: 'Head H (m)', rangemode: 'tozero' }),
  });

  if (legendMode === 'curve_labels') {
    layout.showlegend = true;
    layout.legend = Object.assign({}, layout.legend || {}, {
      bgcolor: 'rgba(22, 27, 34, 0.88)',
      bordercolor: '#30363d',
      borderwidth: 1,
      font: { color: '#c9d1d9', size: 10 }
    });
  }
  if (annotations.length > 0) {
    layout.annotations = annotations;
  }

  if (showNpshCurve && npshYAxis === 'y2') {
    layout.yaxis2 = {
      title: 'NPSHr (m)', overlaying: 'y', side: 'right',
      rangemode: 'tozero', showgrid: false,
      titlefont: { color: '#39d3c0', size: 12 }, tickfont: { color: '#39d3c0' }
    };
  }

  return { traces, layout };
}

/* ── NPSH family chart ───────────────────────────────────────────────────── */
function buildNpshFamilyChart(family) {
  const traces = family.map((d, i) => {
    const col = d.color || DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)];
    const tag = d.curve_mode === 'fit' ? ' (Fitted)' : '';
    return {
      type: 'scatter', mode: 'lines',
      name: `Ø${d.dia} mm${tag}`,
      x: d.q, y: d.npsh,
      line: { color: col, width: 1.8 },
      hovertemplate: `Ø${d.dia}${tag}<br>Q=%{x:.1f}<br>NPSHr=%{y:.2f} m<extra></extra>`,
    };
  });
  return {
    traces, layout: makeLayout('Flow Q (m³/h)', 'NPSHr (m)',
      { yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { rangemode: 'tozero' }) })
  };
}

/* ── Power family chart ──────────────────────────────────────────────────── */
function buildPowerFamilyChart(family) {
  const traces = family.map((d, i) => {
    const col = d.color || DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)];
    const tag = d.curve_mode === 'fit' ? ' (Fitted)' : '';
    return {
      type: 'scatter', mode: 'lines',
      name: `Ø${d.dia} mm${tag}`,
      x: d.q, y: d.power,
      line: { color: col, width: 1.8 },
      hovertemplate: `Ø${d.dia}${tag}<br>Q=%{x:.1f}<br>P=%{y:.2f} kW<extra></extra>`,
    };
  });
  return {
    traces, layout: makeLayout('Flow Q (m³/h)', 'Shaft Power P (kW)',
      { yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { rangemode: 'tozero' }) })
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   STANDALONE SINGLE-DIAMETER CURVES (max impeller)
   ══════════════════════════════════════════════════════════════════════════ */

function buildHQChart(data, showSystem, showClean) {
  const traces = [];
  traces.push({
    type: 'scatter', mode: 'lines',
    name: 'H-Q ' + (data.liquid !== 'water' ? `(${data.liquid})` : ''),
    x: data.q, y: data.h,
    line: { color: '#58a6ff', width: 2.5 },
    hovertemplate: 'Q=%{x:.1f} m³/h<br>H=%{y:.2f} m<extra></extra>',
  });
  if (showClean && data.h_clean) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'H-Q (water ref)',
      x: data.q, y: data.h_clean,
      line: { color: '#58a6ff', width: 1.5, dash: 'dot' }, opacity: 0.45, showlegend: true,
      hovertemplate: 'Q=%{x:.1f}<br>H(clean)=%{y:.2f}<extra></extra>'
    });
  }
  if (showSystem && data.system_h) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'System Curve',
      x: data.q, y: data.system_h, line: { color: '#bc8cff', width: 2, dash: 'dash' },
      hovertemplate: 'Q=%{x:.1f}<br>H_sys=%{y:.2f}<extra></extra>'
    });
  }
  if (data.bep) {
    traces.push({
      type: 'scatter', mode: 'markers', name: 'BEP',
      x: [data.bep.q], y: [data.bep.h],
      marker: { size: 10, color: '#3fb950', symbol: 'star', line: { color: '#fff', width: 1 } },
      hovertemplate: `BEP<br>Q=${data.bep.q}<br>H=${data.bep.h}<extra></extra>`
    });
  }
  const layout = makeLayout('Flow Q (m³/h)', 'Head H (m)');
  layout.yaxis.rangemode = 'tozero';
  return { traces, layout };
}

/* ── Helper: Get active overlay lines (RPM or Diameter Overlay) based on test basis and form toggles ── */
function getActiveOverlayLines(familyData) {
  if (!familyData) return [];
  const famType = familyData.pump?.family_type || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');

  const rpmEl = typeof document !== 'undefined' ? document.getElementById('chkRpmOverlay') : null;
  const diaEl = typeof document !== 'undefined' ? document.getElementById('chkDiaOverlay') : null;

  const chkRpm = rpmEl ? rpmEl.checked : isVarSpeed;
  const chkDia = diaEl ? diaEl.checked : !isVarSpeed;

  const lines = [];

  if (chkRpm && familyData.rpm_overlay && familyData.rpm_overlay.length > 0) {
    lines.push(...familyData.rpm_overlay);
  }

  if (chkDia && familyData.dia_overlay && familyData.dia_overlay.length > 0) {
    lines.push(...familyData.dia_overlay);
  }

  return lines;
}

/* ── Build Efficiency Chart ── */
// This function creates the Efficiency vs Flow (Q) graph.
// Beginner Note: If "Direct Labels" mode is enabled, we attach label badges (e.g. Ø228 mm)
// directly to each curve on this graph too, so the user can drag them or use Arrow keys.
function buildEffChart(familyData, singleData, showClean) {
  const traces = [];
  let family = [];
  if (familyData && familyData.family) {
    family = familyData.family;
  } else if (familyData) {
    family = [{
      dia: familyData.pump?.impeller_dia_mm || (typeof PUMP_MAIN_DIA !== 'undefined' ? PUMP_MAIN_DIA : null) || 0,
      is_max: true,
      ratio: 1.0,
      q: familyData.q,
      h: familyData.h,
      eta: familyData.eta,
      power: familyData.power,
      npsh: familyData.npsh,
      bep: familyData.bep
    }];
  }

  const units = getGraphDisplayUnits();
  const effColor = units.effColor || '#3fb950';
  const effWeight = units.effWeight || 1.5;
  const effStyle = units.effStyle || 'dot';

  const isVarSpeed = (familyData?.pump?.family_type === 'variable_speed');
  const baseRpm = familyData?.pump?.speed_rpm || 1450;
  const baseDia = familyData?.pump?.impeller_dia_mm || 300;
  const formatFamLbl = (v) => isVarSpeed ? `${v} RPM` : `Ø${v} mm`;

  const chkRpmEl = typeof document !== 'undefined' ? document.getElementById('chkRpmOverlay') : null;
  const chkDiaEl = typeof document !== 'undefined' ? document.getElementById('chkDiaOverlay') : null;
  const chkRpm = chkRpmEl ? chkRpmEl.checked : isVarSpeed;
  const chkDia = chkDiaEl ? chkDiaEl.checked : !isVarSpeed;
  const showFamily = isVarSpeed ? (chkRpm || (!chkRpm && !chkDia)) : (chkDia || (!chkRpm && !chkDia));

  if (showFamily) {
    family.forEach((fam, idx) => {
      if (!fam.dia || fam.dia <= 0) return;
      const isMax = fam.is_max;
      const lw = isMax ? (effWeight + 0.7) : effWeight;
      const showInLegend = (units.legendMode === 'curve_labels') ? false : (units.legendMode === 'each');
      const lblText = formatCurveLabel(fam.dia, fam.ratio, isVarSpeed, units.labelFormat, baseDia, baseRpm);
      if (!lblText) return;
      const traceName = `η ${lblText}`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: traceName,
        x: fam.q, y: fam.eta,
        line: { color: effColor, width: lw, dash: effStyle },
        showlegend: showInLegend,
        hovertemplate: `${lblText}<br>Q=%{x:.1f} m³/h<br>η=%{y:.1f}%<extra></extra>`
      });

      if (fam.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `BEP ${lblText}`,
          x: [fam.bep.q], y: [fam.bep.eta],
          marker: { size: isMax ? 10 : 7, color: effColor, symbol: 'star', line: { color: '#fff', width: 1 } },
          showlegend: false,
          hovertemplate: `BEP ${lblText}<br>Q=${fam.bep.q}<br>η=${fam.bep.eta}%<extra></extra>`
        });
      }
    });
  }

  const familyValsE = new Set(family.map(f => Math.round(f.dia || 0)).filter(v => v > 0));

  /* ── Overlay Speed / Impeller Trims on Efficiency Chart ── */
  const spdLinesE = getActiveOverlayLines(familyData);
  if (spdLinesE.length > 0) {
    spdLinesE.forEach((sl, i) => {
      if (!sl.eta || sl.eta.length === 0) return;
      const isRpm = (sl.speed_rpm !== undefined) || (sl.label && sl.label.toLowerCase().includes('rpm')) || (sl.val && sl.val > 100);
      const slVal = Math.round(sl.val || sl.dia || sl.speed_rpm || 0);

      // If it's a duplicate diameter line already in family, skip drawing duplicate line trace!
      if (!isRpm && familyValsE.has(slVal)) return;

      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lineLabel = formatCurveLabel(sl.val || sl.speed_rpm || sl.dia, sl.speed_ratio || sl.ratio, isRpm, units.labelFormat, baseDia, baseRpm);
      if (!lineLabel) return;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: `η ${lineLabel}`,
        x: sl.q, y: sl.eta,
        line: { color: col, width: 1.5, dash: 'dot' },
        showlegend: false,
        hovertemplate: `${lineLabel} η<br>Q=%{x:.1f} m³/h<br>η=%{y:.1f}%<extra></extra>`
      });
    });
  }

  if (showClean && singleData && singleData.eta_clean) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'η (water ref)',
      x: singleData.q, y: singleData.eta_clean,
      line: { color: '#f0c040', width: 1.5, dash: 'dot' }, opacity: 0.45,
      hovertemplate: 'Q=%{x:.1f}<br>η(clean)=%{y:.1f}%<extra></extra>'
    });
  }

  const layout = makeLayout('Flow Q (m³/h)', 'Efficiency η (%)');
  layout.yaxis = Object.assign({}, layout.yaxis, { range: [0, 100] });
  if (units.legendMode === 'hq_only' || units.legendMode === 'curve_labels') {
    layout.showlegend = false;
  }

  layout.annotations = layout.annotations || [];

  if (units.legendMode === 'curve_labels') {
    const drawnBadgeKeysE = new Set();
    const baseRpm = familyData?.pump?.speed_rpm || 1450;
    const baseDia = familyData?.pump?.impeller_dia_mm || 300;

    if (showFamily) {
      family.forEach((fam, idx) => {
        if (!fam.q || fam.q.length === 0 || !fam.eta || !fam.dia || fam.dia <= 0) return;
        const col = DIA_BLUES[Math.min(idx, DIA_BLUES.length - 1)];
        const vKey = (isVarSpeed ? 'rpm_' : 'dia_') + Math.round(fam.dia);
        drawnBadgeKeysE.add(vKey);
        const lblText = formatCurveLabel(fam.dia, fam.ratio, isVarSpeed, units.labelFormat, baseDia, baseRpm);
        if (!lblText) return;
        const curveKey = `eff_${lblText}`;
        const altKey = lblText;

        const annName = (isVarSpeed ? 'eff_spd_' : 'eff_dia_') + idx;
        const candidateKeys = [annName, `eff_dia_${idx}`, curveKey, altKey, `eff_${lblText}`];
        let pos = null;
        if (customLabelPositions && typeof customLabelPositions === 'object') {
          for (const k of candidateKeys) {
            if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
              pos = customLabelPositions[k]; break;
            }
          }
        }

        let targetQ = 0, targetEta = 0, xanchor = 'left', yanchor = 'bottom', xshift = 4, yshift = 4;
        if (pos) {
          targetQ = pos.x;
          targetEta = pos.y;
          xanchor = 'center'; yanchor = 'middle'; xshift = 0; yshift = 0;
        } else {
          const lastIdx = Math.floor(fam.q.length * 0.95);
          targetQ = fam.q[lastIdx];
          targetEta = fam.eta[lastIdx];
        }

        layout.annotations.push({
          x: targetQ, y: targetEta,
          text: `<b>η ${lblText}</b>`,
          showarrow: false, captureevents: true,
          font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.92)',
          bordercolor: col, borderwidth: 1.5, borderpad: 3,
          xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
          name: annName
        });
      });
    }

    if (spdLinesE.length > 0) {
      spdLinesE.forEach((sl, i) => {
        if (!sl.q || sl.q.length === 0 || !sl.eta) return;
        const isRpm = (sl.speed_rpm !== undefined) || (sl.label && sl.label.toLowerCase().includes('rpm')) || (sl.val && sl.val > 100);
        const slVal = Math.round(sl.val || sl.speed_rpm || sl.dia || (sl.speed_ratio ? (isRpm ? baseRpm * sl.speed_ratio : baseDia * sl.speed_ratio) : 0));
        if (slVal <= 0) return;
        const vKey = (isRpm ? 'rpm_' : 'dia_') + slVal;
        if (drawnBadgeKeysE.has(vKey)) return;
        drawnBadgeKeysE.add(vKey);

        const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
        const lineLabel = formatCurveLabel(sl.val || sl.speed_rpm || sl.dia, sl.speed_ratio || sl.ratio, isRpm, units.labelFormat, baseDia, baseRpm);
        if (!lineLabel) return;
        const curveKey = `eff_spd_${i}`;
        const candidateKeys = [curveKey, `spd_lbl_${i}`, lineLabel, `eff_${lineLabel}`];
        let pos = null;
        if (customLabelPositions && typeof customLabelPositions === 'object') {
          for (const k of candidateKeys) {
            if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
              pos = customLabelPositions[k]; break;
            }
          }
        }
        let targetQ = 0, targetEta = 0, xanchor = 'center', yanchor = 'bottom', xshift = 0, yshift = 4;
        if (pos) {
          targetQ = pos.x; targetEta = pos.y; xanchor = 'center'; yanchor = 'middle'; yshift = 0;
        } else {
          const lastIdx = Math.floor(sl.q.length * 0.85);
          targetQ = sl.q[lastIdx]; targetEta = sl.eta[lastIdx];
        }

        layout.annotations.push({
          x: targetQ, y: targetEta,
          text: `<b>η ${lineLabel}</b>`,
          showarrow: false, captureevents: true,
          font: { color: '#ffffff', size: 9, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.90)',
          bordercolor: col, borderwidth: 1, borderpad: 2,
          xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
          name: curveKey
        });
      });
    }
  }

  return { traces, layout };
}

/* ── Build Efficiency & Power Combined Chart ── */
function buildEffPowerChart(familyData, singleData, showClean) {
  const traces = [];
  let family = [];
  if (familyData && familyData.family) {
    family = familyData.family;
  } else if (familyData) {
    family = [{
      dia: familyData.pump?.impeller_dia_mm || (typeof PUMP_MAIN_DIA !== 'undefined' ? PUMP_MAIN_DIA : null) || 0,
      is_max: true,
      ratio: 1.0,
      q: familyData.q,
      h: familyData.h,
      eta: familyData.eta,
      power: familyData.power,
      npsh: familyData.npsh,
      bep: familyData.bep
    }];
  }

  const unitsEP = getGraphDisplayUnits();
  const effColor = unitsEP.effColor || '#3fb950';
  const effWeight = unitsEP.effWeight || 1.5;
  const effStyle = unitsEP.effStyle || 'dot';

  const powColor = unitsEP.powColor || '#f85149';
  const powWeight = unitsEP.powWeight || 1.5;
  const powStyle = unitsEP.powStyle || 'longdash';

  const famType = familyData?.pump?.family_type || singleData?.pump?.family_type || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');
  const baseRpm = familyData?.pump?.speed_rpm || 1450;
  const baseDia = familyData?.pump?.impeller_dia_mm || 300;
  const formatFamLbl = (v) => isVarSpeed ? `${v} RPM` : `Ø${v} mm`;

  const chkRpmEl = typeof document !== 'undefined' ? document.getElementById('chkRpmOverlay') : null;
  const chkDiaEl = typeof document !== 'undefined' ? document.getElementById('chkDiaOverlay') : null;
  const chkRpm = chkRpmEl ? chkRpmEl.checked : isVarSpeed;
  const chkDia = chkDiaEl ? chkDiaEl.checked : !isVarSpeed;
  const showFamily = isVarSpeed ? (chkRpm || (!chkRpm && !chkDia)) : (chkDia || (!chkRpm && !chkDia));

  if (showFamily) {
    family.forEach((fam, idx) => {
      const isMax = fam.is_max;
      const showEffLegend = (unitsEP.legendMode === 'curve_labels') ? (idx === 0) : (unitsEP.legendMode === 'each');
      const showPowLegend = (unitsEP.legendMode === 'curve_labels') ? (idx === 0) : (unitsEP.legendMode === 'each');
      const lblText = formatFamLbl(fam.dia);

      // Efficiency on y1 (left side)
      traces.push({
        type: 'scatter', mode: 'lines',
        name: (unitsEP.legendMode === 'curve_labels') ? 'Efficiency η' : `η ${lblText}`,
        x: fam.q, y: fam.eta,
        line: { color: effColor, width: isMax ? (effWeight + 0.7) : effWeight, dash: effStyle },
        yaxis: 'y1',
        showlegend: showEffLegend,
        hovertemplate: `${lblText} η<br>Q=%{x:.1f} m³/h<br>η=%{y:.1f}%<extra></extra>`
      });

      if (fam.bep) {
        traces.push({
          type: 'scatter', mode: 'markers',
          name: `BEP ${lblText}`,
          x: [fam.bep.q], y: [fam.bep.eta],
          marker: { size: isMax ? 10 : 7, color: effColor, symbol: 'star', line: { color: '#fff', width: 1 } },
          yaxis: 'y1',
          showlegend: false,
          hovertemplate: `BEP ${lblText}<br>Q=${fam.bep.q}<br>η=${fam.bep.eta}%<extra></extra>`
        });
      }

      // Power on y2 (right side)
      if (fam.power) {
        traces.push({
          type: 'scatter', mode: 'lines',
          name: `P ${lblText}`,
          x: fam.q, y: fam.power,
          line: { color: powColor, width: isMax ? (powWeight + 0.7) : powWeight, dash: powStyle },
          yaxis: 'y2',
          hovertemplate: `${lblText} P<br>Q=%{x:.1f} m³/h<br>P=%{y:.2f} kW<extra></extra>`
        });
      }
    });
  }

  /* ── Overlay Speed / Impeller Trims on Efficiency & Power Chart ── */
  const spdLinesEP = getActiveOverlayLines(familyData);
  if (spdLinesEP.length > 0) {
    spdLinesEP.forEach((sl, i) => {
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lineLabel = sl.label || '';
      const pwrArr = sl.pow || sl.power;

      if (sl.eta) {
        traces.push({
          type: 'scatter', mode: 'lines',
          name: `η ${lineLabel}`,
          x: sl.q, y: sl.eta,
          line: { color: col, width: 1.5, dash: 'dot' },
          yaxis: 'y1', showlegend: false,
          hovertemplate: `${lineLabel} η<br>Q=%{x:.1f} m³/h<br>η=%{y:.1f}%<extra></extra>`
        });
      }
      if (pwrArr) {
        traces.push({
          type: 'scatter', mode: 'lines',
          name: `P ${lineLabel}`,
          x: sl.q, y: pwrArr,
          line: { color: col, width: 1.5, dash: 'dashdot' },
          yaxis: 'y2', showlegend: false,
          hovertemplate: `${lineLabel} P<br>Q=%{x:.1f} m³/h<br>P=%{y:.2f} kW<extra></extra>`
        });
      }
    });
  }

  if (showClean && singleData) {
    if (singleData.eta_clean) {
      traces.push({
        type: 'scatter', mode: 'lines', name: 'η (water ref)',
        x: singleData.q, y: singleData.eta_clean,
        line: { color: '#f0c040', width: 1.5, dash: 'dot' }, opacity: 0.45,
        yaxis: 'y1',
        hovertemplate: 'Q=%{x:.1f}<br>η(clean)=%{y:.1f}%<extra></extra>'
      });
    }
    if (singleData.power_clean) {
      traces.push({
        type: 'scatter', mode: 'lines', name: 'P (water ref)',
        x: singleData.q, y: singleData.power_clean,
        line: { color: '#f85149', width: 1.5, dash: 'dot' }, opacity: 0.45,
        yaxis: 'y2',
        hovertemplate: 'Q=%{x:.1f}<br>P(clean)=%{y:.2f} kW<extra></extra>'
      });
    }
  }

  const layout = Object.assign({}, PLOTLY_LAYOUT_BASE, {
    xaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.xaxis, { title: 'Flow Q (m³/h)' }),
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: 'Efficiency η (%)', range: [0, 105] }),
    yaxis2: {
      title: 'Shaft Power P (kW)', overlaying: 'y', side: 'right',
      rangemode: 'tozero', showgrid: false,
      titlefont: { color: '#f85149', size: 12 }, tickfont: { color: '#f85149' }
    }
  });
  applyAxisScaleSettings(layout.xaxis, 'flow', familyData?.pump);
  applyAxisScaleSettings(layout.yaxis, 'eff', familyData?.pump);
  applyAxisScaleSettings(layout.yaxis2, 'power', familyData?.pump);
  if (unitsEP.legendMode === 'hq_only' || unitsEP.legendMode === 'curve_labels') {
    layout.showlegend = false;
  }

  layout.annotations = layout.annotations || [];

  if (showFamily) {
    family.forEach((fam, idx) => {
      if (!fam.q || fam.q.length === 0 || !fam.eta) return;
      const col = DIA_BLUES[Math.min(idx, DIA_BLUES.length - 1)];
      const lblText = formatFamLbl(fam.dia);
      const curveKey = `eff_${lblText}`;
      const altKey = lblText;

      const annName = (isVarSpeed ? 'effpow_spd_' : 'effpow_dia_') + idx;
      const candidateKeys = [annName, `effpow_dia_${idx}`, curveKey, altKey, `effpow_${lblText}`];
      let pos = null;
      if (customLabelPositions && typeof customLabelPositions === 'object') {
        for (const k of candidateKeys) {
          if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
            pos = customLabelPositions[k]; break;
          }
        }
      }

      let targetQ = 0, targetEta = 0, xanchor = 'left', yanchor = 'bottom', xshift = 4, yshift = 4;
      if (pos) {
        targetQ = pos.x;
        targetEta = pos.y;
        xanchor = 'center'; yanchor = 'middle'; xshift = 0; yshift = 0;
      } else {
        const lastIdx = Math.floor(fam.q.length * 0.85);
        targetQ = fam.q[lastIdx];
        targetEta = fam.eta[lastIdx];
      }

      layout.annotations.push({
        x: targetQ, y: targetEta,
        text: `<b>η ${lblText}</b>`,
        showarrow: false, captureevents: true,
        font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
        bgcolor: 'rgba(15, 23, 42, 0.92)',
        bordercolor: col, borderwidth: 1.5, borderpad: 3,
        xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
        name: annName
      });
    });
  }

  if (spdLinesEP.length > 0) {
    spdLinesEP.forEach((sl, i) => {
      if (!sl.q || sl.q.length === 0 || !sl.eta) return;
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const baseRpm = familyData?.pump?.speed_rpm || 1450;
      const baseDia = familyData?.pump?.impeller_dia_mm || 300;
      const lineLabel = sl.label || (isVarSpeed 
        ? (sl.val ? `Ø${sl.val} mm (${Math.round((sl.val / baseDia) * 100)}%)` : `Ø${Math.round(baseDia * sl.speed_ratio)} mm (${Math.round(sl.speed_ratio * 100)}%)`)
        : (sl.val ? `${Math.round(sl.val)} rpm (${Math.round((sl.val / baseRpm) * 100)}%)` : `${sl.speed_rpm || Math.round(baseRpm * sl.speed_ratio)} rpm (${Math.round(sl.speed_ratio * 100)}%)`));

      const curveKey = `eff_spd_${i}`;
      let targetQ = 0, targetEta = 0, xanchor = 'center', yanchor = 'middle', xshift = 0, yshift = 0;
      if (customLabelPositions && customLabelPositions[curveKey]) {
        const pos = customLabelPositions[curveKey];
        targetQ = pos.x; targetEta = pos.y;
      } else {
        const lastIdx = Math.floor(sl.q.length * 0.90);
        targetQ = sl.q[lastIdx]; targetEta = sl.eta[lastIdx];
      }

      layout.annotations.push({
        x: targetQ, y: targetEta,
        text: `<b>η ${lineLabel}</b>`,
        showarrow: false, captureevents: true,
        font: { color: '#ffffff', size: 9, family: 'Arial, sans-serif' },
        bgcolor: 'rgba(15, 23, 42, 0.90)',
        bordercolor: col, borderwidth: 1, borderpad: 2,
        xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
        name: curveKey
      });
    });
  }

  return { traces, layout };
}

/* ── Build Shaft Power Chart ── */
function buildPowerChart(familyData, singleData, showClean) {
  const traces = [];
  let family = [];
  if (familyData && familyData.family) {
    family = familyData.family;
  } else if (familyData) {
    family = [{
      dia: familyData.pump?.impeller_dia_mm || (typeof PUMP_MAIN_DIA !== 'undefined' ? PUMP_MAIN_DIA : null) || 0,
      is_max: true,
      ratio: 1.0,
      q: familyData.q,
      h: familyData.h,
      eta: familyData.eta,
      power: familyData.power,
      npsh: familyData.npsh,
      bep: familyData.bep
    }];
  }

  const unitsP = getGraphDisplayUnits();
  const powColor = unitsP.powColor || '#f85149';
  const powWeight = unitsP.powWeight || 1.5;
  const powStyle = unitsP.powStyle || 'longdash';

  const famType = familyData?.pump?.family_type || singleData?.pump?.family_type || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');
  const baseRpm = familyData?.pump?.speed_rpm || 1450;
  const baseDia = familyData?.pump?.impeller_dia_mm || 300;
  const formatFamLbl = (v) => isVarSpeed ? `${v} RPM` : `Ø${v} mm`;

  const chkRpmEl = typeof document !== 'undefined' ? document.getElementById('chkRpmOverlay') : null;
  const chkDiaEl = typeof document !== 'undefined' ? document.getElementById('chkDiaOverlay') : null;
  const chkRpm = chkRpmEl ? chkRpmEl.checked : isVarSpeed;
  const chkDia = chkDiaEl ? chkDiaEl.checked : !isVarSpeed;
  const showFamily = isVarSpeed ? (chkRpm || (!chkRpm && !chkDia)) : (chkDia || (!chkRpm && !chkDia));

  if (showFamily) {
    family.forEach((fam, idx) => {
      const isMax = fam.is_max;
      const showInLegend = (unitsP.legendMode === 'curve_labels') ? false : (unitsP.legendMode === 'each');
      const lblText = formatFamLbl(fam.dia);
      const traceName = `P ${lblText}`;

      if (fam.power) {
        traces.push({
          type: 'scatter', mode: 'lines',
          name: traceName,
          x: fam.q, y: fam.power,
          line: { color: powColor, width: isMax ? (powWeight + 0.7) : powWeight, dash: powStyle },
          showlegend: showInLegend,
          hovertemplate: `${lblText}<br>Q=%{x:.1f} m³/h<br>P=%{y:.2f} kW<extra></extra>`
        });
      }
    });
  }

  /* ── Overlay Speed / Impeller Trims on Power Chart ── */
  const spdLinesP = getActiveOverlayLines(familyData);
  if (spdLinesP.length > 0) {
    spdLinesP.forEach((sl, i) => {
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lineLabel = sl.label || '';
      const pwrArr = sl.pow || sl.power;

      if (pwrArr) {
        traces.push({
          type: 'scatter', mode: 'lines',
          name: `P ${lineLabel}`,
          x: sl.q, y: pwrArr,
          line: { color: col, width: 1.5, dash: 'dashdot' },
          showlegend: false,
          hovertemplate: `${lineLabel} P<br>Q=%{x:.1f} m³/h<br>P=%{y:.2f} kW<extra></extra>`
        });
      }
    });
  }

  if (showClean && singleData && singleData.power_clean) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'Power (water ref)',
      x: singleData.q, y: singleData.power_clean,
      line: { color: '#f85149', width: 1.5, dash: 'dot' }, opacity: 0.45,
      hovertemplate: 'Q=%{x:.1f}<br>P(clean)=%{y:.2f} kW<extra></extra>'
    });
  }

  const layout = makeLayout('Flow Q (m³/h)', 'Shaft Power P (kW)');
  layout.yaxis.rangemode = 'tozero';
  if (unitsP.legendMode === 'hq_only' || unitsP.legendMode === 'curve_labels') {
    layout.showlegend = false;
  }

  layout.annotations = layout.annotations || [];

  if (unitsP.legendMode === 'curve_labels') {
    const drawnBadgeKeysP = new Set();
    const baseRpm = familyData?.pump?.speed_rpm || 1450;
    const baseDia = familyData?.pump?.impeller_dia_mm || 300;

    if (showFamily) {
      family.forEach((fam, idx) => {
        if (!fam.q || fam.q.length === 0 || !fam.power || !fam.dia || fam.dia <= 0) return;
        const col = DIA_BLUES[Math.min(idx, DIA_BLUES.length - 1)];
        const vKey = (isVarSpeed ? 'rpm_' : 'dia_') + Math.round(fam.dia);
        drawnBadgeKeysP.add(vKey);
        const lblText = formatCurveLabel(fam.dia, fam.ratio, isVarSpeed, unitsP.labelFormat, baseDia, baseRpm);
        const curveKey = `pow_${lblText}`;
        const altKey = lblText;
        // Beginner Note: Look up saved custom label positions for Power graph using annName (pow_dia_0, pow_spd_0)
        const annName = (isVarSpeed ? 'pow_spd_' : 'pow_dia_') + idx;
        const candidateKeys = [annName, `pow_dia_${idx}`, `pow_spd_${idx}`, curveKey, altKey, `pow_${lblText}`];
        let pos = null;
        if (customLabelPositions && typeof customLabelPositions === 'object') {
          for (const k of candidateKeys) {
            if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
              pos = customLabelPositions[k]; break;
            }
          }
        }

        let targetQ = 0, targetPow = 0, xanchor = 'left', yanchor = 'bottom', xshift = 4, yshift = 4;
        if (pos) {
          targetQ = pos.x;
          targetPow = pos.y;
          xanchor = 'center'; yanchor = 'middle'; xshift = 0; yshift = 0;
        } else {
          const lastIdx = Math.floor(fam.q.length * 0.95);
          targetQ = fam.q[lastIdx];
          targetPow = fam.power[lastIdx];
        }

        layout.annotations.push({
          x: targetQ, y: targetPow,
          text: `<b>P ${lblText}</b>`,
          showarrow: false, captureevents: true,
          font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.92)',
          bordercolor: col, borderwidth: 1.5, borderpad: 3,
          xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
          name: annName
        });
      });
    }

    if (spdLinesP.length > 0) {
      spdLinesP.forEach((sl, i) => {
        const pwrArr = sl.pow || sl.power;
        if (!sl.q || sl.q.length === 0 || !pwrArr) return;
        const isRpm = (sl.speed_rpm !== undefined) || (sl.label && sl.label.toLowerCase().includes('rpm')) || (sl.val && sl.val > 100);
        const slVal = Math.round(sl.val || sl.speed_rpm || sl.dia || (sl.speed_ratio ? (isRpm ? baseRpm * sl.speed_ratio : baseDia * sl.speed_ratio) : 0));
        if (slVal <= 0) return;
        const vKey = (isRpm ? 'rpm_' : 'dia_') + slVal;
        if (drawnBadgeKeysP.has(vKey)) return;
        drawnBadgeKeysP.add(vKey);

        const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
        const lineLabel = formatCurveLabel(sl.val || sl.speed_rpm || sl.dia, sl.speed_ratio || sl.ratio, isRpm, unitsP.labelFormat, baseDia, baseRpm);
        if (!lineLabel) return;
        const curveKey = `pow_spd_${i}`;
        const candidateKeys = [curveKey, `spd_lbl_${i}`, lineLabel, `pow_${lineLabel}`];
        let pos = null;
        if (customLabelPositions && typeof customLabelPositions === 'object') {
          for (const k of candidateKeys) {
            if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
              pos = customLabelPositions[k]; break;
            }
          }
        }
        let targetQ = 0, targetPow = 0, xanchor = 'center', yanchor = 'bottom', xshift = 0, yshift = 4;
        if (pos) {
          targetQ = pos.x; targetPow = pos.y; xanchor = 'center'; yanchor = 'middle'; yshift = 0;
        } else {
          const lastIdx = Math.floor(sl.q.length * 0.82);
          targetQ = sl.q[lastIdx]; targetPow = pwrArr[lastIdx];
        }

        layout.annotations.push({
          x: targetQ, y: targetPow,
          text: `<b>P ${lineLabel}</b>`,
          showarrow: false, captureevents: true,
          font: { color: '#ffffff', size: 9, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.90)',
          bordercolor: col, borderwidth: 1, borderpad: 2,
          xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
          name: curveKey
        });
      });
    }
  }

  return { traces, layout };
}

/* ── Build NPSHr Chart ── */
function buildNpshChart(familyData, singleData) {
  const traces = [];
  let family = [];
  if (familyData && familyData.family) {
    family = familyData.family;
  } else if (familyData) {
    family = [{
      dia: familyData.pump?.impeller_dia_mm || (typeof PUMP_MAIN_DIA !== 'undefined' ? PUMP_MAIN_DIA : null) || 0,
      is_max: true,
      ratio: 1.0,
      q: familyData.q,
      h: familyData.h,
      eta: familyData.eta,
      power: familyData.power,
      npsh: familyData.npsh,
      bep: familyData.bep
    }];
  }

  const unitsN = getGraphDisplayUnits();
  const npshColor = unitsN.npshColor || '#39d3c0';
  const npshWeight = unitsN.npshWeight || 1.5;
  const npshStyle = unitsN.npshStyle || 'dashdot';

  const famType = familyData?.pump?.family_type || singleData?.pump?.family_type || 'trimmed_impeller';
  const isVarSpeed = (famType === 'variable_speed');
  const baseRpm = familyData?.pump?.speed_rpm || 1450;
  const baseDia = familyData?.pump?.impeller_dia_mm || 300;
  const formatFamLbl = (v) => isVarSpeed ? `${v} RPM` : `Ø${v} mm`;

  const chkRpmEl = typeof document !== 'undefined' ? document.getElementById('chkRpmOverlay') : null;
  const chkDiaEl = typeof document !== 'undefined' ? document.getElementById('chkDiaOverlay') : null;
  const chkRpm = chkRpmEl ? chkRpmEl.checked : isVarSpeed;
  const chkDia = chkDiaEl ? chkDiaEl.checked : !isVarSpeed;
  const showFamily = isVarSpeed ? (chkRpm || (!chkRpm && !chkDia)) : (chkDia || (!chkRpm && !chkDia));

  if (showFamily) {
    family.forEach((fam, idx) => {
      const isMax = fam.is_max;
      const showInLegend = (unitsN.legendMode === 'curve_labels') ? (idx === 0) : (unitsN.legendMode === 'each');
      const lblText = formatFamLbl(fam.dia);
      const traceName = (unitsN.legendMode === 'curve_labels') ? 'NPSHr' : `NPSHr ${lblText}`;

      traces.push({
        type: 'scatter', mode: 'lines',
        name: traceName,
        x: fam.q, y: fam.npsh,
        line: { color: npshColor, width: isMax ? (npshWeight + 0.7) : npshWeight, dash: npshStyle },
        showlegend: showInLegend,
        hovertemplate: `${lblText}<br>Q=%{x:.1f} m³/h<br>NPSHr=%{y:.2f} m<extra></extra>`
      });
    });
  }

  /* ── Overlay Speed / Impeller Trims on NPSHr Chart ── */
  const spdLinesN = getActiveOverlayLines(familyData);
  if (spdLinesN.length > 0) {
    spdLinesN.forEach((sl, i) => {
      const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
      const lineLabel = sl.label || '';

      if (sl.npsh) {
        traces.push({
          type: 'scatter', mode: 'lines',
          name: `NPSHr ${lineLabel}`,
          x: sl.q, y: sl.npsh,
          line: { color: col, width: 1.5, dash: 'dashdot' },
          showlegend: false,
          hovertemplate: `${lineLabel} NPSHr<br>Q=%{x:.1f} m³/h<br>NPSHr=%{y:.2f} m<extra></extra>`
        });
      }
    });
  }

  const layout = makeLayout('Flow Q (m³/h)', 'NPSHr (m)');
  layout.yaxis.rangemode = 'tozero';
  if (unitsN.legendMode === 'hq_only' || unitsN.legendMode === 'curve_labels') {
    layout.showlegend = false;
  }

  // Add direct curve label badges if Mode 3 (curve_labels) is active
  if (unitsN.legendMode === 'curve_labels') {
    layout.annotations = layout.annotations || [];
    const drawnBadgeKeysN = new Set();
    const baseRpm = familyData?.pump?.speed_rpm || 1450;
    const baseDia = familyData?.pump?.impeller_dia_mm || 300;

    if (showFamily) {
      family.forEach((fam, idx) => {
        if (!fam.q || fam.q.length === 0 || !fam.npsh || !fam.dia || fam.dia <= 0) return;
        const col = DIA_BLUES[Math.min(idx, DIA_BLUES.length - 1)];
        const vKey = (isVarSpeed ? 'rpm_' : 'dia_') + Math.round(fam.dia);
        drawnBadgeKeysN.add(vKey);
        const lblText = formatCurveLabel(fam.dia, fam.ratio, isVarSpeed, unitsN.labelFormat, baseDia, baseRpm);
        if (!lblText) return;
        const curveKey = `npsh_${lblText}`;
        const altKey = lblText;

        const annName = (isVarSpeed ? 'npsh_spd_' : 'npsh_dia_') + idx;
        const candidateKeys = [annName, `npsh_dia_${idx}`, curveKey, altKey, `npsh_${lblText}`];
        let pos = null;
        if (customLabelPositions && typeof customLabelPositions === 'object') {
          for (const k of candidateKeys) {
            if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
              pos = customLabelPositions[k]; break;
            }
          }
        }

        let targetQ = 0, targetNpsh = 0, xanchor = 'center', yanchor = 'bottom', xshift = 0, yshift = 4;
        if (pos) {
          targetQ = pos.x;
          targetNpsh = pos.y;
          xanchor = 'center'; yanchor = 'middle'; xshift = 0; yshift = 0;
        } else {
          const lastIdx = Math.floor(fam.q.length * 0.78);
          targetQ = fam.q[lastIdx];
          targetNpsh = fam.npsh[lastIdx];
        }

        layout.annotations.push({
          x: targetQ, y: targetNpsh,
          text: `<b>${lblText}</b>`,
          showarrow: false, captureevents: true,
          font: { color: '#ffffff', size: 9.5, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(22, 27, 34, 0.92)',
          bordercolor: col, borderwidth: 1.5, borderpad: 3,
          xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
          name: annName
        });
      });
    }

    if (spdLinesN.length > 0) {
      spdLinesN.forEach((sl, i) => {
        if (!sl.q || sl.q.length === 0 || !sl.npsh) return;
        const isRpm = (sl.speed_rpm !== undefined) || (sl.label && sl.label.toLowerCase().includes('rpm')) || (sl.val && sl.val > 100);
        const slVal = Math.round(sl.val || sl.speed_rpm || sl.dia || (sl.speed_ratio ? (isRpm ? baseRpm * sl.speed_ratio : baseDia * sl.speed_ratio) : 0));
        if (slVal <= 0) return;
        const vKey = (isRpm ? 'rpm_' : 'dia_') + slVal;
        if (drawnBadgeKeysN.has(vKey)) return;
        drawnBadgeKeysN.add(vKey);

        const col = SPD_COLORS[Math.min(i, SPD_COLORS.length - 1)];
        const lineLabel = formatCurveLabel(sl.val || sl.speed_rpm || sl.dia, sl.speed_ratio || sl.ratio, isRpm, unitsN.labelFormat, baseDia, baseRpm);
        if (!lineLabel) return;
        const curveKey = `npsh_spd_${i}`;
        const candidateKeys = [curveKey, `spd_lbl_${i}`, lineLabel, `npsh_${lineLabel}`];
        let pos = null;
        if (customLabelPositions && typeof customLabelPositions === 'object') {
          for (const k of candidateKeys) {
            if (customLabelPositions[k] && customLabelPositions[k].x !== undefined) {
              pos = customLabelPositions[k]; break;
            }
          }
        }
        let targetQ = 0, targetNpsh = 0, xanchor = 'center', yanchor = 'bottom', xshift = 0, yshift = 4;
        if (pos) {
          targetQ = pos.x; targetNpsh = pos.y; xanchor = 'center'; yanchor = 'middle'; yshift = 0;
        } else {
          const lastIdx = Math.floor(sl.q.length * 0.78);
          targetQ = sl.q[lastIdx]; targetNpsh = sl.npsh[lastIdx];
        }

        layout.annotations.push({
          x: targetQ, y: targetNpsh,
          text: `<b>${lineLabel}</b>`,
          showarrow: false, captureevents: true,
          font: { color: '#ffffff', size: 9, family: 'Arial, sans-serif' },
          bgcolor: 'rgba(15, 23, 42, 0.90)',
          bordercolor: col, borderwidth: 1, borderpad: 2,
          xanchor: xanchor, yanchor: yanchor, xshift: xshift, yshift: yshift,
          name: curveKey
        });
      });
    }
  }

  return { traces, layout };
}

function buildOverlayChart(data, showEff, showPow, showNpsh) {
  const traces = [];
  traces.push({
    type: 'scatter', mode: 'lines', name: 'H-Q',
    x: data.q, y: data.h, line: { color: '#58a6ff', width: 3 },
    hovertemplate: 'Q=%{x:.1f}<br>H=%{y:.2f} m<extra></extra>'
  });
  if (data.system_h) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'System Curve',
      x: data.q, y: data.system_h, line: { color: '#bc8cff', width: 2, dash: 'dash' },
      hovertemplate: 'Q=%{x:.1f}<br>H_sys=%{y:.2f}<extra></extra>'
    });
  }
  if (showEff) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'η (%)', yaxis: 'y2',
      x: data.q, y: data.eta, line: { color: '#f0c040', width: 2, dash: 'longdash' },
      hovertemplate: 'η=%{y:.1f}%<extra></extra>'
    });
  }
  if (showPow && data.power) {
    const pMax = Math.max(...data.power), hMax = Math.max(...data.h);
    const sc = pMax > 0 ? hMax / pMax * 0.55 : 1;
    traces.push({
      type: 'scatter', mode: 'lines', name: 'Power (scaled)',
      x: data.q, y: data.power.map(p => p * sc),
      line: { color: '#f85149', width: 1.5, dash: 'dot' },
      customdata: data.power,
      hovertemplate: 'P=%{customdata:.2f} kW<extra></extra>'
    });
  }
  if (showNpsh) {
    const useY2 = !showEff && !showPow;
    traces.push({
      type: 'scatter', mode: 'lines', name: 'NPSHr', yaxis: useY2 ? 'y2' : 'y1',
      x: data.q, y: data.npsh, line: { color: '#39d3c0', width: 2, dash: 'dashdot' },
      hovertemplate: 'NPSHr=%{y:.2f} m<extra></extra>'
    });
  }
  if (data.bep) {
    traces.push({
      type: 'scatter', mode: 'markers', name: 'BEP',
      x: [data.bep.q], y: [data.bep.h],
      marker: { size: 10, color: '#3fb950', symbol: 'star', line: { color: '#fff', width: 1 } },
      hovertemplate: `BEP Q=${data.bep.q} H=${data.bep.h}<extra></extra>`
    });
  }
  const layout = Object.assign({}, PLOTLY_LAYOUT_BASE, {
    xaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.xaxis, { title: 'Flow Q (m³/h)' }),
    yaxis: Object.assign({}, PLOTLY_LAYOUT_BASE.yaxis, { title: 'Head H (m)', rangemode: 'tozero' }),
  });
  applyAxisScaleSettings(layout.xaxis, 'flow', data?.pump);
  applyAxisScaleSettings(layout.yaxis, 'head', data?.pump);
  if (showEff) {
    layout.yaxis2 = {
      title: 'Efficiency η (%)', overlaying: 'y', side: 'right',
      range: [0, 105], showgrid: false,
      titlefont: { color: '#f0c040', size: 12 }, tickfont: { color: '#f0c040' },
      ticksuffix: '%'
    };
    applyAxisScaleSettings(layout.yaxis2, 'eff', data?.pump);
  } else if (showNpsh) {
    layout.yaxis2 = {
      title: 'NPSHr (m)', overlaying: 'y', side: 'right',
      rangemode: 'tozero', showgrid: false,
      titlefont: { color: '#39d3c0', size: 12 }, tickfont: { color: '#39d3c0' }
    };
    applyAxisScaleSettings(layout.yaxis2, 'npsh', data?.pump);
  }
  return { traces, layout };
}

/* ── Performance summary table ───────────────────────────────────────────── */
function renderPerfSummary(warmanData, containerId) {
  const family = warmanData.family || [];
  const baseDia = warmanData.pump?.impeller_dia_mm || 1.0;

  let htmlRows = '';

  // 1. Auto-generated family curves
  family.forEach((d, i) => {
    const b = d.bep || {};
    const col = DIA_BLUES[Math.min(i, DIA_BLUES.length - 1)];
    let rowLabel;
    if (d.is_max) {
      // Use the user-specified main curve label/diameter if available
      const mainLabel = (typeof PUMP_MAIN_LABEL !== 'undefined' && PUMP_MAIN_LABEL)
        ? PUMP_MAIN_LABEL
        : '';
      const mainDia = (typeof PUMP_MAIN_DIA !== 'undefined' && PUMP_MAIN_DIA)
        ? PUMP_MAIN_DIA
        : d.dia;
      const diaStr = `Ø${mainDia} mm`;
      rowLabel = mainLabel
        ? `<strong>${diaStr}</strong> <span class="text-muted small">(${mainLabel})</span>`
        : `<strong>${diaStr}</strong>`;
    } else {
      rowLabel = `<strong>Ø${d.dia} mm</strong>`;
    }

    htmlRows += `<tr>
      <td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${col};margin-right:6px;"></span>
        ${rowLabel}${d.is_max ? ' <span class="badge bg-secondary ms-1" style="font-size:0.65rem">BASE</span>' : ''}</td>
      <td class="text-center">${(d.ratio * 100).toFixed(1)}%</td>
      <td class="text-center fw-semibold">${b.q ?? '—'}</td>
      <td class="text-center">${b.h ?? '—'}</td>
      <td class="text-center text-warning fw-semibold">${b.eta ?? '—'}%</td>
      <td class="text-center">${b.power ?? '—'}</td>
    </tr>`;
  });

  // 2. Manually entered custom / additional curves
  const fittedCustom = customCurves.filter(c => c.fitted);
  fittedCustom.forEach(c => {
    let bepQ = '—', bepH = '—', bepEta = '—', bepP = '—';
    if (c.eta && c.eta.length) {
      const maxEta = Math.max(...c.eta);
      const idx = c.eta.indexOf(maxEta);
      bepQ = c.q[idx]?.toFixed(1) ?? '—';
      bepH = c.h[idx]?.toFixed(2) ?? '—';
      bepEta = c.eta[idx]?.toFixed(1) ?? '—';
      bepP = c.power?.[idx]?.toFixed(2) ?? '—';
    }

    const dia = c.diameter || null;
    const ratioStr = dia ? `${((dia / baseDia) * 100).toFixed(1)}%` : '—';
    const labelStr = dia ? `<strong>Ø${dia} mm</strong> (Manual)` : `<strong>${c.label}</strong>`;

    htmlRows += `<tr>
      <td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c.color};margin-right:6px;"></span>
        ${labelStr}</td>
      <td class="text-center">${ratioStr}</td>
      <td class="text-center fw-semibold">${bepQ}</td>
      <td class="text-center">${bepH}</td>
      <td class="text-center text-warning fw-semibold">${bepEta}%</td>
      <td class="text-center">${bepP}</td>
    </tr>`;
  });

  if (!family.length && !fittedCustom.length) {
    document.getElementById(containerId).innerHTML = '<p class="text-muted">No data.</p>';
    return;
  }

  document.getElementById(containerId).innerHTML = `
    <div class="table-responsive">
      <table class="table table-dark table-hover align-middle mb-0" style="font-size:0.88rem">
        <thead><tr>
          <th>Impeller</th>
          <th class="text-center">Trim %</th>
          <th class="text-center">Q<sub>BEP</sub> (m³/h)</th>
          <th class="text-center">H<sub>BEP</sub> (m)</th>
          <th class="text-center">η<sub>BEP</sub></th>
          <th class="text-center">P<sub>BEP</sub> (kW)</th>
        </tr></thead>
        <tbody>${htmlRows}</tbody>
      </table>
    </div>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM CURVES MODULE
   ══════════════════════════════════════════════════════════════════════════ */

const CUSTOM_COLORS = [
  '#58a6ff', // blue
  '#3fb950', // green
  '#f0c040', // yellow
  '#f85149', // red
  '#bc8cff', // purple
  '#39d3c0', // teal
  '#ff9900', // orange
  '#e879f9', // pink
];

let customCurves = [];   // [{id, label, color, q, h, eta, fitted}]
let _curveIdCounter = 0;

/* ── Parse user-entered data text ────────────────────────────────────────── */
function parseDataText(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
  const q_h = [], q_eta = [];
  for (const line of lines) {
    const parts = line.split(/[\s,;]+/).map(Number);
    if (parts.length >= 2 && !parts.some(isNaN)) {
      q_h.push([parts[0], parts[1]]);
      if (parts.length >= 3 && !isNaN(parts[2])) {
        q_eta.push([parts[0], parts[2]]);
      }
    }
  }
  return { q_h, q_eta };
}

/* ── Update the curve-count badge ─────────────────────────────────────────── */
function updateCurveCountBadge() {
  const badge = document.getElementById('customCurveCount');
  const n = customCurves.filter(c => c.fitted).length;
  badge.textContent = n;
  badge.style.display = n > 0 ? '' : 'none';
  document.getElementById('customCurvesEmpty').style.display =
    customCurves.length === 0 ? '' : 'none';
}

function getUnitLabel(type, unitValue) {
  if (!unitValue) {
    if (type === 'q') return 'm³/h';
    if (type === 'h' || type === 'npsh') return 'm';
    if (type === 'pow') return 'kW';
    if (type === 'dia') return 'mm';
    return '';
  }
  if (type === 'q') {
    if (unitValue === 'm3h') return 'm³/h';
    if (unitValue === 'ls') return 'L/s';
    if (unitValue === 'gpm') return 'gpm';
    if (unitValue === 'lmin') return 'L/min';
  }
  if (type === 'h' || type === 'npsh') {
    if (unitValue === 'm') return 'm';
    if (unitValue === 'ft') return 'ft';
  }
  if (type === 'pow') {
    if (unitValue === 'kw') return 'kW';
    if (unitValue === 'hp') return 'hp';
  }
  if (type === 'dia') {
    if (unitValue === 'mm') return 'mm';
    if (unitValue === 'in') return 'in';
    if (unitValue === 'm') return 'm';
  }
  return unitValue;
}

const CURVE_CONVERSIONS = {
  q: { m3h: 1.0, ls: 0.2777777777777778, gpm: 4.402917396, lmin: 16.6666666667 },
  h: { m: 1.0, ft: 3.280839895 },
  npsh: { m: 1.0, ft: 3.280839895 },
  pow: { kw: 1.0, hp: 1.34102209 }
};

/* ── Build Plotly traces for a fitted custom curve ───────────────────────── */
function buildCustomTraces(curve) {
  if (!curve.fitted) return [];
  const { label, color, weight, style, use_custom_style, style_mode, q, h, eta } = curve;
  const units = getGraphDisplayUnits();
  const fQ = CURVE_CONVERSIONS.q[units.q] || 1.0;
  const fH = CURVE_CONVERSIONS.h[units.h] || 1.0;
  const labelH = typeof getUnitLabel === 'function' ? getUnitLabel('h', units.h) : units.h;

  const useCustom = use_custom_style || style_mode === 'custom';
  const cColor = useCustom && color ? color : units.headColor;
  const cWeight = useCustom && weight ? weight : units.headWeight;
  const cStyle = useCustom && style ? style : units.headStyle;

  const qConv = q.map(v => v * fQ);
  const hConv = h.map(v => v * fH);

  const traces = [];

  // H-Q line (drawn solid to match the impeller family)
  traces.push({
    type: 'scatter', mode: 'lines',
    name: label || 'Custom',
    x: qConv, y: hConv,
    line: { color: cColor, width: cWeight, dash: cStyle },
    legendgroup: `custom_${curve.id}`,
    hovertemplate: `${label || 'Custom'}<br>Q=%{x:.1f}<br>H=%{y:.2f} ${labelH}<extra></extra>`,
  });

  // η line (if available)
  if (eta && eta.length) {
    traces.push({
      type: 'scatter', mode: 'lines',
      name: `${label || 'Custom'} η`,
      x: qConv, y: eta,
      line: { color, width: 1.5, dash: 'dot' },
      legendgroup: `custom_${curve.id}`,
      hovertemplate: `${label || 'Custom'}<br>η=%{y:.1f}%<extra></extra>`,
      showlegend: false,
    });
  }

  return traces;
}

/* ── Get all custom traces (optionally filtered for a yaxis) ─────────────── */
function getCustomTracesHQ() {
  return customCurves.flatMap(c => buildCustomTraces(c).filter(t => !t.yaxis || t.yaxis === 'y'));
}

function getCustomTracesEta() {
  const units = getGraphDisplayUnits();
  const fQ = CURVE_CONVERSIONS.q[units.q] || 1.0;
  return customCurves.flatMap(c => {
    if (!c.fitted || !c.eta || !c.eta.length) return [];
    return [{
      type: 'scatter', mode: 'lines',
      name: `${c.label || 'Custom'} η`,
      x: c.q.map(v => v * fQ), y: c.eta,
      line: { color: c.color, width: 1.8, dash: 'dashdot' },
      legendgroup: `custom_${c.id}`,
      hovertemplate: `${c.label || 'Custom'}<br>η=%{y:.1f}%<extra></extra>`,
    }];
  });
}

function getCustomTracesPower() {
  const units = getGraphDisplayUnits();
  const fQ = CURVE_CONVERSIONS.q[units.q] || 1.0;
  const fP = CURVE_CONVERSIONS.pow[units.pow] || 1.0;
  const labelP = typeof getUnitLabel === 'function' ? getUnitLabel('pow', units.pow) : units.pow;
  return customCurves.flatMap(c => {
    if (!c.fitted || !c.power || !c.power.length) return [];
    return [{
      type: 'scatter', mode: 'lines',
      name: `${c.label || 'Custom'} P`,
      x: c.q.map(v => v * fQ), y: c.power.map(v => v * fP),
      line: { color: c.color, width: 1.8, dash: 'dashdot' },
      legendgroup: `custom_${c.id}`,
      hovertemplate: `${c.label || 'Custom'}<br>P=%{y:.2f} ${labelP}<extra></extra>`,
    }];
  });
}

/* ── Fit a custom curve via the existing API endpoint ────────────────────── */
async function fitCustomCurve(curveId) {
  const curve = customCurves.find(c => c.id === curveId);
  if (!curve) return;

  const entry = document.getElementById(`curve-entry-${curveId}`);
  const statusEl = entry.querySelector('.curve-status');
  const plotBtn = entry.querySelector('.btn-plot-curve');
  const textarea = entry.querySelector('.curve-data-input');

  const { q_h, q_eta } = parseDataText(textarea.value);

  if (q_h.length < 3) {
    statusEl.className = 'curve-status error';
    statusEl.textContent = '✗ Need at least 3 Q,H data points';
    return;
  }

  statusEl.className = 'curve-status busy';
  statusEl.textContent = '⟳ Fitting curve…';
  plotBtn.disabled = true;

  const payload = { q_h };
  if (q_eta.length >= 3) payload.q_eta = q_eta;
  else {
    // Synthesise flat η so the API doesn't reject
    payload.q_eta = q_h.map(([q]) => [q, 70]);
  }

  try {
    const res = await fetch('/papi/fit-curves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await res.json();

    if (!d.ok) {
      statusEl.className = 'curve-status error';
      statusEl.textContent = `✗ ${d.error || 'Fit failed'}`;
      return;
    }

    // Evaluate smooth curve from coefficients
    const qMax = d.q_max;
    const qArr = Array.from({ length: 80 }, (_, i) => (i / 79) * qMax);
    const evalP = (coeffs, q) => coeffs.reduce((s, c, i) => s + c * Math.pow(q, i), 0);
    const a = [d.hq_a0, d.hq_a1, d.hq_a2, d.hq_a3];
    const b = [d.eff_b0, d.eff_b1, d.eff_b2, d.eff_b3];
    const pp = [d.pow_p0, d.pow_p1, d.pow_p2];

    curve.q = qArr.map(q => Math.round(q * 100) / 100);
    curve.h = qArr.map(q => Math.max(0, evalP(a, q)));
    curve.eta = q_eta.length >= 3 ? qArr.map(q => Math.max(0, Math.min(100, evalP(b, q)))) : null;
    curve.power = qArr.map(q => Math.max(0, evalP(pp, q)));
    curve.fitted = true;

    // Also store raw points for scatter markers
    curve.raw_q_h = q_h;
    curve.raw_q_eta = q_eta.length >= 3 ? q_eta : null;

    statusEl.className = 'curve-status ok';
    statusEl.textContent = `✓ Fitted — Q_max=${d.q_max.toFixed(1)}, η_BEP=${d.eta_bep}%, R²(H)=${d.r2_hq}`;

    updateCurveCountBadge();
    renderAll();   // re-render all charts with the new curve

  } catch (e) {
    statusEl.className = 'curve-status error';
    statusEl.textContent = `✗ Network error: ${e.message}`;
  } finally {
    plotBtn.disabled = false;
  }
}

/* ── Add a new curve UI row ──────────────────────────────────────────────── */
function addCustomCurveRow() {
  const id = ++_curveIdCounter;
  const color = CUSTOM_COLORS[(id - 1) % CUSTOM_COLORS.length];

  customCurves.push({ id, label: `Curve ${id}`, color, fitted: false });

  const list = document.getElementById('customCurvesList');
  const div = document.createElement('div');
  div.className = 'custom-curve-entry';
  div.id = `curve-entry-${id}`;

  const colorSwatches = CUSTOM_COLORS.map((c, ci) =>
    `<span class="curve-color-swatch ${c === color ? 'active' : ''}"
          style="background:${c}"
          data-color="${c}"
          data-curve-id="${id}"
          title="${c}"></span>`
  ).join('');

  div.innerHTML = `
    <div class="d-flex align-items-start gap-3">
      <div class="flex-grow-1">
        <!-- Header row -->
        <div class="d-flex align-items-center gap-2 mb-2">
          <span class="curve-color-dot"
                style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${color};flex-shrink:0"></span>
          <input type="text" class="form-control form-control-sm form-control-dark curve-label-input"
                 value="Curve ${id}" placeholder="Label"
                 style="max-width:160px;font-weight:600"
                 data-curve-id="${id}">
          <span class="text-muted small ms-1">Color:</span>
          <div class="d-flex gap-1 align-items-center flex-wrap" id="swatches-${id}">
            ${colorSwatches}
          </div>
          <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1 ms-auto btn-remove-curve"
                  data-curve-id="${id}" title="Remove curve">×</button>
        </div>
        <!-- Data entry -->
        <div class="row g-2">
          <div class="col-12">
            <label class="form-label form-label-sm text-muted mb-1">
              Q, H data pairs <span class="text-muted fw-normal">(one per line: <code style="color:#8b949e">100, 45.2</code> — optionally add η: <code style="color:#8b949e">100, 45.2, 78</code>)</span>
            </label>
            <textarea class="form-control curve-data-input w-100" rows="5"
                      placeholder="0, 55&#10;50, 52&#10;100, 45&#10;150, 34&#10;200, 18&#10;220, 0"
                      id="curve-data-${id}"></textarea>
          </div>
        </div>
        <!-- Status + action -->
        <div class="d-flex align-items-center gap-2 mt-2">
          <button type="button" class="btn btn-sm btn-primary btn-plot-curve" data-curve-id="${id}">
            <i class="bi bi-graph-up me-1"></i>Plot
          </button>
          <span class="curve-status" id="curve-status-${id}"></span>
        </div>
      </div>
    </div>`;

  list.appendChild(div);

  // Bind color swatch clicks
  div.querySelectorAll('.curve-color-swatch').forEach(swatch => {
    swatch.addEventListener('click', () => {
      const cid = parseInt(swatch.dataset.curveId);
      const newColor = swatch.dataset.color;
      const curve = customCurves.find(c => c.id === cid);
      if (!curve) return;
      curve.color = newColor;
      div.querySelectorAll('.curve-color-swatch').forEach(s => s.classList.remove('active'));
      swatch.classList.add('active');
      div.querySelector('.curve-color-dot').style.background = newColor;
      if (curve.fitted) renderAll();
    });
  });

  // Bind label input
  div.querySelector('.curve-label-input').addEventListener('input', (e) => {
    const cid = parseInt(e.target.dataset.curveId);
    const curve = customCurves.find(c => c.id === cid);
    if (curve) {
      curve.label = e.target.value || `Curve ${cid}`;
      if (curve.fitted) renderAll();
    }
  });

  // Bind Plot button
  div.querySelector('.btn-plot-curve').addEventListener('click', (e) => {
    fitCustomCurve(parseInt(e.currentTarget.dataset.curveId));
  });

  // Bind Remove button
  div.querySelector('.btn-remove-curve').addEventListener('click', (e) => {
    const cid = parseInt(e.currentTarget.dataset.curveId);
    customCurves = customCurves.filter(c => c.id !== cid);
    document.getElementById(`curve-entry-${cid}`)?.remove();
    updateCurveCountBadge();
    renderAll();
  });

  updateCurveCountBadge();

  // Auto-open the collapse if not already open
  const body = document.getElementById('customCurvesBody');
  if (!body.classList.contains('show')) {
    new bootstrap.Collapse(body, { toggle: true });
  }
}


/* ══════════════════════════════════════════════════════════════════════════
   PUMP CURVE PAGE CONTROLLER
   ══════════════════════════════════════════════════════════════════════════ */

if (typeof PUMP_ID !== 'undefined') {

  let currentData = null;   // Warman chart data (family + isolines)
  let singleData = null;   // Single-dia curve data (max impeller)
  let viewMode = 'warman';

  /* ── Query params ──── */
  function getParams() {
    const liquid = document.getElementById('liquidSelect').value;
    const p = new URLSearchParams({ liquid });
    if (liquid === 'viscous') p.set('viscosity_cSt', document.getElementById('viscosity').value);
    if (liquid === 'slurry') {
      p.set('slurry_cv', document.getElementById('slurryCv').value);
      p.set('slurry_d50', document.getElementById('slurryD50').value);
      p.set('rho_solid', document.getElementById('rhoSolid').value);
    }
    const sh = document.getElementById('staticHead').value;
    const pk = document.getElementById('pipeK').value;
    if (parseFloat(sh) || parseFloat(pk)) {
      p.set('static_head', sh || 0);
      p.set('pipe_k', pk || 0);
    }

    const effL = document.getElementById('txtEffLevels')?.value || '';
    const tpVal = document.getElementById('numTrimPenalty')?.value;
    const powL = document.getElementById('txtPowerLevels')?.value || '';
    const npshL = document.getElementById('txtNpshLevels')?.value || '';
    if (effL) p.set('eff_levels', effL);
    if (tpVal !== undefined && tpVal !== '') p.set('trim_penalty', tpVal);
    if (powL) p.set('power_levels', powL);
    if (npshL) p.set('npsh_levels', npshL);

    const trimModel = document.querySelector('input[name="trimModelChoice"]:checked')?.value || 'fit';
    p.set('force_affinity', trimModel);

    return p;
  }

  function collectGraphOptions() {
    return {
      show_eff_iso: document.getElementById('chkShowEffIso')?.checked !== false,
      eff_levels: document.getElementById('txtEffLevels')?.value || '',
      trim_penalty: document.getElementById('numTrimPenalty')?.value !== '' && document.getElementById('numTrimPenalty')?.value !== undefined ? parseFloat(document.getElementById('numTrimPenalty')?.value) : null,
      show_power_iso: document.getElementById('chkShowPowerIso')?.checked || false,
      power_levels: document.getElementById('txtPowerLevels')?.value || '',
      show_npsh_iso: document.getElementById('chkShowNpshIso')?.checked || false,
      npsh_levels: document.getElementById('txtNpshLevels')?.value || '',
      show_npsh_curve: document.getElementById('chkShowNpshCurve')?.checked || false,
      npsh_yaxis: document.querySelector('input[name="npshYAxisChoice"]:checked')?.value || 'y2',
      show_speed_lines: document.getElementById('chkSpeedLines')?.checked || false,
      show_hq: document.getElementById('chkShowHQ')?.checked !== false,
      show_other: document.getElementById('chkShowOther')?.checked !== false,
      show_eff: document.getElementById('chkShowEff')?.checked !== false,
      show_power: document.getElementById('chkShowPower')?.checked !== false,
      show_npsh: document.getElementById('chkShowNpsh')?.checked !== false,
      combine_eff_power: document.getElementById('chkCombineEffPower')?.checked !== false,
      trim_model: document.querySelector('input[name="trimModelChoice"]:checked')?.value || 'fit',
      legend_mode: document.getElementById('selLegendMode')?.value || 'each',
      custom_label_pos: customLabelPositions
    };
  }

  function applyGraphOptions(opts) {
    if (!opts || typeof opts !== 'object') return;
    if (opts.custom_label_pos) {
      let pos = opts.custom_label_pos;
      if (typeof pos === 'string') {
        try { pos = JSON.parse(pos); } catch (e) { pos = null; }
      }
      if (pos && typeof pos === 'object' && Object.keys(pos).length > 0) {
        customLabelPositions = Object.assign({}, customLabelPositions, pos);
      }
    }
    if (opts.show_eff_iso !== undefined && document.getElementById('chkShowEffIso')) document.getElementById('chkShowEffIso').checked = opts.show_eff_iso;
    if (opts.eff_levels !== undefined && document.getElementById('txtEffLevels')) document.getElementById('txtEffLevels').value = opts.eff_levels;
    if (opts.trim_penalty !== undefined && opts.trim_penalty !== null && document.getElementById('numTrimPenalty')) document.getElementById('numTrimPenalty').value = opts.trim_penalty;

    if (opts.show_power_iso !== undefined && document.getElementById('chkShowPowerIso')) {
      document.getElementById('chkShowPowerIso').checked = opts.show_power_iso;
      const g = document.getElementById('groupPowerLevels');
      if (g) g.style.display = opts.show_power_iso ? '' : 'none';
    }
    if (opts.power_levels !== undefined && document.getElementById('txtPowerLevels')) document.getElementById('txtPowerLevels').value = opts.power_levels;

    if (opts.show_npsh_iso !== undefined && document.getElementById('chkShowNpshIso')) {
      document.getElementById('chkShowNpshIso').checked = opts.show_npsh_iso;
      const g = document.getElementById('groupNpshLevels');
      if (g) g.style.display = opts.show_npsh_iso ? '' : 'none';
    }
    if (opts.npsh_levels !== undefined && document.getElementById('txtNpshLevels')) document.getElementById('txtNpshLevels').value = opts.npsh_levels;

    if (opts.show_npsh_curve !== undefined && document.getElementById('chkShowNpshCurve')) {
      document.getElementById('chkShowNpshCurve').checked = opts.show_npsh_curve;
      const g = document.getElementById('groupNpshYAxis');
      if (g) g.style.display = opts.show_npsh_curve ? '' : 'none';
    }
    if (opts.npsh_yaxis && document.querySelector(`input[name="npshYAxisChoice"][value="${opts.npsh_yaxis}"]`)) {
      document.querySelector(`input[name="npshYAxisChoice"][value="${opts.npsh_yaxis}"]`).checked = true;
    }
    if (opts.show_speed_lines !== undefined && document.getElementById('chkSpeedLines')) document.getElementById('chkSpeedLines').checked = opts.show_speed_lines;
    if (opts.show_hq !== undefined && document.getElementById('chkShowHQ')) document.getElementById('chkShowHQ').checked = opts.show_hq;
    if (opts.show_other !== undefined && document.getElementById('chkShowOther')) document.getElementById('chkShowOther').checked = opts.show_other;
    if (opts.show_eff !== undefined && document.getElementById('chkShowEff')) document.getElementById('chkShowEff').checked = opts.show_eff;
    if (opts.show_power !== undefined && document.getElementById('chkShowPower')) document.getElementById('chkShowPower').checked = opts.show_power;
    if (opts.show_npsh !== undefined && document.getElementById('chkShowNpsh')) document.getElementById('chkShowNpsh').checked = opts.show_npsh;
    if (opts.combine_eff_power !== undefined && document.getElementById('chkCombineEffPower')) document.getElementById('chkCombineEffPower').checked = opts.combine_eff_power;
    if (opts.trim_model && document.querySelector(`input[name="trimModelChoice"][value="${opts.trim_model}"]`)) {
      document.querySelector(`input[name="trimModelChoice"][value="${opts.trim_model}"]`).checked = true;
    }
    if (opts.legend_mode && document.getElementById('selLegendMode')) {
      document.getElementById('selLegendMode').value = opts.legend_mode;
      const g = document.getElementById('groupCurveLabelPos');
      if (g) g.style.display = opts.legend_mode === 'curve_labels' ? '' : 'none';
    }
  }

  async function saveGraphOptions() {
    if (typeof PUMP_ID === 'undefined' || !PUMP_ID) return;
    const btn = document.getElementById('btnSaveGraphOptions');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…';
    }
    const opts = collectGraphOptions();
    try {
      const res = await fetch(`/papi/pump/${PUMP_ID}/graph-options`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(opts)
      });
      const json = await res.json();
      if (json.status === 'ok' && btn) {
        btn.className = 'btn btn-sm btn-success py-0 px-2';
        btn.innerHTML = '<i class="bi bi-check2 me-1"></i>Saved!';
        setTimeout(() => {
          btn.className = 'btn btn-sm btn-outline-accent py-0 px-2';
          btn.innerHTML = '<i class="bi bi-floppy me-1"></i>Save Options';
        }, 1500);
      }
    } catch (e) {
      console.error('Failed to save graph options:', e);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function getDuty() {
    return {
      q: parseFloat(document.getElementById('dutyQ').value) || null,
      h: parseFloat(document.getElementById('dutyH').value) || null,
    };
  }

  /* ── Liquid param panels ──── */
  function updateLiquidPanels() {
    const liquid = document.getElementById('liquidSelect').value;
    document.querySelectorAll('.liquid-param').forEach(el => {
      el.style.display = el.classList.contains(liquid) ? '' : 'none';
    });
  }

  /* ── Render all charts for current display option (+ custom curves) ──── */
  function renderAll() {
    const duty = getDuty();
    const customHQ = getCustomTracesHQ();
    const customEta = getCustomTracesEta();
    const customPow = getCustomTracesPower();

    const showHQ = document.getElementById('chkShowHQ')?.checked !== false;
    const showEffIso = document.getElementById('chkShowEffIso').checked;
    const showPowerIso = document.getElementById('chkShowPowerIso').checked;
    const showNpshIso = document.getElementById('chkShowNpshIso').checked;
    const showNpshCurve = document.getElementById('chkShowNpshCurve').checked;
    const showSpeedLines = (document.getElementById('chkRpmOverlay')?.checked || document.getElementById('chkSpeedLines')?.checked) || false;
    const showDiaOverlay = document.getElementById('chkDiaOverlay')?.checked || false;

    // Toggle main Performance Map panel
    if (document.getElementById('warmanPanel')) {
      document.getElementById('warmanPanel').style.display = showHQ ? '' : 'none';
    }

    // Toggle custom inputs visibility based on checkboxes
    document.getElementById('groupEffLevels').style.display = showEffIso ? '' : 'none';
    document.getElementById('groupPowerLevels').style.display = showPowerIso ? '' : 'none';
    document.getElementById('groupNpshLevels').style.display = showNpshIso ? '' : 'none';
    document.getElementById('groupNpshYAxis').style.display = showNpshCurve ? '' : 'none';

    const npshYAxis = document.querySelector('input[name="npshYAxisChoice"]:checked')?.value || 'y2';

    // Ensure family subpanels are hidden
    if (document.getElementById('npshFamilyPanel')) document.getElementById('npshFamilyPanel').style.display = 'none';
    if (document.getElementById('powerFamilyPanel')) document.getElementById('powerFamilyPanel').style.display = 'none';

    // RENDER MAIN Performance Map
    if (currentData) {
      const wc = buildWarmanChart(currentData, {
        showIsolines: showEffIso,
        showPowerIso: showPowerIso,
        showNpshIso: showNpshIso,
        showSpeedLines: showSpeedLines,
        showDiaOverlay: showDiaOverlay,
        showNpshCurve: showNpshCurve,
        npshYAxis: npshYAxis,
        dutyQ: duty.q, dutyH: duty.h
      });
      Plotly.react('chartWarman', [...wc.traces, ...customHQ], wc.layout, PLOTLY_CONFIG);
      if (wc.layout.annotations && wc.layout.annotations.length > 0) {
        makeAnnotationsDraggable('chartWarman', wc.layout.annotations, PUMP_ID);
      }
      renderPerfSummary(currentData, 'perfSummary');
    }

    // Toggle additional performance graphs below
    const showOther = document.getElementById('chkShowOther').checked;
    document.getElementById('standalonePanels').style.display = showOther ? '' : 'none';
    document.getElementById('otherGraphsOptions').style.display = showOther ? '' : 'none';

    if (showOther && currentData) {
      const showEff = document.getElementById('chkShowEff')?.checked;
      const showPower = document.getElementById('chkShowPower')?.checked;
      const showNpsh = document.getElementById('chkShowNpsh')?.checked;
      const combineEffPower = document.getElementById('chkCombineEffPower')?.checked;

      const showClean = currentData.liquid !== 'water';

      // Toggle panel columns
      if (document.getElementById('panelHQ')) document.getElementById('panelHQ').style.display = 'none';
      document.getElementById('panelEffPower').style.display = (showEff && showPower && combineEffPower) ? '' : 'none';
      document.getElementById('panelEff').style.display = (showEff && (!showPower || !combineEffPower)) ? '' : 'none';
      document.getElementById('panelPower').style.display = (showPower && (!showEff || !combineEffPower)) ? '' : 'none';
      document.getElementById('panelNpsh').style.display = showNpsh ? '' : 'none';

      if (showEff && showPower && combineEffPower) {
        const effPow = buildEffPowerChart(currentData, singleData, showClean);
        Plotly.react('chartEffPower', [...effPow.traces, ...customEta, ...customPow], effPow.layout, PLOTLY_CONFIG);
        if (effPow.layout.annotations) makeAnnotationsDraggable('chartEffPower', effPow.layout.annotations, PUMP_ID);
      } else {
        if (showEff) {
          const eff = buildEffChart(currentData, singleData, showClean);
          Plotly.react('chartEff', [...eff.traces, ...customEta], eff.layout, PLOTLY_CONFIG);
          if (eff.layout.annotations) makeAnnotationsDraggable('chartEff', eff.layout.annotations, PUMP_ID);
        }
        if (showPower) {
          const power = buildPowerChart(currentData, singleData, showClean);
          Plotly.react('chartPower', [...power.traces, ...customPow], power.layout, PLOTLY_CONFIG);
          if (power.layout.annotations) makeAnnotationsDraggable('chartPower', power.layout.annotations, PUMP_ID);
        }
      }

      if (showNpsh) {
        const npsh = buildNpshChart(currentData, singleData);
        Plotly.react('chartNpsh', npsh.traces, npsh.layout, PLOTLY_CONFIG);
        if (npsh.layout.annotations) makeAnnotationsDraggable('chartNpsh', npsh.layout.annotations, PUMP_ID);
      }
    }
  }

  /* ── Custom curve summary table below the standard perfSummary ──────────── */
  function renderCustomSummary() {
    // Disabled - custom/additional curves are now grouped in the main perfSummary table
  }

  /* ── Fetch both endpoints in parallel ──── */
  async function fetchAndRender() {
    const params = getParams();
    const btn = document.getElementById('btnUpdate');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading…';

    try {
      const [warmanRes, singleRes] = await Promise.all([
        fetch(`/papi/warman-chart/${PUMP_ID}?${params}`),
        fetch(`/papi/curve-data/${PUMP_ID}?${params}`)
      ]);
      currentData = await warmanRes.json();
      singleData = await singleRes.json();
      if (currentData && currentData.default_trim_penalty !== undefined) {
        const numTP = document.getElementById('numTrimPenalty');
        if (numTP) numTP.placeholder = `Auto (${currentData.default_trim_penalty}%)`;
      }
      if (currentData && currentData.graph_options) {
        applyGraphOptions(currentData.graph_options);
      }
      renderAll();
    } catch (e) {
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Update';
    }
  }

  const isCurvesPage = !!document.getElementById('btnUpdate');
  if (isCurvesPage) {
    const onOptionChange = () => {
      renderAll();
      saveGraphOptions();
    };
    const onOptionFetchChange = () => {
      fetchAndRender();
      saveGraphOptions();
    };

    // Bind change event to checkboxes and select dropdowns that change overlays
    ['chkShowHQ', 'chkShowEffIso', 'chkShowPowerIso', 'chkShowNpshIso', 'chkShowNpshCurve', 'chkSpeedLines', 'chkShowOther', 'selLegendMode'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', () => {
          if (id === 'chkShowEffIso') {
            const g = document.getElementById('groupEffLevels');
            if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
          }
          if (id === 'chkShowPowerIso') {
            const g = document.getElementById('groupPowerLevels');
            if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
          }
          if (id === 'chkShowNpshIso') {
            const g = document.getElementById('groupNpshLevels');
            if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
          }
          if (id === 'chkShowNpshCurve') {
            const g = document.getElementById('groupNpshYAxis');
            if (g) { g.style.display = el.checked ? '' : 'none'; g.classList.toggle('hidden', !el.checked); }
          }
          if (id === 'selLegendMode') {
            const g = document.getElementById('groupCurveLabelPos');
            if (g) g.style.display = el.value === 'curve_labels' ? '' : 'none';
          }
          onOptionChange();
        });
        if (id === 'txtCurveLabelFlowPct') {
          el.addEventListener('input', onOptionChange);
          el.addEventListener('keyup', onOptionChange);
        }
      }
    });

    // Bind change event to other layout checkboxes & radios
    document.querySelectorAll('#otherGraphsOptions input[type="checkbox"], input[name="npshYAxisChoice"]').forEach(input => {
      input.addEventListener('change', onOptionChange);
    });

    document.querySelectorAll('input[name="trimModelChoice"]').forEach(input => {
      input.addEventListener('change', onOptionFetchChange);
    });

    // Bind change/keypress event to custom levels to automatically fetch
    ['txtEffLevels', 'txtPowerLevels', 'txtNpshLevels', 'numTrimPenalty'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', onOptionFetchChange);
        el.addEventListener('keypress', (e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            onOptionFetchChange();
          }
        });
      }
    });

    document.getElementById('liquidSelect').addEventListener('change', updateLiquidPanels);
    document.getElementById('btnUpdate').addEventListener('click', fetchAndRender);
    const saveOptBtn = document.getElementById('btnSaveGraphOptions');
    if (saveOptBtn) {
      saveOptBtn.addEventListener('click', saveGraphOptions);
    }

    const resetPosBtn = document.getElementById('btnResetLabelPos');
    if (resetPosBtn) {
      resetPosBtn.addEventListener('click', async () => {
        customLabelPositions = {};
        if (typeof PUMP_ID !== 'undefined' && PUMP_ID) {
          const opts = collectGraphOptions();
          opts.reset_label_pos = true;
          opts.custom_label_pos = {};
          try {
            await fetch(`/papi/pump/${PUMP_ID}/graph-options`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(opts)
            });
          } catch (e) { }
        }
        renderAll();
      });
    }

    // Custom curves: Add Curve button + chevron toggle
    document.getElementById('btnAddCurve').addEventListener('click', addCustomCurveRow);

    document.getElementById('customCurvesBody').addEventListener('show.bs.collapse', () => {
      document.getElementById('customCurvesChevron').className = 'bi bi-chevron-up';
    });
    document.getElementById('customCurvesBody').addEventListener('hide.bs.collapse', () => {
      document.getElementById('customCurvesChevron').className = 'bi bi-chevron-down';
    });

    // Initial setup: apply saved options from dataset if available
    const savedGraphOpts = document.getElementById('pump-meta')?.dataset.graphOptions;
    if (savedGraphOpts) {
      try {
        applyGraphOptions(JSON.parse(savedGraphOpts));
      } catch (e) { }
    }
    updateLiquidPanels();
    fetchAndRender();
  }
}
