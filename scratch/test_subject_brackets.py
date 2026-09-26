import smtplib
import time
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

def send_and_check(subject, test_name):
    msg = MIMEMultipart('alternative')
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
    msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
    msg['Reply-To'] = 'admin@pumpmasterpro.com'
    msg['To'] = 'admin@pumpmasterpro.com'
    msg['Subject'] = subject

    text_body = f"Test: {test_name}\nSubject tested: {subject}\nVisit https://www.pumpmasterpro.com"
    html_body = f"<p>Test: {test_name}</p><p>Subject: {subject}</p><p><a href='https://www.pumpmasterpro.com'>Visit site</a></p>"

    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
    server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
    server.quit()
    print(f"Sent: {subject}")

print("Sending Test 1: Subject WITHOUT square brackets...")
send_and_check("Pump Master Pro Notification - Access Request Received", "No Brackets")

print("Sending Test 2: Standard Subject...")
send_and_check("New Access Request for Lytrose Engineering", "Simple Subject")

print("\nWaiting 7 seconds for delivery...")
time.sleep(7)

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for subj_query in ["No Brackets", "Simple Subject"]:
    found = False
    for box in ['INBOX', 'Junk']:
        res, count = mail.select(f'"{box}"')
        if res == 'OK':
            typ, data = mail.search(None, f'BODY "{subj_query}"')
            ids = data[0].split()
            if ids:
                typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
                parsed = email.message_from_bytes(msg_data[0][1])
                print(f"\n==========================================")
                print(f"TEST: {subj_query} -> FOLDER: {box}")
                print(f"Subject in header: {parsed.get('Subject')}")
                print(f"X-Spam-Status: {parsed.get('X-Spam-Status')}")
                print(f"X-Spam-Score: {parsed.get('X-Spam-Score')}")
                found = True
                break

mail.logout()
