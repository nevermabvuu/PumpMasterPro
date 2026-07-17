"""
Seed database with example Warman-style pump data.

Efficiency polynomials use a closed-form quadratic that guarantees:
  - η(0) < 0  (clipped → 0)
  - η(Q_bep) = η_peak  (maximum)
  - η(Q_max) = 0      (falls to zero at runout)
  Requires Q_bep > Q_max / 2.

Power polynomials are fitted with a non-zero shutoff anchor (≈0.35·P_BEP)
so the displayed power curve rises continuously instead of spiking.
"""
import json
from models import db, Pump
from pump_curves import compute_power_poly


def _hq(H0, Q_max):
    """Parabolic H-Q: H = H0 - H0/Q_max² · Q²"""
    return [H0, 0.0, -H0 / Q_max ** 2, 0.0]


def _eff(eta_peak, Q_bep, Q_max):
    """
    Quadratic efficiency bell:
      η = b0 + b1·Q + b2·Q²
      peaks at Q_bep, = 0 at Q_max, < 0 at Q=0  (Q_bep > Q_max/2 required)
    """
    assert Q_bep > Q_max / 2, f"Need Q_bep > Q_max/2 for proper bell curve: {Q_bep} vs {Q_max/2}"
    den = (Q_max - Q_bep) ** 2
    b2  = -eta_peak / den
    b1  =  2 * eta_peak * Q_bep / den
    b0  =  eta_peak * Q_max * (Q_max - 2 * Q_bep) / den
    return [b0, b1, b2, 0.0]


def _pow(h, e, q_bep, q_max):
    """Derive and fit power polynomial from H-Q and efficiency coefficients."""
    return compute_power_poly(h, e, q_bep, q_max)


