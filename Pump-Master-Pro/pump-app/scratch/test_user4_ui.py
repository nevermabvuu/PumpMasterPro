import os, sys
sys.path.insert(0, os.path.abspath('.'))
from app import app
from models import User

with app.app_context():
    u = User.query.get(4)
    print('=== LOGGED IN AS never@tasonline.co.za (User 4) ===')
    print('Email:', u.email, 'Role:', u.role_display_name, 'is_super_admin:', u.is_super_admin_user)
    for m in ['pump_data', 'pump_catalogue', 'report_settings', 'organisation_settings', 'users_settings', 'roles']:
        print(f'  {m}: level={u.get_access_level(m)}, can_edit={u.can_edit(m)}')

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['user_id'] = 4
        sess['_fresh'] = True

    print('\n--- 1. Testing /pump-data ---')
    r = c.get('/pump-data')
    html = r.get_data(as_text=True)
    print('Status:', r.status_code)
    print('Add Pump in HTML?', 'Add Pump' in html)
    print('Edit Pump in HTML?', 'Edit' in html and 'bi-pencil' in html)
    print('Delete Pump in HTML?', 'Delete' in html and 'bi-trash' in html)

    print('\n--- 2. Testing /pump-data/edit/1 ---')
    r = c.get('/pump-data/edit/1')
    print('Status:', r.status_code, 'Location:', r.headers.get('Location'))

    print('\n--- 3. Testing /reports/settings ---')
    r = c.get('/reports/settings')
    html = r.get_data(as_text=True)
    print('Status:', r.status_code)
    print('Create Report Setting in HTML?', 'Create Report Setting' in html)
    print('Add Organisation in HTML?', 'Add Organisation' in html)
    print('Configure in HTML?', 'bi-gear' in html and 'Configure' in html)
    print('Save Graph Area in HTML?', 'Save Graph Area' in html)
    print('Save Supplier in HTML?', 'Save Supplier' in html)
    print('Save Configuration in HTML?', 'Save Configuration' in html)

    print('\n--- 4. Testing /organisations/settings ---')
    r = c.get('/organisations/settings')
    html = r.get_data(as_text=True)
    print('Status:', r.status_code)
    print('Save Organisation Profile in HTML?', 'Save Organisation Profile' in html)
    print('Save Visibility Filters in HTML?', 'Save Visibility Filters' in html)
    print('Save Custom Attributes in HTML?', 'Save Custom Attributes' in html)
    print('Save Graph Display Settings in HTML?', 'Save Graph Display Settings' in html)
    print('Save Catalogue Reports in HTML?', 'Save Catalogue Reports' in html)
