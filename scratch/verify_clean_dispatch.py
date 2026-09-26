import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from app import app
from services.email_service import send_registration_received_confirmation, send_registration_request_notification
from types import SimpleNamespace
from datetime import datetime

with app.app_context():
    mock_req = SimpleNamespace(
        id=1001,
        first_name="Never",
        last_name="Mabvuu",
        full_name="Never Mabvuu",
        email="nevermabvuu@gmail.com",
        company="Lytrose Engineering",
        job_title="Senior Hydraulic Engineer",
        phone="+27 71 234 5678",
        notes="Automated clean delivery verification",
        created_at=datetime.utcnow()
    )
    
    print("Testing clean confirmation email to applicant (nevermabvuu@gmail.com)...")
    ok1, msg1 = send_registration_received_confirmation(mock_req, org_name="Lytrose Engineering")
    print(f"Confirmation Result: {ok1} -> {msg1}")
    
    print("\nTesting admin alert email (admin@pumpmasterpro.com)...")
    ok2, msg2 = send_registration_request_notification(mock_req, target_email="admin@pumpmasterpro.com", org_name="Lytrose Engineering")
    print(f"Admin Alert Result: {ok2} -> {msg2}")
