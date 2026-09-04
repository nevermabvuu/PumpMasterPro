"""
scratch/test_motor_details_and_fixed_speed.py
Comprehensive test suite verifying:
1. Fixed Speed Mode: Automatic Speed calculation vs Manual Speed entry
2. Motor details evaluation and presence in active_result
3. Rendering of selected motor details in default_pump_details.html and lytrose_pump_details.html
4. End-to-end Flask test client execution for /pump-selection and /pump-selection/details/<id>
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'pump-app'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from app import app
from models import Pump, Organisation
from pump_selection import select_pumps


def test_fixed_speed_modes():
    print("\n--- TEST 1: Fixed Speed Modes (Auto vs Manual) ---")
    with app.app_context():
        pumps = Pump.query.all()
        assert len(pumps) > 0, "No pumps found in database!"

        # Duty point: Q = 100 m3/h, H = 25 m
        q_duty = 100.0
        h_duty = 25.0

        # Mode A: Fixed Speed Auto (Automatic pump speed calculation at full diameter)
        results_auto = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='fixed',
            fixed_speed_mode='auto',
            motor_freq_hz=50,
            motor_poles=4
        )
        assert len(results_auto) > 0, "No results for fixed speed auto!"
        top_auto = results_auto[0]
        print(f"Auto Mode: Top pump = {top_auto['pump_name']}")
        print(f"  Calculated Duty Speed = {top_auto['optimal_speed_rpm']} RPM")
        print(f"  Impeller Dia = {top_auto['optimal_trim_dia_mm']} mm (Full = {top_auto['d_max']} mm)")
        assert top_auto['fixed_speed_mode'] == 'auto'
        assert top_auto['motor'] is not None
        assert 'model_name' in top_auto['motor']

        # Mode B: Fixed Speed Manual (User enters 1450 RPM)
        results_manual = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='fixed',
            fixed_speed_mode='manual',
            manual_pump_speed_rpm=1450.0,
            motor_freq_hz=50,
            motor_poles=4
        )
        assert len(results_manual) > 0, "No results for fixed speed manual 1450 RPM!"
        top_manual = results_manual[0]
        print(f"Manual Mode (1450 RPM): Top pump = {top_manual['pump_name']}")
        print(f"  Prescribed Speed = {top_manual['optimal_speed_rpm']} RPM")
        print(f"  Trimmed Impeller Dia = {top_manual['optimal_trim_dia_mm']} mm")
        assert top_manual['optimal_speed_rpm'] == 1450.0
        assert top_manual['fixed_speed_mode'] == 'manual'
        assert top_manual['manual_pump_speed_rpm'] == 1450.0
        assert top_manual['motor'] is not None
        print(f"  Selected Motor: {top_manual['motor']['model_name']} ({top_manual['motor']['rated_power_kw']} kW, {top_manual['motor']['rated_speed_rpm']} RPM)")
        print(f"  Direct Drive Status: {top_manual['motor']['speed_match_status']} ({top_manual['motor']['speed_deviation_pct']}% dev)")

        print(">>> Test 1 Passed!")


def test_details_templates_rendering():
    print("\n--- TEST 2: Pump Details Templates Rendering ---")
    with app.test_request_context('/pump-selection'):
        pumps = Pump.query.all()
        q_duty = 120.0
        h_duty = 30.0
        results = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='fixed',
            fixed_speed_mode='manual',
            manual_pump_speed_rpm=1480.0,
            motor_freq_hz=50,
            motor_poles=4,
            motor_margin_pct=20.0,
            motor_margin_basis='bep'
        )
        assert len(results) > 0
        active_result = results[0]
        pump = Pump.query.get(active_result['pump_id'])

        from flask import render_template
        # Render default_pump_details.html
        html_default = render_template(
            'details/default_pump_details.html',
            pump=pump,
            active_result=active_result,
            form_data={'q_duty': '120', 'h_duty': '30', 'operation_mode': 'fixed', 'fixed_speed_mode': 'manual'},
            current_org=Organisation.query.first(),
            unit_q='m3h', unit_h='m', unit_pow='kw', unit_npsh='m'
        )

        assert "Selected Electric Motor &amp; Drive Specification" in html_default or "Selected Electric Motor & Drive Specification" in html_default
        assert active_result['motor']['model_name'] in html_default
        assert f"{active_result['motor']['rated_power_kw']} kW" in html_default
        assert active_result['motor']['efficiency_class'] in html_default
        print("  default_pump_details.html successfully rendered motor section with model, power, and efficiency!")

        # Render lytrose_pump_details.html
        html_lytrose = render_template(
            'details/lytrose_pump_details.html',
            pump=pump,
            active_result=active_result,
            form_data={'q_duty': '120', 'h_duty': '30', 'operation_mode': 'fixed', 'fixed_speed_mode': 'manual'},
            current_org=Organisation.query.first(),
            unit_q='m3h', unit_h='m', unit_pow='kw', unit_npsh='m'
        )
        assert "Selected Electric Motor &amp; Drive Specification" in html_lytrose or "Selected Electric Motor & Drive Specification" in html_lytrose
        assert active_result['motor']['model_name'] in html_lytrose
        assert f"{active_result['motor']['rated_power_kw']} kW" in html_lytrose
        print("  lytrose_pump_details.html successfully rendered motor section!")

        print(">>> Test 2 Passed!")


def test_full_http_flow():
    print("\n--- TEST 3: Full HTTP Flow (Selection -> Details View) ---")
    client = app.test_client()

    # Submit Selection with Fixed Speed Manual
    res = client.post('/pump-selection', data={
        'q_duty': '150',
        'h_duty': '28',
        'operation_mode': 'fixed',
        'fixed_speed_mode': 'manual',
        'manual_pump_speed_rpm': '1450',
        'motor_freq_hz': '50',
        'motor_poles': '4',
        'motor_selection_mode': 'auto',
        'motor_margin_pct': '15',
        'motor_margin_basis': 'duty',
        'motor_standard': 'IEC',
        'motor_efficiency': 'IE3'
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Fixed Speed: 1450 RPM" in html or "1450" in html
    assert "name=\"manual_pump_speed_rpm\"" in html
    assert "id=\"fixedSpeedManual\"" in html
    print("  /pump-selection returned 200 with Fixed Speed Manual controls and matching results!")

    # Find a pump ID from the results
    with client.session_transaction() as sess:
        form_data = sess.get('selection_form_data', {})
        assert form_data.get('fixed_speed_mode') == 'manual'
        assert form_data.get('manual_pump_speed_rpm') == '1450'

    with app.app_context():
        pumps = Pump.query.all()
        results = select_pumps(
            pumps, 150.0, 28.0,
            operation_mode='fixed',
            fixed_speed_mode='manual',
            manual_pump_speed_rpm=1450.0
        )
        assert len(results) > 0
        target_id = results[0]['pump_id']

    # Now request the Details view for that pump
    res_details = client.get(f'/pump-selection/details/{target_id}')
    assert res_details.status_code == 200
    html_details = res_details.get_data(as_text=True)
    assert "Selected Electric Motor &amp; Drive Specification" in html_details or "Selected Electric Motor & Drive Specification" in html_details
    assert "Rated Motor Power" in html_details
    assert "Motor Rated Speed" in html_details
    assert "Direct-Drive Suitable" in html_details or "Speed Mismatch" in html_details or "Acceptable Match" in html_details
    print("  /pump-selection/details/<id> returned 200 with full motor details card and badges!")

    print(">>> Test 3 Passed!")


if __name__ == '__main__':
    test_fixed_speed_modes()
    test_details_templates_rendering()
    test_full_http_flow()
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
