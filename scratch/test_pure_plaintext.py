import smtplib
import time
import imaplib
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

msg = MIMEText('This is a simple plain text status update without any links or formatting.', 'plain', 'utf-8')
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
msg['To'] = 'admin@pumpmasterpro.com'
msg['Subject'] = 'System Status Notification Update'

server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
server.quit()
print("Sent Plain Text Only email...")

time.sleep(8)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    mail.select(f'"{box}"')
    typ, data = mail.search(None, f'SUBJECT "System Status Notification Update"')
    if data[0]:
        mid = data[0].split()[-1]
        typ, msg_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT X-SPAM-STATUS X-SPAM-SCORE)])')
        hdr = msg_data[0][1].decode('latin1', errors='replace').strip()
        print("="*60)
        print(f"FOUND in [{box}]:")
        print(hdr)

mail.logout()
