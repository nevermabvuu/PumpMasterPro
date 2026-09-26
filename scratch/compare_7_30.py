import imaplib

mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')

mail.select('INBOX')
typ, data = mail.fetch('7', '(RFC822)')
raw7 = data[0][1].decode('latin1', errors='replace')

mail.select('Junk')
typ, data = mail.fetch('30', '(RFC822)')
raw30 = data[0][1].decode('latin1', errors='replace')

print("="*40 + " RAW 7 (INBOX, CLEAN) " + "="*40)
print(raw7[:1500])
print("\n" + "="*40 + " RAW 30 (JUNK, KAM_MARKSPAM) " + "="*40)
print(raw30[:1500])

mail.logout()
