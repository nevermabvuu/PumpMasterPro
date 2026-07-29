import os
import json
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from models import db, Pump
from pump_curves import (
    full_curve_data, operating_point, bep_point,
    system_curve_points, warman_chart_data, fit_pump_polynomials,
    Q_TO_M3H, H_TO_M, POW_TO_KW
)
from pump_selection import select_pumps
from seed_data import seed_pumps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'pumps.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SESSION_SECRET', 'pump-dev-secret')

db.init_app(app)

with app.app_context():
    db.create_all()
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(pumps)"))
            cols = [row[1] for row in result.fetchall()]
            axis_cols = [
                'axis_flow_min', 'axis_flow_max', 'axis_flow_major', 'axis_flow_minor',
                'axis_head_min', 'axis_head_max', 'axis_head_major', 'axis_head_minor',
                'axis_eff_min', 'axis_eff_max', 'axis_eff_major', 'axis_eff_minor',
                'axis_power_min', 'axis_power_max', 'axis_power_major', 'axis_power_minor',
                'axis_npsh_min', 'axis_npsh_max', 'axis_npsh_major', 'axis_npsh_minor',
            ]
            for col_name in ['curve_labels', 'curve_diameters', 'curve_colors', 'curve_modes',
                             'curve_units', 'curve_raw_tables', 'curve_coeffs',
                             'unit_q', 'unit_h', 'unit_npsh', 'unit_pow', 'unit_op_q', 'graph_custom_label_pos',
                             'head_curve_style', 'eff_curve_style', 'power_curve_style', 'npsh_curve_style', 'main_curve_style'] + axis_cols:
                if col_name not in cols:
                    if col_name in axis_cols:
                        col_type = "INTEGER" if col_name.endswith('_minor') else "REAL"
                        conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {col_name} {col_type} DEFAULT NULL"))
                    else:
                        if col_name == 'graph_custom_label_pos':
                            default_val = "'{}'"
                        elif col_name == 'head_curve_style':
                            default_val = "'#58a6ff;2.0,solid'"
                        elif col_name == 'eff_curve_style':
                            default_val = "'#3fb950;1.5,dot'"
                        elif col_name == 'power_curve_style':
                            default_val = "'#f85149;1.5,longdash'"
                        elif col_name == 'npsh_curve_style':
                            default_val = "'#39d3c0;1.5,dashdot'"
                        elif col_name == 'main_curve_style':
                            default_val = "'graph'"
                        elif col_name in ['unit_q', 'unit_op_q']:
                            default_val = "'m3h'"
                        elif col_name in ['unit_h', 'unit_npsh']:
                            default_val = "'m'"
                        elif col_name == 'unit_pow':
                            default_val = "'kw'"
                        else:
                            default_val = "''"
                        conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {col_name} TEXT DEFAULT {default_val}"))
            for old_col in ['main_curve_label', 'main_curve_dia_mm', 'data_units']:
                if old_col in cols:
                    try:
                        conn.execute(text(f"ALTER TABLE pumps DROP COLUMN {old_col}"))
                    except Exception:
                        pass
            conn.commit()
    except Exception as e:
        print("Migration notice:", e)

    seed_pumps(app)


# ── Index ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    pump_count = Pump.query.count()
    return render_template('index.html', pump_count=pump_count)


# ── Pump Data Module ───────────────────────────────────────────────────────────

@app.route('/pump-data')
def pump_data():
    pumps = Pump.query.order_by(Pump.name).all()
    pump_dicts = [p.to_dict() for p in pumps]
    return render_template('pump_data.html', pumps=pumps, pump_dicts=pump_dicts)


