import os
import sys
import time
import imaplib
import email

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from app import app
from services.email_service import send_email

with app.app_context():
    subject = "[Pump Master Pro] Verified Clean URL Notification"
    login_url = "https://www.pumpmasterpro.com/login"
    review_url = "https://www.pumpmasterpro.com/admin/registration-requests"

    text_body = f"""
NEW USER ACCESS REQUEST — PUMP MASTER PRO
==================================================
A new user has submitted an access verification request:

Applicant Name:    John Doe
Work Email:        john.doe@example.com
Organisation/Co:   Lytrose Engineering
Job Title / Role:  Senior Hydraulic Engineer

ADMIN ACTION REQUIRED:
Review and approve this request in the administration console:
{review_url}
==================================================
Pump Master Pro Engineering Suite
Desk: admin@pumpmasterpro.com
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 20px;">
  <h2>Pump Master Pro Notification</h2>
  <p>A new user has submitted an access verification request for <strong>Lytrose Engineering</strong>.</p>
  <p><a href="{review_url}" style="background-color:#58a6ff; color:#0d1117; padding:10px 20px; text-decoration:none; font-weight:bold; border-radius:6px; display:inline-block;">Open Admin Console &rarr;</a></p>
  <p style="font-size:12px; color:#8b949e; margin-top:20px;">Pump Master Pro &bull; <a href="https://www.pumpmasterpro.com" style="color:#58a6ff;">www.pumpmasterpro.com</a></p>
</body>
</html>
"""

    print("Sending verified test email to admin@pumpmasterpro.com...")
    ok, msg = send_email(
        "admin@pumpmasterpro.com",
        subject,
        html_body,
        text_body,
        from_email="admin@pumpmasterpro.com",
        reply_to="admin@pumpmasterpro.com"
    )
    print("Send result:", ok, msg)

print("\nWaiting 6 seconds for delivery...")
time.sleep(6)

# Connect to IMAP and inspect
mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    res, count = mail.select(f'"{box}"')
    if res == 'OK':
        typ, data = mail.search(None, f'SUBJECT "Verified Clean URL"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            raw_email = msg_data[0][1]
            parsed = email.message_from_bytes(raw_email)
            print(f"\n==========================================")
            print(f"DELIVERED IN FOLDER: {box}")
            print(f"Subject: {parsed.get('Subject')}")
            print(f"X-Spam-Status: {parsed.get('X-Spam-Status')}")
            print(f"X-Spam-Score: {parsed.get('X-Spam-Score')}")
            print(f"==========================================")

mail.logout()
