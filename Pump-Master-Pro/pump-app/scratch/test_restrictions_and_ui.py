import os
import sys

sys.path.insert(0, r'c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app')

from app import app, db
from models import User, Organisation, Role, Pump, ReportConfig

def run_tests():
    with app.app_context():
        client = app.test_client()
        
        print("=== 1. TEST UNAUTHENTICATED REDIRECTIONS ===")
        # Unauthenticated requests to protected endpoints must redirect to /login
        for endpoint in ['/pump-data', '/pump-data/new', '/pump-data/edit/1', '/reports/settings']:
            resp = client.get(endpoint)
            assert resp.status_code == 302, f"Expected 302 for unauth {endpoint}, got {resp.status_code}"
            assert '/login' in resp.location, f"Expected redirect to /login for {endpoint}, got {resp.location}"
        print("[PASS] Unauthenticated access properly redirected to /login.")

        print("\n=== 2. TEST LOGIN PAGE RENDERING & MARKETING CONTENT ===")
        login_resp = client.get('/login')
        assert login_resp.status_code == 200, f"Expected 200 for /login, got {login_resp.status_code}"
        login_html = login_resp.get_data(as_text=True)
        
        # Verify SEO keywords & Multi-Pump Coverage
        assert "Pump Sizing &" in login_html or "Pump Sizing" in login_html, "Missing SEO keyword 'Pump Sizing'"
        assert "Positive Displacement" in login_html, "Missing multi-discipline coverage 'Positive Displacement'"
        assert "Multi-Stage" in login_html, "Missing multi-discipline coverage 'Multi-Stage'"
        assert "Submersible" in login_html, "Missing multi-discipline coverage 'Submersible'"
        assert "ISO 9906" in login_html, "Missing SEO keyword 'ISO 9906'"
        assert "Slurry" in login_html, "Missing SEO keyword 'Slurry'"
        
        # Verify NO WARMAN references exist
        assert "Warman" not in login_html, "Forbidden trademark 'Warman' found in login_html!"
        
        # Verify Marketing Slide Carousel
        assert "marketingSlideContainer" in login_html, "Missing marketing slide container"
        assert "goToSlide" in login_html, "Missing slide navigation function"
        assert "slide-0" in login_html, "Missing slide 0 element"

        # Verify Mini "Video" Simulator elements
        assert "demoSvgChart" in login_html, "Missing SVG curve chart in mini video player"
        assert "setDemoStep" in login_html, "Missing demo step controller script"
        assert "demoPlayBtn" in login_html, "Missing video player play/pause button"
        assert "demoProgressBar" in login_html, "Missing video player progress bar"

        # Verify User-Friendly Inputs & Autofill Fix
        assert 'id="inputEmail"' in login_html, "Missing email input"
        assert 'dark-seamless-input' in login_html, "Missing dark-seamless-input styling"
        assert '-webkit-box-shadow: 0 0 0 1000px #0d1117 inset' in login_html, "Missing browser autofill dark override CSS"
        assert 'autocomplete="email"' in login_html, "Missing email autocomplete"
        assert 'id="inputPassword"' in login_html, "Missing password input"
        assert 'autocomplete="current-password"' in login_html, "Missing password autocomplete"
        assert 'id="capsLockAlert"' in login_html, "Missing Caps Lock detector"
        assert 'togglePasswordVisibility' in login_html, "Missing password visibility toggle"
        print("[PASS] Login page rendered successfully with ZERO Warman references, multi-pump slide deck, interactive mini-video demo, and dark autofill fix.")

        print("\n=== 3. SETUP TEST RESTRICTED USER ===")
        # Get or create an organisation
        org = Organisation.query.filter_by(name='Test Restrictions Org').first()
        if not org:
            org = Organisation(name='Test Restrictions Org', contact_email='testrestr@org.com')
            db.session.add(org)
            db.session.commit()

        # Set organisation ceiling: pump_data: 1 (Read Only), report_settings: 1 (Read Only)
        org.set_all_access_levels({
            'pump_catalogue': 1,
            'pump_data': 1,       # Read Only
            'report_settings': 1, # Read Only
            'organisation_settings': 0,
            'comparison': 1,
            'users_settings': 0,
            'roles': 0,
            'selection_liquid': 1,
            'selection_advanced_filters': 1,
            'selection_motors': 1
        })
        db.session.commit()

        role = Role.query.filter_by(organisation_id=org.id, code='restricted_role').first()
        if not role:
            role = Role(organisation_id=org.id, name='Restricted Role', code='restricted_role')
            db.session.add(role)
        role.set_all_access_levels({
            'pump_catalogue': 1,
            'pump_data': 1,       # Read Only
            'report_settings': 1, # Read Only
            'organisation_settings': 0,
            'comparison': 1,
            'users_settings': 0,
            'roles': 0,
            'selection_liquid': 1,
            'selection_advanced_filters': 1,
            'selection_motors': 1
        })
        db.session.commit()

        user = User.query.filter_by(email='restricted_eng@example.com').first()
        if not user:
            user = User(
                email='restricted_eng@example.com',
                first_name='Restricted',
                last_name='Engineer',
                role='engineer',
                organisation_id=org.id,
                role_id=role.id,
                status='active'
            )
            user.set_password('Secret123!')
            db.session.add(user)
            db.session.commit()
        else:
            user.organisation_id = org.id
            user.role_id = role.id
            db.session.commit()

        assert user.get_access_level('pump_data') == 1, "User must have level 1 for pump_data"
        assert not user.can_edit('pump_data'), "User must NOT have edit access to pump_data"
        assert user.get_access_level('report_settings') == 1, "User must have level 1 for report_settings"
        assert not user.can_edit('report_settings'), "User must NOT have edit access to report_settings"
        print(f"[PASS] Restricted user configured: pump_data={user.get_access_level('pump_data')}, report_settings={user.get_access_level('report_settings')}")

        print("\n=== 4. TEST RESTRICTED USER PUMP CATALOGUE & PUMP-DATA RESTRICTIONS ===")
        # Sign in as restricted user
        with client.session_transaction() as sess:
            sess['user_id'] = user.id

        # 4a. Can view /pump-data
        cat_resp = client.get('/pump-data')
        assert cat_resp.status_code == 200, f"Expected 200 for restricted user on /pump-data, got {cat_resp.status_code}"
        cat_html = cat_resp.get_data(as_text=True)

        # Must NOT have "Add Pump" button or link
        assert 'href="/pump-data/new"' not in cat_html, "Restricted user should NOT see Add Pump link"
        assert 'href="/pump-data/edit/' not in cat_html, "Restricted user should NOT see Edit Pump link"
        assert 'action="/pump-data/delete/' not in cat_html, "Restricted user should NOT see Delete Pump form"
        assert 'Read-Only Catalogue' in cat_html, "Catalogue should display Read-Only badge"
        print("[PASS] Restricted user UI: Add, Edit, and Delete buttons are hidden from pump catalogue.")

        # 4b. Direct attempt to mutate pump data must be blocked by backend
        new_resp = client.get('/pump-data/new', follow_redirects=True)
        assert "Permission Denied" in new_resp.get_data(as_text=True), "GET /pump-data/new must be blocked with Permission Denied"

        first_pump = Pump.query.first()
        if first_pump:
            edit_resp = client.get(f'/pump-data/edit/{first_pump.id}', follow_redirects=True)
            assert "Permission Denied" in edit_resp.get_data(as_text=True), f"GET /pump-data/edit/{first_pump.id} must be blocked with Permission Denied"

            del_resp = client.post(f'/pump-data/delete/{first_pump.id}', follow_redirects=True)
            assert "Permission Denied" in del_resp.get_data(as_text=True), f"POST /pump-data/delete/{first_pump.id} must be blocked with Permission Denied"
        print("[PASS] Backend blocks restricted user from /pump-data/new, /pump-data/edit, and /pump-data/delete.")

        print("\n=== 5. TEST RESTRICTED USER PDF REPORT SETTINGS RESTRICTIONS ===")
        # 5a. Can view /reports/settings in read-only mode
        rep_resp = client.get('/reports/settings')
        assert rep_resp.status_code == 200, f"Expected 200 for restricted user on /reports/settings, got {rep_resp.status_code}"
        rep_html = rep_resp.get_data(as_text=True)

        assert "Read-Only Mode:" in rep_html, "Reports settings must display Read-Only Mode banner"
        assert 'onclick="openReportModal()"' not in rep_html, "Restricted user should NOT see Create Report Setting button"
        assert 'onclick="openSupplierModal()"' not in rep_html, "Restricted user should NOT see Add Organisation button"
        assert 'onclick="openGraphAreaModal()"' not in rep_html, "Restricted user should NOT see Graph Area Settings button"
        assert 'onclick="editReport(' not in rep_html, "Restricted user should NOT see Edit Report button"
        assert 'onclick="editSupplier(' not in rep_html, "Restricted user should NOT see Edit Supplier button"
        assert 'action="/reports/settings/report/delete/' not in rep_html, "Restricted user should NOT see Delete Report button"
        print("[PASS] Restricted user UI: Report settings shows Read-Only banner, mutation buttons are hidden.")

        # 5b. Direct attempt to mutate report settings must be blocked by backend
        save_rep = client.post('/reports/settings/report/save', data={'title': 'Hacked Report'}, follow_redirects=True)
        assert "Permission Denied" in save_rep.get_data(as_text=True), "POST /reports/settings/report/save must be blocked"

        save_supp = client.post('/reports/settings/supplier/save', data={'name': 'Hacked Supplier'}, follow_redirects=True)
        assert "Permission Denied" in save_supp.get_data(as_text=True), "POST /reports/settings/supplier/save must be blocked"

        del_rep = client.post('/reports/settings/report/delete/1', follow_redirects=True)
        assert "Permission Denied" in del_rep.get_data(as_text=True), "POST /reports/settings/report/delete/1 must be blocked"
        print("[PASS] Backend blocks restricted user from saving/deleting reports and suppliers.")

        print("\n=== 6. TEST LEVEL 0 (NO ACCESS) USER ===")
        # Set report_settings to 0 (No Access)
        org.set_access_level('report_settings', 0)
        role.set_access_level('report_settings', 0)
        db.session.commit()

        zero_resp = client.get('/reports/settings', follow_redirects=True)
        assert "Access Denied" in zero_resp.get_data(as_text=True), "Level 0 user must receive Access Denied for /reports/settings"
        print("[PASS] Level 0 user completely blocked from /reports/settings.")

        print("\n=== 7. TEST SUPERADMIN FULL ACCESS ===")
        super_admin = User.query.filter_by(email='nevermabvuu@gmail.com').first()
        assert super_admin is not None, "SuperAdmin must exist"

        with client.session_transaction() as sess:
            sess['user_id'] = super_admin.id

        admin_cat = client.get('/pump-data')
        assert 'href="/pump-data/new"' in admin_cat.get_data(as_text=True), "SuperAdmin MUST see Add Pump button"
        assert 'href="/pump-data/edit/' in admin_cat.get_data(as_text=True), "SuperAdmin MUST see Edit button"

        admin_rep = client.get('/reports/settings')
        assert 'openReportModal()' in admin_rep.get_data(as_text=True), "SuperAdmin MUST see Create Report button"
        assert 'openSupplierModal()' in admin_rep.get_data(as_text=True), "SuperAdmin MUST see Add Organisation button"
        print("[PASS] SuperAdmin maintains full unrestricted access to all controls.")

        print("\n==========================================")
        print("ALL TESTS PASSED WITH 100% SUCCESS!")
        print("==========================================")

if __name__ == '__main__':
    run_tests()
