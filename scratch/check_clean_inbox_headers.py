import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
mail.select('"INBOX"')

typ, data = mail.search(None, 'ALL')
ids = data[0].split()
for mid in ids:
    typ, msg_data = mail.fetch(mid, '(RFC822)')
    parsed = email.message_from_bytes(msg_data[0][1])
    print("=" * 60)
    print("SUBJECT:", parsed.get('Subject'))
    print("DATE:", parsed.get('Date'))
    print("HEADERS:")
    for k, v in parsed.items():
        print(f"  {k}: {v}")

mail.logout()
