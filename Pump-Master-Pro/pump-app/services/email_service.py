"""
services/email_service.py — Email Notification Service for PumpSelect Pro.

Beginners Note:
Handles dispatching email notifications when users submit online registration
requests or when administrators approve user access.
Configurable via standard environment variables:
  - SMTP_HOST (e.g. smtp.gmail.com)
  - SMTP_PORT (e.g. 587 or 465)
  - SMTP_USER
  - SMTP_PASSWORD
  - SMTP_FROM

Target administrative recipient for new registration requests:
  nevermabvuu@gmail.com
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)

# Primary admin email as requested by the user
ADMIN_NOTIFICATION_EMAIL = os.environ.get('ADMIN_NOTIFICATION_EMAIL', 'nevermabvuu@gmail.com')

# SMTP configuration from environment variables
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER or 'PumpSelect Pro <no-reply@pumpselectpro.com>')
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000')


def is_smtp_configured():
    """Check if SMTP credentials are fully provided in the environment."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_email, subject, html_content, text_content=""):
    """
    Beginners Note: Generic email sending utility.
    If SMTP credentials are provided, connects via STARTTLS and dispatches email.
    If credentials are not yet configured, cleanly logs the email contents for development.
    """
    if not text_content:
        text_content = html_content.replace('<br>', '\n').replace('</p>', '\n\n')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM
    msg['To'] = to_email

    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))

    if not is_smtp_configured():
        logger.info("[DEV EMAIL LOG] SMTP not configured. Notification email output:")
        safe_subj = str(subject).encode('ascii', errors='replace').decode('ascii')
        safe_body = str(text_content).encode('ascii', errors='replace').decode('ascii')
        print(f"\n=======================================================")
        print(f"[NOTIFICATION TO]: {to_email}")
        print(f"[SUBJECT]: {safe_subj}")
        print(f"-------------------------------------------------------")
        print(safe_body.strip())
        print(f"=======================================================\n")
        return True, "Email logged to console (SMTP credentials not configured in environment)."

    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
            
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Notification email dispatched successfully to {to_email}")
        return True, f"Email delivered to {to_email}"
    except Exception as e:
        logger.error(f"Failed to dispatch email to {to_email}: {e}")
        print(f"[SMTP ERROR]: Failed to send to {to_email}: {e}")
        return False, str(e)


def send_registration_request_notification(reg_request):
    """
    Beginners Note:
    Dispatches a high-priority registration request alert to 'nevermabvuu@gmail.com'
    with complete applicant metadata and direct review links.
    """
    subject = f"[PumpSelect Pro] New Access Request: {reg_request.full_name} ({reg_request.company or 'Individual'})"
    review_url = f"{APP_BASE_URL}/admin/registration-requests"

    req_time = reg_request.created_at.strftime('%Y-%m-%d %H:%M UTC') if reg_request.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    text_content = f"""
NEW USER ACCESS REQUEST — PUMPSELECT PRO
==================================================
An engineer or organization has requested online access to PumpSelect Pro:

Applicant Name:    {reg_request.full_name}
Work Email:        {reg_request.email}
Company / Org:     {reg_request.company or 'Not Specified'}
Job Title / Role:  {reg_request.job_title or 'Not Specified'}
Phone Number:      {reg_request.phone or 'Not Provided'}
Request Date/Time: {req_time}

Reason / Notes:
{reg_request.notes or 'None provided.'}

ADMIN ACTION REQUIRED:
Review and approve or reject this request at:
{review_url}
==================================================
PumpSelect Pro Curve Engine Suite
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
    .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; max-width: 600px; margin: 0 auto; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }}
    .header {{ background: linear-gradient(135deg, #1c2330 0%, #161b22 100%); padding: 24px; border-bottom: 1px solid #30363d; text-align: center; }}
    .header h2 {{ color: #58a6ff; margin: 0 0 6px 0; font-size: 20px; }}
    .header p {{ color: #8b949e; margin: 0; font-size: 13px; }}
    .content {{ padding: 24px; }}
    .table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
    .table td {{ padding: 10px 12px; border-bottom: 1px solid #21262d; font-size: 13px; }}
    .table td.label {{ color: #8b949e; width: 140px; font-weight: 600; }}
    .table td.value {{ color: #e6edf3; font-weight: 500; }}
    .notes-box {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 14px; margin-top: 10px; font-size: 13px; color: #e6edf3; white-space: pre-wrap; }}
    .btn {{ display: inline-block; background-color: #58a6ff; color: #0d1117 !important; text-decoration: none; font-weight: bold; font-size: 14px; padding: 12px 24px; border-radius: 6px; text-align: center; margin: 15px 0; }}
    .footer {{ background-color: #0d1117; padding: 16px; text-align: center; font-size: 11px; color: #6e7681; border-top: 1px solid #30363d; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>PumpSelect Pro &mdash; Online Registration Request</h2>
      <p>A new user has submitted an access verification request</p>
    </div>
    <div class="content">
      <p style="margin-top: 0; font-size: 14px; color: #e6edf3;">Hello Administrator,</p>
      <p style="font-size: 13px; color: #8b949e;">The following applicant has requested an online engineering account on <strong>PumpSelect Pro</strong>:</p>
      
      <table class="table">
        <tr><td class="label">Full Name</td><td class="value"><strong>{reg_request.full_name}</strong></td></tr>
        <tr><td class="label">Work Email</td><td class="value"><a href="mailto:{reg_request.email}" style="color:#58a6ff; text-decoration:none;">{reg_request.email}</a></td></tr>
        <tr><td class="label">Company / Org</td><td class="value">{reg_request.company or '<em style="color:#6e7681">Not specified</em>'}</td></tr>
        <tr><td class="label">Job Title / Role</td><td class="value">{reg_request.job_title or '<em style="color:#6e7681">Not specified</em>'}</td></tr>
        <tr><td class="label">Phone Number</td><td class="value">{reg_request.phone or '<em style="color:#6e7681">Not provided</em>'}</td></tr>
        <tr><td class="label">Request Time</td><td class="value">{req_time}</td></tr>
      </table>

      <div style="margin-top: 14px;">
        <span style="font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase;">Applicant Reason & Notes:</span>
        <div class="notes-box">{reg_request.notes or 'No additional notes provided by applicant.'}</div>
      </div>

      <div style="text-align: center; margin-top: 24px;">
        <a href="{review_url}" class="btn">Open Admin Request Console &rarr;</a>
      </div>
    </div>
    <div class="footer">
      Automated dispatch from PumpSelect Pro Curve Engine v5.0 &bull; Notification sent to {ADMIN_NOTIFICATION_EMAIL}
    </div>
  </div>
</body>
</html>
"""
    return send_email(ADMIN_NOTIFICATION_EMAIL, subject, html_content, text_content)


