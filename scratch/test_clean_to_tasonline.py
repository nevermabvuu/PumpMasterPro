import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, formataddr

# Test clean, high-contrast, standard email without dark-mode rgba or low-contrast text
subject = "Pump Master Pro Registration Update"

plain_text = """Hello Never,

Thank you for your registration with Pump Master Pro.

Your account details for Lytrose Engineering have been received by the administrator.

We will notify you once your engineering profile has been set up.

Thank you,
Pump Master Pro
https://www.pumpmasterpro.com
"""

html_content = """<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #222222; background-color: #f7f9fa; margin: 0; padding: 20px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border: 1px solid #dcdcdc; border-radius: 6px; padding: 24px;">
    <h2 style="color: #0b4f8a; margin-top: 0;">Pump Master Pro</h2>
    <p>Hello <strong>Never</strong>,</p>
    <p>Thank you for registering with <strong>Pump Master Pro</strong>.</p>
    <p>Your account details for <strong>Lytrose Engineering</strong> have been received by the administrator.</p>
    <p>We will notify you once your engineering profile has been set up.</p>
    <hr style="border: 0; border-top: 1px solid #e5e5e5; margin: 20px 0;">
    <p style="font-size: 12px; color: #555555; margin: 0;">Pump Master Pro &bull; Engineering Hydraulics Platform</p>
  </div>
</body>
</html>
"""

msg = MIMEMultipart('alternative')
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
msg['From'] = formataddr(('Pump Master Pro', 'admin@pumpmasterpro.com'))
msg['Reply-To'] = 'admin@pumpmasterpro.com'
msg['To'] = 'never@tasonline.co.za'
msg['Subject'] = subject

msg.attach(MIMEText(plain_text, 'plain', 'utf-8'))
msg.attach(MIMEText(html_content, 'html', 'utf-8'))

server = smtplib.SMTP_SSL('workplace.truehost.cloud', 465, timeout=15)
server.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
server.sendmail('admin@pumpmasterpro.com', ['never@tasonline.co.za'], msg.as_string())
server.quit()
print("Sent light-mode, standard-contrast email to never@tasonline.co.za")