def _get_float(d, key, default=0.0):
    val = d.get(key)
    if val is None or str(val).strip() == '':
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _get_nullable_float(d, key):
    """
    Beginners Note: Helper function to extract a float number from form or JSON data.
    Returns None if the value is empty, blank, or missing, allowing Plotly auto-scaling.
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
    Beginners Note: Helper function to extract an integer number from form or JSON data.
    Returns None if the value is empty, blank, or missing.
    """
    val = d.get(key)
    if val is None or str(val).strip() == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _auto_fit_coeffs(raw_tables_str, coeffs_str, units_str=''):
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
                fitted_c = f"{res['hq_a0']},{res['hq_a1']},{res['hq_a2']},{res['hq_a3']}," \
                           f"{res['eff_b0']},{res['eff_b1']},{res['eff_b2']},{res['eff_b3']}," \
                           f"{res['npsh_c0']},{res['npsh_c1']},{res['npsh_c2']}," \
                           f"{res['pow_p0']},{res['pow_p1']},{res['pow_p2']}," \
                           f"{res['q_max']},{res['q_bep']}"
                updated.append(fitted_c)
            except Exception:
                updated.append(cur_coeff or '0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        else:
            updated.append(cur_coeff or '0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
    return '|'.join(updated)


def _pump_from_form(f, pump=None):
    """Build or update a Pump object from a POST form."""
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
    pump.hq_a0 = _get_float(f, 'hq_a0', pump.hq_a0 if pump.hq_a0 is not None else 0.0)
    pump.hq_a1 = _get_float(f, 'hq_a1', pump.hq_a1 if pump.hq_a1 is not None else 0.0)
    pump.hq_a2 = _get_float(f, 'hq_a2', pump.hq_a2 if pump.hq_a2 is not None else 0.0)
    pump.hq_a3 = _get_float(f, 'hq_a3', pump.hq_a3 if pump.hq_a3 is not None else 0.0)
    pump.eff_b0 = _get_float(f, 'eff_b0', pump.eff_b0 if pump.eff_b0 is not None else 0.0)
    pump.eff_b1 = _get_float(f, 'eff_b1', pump.eff_b1 if pump.eff_b1 is not None else 0.0)
    pump.eff_b2 = _get_float(f, 'eff_b2', pump.eff_b2 if pump.eff_b2 is not None else 0.0)
    pump.eff_b3 = _get_float(f, 'eff_b3', pump.eff_b3 if pump.eff_b3 is not None else 0.0)
    pump.npsh_c0 = _get_float(f, 'npsh_c0', pump.npsh_c0 if pump.npsh_c0 is not None else 1.0)
    pump.npsh_c1 = _get_float(f, 'npsh_c1', pump.npsh_c1 if pump.npsh_c1 is not None else 0.0)
    pump.npsh_c2 = _get_float(f, 'npsh_c2', pump.npsh_c2 if pump.npsh_c2 is not None else 0.0)
    pump.pow_p0 = _get_float(f, 'pow_p0', pump.pow_p0 if pump.pow_p0 is not None else 0.0)
    pump.pow_p1 = _get_float(f, 'pow_p1', pump.pow_p1 if pump.pow_p1 is not None else 0.0)
    pump.pow_p2 = _get_float(f, 'pow_p2', pump.pow_p2 if pump.pow_p2 is not None else 0.0)
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


@app.route('/pump-data/new', methods=['GET', 'POST'])
def pump_new():
    if request.method == 'POST':
        pump = _pump_from_form(request.form)
        db.session.add(pump)
        db.session.commit()
        return redirect(url_for('pump_edit', pump_id=pump.id))
    return render_template('pump_form.html', pump=None, action='new')


@app.route('/pump-data/edit/<int:pump_id>', methods=['GET', 'POST'])
def pump_edit(pump_id):
    pump = Pump.query.get_or_404(pump_id)
    if request.method == 'POST':
        _pump_from_form(request.form, pump)
        db.session.commit()
        return redirect(url_for('pump_edit', pump_id=pump.id))
    return render_template('pump_form.html', pump=pump, action='edit')


@app.route('/pump-data/delete/<int:pump_id>', methods=['POST'])
def pump_delete(pump_id):
    pump = Pump.query.get_or_404(pump_id)
    db.session.delete(pump)
    db.session.commit()
    return redirect(url_for('pump_data'))


# ── Curve fitting from data points ────────────────────────────────────────────

@app.route('/papi/fit-curves', methods=['POST'])
def api_fit_curves():
    """
    Fit polynomial curves from tabular performance data.

    Expects JSON:
    {
      "q_h":   [[Q, H], ...],       // at least 3 points, required
      "q_eta": [[Q, eta%], ...],    // at least 3 points, required
      "q_npsh": [[Q, npsh], ...],   // optional
      "q_p":   [[Q, kW], ...],      // optional, overrides derived power
      "rho":   1000                  // fluid density (default 1000)
    }
    Returns fitted polynomial coefficients + key performance metrics.
    """
    data = request.get_json(force=True)
    try:
        result = fit_pump_polynomials(
            q_h   = data.get('q_h', []),
            q_eta = data.get('q_eta', []),
            q_npsh= data.get('q_npsh', None),
            q_p   = data.get('q_p', None),
            rho   = float(data.get('rho', 1000)),
        )
        return jsonify({'ok': True, **result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


# ── Pump Curve Viewer ──────────────────────────────────────────────────────────

@app.route('/pump-curve/<int:pump_id>')
def pump_curve(pump_id):
    pump = Pump.query.get_or_404(pump_id)
    return render_template('pump_curve.html', pump=pump)


@app.route('/papi/curve-data/<int:pump_id>')
def api_curve_data(pump_id):
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


@app.route('/papi/warman-chart/<int:pump_id>')
def api_warman_chart(pump_id):
    """Return full Warman performance map data: family curves + isolines + power lines."""
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


@app.route('/papi/preview-warman-chart', methods=['POST'])
def api_preview_warman_chart():
    """Return full Warman performance map data for unsaved/preview pump data."""
    data = request.get_json(force=True)
    pump = Pump()
    for field in ['hq_a0', 'hq_a1', 'hq_a2', 'hq_a3',
                  'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3',
                  'npsh_c0', 'npsh_c1', 'npsh_c2',
                  'pow_p0', 'pow_p1', 'pow_p2',
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

    # Beginners Note: Set 20 custom axis scale settings on temporary Pump object for preview chart rendering
    for axis_name in ['flow', 'head', 'eff', 'power', 'npsh']:
        for prop in ['min', 'max', 'major']:
            col_key = f'axis_{axis_name}_{prop}'
            setattr(pump, col_key, _get_nullable_float(data, col_key))
        col_minor = f'axis_{axis_name}_minor'
        setattr(pump, col_minor, _get_nullable_int(data, col_minor))

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


@app.route('/papi/preview-curve-data', methods=['POST'])
def api_preview_curve_data():
    """Return single-diameter curve data for unsaved/preview pump data."""
    data = request.get_json(force=True)
    pump = Pump()
    for field in ['hq_a0', 'hq_a1', 'hq_a2', 'hq_a3',
                  'eff_b0', 'eff_b1', 'eff_b2', 'eff_b3',
                  'npsh_c0', 'npsh_c1', 'npsh_c2',
                  'pow_p0', 'pow_p1', 'pow_p2',
                  'speed_rpm', 'impeller_dia_mm', 'q_min', 'q_max', 'q_bep',
                  'hr', 'qr', 'er']:
        val = data.get(field)
        if val is not None:
            setattr(pump, field, float(val))
        else:
            setattr(pump, field, 0.0)

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


# ── Pump Selection Module ──────────────────────────────────────────────────────

@app.route('/pump-selection', methods=['GET', 'POST'])
def pump_selection():
    results   = None
    form_data = {}

    if request.method == 'POST':
        f = request.form
        form_data = f.to_dict()

        q_duty     = _get_float(f, 'q_duty', 0.0)
        h_duty     = _get_float(f, 'h_duty', 0.0)
        
        npsh_val   = f.get('npsh_avail')
        npsh_avail = _get_float(f, 'npsh_avail', 0.0) if (npsh_val is not None and npsh_val.strip() != '') else None

        liquid       = f.get('liquid', 'water')
        rho          = _get_float(f, 'rho', 1000.0)
        vis          = _get_float(f, 'viscosity_cSt', 1.0)
        cv           = _get_float(f, 'slurry_cv', 0.0)
        d50          = _get_float(f, 'slurry_d50', 0.3)
        rho_s        = _get_float(f, 'rho_solid', 2650.0)

        pumps   = Pump.query.all()
        results = select_pumps(pumps, q_duty, h_duty, npsh_avail,
                               liquid, rho, vis, cv, d50, rho_s)

    return render_template('pump_selection.html', results=results, form_data=form_data)


@app.route('/papi/select-pumps', methods=['POST'])
def api_select_pumps():
    data  = request.get_json() or {}
    pumps = Pump.query.all()
    
    npsh_val   = data.get('npsh_avail')
    npsh_avail = _get_float(data, 'npsh_avail', 0.0) if (npsh_val is not None and str(npsh_val).strip() != '') else None
    
    results = select_pumps(
        pumps,
        q_duty=_get_float(data, 'q_duty', 0.0),
        h_duty=_get_float(data, 'h_duty', 0.0),
        npsh_avail=npsh_avail,
        liquid=data.get('liquid', 'water'),
        rho=_get_float(data, 'rho', 1000.0),
        viscosity_cSt=_get_float(data, 'viscosity_cSt', 1.0),
        slurry_cv=_get_float(data, 'slurry_cv', 0.0),
        slurry_d50=_get_float(data, 'slurry_d50', 0.3),
        rho_solid=_get_float(data, 'rho_solid', 2650.0),
    )
    return jsonify(results)


# ── Pump Comparison ────────────────────────────────────────────────────────────

@app.route('/pump-comparison')
def pump_comparison():
    pump_ids = request.args.getlist('ids', type=int)
    q_duty   = request.args.get('q_duty', type=float)
    h_duty   = request.args.get('h_duty', type=float)
    liquid   = request.args.get('liquid', 'water')
    pumps    = Pump.query.filter(Pump.id.in_(pump_ids)).all() if pump_ids else []
    all_pumps= Pump.query.order_by(Pump.name).all()
    return render_template('pump_comparison.html',
                           pumps=pumps, all_pumps=all_pumps,
                           pump_ids=pump_ids, q_duty=q_duty,
                           h_duty=h_duty, liquid=liquid)


@app.route('/papi/compare-pumps')
def api_compare_pumps():
    pump_ids = request.args.getlist('ids', type=int)
    args   = request.args
    liquid   = args.get('liquid', 'water')
    rho      = _get_float(args, 'rho', 1000.0)
    vis      = _get_float(args, 'viscosity_cSt', 1.0)
    cv       = _get_float(args, 'slurry_cv', 0.0)
    d50      = _get_float(args, 'slurry_d50', 0.3)
    rho_s    = _get_float(args, 'rho_solid', 2650.0)

    pumps = Pump.query.filter(Pump.id.in_(pump_ids)).all()
    comparison = []
    for pump in pumps:
        data = full_curve_data(pump, n_points=100, liquid=liquid, rho=rho,
                           viscosity_cSt=vis, slurry_cv=cv,
                               slurry_d50=d50, rho_solid=rho_s)
        bep  = bep_point(pump, liquid, rho, vis, cv, d50, rho_s)
        comparison.append({'pump': pump.to_dict(), 'curves': data, 'bep': bep})
    return jsonify(comparison)


@app.route('/papi/pump/<int:pump_id>/graph-options', methods=['POST'])
def api_save_graph_options(pump_id):
    pump = Pump.query.get_or_404(pump_id)
    data = request.get_json(force=True, silent=True) or {}
    pump.set_graph_options(data)
    db.session.commit()
    return jsonify({'status': 'ok', 'graph_options': pump.get_graph_options()})


# Beginner Note: This API endpoint receives label drag positions from JavaScript in the browser
# whenever a user drags or moves a label on the graph. It saves the coordinates directly
# into the 'graph_custom_label_pos' database column for this pump ID.
@app.route('/papi/pump/<int:pump_id>/label-pos', methods=['POST'])
def api_save_label_pos(pump_id):
    """Save custom label positions to graph_custom_label_pos column in SQLite database."""
    pump = Pump.query.get_or_404(pump_id)
    data = request.get_json(force=True, silent=True) or {}
    print(f"[label-pos] pump_id={pump_id}  incoming={data!r}", flush=True)

    # Save incoming (X, Y) coordinates into pump model and commit to SQLite
    pump.set_custom_label_pos(data, overwrite=False)
    db.session.commit()

    saved = pump.get_custom_label_pos()
    print(f"[label-pos] saved to DB: {saved!r}", flush=True)
    return jsonify({'status': 'ok', 'label_pos': saved})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
