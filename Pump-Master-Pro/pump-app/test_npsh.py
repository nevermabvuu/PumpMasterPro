from app import app
from models import Pump
from pump_curves import warman_chart_data, npsh_isolines, _compute_iso_override
import json

with app.app_context():
    pump = Pump.query.filter_by(name='ISF').first() or Pump.query.first()
    
    # Simulate JS API endpoint
    w_data = warman_chart_data(pump, liquid='water', rho=1000.0, show_rpm_overlay=False, show_dia_overlay=False)
    js_npsh = w_data.get('npsh_isolines', [])
    
    # Simulate reports.py
    iso_r_min, iso_trim = _compute_iso_override(pump, False, False)
    rep_npsh = npsh_isolines(pump, override_r_min=iso_r_min)
    
    print("JS NPSH len:", len(js_npsh))
    print("JS NPSH:", js_npsh)
    
    print("REP NPSH len:", len(rep_npsh))
    print("REP NPSH:", rep_npsh)
