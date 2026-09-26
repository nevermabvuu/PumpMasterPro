import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from types import SimpleNamespace
from datetime import datetime
from services.email_service import send_registration_received_confirmation

mock_req = SimpleNamespace(
    id=999,
    first_name="Never",
    last_name="Mabvuu",
    full_name="Never Mabvuu",
    email="nevermabvuu@gmail.com",
    company="Lytrose Engineering",
    job_title="Lead Engineer",
    phone="+27 12 345 6789",
    notes="Test confirmation",
    created_at=datetime.utcnow()
)

print("Calling send_registration_received_confirmation...")
ok, msg = send_registration_received_confirmation(mock_req, org_name="Lytrose Engineering")
print("OK:", ok)
print("MSG:", msg)
