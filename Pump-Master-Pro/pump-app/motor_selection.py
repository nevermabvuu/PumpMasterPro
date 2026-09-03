"""
motor_selection.py — Motor sizing, drive arrangement, and speed relationship evaluation.

Beginners Note:
This module encapsulates the engineering logic connecting:
1. Pump Duty Point → Required Pump Speed (determined by hydraulic calculation)
2. Motor Sizing → Sizing by required shaft power (+15% margin) and retrieving actual rated speed from database
3. Drive Arrangement → Direct coupled (transmission ratio = 1.0), with clean architecture for future belt/gearbox
4. Fixed Speed Evaluation → Compares motor rated speed against required pump speed to determine direct-coupling suitability
5. VSD Mode Evaluation → Calculates the exact inverter output frequency (Hz) required to run the pump at duty speed,
   and validates that it falls within user-specified min/max frequency limits.
"""

from motor_models import Motor, get_available_motors, get_motor_by_id


# Supported drive arrangements
DRIVE_DIRECT = 'direct'
DRIVE_BELT = 'belt'
DRIVE_GEARBOX = 'gearbox'

DRIVE_ARRANGEMENTS = [
    {'id': DRIVE_DIRECT, 'name': 'Direct Coupled', 'available': True, 'ratio': 1.0, 'efficiency': 1.0},
    {'id': DRIVE_BELT, 'name': 'Belt Driven (Future)', 'available': False, 'ratio': None, 'efficiency': 0.95},
    {'id': DRIVE_GEARBOX, 'name': 'Gearbox (Future)', 'available': False, 'ratio': None, 'efficiency': 0.97},
]


def select_automatic_motor(required_shaft_power_kw, frequency_hz=50, poles=4, margin=1.15):
    """
    Select the standard industrial motor matching frequency and pole count whose rated kW
    satisfies the required pump shaft power plus engineering safety margin (default +15%).

    Beginners Note:
    Pumps operate with variable liquid density and system transients, so a 10–15% motor power
    margin above operating shaft power is standard engineering practice.
    """
    target_kw = (required_shaft_power_kw or 1.0) * margin
    motors = get_available_motors(frequency_hz=frequency_hz, poles=poles)

    if not motors:
        return None

    # Find the smallest motor where rated_power_kw >= target_kw
    for m in motors:
        if m.rated_power_kw >= target_kw:
            return m

    # If pump exceeds all catalogue motors, return the largest available
    return motors[-1]