def seed_pumps(app):
    with app.app_context():
        if Pump.query.count() > 0:
            return

        pumps = []

        # ── Warman 4/3 C-AH ─────────────────────────────────────────────────
        h = _hq(46.0, 80.0)
        e = _eff(72.0, 44.0, 80.0)
        p = _pow(h, e, 44.0, 80.0)
        pumps.append(Pump(
            name='Warman 4/3 C-AH', manufacturer='Weir Minerals',
            model_number='4/3 C-AH', size='4/3 C-AH',
            speed_rpm=1450, impeller_dia_mm=330,
            impeller_diameters=json.dumps([330, 305, 280, 255, 230]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=1.8, npsh_c1=0.0, npsh_c2=0.0012,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=80.0, q_bep=44.0,
            hr=0.90, qr=0.92, er=0.85,
            pump_type='centrifugal slurry',
            application='Slurry / mineral processing',
            notes='Standard duty slurry pump. Up to 40% w/w abrasive slurry.',
        ))

        # ── Warman 6/4 D-AH ─────────────────────────────────────────────────
        h = _hq(58.0, 350.0)
        e = _eff(80.0, 195.0, 350.0)
        p = _pow(h, e, 195.0, 350.0)
        pumps.append(Pump(
            name='Warman 6/4 D-AH', manufacturer='Weir Minerals',
            model_number='6/4 D-AH', size='6/4 D-AH',
            speed_rpm=1000, impeller_dia_mm=480,
            impeller_diameters=json.dumps([480, 450, 420, 390, 360]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=2.2, npsh_c1=0.0, npsh_c2=0.000045,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=350.0, q_bep=195.0,
            hr=0.88, qr=0.90, er=0.82,
            pump_type='centrifugal slurry',
            application='Slurry / tailings',
            notes='Heavy duty slurry pump for coarse and abrasive slurries.',
        ))

        # ── Warman 8/6 E-AH ─────────────────────────────────────────────────
        h = _hq(72.0, 800.0)
        e = _eff(82.0, 440.0, 800.0)
        p = _pow(h, e, 440.0, 800.0)
        pumps.append(Pump(
            name='Warman 8/6 E-AH', manufacturer='Weir Minerals',
            model_number='8/6 E-AH', size='8/6 E-AH',
            speed_rpm=750, impeller_dia_mm=610,
            impeller_diameters=json.dumps([610, 570, 530, 490, 450]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=2.8, npsh_c1=0.0, npsh_c2=0.000025,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=800.0, q_bep=440.0,
            hr=0.87, qr=0.90, er=0.80,
            pump_type='centrifugal slurry',
            application='Slurry / coarse solids',
            notes='Large slurry pump for high flow, coarse slurry duties.',
        ))

        # ── Warman 10/8 F-M ─────────────────────────────────────────────────
        h = _hq(82.0, 1600.0)
        e = _eff(80.0, 880.0, 1600.0)
        p = _pow(h, e, 880.0, 1600.0)
        pumps.append(Pump(
            name='Warman 10/8 F-M', manufacturer='Weir Minerals',
            model_number='10/8 F-M', size='10/8 F-M',
            speed_rpm=600, impeller_dia_mm=760,
            impeller_diameters=json.dumps([760, 710, 660, 610, 560]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=3.2, npsh_c1=0.0, npsh_c2=0.000012,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=1600.0, q_bep=880.0,
            hr=0.86, qr=0.89, er=0.78,
            pump_type='centrifugal slurry',
            application='Mill circuit',
            notes='Mill discharge pump for SAG/ball mill circuits.',
        ))

        # ── Generic End-Suction 50-200 ───────────────────────────────────────
        h = _hq(55.0, 22.0)
        e = _eff(68.0, 12.0, 22.0)
        p = _pow(h, e, 12.0, 22.0)
        pumps.append(Pump(
            name='Generic CW 50-200', manufacturer='Generic',
            model_number='CW50-200', size='50-200',
            speed_rpm=2900, impeller_dia_mm=200,
            impeller_diameters=json.dumps([200, 185, 170, 155]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=1.2, npsh_c1=0.0, npsh_c2=0.040,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=22.0, q_bep=12.0,
            hr=1.0, qr=1.0, er=1.0,
            pump_type='centrifugal',
            application='General water service',
            notes='Standard end-suction centrifugal pump for water duties.',
        ))

        # ── Generic 100-315 ──────────────────────────────────────────────────
        h = _hq(68.0, 250.0)
        e = _eff(78.0, 138.0, 250.0)
        p = _pow(h, e, 138.0, 250.0)
        pumps.append(Pump(
            name='Generic CW 100-315', manufacturer='Generic',
            model_number='CW100-315', size='100-315',
            speed_rpm=1450, impeller_dia_mm=315,
            impeller_diameters=json.dumps([315, 290, 265, 240]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=1.8, npsh_c1=0.0, npsh_c2=0.000095,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=250.0, q_bep=138.0,
            hr=1.0, qr=1.0, er=1.0,
            pump_type='centrifugal',
            application='General water / process',
            notes='Medium-duty centrifugal pump for water and mild process fluids.',
        ))

        # ── KSB Etanorm 32-200 ───────────────────────────────────────────────
        h = _hq(30.0, 16.0)
        e = _eff(62.0, 9.0, 16.0)
        p = _pow(h, e, 9.0, 16.0)
        pumps.append(Pump(
            name='KSB Etanorm 32-200', manufacturer='KSB',
            model_number='Etanorm 32-200', size='32-200',
            speed_rpm=2900, impeller_dia_mm=190,
            impeller_diameters=json.dumps([190, 175, 160]),
            hq_a0=h[0], hq_a1=h[1], hq_a2=h[2], hq_a3=h[3],
            eff_b0=e[0], eff_b1=e[1], eff_b2=e[2], eff_b3=e[3],
            npsh_c0=1.0, npsh_c1=0.0, npsh_c2=0.10,
            pow_p0=p[0], pow_p1=p[1], pow_p2=p[2],
            q_min=0.0, q_max=16.0, q_bep=9.0,
            hr=1.0, qr=1.0, er=1.0,
            pump_type='centrifugal',
            application='Building services / HVAC',
            notes='Compact process pump for heating / cooling circuits.',
        ))

        db.session.bulk_save_objects(pumps)
        db.session.commit()
        print(f'Seeded {len(pumps)} pumps.')
