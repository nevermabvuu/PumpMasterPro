import sys, os
sys.path.insert(0, os.path.abspath('c:/Users/DELL/Documents/admin/Lytrose/repos/Pump-Master-Pro/Pump-Master-Pro/pump-app'))

from app import app

client = app.test_client()

# 1. Post selection with manual speed = 1450 RPM
form_data = {
    'q_duty': '50',
    'h_duty': '15',
    'operation_mode': 'fixed',
    'fixed_speed_mode': 'manual',
    'manual_pump_speed_rpm': '1450',
    'motor_freq_hz': '50',
    'motor_poles': '4',
    'motor_selection_mode': 'auto',
    'drive_type': 'direct'
}

resp = client.post('/pump-selection', data=form_data, follow_redirects=True)
assert resp.status_code == 200
html = resp.data.decode('utf-8')

print("Selection page returned 200 OK.")
assert 'ISF100x65-200 2P' in html, "ISF pump should be selected at 1450 RPM!"
print("ISF pump found in results.")

# Verify Fixed Speed manual display on card
assert 'Fixed Speed: 1450 RPM (Manual)' in html, "Card should state Fixed Speed: 1450 RPM (Manual)"
print("Fixed Speed 1450 RPM (Manual) badge verified on card.")

# 2. View details page for ISF pump (ID 9)
details_resp = client.get('/pump-selection/details/9')
assert details_resp.status_code == 200
details_html = details_resp.data.decode('utf-8')

print("Details page returned 200 OK.")
assert '1450 rpm' in details_html, "Details page should display 1450 rpm for operating speed"
assert 'Operating Duty Speed' in details_html, "Details table should show Operating Duty Speed"
assert 'Catalogue Base Speed' in details_html, "Details table should show Catalogue Base Speed"
print("Details page verified with Operating Duty Speed and Catalogue Base Speed.")

print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY!")
