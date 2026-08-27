"""
routes/selection.py — Pump selection blueprint.

Beginners Note: Searches pump database for pumps matching a target duty point (Flow Q & Head H).
"""

from flask import Blueprint, render_template, request, jsonify
from models import Pump
from utils import _get_float, get_visible_pumps_query
from pump_selection import select_pumps

selection_bp = Blueprint('selection', __name__)


@selection_bp.route('/pump-selection', methods=['GET', 'POST'], endpoint='pump_selection')
def pump_selection():
    """Render pump selection search page and display matching pumps filtered by allowed organisations."""
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

        pumps   = get_visible_pumps_query().all()
        results = select_pumps(pumps, q_duty, h_duty, npsh_avail,
                               liquid, rho, vis, cv, d50, rho_s)

    return render_template('pump_selection.html', results=results, form_data=form_data)


@selection_bp.route('/papi/select-pumps', methods=['POST'])
def api_select_pumps():
    """API endpoint for pump selection search."""
    data  = request.get_json() or {}
    pumps = get_visible_pumps_query().all()
    
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
