import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

msg = MIMEMultipart('alternative')
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
msg['To'] = 'nevermabvuu@gmail.com'
msg['Subject'] = 'Test Pure Direct Subject 101'
msg.attach(MIMEText('Testing direct sending from pumpmasterpro.com', 'plain', 'utf-8'))
msg.attach(MIMEText('<p>Testing direct sending from pumpmasterpro.com</p>', 'html', 'utf-8'))

server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
try:
    res = server.sendmail('admin@pumpmasterpro.com', ['nevermabvuu@gmail.com'], msg.as_string())
    print("SENDMAIL RESULT:", res)
except Exception as e:
    print("SENDMAIL ERROR:", e)
finally:
    server.quit()
