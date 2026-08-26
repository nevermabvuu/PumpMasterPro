from app import app
from models import Pump, ReportConfig
from routes.reports import _build_report_curve_context
import json

with app.app_context():
    pump = Pump.query.filter_by(name='ISF100x65-200 2P').first()
    class MockReport:
        show_dia_overlay = False
        show_rpm_overlay = True
        show_speed_lines = True
        show_family = False
        curve_display_mode = 'all'
        primary_color = '#1e3a8a'
        unit_power = 'kw'
        unit_npsh = 'm'
        unit_flow = 'ls'
        unit_head = 'm'
        power_isolines = '10, 16, 20, 30'
        eff_isolines = '30, 40, 60, 80, 75, 78'
        show_eff_isolines = True
        show_power_isolines = True
    
    import routes.reports
    _original_generate = routes.reports.generate_chart_svg
    
    def mock_generate(curves_list, *args, **kwargs):
        if kwargs.get('chart_type') == 'hq':
            c = curves_list[0]
            print("HQ Y values:", c['y'][:10])
        return _original_generate(curves_list, *args, **kwargs)
        
    routes.reports.generate_chart_svg = mock_generate
    ctx = _build_report_curve_context(pump, MockReport())