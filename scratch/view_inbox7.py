import imaplib

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
mail.select('INBOX')
typ, data = mail.fetch('7', '(RFC822)')
raw = data[0][1].decode('latin1', errors='replace')
headers = raw.split('\r\n\r\n')[0]
print(headers)
mail.logout()