def evaluate_motor_and_drive(
    pump_duty_power_kw,
    pump_duty_speed_rpm,
    operation_mode='fixed',
    drive_type='direct',
    motor_freq_hz=50,
    motor_poles=4,
    motor_selection_mode='auto',
    manual_motor_id=None,
    vsd_f_min=30.0,
    vsd_f_max=50.0
):
    """
    Evaluate the motor selection and drive relationship against the calculated required pump speed.

    Parameters:
        pump_duty_power_kw: Calculated pump operating power in kW
        pump_duty_speed_rpm: Calculated required pump operating speed in RPM
        operation_mode: 'fixed' or 'vsd'
        drive_type: 'direct' (future: 'belt', 'gearbox')
        motor_freq_hz: 50 or 60 Hz
        motor_poles: 2, 4, 6, 8
        motor_selection_mode: 'auto' or 'manual'
        manual_motor_id: ID of selected Motor if mode is 'manual'
        vsd_f_min: User-specified minimum VSD frequency (Hz)
        vsd_f_max: User-specified maximum VSD frequency (Hz)

    Returns:
        Dictionary containing motor details, speed comparison, and suitability assessment.
    """
    try:
        motor_freq_hz = int(motor_freq_hz)
    except (ValueError, TypeError):
        motor_freq_hz = 50

    try:
        motor_poles = int(motor_poles)
    except (ValueError, TypeError):
        motor_poles = 4

    try:
        vsd_f_min = float(vsd_f_min) if vsd_f_min is not None else 30.0
    except (ValueError, TypeError):
        vsd_f_min = 30.0

    try:
        vsd_f_max = float(vsd_f_max) if vsd_f_max is not None else (60.0 if motor_freq_hz == 60 else 50.0)
    except (ValueError, TypeError):
        vsd_f_max = 50.0

    # 1. Resolve Selected Motor
    selected_motor = None
    if motor_selection_mode == 'manual' and manual_motor_id:
        selected_motor = get_motor_by_id(manual_motor_id)

    if selected_motor is None:
        selected_motor = select_automatic_motor(
            required_shaft_power_kw=pump_duty_power_kw,
            frequency_hz=motor_freq_hz,
            poles=motor_poles,
            margin=1.15
        )

    if selected_motor is None:
        # Fallback safety if database is empty
        return {
            'error': 'No motors available in database',
            'is_suitable': False
        }

    # 2. Drive Relationship (Direct coupling ratio = 1.0)
    # Beginners Note: For direct coupling, motor speed equals pump speed (i = 1.0).
    drive_ratio = 1.0
    if drive_type == DRIVE_DIRECT:
        motor_req_speed_rpm = pump_duty_speed_rpm * drive_ratio
    else:
        # Belt or gearbox (prepared for future extension)
        motor_req_speed_rpm = pump_duty_speed_rpm * drive_ratio

    motor_rated_rpm = selected_motor.rated_speed_rpm

    # 3. Fixed Speed Suitability Assessment
    # Beginners Note:
    # We compare the selected motor's actual rated speed against the required pump speed.
    # We DO NOT force the motor to match pump speed; we report speed match suitability.
    speed_deviation_pct = 0.0
    speed_match_status = 'suitable'
    match_message = ''
    vsd_req_freq_hz = None
    vsd_freq_status = None

    if operation_mode == 'fixed':
        if pump_duty_speed_rpm and pump_duty_speed_rpm > 0:
            speed_deviation_pct = round(
                abs(motor_rated_rpm - pump_duty_speed_rpm) / pump_duty_speed_rpm * 100.0, 1
            )
        else:
            speed_deviation_pct = 0.0

        if speed_deviation_pct <= 4.0:
            speed_match_status = 'suitable'
            match_message = (
                f"Direct-drive suitable: motor rated at {int(motor_rated_rpm)} RPM matches "
                f"required pump speed {int(pump_duty_speed_rpm)} RPM ({speed_deviation_pct:.1f}% deviation)."
            )
        elif speed_deviation_pct <= 8.0:
            speed_match_status = 'marginal'
            match_message = (
                f"Acceptable match: {speed_deviation_pct:.1f}% speed difference between motor "
                f"({int(motor_rated_rpm)} RPM) and pump duty speed ({int(pump_duty_speed_rpm)} RPM)."
            )
        else:
            speed_match_status = 'unsuitable'
            match_message = (
                f"Speed mismatch: selected motor rated at {int(motor_rated_rpm)} RPM is unsuitable for direct "
                f"coupling to pump duty speed ({int(pump_duty_speed_rpm)} RPM, {speed_deviation_pct:.1f}% difference). "
                f"A belt drive or gearbox is required for this speed difference."
            )

    # 4. Variable Speed Drive (VSD) Assessment
    # Beginners Note:
    # In VSD mode, the inverter adjusts motor frequency to achieve the exact required pump speed.
    # Required VSD frequency = f_rated * (N_pump_req / N_motor_rated)
    else:
        if motor_rated_rpm > 0:
            vsd_req_freq_hz = round(selected_motor.frequency_hz * (pump_duty_speed_rpm / motor_rated_rpm), 1)
        else:
            vsd_req_freq_hz = float(selected_motor.frequency_hz)

        if vsd_req_freq_hz < vsd_f_min:
            vsd_freq_status = 'low'
            speed_match_status = 'unsuitable'
            match_message = (
                f"VSD frequency warning: calculated {vsd_req_freq_hz:.1f} Hz is below minimum limit {vsd_f_min:.1f} Hz "
                f"(risk of motor fan self-cooling deficiency)."
            )
        elif vsd_req_freq_hz > vsd_f_max:
            vsd_freq_status = 'high'
            speed_match_status = 'unsuitable'
            match_message = (
                f"VSD frequency warning: calculated {vsd_req_freq_hz:.1f} Hz exceeds maximum limit {vsd_f_max:.1f} Hz "
                f"(risk of motor insulation or bearing over-frequency)."
            )
        else:
            vsd_freq_status = 'suitable'
            speed_match_status = 'suitable'
            match_message = (
                f"VSD frequency suitable: {vsd_req_freq_hz:.1f} Hz operates within user limits "
                f"({vsd_f_min:.1f}–{vsd_f_max:.1f} Hz)."
            )

    return {
        'motor_id': selected_motor.id,
        'model_name': selected_motor.model_name,
        'manufacturer': selected_motor.manufacturer,
        'rated_power_kw': selected_motor.rated_power_kw,
        'rated_power_hp': selected_motor.rated_power_hp,
        'frequency_hz': selected_motor.frequency_hz,
        'poles': selected_motor.poles,
        'sync_speed_rpm': selected_motor.sync_speed_rpm,
        'rated_speed_rpm': selected_motor.rated_speed_rpm,
        'efficiency_pct': selected_motor.efficiency_pct,
        'frame_size': selected_motor.frame_size,
        'voltage': selected_motor.voltage,
        'drive_type': drive_type,
        'drive_name': 'Direct Coupled',
        'pump_required_speed_rpm': round(pump_duty_speed_rpm, 1),
        'motor_required_speed_rpm': round(motor_req_speed_rpm, 1),
        'speed_deviation_pct': speed_deviation_pct,
        'speed_match_status': speed_match_status,
        'match_message': match_message,
        'vsd_required_freq_hz': vsd_req_freq_hz,
        'vsd_f_min': vsd_f_min,
        'vsd_f_max': vsd_f_max,
        'vsd_freq_status': vsd_freq_status,
        'motor_selection_mode': motor_selection_mode
    }
