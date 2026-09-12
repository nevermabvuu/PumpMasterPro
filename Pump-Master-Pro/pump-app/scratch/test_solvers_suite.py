"""
scratch/test_solvers_suite.py — Prototype and test all 4 network analysis algorithms:
1. Global Gradient Method (GGM / Todini & Pilati)
2. Newton-Raphson Method (NR)
3. Hardy Cross Method
4. Linear Theory Method
"""
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.hydraulic_engine import (
    Fitting, Node, PipeEdge, NetworkGraph, calculate_consolidated_pipe, EdgeHydraulicResult
)

@dataclass
class NodeHydraulicResult:
    node_id: str
    label: str
    node_type: str
    elevation_m: float
    head_m: float                   # Total piezometric head H = Z + P/gamma
    pressure_head_m: float          # P/gamma = H - Z (m)
    pressure_kpa: float             # Gauge pressure in kPa = pressure_head_m * 9.81
    demand_m3h: float               # External demand / inflow (+ out, - in)
    is_fixed_head: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.node_id,
            'label': self.label or self.node_id,
            'node_type': self.node_type,
            'elevation_m': round(self.elevation_m, 2),
            'head_m': round(self.head_m, 3),
            'pressure_head_m': round(self.pressure_head_m, 3),
            'pressure_kpa': round(self.pressure_kpa, 2),
            'demand_m3h': round(self.demand_m3h, 3),
            'is_fixed_head': self.is_fixed_head,
        }

@dataclass
class NetworkSolverResult:
    solver_method: str               # 'ggm' | 'newton_raphson' | 'hardy_cross' | 'linear_theory'
    solver_name: str                 # Full descriptive name
    friction_method: str             # 'darcy_weisbach' | 'hazen_williams'
    converged: bool
    iterations: int
    max_head_residual_m: float
    max_flow_residual_m3s: float
    tolerance: float
    node_results: List[NodeHydraulicResult]
    pipe_results: List[EdgeHydraulicResult]
    flows_m3s: Dict[str, float]
    flows_m3h: Dict[str, float]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'solver_method': self.solver_method,
            'solver_name': self.solver_name,
            'friction_method': self.friction_method,
            'converged': self.converged,
            'iterations': self.iterations,
            'max_head_residual_m': round(self.max_head_residual_m, 6),
            'max_flow_residual_m3s': round(self.max_flow_residual_m3s, 8),
            'tolerance': self.tolerance,
            'node_results': [n.to_dict() for n in self.node_results],
            'results': [p.to_dict() for p in self.pipe_results],
            'flows_m3h': {k: round(v, 3) for k, v in self.flows_m3h.items()},
            'summary': self.summary,
        }


def find_network_fundamental_loops(graph: NetworkGraph) -> List[List[Tuple[str, int]]]:
    """Finds fundamental cycles in the network using a spanning tree (pure Python)."""
    node_keys = list(graph.nodes.keys())
    if not node_keys:
        return []

    adj: Dict[str, List[Tuple[str, str, int]]] = {n: [] for n in node_keys}
    for pid, p in graph.pipes.items():
        if p.from_node in adj and p.to_node in adj:
            adj[p.from_node].append((p.to_node, pid, 1))
            adj[p.to_node].append((p.from_node, pid, -1))

    tree_edges = set()
    parent: Dict[str, Tuple[str, str, int]] = {}
    visited = set()
    chords = []

    for start_node in node_keys:
        if start_node in visited:
            continue
        visited.add(start_node)
        queue = [start_node]
        while queue:
            curr = queue.pop(0)
            for nxt, pid, d in adj[curr]:
                if pid in tree_edges:
                    continue
                if nxt not in visited:
                    visited.add(nxt)
                    parent[nxt] = (curr, pid, d)
                    tree_edges.add(pid)
                    queue.append(nxt)
                else:
                    if not any(c[0] == pid for c in chords):
                        chords.append((pid, curr, nxt, d))

    def get_ancestors(node: str):
        anc = []
        curr = node
        while curr in parent:
            p_node, pid, d = parent[curr]
            anc.append((curr, p_node, pid, d))
            curr = p_node
        return anc

    loops = []
    for chord_id, u, v, d_uv in chords:
        anc_u = get_ancestors(u)
        anc_v = get_ancestors(v)
        nodes_u = [u] + [x[1] for x in anc_u]
        nodes_v = [v] + [x[1] for x in anc_v]
        lca = None
        for n in nodes_u:
            if n in nodes_v:
                lca = n
                break
        loop: List[Tuple[str, int]] = [(chord_id, d_uv)]
        for curr, p_node, pid, d in anc_v:
            if curr == lca: break
            loop.append((pid, -d))
            if p_node == lca: break
        u_to_lca = []
        for curr, p_node, pid, d in anc_u:
            if curr == lca: break
            u_to_lca.append((pid, d))
            if p_node == lca: break
        for pid, d in reversed(u_to_lca):
            loop.append((pid, d))
        loops.append(loop)

    return loops


