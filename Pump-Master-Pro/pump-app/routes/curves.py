"""
routes/curves.py — Pump curve viewer, polynomial fitting, and chart preview APIs.

Beginners Note: Handles chart rendering, polynomial fitting, live preview endpoints, and label drag positions.
"""

import json
import numpy as np
from flask import Blueprint, render_template, request, jsonify
from models import db, Pump
from utils import _get_float, _get_nullable_float, _get_nullable_int
from pump_curves import (
    full_curve_data, bep_point, system_curve_points,
    warman_chart_data, fit_pump_polynomials
)

curves_bp = Blueprint('curves', __name__)


@curves_bp.route('/pump-curve/<int:pump_id>', endpoint='pump_curve')
def pump_curve(pump_id):
    """Render interactive Warman curve viewer page for a pump."""
    pump = Pump.query.get_or_404(pump_id)
    return render_template('pump_curve.html', pump=pump)


@curves_bp.route('/papi/fit-curves', methods=['POST'])
def api_fit_curves():
    """Fit polynomial curves from tabular performance data."""
    data = request.get_json(force=True)
    try:
        result = fit_pump_polynomials(
            q_h   = data.get('q_h', []),
            q_eta = data.get('q_eta', []),
            q_npsh= data.get('q_npsh', None),
            q_p   = data.get('q_p', None),
            rho   = float(data.get('rho', 1000)),
            poly_order = int(data.get('poly_order', 3)),
            poly_order_hq = int(data['poly_order_hq']) if data.get('poly_order_hq') else None,
            poly_order_eff = int(data['poly_order_eff']) if data.get('poly_order_eff') else None,
            poly_order_npsh = int(data['poly_order_npsh']) if data.get('poly_order_npsh') else None,
            poly_order_pow = int(data['poly_order_pow']) if data.get('poly_order_pow') else None,
        )
        return jsonify({'ok': True, **result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@curves_bp.route('/papi/curve-data/<int:pump_id>')
def api_curve_data(pump_id):
    """Return curve data JSON for a single saved pump ID."""
    pump   = Pump.query.get_or_404(pump_id)
    args   = request.args
    liquid = args.get('liquid', 'water')
    rho    = _get_float(args, 'rho', 1000.0)
    vis    = _get_float(args, 'viscosity_cSt', 1.0)
    cv     = _get_float(args, 'slurry_cv', 0.0)
    d50    = _get_float(args, 'slurry_d50', 0.3)
    rho_s  = _get_float(args, 'rho_solid', 2650.0)

    data = full_curve_data(pump, n_points=100, liquid=liquid, rho=rho,
                           viscosity_cSt=vis, slurry_cv=cv,
                           slurry_d50=d50, rho_solid=rho_s)
    bep = bep_point(pump, liquid, rho, vis, cv, d50, rho_s)

    sh   = _get_float(args, 'static_head', 0.0)
    pk   = _get_float(args, 'pipe_k', 0.0)
    data['system_h'] = system_curve_points(sh, pk, data['q']) if (pk or sh) else None

    data['bep']  = bep
    data['pump'] = pump.to_dict()
    data['raw_table_json'] = json.dumps(pump.get_raw_table())
    data['data_units'] = pump._get_data_units()
    return jsonify(data)


@curves_bp.route('/papi/warman-chart/<int:pump_id>')
def api_warman_chart(pump_id):
    """Return full Warman performance map data for a saved pump ID."""
    pump   = Pump.query.get_or_404(pump_id)
    args   = request.args
    liquid = args.get('liquid', 'water')
    rho    = _get_float(args, 'rho', 1000.0)
    vis    = _get_float(args, 'viscosity_cSt', 1.0)
    cv     = _get_float(args, 'slurry_cv', 0.0)
    d50    = _get_float(args, 'slurry_d50', 0.3)
    rho_s  = _get_float(args, 'rho_solid', 2650.0)

    def parse_levels(raw_str):
        if not raw_str or not raw_str.strip():
            return None
        try:
            return [float(x.strip()) for x in raw_str.replace(';', ',').split(',') if x.strip()]
        except ValueError:
            return None

    eff_levels   = parse_levels(args.get('eff_levels'))
    power_levels = parse_levels(args.get('power_levels'))
    npsh_levels  = parse_levels(args.get('npsh_levels'))
    raw_fa       = args.get('force_affinity', '')
    if raw_fa in ['true', '1', 'affinity']:
        force_affinity = 'affinity'
    elif raw_fa == 'both':
        force_affinity = 'both'
    elif raw_fa == 'fit':
        force_affinity = 'fit'
    else:
        force_affinity = False

    data = warman_chart_data(pump, liquid=liquid, rho=rho, viscosity_cSt=vis,
                             slurry_cv=cv, slurry_d50=d50, rho_solid=rho_s,
                             eff_levels=eff_levels, power_levels=power_levels,
                             npsh_levels=npsh_levels, force_affinity=force_affinity)

    sh = _get_float(args, 'static_head', 0.0)
    pk = _get_float(args, 'pipe_k', 0.0)
    q_max = pump.q_max
    if sh or pk:
        q_sys = np.linspace(0, q_max, 100).tolist()
        data['system_q'] = q_sys
        data['system_h'] = system_curve_points(sh, pk, q_sys)

    data['raw_table_json'] = json.dumps(pump.get_raw_table())
    data['data_units'] = pump._get_data_units()
    data['graph_options'] = pump.get_graph_options()
    return jsonify(data)


@curves_bp.route('/papi/preview-warman-chart', methods=['POST'])
def api_preview_warman_chart():
    """Return full Warman performance map data for unsaved preview pump data."""
    data = request.get_json(force=True)
    pump = Pump()
    for field in ['hq_a0', 'hq_a1', 'hq_a2', 'hq_a3', 'hq_a4', 'hq_a5',
                  'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3', 'eff_b4', 'eff_b5',
                  'npsh_c0', 'npsh_c1', 'npsh_c2', 'npsh_c3', 'npsh_c4', 'npsh_c5',
                  'pow_p0', 'pow_p1', 'pow_p2', 'pow_p3', 'pow_p4', 'pow_p5',
                  'speed_rpm', 'impeller_dia_mm', 'q_min', 'q_max', 'q_bep',
                  'hr', 'qr', 'er']:
        val = data.get(field)
        if val is not None:
            setattr(pump, field, float(val))
        else:
            setattr(pump, field, 0.0)

    for field in ['head_curve_style', 'eff_curve_style', 'power_curve_style', 'npsh_curve_style', 'main_curve_style']:
        if field in data and data[field]:
            setattr(pump, field, str(data[field]))

    if 'family_type' in data:
        pump.family_type = str(data['family_type'])

    # Set 20 custom axis scale settings on temporary Pump object
    for axis_name in ['flow', 'head', 'eff', 'power', 'npsh']:
        for prop in ['min', 'max', 'major']:
            col_key = f'axis_{axis_name}_{prop}'
            setattr(pump, col_key, _get_nullable_float(data, col_key))
        col_minor = f'axis_{axis_name}_minor'
        setattr(pump, col_minor, _get_nullable_int(data, col_minor))

    # Beginners Note: Set per-curve polynomial orders (1 to 5) on temporary Pump instance for preview calculation
    for p_key in ['poly_order', 'poly_order_hq', 'poly_order_eff', 'poly_order_npsh', 'poly_order_pow']:
        if p_key in data and data[p_key]:
            try: setattr(pump, p_key, int(data[p_key]))
            except (ValueError, TypeError): pass

    imp_dia = data.get('impeller_diameters')
    if isinstance(imp_dia, list):
        pump.impeller_diameters = json.dumps(imp_dia)
    elif isinstance(imp_dia, str):
        pump.impeller_diameters = imp_dia

    extra_curves = data.get('extra_curves') or data.get('extra_curves_json')
    if isinstance(extra_curves, str) and extra_curves.strip():
        try: extra_curves = json.loads(extra_curves)
        except Exception: extra_curves = []
    if isinstance(extra_curves, list):
        pump._transient_extra_curves = extra_curves
        pump.sync_curve_fields(extra_curves_data=extra_curves)

    liquid = data.get('liquid', 'water')
    rho = float(data.get('rho', 1000.0))
    vis = float(data.get('viscosity_cSt', 1.0))
    cv = float(data.get('slurry_cv', 0.0))
    d50 = float(data.get('slurry_d50', 0.3))
    rho_s = float(data.get('rho_solid', 2650.0))

    def parse_levels(raw_str):
        if not raw_str or not str(raw_str).strip():
            return None
        try:
            return [float(x.strip()) for x in str(raw_str).replace(';', ',').split(',') if x.strip()]
        except ValueError:
            return None

    eff_levels = parse_levels(data.get('eff_levels'))
    power_levels = parse_levels(data.get('power_levels'))
    npsh_levels = parse_levels(data.get('npsh_levels'))
    raw_fa = data.get('force_affinity', False)
    if str(raw_fa) in ['true', '1', 'affinity']:
        force_affinity = 'affinity'
    elif str(raw_fa) == 'both':
        force_affinity = 'both'
    elif str(raw_fa) == 'fit':
        force_affinity = 'fit'
    else:
        force_affinity = False

    chart_data = warman_chart_data(pump, liquid=liquid, rho=rho, viscosity_cSt=vis,
                                   slurry_cv=cv, slurry_d50=d50, rho_solid=rho_s,
                                   eff_levels=eff_levels, power_levels=power_levels,
                                   npsh_levels=npsh_levels, force_affinity=force_affinity)

    sh = float(data.get('static_head', 0.0))
    pk = float(data.get('pipe_k', 0.0))
    if sh or pk:
        q_sys = np.linspace(0, pump.q_max or 100, 100).tolist()
        chart_data['system_q'] = q_sys
        chart_data['system_h'] = system_curve_points(sh, pk, q_sys)

    chart_data['raw_table_json'] = data.get('raw_table_json', '[]')
    data_units = data.get('data_units')
    if isinstance(data_units, str):
        try:
            chart_data['data_units'] = json.loads(data_units)
        except Exception:
            chart_data['data_units'] = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw'}
    elif isinstance(data_units, dict):
        chart_data['data_units'] = data_units
    else:
        chart_data['data_units'] = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw'}

    return jsonify(chart_data)


@curves_bp.route('/papi/preview-curve-data', methods=['POST'])
def api_preview_curve_data():
    """Return single-diameter curve data for unsaved preview pump data."""
    data = request.get_json(force=True)
    pump = Pump()
    for field in ['hq_a0', 'hq_a1', 'hq_a2', 'hq_a3', 'hq_a4', 'hq_a5',
                  'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3', 'eff_b4', 'eff_b5',
                  'npsh_c0', 'npsh_c1', 'npsh_c2', 'npsh_c3', 'npsh_c4', 'npsh_c5',
                  'pow_p0', 'pow_p1', 'pow_p2', 'pow_p3', 'pow_p4', 'pow_p5',
                  'speed_rpm', 'impeller_dia_mm', 'q_min', 'q_max', 'q_bep',
                  'hr', 'qr', 'er']:
        val = data.get(field)
        if val is not None:
            setattr(pump, field, float(val))
        else:
            setattr(pump, field, 0.0)

    # Beginners Note: Set per-curve polynomial orders (1 to 5) on temporary Pump instance for preview calculation
    for p_key in ['poly_order', 'poly_order_hq', 'poly_order_eff', 'poly_order_npsh', 'poly_order_pow']:
        if p_key in data and data[p_key]:
            try: setattr(pump, p_key, int(data[p_key]))
            except (ValueError, TypeError): pass

    liquid = data.get('liquid', 'water')
    rho = float(data.get('rho', 1000.0))
    vis = float(data.get('viscosity_cSt', 1.0))
    cv = float(data.get('slurry_cv', 0.0))
    d50 = float(data.get('slurry_d50', 0.3))
    rho_s = float(data.get('rho_solid', 2650.0))

    chart_data = full_curve_data(pump, n_points=100, liquid=liquid, rho=rho,
                                 viscosity_cSt=vis, slurry_cv=cv,
                                 slurry_d50=d50, rho_solid=rho_s)
    bep = bep_point(pump, liquid, rho, vis, cv, d50, rho_s)

    sh = float(data.get('static_head', 0.0))
    pk = float(data.get('pipe_k', 0.0))
    chart_data['system_h'] = system_curve_points(sh, pk, chart_data['q']) if (pk or sh) else None

    chart_data['bep'] = bep
    chart_data['pump'] = pump.to_dict()
    chart_data['raw_table_json'] = data.get('raw_table_json', '[]')
    data_units = data.get('data_units')
    if isinstance(data_units, str):
        try:
            chart_data['data_units'] = json.loads(data_units)
        except Exception:
            chart_data['data_units'] = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw'}
    elif isinstance(data_units, dict):
        chart_data['data_units'] = data_units
    else:
        chart_data['data_units'] = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw'}

    return jsonify(chart_data)


@curves_bp.route('/papi/pump/<int:pump_id>/graph-options', methods=['POST'])
def api_save_graph_options(pump_id):
    """Save graph options dictionary for a pump ID."""
    pump = Pump.query.get_or_404(pump_id)
    data = request.get_json(force=True, silent=True) or {}
    pump.set_graph_options(data)
    db.session.commit()
    return jsonify({'status': 'ok', 'graph_options': pump.get_graph_options()})


@curves_bp.route('/papi/pump/<int:pump_id>/label-pos', methods=['POST'])
def api_save_label_pos(pump_id):
    """Save custom label positions for a pump ID."""
    pump = Pump.query.get_or_404(pump_id)
    data = request.get_json(force=True, silent=True) or {}
    pump.set_custom_label_pos(data, overwrite=False)
    db.session.commit()
    saved = pump.get_custom_label_pos()
    return jsonify({'status': 'ok', 'label_pos': saved})
