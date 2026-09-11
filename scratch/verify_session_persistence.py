import sys, os, json
sys.path.insert(0, os.path.abspath('Pump-Master-Pro/pump-app'))
from app import app

client = app.test_client()

# Set up authenticated session
with client.session_transaction() as sess:
    sess['user_id'] = 1

# Step 1: User creates a pipe network with a pump
network_data = {
    'version': 2,
    'nodes': [
        {
            'id': 'N-1',
            'type': 'pump',
            'x': 260,
            'y': 320,
            'props': {
                'label': 'Booster Pump A',
                'flow_m3h': 42.5,
                'elevation_m': 3.0,
                'pump_config': 'end_suction'
            }
        },
        {
            'id': 'N-2',
            'type': 'tank',
            'x': 600,
            'y': 150,
            'props': {
                'label': 'Header Tank',
                'elevation_m': 15.0
            }
        }
    ],
    'pipes': [
        {
            'id': 'P-1',
            'fromNodeId': 'N-1',
            'toNodeId': 'N-2',
            'props': {
                'label': 'Discharge Pipe',
                'diameter_mm': 100.0,
                'length_m': 50.0,
                'elev_change_m': 12.0,
                'material': 'commercial_steel',
                'fittings': ['elbow_90_standard', 'gate_valve_open']
            }
        }
    ],
    'globalFlow': 42.5,
    'nextId': 3
}

# Step 2: Save to server session['active_selection']
save_res = client.post('/api/pipe-network/save', json=network_data)
assert save_res.status_code == 200, f'Save failed: {save_res.status_code}'
save_json = save_res.get_json()
assert save_json['status'] == 'ok'
active_sel = save_json['active_selection']
print('[PASS] Save endpoint returned 200 and active_selection')
assert active_sel['q_duty'] == 42.5
assert active_sel['disp_q_duty'] == 42.5
assert active_sel['pump_config'] == 'end_suction'
assert active_sel['pipe_network']['nodes'][0]['props']['label'] == 'Booster Pump A'
print('[PASS] session active_selection verified with pump, flow, and network graph')

# Step 3: Check GET /api/pipe-network/session
sess_res = client.get('/api/pipe-network/session')
assert sess_res.status_code == 200
sess_data = sess_res.get_json()
assert sess_data['pipe_network']['nodes'][0]['props']['label'] == 'Booster Pump A'
print('[PASS] GET /api/pipe-network/session verified')

# Step 4: Navigate to /pump-selection
sel_res = client.get('/pump-selection')
assert sel_res.status_code == 200
sel_html = sel_res.get_data(as_text=True)
assert 'Booster Pump A' in sel_html
print('[PASS] /pump-selection rendered with preserved pipe_network in session')

# Step 5: Navigate back to /pipe-network
pn_res = client.get('/pipe-network')
assert pn_res.status_code == 200
pn_html = pn_res.get_data(as_text=True)
assert 'Booster Pump A' in pn_html
assert 'window.__PMP_SESSION_PIPE_NETWORK' in pn_html
print('[PASS] /pipe-network rendered with window.__PMP_SESSION_PIPE_NETWORK containing Booster Pump A')

# Step 6: Test calculate network
calc_res = client.post('/api/pipe-network/calculate', json=network_data)
assert calc_res.status_code == 200
calc_json = calc_res.get_json()
assert 'summary' in calc_json
total_h = calc_json['summary']['total_system_head_m']
print(f'[PASS] Calculation successful: total head = {total_h} m')

# Verify active_selection was updated with calculation results
with client.session_transaction() as sess:
    current_sel = sess.get('active_selection')
    assert current_sel is not None
    assert 'h_duty' in current_sel
    assert current_sel['h_duty'] == round(total_h, 3)
    print(f'[PASS] Calculation results auto-synced to session active_selection: h_duty={current_sel["h_duty"]}, q_duty={current_sel["q_duty"]}')

print('\n=== ALL END-TO-END CHECKS PASSED SUCCESSFULLY ===')
