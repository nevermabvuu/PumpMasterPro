"""
calculations.py — Centralized Engineering Calculation API Endpoints.

Protects proprietary hydraulic mathematics, curve fitting, slurry rheology,
and affinity law algorithms by running them securely on the server side
rather than exposing them in client-side JavaScript.
"""

import math
from typing import Dict, Any, List
from flask import Blueprint, request, jsonify
from utils import convert_unit
from services.hydraulic_engine import (
    GRAVITY,
    water_vapor_pressure_kpa,
    particle_settling_velocity_m_s,
    critical_deposition_velocity_m_s,
    fluid_density_kg_m3
)

calculations_bp = Blueprint('calculations', __name__, url_prefix='/api/calc')

WATER_DENSITY_BASE = 1000.0  # kg/m³


def _compute_single_power(q: float, h: float, eta: float, 
                         unit_q: str = 'm3h', unit_h: str = 'm', 
                         unit_pow: str = 'kw', sg: float = 1.0) -> Dict[str, Any]:
    """
    Computes hydraulic power and shaft power.
    
    Formula:
        P_hyd (kW)   = (rho * g * Q * H) / 1000
        P_shaft (kW) = P_hyd / (eta / 100)
    """
    if q is None or h is None or eta is None or eta <= 0 or q < 0 or h < 0:
        return {'power_kw': None, 'power_display': None, 'water_power_kw': None}

    # Convert to base SI units: Q in m³/h -> m³/s, H in m -> m
    q_m3h = convert_unit(q, unit_q, 'm3h', 'flow')
    h_m = convert_unit(h, unit_h, 'm', 'head')

    if q_m3h is None or h_m is None:
        return {'power_kw': None, 'power_display': None, 'water_power_kw': None}

    q_m3s = q_m3h / 3600.0
    rho = WATER_DENSITY_BASE * max(0.1, float(sg))
    g = GRAVITY

    # Hydraulic power (useful fluid power) in kW
    p_hyd_kw = (rho * g * q_m3s * h_m) / 1000.0

    # Shaft brake power (kW)
    eta_frac = eta / 100.0
    p_shaft_kw = p_hyd_kw / eta_frac if eta_frac > 0 else 0.0

    # Convert power back to user display unit
    p_display = convert_unit(p_shaft_kw, 'kw', unit_pow, 'power')

    return {
        'power_kw': round(p_shaft_kw, 3),
        'power_display': round(p_display, 2) if p_display is not None else None,
        'water_power_kw': round(p_hyd_kw, 3),
        'eta_pct': round(eta, 2)
    }


