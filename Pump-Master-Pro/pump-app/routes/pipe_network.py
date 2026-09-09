"""
pipe_network.py — Flask Blueprint for the Pipe Network System Designer.

Provides two endpoints:
  - GET  /pipe-network           -> serves the interactive visual designer page
  - POST /api/pipe-network/calc  -> accepts a JSON network graph and returns
                                   friction-loss calculations for every pipe
                                   segment in the network.

Friction Loss Models Used
--------------------------
  Major losses  (pipe friction):
      Darcy-Weisbach:  hf = f . (L/D) . V^2 / (2g)
      Friction factor: Swamee-Jain explicit approximation to Colebrook-White
                       f = 0.25 / [log10(e/3.7D + 5.74/Re^0.9)]^2

  Minor losses  (fittings, valves, transitions):
      K-factor method: hm = K . V^2 / (2g)

  Static head   (elevation difference between start and end nodes):
      hstatic = Dz  (m)

  Total system head:
      H = hf_major + hf_minor + hstatic
"""

import math
from flask import Blueprint, render_template, request, jsonify

# -- Blueprint registration --------------------------------------------------
pipe_network_bp = Blueprint('pipe_network', __name__)

# -- Physical constants ------------------------------------------------------
GRAVITY = 9.81           # gravitational acceleration (m/s^2)
KINEMATIC_VISCOSITY = 1.004e-6   # water at 20 C (m^2/s)

# -- Pipe material roughness values (mm) -------------------------------------
# Absolute roughness (e) in millimetres for common pipe materials.
PIPE_ROUGHNESS_MM = {
    'smooth':           0.0015,
    'commercial_steel': 0.046,
    'galvanised_steel': 0.150,
    'cast_iron':        0.260,
    'concrete':         1.000,
    'pvc':              0.0015,
    'hdpe':             0.007,
    'stainless_steel':  0.015,
}

# -- K-factors for common pipe fittings --------------------------------------
# Source: Crane TP-410 / Idelchik handbook
# hm = K * V^2 / (2g)
FITTING_K = {
    'elbow_90_standard':    0.90,
    'elbow_90_long_radius': 0.60,
    'elbow_45':             0.40,
    'gate_valve_open':      0.20,
    'gate_valve_half':      5.60,
    'globe_valve_open':     10.0,
    'check_valve_swing':    2.50,
    'check_valve_ball':     4.50,
    'ball_valve_open':      0.05,
    'butterfly_valve_open': 0.30,
    'tee_run_through':      0.40,
    'tee_branch_flow':      1.80,
    'entry_sharp':          0.50,
    'entry_rounded':        0.20,
    'exit_abrupt':          1.00,
    'reducer_gradual':      0.10,
    'reducer_sudden':       0.50,
    'expander_gradual':     0.30,
}

FITTING_LABELS = {
    'elbow_90_standard':    '90 Elbow (Standard)',
    'elbow_90_long_radius': '90 Elbow (Long Radius)',
    'elbow_45':             '45 Elbow',
    'gate_valve_open':      'Gate Valve (Open)',
    'gate_valve_half':      'Gate Valve (50% Open)',
    'globe_valve_open':     'Globe Valve (Open)',
    'check_valve_swing':    'Check Valve (Swing)',
    'check_valve_ball':     'Check Valve (Ball)',
    'ball_valve_open':      'Ball Valve (Open)',
    'butterfly_valve_open': 'Butterfly Valve (Open)',
    'tee_run_through':      'Tee (Run Through)',
    'tee_branch_flow':      'Tee (Branch Flow)',
    'entry_sharp':          'Pipe Entry (Sharp)',
    'entry_rounded':        'Pipe Entry (Rounded)',
    'exit_abrupt':          'Pipe Exit (Abrupt)',
    'reducer_gradual':      'Reducer (Gradual)',
    'reducer_sudden':       'Reducer (Sudden)',
    'expander_gradual':     'Expander (Gradual)',
}


def friction_factor(Re, epsilon_mm, diameter_m):
    """
    Return the Darcy-Weisbach friction factor.
    
    Laminar  (Re < 2300):        f = 64 / Re
    Turbulent (Re >= 4000):      Swamee-Jain approximation
    Transitional (2300-4000):    linear blend
    """
    if Re <= 0:
        return 0.02  # fallback for zero-flow edge case

    if Re < 2300:
        return 64.0 / Re  # Hagen-Poiseuille for laminar flow

    # Swamee-Jain for turbulent flow
    rel_roughness = max(1e-6, min((epsilon_mm / 1000.0) / diameter_m, 0.05))
    f_turb = 0.25 / (math.log10(rel_roughness / 3.7 + 5.74 / (Re ** 0.9))) ** 2

    if Re < 4000:
        # Blend laminar and turbulent in the transitional zone
        f_lam = 64.0 / Re
        blend = (Re - 2300) / (4000 - 2300)
        return f_lam * (1 - blend) + f_turb * blend

    return f_turb


