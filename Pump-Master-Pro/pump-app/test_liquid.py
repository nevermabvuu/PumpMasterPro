from app import app
from models import Pump
from pump_curves import warman_chart_data, npsh_isolines, _compute_iso_override

with app.app_context():
    pump = Pump.query.filter_by(name='ISF').first() or Pump.query.first()
    
    rep = pump.reports[0] if pump.reports else None
    
    print("Pump Liquid:", pump.test_basis)
    print("Pump Slurry CV:", pump.slurry_cv)
    print("Report Liquid:", rep.liquid if rep else "No report")
