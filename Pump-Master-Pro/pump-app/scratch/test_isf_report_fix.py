import sys, os
sys.path.insert(0, r"c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app")

from app import app
from models import Pump, ReportConfig
from routes.reports import _build_report_curve_context

with app.app_context():
    # Find ISF pump or fallback to first pump
    pump = Pump.query.filter(Pump.name.like('%ISF%')).first() or Pump.query.first()
    report = ReportConfig.query.first() or ReportConfig()

    print(f"Testing with Pump: {pump.name} (ID: {pump.id}, Family: {pump.family_type})")
    
    context = _build_report_curve_context(pump, report)
    
    print("\n--- CURVE COUNTS IN SUB-CHARTS ---")
    print("HQ Curves Count:", len(context.get('hq_curves', [])))
    print("ETA Curves Count:", len(context.get('eta_curves', [])))
    print("POW Curves Count:", len(context.get('pow_curves', [])))
    print("NPSH Curves Count:", len(context.get('npsh_curves', [])))
    
    svg_hq = context.get('svg_hq', '')
    svg_eta = context.get('svg_eta', '')
    svg_pow = context.get('svg_pow', '')
    svg_npsh = context.get('svg_npsh', '')
    
    print("\n--- LEGEND PRESENCE IN SVGs ---")
    print("SVG HQ contains legend rect:", '<rect x="' in svg_hq and 'stroke="#cbd5e1"' in svg_hq)
    print("SVG ETA contains legend rect:", '<rect x="' in svg_eta and 'stroke="#cbd5e1"' in svg_eta)
    print("SVG POW contains legend rect:", '<rect x="' in svg_pow and 'stroke="#cbd5e1"' in svg_pow)
    print("SVG NPSH contains legend rect:", '<rect x="' in svg_npsh and 'stroke="#cbd5e1"' in svg_npsh)

print("\nISF TEST COMPLETED SUCCESSFULLY!")
