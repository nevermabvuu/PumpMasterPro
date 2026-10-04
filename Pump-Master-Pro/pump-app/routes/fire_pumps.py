"""
routes/fire_pumps.py — Fire Protection Pump Sizing & Selection Blueprint.

Beginners & Engineering Note:
    Fire pump systems are critical life-safety and asset-protection installations.
    Unlike standard water supply or process pumps that operate continuously at Best
    Efficiency Point (BEP), fire pumps operate intermittently under extreme demand
    and must satisfy stringent international fire safety codes:

    1. NFPA 20 (National Fire Protection Association - Stationary Fire Pumps):
       - Requires pumps to deliver at least 100% rated pressure at 100% rated flow.
       - Maximum shutoff (churn) head must NOT exceed 140% of rated head.
       - Overload capacity: at 150% rated flow, pump head must NOT drop below 65% of rated head.
       - Driver (Electric or Diesel) must be sized non-overloading across the entire curve.

    2. NFPA 13 (Automatic Sprinkler Systems):
       - Density / Area method determines required sprinkler flow demand based on hazard classification
         (Light Hazard, Ordinary Hazard Groups 1 & 2, Extra Hazard Groups 1 & 2, High-Bay Storage/ESFR).
       - Hose stream allowance (100 to 500 GPM) is added to sprinkler demand.

    3. NFPA 14 (Standpipe and Hose Systems):
       - Class I (2.5" / 65mm firefighter connections): 500 GPM for 1st riser + 250 GPM per additional riser.
       - Minimum residual pressure of 100 PSI (6.9 bar / 70.3 m) at the hydraulically most remote outlet.

    4. EN 12845 (European Standard / LPC Rules):
       - Hazard categories: Light Hazard (LH), Ordinary Hazard (OH1-OH4), High Hazard (HHP/HHS).
       - Prescribed flow and pressure design points at the most disadvantaged sprinkler group.

    5. AS 2941 & AS 2419.1 (Australian Standards):
       - Standard pumpsets for sprinkler (AS 2118) and fire hydrant systems (10 to 30+ L/s @ 700 kPa).

    6. Auxiliary Fire Protection Sizing:
       - Jockey Pump (Pressure Maintenance Pump): Sized to maintain system pressure and prevent main pump starts on minor leaks.
       - Fire Water Storage Tank: Duration (30 to 120+ min) and usable volume ($V = Q \times t$).
       - NFPA 20 Table 4.27 Pipe Sizing: Suction, discharge, bypass, and test header sizing.

Routes:
    GET  /fire-pumps                — Main Fire Protection Pump Sizing & Selection page
    GET  /fire-pump-selection       — Canonical alias redirect
    POST /fire-pumps/api/calculate  — AJAX calculation & NFPA 20 compliance evaluation API
    POST /fire-pumps/api/select-pump — Selects a pump and syncs duty point into session
    GET  /fire-pumps/api/standards-data — JSON catalog of hazard presets
"""

from __future__ import annotations
import os
import sys
import json
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from models import db, Pump, Organisation, Project
from utils import (
    get_visible_pumps_query, get_current_organisation,
    UNITS_FLOW, UNITS_HEAD, UNITS_POWER, convert_unit
)

UNITS_PRESSURE = {
    'bar': UNITS_HEAD['bar'],
    'psi': UNITS_HEAD['psi'],
    'kpa': UNITS_HEAD['kpa'],
}
from services.fire_protection import (
    calculate_fire_system_demand,
    evaluate_pump_nfpa20_compliance,
    get_nfpa20_pipe_sizes,
    NFPA_13_HAZARDS,
    NFPA_14_STANDPIPE,
    EN_12845_HAZARDS,
    AS_2941_CRITERIA,
    NFPA_20_PIPE_SCHEDULE,
    GPM_TO_M3H,
    M3H_TO_GPM,
    PSI_TO_M,
    M_TO_PSI,
    BAR_TO_M,
    M_TO_BAR
)

