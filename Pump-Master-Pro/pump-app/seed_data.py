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
from models import db, Pump, PipeFitting, PipeMaterial, StandardPipe
from pump_curves import compute_power_poly


def seed_standard_pipes_data():
    """Build and insert comprehensive standard commercial pipe catalog."""
    pipes = []
    order = 1

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ASME B36.10M — Carbon Steel Pipes (Commercial Steel, e = 0.046 mm)
    # ─────────────────────────────────────────────────────────────────────────
    # (nb_mm, nb_inch, od_mm, [ (sch, wall_mm, rating_bar) ])
    cs_specs = [
        (15,  '1/2"',  21.3, [('Sch 40 (STD)', 2.77, 197), ('Sch 80 (XS)', 3.73, 265)]),
        (20,  '3/4"',  26.7, [('Sch 40 (STD)', 2.87, 161), ('Sch 80 (XS)', 3.91, 220)]),
        (25,  '1"',    33.4, [('Sch 40 (STD)', 3.38, 152), ('Sch 80 (XS)', 4.55, 205)]),
        (32,  '1-1/4"', 42.2, [('Sch 40 (STD)', 3.56, 127), ('Sch 80 (XS)', 4.85, 172)]),
        (40,  '1-1/2"', 48.3, [('Sch 40 (STD)', 3.68, 114), ('Sch 80 (XS)', 5.08, 158)]),
        (50,  '2"',    60.3, [('Sch 10', 2.77, 69), ('Sch 40 (STD)', 3.91, 97), ('Sch 80 (XS)', 5.54, 138), ('Sch 160', 8.74, 217)]),
        (65,  '2-1/2"', 73.0, [('Sch 40 (STD)', 5.16, 106), ('Sch 80 (XS)', 7.01, 144)]),
        (80,  '3"',    88.9, [('Sch 10', 3.05, 51), ('Sch 40 (STD)', 5.49, 93), ('Sch 80 (XS)', 7.62, 129), ('Sch 160', 11.13, 188)]),
        (100, '4"',    114.3, [('Sch 10', 3.05, 40), ('Sch 40 (STD)', 6.02, 79), ('Sch 80 (XS)', 8.56, 112), ('Sch 120', 11.13, 146), ('Sch 160', 13.49, 177)]),
        (125, '5"',    141.3, [('Sch 40 (STD)', 6.55, 70), ('Sch 80 (XS)', 9.53, 101)]),
        (150, '6"',    168.3, [('Sch 10', 3.40, 30), ('Sch 40 (STD)', 7.11, 63), ('Sch 80 (XS)', 10.97, 98), ('Sch 160', 18.26, 163)]),
        (200, '8"',    219.1, [('Sch 10', 3.76, 26), ('Sch 20', 6.35, 44), ('Sch 40 (STD)', 8.18, 56), ('Sch 80 (XS)', 12.70, 87), ('Sch 120', 18.26, 125), ('Sch 160', 23.01, 158)]),
        (250, '10"',   273.0, [('Sch 20', 6.35, 35), ('Sch 40 (STD)', 9.27, 51), ('Sch 80 (XS)', 15.09, 83), ('Sch 120', 21.44, 118), ('Sch 160', 28.58, 157)]),
        (300, '12"',   323.8, [('Sch 20', 6.35, 29), ('Sch 40 (STD)', 10.31, 48), ('Sch 80 (XS)', 17.48, 81)]),
        (350, '14"',   355.6, [('Sch 30', 9.53, 40), ('Sch 40 (STD)', 11.13, 47), ('Sch 80 (XS)', 19.05, 80)]),
        (400, '16"',   406.4, [('Sch 30', 9.53, 35), ('Sch 40 (STD)', 12.70, 47), ('Sch 80 (XS)', 21.44, 79)]),
        (450, '18"',   457.0, [('Sch 40 (STD)', 14.27, 47), ('Sch 80 (XS)', 23.83, 78)]),
        (500, '20"',   508.0, [('Sch 40 (STD)', 15.09, 45), ('Sch 80 (XS)', 26.19, 77)]),
        (600, '24"',   610.0, [('Sch 40 (STD)', 17.48, 43), ('Sch 80 (XS)', 30.96, 76)]),
    ]
    for nb_mm, nb_inch, od_mm, sch_list in cs_specs:
        for sch, wall_mm, p_bar in sch_list:
            id_mm = od_mm - 2.0 * wall_mm
            pipes.append(StandardPipe(
                standard='ASME B36.10M',
                material='Carbon Steel',
                material_key='commercial_steel',
                schedule_sdr=sch,
                nb_mm=nb_mm,
                nb_inch=nb_inch,
                od_mm=od_mm,
                wall_thickness_mm=wall_mm,
                id_mm=round(id_mm, 2),
                sdr=round(od_mm / wall_mm, 1),
                pressure_rating=f'PN {p_bar} bar ({int(p_bar * 14.5038)} psi)',
                notes='Standard welded/seamless carbon steel line pipe',
                sort_order=order
            ))
            order += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ASME B36.19M — Stainless Steel Pipes 304L/316L (e = 0.015 mm)
    # ─────────────────────────────────────────────────────────────────────────
    ss_specs = [
        (15,  '1/2"',  21.3, [('Sch 10S', 2.11, 148), ('Sch 40S', 2.77, 197), ('Sch 80S', 3.73, 265)]),
        (20,  '3/4"',  26.7, [('Sch 10S', 2.11, 118), ('Sch 40S', 2.87, 161), ('Sch 80S', 3.91, 220)]),
        (25,  '1"',    33.4, [('Sch 10S', 2.77, 124), ('Sch 40S', 3.38, 152), ('Sch 80S', 4.55, 205)]),
        (32,  '1-1/4"', 42.2, [('Sch 10S', 2.77, 98),  ('Sch 40S', 3.56, 127), ('Sch 80S', 4.85, 172)]),
        (40,  '1-1/2"', 48.3, [('Sch 10S', 2.77, 86),  ('Sch 40S', 3.68, 114), ('Sch 80S', 5.08, 158)]),
        (50,  '2"',    60.3, [('Sch 10S', 2.77, 69),  ('Sch 40S', 3.91, 97),  ('Sch 80S', 5.54, 138)]),
        (65,  '2-1/2"', 73.0, [('Sch 10S', 3.05, 63),  ('Sch 40S', 5.16, 106), ('Sch 80S', 7.01, 144)]),
        (80,  '3"',    88.9, [('Sch 10S', 3.05, 51),  ('Sch 40S', 5.49, 93),  ('Sch 80S', 7.62, 129)]),
        (100, '4"',    114.3, [('Sch 10S', 3.05, 40),  ('Sch 40S', 6.02, 79),  ('Sch 80S', 8.56, 112)]),
        (150, '6"',    168.3, [('Sch 10S', 3.40, 30),  ('Sch 40S', 7.11, 63),  ('Sch 80S', 10.97, 98)]),
        (200, '8"',    219.1, [('Sch 10S', 3.76, 26),  ('Sch 40S', 8.18, 56),  ('Sch 80S', 12.70, 87)]),
        (250, '10"',   273.0, [('Sch 10S', 4.19, 23),  ('Sch 40S', 9.27, 51),  ('Sch 80S', 12.70, 70)]),
        (300, '12"',   323.8, [('Sch 10S', 4.57, 21),  ('Sch 40S', 9.53, 44),  ('Sch 80S', 12.70, 59)]),
    ]
    for nb_mm, nb_inch, od_mm, sch_list in ss_specs:
        for sch, wall_mm, p_bar in sch_list:
            id_mm = od_mm - 2.0 * wall_mm
            pipes.append(StandardPipe(
                standard='ASME B36.19M',
                material='Stainless Steel',
                material_key='stainless_steel',
                schedule_sdr=sch,
                nb_mm=nb_mm,
                nb_inch=nb_inch,
                od_mm=od_mm,
                wall_thickness_mm=wall_mm,
                id_mm=round(id_mm, 2),
                sdr=round(od_mm / wall_mm, 1),
                pressure_rating=f'PN {p_bar} bar ({int(p_bar * 14.5038)} psi)',
                notes='Stainless Steel 304L/316L schedule pipe',
                sort_order=order
            ))
            order += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 3. ISO 4427 / EN 12201 / SANS 4427 — HDPE PE100 Polyethylene (e = 0.007 mm)
    # ─────────────────────────────────────────────────────────────────────────
    hdpe_sdrs = [
        ('SDR 7.4', 7.4, 25.0, 'PN 25 (25 bar / 363 psi)'),
        ('SDR 9',   9.0, 20.0, 'PN 20 (20 bar / 290 psi)'),
        ('SDR 11',  11.0, 16.0, 'PN 16 (16 bar / 232 psi)'),
        ('SDR 13.6', 13.6, 12.5, 'PN 12.5 (12.5 bar / 181 psi)'),
        ('SDR 17',  17.0, 10.0, 'PN 10 (10 bar / 145 psi)'),
        ('SDR 21',  21.0, 8.0,  'PN 8 (8 bar / 116 psi)'),
        ('SDR 26',  26.0, 6.0,  'PN 6 (6 bar / 87 psi)'),
    ]
    hdpe_ods = [
        (25, 20), (32, 25), (40, 32), (50, 40), (63, 50), (75, 65), (90, 80),
        (110, 100), (125, 100), (140, 125), (160, 150), (180, 150), (200, 200),
        (225, 200), (250, 250), (280, 250), (315, 300), (355, 350), (400, 400),
        (450, 450), (500, 500), (560, 500), (630, 600)
    ]
    for sch_label, sdr_val, pn_bar, rating_str in hdpe_sdrs:
        for od_mm, nb_mm in hdpe_ods:
            wall_mm = round(od_mm / sdr_val, 2)
            if wall_mm < 2.0:
                wall_mm = 2.0
            id_mm = round(od_mm - 2.0 * wall_mm, 2)
            if id_mm <= 0:
                continue
            pipes.append(StandardPipe(
                standard='ISO 4427 / SANS 4427',
                material='HDPE (PE100)',
                material_key='hdpe',
                schedule_sdr=sch_label,
                nb_mm=nb_mm,
                nb_inch=f'{int(nb_mm)}mm',
                od_mm=float(od_mm),
                wall_thickness_mm=wall_mm,
                id_mm=id_mm,
                sdr=sdr_val,
                pressure_rating=rating_str,
                notes=f'HDPE PE100 High Density Polyethylene ({sch_label})',
                sort_order=order
            ))
            order += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 4. DIN 8062 / ISO 1452 / SANS 966-1 — uPVC Metric Pressure Pipe (e = 0.0015 mm)
    # ─────────────────────────────────────────────────────────────────────────
    pvc_classes = [
        ('Class 6 / SDR 41', 41.0, 6.0, 'PN 6 (6 bar / 87 psi)'),
        ('Class 9 / SDR 26', 26.0, 9.0, 'PN 9 (9 bar / 130 psi)'),
        ('Class 12 / SDR 21', 21.0, 12.0, 'PN 12 (12 bar / 174 psi)'),
        ('Class 16 / SDR 13.5', 13.5, 16.0, 'PN 16 (16 bar / 232 psi)'),
        ('Class 20 / SDR 11', 11.0, 20.0, 'PN 20 (20 bar / 290 psi)'),
    ]
    pvc_ods = [
        (32, 25), (40, 32), (50, 40), (63, 50), (75, 65), (90, 80),
        (110, 100), (125, 100), (140, 125), (160, 150), (200, 200),
        (250, 250), (315, 300), (400, 400), (500, 500)
    ]
    for sch_label, sdr_val, pn_bar, rating_str in pvc_classes:
        for od_mm, nb_mm in pvc_ods:
            wall_mm = round(od_mm / sdr_val, 2)
            if wall_mm < 1.5:
                wall_mm = 1.5
            id_mm = round(od_mm - 2.0 * wall_mm, 2)
            pipes.append(StandardPipe(
                standard='DIN 8062 / ISO 1452',
                material='uPVC',
                material_key='pvc',
                schedule_sdr=sch_label,
                nb_mm=nb_mm,
                nb_inch=f'{int(nb_mm)}mm',
                od_mm=float(od_mm),
                wall_thickness_mm=wall_mm,
                id_mm=id_mm,
                sdr=sdr_val,
                pressure_rating=rating_str,
                notes=f'Unplasticized Polyvinyl Chloride Metric ({sch_label})',
                sort_order=order
            ))
            order += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 5. ASTM D1785 — PVC Schedule 40 & Schedule 80 (e = 0.0015 mm)
    # ─────────────────────────────────────────────────────────────────────────
    pvc_ips = [
        (15,  '1/2"',  21.3, [('Sch 40', 2.77, 'PN 41 (600 psi)'), ('Sch 80', 3.73, 'PN 59 (850 psi)')]),
        (20,  '3/4"',  26.7, [('Sch 40', 2.87, 'PN 33 (480 psi)'), ('Sch 80', 3.91, 'PN 48 (690 psi)')]),
        (25,  '1"',    33.4, [('Sch 40', 3.38, 'PN 31 (450 psi)'), ('Sch 80', 4.55, 'PN 43 (630 psi)')]),
        (32,  '1-1/4"', 42.2, [('Sch 40', 3.56, 'PN 25 (370 psi)'), ('Sch 80', 4.85, 'PN 36 (520 psi)')]),
        (40,  '1-1/2"', 48.3, [('Sch 40', 3.68, 'PN 23 (330 psi)'), ('Sch 80', 5.08, 'PN 32 (470 psi)')]),
        (50,  '2"',    60.3, [('Sch 40', 3.91, 'PN 19 (280 psi)'), ('Sch 80', 5.54, 'PN 28 (400 psi)')]),
        (65,  '2-1/2"', 73.0, [('Sch 40', 5.16, 'PN 21 (300 psi)'), ('Sch 80', 7.01, 'PN 29 (420 psi)')]),
        (80,  '3"',    88.9, [('Sch 40', 5.49, 'PN 18 (260 psi)'), ('Sch 80', 7.62, 'PN 26 (370 psi)')]),
        (100, '4"',    114.3, [('Sch 40', 6.02, 'PN 15 (220 psi)'), ('Sch 80', 8.56, 'PN 22 (320 psi)')]),
        (150, '6"',    168.3, [('Sch 40', 7.11, 'PN 12 (180 psi)'), ('Sch 80', 10.97, 'PN 19 (280 psi)')]),
        (200, '8"',    219.1, [('Sch 40', 8.18, 'PN 11 (160 psi)'), ('Sch 80', 12.70, 'PN 17 (250 psi)')]),
        (250, '10"',   273.0, [('Sch 40', 9.27, 'PN 10 (140 psi)'), ('Sch 80', 15.09, 'PN 16 (230 psi)')]),
        (300, '12"',   323.8, [('Sch 40', 10.31, 'PN 9 (130 psi)'), ('Sch 80', 17.48, 'PN 16 (230 psi)')]),
    ]
    for nb_mm, nb_inch, od_mm, sch_list in pvc_ips:
        for sch, wall_mm, rating_str in sch_list:
            id_mm = od_mm - 2.0 * wall_mm
            pipes.append(StandardPipe(
                standard='ASTM D1785 (PVC)',
                material='uPVC',
                material_key='pvc',
                schedule_sdr=sch,
                nb_mm=nb_mm,
                nb_inch=nb_inch,
                od_mm=od_mm,
                wall_thickness_mm=wall_mm,
                id_mm=round(id_mm, 2),
                sdr=round(od_mm / wall_mm, 1),
                pressure_rating=rating_str,
                notes='Rigid PVC pressure pipe (ASTM D1785 IPS)',
                sort_order=order
            ))
            order += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 6. EN 545 / ISO 2531 — Ductile Iron Water Pipes (e = 0.260 mm)
    # ─────────────────────────────────────────────────────────────────────────
    di_specs = [
        (80,  '3"',  98.0,  [('Class C40', 4.4, 'PN 40 (40 bar)'), ('Class K9', 6.0, 'PN 50 (50 bar)')]),
        (100, '4"',  118.0, [('Class C40', 4.4, 'PN 40 (40 bar)'), ('Class K9', 6.0, 'PN 50 (50 bar)')]),
        (150, '6"',  170.0, [('Class C40', 4.5, 'PN 40 (40 bar)'), ('Class K9', 6.0, 'PN 45 (45 bar)')]),
        (200, '8"',  222.0, [('Class C40', 4.7, 'PN 40 (40 bar)'), ('Class K9', 6.3, 'PN 40 (40 bar)')]),
        (250, '10"', 274.0, [('Class C40', 5.5, 'PN 40 (40 bar)'), ('Class K9', 6.8, 'PN 35 (35 bar)')]),
        (300, '12"', 326.0, [('Class C40', 6.2, 'PN 40 (40 bar)'), ('Class K9', 7.2, 'PN 32 (32 bar)')]),
        (350, '14"', 378.0, [('Class C30', 6.3, 'PN 30 (30 bar)'), ('Class K9', 7.7, 'PN 30 (30 bar)')]),
        (400, '16"', 429.0, [('Class C30', 6.5, 'PN 30 (30 bar)'), ('Class K9', 8.1, 'PN 30 (30 bar)')]),
        (500, '20"', 532.0, [('Class C30', 7.5, 'PN 30 (30 bar)'), ('Class K9', 9.0, 'PN 28 (28 bar)')]),
        (600, '24"', 635.0, [('Class C25', 7.9, 'PN 25 (25 bar)'), ('Class K9', 9.9, 'PN 25 (25 bar)')]),
    ]
    for nb_mm, nb_inch, od_mm, sch_list in di_specs:
        for sch, wall_mm, rating_str in sch_list:
            id_mm = od_mm - 2.0 * wall_mm
            pipes.append(StandardPipe(
                standard='EN 545 / ISO 2531',
                material='Ductile Iron',
                material_key='cast_iron',
                schedule_sdr=sch,
                nb_mm=nb_mm,
                nb_inch=nb_inch,
                od_mm=od_mm,
                wall_thickness_mm=wall_mm,
                id_mm=round(id_mm, 2),
                sdr=round(od_mm / wall_mm, 1),
                pressure_rating=rating_str,
                notes='Ductile Iron pressure pipe for water and slurry',
                sort_order=order
            ))
            order += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 7. SANS 62 / BS 1387 — Galvanised Steel (e = 0.150 mm)
    # ─────────────────────────────────────────────────────────────────────────
    galv_specs = [
        (15,  '1/2"', 21.3, [('Medium (Class B)', 2.65, 'PN 25 (25 bar)'), ('Heavy (Class C)', 3.25, 'PN 32 (32 bar)')]),
        (20,  '3/4"', 26.9, [('Medium (Class B)', 2.65, 'PN 25 (25 bar)'), ('Heavy (Class C)', 3.25, 'PN 32 (32 bar)')]),
        (25,  '1"',   33.7, [('Medium (Class B)', 3.25, 'PN 25 (25 bar)'), ('Heavy (Class C)', 4.05, 'PN 32 (32 bar)')]),
        (32,  '1-1/4"', 42.4, [('Medium (Class B)', 3.25, 'PN 25 (25 bar)'), ('Heavy (Class C)', 4.05, 'PN 32 (32 bar)')]),
        (40,  '1-1/2"', 48.3, [('Medium (Class B)', 3.25, 'PN 25 (25 bar)'), ('Heavy (Class C)', 4.05, 'PN 32 (32 bar)')]),
        (50,  '2"',   60.3, [('Medium (Class B)', 3.65, 'PN 25 (25 bar)'), ('Heavy (Class C)', 4.50, 'PN 32 (32 bar)')]),
        (65,  '2-1/2"', 76.1, [('Medium (Class B)', 3.65, 'PN 25 (25 bar)'), ('Heavy (Class C)', 4.50, 'PN 32 (32 bar)')]),
        (80,  '3"',   88.9, [('Medium (Class B)', 4.05, 'PN 25 (25 bar)'), ('Heavy (Class C)', 4.85, 'PN 32 (32 bar)')]),
        (100, '4"',   114.3, [('Medium (Class B)', 4.50, 'PN 25 (25 bar)'), ('Heavy (Class C)', 5.40, 'PN 32 (32 bar)')]),
        (150, '6"',   165.1, [('Medium (Class B)', 4.85, 'PN 25 (25 bar)'), ('Heavy (Class C)', 5.40, 'PN 32 (32 bar)')]),
    ]
    for nb_mm, nb_inch, od_mm, sch_list in galv_specs:
        for sch, wall_mm, rating_str in sch_list:
            id_mm = od_mm - 2.0 * wall_mm
            pipes.append(StandardPipe(
                standard='SANS 62 / BS 1387',
                material='Galvanised Steel',
                material_key='galvanised_steel',
                schedule_sdr=sch,
                nb_mm=nb_mm,
                nb_inch=nb_inch,
                od_mm=od_mm,
                wall_thickness_mm=wall_mm,
                id_mm=round(id_mm, 2),
                sdr=round(od_mm / wall_mm, 1),
                pressure_rating=rating_str,
                notes='Galvanized mild steel threaded/flanged water pipe',
                sort_order=order
            ))
            order += 1

    db.session.add_all(pipes)
    db.session.commit()
    print(f'Seeded {len(pipes)} standard commercial pipes.')


def seed_pipe_reference_data(app):
    """
    Seed default pipe fittings (K-factors), pipe materials (roughness values),
    and standard commercial pipes into the database. Idempotent — skips if rows already exist.
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
                PipeFitting(key='entry_bellmouth',      label='Pipe Entry (Bellmouth)',   k_factor=0.05, category='entry_exit', sort_order=13),
                PipeFitting(key='entry_rounded',        label='Pipe Entry (Rounded)',     k_factor=0.20, category='entry_exit', sort_order=14),
                PipeFitting(key='entry_sharp',          label='Pipe Entry (Sharp)',       k_factor=0.50, category='entry_exit', sort_order=15),
                PipeFitting(key='exit_abrupt',          label='Pipe Exit (Abrupt)',       k_factor=1.00, category='entry_exit', sort_order=16),
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

        # ── Seed Standard Pipes ──────────────────────────────────────────────
        if StandardPipe.query.count() == 0:
            seed_standard_pipes_data()



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
