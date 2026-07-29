"""
routes/comparison.py — Pump comparison blueprint.

Beginners Note: Compares performance curves and metrics across multiple selected pump models.
"""

from flask import Blueprint, render_template, request, jsonify
from models import Pump
from utils import _get_float
from pump_curves import full_curve_data, bep_point

comparison_bp = Blueprint('comparison', __name__)


@comparison_bp.route('/pump-comparison', endpoint='pump_comparison')
def pump_comparison():
    """Render pump comparison page."""
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


@comparison_bp.route('/papi/compare-pumps')
def api_compare_pumps():
    """API endpoint for multi-pump performance comparison."""
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
