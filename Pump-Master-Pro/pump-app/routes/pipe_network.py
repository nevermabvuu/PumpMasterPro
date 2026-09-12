"""
pipe_network.py — Flask Blueprint for the Pipe Network System Designer.

Provides:
  - GET  /pipe-network               -> serves the interactive visual designer page
  - POST /api/pipe-network/calculate  -> accepts a JSON network graph and returns
                                         friction-loss calculations for every pipe
                                         segment in the network.
  - CRUD /api/pipe-network/fittings   -> manage pipe fittings (K-factors)
  - CRUD /api/pipe-network/materials  -> manage pipe materials (roughness)

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

import json
import math
import re
from flask import Blueprint, render_template, request, jsonify, g, session
from models import db, PipeFitting, PipeMaterial, StandardPipe

# -- Blueprint registration --------------------------------------------------
pipe_network_bp = Blueprint('pipe_network', __name__)

# -- Physical constants ------------------------------------------------------
GRAVITY = 9.81           # gravitational acceleration (m/s^2)
KINEMATIC_VISCOSITY = 1.004e-6   # water at 20 C (m^2/s)


# -- Database-backed lookup helpers (cached per-request via Flask g) ----------

def get_fitting_k_map():
    """Return {key: k_factor} dict for all active fittings, cached per request."""
    if not hasattr(g, '_fitting_k'):
        fittings = PipeFitting.query.filter_by(is_active=True).order_by(PipeFitting.sort_order).all()
        g._fitting_k = {f.key: f.k_factor for f in fittings}
    return g._fitting_k


def get_fitting_label_map():
    """Return {key: label} dict for all active fittings, cached per request."""
    if not hasattr(g, '_fitting_labels'):
        fittings = PipeFitting.query.filter_by(is_active=True).order_by(PipeFitting.sort_order).all()
        g._fitting_labels = {f.key: f.label for f in fittings}
    return g._fitting_labels


def get_roughness_map():
    """Return {key: roughness_mm} dict for all active materials, cached per request."""
    if not hasattr(g, '_roughness'):
        materials = PipeMaterial.query.filter_by(is_active=True).order_by(PipeMaterial.sort_order).all()
        g._roughness = {m.key: m.roughness_mm for m in materials}
    return g._roughness


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
    fitting_k = get_fitting_k_map()
    roughness_map = get_roughness_map()

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
    eps_mm = roughness_map.get(material, roughness_map.get('commercial_steel', 0.046))

    # Hydraulic quantities
    A_m2  = math.pi * D_m ** 2 / 4.0    # cross-sectional area
    V_ms  = Q_m3s / A_m2                  # mean velocity
    Re    = V_ms * D_m / KINEMATIC_VISCOSITY  # Reynolds number
    f     = friction_factor(Re, eps_mm, D_m)  # Darcy friction factor

    vel_head  = V_ms ** 2 / (2.0 * GRAVITY)  # velocity head V^2/2g

    # Major (pipe-wall friction) losses
    hf_major  = f * (L_m / D_m) * vel_head

    # Minor (fitting) losses supporting both standard lookup keys and custom K overrides
    K_total = 0.0
    for item in fittings:
        if isinstance(item, dict):
            k_val = item.get('k')
            if k_val is not None:
                try:
                    K_total += float(k_val)
                except (ValueError, TypeError):
                    K_total += float(fitting_k.get(item.get('key'), 0.0))
            else:
                K_total += float(fitting_k.get(item.get('key'), 0.0))
        elif isinstance(item, (int, float)):
            K_total += float(item)
        elif isinstance(item, str):
            K_total += float(fitting_k.get(item, 0.0))

    if seg.get('custom_k') is not None:
        try:
            K_total += float(seg.get('custom_k'))
        except (ValueError, TypeError):
            pass

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
        'standard':        seg.get('standard'),
        'schedule_sdr':    seg.get('schedule_sdr'),
        'nb_mm':           seg.get('nb_mm'),
        'od_mm':           seg.get('od_mm'),
        'id_mm':           seg.get('id_mm', round(D_mm, 1)),
        'pressure_rating': seg.get('pressure_rating'),
    }


# ── Page Route ──────────────────────────────────────────────────────────────

@pipe_network_bp.route('/pipe-network')
def pipe_network():
    """Render the interactive pipe-network visual designer page with DB-injected reference data and active session state."""
    fittings = PipeFitting.query.filter_by(is_active=True).order_by(PipeFitting.sort_order).all()
    materials = PipeMaterial.query.filter_by(is_active=True).order_by(PipeMaterial.sort_order).all()
    standard_pipes = StandardPipe.query.filter_by(is_active=True).order_by(StandardPipe.sort_order).all()

    fittings_json = json.dumps([f.to_dict() for f in fittings])
    materials_json = json.dumps([m.to_dict() for m in materials])
    standard_pipes_json = json.dumps([p.to_dict() for p in standard_pipes])

    active_sel = session.get('active_selection') or {}
    pipe_net_data = active_sel.get('pipe_network')
    pipe_network_json = json.dumps(pipe_net_data) if pipe_net_data else 'null'
    active_selection_json = json.dumps(active_sel)

    return render_template('pipe_network.html',
                           fittings_json=fittings_json,
                           materials_json=materials_json,
                           standard_pipes_json=standard_pipes_json,
                           pipe_network_json=pipe_network_json,
                           active_selection_json=active_selection_json,
                           active_selection=active_sel)


@pipe_network_bp.route('/api/pipe-network/standard-pipes', methods=['GET'])
def get_standard_pipes():
    """Return standard pipes catalog with optional filtering by standard, material, schedule_sdr, nb_mm."""
    q = StandardPipe.query.filter_by(is_active=True)
    std = request.args.get('standard')
    if std and std != 'all':
        q = q.filter(StandardPipe.standard == std)
    mat = request.args.get('material')
    if mat and mat != 'all':
        q = q.filter(StandardPipe.material == mat)
    sch = request.args.get('schedule_sdr')
    if sch and sch != 'all':
        q = q.filter(StandardPipe.schedule_sdr == sch)
    nb = request.args.get('nb_mm')
    if nb and nb != 'all':
        try:
            q = q.filter(StandardPipe.nb_mm == float(nb))
        except (ValueError, TypeError):
            pass
    pipes = q.order_by(StandardPipe.sort_order).all()
    return jsonify({
        'status': 'ok',
        'pipes': [p.to_dict() for p in pipes],
        'total': len(pipes)
    })


@pipe_network_bp.route('/api/pipe-network/save', methods=['POST'])
def save_pipe_network_session():
    """
    Save the current pipe network designer graph, pump settings,
    and calculation results to session['active_selection'].
    """
    data = request.get_json(silent=True)
    if not data and request.data:
        try:
            data = json.loads(request.data.decode('utf-8'))
        except Exception:
            data = {}
    data = data or {}

    active_sel = session.get('active_selection') or {}
    active_sel['pipe_network'] = data

    # Sync pump and duty parameters into active_selection
    nodes = data.get('nodes', [])
    pump_nodes = [n for n in nodes if n.get('type') == 'pump']
    global_flow = data.get('globalFlow')

    if pump_nodes:
        first_pump = pump_nodes[0]
        pump_props = first_pump.get('props', {})
        flow = pump_props.get('flow_m3h') or global_flow
        if flow:
            try:
                active_sel['q_duty'] = float(flow)
                active_sel['disp_q_duty'] = float(flow)
            except (ValueError, TypeError):
                pass
        if pump_props.get('pump_config'):
            active_sel['pump_config'] = pump_props.get('pump_config')
        if pump_props.get('label'):
            active_sel['pump_label'] = pump_props.get('label')
    elif global_flow:
        try:
            active_sel['q_duty'] = float(global_flow)
            active_sel['disp_q_duty'] = float(global_flow)
        except (ValueError, TypeError):
            pass

    calc = data.get('lastCalculation')
    if calc and isinstance(calc, dict):
        summary = calc.get('summary', {})
        total_head = summary.get('total_system_head_m')
        if total_head is not None:
            try:
                active_sel['h_duty'] = round(float(total_head), 3)
                active_sel['disp_h_duty'] = round(float(total_head), 3)
            except (ValueError, TypeError):
                pass

    session['active_selection'] = active_sel
    session.modified = True
    return jsonify({
        'status': 'ok',
        'message': 'Pipe network saved to session active_selection',
        'active_selection': active_sel
    })


@pipe_network_bp.route('/api/pipe-network/session', methods=['GET'])
def get_pipe_network_session():
    """Return the saved pipe network from session['active_selection']."""
    active_sel = session.get('active_selection') or {}
    return jsonify({
        'status': 'ok',
        'pipe_network': active_sel.get('pipe_network'),
        'active_selection': active_sel
    })


# ── Calculation Endpoint ────────────────────────────────────────────────────

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

    calc_summary = {
        'total_hf_major_m':    round(total_major, 3),
        'total_hf_minor_m':    round(total_minor, 3),
        'total_elevation_m':   round(total_elev,  3),
        'total_system_head_m': round(total_head,  3),
        'pipe_count':          len(results),
    }

    # Auto-sync calculation results and duty point to session['active_selection']
    try:
        active_sel = session.get('active_selection') or {}
        pn = active_sel.get('pipe_network') or {}
        pn['lastCalculation'] = {
            'results': results,
            'errors': errors,
            'summary': calc_summary,
        }
        pn['globalFlow'] = global_flow
        active_sel['pipe_network'] = pn
        active_sel['q_duty'] = global_flow
        active_sel['disp_q_duty'] = global_flow
        active_sel['h_duty'] = round(total_head, 3)
        active_sel['disp_h_duty'] = round(total_head, 3)
        session['active_selection'] = active_sel
        session.modified = True
    except Exception:
        pass

    return jsonify({
        'results': results,
        'errors':  errors,
        'summary': calc_summary,
        'constants': {
            'fitting_k_values': get_fitting_k_map(),
            'fitting_labels':   get_fitting_label_map(),
            'pipe_roughness':   get_roughness_map(),
        }
    })


# ══════════════════════════════════════════════════════════════════════════════
# CRUD API — Pipe Fittings
# ══════════════════════════════════════════════════════════════════════════════

@pipe_network_bp.route('/api/pipe-network/fittings', methods=['GET'])
def list_fittings():
    """List all pipe fittings (active and inactive)."""
    fittings = PipeFitting.query.order_by(PipeFitting.sort_order).all()
    return jsonify([f.to_dict() for f in fittings])


@pipe_network_bp.route('/api/pipe-network/fittings', methods=['POST'])
def create_fitting():
    """Create a new pipe fitting."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON body'}), 400

    key = (data.get('key') or '').strip()
    label = (data.get('label') or '').strip()
    k_factor = data.get('K') or data.get('k_factor')

    if not key or not label or k_factor is None:
        return jsonify({'error': 'key, label, and K (k_factor) are required'}), 400

    # Sanitize key: lowercase, underscores, no spaces
    key = re.sub(r'[^a-z0-9_]', '_', key.lower())

    if PipeFitting.query.filter_by(key=key).first():
        return jsonify({'error': f'Fitting with key "{key}" already exists'}), 409

    try:
        k_val = float(k_factor)
    except (ValueError, TypeError):
        return jsonify({'error': 'K factor must be a number'}), 400

    max_order = db.session.query(db.func.max(PipeFitting.sort_order)).scalar() or 0

    fitting = PipeFitting(
        key=key,
        label=label,
        k_factor=k_val,
        category=(data.get('category') or 'general').strip(),
        sort_order=max_order + 1,
        is_active=True,
    )
    db.session.add(fitting)
    db.session.commit()
    return jsonify(fitting.to_dict()), 201


