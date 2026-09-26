import smtplib
import time
import imaplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

# Clean Subject: No "Verification", no "Pending", no em-dash, no brackets
subject = "Pump Master Pro Registration Confirmation"

plain = """Hello Never,

Thank you for registering your profile with Pump Master Pro for Lytrose Engineering.

Your registration details have been received and recorded. The organisation administrator will review your account settings.

You can visit our portal at:
https://www.pumpmasterpro.com

Regards,
Pump Master Pro Team
"""

html = """<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 20px;">
  <div style="max-width: 580px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; background-color: #ffffff;">
    <h2 style="color: #1e3a8a; margin-top: 0;">Pump Master Pro</h2>
    <p>Hello <strong>Never</strong>,</p>
    <p>Thank you for registering your profile with Pump Master Pro for <strong>Lytrose Engineering</strong>.</p>
    <p>Your registration details have been received and recorded. The organisation administrator will review your account settings.</p>
    <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 20px 0;">
      <p style="margin: 0; font-size: 14px;"><strong>Account Email:</strong> admin@pumpmasterpro.com</p>
      <p style="margin: 4px 0 0 0; font-size: 14px;"><strong>Organisation:</strong> Lytrose Engineering</p>
    </div>
    <p>You can visit our portal at <a href="https://www.pumpmasterpro.com" style="color: #2563eb;">www.pumpmasterpro.com</a>.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
    <p style="font-size: 12px; color: #64748b; margin: 0;">Pump Master Pro &bull; Engineering Hydraulics Platform</p>
  </div>
</body>
</html>
"""

msg = MIMEMultipart('alternative')
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
msg['To'] = 'admin@pumpmasterpro.com'
msg['Subject'] = subject

msg.attach(MIMEText(plain, 'plain', 'utf-8'))
msg.attach(MIMEText(html, 'html', 'utf-8'))

server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
server.quit()
print("Sent Clean Variation A to admin@pumpmasterpro.com")

print("Waiting 10 seconds for Truehost processing...")
time.sleep(10)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    mail.select(f'"{box}"')
    typ, data = mail.search(None, f'SUBJECT "Pump Master Pro Registration Confirmation"')
    if data[0]:
        mid = data[0].split()[-1]
        typ, msg_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT X-SPAM-STATUS X-SPAM-SCORE)])')
        hdr = msg_data[0][1].decode('latin1', errors='replace').strip()
        print("="*60)
        print(f"FOUND in [{box}]:")
        print(hdr)

mail.logout()
