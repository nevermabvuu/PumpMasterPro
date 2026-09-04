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


def select_automatic_motor(
    target_kw,
    frequency_hz=50,
    poles=4,
    standard=None,
    efficiency_class=None,
    manufacturer=None
):
    """
    Select the standard industrial motor meeting or exceeding target_kw,
    filtered by frequency, pole count, standard (IEC/NEMA), efficiency class (IE2/IE3/IE4/NEMA Premium),
    and manufacturer/supplier.

    Beginners Note:
    Pumps operate with variable liquid density and system transients, so a motor power
    margin above operating shaft power is standard engineering practice.
    """
    motors = get_available_motors(
        frequency_hz=frequency_hz,
        poles=poles,
        standard=standard,
        efficiency_class=efficiency_class,
        manufacturer=manufacturer
    )

    if not motors:
        # Fallback to general search without strict manufacturer/efficiency constraints
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
    manual_motor_speed_rpm=None,
    manual_speed_tolerance_pct=5.0,
    motor_margin_pct=15.0,
    motor_margin_basis='duty',
    base_power_kw=None,
    motor_standard=None,
    motor_efficiency=None,
    motor_supplier=None,
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
        manual_motor_speed_rpm: Entered motor speed in RPM (Manual mode)
        manual_speed_tolerance_pct: Allowable speed deviation in % (Manual mode, default 5.0)
        motor_margin_pct: Sizing safety margin in % (default 15.0)
        motor_margin_basis: 'duty', 'bep', 'shutoff', 'eoc'
        base_power_kw: Base power in kW for chosen basis
        motor_standard: 'IEC', 'NEMA', or 'all'
        motor_efficiency: 'IE2', 'IE3', 'IE4', 'NEMA Premium', or 'all'
        motor_supplier: Manufacturer name or 'all'
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
        motor_margin_pct = float(motor_margin_pct) if motor_margin_pct is not None else 15.0
    except (ValueError, TypeError):
        motor_margin_pct = 15.0

    try:
        manual_speed_tolerance_pct = float(manual_speed_tolerance_pct) if manual_speed_tolerance_pct is not None else 5.0
    except (ValueError, TypeError):
        manual_speed_tolerance_pct = 5.0

    try:
        vsd_f_min = float(vsd_f_min) if vsd_f_min is not None else 30.0
    except (ValueError, TypeError):
        vsd_f_min = 30.0

    try:
        vsd_f_max = float(vsd_f_max) if vsd_f_max is not None else (60.0 if motor_freq_hz == 60 else 50.0)
    except (ValueError, TypeError):
        vsd_f_max = 50.0

    # 1. Determine Power Sizing Basis and Target Power (kW)
    if base_power_kw is None or base_power_kw <= 0:
        base_power_kw = pump_duty_power_kw if (pump_duty_power_kw and pump_duty_power_kw > 0) else 1.0
    base_power_kw = round(float(base_power_kw), 2)

    margin_factor = 1.0 + (motor_margin_pct / 100.0)
    target_power_kw = round(base_power_kw * margin_factor, 2)

    basis_labels = {
        'duty': 'Duty Power',
        'bep': 'BEP Power',
        'shutoff': 'Shutoff Power',
        'eoc': 'End of Curve Power'
    }
    basis_label = basis_labels.get(motor_margin_basis, 'Duty Power')

    # 2. Select Motor from Catalogue (Always sized to ensure power coverage)
    selected_motor = None
    if manual_motor_id and motor_selection_mode != 'manual':
        selected_motor = get_motor_by_id(manual_motor_id)

    if selected_motor is None:
        selected_motor = select_automatic_motor(
            target_kw=target_power_kw,
            frequency_hz=motor_freq_hz,
            poles=motor_poles,
            standard=motor_standard,
            efficiency_class=motor_efficiency,
            manufacturer=motor_supplier
        )

    if selected_motor is None:
        return {
            'error': 'No motors available in database matching criteria',
            'is_suitable': False
        }

    # 3. Determine Operating Rated Motor Speed
    # Beginners Note:
    # In manual mode, the user enters the required motor rated speed (e.g. 1450 RPM).
    # In auto mode, the actual rated speed comes from the motor database record (e.g. 1470 RPM).
    is_manual = (motor_selection_mode == 'manual')
    if is_manual and manual_motor_speed_rpm:
        try:
            motor_rated_rpm = float(manual_motor_speed_rpm)
        except (ValueError, TypeError):
            motor_rated_rpm = selected_motor.rated_speed_rpm
    else:
        motor_rated_rpm = selected_motor.rated_speed_rpm

    # 4. Drive Relationship (Direct coupling ratio = 1.0)
    drive_ratio = 1.0
    motor_req_speed_rpm = pump_duty_speed_rpm * drive_ratio

    # 5. Speed Suitability Assessment
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

        if is_manual:
            # Manual Mode: Evaluate against user-specified tolerance
            if speed_deviation_pct <= manual_speed_tolerance_pct:
                speed_match_status = 'suitable'
                match_message = (
                    f"Direct-drive suitable: entered motor speed {int(motor_rated_rpm)} RPM matches "
                    f"pump duty speed {int(pump_duty_speed_rpm)} RPM within ±{manual_speed_tolerance_pct:.1f}% "
                    f"tolerance ({speed_deviation_pct:.1f}% deviation)."
                )
            else:
                speed_match_status = 'unsuitable'
                match_message = (
                    f"Speed mismatch: entered motor speed {int(motor_rated_rpm)} RPM deviates from "
                    f"pump duty speed {int(pump_duty_speed_rpm)} RPM by {speed_deviation_pct:.1f}%, "
                    f"exceeding specified ±{manual_speed_tolerance_pct:.1f}% tolerance."
                )
        else:
            # Automatic Mode: Standard engineering direct-drive thresholds
            if speed_deviation_pct <= 4.0:
                speed_match_status = 'suitable'
                match_message = (
                    f"Direct-drive suitable: catalogue motor rated at {int(motor_rated_rpm)} RPM matches "
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

    # 6. Variable Speed Drive (VSD) Assessment
    else:
        base_rated_rpm = motor_rated_rpm if motor_rated_rpm > 0 else selected_motor.rated_speed_rpm
        if base_rated_rpm > 0:
            vsd_req_freq_hz = round(motor_freq_hz * (pump_duty_speed_rpm / base_rated_rpm), 1)
        else:
            vsd_req_freq_hz = float(motor_freq_hz)

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
        'standard': getattr(selected_motor, 'standard', 'IEC') or 'IEC',
        'efficiency_class': getattr(selected_motor, 'efficiency_class', 'IE3') or 'IE3',
        'rated_power_kw': selected_motor.rated_power_kw,
        'rated_power_hp': selected_motor.rated_power_hp,
        'frequency_hz': motor_freq_hz,
        'poles': motor_poles,
        'sync_speed_rpm': selected_motor.sync_speed_rpm,
        'rated_speed_rpm': motor_rated_rpm,
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
        'motor_selection_mode': motor_selection_mode,
        'is_manual': is_manual,
        'manual_motor_speed_rpm': manual_motor_speed_rpm,
        'manual_speed_tolerance_pct': manual_speed_tolerance_pct,
        'motor_margin_pct': motor_margin_pct,
        'motor_margin_basis': motor_margin_basis,
        'basis_label': basis_label,
        'base_power_kw': base_power_kw,
        'target_power_kw': target_power_kw
    }
