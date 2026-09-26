"""
services/email_service.py — Email Notification Service for Pump Master Pro.

Beginners Note:
Handles dispatching email notifications for all stages of user account onboarding:
  1. When a new registration request is submitted:
     - Dispatches the main user registration request alert to whatever email is set
       for user registration in the database for the organisation 'Lytrose Engineering'.
     - If another specific organisation was requested, that organisation's contact email
       is also notified.
     - Dispatches a receipt/acknowledgment email to the applicant confirming their request is pending review.
  2. When an administrator reviews the request (approved or denied):
     - Dispatches response emails to the user (approval or rejection).
     - The responses are sent FROM the exact same Lytrose Engineering registration email.

Configurable via standard environment variables:
  - SMTP_HOST (e.g. smtp.gmail.com, smtp.office365.com, or mail server)
  - SMTP_PORT (e.g. 587 for STARTTLS or 465 for SSL)
  - SMTP_USER
  - SMTP_PASSWORD
  - SMTP_FROM
  - ADMIN_NOTIFICATION_EMAIL (defaults dynamically to Lytrose Engineering DB email)
  - APP_BASE_URL / SITE_URL (defaults to 'https://www.pumpmasterpro.com' or local host)
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid, formataddr
from datetime import datetime

logger = logging.getLogger(__name__)

def get_app_base_url():
    """
    Retrieve base application URL for notification links.
    Always uses the canonical production domain (https://www.pumpmasterpro.com)
    for email templates, ensuring links never leak raw loopback IPs (127.0.0.1:8000)
    which trigger aggressive anti-spam rules (NUMERIC_HTTP_ADDR, KAM_BADIPHTTP).
    """
    url = os.environ.get('APP_BASE_URL') or os.environ.get('SITE_URL') or 'https://www.pumpmasterpro.com'
    url = url.rstrip('/')
    if '127.0.0.1' in url or 'localhost' in url:
        return 'https://www.pumpmasterpro.com'
    return url

APP_BASE_URL = get_app_base_url()
ADMIN_NOTIFICATION_EMAIL = os.environ.get('ADMIN_NOTIFICATION_EMAIL', '').strip()


def get_smtp_config():
    """
    Retrieve up-to-date SMTP configuration dynamically from environment or .env.
    Reloads .env so changes take effect immediately without requiring code changes.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

    host = os.environ.get('SMTP_HOST', '').strip()
    port_val = os.environ.get('SMTP_PORT', '587').strip()
    try:
        port = int(port_val)
    except (ValueError, TypeError):
        port = 587
    user = os.environ.get('SMTP_USER', '').strip()
    password = os.environ.get('SMTP_PASSWORD', '').strip()
    from_addr = os.environ.get('SMTP_FROM', '').strip()

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'from': from_addr,
        'is_configured': bool(host and user and password)
    }


def is_smtp_configured():
    """Check if SMTP credentials are fully provided in the environment."""
    return get_smtp_config()['is_configured']


def get_lytrose_registration_email():
    """
    Beginners Note:
    Returns whatever email is set for user registration in the database for the organisation 'Lytrose Engineering'.
    Priority Order:
      1. 'admin_notification_email' on Organisation record for Lytrose Engineering (id=2 or name ilike 'Lytrose%')
      2. 'contact_email' on Organisation record for Lytrose Engineering
      3. Environment variable SMTP_FROM / SMTP_USER
      4. Fallback default: 'admin@pumpmasterpro.com'
    CRITICAL: Never fall back to an external personal freemail (e.g. @gmail.com) for From headers,
    as sending from @gmail.com through Truehost SMTP triggers instant DMARC/SPF forgery flags.
    """
    try:
        from models import Organisation
        lytrose = Organisation.query.get(2)
        if not lytrose:
            lytrose = Organisation.query.filter(Organisation.name.ilike('%Lytrose%')).first()
        if lytrose:
            alert_email = (getattr(lytrose, 'admin_notification_email', None) or '').strip()
            if alert_email and '@' in alert_email and not alert_email.lower().endswith('@gmail.com'):
                return alert_email
            contact = (getattr(lytrose, 'contact_email', None) or '').strip()
            if contact and '@' in contact:
                return contact
    except Exception as e:
        logger.warning(f"[EMAIL SERVICE] Could not query Lytrose Engineering registration email from DB: {e}")

    # Fallback MUST be the domain mailbox, NEVER an external personal address (like @gmail.com)
    smtp_from = os.environ.get('SMTP_FROM', '').strip()
    smtp_user = os.environ.get('SMTP_USER', '').strip()
    return smtp_from or smtp_user or 'admin@pumpmasterpro.com'