@calculations_bp.route('/power', methods=['POST'])
def calculate_power():
    """
    Endpoint for real-time power calculation on single duty points / table cells.
    """
    data = request.get_json(silent=True) or {}
    try:
        q = float(data.get('flow', 0))
        h = float(data.get('head', 0))
        eta = float(data.get('eta', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid numerical inputs'}), 400

    unit_q = data.get('unit_q', 'm3h')
    unit_h = data.get('unit_h', 'm')
    unit_pow = data.get('unit_pow', 'kw')
    sg = float(data.get('sg', 1.0))

    res = _compute_single_power(q, h, eta, unit_q=unit_q, unit_h=unit_h, unit_pow=unit_pow, sg=sg)
    res['success'] = True
    return jsonify(res)


@calculations_bp.route('/batch-power', methods=['POST'])
def calculate_batch_power():
    """
    Batch power calculation for entire pump performance tables or imported CSVs.
    """
    data = request.get_json(silent=True) or {}
    rows = data.get('rows', [])
    unit_q = data.get('unit_q', 'm3h')
    unit_h = data.get('unit_h', 'm')
    unit_pow = data.get('unit_pow', 'kw')
    sg = float(data.get('sg', 1.0))

    results = []
    for idx, row in enumerate(rows):
        try:
            q = float(row.get('q')) if row.get('q') not in (None, '') else None
            h = float(row.get('h')) if row.get('h') not in (None, '') else None
            eta = float(row.get('eta')) if row.get('eta') not in (None, '') else None
            out = _compute_single_power(q, h, eta, unit_q=unit_q, unit_h=unit_h, unit_pow=unit_pow, sg=sg)
            results.append({
                'index': idx,
                'power_kw': out['power_kw'],
                'power_display': out['power_display'],
                'water_power_kw': out['water_power_kw']
            })
        except Exception:
            results.append({'index': idx, 'power_kw': None, 'power_display': None})

    return jsonify({'success': True, 'results': results})


@calculations_bp.route('/affinity-curve', methods=['POST'])
def generate_affinity_curve():
    """
    Generates affinity-scaled curve points from an existing base curve.
    Protects proprietary scaling corrections and efficiency cut-offs.
    """
    data = request.get_json(silent=True) or {}
    points = data.get('points', [])
    affinity_type = data.get('affinity_type', 'diameter')  # 'diameter' or 'speed'
    
    try:
        if affinity_type == 'diameter':
            base_val = float(data.get('base_dia_mm', 0))
            target_val = float(data.get('target_dia_mm', 0))
            label_suffix = f"Ø {target_val:.0f} mm"
        else:
            base_val = float(data.get('base_speed_rpm', 0))
            target_val = float(data.get('target_speed_rpm', 0))
            label_suffix = f"{target_val:.0f} RPM"
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid base or target values'}), 400

    if base_val <= 0 or target_val <= 0:
        return jsonify({'success': False, 'error': 'Base and target values must be positive'}), 400

    ratio = target_val / base_val
    r = ratio
    r2 = r * r
    r3 = r2 * r

    scaled_points = []
    for pt in points:
        try:
            q1 = float(pt.get('q', 0))
            h1 = float(pt.get('h', 0)) if pt.get('h') is not None else None
            eta1 = float(pt.get('eta', 0)) if pt.get('eta') is not None else None
            p1 = float(pt.get('power', 0)) if pt.get('power') is not None else None
            npsh1 = float(pt.get('npsh', 0)) if pt.get('npsh') is not None else None

            # Affinity equations:
            # Q2 = Q1 * r
            # H2 = H1 * r²
            # P2 = P1 * r³
            # NPSH2 = NPSH1 * r²
            q2 = round(q1 * r, 2)
            h2 = round(h1 * r2, 2) if h1 is not None else None
            p2 = round(p1 * r3, 2) if p1 is not None else None
            npsh2 = round(npsh1 * r2, 2) if npsh1 is not None else None
            
            # Efficiency correction:
            # In pure speed variation, eta is invariant: eta2 = eta1
            # In diameter trimming, efficiency drops slightly for excessive trims:
            # Anderson/Karassik trim correction formula: (1 - eta2)/(1 - eta1) = (D1/D2)^0.17
            eta2 = eta1
            if affinity_type == 'diameter' and eta1 is not None and r < 0.95:
                eta_frac = eta1 / 100.0
                corrected_eta_frac = 1.0 - (1.0 - eta_frac) * math.pow(1.0 / r, 0.17)
                eta2 = round(max(1.0, min(100.0, corrected_eta_frac * 100.0)), 2)

            scaled_points.append({
                'q': q2,
                'h': h2,
                'eta': eta2,
                'power': p2,
                'npsh': npsh2
            })
        except Exception:
            continue

    return jsonify({
        'success': True,
        'affinity_type': affinity_type,
        'ratio': round(ratio, 4),
        'label': f"Affinity ({label_suffix})",
        'points': scaled_points
    })


@calculations_bp.route('/slurry-properties', methods=['POST'])
def calculate_slurry_properties():
    """
    Computes slurry mixture phase balance (Cw -> Cv, Sm),
    Ferguson & Church terminal settling velocity (Vt), and
    Durand critical deposition velocity (Vc).
    """
    data = request.get_json(silent=True) or {}
    try:
        cw_pct = float(data.get('c_weight_pct', 25.0))
        solids_sg = max(1.01, float(data.get('solids_sg', 2.65)))
        liquid_sg = max(0.5, float(data.get('liquid_sg', 1.0)))
        d50_mm = max(0.001, float(data.get('d50_mm', 0.15)))
        pipe_d_mm = float(data.get('pipe_d_mm', 100.0)) if data.get('pipe_d_mm') else None
        temp_c = float(data.get('temperature_c', 20.0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid numerical inputs'}), 400

    # Mixture Specific Gravity (Sm) and Volumetric Concentration (Cv)
    cw_frac = cw_pct / 100.0
    vol_solids = cw_frac / solids_sg
    vol_liquid = (1.0 - cw_frac) / liquid_sg
    total_vol = vol_solids + vol_liquid

    cv_frac = (vol_solids / total_vol) if total_vol > 0 else 0.0
    cv_pct = cv_frac * 100.0
    sm = (1.0 / total_vol) if total_vol > 0 else liquid_sg

    # Terminal settling velocity via Ferguson & Church (2004)
    settling_res = particle_settling_velocity_m_s(
        d50_mm=d50_mm,
        s_solids=solids_sg,
        s_liquid=liquid_sg,
        temperature_c=temp_c
    )

    # Durand critical deposition velocity Vc (if pipe diameter supplied)
    durand_res = None
    if pipe_d_mm and pipe_d_mm > 0:
        durand_res = critical_deposition_velocity_m_s(
            d50_mm=d50_mm,
            diameter_m=pipe_d_mm / 1000.0,
            s_solids=solids_sg,
            s_liquid=liquid_sg,
            cv_volume_fraction=cv_frac
        )

    # Slurry regime assessment
    vt = settling_res.get('settling_velocity_ms', 0)
    if d50_mm < 0.04 and cw_pct > 30:
        regime = 'homogeneous (non-Newtonian / pseudo-homogeneous)'
    elif vt < 0.005:
        regime = 'pseudo-homogeneous (fine suspended solids)'
    elif vt < 0.05:
        regime = 'heterogeneous (standard settling slurry)'
    else:
        regime = 'stratified / sliding bed (coarse fast-settling)'

    return jsonify({
        'success': True,
        'c_weight_pct': round(cw_pct, 1),
        'c_volume_pct': round(cv_pct, 1),
        'slurry_sg': round(sm, 2),
        'density_kg_m3': round(sm * 1000.0, 1),
        'settling_velocity_vt_m_s': settling_res.get('settling_velocity_ms'),
        'stokes_velocity_vt_m_s': settling_res.get('stokes_velocity_ms'),
        'particle_reynolds': settling_res.get('particle_reynolds'),
        'durand_vc_m_s': durand_res.get('critical_velocity_ms') if durand_res else None,
        'durand_fl': durand_res.get('durand_fl') if durand_res else None,
        'regime': regime
    })


@calculations_bp.route('/system-curve', methods=['POST'])
def calculate_system_curve():
    """
    Computes system resistance curve coordinates:
        H_sys = H_static + k * Q²
    where k = (H_duty - H_static) / Q_duty²
    """
    data = request.get_json(silent=True) or {}
    try:
        q_duty = float(data.get('q_duty', 0))
        h_duty = float(data.get('h_duty', 0))
        h_static = float(data.get('h_static', 0.0))
        max_q = float(data.get('max_q', q_duty * 1.35 if q_duty > 0 else 100.0))
        num_points = int(data.get('num_points', 35))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid numerical inputs'}), 400

    if q_duty <= 0:
        return jsonify({'success': False, 'error': 'Duty flow must be greater than zero'}), 400

    # Calculate system dynamic resistance friction factor k
    k = (h_duty - h_static) / (q_duty ** 2) if q_duty > 0 else 0.0
    if k < 0:
        k = 0.0  # Physical head cannot decrease with flow in passive piping

    q_points = []
    h_points = []
    step = max_q / max(1, num_points - 1)
    for i in range(num_points):
        q = i * step
        h = h_static + k * (q ** 2)
        q_points.append(round(q, 2))
        h_points.append(round(h, 2))

    return jsonify({
        'success': True,
        'k_factor': round(k, 6),
        'h_static': round(h_static, 2),
        'q_duty': round(q_duty, 2),
        'h_duty': round(h_duty, 2),
        'q_points': q_points,
        'h_points': h_points
    })


@calculations_bp.route('/vapor-pressure', methods=['POST'])
def calculate_vapor_pressure():
    """
    Computes saturated liquid water vapor pressure Pv (kPa) for NPSH analysis.
    """
    data = request.get_json(silent=True) or {}
    try:
        temp_c = float(data.get('temperature_c', 20.0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid temperature input'}), 400

    pv_kpa = water_vapor_pressure_kpa(temp_c)
    return jsonify({
        'success': True,
        'temperature_c': round(temp_c, 1),
        'vapor_pressure_kpa': round(pv_kpa, 3)
    })
