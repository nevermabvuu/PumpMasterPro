"""
motor_models.py — Motor database models and standard motor catalogue seeding.

Beginners Note:
In industrial pumping, pump speed and motor speed are distinct:
- The pump hydraulic calculation determines the required pump duty speed.
- The motor speed is determined by the motor frequency (50/60 Hz), pole count (2, 4, 6, 8),
  and actual motor design (accounting for full-load slip, e.g. 1465 RPM for a 4-pole 50Hz motor).
- The drive arrangement (Direct coupled, Belt driven, Gearbox) relates the motor speed
  to the pump speed.
This module stores and provides standard industrial electric motors from the database.
"""

from models import db


class Motor(db.Model):
    __tablename__ = 'motors'

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(120), nullable=False)
    manufacturer = db.Column(db.String(100), default='Standard IEC')
    rated_power_kw = db.Column(db.Float, nullable=False)
    rated_power_hp = db.Column(db.Float, nullable=False)
    frequency_hz = db.Column(db.Integer, nullable=False, default=50)  # 50 or 60 Hz
    poles = db.Column(db.Integer, nullable=False, default=4)         # 2, 4, 6, 8
    sync_speed_rpm = db.Column(db.Float, nullable=False)             # Theoretical synchronous speed
    rated_speed_rpm = db.Column(db.Float, nullable=False)            # Actual full-load operating speed
    efficiency_pct = db.Column(db.Float, default=93.0)               # Full-load efficiency % (IE3/IE4)
    power_factor = db.Column(db.Float, default=0.85)
    frame_size = db.Column(db.String(50), default='')                # e.g. '160M', '180L'
    voltage = db.Column(db.String(50), default='400V')               # e.g. '400V', '460V', '525V'

    def to_dict(self):
        return {
            'id': self.id,
            'model_name': self.model_name,
            'manufacturer': self.manufacturer,
            'rated_power_kw': self.rated_power_kw,
            'rated_power_hp': self.rated_power_hp,
            'frequency_hz': self.frequency_hz,
            'poles': self.poles,
            'sync_speed_rpm': self.sync_speed_rpm,
            'rated_speed_rpm': self.rated_speed_rpm,
            'efficiency_pct': self.efficiency_pct,
            'power_factor': self.power_factor,
            'frame_size': self.frame_size,
            'voltage': self.voltage
        }


# Standard IEC power ratings (kW)
STANDARD_KW_RATINGS = [
    0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11.0, 15.0, 18.5, 22.0, 30.0,
    37.0, 45.0, 55.0, 75.0, 90.0, 110.0, 132.0, 160.0, 200.0, 250.0, 315.0,
    355.0, 400.0, 450.0, 500.0
]


def _calc_slip_rpm(sync_rpm, kw, pole_count):
    """
    Beginners Note:
    Induction motors do not run at synchronous speed; they require 'slip' to produce torque.
    Smaller motors have ~3-5% slip, while large multi-hundred kW motors have ~0.8-1.5% slip.
    This helper generates realistic rated full-load speeds matching standard manufacturer catalogues (WEG, ABB, Siemens).
    """
    if kw < 2.2:
        slip_pct = 0.045
    elif kw < 11.0:
        slip_pct = 0.035
    elif kw < 45.0:
        slip_pct = 0.024
    elif kw < 160.0:
        slip_pct = 0.015
    else:
        slip_pct = 0.010

    # Slightly higher slip for higher pole counts (6P, 8P)
    if pole_count == 6:
        slip_pct *= 1.15
    elif pole_count == 8:
        slip_pct *= 1.25

    rated = round(sync_rpm * (1.0 - slip_pct))
    # Round to nearest 5 RPM for clean catalogue numbers
    return float(int(rated / 5) * 5)


def _get_frame_size(kw, poles):
    """Typical IEC frame size mapping."""
    if kw <= 0.75: return '80M'
    if kw <= 1.5: return '90S' if poles == 2 else '90L'
    if kw <= 2.2: return '90L' if poles == 2 else '100L'
    if kw <= 4.0: return '112M'
    if kw <= 7.5: return '132S' if kw == 5.5 else '132M'
    if kw <= 15.0: return '160M'
    if kw <= 22.0: return '160L' if kw == 18.5 else '180M'
    if kw <= 37.0: return '200L'
    if kw <= 55.0: return '225S' if kw == 45.0 else '225M'
    if kw <= 90.0: return '250M' if kw == 75.0 else '280S'
    if kw <= 132.0: return '280M' if kw == 110.0 else '315S'
    if kw <= 200.0: return '315M'
    if kw <= 315.0: return '315L'
    if kw <= 400.0: return '355M'
    return '355L'


def seed_motors(app_db):
    """
    Seed standard industrial electric motors for 50 Hz and 60 Hz across 2, 4, 6, 8 poles.
    """
    # Create table if it doesn't exist
    app_db.create_all()

    if Motor.query.first() is not None:
        return  # Already seeded

    records = []

    # 50 Hz configurations: sync speeds = 3000, 1500, 1000, 750
    # 60 Hz configurations: sync speeds = 3600, 1800, 1200, 900
    configs = [
        (50, 2, 3000.0, '400V'),
        (50, 4, 1500.0, '400V'),
        (50, 6, 1000.0, '400V'),
        (50, 8, 750.0,  '400V'),
        (60, 2, 3600.0, '460V'),
        (60, 4, 1800.0, '460V'),
        (60, 6, 1200.0, '460V'),
        (60, 8, 900.0,  '460V'),
    ]

    for freq, poles, sync_rpm, volt in configs:
        for kw in STANDARD_KW_RATINGS:
            rated_rpm = _calc_slip_rpm(sync_rpm, kw, poles)
            hp = round(kw * 1.34102, 1)
            frame = _get_frame_size(kw, poles)
            eff = min(96.8, round(88.0 + 8.0 * (kw / (kw + 30.0)), 1))

            model_name = f"IE3 {kw:.1f}kW {poles}P {freq}Hz ({int(rated_rpm)} rpm)"
            records.append(Motor(
                model_name=model_name,
                manufacturer='Standard IEC',
                rated_power_kw=kw,
                rated_power_hp=hp,
                frequency_hz=freq,
                poles=poles,
                sync_speed_rpm=sync_rpm,
                rated_speed_rpm=rated_rpm,
                efficiency_pct=eff,
                power_factor=0.86,
                frame_size=frame,
                voltage=volt
            ))

    app_db.session.bulk_save_objects(records)
    app_db.session.commit()
    print(f"[OK] Seeded {len(records)} industrial electric motors into database.")


def get_available_motors(frequency_hz=50, poles=4):
    """
    Query available motors for a given frequency and pole count, sorted by rated power.
    """
    return Motor.query.filter_by(frequency_hz=int(frequency_hz), poles=int(poles))\
                      .order_by(Motor.rated_power_kw.asc()).all()


def get_motor_by_id(motor_id):
    """
    Lookup a motor by primary key ID.
    """
    if not motor_id:
        return None
    try:
        return Motor.query.get(int(motor_id))
    except Exception:
        return None
