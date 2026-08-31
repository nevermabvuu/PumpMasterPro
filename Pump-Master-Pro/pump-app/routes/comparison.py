"""
routes/comparison.py — Pump comparison blueprint.

Beginners Note: Compares performance curves and metrics across multiple selected pump models.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, request, jsonify
from models import Pump
from utils import _get_float, get_visible_pumps_query
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
    all_pumps= get_visible_pumps_query().order_by(Pump.name).all()
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
    
    from pump_curves import family_curves_diameter
    
    op_mode = args.get('operation_mode', 'fixed')
    
    for pump in pumps:
        # If the pump is VSD but we want a fixed-speed comparison, temporarily override its family type
        # so that it only returns the physical impeller diameter curve, not the RPM overlays.
        orig_family_type = pump.family_type
        orig_extra = pump.extra_curves_json
        orig_cd = getattr(pump, 'curve_diameters', None)
        
        # When evaluating a VS pump in fixed-speed mode, treat it as a trimmed impeller pump.
        # We clear extra_curves_json so it ignores its native RPM curves,
        # but keep graph_dia_overlay_values so it uses the user-specified dia overlays.
        if op_mode == 'fixed' and pump.family_type == 'variable_speed':
            pump.family_type = 'trimmed_impeller'
            pump.extra_curves_json = '[]'
            pump.curve_diameters = ''
            
        # Conversely, when evaluating a fixed-speed pump in VSD mode, treat it as a variable speed pump.
        # We clear extra_curves_json so it ignores its native dia curves,
        # but keep graph_rpm_values so it uses the user-specified RPM overlays.
        elif op_mode == 'vsd' and pump.family_type != 'variable_speed':
            pump.family_type = 'variable_speed'
            pump.extra_curves_json = '[]'
            pump.curve_diameters = ''

        data = full_curve_data(pump, n_points=100, liquid=liquid, rho=rho,
                               viscosity_cSt=vis, slurry_cv=cv,
                               slurry_d50=d50, rho_solid=rho_s)
        family = family_curves_diameter(pump, n_points=100, liquid=liquid, rho=rho,
                                        viscosity_cSt=vis, slurry_cv=cv, slurry_d50=d50, rho_solid=rho_s)
        bep  = bep_point(pump, liquid, rho, vis, cv, d50, rho_s)
        
        # Restore family_type and extra attributes
        pump.family_type = orig_family_type
        pump.extra_curves_json = orig_extra
        if orig_cd is not None: pump.curve_diameters = orig_cd
        
        comparison.append({'pump': pump.to_dict(), 'curves': data, 'family': family, 'bep': bep})
    return jsonify(comparison)


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