def _normalize_recipients(to_email):
    """Parses email input (string, comma-separated, list, or set) into a list of clean, unique emails."""
    if not to_email:
        return []
    raw_list = []
    if isinstance(to_email, (list, tuple, set)):
        for item in to_email:
            if item:
                raw_list.extend(str(item).split(','))
    elif isinstance(to_email, str):
        raw_list = to_email.split(',')
    else:
        raw_list = [str(to_email)]

    cleaned = []
    seen = set()
    for addr in raw_list:
        c = addr.strip().lower()
        if c and '@' in c and c not in seen:
            seen.add(c)
            cleaned.append(addr.strip())
    return cleaned


def send_email(to_email, subject, html_content, text_content="", from_email=None, reply_to=None):
    """
    Beginners Note: Generic email sending utility.
    Supports single or multiple recipients.
    Dynamically configures 'From' and 'Reply-To' to the Lytrose Engineering registration email
    (or custom from_email if provided).
    If SMTP credentials are provided, connects via STARTTLS or SSL and dispatches email.
    If credentials are not yet configured, cleanly logs the email contents for development.
    """
    recipients = _normalize_recipients(to_email)
    if not recipients:
        logger.warning("[EMAIL SERVICE] No valid recipients provided for dispatch.")
        return False, "No valid recipients specified."

    if not text_content:
        text_content = html_content.replace('<br>', '\n').replace('</p>', '\n\n')

    # Determine sender email: defaults to whatever email is set for Lytrose Engineering in DB (admin@pumpmasterpro.com)
    sender_email = (from_email or get_lytrose_registration_email()).strip()
    # Guard against DMARC spoofing: if sender_email accidentally has @gmail.com or third-party domain, use SMTP_FROM
    if '@gmail.com' in sender_email.lower() or '@yahoo.com' in sender_email.lower() or '@outlook.com' in sender_email.lower():
        smtp_cfg_check = get_smtp_config()
        sender_email = smtp_cfg_check['from'] or smtp_cfg_check['user'] or 'admin@pumpmasterpro.com'

    sender_header = f"Pump Master Pro <{sender_email}>"
    reply_to_header = (reply_to or sender_email).strip()

    smtp_cfg = get_smtp_config()

    # If SMTP is not configured, log clearly to console in dev mode
    if not smtp_cfg['is_configured']:
        logger.warning("[DEV EMAIL LOG] SMTP not configured. Notification output:")
        safe_subj = str(subject).encode('ascii', errors='replace').decode('ascii')
        safe_body = str(text_content).encode('ascii', errors='replace').decode('ascii')
        print(f"\n=======================================================")
        print(f"[PUMP MASTER PRO EMAIL DISPATCH - CONSOLE/DEV MODE]")
        print(f"[NOTE]: Live SMTP credentials (SMTP_HOST, SMTP_USER, SMTP_PASSWORD) not found in .env.")
        print(f"[NOTE]: Actual email was NOT sent across the network.")
        print(f"[TO]: {', '.join(recipients)}")
        print(f"[FROM]: {sender_header}")
        print(f"[REPLY-TO]: {reply_to_header}")
        print(f"[SUBJECT]: {safe_subj}")
        print(f"-------------------------------------------------------")
        print(safe_body.strip())
        print(f"=======================================================\n")
        return False, f"Live SMTP credentials not configured in .env. Logged to server terminal."

    # SMTP is configured — perform actual dispatch
    overall_success = True
    errors = []
    host = smtp_cfg['host']
    port = smtp_cfg['port']
    user = smtp_cfg['user']
    password = smtp_cfg['password']
    envelope_from = smtp_cfg['from'] if (smtp_cfg['from'] and '@' in smtp_cfg['from']) else (user or sender_email)

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()

        server.login(user, password)

        for idx, recipient in enumerate(recipients):
            try:
                # When dispatching to multiple recipients in a single call, reset SMTP state
                # between messages and include a brief pause so Truehost Cloud's spam filter
                # does not trigger a burst/flood rate-limit rejection.
                if idx > 0:
                    try:
                        server.rset()
                    except Exception:
                        pass
                    import time
                    time.sleep(0.6)

                msg = MIMEMultipart('alternative')
                msg['Date'] = formatdate(localtime=True)
                msg['Message-ID'] = make_msgid(domain='pumpmasterpro.com')
                msg['Subject'] = subject
                msg['From'] = formataddr(('Pump Master Pro', sender_email))
                msg['Reply-To'] = reply_to_header
                msg['To'] = recipient

                msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))

                server.sendmail(envelope_from, [recipient], msg.as_string())
                logger.info(f"Email dispatched successfully to {recipient} with From: {sender_header}")
            except Exception as item_err:
                overall_success = False
                errors.append(f"{recipient}: {item_err}")
                logger.error(f"Failed to dispatch email to {recipient}: {item_err}")

        server.quit()
        if overall_success:
            return True, f"Dispatched email to: {', '.join(recipients)}"
        else:
            return False, f"Partial dispatch errors: {'; '.join(errors)}"

    except Exception as e:
        logger.error(f"Failed to connect to SMTP server: {e}")
        print(f"[SMTP SERVER ERROR]: {e}")
        return False, str(e)


