import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from app import app
from services.email_service import send_registration_received_confirmation
from types import SimpleNamespace
from datetime import datetime

with app.app_context():
    mock_req_tas = SimpleNamespace(
        id=1002,
        first_name="Never",
        last_name="Mabvuu",
        full_name="Never Mabvuu",
        email="never@tasonline.co.za",
        company="Lytrose Engineering",
        job_title="Senior Hydraulic Engineer",
        phone="+27 71 234 5678",
        notes="Testing clean high contrast layout",
        created_at=datetime.utcnow()
    )
    
    mock_req_gmail = SimpleNamespace(
        id=1003,
        first_name="Never",
        last_name="Mabvuu",
        full_name="Never Mabvuu",
        email="nevermabvuu@gmail.com",
        company="Lytrose Engineering",
        job_title="Senior Hydraulic Engineer",
        phone="+27 71 234 5678",
        notes="Testing clean high contrast layout",
        created_at=datetime.utcnow()
    )
    
    print("Dispatching clean confirmation to never@tasonline.co.za...")
    ok1, msg1 = send_registration_received_confirmation(mock_req_tas, org_name="Lytrose Engineering")
    print(f"TasOnline Result: {ok1} -> {msg1}")
    
    import time
    time.sleep(1)
    
    print("\nDispatching clean confirmation to nevermabvuu@gmail.com...")
    ok2, msg2 = send_registration_received_confirmation(mock_req_gmail, org_name="Lytrose Engineering")
    print(f"Gmail Result: {ok2} -> {msg2}")
