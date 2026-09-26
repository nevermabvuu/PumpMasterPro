import imaplib

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
mail.select('Junk')
typ, data = mail.search(None, 'ALL')
ids = data[0].split()

print("First 10 in Junk:")
for mid in ids[:10]:
    typ, msg_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE X-SPAM-STATUS)])')
    hdr = msg_data[0][1].decode('latin1', errors='replace').strip()
    print(f"[{mid.decode()}]\n{hdr}\n---")

mail.logout()
