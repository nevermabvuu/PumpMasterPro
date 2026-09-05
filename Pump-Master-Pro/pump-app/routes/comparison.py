"""
routes/comparison.py — Pump comparison blueprint.

Beginners Note: Compares performance curves and metrics across multiple selected pump models.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, request, jsonify, session
from models import Pump
from utils import _get_float, get_visible_pumps_query, get_current_organisation
from pump_curves import full_curve_data, bep_point
from routes.selection import run_selection_from_form

comparison_bp = Blueprint('comparison', __name__)


@comparison_bp.route('/pump-comparison', endpoint='pump_comparison')
def pump_comparison():
    """
    Render pump comparison page.
    If an active pump selection exists in the session, automatically loads the
    complete detailed shortlisted pumps list and pre-selects the compared pumps.
    """
    # ── 1. Load active selection parameters ──────────────────────────────────
    # Check session for selection parameters; if absent (e.g. direct link or fresh tab),
    # fallback to URL query parameters so shortlisted pumps are always automatically listed.
    f = session.get('selection_form_data', {})
    if not f or not f.get('q_duty'):
        args_dict = request.args.to_dict()
        if args_dict.get('q_duty') and args_dict.get('h_duty'):
            f = args_dict
            session['selection_form_data'] = f
            session.modified = True

    # ── 1b. Fetch organisation and catalogue pumps for selection engine ──────
    # Beginners Note: Ensures selection engine has the complete catalogue dataset
    current_org = get_current_organisation()
    all_pumps = get_visible_pumps_query().order_by(Pump.name).all()

    # ── 2. Run selection engine to get all shortlisted pumps ─────────────────
    # If selection parameters exist, calculate all shortlisted pumps for automatic listing.
    shortlisted_results, ctx = run_selection_from_form(f, all_pumps=all_pumps, current_org=current_org)
    if shortlisted_results is None:
        shortlisted_results = []

    # Get pump IDs requested for comparison
    pump_ids = request.args.getlist('ids', type=int)
    
    # If no IDs explicitly passed via query string, but shortlisted results exist:
    if not pump_ids and shortlisted_results:
        # Pre-select top 2-3 pumps
        pump_ids = [r['pump_id'] for r in shortlisted_results[:3] if 'pump_id' in r]
    
    pumps = Pump.query.filter(Pump.id.in_(pump_ids)).all() if pump_ids else []

    # Duty point parameters (prefer query params, fallback to session ctx)
    q_duty = request.args.get('q_duty', type=float)
    if q_duty is None and ctx.get('raw_q_duty'):
        q_duty = ctx.get('raw_q_duty')

    h_duty = request.args.get('h_duty', type=float)
    if h_duty is None and ctx.get('raw_h_duty'):
        h_duty = ctx.get('raw_h_duty')

    liquid = request.args.get('liquid')
    if not liquid:
        liquid = ctx.get('liquid', 'water')

    operation_mode = f.get('operation_mode', 'fixed')

    return render_template('pump_comparison.html',
                           pumps=pumps,
                           all_pumps=all_pumps,
                           pump_ids=pump_ids,
                           shortlisted_results=shortlisted_results,
                           q_duty=q_duty,
                           h_duty=h_duty,
                           liquid=liquid,
                           ctx=ctx,
                           form_data=f,
                           operation_mode=operation_mode)


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

