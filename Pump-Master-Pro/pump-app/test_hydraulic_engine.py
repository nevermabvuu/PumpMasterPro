"""
test_hydraulic_engine.py — Test suite for refactored pipe network analysis engine.
Verifies all 4 structural rules:
  1. Fittings as attributes on continuous pipe edges.
  2. Minor loss accumulation (K_total).
  3. Genuine splitting criteria (branches, diameter/material transitions, boundary conditions).
  4. Consolidated resistance R and exponent n for Darcy-Weisbach and Hazen-Williams, and Hardy Cross convergence.
"""

import math
from services.hydraulic_engine import (
    Fitting, Node, PipeEdge, NetworkGraph,
    calculate_consolidated_pipe, solve_hardy_cross, LoopDefinition
)

def test_minor_loss_accumulation():
    print("--- Test 1: Minor Loss Accumulation on Single Pipe ---")
    pipe = PipeEdge(
        id="P1",
        from_node="J1",
        to_node="J2",
        length_m=50.0,
        diameter_mm=100.0,
        material="commercial_steel",
        custom_k=0.5
    )
    # Add child fittings
    pipe.add_fitting(Fitting(id="f1", type="gate_valve", label="Gate Valve", k_factor=0.2, count=1))
    pipe.add_fitting(Fitting(id="f2", type="elbow_90", label="90 Elbow", k_factor=0.75, count=2))

    # K_total should be: 0.2*1 + 0.75*2 + 0.5 = 0.2 + 1.5 + 0.5 = 2.2
    print(f"K_total: {pipe.k_total} (Expected: 2.2)")
    assert abs(pipe.k_total - 2.2) < 1e-6, f"Expected 2.2, got {pipe.k_total}"

    # Calculate hydraulics under Darcy-Weisbach at 20 m^3/h
    res_dw = calculate_consolidated_pipe(pipe, flow_m3h=20.0, friction_method="darcy_weisbach")
    print(f"Darcy-Weisbach: hf_major={res_dw.hf_major_m:.4f}m, hf_minor={res_dw.hf_minor_m:.4f}m, hf_total={res_dw.hf_friction_m:.4f}m")
    print(f"Consolidated R_dw={res_dw.resistance_R:.2f}, n={res_dw.flow_exponent_n}")

    # Check that hf = R * Q^n matches
    q_m3s = 20.0 / 3600.0
    hf_from_R = res_dw.resistance_R * (q_m3s ** res_dw.flow_exponent_n)
    assert abs(hf_from_R - res_dw.hf_friction_m) < 1e-4, f"Discrepancy: {hf_from_R} vs {res_dw.hf_friction_m}"

    # Calculate hydraulics under Hazen-Williams at 20 m^3/h
    res_hw = calculate_consolidated_pipe(pipe, flow_m3h=20.0, friction_method="hazen_williams")
    print(f"Hazen-Williams: hf_major={res_hw.hf_major_m:.4f}m, hf_minor={res_hw.hf_minor_m:.4f}m, hf_total={res_hw.hf_friction_m:.4f}m")
    print(f"Consolidated R_hw={res_hw.resistance_R:.2f}, n={res_hw.flow_exponent_n}")
    print("Test 1 PASSED!\n")


