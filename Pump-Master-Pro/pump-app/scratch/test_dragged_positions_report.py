import sys
import os

sys.path.insert(0, r"c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app")

from app import app
from models import Pump, ReportConfig
from routes.reports import generate_chart_svg

with app.app_context():
    pump = Pump.query.first()
    report = ReportConfig.query.first() or ReportConfig()

    custom_pos = {
        'eta_75': {'x': 120.0, 'y': 25.0},
        'pow_15': {'x': 110.0, 'y': 15.0},
        '228 mm': {'x': 130.0, 'y': 35.0}
    }
    if pump:
        pump.set_custom_label_pos(custom_pos)

    curves = [{'label': '228 mm', 'x': [0, 50, 100, 150], 'y': [50, 45, 35, 20]}]
    isolines = [{'label': '75%', 'x': [0, 50, 100, 150], 'y': [10, 20, 25, 20], 'color': '#059669'}]

    svg_out = generate_chart_svg(
        curves, custom_range={'x_min': 0, 'x_max': 200, 'y_min': 0, 'y_max': 60},
        width=480, height=240, isolines_list=isolines,
        legend_mode='curve_labels', custom_label_pos=custom_pos, label_format='simple'
    )

    print("=================== DRAGGED POSITIONS REPORT TEST ===================")
    print("SVG generated successfully, length:", len(svg_out))
    print("Isoline label in SVG:", '75%' in svg_out)
    print("Curve label in SVG:", '228 mm' in svg_out)

print("\nTEST COMPLETE!")
