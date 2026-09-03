"""
scratch/test_motor_selection_integration.py — Integration tests for motor selection and drive arrangement.
"""
import os
import sys

# Add pump-app to path
sys.path.insert(0, os.path.abspath('Pump-Master-Pro/pump-app'))

from app import app, db
from motor_models import Motor, get_available_motors
from motor_selection import evaluate_motor_and_drive, select_automatic_motor
from pump_selection import select_pumps
from models import Pump

with app.app_context():
    print("=" * 60)
    print("1. VERIFYING MOTOR DATABASE")
    print("=" * 60)
    count = Motor.query.count()
    print(f"Total motors in DB: {count}")
    assert count >= 200, f"Expected >= 200 motors, found {count}"

    m_50_4p = get_available_motors(50, 4)
    print(f"50Hz 4-Pole motors: {len(m_50_4p)}")
    sample_motor = m_50_4p[5]  # ~15 kW
    print(f"Sample Motor: {sample_motor.model_name}")
    print(f"  Power: {sample_motor.rated_power_kw} kW")
    print(f"  Sync Speed: {sample_motor.sync_speed_rpm} RPM")
    print(f"  Rated Speed (with slip): {sample_motor.rated_speed_rpm} RPM")
    print(f"  Frame Size: {sample_motor.frame_size}")
    assert sample_motor.rated_speed_rpm < sample_motor.sync_speed_rpm, "Rated speed must reflect slip below synchronous speed"

    print("\n" + "=" * 60)
    print("2. VERIFYING AUTOMATIC MOTOR SIZING")
    print("=" * 60)
    # 12 kW pump shaft power -> 12 * 1.15 = 13.8 kW -> Should pick 15 kW motor
    m_sized = select_automatic_motor(12.0, frequency_hz=50, poles=4, margin=1.15)
    print(f"Required 12.0 kW (+15% = 13.8 kW) -> Sized Motor: {m_sized.rated_power_kw} kW ({m_sized.model_name})")
    assert m_sized.rated_power_kw == 15.0, f"Expected 15.0 kW, got {m_sized.rated_power_kw}"

    print("\n" + "=" * 60)
    print("3. VERIFYING FIXED SPEED DIRECT COUPLING SUITABILITY")
    print("=" * 60)
    # Case A: 4-pole motor with 1450 RPM pump duty speed -> direct drive match
    eval_match = evaluate_motor_and_drive(
        pump_duty_power_kw=10.0,
        pump_duty_speed_rpm=1450.0,
        operation_mode='fixed',
        drive_type='direct',
        motor_freq_hz=50,
        motor_poles=4,
        motor_selection_mode='auto'
    )
    print(f"Case A (4P @ 1450 RPM): Status = {eval_match['speed_match_status']}, Dev = {eval_match['speed_deviation_pct']}%, Msg = {eval_match['match_message']}")
    assert eval_match['speed_match_status'] == 'suitable', "Expected suitable direct-drive match"

    # Case B: 2-pole motor with 1450 RPM pump duty speed -> speed mismatch warning
    eval_mismatch = evaluate_motor_and_drive(
        pump_duty_power_kw=10.0,
        pump_duty_speed_rpm=1450.0,
        operation_mode='fixed',
        drive_type='direct',
        motor_freq_hz=50,
        motor_poles=2,
        motor_selection_mode='auto'
    )
    print(f"Case B (2P @ 1450 RPM): Status = {eval_mismatch['speed_match_status']}, Dev = {eval_mismatch['speed_deviation_pct']}%, Msg = {eval_mismatch['match_message']}")
    assert eval_mismatch['speed_match_status'] == 'unsuitable', "Expected unsuitable speed mismatch"
    assert "Speed mismatch" in eval_mismatch['match_message']

    print("\n" + "=" * 60)
    print("4. VERIFYING VSD FREQUENCY CALCULATION")
    print("=" * 60)
    # Motor rated 1460 RPM, required pump speed 1200 RPM -> f_req = 50 * (1200 / 1460) = 41.1 Hz
    eval_vsd = evaluate_motor_and_drive(
        pump_duty_power_kw=10.0,
        pump_duty_speed_rpm=1200.0,
        operation_mode='vsd',
        drive_type='direct',
        motor_freq_hz=50,
        motor_poles=4,
        vsd_f_min=30.0,
        vsd_f_max=50.0
    )
    print(f"VSD Normal: f_req = {eval_vsd['vsd_required_freq_hz']} Hz, Status = {eval_vsd['vsd_freq_status']}, Msg = {eval_vsd['match_message']}")
    assert 40.0 <= eval_vsd['vsd_required_freq_hz'] <= 42.0, f"Unexpected frequency: {eval_vsd['vsd_required_freq_hz']}"
    assert eval_vsd['vsd_freq_status'] == 'suitable'

    # VSD Low Limit breach: pump speed 600 RPM -> f_req = 50 * (600 / 1460) = 20.5 Hz < 30 Hz
    eval_vsd_low = evaluate_motor_and_drive(
        pump_duty_power_kw=5.0,
        pump_duty_speed_rpm=600.0,
        operation_mode='vsd',
        drive_type='direct',
        motor_freq_hz=50,
        motor_poles=4,
        vsd_f_min=30.0,
        vsd_f_max=50.0
    )
    print(f"VSD Under-freq: f_req = {eval_vsd_low['vsd_required_freq_hz']} Hz, Status = {eval_vsd_low['vsd_freq_status']}, Msg = {eval_vsd_low['match_message']}")
    assert eval_vsd_low['vsd_freq_status'] == 'low'

    print("\n" + "=" * 60)
    print("5. VERIFYING SELECT_PUMPS ATTACHES MOTOR OBJECT")
    print("=" * 60)
    pumps = Pump.query.all()
    results = select_pumps(
        pumps,
        q_duty=100.0,
        h_duty=25.0,
        operation_mode='fixed',
        motor_freq_hz=50,
        motor_poles=4,
        motor_selection_mode='auto'
    )
    print(f"Selected pumps count: {len(results)}")
    assert len(results) > 0, "Expected at least one matching pump"
    top_pump = results[0]
    assert 'motor' in top_pump, "Top pump result must contain 'motor' dict"
    m_info = top_pump['motor']
    print(f"Top Pump: {top_pump['pump_name']}")
    print(f"  Motor: {m_info['model_name']}, Rated: {m_info['rated_speed_rpm']} RPM")
    print(f"  Drive: {m_info['drive_name']}")
    print(f"  Speed Status: {m_info['speed_match_status']}")

    print("\n" + "=" * 60)
    print("6. VERIFYING FLASK CLIENT ENDPOINTS")
    print("=" * 60)
    client = app.test_client()
    resp = client.get('/papi/motors-by-spec?freq=50&poles=4')
    assert resp.status_code == 200
    data = resp.get_json()
    print(f"/papi/motors-by-spec returned {len(data)} motors for 50Hz 4P")
    assert len(data) == 28

    resp_html = client.get('/pump-selection')
    assert resp_html.status_code == 200
    html_text = resp_html.get_data(as_text=True)
    assert 'Motor &amp; Drive Arrangement' in html_text or 'Motor & Drive Arrangement' in html_text
    assert 'Drive Arrangement' in html_text
    assert 'Direct Coupled' in html_text
    assert 'Motor Supply Frequency' in html_text
    assert '50 Hz' in html_text
    assert '60 Hz' in html_text
    assert 'Number of Poles' in html_text
    print("HTML page contains Motor & Drive Arrangement controls!")

    print("\nALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
