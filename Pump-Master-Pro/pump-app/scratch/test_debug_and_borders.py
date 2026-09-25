import os
import sys

sys.path.insert(0, r'c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app')

from app import app, db
from models import User, Organisation, Role, ACCESS_MODULE_INFO

def verify_all():
    with app.app_context():
        print("=== 1. VERIFY ACCESS_MODULE_INFO ===")
        assert 'debug' in ACCESS_MODULE_INFO, "debug module must be in ACCESS_MODULE_INFO"
        print(f"[PASS] debug module found: {ACCESS_MODULE_INFO['debug']}")
        print(f"Total modules: {len(ACCESS_MODULE_INFO)}")

        print("\n=== 2. VERIFY GRAPH STYLES DEFAULTS ===")
        org = Organisation.query.first()
        if org:
            styles = org.get_graph_styles()
            assert 'border_outline_mode' in styles, "border_outline_mode should be in get_graph_styles"
            print(f"[PASS] Organisation graph styles includes border_outline_mode: {styles['border_outline_mode']}")

        print("\n=== 3. VERIFY ROLE & USER ACCESS TO DEBUG ===")
        superadmin = User.query.filter(
            (User.is_super_admin == True) | 
            (User.email == 'nevermabvuu@gmail.com') | 
            (User.role.in_(['superadmin', 'super_admin']))
        ).first()
        if not superadmin:
            # Fallback to finding user where is_super_admin_user property is True
            for u in User.query.all():
                if u.is_super_admin_user:
                    superadmin = u
                    break
        if superadmin:
            lvl = superadmin.get_access_level('debug')
            assert lvl == 2, f"SuperAdmin must have level 2 access to debug, got {lvl}"
            assert superadmin.can_access('debug', 1) is True
            assert superadmin.can_access('debug', 2) is True
            print(f"[PASS] SuperAdmin ({superadmin.email}) has level {lvl} on debug.")

        # Test normal user
        engineer = User.query.filter(User.role != 'superadmin', User.email != (superadmin.email if superadmin else '')).first()
        if engineer:
            eng_lvl = engineer.get_access_level('debug')
            print(f"Engineer user ({engineer.email}, role={engineer.role}) debug access level: {eng_lvl}")

        print("\n=== 4. TEST CLIENT REQUESTS ===")
        client = app.test_client()

        # Unauthenticated request to /debug/session should redirect to login
        res = client.get('/debug/session')
        print(f"Unauthenticated /debug/session response status: {res.status_code}")
        assert res.status_code in (302, 403), f"Expected 302 or 403, got {res.status_code}"

        # SuperAdmin authenticated request to /debug/session should succeed (200)
        if superadmin:
            with client.session_transaction() as sess:
                sess['user_id'] = superadmin.id
                sess['user_email'] = superadmin.email
                sess['role'] = superadmin.role
                sess['_user_id'] = str(superadmin.id)
            res2 = client.get('/debug/session')
            print(f"SuperAdmin /debug/session response status: {res2.status_code}")
            assert res2.status_code == 200, f"Expected 200 for SuperAdmin, got {res2.status_code}"

            # Test API endpoint
            res_api = client.get('/debug/api/session-json')
            assert res_api.status_code == 200, f"Expected 200 for SuperAdmin API, got {res_api.status_code}"
            print("[PASS] SuperAdmin can access debug API")

        # Test non-admin user (engineer) accessing debug endpoints
        if engineer:
            client_eng = app.test_client()
            with client_eng.session_transaction() as sess:
                sess['user_id'] = engineer.id
                sess['user_email'] = engineer.email
                sess['role'] = engineer.role
                sess['_user_id'] = str(engineer.id)

            # Accessing /debug/session should be denied (redirected away from debug)
            res_eng = client_eng.get('/debug/session')
            print(f"Engineer /debug/session response status: {res_eng.status_code}")
            assert res_eng.status_code in (302, 403), f"Expected 302 or 403 for engineer, got {res_eng.status_code}"

            # Accessing /debug/api/session-json should return 403
            res_eng_api = client_eng.get('/debug/api/session-json')
            print(f"Engineer /debug/api/session-json response status: {res_eng_api.status_code}")
            assert res_eng_api.status_code == 403, f"Expected 403 for engineer without debug access, got {res_eng_api.status_code}"
            print("[PASS] Engineer correctly denied access (403) to debug API")

        print("\n=== ALL VERIFICATIONS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    verify_all()
