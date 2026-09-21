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
from utils import UNITS_FLOW, UNITS_HEAD, UNITS_POWER, UNITS_DENSITY, UNITS_SIZE
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

    slurry_liquid_sg = float(seg.get('slurry_liquid_sg') or 1.0)
    res = calculate_consolidated_pipe(
        pipe_edge, flow_m3h=flow_m3h, friction_method=friction_method,
        kinematic_viscosity=nu, fluid_density=rho,
        is_slurry=is_slurry, slurry_d50_mm=slurry_d50_mm,
        slurry_solids_sg=slurry_solids_sg, slurry_c_weight=slurry_c_weight,
        slurry_liquid_sg=slurry_liquid_sg
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

    # Engineering units metadata passed from active session/selection form
    units_tables = {
        'flow': UNITS_FLOW,
        'head': UNITS_HEAD,
        'power': UNITS_POWER,
        'density': UNITS_DENSITY,
        'size': UNITS_SIZE
    }
    unit_system = sel_form.get('unit_system') or active_sel.get('unit_system') or session.get('unit_system') or 'metric'
    unit_q = sel_form.get('unit_q') or active_sel.get('unit_q') or session.get('unit_q') or 'm3h'
    unit_h = sel_form.get('unit_h') or active_sel.get('unit_h') or session.get('unit_h') or 'm'

    return render_template('pipe_network.html',
                           fittings_json=fittings_json,
                           materials_json=materials_json,
                           standard_pipes_json=standard_pipes_json,
                           pipe_network_json=pipe_network_json,
                           active_selection_json=active_selection_json,
                           selection_form_data_json=selection_form_data_json,
                           active_selection=active_sel,
                           selection_form_data=sel_form,
                           units_tables=units_tables,
                           unit_system=unit_system,
                           unit_q=unit_q,
                           unit_h=unit_h)



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

        # =====================================================================
        # TOPOLOGICAL CONNECTIVITY & COMPLETENESS VALIDATION
        # If any member (node or pipe) is not connected to a complete network line,
        # refuse to perform the calculation and return HTTP 400 with diagnostic details.
        # Rationale: Prevents numerical divergence, undefined boundary pressures,
        # and physical flow law violations in disconnected/orphan piping members.
        # =====================================================================
        is_valid, validation_msg, disc_info = graph.validate_network_completeness()
        if not is_valid:
            return jsonify({
                'error': validation_msg,
                'disconnected_members': disc_info,
                'status': 'unconnected_network_line'
            }), 400

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
        # Synchronize static elevation head and NPSHa metrics into active duty point
        static_elev = round(float(calc_summary.get('total_elevation_m', 0.0) or 0.0), 3)
        active_sel['static_head'] = static_elev
        active_sel['disp_static_head'] = static_elev
        if calc_summary.get('npsha_m') is not None:
            npsh_val = round(float(calc_summary['npsha_m']), 2)
            active_sel['npsh_avail'] = npsh_val
            active_sel['disp_npsh_avail'] = npsh_val

        active_sel['liquid'] = fluid_type
        active_sel['viscosity_cSt'] = viscosity_cSt
        active_sel['is_slurry'] = is_slurry
        active_sel['slurry_d50_mm'] = slurry_d50_mm
        active_sel['slurry_solids_sg'] = slurry_solids_sg
        active_sel['slurry_liquid_sg'] = slurry_liquid_sg
        active_sel['slurry_c_weight'] = slurry_c_weight
        active_sel['slurry_c_volume'] = slurry_c_volume
        session['active_selection'] = active_sel

        # Also synchronize selection_form_data for immediate server-side form pre-fill
        sel_form = session.get('selection_form_data') or {}
        sel_form['q_duty'] = global_flow
        sel_form['h_duty'] = round(total_head, 3)
        sel_form['static_head'] = static_elev
        if calc_summary.get('npsha_m') is not None:
            sel_form['npsh_avail'] = round(float(calc_summary['npsha_m']), 2)
        session['selection_form_data'] = sel_form
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


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLE NETWORK MODE API (SERIES & PARALLEL PIPELINES VIA DROPDOWNS)
# ══════════════════════════════════════════════════════════════════════════════

@pipe_network_bp.route('/api/pipe-network/simple-calculate', methods=['POST'])
def simple_calculate():
    """
    Calculate friction losses, flow distribution, and system dynamic head for a simple pipe network
    (Series or Parallel) using the exact same unified hydraulic engine and solver methods as Drawing Mode.

    Supported Solvers:
      - 'ggm': Global Gradient Method (Todini & Pilati / EPANET standard)
      - 'newton_raphson': Newton-Raphson Method (Node-Head formulation)
      - 'hardy_cross': Hardy Cross Loop Balancing Method
      - 'linear_theory': Linear Theory Method (Isaacs & Mills Successive Linearization)

    Beginners Note & Hydraulic Architecture:
    -----------------------------------------
    1. Series Mode (Sequential Pipeline):
       - Generates an inlet boundary reservoir node (Head=0), intermediate junctions, and a terminal discharge node.
       - Connects pipe segments sequentially: Node_0 -> Node_1 -> ... -> Node_k.
       - Dispatches to solve_network() to evaluate exact friction losses across every segment.
       - Major + minor losses + elevation changes accumulate to form Total Dynamic Head (TDH).

    2. Parallel Mode (Branched Pipeline / Manifold):
       - Generates a common inlet manifold reservoir node and a common discharge header node.
       - Connects each parallel branch pipe from inlet to outlet.
       - Dispatches to solve_network() using the chosen solver to iteratively balance flow rates
         across all branches until piezometric head losses across parallel branches are equal.
       - Alternatively, supports manual % flow share allocation if specified by the user.
    """
    data = request.get_json(silent=True) or {}
    topology = (data.get('topology') or 'series').lower().strip()
    if topology not in ('series', 'parallel'):
        topology = 'series'

    # User-selectable network analysis solver method
    solver_method = (data.get('solver_method') or 'ggm').lower().strip()
    if solver_method not in ('ggm', 'newton_raphson', 'hardy_cross', 'linear_theory'):
        solver_method = 'ggm'

    parallel_balancing = (data.get('parallel_balancing') or 'auto').lower().strip()

    # Flow rate and engineering unit conversion
    flow_rate = float(data.get('flow_rate') or data.get('flow_m3h') or 10.0)
    flow_unit = (data.get('flow_unit') or 'm3h').lower().strip()
    flow_unit_factor = UNITS_FLOW.get(flow_unit, {}).get('factor_to_base', 1.0)
    global_flow_m3h = max(0.001, flow_rate * flow_unit_factor)

    static_elevation_m = float(data.get('static_elevation_m') or 0.0)
    friction_method = (data.get('friction_method') or 'darcy_weisbach').lower().strip()
    if friction_method not in ('darcy_weisbach', 'hazen_williams'):
        friction_method = 'darcy_weisbach'

    fluid = data.get('fluid') or {}
    temperature_c = float(fluid.get('temp_c') or data.get('temperature_c') or 20.0)
    specific_gravity = float(fluid.get('sg') or data.get('specific_gravity') or 1.0)
    fluid_type = (fluid.get('type') or data.get('fluid_type') or 'water').lower().strip()
    viscosity_cSt = float(fluid.get('viscosity_cst') or data.get('viscosity_cSt') or 1.004)

    # Fluid properties: density (rho) and kinematic viscosity (nu)
    if fluid_type != 'water':
        nu = float(viscosity_cSt) * 1e-6
        rho = float(specific_gravity) * 1000.0 if specific_gravity > 0 else 1000.0
    else:
        nu = fluid_kinematic_viscosity_m2s(temperature_c)
        rho = fluid_density_kg_m3(temperature_c, specific_gravity)

    raw_pipes = data.get('pipes') or []
    raw_parallel_branches = data.get('parallel_branches') or []

    fitting_k_map = get_fitting_k_map()
    roughness_map = get_roughness_map()

    def parse_single_pipe(p, default_idx=1, default_prefix='Pipe'):
        """
        Parses a single pipeline segment dictionary:
        - Resolves geometry (diameter, length, roughness, elevation)
        - Resolves valves & fittings and accumulates their K-factors
        - Converts child fittings into Fitting dataclass objects for the hydraulic engine
        """
        pipe_id = p.get('id') or f'pipe_{default_idx}_{int(time.time() * 1000) % 10000}'
        label = p.get('label') or f'{default_prefix} {default_idx}'
        length_m = max(0.001, float(p.get('length_m') or 10.0))
        diameter_mm = max(1.0, float(p.get('diameter_mm') or 100.0))
        material = p.get('material') or 'commercial_steel'
        roughness_mm = float(p.get('roughness_mm') or roughness_map.get(material, 0.046))
        elevation_m = float(p.get('elevation_m') or 0.0)
        custom_k = max(0.0, float(p.get('custom_k') or 0.0))
        flow_pct = float(p.get('flow_pct') or p.get('flow_share_pct') or 0.0)

        # Parse child fittings (supports dict {key: qty}, list of dicts, or list of strings)
        fittings_raw = p.get('fittings') or {}
        total_k = custom_k
        fittings_details = []
        fittings_objs = []

        if isinstance(fittings_raw, dict):
            for f_key, f_val in fittings_raw.items():
                if isinstance(f_val, dict):
                    count = max(0, int(f_val.get('count') or 1))
                    k_single = float(f_val.get('k_factor') if f_val.get('k_factor') is not None else fitting_k_map.get(f_key, 0.0))
                else:
                    try:
                        count = max(0, int(f_val))
                    except (ValueError, TypeError):
                        count = 1
                    k_single = float(fitting_k_map.get(f_key, 0.0))
                if count > 0:
                    k_sub = k_single * count
                    total_k += k_sub
                    fittings_details.append({
                        'type': f_key,
                        'count': count,
                        'k_single': round(k_single, 3),
                        'k_subtotal': round(k_sub, 3)
                    })
                    fittings_objs.append(Fitting(
                        id=f_key,
                        type=f_key,
                        label=f_key.replace('_', ' ').title(),
                        k_factor=k_single,
                        count=count
                    ))
        elif isinstance(fittings_raw, list):
            for f in fittings_raw:
                if isinstance(f, dict):
                    f_type = f.get('type') or f.get('key') or ''
                    count = max(1, int(f.get('count') or 1))
                    k_single = float(f.get('k_factor') if f.get('k_factor') is not None else fitting_k_map.get(f_type, 0.0))
                elif isinstance(f, str):
                    f_type = f
                    count = 1
                    k_single = float(fitting_k_map.get(f_type, 0.0))
                else:
                    continue
                k_sub = k_single * count
                total_k += k_sub
                fittings_details.append({
                    'type': f_type,
                    'count': count,
                    'k_single': round(k_single, 3),
                    'k_subtotal': round(k_sub, 3)
                })
                fittings_objs.append(Fitting(
                    id=f_type,
                    type=f_type,
                    label=f_type.replace('_', ' ').title(),
                    k_factor=k_single,
                    count=count
                ))

        return {
            'id': pipe_id,
            'label': label,
            'length_m': length_m,
            'diameter_mm': diameter_mm,
            'material': material,
            'roughness_mm': roughness_mm,
            'elevation_m': elevation_m,
            'custom_k': custom_k,
            'total_k': total_k,
            'flow_pct': flow_pct,
            'fittings_objs': fittings_objs,
            'fittings_details': fittings_details
        }

    results = []
    branch_summaries = []
    solver_name = "Unified Hydraulic Solver"
    converged = True

    # =========================================================================
    # CASE 1: COMPOUND PARALLEL NETWORK (UP TO 5 SERIES PIPES PER BRANCH)
    # =========================================================================
    if topology == 'parallel':
        # Parse parallel branches: if raw_parallel_branches is provided, use it;
        # otherwise wrap raw_pipes for backward compatibility.
        parsed_branches = []
        if raw_parallel_branches:
            for b_idx, b in enumerate(raw_parallel_branches):
                b_id = b.get('id') or f'branch_{b_idx + 1}'
                b_label = b.get('label') or f'Branch {b_idx + 1}'
                b_dis_elev = float(b.get('discharge_elevation_m') if b.get('discharge_elevation_m') is not None else (b.get('elevation_m') or static_elevation_m))
                b_flow_pct = float(b.get('flow_pct') or 0.0)
                sub_pipes_raw = b.get('pipes') or b.get('sub_pipes') or []
                # Enforce up to 5 series pipes per branch
                sub_pipes = [parse_single_pipe(sp, default_idx=p_i + 1, default_prefix=f'{b_idx + 1}.') for p_i, sp in enumerate(sub_pipes_raw[:5])]
                if not sub_pipes:
                    sub_pipes = [parse_single_pipe({}, default_idx=1, default_prefix=f'{b_idx + 1}.')]
                parsed_branches.append({
                    'id': b_id,
                    'label': b_label,
                    'discharge_elevation_m': b_dis_elev,
                    'flow_pct': b_flow_pct,
                    'pipes': sub_pipes
                })
        else:
            # Flat pipes fallback: treat each pipe as a single-pipe parallel branch
            for b_idx, p in enumerate(raw_pipes):
                sp = parse_single_pipe(p, default_idx=b_idx + 1, default_prefix='Branch Pipe')
                parsed_branches.append({
                    'id': f'branch_{b_idx + 1}',
                    'label': sp['label'],
                    'discharge_elevation_m': float(p.get('elevation_m') or static_elevation_m),
                    'flow_pct': sp['flow_pct'],
                    'pipes': [sp]
                })

        num_branches = len(parsed_branches)

        # Helper to compute branch friction loss and dH/dQ for a trial flow Q (m3/h)
        def eval_branch_hydraulics(branch_obj, q_flow_m3h):
            tot_major = 0.0
            tot_minor = 0.0
            tot_dh_dq = 0.0
            pipe_res_list = []
            for sp in branch_obj['pipes']:
                edge = PipeEdge(
                    id=sp['id'],
                    from_node='a',
                    to_node='b',
                    length_m=sp['length_m'],
                    diameter_mm=sp['diameter_mm'],
                    material=sp['material'],
                    roughness_mm=sp['roughness_mm'],
                    fittings=sp['fittings_objs'],
                    custom_k=sp['custom_k'],
                    elev_change_m=sp['elevation_m'],
                    label=sp['label']
                )
                calc_res = calculate_consolidated_pipe(
                    edge,
                    flow_m3h=q_flow_m3h,
                    friction_method=friction_method,
                    kinematic_viscosity=nu,
                    fluid_density=rho,
                    is_slurry=(fluid_type == 'slurry')
                )
                tot_major += calc_res.hf_major_m
                tot_minor += calc_res.hf_minor_m
                tot_dh_dq += calc_res.derivative_dh_dq
                pipe_res_list.append(calc_res)
            
            tot_fric = tot_major + tot_minor
            total_branch_head = branch_obj['discharge_elevation_m'] + tot_fric
            return total_branch_head, tot_fric, tot_dh_dq, pipe_res_list

        is_manual = (parallel_balancing == 'manual' and any(b['flow_pct'] > 0 for b in parsed_branches))

        if is_manual:
            # 1. Manual Flow Allocation: Flow divides per user specified percentage
            solver_name = "Manual Percentage Flow Allocation"
            pct_sum = sum(b['flow_pct'] for b in parsed_branches)
            norm_factor = (100.0 / pct_sum) if pct_sum > 0 else (1.0 / num_branches)
            branch_flows = [global_flow_m3h * (b['flow_pct'] * norm_factor / 100.0) for b in parsed_branches]

            branch_heads = []
            for b_idx, b in enumerate(parsed_branches):
                q_b = branch_flows[b_idx]
                h_b, fric_b, _, sub_calcs = eval_branch_hydraulics(b, q_b)
                branch_heads.append(h_b)

                branch_summaries.append({
                    'id': b['id'],
                    'label': b['label'],
                    'flow_m3h': round(q_b, 3),
                    'flow_share_pct': round((q_b / global_flow_m3h * 100.0) if global_flow_m3h > 0 else 0.0, 1),
                    'discharge_elevation_m': round(b['discharge_elevation_m'], 2),
                    'total_branch_head_m': round(h_b, 3),
                    'friction_loss_m': round(fric_b, 3),
                    'friction_head_m': round(fric_b, 3),
                    'sub_pipe_count': len(b['pipes']),
                    'num_sub_pipes': len(b['pipes'])
                })

                for sp, c_res in zip(b['pipes'], sub_calcs):
                    results.append({
                        'id': sp['id'],
                        'label': sp['label'],
                        'branch_id': b['id'],
                        'branch_label': b['label'],
                        'length_m': round(sp['length_m'], 2),
                        'diameter_mm': round(sp['diameter_mm'], 2),
                        'material': sp['material'],
                        'roughness_mm': round(sp['roughness_mm'], 4),
                        'flow_m3h': round(c_res.flow_m3h, 3),
                        'flow_ls': round(c_res.flow_m3h / 3.6, 3),
                        'flow_share_pct': round((c_res.flow_m3h / global_flow_m3h * 100.0) if global_flow_m3h > 0 else 0.0, 1),
                        'velocity_m_s': round(c_res.velocity_ms, 3),
                        'velocity_ms': round(c_res.velocity_ms, 3),
                        'reynolds': c_res.reynolds,
                        'flow_regime': c_res.regime,
                        'regime': c_res.regime,
                        'friction_factor': round(c_res.friction_factor, 5),
                        'k_total': round(c_res.K_total, 3),
                        'K_total': round(c_res.K_total, 3),
                        'hf_major_m': round(c_res.hf_major_m, 3),
                        'hf_minor_m': round(c_res.hf_minor_m, 3),
                        'hf_elevation_m': round(sp['elevation_m'], 3),
                        'head_loss_m': round(c_res.hf_friction_m, 3),
                        'total_segment_head_m': round(c_res.h_total_m, 3),
                        'resistance_R': round(c_res.resistance_R, 6),
                        'fittings_details': sp['fittings_details']
                    })

            total_system_head_m = max(branch_heads) if branch_heads else 0.0
            equiv_system_R = (total_system_head_m / (global_flow_m3h ** 2)) if global_flow_m3h > 0 else 0.0

        else:
            # 2. Auto Hydraulic Balancing with Differential Discharge Elevations
            # Solves for manifold head H such that: Z_j + sum(h_f,j(Q_j)) = H for all branches, and sum(Q_j) = Q_total
            solver_name = f"Auto Hydraulic Balancing ({solver_method.upper()})"

            # Guaranteed Monotonic Bisection Solver for Differential Discharge Elevations:
            # Piezometric head H is strictly monotonic with total flow sum(Q_j(H)).
            # Solves for manifold head H such that: Z_j + sum(h_f,j(Q_j)) = H for all branches, and sum(Q_j) = Q_total
            h_low = min(b['discharge_elevation_m'] for b in parsed_branches)
            h_high = max(b['discharge_elevation_m'] for b in parsed_branches) + 50.0

            # Function to compute flow Q_b in branch b for a given manifold head H
            def get_branch_flow_for_head(branch, head_target):
                z_dis = branch['discharge_elevation_m']
                if head_target <= z_dis:
                    return 0.0
                target_fric = head_target - z_dis
                # Bisect on Q in [0, max(global_flow_m3h * 2.0, 10.0)]
                q_lo, q_hi = 0.0, max(global_flow_m3h * 2.0, 10.0)
                for _ in range(25):
                    q_m = 0.5 * (q_lo + q_hi)
                    _, fric_loss, _, _ = eval_branch_hydraulics(branch, q_m)
                    if fric_loss < target_fric:
                        q_lo = q_m
                    else:
                        q_hi = q_m
                return 0.5 * (q_lo + q_hi)

            # Ensure h_high is high enough so sum(Q) >= global_flow_m3h
            for _ in range(10):
                q_sum_hi = sum(get_branch_flow_for_head(b, h_high) for b in parsed_branches)
                if q_sum_hi >= global_flow_m3h:
                    break
                h_high += 50.0

            # Outer bisection on manifold Head H to match total system flow
            for it in range(35):
                h_mid = 0.5 * (h_low + h_high)
                q_sum = sum(get_branch_flow_for_head(b, h_mid) for b in parsed_branches)
                if q_sum < global_flow_m3h:
                    h_low = h_mid
                else:
                    h_high = h_mid
                if abs(q_sum - global_flow_m3h) < 1e-4:
                    break

            total_system_head_m = 0.5 * (h_low + h_high)
            q_branches = [get_branch_flow_for_head(b, total_system_head_m) for b in parsed_branches]

            # Re-normalize slightly so sum of flows strictly equals global_flow_m3h (zero residual)
            tot_q_actual = sum(q_branches)
            if tot_q_actual > 0:
                q_branches = [q * (global_flow_m3h / tot_q_actual) for q in q_branches]
            converged = True

            # Evaluate final results per branch and sub-pipe
            for b_idx, b in enumerate(parsed_branches):
                q_b = q_branches[b_idx] if b_idx < len(q_branches) else (global_flow_m3h / num_branches)
                h_b, fric_b, _, sub_calcs = eval_branch_hydraulics(b, q_b)

                branch_summaries.append({
                    'id': b['id'],
                    'label': b['label'],
                    'flow_m3h': round(q_b, 3),
                    'flow_share_pct': round((q_b / global_flow_m3h * 100.0) if global_flow_m3h > 0 else 0.0, 1),
                    'discharge_elevation_m': round(b['discharge_elevation_m'], 2),
                    'total_branch_head_m': round(h_b, 3),
                    'friction_loss_m': round(fric_b, 3),
                    'friction_head_m': round(fric_b, 3),
                    'sub_pipe_count': len(b['pipes']),
                    'num_sub_pipes': len(b['pipes'])
                })

                for sp, c_res in zip(b['pipes'], sub_calcs):
                    results.append({
                        'id': sp['id'],
                        'label': sp['label'],
                        'branch_id': b['id'],
                        'branch_label': b['label'],
                        'length_m': round(sp['length_m'], 2),
                        'diameter_mm': round(sp['diameter_mm'], 2),
                        'material': sp['material'],
                        'roughness_mm': round(sp['roughness_mm'], 4),
                        'flow_m3h': round(c_res.flow_m3h, 3),
                        'flow_ls': round(c_res.flow_m3h / 3.6, 3),
                        'flow_share_pct': round((c_res.flow_m3h / global_flow_m3h * 100.0) if global_flow_m3h > 0 else 0.0, 1),
                        'velocity_m_s': round(c_res.velocity_ms, 3),
                        'velocity_ms': round(c_res.velocity_ms, 3),
                        'reynolds': c_res.reynolds,
                        'flow_regime': c_res.regime,
                        'regime': c_res.regime,
                        'friction_factor': round(c_res.friction_factor, 5),
                        'k_total': round(c_res.K_total, 3),
                        'K_total': round(c_res.K_total, 3),
                        'hf_major_m': round(c_res.hf_major_m, 3),
                        'hf_minor_m': round(c_res.hf_minor_m, 3),
                        'hf_elevation_m': round(sp['elevation_m'], 3),
                        'head_loss_m': round(c_res.hf_friction_m, 3),
                        'total_segment_head_m': round(c_res.h_total_m, 3),
                        'resistance_R': round(c_res.resistance_R, 6),
                        'fittings_details': sp['fittings_details']
                    })

            equiv_system_R = (total_system_head_m / (global_flow_m3h ** 2)) if global_flow_m3h > 0 else 0.0

    # =========================================================================
    # CASE 2: SERIES PIPELINE NETWORK (SEQUENTIAL END-TO-END)
    # =========================================================================
    else:
        parsed_pipes = [parse_single_pipe(p, default_idx=idx + 1) for idx, p in enumerate(raw_pipes)]
        num_pipes = len(parsed_pipes)

        # Standard NetworkGraph construction & solve_network() execution
        graph = NetworkGraph()
        n0 = Node(id='n_inlet', label='Inlet Source', node_type='reservoir', elevation_m=0.0, head_m=0.0)
        graph.add_node(n0)
        cum_z = 0.0
        for i, p in enumerate(parsed_pipes):
            cum_z += p['elevation_m']
            from_n = 'n_inlet' if i == 0 else f'n_junc_{i}'
            to_n = 'n_outlet' if i == num_pipes - 1 else f'n_junc_{i + 1}'

            if i < num_pipes - 1:
                graph.add_node(Node(
                    id=to_n,
                    label=f'Junction {i + 1}',
                    node_type='junction',
                    elevation_m=round(cum_z, 3)
                ))
            else:
                graph.add_node(Node(
                    id='n_outlet',
                    label='System Discharge',
                    node_type='discharge',
                    elevation_m=round(cum_z + static_elevation_m, 3),
                    demand_m3h=global_flow_m3h
                ))

            edge = PipeEdge(
                id=p['id'],
                from_node=from_n,
                to_node=to_n,
                length_m=p['length_m'],
                diameter_mm=p['diameter_mm'],
                material=p['material'],
                roughness_mm=p['roughness_mm'],
                fittings=p['fittings_objs'],
                custom_k=p['custom_k'],
                elev_change_m=p['elevation_m'],
                label=p['label']
            )
            graph.add_pipe(edge)

        # Execute unified network solver
        solver_res = solve_network(
            graph=graph,
            solver_method=solver_method,
            friction_method=friction_method,
            global_flow_m3h=global_flow_m3h,
            altitude_m=0.0,
            temperature_c=temperature_c,
            specific_gravity=specific_gravity,
            viscosity_cSt=viscosity_cSt,
            fluid_type=fluid_type,
            is_slurry=(fluid_type == 'slurry')
        )

        solver_name = solver_res.solver_name
        converged = solver_res.converged
        total_system_head_m = solver_res.summary['total_system_head_m']
        equiv_system_R = solver_res.summary.get('equivalent_system_R', 0.0)

        # Build pipe results matching simple mode UI structure
        parsed_pipe_map = {p['id']: p for p in parsed_pipes}
        for p_res in solver_res.pipe_results:
            p_orig = parsed_pipe_map.get(p_res.pipe_id, {})
            results.append({
                'id': p_res.pipe_id,
                'label': p_res.label,
                'length_m': round(p_res.length_m, 2),
                'diameter_mm': round(p_res.diameter_mm, 2),
                'material': p_res.material,
                'roughness_mm': round(p_orig.get('roughness_mm', 0.046), 4),
                'flow_m3h': round(p_res.flow_m3h, 3),
                'flow_ls': round(p_res.flow_m3h / 3.6, 3),
                'flow_share_pct': round((p_res.flow_m3h / global_flow_m3h * 100.0) if global_flow_m3h > 0 else 0.0, 1),
                'velocity_m_s': round(p_res.velocity_ms, 3),
                'velocity_ms': round(p_res.velocity_ms, 3),
                'reynolds': p_res.reynolds,
                'flow_regime': p_res.regime,
                'regime': p_res.regime,
                'friction_factor': round(p_res.friction_factor, 5),
                'k_total': round(p_res.K_total, 3),
                'K_total': round(p_res.K_total, 3),
                'hf_major_m': round(p_res.hf_major_m, 3),
                'hf_minor_m': round(p_res.hf_minor_m, 3),
                'hf_elevation_m': round(p_res.hf_elevation_m, 3),
                'head_loss_m': round(p_res.hf_friction_m, 3),
                'total_segment_head_m': round(p_res.h_total_m, 3),
                'resistance_R': round(p_res.resistance_R, 6),
                'fittings_details': p_orig.get('fittings_details', [])
            })

    # Fluid hydraulic power required: P_hyd = rho * g * Q * H / 1000 (kW)
    q_m3s_total = global_flow_m3h / 3600.0
    hydraulic_power_kw = (rho * G_ACCEL * q_m3s_total * total_system_head_m) / 1000.0 if total_system_head_m > 0 else 0.0
    total_fric_loss = sum(r['hf_major_m'] + r['hf_minor_m'] for r in results) if topology == 'series' else (total_system_head_m - static_elevation_m)

    # ─────────────────────────────────────────────────────────────────────────
    # Net Positive Suction Head Available (NPSHa) Calculation for Simple Mode
    # Formula: NPSHa = h_atm - h_vp + h_suction_static - h_suction_friction + h_v_suction
    # ─────────────────────────────────────────────────────────────────────────
    p_atm_kpa = 101.325
    t_c = max(0.1, min(100.0, temperature_c))
    # Antoine equation: water saturation vapor pressure in kPa
    p_vapor_kpa = (10.0 ** (8.07131 - (1730.63 / (233.426 + t_c)))) * 0.133322
    h_atm_m = (p_atm_kpa * 1000.0) / (rho * G_ACCEL)
    h_vapor_m = (p_vapor_kpa * 1000.0) / (rho * G_ACCEL)

    # Suction segment friction & elevation evaluation
    suction_fric_m = 0.0
    suction_elev_m = 0.0
    suction_vel_head_m = 0.0

    if results and len(results) > 0:
        first_p = results[0]
        lbl = str(first_p.get('label', '')).lower()
        is_suction = 'suction' in lbl or len(results) > 1
        if is_suction:
            suction_fric_m = float(first_p.get('hf_major_m', 0.0) or 0.0) + float(first_p.get('hf_minor_m', 0.0) or 0.0)
            suction_elev_m = float(first_p.get('hf_elevation_m', 0.0) or 0.0)
            v_ms = float(first_p.get('velocity_m_s', 0.0) or first_p.get('velocity_ms', 0.0) or 0.0)
            suction_vel_head_m = (v_ms ** 2) / (2.0 * G_ACCEL)

    npsha_m = max(0.0, h_atm_m - h_vapor_m + suction_elev_m - suction_fric_m + suction_vel_head_m)

    npsha_m = round(npsha_m, 2)
    npsha_ft = round(npsha_m * 3.28084, 2)

    summary = {
        'topology': topology,
        'solver_method': solver_method,
        'solver_name': solver_name,
        'converged': converged,
        'global_flow_m3h': round(global_flow_m3h, 3),
        'global_flow_ls': round(global_flow_m3h / 3.6, 3),
        'flow_user_unit': round(flow_rate, 3),
        'unit_q': flow_unit,
        'static_elevation_m': round(static_elevation_m, 3),
        'total_friction_loss_m': round(total_fric_loss, 3),
        'total_system_head_m': round(total_system_head_m, 3),
        'total_system_head_ft': round(total_system_head_m * 3.28084, 2),
        'total_system_R': round(equiv_system_R, 6),
        'npsha_m': npsha_m,
        'npsha_ft': npsha_ft,
        'pipe_count': len(results),
        'friction_method': friction_method,
        'temperature_c': temperature_c,
        'specific_gravity': specific_gravity,
        'fluid_type': fluid_type,
        'fluid_density_kg_m3': round(rho, 1),
        'kinematic_viscosity_cSt': round(nu * 1e6, 3),
        'hydraulic_power_kw': round(hydraulic_power_kw, 2),
        'hydraulic_power_hp': round(hydraulic_power_kw * 1.34102, 2)
    }

    # Auto-sync duty point to active selection session
    try:
        active_sel = session.get('active_selection') or {}
        active_sel['q_duty'] = round(global_flow_m3h, 3)
        active_sel['h_duty'] = round(total_system_head_m, 3)
        active_sel['static_head'] = round(static_elevation_m, 3)
        active_sel['npsh_avail'] = npsha_m
        active_sel['disp_q_duty'] = round(flow_rate, 3)
        active_sel['disp_h_duty'] = round(total_system_head_m, 3)
        active_sel['disp_static_head'] = round(static_elevation_m, 3)
        active_sel['disp_npsh_avail'] = npsha_m
        active_sel['pipe_network'] = {
            'mode': 'simple',
            'topology': topology,
            'solver_method': solver_method,
            'globalFlow': global_flow_m3h,
            'flow_rate': flow_rate,
            'flow_unit': flow_unit,
            'static_elevation_m': static_elevation_m,
            'friction_method': friction_method,
            'fluid': fluid,
            'pipes': raw_pipes,
            'lastCalculation': {
                'summary': summary,
                'results': results
            }
        }
        session['active_selection'] = active_sel

        # Synchronize selection_form_data
        sel_form = session.get('selection_form_data') or {}
        sel_form['q_duty'] = round(flow_rate, 3)
        sel_form['unit_q'] = flow_unit
        sel_form['h_duty'] = round(total_system_head_m, 3)
        sel_form['static_head'] = round(static_elevation_m, 3)
        sel_form['npsh_avail'] = npsha_m
        session['selection_form_data'] = sel_form
        session.modified = True
    except Exception:
        pass

    return jsonify({
        'status': 'ok',
        'topology': topology,
        'solver_method': solver_method,
        'solver_name': solver_name,
        'converged': converged,
        'total_system_head_m': round(total_system_head_m, 3),
        'total_system_head_ft': round(total_system_head_m * 3.28084, 2),
        'total_friction_loss_m': round(total_fric_loss, 3),
        'static_elevation_m': round(static_elevation_m, 3),
        'npsha_m': npsha_m,
        'npsha_ft': npsha_ft,
        'flow_m3h': round(global_flow_m3h, 3),
        'flow_user_unit': round(flow_rate, 3),
        'unit_q': flow_unit,
        'unit_h': 'm',
        'hydraulic_power_kw': round(hydraulic_power_kw, 2),
        'hydraulic_power_hp': round(hydraulic_power_kw * 1.34102, 2),
        'equivalent_system_R': round(equiv_system_R, 6),
        'applied_to_selection': bool(data.get('apply_to_selection') or request.args.get('apply_to_selection')),
        'total_system_head_user_unit': round(total_system_head_m, 3),
        'branch_summaries': branch_summaries,
        'pipes': results,
        'results': results,
        'summary': summary
    })
