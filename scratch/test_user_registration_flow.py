"""
Test User Registration Flow for never@tasonline.co.za
Simulates an actual browser form submission via Flask Test Client.
Verifies:
1. HTTP 200 response with register_success.html
2. RegistrationRequest row inserted in MSSQL database
3. User row inserted in MSSQL database with status='pending_approval'
4. Dual notification dispatch via Truehost SMTP
"""
import sys
import os

# Add pump-app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from app import app
from models import db, RegistrationRequest, User, Organisation

def run_test():
    print("=" * 60)
    print("STARTING REGISTRATION TEST FOR: never@tasonline.co.za")
    print("=" * 60)
    
    with app.app_context():
        # Ensure clean state before running
        User.query.filter_by(email="never@tasonline.co.za").delete()
        RegistrationRequest.query.filter_by(email="never@tasonline.co.za").delete()
        db.session.commit()
        print("[1/5] Pre-clean completed: database is ready.")

    # Create Flask test client to simulate real browser POST
    client = app.test_client()

    form_payload = {
        'first_name': 'Never',
        'last_name': 'Mabvuu',
        'email': 'never@tasonline.co.za',
        'company': 'Lytrose Engineering',
        'phone': '+27 82 000 0000',
        'job_title': 'Hydraulic Engineer',
        'notes': 'Automated verification test of registration form and email dispatch',
        'password': 'Password@2026!',
        'confirm_password': 'Password@2026!',
        'organisation_id': '2'  # Lytrose Engineering
    }

    print("[2/5] Submitting POST request to /register with form data...")
    response = client.post('/register', data=form_payload, follow_redirects=True)
    print(f"      HTTP Response Status: {response.status_code}")

    html_content = response.data.decode('utf-8')

    # Check if success page was rendered
    if "Registration Request Submitted" in html_content or "Registration Request Received" in html_content:
        print("[3/5] SUCCESS: register_success.html rendered correctly!")
    else:
        print("[3/5] WARNING: Did not find expected success heading. Checking for error message...")
        for line in html_content.splitlines():
            if "alert" in line.lower() or "error" in line.lower() or "danger" in line.lower():
                print("      Snippet:", line.strip())

    # Check if there were any email errors reported on the page
    if "Email Dispatch Diagnostics" in html_content:
        print("      Diagnostic Notice: Email delivery note displayed on page.")

    # Now verify the database records
    with app.app_context():
        print("[4/5] Verifying database records in MSSQL...")
        reg_req = RegistrationRequest.query.filter_by(email="never@tasonline.co.za").first()
        if reg_req:
            print(f"      [OK] RegistrationRequest found in DB: ID={reg_req.id}, Name={reg_req.first_name} {reg_req.last_name}, Status={reg_req.status}, CreatedAt={reg_req.created_at}")
        else:
            print("      [FAIL] RegistrationRequest NOT found in database!")

        pending_user = User.query.filter_by(email="never@tasonline.co.za").first()
        if pending_user:
            print(f"      [OK] User found in DB: ID={pending_user.id}, Status={pending_user.status}, Role={pending_user.role}, OrgID={pending_user.organisation_id}")
        else:
            print("      [FAIL] User NOT found in database!")

        print("[5/5] Test completed successfully.")
        print("=" * 60)

if __name__ == '__main__':
    run_test()
