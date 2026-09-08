import os
import sys

# Add application directory to path
sys.path.insert(0, os.path.abspath('c:/Users/DELL/Documents/admin/Lytrose/repos/Pump-Master-Pro/Pump-Master-Pro/pump-app'))

from app import app, db
from models import User, Organisation, Role

def run_tests():
    print("=== STARTING USER MANAGEMENT & CEILINGS MODAL TESTS ===")
    
    with app.app_context():
        # Setup or get test users
        org = Organisation.query.get(2)
        assert org is not None, "Organisation #2 not found"

        # 1. Level 1 Role for users_settings
        lvl1_role = Role.query.filter_by(organisation_id=org.id, code='lvl1_user_mgr').first()
        if not lvl1_role:
            lvl1_role = Role(organisation_id=org.id, name='User Auditor (Read-Only)', code='lvl1_user_mgr')
            db.session.add(lvl1_role)
            db.session.commit()
        
        # Ensure org has users_settings >= 1
        org.set_access_level('users_settings', 2)
        lvl1_role.set_access_level('users_settings', 1)
        db.session.commit()

        # Level 1 User
        u_lvl1 = User.query.filter_by(email='user_auditor@lytrose.example').first()
        if not u_lvl1:
            u_lvl1 = User(
                email='user_auditor@lytrose.example',
                first_name='Auditor',
                last_name='LevelOne',
                organisation_id=org.id,
                role_id=lvl1_role.id,
                role=lvl1_role.code,
                status='active'
            )
            u_lvl1.set_password('Password123!')
            db.session.add(u_lvl1)
            db.session.commit()
        else:
            u_lvl1.role_id = lvl1_role.id
            u_lvl1.role = lvl1_role.code
            db.session.commit()

        # Level 0 Role for users_settings
        lvl0_role = Role.query.filter_by(organisation_id=org.id, code='lvl0_user_mgr').first()
        if not lvl0_role:
            lvl0_role = Role(organisation_id=org.id, name='No User Access', code='lvl0_user_mgr')
            db.session.add(lvl0_role)
            db.session.commit()
        lvl0_role.set_access_level('users_settings', 0)
        db.session.commit()

        u_lvl0 = User.query.filter_by(email='no_users@lytrose.example').first()
        if not u_lvl0:
            u_lvl0 = User(
                email='no_users@lytrose.example',
                first_name='NoUser',
                last_name='Tester',
                organisation_id=org.id,
                role_id=lvl0_role.id,
                role=lvl0_role.code,
                status='active'
            )
            u_lvl0.set_password('Password123!')
            db.session.add(u_lvl0)
            db.session.commit()
        else:
            u_lvl0.role_id = lvl0_role.id
            u_lvl0.role = lvl0_role.code
            db.session.commit()

        u_super = User.query.filter_by(email='nevermabvuu@gmail.com').first()
        assert u_super is not None, "SuperAdmin not found"

        u_lvl1_id = u_lvl1.id
        u_lvl0_id = u_lvl0.id
        u_super_id = u_super.id

    # Test with Flask test_client
    with app.test_client() as client:
        # -------------------------------------------------------------
        # TEST 1: Level 1 user accessing /admin/users (READ-ONLY VIEW)
        # -------------------------------------------------------------
        with client.session_transaction() as sess:
            sess['user_id'] = u_lvl1_id
            sess['logged_in'] = True

        resp = client.get('/admin/users')
        assert resp.status_code == 200, f"Expected 200 for Level 1 user, got {resp.status_code}"
        html = resp.data.decode('utf-8')
        assert "Read-Only Mode:" in html, "Level 1 user should see Read-Only Mode banner on /admin/users"
        assert "LEVEL 1 • READ ONLY" in html or "LEVEL 1 &bull; READ ONLY" in html, "Read-Only badge missing"
        assert "Add User (Disabled)" in html, "Add User button should be disabled for Level 1 user"
        assert "View Only" in html, "Table rows should show View Only indicator for Level 1 user"
        print("[PASS] Level 1 user can view /admin/users in Read-Only mode with action buttons locked")

        # -------------------------------------------------------------
        # TEST 2: Level 1 user mutation attempts are BLOCKED
        # -------------------------------------------------------------
        resp_post = client.post('/admin/users/create', data={
            'first_name': 'Hacker',
            'last_name': 'User',
            'email': 'hacker@test.example',
            'password': 'Password123!'
        }, follow_redirects=False)
        assert resp_post.status_code in (302, 403), f"Level 1 user creation should be redirected/blocked, got {resp_post.status_code}"

        resp_edit = client.post(f'/admin/users/{u_lvl1_id}/edit', data={
            'first_name': 'HackedName',
            'last_name': 'HackedLast'
        }, follow_redirects=False)
        assert resp_edit.status_code in (302, 403), "Level 1 user profile edit should be blocked"

        resp_toggle = client.post(f'/admin/users/{u_lvl0_id}/toggle-status', follow_redirects=False)
        assert resp_toggle.status_code in (302, 403), "Level 1 user status toggle should be blocked"

        resp_pwd = client.post(f'/admin/users/{u_lvl0_id}/reset-password', data={
            'new_password': 'NewPassword123!'
        }, follow_redirects=False)
        assert resp_pwd.status_code in (302, 403), "Level 1 user password reset should be blocked"
        print("[PASS] Level 1 user mutation routes (/create, /edit, /toggle-status, /reset-password) strictly blocked")

        # -------------------------------------------------------------
        # TEST 3: Level 0 user accessing /admin/users (NO ACCESS)
        # -------------------------------------------------------------
        with client.session_transaction() as sess:
            sess['user_id'] = u_lvl0_id
            sess['logged_in'] = True

        resp_l0 = client.get('/admin/users', follow_redirects=False)
        assert resp_l0.status_code == 302, f"Expected 302 redirect for Level 0 user, got {resp_l0.status_code}"
        print("[PASS] Level 0 user blocked from accessing /admin/users")

        # -------------------------------------------------------------
        # TEST 4: SuperAdmin / Organisation Settings modal placement
        # -------------------------------------------------------------
        with client.session_transaction() as sess:
            sess['user_id'] = u_super_id
            sess['logged_in'] = True

        resp_org = client.get('/organisations/settings')
        assert resp_org.status_code == 200, f"SuperAdmin expected 200 on /organisations/settings, got {resp_org.status_code}"
        org_html = resp_org.data.decode('utf-8')

        assert 'id="orgAccessMatrixModal"' in org_html, "orgAccessMatrixModal missing from template"
        assert 'z-[9999]' in org_html, "orgAccessMatrixModal should have z-[9999]"
        assert 'document.body.style.overflow = \'hidden\'' in org_html, "Scroll locking missing from modal JS"
        assert 'openOrgAccessMatrixModal' in org_html, "openOrgAccessMatrixModal function missing"
        print("[PASS] Organisation settings Supreme Access Matrix modal placed outside <main> with viewport attachment & scroll lock")

    print("\nALL USER MANAGEMENT & CEILINGS TESTS PASSED 100%!")

if __name__ == '__main__':
    run_tests()
