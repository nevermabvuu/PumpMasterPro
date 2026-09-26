import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))
from app import app
from models import RegistrationRequest
from services.email_service import send_email, get_lytrose_registration_email

with app.app_context():
    req = RegistrationRequest.query.order_by(RegistrationRequest.id.desc()).first()
    
    # Test 1: Just subject
    print("Testing Test 1: Simple body with actual Subject...")
    subject = f"[Pump Master Pro] New Registration Request: {req.full_name} (Lytrose Engineering)"
    s1, m1 = send_email('admin@pumpmasterpro.com', subject, "<p>Simple body test</p>", "Simple body test")
    print("Test 1 Result:", s1, m1)
    
    # Test 2: Different subject with actual HTML body
    print("\nTesting Test 2: Different subject...")
    subject2 = f"New Access Request: {req.full_name}"
    s2, m2 = send_email('admin@pumpmasterpro.com', subject2, "<p>Simple body test 2</p>", "Simple body test 2")
    print("Test 2 Result:", s2, m2)
