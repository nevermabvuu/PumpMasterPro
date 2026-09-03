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

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, abort
from models import Pump
from utils import (
    _get_float, get_visible_pumps_query, get_current_organisation,
    UNITS_FLOW, UNITS_HEAD, UNITS_POWER, UNITS_DENSITY, UNITS_SIZE, convert_unit
)
from pump_selection import select_pumps, get_filter_options

selection_bp = Blueprint('selection', __name__)


def _get_enabled_pump_attributes(current_org, all_pumps):
    """
    Beginners Note:
        Collects all defined and enabled custom pump attributes (slots 1 to 30)
        from the active working organisation as well as any organisations owning
        the pumps currently visible to the user.
        
        Why this is important:
        - In Organisation Settings, users configure custom attributes such as:
          Slot #1: 'Impeller Type' (Open, Semi-Open, Closed)
          Slot #2: 'Design Standard' (ANSI, ISO, API 610)
          Slot #5: 'Impeller Material' (Rubber, Metal, Stainless Steel)
        - This helper aggregates all enabled attribute definitions so that the
          Pump Selection view can render interactive filter controls for every active attribute.
    """
    attr_map = {}
    
    # 1. Attributes defined and enabled on the current active organisation
    if current_org and hasattr(current_org, 'get_enabled_pump_attributes'):
        for a in current_org.get_enabled_pump_attributes():
            attr_map[a['index']] = a
            
    # 2. Attributes defined and enabled on organisations of visible catalogue pumps
    for p in (all_pumps or []):
        if p.organisation and hasattr(p.organisation, 'get_enabled_pump_attributes'):
            for a in p.organisation.get_enabled_pump_attributes():
                if a['index'] not in attr_map:
                    attr_map[a['index']] = a

    # 3. Fallback: check all registered organisations in case none were attached yet
    if not attr_map:
        from models import Organisation
        for org in Organisation.query.all():
            for a in org.get_enabled_pump_attributes():
                if a['index'] not in attr_map:
                    attr_map[a['index']] = a

    return sorted(attr_map.values(), key=lambda a: a['index'])


