import imaplib
import email

try:
    mail = imaplib.IMAP4_SSL('workplace.truehost.cloud', 993, timeout=15)
    mail.login('admin@pumpmasterpro.com', 'NaleshTapiwa@21')
    print("IMAP Login successful.")
    
    status, folders = mail.list()
    for f in folders:
        print("Folder:", f.decode('utf-8', errors='ignore'))
        
    for box in ['INBOX', 'Junk', 'Spam', 'Trash']:
        try:
            res, count = mail.select(f'"{box}"')
            if res == 'OK':
                print(f"\nChecking folder: {box} (Total messages: {count[0].decode()})")
                typ, data = mail.search(None, 'ALL')
                ids = data[0].split()
                if ids:
                    latest_id = ids[-1]
                    typ, msg_data = mail.fetch(latest_id, '(RFC822)')
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    print(f"--- Latest Email in {box} ---")
                    print("Date:", msg.get('Date'))
                    print("From:", msg.get('From'))
                    print("To:", msg.get('To'))
                    print("Subject:", msg.get('Subject'))
                    print("X-Spam-Status:", msg.get('X-Spam-Status'))
                    print("X-Spam-Report:", msg.get('X-Spam-Report'))
                    print("X-Spam-Score:", msg.get('X-Spam-Score'))
                    print("X-Spam-Bar:", msg.get('X-Spam-Bar'))
                    print("Authentication-Results:", msg.get('Authentication-Results'))
                    print("Received-SPF:", msg.get('Received-SPF'))
                    print("DKIM-Signature:", "Present" if msg.get('DKIM-Signature') else "None")
        except Exception as box_err:
            print(f"Could not inspect {box}: {box_err}")

    mail.logout()
except Exception as e:
    print("IMAP Error:", e)