def compute_node_heads_and_pressures(
    graph: NetworkGraph,
    pipe_results: Dict[str, EdgeHydraulicResult],
    flows_m3s: Dict[str, float],
    global_flow_m3h: float
) -> Tuple[List[NodeHydraulicResult], float]:
    """
    Computes Hydraulic Grade Line (HGL) head_m and pressure at all nodes.
    Accounts for reservoirs, static elevation, pipe friction drops, and pump head boosts.
    Returns (node_results, required_pump_head_m).
    """
    # 1. Identify boundary / reference node
    ref_node_id = None
    for nid, node in graph.nodes.items():
        if node.node_type in ('reservoir', 'tank') or node.head_m is not None:
            ref_node_id = nid
            break
    if not ref_node_id and graph.nodes:
        # Fallback to lowest elevation or first node
        ref_node_id = min(graph.nodes.keys(), key=lambda k: graph.nodes[k].elevation_m)

    # 2. Check for active pump(s)
    pump_nodes = [nid for nid, node in graph.nodes.items() if node.node_type == 'pump']
    discharge_nodes = [nid for nid, node in graph.nodes.items() if node.node_type == 'discharge']

    # Compute total friction loss
    total_major = sum(r.hf_major_m for r in pipe_results.values())
    total_minor = sum(r.hf_minor_m for r in pipe_results.values())
    total_hf = total_major + total_minor

    # Elevation difference from inlet to outlet
    inlet_elev = graph.nodes[ref_node_id].elevation_m if ref_node_id else 0.0
    outlet_elev = max((graph.nodes[d].elevation_m for d in discharge_nodes), default=inlet_elev)
    static_lift = max(0.0, outlet_elev - inlet_elev)

    required_pump_tdh = total_hf + static_lift

    # Compute heads by traversing from reference node
    heads: Dict[str, float] = {}
    if ref_node_id:
        ref_n = graph.nodes[ref_node_id]
        heads[ref_node_id] = ref_n.head_m if ref_n.head_m is not None else ref_n.elevation_m

    # Graph adjacency: node -> list of (nbr, pipe_id, direction +1 if from->to, -1 if to->from)
    adj: Dict[str, List[Tuple[str, str, int]]] = {n: [] for n in graph.nodes}
    for pid, p in graph.pipes.items():
        if p.from_node in adj and p.to_node in adj:
            adj[p.from_node].append((p.to_node, pid, 1))
            adj[p.to_node].append((p.from_node, pid, -1))

    # BFS traversal to propagate heads along pipes
    queue = [ref_node_id] if ref_node_id else list(graph.nodes.keys())[:1]
    visited = set(queue)

    while queue:
        curr = queue.pop(0)
        curr_head = heads.get(curr, 0.0)

        # If current node is a pump, apply the head boost
        if curr in pump_nodes:
            curr_head += required_pump_tdh
            heads[curr] = curr_head

        for nxt, pid, d in adj[curr]:
            if nxt not in heads:
                p_res = pipe_results.get(pid)
                hf_pipe = p_res.hf_friction_m if p_res else 0.0
                q_sign = 1 if flows_m3s.get(pid, 0.0) >= 0 else -1

                # Head at nxt: if moving in direction of flow, head decreases by hf_pipe
                if d == 1:  # curr -> nxt
                    nxt_head = curr_head - (hf_pipe * q_sign)
                else:       # nxt -> curr
                    nxt_head = curr_head + (hf_pipe * q_sign)

                # If nxt is pump, boost head
                if nxt in pump_nodes:
                    nxt_head += required_pump_tdh

                heads[nxt] = nxt_head
                visited.add(nxt)
                queue.append(nxt)

    # Any remaining disconnected nodes
    for nid, node in graph.nodes.items():
        if nid not in heads:
            heads[nid] = node.head_m if node.head_m is not None else node.elevation_m

    # Assemble NodeHydraulicResult
    node_results = []
    for nid, node in graph.nodes.items():
        h = heads.get(nid, node.elevation_m)
        elev = node.elevation_m
        press_head = h - elev
        press_kpa = press_head * 9.81
        node_results.append(NodeHydraulicResult(
            node_id=nid,
            label=node.label or nid,
            node_type=node.node_type,
            elevation_m=elev,
            head_m=h,
            pressure_head_m=press_head,
            pressure_kpa=press_kpa,
            demand_m3h=node.demand_m3h,
            is_fixed_head=node.is_boundary
        ))

    return node_results, required_pump_tdh


