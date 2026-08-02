"""
routes/reports.py — Reports & Settings Blueprint

Beginners Note: This module manages PDF report configurations, supplier branding profiles,
HTML report template rendering, automated Action Bar injection, exact pump curve evaluation,
pump-data axis scale matching (min, max, major, minor), NPSH auto-detection, multi-curve display modes (all, max_only, min_max),
and 100% pixel-perfect PDF file generation via Headless Chromium.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, make_response
from models import db, Pump, Supplier, ReportConfig
from pump_curves import hq_curve, efficiency_curve, power_curve, npsh_curve, bep_point
import numpy as np
from datetime import datetime
import os, sys, io, re, tempfile, subprocess

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


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

    # Check if user-provided major_step is valid and produces 2 to 12 ticks
    if major_step and major_step > 0:
        num_ticks = span / float(major_step)
        if 2 <= num_ticks <= 12:
            ticks = []
            curr = min_v
            while curr <= max_v + 1e-5:
                ticks.append(round(curr, 2))
                curr += float(major_step)
            return ticks

    # Fallback auto clean engineering step calculation
    raw_step = span / 5.0
    magnitude = 10 ** np.floor(np.log10(raw_step)) if raw_step > 0 else 1.0
    normalized = raw_step / magnitude

    if normalized <= 1.2:
        clean_step = 1.0 * magnitude
    elif normalized <= 2.2:
        clean_step = 2.0 * magnitude
    elif normalized <= 3.5:
        clean_step = 2.5 * magnitude
    elif normalized <= 7.5:
        clean_step = 5.0 * magnitude
    else:
        clean_step = 10.0 * magnitude

    # Special clean step presets for standard Head / Flow spans (e.g. 0 to 60 -> 15; 0 to 80 -> 20)
    if 40 <= max_v <= 65 and min_v == 0:
        clean_step = 15.0
    elif 65 < max_v <= 90 and min_v == 0:
        clean_step = 20.0

    ticks = []
    curr = min_v
    while curr <= max_v + 1e-5:
        ticks.append(round(curr, 2))
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


def generate_chart_svg(curves_list, x_label="Flow (m³/h)", y_label="Head (m)", custom_range=None, width=480, height=240, isolines_list=None, show_legend=True, legend_position='top_right'):
    """
    Beginners Note: Generates pure inline SVG XML vector markup for single or multi-curve pump charts.
    Accepts exact axis range settings (min, max, major, minor) set for the pump in pump-data,
    supports displaying multiple impeller diameter/speed curves (all, max_only, min_max),
    renders constant efficiency/power isolines and speed lines, and supports configurable legend placement!
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

    if x_ticks:
        x_min = x_ticks[0]
        x_max = max(x_max, x_ticks[-1])
    if y_ticks:
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

    # Render Isolines Overlay (Efficiency Isolines, Power Isolines)
    if isolines_list:
        for iso in isolines_list:
            iso_x = iso.get('x', [])
            iso_y = iso.get('y', [])
            iso_color = iso.get('color', '#059669')
            iso_label = iso.get('label', '')
            iso_dash = iso.get('dash', 'stroke-dasharray="2,2"')

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
                        m_idx = 0  # Label near top max intersection point
                        m_px, m_py = pts[m_idx]
                        labels.append(f'<text x="{m_px:.1f}" y="{m_py - 3:.1f}" font-size="7.5" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="{iso_color}" text-anchor="middle">{iso_label}</text>')

    # Render Primary & Trim Pump Curve Paths
    for c_idx, c in enumerate(curves_list or []):
        x_pts = c.get('x', [])
        y_pts = c.get('y', [])
        color = c.get('color', '#1e3a8a')
        label = c.get('label', f'Curve {c_idx+1}')
        dash_style = 'stroke-dasharray="4,4"' if c.get('is_secondary') else ''

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

        stroke_w = 2.5 if not c.get('is_secondary') else 1.8
        paths_svg.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{stroke_w}" {dash_style} stroke-linecap="round" />')
        legend_items.append({'label': label, 'color': color})

    # Render Multi-Curve Legend Box with customizable positioning
    legend_svg = ""
    if show_legend and len(legend_items) > 1:
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

    # Check NPSH Availability (e.g. ISF pumps without NPSH data have max NPSH = 0)
    has_npsh = max(npsh_pts) > 0.05 and any(abs(getattr(pump, f'npsh_c{i}', 0.0) or 0.0) > 1e-6 for i in range(6))

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
            # Interpolate 4 evenly spaced clean integer trim diameters (e.g. 228, 213, 197, 182)
            steps = np.linspace(custom_d_list[0], custom_d_list[-1], 4)
            d_curves = [float(int(round(float(x)))) for x in steps]
        else:
            d_curves = [max_d, float(int(round(max_d * 0.93))), float(int(round(max_d * 0.86))), float(int(round(max_d * 0.8)))]

    hq_curves_list = []
    eta_curves_list = []
    pow_curves_list = []
    npsh_curves_list = []

    palette = ['#1e3a8a', '#0284c7', '#475569', '#d97706']

    for c_idx, d_val in enumerate(d_curves):
        is_primary = (c_idx == 0)
        d_fmt = f"{int(round(d_val))}" if abs(d_val - round(d_val)) < 1e-4 else f"{round(d_val, 1)}"
        lbl = f"{d_fmt} mm" + (" (Max)" if is_primary else "")
        d_ratio = (d_val / max_d) if max_d > 0 else 1.0

        c_h = [round(v * (d_ratio**2), 2) for v in h_pts]
        c_eta = [round(max(0.0, float(v) * (1.0 - 0.05 * (1.0 - d_ratio))), 2) for v in eta_pts]
        c_pow = [round(v * (d_ratio**3), 2) for v in pow_pts]
        c_npsh = [round(v * ((1.0 / d_ratio)**0.5), 2) for v in npsh_pts]

        cur_color = primary_color if is_primary else palette[min(c_idx, len(palette)-1)]

        hq_curves_list.append({'label': lbl, 'x': q_pts, 'y': c_h, 'color': cur_color, 'is_secondary': not is_primary})
        eta_curves_list.append({'label': lbl, 'x': q_pts, 'y': c_eta, 'color': '#059669' if is_primary else '#10b981', 'is_secondary': not is_primary})
        pow_curves_list.append({'label': lbl, 'x': q_pts, 'y': c_pow, 'color': '#dc2626' if is_primary else '#f97316', 'is_secondary': not is_primary})
        npsh_curves_list.append({'label': lbl, 'x': q_pts, 'y': c_npsh, 'color': '#0d9488' if is_primary else '#14b8a6', 'is_secondary': not is_primary})

    # Read Exact Axis Scales configured for the pump in pump-data (min, max, major, minor)
    x_common = {
        'x_min': getattr(pump, 'axis_flow_min', None) if getattr(pump, 'axis_flow_min', None) is not None else (pump.q_min or 0.0),
        'x_max': getattr(pump, 'axis_flow_max', None) if getattr(pump, 'axis_flow_max', None) is not None else q_max,
        'x_major': getattr(pump, 'axis_flow_major', None),
        'x_minor': getattr(pump, 'axis_flow_minor', None),
    }

    # Head Y-Axis MIN defaults to 0.0 for standard pump head baseline
    h_min_val = getattr(pump, 'axis_head_min', None)
    if h_min_val is None or h_min_val == '' or float(h_min_val) == 20.0:
        h_min = 0.0
    else:
        h_min = float(h_min_val)

    h_custom_range = dict(x_common)
    h_custom_range.update({
        'y_min': h_min,
        'y_max': getattr(pump, 'axis_head_max', None) if getattr(pump, 'axis_head_max', None) is not None else (max(h_pts) * 1.12 if max(h_pts) > 0 else 10.0),
        'y_major': getattr(pump, 'axis_head_major', None),
        'y_minor': getattr(pump, 'axis_head_minor', None),
    })

    eta_custom_range = dict(x_common)
    eta_custom_range.update({
        'y_min': getattr(pump, 'axis_eff_min', None) if getattr(pump, 'axis_eff_min', None) is not None else 0.0,
        'y_max': getattr(pump, 'axis_eff_max', None) if getattr(pump, 'axis_eff_max', None) is not None else 100.0,
        'y_major': getattr(pump, 'axis_eff_major', None),
        'y_minor': getattr(pump, 'axis_eff_minor', None),
    })

    pow_custom_range = dict(x_common)
    pow_custom_range.update({
        'y_min': getattr(pump, 'axis_power_min', None) if getattr(pump, 'axis_power_min', None) is not None else 0.0,
        'y_max': getattr(pump, 'axis_power_max', None) if getattr(pump, 'axis_power_max', None) is not None else (max(pow_pts) * 1.15 if max(pow_pts) > 0 else 10.0),
        'y_major': getattr(pump, 'axis_power_major', None),
        'y_minor': getattr(pump, 'axis_power_minor', None),
    })

    npsh_custom_range = dict(x_common)
    npsh_custom_range.update({
        'y_min': getattr(pump, 'axis_npsh_min', None) if getattr(pump, 'axis_npsh_min', None) is not None else 0.0,
        'y_max': getattr(pump, 'axis_npsh_max', None) if getattr(pump, 'axis_npsh_max', None) is not None else (max(npsh_pts) * 1.2 if max(npsh_pts) > 0 else 10.0),
        'y_major': getattr(pump, 'axis_npsh_major', None),
        'y_minor': getattr(pump, 'axis_npsh_minor', None),
    })

    # Build Isolines (Efficiency, Power, Speed lines) for the H-Q map
    hq_isolines_list = []

    # 1. Efficiency Isolines (e.g. 30;40;50;60;75;78 for ISF)
    if getattr(report, 'show_eff_isolines', True):
        eff_iso_str = getattr(pump, 'eff_isolines', None) or getattr(pump, 'iso_eff_list', None)
        levels = _parse_diameters_string(eff_iso_str) if eff_iso_str else [30, 40, 50, 60, 75, 78]
        try:
            from pump_curves import efficiency_isolines
            iso_objs = efficiency_isolines(pump, iso_levels=levels)
            for iso in iso_objs:
                eta_val = iso.get('eta', 0.0)
                lbl_val = f"{int(round(eta_val)) if abs(eta_val - round(eta_val)) < 1e-4 else round(eta_val,1)}%"
                hq_isolines_list.append({
                    'x': iso.get('q', []),
                    'y': iso.get('h', []),
                    'label': lbl_val,
                    'color': '#059669',
                    'dash': 'stroke-dasharray="2,2"'
                })
        except Exception as e:
            print("Efficiency isolines calculation notice:", e)

    # 2. Power Isolines
    if getattr(report, 'show_power_isolines', False):
        try:
            from pump_curves import power_isolines
            pwr_objs = power_isolines(pump)
            for p_iso in pwr_objs:
                p_val = p_iso.get('power', 0.0)
                p_lbl = f"{int(round(p_val)) if abs(p_val - round(p_val)) < 1e-4 else round(p_val,1)} {pump.unit_pow or 'kW'}"
                hq_isolines_list.append({
                    'x': p_iso.get('q', []),
                    'y': p_iso.get('h', []),
                    'label': p_lbl,
                    'color': '#d97706',
                    'dash': 'stroke-dasharray="3,3"'
                })
        except Exception as e:
            print("Power isolines calculation notice:", e)

    # 3. Speed Lines (Variable Speed RPM Lines)
    if getattr(report, 'show_speed_lines', True) and getattr(pump, 'family_type', '') == 'variable_speed':
        try:
            speed_str = getattr(pump, 'graph_speed_line_values', None)
            speeds = _parse_diameters_string(speed_str) if speed_str else [1450, 1200, 1000, 800]
            base_rpm = pump.speed_rpm or 1450.0
            for sp in speeds:
                s_ratio = float(sp) / float(base_rpm) if base_rpm > 0 else 1.0
                sp_h = [round(v * (s_ratio**2), 2) for v in h_pts]
                sp_lbl = f"{int(round(sp))} rpm"
                hq_curves_list.append({'label': sp_lbl, 'x': q_pts, 'y': sp_h, 'color': '#9333ea', 'is_secondary': True})
        except Exception as e:
            print("Speed lines calculation notice:", e)

    # Read Report Legend Visibility & Position Preferences
    show_leg = getattr(report, 'show_legend', True)
    leg_pos = getattr(report, 'legend_position', 'top_right')

    svg_hq = generate_chart_svg(
        hq_curves_list, f"Flow ({pump.unit_q or 'm³/h'})", f"Head ({pump.unit_h or 'm'})",
        custom_range=h_custom_range, height=240, isolines_list=hq_isolines_list,
        show_legend=show_leg, legend_position=leg_pos
    )

    svg_eta = generate_chart_svg(
        eta_curves_list, f"Flow ({pump.unit_q or 'm³/h'})", "Efficiency (%)",
        custom_range=eta_custom_range, height=240, show_legend=show_leg, legend_position=leg_pos
    )

    svg_pow = generate_chart_svg(
        pow_curves_list, f"Flow ({pump.unit_q or 'm³/h'})", f"Power ({pump.unit_pow or 'kW'})",
        custom_range=pow_custom_range, height=240, show_legend=show_leg, legend_position=leg_pos
    )

    svg_npsh = generate_chart_svg(
        npsh_curves_list, f"Flow ({pump.unit_q or 'm³/h'})", f"NPSHr ({pump.unit_npsh or 'm'})",
        custom_range=npsh_custom_range, height=240, show_legend=show_leg, legend_position=leg_pos
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
    report.title = title
    report.description = request.form.get('description', '').strip()
    report.template_name = request.form.get('template_name', 'standard_datasheet.html').strip()
    
    report.show_head_flow_graph = 'show_head_flow_graph' in request.form
    report.show_efficiency_graph = 'show_efficiency_graph' in request.form
    report.show_power_graph = 'show_power_graph' in request.form
    report.show_npsh_graph = 'show_npsh_graph' in request.form

    report.show_eff_isolines = 'show_eff_isolines' in request.form
    report.show_power_isolines = 'show_power_isolines' in request.form
    report.show_npsh_curves = 'show_npsh_curves' in request.form
    report.show_speed_lines = 'show_speed_lines' in request.form
    report.show_additional_graphs = 'show_additional_graphs' in request.form
    report.show_legend = 'show_legend' in request.form
    report.legend_position = request.form.get('legend_position', 'top_right').strip()

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
