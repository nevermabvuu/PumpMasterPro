"""
routes/reports.py — Reports & Settings Blueprint

Beginners Note: This module manages PDF report configurations, supplier branding profiles,
HTML report template rendering, automated Action Bar injection, exact pump curve evaluation,
pump-data axis scale matching (min, max, major, minor), NPSH auto-detection, multi-curve display modes (all, max_only, min_max),
and 100% pixel-perfect PDF file generation via Headless Chromium.
"""

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
    - If conv_factor == 1.0 (primary units / no conversion): strictly respects user-defined graph bounds and intervals.
    - If conv_factor != 1.0 (display units converted): adapts intervals to the closest standard engineering round numbers
      (multiples of 1, 1.5, 2, 2.5, 5, 10 * 10^k yielding clean 5s, 10s, 20s, 50s...) and expands max to the next clean multiple,
      ensuring highly readable axes without awkward fractional decimals (e.g. 20, 40, 60... instead of 21.6, 43.2, 64.8...).
    """
    import math
    is_conv = abs(conv_factor - 1.0) > 1e-4

    raw_min = (float(min_v) * conv_factor) if min_v is not None else float(default_min)
    raw_max = (float(max_v) * conv_factor) if max_v is not None else (float(default_max) if default_max is not None else None)
    raw_maj = (float(maj_v) * conv_factor) if maj_v is not None else None
    raw_minr = (float(minr_v) * conv_factor) if minr_v is not None else None

    if not is_conv or raw_max is None:
        return {
            'min': raw_min,
            'max': raw_max,
            'major': raw_maj,
            'minor': raw_minr
        }

    span = raw_max - raw_min
    if span <= 0:
        return {'min': raw_min, 'max': raw_max, 'major': raw_maj, 'minor': raw_minr}

    target_step = raw_maj if (raw_maj and raw_maj > 0) else (span / 5.0)

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
    if raw_minr and raw_minr > 0 and raw_maj and raw_maj > 0:
        sub_divs = round(raw_maj / raw_minr)
        if sub_divs > 1:
            allowed_divs = [2, 4, 5, 10]
            best_div = min(allowed_divs, key=lambda d: abs(d - sub_divs))
            clean_minor = round(clean_step / best_div, 4) if (clean_step / best_div) < 1 else round(clean_step / best_div, 2)

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

def generate_chart_svg(curves_list, x_label="Flow (m³/h)", y_label="Head (m)", custom_range=None, width=480, height=240, isolines_list=None, show_legend=True, legend_position='top_right', legend_mode='each', custom_label_pos=None, label_format='auto', chart_type='hq'):
    """
    Beginners Note: Generates pure inline SVG XML vector markup for single or multi-curve pump charts.
    Accepts exact axis range settings (min, max, major, minor) set for the pump in pump-data,
    supports displaying multiple impeller diameter/speed curves (all, max_only, min_max),
    renders constant efficiency/power isolines and speed lines, and supports configurable legend placement & direct curve labels!
    
    chart_type parameter ('hq', 'eff', 'pow', 'npsh') ensures label drag coordinates saved on one graph (e.g. H-Q Head in meters)
    do not bleed into other graphs with different Y-axis units (e.g. Efficiency in %, Power in kW).
    """
    if not curves_list and not isolines_list:
        return ""

    padding_left = 40
    padding_right = 16
    padding_top = 10
    padding_bottom = 24

    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

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

    # Preserve exact custom bounds when provided to maintain pixel-perfect matching with pump-data Plotly charts
    if x_ticks and not has_custom_x_max:
        x_min = x_ticks[0]
        x_max = max(x_max, x_ticks[-1])
    if y_ticks and not has_custom_y_max:
        y_min = y_ticks[0]
        y_max = max(y_max, y_ticks[-1])

    grid_lines = []
    labels = []

    # X Minor Grid Lines (if set in pump-data)
    if x_minor and x_minor > 0:
        curr_m = x_min + x_minor
        while curr_m < x_max - 1e-5:
            if not any(abs(curr_m - t) < 1e-4 for t in x_ticks):
                px = padding_left + ((curr_m - x_min) / (x_max - x_min)) * plot_w
                grid_lines.append(f'<line x1="{px:.1f}" y1="{padding_top}" x2="{px:.1f}" y2="{padding_top + plot_h}" stroke="#cbd5e1" stroke-width="0.7" stroke-dasharray="1,3" />')
            curr_m += x_minor

    # Y Minor Grid Lines (if set in pump-data)
    if y_minor and y_minor > 0:
        curr_m = y_min + y_minor
        while curr_m < y_max - 1e-5:
            if not any(abs(curr_m - t) < 1e-4 for t in y_ticks):
                py = padding_top + plot_h - ((curr_m - y_min) / (y_max - y_min)) * plot_h
                grid_lines.append(f'<line x1="{padding_left}" y1="{py:.1f}" x2="{width - padding_right}" y2="{py:.1f}" stroke="#cbd5e1" stroke-width="0.7" stroke-dasharray="1,3" />')
            curr_m += y_minor

    # X Major Grid Lines & Labels
    for val in x_ticks:
        if x_min - 1e-5 <= val <= x_max + 1e-5:
            px = padding_left + ((val - x_min) / (x_max - x_min)) * plot_w
            grid_lines.append(f'<line x1="{px:.1f}" y1="{padding_top}" x2="{px:.1f}" y2="{padding_top + plot_h}" stroke="#94a3b8" stroke-dasharray="3,3" stroke-width="1.2" />')
            val_str = f"{val:.0f}" if abs(val - round(val)) < 1e-5 else f"{val:.1f}"
            labels.append(f'<text x="{px:.1f}" y="{padding_top + plot_h + 11}" font-size="8.5" font-family="Helvetica, Arial, sans-serif" fill="#475569" text-anchor="middle">{val_str}</text>')

    # Y Major Grid Lines & Labels
    for val in y_ticks:
        if y_min - 1e-5 <= val <= y_max + 1e-5:
            py = padding_top + plot_h - ((val - y_min) / (y_max - y_min)) * plot_h
            grid_lines.append(f'<line x1="{padding_left}" y1="{py:.1f}" x2="{width - padding_right}" y2="{py:.1f}" stroke="#94a3b8" stroke-dasharray="3,3" stroke-width="1.2" />')
            val_str = f"{val:.0f}" if abs(val - round(val)) < 1e-5 else f"{val:.1f}"
            labels.append(f'<text x="{padding_left - 5}" y="{py + 3:.1f}" font-size="8.5" font-family="Helvetica, Arial, sans-serif" fill="#475569" text-anchor="end">{val_str}</text>')

    paths_svg = []
    legend_items = []
    drawn_label_keys = set()

    # Render Isolines Overlay (Efficiency Isolines, Power Isolines, NPSH Isolines)
    if isolines_list:
        for iso_idx, iso in enumerate(isolines_list):
            iso_x = iso.get('x', [])
            iso_y = iso.get('y', [])
            iso_color = iso.get('color', '#059669')
            iso_label = iso.get('label', '')
            iso_dash = iso.get('dash', 'stroke-dasharray="2,2"')

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

            if len(iso_x) == len(iso_y) and len(iso_x) > 1:
                pts = []
                for x, y in zip(iso_x, iso_y):
                    raw_px = padding_left + ((x - x_min) / (x_max - x_min)) * plot_w
                    raw_py = padding_top + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
                    px = min(max(float(padding_left), float(raw_px)), float(width - padding_right))
                    py = min(max(float(padding_top), float(raw_py)), float(padding_top + plot_h))
                    pts.append((px, py))

                if len(pts) > 1:
                    path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
                    for px, py in pts[1:]:
                        path_d += f" L {px:.1f},{py:.1f}"
                    paths_svg.append(f'<path d="{path_d}" fill="none" stroke="{iso_color}" stroke-width="1.2" {iso_dash} stroke-linecap="round" stroke-linejoin="round" />')

                    if iso_label:
                        clean_iso = iso_label.replace('%','').replace('kW','').replace('hp','').replace('m','').replace('ft','').strip()
                        num_m = re.search(r'(\d+(?:\.\d+)?)', iso_label)
                        iso_val = num_m.group(1) if num_m else clean_iso
                        
                        prefix = iso_type
                        candidate_keys = []

                        # 1. Exact branch match (e.g. eta_75_left, eta_75_right, pow_30_left)
                        if iso_branch:
                            candidate_keys.append(f"{prefix}_{iso_val}_{iso_branch}")
                            candidate_keys.append(f"{prefix}_{clean_iso}_{iso_branch}")

                        # 2. Sequential / index match (e.g. pow_10_0, pow_30_4, npsh_2.5_1, eta_30_0)
                        candidate_keys.append(f"{prefix}_{iso_val}_{iso_t_idx}")
                        if iso_idx != iso_t_idx:
                            candidate_keys.append(f"{prefix}_{iso_val}_{iso_idx}")
                        candidate_keys.append(f"{prefix}_{clean_iso}_{iso_t_idx}")

                        # 3. Simple value match (e.g. eta_75, pow_30, npsh_2.5)
                        candidate_keys.append(f"{prefix}_{iso_val}")
                        candidate_keys.append(f"{prefix}_{clean_iso}")
                        candidate_keys.append(f"{prefix}_{iso_label.strip()}")

                        # 4. Fallback raw text labels
                        candidate_keys.append(iso_label.strip())
                        candidate_keys.append(clean_iso)
                        candidate_keys.append(iso_val)

                        pos = find_custom_pos(custom_label_pos, candidate_keys)

                        if pos and isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                            try:
                                c_x = float(pos['x'])
                                c_y = float(pos['y'])
                                m_px = padding_left + ((c_x - x_min) / (x_max - x_min)) * plot_w
                                m_py = padding_top + plot_h - ((c_y - y_min) / (y_max - y_min)) * plot_h
                            except Exception:
                                m_idx = int(len(pts) / 2)
                                m_px, m_py = pts[m_idx]
                        else:
                            # Beginners Note: Fallback to midpoint of isoline curve (matching pump_curves.js) to avoid top-left corner label clashing
                            m_idx = int(len(pts) / 2)
                            m_px, m_py = pts[m_idx]

                        m_px = min(max(float(padding_left + 10), float(m_px)), float(width - padding_right - 10))
                        m_py = min(max(float(padding_top + 10), float(m_py)), float(height - padding_bottom - 5))

                        # Beginners Note: dominant-baseline="central" centers the text vertically on (m_px, m_py) without Y-offset displacement
                        labels.append(f'<text x="{m_px:.1f}" y="{m_py:.1f}" font-size="7.5" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="{iso_color}" text-anchor="middle" dominant-baseline="central">{iso_label}</text>')

    # Render Primary & Trim Pump Curve Paths
    sec_count = 0
    for c_idx, c in enumerate(curves_list or []):
        x_pts = c.get('x', [])
        y_pts = c.get('y', [])
        color = c.get('color', '#1e3a8a')
        label = c.get('label', f'Curve {c_idx+1}')
        is_sec = c.get('is_secondary', False)
        dash_style = 'stroke-dasharray="4,4"' if is_sec else ''

        if is_sec:
            sec_idx = sec_count
            sec_count += 1
        else:
            sec_idx = c_idx

        if len(x_pts) != len(y_pts) or len(x_pts) == 0:
            continue

        pts = []
        for x, y in zip(x_pts, y_pts):
            px = padding_left + ((x - x_min) / (x_max - x_min)) * plot_w
            py = padding_top + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
            pts.append((px, py))

        path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
        for px, py in pts[1:]:
            path_d += f" L {px:.1f},{py:.1f}"

        stroke_w = 2.5 if not is_sec else 1.8
        paths_svg.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{stroke_w}" {dash_style} stroke-linecap="round" />')
        legend_items.append({'label': label, 'color': color})

        # Option 4: Direct labels on each impeller curve
        if legend_mode == 'curve_labels' and len(pts) > 1:
            raw_label = label
            clean_lbl = raw_label.replace(' (Max)', '').replace(' (Fitted)', '').replace(' (Affinity)', '').strip()

            dedup_key = f"{c_idx}_{clean_lbl}"
            if dedup_key in drawn_label_keys:
                continue
            drawn_label_keys.add(dedup_key)

            num_match = re.search(r'(\d+(?:\.\d+)?)', clean_lbl)
            val_key = num_match.group(1) if num_match else clean_lbl
            pct_val = c.get('pct')
            is_rpm_lbl = ('rpm' in clean_lbl.lower()) or ('rpm' in raw_label.lower())
            chart_prefix = f"{chart_type}_" if chart_type != 'hq' else ""

            # Format text badge according to user label_format choice
            if label_format == 'percent':
                if is_rpm_lbl:
                    display_text = f"{val_key} RPM ({pct_val}%)" if pct_val is not None else f"{val_key} RPM"
                else:
                    display_text = f"Ø{val_key} mm ({pct_val}%)" if pct_val is not None else f"Ø{val_key} mm"
            else:  # simple
                if is_rpm_lbl:
                    display_text = f"{val_key} RPM"
                else:
                    display_text = f"{val_key} mm"

            candidate_keys = []
            if is_rpm_lbl:
                simple_rpm_keys = [
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
                    lx = padding_left + ((c_x - x_min) / (x_max - x_min)) * plot_w
                    ly = padding_top + plot_h - ((c_y - y_min) / (y_max - y_min)) * plot_h
                except Exception:
                    idx = int(len(pts) * 0.85)
                    lx, ly = pts[idx]
            else:
                idx = int(len(pts) * 0.85)
                lx, ly = pts[idx]

            lx = min(max(float(padding_left + 15), float(lx)), float(width - padding_right - 15))
            ly = min(max(float(padding_top + 10), float(ly)), float(height - padding_bottom - 5))

            tw = len(display_text) * 5 + 8
            labels.append(f'<rect x="{lx - tw/2:.1f}" y="{ly - 10:.1f}" width="{tw}" height="12" fill="#ffffff" fill-opacity="0.9" stroke="{color}" stroke-width="0.8" rx="3" />')
            labels.append(f'<text x="{lx:.1f}" y="{ly - 1.5:.1f}" font-size="7.5" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="{color}" text-anchor="middle">{display_text}</text>')

    # Render Multi-Curve Legend Box with customizable positioning
    legend_svg = ""
    if show_legend and len(legend_items) >= 1:
        leg_box = []
        b_w = 110
        b_h = 14 + len(legend_items) * 12

        if legend_position == 'top_left':
            box_x = padding_left + 8
            box_y = padding_top + 4
        elif legend_position == 'bottom_right':
            box_x = width - padding_right - b_w - 4
            box_y = height - padding_bottom - b_h - 4
        elif legend_position == 'bottom_left':
            box_x = padding_left + 8
            box_y = height - padding_bottom - b_h - 4
        else:  # 'top_right'
            box_x = width - padding_right - b_w - 4
            box_y = padding_top + 4

        leg_box.append(f'<rect x="{box_x}" y="{box_y}" width="{b_w}" height="{b_h}" fill="#ffffff" fill-opacity="0.9" stroke="#cbd5e1" rx="4" />')
        for l_idx, leg in enumerate(legend_items):
            ly = box_y + 12 + l_idx * 12
            leg_box.append(f'<line x1="{box_x + 8}" y1="{ly - 3}" x2="{box_x + 22}" y2="{ly - 3}" stroke="{leg["color"]}" stroke-width="2" />')
            leg_box.append(f'<text x="{box_x + 26}" y="{ly}" font-size="8" font-family="Helvetica, Arial, sans-serif" fill="#334155">{leg["label"]}</text>')
        legend_svg = "".join(leg_box)

    svg_code = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="auto" style="background:#ffffff; border-radius:4px; display:block;">
  {''.join(grid_lines)}
  <line x1="{padding_left}" y1="{padding_top + plot_h}" x2="{width - padding_right}" y2="{padding_top + plot_h}" stroke="#475569" stroke-width="1.5" />
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + plot_h}" stroke="#475569" stroke-width="1.5" />
  {''.join(labels)}
  <text x="{(padding_left + width - padding_right) / 2}" y="{height - 2}" font-size="9" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="#334155" text-anchor="middle">{x_label}</text>
  <text x="10" y="{(padding_top + padding_top + plot_h) / 2}" font-size="9" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="#334155" text-anchor="middle" transform="rotate(-90 10 {(padding_top + padding_top + plot_h) / 2})">{y_label}</text>
  {''.join(paths_svg)}
  {legend_svg}
</svg>'''
    return svg_code


def _build_report_curve_context(pump, report):
    """
    Beginners Note: Evaluates exact mathematical pump curves using pump_curves.py polynomial math,
    applies exact pump-data axis scale settings (min, max, major, minor), auto-detects NPSHr availability,
    and supports Curve Display Modes (all, max_only, min_max).
    """
    rep_unit_q = getattr(report, 'unit_flow', pump.unit_q) or 'm3h'
    rep_unit_h = getattr(report, 'unit_head', pump.unit_h) or 'm'
    rep_unit_pow = getattr(report, 'unit_power', pump.unit_pow) or 'kw'
    rep_unit_npsh = getattr(report, 'unit_npsh', pump.unit_npsh) or 'm'

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
    q_pts = list(np.linspace(pump.q_min or 0.0, q_max, 60))

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

    palette = ['#1e3a8a', '#0284c7', '#475569', '#d97706']

    report_show_dia = getattr(report, 'show_dia_overlay', None)
    if report_show_dia is None:
        report_show_dia = getattr(report, 'show_family', None)
    if report_show_dia is None:
        report_show_dia = getattr(pump, 'graph_show_dia_overlay', None)
        if report_show_dia is None:
            report_show_dia = getattr(pump, 'graph_show_family', True)
    show_dia = bool(report_show_dia) if report_show_dia is not None else True

    report_show_rpm = getattr(report, 'show_rpm_overlay', None)
    if report_show_rpm is None:
        report_show_rpm = getattr(report, 'show_speed_lines', None)
    if report_show_rpm is None:
        report_show_rpm = getattr(pump, 'graph_show_rpm_overlay', None)
        if report_show_rpm is None:
            report_show_rpm = getattr(pump, 'graph_show_speed_lines', True)
    show_rpm = bool(report_show_rpm) if report_show_rpm is not None else True

    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    is_var_speed = (fam_type == 'variable_speed')

    show_primary = show_rpm if is_var_speed else show_dia
    show_secondary = show_dia if is_var_speed else show_rpm

    # ── 1. Variable Speed Pump Curve Family & Overlays ──
    if is_var_speed:
        rpm_str = (getattr(pump, 'graph_rpm_values', None) or getattr(pump, 'graph_speed_line_values', None) or '').strip()
        rpm_list = _parse_diameters_string(rpm_str)
        if not rpm_list:
            base_rpm = pump.speed_rpm or 1000.0
            rpm_list = [base_rpm, base_rpm * 0.9, base_rpm * 0.8, base_rpm * 0.7]
        rpm_list.sort(reverse=True)
        base_rpm = rpm_list[0] if rpm_list else (pump.speed_rpm or 1000.0)

        if mode == 'max_only':
            rpm_to_plot = [rpm_list[0]]
        elif mode == 'min_max':
            rpm_to_plot = [rpm_list[0], rpm_list[-1]] if len(rpm_list) >= 2 else rpm_list
        else:
            rpm_to_plot = rpm_list

        # Primary RPM curves (rendered when show_primary is True, or as base curve when neither is selected)
        if show_primary or (not show_primary and not show_secondary):
            curves_to_draw = rpm_to_plot if show_primary else [rpm_to_plot[0]]
            for c_idx, rpm_val in enumerate(curves_to_draw):
                is_primary = (c_idx == 0)
                k = rpm_val / base_rpm if base_rpm > 0 else 1.0
                rpm_fmt = f"{round(rpm_val)}" if abs(rpm_val - round(rpm_val)) < 1e-4 else f"{round(rpm_val, 1)}"
                lbl = f"{rpm_fmt} RPM" + (" (Max)" if is_primary else "")
                pct = round(k * 100)

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

        # Secondary Diameter Overlay curves
        dia_str = (getattr(pump, 'graph_dia_overlay_values', None) or '').strip()
        if show_secondary and dia_str:
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
        else:  # mode == 'all'
            if len(custom_d_list) >= 3:
                d_curves = custom_d_list
            elif len(custom_d_list) == 2:
                steps = np.linspace(custom_d_list[0], custom_d_list[-1], 4)
                d_curves = [float(round(x)) for x in steps]
            else:
                d_curves = [max_d, float(round(max_d * 0.93)), float(round(max_d * 0.86)), float(round(max_d * 0.8))]

        # Primary Diameter trim curves (rendered when show_primary is True, or as base curve when neither is selected)
        if show_primary or (not show_primary and not show_secondary):
            curves_to_draw = d_curves if show_primary else [d_curves[0]]
            for c_idx, d_val in enumerate(curves_to_draw):
                is_primary = (c_idx == 0)
                d_fmt = f"{round(d_val)}" if abs(d_val - round(d_val)) < 1e-4 else f"{round(d_val, 1)}"
                lbl = f"{d_fmt} mm" + (" (Max)" if is_primary else "")
                d_ratio = (d_val / max_d) if max_d > 0 else 1.0
                pct = round(d_ratio * 100)

                c_q = [round(v * d_ratio, 2) for v in q_pts]
                c_h = [round(v * (d_ratio**2), 2) for v in h_pts]
                c_eta = [round(max(0.0, v * (1.0 - 0.05 * (1.0 - d_ratio))), 2) for v in eta_pts]
                c_pow = [round(v * (d_ratio**3), 2) for v in pow_pts]
                c_npsh = [round(v * (d_ratio**2), 2) for v in npsh_pts]

                cur_color = primary_color if is_primary else palette[min(c_idx, len(palette)-1)]

                hq_curves_list.append({'label': lbl, 'x': c_q, 'y': c_h, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})
                eta_curves_list.append({'label': lbl, 'x': c_q, 'y': c_eta, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})
                pow_curves_list.append({'label': lbl, 'x': c_q, 'y': c_pow, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})
                npsh_curves_list.append({'label': lbl, 'x': c_q, 'y': c_npsh, 'color': cur_color, 'is_secondary': not is_primary, 'pct': pct, 'val': d_val, 'dia': d_val})

        # Secondary RPM Overlay curves
        rpm_str = (getattr(pump, 'graph_rpm_values', None) or getattr(pump, 'graph_speed_line_values', None) or '').strip()
        if show_secondary and rpm_str:
            try:
                from pump_curves import speed_lines as calc_speed_lines
                spd_objs = calc_speed_lines(pump, values_str=rpm_str)
                is_main_sec = (not show_primary)
                for sl_idx, sl in enumerate(spd_objs):
                    lbl = sl.get('label', '')
                    is_top = (sl_idx == 0)
                    cur_color = (primary_color if is_top else palette[min(sl_idx, len(palette)-1)]) if is_main_sec else '#9333ea'
                    s_ratio = sl.get('speed_ratio') or sl.get('ratio') or 1.0
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

    # Compute proper isoline range (r_min) and trim penalty based on active curve selection
    iso_r_min, iso_trim = _compute_iso_override(pump, show_rpm_overlay=show_rpm, show_dia_overlay=show_dia)

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
                n_lbl = f"{int(round(n_val)) if abs(n_val - round(n_val)) < 1e-4 else round(n_val,1)} m"
                hq_isolines_list.append({
                    'x': n_iso.get('q', []),
                    'y': n_iso.get('h', []),
                    'label': n_lbl,
                    'branch': n_iso.get('branch'),
                    'type_idx': n_i,
                    'iso_type': 'npsh',
                    'color': '#2563eb',
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

    # Compute scaling factors for labels (from pump graph base units to report display units)
    fQ_raw = CURVE_CONVERSIONS['q'].get(rep_unit_q.lower().replace('/', ''), 1.0) / CURVE_CONVERSIONS['q'].get(base_unit_q.lower().replace('/', ''), 1.0)
    fH_raw = CURVE_CONVERSIONS['h'].get(rep_unit_h.lower(), 1.0) / CURVE_CONVERSIONS['h'].get(base_unit_h.lower(), 1.0)
    fPow_raw = CURVE_CONVERSIONS['pow'].get(rep_unit_pow.lower(), 1.0) / CURVE_CONVERSIONS['pow'].get(base_unit_pow.lower(), 1.0)
    fNpsh_raw = CURVE_CONVERSIONS['npsh'].get(rep_unit_npsh.lower(), 1.0) / CURVE_CONVERSIONS['npsh'].get(base_unit_npsh.lower(), 1.0)

    raw_custom_pos = pump.get_custom_label_pos() if hasattr(pump, 'get_custom_label_pos') else {}
    rep_label_fmt = getattr(report, 'label_format', 'auto') or 'auto'
    if rep_label_fmt == 'auto' or rep_label_fmt == 'pump_default':
        label_fmt = p_opts.get('label_format', 'percent')
    else:
        label_fmt = rep_label_fmt

    # Scale custom label positions cleanly per chart type
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
                    custom_pos_hq[k] = {'x': vx * fQ_raw, 'y': vy * fH_raw}
                    custom_pos_eff[k] = {'x': vx * fQ_raw, 'y': vy * 1.0}
                    custom_pos_pow[k] = {'x': vx * fQ_raw, 'y': vy * fPow_raw}
                    custom_pos_npsh[k] = {'x': vx * fQ_raw, 'y': vy * fNpsh_raw}
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

    svg_hq = generate_chart_svg(
        hq_curves_list, f"Flow ({lbl_q})", f"Head ({lbl_h})",
        custom_range=h_custom_range, height=240, isolines_list=hq_isolines_list,
        show_legend=show_leg_hq, legend_position=leg_pos, legend_mode=effective_legend_mode,
        custom_label_pos=custom_pos_hq, label_format=label_fmt, chart_type='hq'
    )

    svg_eta = generate_chart_svg(
        eta_curves_list, f"Flow ({lbl_q})", "Efficiency (%)",
        custom_range=eta_custom_range, height=240, show_legend=show_leg_sub, legend_position=leg_pos, legend_mode=effective_legend_mode,
        custom_label_pos=custom_pos_eff, label_format=label_fmt, chart_type='eff'
    )

    svg_pow = generate_chart_svg(
        pow_curves_list, f"Flow ({lbl_q})", f"Power ({lbl_pow})",
        custom_range=pow_custom_range, height=240, show_legend=show_leg_sub, legend_position=leg_pos, legend_mode=effective_legend_mode,
        custom_label_pos=custom_pos_pow, label_format=label_fmt, chart_type='pow'
    )

    svg_npsh = generate_chart_svg(
        npsh_curves_list, f"Flow ({lbl_q})", f"NPSHr ({lbl_npsh})",
        custom_range=npsh_custom_range, height=240, show_legend=show_leg_sub, legend_position=leg_pos, legend_mode=effective_legend_mode,
        custom_label_pos=custom_pos_npsh, label_format=label_fmt, chart_type='npsh'
    ) if (has_npsh and getattr(report, 'show_npsh_curves', True)) else ""


    bep_info = None
    try:
        bep_info = bep_point(pump)
    except Exception:
        pass

    return {
        'q_max': q_max,
        'has_npsh': has_npsh,
        'svg_hq': svg_hq,
        'svg_eta': svg_eta,
        'svg_pow': svg_pow,
        'svg_npsh': svg_npsh,
        'bep_info': bep_info
    }


@reports_bp.route('/settings')
def settings():
    reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    available_templates = ['standard_datasheet.html', 'compact_datasheet.html', 'slurry_specsheet.html']
    
    return render_template(
        'reports_settings.html',
        reports=reports,
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
    flash(f'Supplier "{supplier.name}" saved successfully.', 'success')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/settings/report/save', methods=['POST'])
def save_report():
    report_id = request.form.get('report_id')
    title = request.form.get('title', '').strip()
    
    if not title:
        flash('Report Title is required.', 'error')
        return redirect(url_for('reports.settings'))

    if report_id and report_id.isdigit():
        report = ReportConfig.query.get_or_404(int(report_id))
    else:
        report = ReportConfig()
        db.session.add(report)

    supplier_id = request.form.get('supplier_id')
    report.supplier_id = int(supplier_id) if supplier_id and supplier_id.isdigit() else None
    report.report_name = request.form.get('report_name', 'standard').strip() or 'standard'
    report.title = title
    report.report_type = request.form.get('report_type', 'Technical Datasheet').strip() or 'Technical Datasheet'
    report.description = request.form.get('description', '').strip()
    report.template_name = request.form.get('template_name', 'standard_datasheet.html').strip()
    
    report.show_head_flow_graph = 'show_head_flow_graph' in request.form
    report.show_efficiency_graph = 'show_efficiency_graph' in request.form
    report.show_power_graph = 'show_power_graph' in request.form
    report.show_npsh_graph = 'show_npsh_graph' in request.form

    report.show_eff_isolines = 'show_eff_isolines' in request.form
    report.show_power_isolines = 'show_power_isolines' in request.form
    report.show_npsh_curves = 'show_npsh_curves' in request.form
    report.show_speed_lines = 'show_speed_lines' in request.form or 'show_rpm_overlay' in request.form
    report.show_rpm_overlay = 'show_rpm_overlay' in request.form or 'show_speed_lines' in request.form
    report.show_dia_overlay = 'show_dia_overlay' in request.form
    report.show_additional_graphs = 'show_additional_graphs' in request.form
    report.show_legend = 'show_legend' in request.form
    report.legend_position = request.form.get('legend_position', 'top_right').strip()
    report.legend_mode = request.form.get('legend_mode', 'pump_default').strip()
    report.label_format = request.form.get('label_format', 'auto').strip()

    report.unit_flow = request.form.get('unit_flow', '').strip() or None
    report.unit_head = request.form.get('unit_head', '').strip() or None
    report.unit_power = request.form.get('unit_power', '').strip() or None
    report.unit_npsh = request.form.get('unit_npsh', '').strip() or None

    report.header_text = request.form.get('header_text', 'PUMP MASTER PRO - TECHNICAL DATASHEET').strip()
    report.footer_text = request.form.get('footer_text', 'Generated by Pump Master Pro Engineering Suite').strip()
    report.primary_color = request.form.get('primary_color', '#1e3a8a').strip()
    report.curve_display_mode = request.form.get('curve_display_mode', 'all').strip()
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
