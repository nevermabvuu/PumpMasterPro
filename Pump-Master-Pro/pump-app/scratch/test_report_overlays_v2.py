import sys
import os

sys.path.insert(0, r"c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app")

from app import app
from models import Pump, ReportConfig
from routes.reports import _build_report_curve_context

with app.app_context():
    isf = Pump.query.filter_by(family_type='trimmed_impeller').first()
    vs = Pump.query.filter_by(family_type='variable_speed').first()

    report = ReportConfig.query.first() or ReportConfig()
    report.legend_mode = 'curve_labels'
    report.show_rpm_overlay = True
    report.show_dia_overlay = True

    print("=================== REPORT OVERLAYS & LABELS TEST ===================")
    if isf:
        print(f"\n1. ISF Pump: {isf.model_number}")
        ctx_isf = _build_report_curve_context(isf, report)
        print(f"   SVG HQ Length: {len(ctx_isf['svg_hq'])}")
        print(f"   SVG Efficiency Length: {len(ctx_isf['svg_eta'])}")
        print(f"   SVG Power Length: {len(ctx_isf['svg_pow'])}")
        print(f"   SVG NPSH Length: {len(ctx_isf['svg_npsh'])}")
        print(f"   Contains RPM in Efficiency SVG: {'RPM' in ctx_isf['svg_eta']}")
        print(f"   Contains Diameter in Efficiency SVG: {'mm' in ctx_isf['svg_eta']}")

    if vs:
        print(f"\n2. VS Pump: {vs.model_number}")
        ctx_vs = _build_report_curve_context(vs, report)
        print(f"   SVG HQ Length: {len(ctx_vs['svg_hq'])}")
        print(f"   SVG Efficiency Length: {len(ctx_vs['svg_eta'])}")
        print(f"   SVG Power Length: {len(ctx_vs['svg_pow'])}")
        print(f"   SVG NPSH Length: {len(ctx_vs['svg_npsh'])}")
        print(f"   Contains RPM in Power SVG: {'RPM' in ctx_vs['svg_pow']}")
        print(f"   Contains Diameter in Power SVG: {'mm' in ctx_vs['svg_pow']}")

print("\nTEST COMPLETE!")
