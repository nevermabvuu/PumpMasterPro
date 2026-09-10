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
from models import db, Pump, PipeFitting, PipeMaterial
from pump_curves import compute_power_poly


def seed_pipe_reference_data(app):
    """
    Seed default pipe fittings (K-factors) and pipe materials (roughness values)
    into the database. Idempotent — skips if rows already exist.

    These values were previously hardcoded in pipe_network.js and routes/pipe_network.py.
    Sources: Crane TP-410, Idelchik Handbook, engineering handbooks.
    """
    with app.app_context():
        # ── Seed Fittings ────────────────────────────────────────────────────
        if PipeFitting.query.count() == 0:
            fittings = [
                PipeFitting(key='elbow_90_standard',    label='90 Elbow (Standard)',     k_factor=0.90, category='elbow',      sort_order=1),
                PipeFitting(key='elbow_90_long_radius', label='90 Elbow (Long Radius)',  k_factor=0.60, category='elbow',      sort_order=2),
                PipeFitting(key='elbow_45',             label='45 Elbow',                k_factor=0.40, category='elbow',      sort_order=3),
                PipeFitting(key='gate_valve_open',      label='Gate Valve (Open)',        k_factor=0.20, category='valve',      sort_order=4),
                PipeFitting(key='gate_valve_half',      label='Gate Valve (50% Open)',    k_factor=5.60, category='valve',      sort_order=5),
                PipeFitting(key='globe_valve_open',     label='Globe Valve (Open)',       k_factor=10.0, category='valve',      sort_order=6),
                PipeFitting(key='check_valve_swing',    label='Check Valve (Swing)',      k_factor=2.50, category='valve',      sort_order=7),
                PipeFitting(key='check_valve_ball',     label='Check Valve (Ball)',       k_factor=4.50, category='valve',      sort_order=8),
                PipeFitting(key='ball_valve_open',      label='Ball Valve (Open)',        k_factor=0.05, category='valve',      sort_order=9),
                PipeFitting(key='butterfly_valve_open', label='Butterfly Valve (Open)',   k_factor=0.30, category='valve',      sort_order=10),
                PipeFitting(key='tee_run_through',      label='Tee (Run Through)',        k_factor=0.40, category='tee',        sort_order=11),
                PipeFitting(key='tee_branch_flow',      label='Tee (Branch Flow)',        k_factor=1.80, category='tee',        sort_order=12),
                PipeFitting(key='entry_sharp',          label='Pipe Entry (Sharp)',       k_factor=0.50, category='entry_exit', sort_order=13),
                PipeFitting(key='entry_rounded',        label='Pipe Entry (Rounded)',     k_factor=0.20, category='entry_exit', sort_order=14),
                PipeFitting(key='exit_abrupt',          label='Pipe Exit (Abrupt)',       k_factor=1.00, category='entry_exit', sort_order=15),
                PipeFitting(key='reducer_gradual',      label='Reducer (Gradual)',        k_factor=0.10, category='transition', sort_order=16),
                PipeFitting(key='reducer_sudden',       label='Reducer (Sudden)',         k_factor=0.50, category='transition', sort_order=17),
                PipeFitting(key='expander_gradual',     label='Expander (Gradual)',       k_factor=0.30, category='transition', sort_order=18),
            ]
            db.session.add_all(fittings)
            db.session.commit()
            print(f'Seeded {len(fittings)} pipe fittings.')

        # ── Seed Materials ───────────────────────────────────────────────────
        if PipeMaterial.query.count() == 0:
            materials = [
                PipeMaterial(key='commercial_steel', label='Commercial Steel  (e = 0.046 mm)', roughness_mm=0.046,  sort_order=1),
                PipeMaterial(key='galvanised_steel', label='Galvanised Steel  (e = 0.150 mm)', roughness_mm=0.150,  sort_order=2),
                PipeMaterial(key='cast_iron',        label='Cast Iron         (e = 0.260 mm)', roughness_mm=0.260,  sort_order=3),
                PipeMaterial(key='pvc',              label='PVC / Plastic     (e = 0.002 mm)', roughness_mm=0.0015, sort_order=4),
                PipeMaterial(key='hdpe',             label='HDPE              (e = 0.007 mm)', roughness_mm=0.007,  sort_order=5),
                PipeMaterial(key='stainless_steel',  label='Stainless Steel   (e = 0.015 mm)', roughness_mm=0.015,  sort_order=6),
                PipeMaterial(key='concrete',         label='Concrete          (e = 1.000 mm)', roughness_mm=1.000,  sort_order=7),
                PipeMaterial(key='smooth',           label='Smooth / Drawn    (e = 0.002 mm)', roughness_mm=0.0015, sort_order=8),
            ]
            db.session.add_all(materials)
            db.session.commit()
            print(f'Seeded {len(materials)} pipe materials.')



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
            impeller_diameters='330;305;280;255;230',
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
            impeller_diameters='480;450;420;390;360',
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
            impeller_diameters='610;570;530;490;450',
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
            name='Warman 10/8 F-MTest', manufacturer='Weir Minerals',
            model_number='10/8 F-M', size='10/8 F-M',
            speed_rpm=600, impeller_dia_mm=760,
            impeller_diameters='760;710;660;610;560',
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
            impeller_diameters='200;185;170;155',
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
            impeller_diameters='315;290;265;240',
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
            impeller_diameters='190;175;160',
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

        for p_obj in pumps:
            p_obj.sync_curve_fields()

        db.session.add_all(pumps)
        db.session.commit()
        print(f'Seeded {len(pumps)} pumps.')
