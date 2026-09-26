import smtplib
import time
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

# Construct message with proper RFC headers and clean HTTPS domain
msg = MIMEMultipart('alternative')
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
msg['Reply-To'] = 'admin@pumpmasterpro.com'
msg['To'] = 'admin@pumpmasterpro.com'
msg['Subject'] = '[Pump Master Pro] Clean Access Request Notification Test'
msg['Auto-Submitted'] = 'auto-generated'
msg['X-Mailer'] = 'Pump Master Pro Mailer v2.0'

text_body = """
NEW ACCESS REGISTRATION REQUEST — PUMP MASTER PRO
==================================================
A new registration request has been submitted for Lytrose Engineering.

Applicant:  Never Mabvuu
Email:      never@tasonline.co.za
Company:    Lytrose Engineering

Review request in administration console:
https://www.pumpmasterpro.com/admin/registration-requests
==================================================
Pump Master Pro Engineering Suite
Desk: admin@pumpmasterpro.com
"""

html_body = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 24px;">
  <div style="background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; max-width: 580px; margin: 0 auto; padding: 24px;">
    <h2 style="color: #ffffff; margin-top: 0;">Access Request Received</h2>
    <p>A new user has submitted an access verification request for <strong>Lytrose Engineering</strong>.</p>
    <div style="text-align: center; margin: 24px 0;">
      <a href="https://www.pumpmasterpro.com/admin/registration-requests" style="background-color: #58a6ff; color: #0d1117; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Review in Admin Console &rarr;</a>
    </div>
    <p style="font-size: 11px; color: #8b949e; border-top: 1px solid #30363d; padding-top: 12px; margin-bottom: 0;">Pump Master Pro Curve Engine &bull; Registration Desk: <a href="mailto:admin@pumpmasterpro.com" style="color: #58a6ff;">admin@pumpmasterpro.com</a></p>
  </div>
</body>
</html>
"""

msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
msg.attach(MIMEText(html_body, 'html', 'utf-8'))

print("Sending clean test via SMTP_SSL...")
server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
server.quit()
print("Dispatched successfully without SMTP error!")

print("Waiting 6 seconds for delivery to Truehost IMAP...")
time.sleep(6)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    res, count = mail.select(f'"{box}"')
    if res == 'OK':
        typ, data = mail.search(None, 'SUBJECT "Clean Access Request Notification Test"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            parsed = email.message_from_bytes(msg_data[0][1])
            print(f"\n==========================================")
            print(f"DELIVERY FOLDER: {box}")
            print(f"Subject: {parsed.get('Subject')}")
            print(f"From: {parsed.get('From')}")
            print(f"X-Spam-Status: {parsed.get('X-Spam-Status')}")
            print(f"X-Spam-Score: {parsed.get('X-Spam-Score')}")
            print(f"==========================================")

mail.logout()
