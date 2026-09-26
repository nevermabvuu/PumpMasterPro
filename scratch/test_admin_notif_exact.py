import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))
from app import app
from models import RegistrationRequest
from services.email_service import send_registration_request_notification

with app.app_context():
    req = RegistrationRequest.query.filter_by(email='never@tasonline.co.za').first()
    if not req:
        req = RegistrationRequest.query.order_by(RegistrationRequest.id.desc()).first()
    print('Testing with req:', req.id, req.email, req.full_name, req.company)
    
    # Try sending to admin@pumpmasterpro.com
    res, msg = send_registration_request_notification(req, target_email='admin@pumpmasterpro.com')
    print('Result:', res, msg)