def send_registration_decision_notification(reg_request, approved=True, notes=""):
    """
    Beginners Note:
    Dispatches a confirmation email to the applicant once the administrator
    approves or rejects their online registration request.
    """
    login_url = f"{APP_BASE_URL}/login"
    
    if approved:
        subject = "[PumpSelect Pro] Welcome - Your Access Has Been Approved"
        text_content = f"""
Hello {reg_request.first_name},

Great news! Your online access request for PumpSelect Pro has been reviewed and approved by the engineering administration.

You may now log in to your account with your registered email ({reg_request.email}) and password:
{login_url}

{f"Administrator Note: {notes}" if notes else ""}

Thank you,
PumpSelect Pro Engineering Team
"""
        html_content = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px;">
  <div style="max-width:550px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;">
    <h2 style="color:#3fb950;margin-top:0;">Access Approved!</h2>
    <p>Hello <strong>{reg_request.first_name}</strong>,</p>
    <p>Your access request for <strong>PumpSelect Pro</strong> has been approved. You are now equipped with full access to industrial pump selection, catalogue analysis, and PDF datasheet generation.</p>
    <div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;margin:16px 0;">
      <div style="font-size:12px;color:#8b949e;">Login Email:</div>
      <div style="font-size:14px;color:#e6edf3;font-weight:600;">{reg_request.email}</div>
    </div>
    {f'<p style="font-size:13px;color:#8b949e;"><em>Admin Note: {notes}</em></p>' if notes else ''}
    <div style="text-align:center;margin:24px 0;">
      <a href="{login_url}" style="background:#58a6ff;color:#0d1117;padding:10px 20px;border-radius:6px;font-weight:bold;text-decoration:none;display:inline-block;">Sign In to PumpSelect Pro</a>
    </div>
    <p style="font-size:11px;color:#6e7681;border-top:1px solid #30363d;padding-top:12px;margin-bottom:0;">PumpSelect Pro Curve Engine v5.0</p>
  </div>
</body>
</html>
"""
    else:
        subject = "PumpSelect Pro Access Request Status Update"
        text_content = f"""
Hello {reg_request.first_name},

Thank you for your interest in PumpSelect Pro. After review, your registration request could not be approved at this time.

{f"Reason: {notes}" if notes else ""}

If you believe this is in error, please contact support or your organization administrator.
"""
        html_content = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px;">
  <div style="max-width:550px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;">
    <h3 style="color:#f85149;margin-top:0;">Access Request Update</h3>
    <p>Hello <strong>{reg_request.first_name}</strong>,</p>
    <p>Your access request for <strong>PumpSelect Pro</strong> could not be approved at this time.</p>
    {f'<p style="font-size:13px;color:#8b949e;"><em>Note: {notes}</em></p>' if notes else ''}
    <p style="font-size:12px;color:#8b949e;">If you require assistance or believe this was an error, please reach out to engineering support.</p>
  </div>
</body>
</html>
"""

    return send_email(reg_request.email, subject, html_content, text_content)
