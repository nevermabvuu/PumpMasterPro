import smtplib
import time
import imaplib
import email
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

def send_var(name, extra_headers=None, body="Hello World test"):
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Date'] = formatdate(localtime=True)
    msg['From'] = 'admin@pumpmasterpro.com'
    msg['To'] = 'admin@pumpmasterpro.com'
    msg['Subject'] = f"DiagTest {name}"
    if extra_headers:
        for k, v in extra_headers.items():
            msg[k] = v

    server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
    server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
    server.quit()
    print(f"Sent {name}")

# Test 1: Bare minimal plain text, NO extra headers, NO make_msgid
send_var("V1_Bare")

# Test 2: With make_msgid()
send_var("V2_MsgId", {'Message-ID': make_msgid()})

# Test 3: With make_msgid(domain='pumpmasterpro.com')
send_var("V3_MsgIdDomain", {'Message-ID': make_msgid(domain='pumpmasterpro.com')})

print("\nWaiting 7s for delivery...")
time.sleep(7)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for var_name in ["V1_Bare", "V2_MsgId", "V3_MsgIdDomain"]:
    for box in ['INBOX', 'Junk']:
        mail.select(f'"{box}"')
        typ, data = mail.search(None, f'SUBJECT "{var_name}"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            parsed = email.message_from_bytes(msg_data[0][1])
            print(f"\n{var_name} delivered in: {box}")
            print(f"  Subject: {parsed.get('Subject')}")
            print(f"  X-Spam-Status: {parsed.get('X-Spam-Status')}")
            print(f"  Tests: {parsed.get('X-Spam-Status', '').split('tests=')[-1].split('autolearn=')[0].strip() if 'tests=' in str(parsed.get('X-Spam-Status')) else 'None'}")
            break

mail.logout()
