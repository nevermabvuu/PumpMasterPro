import sys
import os

# Add pump-app to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from app import app
from models import RegistrationRequest
from services.email_service import send_registration_received_confirmation

with app.app_context():
    print("=" * 60)
    print("SENDING TEST CONFIRMATION TO never@tasonline.co.za WITH LIVE SPF")
    print("=" * 60)
    
    # Query request for never@tasonline.co.za
    req = RegistrationRequest.query.filter_by(email='never@tasonline.co.za').order_by(RegistrationRequest.id.desc()).first()
    if not req:
        print("RegistrationRequest not found, creating dummy object...")
        class DummyReq:
            first_name = "Never"
            full_name = "Never Mabvuu"
            email = "never@tasonline.co.za"
            company = "Lytrose Engineering"
            job_title = "Senior Hydraulic Engineer"
            created_at = None
        req = DummyReq()
    
    print(f"Sending confirmation for: {req.full_name} ({req.email})...")
    ok, msg = send_registration_received_confirmation(req, org_name="Lytrose Engineering")
    print(f"Result: {ok} -> {msg}")
    print("=" * 60)
