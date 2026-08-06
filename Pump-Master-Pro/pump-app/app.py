"""
app.py — Main Flask application entry point.

Beginners Note: This file initializes Flask, configures the database connection,
runs auto-migrations, registers modular Flask Blueprints, and launches the server.
"""

import os
import re
from flask import Flask
from models import db, Supplier, ReportConfig
from seed_data import seed_pumps
from routes import main_bp, pumps_bp, curves_bp, selection_bp, comparison_bp, reports_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'pumps.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SESSION_SECRET', 'pump-dev-secret')

# Initialize database extension with Flask app
db.init_app(app)

# ── Database Creation & Auto-Migration ─────────────────────────────────────────
with app.app_context():
    db.create_all()
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # 1. Reports table schema migrations
            rep_res = conn.execute(text("PRAGMA table_info(reports)"))
            rep_cols = [row[1] for row in rep_res.fetchall()]
            if 'curve_display_mode' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN curve_display_mode VARCHAR(20) DEFAULT 'all'"))
            if 'show_eff_isolines' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_eff_isolines INTEGER DEFAULT 1"))
            if 'show_power_isolines' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_power_isolines INTEGER DEFAULT 0"))
            if 'show_npsh_curves' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_npsh_curves INTEGER DEFAULT 1"))
            if 'show_speed_lines' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_speed_lines INTEGER DEFAULT 1"))
            if 'show_additional_graphs' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_additional_graphs INTEGER DEFAULT 1"))
            if 'show_legend' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_legend INTEGER DEFAULT 1"))
            if 'legend_position' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN legend_position VARCHAR(30) DEFAULT 'top_right'"))
            for rep_overlay in ['show_rpm_overlay', 'show_dia_overlay']:
                if rep_overlay not in rep_cols:
                    conn.execute(text(f"ALTER TABLE reports ADD COLUMN {rep_overlay} INTEGER DEFAULT 0"))

            # 2. Pumps table schema migrations
            result = conn.execute(text("PRAGMA table_info(pumps)"))
            cols = [row[1] for row in result.fetchall()]
            axis_cols = [
                'axis_flow_min', 'axis_flow_max', 'axis_flow_major', 'axis_flow_minor',
                'axis_head_min', 'axis_head_max', 'axis_head_major', 'axis_head_minor',
                'axis_eff_min', 'axis_eff_max', 'axis_eff_major', 'axis_eff_minor',
                'axis_power_min', 'axis_power_max', 'axis_power_major', 'axis_power_minor',
                'axis_npsh_min', 'axis_npsh_max', 'axis_npsh_major', 'axis_npsh_minor',
            ]
            bool_design_cols = ['is_multistage', 'is_double_suction', 'is_angle_trim', 'is_self_priming', 'is_non_clog', 'has_inducer', 'is_throttling_capable']
            for b_col in bool_design_cols:
                if b_col not in cols:
                    def_v = 1 if b_col == 'is_throttling_capable' else 0
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {b_col} INTEGER DEFAULT {def_v}"))

            if 'num_stages' not in cols:
                conn.execute(text("ALTER TABLE pumps ADD COLUMN num_stages INTEGER DEFAULT 1"))

            real_cols = ['min_flow_m3h', 'max_orifice_dia_mm', 'impeller_eye_area_cm2', 'vfd_min_hz', 'vfd_max_hz']
            for r_col in real_cols:
                if r_col not in cols:
                    def_r = 30.0 if r_col == 'vfd_min_hz' else (60.0 if r_col == 'vfd_max_hz' else 0.0)
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {r_col} REAL DEFAULT {def_r}"))

            for col_name in ['family_type', 'curve_labels', 'curve_diameters', 'curve_colors', 'curve_modes',
                             'curve_units', 'curve_raw_tables', 'curve_coeffs',
                             'unit_q', 'unit_h', 'unit_npsh', 'unit_pow', 'unit_op_q', 'graph_custom_label_pos', 'graph_speed_line_values',
                             'graph_rpm_values', 'graph_dia_overlay_values',
                             'head_curve_style', 'eff_curve_style', 'power_curve_style', 'npsh_curve_style', 'main_curve_style',
                             'app_modules', 'impeller_material', 'casing_material', 'number_of_vanes', 'suction_size', 'discharge_size',
                             'unit_suction', 'unit_discharge', 'unit_solid', 'unit_pressure', 'unit_temp',
                             'max_solid_size_mm', 'max_pressure_bar', 'max_temp_c', 'seal_type', 'drive_type'] + axis_cols:
                if col_name not in cols:
                    if col_name in axis_cols:
                        col_type = "INTEGER" if col_name.endswith('_minor') else "REAL"
                        conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {col_name} {col_type} DEFAULT NULL"))
                    else:
                        if col_name == 'family_type':
                            default_val = "'trimmed_impeller'"
                        elif col_name == 'graph_custom_label_pos':
                            default_val = "'{}'"
                        elif col_name == 'head_curve_style':
                            default_val = "'#58a6ff;2.0,solid'"
                        elif col_name == 'eff_curve_style':
                            default_val = "'#3fb950;1.5,dot'"
                        elif col_name == 'power_curve_style':
                            default_val = "'#f85149;1.5,longdash'"
                        elif col_name == 'npsh_curve_style':
                            default_val = "'#39d3c0;1.5,dashdot'"
                        elif col_name == 'main_curve_style':
                            default_val = "'graph'"
                        elif col_name in ['unit_q', 'unit_op_q']:
                            default_val = "'m3h'"
                        elif col_name in ['unit_h', 'unit_npsh']:
                            default_val = "'m'"
                        elif col_name == 'unit_pow':
                            default_val = "'kw'"
                        else:
                            default_val = "''"
                        conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {col_name} TEXT DEFAULT {default_val}"))

            # Boolean overlay columns for pumps
            for b_overlay_col in ['graph_show_rpm_overlay', 'graph_show_dia_overlay']:
                if b_overlay_col not in cols:
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {b_overlay_col} INTEGER DEFAULT 0"))

            poly_cols = [
                'hq_a4', 'hq_a5', 'eff_b4', 'eff_b5',
                'npsh_c3', 'npsh_c4', 'npsh_c5',
                'pow_p3', 'pow_p4', 'pow_p5'
            ]
            for p_col in poly_cols:
                if p_col not in cols:
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {p_col} REAL DEFAULT 0.0"))

            for p_col, p_def in [('poly_order', 3), ('poly_order_hq', 3), ('poly_order_eff', 3), ('poly_order_npsh', 2), ('poly_order_pow', 2)]:
                if p_col not in cols:
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {p_col} INTEGER DEFAULT {p_def}"))
            for old_col in ['main_curve_label', 'main_curve_dia_mm', 'data_units']:
                if old_col in cols:
                    try:
                        conn.execute(text(f"ALTER TABLE pumps DROP COLUMN {old_col}"))
                    except Exception:
                        pass

            # Data cleanup for VS pumps where diameter values were saved in graph_speed_line_values
            try:
                vs_pumps = conn.execute(text("SELECT id, speed_rpm, impeller_dia_mm, graph_speed_line_values, graph_dia_overlay_values FROM pumps WHERE family_type = 'variable_speed' AND graph_speed_line_values != '' AND graph_speed_line_values IS NOT NULL")).fetchall()
                for p_row in vs_pumps:
                    pid, s_rpm, i_dia, spd_val, dia_val = p_row[0], p_row[1], p_row[2], p_row[3], p_row[4]
                    if spd_val and not dia_val:
                        vals = [float(x.strip()) for x in re.split(r'[,;\s]+', spd_val) if x.strip() and x.strip().replace('.','',1).isdigit()]
                        if vals and max(vals) < 600 and (s_rpm is None or max(vals) < s_rpm * 0.7):
                            conn.execute(text("UPDATE pumps SET graph_dia_overlay_values = :d_val, graph_show_dia_overlay = 1, graph_speed_line_values = '' WHERE id = :pid"), {"d_val": spd_val, "pid": pid})
                conn.execute(text("UPDATE pumps SET graph_show_speed_lines = 0 WHERE graph_show_rpm_overlay = 0 AND (graph_rpm_values IS NULL OR graph_rpm_values = '')"))
            except Exception as e:
                print("VS pump data cleanup notice:", e)

            conn.commit()

            # Seed default supplier if table is empty
            if Supplier.query.count() == 0:
                def_sup = Supplier(
                    name="Weir Minerals / Warman",
                    contact_email="engineering@weirminerals.com",
                    website="www.global.weir",
                    phone="+1-800-PUMPS",
                    address="Global Slurry & Heavy Duty Engineering Division"
                )
                db.session.add(def_sup)
                db.session.commit()

            # Seed default report configuration if table is empty
            if ReportConfig.query.count() == 0:
                def_sup = Supplier.query.first()
                def_rep = ReportConfig(
                    supplier_id=def_sup.id if def_sup else None,
                    title="Standard Pump Technical Datasheet",
                    description="Comprehensive engineering datasheet showing duty point, performance curves, construction materials, and operational limits.",
                    template_name="standard_datasheet.html",
                    show_head_flow_graph=True,
                    show_efficiency_graph=True,
                    show_power_graph=True,
                    show_npsh_graph=True,
                    header_text="PUMP MASTER PRO - TECHNICAL DATASHEET",
                    footer_text="Generated by Pump Master Pro Engineering Suite",
                    primary_color="#1e3a8a",
                    show_duty_point=True,
                    show_materials_table=True,
                    show_extended_specs=True,
                    show_notes=True
                )
                db.session.add(def_rep)
                db.session.commit()
    except Exception as e:
        print("Migration notice:", e)

    seed_pumps(app)

# ── Register Modular Blueprints ────────────────────────────────────────────────
app.register_blueprint(main_bp)
app.register_blueprint(pumps_bp)
app.register_blueprint(curves_bp)
app.register_blueprint(selection_bp)
app.register_blueprint(comparison_bp)
app.register_blueprint(reports_bp)


# Beginners Note: Register url_for alias resolver so templates calling url_for('pump_data')
# automatically resolve to blueprint endpoints (e.g. pumps.pump_data) seamlessly.
def handle_url_build_error(error, endpoint, values):
    if '.' not in endpoint:
        from flask import url_for as flask_url_for
        for bp in ['main', 'pumps', 'curves', 'selection', 'comparison', 'reports']:
            target = f"{bp}.{endpoint}"
            if target in app.view_functions:
                return flask_url_for(target, **values)
    raise error

@app.route('/favicon.ico')
def favicon():
    return ('', 204)

app.url_build_error_handlers.append(handle_url_build_error)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
