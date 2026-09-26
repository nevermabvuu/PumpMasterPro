import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    res, count = mail.select(f'"{box}"')
    if res == 'OK':
        typ, data = mail.search(None, 'SUBJECT "Verification Test"')
        ids = data[0].split()
        if ids:
            typ, msg_data = mail.fetch(ids[-1], '(RFC822)')
            parsed = email.message_from_bytes(msg_data[0][1])
            print(f"FOLDER: {box}")
            print("Subject:", parsed.get('Subject'))
            print("From:", parsed.get('From'))
            print("To:", parsed.get('To'))
            print("Sender:", parsed.get('Sender'))
            print("Reply-To:", parsed.get('Reply-To'))
            print("Return-Path:", parsed.get('Return-Path'))
            print("X-Spam-Status:", parsed.get('X-Spam-Status'))
            print("X-Spam-Score:", parsed.get('X-Spam-Score'))

mail.logout()
