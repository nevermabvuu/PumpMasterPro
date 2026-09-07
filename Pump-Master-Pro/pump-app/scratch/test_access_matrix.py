import os
import sys

sys.path.insert(0, r'c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app')

from app import app, db
from models import User, Organisation, Role, ACCESS_MODULE_INFO

def run_tests():
    with app.app_context():
        print("=== 1. TEST ACCESS_MODULE_INFO ===")
        assert len(ACCESS_MODULE_INFO) == 10, f"Expected 10 modules, found {len(ACCESS_MODULE_INFO)}"
        expected_modules = [
            'organisation_settings', 'pump_data', 'comparison', 'report_settings',
            'users_settings', 'roles', 'selection_liquid', 'selection_advanced_filters',
            'selection_motors', 'pump_catalogue'
        ]
        for em in expected_modules:
            assert em in ACCESS_MODULE_INFO, f"Missing expected module {em}"
        print("[PASS] All 10 modules present with icons, labels, and descriptions.")

        print("\n=== 2. TEST ORGANISATION ACCESS CEILINGS ===")
        org = Organisation.query.filter_by(name='Test Org Supreme').first()
        if not org:
            org = Organisation(name='Test Org Supreme', contact_email='testsupreme@org.com')
            db.session.add(org)
            db.session.commit()

        # Set specific supreme ceilings:
        # liquid: 1 (Read Only), comparison: 0 (No Access), pump_data: 2 (Full Access)
        custom_org_levels = {
            'organisation_settings': 1,
            'pump_data': 2,
            'comparison': 0,
            'report_settings': 1,
            'users_settings': 0,
            'roles': 0,
            'selection_liquid': 1,
            'selection_advanced_filters': 2,
            'selection_motors': 1,
            'pump_catalogue': 2
        }
        org.set_all_access_levels(custom_org_levels)
        db.session.commit()

        reloaded_org = Organisation.query.get(org.id)
        org_levels = reloaded_org.get_all_access_levels()
        assert org_levels['comparison'] == 0, f"Expected comparison 0, got {org_levels['comparison']}"
        assert org_levels['selection_liquid'] == 1, f"Expected liquid 1, got {org_levels['selection_liquid']}"
        assert org_levels['pump_data'] == 2, f"Expected pump_data 2, got {org_levels['pump_data']}"
        print("[PASS] Organisation ceilings persisted and reloaded properly from JSON.")

        print("\n=== 3. TEST ROLE LEVEL CLAMPING & SUPREME ORGANISATION RULE ===")
        # Create a role in Test Org Supreme that tries to grant level 2 to everything
        role = Role.query.filter_by(organisation_id=org.id, code='super_engineer').first()
        if not role:
            role = Role(organisation_id=org.id, name='Super Engineer', code='super_engineer')
            db.session.add(role)

        role.set_all_access_levels({k: 2 for k in expected_modules})
        db.session.commit()

        # Check role internal level vs effective user level
        assert role.get_access_level('comparison') == 2, "Role internal was set to 2"

        # Create a regular user assigned to this role
        user = User.query.filter_by(email='test_supreme_eng@example.com').first()
        if not user:
            user = User(
                email='test_supreme_eng@example.com',
                first_name='Test',
                last_name='Supreme Engineer',
                role='engineer',
                organisation_id=org.id,
                role_id=role.id,
                status='active'
            )
            user.set_password('Password123!')
            db.session.add(user)
            db.session.commit()
        else:
            user.organisation_id = org.id
            user.role_id = role.id
            db.session.commit()

        # The Supreme Rule: min(org_cap, role_level)
        # For comparison: role=2, org=0 -> effective must be 0!
        eff_comp = user.get_access_level('comparison')
        assert eff_comp == 0, f"Supreme Rule failed! Expected comparison level 0, got {eff_comp}"

        # For selection_liquid: role=2, org=1 -> effective must be 1!
        eff_liquid = user.get_access_level('selection_liquid')
        assert eff_liquid == 1, f"Supreme Rule failed! Expected liquid level 1, got {eff_liquid}"

        # For pump_data: role=2, org=2 -> effective is 2!
        eff_pump = user.get_access_level('pump_data')
        assert eff_pump == 2, f"Expected pump_data level 2, got {eff_pump}"

        # can_access helper checks
        assert not user.can_access('comparison', 1), "User should NOT have view access to comparison"
        assert user.can_access('selection_liquid', 1), "User SHOULD have view access to selection_liquid"
        assert not user.can_access('selection_liquid', 2), "User should NOT have full/edit access to selection_liquid"
        assert user.can_access('pump_data', 2), "User SHOULD have full access to pump_data"

        print("[PASS] Supreme Organisation Rule verified! Effective level = min(org_cap, role_level)")

        print("\n=== 4. TEST SUPERADMIN UNLIMITED AUTHORITY ===")
        super_admin = User.query.filter_by(email='nevermabvuu@gmail.com').first()
        assert super_admin is not None, "SuperAdmin nevermabvuu@gmail.com must exist"
        assert super_admin.is_super_admin_user, "Must be super admin user"

        for em in expected_modules:
            assert super_admin.get_access_level(em) == 2, f"SuperAdmin must have level 2 for {em}"
            assert super_admin.can_access(em, 2), f"SuperAdmin must have full access to {em}"

        print("[PASS] SuperAdmin retains level 2 full access across all 10 modules unconditionally.")

        print("\n=== ALL MATRIX TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_tests()
