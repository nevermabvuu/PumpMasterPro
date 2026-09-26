import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

def send_test_url(url_test):
    msg = MIMEMultipart('alternative')
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
    msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
    msg['To'] = 'admin@pumpmasterpro.com'
    msg['Subject'] = 'Test URL Check'
    body = f'Please visit: {url_test}'
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    msg.attach(MIMEText(f'<p><a href="{url_test}">Click here</a></p>', 'html', 'utf-8'))
    
    server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
    server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    try:
        server.sendmail('admin@pumpmasterpro.com', ['admin@pumpmasterpro.com'], msg.as_string())
        print(f'SUCCESS with URL: {url_test}')
    except Exception as e:
        print(f'FAILED with URL {url_test}: {e}')
    server.quit()

print('Testing with 127.0.0.1:')
send_test_url('http://127.0.0.1:8000/admin/registration-requests')

print('Testing with pumpmasterpro.com:')
send_test_url('https://www.pumpmasterpro.com/admin/registration-requests')
