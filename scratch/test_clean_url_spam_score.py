import os
import sys
import time
import imaplib
import email

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from services.email_service import send_email

subject = "[Pump Master Pro] Test Clean URL Spam Score Check"
login_url = "https://www.pumpmasterpro.com/login"
review_url = "https://www.pumpmasterpro.com/admin/registration-requests"

text_body = f"""
Hello Administrator,

This is a test notification using clean domain links:
Console: {review_url}
Login: {login_url}

Best regards,
Pump Master Pro Engineering Team
https://www.pumpmasterpro.com
"""

html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 20px;">
  <h2>Pump Master Pro Notification</h2>
  <p>This is a test notification using clean domain links:</p>
  <p><a href="{review_url}" style="color: #58a6ff;">Open Admin Console</a></p>
  <p><a href="{login_url}" style="color: #58a6ff;">Sign In</a></p>
  <p>Pump Master Pro Engineering Team<br><a href="https://www.pumpmasterpro.com" style="color: #8b949e;">www.pumpmasterpro.com</a></p>
</body>
</html>
"""

print("Sending test email to admin@pumpmasterpro.com with HTTPS domain URLs...")
ok, msg = send_email("admin@pumpmasterpro.com", subject, html_body, text_body)
print("Send result:", ok, msg)

print("Waiting 5 seconds for mail delivery...")
time.sleep(5)

# Connect to IMAP and inspect
mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    res, count = mail.select(f'"{box}"')
    if res == 'OK':
        typ, data = mail.search(None, f'SUBJECT "{subject}"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            raw_email = msg_data[0][1]
            parsed = email.message_from_bytes(raw_email)
            print(f"\nFOUND in {box}:")
            print("Subject:", parsed.get('Subject'))
            print("X-Spam-Status:", parsed.get('X-Spam-Status'))
            print("X-Spam-Score:", parsed.get('X-Spam-Score'))

mail.logout()
