import sys
sys.path.insert(0, r"c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app")
from app import app
from models import User

with app.app_context():
    u = User.query.first()
    uid = u.id if u else 1

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = uid

    # 1. Test Power
    res = client.post('/api/calc/power', json={'flow': 100, 'head': 50, 'eta': 75, 'unit_q': 'm3h', 'unit_h': 'm', 'unit_pow': 'kw'})
    print("Power:", res.status_code, res.get_json())
    assert res.status_code == 200 and res.get_json()['success'] is True

    # 2. Test Batch Power
    res = client.post('/api/calc/batch-power', json={'rows': [{'q': 50, 'h': 40, 'eta': 70}, {'q': 100, 'h': 35, 'eta': 75}]})
    print("Batch Power:", res.status_code, res.get_json())
    assert res.status_code == 200 and len(res.get_json()['results']) == 2

    # 3. Test Affinity Curve
    res = client.post('/api/calc/affinity-curve', json={
        'points': [{'q': 100, 'h': 50, 'eta': 75, 'power': 18.1, 'npsh': 3.2}],
        'affinity_type': 'diameter',
        'base_dia_mm': 300,
        'target_dia_mm': 270
    })
    print("Affinity Curve:", res.status_code, res.get_json())
    assert res.status_code == 200 and res.get_json()['ratio'] == 0.9

    # 4. Test Slurry Properties
    res = client.post('/api/calc/slurry-properties', json={
        'c_weight_pct': 30,
        'solids_sg': 2.65,
        'liquid_sg': 1.0,
        'd50_mm': 0.2,
        'pipe_d_mm': 150
    })
    print("Slurry Properties:", res.status_code, res.get_json())
    assert res.status_code == 200 and res.get_json()['slurry_sg'] > 1.0

    # 5. Test System Curve
    res = client.post('/api/calc/system-curve', json={'q_duty': 120, 'h_duty': 45, 'h_static': 10})
    print("System Curve:", res.status_code, res.get_json())
    assert res.status_code == 200 and len(res.get_json()['q_points']) > 10

    # 6. Test Vapor Pressure
    res = client.post('/api/calc/vapor-pressure', json={'temperature_c': 25.0})
    print("Vapor Pressure:", res.status_code, res.get_json())
    assert res.status_code == 200 and res.get_json()['vapor_pressure_kpa'] > 0

    print("ALL CALCULATION API ENDPOINT TESTS PASSED SUCCESSFULLY!")