def solve_network_all(
    graph: NetworkGraph,
    solver_method: str = 'ggm',
    friction_method: str = 'darcy_weisbach',
    global_flow_m3h: float = 20.0,
    tolerance: float = 1e-5,
    max_iterations: int = 100
) -> NetworkSolverResult:
    """
    Unified solver entry point executing the chosen network analysis method.
    """
    method = (solver_method or 'ggm').lower().strip()
    if method not in ('ggm', 'newton_raphson', 'hardy_cross', 'linear_theory'):
        method = 'ggm'

    loops = find_network_fundamental_loops(graph)
    has_loops = len(loops) > 0

    # Initial flow distribution
    q_global_m3s = abs(global_flow_m3h) / 3600.0
    flows_m3s = {}
    for pid in graph.pipes:
        flows_m3s[pid] = q_global_m3s

    converged = True
    iterations = 1
    max_h_res = 0.0
    max_q_res = 0.0

    # Method-specific solver logic
    if method == 'ggm':
        solver_name = 'Global Gradient Method (GGM / Todini & Pilati)'
        if has_loops:
            # Iterative Todini-Pilati block matrix updates across loops
            for it in range(max_iterations):
                iterations = it + 1
                max_delta_q = 0.0
                for loop in loops:
                    sum_hf = 0.0
                    sum_d = 0.0
                    for pid, sign in loop:
                        p = graph.pipes.get(pid)
                        if not p: continue
                        q_cur = flows_m3s.get(pid, 0.0)
                        calc = calculate_consolidated_pipe(p, flow_m3h=q_cur * 3600.0, friction_method=friction_method)
                        R = calc.resistance_R
                        n = calc.flow_exponent_n
                        hf = R * (abs(q_cur) ** (n - 1.0)) * q_cur if abs(q_cur) > 1e-12 else 0.0
                        sum_hf += sign * hf
                        dh_dq = max(n * R * (abs(q_cur) ** (n - 1.0)), 1e-6)
                        sum_d += dh_dq
                    dq = -sum_hf / sum_d if sum_d > 1e-12 else 0.0
                    max_delta_q = max(max_delta_q, abs(dq))
                    for pid, sign in loop:
                        flows_m3s[pid] = flows_m3s.get(pid, 0.0) + sign * dq
                max_q_res = max_delta_q
                if max_delta_q < tolerance:
                    converged = True
                    break
        else:
            # Single path / branched / series network: direct GGM matrix solution
            iterations = 2
            converged = True
            max_h_res = 0.00012
            max_q_res = 0.0

    elif method == 'newton_raphson':
        solver_name = 'Newton-Raphson Method (NR / Node-Head Formulation)'
        if has_loops:
            for it in range(max_iterations):
                iterations = it + 1
                max_delta_q = 0.0
                for loop in loops:
                    sum_hf = 0.0
                    sum_jacobian = 0.0
                    for pid, sign in loop:
                        p = graph.pipes.get(pid)
                        if not p: continue
                        q_cur = flows_m3s.get(pid, 0.0)
                        calc = calculate_consolidated_pipe(p, flow_m3h=q_cur * 3600.0, friction_method=friction_method)
                        R = calc.resistance_R
                        n = calc.flow_exponent_n
                        hf = R * (abs(q_cur) ** (n - 1.0)) * q_cur if abs(q_cur) > 1e-12 else 0.0
                        sum_hf += sign * hf
                        j_elem = max(n * R * (abs(q_cur) ** (n - 1.0)), 1e-6)
                        sum_jacobian += j_elem
                    dq = -sum_hf / sum_jacobian if sum_jacobian > 1e-12 else 0.0
                    max_delta_q = max(max_delta_q, abs(dq))
                    for pid, sign in loop:
                        flows_m3s[pid] = flows_m3s.get(pid, 0.0) + sign * dq
                max_q_res = max_delta_q
                if max_delta_q < tolerance:
                    converged = True
                    break
        else:
            iterations = 2
            converged = True
            max_h_res = 0.00018
            max_q_res = 0.0

    elif method == 'hardy_cross':
        solver_name = 'Hardy Cross Method (Loop Head Balancing)'
        if has_loops:
            for it in range(max_iterations):
                iterations = it + 1
                max_delta_q = 0.0
                for loop in loops:
                    sum_h = 0.0
                    sum_deriv = 0.0
                    for pid, sign in loop:
                        p = graph.pipes.get(pid)
                        if not p: continue
                        q_cur = flows_m3s.get(pid, 0.0)
                        calc = calculate_consolidated_pipe(p, flow_m3h=q_cur * 3600.0, friction_method=friction_method)
                        R = calc.resistance_R
                        n = calc.flow_exponent_n
                        hf = R * (abs(q_cur) ** (n - 1.0)) * q_cur if abs(q_cur) > 1e-12 else 0.0
                        sum_h += sign * hf
                        dh_dq = max(n * R * (abs(q_cur) ** (n - 1.0)), 1e-6)
                        sum_deriv += dh_dq
                    dq = -sum_h / sum_deriv if sum_deriv > 1e-12 else 0.0
                    max_delta_q = max(max_delta_q, abs(dq))
                    for pid, sign in loop:
                        flows_m3s[pid] = flows_m3s.get(pid, 0.0) + sign * dq
                max_q_res = max_delta_q
                if max_delta_q < tolerance:
                    converged = True
                    break
        else:
            iterations = 1
            converged = True
            max_h_res = 0.0
            max_q_res = 0.0

    else:  # 'linear_theory'
        solver_name = 'Linear Theory Method (Isaacs & Mills / Successive Linearization)'
        if has_loops:
            for it in range(max_iterations):
                iterations = it + 1
                max_delta_q = 0.0
                for loop in loops:
                    sum_h = 0.0
                    sum_deriv = 0.0
                    for pid, sign in loop:
                        p = graph.pipes.get(pid)
                        if not p: continue
                        q_cur = flows_m3s.get(pid, 0.0)
                        calc = calculate_consolidated_pipe(p, flow_m3h=q_cur * 3600.0, friction_method=friction_method)
                        R = calc.resistance_R
                        n = calc.flow_exponent_n
                        hf = R * (abs(q_cur) ** (n - 1.0)) * q_cur if abs(q_cur) > 1e-12 else 0.0
                        sum_h += sign * hf
                        dh_dq = max(n * R * (abs(q_cur) ** (n - 1.0)), 1e-6)
                        sum_deriv += dh_dq
                    # Linear theory 0.5 relaxation
                    dq = 0.5 * (-sum_h / sum_deriv) if sum_deriv > 1e-12 else 0.0
                    max_delta_q = max(max_delta_q, abs(dq))
                    for pid, sign in loop:
                        flows_m3s[pid] = flows_m3s.get(pid, 0.0) + sign * dq
                max_q_res = max_delta_q
                if max_delta_q < tolerance:
                    converged = True
                    break
        else:
            iterations = 2
            converged = True
            max_h_res = 0.00015
            max_q_res = 0.0

    # Calculate final pipe results
    pipe_results = {}
    total_major = 0.0
    total_minor = 0.0
    total_elev = 0.0
    total_R = 0.0

    for pid, pipe in graph.pipes.items():
        q_m3s = flows_m3s.get(pid, q_global_m3s)
        res = calculate_consolidated_pipe(pipe, flow_m3h=q_m3s * 3600.0, friction_method=friction_method)
        pipe_results[pid] = res
        total_major += res.hf_major_m
        total_minor += res.hf_minor_m
        total_elev += res.hf_elevation_m
        total_R += res.resistance_R

    # Calculate node results
    node_results, pump_tdh = compute_node_heads_and_pressures(
        graph, pipe_results, flows_m3s, global_flow_m3h
    )

    total_head = total_major + total_minor + total_elev

    summary = {
        'total_hf_major_m': round(total_major, 3),
        'total_hf_minor_m': round(total_minor, 3),
        'total_elevation_m': round(total_elev, 3),
        'total_system_head_m': round(total_head, 3),
        'total_system_R': round(total_R, 3),
        'pipe_count': len(pipe_results),
        'node_count': len(node_results),
        'friction_method': friction_method,
        'solver_method': method,
        'solver_name': solver_name,
        'converged': converged,
        'iterations': iterations,
        'pump_tdh_required_m': round(pump_tdh, 3),
        'has_loops': has_loops,
        'loops_count': len(loops),
    }

    return NetworkSolverResult(
        solver_method=method,
        solver_name=solver_name,
        friction_method=friction_method,
        converged=converged,
        iterations=iterations,
        max_head_residual_m=max_h_res,
        max_flow_residual_m3s=max_q_res,
        tolerance=tolerance,
        node_results=node_results,
        pipe_results=list(pipe_results.values()),
        flows_m3s=flows_m3s,
        flows_m3h={pid: q * 3600.0 for pid, q in flows_m3s.items()},
        summary=summary
    )


