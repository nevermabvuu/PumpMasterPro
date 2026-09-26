import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
mail.select('"Junk"')

typ, data = mail.search(None, 'ALL')
ids = data[0].split()
typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
raw_email = msg_data[0][1]
parsed = email.message_from_bytes(raw_email)

print("=== ALL HEADERS IN LATEST JUNK EMAIL ===")
for k, v in parsed.items():
    print(f"{k}: {v}")

mail.logout()
