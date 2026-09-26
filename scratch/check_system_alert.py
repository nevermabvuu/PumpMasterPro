import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    res, count = mail.select(f'"{box}"')
    typ, data = mail.search(None, 'SUBJECT "System Alert Verification"')
    ids = data[0].split()
    for mid in ids:
        typ, msg_data = mail.fetch(mid, '(RFC822)')
        parsed = email.message_from_bytes(msg_data[0][1])
        print(f"FOLDER: {box}")
        print("  From:", parsed.get('From'))
        print("  Subject:", parsed.get('Subject'))
        print("  Score:", parsed.get('X-Spam-Score'))
        print("  Status:", parsed.get('X-Spam-Status'))

mail.logout()