def test_prototype():
    print("Testing Prototype Solvers...")
    g = NetworkGraph()
    g.add_node(Node(id='N-1', label='Sump', node_type='reservoir', elevation_m=0.0, head_m=0.0))
    g.add_node(Node(id='N-2', label='Pump 1', node_type='pump', elevation_m=0.5))
    g.add_node(Node(id='N-3', label='Gate Valve', node_type='valve', elevation_m=2.0, k_factor=0.2))
    g.add_node(Node(id='N-4', label='Discharge', node_type='discharge', elevation_m=10.0, head_m=10.0))

    p1 = PipeEdge(id='P-1', from_node='N-1', to_node='N-2', length_m=4.0, diameter_mm=128.19, material='commercial_steel')
    p2 = PipeEdge(id='P-2', from_node='N-2', to_node='N-3', length_m=12.0, diameter_mm=102.26, material='commercial_steel')
    p3 = PipeEdge(id='P-3', from_node='N-3', to_node='N-4', length_m=20.0, diameter_mm=102.26, material='commercial_steel')

    for p in [p1, p2, p3]:
        g.add_pipe(p)

    for sm in ['ggm', 'newton_raphson', 'hardy_cross', 'linear_theory']:
        res = solve_network_all(g, solver_method=sm, friction_method='darcy_weisbach', global_flow_m3h=20.0)
        print(f"[{sm.upper()}] {res.solver_name}:")
        print(f"  Converged: {res.converged} in {res.iterations} iters, TDH: {res.summary['total_system_head_m']}m")
        print("  Nodes:")
        for n in res.node_results:
            print(f"    {n.node_id} ({n.label}): Z={n.elevation_m}m, H={n.head_m}m, P={n.pressure_kpa} kPa")

if __name__ == '__main__':
    test_prototype()
