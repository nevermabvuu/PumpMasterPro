import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
mail.select('"INBOX"')

typ, data = mail.search(None, 'SUBJECT "Test To admin@pumpmasterpro.com"')
ids = data[0].split()
typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
parsed = email.message_from_bytes(msg_data[0][1])

print("BODY OF CLEAN EMAIL:")
for p in parsed.walk():
    if p.get_content_type() in ['text/plain', 'text/html']:
        print("--- PART:", p.get_content_type(), "---")
        print(p.get_payload())

mail.logout()