def calculate_segment(seg, global_flow_m3h):
    """
    Calculate all hydraulic quantities for one pipe segment.

    Required keys in seg dict:
        id, diameter_mm, length_m, material, elev_change_m, fittings
    Optional:
        flow_m3h  (overrides global_flow_m3h for this segment)
    """
    seg_id   = seg.get('id', 'pipe')
    D_mm     = float(seg.get('diameter_mm', 100.0))
    L_m      = float(seg.get('length_m', 10.0))
    material = seg.get('material', 'commercial_steel')
    flow_m3h = float(seg.get('flow_m3h', global_flow_m3h))
    dz_m     = float(seg.get('elev_change_m', 0.0))
    fittings = seg.get('fittings', [])

    # Unit conversions
    D_m   = D_mm / 1000.0
    Q_m3s = flow_m3h / 3600.0
    eps_mm = PIPE_ROUGHNESS_MM.get(material, PIPE_ROUGHNESS_MM['commercial_steel'])

    # Hydraulic quantities
    A_m2  = math.pi * D_m ** 2 / 4.0    # cross-sectional area
    V_ms  = Q_m3s / A_m2                  # mean velocity
    Re    = V_ms * D_m / KINEMATIC_VISCOSITY  # Reynolds number
    f     = friction_factor(Re, eps_mm, D_m)  # Darcy friction factor

    vel_head  = V_ms ** 2 / (2.0 * GRAVITY)  # velocity head V^2/2g

    # Major (pipe-wall friction) losses
    hf_major  = f * (L_m / D_m) * vel_head

    # Minor (fitting) losses
    K_total   = sum(FITTING_K.get(k, 0.0) for k in fittings)
    hf_minor  = K_total * vel_head

    # Elevation head (positive = uphill = adds to required pump head)
    hf_elev   = dz_m

    # Totals
    hf_friction = hf_major + hf_minor
    h_total     = hf_friction + hf_elev

    # Flow regime label
    if Re < 2300:
        regime = 'Laminar'
    elif Re < 4000:
        regime = 'Transitional'
    else:
        regime = 'Turbulent'

    # Velocity advisory (recommended range for water: 0.5 - 3.0 m/s)
    if V_ms < 0.3:
        vel_status = 'Too slow'
    elif V_ms > 4.0:
        vel_status = 'Too fast'
    elif V_ms > 3.0:
        vel_status = 'High - consider larger pipe'
    else:
        vel_status = 'OK'

    return {
        'id':              seg_id,
        'label':           seg.get('label', seg_id),
        'diameter_mm':     round(D_mm, 1),
        'length_m':        round(L_m, 2),
        'material':        material,
        'flow_m3h':        round(flow_m3h, 3),
        'velocity_ms':     round(V_ms, 3),
        'reynolds':        int(Re),
        'regime':          regime,
        'velocity_status': vel_status,
        'friction_factor': round(f, 6),
        'velocity_head_m': round(vel_head, 5),
        'hf_major_m':      round(hf_major, 4),
        'hf_minor_m':      round(hf_minor, 4),
        'hf_friction_m':   round(hf_friction, 4),
        'hf_elevation_m':  round(hf_elev, 4),
        'h_total_m':       round(h_total, 4),
        'fittings':        fittings,
        'K_total':         round(K_total, 3),
    }


@pipe_network_bp.route('/pipe-network')
def pipe_network():
    """Render the interactive pipe-network visual designer page."""
    return render_template('pipe_network.html')


@pipe_network_bp.route('/api/pipe-network/calculate', methods=['POST'])
def calculate_network():
    """
    Calculate friction losses for every pipe segment in the submitted network.

    Request JSON:
    {
        "flow_m3h": 10.0,
        "pipes": [ { pipe segment dicts } ]
    }

    Response JSON:
    {
        "results": [ { per-segment results } ],
        "errors":  [ { per-segment errors } ],
        "summary": { totals },
        "constants": { reference tables }
    }
    """
    data = request.get_json(silent=True)
    if not data or 'pipes' not in data:
        return jsonify({'error': 'Missing required field: pipes'}), 400

    global_flow = float(data.get('flow_m3h', 10.0))
    pipe_list   = data['pipes']

    if not isinstance(pipe_list, list) or len(pipe_list) == 0:
        return jsonify({'error': 'pipes must be a non-empty list'}), 400

    results     = []
    errors      = []
    total_major = 0.0
    total_minor = 0.0
    total_elev  = 0.0

    for seg in pipe_list:
        try:
            result = calculate_segment(seg, global_flow)
            results.append(result)
            total_major += result['hf_major_m']
            total_minor += result['hf_minor_m']
            total_elev  += result['hf_elevation_m']
        except (ValueError, ZeroDivisionError, KeyError) as exc:
            errors.append({'id': seg.get('id', '?'), 'error': str(exc)})

    total_head = total_major + total_minor + total_elev

    return jsonify({
        'results': results,
        'errors':  errors,
        'summary': {
            'total_hf_major_m':    round(total_major, 3),
            'total_hf_minor_m':    round(total_minor, 3),
            'total_elevation_m':   round(total_elev,  3),
            'total_system_head_m': round(total_head,  3),
            'pipe_count':          len(results),
        },
        'constants': {
            'fitting_k_values': FITTING_K,
            'fitting_labels':   FITTING_LABELS,
            'pipe_roughness':   PIPE_ROUGHNESS_MM,
        }
    })
