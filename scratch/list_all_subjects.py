import imaplib
import email

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

for box in ['INBOX', 'Junk']:
    mail.select(f'"{box}"')
    typ, data = mail.search(None, 'ALL')
    ids = data[0].split()
    print(f"=== {box} ===")
    for mid in ids:
        typ, msg_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT X-SPAM-STATUS X-SPAM-SCORE DATE)])')
        header_text = msg_data[0][1].decode('latin1', errors='replace').strip()
        print(f"[{mid.decode()}] {header_text}\n---")

mail.logout()
