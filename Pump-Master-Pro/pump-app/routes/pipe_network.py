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
from services.hydraulic_engine import (
    Fitting, Node, PipeEdge, NetworkGraph,
    calculate_consolidated_pipe, DEFAULT_HAZEN_WILLIAMS_C,
    solve_network, NetworkSolverResult, NodeHydraulicResult,
    fluid_kinematic_viscosity_m2s, fluid_density_kg_m3,
    water_vapor_pressure_kpa, altitude_to_barometric_pressure_kpa,
    colebrook_white_exact,
    GRAVITY
)

# -- Blueprint registration --------------------------------------------------
pipe_network_bp = Blueprint('pipe_network', __name__)

# -- Physical constants ------------------------------------------------------
# Gravitational constant g = 9.80665 m/s^2
G_ACCEL = GRAVITY        # Standard gravitational acceleration (m/s^2)
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
    Return the Darcy-Weisbach friction factor f using the exact Colebrook-White equation.

    Numerical & Hydraulic Details:
    -------------------------------
    - Laminar regime (Re < 2300):
        Exact Hagen-Poiseuille law: f = 64 / Re
    - Critical / Transitional regime (2300 <= Re < 4000):
        Smooth linear blending between laminar and turbulent values.
    - Fully turbulent regime (Re >= 4000):
        Exact implicit Colebrook-White equation solved via Newton-Raphson iteration:
        1 / sqrt(f) = -2 * log10( (epsilon / 3.7D) + (2.51 / (Re * sqrt(f))) )
        Eliminates the ~1-3% error inherent to explicit empirical approximations like Swamee-Jain.
    """
    return colebrook_white_exact(Re, epsilon_mm, diameter_m)


def calculate_segment(seg, global_flow_m3h, friction_method='darcy_weisbach',
                      temperature_c=20.0, specific_gravity=1.0,
                      liquid='water', viscosity_cSt=1.0,
                      is_slurry=False, slurry_d50_mm=0.15,
                      slurry_solids_sg=2.65, slurry_c_weight=25.0,
                      slurry_c_volume=None):
    """
    Calculate all hydraulic quantities for one pipe segment using the consolidated
    hydraulic engine pipeline. Accumulates child fittings without splitting the pipe.
    Incorporates temperature-dependent or viscous kinematic viscosity, density, and slurry transport properties.
    """
    fitting_k = get_fitting_k_map()
    roughness_map = get_roughness_map()

    seg_id   = seg.get('id', 'pipe')
    D_mm     = float(seg.get('diameter_mm') or seg.get('id_mm') or 100.0)
    L_m      = float(seg.get('length_m', 10.0))
    material = seg.get('material', 'commercial_steel')
    flow_raw = seg.get('flow_m3h')
    flow_m3h = float(flow_raw) if flow_raw is not None else float(global_flow_m3h)
    dz_m     = float(seg.get('elev_change_m', 0.0))
    raw_fittings = seg.get('fittings', [])

    eps_mm = roughness_map.get(material, roughness_map.get('commercial_steel', 0.046))

    # Parse fittings into Fitting objects with resolved K values
    parsed_fittings = []
    for item in raw_fittings:
        if isinstance(item, dict):
            k_val = item.get('k') or item.get('k_factor')
            key = item.get('key') or item.get('type')
            if k_val is None:
                k_val = fitting_k.get(key, 0.0)
            parsed_fittings.append(Fitting(
                id=str(item.get('id') or key or 'fit'),
                type=str(key or 'fitting'),
                label=str(item.get('label') or (key or 'Fitting').replace('_', ' ').title()),
                k_factor=float(k_val or 0.0),
                count=int(item.get('count') or 1),
                custom_k=float(item['custom_k']) if item.get('custom_k') is not None else None,
            ))
        elif isinstance(item, (int, float)):
            parsed_fittings.append(Fitting(type='custom', label=f'Custom K={item}', k_factor=float(item)))
        elif isinstance(item, str):
            k_val = fitting_k.get(item, 0.0)
            parsed_fittings.append(Fitting(type=item, label=item.replace('_', ' ').title(), k_factor=float(k_val)))

    pipe_edge = PipeEdge(
        id=seg_id,
        from_node=str(seg.get('from_node') or seg.get('fromNodeId') or ''),
        to_node=str(seg.get('to_node') or seg.get('toNodeId') or ''),
        length_m=L_m,
        diameter_mm=D_mm,
        material=material,
        roughness_mm=float(seg.get('roughness_mm') or eps_mm),
        hazen_williams_c=float(seg['hazen_williams_c']) if seg.get('hazen_williams_c') else None,
        fittings=parsed_fittings,
        custom_k=float(seg.get('custom_k') or 0.0),
        elev_change_m=dz_m,
        label=str(seg.get('label') or seg_id),
        standard=seg.get('standard'),
        schedule_sdr=seg.get('schedule_sdr'),
        nb_mm=seg.get('nb_mm'),
        od_mm=seg.get('od_mm'),
        id_mm=seg.get('id_mm', round(D_mm, 1)),
        pressure_rating=seg.get('pressure_rating'),
        flow_m3h=flow_m3h,
    )

    is_visc = (liquid == 'viscous' or (viscosity_cSt is not None and float(viscosity_cSt) > 1.05 and not is_slurry))
    if is_visc and viscosity_cSt > 0:
        nu = float(viscosity_cSt) * 1e-6
        rho = float(specific_gravity) * 1000.0 if specific_gravity > 0 else 1000.0
    else:
        nu = fluid_kinematic_viscosity_m2s(temperature_c)
        rho = fluid_density_kg_m3(temperature_c, specific_gravity)

    res = calculate_consolidated_pipe(
        pipe_edge, flow_m3h=flow_m3h, friction_method=friction_method,
        kinematic_viscosity=nu, fluid_density=rho,
        is_slurry=is_slurry, slurry_d50_mm=slurry_d50_mm,
        slurry_solids_sg=slurry_solids_sg, slurry_c_weight=slurry_c_weight
    )
    return res.to_dict()



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
    sel_form = session.get('selection_form_data') or {}

    # Merge fluid properties from pump selection form into active_sel if missing
    fluid_keys = [
        'liquid', 'temperature_c', 'rho', 'viscosity_cSt', 'fluid_ph',
        'fluid_concentration', 'is_hazardous', 'is_flammable',
        'sg_l', 'sg_s', 'sg_m', 'slurry_cv', 'slurry_cw', 'slurry_d50', 'unit_d50'
    ]
    for k in fluid_keys:
        if k in sel_form and k not in active_sel:
            active_sel[k] = sel_form[k]

    pipe_net_data = active_sel.get('pipe_network')
    pipe_network_json = json.dumps(pipe_net_data) if pipe_net_data else 'null'
    active_selection_json = json.dumps(active_sel)
    selection_form_data_json = json.dumps(sel_form)

    return render_template('pipe_network.html',
                           fittings_json=fittings_json,
                           materials_json=materials_json,
                           standard_pipes_json=standard_pipes_json,
                           pipe_network_json=pipe_network_json,
                           active_selection_json=active_selection_json,
                           selection_form_data_json=selection_form_data_json,
                           active_selection=active_sel,
                           selection_form_data=sel_form)



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
    Calculate consolidated friction losses and hydraulic resistance for every
    pipe segment in the submitted network.
    Automatically collapses degree-2 pseudo-nodes if full network graph is submitted.

    Request JSON:
    {
        "flow_m3h": 10.0,
        "friction_method": "darcy_weisbach" | "hazen_williams",
        "nodes": [ { node dicts } ],   // optional for graph consolidation
        "pipes": [ { pipe segment dicts } ]
    }

    Response JSON:
    {
        "results": [ { per-segment results including R and n } ],
        "errors":  [ { per-segment errors } ],
        "summary": { totals, R_system, friction_method },
        "constants": { reference tables }
    }
    """
    data = request.get_json(silent=True)
    if not data or 'pipes' not in data:
        return jsonify({'error': 'Missing required field: pipes'}), 400

    global_flow = float(data.get('flow_m3h', 10.0))
    friction_method = (data.get('friction_method') or 'darcy_weisbach').lower().strip()
    if friction_method not in ('darcy_weisbach', 'hazen_williams'):
        friction_method = 'darcy_weisbach'

    solver_method = (data.get('solver_method') or data.get('network_solver') or 'ggm').lower().strip()
    if solver_method not in ('ggm', 'newton_raphson', 'hardy_cross', 'linear_theory'):
        solver_method = 'ggm'

    # Environmental & Fluid Parameters:
    # 1. Site altitude (m above sea level) or barometric pressure override (kPa)
    altitude_m = float(data.get('altitude_m', 0.0) or 0.0)
    barometric_pressure_kpa = float(data.get('barometric_pressure_kpa')) if data.get('barometric_pressure_kpa') is not None else None

    # 2. Fluid operating temperature (°C) — determines saturation vapor pressure and viscosity
    temperature_c = float(data.get('temperature_c', 20.0) if data.get('temperature_c') is not None else 20.0)

    # 3. Fluid specific gravity (SG) — determines fluid density relative to water
    specific_gravity = float(data.get('specific_gravity', 1.0) or 1.0)

    # 4. Vapor pressure override (kPa)
    vapor_pressure_kpa = float(data['vapor_pressure_kpa']) if (data.get('vapor_pressure_kpa') is not None and str(data.get('vapor_pressure_kpa')).strip() != '') else None

    # 5. Fluid details from Pump Selection page (Water / Viscous / Slurry)
    fluid_type = (data.get('fluid_type') or data.get('liquid') or 'water').lower().strip()
    viscosity_cSt = float(data.get('viscosity_cSt', 1.0) or 1.0)
    fluid_ph = float(data.get('fluid_ph', 7.0)) if data.get('fluid_ph') is not None else None
    fluid_concentration = str(data.get('fluid_concentration') or '')
    is_hazardous = bool(data.get('is_hazardous', False))
    is_flammable = bool(data.get('is_flammable', False))

    # 6. Slurry transport parameters
    is_slurry = bool(data.get('is_slurry', False) or fluid_type == 'slurry')
    slurry_d50_mm = float(data.get('slurry_d50_mm', 0.15) or 0.15)
    slurry_solids_sg = float(data.get('slurry_solids_sg', 2.65) or 2.65)
    slurry_liquid_sg = float(data.get('slurry_liquid_sg') or data.get('sg_l') or 1.0)
    slurry_c_weight = float(data.get('slurry_c_weight', 25.0) or 25.0)
    slurry_c_volume = float(data.get('slurry_c_volume')) if data.get('slurry_c_volume') is not None else None

    raw_pipes = data['pipes']
    raw_nodes = data.get('nodes')

    if not isinstance(raw_pipes, list) or len(raw_pipes) == 0:
        return jsonify({'error': 'pipes must be a non-empty list'}), 400

    # =========================================================================
    # STEP 1: GRAPH TOPOLOGY INGESTION & CONSOLIDATION
    # =========================================================================
    results = []
    node_results = []
    errors = []
    consolidated_nodes = []

    if raw_nodes and isinstance(raw_nodes, list) and len(raw_nodes) > 0:
        graph = NetworkGraph()
        fitting_k = get_fitting_k_map()
        roughness_map = get_roughness_map()

        # Ingest nodes into graph representation
        for nd in raw_nodes:
            node_obj = Node.from_dict(nd)
            if node_obj.k_factor == 0.0 and node_obj.fitting_key and node_obj.fitting_key in fitting_k:
                node_obj.k_factor = float(fitting_k[node_obj.fitting_key])
            graph.add_node(node_obj)

        # Ingest pipe edges and resolve material roughness and fitting loss coefficients
        for pd in raw_pipes:
            p_obj = PipeEdge.from_dict(pd)
            if not p_obj.roughness_mm or p_obj.roughness_mm <= 0:
                p_obj.roughness_mm = roughness_map.get(p_obj.material, 0.046)
            for f in p_obj.fittings:
                if f.k_factor == 0.0 and f.type in fitting_k:
                    f.k_factor = float(fitting_k[f.type])

            # Enforce physical elevation integrity: Delta Z = Z_to - Z_from
            if p_obj.from_node in graph.nodes and p_obj.to_node in graph.nodes:
                p_obj.elev_change_m = round(graph.nodes[p_obj.to_node].elevation_m - graph.nodes[p_obj.from_node].elevation_m, 3)

            graph.add_pipe(p_obj)

        # Consolidate collinear edges across degree-2 pseudo-nodes
        consolidated = graph.consolidate()
        consolidated_nodes = [n.to_dict() for n in consolidated.nodes.values()]

        # =====================================================================
        # STEP 2: NETWORK ANALYSIS SOLVER EXECUTION
        # (Global Gradient Method, Newton-Raphson, Hardy Cross, Linear Theory)
        # =====================================================================
        try:
            solver_res = solve_network(
                graph=consolidated,
                solver_method=solver_method,
                friction_method=friction_method,
                global_flow_m3h=global_flow,
                altitude_m=altitude_m,
                temperature_c=temperature_c,
                specific_gravity=specific_gravity,
                barometric_pressure_kpa=barometric_pressure_kpa,
                vapor_pressure_kpa=vapor_pressure_kpa,
                is_slurry=is_slurry,
                slurry_d50_mm=slurry_d50_mm,
                slurry_solids_sg=slurry_solids_sg,
                slurry_liquid_sg=slurry_liquid_sg,
                slurry_c_weight=slurry_c_weight,
                slurry_c_volume=slurry_c_volume,
                fluid_type=fluid_type,
                viscosity_cSt=viscosity_cSt,
                fluid_ph=fluid_ph,
                fluid_concentration=fluid_concentration,
                is_hazardous=is_hazardous,
                is_flammable=is_flammable,
            )
            results = [p.to_dict() for p in solver_res.pipe_results]
            node_results = [n.to_dict() for n in solver_res.node_results]
            calc_summary = solver_res.summary
            total_head = calc_summary['total_system_head_m']
        except Exception as exc:
            errors.append({'id': 'solver', 'error': str(exc)})
            # Fallback to single segment calculation
            pipe_list_to_calc = [p.to_dict() for p in consolidated.pipes.values()]
            total_major, total_minor, total_elev, total_R = 0.0, 0.0, 0.0, 0.0
            for seg in pipe_list_to_calc:
                try:
                    res = calculate_segment(
                        seg, global_flow, friction_method=friction_method,
                        temperature_c=temperature_c, specific_gravity=specific_gravity,
                        liquid=fluid_type, viscosity_cSt=viscosity_cSt,
                        is_slurry=is_slurry, slurry_d50_mm=slurry_d50_mm,
                        slurry_solids_sg=slurry_solids_sg, slurry_c_weight=slurry_c_weight,
                        slurry_c_volume=slurry_c_volume
                    )
                    results.append(res)
                    total_major += res['hf_major_m']
                    total_minor += res['hf_minor_m']
                    total_elev  += res['hf_elevation_m']
                    total_R     += res.get('resistance_R', 0.0)
                except Exception as e:
                    errors.append({'id': seg.get('id', '?'), 'error': str(e)})
            total_head = total_major + total_minor + total_elev
            calc_summary = {
                'total_hf_major_m': round(total_major, 3),
                'total_hf_minor_m': round(total_minor, 3),
                'total_elevation_m': round(total_elev, 3),
                'total_system_head_m': round(total_head, 3),
                'total_system_R': round(total_R, 3),
                'pipe_count': len(results),
                'friction_method': friction_method,
                'solver_method': solver_method,
                'solver_name': solver_method.upper(),
                'converged': True,
                'iterations': 1,
                'altitude_m': altitude_m,
                'temperature_c': temperature_c,
                'specific_gravity': specific_gravity,
                'fluid_type': fluid_type,
                'liquid': fluid_type,
                'viscosity_cSt': viscosity_cSt,
                'is_slurry': is_slurry,
            }
    else:
        # Fallback for flat pipe list (legacy mode)
        pipe_list_to_calc = raw_pipes
        total_major, total_minor, total_elev, total_R = 0.0, 0.0, 0.0, 0.0
        for seg in pipe_list_to_calc:
            try:
                res = calculate_segment(
                    seg, global_flow, friction_method=friction_method,
                    temperature_c=temperature_c, specific_gravity=specific_gravity,
                    liquid=fluid_type, viscosity_cSt=viscosity_cSt,
                    is_slurry=is_slurry, slurry_d50_mm=slurry_d50_mm,
                    slurry_solids_sg=slurry_solids_sg, slurry_c_weight=slurry_c_weight,
                    slurry_c_volume=slurry_c_volume
                )
                results.append(res)
                total_major += res['hf_major_m']
                total_minor += res['hf_minor_m']
                total_elev  += res['hf_elevation_m']
                total_R     += res.get('resistance_R', 0.0)
            except (ValueError, ZeroDivisionError, KeyError) as exc:
                errors.append({'id': seg.get('id', '?'), 'error': str(exc)})
        total_head = total_major + total_minor + total_elev
        calc_summary = {
            'total_hf_major_m': round(total_major, 3),
            'total_hf_minor_m': round(total_minor, 3),
            'total_elevation_m': round(total_elev, 3),
            'total_system_head_m': round(total_head, 3),
            'total_system_R': round(total_R, 3),
            'pipe_count': len(results),
            'friction_method': friction_method,
            'solver_method': solver_method,
            'solver_name': solver_method.upper(),
            'converged': True,
            'iterations': 1,
            'altitude_m': altitude_m,
            'temperature_c': temperature_c,
            'specific_gravity': specific_gravity,
            'fluid_type': fluid_type,
            'liquid': fluid_type,
            'viscosity_cSt': viscosity_cSt,
            'is_slurry': is_slurry,
        }

    # Auto-sync calculation results and duty point to session['active_selection']
    try:
        active_sel = session.get('active_selection') or {}
        pn = active_sel.get('pipe_network') or {}
        pn['lastCalculation'] = {
            'results': results,
            'node_results': node_results,
            'errors': errors,
            'summary': calc_summary,
        }
        pn['globalFlow'] = global_flow
        pn['friction_method'] = friction_method
        pn['solver_method'] = solver_method
        pn['liquid'] = fluid_type
        pn['viscosity_cSt'] = viscosity_cSt
        pn['is_slurry'] = is_slurry
        pn['slurry_d50_mm'] = slurry_d50_mm
        pn['slurry_solids_sg'] = slurry_solids_sg
        pn['slurry_liquid_sg'] = slurry_liquid_sg
        pn['slurry_c_weight'] = slurry_c_weight
        pn['slurry_c_volume'] = slurry_c_volume

        active_sel['pipe_network'] = pn
        active_sel['q_duty'] = global_flow
        active_sel['disp_q_duty'] = global_flow
        active_sel['h_duty'] = round(total_head, 3)
        active_sel['disp_h_duty'] = round(total_head, 3)
        active_sel['liquid'] = fluid_type
        active_sel['viscosity_cSt'] = viscosity_cSt
        active_sel['is_slurry'] = is_slurry
        active_sel['slurry_d50_mm'] = slurry_d50_mm
        active_sel['slurry_solids_sg'] = slurry_solids_sg
        active_sel['slurry_liquid_sg'] = slurry_liquid_sg
        active_sel['slurry_c_weight'] = slurry_c_weight
        active_sel['slurry_c_volume'] = slurry_c_volume
        session['active_selection'] = active_sel
        session.modified = True
    except Exception:
        pass

    return jsonify({
        'results': results,
        'node_results': node_results,
        'errors':  errors,
        'summary': calc_summary,
        'consolidated_nodes': consolidated_nodes,
        'constants': {
            'fitting_k_values': get_fitting_k_map(),
            'fitting_labels':   get_fitting_label_map(),
            'pipe_roughness':   get_roughness_map(),
            'hazen_williams_c': DEFAULT_HAZEN_WILLIAMS_C,
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
