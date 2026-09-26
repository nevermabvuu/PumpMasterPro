import smtplib
import time
import imaplib
import email
import sys
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

def send_test(test_id, subject, html_content, text_content):
    msg = MIMEMultipart('alternative')
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
    msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
    msg['Sender'] = 'admin@pumpmasterpro.com'
    msg['To'] = 'admin@pumpmasterpro.com'
    msg['Subject'] = subject
    msg['Auto-Submitted'] = 'auto-generated'
    msg['X-Mailer'] = 'Pump Master Pro Mailer v2.0'
    
    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
    server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
    server.quit()
    print(f"Sent {test_id}: {subject}")

# Var 1: Exact current subject (with em-dash) + Simple body
send_test("V1_EmDashSubj", 
          "Pump Master Pro: Access Request Received — Pending Verification",
          "<p>Simple confirmation body test.</p>", 
          "Simple confirmation body test.")

# Var 2: ASCII hyphen + No 'Verification' word
send_test("V2_AsciiHyphen", 
          "Pump Master Pro: Online Registration Request Received",
          "<p>Simple confirmation body test.</p>", 
          "Simple confirmation body test.")

# Var 3: Full HTML template but with clean ASCII subject
from services.email_service import get_app_base_url
login_url = f"{get_app_base_url()}/login"
html_clean = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e1e4e8; border-radius: 8px;">
  <h2 style="color: #0366d6;">Pump Master Pro</h2>
  <p>Hello Never,</p>
  <p>Thank you for submitting your registration request for <strong>Lytrose Engineering</strong>.</p>
  <p>Your request has been received and is currently under review by our engineering administrators.</p>
  <p>Once your profile is activated, you may sign in at <a href="{login_url}">{login_url}</a>.</p>
  <hr style="border: 0; border-top: 1px solid #e1e4e8; margin: 20px 0;">
  <p style="font-size: 12px; color: #586069;">Pump Master Pro Engineering Suite &bull; Lytrose Engineering</p>
</div>
"""
text_clean = f"""
Pump Master Pro
Hello Never,
Thank you for submitting your registration request for Lytrose Engineering.
Your request has been received and is currently under review by our engineering administrators.
Once your profile is activated, you may sign in at {login_url}.

Pump Master Pro Engineering Suite • Lytrose Engineering
"""

send_test("V3_CleanTemplate",
          "Pump Master Pro: Registration Application Acknowledgment",
          html_clean,
          text_clean)

print("\nWaiting 8 seconds for delivery and SpamAssassin scoring...")
time.sleep(8)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for var_name in ["V1_EmDashSubj", "V2_AsciiHyphen", "V3_CleanTemplate"]:
    found = False
    for box in ['INBOX', 'Junk']:
        mail.select(f'"{box}"')
        typ, data = mail.search(None, f'BODY "{var_name}"')
        if not data[0]:
            # search by subject
            typ, data = mail.search(None, 'ALL')
        ids = data[0].split()
        for mid in reversed(ids[-5:]):
            typ, msg_data = mail.fetch(mid, '(RFC822)')
            parsed = email.message_from_bytes(msg_data[0][1])
            raw_body = str(msg_data[0][1])
            if var_name in raw_body or (var_name == "V1_EmDashSubj" and "V1" in str(parsed.get('Subject', ''))):
                print("=" * 60)
                print(f"RESULT FOR {var_name}:")
                print(f"  Folder:         {box}")
                print(f"  Subject Header: {parsed.get('Subject')}")
                print(f"  X-Spam-Status:  {parsed.get('X-Spam-Status')}")
                print(f"  X-Spam-Score:   {parsed.get('X-Spam-Score')}")
                found = True
                break
        if found:
            break

mail.logout()
