import sys
import os
sys.path.insert(0, r'c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app')

from app import app
from models import Pump

client = app.test_client()

print("--- STARTING SYSTEMATIC ROUTE TESTING ---")

# 1. Test POST /pump-data/new with blank fields (optional floats and strings)
post_pump_data = {
    'name': 'Robust Test Pump',
    'manufacturer': '',
    'model_number': '',
    'size': '',
    'speed_rpm': '',  # blank, should fall back to default
    'impeller_dia_mm': '',  # blank, should fall back to default
    'impeller_diameters': '',
    'hq_a0': '45.0',
    'hq_a1': '',  # blank
    'hq_a2': '',  # blank
    'hq_a3': '',  # blank
    'eff_b0': '75.0',
    'eff_b1': '',  # blank
    'eff_b2': '',  # blank
    'eff_b3': '',  # blank
    'npsh_c0': '',  # blank
    'npsh_c1': '',  # blank
    'npsh_c2': '',  # blank
    'pow_p0': '',  # blank
    'pow_p1': '',  # blank
    'pow_p2': '',  # blank
    'q_min': '',  # blank
    'q_max': '120.0',
    'q_bep': '',  # blank
    'hr': '',  # blank
    'qr': '',  # blank
    'er': '',  # blank
    'pump_type': '',
    'application': '',
    'notes': ''
}
res = client.post('/pump-data/new', data=post_pump_data)
print("1. POST /pump-data/new (empty fields):", res.status_code)
assert res.status_code == 302 or res.status_code == 200, f"Failed: {res.status_code}"

# 2. Test POST /pump-selection with blank fields (optional floats)
post_selection_data = {
    'q_duty': '60',
    'h_duty': '25',
    'npsh_avail': '',  # blank optional
    'liquid': 'viscous',
    'rho': '',  # blank optional
    'viscosity_cSt': '',  # blank optional
    'slurry_cv': '',  # blank optional
    'slurry_d50': '',  # blank optional
    'rho_solid': ''  # blank optional
}
res = client.post('/pump-selection', data=post_selection_data)
print("2. POST /pump-selection (empty fields):", res.status_code)
assert res.status_code == 200, f"Failed: {res.status_code}"

# 3. Test GET /papi/curve-data/1 with empty query parameters
res = client.get('/papi/curve-data/1?rho=&viscosity_cSt=&slurry_cv=&static_head=&pipe_k=')
print("3. GET /papi/curve-data/1 (empty query params):", res.status_code)
assert res.status_code == 200, f"Failed: {res.status_code}"

# 4. Test GET /papi/warman-chart/1 with empty query parameters
res = client.get('/papi/warman-chart/1?rho=&viscosity_cSt=&slurry_cv=&static_head=&pipe_k=')
print("4. GET /papi/warman-chart/1 (empty query params):", res.status_code)
assert res.status_code == 200, f"Failed: {res.status_code}"

# 5. Test GET /papi/compare-pumps with empty query parameters
res = client.get('/papi/compare-pumps?ids=1&rho=&viscosity_cSt=&slurry_cv=')
print("5. GET /papi/compare-pumps (empty query params):", res.status_code)
assert res.status_code == 200, f"Failed: {res.status_code}"

# 6. Test POST /papi/select-pumps JSON with empty/null/missing attributes
res = client.post('/papi/select-pumps', json={
    'q_duty': 50,
    'h_duty': 20,
    'npsh_avail': '',
    'rho': None,
    'viscosity_cSt': '',
    'slurry_cv': None
})
print("6. POST /papi/select-pumps JSON (empty/null attributes):", res.status_code)
assert res.status_code == 200, f"Failed: {res.status_code}"

print("--- ALL TESTS COMPLETED SUCCESSFULLY! NO CRASHES DETECTED. ---")
