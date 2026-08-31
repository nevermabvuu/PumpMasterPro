"""
routes/reports.py — Reports & Settings Blueprint

Beginners Note: This module manages PDF report configurations, supplier branding profiles,
HTML report template rendering, automated Action Bar injection, exact pump curve evaluation,
pump-data axis scale matching (min, max, major, minor), NPSH auto-detection, multi-curve display modes (all, max_only, min_max),
and 100% pixel-perfect PDF file generation via Headless Chromium.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, make_response
from models import db, Pump, Supplier, ReportConfig

CURVE_CONVERSIONS = {
    'q': {
        'm3h': 1.0,
        'ls': 0.2777777777777778,
        'gpm': 4.4028675393,
        'lmin': 16.666666666666668
    },
    'h': {
        'm': 1.0,
        'ft': 3.280839895
    },
    'pow': {
        'kw': 1.0,
        'hp': 1.3410220896
    },
    'npsh': {
        'm': 1.0,
        'ft': 3.280839895
    }
}
from pump_curves import hq_curve, efficiency_curve, power_curve, npsh_curve, bep_point
import numpy as np
from datetime import datetime
import os, sys, io, re, tempfile, subprocess, json

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# Human-readable labels for unit keys stored in the database
UNIT_DISPLAY_LABELS = {
    'q': {'m3h': 'm³/h', 'ls': 'L/s', 'gpm': 'US gpm', 'lmin': 'L/min'},
    'h': {'m': 'm', 'ft': 'ft'},
    'pow': {'kw': 'kW', 'hp': 'hp'},
    'npsh': {'m': 'm', 'ft': 'ft'}
}

def _unit_label(axis, key):
    """Return a human-readable unit label for a given axis and key."""
    return UNIT_DISPLAY_LABELS.get(axis, {}).get(key, key)


def render_pdf_with_headless_browser(html_content, output_path):
    """
    Beginners Note: Uses Headless Chromium (Chrome/Edge) to render 100% pixel-perfect PDF files.
    Because Headless Chromium uses the real browser rendering engine, all CSS styles, Tailwind classes,
    fonts, colors, and Plotly/SVG graphs match the browser preview 100% identically!
    """
    executables = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    ]
    browser_path = None
    for exe in executables:
        if os.path.exists(exe):
            browser_path = exe
            break
            
    if not browser_path:
        return False
        
    temp_html = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name
            
        file_uri = 'file:///' + temp_html.replace('\\', '/')
        cmd = [
            browser_path,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            '--no-pdf-header-footer',
            '--force-device-scale-factor=2',
            '--high-dpi-support=1',
            '--enable-font-antialiasing',
            '--font-render-hinting=max',
            '--window-size=2480,3508',
            '--virtual-time-budget=5000',
            f'--print-to-pdf={output_path}',
            file_uri
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print("Headless browser PDF rendering error:", e)
        return False
    finally:
        if temp_html and os.path.exists(temp_html):
            try:
                os.remove(temp_html)
            except Exception:
                pass


def _safe_float(val):
    if val is None or val == '':
        return None
    try:
        f = float(val)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None

def _safe_range_val(val, default_val):
    if val is None or val == '':
        return default_val
    try:
        return float(val)
    except (TypeError, ValueError):
        return default_val


def _clean_axis_scale(min_v, max_v, maj_v, minr_v, conv_factor=1.0, default_min=0.0, default_max=100.0):
    """
    Beginners Note: Normalizes axis scale bounds and intervals.
    - In pump-data and Plotly (applyAxisScaleSettings):
      majorVal = number of major divisions across [min, max] (dtick = (max - min) / majorVal).
      minorVal = number of subdivisions per major interval (minor.nticks = minorVal + 1).
    - If conv_factor == 1.0 (primary units / no conversion): strictly respects user-defined graph bounds and division step.
    - If conv_factor != 1.0 (display units converted): adapts intervals to the closest standard engineering round numbers
      (multiples of 1, 1.5, 2, 2.5, 5, 10 * 10^k) and expands max to the next clean multiple.
    """
    import math
    is_conv = abs(conv_factor - 1.0) > 1e-4

    raw_min = (float(min_v) * conv_factor) if min_v is not None else float(default_min)
    raw_max = (float(max_v) * conv_factor) if max_v is not None else (float(default_max) if default_max is not None else None)
    
    span = (raw_max - raw_min) if raw_max is not None else None
    
    # Calculate step size from major divisions (matching Plotly: dtick = span / majorVal)
    if maj_v is not None and float(maj_v) > 0 and span is not None and span > 0:
        raw_maj_step = span / float(maj_v)
    elif maj_v is not None and float(maj_v) > 0:
        raw_maj_step = float(maj_v) * conv_factor
    else:
        raw_maj_step = None

    # Calculate minor step size from minor subdivisions (matching Plotly: minor nticks = minorVal + 1)
    if minr_v is not None and float(minr_v) > 0 and raw_maj_step is not None:
        raw_minr_step = raw_maj_step / float(minr_v)
    elif minr_v is not None and float(minr_v) > 0:
        raw_minr_step = float(minr_v) * conv_factor
    else:
        raw_minr_step = None

    if not is_conv or raw_max is None or span is None or span <= 0:
        return {
            'min': raw_min,
            'max': raw_max,
            'major': raw_maj_step,
            'minor': raw_minr_step
        }

    target_step = raw_maj_step if (raw_maj_step and raw_maj_step > 0) else (span / 5.0)

    # Standard clean multipliers in any decade: 1, 1.5, 2, 2.5, 5, 10
    multipliers = [1.0, 1.5, 2.0, 2.5, 5.0, 10.0]
    mag = 10.0 ** math.floor(math.log10(target_step)) if target_step > 0 else 1.0
    candidates = []
    for m in [0.1, 1.0, 10.0]:
        for mult in multipliers:
            candidates.append(mult * mag * m)

    candidates = sorted(list(set([round(c, 6) for c in candidates if c > 0])))
    reasonable = [c for c in candidates if 2.5 <= (span / c) <= 12.0]
    if not reasonable:
        reasonable = candidates

    clean_step = min(reasonable, key=lambda c: abs(c - target_step))

    # Clean max: ceiling to the nearest multiple of clean_step so that all curve data fits and ends on a clean tick
    num_steps = math.ceil((raw_max - raw_min) / clean_step - 1e-5)
    clean_max = raw_min + num_steps * clean_step

    # Clean minor step
    clean_minor = None
    if minr_v is not None and float(minr_v) > 1 and clean_step and clean_step > 0:
        clean_minor = round(clean_step / float(minr_v), 4) if (clean_step / float(minr_v)) < 1 else round(clean_step / float(minr_v), 2)

    return {
        'min': raw_min,
        'max': clean_max,
        'major': clean_step,
        'minor': clean_minor
    }


def _calculate_axis_ticks(min_v, max_v, major_step=None):
    """
    Beginners Note: Calculates exact clean engineering major tick mark values (e.g. 0, 15, 30, 45, 60 or 0, 20, 40, 60, 80).
    Respects explicit major_step if provided and reasonable, otherwise auto-generates clean engineering ticks.
    """
    min_v = float(min_v)
    max_v = float(max_v)
    if min_v >= max_v:
        max_v = min_v + 10.0

    span = max_v - min_v

    # Check if user-provided major_step is valid and produces 2 to 14 ticks
    if major_step and major_step > 0:
        step = float(major_step)
        num_ticks = span / step
        if 2 <= num_ticks <= 14:
            ticks = []
            curr = min_v
            while curr <= max_v + (step * 0.05):
                ticks.append(round(curr, 4) if step < 1 else round(curr, 2))
                curr += step
            return ticks

    # Fallback auto clean engineering step calculation
    raw_step = span / 5.0
    magnitude = 10.0 ** np.floor(np.log10(raw_step)) if raw_step > 0 else 1.0
    normalized = raw_step / magnitude

    if normalized <= 1.2:
        clean_step = 1.0 * magnitude
    elif normalized <= 1.8:
        clean_step = 1.5 * magnitude
    elif normalized <= 2.2:
        clean_step = 2.0 * magnitude
    elif normalized <= 3.5:
        clean_step = 2.5 * magnitude
    elif normalized <= 7.5:
        clean_step = 5.0 * magnitude
    else:
        clean_step = 10.0 * magnitude

    ticks = []
    curr = min_v
    while curr <= max_v + (clean_step * 0.05):
        ticks.append(round(curr, 4) if clean_step < 1 else round(curr, 2))
        curr += clean_step

    return ticks


def _parse_diameters_string(raw_str):
    """
    Beginners Note: Parses diameters from string input, supporting semicolon (;), pipe (|), comma (,), space, or units.
    Example: "228;213;197;182" or "228.0;mm|182;mm" -> [228.0, 213.0, 197.0, 182.0]
    """
    if not raw_str:
        return []
    clean = re.sub(r'mm|in', '', str(raw_str), flags=re.IGNORECASE)
    clean_str = re.sub(r'[;\s|:]+', ',', clean)
    parts = [p.strip() for p in clean_str.split(',') if p.strip()]
    results = []
    for p in parts:
        try:
            v = float(p)
            if v > 0 and v not in results:
                results.append(v)
        except (TypeError, ValueError):
            pass
    return results
def find_custom_pos(custom_label_pos, candidate_keys):
    """
    Beginners Note: Search custom_label_pos dictionary with exact, fuzzy/normalized, and prefix branch matching
    so dragged coordinates from pump-data always map to report SVG elements.
    """
    if not custom_label_pos or not isinstance(custom_label_pos, dict):
        return None

    # 1. Direct exact key match (highest priority, strictly preserves candidate key precedence)
    for k in candidate_keys:
        if k in custom_label_pos and isinstance(custom_label_pos[k], dict):
            v = custom_label_pos[k]
            if 'x' in v and 'y' in v and v['x'] is not None and v['y'] is not None:
                return v

    # 2. Fuzzy normalized key match (removes non-alphanumeric chars for minor formatting diffs)
    norm_dict = {}
    for k, v in custom_label_pos.items():
        if isinstance(v, dict) and 'x' in v and 'y' in v and v['x'] is not None and v['y'] is not None:
            nk = re.sub(r'[^a-z0-9]', '', str(k).lower())
            if nk and nk not in norm_dict:
                norm_dict[nk] = v

    for k in candidate_keys:
        nk = re.sub(r'[^a-z0-9]', '', str(k).lower())
        if nk in norm_dict:
            return norm_dict[nk]

    # 3. Exact prefix key matching with underscore (e.g. matching 'pow_30' with 'pow_30_4', 'eta_75' with 'eta_75_left')
    for k in candidate_keys:
        clean_k = str(k).strip()
        if not clean_k or len(clean_k) < 3:
            continue
        for db_key, pos_val in custom_label_pos.items():
            if isinstance(pos_val, dict) and 'x' in pos_val and 'y' in pos_val:
                if db_key.startswith(clean_k + '_'):
                    return pos_val

    return None

def _dash_style_to_svg(style_name, default=''):
    if not style_name or style_name == 'solid':
        return ''
    elif style_name == 'dashed':
        return 'stroke-dasharray="6,4"'
    elif style_name == 'dotted':
        return 'stroke-dasharray="2.5,3"'
    elif style_name == 'dash_dot':
        return 'stroke-dasharray="6,3,2,3"'
    elif style_name == 'none':
        return 'stroke="none"'
    return default


def generate_chart_svg(curves_list, x_label="Flow (m³/h)", y_label="Head (m)", custom_range=None, width=720, height=240, isolines_list=None, show_legend=True, legend_position='top_right', legend_mode='each', custom_label_pos=None, label_format='auto', chart_type='hq', graph_styles=None, duty_point=None):
    """
    Beginners Note: Generates pure inline SVG XML vector markup for single or multi-curve pump charts in Ultra-HD resolution.
    Applies custom visual styles (per-chart colors, max/min/trim curve thickness & styles, custom typography, and axes/grid styles).
    """
    if not curves_list and not isolines_list:
        return ""

    def find_custom_pos(custom_pos_dict, keys_to_try):
        if not custom_pos_dict or not isinstance(custom_pos_dict, dict):
            return None
        for k in keys_to_try:
            if k in custom_pos_dict:
                return custom_pos_dict[k]
        return None

    styles = graph_styles or {}

    # Typography & Font family settings
    f_family_choice = styles.get('font_family', 'Segoe UI')
    font_family = {
        'Segoe UI': "'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif",
        'Inter': "'Inter', 'Segoe UI', -apple-system, sans-serif",
        'Roboto': "'Roboto', 'Segoe UI', -apple-system, sans-serif",
        'Helvetica': "'Helvetica Neue', Helvetica, Arial, sans-serif",
        'Arial': "Arial, Helvetica, sans-serif",
        'Monospace': "'SF Mono', Consolas, 'Courier New', monospace"
    }.get(f_family_choice, "'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif")

    f_scale = {'small': 0.88, 'standard': 1.0, 'large': 1.15}.get(styles.get('font_scale', 'standard'), 1.0)
    f_weight = styles.get('font_weight', '600')
    badge_style = styles.get('badge_style', 'pill_white')

    # Canvas & Axes & Grid Styling
    chart_bg = styles.get('chart_bg_color', '#ffffff')
    axis_col = styles.get('axis_line_color', '#475569')
    axis_w = float(styles.get('axis_line_width', 1.5))

    maj_grid_col = styles.get('major_grid_color', '#cbd5e1')
    maj_grid_w = float(styles.get('major_grid_width', 1.0))
    maj_grid_style = styles.get('major_grid_style', 'dashed')
    maj_grid_dash = _dash_style_to_svg(maj_grid_style, 'stroke-dasharray="3,3"')

    min_grid_col = styles.get('minor_grid_color', '#e2e8f0')
    min_grid_w = float(styles.get('minor_grid_width', 0.8))
    min_grid_style = styles.get('minor_grid_style', 'dotted')
    min_grid_dash = _dash_style_to_svg(min_grid_style, 'stroke-dasharray="2,3"')

    # Scale to Ultra-HD high-density internal vector coordinate space
    VIEW_W = 960
    scale = VIEW_W / 720.0
    VIEW_H = max(100, int(round(height * scale)))

    padding_left = 50
    padding_right = 18
    padding_top = 12
    padding_bottom = 28

    plot_w = VIEW_W - padding_left - padding_right
    plot_h = VIEW_H - padding_top - padding_bottom

    # Extract X & Y values across curves & isolines
    all_x = []
    all_y = []
    for c in (curves_list or []):
        all_x.extend(c.get('x', []))
        all_y.extend(c.get('y', []))
    for iso in (isolines_list or []):
        all_x.extend(iso.get('x', []))
        all_y.extend(iso.get('y', []))

    if not all_x or not all_y:
        return ""

    axis = custom_range or {}
    has_custom_x_max = ('x_max' in axis and axis['x_max'] is not None)
    has_custom_y_max = ('y_max' in axis and axis['y_max'] is not None)

    x_min = _safe_range_val(axis.get('x_min'), min(all_x))
    x_max = _safe_range_val(axis.get('x_max'), max(all_x))
    x_major = _safe_float(axis.get('x_major'))
    x_minor = _safe_float(axis.get('x_minor'))

    y_min = _safe_range_val(axis.get('y_min'), 0.0)
    y_max = _safe_range_val(axis.get('y_max'), max(all_y) * 1.12 if max(all_y) > 0 else 10.0)
    y_major = _safe_float(axis.get('y_major'))
    y_minor = _safe_float(axis.get('y_minor'))

    if x_max <= x_min: x_max = x_min + 1.0
    if y_max <= y_min: y_max = y_min + 1.0

    # Calculate Clean Major Ticks
    x_ticks = _calculate_axis_ticks(x_min, x_max, x_major)
    y_ticks = _calculate_axis_ticks(y_min, y_max, y_major)

    if x_ticks and not has_custom_x_max:
        x_min = x_ticks[0]
        x_max = max(x_max, x_ticks[-1])
    if y_ticks and not has_custom_y_max:
        y_min = y_ticks[0]
        y_max = max(y_max, y_ticks[-1])

    grid_lines = []
    labels = []

    # X Minor Grid Lines
    if min_grid_style != 'none' and x_minor and x_minor > 0:
        curr_m = x_min + x_minor
        while curr_m < x_max - 1e-5:
            if not any(abs(curr_m - t) < 1e-4 for t in x_ticks):
                px = padding_left + ((curr_m - x_min) / (x_max - x_min)) * plot_w
                grid_lines.append(f'<line x1="{px:.1f}" y1="{padding_top}" x2="{px:.1f}" y2="{padding_top + plot_h}" stroke="{min_grid_col}" stroke-width="{min_grid_w}" {min_grid_dash} />')
            curr_m += x_minor

    # Y Minor Grid Lines
    if min_grid_style != 'none' and y_minor and y_minor > 0:
        curr_m = y_min + y_minor
        while curr_m < y_max - 1e-5:
            if not any(abs(curr_m - t) < 1e-4 for t in y_ticks):
                py = padding_top + plot_h - ((curr_m - y_min) / (y_max - y_min)) * plot_h
                grid_lines.append(f'<line x1="{padding_left}" y1="{py:.1f}" x2="{VIEW_W - padding_right}" y2="{py:.1f}" stroke="{min_grid_col}" stroke-width="{min_grid_w}" {min_grid_dash} />')
            curr_m += y_minor

    # X Major Grid Lines & Labels
    for val in x_ticks:
        if x_min - 1e-5 <= val <= x_max + 1e-5:
            px = padding_left + ((val - x_min) / (x_max - x_min)) * plot_w
            if maj_grid_style != 'none':
                grid_lines.append(f'<line x1="{px:.1f}" y1="{padding_top}" x2="{px:.1f}" y2="{padding_top + plot_h}" stroke="{maj_grid_col}" {maj_grid_dash} stroke-width="{maj_grid_w}" />')
            val_str = f"{val:.0f}" if abs(val - round(val)) < 1e-5 else f"{val:.1f}"
            labels.append(f'<text x="{px:.1f}" y="{padding_top + plot_h + 13}" font-size="{9.5 * f_scale:.1f}" font-weight="{f_weight}" font-family="{font_family}" fill="#475569" text-anchor="middle">{val_str}</text>')

    # Y Major Grid Lines & Labels
    for val in y_ticks:
        if y_min - 1e-5 <= val <= y_max + 1e-5:
            py = padding_top + plot_h - ((val - y_min) / (y_max - y_min)) * plot_h
            if maj_grid_style != 'none':
                grid_lines.append(f'<line x1="{padding_left}" y1="{py:.1f}" x2="{VIEW_W - padding_right}" y2="{py:.1f}" stroke="{maj_grid_col}" {maj_grid_dash} stroke-width="{maj_grid_w}" />')
            val_str = f"{val:.0f}" if abs(val - round(val)) < 1e-5 else f"{val:.1f}"
            labels.append(f'<text x="{padding_left - 6}" y="{py + 3.5:.1f}" font-size="{9.5 * f_scale:.1f}" font-weight="{f_weight}" font-family="{font_family}" fill="#475569" text-anchor="end">{val_str}</text>')

    paths_svg = []
    legend_items = []
    drawn_label_keys = set()

    # Render Isolines Overlay (Efficiency Isolines, Power Isolines, NPSH Isolines)
    if isolines_list:
        iso_w = float(styles.get('iso_width', 1.3))
        iso_dash_cfg = _dash_style_to_svg(styles.get('iso_style', 'dashed'), 'stroke-dasharray="2.5,2.5"')

        for iso_idx, iso in enumerate(isolines_list):
            iso_x = iso.get('x', [])
            iso_y = iso.get('y', [])
            iso_label = iso.get('label', '')

            iso_branch = iso.get('branch', '')
            iso_t_idx = iso.get('type_idx', iso_idx)
            iso_type = iso.get('iso_type')
            if not iso_type:
                if '%' in iso_label:
                    iso_type = 'eta'
                elif 'kw' in iso_label.lower() or 'hp' in iso_label.lower():
                    iso_type = 'pow'
                else:
                    iso_type = 'npsh'

            # Apply custom isoline color
            if iso_type == 'eta':
                iso_color = styles.get('iso_eta_color', iso.get('color', '#059669'))
            elif iso_type == 'pow':
                iso_color = styles.get('iso_pow_color', iso.get('color', '#d97706'))
            else:
                iso_color = styles.get('iso_npsh_color', iso.get('color', '#0284c7'))

            if len(iso_x) == len(iso_y) and len(iso_x) > 1:
                pts = []
                for x, y in zip(iso_x, iso_y):
                    raw_px = padding_left + ((x - x_min) / (x_max - x_min)) * plot_w
                    raw_py = padding_top + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
                    px = min(max(float(padding_left), float(raw_px)), float(VIEW_W - padding_right))
                    py = min(max(float(padding_top), float(raw_py)), float(padding_top + plot_h))
                    pts.append((px, py))

                if len(pts) > 1:
                    path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
                    for px, py in pts[1:]:
                        path_d += f" L {px:.1f},{py:.1f}"
                    paths_svg.append(f'<path d="{path_d}" fill="none" stroke="{iso_color}" stroke-width="{iso_w}" {iso_dash_cfg} stroke-linecap="round" stroke-linejoin="round" />')

                    if iso_label:
                        clean_iso = iso_label.replace('%','').replace('kW','').replace('hp','').replace('m','').replace('ft','').strip()
                        num_m = re.search(r'(\d+(?:\.\d+)?)', iso_label)
                        iso_val = num_m.group(1) if num_m else clean_iso
                        
                        prefix = iso_type
                        candidate_keys = []

                        if iso_branch:
                            candidate_keys.append(f"{prefix}_{iso_val}_{iso_branch}")
                            candidate_keys.append(f"{prefix}_{clean_iso}_{iso_branch}")

                        candidate_keys.append(f"{prefix}_{iso_val}_{iso_t_idx}")
                        if iso_idx != iso_t_idx:
                            candidate_keys.append(f"{prefix}_{iso_val}_{iso_idx}")
                        candidate_keys.append(f"{prefix}_{clean_iso}_{iso_t_idx}")

                        candidate_keys.append(f"{prefix}_{iso_val}")
                        candidate_keys.append(f"{prefix}_{clean_iso}")
                        candidate_keys.append(f"{prefix}_{iso_label.strip()}")

                        candidate_keys.append(iso_label.strip())
                        candidate_keys.append(clean_iso)
                        candidate_keys.append(iso_val)

                        pos = find_custom_pos(custom_label_pos, candidate_keys)

                        if pos and isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                            try:
                                c_x = float(pos['x'])
                                c_y = float(pos['y'])
                                if x_min <= c_x <= x_max and y_min <= c_y <= y_max:
                                    m_px = padding_left + ((c_x - x_min) / (x_max - x_min)) * plot_w
                                    m_py = padding_top + plot_h - ((c_y - y_min) / (y_max - y_min)) * plot_h
                                else:
                                    m_idx = int(len(pts) / 2)
                                    m_px, m_py = pts[m_idx]
                            except Exception:
                                m_idx = int(len(pts) / 2)
                                m_px, m_py = pts[m_idx]
                        else:
                            m_idx = int(len(pts) / 2)
                            m_px, m_py = pts[m_idx]

                        m_px = min(max(float(padding_left + 12), float(m_px)), float(VIEW_W - padding_right - 12))
                        m_py = min(max(float(padding_top + 10), float(m_py)), float(VIEW_H - padding_bottom - 6))

                        labels.append(f'<text x="{m_px:.1f}" y="{m_py:.1f}" font-size="{9 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="{iso_color}" text-anchor="middle" dominant-baseline="central" paint-order="stroke" stroke="{chart_bg}" stroke-width="3.5px" stroke-linejoin="round">{iso_label}</text>')

    # Chart primary color lookup for 'chart_custom' mode
    chart_key = 'eta' if chart_type == 'eff' else chart_type
    chart_specific_color = None
    chart_key = chart_type.lower()
    if chart_key == 'hq':
        chart_specific_color = styles.get('hq_color')
    elif chart_key == 'eta':
        chart_specific_color = styles.get('eta_color')
    elif chart_key == 'pow':
        chart_specific_color = styles.get('pow_color')
    elif chart_key == 'npsh':
        chart_specific_color = styles.get('npsh_color')

    sec_count = 0
    for c_idx, c in enumerate(curves_list or []):
        x_pts = c.get('x', [])
        y_pts = c.get('y', [])
        label = c.get('label', '')
        color = c.get('color', '#1e3a8a')
        is_sec = c.get('is_secondary', False)
        is_rated = bool(c.get('is_rated')) or ('(rated)' in label.lower())
        is_max = (c_idx == 0 and not is_sec and not is_rated)
        is_min = (c_idx == len(curves_list) - 1 and len(curves_list) > 1 and not is_sec and not is_rated)

        if is_sec:
            sec_idx = sec_count
            sec_count += 1
        else:
            sec_idx = c_idx

        if not x_pts or not y_pts or len(x_pts) != len(y_pts):
            continue

        # Custom Curve Colors
        if is_rated:
            color = styles.get('rated_curve_color') or '#d97706'
        elif is_max and styles.get('max_curve_color'):
            color = styles['max_curve_color']
        elif is_min and styles.get('min_curve_color'):
            color = styles['min_curve_color']
        elif legend_mode == 'chart_custom' and chart_specific_color:
            if is_max:
                color = chart_specific_color

        # Custom Curve Thickness & Dash Patterns
        if is_rated:
            stroke_w = float(styles.get('rated_curve_width') or 2.8)
            dash_style = _dash_style_to_svg(styles.get('rated_curve_style') or 'dashed', 'stroke-dasharray="6,4"')
        elif is_max:
            stroke_w = float(styles.get('max_curve_width') or styles.get(f"{chart_key}_width") or 2.4)
            dash_style = _dash_style_to_svg(styles.get('max_curve_style') or styles.get(f"{chart_key}_style") or 'solid', '')
        elif is_min:
            stroke_w = float(styles.get('min_curve_width') or 1.6)
            dash_style = _dash_style_to_svg(styles.get('min_curve_style') or 'solid', '')
        else:
            stroke_w = float(styles.get('trim_curve_width') or 1.6)
            dash_style = _dash_style_to_svg(styles.get('trim_curve_style') or 'solid', '')

        pts = []
        for x, y in zip(x_pts, y_pts):
            if x_min <= x <= x_max and y_min <= y <= y_max:
                px = padding_left + ((x - x_min) / (x_max - x_min)) * plot_w
                py = padding_top + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
                pts.append((px, py))

        if not pts:
            continue

        path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
        for px, py in pts[1:]:
            path_d += f" L {px:.1f},{py:.1f}"

        paths_svg.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{stroke_w}" {dash_style} stroke-linecap="round" stroke-linejoin="round" />')
        pct_val = c.get('pct')
        legend_items.append({'label': label, 'color': color, 'pct': pct_val, 'val': c.get('val'), 'width': stroke_w, 'dash': dash_style, 'is_rated': is_rated})

        # Option 4: Direct labels on each impeller curve
        if legend_mode == 'curve_labels' and len(pts) > 1:
            raw_label = label
            clean_lbl = raw_label.replace(' (Max)', '').replace(' (Rated)', '').replace(' (Fitted)', '').replace(' (Affinity)', '').strip()

            dedup_key = f"{c_idx}_{clean_lbl}"
            if dedup_key in drawn_label_keys:
                continue
            drawn_label_keys.add(dedup_key)

            num_match = re.search(r'(\d+(?:\.\d+)?)', clean_lbl)
            val_key = num_match.group(1) if num_match else clean_lbl
            is_rpm_lbl = ('rpm' in clean_lbl.lower()) or ('rpm' in raw_label.lower())
            chart_prefix = f"{chart_type}_" if chart_type != 'hq' else ""

            # Format text badge according to user label_format choice & is_rated status
            if is_rated:
                if is_rpm_lbl:
                    display_text = f"{val_key} RPM (Rated)"
                else:
                    display_text = f"Ø{val_key} mm (Rated)"
            elif label_format == 'percent':
                if pct_val is not None:
                    display_text = f"{pct_val}%"
                elif is_rpm_lbl:
                    display_text = f"{val_key} RPM"
                else:
                    display_text = f"Ø{val_key} mm"
            elif label_format == 'simple':
                if is_rpm_lbl:
                    display_text = f"{val_key} RPM"
                else:
                    display_text = f"Ø{val_key} mm"
            else:  # 'auto': dimension with percentage
                if is_rpm_lbl:
                    display_text = f"{val_key} RPM ({pct_val}%)" if pct_val is not None else f"{val_key} RPM"
                else:
                    display_text = f"Ø{val_key} mm ({pct_val}%)" if pct_val is not None else f"Ø{val_key} mm"

            candidate_keys = []
            if is_rpm_lbl:
                simple_rpm_keys = [
                    f"{chart_prefix}{val_key} RPM (Rated)",
                    f"{chart_prefix}{val_key} RPM (Max)",
                    f"{chart_prefix}{val_key} RPM",
                    f"{chart_prefix}{raw_label}",
                    f"{chart_prefix}{clean_lbl}",
                ]
                pct_rpm_keys = [
                    f"{chart_prefix}{val_key} RPM ({pct_val}%)",
                    f"{chart_prefix}{val_key} RPM ({pct_val}%) (Max)",
                ] if pct_val else []
                idx_rpm_keys = [
                    f"{chart_prefix}spd_lbl_{c_idx}",
                    f"{chart_prefix}spd_lbl_{sec_idx}",
                    f"{chart_prefix}rpm_{val_key}",
                    f"{chart_prefix}spd_{val_key}",
                ]
                if label_format == 'percent':
                    candidate_keys.extend(pct_rpm_keys)
                    candidate_keys.extend(simple_rpm_keys)
                else:
                    candidate_keys.extend(simple_rpm_keys)
                    candidate_keys.extend(pct_rpm_keys)
                candidate_keys.extend(idx_rpm_keys)
            else:
                simple_dia_keys = [
                    f"{chart_prefix}Ø{val_key} mm (Rated)",
                    f"{chart_prefix}Ø{val_key} mm (Max)",
                    f"{chart_prefix}Ø{val_key} mm",
                    f"{chart_prefix}Ø{raw_label}",
                    f"{chart_prefix}Ø{clean_lbl}",
                    f"{chart_prefix}{raw_label}",
                    f"{chart_prefix}{clean_lbl}",
                    f"{chart_prefix}{val_key} mm (Max)",
                    f"{chart_prefix}{val_key} mm",
                ]
                pct_dia_keys = [
                    f"{chart_prefix}Ø{val_key} mm ({pct_val}%)",
                    f"{chart_prefix}Ø{val_key} mm ({pct_val}%) (Max)",
                    f"{chart_prefix}{val_key} mm ({pct_val}%)",
                    f"{chart_prefix}{val_key} mm ({pct_val}%) (Max)",
                ] if pct_val else []
                idx_dia_keys = [
                    f"{chart_prefix}dia_lbl_{c_idx}",
                    f"{chart_prefix}dia_lbl_{sec_idx}",
                    f"{chart_prefix}dia_{c_idx}",
                    f"{chart_prefix}dia_{val_key}",
                ]
                if label_format == 'percent':
                    candidate_keys.extend(pct_dia_keys)
                    candidate_keys.extend(simple_dia_keys)
                else:
                    candidate_keys.extend(simple_dia_keys)
                    candidate_keys.extend(pct_dia_keys)
                candidate_keys.extend(idx_dia_keys)

            if chart_type == 'hq':
                candidate_keys.append(f"ol_lbl_{c_idx}")
                candidate_keys.append(f"ol_lbl_{sec_idx}")
                candidate_keys.append(f"curve_{c_idx}")
                candidate_keys.append(f"HQ_{clean_lbl}")
                candidate_keys.append(val_key)

            pos = find_custom_pos(custom_label_pos, candidate_keys)

            if pos and isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                try:
                    c_x = float(pos['x'])
                    c_y = float(pos['y'])
                    if x_min <= c_x <= x_max and y_min <= c_y <= y_max:
                        lx = padding_left + ((c_x - x_min) / (x_max - x_min)) * plot_w
                        ly = padding_top + plot_h - ((c_y - y_min) / (y_max - y_min)) * plot_h
                    else:
                        idx = int(len(pts) * 0.85)
                        lx, ly = pts[idx]
                except Exception:
                    idx = int(len(pts) * 0.85)
                    lx, ly = pts[idx]
            else:
                idx = int(len(pts) * 0.85)
                lx, ly = pts[idx]

            lx = min(max(float(padding_left + 18), float(lx)), float(VIEW_W - padding_right - 18))
            ly = min(max(float(padding_top + 12), float(ly)), float(VIEW_H - padding_bottom - 6))

            tw = len(display_text) * 5.8 + 10
            if is_rated:
                # Highlighted Amber badge for rated curve
                labels.append(f'<rect x="{lx - tw/2:.1f}" y="{ly - 11:.1f}" width="{tw:.1f}" height="14" fill="#fffbeb" fill-opacity="0.95" stroke="#d97706" stroke-width="1.2" rx="3.5" />')
                labels.append(f'<text x="{lx:.1f}" y="{ly - 1.5:.1f}" font-size="{9 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="#b45309" text-anchor="middle">{display_text}</text>')
            elif badge_style == 'pill_tinted':
                labels.append(f'<rect x="{lx - tw/2:.1f}" y="{ly - 11:.1f}" width="{tw:.1f}" height="14" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.0" rx="3.5" />')
                labels.append(f'<text x="{lx:.1f}" y="{ly - 1.5:.1f}" font-size="{9 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="{color}" text-anchor="middle">{display_text}</text>')
            elif badge_style == 'subtle_glow':
                labels.append(f'<text x="{lx:.1f}" y="{ly - 1.5:.1f}" font-size="{9 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="{color}" text-anchor="middle" paint-order="stroke" stroke="{chart_bg}" stroke-width="4px" stroke-linejoin="round">{display_text}</text>')
            elif badge_style == 'plain':
                labels.append(f'<text x="{lx:.1f}" y="{ly - 1.5:.1f}" font-size="{9 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="{color}" text-anchor="middle">{display_text}</text>')
            else:  # pill_white default
                labels.append(f'<rect x="{lx - tw/2:.1f}" y="{ly - 11:.1f}" width="{tw:.1f}" height="14" fill="{chart_bg}" fill-opacity="0.95" stroke="{color}" stroke-width="1.0" rx="3.5" />')
                labels.append(f'<text x="{lx:.1f}" y="{ly - 1.5:.1f}" font-size="{9 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="{color}" text-anchor="middle">{display_text}</text>')

    # Render Multi-Curve Legend Box with customizable positioning
    legend_svg = ""
    if show_legend and legend_mode != 'curve_labels' and legend_mode != 'none' and len(legend_items) >= 1:
        leg_box = []
        b_w = 145
        b_h = 16 + len(legend_items) * 14

        if legend_position == 'top_left':
            box_x = padding_left + 10
            box_y = padding_top + 6
        elif legend_position == 'bottom_right':
            box_x = VIEW_W - padding_right - b_w - 6
            box_y = VIEW_H - padding_bottom - b_h - 6
        elif legend_position == 'bottom_left':
            box_x = padding_left + 10
            box_y = VIEW_H - padding_bottom - b_h - 6
        else:  # 'top_right'
            box_x = VIEW_W - padding_right - b_w - 6
            box_y = padding_top + 6

        leg_box.append(f'<rect x="{box_x}" y="{box_y}" width="{b_w}" height="{b_h}" fill="{chart_bg}" fill-opacity="0.95" stroke="#cbd5e1" rx="4" />')
        for l_idx, leg in enumerate(legend_items):
            ly = box_y + 13 + l_idx * 14
            l_text = leg["label"]
            l_pct = leg.get("pct")
            l_dash = leg.get("dash", "")
            l_w = min(2.5, leg.get("width", 2.0))
            is_leg_rated = leg.get("is_rated", False)

            if is_leg_rated:
                l_text = leg["label"]
            elif label_format == 'percent' and l_pct is not None:
                l_text = f"{leg['label']} ({l_pct}%)" if '%' not in leg['label'] else leg['label']
            elif label_format == 'auto' and l_pct is not None and '%' not in leg['label']:
                l_text = f"{leg['label']} ({l_pct}%)"
            elif label_format == 'simple':
                l_text = re.sub(r'\s*\(\d+%\)', '', leg['label'])

            leg_box.append(f'<line x1="{box_x + 8}" y1="{ly - 3}" x2="{box_x + 24}" y2="{ly - 3}" stroke="{leg["color"]}" stroke-width="{l_w}" {l_dash} stroke-linecap="round" />')
            text_color = '#b45309' if is_leg_rated else '#334155'
            text_weight = '700' if is_leg_rated else f_weight
            leg_box.append(f'<text x="{box_x + 28}" y="{ly}" font-size="{9 * f_scale:.1f}" font-weight="{text_weight}" font-family="{font_family}" fill="{text_color}">{l_text}</text>')
        legend_svg = "".join(leg_box)

    # ── Render Operating Duty Point Marker (Target icon + crosshairs) on H-Q chart ──
    duty_svg = ""
    if duty_point and isinstance(duty_point, dict) and chart_type == 'hq':
        try:
            dq = float(duty_point.get('q', 0))
            dh = float(duty_point.get('h', 0))
            if x_min <= dq <= x_max and y_min <= dh <= y_max:
                d_px = padding_left + ((dq - x_min) / (x_max - x_min)) * plot_w
                d_py = padding_top + plot_h - ((dh - y_min) / (y_max - y_min)) * plot_h

                # Crosshairs
                ch_lines = f'<line x1="{padding_left}" y1="{d_py:.1f}" x2="{d_px:.1f}" y2="{d_py:.1f}" stroke="#ef4444" stroke-width="1.2" stroke-dasharray="3,3" />' \
                           f'<line x1="{d_px:.1f}" y1="{d_py:.1f}" x2="{d_px:.1f}" y2="{padding_top + plot_h}" stroke="#ef4444" stroke-width="1.2" stroke-dasharray="3,3" />'

                # Bullseye Target Icon
                target_dot = f'<circle cx="{d_px:.1f}" cy="{d_py:.1f}" r="6.5" fill="#ef4444" fill-opacity="0.2" stroke="#ef4444" stroke-width="1.5" />' \
                             f'<circle cx="{d_px:.1f}" cy="{d_py:.1f}" r="2.5" fill="#dc2626" />'

                # Duty Coordinate Badge
                d_lbl = duty_point.get('label') or f"Duty: {round(dq, 1)} @ {round(dh, 1)}"
                tw_d = len(d_lbl) * 5.6 + 10
                badge_x = min(max(float(padding_left + tw_d/2 + 2), float(d_px)), float(VIEW_W - padding_right - tw_d/2 - 2))
                badge_y = max(float(padding_top + 14), float(d_py - 10))
                duty_badge = f'<rect x="{badge_x - tw_d/2:.1f}" y="{badge_y - 10:.1f}" width="{tw_d:.1f}" height="13" fill="#ffffff" fill-opacity="0.95" stroke="#ef4444" stroke-width="1.0" rx="3" />' \
                             f'<text x="{badge_x:.1f}" y="{badge_y - 1.0:.1f}" font-size="8.5" font-weight="700" font-family="{font_family}" fill="#b91c1c" text-anchor="middle">🎯 {d_lbl}</text>'

                duty_svg = ch_lines + target_dot + duty_badge
        except Exception as e:
            print("Duty point render notice:", e)

    svg_code = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" preserveAspectRatio="none" width="100%" height="100%" shape-rendering="geometricPrecision" text-rendering="geometricPrecision" style="background:{chart_bg}; border-radius:4px; display:block; width:100%; height:100%; max-height:{height}px;">
  {''.join(grid_lines)}
  {''.join(paths_svg)}
  {duty_svg}
  {''.join(labels)}
  {legend_svg}
  <!-- X-Axis Line -->
  <line x1="{padding_left}" y1="{padding_top + plot_h}" x2="{VIEW_W - padding_right}" y2="{padding_top + plot_h}" stroke="{axis_col}" stroke-width="{axis_w}" />
  <!-- Y-Axis Line -->
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + plot_h}" stroke="{axis_col}" stroke-width="{axis_w}" />
  <!-- X-Axis Ticks & Values -->
'''
    for val in x_ticks:
        px = padding_left + ((val - x_min) / (x_max - x_min)) * plot_w
        svg_code += f'  <line x1="{px:.1f}" y1="{padding_top + plot_h}" x2="{px:.1f}" y2="{padding_top + plot_h + 4}" stroke="{axis_col}" stroke-width="1.0" />\n'
        val_fmt = f"{int(round(val))}" if abs(val - round(val)) < 1e-4 else f"{val:.1f}"
        svg_code += f'  <text x="{px:.1f}" y="{padding_top + plot_h + 15}" font-size="{9 * f_scale:.1f}" font-family="{font_family}" font-weight="{f_weight}" fill="#475569" text-anchor="middle">{val_fmt}</text>\n'

    for val in y_ticks:
        py = padding_top + plot_h - ((val - y_min) / (y_max - y_min)) * plot_h
        svg_code += f'  <line x1="{padding_left - 4}" y1="{py:.1f}" x2="{padding_left}" y2="{py:.1f}" stroke="{axis_col}" stroke-width="1.0" />\n'
        val_fmt = f"{int(round(val))}" if abs(val - round(val)) < 1e-4 else f"{val:.1f}"
        svg_code += f'  <text x="{padding_left - 6}" y="{py + 3:.1f}" font-size="{9 * f_scale:.1f}" font-family="{font_family}" font-weight="{f_weight}" fill="#475569" text-anchor="end">{val_fmt}</text>\n'

    # Axis Labels
    svg_code += f'  <text x="{padding_left + plot_w / 2:.1f}" y="{VIEW_H - 4}" font-size="{10 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="#1e293b" text-anchor="middle">{x_label}</text>\n'
    svg_code += f'  <text x="14" y="{padding_top + plot_h / 2:.1f}" font-size="{10 * f_scale:.1f}" font-weight="700" font-family="{font_family}" fill="#1e293b" text-anchor="middle" transform="rotate(-90 14 {padding_top + plot_h / 2:.1f})">{y_label}</text>\n'
    svg_code += '</svg>'

    return svg_code


def _calc_optimal_trim_ratio(pump, q_duty, h_duty):
    """
    Calculate optimal trim ratio r in [0.2, 1.15] using bisection root-finding
    such that H(q_duty / r) * r^2 = h_duty.
    """
    try:
        q_val = float(q_duty)
        h_val = float(h_duty)
        if q_val <= 0 or h_val <= 0:
            return 1.0

        r_low = 0.2
        r_high = 1.15
        for _ in range(30):
            r_mid = (r_low + r_high) / 2.0
            q_eval = np.array([q_val / r_mid])
            h_eval = float(hq_curve(pump, q_eval)[0])
            h_calc = h_eval * (r_mid ** 2)
            if h_calc < h_val:
                r_low = r_mid
            else:
                r_high = r_mid
        r_opt = (r_low + r_high) / 2.0
        return max(0.2, min(1.15, r_opt))
    except Exception:
        return 1.0


def _build_report_curve_context(pump, report):
    """
    Beginners Note: Evaluates exact mathematical pump curves using pump_curves.py polynomial math,
    applies exact pump-data axis scale settings (min, max, major, minor), auto-detects NPSHr availability,
    and supports Curve Display Modes (all, max_only, min_max, rated_only).
    """
    rep_unit_q = getattr(report, 'unit_flow', None) or pump.unit_q or 'm3h'
    rep_unit_h = getattr(report, 'unit_head', None) or pump.unit_h or 'm'
    rep_unit_pow = getattr(report, 'unit_power', None) or pump.unit_pow or 'kw'
    rep_unit_npsh = getattr(report, 'unit_npsh', None) or pump.unit_npsh or 'm'

    # Compute scaling factors for curves (curves are ALWAYS generated in m3h, m, kw by pump_curves.py)
    fQ_curve = CURVE_CONVERSIONS['q'].get(rep_unit_q.lower().replace('/', ''), 1.0) / 1.0
    fH_curve = CURVE_CONVERSIONS['h'].get(rep_unit_h.lower(), 1.0) / 1.0
    fPow_curve = CURVE_CONVERSIONS['pow'].get(rep_unit_pow.lower(), 1.0) / 1.0
    fNpsh_curve = CURVE_CONVERSIONS['npsh'].get(rep_unit_npsh.lower(), 1.0) / 1.0

    # Compute scaling factors for labels (labels are saved relative to the pump's native base unit)
    fQ_raw = CURVE_CONVERSIONS['q'].get(rep_unit_q.lower().replace('/', ''), 1.0) / CURVE_CONVERSIONS['q'].get((pump.unit_q or 'm3h').lower().replace('/', ''), 1.0)
    fH_raw = CURVE_CONVERSIONS['h'].get(rep_unit_h.lower(), 1.0) / CURVE_CONVERSIONS['h'].get((pump.unit_h or 'm').lower(), 1.0)
    fPow_raw = CURVE_CONVERSIONS['pow'].get(rep_unit_pow.lower(), 1.0) / CURVE_CONVERSIONS['pow'].get((pump.unit_pow or 'kw').lower(), 1.0)
    fNpsh_raw = CURVE_CONVERSIONS['npsh'].get(rep_unit_npsh.lower(), 1.0) / CURVE_CONVERSIONS['npsh'].get((pump.unit_npsh or 'm').lower(), 1.0)

    q_max = pump.q_max if hasattr(pump, 'q_max') and pump.q_max and pump.q_max > 0 else 200.0
    q_pts = list(np.linspace(pump.q_min or 0.0, q_max, 150))

    # Evaluate Primary Max Curve
    h_arr = hq_curve(pump, np.array(q_pts))
    eta_arr = efficiency_curve(pump, np.array(q_pts))
    pow_arr = power_curve(pump, np.array(q_pts))
    npsh_arr = npsh_curve(pump, np.array(q_pts))

    h_pts = [round(float(v), 2) for v in h_arr]
    eta_pts = [round(float(v), 2) for v in eta_arr]
    pow_pts = [round(float(v), 2) for v in pow_arr]
    npsh_pts = [round(float(v), 2) for v in npsh_arr]

    primary_color = report.primary_color if report and report.primary_color else '#1e3a8a'
    mode = report.curve_display_mode if report and report.curve_display_mode else 'all'
    show_rated = getattr(report, 'show_rated_curve', True)
    if show_rated is None:
        show_rated = True

    # Check NPSH Availability (e.g. pumps without NPSH data have max NPSH = 0)
    has_npsh = max(npsh_pts) > 0.05 and (pump.has_npsh_poly() if hasattr(pump, 'has_npsh_poly') else any(abs(getattr(pump, f'npsh_c{i}', 0.0) or 0.0) > 1e-6 for i in range(6)))

    # 1. Parse custom curve diameters from pump.curve_diameters (supporting ;, |, ,, spaces)
    custom_d_list = _parse_diameters_string(getattr(pump, 'curve_diameters', None))

    # 2. Check if extra_curves_json has additional diameters
    if hasattr(pump, 'extra_curves_json') and pump.extra_curves_json:
        try:
            extra_data = json.loads(pump.extra_curves_json)
            if isinstance(extra_data, list):
                for item in extra_data:
                    if isinstance(item, dict) and 'diameter' in item:
                        d_val = _safe_float(item.get('diameter'))
                        if d_val and d_val not in custom_d_list:
                            custom_d_list.append(d_val)
        except Exception:
            pass

    # Sort custom diameters in descending order (Max first)
    if custom_d_list:
        custom_d_list.sort(reverse=True)
        max_d = custom_d_list[0]
    else:
        max_d = pump.impeller_dia_mm if (hasattr(pump, 'impeller_dia_mm') and pump.impeller_dia_mm and pump.impeller_dia_mm > 0) else 300.0

    hq_curves_list = []
    eta_curves_list = []
    pow_curves_list = []
    npsh_curves_list = []
    lines_to_draw = []
    curves_to_draw = []
    dia_objs = []

    palette = ['#1e3a8a', '#2563eb', '#3b82f6', '#64748b', '#94a3b8']

    # Determine if user explicitly forced a specific overlay via report settings
    explicit_dia = getattr(report, 'show_dia_overlay', None)
    explicit_rpm = getattr(report, 'show_rpm_overlay', None)

    # Check Family Type / Test Basis (auto-detects VSD templates so VSD reports display RPM curves and labels)
    is_variable_speed = (pump.family_type == 'variable_speed') or \
                        ('vsd' in (getattr(report, 'report_name', '') or '').lower()) or \
                        ('variable' in (getattr(report, 'report_name', '') or '').lower()) or \
                        (explicit_rpm is True and explicit_dia is False)

    show_dia = (explicit_dia if explicit_dia is not None else getattr(pump, 'graph_show_dia_overlay', True))
    show_rpm = (explicit_rpm if explicit_rpm is not None else getattr(pump, 'graph_show_rpm_overlay', True))

    # Conflict resolution: if one is explicitly requested by the report, turn the other off (unless both were explicitly requested)
    if explicit_dia is True and explicit_rpm is None:
        show_rpm = False
    elif explicit_rpm is True and explicit_dia is None:
        show_dia = False

    # ── Resolve Operating Duty Point & Optimal Trim / Speed Ratio ──
    q_duty_val = None
    h_duty_val = None
    r_opt = None
    try:
        from flask import request, session
        if request:
            q_d = _safe_float(request.args.get('q_duty') or request.args.get('q') or request.args.get('flow'))
            h_d = _safe_float(request.args.get('h_duty') or request.args.get('h') or request.args.get('head'))
            if (not q_d or not h_d) and session:
                s_data = session.get('selection_form_data', {})
                q_d = q_d or _safe_float(s_data.get('q_duty') or s_data.get('q'))
                h_d = h_d or _safe_float(s_data.get('h_duty') or s_data.get('h'))
            if q_d and h_d and q_d > 0 and h_d > 0:
                q_duty_val = q_d
                h_duty_val = h_d
                q_m3h = q_duty_val / fQ_curve
                h_m = h_duty_val / fH_curve
                r_opt = _calc_optimal_trim_ratio(pump, q_m3h, h_m)
    except Exception:
        pass

    # Determine primary vs secondary display selection
    show_primary = (show_rpm if is_variable_speed else show_dia)
    show_secondary = (show_dia if is_variable_speed else show_rpm)

    # ── 1. Variable Speed Family (Constant Diameter, Varying Speeds) ──
    if is_variable_speed:
        rpm_str = (getattr(pump, 'graph_rpm_values', None) or '').strip()
        from pump_curves import speed_lines as calc_speed_lines
        spd_objs = calc_speed_lines(pump, values_str=rpm_str)

        lines_to_draw = []
        if show_primary:
            if mode == 'max_only':
                lines_to_draw = [spd_objs[0]] if spd_objs else []
            elif mode == 'min_max':
                lines_to_draw = [spd_objs[0], spd_objs[-1]] if len(spd_objs) >= 2 else (spd_objs if spd_objs else [])
            elif mode == 'rated_only':
                lines_to_draw = []
            else:
                lines_to_draw = spd_objs if spd_objs else []

            for c_idx, sl in enumerate(lines_to_draw):
                is_primary = (c_idx == 0)
                rpm_val = _safe_float(sl.get('rpm', pump.speed_rpm)) or 1450.0
                s_ratio = _safe_float(sl.get('ratio', 1.0)) or 1.0
                pct = round(s_ratio * 100) if s_ratio else None
                lbl = f"{int(round(rpm_val))} RPM (Max)" if is_primary else f"{int(round(rpm_val))} RPM"

                k = float(s_ratio)
                c_q = [round(v * k, 2) for v in q_pts]
                c_h = [round(v * (k**2), 2) for v in h_pts]
                c_eta = [round(max(0.0, v), 2) for v in eta_pts]
                c_pow = [round(v * (k**3), 2) for v in pow_pts]
                c_npsh = [round(v * (k**2), 2) for v in npsh_pts]

                cur_color = primary_color if is_primary else palette[min(c_idx, len(palette)-1)]

                hq_curves_list.append({'label': lbl, 'x': c_q, 'y': c_h, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': rpm_val, 'rpm': rpm_val})
                eta_curves_list.append({'label': lbl, 'x': c_q, 'y': c_eta, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': rpm_val, 'rpm': rpm_val})
                pow_curves_list.append({'label': lbl, 'x': c_q, 'y': c_pow, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': rpm_val, 'rpm': rpm_val})
                npsh_curves_list.append({'label': lbl, 'x': c_q, 'y': c_npsh, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': rpm_val, 'rpm': rpm_val})

        # ── Overlay Rated Speed Curve (if show_rated is enabled or mode == 'rated_only') ──
        if show_rated or mode == 'rated_only':
            rated_rpm = None
            try:
                if request:
                    rpm_arg = request.args.get('rpm') or request.args.get('speed') or request.args.get('rated_speed') or request.args.get('optimal_speed_rpm')
                    if rpm_arg:
                        rated_rpm = _safe_float(rpm_arg)
            except Exception:
                pass
            if not rated_rpm and r_opt:
                base_spd = spd_objs[0].get('rpm', pump.speed_rpm) if spd_objs else (pump.speed_rpm or 1450.0)
                rated_rpm = round(base_spd * r_opt)
            if not rated_rpm:
                if mode == 'rated_only':
                    rated_rpm = pump.speed_rpm or (spd_objs[0].get('rpm') if spd_objs else 1450.0)

            if rated_rpm and rated_rpm > 0:
                base_spd = spd_objs[0].get('rpm', pump.speed_rpm) if spd_objs else (pump.speed_rpm or 1450.0)
                s_ratio = (rated_rpm / base_spd) if base_spd else 1.0
                k = float(s_ratio)
                pct = round(s_ratio * 100) if s_ratio else None
                lbl = f"{int(round(rated_rpm))} RPM (Rated)"
                c_q = [round(v * k, 2) for v in q_pts]
                c_h = [round(v * (k**2), 2) for v in h_pts]
                c_eta = [round(max(0.0, v), 2) for v in eta_pts]
                c_pow = [round(v * (k**3), 2) for v in pow_pts]
                c_npsh = [round(v * (k**2), 2) for v in npsh_pts]
                rated_color = '#d97706'

                if mode == 'rated_only':
                    hq_curves_list = [{'label': lbl, 'x': c_q, 'y': c_h, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm}]
                    eta_curves_list = [{'label': lbl, 'x': c_q, 'y': c_eta, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm}]
                    pow_curves_list = [{'label': lbl, 'x': c_q, 'y': c_pow, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm}]
                    npsh_curves_list = [{'label': lbl, 'x': c_q, 'y': c_npsh, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm}]
                else:
                    exists = any(abs(c.get('val', 0) - rated_rpm) < 1.0 for c in hq_curves_list)
                    if not exists:
                        hq_curves_list.append({'label': lbl, 'x': c_q, 'y': c_h, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm})
                        eta_curves_list.append({'label': lbl, 'x': c_q, 'y': c_eta, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm})
                        pow_curves_list.append({'label': lbl, 'x': c_q, 'y': c_pow, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm})
                        npsh_curves_list.append({'label': lbl, 'x': c_q, 'y': c_npsh, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_rpm, 'rpm': rated_rpm})

        # Secondary Diameter Overlay curves
        dia_str = (getattr(pump, 'graph_dia_overlay_values', None) or '').strip()
        if show_secondary and dia_str and mode != 'rated_only':
            try:
                from pump_curves import _dia_overlay_lines
                dia_objs = _dia_overlay_lines(pump, values_str=dia_str)
                is_main_sec = (not show_primary)
                for dl_idx, dl in enumerate(dia_objs):
                    lbl = dl.get('label', '')
                    is_top = (dl_idx == 0)
                    cur_color = (primary_color if is_top else palette[min(dl_idx, len(palette)-1)]) if is_main_sec else '#d97706'
                    d_ratio = dl.get('ratio', 1.0)
                    pct = round(d_ratio * 100) if d_ratio else None

                    if dl.get('q') and dl.get('h'):
                        hq_curves_list.append({'label': lbl, 'x': dl['q'], 'y': dl['h'], 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': dl.get('dia')})
                    if dl.get('q') and dl.get('eta'):
                        eta_curves_list.append({'label': lbl, 'x': dl['q'], 'y': dl['eta'], 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': dl.get('dia')})
                    pwr_arr = dl.get('pow') or dl.get('power')
                    if dl.get('q') and pwr_arr:
                        pow_curves_list.append({'label': lbl, 'x': dl['q'], 'y': pwr_arr, 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': dl.get('dia')})
                    if dl.get('q') and dl.get('npsh'):
                        npsh_curves_list.append({'label': lbl, 'x': dl['q'], 'y': dl['npsh'], 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': dl.get('dia')})
            except Exception as e:
                print("Diameter overlay lines calculation notice:", e)

    # ── 2. Trimmed Impeller Pump Curve Family & Overlays ──
    else:
        if mode == 'max_only':
            d_curves = [max_d]
        elif mode == 'min_max':
            if len(custom_d_list) >= 2:
                d_curves = [max_d, custom_d_list[-1]]
            else:
                d_curves = [max_d, round(max_d * 0.8, 1)]
        elif mode == 'rated_only':
            d_curves = []
        else:  # mode == 'all'
            if len(custom_d_list) >= 3:
                d_curves = custom_d_list
            elif len(custom_d_list) == 2:
                steps = np.linspace(custom_d_list[0], custom_d_list[-1], 4)
                d_curves = [float(round(x)) for x in steps]
            else:
                d_curves = [max_d, float(round(max_d * 0.93)), float(round(max_d * 0.86)), float(round(max_d * 0.8))]

        # Primary Diameter trim curves
        curves_to_draw = d_curves
        for c_idx, d_val in enumerate(curves_to_draw):
                is_primary = (c_idx == 0)
                d_fmt = f"{round(d_val)}" if abs(d_val - round(d_val)) < 1e-4 else f"{round(d_val, 1)}"
                lbl = f"Ø{d_fmt} mm (Max)" if is_primary else f"Ø{d_fmt} mm"
                d_ratio = d_val / max_d
                pct = round(d_ratio * 100)

                c_q = [round(v * d_ratio, 2) for v in q_pts]
                c_h = [round(v * (d_ratio**2), 2) for v in h_pts]
                c_eta = [round(max(0.0, v), 2) for v in eta_pts]
                c_pow = [round(v * (d_ratio**3), 2) for v in pow_pts]
                c_npsh = [round(v * (d_ratio**2), 2) for v in npsh_pts]

                cur_color = primary_color if is_primary else palette[min(c_idx, len(palette)-1)]

                hq_curves_list.append({'label': lbl, 'x': c_q, 'y': c_h, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})
                eta_curves_list.append({'label': lbl, 'x': c_q, 'y': c_eta, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})
                pow_curves_list.append({'label': lbl, 'x': c_q, 'y': c_pow, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})
                npsh_curves_list.append({'label': lbl, 'x': c_q, 'y': c_npsh, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})

        # ── Overlay Rated Impeller Diameter Curve (if show_rated is enabled or mode == 'rated_only') ──
        if show_rated or mode == 'rated_only':
            rated_d = None
            try:
                if request:
                    dia_arg = request.args.get('dia') or request.args.get('trim_dia') or request.args.get('rated_dia') or request.args.get('impeller_dia') or request.args.get('optimal_trim_dia_mm')
                    if dia_arg:
                        rated_d = _safe_float(dia_arg)
            except Exception:
                pass
            if not rated_d and r_opt:
                rated_d = round(max_d * r_opt, 1)
            if not rated_d:
                if mode == 'rated_only':
                    rated_d = pump.impeller_dia_mm if (pump.impeller_dia_mm and pump.impeller_dia_mm > 0) else max_d

            if rated_d and rated_d > 0:
                d_ratio = rated_d / max_d
                pct = round(d_ratio * 100)
                d_fmt = f"{round(rated_d)}" if abs(rated_d - round(rated_d)) < 1e-4 else f"{round(rated_d, 1)}"
                lbl = f"Ø{d_fmt} mm (Rated)"
                c_q = [round(v * d_ratio, 2) for v in q_pts]
                c_h = [round(v * (d_ratio**2), 2) for v in h_pts]
                c_eta = [round(max(0.0, v), 2) for v in eta_pts]
                c_pow = [round(v * (d_ratio**3), 2) for v in pow_pts]
                c_npsh = [round(v * (d_ratio**2), 2) for v in npsh_pts]
                rated_color = '#d97706'

                if mode == 'rated_only':
                    hq_curves_list = [{'label': lbl, 'x': c_q, 'y': c_h, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d}]
                    eta_curves_list = [{'label': lbl, 'x': c_q, 'y': c_eta, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d}]
                    pow_curves_list = [{'label': lbl, 'x': c_q, 'y': c_pow, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d}]
                    npsh_curves_list = [{'label': lbl, 'x': c_q, 'y': c_npsh, 'color': rated_color, 'is_secondary': False, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d}]
                else:
                    exists = any(abs(c.get('val', 0) - rated_d) < 0.5 for c in hq_curves_list)
                    if not exists:
                        hq_curves_list.append({'label': lbl, 'x': c_q, 'y': c_h, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d})
                        eta_curves_list.append({'label': lbl, 'x': c_q, 'y': c_eta, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d})
                        pow_curves_list.append({'label': lbl, 'x': c_q, 'y': c_pow, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d})
                        npsh_curves_list.append({'label': lbl, 'x': c_q, 'y': c_npsh, 'color': rated_color, 'is_secondary': True, 'is_rated': True, 'pct': pct, 'val': rated_d, 'dia': rated_d})

        # Secondary RPM Speed Overlay curves
        rpm_str = (getattr(pump, 'graph_rpm_overlay_values', None) or '').strip()
        if show_secondary and rpm_str and mode != 'rated_only':
            try:
                from pump_curves import speed_lines as calc_speed_lines
                spd_objs = calc_speed_lines(pump, values_str=rpm_str)
                is_main_sec = (not show_primary)
                for sl_idx, sl in enumerate(spd_objs):
                    lbl = sl.get('label', '')
                    is_top = (sl_idx == 0)
                    cur_color = (primary_color if is_top else palette[min(sl_idx, len(palette)-1)]) if is_main_sec else '#d97706'
                    s_ratio = sl.get('ratio', 1.0)
                    pct = round(s_ratio * 100) if s_ratio else None

                    if sl.get('q') and sl.get('h'):
                        hq_curves_list.append({'label': lbl, 'x': sl['q'], 'y': sl['h'], 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': sl.get('rpm')})
                    if sl.get('q') and sl.get('eta'):
                        eta_curves_list.append({'label': lbl, 'x': sl['q'], 'y': sl['eta'], 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': sl.get('rpm')})
                    pwr_arr = sl.get('pow') or sl.get('power')
                    if sl.get('q') and pwr_arr:
                        pow_curves_list.append({'label': lbl, 'x': sl['q'], 'y': pwr_arr, 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': sl.get('rpm')})
                    if sl.get('q') and sl.get('npsh'):
                        npsh_curves_list.append({'label': lbl, 'x': sl['q'], 'y': sl['npsh'], 'color': cur_color, 'is_secondary': not (is_main_sec and is_top), 'pct': pct, 'val': sl.get('rpm')})
            except Exception as e:
                print("RPM overlay lines calculation notice:", e)

    # Read Exact Axis Scales configured for the pump in pump-data (min, max, major, minor)
    x_flow_min = getattr(pump, 'axis_flow_min', None)
    x_flow_max = getattr(pump, 'axis_flow_max', None)
    x_flow_maj = getattr(pump, 'axis_flow_major', None)
    x_flow_minr = getattr(pump, 'axis_flow_minor', None)

    x_clean = _clean_axis_scale(
        x_flow_min, x_flow_max, x_flow_maj, x_flow_minr,
        conv_factor=fQ_raw, default_min=(pump.q_min or 0.0) * fQ_curve, default_max=q_max * fQ_curve
    )
    
    x_common = {
        'x_min': x_clean['min'],
        'x_max': x_clean['max'],
        'x_major': x_clean['major'],
        'x_minor': x_clean['minor'],
    }

    # Head Y-Axis MIN defaults to 0.0 for standard pump head baseline
    h_min_val = getattr(pump, 'axis_head_min', None)
    h_max_val = getattr(pump, 'axis_head_max', None)
    h_maj_val = getattr(pump, 'axis_head_major', None)
    h_minr_val = getattr(pump, 'axis_head_minor', None)
    
    if h_min_val is not None and (h_min_val == '' or float(h_min_val) == 20.0):
        h_min_val = 0.0

    h_clean = _clean_axis_scale(
        h_min_val, h_max_val, h_maj_val, h_minr_val,
        conv_factor=fH_raw, default_min=0.0, default_max=(max(h_pts) * 1.12 if max(h_pts) > 0 else 10.0) * fH_curve
    )

    h_custom_range = dict(x_common)
    h_custom_range.update({
        'y_min': h_clean['min'],
        'y_max': h_clean['max'],
        'y_major': h_clean['major'],
        'y_minor': h_clean['minor'],
    })

    eta_min_val = getattr(pump, 'axis_eff_min', None)
    eta_max_val = getattr(pump, 'axis_eff_max', None)
    eta_maj_val = getattr(pump, 'axis_eff_major', None)
    eta_minr_val = getattr(pump, 'axis_eff_minor', None)
    eta_clean = _clean_axis_scale(
        eta_min_val, eta_max_val, eta_maj_val, eta_minr_val,
        conv_factor=1.0, default_min=0.0, default_max=100.0
    )
    eta_custom_range = dict(x_common)
    eta_custom_range.update({
        'y_min': eta_clean['min'],
        'y_max': eta_clean['max'],
        'y_major': eta_clean['major'],
        'y_minor': eta_clean['minor'],
    })

    pow_min_val = getattr(pump, 'axis_power_min', None)
    pow_max_val = getattr(pump, 'axis_power_max', None)
    pow_maj_val = getattr(pump, 'axis_power_major', None)
    pow_minr_val = getattr(pump, 'axis_power_minor', None)
    pow_clean = _clean_axis_scale(
        pow_min_val, pow_max_val, pow_maj_val, pow_minr_val,
        conv_factor=fPow_raw, default_min=0.0, default_max=(max(pow_pts) * 1.15 if max(pow_pts) > 0 else 10.0) * fPow_curve
    )
    pow_custom_range = dict(x_common)
    pow_custom_range.update({
        'y_min': pow_clean['min'],
        'y_max': pow_clean['max'],
        'y_major': pow_clean['major'],
        'y_minor': pow_clean['minor'],
    })

    npsh_min_val = getattr(pump, 'axis_npsh_min', None)
    npsh_max_val = getattr(pump, 'axis_npsh_max', None)
    npsh_maj_val = getattr(pump, 'axis_npsh_major', None)
    npsh_minr_val = getattr(pump, 'axis_npsh_minor', None)
    npsh_clean = _clean_axis_scale(
        npsh_min_val, npsh_max_val, npsh_maj_val, npsh_minr_val,
        conv_factor=fNpsh_raw, default_min=0.0, default_max=(max(npsh_pts) * 1.2 if max(npsh_pts) > 0 else 10.0) * fNpsh_curve
    )
    npsh_custom_range = dict(x_common)
    npsh_custom_range.update({
        'y_min': npsh_clean['min'],
        'y_max': npsh_clean['max'],
        'y_major': npsh_clean['major'],
        'y_minor': npsh_clean['minor'],
    })

    # Build Isolines (Efficiency, Power, Speed lines) for the H-Q map
    hq_isolines_list = []

    # Import isoline generators and helper for override scaling
    from pump_curves import _compute_iso_override, efficiency_isolines, power_isolines, npsh_isolines

    # Compute isoline range (r_min) bounded strictly by the bottom-most curve plotted on the chart
    if show_rpm:
        iso_r_min = min([sl.get('ratio', 1.0) for sl in lines_to_draw]) if lines_to_draw else 0.70
        iso_trim = 0.0
    else:
        # We are showing diameter curves (either for fixed speed pump, or VSD overridden to show mm)
        from pump_curves import family_curves_diameter
        if 'curves_to_draw' in locals() and curves_to_draw:
            iso_r_min = min([d / max_d for d in curves_to_draw])
        elif 'dia_objs' in locals() and dia_objs:
            iso_r_min = min([dl.get('ratio', 1.0) for dl in dia_objs])
        else:
            iso_r_min = 0.75
        iso_trim = 20.0

    # 1. Efficiency Isolines
    show_eff = getattr(report, 'show_eff_isolines', True)
    if show_eff is None:
        show_eff = getattr(pump, 'graph_show_eff_iso', True)
    if show_eff:
        eff_iso_str = (
            getattr(report, 'eff_isolines', None) or
            getattr(pump, 'graph_eff_levels', None) or
            getattr(pump, 'eff_isolines', None)
        )
        levels = _parse_diameters_string(eff_iso_str) if (eff_iso_str and str(eff_iso_str).strip()) else None
        try:
            iso_objs = efficiency_isolines(pump, iso_levels=levels, override_r_min=iso_r_min, override_trim_penalty=iso_trim)
            for iso_i, iso in enumerate(iso_objs):
                eta_val = iso.get('eta', 0.0)
                lbl_val = f"{int(round(eta_val)) if abs(eta_val - round(eta_val)) < 1e-4 else round(eta_val,1)}%"
                hq_isolines_list.append({
                    'x': iso.get('q', []),
                    'y': iso.get('h', []),
                    'label': lbl_val,
                    'branch': iso.get('branch'),
                    'type_idx': iso_i,
                    'iso_type': 'eta',
                    'color': '#059669',
                    'dash': 'stroke-dasharray="2,2"'
                })
        except Exception as e:
            print("Efficiency isolines calculation notice:", e)

    # 2. Power Isolines
    show_pwr = getattr(report, 'show_power_isolines', None)
    if show_pwr is None:
        show_pwr = getattr(pump, 'graph_show_power_iso', False)
    if show_pwr:
        pwr_iso_str = (
            getattr(report, 'power_isolines', None) or
            getattr(pump, 'graph_power_levels', None)
        )
        p_levels = _parse_diameters_string(pwr_iso_str) if (pwr_iso_str and str(pwr_iso_str).strip()) else None
        try:
            pwr_objs = power_isolines(pump, power_levels=p_levels, override_r_min=iso_r_min)
            for p_i, p_iso in enumerate(pwr_objs):
                p_val = p_iso.get('power', 0.0)
                p_lbl = f"{int(round(p_val)) if abs(p_val - round(p_val)) < 1e-4 else round(p_val,1)} {pump.unit_pow or 'kW'}"
                hq_isolines_list.append({
                    'x': p_iso.get('q', []),
                    'y': p_iso.get('h', []),
                    'label': p_lbl,
                    'branch': p_iso.get('branch'),
                    'type_idx': p_i,
                    'iso_type': 'pow',
                    'color': '#d97706',
                    'dash': 'stroke-dasharray="3,3"'
                })
        except Exception as e:
            print("Power isolines calculation notice:", e)

    # 3. NPSH Isolines
    show_npsh_iso = getattr(report, 'show_npsh_isolines', None)
    if show_npsh_iso is None:
        show_npsh_iso = getattr(pump, 'graph_show_npsh_iso', False)
    if show_npsh_iso:
        npsh_iso_str = (
            getattr(report, 'npsh_isolines', None) or
            getattr(pump, 'graph_npsh_levels', None)
        )
        n_levels = _parse_diameters_string(npsh_iso_str) if (npsh_iso_str and str(npsh_iso_str).strip()) else None
        try:
            npsh_objs = npsh_isolines(pump, iso_levels=n_levels, override_r_min=iso_r_min)
            for n_i, n_iso in enumerate(npsh_objs):
                n_val = n_iso.get('npsh', 0.0)
                n_lbl = f"{round(n_val, 1)} {pump.unit_npsh or 'm'}"
                hq_isolines_list.append({
                    'x': n_iso.get('q', []),
                    'y': n_iso.get('h', []),
                    'label': n_lbl,
                    'branch': n_iso.get('branch'),
                    'type_idx': n_i,
                    'iso_type': 'npsh',
                    'color': '#0284c7',
                    'dash': 'stroke-dasharray="4,2"'
                })
        except Exception as e:
            print("NPSH isolines calculation notice:", e)

    # Custom Label Positions & Format
    p_opts = pump.get_graph_options() if hasattr(pump, 'get_graph_options') else {}
    base_unit_q = p_opts.get('graph_unit_q') or pump.unit_q or 'm3h'
    base_unit_h = p_opts.get('graph_unit_h') or pump.unit_h or 'm'
    base_unit_pow = p_opts.get('graph_unit_pow') or pump.unit_pow or 'kw'
    base_unit_npsh = p_opts.get('graph_unit_npsh') or pump.unit_npsh or 'm'

    raw_custom_pos = pump.get_custom_label_pos() if hasattr(pump, 'get_custom_label_pos') else {}
    rep_label_fmt = getattr(report, 'label_format', 'auto') or 'auto'
    if rep_label_fmt == 'pump_default':
        label_fmt = p_opts.get('label_format', 'auto')
    else:
        label_fmt = rep_label_fmt

    # Scale custom label positions cleanly per chart type from standard SI to report display units
    custom_pos_hq = {}
    custom_pos_eff = {}
    custom_pos_pow = {}
    custom_pos_npsh = {}

    if raw_custom_pos:
        for k, v in raw_custom_pos.items():
            if isinstance(v, dict) and 'x' in v and 'y' in v and v['x'] is not None and v['y'] is not None:
                try:
                    vx = float(v['x'])
                    vy = float(v['y'])
                    # On H-Q chart, all curves and isolines (efficiency, power, npsh) are located on Head Y axis!
                    custom_pos_hq[k] = {'x': vx * fQ_curve, 'y': vy * fH_curve}
                    custom_pos_eff[k] = {'x': vx * fQ_curve, 'y': vy * 1.0}
                    custom_pos_pow[k] = {'x': vx * fQ_curve, 'y': vy * fPow_curve}
                    custom_pos_npsh[k] = {'x': vx * fQ_curve, 'y': vy * fNpsh_curve}
                except (TypeError, ValueError):
                    pass

    # Read Report Legend Visibility & Position Preferences
    rep_leg_mode = getattr(report, 'legend_mode', 'pump_default') or 'pump_default'
    pump_leg_mode = p_opts.get('legend_mode', 'each')

    if rep_leg_mode == 'pump_default':
        effective_legend_mode = pump_leg_mode
    else:
        effective_legend_mode = rep_leg_mode

    show_leg = getattr(report, 'show_legend', True)
    if show_leg is None:
        show_leg = True
    leg_pos = getattr(report, 'legend_position', 'top_right')

    show_leg_hq = bool(show_leg)
    show_leg_sub = bool(show_leg) and (effective_legend_mode != 'hq_only')

    # Function to scale curve list from server base units to report display units
    def scale_curve_list(c_list, fx, fy):
        for c in c_list:
            if 'x' in c: c['x'] = [val * fx for val in c['x']]
            if 'y' in c: c['y'] = [val * fy for val in c['y']]
            if 'bep' in c and isinstance(c['bep'], dict):
                if 'q' in c['bep']: c['bep']['q'] *= fx
                if 'h' in c['bep']: c['bep']['h'] *= fy

    scale_curve_list(hq_curves_list, fQ_curve, fH_curve)
    scale_curve_list(hq_isolines_list, fQ_curve, fH_curve)
    scale_curve_list(eta_curves_list, fQ_curve, 1.0)
    scale_curve_list(pow_curves_list, fQ_curve, fPow_curve)
    scale_curve_list(npsh_curves_list, fQ_curve, fNpsh_curve)

    lbl_q = _unit_label('q', rep_unit_q)
    lbl_h = _unit_label('h', rep_unit_h)
    lbl_pow = _unit_label('pow', rep_unit_pow)
    lbl_npsh = _unit_label('npsh', rep_unit_npsh)

    # ── Dynamic Graph Ordering & Height Split Assignment ──
    hq_active = bool(getattr(report, 'show_head_flow_graph', True))
    eta_active = bool(getattr(report, 'show_additional_graphs', True) and getattr(report, 'show_efficiency_graph', True))
    pow_active = bool(getattr(report, 'show_additional_graphs', True) and getattr(report, 'show_power_graph', True))
    npsh_active = bool(getattr(report, 'show_additional_graphs', True) and getattr(report, 'show_npsh_graph', True) and has_npsh)

    graph_styles = report.get_graph_styles() if (report and hasattr(report, 'get_graph_styles')) else {}

    duty_pt_dict = None
    if q_duty_val and h_duty_val and getattr(report, 'show_duty_point', True):
        duty_pt_dict = {
            'q': q_duty_val,
            'h': h_duty_val,
            'label': f"Duty: {round(q_duty_val, 1)} {rep_unit_q} @ {round(h_duty_val, 1)} {rep_unit_h}"
        }

    graph_defs = {
        'hq': {
            'title': 'Head vs Flow (H-Q)',
            'unit': _unit_label('h', rep_unit_h),
            'color': graph_styles.get('hq_color', getattr(report, 'primary_color', '#1e3a8a')) or '#1e3a8a',
            'is_active': hq_active,
            'builder': lambda h: generate_chart_svg(
                hq_curves_list, f"Flow ({lbl_q})", f"Head ({lbl_h})",
                custom_range=h_custom_range, height=h, isolines_list=hq_isolines_list,
                show_legend=show_leg_hq, legend_position=leg_pos, legend_mode=effective_legend_mode,
                custom_label_pos=custom_pos_hq, label_format=label_fmt, chart_type='hq', graph_styles=graph_styles,
                duty_point=duty_pt_dict
            )
        },
        'eta': {
            'title': 'Efficiency vs Flow (η-Q)',
            'unit': '%',
            'color': graph_styles.get('eta_color', '#059669'),
            'is_active': eta_active,
            'builder': lambda h: generate_chart_svg(
                eta_curves_list, f"Flow ({lbl_q})", "Efficiency (%)",
                custom_range=eta_custom_range, height=h, show_legend=show_leg_sub, legend_position=leg_pos, legend_mode=effective_legend_mode,
                custom_label_pos=custom_pos_eff, label_format=label_fmt, chart_type='eff', graph_styles=graph_styles
            )
        },
        'pow': {
            'title': 'Power vs Flow (P-Q)',
            'unit': _unit_label('pow', rep_unit_pow),
            'color': graph_styles.get('pow_color', '#dc2626'),
            'is_active': pow_active,
            'builder': lambda h: generate_chart_svg(
                pow_curves_list, f"Flow ({lbl_q})", f"Power ({lbl_pow})",
                custom_range=pow_custom_range, height=h, show_legend=show_leg_sub, legend_position=leg_pos, legend_mode=effective_legend_mode,
                custom_label_pos=custom_pos_pow, label_format=label_fmt, chart_type='pow', graph_styles=graph_styles
            )
        },
        'npsh': {
            'title': 'NPSHr vs Flow',
            'unit': _unit_label('npsh', rep_unit_npsh),
            'color': graph_styles.get('npsh_color', '#0284c7'),
            'is_active': npsh_active,
            'builder': lambda h: generate_chart_svg(
                npsh_curves_list, f"Flow ({lbl_q})", f"NPSHr ({lbl_npsh})",
                custom_range=npsh_custom_range, height=h, show_legend=show_leg_sub, legend_position=leg_pos, legend_mode=effective_legend_mode,
                custom_label_pos=custom_pos_npsh, label_format=label_fmt, chart_type='npsh', graph_styles=graph_styles
            )
        }
    }

    configured_order = report.get_graph_order() if (report and hasattr(report, 'get_graph_order')) else ['hq', 'eta', 'pow', 'npsh']
    active_keys = [k for k in configured_order if graph_defs.get(k, {}).get('is_active', False)]
    active_count = len(active_keys)

    splits_dict = report.get_graph_splits() if (report and hasattr(report, 'get_graph_splits')) else {}
    splits = splits_dict.get(str(active_count), [])
    if not splits or len(splits) != active_count:
        splits = [round(100.0 / active_count, 1)] * active_count if active_count > 0 else []

    ordered_graphs = []
    svg_map = {'hq': '', 'eta': '', 'pow': '', 'npsh': ''}

    # Dynamic total reference height from report.graph_area_height (default 520px)
    raw_area_h = str(getattr(report, 'graph_area_height', 'auto') or 'auto').strip().lower()
    match_h = re.search(r'(\d+(?:\.\d+)?)', raw_area_h)
    if match_h:
        val = float(match_h.group(1))
        if 'mm' in raw_area_h:
            total_area_h = val * 3.78
        elif 'in' in raw_area_h:
            total_area_h = val * 96.0
        elif 'pt' in raw_area_h:
            total_area_h = val * 1.333
        else:
            total_area_h = val
    else:
        total_area_h = 520.0

    for idx, k in enumerate(active_keys):
        pct = splits[idx] if idx < len(splits) else (100.0 / active_count)
        # Scaled SVG height based on split % and total area height
        calc_h = max(70, int(round(total_area_h * (pct / 100.0))))
        g_def = graph_defs[k]
        rendered_svg = g_def['builder'](calc_h)
        svg_map[k] = rendered_svg
        ordered_graphs.append({
            'key': k,
            'title': g_def['title'],
            'unit': g_def['unit'],
            'color': g_def['color'],
            'height_pct': pct,
            'calc_h': calc_h,
            'svg': rendered_svg
        })

    # Fallback standard SVGs for legacy single references
    svg_hq = svg_map.get('hq') or (graph_defs['hq']['builder'](240) if hq_active else "")
    svg_eta = svg_map.get('eta') or (graph_defs['eta']['builder'](240) if eta_active else "")
    svg_pow = svg_map.get('pow') or (graph_defs['pow']['builder'](240) if pow_active else "")
    svg_npsh = svg_map.get('npsh') or (graph_defs['npsh']['builder'](240) if npsh_active else "")

    bep_info = None
    try:
        bep_info = bep_point(pump)
    except Exception:
        pass

    final_rated_dia = rated_d if ('rated_d' in locals() and rated_d) else None
    final_rated_rpm = rated_rpm if ('rated_rpm' in locals() and rated_rpm) else None

    return {
        'q_max': q_max,
        'has_npsh': has_npsh,
        'svg_hq': svg_hq,
        'svg_eta': svg_eta,
        'svg_pow': svg_pow,
        'svg_npsh': svg_npsh,
        'ordered_graphs': ordered_graphs,
        'active_graph_count': active_count,
        'bep_info': bep_info,
        'duty_point': duty_pt_dict,
        'rated_dia': round(final_rated_dia, 1) if final_rated_dia else None,
        'rated_rpm': int(round(final_rated_rpm)) if final_rated_rpm else None,
        'rep_unit_q': _unit_label('q', rep_unit_q),
        'rep_unit_h': _unit_label('h', rep_unit_h),
    }


@reports_bp.route('/settings')
def settings():
    reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    available_templates = ['standard_datasheet.html', 'compact_datasheet.html', 'slurry_specsheet.html']
    reports_json = [r.to_dict() for r in reports]
    
    return render_template(
        'reports_settings.html',
        reports=reports,
        reports_json=reports_json,
        suppliers=suppliers,
        available_templates=available_templates
    )


@reports_bp.route('/settings/supplier/save', methods=['POST'])
def save_supplier():
    supplier_id = request.form.get('supplier_id')
    name = request.form.get('name', '').strip()
    
    if not name:
        flash('Supplier name is required.', 'error')
        return redirect(url_for('reports.settings'))
        
    if supplier_id and supplier_id.isdigit():
        supplier = Supplier.query.get_or_404(int(supplier_id))
    else:
        supplier = Supplier()
        db.session.add(supplier)

    supplier.name = name
    supplier.logo_url = request.form.get('logo_url', '').strip()
    supplier.contact_email = request.form.get('contact_email', '').strip()
    supplier.phone = request.form.get('phone', '').strip()
    supplier.website = request.form.get('website', '').strip()
    supplier.address = request.form.get('address', '').strip()
    
    db.session.commit()
    flash(f'Supplier "{name}" saved successfully.', 'success')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/settings/report/save_graph_area', methods=['POST'])
def save_graph_area():
    """Dedicated endpoint to save Graph Area dimensions, order, and height splits."""
    report_id = request.form.get('report_id')
    if not report_id or not report_id.isdigit():
        flash('Invalid report selected.', 'error')
        return redirect(url_for('reports.settings'))
    
    report = ReportConfig.query.get_or_404(int(report_id))
    report.graph_area_top = request.form.get('graph_area_top', '4px').strip() or '4px'
    report.graph_area_left = request.form.get('graph_area_left', '0px').strip() or '0px'
    report.graph_area_width = request.form.get('graph_area_width', '100%').strip() or '100%'
    report.graph_area_height = request.form.get('graph_area_height', 'auto').strip() or 'auto'
    report.graph_order = request.form.get('graph_order', 'hq,eta,pow,npsh').strip() or 'hq,eta,pow,npsh'
    report.graph_splits_json = request.form.get('graph_splits_json', '').strip() or '{"1":[100],"2":[55,45],"3":[40,30,30],"4":[30,25,25,20]}'

    db.session.commit()
    flash(f'Graph area settings for "{report.title}" updated successfully.', 'success')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/settings/report/save', methods=['POST'])
def save_report():
    report_id = request.form.get('report_id')
    title = request.form.get('title', '').strip()
    supplier_id = request.form.get('supplier_id')
    
    if not title:
        flash('Report title is required.', 'error')
        return redirect(url_for('reports.settings'))
        
    if report_id and report_id.isdigit():
        report = ReportConfig.query.get_or_404(int(report_id))
    else:
        report = ReportConfig()
        db.session.add(report)

    report.title = title
    report.report_name = request.form.get('report_name', 'standard').strip() or 'standard'
    report.report_type = request.form.get('report_type', 'Technical Datasheet').strip() or 'Technical Datasheet'
    report.organisation_id = int(supplier_id) if supplier_id and supplier_id.isdigit() else None
    report.description = request.form.get('description', '').strip()
    report.template_name = request.form.get('template_name', 'standard_datasheet.html').strip()
    
    report.show_head_flow_graph = 'show_head_flow_graph' in request.form
    report.show_efficiency_graph = 'show_efficiency_graph' in request.form
    report.show_power_graph = 'show_power_graph' in request.form
    report.show_npsh_graph = 'show_npsh_graph' in request.form

    report.show_eff_isolines = 'show_eff_isolines' in request.form
    report.show_power_isolines = 'show_power_isolines' in request.form
    report.show_npsh_isolines = 'show_npsh_isolines' in request.form or 'show_npsh_curves' in request.form
    report.show_npsh_curves = report.show_npsh_isolines
    report.show_speed_lines = 'show_speed_lines' in request.form or 'show_rpm_overlay' in request.form
    report.show_rpm_overlay = 'show_rpm_overlay' in request.form or 'show_speed_lines' in request.form
    report.show_dia_overlay = 'show_dia_overlay' in request.form
    report.show_additional_graphs = 'show_additional_graphs' in request.form
    report.show_legend = 'show_legend' in request.form
    report.legend_position = request.form.get('legend_position', 'top_right').strip()
    report.legend_mode = request.form.get('legend_mode', 'pump_default').strip()
    report.label_format = request.form.get('label_format', 'auto').strip()

    # Graph Area Geometry & Vertical Layout Settings
    report.graph_area_top = request.form.get('graph_area_top', '4px').strip() or '4px'
    report.graph_area_left = request.form.get('graph_area_left', '0px').strip() or '0px'
    report.graph_area_width = request.form.get('graph_area_width', '100%').strip() or '100%'
    report.graph_area_height = request.form.get('graph_area_height', 'auto').strip() or 'auto'
    report.graph_order = request.form.get('graph_order', 'hq,eta,pow,npsh').strip() or 'hq,eta,pow,npsh'
    report.graph_splits_json = request.form.get('graph_splits_json', '').strip() or '{"1":[100],"2":[55,45],"3":[40,30,30],"4":[30,25,25,20]}'
    report.graph_styles_json = request.form.get('graph_styles_json', '').strip() or '{}'

    report.unit_flow = request.form.get('unit_flow', '').strip() or None
    report.unit_head = request.form.get('unit_head', '').strip() or None
    report.unit_power = request.form.get('unit_power', '').strip() or None
    report.unit_npsh = request.form.get('unit_npsh', '').strip() or None

    report.header_text = request.form.get('header_text', 'PUMP MASTER PRO - TECHNICAL DATASHEET').strip()
    report.footer_text = request.form.get('footer_text', 'Generated by Pump Master Pro Engineering Suite').strip()
    report.primary_color = request.form.get('primary_color', '#1e3a8a').strip()
    report.curve_display_mode = request.form.get('curve_display_mode', 'all').strip()
    report.show_rated_curve = 'show_rated_curve' in request.form
    report.show_duty_point = 'show_duty_point' in request.form
    report.show_materials_table = 'show_materials_table' in request.form
    report.show_extended_specs = 'show_extended_specs' in request.form
    report.show_notes = 'show_notes' in request.form
    report.is_active = 'is_active' in request.form

    db.session.commit()
    flash(f'Report configuration "{report.title}" saved successfully.', 'success')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/settings/report/delete/<int:id>', methods=['POST'])
def delete_report(id):
    report = ReportConfig.query.get_or_404(id)
    title = report.title
    db.session.delete(report)
    db.session.commit()
    flash(f'Report "{title}" deleted.', 'info')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/view/<int:report_id>/pump/<int:pump_id>')
def view_report(report_id, pump_id):
    report = ReportConfig.query.get_or_404(report_id)
    pump = Pump.query.get_or_404(pump_id)
    
    template_file = f"reports/{report.template_name}" if report.template_name else "reports/standard_datasheet.html"
    current_date = datetime.now().strftime("%B %d, %Y")
    
    curves_ctx = _build_report_curve_context(pump, report)

    report_content = render_template(
        template_file,
        report=report,
        pump=pump,
        supplier=report.supplier,
        current_date=current_date,
        curves=curves_ctx,
        is_pdf_export=False
    )

    return render_template(
        'reports/report_wrapper.html',
        report=report,
        pump=pump,
        supplier=report.supplier,
        report_content=report_content
    )


@reports_bp.route('/download/<int:report_id>/pump/<int:pump_id>')
def download_pdf(report_id, pump_id):
    """
    Beginners Note: Converts the report template into a downloadable PDF stream attachment.
    Does NOT save a copy into the repository pdf/ folder.
    Renders 100% pixel-perfect PDF file using Headless Chromium or xhtml2pdf fallback,
    and returns the byte stream directly to the browser.
    """
    report = ReportConfig.query.get_or_404(report_id)
    pump = Pump.query.get_or_404(pump_id)
    
    template_file = f"reports/{report.template_name}" if report.template_name else "reports/standard_datasheet.html"
    current_date = datetime.now().strftime("%B %d, %Y")
    
    curves_ctx = _build_report_curve_context(pump, report)

    rendered_html = render_template(
        template_file,
        report=report,
        pump=pump,
        supplier=report.supplier,
        current_date=current_date,
        curves=curves_ctx,
        is_pdf_export=True
    )

    clean_name = re.sub(r'[^\w\-]', '_', pump.name or 'Pump').strip('_')
    filename = f"Report_{clean_name}.pdf"

    # Temporary output path for Headless browser PDF generation
    temp_pdf = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.pdf', delete=False) as f:
            temp_pdf = f.name

        rendered_success = render_pdf_with_headless_browser(rendered_html, temp_pdf)
        
        if rendered_success and os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 0:
            with open(temp_pdf, 'rb') as f:
                pdf_bytes = f.read()
            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        print("Headless PDF stream notice:", e)
    finally:
        if temp_pdf and os.path.exists(temp_pdf):
            try:
                os.remove(temp_pdf)
            except Exception:
                pass

    # Fallback response via xhtml2pdf if Headless Chromium is bypassed
    try:
        from xhtml2pdf import pisa
        pdf_stream = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(rendered_html), dest=pdf_stream)
        
        if not pisa_status.err:
            pdf_bytes = pdf_stream.getvalue()
            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        print("xhtml2pdf fallback notice:", e)

    response = make_response(rendered_html)
    response.headers['Content-Type'] = 'text/html'
    return response


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

