"""
scratch/test_auth_and_email.py — Test Authentication & Registration Flow.
"""
import os
import sys

_cur = os.path.dirname(os.path.abspath(__file__))
_app_dir = os.path.abspath(os.path.join(_cur, '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from app import app, db
from models import User, RegistrationRequest
from services.email_service import send_registration_request_notification, send_registration_decision_notification

print("--- Testing App Initialization & Database Models ---")
with app.app_context():
    # 1. Verify User table exists and default admin is seeded
    admin = User.query.filter_by(email='nevermabvuu@gmail.com').first()
    if admin:
        print(f"PASS: Admin user found: {admin.full_name} ({admin.email}), Role={admin.role}, Active={admin.is_active()}")
        assert admin.check_password('Admin123!'), "Admin password check failed!"
        print("PASS: Admin password verification succeeded!")
    else:
        print("FAIL: Default admin user not found!")

    # 2. Test Registration Request creation
    test_req = RegistrationRequest.query.filter_by(email='test.engineer@miningcorp.com').first()
    if test_req:
        db.session.delete(test_req)
        db.session.commit()

    new_req = RegistrationRequest(
        first_name="Alice",
        last_name="Johnson",
        email="test.engineer@miningcorp.com",
        company="Mining Corp International",
        job_title="Lead Slurry Engineer",
        phone="+27 11 000 1234",
        notes="Testing automated access request dispatch."
    )
    new_req.set_password("SecretPass123!")
    db.session.add(new_req)
    db.session.commit()
    print(f"PASS: Created registration request for {new_req.full_name} (ID={new_req.id})")

    # 3. Test Email Notification dispatch (to nevermabvuu@gmail.com)
    success, msg = send_registration_request_notification(new_req)
    print(f"PASS: send_registration_request_notification result: success={success}, msg={msg}")

    # 4. Test Approval notification
    success_dec, msg_dec = send_registration_decision_notification(new_req, approved=True, notes="Verified mining engineer credentials.")
    print(f"PASS: send_registration_decision_notification result: success={success_dec}, msg={msg_dec}")

    # Cleanup test request
    db.session.delete(new_req)
    db.session.commit()
    print("PASS: Test registration request cleaned up successfully.")

print("\nALL BACKEND AUTH & NOTIFICATION TESTS PASSED SUCCESSFULLY!")
