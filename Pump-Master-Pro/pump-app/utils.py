"""
utils.py — Shared utility functions for form processing, numeric parsing, and polynomial auto-fitting.

Beginners Note: This module isolates reusable data processing helpers used across Flask route handlers.
"""

import json
from models import db, Pump
from pump_curves import (
    fit_pump_polynomials, Q_TO_M3H, H_TO_M, POW_TO_KW
)


def _get_float(d, key, default=0.0):
    """
    Extract a float number from a dictionary or form submission.
    Returns default value if missing or invalid.
    """
    val = d.get(key)
    if val is None or str(val).strip() == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_nullable_float(d, key):
    """
    Extract a float number from form or JSON data.
    Returns None if empty or invalid, allowing Plotly auto-scaling.
    """
    val = d.get(key)
    if val is None or str(val).strip() == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_nullable_int(d, key):
    """
    Extract an integer number from form or JSON data.
    Returns None if empty or invalid.
    """
    val = d.get(key)
    if val is None or str(val).strip() == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _auto_fit_coeffs(raw_tables_str, coeffs_str, units_str=''):
    """
    Beginners Note: Automatically fits polynomial coefficients for extra curves
    from raw user-entered data table rows if coefficients were not manually entered.
    """
    if not raw_tables_str or not raw_tables_str.strip():
        return coeffs_str
    tables = raw_tables_str.split('|')
    coeffs_list = coeffs_str.split('|') if coeffs_str else []
    units_list = units_str.split('|') if units_str else []
    updated = []
    for idx, t_str in enumerate(tables):
        cur_coeff = coeffs_list[idx] if idx < len(coeffs_list) else ''
        c_vals = [float(x.strip()) for x in cur_coeff.split(',') if x.strip()] if cur_coeff else []
        has_hq = len(c_vals) >= 4 and any(c_vals[0:4])
        if has_hq:
            updated.append(cur_coeff)
            continue

        cur_unit_str = units_list[idx] if idx < len(units_list) else ''
        u_parts = [u.strip() for u in cur_unit_str.split(',') if u.strip()]
        u_q = u_parts[0] if len(u_parts) >= 1 else 'm3h'
        u_h = u_parts[1] if len(u_parts) >= 2 else 'm'
        u_p = u_parts[3] if len(u_parts) >= 4 else 'kw'

        f_q = Q_TO_M3H.get(u_q, 1.0)
        f_h = H_TO_M.get(u_h, 1.0)
        f_p = POW_TO_KW.get(u_p, 1.0)

        q_h, q_eta, q_p = [], [], []
        for r_str in t_str.split(';'):
            parts = [p.strip() for p in r_str.split(',') if p.strip()]
            if len(parts) >= 2:
                try:
                    q_v, h_v = float(parts[0]) * f_q, float(parts[1]) * f_h
                    q_h.append([q_v, h_v])
                    if len(parts) >= 3 and parts[2]: q_eta.append([q_v, float(parts[2])])
                    if len(parts) >= 5 and parts[4]: q_p.append([q_v, float(parts[4]) * f_p])
                except ValueError:
                    pass
        if len(q_h) >= 3:
            try:
                res = fit_pump_polynomials(q_h=q_h, q_eta=q_eta or None, q_p=q_p or None)
                fitted_c = f"{res['hq_a0']},{res['hq_a1']},{res['hq_a2']},{res['hq_a3']},{res['hq_a4']},{res['hq_a5']}," \
                           f"{res['eff_b0']},{res['eff_b1']},{res['eff_b2']},{res['eff_b3']},{res['eff_b4']},{res['eff_b5']}," \
                           f"{res['npsh_c0']},{res['npsh_c1']},{res['npsh_c2']},{res['npsh_c3']},{res['npsh_c4']},{res['npsh_c5']}," \
                           f"{res['pow_p0']},{res['pow_p1']},{res['pow_p2']},{res['pow_p3']},{res['pow_p4']},{res['pow_p5']}," \
                           f"{res['q_max']},{res['q_bep']}"
                updated.append(fitted_c)
            except Exception:
                updated.append(cur_coeff or '0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        else:
            updated.append(cur_coeff or '0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
    return '|'.join(updated)


def _pump_from_form(f, pump=None):
    """
    Beginners Note: Builds or updates a Pump model instance from an incoming POST form.
    Assigns polynomial coefficients, display units, curve styles, and 20 axis scale settings.
    """
    if pump is None:
        pump = Pump(hq_a0=0.0, q_max=100.0)

    pump.name             = f['name']
    pump.manufacturer     = f.get('manufacturer', pump.manufacturer or '')
    pump.model_number     = f.get('model_number', pump.model_number or '')
    pump.size             = f.get('size', pump.size or '')
    pump.speed_rpm = _get_float(f, 'speed_rpm', pump.speed_rpm if pump.speed_rpm is not None else 1450.0)
    
    val_max_imp = _get_float(f, 'impeller_dia_val', pump.impeller_dia_mm if pump.impeller_dia_mm is not None else 300.0)
    unit_max_imp = f.get('unit_max_imp', 'mm')
    if unit_max_imp == 'in':
        pump.impeller_dia_mm = val_max_imp * 25.4
    else:
        pump.impeller_dia_mm = val_max_imp

    pump.impeller_diameters = f.get('impeller_diameters', pump.impeller_diameters or '')
    pump.hq_a0 = _get_float(f, 'hq_a0', getattr(pump, 'hq_a0', 0.0))
    pump.hq_a1 = _get_float(f, 'hq_a1', getattr(pump, 'hq_a1', 0.0))
    pump.hq_a2 = _get_float(f, 'hq_a2', getattr(pump, 'hq_a2', 0.0))
    pump.hq_a3 = _get_float(f, 'hq_a3', getattr(pump, 'hq_a3', 0.0))
    pump.hq_a4 = _get_float(f, 'hq_a4', getattr(pump, 'hq_a4', 0.0))
    pump.hq_a5 = _get_float(f, 'hq_a5', getattr(pump, 'hq_a5', 0.0))

    pump.eff_b0 = _get_float(f, 'eff_b0', getattr(pump, 'eff_b0', 0.0))
    pump.eff_b1 = _get_float(f, 'eff_b1', getattr(pump, 'eff_b1', 0.0))
    pump.eff_b2 = _get_float(f, 'eff_b2', getattr(pump, 'eff_b2', 0.0))
    pump.eff_b3 = _get_float(f, 'eff_b3', getattr(pump, 'eff_b3', 0.0))
    pump.eff_b4 = _get_float(f, 'eff_b4', getattr(pump, 'eff_b4', 0.0))
    pump.eff_b5 = _get_float(f, 'eff_b5', getattr(pump, 'eff_b5', 0.0))

    pump.npsh_c0 = _get_float(f, 'npsh_c0', getattr(pump, 'npsh_c0', 1.0))
    pump.npsh_c1 = _get_float(f, 'npsh_c1', getattr(pump, 'npsh_c1', 0.0))
    pump.npsh_c2 = _get_float(f, 'npsh_c2', getattr(pump, 'npsh_c2', 0.0))
    pump.npsh_c3 = _get_float(f, 'npsh_c3', getattr(pump, 'npsh_c3', 0.0))
    pump.npsh_c4 = _get_float(f, 'npsh_c4', getattr(pump, 'npsh_c4', 0.0))
    pump.npsh_c5 = _get_float(f, 'npsh_c5', getattr(pump, 'npsh_c5', 0.0))

    pump.pow_p0 = _get_float(f, 'pow_p0', getattr(pump, 'pow_p0', 0.0))
    pump.pow_p1 = _get_float(f, 'pow_p1', getattr(pump, 'pow_p1', 0.0))
    pump.pow_p2 = _get_float(f, 'pow_p2', getattr(pump, 'pow_p2', 0.0))
    pump.pow_p3 = _get_float(f, 'pow_p3', getattr(pump, 'pow_p3', 0.0))
    pump.pow_p4 = _get_float(f, 'pow_p4', getattr(pump, 'pow_p4', 0.0))
    pump.pow_p5 = _get_float(f, 'pow_p5', getattr(pump, 'pow_p5', 0.0))
    pump.q_min  = _get_float(f, 'q_min', pump.q_min if pump.q_min is not None else 0.0)
    pump.q_max  = _get_float(f, 'q_max', pump.q_max if pump.q_max is not None else 100.0)
    pump.q_bep  = _get_float(f, 'q_bep', pump.q_bep if pump.q_bep is not None else 0.0)
    pump.hr     = _get_float(f, 'hr', pump.hr if pump.hr is not None else 1.0)
    pump.qr     = _get_float(f, 'qr', pump.qr if pump.qr is not None else 1.0)
    pump.er     = _get_float(f, 'er', pump.er if pump.er is not None else 1.0)
    pump.pump_type        = f.get('pump_type', pump.pump_type or 'centrifugal')
    pump.application      = f.get('application', pump.application or '')
    pump.notes            = f.get('notes', pump.notes or '')
    if 'graph_options_json' in f:
        try:
            raw_g_opts = f.getlist('graph_options_json') if hasattr(f, 'getlist') else [f.get('graph_options_json')]
            g_opts_str = [x for x in raw_g_opts if x][-1] if any(raw_g_opts) else ''
            if g_opts_str:
                g_opts = json.loads(g_opts_str)
                if isinstance(g_opts, dict):
                    pump.set_graph_options(g_opts)
        except Exception:
            pass
    pump.curve_labels    = f.get('curve_labels', pump.curve_labels or '')
    pump.curve_diameters = f.get('curve_diameters', pump.curve_diameters or '')
    pump.curve_colors    = f.get('curve_colors', pump.curve_colors or '')
    pump.curve_modes     = f.get('curve_modes', pump.curve_modes or '')
    pump.curve_units     = f.get('curve_units', pump.curve_units or '')
    pump.curve_raw_tables = f.get('curve_raw_tables', pump.curve_raw_tables or '')
    pump.extra_curves_json = f.get('extra_curves_json', pump.extra_curves_json or '')
    
    raw_coeffs = f.get('curve_coeffs', pump.curve_coeffs or '')
    pump.curve_coeffs    = _auto_fit_coeffs(pump.curve_raw_tables, raw_coeffs, pump.curve_units)

    pump.unit_q    = f.get('unit_q', pump.unit_q or 'm3h')
    pump.unit_h    = f.get('unit_h', pump.unit_h or 'm')
    pump.unit_npsh = f.get('unit_npsh', pump.unit_npsh or 'm')
    pump.unit_pow  = f.get('unit_pow', pump.unit_pow or 'kw')
    pump.unit_op_q = f.get('unit_op_q', pump.unit_op_q or 'm3h')

    pump.head_curve_style  = f.get('head_curve_style', pump.head_curve_style or '#58a6ff;2.0,solid')
    pump.eff_curve_style   = f.get('eff_curve_style', pump.eff_curve_style or '#3fb950;1.5,dot')
    pump.power_curve_style = f.get('power_curve_style', pump.power_curve_style or '#f85149;1.5,longdash')
    pump.npsh_curve_style  = f.get('npsh_curve_style', pump.npsh_curve_style or '#39d3c0;1.5,dashdot')
    pump.main_curve_style  = f.get('main_curve_style', pump.main_curve_style or 'graph')

    # Beginners Note: Extract 20 custom axis scaling settings from form data and save to database columns
    for axis_name in ['flow', 'head', 'eff', 'power', 'npsh']:
        for prop in ['min', 'max', 'major']:
            col_key = f'axis_{axis_name}_{prop}'
            setattr(pump, col_key, _get_nullable_float(f, col_key))
        col_minor = f'axis_{axis_name}_minor'
        setattr(pump, col_minor, _get_nullable_int(f, col_minor))

    # Beginners Note: Extract per-curve polynomial fitting orders (1 to 5) from form data
    for order_key in ['poly_order', 'poly_order_hq', 'poly_order_eff', 'poly_order_npsh', 'poly_order_pow']:
        po_val = _get_nullable_int(f, order_key)
        if po_val is not None and 1 <= po_val <= 5:
            setattr(pump, order_key, po_val)

    # Convert op-range values from display unit to SI (m³/h) before persisting
    units_dict = pump._get_data_units()
    op_q_unit = units_dict.get('op_q', 'm3h')
    factor = Q_TO_M3H.get(op_q_unit, 1.0)
    q_min_raw = _get_float(f, 'q_min', None)
    q_max_raw = _get_float(f, 'q_max', None)
    q_bep_raw = _get_float(f, 'q_bep', None)
    if q_min_raw is not None:
        pump.q_min = q_min_raw * factor
    if q_max_raw is not None:
        pump.q_max = q_max_raw * factor
    if q_bep_raw is not None:
        pump.q_bep = q_bep_raw * factor

    return pump
