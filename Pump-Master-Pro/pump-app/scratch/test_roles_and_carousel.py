"""
scratch/test_roles_and_carousel.py
End-to-end automated verification script for:
1. Marketing carousel implementation in login.html (5 slides, track, progress bar, dots)
2. Strict Level 1 (Read-Only) RBAC enforcement across pump-data, pump-catalogue, and reports
3. Level 0 access denial for unauthorized modules
4. Super Administrator full bypass
"""

import re
from app import app
from models import db, User, Role, Pump, ReportConfig, Organisation

def run_tests():
    print("======================================================================")
    print("STARTING TEST SUITE: MARKETING CAROUSEL & RBAC RESTRICTION ENFORCEMENT")
    print("======================================================================\n")

    client = app.test_client()

    with app.app_context():
        # Retrieve users
        samuel = User.query.filter_by(email="samuel.ndlovu@angloamerican.com").first()
        super_admin = User.query.filter_by(email="nevermabvuu@gmail.com").first()
        restricted = User.query.filter_by(email="restricted_eng@example.com").first()
        
        assert samuel is not None, "Samuel Ndlovu user not found"
        assert super_admin is not None, "Super admin user not found"
        assert restricted is not None, "Restricted engineer user not found"

        print(f"[USER VERIFICATION]")
        print(f"  Samuel (ID {samuel.id}): role={samuel.role_display_name}, org={samuel.organisation_id}")
        sam_levels = samuel.to_dict()['access_levels']
        print(f"  Samuel Effective Levels: pump_data={sam_levels.get('pump_data')}, pump_catalogue={sam_levels.get('pump_catalogue')}, report_settings={sam_levels.get('report_settings')}, org_settings={sam_levels.get('organisation_settings')}")
        
        assert sam_levels.get('pump_data') == 1, "Samuel must have pump_data=1"
        assert sam_levels.get('pump_catalogue') == 1, "Samuel must have pump_catalogue=1"
        assert sam_levels.get('report_settings') == 1, "Samuel must have report_settings=1"
        assert sam_levels.get('organisation_settings') == 1, "Samuel must have organisation_settings=1"
        assert not samuel.can_edit('pump_data'), "Samuel can_edit('pump_data') must be False"
        assert not samuel.can_edit('pump_catalogue'), "Samuel can_edit('pump_catalogue') must be False"
        assert not samuel.can_edit_catalogue(), "Samuel can_edit_catalogue() must be False"
        print("  --> Samuel is confirmed strictly Level 1 (Read-Only) across all targeted modules. [PASS]\n")

    # ──────────────────────────────────────────────────────────────────
    # 1. LOGIN PAGE & CAROUSEL VALIDATION
    # ──────────────────────────────────────────────────────────────────
    print("[TEST GROUP 1: LOGIN CAROUSEL & ZERO TRADEMARK COMPLIANCE]")
    resp = client.get('/login')
    assert resp.status_code == 200, f"Login page failed with status {resp.status_code}"
    html = resp.get_data(as_text=True)

    assert 'id="marketingCarousel"' in html, "marketingCarousel container missing"
    assert 'id="carouselTrack"' in html, "carouselTrack missing"
    assert 'id="carouselProgressBar"' in html, "carouselProgressBar missing"
    assert 'id="slideCategoryBadge"' in html, "slideCategoryBadge missing"
    assert 'id="slideNumberBadge"' in html, "slideNumberBadge missing"
    assert 'id="cdot-0"' in html and 'id="cdot-4"' in html, "Carousel dot indicators missing"
    assert 'goToCarouselSlide' in html, "goToCarouselSlide function missing"
    assert 'startCarouselAutoPlay' in html, "startCarouselAutoPlay function missing"

    # Verify 5 distinct slides exist
    assert "Universal Sizing: Centrifugal, PD, Multi-Stage" in html, "Slide 1 missing"
    assert "100% Bespoke OEM Customization: User-Defined Engines" in html, "Slide 2 missing"
    assert "Abrasive Slurry &amp; Viscous Fluid Derating Engine" in html or "Abrasive Slurry & Viscous Fluid Derating Engine" in html, "Slide 3 missing"
    assert "Precision Duty Matching &amp; Best Efficiency Point" in html or "Precision Duty Matching & Best Efficiency Point" in html, "Slide 4 missing"
    assert "Submittal-Ready Vector PDFs &amp; Multi-Tenant RBAC" in html or "Submittal-Ready Vector PDFs & Multi-Tenant RBAC" in html, "Slide 5 missing"

    # Verify zero Warman trademark references
    warman_matches = re.findall(r'warman', html, re.IGNORECASE)
    assert len(warman_matches) == 0, f"Found {len(warman_matches)} trademark Warman occurrences in login.html!"
    print("  --> Login carousel contains 5 high-density slides, horizontal track, progress bar & zero trademarks. [PASS]\n")

    # ──────────────────────────────────────────────────────────────────
    # 2. SAMUEL (LEVEL 1) PUMP DATA & CATALOGUE RESTRICTIONS
    # ──────────────────────────────────────────────────────────────────
    print("[TEST GROUP 2: SAMUEL (LEVEL 1) PUMP CATALOGUE & CURVE RESTRICTIONS]")
    with client.session_transaction() as sess:
        sess['user_id'] = samuel.id

    # 2.1 View /pump-data
    r_cat = client.get('/pump-data')
    assert r_cat.status_code == 200, f"GET /pump-data failed with status {r_cat.status_code}"
    cat_html = r_cat.get_data(as_text=True)
    assert "Read-Only Catalogue" in cat_html, "Read-Only Catalogue pill missing on /pump-data"
    assert '<a href="/pump-data/new"' not in cat_html, "Add Pump link should NOT be present for Level 1 user"
    assert 'action="/pump-data/delete/' not in cat_html, "Delete form should NOT be present for Level 1 user"
    assert 'title="Edit pump data"' not in cat_html, "Edit button should NOT be present for Level 1 user"
    print("  --> /pump-data displays 'Read-Only Catalogue' and hides Add/Edit/Delete buttons. [PASS]")

    # 2.2 View /pump-curve/1
    r_curve = client.get('/pump-curve/1')
    assert r_curve.status_code == 200, f"GET /pump-curve/1 failed with status {r_curve.status_code}"
    curve_html = r_curve.get_data(as_text=True)
    assert "Read-Only View" in curve_html, "Read-Only View badge missing in pump_curve.html"
    assert "Pump Data Editing Locked (Read-Only)" in curve_html, "Locked pill missing in pump_curve.html"
    assert '<a href="/pump-data/edit/1"' not in curve_html, "Edit pump link should NOT appear in pump_curve.html for Level 1"
    print("  --> /pump-curve/1 displays 'Read-Only View' and hides all edit controls. [PASS]")

    # 2.3 Attempt mutations on pump-data (POST /pump-data/new, GET /pump-data/new, POST /pump-data/edit/1, POST /pump-data/delete/1)
    r_new_get = client.get('/pump-data/new', follow_redirects=False)
    assert r_new_get.status_code == 302, f"Expected 302 on GET /pump-data/new, got {r_new_get.status_code}"

    r_new_post = client.post('/pump-data/new', data={'name': 'Illegal Pump'}, follow_redirects=False)
    assert r_new_post.status_code == 302, f"Expected 302 on POST /pump-data/new, got {r_new_post.status_code}"

    r_edit_post = client.post('/pump-data/edit/1', data={'name': 'Hacked Name'}, follow_redirects=False)
    assert r_edit_post.status_code == 302, f"Expected 302 on POST /pump-data/edit/1, got {r_edit_post.status_code}"

    r_del_post = client.post('/pump-data/delete/1', follow_redirects=False)
    assert r_del_post.status_code == 302, f"Expected 302 on POST /pump-data/delete/1, got {r_del_post.status_code}"

    # 2.4 Attempt curve APIs
    r_opts = client.post('/papi/pump/1/graph-options', json={'test': 1}, follow_redirects=False)
    assert r_opts.status_code == 302, f"Expected 302 on /papi/pump/1/graph-options, got {r_opts.status_code}"

    r_label = client.post('/papi/pump/1/label-pos', json={'test': 1}, follow_redirects=False)
    assert r_label.status_code == 302, f"Expected 302 on /papi/pump/1/label-pos, got {r_label.status_code}"
    print("  --> All pump-data and curve mutation routes strictly block Level 1 with 302 redirects. [PASS]\n")

    # ──────────────────────────────────────────────────────────────────
    # 3. SAMUEL (LEVEL 1) ORGANISATION SETTINGS RESTRICTIONS
    # ──────────────────────────────────────────────────────────────────
    print("[TEST GROUP 3: SAMUEL (LEVEL 1) ORGANISATION SETTINGS RESTRICTIONS]")
    r_org = client.get('/organisations/settings')
    assert r_org.status_code == 200, f"GET /organisations/settings failed with {r_org.status_code}"
    org_html = r_org.get_data(as_text=True)
    assert "Read-Only Mode:" in org_html, "Read-Only banner missing in organisations_settings.html"
    assert "disabled" in org_html, "Fieldsets should be disabled in organisations_settings.html"

    # Attempt mutation on catalogue-reports
    r_cat_rep = client.post('/organisations/catalogue-reports/save', data={'catalogue_report_ids': 'all'}, follow_redirects=False)
    assert r_cat_rep.status_code == 302, f"Expected 302 on POST /organisations/catalogue-reports/save, got {r_cat_rep.status_code}"

    r_prof = client.post('/organisations/profile/save', data={'name': 'Malicious Name'}, follow_redirects=False)
    assert r_prof.status_code == 302, f"Expected 302 on POST /organisations/profile/save, got {r_prof.status_code}"
    print("  --> Organisation settings correctly locked in Read-Only mode and mutations blocked. [PASS]\n")

    # ──────────────────────────────────────────────────────────────────
    # 4. SAMUEL (LEVEL 1) REPORT SETTINGS RESTRICTIONS & VIEW ACCESS
    # ──────────────────────────────────────────────────────────────────
    print("[TEST GROUP 4: SAMUEL (LEVEL 1) REPORT SETTINGS RESTRICTIONS]")
    r_rep = client.get('/reports/settings')
    assert r_rep.status_code == 200, f"GET /reports/settings failed with {r_rep.status_code}"
    rep_html = r_rep.get_data(as_text=True)
    assert "Read-Only Reports" in rep_html, "'Read-Only Reports' badge missing in reports_settings.html"
    assert "Read-Only Mode:" in rep_html, "Read-Only banner missing in reports_settings.html"
    assert '<button type="submit"' not in rep_html or 'disabled' in rep_html, "Submit buttons should be disabled or absent"

    # Attempt mutation on report templates
    r_rep_save = client.post('/reports/settings/report/save', data={'title': 'Unauthorized'}, follow_redirects=False)
    assert r_rep_save.status_code == 302, f"Expected 302 on POST /reports/settings/report/save, got {r_rep_save.status_code}"

    r_sup_save = client.post('/reports/settings/supplier/save', data={'name': 'Unauthorized'}, follow_redirects=False)
    assert r_sup_save.status_code == 302, f"Expected 302 on POST /reports/settings/supplier/save, got {r_sup_save.status_code}"

    r_del_rep = client.post('/reports/settings/report/delete/1', follow_redirects=False)
    assert r_del_rep.status_code == 302, f"Expected 302 on POST /reports/settings/report/delete/1, got {r_del_rep.status_code}"

    # Level 1 IS allowed to view and export reports (read-only capability) for pumps within their organisation (Pump 2 is Org 2)
    r_rep_view = client.get('/reports/view/1/pump/2')
    assert r_rep_view.status_code == 200, f"Expected 200 on GET /reports/view/1/pump/2 for Level 1, got {r_rep_view.status_code}"

    r_rep_dl = client.get('/reports/download/1/pump/2')
    assert r_rep_dl.status_code == 200, f"Expected 200 on GET /reports/download/1/pump/2 for Level 1, got {r_rep_dl.status_code}"
    print("  --> Report settings mutation blocked while Read-Only viewing and PDF export succeed. [PASS]\n")

    # ──────────────────────────────────────────────────────────────────
    # 5. RESTRICTED USER (LEVEL 0 ON REPORTS) ACCESS DENIAL
    # ──────────────────────────────────────────────────────────────────
    print("[TEST GROUP 5: LEVEL 0 MODULE ACCESS DENIAL]")
    with client.session_transaction() as sess:
        sess['user_id'] = restricted.id

    r_lvl0_rep = client.get('/reports/settings', follow_redirects=False)
    assert r_lvl0_rep.status_code == 302, f"Expected 302 on /reports/settings for Level 0 user, got {r_lvl0_rep.status_code}"

    r_lvl0_view = client.get('/reports/view/1/pump/1', follow_redirects=False)
    assert r_lvl0_view.status_code == 302, f"Expected 302 on /reports/view for Level 0 user, got {r_lvl0_view.status_code}"

    r_lvl0_dl = client.get('/reports/download/1/pump/1', follow_redirects=False)
    assert r_lvl0_dl.status_code == 302, f"Expected 302 on /reports/download for Level 0 user, got {r_lvl0_dl.status_code}"
    print("  --> Level 0 user is strictly denied from viewing or downloading reports. [PASS]\n")

    # ──────────────────────────────────────────────────────────────────
    # 6. SUPER ADMINISTRATOR FULL UNRESTRICTED BYPASS
    # ──────────────────────────────────────────────────────────────────
    print("[TEST GROUP 6: SUPER ADMINISTRATOR UNRESTRICTED ACCESS]")
    with client.session_transaction() as sess:
        sess['user_id'] = super_admin.id

    r_admin_cat = client.get('/pump-data')
    assert r_admin_cat.status_code == 200
    admin_cat_html = r_admin_cat.get_data(as_text=True)
    assert "Add Pump" in admin_cat_html, "Super admin should see Add Pump button in catalogue"
    assert "Read-Only Catalogue" not in admin_cat_html, "Super admin should not see Read-Only Catalogue badge"

    r_admin_curve = client.get('/pump-curve/1')
    assert r_admin_curve.status_code == 200
    admin_curve_html = r_admin_curve.get_data(as_text=True)
    assert 'Edit Pump Data &amp; Preview' in admin_curve_html or 'Edit Pump Data & Preview' in admin_curve_html, "Super admin should see Edit Pump Data button"

    r_admin_rep = client.get('/reports/settings')
    assert r_admin_rep.status_code == 200
    admin_rep_html = r_admin_rep.get_data(as_text=True)
    assert "Create Report Setting" in admin_rep_html, "Super admin should see Create Report Setting button"
    assert "Read-Only Reports" not in admin_rep_html, "Super admin should not see Read-Only Reports badge"
    print("  --> Super Administrator maintains complete, unrestricted editing access. [PASS]\n")

    print("======================================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (100% VERIFIED)")
    print("======================================================================")

if __name__ == '__main__':
    run_tests()