def test_pseudo_node_collapsing():
    print("--- Test 2: Collapsing Degree-2 Pseudo-Nodes ---")
    # Network: ResA -> Pipe1 -> ValveNode -> Pipe2 -> TankB
    # ValveNode is a degree-2 pseudo-node created when placing a valve inline.
    graph = NetworkGraph()
    graph.add_node(Node(id="ResA", node_type="reservoir", elevation_m=10.0, head_m=10.0))
    graph.add_node(Node(id="ValveNode", node_type="valve", elevation_m=12.0))
    # Give the valve node a K factor
    setattr(graph.nodes["ValveNode"], "k_factor", 0.3)
    graph.add_node(Node(id="TankB", node_type="tank", elevation_m=15.0, head_m=15.0))

    # Pipe 1: ResA -> ValveNode (20m, 100mm, 1 elbow K=0.75)
    p1 = PipeEdge(id="P1", from_node="ResA", to_node="ValveNode", length_m=20.0, diameter_mm=100.0, material="commercial_steel")
    p1.add_fitting(Fitting(id="e1", type="elbow_90", label="Elbow 1", k_factor=0.75, count=1))
    graph.add_pipe(p1)

    # Pipe 2: ValveNode -> TankB (30m, 100mm, 1 elbow K=0.75)
    p2 = PipeEdge(id="P2", from_node="ValveNode", to_node="TankB", length_m=30.0, diameter_mm=100.0, material="commercial_steel")
    p2.add_fitting(Fitting(id="e2", type="elbow_90", label="Elbow 2", k_factor=0.75, count=1))
    graph.add_pipe(p2)

    # Check is_genuine_split on ValveNode
    assert not graph.is_genuine_split("ValveNode"), "ValveNode should NOT be considered a genuine split!"
    assert graph.is_genuine_split("ResA"), "ResA must be a genuine split (boundary)!"
    assert graph.is_genuine_split("TankB"), "TankB must be a genuine split (boundary)!"

    # Consolidate graph
    consolidated = graph.consolidate()
    print(f"Consolidated nodes count: {len(consolidated.nodes)} (Expected: 2 -> ResA, TankB)")
    print(f"Consolidated pipes count: {len(consolidated.pipes)} (Expected: 1 -> continuous ResA to TankB)")

    assert len(consolidated.nodes) == 2
    assert "ValveNode" not in consolidated.nodes
    assert len(consolidated.pipes) == 1

    merged_pipe = list(consolidated.pipes.values())[0]
    print(f"Merged pipe: {merged_pipe.id}, from={merged_pipe.from_node}, to={merged_pipe.to_node}")
    print(f"Merged length: {merged_pipe.length_m}m (Expected: 50m)")
    print(f"Merged elevation change: {merged_pipe.elev_change_m}m (Expected: 5m)")
    print(f"Merged fittings count: {len(merged_pipe.fittings)} (Expected: 3 -> elbow1, valve, elbow2)")
    print(f"Merged K_total: {merged_pipe.k_total} (Expected: 0.75 + 0.3 + 0.75 = 1.8)")

    assert abs(merged_pipe.length_m - 50.0) < 1e-6
    assert abs(merged_pipe.elev_change_m - 5.0) < 1e-6
    assert abs(merged_pipe.k_total - 1.8) < 1e-6
    print("Test 2 PASSED!\n")


def test_genuine_splits_preserved():
    print("--- Test 3: Genuine Splits Preserved (Branches, Diameter/Material Transitions) ---")
    graph = NetworkGraph()

    # Case A: True 3-way branching junction
    graph.add_node(Node(id="J_Branch", node_type="junction", elevation_m=5.0))
    graph.add_node(Node(id="Inlet", node_type="reservoir", elevation_m=0.0))
    graph.add_node(Node(id="Outlet1", node_type="discharge", elevation_m=10.0))
    graph.add_node(Node(id="Outlet2", node_type="discharge", elevation_m=12.0))

    graph.add_pipe(PipeEdge(id="P_in", from_node="Inlet", to_node="J_Branch", diameter_mm=150.0))
    graph.add_pipe(PipeEdge(id="P_out1", from_node="J_Branch", to_node="Outlet1", diameter_mm=100.0))
    graph.add_pipe(PipeEdge(id="P_out2", from_node="J_Branch", to_node="Outlet2", diameter_mm=100.0))

    assert graph.is_genuine_split("J_Branch"), "3-way branch must be preserved as genuine split!"

    # Case B: Diameter transition (Reductions) on a 2-pipe line
    graph2 = NetworkGraph()
    graph2.add_node(Node(id="A", node_type="reservoir"))
    graph2.add_node(Node(id="Transition", node_type="junction"))
    graph2.add_node(Node(id="B", node_type="discharge"))

    graph2.add_pipe(PipeEdge(id="P1", from_node="A", to_node="Transition", diameter_mm=150.0, material="commercial_steel"))
    graph2.add_pipe(PipeEdge(id="P2", from_node="Transition", to_node="B", diameter_mm=100.0, material="commercial_steel"))

    assert graph2.is_genuine_split("Transition"), "Diameter transition node must be preserved!"

    # Case C: Material transition on a 2-pipe line
    graph3 = NetworkGraph()
    graph3.add_node(Node(id="A", node_type="reservoir"))
    graph3.add_node(Node(id="MatTransition", node_type="junction"))
    graph3.add_node(Node(id="B", node_type="discharge"))

    graph3.add_pipe(PipeEdge(id="P1", from_node="A", to_node="MatTransition", diameter_mm=100.0, material="commercial_steel"))
    graph3.add_pipe(PipeEdge(id="P2", from_node="MatTransition", to_node="B", diameter_mm=100.0, material="pvc"))

    assert graph3.is_genuine_split("MatTransition"), "Material transition node must be preserved!"
    print("Test 3 PASSED!\n")


