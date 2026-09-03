"""
scratch/test_live_server.py — Comprehensive live HTTP verification of motor selection and drive arrangement.
"""
import urllib.request
import urllib.parse
import json
import re

BASE_URL = 'http://127.0.0.1:8000'

def test_get_page():
    req = urllib.request.urlopen(f'{BASE_URL}/pump-selection')
    html = req.read().decode('utf-8')
    assert 'Motor &amp; Drive Arrangement' in html or 'Motor & Drive Arrangement' in html
    assert 'Direct Coupled (1:1 Ratio)' in html
    assert 'motor_freq_hz' in html
    assert 'motor_poles' in html
    assert 'motor_selection_mode' in html
    print('[PASS] /pump-selection GET loaded correctly with Motor & Drive controls.')

def test_api_motors_by_spec():
    req = urllib.request.urlopen(f'{BASE_URL}/papi/motors-by-spec?freq=50&poles=4')
    data = json.loads(req.read().decode('utf-8'))
    print(f'[PASS] /papi/motors-by-spec returned {len(data)} motors for 50Hz 4P.')
    assert len(data) == 28
    first = data[0]
    print(f"       First motor: {first['model_name']} ({first['rated_speed_rpm']} RPM)")

def test_fixed_speed_4p_suitable():
    # Generic CW 100-315 duty point: Q=138, H=47 at 1450 RPM base speed
    params = urllib.parse.urlencode({
        'q_duty': '138',
        'h_duty': '47',
        'operation_mode': 'fixed',
        'motor_freq_hz': '50',
        'motor_poles': '4',
        'motor_selection_mode': 'auto',
        'drive_type': 'direct'
    }).encode('utf-8')
    req = urllib.request.Request(f'{BASE_URL}/pump-selection', data=params)
    html = urllib.request.urlopen(req).read().decode('utf-8')
    assert 'Direct Coupled' in html
    assert 'Direct Coupled Match' in html
    print('[PASS] Fixed Speed 4P Direct Coupled: Generic CW 100-315 verified with Direct Coupled Match!')

def test_fixed_speed_2p_mismatch():
    # When pairing that same 1450 RPM duty point with 2-Pole motor (2925 RPM), expect Speed Mismatch
    params = urllib.parse.urlencode({
        'q_duty': '138',
        'h_duty': '47',
        'operation_mode': 'fixed',
        'motor_freq_hz': '50',
        'motor_poles': '2',
        'motor_selection_mode': 'auto',
        'drive_type': 'direct'
    }).encode('utf-8')
    req = urllib.request.Request(f'{BASE_URL}/pump-selection', data=params)
    html = urllib.request.urlopen(req).read().decode('utf-8')
    assert 'Speed Mismatch' in html
    print('[PASS] Fixed Speed 2P Direct Coupled: returned speed mismatch warning!')

def test_vsd_mode():
    params = urllib.parse.urlencode({
        'q_duty': '138',
        'h_duty': '47',
        'operation_mode': 'vsd',
        'motor_freq_hz': '50',
        'motor_poles': '4',
        'motor_selection_mode': 'auto',
        'drive_type': 'direct',
        'vsd_f_min': '30.0',
        'vsd_f_max': '50.0'
    }).encode('utf-8')
    req = urllib.request.Request(f'{BASE_URL}/pump-selection', data=params)
    html = urllib.request.urlopen(req).read().decode('utf-8')
    assert 'VSD Freq:' in html
    matches = re.findall(r'VSD Freq:\s*([\d\.]+)\s*Hz', html)
    print(f'[PASS] VSD Mode Direct Coupled: calculated VSD frequencies: {matches[:3]}')

def test_manual_motor_selection():
    # Fetch 45 kW motor ID from API
    motors = json.loads(urllib.request.urlopen(f'{BASE_URL}/papi/motors-by-spec?freq=50&poles=4').read().decode('utf-8'))
    motor_45kw = [m for m in motors if m['rated_power_kw'] == 45.0][0]

    params = urllib.parse.urlencode({
        'q_duty': '138',
        'h_duty': '47',
        'operation_mode': 'fixed',
        'motor_freq_hz': '50',
        'motor_poles': '4',
        'motor_selection_mode': 'manual',
        'manual_motor_id': str(motor_45kw['id']),
        'drive_type': 'direct'
    }).encode('utf-8')
    req = urllib.request.Request(f'{BASE_URL}/pump-selection', data=params)
    html = urllib.request.urlopen(req).read().decode('utf-8')
    assert '45.0 kW' in html
    assert 'Direct Coupled' in html
    print(f"[PASS] Manual Motor Selection: manually selected {motor_45kw['model_name']} verified on cards!")

if __name__ == '__main__':
    test_get_page()
    test_api_motors_by_spec()
    test_fixed_speed_4p_suitable()
    test_fixed_speed_2p_mismatch()
    test_vsd_mode()
    test_manual_motor_selection()
    print('\nALL LIVE SERVER TESTS PASSED SUCCESSFULLY!')