@selection_bp.route('/pump-selection', methods=['GET', 'POST'], endpoint='pump_selection')
def pump_selection():
    """
    Render pump selection search page and display matching pumps filtered by allowed organisations.

    Beginners Note:
        Supports comprehensive multi-unit engineering conversions (Metric SI vs Imperial US and custom mixed units).
        User inputs are normalized to base SI units (m³/h, m, kg/m³) for hydraulic evaluation,
        and results are dynamically presented in the user's selected display units.
        Custom organisation pump attributes (e.g. Impeller Type: Open/Closed) are loaded and
        rendered as selection filters.
    """
    results   = None
    form_data = {}

    # ── Active organisation and enabled custom attributes ─────────────────
    # Beginners Note:
    # Fetch the active working organisation and determine which custom pump attributes
    # are enabled. These enabled attributes (e.g., 'Impeller Type', 'Impeller Material')
    # will be rendered directly in the Pump Selection view as selectable filters.
    current_org = get_current_organisation()
    all_pumps = get_visible_pumps_query().all()
    enabled_pump_attributes = _get_enabled_pump_attributes(current_org, all_pumps)

    # ── Populate filter options from all visible pumps ─────────────────────
    # Beginners Note:
    # get_filter_options extracts distinct catalogue values (e.g., 'Open', 'Closed')
    # for each enabled custom attribute slot to populate the dropdown selectors.
    filter_options = get_filter_options(all_pumps, enabled_attributes=enabled_pump_attributes)

    if request.method == 'POST':
        f = request.form.to_dict()
        session['selection_form_data'] = f
        form_data = f
    else:
        # GET request - load from session
        f = session.get('selection_form_data', {})
        form_data = f

    # ── Unit System & Individual Dropdown Selections ─────────────────────────
    # Beginners Note: Default to Metric SI if not explicitly specified by user
    unit_system      = f.get('unit_system', 'metric')
    unit_q           = f.get('unit_q', 'm3h')
    unit_h           = f.get('unit_h', 'm')
    unit_npsh        = f.get('unit_npsh', 'm')
    unit_static_head = f.get('unit_static_head', 'm')
    unit_rho         = f.get('unit_rho', 'kgm3')
    unit_d50         = f.get('unit_d50', 'mm')
    unit_pow         = f.get('unit_pow', 'hp' if unit_system == 'imperial' else 'kw')

    # If we have basic duty point, run the selection
    q_duty_str = f.get('q_duty')
    h_duty_str = f.get('h_duty')
    
    if q_duty_str and h_duty_str:
        # ── Extract raw user-entered numbers ─────────────────────────────────
        raw_q_duty     = _get_float(f, 'q_duty', 0.0)
        raw_h_duty     = _get_float(f, 'h_duty', 0.0)

        npsh_val       = f.get('npsh_avail')
        raw_npsh_avail = _get_float(f, 'npsh_avail', 0.0) if (npsh_val is not None and str(npsh_val).strip() != '') else None

        # ── Normalize inputs into Base SI Metric for the Selection Engine ─────
        # Base units: Q in m³/h, H in m, NPSHa in m, Static Head in m
        q_duty     = convert_unit(raw_q_duty, unit_q, 'm3h', 'flow')
        h_duty     = convert_unit(raw_h_duty, unit_h, 'm', 'head')
        npsh_avail = convert_unit(raw_npsh_avail, unit_npsh, 'm', 'head') if raw_npsh_avail is not None else None

        # ── Extract liquid parameters ──────────────────────────────────────
        liquid       = f.get('liquid', 'water')
        if liquid == 'slurry':
            raw_rho_l = _get_float(f, 'rho_l', 1000.0)
            rho       = convert_unit(raw_rho_l, unit_rho, 'kgm3', 'density')
        else:
            raw_rho   = _get_float(f, 'rho', 1000.0)
            rho       = convert_unit(raw_rho, unit_rho, 'kgm3', 'density')
            
        vis          = _get_float(f, 'viscosity_cSt', 1.0)
        cv           = _get_float(f, 'slurry_cv', 0.0)
        raw_d50      = _get_float(f, 'slurry_d50', 0.3)
        d50          = convert_unit(raw_d50, unit_d50, 'mm', 'size')
        raw_rho_s    = _get_float(f, 'rho_solid', 2650.0)
        rho_s        = convert_unit(raw_rho_s, unit_rho, 'kgm3', 'density')

        # ── Extract filter criteria ────────────────────────────────────────
        filters = {}
        if f.get('filter_manufacturer'): filters['manufacturer'] = f.get('filter_manufacturer')
        if f.get('filter_pump_type'):     filters['pump_type'] = f.get('filter_pump_type')
        if f.get('filter_speed_min'):    filters['speed_min'] = f.get('filter_speed_min')
        if f.get('filter_speed_max'):    filters['speed_max'] = f.get('filter_speed_max')
        if f.get('filter_size'):         filters['size'] = f.get('filter_size')
        if f.get('filter_application'):  filters['application'] = f.get('filter_application')

        # Extract custom organisation pump attribute filters (1 to 30)
        for i in range(1, 31):
            attr_val = f.get(f'filter_attribute_{i}') or f.get(f'filter_PumpAttribute{i}') or f.get(f'PumpAttribute{i}')
            if attr_val and str(attr_val).strip():
                filters[f'attribute_{i}'] = str(attr_val).strip()

        # ── Fixed Speed Mode (Auto Calculate Pump Speed vs Catalogue Speed) ──
        fixed_speed_mode = f.get('fixed_speed_mode', 'auto')

        # ── Motor Selection & Drive Arrangement Controls ─────────────────
        # Beginners Note:
        # Motor frequency (50/60 Hz), poles (2, 4, 6, 8), selection mode (auto/manual),
        # VSD frequency limits, and drive arrangement (Direct Coupled).
        try:
            motor_freq_hz = int(f.get('motor_freq_hz', 50))
        except (ValueError, TypeError):
            motor_freq_hz = 50

        try:
            motor_poles = int(f.get('motor_poles', 4))
        except (ValueError, TypeError):
            motor_poles = 4

        motor_selection_mode = f.get('motor_selection_mode', 'auto')
        manual_motor_id      = int(f.get('manual_motor_id')) if (f.get('manual_motor_id') and str(f.get('manual_motor_id')).strip() != '') else None
        vsd_f_min            = _get_float(f, 'vsd_f_min', 30.0)
        vsd_f_max            = _get_float(f, 'vsd_f_max', 60.0 if motor_freq_hz == 60 else 50.0)
        drive_type           = f.get('drive_type', 'direct')

        # ── Run selection engine ───────────────────────────────────────────
        results = select_pumps(all_pumps, q_duty, h_duty, npsh_avail,
                               liquid, rho, vis, cv, d50, rho_s,
                               filters=filters,
                               operation_mode=f.get('operation_mode', 'fixed'),
                               enabled_attributes=enabled_pump_attributes,
                               fixed_speed_mode=fixed_speed_mode,
                               motor_freq_hz=motor_freq_hz,
                               motor_poles=motor_poles,
                               motor_selection_mode=motor_selection_mode,
                               manual_motor_id=manual_motor_id,
                               vsd_f_min=vsd_f_min,
                               vsd_f_max=vsd_f_max,
                               drive_type=drive_type)

        # ── Convert result performance metrics into user-selected display units ─
        # Beginners Note: Attach display values so cards & result tables show native user units
        for r in results:
            r['disp_q_duty']   = raw_q_duty
            r['disp_h_duty']   = raw_h_duty
            r['disp_unit_q']   = UNITS_FLOW.get(unit_q, {}).get('name', unit_q)
            r['disp_unit_h']   = UNITS_HEAD.get(unit_h, {}).get('name', unit_h)
            r['disp_unit_pow'] = UNITS_POWER.get(unit_pow, {}).get('name', unit_pow)
            r['disp_unit_npsh']= UNITS_HEAD.get(unit_npsh, {}).get('name', unit_npsh)
            
            # Power in user's unit (kW or hp)
            raw_p = r.get('op_power')
            r['disp_power']    = convert_unit(raw_p, 'kw', unit_pow, 'power') if raw_p is not None else None
            
            # NPSHr in user's unit (m or ft)
            raw_np = r.get('op_npsh')
            r['disp_npshr']    = convert_unit(raw_np, 'm', unit_npsh, 'head') if raw_np is not None else None

    # ── Unit dictionary bundles for template dropdown rendering ─────────────
    units_tables = {
        'flow':    UNITS_FLOW,
        'head':    UNITS_HEAD,
        'power':   UNITS_POWER,
        'density': UNITS_DENSITY,
        'size':    UNITS_SIZE
    }

    # ── Available Motors for Manual Selection ───────────────────────────────
    # Beginners Note: Query standard motors matching the active frequency and pole count
    from motor_models import get_available_motors
    active_motor_freq = int(form_data.get('motor_freq_hz', 50))
    active_motor_poles = int(form_data.get('motor_poles', 4))
    available_motors = get_available_motors(frequency_hz=active_motor_freq, poles=active_motor_poles)

    # ── Render template with results and filter options ─────────────────────
    return render_template('pump_selection.html',
                           results=results,
                           form_data=form_data,
                           filter_options=filter_options,
                           current_org=current_org,
                           enabled_pump_attributes=enabled_pump_attributes,
                           available_motors=available_motors,
                           units_tables=units_tables,
                           unit_system=unit_system,
                           unit_q=unit_q,
                           unit_h=unit_h,
                           unit_npsh=unit_npsh,
                           unit_static_head=unit_static_head,
                           unit_rho=unit_rho,
                           unit_d50=unit_d50,
                           unit_pow=unit_pow,
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
    
    unit_system      = f.get('unit_system', 'metric')
    unit_q           = f.get('unit_q', 'm3h')
    unit_h           = f.get('unit_h', 'm')
    unit_npsh        = f.get('unit_npsh', 'm')
    unit_static_head = f.get('unit_static_head', 'm')
    unit_rho         = f.get('unit_rho', 'kgm3')
    unit_d50         = f.get('unit_d50', 'mm')
    unit_pow         = f.get('unit_pow', 'hp' if unit_system == 'imperial' else 'kw')

    # Run the selection engine to get the shortlist
    results = []
    current_org = get_current_organisation()
    all_pumps = get_visible_pumps_query().all()
    enabled_pump_attributes = _get_enabled_pump_attributes(current_org, all_pumps)
    q_duty_str = f.get('q_duty')
    h_duty_str = f.get('h_duty')
    
    if q_duty_str and h_duty_str:
        raw_q_duty = _get_float(f, 'q_duty', 0.0)
        raw_h_duty = _get_float(f, 'h_duty', 0.0)
        npsh_val = f.get('npsh_avail')
        raw_npsh_avail = _get_float(f, 'npsh_avail', 0.0) if (npsh_val is not None and str(npsh_val).strip() != '') else None

        # Normalize to SI base
        q_duty     = convert_unit(raw_q_duty, unit_q, 'm3h', 'flow')
        h_duty     = convert_unit(raw_h_duty, unit_h, 'm', 'head')
        npsh_avail = convert_unit(raw_npsh_avail, unit_npsh, 'm', 'head') if raw_npsh_avail is not None else None

        liquid = f.get('liquid', 'water')
        if liquid == 'slurry':
            raw_rho_l = _get_float(f, 'rho_l', 1000.0)
            rho       = convert_unit(raw_rho_l, unit_rho, 'kgm3', 'density')
        else:
            raw_rho   = _get_float(f, 'rho', 1000.0)
            rho       = convert_unit(raw_rho, unit_rho, 'kgm3', 'density')
            
        vis = _get_float(f, 'viscosity_cSt', 1.0)
        cv = _get_float(f, 'slurry_cv', 0.0)
        raw_d50 = _get_float(f, 'slurry_d50', 0.3)
        d50 = convert_unit(raw_d50, unit_d50, 'mm', 'size')
        raw_rho_s = _get_float(f, 'rho_solid', 2650.0)
        rho_s = convert_unit(raw_rho_s, unit_rho, 'kgm3', 'density')

        filters = {}
        if f.get('filter_manufacturer'): filters['manufacturer'] = f.get('filter_manufacturer')
        if f.get('filter_pump_type'):     filters['pump_type'] = f.get('filter_pump_type')
        if f.get('filter_speed_min'):    filters['speed_min'] = f.get('filter_speed_min')
        if f.get('filter_speed_max'):    filters['speed_max'] = f.get('filter_speed_max')
        if f.get('filter_size'):         filters['size'] = f.get('filter_size')
        if f.get('filter_application'):  filters['application'] = f.get('filter_application')

        for i in range(1, 31):
            attr_val = f.get(f'filter_attribute_{i}') or f.get(f'filter_PumpAttribute{i}') or f.get(f'PumpAttribute{i}')
            if attr_val and str(attr_val).strip():
                filters[f'attribute_{i}'] = str(attr_val).strip()

        fixed_speed_mode = f.get('fixed_speed_mode', 'auto')
        try:
            motor_freq_hz = int(f.get('motor_freq_hz', 50))
        except (ValueError, TypeError):
            motor_freq_hz = 50

        try:
            motor_poles = int(f.get('motor_poles', 4))
        except (ValueError, TypeError):
            motor_poles = 4

        motor_selection_mode = f.get('motor_selection_mode', 'auto')
        manual_motor_id      = int(f.get('manual_motor_id')) if (f.get('manual_motor_id') and str(f.get('manual_motor_id')).strip() != '') else None
        vsd_f_min            = _get_float(f, 'vsd_f_min', 30.0)
        vsd_f_max            = _get_float(f, 'vsd_f_max', 60.0 if motor_freq_hz == 60 else 50.0)
        drive_type           = f.get('drive_type', 'direct')

        results = select_pumps(all_pumps, q_duty, h_duty, npsh_avail,
                               liquid, rho, vis, cv, d50, rho_s,
                               filters=filters,
                               operation_mode=f.get('operation_mode', 'fixed'),
                               enabled_attributes=enabled_pump_attributes,
                               fixed_speed_mode=fixed_speed_mode,
                               motor_freq_hz=motor_freq_hz,
                               motor_poles=motor_poles,
                               motor_selection_mode=motor_selection_mode,
                               manual_motor_id=manual_motor_id,
                               vsd_f_min=vsd_f_min,
                               vsd_f_max=vsd_f_max,
                               drive_type=drive_type)

        for r in results:
            r['disp_q_duty']   = raw_q_duty
            r['disp_h_duty']   = raw_h_duty
            r['disp_unit_q']   = UNITS_FLOW.get(unit_q, {}).get('name', unit_q)
            r['disp_unit_h']   = UNITS_HEAD.get(unit_h, {}).get('name', unit_h)
            r['disp_unit_pow'] = UNITS_POWER.get(unit_pow, {}).get('name', unit_pow)
            r['disp_unit_npsh']= UNITS_HEAD.get(unit_npsh, {}).get('name', unit_npsh)
            raw_p = r.get('op_power')
            r['disp_power']    = convert_unit(raw_p, 'kw', unit_pow, 'power') if raw_p is not None else None
            raw_np = r.get('op_npsh')
            r['disp_npshr']    = convert_unit(raw_np, 'm', unit_npsh, 'head') if raw_np is not None else None

    # Sort results
    sort_by = f.get('sort_by', 'rating')
    if sort_by == 'rating':
        results.sort(key=lambda x: x.get('rating', 0), reverse=True)
    elif sort_by == 'eff':
        results.sort(key=lambda x: x.get('op_eta', 0), reverse=True)

    # ── Security & Shortlist Authorization Check ──────────────────────────────
    shortlisted_ids = [r['pump_id'] for r in results if 'pump_id' in r]

    if not results or not shortlisted_ids:
        flash("No active pump selection found. Please specify your operating duty point to find matching pumps.", "warning")
        return redirect(url_for('selection.pump_selection'))

    if pump_id not in shortlisted_ids:
        flash(f"Access Denied: Pump #{pump_id} is not in your current selection shortlist. You can only view shortlisted pumps.", "warning")
        active_sel = session.get('active_selection', {})
        current_active_id = active_sel.get('pump_id')
        fallback_id = current_active_id if (current_active_id and current_active_id in shortlisted_ids) else shortlisted_ids[0]
        return redirect(url_for('selection.pump_selection_details', pump_id=fallback_id))

    pump = get_visible_pumps_query().filter(Pump.id == pump_id).first()
    if not pump:
        abort(403)

    current_org = get_current_organisation()
    org_styles = current_org.get_graph_styles() if current_org else {}
    
    active_result = None
    default_report_id = 1
    for r in results:
        if r.get('pump_id') == pump_id:
            active_result = r
            default_report_id = r.get('default_report_id', 1)
            break

    from models import ReportConfig
    available_reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()

    # ── Store Selection State into Server-Side Session ──
    # Beginners Note: Save full engineering parameters, active duty point, unit settings,
    # and default report ID into session['active_selection'].
    session['active_selection'] = {
        'pump_id': pump.id,
        'report_id': default_report_id,
        'q_duty': f.get('q_duty'),
        'h_duty': f.get('h_duty'),
        'unit_system': unit_system,
        'unit_q': unit_q,
        'unit_h': unit_h,
        'unit_pow': unit_pow,
        'unit_npsh': unit_npsh,
        'unit_static_head': unit_static_head,
        'unit_rho': unit_rho,
        'unit_d50': unit_d50,
        'disp_q_duty': active_result.get('disp_q_duty') if active_result else f.get('q_duty'),
        'disp_h_duty': active_result.get('disp_h_duty') if active_result else f.get('h_duty'),
        'disp_unit_q': UNITS_FLOW.get(unit_q, {}).get('name', unit_q),
        'disp_unit_h': UNITS_HEAD.get(unit_h, {}).get('name', unit_h),
        'dia': active_result.get('optimal_trim_dia_mm') if active_result else None,
        'rpm': active_result.get('optimal_speed_rpm') if active_result else None,
        'operation_mode': f.get('operation_mode', 'fixed'),
        'show_hq': '1',
        'show_eta': '1',
        'show_pow': '1',
        'show_npsh': '1',
        'show_rated': '1',
        'show_sys': '1',
        'show_duty': '1',
        'hidden_curves': ''
    }
    
    units_tables = {
        'flow':    UNITS_FLOW,
        'head':    UNITS_HEAD,
        'power':   UNITS_POWER,
        'density': UNITS_DENSITY,
        'size':    UNITS_SIZE
    }

    details_template = current_org.get_pump_details_template() if current_org else 'details/default_pump_details.html'

    return render_template('pump_selection_details.html',
                           pump=pump,
                           results=results,
                           active_result=active_result,
                           form_data=f,
                           current_org=current_org,
                           org_styles=org_styles,
                           details_template=details_template,
                           default_report_id=default_report_id,
                           available_reports=available_reports,
                           units_tables=units_tables,
                           unit_system=unit_system,
                           unit_q=unit_q,
                           unit_h=unit_h,
                           unit_npsh=unit_npsh,
                           unit_pow=unit_pow)


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


@selection_bp.route('/papi/motors-by-spec')
def api_motors_by_spec():
    """
    Beginners Note:
    JSON API endpoint returning available standard electric motors from the database
    filtered by frequency (50 or 60 Hz) and pole count (2, 4, 6, 8).
    Used by dynamic frontend dropdowns when the user toggles Frequency or Poles.
    """
    from motor_models import get_available_motors
    freq = request.args.get('freq', 50, type=int)
    poles = request.args.get('poles', 4, type=int)
    motors = get_available_motors(frequency_hz=freq, poles=poles)
    return jsonify([m.to_dict() for m in motors])


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

