"""
app.py — Main Flask application entry point.

Beginners Note: This file initializes Flask, configures the database connection,
runs auto-migrations, registers modular Flask Blueprints, and launches the server.
"""

import os
from flask import Flask
from models import db
from seed_data import seed_pumps
from routes import main_bp, pumps_bp, curves_bp, selection_bp, comparison_bp

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
            result = conn.execute(text("PRAGMA table_info(pumps)"))
            cols = [row[1] for row in result.fetchall()]
            axis_cols = [
                'axis_flow_min', 'axis_flow_max', 'axis_flow_major', 'axis_flow_minor',
                'axis_head_min', 'axis_head_max', 'axis_head_major', 'axis_head_minor',
                'axis_eff_min', 'axis_eff_max', 'axis_eff_major', 'axis_eff_minor',
                'axis_power_min', 'axis_power_max', 'axis_power_major', 'axis_power_minor',
                'axis_npsh_min', 'axis_npsh_max', 'axis_npsh_major', 'axis_npsh_minor',
            ]
            for col_name in ['curve_labels', 'curve_diameters', 'curve_colors', 'curve_modes',
                             'curve_units', 'curve_raw_tables', 'curve_coeffs',
                             'unit_q', 'unit_h', 'unit_npsh', 'unit_pow', 'unit_op_q', 'graph_custom_label_pos',
                             'head_curve_style', 'eff_curve_style', 'power_curve_style', 'npsh_curve_style', 'main_curve_style'] + axis_cols:
                if col_name not in cols:
                    if col_name in axis_cols:
                        col_type = "INTEGER" if col_name.endswith('_minor') else "REAL"
                        conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {col_name} {col_type} DEFAULT NULL"))
                    else:
                        if col_name == 'graph_custom_label_pos':
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
            for p_col, p_def in [('poly_order', 3), ('poly_order_hq', 3), ('poly_order_eff', 3), ('poly_order_npsh', 2), ('poly_order_pow', 2)]:
                if p_col not in cols:
                    conn.execute(text(f"ALTER TABLE pumps ADD COLUMN {p_col} INTEGER DEFAULT {p_def}"))
            for old_col in ['main_curve_label', 'main_curve_dia_mm', 'data_units']:
                if old_col in cols:
                    try:
                        conn.execute(text(f"ALTER TABLE pumps DROP COLUMN {old_col}"))
                    except Exception:
                        pass
            conn.commit()
    except Exception as e:
        print("Migration notice:", e)

    seed_pumps(app)

# ── Register Modular Blueprints ────────────────────────────────────────────────
app.register_blueprint(main_bp)
app.register_blueprint(pumps_bp)
app.register_blueprint(curves_bp)
app.register_blueprint(selection_bp)
app.register_blueprint(comparison_bp)


# Beginners Note: Register url_for alias resolver so templates calling url_for('pump_data')
# automatically resolve to blueprint endpoints (e.g. pumps.pump_data) seamlessly.
def handle_url_build_error(error, endpoint, values):
    if '.' not in endpoint:
        from flask import url_for as flask_url_for
        for bp in ['main', 'pumps', 'curves', 'selection', 'comparison']:
            target = f"{bp}.{endpoint}"
            if target in app.view_functions:
                return flask_url_for(target, **values)
    raise error

app.url_build_error_handlers.append(handle_url_build_error)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
