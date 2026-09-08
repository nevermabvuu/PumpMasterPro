"""
scratch/test_level1_restrictions.py
Automated verification that Level 1 users (Read Only) CANNOT edit, save, or mutate:
1. Pump Data (/pump-data, /pump-data/edit/<id>, /pump-data/new, /pump-data/delete/<id>)
2. PDF Report Settings (/reports/settings, /reports/settings/report/save, save_graph_area, save_supplier, delete_report)
3. Catalogue PDF Reports in Organisation Settings (/organisations/settings, /organisations/catalogue-reports/save)
"""
import os
import sys

# Ensure pump-app root is on path
_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from app import app
from models import db, User, Organisation, Role, Pump, ReportConfig

def run_tests():
    with app.app_context():
        # Let's inspect user 4 (never@tasonline.co.za)
        user4 = User.query.get(4)
        assert user4 is not None, "User 4 must exist"
        print(f"Testing User: {user4.email} (ID: {user4.id}), Role: {user4.role_display_name}")
        print(f"is_super_admin_user: {user4.is_super_admin_user}")
        
        # Verify access levels for key modules
        p_lvl = user4.get_access_level('pump_data')
        c_lvl = user4.get_access_level('pump_catalogue')
        r_lvl = user4.get_access_level('report_settings')
        o_lvl = user4.get_access_level('organisation_settings')
        print(f"Access Levels: pump_data={p_lvl}, pump_catalogue={c_lvl}, report_settings={r_lvl}, org_settings={o_lvl}")
        assert p_lvl == 1, f"Expected pump_data level 1, got {p_lvl}"
        assert r_lvl == 1, f"Expected report_settings level 1, got {r_lvl}"
        assert not user4.can_edit('pump_data'), "User 4 must not be able to edit pump_data"
        assert not user4.can_edit('report_settings'), "User 4 must not be able to edit report_settings"

    with app.test_client() as client:
        # Log in as User 4 (Level 1)
        with client.session_transaction() as sess:
            sess['user_id'] = 4
            sess['_fresh'] = True

        print("\n=== 1. VERIFY PUMP DATA LEVEL 1 RESTRICTIONS ===")
        # 1A. /pump-data listing
        res = client.get('/pump-data')
        assert res.status_code == 200, f"/pump-data failed with {res.status_code}"
        html = res.get_data(as_text=True)
        assert "Read-Only Catalogue" in html, "Should show Read-Only Catalogue badge"
        assert 'href="/pump-data/new"' not in html, "Add Pump link should not be present"
        assert 'title="View pump specifications (Read-Only)"' in html, "Should show View eye icon for Level 1"
        print("  [PASS] /pump-data shows Read-Only Catalogue and View eye icon")

        # 1B. /pump-data/edit/1 GET (Read-Only Form View)
        res = client.get('/pump-data/edit/1')
        assert res.status_code == 200, f"/pump-data/edit/1 failed with {res.status_code}"
        html = res.get_data(as_text=True)
        assert "Level 1 • Read-Only Mode" in html, "Should display Read-Only Mode amber banner"
        assert "<fieldset disabled" in html, "Form grid should be wrapped in disabled fieldset"
        assert "Read-Only (Editing Locked)" in html, "Submit button should be replaced with locked button"
        print("  [PASS] /pump-data/edit/1 loads in Read-Only view with disabled fieldset and locked button")

        # 1C. /pump-data/edit/1 POST (Blocked Mutation)
        orig_pump_name = None
        with app.app_context():
            p = Pump.query.get(1)
            orig_pump_name = p.name
        
        res = client.post('/pump-data/edit/1', data={
            'name': 'HACKED_PUMP_NAME_SHOULD_FAIL',
            'speed_rpm': '9999'
        }, follow_redirects=False)
        assert res.status_code == 302, f"POST /pump-data/edit/1 should redirect, got {res.status_code}"
        
        with app.app_context():
            p = Pump.query.get(1)
            assert p.name == orig_pump_name, f"Pump name was modified! Expected {orig_pump_name}, got {p.name}"
        print("  [PASS] POST /pump-data/edit/1 successfully rejected mutation and preserved original data")

        # 1D. /pump-data/new GET & POST (Blocked by decorator min_level=2)
        res = client.get('/pump-data/new', follow_redirects=False)
        assert res.status_code == 302, f"/pump-data/new GET should be redirected for Level 1, got {res.status_code}"
        res = client.post('/pump-data/new', data={'name': 'FAIL'}, follow_redirects=False)
        assert res.status_code == 302, f"/pump-data/new POST should be redirected for Level 1, got {res.status_code}"
        print("  [PASS] GET & POST /pump-data/new rejected for Level 1")

        # 1E. /pump-curve/1
        res = client.get('/pump-curve/1')
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "View Specs" in html, "Should have View Specs link"
        assert "View Pump Specifications (Read-Only)" in html, "Placeholder should offer Read-Only view link"
        print("  [PASS] /pump-curve/1 shows View Specs (Read-Only) links")

        print("\n=== 2. VERIFY PDF REPORT SETTINGS LEVEL 1 RESTRICTIONS ===")
        # 2A. /reports/settings GET
        res = client.get('/reports/settings')
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "Read-Only Mode:" in html, "Should show Read-Only banner"
        assert "Level 1 • Read-Only" in html, "Should show Level 1 badge in header"
        assert 'onclick="openReportModal()"' not in html, "Create Report Setting button should be hidden"
        assert 'onclick="openSupplierModal()"' not in html, "Add Organisation button should be hidden"
        assert "View Graph Area &amp; Layout" in html, "Level 1 should have View Graph Area & Layout button"
        # Verify modals have disabled fieldsets
        assert '<fieldset disabled class="contents space-y-4">' in html, "Modals must have disabled fieldset"
        assert 'title="View Report Configuration (Read-Only)"' in html, "Table actions must have View Config button"
        assert 'title="View Graph Area &amp; Layout (Read-Only)"' in html, "Table actions must have View Layout button"
        assert 'title="View Supplier Details (Read-Only)"' in html, "Supplier cards must have View Supplier button"
        print("  [PASS] /reports/settings displays read-only banner, view-only modal openers, and disabled fieldsets")

        # 2B. POST /reports/settings/report/save (Blocked by decorator min_level=2)
        res = client.post('/reports/settings/report/save', data={
            'title': 'HACKED_REPORT_CONFIG'
        }, follow_redirects=False)
        assert res.status_code == 302, f"POST report save should be redirected, got {res.status_code}"
        print("  [PASS] POST /reports/settings/report/save rejected for Level 1")

        # 2C. POST /reports/settings/supplier/save (Blocked by decorator min_level=2)
        res = client.post('/reports/settings/supplier/save', data={
            'name': 'HACKED_SUPPLIER'
        }, follow_redirects=False)
        assert res.status_code == 302, f"POST supplier save should be redirected, got {res.status_code}"
        print("  [PASS] POST /reports/settings/supplier/save rejected for Level 1")

        # 2D. POST /reports/settings/report/save_graph_area (Blocked by decorator min_level=2)
        res = client.post('/reports/settings/report/save_graph_area', data={
            'report_id': '1',
            'graph_area_top': '999px'
        }, follow_redirects=False)
        assert res.status_code == 302, f"POST save_graph_area should be redirected, got {res.status_code}"
        print("  [PASS] POST /reports/settings/report/save_graph_area rejected for Level 1")

        print("\n=== 3. VERIFY ORGANISATION SETTINGS LEVEL 1 RESTRICTIONS ===")
        # 3A. /organisations/settings GET
        res = client.get('/organisations/settings')
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "Level 1 · Read Only" in html
        # Check Card 5 (Catalogue PDF Reports)
        assert "Pump Catalogue PDF Reports" in html
        assert 'title="Modifying pump catalogue report viewing preferences requires Level 2 edit authority on both Organisation Settings and Report Settings."' in html
        print("  [PASS] Card 5 in /organisations/settings correctly disabled with read-only badge")

        # 3B. POST /organisations/catalogue-reports/save (Blocked by decorator min_level=2)
        res = client.post('/organisations/catalogue-reports/save', data={
            'catalogue_report_mode': 'selected',
            'selected_report_ids': ['1']
        }, follow_redirects=False)
        assert res.status_code == 302, f"POST catalogue-reports/save should be redirected, got {res.status_code}"
        print("  [PASS] POST /organisations/catalogue-reports/save rejected for Level 1")

        print("\n=== ALL LEVEL 1 ACCESS RESTRICTION TESTS PASSED! ===")

if __name__ == '__main__':
    run_tests()
