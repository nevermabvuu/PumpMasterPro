import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    mail.select(f'"{box}"')
    typ, data = mail.search(None, 'ALL')
    ids = data[0].split()
    print(f'=== Folder: {box} (Total: {len(ids)}) ===')
    for mid in ids[-6:]:
        typ, msg_data = mail.fetch(mid, '(RFC822)')
        parsed = email.message_from_bytes(msg_data[0][1])
        print(f"ID: {mid.decode()} | Date: {parsed.get('Date')} | Subject: {parsed.get('Subject')}")
        print(f"   X-Spam-Status: {parsed.get('X-Spam-Status')}")
        print(f"   X-Spam-Score: {parsed.get('X-Spam-Score')}")
mail.logout()