def send_registration_request_notification(reg_request, target_email=None, org_name=""):
    """
    Beginners Note:
    Dispatches the main user registration request alert.
    Rule: The main registration request alert is ALWAYS sent to whatever email is set
    for user registration in the database for the organisation 'Lytrose Engineering'.
    Additional recipients (such as a specifically requested organisation contact email)
    are also included. Responses and From headers are also sent from this same email.
    """
    lytrose_reg_email = get_lytrose_registration_email()

    recipients = set()
    # 1. The main user registration request MUST always be sent to Lytrose Engineering's registration email
    if lytrose_reg_email:
        recipients.add(lytrose_reg_email)

    # 2. Also include any specific target email (e.g. another organisation requested by the user)
    if target_email:
        for r in _normalize_recipients(target_email):
            recipients.add(r)

    # 3. Include central admin backup if distinct
    env_admin = (ADMIN_NOTIFICATION_EMAIL or os.environ.get('ADMIN_NOTIFICATION_EMAIL', '')).strip()
    if env_admin and '@' in env_admin:
        recipients.add(env_admin)

    recipients_list = list(recipients)
    if not recipients_list:
        recipients_list = [lytrose_reg_email or ADMIN_NOTIFICATION_EMAIL]

    display_org = (org_name or reg_request.company or 'General Access').strip()
    subject = f"Pump Master Pro: New Registration Request - {reg_request.full_name} ({display_org})"
    review_url = f"{get_app_base_url()}/admin/registration-requests"

    req_time = reg_request.created_at.strftime('%Y-%m-%d %H:%M UTC') if getattr(reg_request, 'created_at', None) else datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    text_content = f"""
NEW USER REGISTRATION REQUEST — PUMP MASTER PRO
==================================================
A new user has submitted an access verification request:

Applicant Name:    {reg_request.full_name}
Work Email:        {reg_request.email}
Organisation/Co:   {display_org}
Job Title / Role:  {reg_request.job_title or 'Not Specified'}
Phone Number:      {reg_request.phone or 'Not Provided'}
Request Date/Time: {req_time}

Applicant Project Reason & Notes:
{reg_request.notes or 'None provided.'}

ADMIN ACTION REQUIRED:
Review and approve or reject this request in the administration console:
{review_url}
==================================================
Pump Master Pro Engineering Suite & Curve Engine
Registration desk: {lytrose_reg_email}
Notification routed to: {', '.join(recipients_list)}
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 24px; }}
    .card {{ background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; max-width: 600px; margin: 0 auto; overflow: hidden; }}
    .header {{ background-color: #0f172a; padding: 22px 24px; text-align: left; }}
    .header h2 {{ color: #ffffff; margin: 0 0 4px 0; font-size: 18px; font-weight: 700; }}
    .header p {{ color: #94a3b8; margin: 0; font-size: 12px; }}
    .content {{ padding: 24px; }}
    .table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
    .table td {{ padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
    .table tr:last-child td {{ border-bottom: none; }}
    .table td.label {{ color: #475569; width: 140px; font-weight: 600; }}
    .table td.value {{ color: #0f172a; font-weight: 500; }}
    .notes-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-top: 6px; font-size: 13px; color: #334155; }}
    .btn {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none; font-weight: 600; font-size: 13px; padding: 10px 20px; border-radius: 6px; margin: 16px 0; }}
    .footer {{ background-color: #f8fafc; padding: 14px 24px; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>Pump Master Pro &bull; New Registration Request</h2>
      <p>A new applicant has submitted an online engineering access request</p>
    </div>
    <div class="content">
      <p style="margin-top: 0; font-size: 14px; color: #0f172a;">Hello Administrator,</p>
      <p style="font-size: 13px; color: #334155; line-height: 1.5;">The following applicant has requested an online account for <strong>{display_org}</strong>:</p>
      
      <table class="table">
        <tr><td class="label">Applicant Name</td><td class="value"><strong>{reg_request.full_name}</strong></td></tr>
        <tr><td class="label">Work Email</td><td class="value"><a href="mailto:{reg_request.email}" style="color: #2563eb;">{reg_request.email}</a></td></tr>
        <tr><td class="label">Organisation</td><td class="value">{display_org}</td></tr>
        <tr><td class="label">Job Title</td><td class="value">{reg_request.job_title or 'Engineer'}</td></tr>
        <tr><td class="label">Phone</td><td class="value">{reg_request.phone or 'Not provided'}</td></tr>
        <tr><td class="label">Submission Date</td><td class="value">{req_time}</td></tr>
      </table>

      <div style="margin-top: 14px;">
        <span style="font-size: 12px; font-weight: 600; color: #475569;">Applicant Notes:</span>
        <div class="notes-box">{reg_request.notes or 'No additional notes provided.'}</div>
      </div>

      <div style="text-align: center; margin-top: 20px;">
        <a href="{review_url}" class="btn">Open Admin Console &rarr;</a>
      </div>
    </div>
    <div class="footer">
      Pump Master Pro Curve Engine &bull; Support: {lytrose_reg_email}
    </div>
  </div>
</body>
</html>"""
    return send_email(recipients_list, subject, html_content, text_content, from_email=lytrose_reg_email, reply_to=lytrose_reg_email)


