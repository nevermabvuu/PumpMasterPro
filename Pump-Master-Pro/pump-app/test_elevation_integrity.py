"""
test_elevation_integrity.py — Verify Elevation Integrity across network calculations
"""

from services.hydraulic_engine import (
    Node, PipeEdge, NetworkGraph, solve_network
)

def test_elevation_integrity_enforcement():
    print("--- Test: Elevation Integrity Enforcement ---")
    g = NetworkGraph()
    
    # 1. Setup Sump at 0m, Pump at 10m, Discharge at 25m
    n1 = Node(id="N-1", node_type="reservoir", elevation_m=0.0, label="Sump")
    n2 = Node(id="N-2", node_type="pump", elevation_m=10.0, label="Pump 1")
    n3 = Node(id="N-3", node_type="discharge", elevation_m=25.0, label="Discharge")
    
    g.add_node(n1)
    g.add_node(n2)
    g.add_node(n3)
    
    # 2. Setup pipes with deliberately mismatched Delta Z to test backend auto-reconciliation:
    # P-1 claims elev_change_m = 0.0, but N-1 is 0m and N-2 is 10m (True Delta Z = 10m)
    p1 = PipeEdge(id="P-1", from_node="N-1", to_node="N-2", length_m=15.0, diameter_mm=128.2, elev_change_m=0.0)
    # P-2 claims elev_change_m = 5.0, but N-2 is 10m and N-3 is 25m (True Delta Z = 15m)
    p2 = PipeEdge(id="P-2", from_node="N-2", to_node="N-3", length_m=40.0, diameter_mm=102.26, elev_change_m=5.0)
    
    g.add_pipe(p1)
    g.add_pipe(p2)
    
    # Run solve_network
    res = solve_network(g, solver_method='ggm', friction_method='darcy_weisbach', global_flow_m3h=20.0)
    
    # Verify pipe results have reconciled elevation changes
    p1_res = next(p for p in res.pipe_results if p.pipe_id == 'P-1')
    p2_res = next(p for p in res.pipe_results if p.pipe_id == 'P-2')
    
    print(f"P-1 hf_elevation: {p1_res.hf_elevation_m} m (Expected: 10.0 m)")
    print(f"P-2 hf_elevation: {p2_res.hf_elevation_m} m (Expected: 15.0 m)")
    assert abs(p1_res.hf_elevation_m - 10.0) < 1e-3, "P-1 elevation change must equal N-2.elev - N-1.elev (10m)"
    assert abs(p2_res.hf_elevation_m - 15.0) < 1e-3, "P-2 elevation change must equal N-3.elev - N-2.elev (15m)"
    
    # Total elevation head must be 10 + 15 = 25m
    print(f"Total Elevation Head: {res.summary['total_elevation_m']} m (Expected: 25.0 m)")
    assert abs(res.summary['total_elevation_m'] - 25.0) < 1e-3
    
    # Check node results
    n1_res = next(n for n in res.node_results if n.node_id == 'N-1')
    n2_res = next(n for n in res.node_results if n.node_id == 'N-2')
    n3_res = next(n for n in res.node_results if n.node_id == 'N-3')
    
    print(f"Node N-1: Z={n1_res.elevation_m}m, HGL={n1_res.head_m}m, P={n1_res.pressure_kpa}kPa")
    print(f"Node N-2: Z={n2_res.elevation_m}m, HGL={n2_res.head_m}m, P={n2_res.pressure_kpa}kPa")
    print(f"Node N-3: Z={n3_res.elevation_m}m, HGL={n3_res.head_m}m, P={n3_res.pressure_kpa}kPa")
    
    assert abs(n1_res.elevation_m - 0.0) < 1e-3
    assert abs(n2_res.elevation_m - 10.0) < 1e-3
    assert abs(n3_res.elevation_m - 25.0) < 1e-3
    
    print("Elevation Integrity Test PASSED successfully!\n")

if __name__ == '__main__':
    test_elevation_integrity_enforcement()
