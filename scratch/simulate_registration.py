import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))
from app import app
from models import db, RegistrationRequest, User, Organisation
from services.email_service import send_registration_request_notification, send_registration_received_confirmation

with app.app_context():
    test_email = "tester_temp_check_99@lytrose.com"
    print("Testing registration flow simulation for:", test_email)
    
    # Clean up if exists
    User.query.filter_by(email=test_email).delete()
    RegistrationRequest.query.filter_by(email=test_email).delete()
    db.session.commit()
    
    reg_req = RegistrationRequest(
        first_name="Test",
        last_name="Applicant",
        email=test_email,
        company="Lytrose Engineering",
        phone="123456789",
        job_title="Engineer",
        notes="Automated test check",
        status="pending"
    )
    reg_req.set_password("Secret123!")
    db.session.add(reg_req)
    
    pending_user = User(
        email=test_email,
        first_name="Test",
        last_name="Applicant",
        company="Lytrose Engineering",
        phone="123456789",
        job_title="Engineer",
        role="engineer",
        status="pending_approval"
    )
    pending_user.set_password("Secret123!")
    db.session.add(pending_user)
    
    try:
        db.session.commit()
        print("db.session.commit() SUCCEEDED! reg_req.id =", reg_req.id, "pending_user.id =", pending_user.id)
    except Exception as e:
        print("db.session.commit() FAILED:", e)
        db.session.rollback()
    
    # Now test email dispatch
    try:
        res1 = send_registration_request_notification(reg_req, target_email=["admin@pumpmasterpro.com"], org_name="Lytrose Engineering")
        print("send_registration_request_notification result:", res1)
    except Exception as e:
        print("send_registration_request_notification EXCEPTION:", e)
        
    try:
        res2 = send_registration_received_confirmation(reg_req, org_name="Lytrose Engineering")
        print("send_registration_received_confirmation result:", res2)
    except Exception as e:
        print("send_registration_received_confirmation EXCEPTION:", e)
        
    # Clean up test records
    User.query.filter_by(email=test_email).delete()
    RegistrationRequest.query.filter_by(email=test_email).delete()
    db.session.commit()
    print("Cleanup completed.")
