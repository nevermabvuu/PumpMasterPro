import smtplib
import time
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

def send_isolated(tag, subject, plain, html, extra_headers=None):
    msg = MIMEMultipart('alternative')
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
    msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
    msg['To'] = 'admin@pumpmasterpro.com'
    msg['Subject'] = f"{tag} {subject}"
    
    if extra_headers:
        for k, v in extra_headers.items():
            msg[k] = v
            
    msg.attach(MIMEText(plain, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
    server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
    server.quit()
    print(f"Sent {tag}: {subject}")

print("Sending test variations...")

# T1: Minimal exact like Message 7
send_isolated("T1_MINIMAL", "Simple Hello World", "Simple text", "<p>Simple html</p>")
time.sleep(2)

# T2: Registration Subject with minimal body
send_isolated("T2_REGSUBJ", "Access Request Received", "Simple text", "<p>Simple html</p>")
time.sleep(2)

# T3: With Auto-Submitted header
send_isolated("T3_AUTOSUBMITTED", "Simple Hello World with AutoSubmitted", "Simple text", "<p>Simple html</p>", 
              extra_headers={"Auto-Submitted": "auto-generated"})
time.sleep(2)

# T4: Minimal with links to https://www.pumpmasterpro.com/login
send_isolated("T4_HTTPSLINK", "Simple With Link", 
              "Login at https://www.pumpmasterpro.com/login", 
              "<p>Login at <a href='https://www.pumpmasterpro.com/login'>https://www.pumpmasterpro.com/login</a></p>")
time.sleep(2)

# T5: Minimal with word 'Verification' and 'Registration'
send_isolated("T5_VERIFYWORD", "Registration Application Pending Verification", 
              "Verification needed for application", 
              "<p>Verification needed for application</p>")

print("\nWaiting 10 seconds for Truehost processing...")
time.sleep(10)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for tag in ["T1_MINIMAL", "T2_REGSUBJ", "T3_AUTOSUBMITTED", "T4_HTTPSLINK", "T5_VERIFYWORD"]:
    found = False
    for box in ['INBOX', 'Junk']:
        mail.select(f'"{box}"')
        typ, data = mail.search(None, f'SUBJECT "{tag}"')
        if data[0]:
            mid = data[0].split()[-1]
            typ, msg_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT X-SPAM-STATUS X-SPAM-SCORE)])')
            hdr = msg_data[0][1].decode('latin1', errors='replace').strip()
            print("="*60)
            print(f"RESULT FOR {tag} in [{box}]:")
            print(hdr)
            found = True
            break
    if not found:
        print(f"NOT FOUND: {tag}")

mail.logout()
