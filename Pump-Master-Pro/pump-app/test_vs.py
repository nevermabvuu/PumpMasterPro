from app import app
from models import Pump, Report
from routes.reports import _build_report_curve_context
with app.app_context():
    pump = Pump.query.filter_by(name='VS150S-METAL').first() or Pump.query.filter_by(name='VS').first() or Pump.query.first()
    rep = Report.query.filter_by(pump_id=pump.id).first()
    
    # Let's mock what reports.py does for curves
    import numpy as np
    q_max = pump.q_max if hasattr(pump, 'q_max') and pump.q_max and pump.q_max > 0 else 200.0
    q_pts = list(np.linspace(pump.q_min or 0.0, q_max, 60))
    print(f"q_pts length: {len(q_pts)}, min: {q_pts[0]}, max: {q_pts[-1]}")
    
    rpm_list = [1000, 900, 800, 700, 600, 500]
    base_rpm = pump.speed_rpm if getattr(pump, 'speed_rpm', 0) > 0 else 1000.0
    
    for c_idx, rpm_val in enumerate(rpm_list):
        k = rpm_val / base_rpm if base_rpm > 0 else 1.0
        c_q = [round(v * k, 2) for v in q_pts]
        print(f"RPM {rpm_val}: k={k}, c_q max={c_q[-1]}")