def send_registration_received_confirmation(reg_request, org_name=""):
    """
    Beginners Note:
    Dispatches an instant confirmation / acknowledgment email to the applicant
    notifying them that their registration request has been received and is
    currently pending review by the organisation administrator.
    Rule: Sent FROM whatever email is set for user registration in the database for 'Lytrose Engineering'.
    """
    lytrose_reg_email = get_lytrose_registration_email()
    display_org = (org_name or reg_request.company or 'Pump Master Pro').strip()
    subject = "Pump Master Pro: Registration Confirmation"
    login_url = f"{get_app_base_url()}/login"
    req_time = reg_request.created_at.strftime('%Y-%m-%d %H:%M UTC') if getattr(reg_request, 'created_at', None) else datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    text_content = f"""
Hello {reg_request.first_name},

Thank you for requesting access to Pump Master Pro.

We have successfully received your online access registration request for {display_org}.

Your application has been routed to the Lytrose Engineering administration desk ({lytrose_reg_email}) and is currently pending verification.

REGISTRATION SUMMARY:
--------------------------------------------------
Applicant Name:       {reg_request.full_name}
Registered Email:     {reg_request.email}
Organisation / Co:    {display_org}
Job Title / Role:     {reg_request.job_title or 'Engineer'}
Request Date & Time:  {req_time}
Status:               Pending Administrator Approval
--------------------------------------------------

WHAT HAPPENS NEXT:
Our engineering administrators review incoming access requests to configure appropriate catalogue visibility and role permissions.
You will receive an activation email as soon as your access has been reviewed and approved.

Once activated, you can sign in to your account at:
{login_url}

If you have questions, reply directly to this email or contact {lytrose_reg_email}.

Thank you,
Pump Master Pro Engineering Team
https://www.pumpmasterpro.com
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 24px; }}
    .card {{ background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; max-width: 600px; margin: 0 auto; overflow: hidden; }}
    .header {{ background-color: #0f172a; padding: 22px 24px; text-align: left; }}
    .header h2 {{ color: #ffffff; margin: 0 0 4px 0; font-size: 18px; font-weight: 700; }}
    .header p {{ color: #94a3b8; margin: 0; font-size: 12px; }}
    .content {{ padding: 24px; }}
    .table {{ width: 100%; border-collapse: collapse; margin: 18px 0; }}
    .table td {{ padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
    .table tr:last-child td {{ border-bottom: none; }}
    .table td.label {{ color: #475569; width: 150px; font-weight: 600; }}
    .table td.value {{ color: #0f172a; font-weight: 500; }}
    .info-box {{ background-color: #eff6ff; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 18px 0; border-radius: 4px; }}
    .info-box h4 {{ margin: 0 0 4px 0; color: #1e40af; font-size: 13px; font-weight: 700; }}
    .info-box p {{ margin: 0; color: #1e3a8a; font-size: 12px; line-height: 1.5; }}
    .footer {{ background-color: #f8fafc; padding: 14px 24px; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>Pump Master Pro</h2>
      <p>Registration Application Acknowledged</p>
    </div>
    <div class="content">
      <p style="margin-top: 0; font-size: 14px; color: #0f172a;">Hello <strong>{reg_request.first_name}</strong>,</p>
      <p style="font-size: 13px; color: #334155; line-height: 1.5;">
        Thank you for submitting your registration request for <strong>{display_org}</strong>. Your profile details have been received and routed to the administrator desk (<strong style="color: #2563eb;">{lytrose_reg_email}</strong>).
      </p>

      <table class="table">
        <tr><td class="label">Applicant Name</td><td class="value"><strong>{reg_request.full_name}</strong></td></tr>
        <tr><td class="label">Account Email</td><td class="value" style="color: #2563eb;">{reg_request.email}</td></tr>
        <tr><td class="label">Organisation</td><td class="value">{display_org}</td></tr>
        <tr><td class="label">Job Title</td><td class="value">{reg_request.job_title or 'Engineer'}</td></tr>
        <tr><td class="label">Submission Date</td><td class="value">{req_time}</td></tr>
      </table>

      <div class="info-box">
        <h4>Next Steps</h4>
        <p>
          Our engineering administrators review submitted requests to assign access privileges. You will receive an email once your account is ready.
        </p>
      </div>

      <p style="font-size: 12px; color: #64748b; line-height: 1.5; margin-bottom: 0;">
        Once approved, you will be able to sign in with your email and password at <a href="{login_url}" style="color: #2563eb;">{login_url}</a>.
      </p>
    </div>
    <div class="footer">
      Pump Master Pro Curve Engine &bull; Support: <a href="mailto:{lytrose_reg_email}" style="color: #64748b;">{lytrose_reg_email}</a>
    </div>
  </div>
</body>
</html>"""
    return send_email(reg_request.email, subject, html_content, text_content, from_email=lytrose_reg_email, reply_to=lytrose_reg_email)