def _safe_float(val, default=None):
    """
    Safely converts a scalar value or string into a float, returning default if None or invalid.
    """
    if val is None or str(val).strip() == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

fire_pumps_bp = Blueprint('fire_pumps', __name__)


@fire_pumps_bp.route('/fire-pumps', methods=['GET'])
def index():
    """
    Consolidated Module Access:
    Fire protection pump sizing & selection is accessed directly via Pump Selection.
    Redirects canonical requests to /pump-selection with filter_pump_type='fire pump'.
    """
    if request.args.get('standalone') != '1':
        return redirect(url_for('pump_selection', filter_pump_type='fire pump'))

    current_org = get_current_organisation()

    # Load initial or session defaults
    s_form = session.get('selection_form_data') or {}
    unit_system = session.get('unit_system', 'metric')

    # Default calculation for initial display
    default_calc = calculate_fire_system_demand(
        standard='nfpa13',
        hazard_class='ordinary_hazard_1',
        static_elevation_m=15.0,
        friction_loss_m=5.0,
        unit_system=unit_system
    )

    # Initial query for fire protection pumps
    all_pumps_q = get_visible_pumps_query()
    all_pumps = all_pumps_q.all()

    # Separate pumps explicitly flagged for fire protection, plus general clean water centrifugal pumps
    fire_pumps = []
    other_candidates = []

    target_flow = default_calc['flow_m3h']
    target_head = default_calc['head_m']

    for p in all_pumps:
        pump_mods = [m.strip().lower() for m in (p.app_modules or '').split(',') if m.strip()]
        full_meta = ((p.app_modules or '') + ' ' + (p.application or '') + ' ' + (p.pump_type or '') + ' ' + (p.name or '')).lower()
        is_slurry_or_dirty = any(t in full_meta for t in ['slurry', 'sump', 'sewage', 'sludge', 'dredge', 'froth'])

        if pump_mods:
            # If specific modules are checked in pump-data, it MUST include 'fire'
            if 'fire' not in pump_mods:
                continue
            is_dedicated = True
        else:
            # If no module is checked, it is available for ALL modules (unless explicitly slurry/sump)
            if is_slurry_or_dirty:
                continue
            is_dedicated = False

        eval_res = evaluate_pump_nfpa20_compliance(p, target_flow, target_head)
        item = {
            'pump': p,
            'eval': eval_res,
            'is_dedicated_fire': is_dedicated
        }
        if is_dedicated:
            fire_pumps.append(item)
        elif eval_res['pass_rated']:
            other_candidates.append(item)

    # Sort: dedicated fire pumps first, then by compliance score descending
    fire_pumps.sort(key=lambda x: (x['eval']['is_compliant'], x['eval']['score']), reverse=True)
    other_candidates.sort(key=lambda x: (x['eval']['is_compliant'], x['eval']['score']), reverse=True)
    initial_pumps = fire_pumps + other_candidates[:8]

    # Available Projects for "Save to Project" modal
    projects = []
    if current_org:
        projects = Project.query.filter_by(organisation_id=current_org.id).order_by(Project.created_at.desc()).all()

    return render_template(
        'fire_pump_selection.html',
        calc=default_calc,
        initial_pumps=initial_pumps,
        nfpa13_hazards=NFPA_13_HAZARDS,
        nfpa14_standpipe=NFPA_14_STANDPIPE,
        en12845_hazards=EN_12845_HAZARDS,
        as2941_criteria=AS_2941_CRITERIA,
        units_flow=UNITS_FLOW,
        units_head=UNITS_HEAD,
        units_pressure=UNITS_PRESSURE,
        unit_system=unit_system,
        current_org=current_org,
        projects=projects
    )


@fire_pumps_bp.route('/fire-pump-selection', methods=['GET'])
def fire_pump_selection_redirect():
    """Canonical alias redirect to pump_selection."""
    return redirect(url_for('pump_selection', filter_pump_type='fire pump'))


