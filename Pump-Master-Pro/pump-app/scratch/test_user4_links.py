import os, sys, re
sys.path.insert(0, os.path.abspath('.'))
from app import app

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['user_id'] = 4
        sess['_fresh'] = True
    r = c.get('/')
    html = r.get_data(as_text=True)
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
    print("All links on / for User 4 (need mugidwa):")
    for href, text in links:
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if clean_text:
            print(f"  {href:30} -> {clean_text}")
