import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from models import User

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['user_id'] = 2
        sess['_fresh'] = True
    r = c.get('/reports/settings')
    html = r.get_data(as_text=True)
    print('Has Configure button in table:', 'Configure' in html and 'editReport(' in html and 'button data-report' in html)
    print('Has Read-Only badge in table:', 'Read-Only</span>' in html)
    print('Has Create Report Setting button:', 'Create Report Setting' in html)
    print('Has Add Organisation button:', 'Add Organisation' in html)
