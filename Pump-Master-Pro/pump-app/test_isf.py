from app import app
from models import Pump
from pump_curves import speed_lines as calc_speed_lines
with app.app_context():
    pump = Pump.query.filter_by(name='ISF100x65-200 2P').first() or Pump.query.filter_by(name='ISF').first() or Pump.query.first()
    print('ISF rpm:', pump.speed_rpm)
    rpm_str = getattr(pump, 'graph_rpm_values', '') or '2900,2100,1450,750'
    spd_objs = calc_speed_lines(pump, values_str=rpm_str)
    for sl in spd_objs:
        q_max = max(sl['q'])
        print(f"{sl['label']} ends at Q={q_max}")
