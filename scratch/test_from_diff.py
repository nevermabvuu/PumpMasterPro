import smtplib
import time
import imaplib
import email
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

def test_kam(name, from_hdr, subj, body="Test message"):
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
    msg['From'] = from_hdr
    msg['To'] = 'admin@pumpmasterpro.com'
    msg['Subject'] = subj

    server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
    server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
    server.quit()
    print(f"Sent {name}")

# T1: Simple From without display name
test_kam("T1_NoDisplayName", "admin@pumpmasterpro.com", "System Alert Verification")

# T2: Different From address (e.g. notifications@pumpmasterpro.com or info@pumpmasterpro.com)
test_kam("T2_DiffFrom", "notifications@pumpmasterpro.com", "System Alert Verification 2")

print("Waiting 6s...")
time.sleep(6)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for tname in ["T1_NoDisplayName", "T2_DiffFrom"]:
    for box in ['INBOX', 'Junk']:
        mail.select(f'"{box}"')
        typ, data = mail.search(None, f'SUBJECT "{tname}"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            parsed = email.message_from_bytes(msg_data[0][1])
            print(f"\n{tname} -> {box}")
            print(f"  Score: {parsed.get('X-Spam-Score')}")
            print(f"  Status: {parsed.get('X-Spam-Status')}")
            break

mail.logout()