def send_registration_decision_notification(reg_request, approved=True, notes="", role_name="", org_name=""):
    """
    Beginners Note:
    Dispatches a confirmation email to the applicant once the administrator
    approves or rejects their online registration request.
    Rule: Sent FROM whatever email is set for user registration in the database for 'Lytrose Engineering'.
    """
    lytrose_reg_email = get_lytrose_registration_email()
    login_url = f"{get_app_base_url()}/login"
    display_org = (org_name or getattr(reg_request, 'company', None) or 'Pump Master Pro').strip()
    display_role = (role_name or 'Hydraulic Engineer').strip()

    first_name = getattr(reg_request, 'first_name', '') or 'Engineer'
    email = getattr(reg_request, 'email', '')

    if approved:
        subject = "Pump Master Pro: Welcome! Your Access Has Been Approved"
        text_content = f"""
Hello {first_name},

Great news! Your online access request for Pump Master Pro has been reviewed and approved by the engineering administration.

You may now log in to your account with your registered email:
Email: {email}
Organisation: {display_org}
Assigned Role: {display_role}

{f"Administrator Note: {notes}" if notes else ""}

Sign In to your account:
{login_url}

UNLOCKED CAPABILITIES:
- Industrial Pump Sizing & Duty Point Matching
- Pipe Network System Resistance Calculations
- Viscous & Slurry Correction Derating
- High-Resolution PDF Technical Datasheet Generation

Thank you,
Pump Master Pro Engineering Suite
https://www.pumpmasterpro.com
Support & Inquiries: {lytrose_reg_email}
"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
    .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; max-width: 600px; margin: 0 auto; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #162a1d 0%, #161b22 100%); padding: 28px 20px; border-bottom: 1px solid #30363d; text-align: center; }}
    .badge {{ display: inline-block; padding: 4px 12px; font-size: 11px; font-weight: 700; color: #3fb950; background: rgba(63,185,80,0.15); border: 1px solid rgba(63,185,80,0.3); border-radius: 20px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .header h2 {{ color: #ffffff; margin: 0 0 6px 0; font-size: 22px; font-weight: 700; }}
    .header p {{ color: #8b949e; margin: 0; font-size: 13px; }}
    .content {{ padding: 24px; }}
    .account-box {{ background: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin: 18px 0; }}
    .btn {{ display: inline-block; background-color: #3fb950; color: #0d1117 !important; text-decoration: none; font-weight: 700; font-size: 14px; padding: 13px 28px; border-radius: 8px; text-align: center; margin: 18px 0; box-shadow: 0 4px 14px rgba(63,185,80,0.3); }}
    .feature-list {{ margin: 16px 0; padding-left: 20px; font-size: 13px; color: #c9d1d9; line-height: 1.8; }}
    .admin-note {{ background: rgba(210,153,34,0.1); border-left: 3px solid #d29922; padding: 10px 14px; margin: 16px 0; font-size: 12px; color: #e6edf3; border-radius: 0 6px 6px 0; }}
    .footer {{ background-color: #0d1117; padding: 16px; text-align: center; font-size: 11px; color: #6e7681; border-top: 1px solid #30363d; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <span class="badge">&bull; Access Granted &bull;</span>
      <h2>Welcome to Pump Master Pro</h2>
      <p>Your engineering account has been reviewed and authorized</p>
    </div>
    <div class="content">
      <p style="margin-top: 0; font-size: 14px; color: #e6edf3;">Hello <strong>{first_name}</strong>,</p>
      <p style="font-size: 13px; color: #8b949e; line-height: 1.5;">
        Great news! Your access request for <strong>Pump Master Pro</strong> has been reviewed and approved by the administration. You now have full access to pump selection, curve analysis, and technical report generation.
      </p>

      <div class="account-box">
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
          <tr>
            <td style="color:#8b949e; padding:6px 0; font-weight:600; width:130px;">Login Email:</td>
            <td style="color:#58a6ff; padding:6px 0; font-family:monospace; font-weight:600;">{email}</td>
          </tr>
          <tr>
            <td style="color:#8b949e; padding:6px 0; font-weight:600;">Organisation:</td>
            <td style="color:#ffffff; padding:6px 0; font-weight:500;">{display_org}</td>
          </tr>
          <tr>
            <td style="color:#8b949e; padding:6px 0; font-weight:600;">Assigned Role:</td>
            <td style="color:#ffffff; padding:6px 0; font-weight:500;">{display_role}</td>
          </tr>
        </table>
      </div>

      {f'<div class="admin-note"><strong>Administrator Note:</strong> {notes}</div>' if notes else ''}

      <div style="text-align: center; margin: 24px 0 16px 0;">
        <a href="{login_url}" class="btn">Sign In to Pump Master Pro &rarr;</a>
      </div>

      <div style="border-top: 1px solid #21262d; padding-top: 16px; margin-top: 20px;">
        <div style="font-size: 11px; font-weight: 700; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px;">Included Capabilities:</div>
        <ul class="feature-list">
          <li>Centrifugal &amp; Slurry Pump Selection &amp; Duty Point Evaluation</li>
          <li>Pipe Network Resistance &amp; Friction Head Analysis</li>
          <li>Dynamic Operating Curve Generation &amp; Impeller Trimming</li>
          <li>Automated Engineering Datasheet &amp; PDF Export</li>
        </ul>
      </div>
    </div>
    <div class="footer">
      Pump Master Pro Curve Engine &bull; Support: <a href="mailto:{lytrose_reg_email}" style="color:#8b949e;">{lytrose_reg_email}</a>
    </div>
  </div>
</body>
</html>
"""
    else:
        subject = "Pump Master Pro: Access Request Status Update"
        text_content = f"""
Hello {first_name},

Thank you for your interest in Pump Master Pro.

After review, your online registration request for {display_org} could not be approved at this time.

{f"Reason / Administrator Note: {notes}" if notes else ""}

If you believe this is in error or require assistance, please contact our engineering administration desk at {lytrose_reg_email}.

Pump Master Pro Engineering Suite
https://www.pumpmasterpro.com
"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
    .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; max-width: 600px; margin: 0 auto; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #2a1818 0%, #161b22 100%); padding: 28px 20px; border-bottom: 1px solid #30363d; text-align: center; }}
    .badge {{ display: inline-block; padding: 4px 12px; font-size: 11px; font-weight: 700; color: #f85149; background: rgba(248,81,73,0.15); border: 1px solid rgba(248,81,73,0.3); border-radius: 20px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .header h2 {{ color: #ffffff; margin: 0 0 6px 0; font-size: 20px; font-weight: 700; }}
    .header p {{ color: #8b949e; margin: 0; font-size: 13px; }}
    .content {{ padding: 24px; }}
    .notes-box {{ background: #0d1117; border-left: 3px solid #f85149; border-radius: 0 8px 8px 0; padding: 14px; margin: 18px 0; font-size: 13px; color: #e6edf3; }}
    .footer {{ background-color: #0d1117; padding: 16px; text-align: center; font-size: 11px; color: #6e7681; border-top: 1px solid #30363d; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <span class="badge">&bull; Status Update &bull;</span>
      <h2>Pump Master Pro &mdash; Access Request Update</h2>
      <p>An update regarding your registration application</p>
    </div>
    <div class="content">
      <p style="margin-top: 0; font-size: 14px; color: #e6edf3;">Hello <strong>{first_name}</strong>,</p>
      <p style="font-size: 13px; color: #8b949e; line-height: 1.5;">
        Thank you for your interest in <strong>Pump Master Pro</strong>. After careful review, your online registration request for <strong>{display_org}</strong> could not be approved at this time.
      </p>

      {f'<div class="notes-box"><strong style="color:#f85149; display:block; margin-bottom:4px; font-size:12px; text-transform:uppercase;">Reason / Note from Reviewer:</strong> {notes}</div>' if notes else ''}

      <p style="font-size: 12px; color: #8b949e; line-height: 1.5; margin-top: 20px;">
        If you believe this decision is in error or require enterprise licensing assistance, please contact our engineering administration desk at <a href="mailto:{lytrose_reg_email}" style="color:#58a6ff; text-decoration:none;">{lytrose_reg_email}</a>.
      </p>
    </div>
    <div class="footer">
      Pump Master Pro Engineering Suite &bull; Support: <a href="mailto:{lytrose_reg_email}" style="color:#8b949e;">{lytrose_reg_email}</a>
    </div>
  </div>
</body>
</html>
"""

    return send_email(email, subject, html_content, text_content, from_email=lytrose_reg_email, reply_to=lytrose_reg_email)