@pipe_network_bp.route('/api/pipe-network/fittings/<int:fitting_id>', methods=['PUT'])
def update_fitting(fitting_id):
    """Update an existing pipe fitting."""
    fitting = PipeFitting.query.get(fitting_id)
    if not fitting:
        return jsonify({'error': 'Fitting not found'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON body'}), 400

    if 'label' in data and data['label']:
        fitting.label = data['label'].strip()
    if 'K' in data or 'k_factor' in data:
        try:
            fitting.k_factor = float(data.get('K') or data.get('k_factor'))
        except (ValueError, TypeError):
            return jsonify({'error': 'K factor must be a number'}), 400
    if 'category' in data:
        fitting.category = (data['category'] or 'general').strip()
    if 'sort_order' in data:
        fitting.sort_order = int(data['sort_order'])
    if 'is_active' in data:
        fitting.is_active = bool(data['is_active'])
    if 'key' in data and data['key']:
        new_key = re.sub(r'[^a-z0-9_]', '_', data['key'].lower().strip())
        existing = PipeFitting.query.filter(PipeFitting.key == new_key, PipeFitting.id != fitting_id).first()
        if existing:
            return jsonify({'error': f'Key "{new_key}" already in use'}), 409
        fitting.key = new_key

    db.session.commit()
    return jsonify(fitting.to_dict())


@pipe_network_bp.route('/api/pipe-network/fittings/<int:fitting_id>', methods=['DELETE'])
def delete_fitting(fitting_id):
    """Delete a pipe fitting (hard delete)."""
    fitting = PipeFitting.query.get(fitting_id)
    if not fitting:
        return jsonify({'error': 'Fitting not found'}), 404

    db.session.delete(fitting)
    db.session.commit()
    return jsonify({'ok': True, 'deleted': fitting_id})


# ══════════════════════════════════════════════════════════════════════════════
# CRUD API — Pipe Materials
# ══════════════════════════════════════════════════════════════════════════════

@pipe_network_bp.route('/api/pipe-network/materials', methods=['GET'])
def list_materials():
    """List all pipe materials (active and inactive)."""
    materials = PipeMaterial.query.order_by(PipeMaterial.sort_order).all()
    return jsonify([m.to_dict() for m in materials])


@pipe_network_bp.route('/api/pipe-network/materials', methods=['POST'])
def create_material():
    """Create a new pipe material."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON body'}), 400

    key = (data.get('key') or '').strip()
    label = (data.get('label') or '').strip()
    roughness = data.get('roughness_mm')

    if not key or not label or roughness is None:
        return jsonify({'error': 'key, label, and roughness_mm are required'}), 400

    key = re.sub(r'[^a-z0-9_]', '_', key.lower())

    if PipeMaterial.query.filter_by(key=key).first():
        return jsonify({'error': f'Material with key "{key}" already exists'}), 409

    try:
        rough_val = float(roughness)
    except (ValueError, TypeError):
        return jsonify({'error': 'roughness_mm must be a number'}), 400

    max_order = db.session.query(db.func.max(PipeMaterial.sort_order)).scalar() or 0

    material = PipeMaterial(
        key=key,
        label=label,
        roughness_mm=rough_val,
        sort_order=max_order + 1,
        is_active=True,
    )
    db.session.add(material)
    db.session.commit()
    return jsonify(material.to_dict()), 201


@pipe_network_bp.route('/api/pipe-network/materials/<int:material_id>', methods=['PUT'])
def update_material(material_id):
    """Update an existing pipe material."""
    material = PipeMaterial.query.get(material_id)
    if not material:
        return jsonify({'error': 'Material not found'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON body'}), 400

    if 'label' in data and data['label']:
        material.label = data['label'].strip()
    if 'roughness_mm' in data:
        try:
            material.roughness_mm = float(data['roughness_mm'])
        except (ValueError, TypeError):
            return jsonify({'error': 'roughness_mm must be a number'}), 400
    if 'sort_order' in data:
        material.sort_order = int(data['sort_order'])
    if 'is_active' in data:
        material.is_active = bool(data['is_active'])
    if 'key' in data and data['key']:
        new_key = re.sub(r'[^a-z0-9_]', '_', data['key'].lower().strip())
        existing = PipeMaterial.query.filter(PipeMaterial.key == new_key, PipeMaterial.id != material_id).first()
        if existing:
            return jsonify({'error': f'Key "{new_key}" already in use'}), 409
        material.key = new_key

    db.session.commit()
    return jsonify(material.to_dict())


@pipe_network_bp.route('/api/pipe-network/materials/<int:material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a pipe material (hard delete)."""
    material = PipeMaterial.query.get(material_id)
    if not material:
        return jsonify({'error': 'Material not found'}), 404

    db.session.delete(material)
    db.session.commit()
    return jsonify({'ok': True, 'deleted': material_id})
