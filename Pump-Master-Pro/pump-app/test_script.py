from app import app
from models import Pump
from routes.curves import api_curve_data
with app.app_context():
    pump = Pump.query.filter_by(name='ISF100x65-200 2P').first()
    # Mocking a request context
    with app.test_request_context('/papi/curve-data/'+str(pump.id)):
        resp = api_curve_data(pump.id)
        data = resp.get_json()
        print("Keys in curve-data:", data.keys())
        if 'family' in data:
            for f in data['family']:
                if f.get('is_max'):
                    print("Max Q[-1]:", f['q'][-1])
        if 'rpm_overlay' in data:
            print("rpm_overlay length:", len(data['rpm_overlay']))
            for r in data['rpm_overlay']:
                print(r['label_tag'], "Q[-1]:", r['q'][-1])