import os, sys
_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from app import app
from models import Pump, ReportConfig
from routes.reports import _build_report_curve_context

def test_reports():
    with app.app_context():
        pump = Pump.query.get(9) or Pump.query.first()
        assert pump is not None, "Pump not found"
        
        rep_std = ReportConfig.query.get(1) # Standard datasheet (unit_flow = 'm3h')
        rep_vsd = ReportConfig.query.get(2) # Standard VSD report (unit_flow = 'ls')
        
        print(f"Testing with Pump: {pump.name} (id={pump.id})")
        print(f"Report 1: {rep_std.title}, unit_flow={rep_std.unit_flow}")
        print(f"Report 2: {rep_vsd.title}, unit_flow={rep_vsd.unit_flow}")
        
        # ── TEST 1: Fixed Speed Selection in m3/hr, viewing Standard VSD Report (ID 2) ──
        fixed_sel_params = {
            'pump_id': pump.id,
            'q_duty': 50.0,
            'h_duty': 20.0,
            'unit_q': 'm3h',
            'unit_h': 'm',
            'operation_mode': 'fixed',
            'dia': 185.0,
            'show_duty': '1',
            'show_rated': '1'
        }
        ctx1 = _build_report_curve_context(pump, rep_vsd, params_override=fixed_sel_params)
        print("\n--- TEST 1: Fixed Speed in m3/hr with VSD Report (ID 2) ---")
        print("rep_unit_q:", ctx1['rep_unit_q'])
        print("duty_point:", ctx1['duty_point'])
        print("rated_dia:", ctx1['rated_dia'])
        print("rated_rpm:", ctx1['rated_rpm'])
        assert ctx1['rep_unit_q'] == 'm³/h', f"Expected 'm³/h', got {ctx1['rep_unit_q']}"
        assert ctx1['duty_point'] is not None, "Duty point should exist"
        assert '50.0 m³/h' in ctx1['duty_point']['label'], f"Duty label mismatch: {ctx1['duty_point']['label']}"
        assert ctx1['rated_dia'] is not None, "Rated diameter should be present for fixed speed"
        assert ctx1['rated_rpm'] is None, "Rated RPM should be None for fixed speed"
        print("TEST 1 PASSED!")

        # ── TEST 2: Variable Speed Selection in L/s, viewing Standard Datasheet (ID 1) ──
        vsd_sel_params = {
            'pump_id': pump.id,
            'q_duty': 25.0,
            'h_duty': 18.0,
            'unit_q': 'ls',
            'unit_h': 'm',
            'operation_mode': 'vsd',
            'rpm': 1350.0,
            'show_duty': '1',
            'show_rated': '1'
        }
        ctx2 = _build_report_curve_context(pump, rep_std, params_override=vsd_sel_params)
        print("\n--- TEST 2: VSD in L/s with Standard Report (ID 1) ---")
        print("rep_unit_q:", ctx2['rep_unit_q'])
        print("duty_point:", ctx2['duty_point'])
        print("rated_dia:", ctx2['rated_dia'])
        print("rated_rpm:", ctx2['rated_rpm'])
        assert ctx2['rep_unit_q'] == 'L/s', f"Expected 'L/s', got {ctx2['rep_unit_q']}"
        assert ctx2['duty_point'] is not None, "Duty point should exist"
        assert '25.0 L/s' in ctx2['duty_point']['label'], f"Duty label mismatch: {ctx2['duty_point']['label']}"
        assert ctx2['rated_rpm'] is not None, "Rated RPM should be present for VSD"
        print("TEST 2 PASSED!")

        # ── TEST 3: Catalogue View of Pump (source='catalogue') on Report 1 ──
        cat_params = {'source': 'catalogue'}
        ctx3 = _build_report_curve_context(pump, rep_std, params_override=cat_params)
        print("\n--- TEST 3: Catalogue View on Standard Report (ID 1) ---")
        print("rep_unit_q:", ctx3['rep_unit_q'])
        print("duty_point:", ctx3['duty_point'])
        print("rated_dia:", ctx3['rated_dia'])
        print("rated_rpm:", ctx3['rated_rpm'])
        print("is_from_catalogue:", ctx3.get('is_from_catalogue'))
        assert ctx3['is_from_catalogue'] is True, "Expected is_from_catalogue True"
        assert ctx3['rep_unit_q'] == 'm³/h', f"Catalogue should respect report unit 'm³/h', got {ctx3['rep_unit_q']}"
        assert ctx3['duty_point'] is None, "Catalogue report MUST NOT plot duty point"
        assert ctx3['rated_dia'] is None, "Catalogue report MUST NOT have rated_dia"
        assert ctx3['rated_rpm'] is None, "Catalogue report MUST NOT have rated_rpm"
        print("TEST 3 PASSED!")

        # ── TEST 4: Catalogue View of Pump (source='catalogue') on Report 2 (VSD Report) ──
        ctx4 = _build_report_curve_context(pump, rep_vsd, params_override=cat_params)
        print("\n--- TEST 4: Catalogue View on VSD Report (ID 2) ---")
        print("rep_unit_q:", ctx4['rep_unit_q'])
        print("duty_point:", ctx4['duty_point'])
        print("rated_dia:", ctx4['rated_dia'])
        print("rated_rpm:", ctx4['rated_rpm'])
        assert ctx4['is_from_catalogue'] is True, "Expected is_from_catalogue True"
        assert ctx4['rep_unit_q'] == 'L/s', f"Catalogue should respect report unit 'L/s', got {ctx4['rep_unit_q']}"
        assert ctx4['duty_point'] is None, "Catalogue report MUST NOT plot duty point"
        assert ctx4['rated_dia'] is None, "Catalogue report MUST NOT have rated_dia"
        assert ctx4['rated_rpm'] is None, "Catalogue report MUST NOT have rated_rpm"
        print("TEST 4 PASSED!")

        # ── TEST 5: HTTP Endpoints testing with Flask test client ──
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['active_selection'] = fixed_sel_params
            
            # View clean report -> should use selection units (m3/h) even if report 2 is selected
            res = client.post('/reports/api/set-active-report', json={'report_id': 2})
            assert res.status_code == 200
            res = client.get('/reports/view')
            html = res.data.decode('utf-8')
            assert 'Flow (m³/h)' in html, "Report view should have Flow (m³/h)"
            assert 'Duty: 50.0 m³/h' in html, "Report view should display Duty: 50.0 m³/h"
            print("\n--- HTTP Clean Report View Test: PASSED! Flow (m³/h) and Duty: 50.0 m³/h present")

            # Catalogue view of pump 9 via /reports/view/1/pump/9?source=catalogue
            # Even though session has active_selection for pump 9, source='catalogue' must omit duty point and rated curve!
            res_cat = client.get(f'/reports/view/1/pump/{pump.id}?source=catalogue')
            html_cat = res_cat.data.decode('utf-8')
            assert 'Duty Point' not in html_cat or '⏱ Technical Summary' in html_cat
            assert '🎯 Operating Duty Point' not in html_cat, "Catalogue view must not show '🎯 Operating Duty Point'"
            assert 'BEP Flow / Duty' in html_cat, "Catalogue view must show 'BEP Flow / Duty'"
            assert '(Rated)' not in html_cat, "Catalogue view must not show '(Rated)'"
            print("--- HTTP Catalogue View Test: PASSED! No duty point or rated curve plotted, BEP displayed")

        print("\nALL BACKEND TESTS PASSED CLEANLY!")

if __name__ == '__main__':
    test_reports()
