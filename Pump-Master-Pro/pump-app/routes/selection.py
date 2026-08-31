"""
routes/selection.py — Pump Selection blueprint.

Beginners Note:
    This module handles the pump selection page and API endpoints.
    It receives duty point parameters and filter criteria from the user,
    passes them to the selection engine (pump_selection.py), and renders
    the shortlist results with filter options populated from the database.

Routes:
    GET/POST /pump-selection    — Main pump selection page (HTML form + results)
    POST     /papi/select-pumps — AJAX API endpoint returning JSON results
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, request, jsonify, session
from models import Pump
from utils import _get_float, get_visible_pumps_query, get_current_organisation
from pump_selection import select_pumps, get_filter_options

selection_bp = Blueprint('selection', __name__)


@selection_bp.route('/pump-selection', methods=['GET', 'POST'], endpoint='pump_selection')
def pump_selection():
    """
    Render pump selection search page and display matching pumps filtered by allowed organisations.

    Beginners Note:
        GET  → Shows empty form with filter dropdowns populated from the database
        POST → Processes the duty point + filters, runs selection engine, displays shortlist results

    Template context:
        - results: List of matching pump dicts (None if GET, empty list if no matches on POST)
        - form_data: Dict of submitted form values (for re-populating the form)
        - filter_options: Dict of unique values for dropdown filters (manufacturers, types, etc.)
        - sort_by: Current sort field (default 'rating')
    """
    results   = None
    form_data = {}

    # ── Populate filter options from all visible pumps ─────────────────────
    # Beginners Note: We always need filter options to populate the dropdowns, even on GET
    all_pumps = get_visible_pumps_query().all()
    filter_options = get_filter_options(all_pumps)

    if request.method == 'POST':
        f = request.form.to_dict()
        session['selection_form_data'] = f
        form_data = f
    else:
        # GET request - load from session
        f = session.get('selection_form_data', {})
        form_data = f

    # If we have basic duty point, run the selection
    q_duty_str = f.get('q_duty')
    h_duty_str = f.get('h_duty')
    
    if q_duty_str and h_duty_str:
        # ── Extract duty point parameters ──────────────────────────────────
        q_duty     = _get_float(f, 'q_duty', 0.0)
        h_duty     = _get_float(f, 'h_duty', 0.0)

        # Beginners Note: NPSH is optional — None means "don't check NPSH margin"
        npsh_val   = f.get('npsh_avail')
        npsh_avail = _get_float(f, 'npsh_avail', 0.0) if (npsh_val is not None and npsh_val.strip() != '') else None

        # ── Extract liquid parameters ──────────────────────────────────────
        liquid       = f.get('liquid', 'water')
        if liquid == 'slurry':
            rho      = _get_float(f, 'rho_l', 1000.0)
        else:
            # We might have multiple 'rho' inputs in the form, to_dict() might grab the last one.
            # We will just grab the first 'rho' available.
            rho      = _get_float(f, 'rho', 1000.0)
            
        vis          = _get_float(f, 'viscosity_cSt', 1.0)
        cv           = _get_float(f, 'slurry_cv', 0.0)
        d50          = _get_float(f, 'slurry_d50', 0.3)
        rho_s        = _get_float(f, 'rho_solid', 2650.0)

        # ── Extract filter criteria ────────────────────────────────────────
        # Beginners Note: Build a filters dict from the form. Empty strings mean "no filter".
        filters = {}
        if f.get('filter_manufacturer'):
            filters['manufacturer'] = f.get('filter_manufacturer')
        if f.get('filter_pump_type'):
            filters['pump_type'] = f.get('filter_pump_type')
        if f.get('filter_speed_min'):
            filters['speed_min'] = f.get('filter_speed_min')
        if f.get('filter_speed_max'):
            filters['speed_max'] = f.get('filter_speed_max')
        if f.get('filter_size'):
            filters['size'] = f.get('filter_size')
        if f.get('filter_application'):
            filters['application'] = f.get('filter_application')

        # ── Run selection engine ───────────────────────────────────────────
        results = select_pumps(all_pumps, q_duty, h_duty, npsh_avail,
                               liquid, rho, vis, cv, d50, rho_s,
                               filters=filters,
                               operation_mode=f.get('operation_mode', 'fixed'))

    # ── Render template with results and filter options ─────────────────────
    return render_template('pump_selection.html',
                           results=results,
                           form_data=form_data,
                            filter_options=filter_options,
                           sort_by=form_data.get('sort_by', 'rating'))
@selection_bp.route('/pump-selection/details/<int:pump_id>', endpoint='pump_selection_details')
def pump_selection_details(pump_id):
    """
    Detailed view for a specific pump in the selection results.
    Shows the graphs for the pump and a sidebar with the other shortlisted pumps.
    """
    from models import Pump
    
    # Load session data
    f = session.get('selection_form_data', {})
    
    # Run the selection engine to get the shortlist
    results = []
    all_pumps = get_visible_pumps_query().all()
    q_duty_str = f.get('q_duty')
    h_duty_str = f.get('h_duty')
    
    if q_duty_str and h_duty_str:
        q_duty = _get_float(f, 'q_duty', 0.0)
        h_duty = _get_float(f, 'h_duty', 0.0)
        npsh_val = f.get('npsh_avail')
        npsh_avail = _get_float(f, 'npsh_avail', 0.0) if (npsh_val is not None and npsh_val.strip() != '') else None

        liquid = f.get('liquid', 'water')
        if liquid == 'slurry':
            rho = _get_float(f, 'rho_l', 1000.0)
        else:
            rho = _get_float(f, 'rho', 1000.0)
            
        vis = _get_float(f, 'viscosity_cSt', 1.0)
        cv = _get_float(f, 'slurry_cv', 0.0)
        d50 = _get_float(f, 'slurry_d50', 0.3)
        rho_s = _get_float(f, 'rho_solid', 2650.0)

        filters = {}
        if f.get('filter_manufacturer'): filters['manufacturer'] = f.get('filter_manufacturer')
        if f.get('filter_pump_type'): filters['pump_type'] = f.get('filter_pump_type')
        if f.get('filter_speed_min'): filters['speed_min'] = f.get('filter_speed_min')
        if f.get('filter_speed_max'): filters['speed_max'] = f.get('filter_speed_max')
        if f.get('filter_size'): filters['size'] = f.get('filter_size')
        if f.get('filter_application'): filters['application'] = f.get('filter_application')

        results = select_pumps(all_pumps, q_duty, h_duty, npsh_avail,
                               liquid, rho, vis, cv, d50, rho_s,
                               filters=filters,
                               operation_mode=f.get('operation_mode', 'fixed'))

    # Sort results
    sort_by = f.get('sort_by', 'rating')
    if sort_by == 'rating':
        results.sort(key=lambda x: x.get('rating', 0), reverse=True)
    elif sort_by == 'eff':
        results.sort(key=lambda x: x.get('op_eta', 0), reverse=True)

    pump = Pump.query.get_or_404(pump_id)
    current_org = get_current_organisation()
    org_styles = current_org.get_graph_styles() if current_org else {}
    
    # Beginners Note: Find the active_result, default_report_id, and available_reports for the selected pump so we can build the Report URLs
    active_result = None
    default_report_id = 1 # Fallback
    for r in results:
        if r.get('pump_id') == pump_id:
            active_result = r
            default_report_id = r.get('default_report_id', 1)
            break

    # Get all available reports for the organisation / pump
    available_reports = pump.get_effective_catalogue_reports(current_org)
    if not available_reports and current_org:
        available_reports = current_org.get_catalogue_reports()
    if not available_reports:
        from models import ReportConfig
        available_reports = ReportConfig.query.all()
    
    return render_template('pump_selection_details.html',
                           pump=pump,
                           results=results,
                           active_result=active_result,
                           form_data=f,
                           current_org=current_org,
                           org_styles=org_styles,
                           default_report_id=default_report_id,
                           available_reports=available_reports)


@selection_bp.route('/papi/select-pumps', methods=['POST'])
def api_select_pumps():
    """
    AJAX API endpoint for pump selection search.

    Beginners Note:
        Accepts JSON body with duty point parameters and optional filters.
        Returns a JSON array of matching pump dicts sorted by rating.
        Used by the frontend for live search without page reload.

    Request body (JSON):
        {
            "q_duty": 150, "h_duty": 35, "npsh_avail": 8,
            "liquid": "water", "rho": 1000,
            "filters": {"manufacturer": "Warman", "pump_type": "centrifugal slurry"}
        }

    Response:
        [{ "pump_id": 2, "pump_name": "Warman 6/4 D-AH", "rating": 85, ... }, ...]
    """
    data  = request.get_json() or {}
    pumps = get_visible_pumps_query().all()

    # ── Extract NPSH (optional) ────────────────────────────────────────────
    npsh_val   = data.get('npsh_avail')
    npsh_avail = _get_float(data, 'npsh_avail', 0.0) if (npsh_val is not None and str(npsh_val).strip() != '') else None

    # ── Extract filters from JSON body ─────────────────────────────────────
    filters = data.get('filters') or {}

    # ── Run selection engine ───────────────────────────────────────────────
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
        filters=filters,
        operation_mode=data.get('operation_mode', 'fixed')
    )
    return jsonify(results)


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

