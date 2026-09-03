"""
app.py — Main Flask application entry point.

Beginners Note: This file initializes Flask, configures the database connection,
runs auto-migrations, registers modular Flask Blueprints, and launches the server.
"""

import os
import sys
import re
import json
from flask import Flask
from models import db, Organisation, Supplier, ReportConfig
from seed_data import seed_pumps
from routes import main_bp, pumps_bp, curves_bp, selection_bp, comparison_bp, reports_bp, organisations_bp, debug_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'pumps.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SESSION_SECRET', 'pump-dev-secret')

# Initialize database extension with Flask app
db.init_app(app)

# Expose helper builtins to Jinja templates
app.jinja_env.globals['getattr'] = getattr

# ── Database Creation & Auto-Migration ─────────────────────────────────────────
with app.app_context():
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # 0. Rename suppliers table to organisations if suppliers exists and organisations does not
            table_res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            existing_tables = [row[0] for row in table_res]
            if 'suppliers' in existing_tables and 'organisations' not in existing_tables:
                conn.execute(text("ALTER TABLE suppliers RENAME TO organisations"))
    except Exception as e:
        print("Table rename notice:", e)

    db.create_all()

    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # 0b. Organisations table schema migrations
            org_res = conn.execute(text("PRAGMA table_info(organisations)"))
            org_cols = [row[1] for row in org_res.fetchall()]
            if 'allowed_view_org_ids' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN allowed_view_org_ids VARCHAR(255) DEFAULT ''"))
            if 'catalogue_report_ids' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN catalogue_report_ids VARCHAR(255) DEFAULT ''"))
            if 'default_unit_flow' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN default_unit_flow VARCHAR(10) DEFAULT 'm3h'"))
            if 'default_unit_head' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN default_unit_head VARCHAR(10) DEFAULT 'm'"))
            if 'default_unit_power' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN default_unit_power VARCHAR(10) DEFAULT 'kw'"))
            if 'default_unit_npsh' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN default_unit_npsh VARCHAR(10) DEFAULT 'm'"))
            if 'primary_color' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN primary_color VARCHAR(20) DEFAULT '#1e3a8a'"))
            if 'notes' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN notes TEXT DEFAULT ''"))
            if 'graph_styles_json' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN graph_styles_json TEXT DEFAULT '{}'"))
            if 'pump_details_template' not in org_cols:
                conn.execute(text("ALTER TABLE organisations ADD COLUMN pump_details_template VARCHAR(255) DEFAULT 'details/default_pump_details.html'"))
            for i in range(1, 31):
                col_name = f'PumpAttributeName{i}'
                if col_name not in org_cols:
                    conn.execute(text(f"ALTER TABLE organisations ADD COLUMN {col_name} VARCHAR(100) DEFAULT ''"))
                col_enabled = f'PumpAttributeEnabled{i}'
                if col_enabled not in org_cols:
                    conn.execute(text(f"ALTER TABLE organisations ADD COLUMN {col_enabled} INTEGER DEFAULT 1"))

            # 1. Reports table schema migrations
            rep_res = conn.execute(text("PRAGMA table_info(reports)"))
            rep_cols = [row[1] for row in rep_res.fetchall()]
            if 'organisation_id' not in rep_cols:
                if 'supplier_id' in rep_cols:
                    conn.execute(text("ALTER TABLE reports ADD COLUMN organisation_id INTEGER"))
                    conn.execute(text("UPDATE reports SET organisation_id = supplier_id WHERE organisation_id IS NULL"))
                else:
                    conn.execute(text("ALTER TABLE reports ADD COLUMN organisation_id INTEGER DEFAULT 2"))
            if 'report_name' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN report_name VARCHAR(100) DEFAULT 'standard'"))
            if 'curve_display_mode' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN curve_display_mode VARCHAR(20) DEFAULT 'all'"))
            if 'show_rated_curve' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN show_rated_curve INTEGER DEFAULT 1"))
            if 'report_type' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN report_type VARCHAR(100) DEFAULT 'Technical Datasheet'"))
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
            if 'legend_mode' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN legend_mode VARCHAR(30) DEFAULT 'pump_default'"))
            for rep_overlay in ['show_rpm_overlay', 'show_dia_overlay']:
                if rep_overlay not in rep_cols:
                    conn.execute(text(f"ALTER TABLE reports ADD COLUMN {rep_overlay} INTEGER DEFAULT 0"))
            if 'graph_area_top' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN graph_area_top VARCHAR(50) DEFAULT '4px'"))
            if 'graph_area_left' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN graph_area_left VARCHAR(50) DEFAULT '0px'"))
            if 'graph_area_width' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN graph_area_width VARCHAR(50) DEFAULT '100%'"))
            if 'graph_area_height' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN graph_area_height VARCHAR(50) DEFAULT 'auto'"))
            if 'graph_order' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN graph_order VARCHAR(100) DEFAULT 'hq,eta,pow,npsh'"))
            if 'graph_splits_json' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN graph_splits_json TEXT DEFAULT '{\"1\":[100],\"2\":[55,45],\"3\":[40,30,30],\"4\":[30,25,25,20]}'"))

            # 2. Pumps table schema migrations
            result = conn.execute(text("PRAGMA table_info(pumps)"))
            cols = [row[1] for row in result.fetchall()]
            if 'organisation_id' not in cols:
                conn.execute(text("ALTER TABLE pumps ADD COLUMN organisation_id INTEGER DEFAULT 2"))
            conn.execute(text("UPDATE pumps SET organisation_id = 2 WHERE organisation_id IS NULL"))
            if 'catalogue_report_ids' not in cols:
                conn.execute(text("ALTER TABLE pumps ADD COLUMN catalogue_report_ids VARCHAR(255) DEFAULT 'all'"))
            conn.execute(text("UPDATE pumps SET catalogue_report_ids = 'all' WHERE catalogue_report_ids IS NULL OR catalogue_report_ids = ''"))
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

            for i in range(1, 31):
                col_attr = f'PumpAttribute{i}'
                if col_attr not in cols:
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {col_attr} TEXT DEFAULT ''"))
            # Auto-migrate reports table columns
            rep_cols = [c[1] for c in conn.execute(text("PRAGMA table_info(reports)")).fetchall()]
            if 'label_format' not in rep_cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN label_format VARCHAR(20) DEFAULT 'auto'"))

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
                conn.execute(text("UPDATE pumps SET npsh_c0 = 0.0 WHERE npsh_c0 = 1.0 AND npsh_c1 = 0.0 AND npsh_c2 = 0.0 AND npsh_c3 = 0.0 AND npsh_c4 = 0.0 AND npsh_c5 = 0.0"))

                # Migrate legacy impeller_diameters into graph_rpm_values / graph_dia_overlay_values and clear impeller_diameters column
                imp_rows = conn.execute(text("SELECT id, family_type, impeller_diameters, graph_rpm_values, graph_dia_overlay_values FROM pumps WHERE impeller_diameters IS NOT NULL AND impeller_diameters != ''")).fetchall()
                for r_row in imp_rows:
                    pid, fam_t, imp_str, rpm_v, dia_v = r_row[0], r_row[1], r_row[2], r_row[3], r_row[4]
                    clean_s = imp_str
                    if clean_s.startswith('['):
                        try:
                            clean_s = ';'.join(str(x) for x in json.loads(clean_s))
                        except Exception:
                            pass
                    clean_s = re.sub(r'[,;\s]+', ';', clean_s.strip())
                    if fam_t == 'variable_speed':
                        if not rpm_v and clean_s:
                            conn.execute(text("UPDATE pumps SET graph_rpm_values = :val, graph_show_rpm_overlay = 1 WHERE id = :pid"), {"val": clean_s, "pid": pid})
                    else:
                        if not dia_v and clean_s:
                            conn.execute(text("UPDATE pumps SET graph_dia_overlay_values = :val, graph_show_dia_overlay = 1 WHERE id = :pid"), {"val": clean_s, "pid": pid})
                conn.execute(text("UPDATE pumps SET impeller_diameters = ''"))
            except Exception as e:
                print("Pump data cleanup notice:", e)

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

            # Ensure Lytrose Engineering (ID = 2) exists as active working organisation
            lytrose = Organisation.query.get(2)
            if not lytrose:
                lytrose = Organisation(
                    id=2,
                    name="Lytrose Engineering",
                    contact_email="sales@lytrose.co.za",
                    phone="",
                    website="",
                    address="",
                    allowed_view_org_ids="all",
                    default_unit_flow="m3h",
                    default_unit_head="m",
                    default_unit_power="kw",
                    default_unit_npsh="m",
                    primary_color="#1e3a8a"
                )
                db.session.add(lytrose)
                db.session.commit()

            # Seed default report configuration if table is empty
            if ReportConfig.query.count() == 0:
                def_org = Organisation.query.get(2) or Organisation.query.first()
                def_rep = ReportConfig(
                    organisation_id=def_org.id if def_org else None,
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
app.register_blueprint(organisations_bp)
app.register_blueprint(debug_bp)


# Beginners Note: Register url_for alias resolver so templates calling url_for('pump_data')
# automatically resolve to blueprint endpoints (e.g. pumps.pump_data) seamlessly.
def handle_url_build_error(error, endpoint, values):
    if '.' not in endpoint:
        from flask import url_for as flask_url_for
        for bp in ['main', 'pumps', 'curves', 'selection', 'comparison', 'reports', 'organisations', 'debug']:
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
    # Beginners Note: Werkzeug's reloader restarts via sys.exit(3), which debugpy / VS Code intercepts
    # as an unhandled SystemExit: 3 exception. We set use_reloader=False so the debugger runs cleanly.
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
