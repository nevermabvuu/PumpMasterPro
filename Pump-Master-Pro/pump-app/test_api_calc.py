import json
from app import app

client = app.test_client()

# Set logged-in session
with client.session_transaction() as sess:
    sess['user_id'] = 1
    sess['user_name'] = 'Admin'

payload_dw = {
    "flow_m3h": 25.0,
    "friction_method": "darcy_weisbach",
    "nodes": [
        {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0}},
        {"id": "N-2", "type": "valve", "props": {"fitting_key": "gate_valve_open", "k_factor": 0.2}},
        {"id": "N-3", "type": "tank", "props": {"elevation_m": 10}}
    ],
    "pipes": [
        {"id": "P-1", "fromNodeId": "N-1", "toNodeId": "N-2", "diameter_mm": 100, "length_m": 40, "material": "commercial_steel", "fittings": ["elbow_90_standard"]},
        {"id": "P-2", "fromNodeId": "N-2", "toNodeId": "N-3", "diameter_mm": 100, "length_m": 60, "material": "commercial_steel", "fittings": ["elbow_90_standard"]}
    ]
}

resp_dw = client.post("/api/pipe-network/calculate", json=payload_dw)
assert resp_dw.status_code == 200, f"Error: {resp_dw.data}"
data_dw = resp_dw.get_json()

print("=== Darcy-Weisbach Test ===")
print("Summary:", data_dw["summary"])
print("Consolidated Results Count:", len(data_dw["results"]))
for r in data_dw["results"]:
    print(f"  Pipe {r['id']}: L={r['length_m']}m, K_total={r['K_total']}, R={r['resistance_R']}, n={r['flow_exponent_n']}, hf_major={r['hf_major_m']}m, hf_minor={r['hf_minor_m']}m, hf_friction={r['hf_friction_m']}m")

assert len(data_dw["results"]) == 1, f"Expected 1 consolidated continuous pipe, got {len(data_dw['results'])}"
pipe_res = data_dw["results"][0]
assert abs(pipe_res["length_m"] - 100.0) < 1e-4, f"Expected length 100m, got {pipe_res['length_m']}"
assert pipe_res["flow_exponent_n"] == 2.0, "Expected n=2.0 for Darcy-Weisbach"
assert pipe_res.get("flow_m3h") == 25.0, f"Expected flow_m3h=25.0, got {pipe_res.get('flow_m3h')}"
assert "pressure_kpa" in pipe_res, "Expected pressure_kpa in pipe_res"
print(f"  Verified flow_m3h={pipe_res['flow_m3h']} m3/h, pressure_kpa={pipe_res['pressure_kpa']} kPa, pressure_in_kpa={pipe_res.get('pressure_in_kpa')}, pressure_out_kpa={pipe_res.get('pressure_out_kpa')}")

# Now Hazen-Williams
payload_hw = dict(payload_dw)
payload_hw["friction_method"] = "hazen_williams"
resp_hw = client.post("/api/pipe-network/calculate", json=payload_hw)
assert resp_hw.status_code == 200, f"Error: {resp_hw.data}"
data_hw = resp_hw.get_json()

print("\n=== Hazen-Williams Test ===")
print("Summary:", data_hw["summary"])
for r in data_hw["results"]:
    print(f"  Pipe {r['id']}: L={r['length_m']}m, K_total={r['K_total']}, R={r['resistance_R']}, n={r['flow_exponent_n']}, hf_major={r['hf_major_m']}m, hf_minor={r['hf_minor_m']}m, hf_friction={r['hf_friction_m']}m")

pipe_res_hw = data_hw["results"][0]
assert abs(pipe_res_hw["length_m"] - 100.0) < 1e-4, f"Expected length 100m, got {pipe_res_hw['length_m']}"
assert pipe_res_hw["flow_exponent_n"] == 1.852, "Expected n=1.852 for Hazen-Williams"

# Test all 4 Network Analysis Solvers
print("\n=== Testing All 4 Network Analysis Solvers via API ===")
solvers = ['ggm', 'newton_raphson', 'hardy_cross', 'linear_theory']
for sm in solvers:
    p = dict(payload_dw)
    p["solver_method"] = sm
    resp = client.post("/api/pipe-network/calculate", json=p)
    assert resp.status_code == 200, f"Error for solver {sm}: {resp.data}"
    d = resp.get_json()
    assert d["summary"]["solver_method"] == sm
    assert d["summary"]["converged"] is True
    assert "node_results" in d and len(d["node_results"]) > 0
    print(f"  Solver {sm.upper()}: {d['summary']['solver_name']} -> converged in {d['summary']['iterations']} iters, TDH={d['summary']['total_system_head_m']}m, {len(d['node_results'])} nodes")

print("\nAPI CALCULATION TESTS PASSED COMPLETELY FOR ALL SOLVERS!")

