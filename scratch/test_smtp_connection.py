"""
scratch/test_smtp_connection.py
Diagnoses SMTP mail configuration and sends a test email ping.
Usage:
    python scratch/test_smtp_connection.py [recipient@example.com]
"""

import sys
import os

# Add pump-app to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass

from app import app
from services.email_service import get_smtp_config, send_email, is_smtp_configured, get_lytrose_registration_email

def main():
    with app.app_context():
        print("=" * 60)
        print("   PUMP MASTER PRO — SMTP DIAGNOSTIC UTILITY")
        print("=" * 60)

        cfg = get_smtp_config()
        print(f"SMTP Host:        {cfg['host'] or '(NOT SET in .env)'}")
        print(f"SMTP Port:        {cfg['port']}")
        print(f"SMTP User:        {cfg['user'] or '(NOT SET in .env)'}")
        print(f"SMTP Password:    {'*' * len(cfg['password']) if cfg['password'] else '(NOT SET in .env)'}")
        print(f"SMTP From:        {cfg['from'] or '(Defaults to SMTP User or Lytrose DB email)'}")
        print(f"Lytrose DB Email: {get_lytrose_registration_email()}")
        print("-" * 60)

    if not cfg['is_configured']:
        print("[STATUS]: Incomplete SMTP configuration in .env.")
        print(f"Current Host:     {cfg['host']}")
        print(f"Current Port:     {cfg['port']}")
        print(f"Current User:     {cfg['user']}")
        print(f"Password set?     {'YES' if cfg['password'] else 'NO (Missing SMTP_PASSWORD in .env)'}")
        print("")
        print("To complete configuration, open .env and set your mailbox password:")
        print("  SMTP_PASSWORD=your_mailbox_password")
        print("=" * 60)
        return

    print("[STATUS]: SMTP credentials detected! Testing live connection...")
    target = sys.argv[1] if len(sys.argv) > 1 else cfg['user']
    print(f"Sending test email to: {target}")

    success, msg = send_email(
        to_email=target,
        subject="Pump Master Pro — SMTP Verification Test",
        html_content="<h2 style='color:#3fb950;'>SMTP Test Successful</h2><p>Your Pump Master Pro outgoing mail configuration is operating properly.</p>",
        text_content="SMTP Test Successful. Your Pump Master Pro outgoing mail configuration is operating properly."
    )

    if success:
        print(f"[SUCCESS]: {msg}")
    else:
        print(f"[FAILED]: {msg}")
    print("=" * 60)

if __name__ == '__main__':
    main()