@fire_pumps_bp.route('/fire-pumps/api/standards-data', methods=['GET'])
def api_standards_data():
    """
    Returns full dictionary of standards profiles and hazard presets
    for instant client-side dynamic switching without page reloads.
    """
    return jsonify({
        'nfpa13': NFPA_13_HAZARDS,
        'nfpa14': NFPA_14_STANDPIPE,
        'en12845': EN_12845_HAZARDS,
        'as2941': AS_2941_CRITERIA,
        'pipe_schedule': NFPA_20_PIPE_SCHEDULE
    })


@fire_pumps_bp.route('/fire-pumps/api/calculate', methods=['POST'])
def api_calculate():
    """
    AJAX endpoint to recalculate fire protection system demand and evaluate
    all candidate pumps in the catalogue against NFPA 20 characteristic curve criteria.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    standard = data.get('standard', 'nfpa13')
    hazard_class = data.get('hazard_class', 'ordinary_hazard_1')
    unit_system = data.get('unit_system', 'metric')

    # Extract numeric engineering parameters
    area_user = _safe_float(data.get('area'))
    density_user = _safe_float(data.get('density'))
    hose_stream_user = _safe_float(data.get('hose_stream'))
    risers_count = int(data.get('risers_count', 1) or 1)
    sprinklered = bool(data.get('sprinklered', True))

    static_elevation_m = _safe_float(data.get('static_elevation_m'), 0.0) or 0.0
    friction_loss_m = _safe_float(data.get('friction_loss_m'), 0.0) or 0.0
    residual_pressure_bar = _safe_float(data.get('residual_pressure_bar'))

    custom_flow_m3h = _safe_float(data.get('custom_flow_m3h'))
    custom_head_m = _safe_float(data.get('custom_head_m'))

    # If imperial units were provided on custom inputs, convert to metric internally
    if unit_system == 'imperial':
        if custom_flow_m3h is not None:
            custom_flow_m3h = custom_flow_m3h * GPM_TO_M3H
        if custom_head_m is not None:
            # If user entered PSI
            custom_head_m = custom_head_m * PSI_TO_M

    # 1. Run Complete Hydraulic Demand & Auxiliary Sizing Engine
    calc = calculate_fire_system_demand(
        standard=standard,
        hazard_class=hazard_class,
        area_user=area_user,
        density_user=density_user,
        hose_stream_user=hose_stream_user,
        risers_count=risers_count,
        sprinklered=sprinklered,
        static_elevation_m=static_elevation_m,
        friction_loss_m=friction_loss_m,
        residual_pressure_bar=residual_pressure_bar,
        custom_flow_m3h=custom_flow_m3h,
        custom_head_m=custom_head_m,
        unit_system=unit_system
    )

    q_duty_m3h = calc['flow_m3h']
    h_duty_m = calc['head_m']

    # 2. Query Catalogue Pumps & Evaluate NFPA 20 Compliance
    all_pumps = get_visible_pumps_query().all()

    dedicated_only = bool(data.get('dedicated_only') in (True, 'true', '1', 1))

    candidates = []
    for p in all_pumps:
        pump_mods = [m.strip().lower() for m in (p.app_modules or '').split(',') if m.strip()]
        full_meta = ((p.app_modules or '') + ' ' + (p.application or '') + ' ' + (p.pump_type or '') + ' ' + (p.name or '')).lower()
        is_slurry_or_dirty = any(t in full_meta for t in ['slurry', 'sump', 'sewage', 'sludge', 'dredge', 'froth'])

        if pump_mods:
            # If specific modules are checked in pump-data, it MUST include 'fire'
            if 'fire' not in pump_mods:
                continue
            is_dedicated = True
        else:
            # If no module is checked, it is available for ALL modules (unless explicitly slurry/sump)
            if is_slurry_or_dirty:
                continue
            is_dedicated = False

        # If user selected Dedicated Fire Pumps Only, filter out general water pumps
        if dedicated_only and not is_dedicated:
            continue

        eval_res = evaluate_pump_nfpa20_compliance(p, q_duty_m3h, h_duty_m)

        # Include if pump passes rated head or is a dedicated fire pump
        if eval_res['pass_rated'] or is_dedicated:
            candidates.append({
                'pump_id': p.id,
                'name': p.name,
                'manufacturer': p.manufacturer or 'Generic',
                'model_number': p.model_number or p.size or '',
                'pump_type': p.pump_type or 'centrifugal',
                'speed_rpm': p.speed_rpm,
                'impeller_dia_mm': p.impeller_dia_mm,
                'is_dedicated_fire': is_dedicated,
                'app_modules': p.app_modules or '',
                'suction_size': p.suction_size or '',
                'discharge_size': p.discharge_size or '',
                'eval': eval_res,
            })

    # Sort candidates:
    # 1. Dedicated fire pumps first
    # 2. Fully NFPA 20 Compliant next
    # 3. Highest compliance score
    candidates.sort(
        key=lambda c: (
            c['is_dedicated_fire'],
            c['eval']['is_compliant'],
            c['eval']['score']
        ),
        reverse=True
    )

    return jsonify({
        'success': True,
        'demand': calc,
        'candidates_count': len(candidates),
        'candidates': candidates[:15]  # Top 15 matching candidates
    })


@fire_pumps_bp.route('/fire-pumps/api/select-pump', methods=['POST'])
def api_select_pump():
    """
    Selects a candidate fire pump and synchronizes its duty point,
    fire protection standard, and NFPA 20 metrics into active session
    so the user can view curves, export reports, or save to project.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    pump_id = data.get('pump_id')
    if not pump_id:
        return jsonify({'error': 'No pump ID provided.'}), 400

    pump = Pump.query.get(pump_id)
    if not pump:
        return jsonify({'error': 'Pump not found.'}), 404

    q_duty_m3h = _safe_float(data.get('flow_m3h'), 100.0) or 100.0
    h_duty_m = _safe_float(data.get('head_m'), 70.0) or 70.0
    standard = data.get('standard', 'nfpa13')
    hazard_class = data.get('hazard_class', 'ordinary_hazard_1')

    # Evaluate compliance
    compliance = evaluate_pump_nfpa20_compliance(pump, q_duty_m3h, h_duty_m)

    # Synchronize into Flask session['active_selection'] and session['selection_form_data']
    active_sel = {
        'pump_id': pump.id,
        'pump_name': pump.name,
        'model_number': pump.model_number,
        'manufacturer': pump.manufacturer,
        'q_duty': q_duty_m3h,
        'h_duty': h_duty_m,
        'unit_q': 'm3h',
        'unit_h': 'm',
        'liquid': 'water',
        'sg_l': 1.0,
        'temperature_c': 20.0,
        'is_fire_pump': True,
        'fire_standard': standard,
        'fire_hazard_class': hazard_class,
        'pump_arrangement': 'single',
        'pumps_operating': 1,
        'pumps_standby': 0,
        'nfpa20_compliance': compliance,
    }
    session['active_selection'] = active_sel

    s_form = session.get('selection_form_data') or {}
    s_form.update({
        'q_duty': str(q_duty_m3h),
        'h_duty': str(h_duty_m),
        'unit_q': 'm3h',
        'unit_h': 'm',
        'liquid': 'water',
        'pump_arrangement': 'single',
        'pumps_operating': '1',
        'pumps_standby': '0',
    })
    session['selection_form_data'] = s_form
    session.modified = True

    return jsonify({
        'success': True,
        'message': f'Fire Pump {pump.name} successfully selected!',
        'pump_id': pump.id,
        'redirect_url': url_for('selection.pump_selection_details', pump_id=pump.id)
    })
