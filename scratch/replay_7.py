import smtplib
import time
import imaplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

msg = MIMEMultipart('alternative')
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
msg['To'] = 'admin@pumpmasterpro.com'
msg['Subject'] = 'Test To admin@pumpmasterpro.com'

msg.attach(MIMEText('Test body text again', 'plain', 'utf-8'))
msg.attach(MIMEText('<p>Test body html again</p>', 'html', 'utf-8'))

server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
server.quit()
print("Sent exact replay of Message 7...")

time.sleep(8)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    mail.select(f'"{box}"')
    typ, data = mail.search(None, 'ALL')
    for mid in reversed(data[0].split()[-3:]):
        typ, msg_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE X-SPAM-STATUS)])')
        hdr = msg_data[0][1].decode('latin1', errors='replace').strip()
        if 'Test body' in str(msg_data) or 'Test To admin' in hdr:
            print(f"FOUND in [{box}] ID {mid.decode()}:")
            print(hdr)
            break

mail.logout()
