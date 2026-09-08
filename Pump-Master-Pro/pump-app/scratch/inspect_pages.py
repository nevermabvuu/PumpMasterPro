import os, sys, re
sys.path.insert(0, os.path.abspath('.'))
from app import app

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['user_id'] = 4
        sess['_fresh'] = True

    for endpoint, url in [('pump-data', '/pump-data'), ('reports-settings', '/reports/settings'), ('org-settings', '/organisations/settings')]:
        print(f"\n==================== {endpoint} ({url}) ====================")
        r = c.get(url)
        html = r.get_data(as_text=True)
        # Find all inputs
        inputs = re.findall(r'<input[^>]+>', html)
        forms = re.findall(r'<form[^>]+action=["\']([^"\']+)["\'][^>]*>', html)
        buttons = re.findall(r'<button[^>]*>(.*?)</button>', html, re.DOTALL)
        
        print(f"Status: {r.status_code}")
        print(f"Forms ({len(forms)}):")
        for f in forms:
            print(f"  Form action: {f}")
        print(f"Active Submit Buttons:")
        submits = re.findall(r'<button[^>]+type=["\']submit["\'][^>]*>(.*?)</button>', html, re.DOTALL)
        for s in submits:
            clean = re.sub(r'<[^>]+>', '', s).strip()
            print(f"  Submit: {clean}")
        
        # Check for any disabled fieldset
        fieldsets = re.findall(r'<fieldset([^>]*)>', html)
        print(f"Fieldsets ({len(fieldsets)}):")
        for fs in fieldsets:
            print(f"  fieldset attrs: {fs.strip()[:80]}")