def test_hardy_cross_loop_solver():
    print("--- Test 4: Hardy Cross Loop Solver with Consolidated Edges ---")
    # Classical two-loop network:
    # Nodes: N1 (inflow 100 m^3/h), N2, N3, N4, N5, N6 (outflow 100 m^3/h)
    # Loop 1: N1-N2-N5-N4-N1
    # Loop 2: N2-N3-N6-N5-N2
    # All pipes continuous edges with internal fittings!
    graph = NetworkGraph()
    for i in range(1, 7):
        graph.add_node(Node(id=f"N{i}", node_type="junction", elevation_m=0.0))

    # Add pipes
    # Loop 1
    p12 = PipeEdge(id="P12", from_node="N1", to_node="N2", length_m=200.0, diameter_mm=150.0, material="commercial_steel")
    p12.add_fitting(Fitting(type="gate_valve", k_factor=0.2))

    p25 = PipeEdge(id="P25", from_node="N2", to_node="N5", length_m=100.0, diameter_mm=100.0, material="commercial_steel")
    p25.add_fitting(Fitting(type="elbow_90", k_factor=0.75, count=2))

    p54 = PipeEdge(id="P54", from_node="N5", to_node="N4", length_m=200.0, diameter_mm=150.0, material="commercial_steel")
    p41 = PipeEdge(id="P41", from_node="N4", to_node="N1", length_m=100.0, diameter_mm=150.0, material="commercial_steel")

    # Loop 2
    p23 = PipeEdge(id="P23", from_node="N2", to_node="N3", length_m=200.0, diameter_mm=100.0, material="commercial_steel")
    p36 = PipeEdge(id="P36", from_node="N3", to_node="N6", length_m=100.0, diameter_mm=100.0, material="commercial_steel")
    p65 = PipeEdge(id="P65", from_node="N6", to_node="N5", length_m=200.0, diameter_mm=100.0, material="commercial_steel")

    for p in [p12, p25, p54, p41, p23, p36, p65]:
        graph.add_pipe(p)

    # Initial flows satisfying continuity (Q_in = 100 m^3/h = 0.02777 m^3/s)
    q_in = 100.0 / 3600.0
    initial_flows = {
        "P41": -0.5 * q_in,
        "P12": 0.5 * q_in,
        "P25": 0.25 * q_in,
        "P54": -0.5 * q_in,
        "P23": 0.25 * q_in,
        "P36": 0.25 * q_in,
        "P65": -0.25 * q_in,
    }

    loop1 = LoopDefinition(
        loop_id="Loop1",
        pipe_orientations=[("P12", 1), ("P25", 1), ("P54", 1), ("P41", 1)]
    )
    loop2 = LoopDefinition(
        loop_id="Loop2",
        pipe_orientations=[("P23", 1), ("P36", 1), ("P65", 1), ("P25", -1)]
    )

    solver_res = solve_hardy_cross(
        graph,
        loops=[loop1, loop2],
        initial_flows_m3s=initial_flows,
        friction_method="darcy_weisbach",
        max_iterations=30,
        tolerance_m3s=1e-6
    )

    print(f"Hardy Cross converged: {solver_res['converged']} in {solver_res['iterations']} iterations")
    print("Final Flows (m^3/h):", {k: round(v, 2) for k, v in solver_res['flows_m3h'].items()})
    assert solver_res['converged'], "Hardy Cross solver must converge!"
    print("Test 4 PASSED!\n")


if __name__ == "__main__":
    test_minor_loss_accumulation()
    test_pseudo_node_collapsing()
    test_genuine_splits_preserved()
    test_hardy_cross_loop_solver()
    print("ALL TESTS PASSED SUCCESSFULLY!")
