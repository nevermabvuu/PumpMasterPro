import os
import json
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from models import db, Pump
from pump_curves import (
    full_curve_data, operating_point, bep_point,
    system_curve_points, warman_chart_data, fit_pump_polynomials
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


def _pump_from_form(f, pump=None):
    """Build or update a Pump object from a POST form."""
    if pump is None:
        pump = Pump(hq_a0=0.0, q_max=100.0)

    pump.name             = f['name']
    pump.manufacturer     = f.get('manufacturer', pump.manufacturer or '')
    pump.model_number     = f.get('model_number', pump.model_number or '')
    pump.size             = f.get('size', pump.size or '')
    pump.speed_rpm        = _get_float(f, 'speed_rpm', pump.speed_rpm if pump.speed_rpm is not None else 1450.0)
    pump.impeller_dia_mm  = _get_float(f, 'impeller_dia_mm', pump.impeller_dia_mm if pump.impeller_dia_mm is not None else 300.0)
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
    pump.pump_type   = f.get('pump_type', pump.pump_type or 'centrifugal')
    pump.application = f.get('application', pump.application or '')
    pump.notes       = f.get('notes', pump.notes or '')
    return pump


@app.route('/pump-data/new', methods=['GET', 'POST'])
def pump_new():
    if request.method == 'POST':
        pump = _pump_from_form(request.form)
        db.session.add(pump)
        db.session.commit()
        return redirect(url_for('pump_data'))
    return render_template('pump_form.html', pump=None, action='new')


@app.route('/pump-data/edit/<int:pump_id>', methods=['GET', 'POST'])
def pump_edit(pump_id):
    pump = Pump.query.get_or_404(pump_id)
    if request.method == 'POST':
        _pump_from_form(request.form, pump)
        db.session.commit()
        return redirect(url_for('pump_data'))
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

    data = warman_chart_data(pump, liquid=liquid, rho=rho, viscosity_cSt=vis,
                             slurry_cv=cv, slurry_d50=d50, rho_solid=rho_s)

    sh = _get_float(args, 'static_head', 0.0)
    pk = _get_float(args, 'pipe_k', 0.0)
    q_max = pump.q_max
    if sh or pk:
        q_sys = np.linspace(0, q_max, 100).tolist()
        data['system_q'] = q_sys
        data['system_h'] = system_curve_points(sh, pk, q_sys)

    return jsonify(data)


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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
