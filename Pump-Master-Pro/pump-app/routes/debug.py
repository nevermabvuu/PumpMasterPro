"""
routes/debug.py — Session & Object State Debug Inspector

Beginners Note:
This module provides an interactive developer console / debug inspector view (/debug/session).
It displays all session variables, active selection states, pump hydraulics, polynomial coefficients,
report configuration options, active organisation branding, and evaluated curve summaries.
"""

import json
from datetime import datetime
from flask import Blueprint, render_template, session, jsonify, request, redirect, url_for, flash
from models import db, Pump, ReportConfig, Organisation
from utils import get_current_organisation

debug_bp = Blueprint('debug', __name__)


def model_to_dict(obj):
    """
    Beginners Note: Utility function to convert any SQLAlchemy model instance into a clean
    JSON-serializable Python dictionary. Safely serializes columns and custom helper methods.
    """
    if obj is None:
        return None

    data = {}
    # 1. Serialize all standard database table columns
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, (datetime,)):
            val = val.isoformat()
        data[col.name] = val

    # 2. Append parsed JSON fields and helper properties if available
    if isinstance(obj, Pump):
        if hasattr(obj, 'get_graph_options'):
            data['_parsed_graph_options'] = obj.get_graph_options()
        if hasattr(obj, 'get_custom_label_pos'):
            data['_parsed_custom_label_pos'] = obj.get_custom_label_pos()
        if hasattr(obj, 'get_extra_curves'):
            data['_parsed_extra_curves'] = obj.get_extra_curves()
        if hasattr(obj, 'has_npsh_poly'):
            data['_has_npsh_poly'] = obj.has_npsh_poly()
    elif isinstance(obj, Organisation):
        if hasattr(obj, 'get_allowed_org_ids'):
            data['_parsed_allowed_org_ids'] = obj.get_allowed_org_ids()
        if hasattr(obj, 'get_graph_styles'):
            data['_parsed_graph_styles'] = obj.get_graph_styles()

    return data


@debug_bp.route('/debug/session')
@debug_bp.route('/session-debug')
@debug_bp.route('/reports/debug')
def session_debug_view():
    """
    Beginners Note: Main debug inspector view.
    Aggregates:
      1. All raw session keys & values
      2. Active pump object details & polynomial coefficients
      3. Active report configuration options
      4. Active organisation data
      5. Evaluated curve mathematical summaries (BEP, Q max, legend badges)
    """
    # 1. Extract all session keys safely
    session_data = {}
    for k in list(session.keys()):
        try:
            val = session[k]
            # Test JSON serializability
            json.dumps(val)
            session_data[k] = val
        except Exception:
            session_data[k] = str(session[k])

    active_selection = session.get('active_selection', {})

    # 2. Load active Pump if pump_id is in selection
    pump_id = active_selection.get('pump_id')
    pump = Pump.query.get(pump_id) if pump_id else None
    pump_dict = model_to_dict(pump)

    # 3. Load active ReportConfig if report_id is in selection
    report_id = active_selection.get('report_id')
    report = ReportConfig.query.get(report_id) if report_id else None
    report_dict = model_to_dict(report)

    # 4. Load active Organisation
    current_org = get_current_organisation()
    org_dict = model_to_dict(current_org)

    # 5. Evaluate curve math summary if pump & report exist
    evaluated_curves_summary = None
    if pump and report:
        try:
            from routes.reports import _build_report_curve_context
            curves_ctx = _build_report_curve_context(pump, report, params_override=active_selection)
            evaluated_curves_summary = {
                'q_max': curves_ctx.get('q_max'),
                'has_npsh': curves_ctx.get('has_npsh'),
                'active_graph_count': curves_ctx.get('active_graph_count'),
                'bep_info': curves_ctx.get('bep_info'),
                'duty_point': curves_ctx.get('duty_point'),
                'rated_dia': curves_ctx.get('rated_dia'),
                'rated_rpm': curves_ctx.get('rated_rpm'),
                'rep_unit_q': curves_ctx.get('rep_unit_q'),
                'rep_unit_h': curves_ctx.get('rep_unit_h'),
                'is_proposal': curves_ctx.get('is_proposal'),
                'proposal_legend_items': curves_ctx.get('proposal_legend_items', [])
            }
        except Exception as e:
            evaluated_curves_summary = {'error': str(e)}

    # 6. Assemble complete debug bundle
    debug_bundle = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'active_selection': active_selection,
        'session_raw': session_data,
        'active_pump': pump_dict,
        'active_report': report_dict,
        'active_organisation': org_dict,
        'evaluated_curves_summary': evaluated_curves_summary,
        'request_environment': {
            'client_ip': request.remote_addr,
            'user_agent': request.user_agent.string if request.user_agent else '',
            'method': request.method,
            'is_secure': request.is_secure,
            'cookies_count': len(request.cookies)
        }
    }

    formatted_json = json.dumps(debug_bundle, indent=2, ensure_ascii=False)

    return render_template(
        'debug_session.html',
        bundle=debug_bundle,
        formatted_json=formatted_json,
        active_selection=active_selection,
        pump=pump,
        report=report,
        current_org=current_org,
        evaluated_curves=evaluated_curves_summary
    )


@debug_bp.route('/debug/api/session-json')
def api_session_json():
    """
    Beginners Note: Returns the aggregated debug state as raw JSON for API consumption or test scripts.
    """
    session_data = {k: session[k] for k in list(session.keys())}
    active_selection = session.get('active_selection', {})

    pump_id = active_selection.get('pump_id')
    pump = Pump.query.get(pump_id) if pump_id else None

    report_id = active_selection.get('report_id')
    report = ReportConfig.query.get(report_id) if report_id else None

    current_org = get_current_organisation()

    data = {
        'timestamp': datetime.now().isoformat(),
        'session': session_data,
        'active_selection': active_selection,
        'pump': model_to_dict(pump),
        'report': model_to_dict(report),
        'organisation': model_to_dict(current_org)
    }
    return jsonify(data)


@debug_bp.route('/debug/clear-session', methods=['POST'])
def clear_session():
    """
    Beginners Note: Clears all variables in the active user session.
    Useful for testing fresh session states or testing uninitialized visitors.
    """
    session.clear()
    flash("Session data cleared successfully.", "info")
    return redirect(url_for('debug.session_debug_view'))


@debug_bp.route('/debug/seed-sample-session', methods=['POST'])
def seed_sample_session():
    """
    Beginners Note: Populates a realistic sample pump selection session (Pump 1, Proposal report, Q=40, H=28).
    Useful when debugging without navigating through the search form.
    """
    first_pump = Pump.query.first()
    first_report = ReportConfig.query.first()

    p_id = first_pump.id if first_pump else 1
    r_id = first_report.id if first_report else 1

    session['active_selection'] = {
        'pump_id': p_id,
        'report_id': r_id,
        'q_duty': 40.0,
        'h_duty': 28.0,
        'dia': 293.3,
        'rpm': 1289.0,
        'operation_mode': 'vsd',
        'show_hq': '1',
        'show_eta': '1',
        'show_pow': '1',
        'show_npsh': '1',
        'show_rated': '1',
        'show_sys': '1',
        'show_duty': '1',
        'hidden_curves': ''
    }
    session['selection_form_data'] = {
        'q_duty': 40.0,
        'h_duty': 28.0,
        'operation_mode': 'vsd'
    }
    session.modified = True
    flash(f"Sample debug session seeded with Pump #{p_id} and Report #{r_id}.", "success")
    return redirect(url_for('debug.session_debug_view'))
