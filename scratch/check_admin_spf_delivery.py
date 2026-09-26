import sys
import os
import time
import imaplib
import email

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

from app import app
from services.email_service import send_email

with app.app_context():
    subj = "Pump Master Pro: System SPF Verification"
    text = "SPF record is now active in DNS. Testing delivery to admin mailbox."
    html = "<p>SPF record is now active in DNS. Testing delivery to admin mailbox.</p>"
    
    print("Dispatching to admin@pumpmasterpro.com...")
    ok, msg = send_email("admin@pumpmasterpro.com", subj, html, text)
    print("Dispatch result:", ok, msg)

print("Waiting 6s...")
time.sleep(6)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    res, count = mail.select(f'"{box}"')
    if res == 'OK':
        typ, data = mail.search(None, f'SUBJECT "{subj}"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            parsed = email.message_from_bytes(msg_data[0][1])
            print("=" * 50)
            print(f"DELIVERED TO: {box}")
            print("Subject:", parsed.get('Subject'))
            print("X-Spam-Score:", parsed.get('X-Spam-Score'))
            print("X-Spam-Status:", parsed.get('X-Spam-Status'))
            print("=" * 50)
            break

mail.logout()
