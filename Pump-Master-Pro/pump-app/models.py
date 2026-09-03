from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json
import re

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


def sanitize_hex_color(val, fallback='#3fb950'):
    if not val or not isinstance(val, str):
        return fallback
    val = val.strip()
    if ';' in val:
        parts = val.split(';')
        for p in parts:
            p_strip = p.strip()
            if p_strip.startswith('#'):
                val = p_strip
                break
    val = val.strip()
    if val.startswith('#') and len(val) in (4, 7):
        return val
    elif not val.startswith('#') and len(val) in (3, 6):
        return '#' + val
    return fallback



class Pump(db.Model):
    __tablename__ = 'pumps'

    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'), nullable=True, default=2)
    name = db.Column(db.String(100), nullable=False)
    manufacturer = db.Column(db.String(100), default='')
    model_number = db.Column(db.String(100), default='')
    size = db.Column(db.String(50), default='')
    speed_rpm = db.Column(db.Float, default=1450.0)
    impeller_dia_mm = db.Column(db.Float, default=300.0)

    # Specified report IDs enabled specifically for this pump record (comma-separated ReportConfig IDs or 'all')
    catalogue_report_ids = db.Column(db.String(255), default='all')

    # Test Basis / Family Type: 'trimmed_impeller' (constant speed) or 'variable_speed' (constant diameter)
    family_type = db.Column(db.String(50), default='trimmed_impeller')

    # Comma/JSON list of available impeller diameters (mm), largest first
    impeller_diameters = db.Column(db.Text, default='')

    # H-Q polynomial: H = hq_a0 + hq_a1*Q + hq_a2*Q^2 + hq_a3*Q^3 + hq_a4*Q^4 + hq_a5*Q^5
    hq_a0 = db.Column(db.Float, nullable=False)
    hq_a1 = db.Column(db.Float, default=0.0)
    hq_a2 = db.Column(db.Float, default=0.0)
    hq_a3 = db.Column(db.Float, default=0.0)
    hq_a4 = db.Column(db.Float, default=0.0)
    hq_a5 = db.Column(db.Float, default=0.0)

    # Efficiency polynomial: η(%) = eff_b0 + eff_b1*Q + eff_b2*Q^2 + eff_b3*Q^3 + eff_b4*Q^4 + eff_b5*Q^5
    eff_b0 = db.Column(db.Float, default=0.0)
    eff_b1 = db.Column(db.Float, default=0.0)
    eff_b2 = db.Column(db.Float, default=0.0)
    eff_b3 = db.Column(db.Float, default=0.0)
    eff_b4 = db.Column(db.Float, default=0.0)
    eff_b5 = db.Column(db.Float, default=0.0)

    # NPSH polynomial: NPSHr (m) = npsh_c0 + npsh_c1*Q + npsh_c2*Q^2 + npsh_c3*Q^3 + npsh_c4*Q^4 + npsh_c5*Q^5
    npsh_c0 = db.Column(db.Float, default=0.0)
    npsh_c1 = db.Column(db.Float, default=0.0)
    npsh_c2 = db.Column(db.Float, default=0.0)
    npsh_c3 = db.Column(db.Float, default=0.0)
    npsh_c4 = db.Column(db.Float, default=0.0)
    npsh_c5 = db.Column(db.Float, default=0.0)

    # Power polynomial: P (kW) = pow_p0 + pow_p1*Q + pow_p2*Q^2 + pow_p3*Q^3 + pow_p4*Q^4 + pow_p5*Q^5
    pow_p0 = db.Column(db.Float, default=0.0)
    pow_p1 = db.Column(db.Float, default=0.0)
    pow_p2 = db.Column(db.Float, default=0.0)
    pow_p3 = db.Column(db.Float, default=0.0)
    pow_p4 = db.Column(db.Float, default=0.0)
    pow_p5 = db.Column(db.Float, default=0.0)

    # Operating range (for the maximum impeller)
    q_min = db.Column(db.Float, default=0.0)
    q_max = db.Column(db.Float, nullable=False)
    q_bep = db.Column(db.Float, default=0.0)

    # Slurry derating factors (Warman method)
    hr = db.Column(db.Float, default=1.0)
    qr = db.Column(db.Float, default=1.0)
    er = db.Column(db.Float, default=1.0)

    pump_type = db.Column(db.String(50), default='centrifugal')
    application = db.Column(db.String(100), default='')
    notes = db.Column(db.Text, default='')

    # JSON array of extra manually-defined curves:
    extra_curves_json = db.Column(db.Text, default='')

    # Saved graph & display options stored as separate database columns
    graph_show_eff_iso      = db.Column(db.Boolean, default=True)
    graph_eff_levels        = db.Column(db.String(100), default='')
    graph_show_power_iso    = db.Column(db.Boolean, default=False)
    graph_power_levels      = db.Column(db.String(100), default='')
    graph_show_npsh_iso     = db.Column(db.Boolean, default=False)
    graph_npsh_levels       = db.Column(db.String(100), default='')
    graph_show_npsh_curve   = db.Column(db.Boolean, default=False)
    graph_npsh_yaxis        = db.Column(db.String(20), default='y2')
    graph_show_speed_lines  = db.Column(db.Boolean, default=False)
    graph_speed_line_values = db.Column(db.String(100), default='')
    # New: explicit RPM and Diameter overlay fields
    graph_show_rpm_overlay  = db.Column(db.Boolean, default=False)
    graph_rpm_values        = db.Column(db.String(100), default='')
    graph_show_dia_overlay  = db.Column(db.Boolean, default=False)
    graph_dia_overlay_values = db.Column(db.String(100), default='')
    graph_show_hq           = db.Column(db.Boolean, default=True)
    graph_show_other        = db.Column(db.Boolean, default=True)
    graph_show_eff          = db.Column(db.Boolean, default=True)
    graph_show_power        = db.Column(db.Boolean, default=True)
    graph_show_npsh         = db.Column(db.Boolean, default=True)
    graph_combine_eff_power = db.Column(db.Boolean, default=True)
    graph_trim_model        = db.Column(db.String(20), default='fit')
    graph_trim_penalty      = db.Column(db.Float, nullable=True)

    # Selection Engine Flags
    selection_allow_fixed_speed = db.Column(db.Boolean, default=True)
    selection_allow_vsd = db.Column(db.Boolean, default=True)

    # Dimensional Data
    graph_options_json      = db.Column(db.Text, default='')
    graph_custom_label_pos  = db.Column(db.Text, default='{}')

    # Delimited fields for curve metadata & performance tables
    # curve_labels: "Main;Curve 2;Curve 3"
    # curve_diameters: "228;mm|182;mm|300;in"
    # curve_colors: "#58a6ff;#3fb950"
    # curve_modes: "fit;fit"
    # curve_units: "m3h,m,m,kw|ls,m,m,kw"
    # curve_raw_tables: "q,h,eta,npsh,pow;...|q,h,..."
    # curve_coeffs: "hq_a0,a1,a2,a3,eff_b0,b1,b2,b3,npsh_c0,c1,c2,pow_p0,p1,p2,q_max,q_bep|..."
    curve_labels     = db.Column(db.Text, default='')
    curve_diameters  = db.Column(db.Text, default='')
    curve_colors     = db.Column(db.Text, default='')
    curve_modes      = db.Column(db.Text, default='')
    curve_units      = db.Column(db.Text, default='')
    curve_raw_tables = db.Column(db.Text, default='')
    curve_coeffs     = db.Column(db.Text, default='')

    # Unit preferences as separate columns (replaces data_units JSON)
    unit_q    = db.Column(db.String(20), default='m3h')
    unit_h    = db.Column(db.String(20), default='m')
    unit_npsh = db.Column(db.String(20), default='m')
    unit_pow  = db.Column(db.String(20), default='kw')
    unit_op_q = db.Column(db.String(20), default='m3h')

    # Extended Setup & Application Selection Specification Fields
    app_modules        = db.Column(db.Text, default='')  # Comma-separated app keys e.g. 'slurry,fire,borehole'
    impeller_material  = db.Column(db.String(100), default='')
    casing_material    = db.Column(db.String(100), default='')
    number_of_vanes    = db.Column(db.Integer, default=5)

    # Pipe Sizes & Mechanical Operating Limits with Selectable Units
    suction_size       = db.Column(db.String(50), default='')
    discharge_size     = db.Column(db.String(50), default='')
    unit_suction       = db.Column(db.String(20), default='mm')
    unit_discharge     = db.Column(db.String(20), default='mm')

    max_solid_size_mm  = db.Column(db.Float, default=0.0)
    unit_solid         = db.Column(db.String(20), default='mm')

    max_pressure_bar   = db.Column(db.Float, default=0.0)
    unit_pressure      = db.Column(db.String(20), default='bar')

    max_temp_c         = db.Column(db.Float, default=0.0)
    unit_temp          = db.Column(db.String(20), default='degC')

    seal_type          = db.Column(db.String(100), default='')
    drive_type         = db.Column(db.String(100), default='')

    # Special Hydraulic & Construction Design Considerations
    is_multistage      = db.Column(db.Boolean, default=False)
    num_stages         = db.Column(db.Integer, default=1)
    is_double_suction  = db.Column(db.Boolean, default=False)
    is_angle_trim      = db.Column(db.Boolean, default=False)
    is_self_priming    = db.Column(db.Boolean, default=False)
    is_non_clog        = db.Column(db.Boolean, default=False)
    has_inducer        = db.Column(db.Boolean, default=False)

    # Flow Control, Throttling & Minimum Flow Orifice Specifications
    is_throttling_capable  = db.Column(db.Boolean, default=True)
    min_flow_m3h           = db.Column(db.Float, default=0.0)
    max_orifice_dia_mm     = db.Column(db.Float, default=0.0)
    impeller_eye_area_cm2  = db.Column(db.Float, default=0.0)
    vfd_min_hz             = db.Column(db.Float, default=30.0)
    vfd_max_hz             = db.Column(db.Float, default=60.0)

    # Custom Organisation Pump Attributes (PumpAttribute1 to PumpAttribute30)
    PumpAttribute1  = db.Column(db.String(255), default='')
    PumpAttribute2  = db.Column(db.String(255), default='')
    PumpAttribute3  = db.Column(db.String(255), default='')
    PumpAttribute4  = db.Column(db.String(255), default='')
    PumpAttribute5  = db.Column(db.String(255), default='')
    PumpAttribute6  = db.Column(db.String(255), default='')
    PumpAttribute7  = db.Column(db.String(255), default='')
    PumpAttribute8  = db.Column(db.String(255), default='')
    PumpAttribute9  = db.Column(db.String(255), default='')
    PumpAttribute10 = db.Column(db.String(255), default='')
    PumpAttribute11 = db.Column(db.String(255), default='')
    PumpAttribute12 = db.Column(db.String(255), default='')
    PumpAttribute13 = db.Column(db.String(255), default='')
    PumpAttribute14 = db.Column(db.String(255), default='')
    PumpAttribute15 = db.Column(db.String(255), default='')
    PumpAttribute16 = db.Column(db.String(255), default='')
    PumpAttribute17 = db.Column(db.String(255), default='')
    PumpAttribute18 = db.Column(db.String(255), default='')
    PumpAttribute19 = db.Column(db.String(255), default='')
    PumpAttribute20 = db.Column(db.String(255), default='')
    PumpAttribute21 = db.Column(db.String(255), default='')
    PumpAttribute22 = db.Column(db.String(255), default='')
    PumpAttribute23 = db.Column(db.String(255), default='')
    PumpAttribute24 = db.Column(db.String(255), default='')
    PumpAttribute25 = db.Column(db.String(255), default='')
    PumpAttribute26 = db.Column(db.String(255), default='')
    PumpAttribute27 = db.Column(db.String(255), default='')
    PumpAttribute28 = db.Column(db.String(255), default='')
    PumpAttribute29 = db.Column(db.String(255), default='')
    PumpAttribute30 = db.Column(db.String(255), default='')

    # Graph curve styles stored as 'color;weight,lineStyle' format
    head_curve_style  = db.Column(db.String(50), default='#58a6ff;2.0,solid')
    eff_curve_style   = db.Column(db.String(50), default='#3fb950;1.5,dot')
    power_curve_style = db.Column(db.String(50), default='#f85149;1.5,longdash')
    npsh_curve_style  = db.Column(db.String(50), default='#39d3c0;1.5,dashdot')
    main_curve_style  = db.Column(db.String(50), default='graph')

    # ── Custom Axis Scaling Settings ──────────────────────────────────────────────
    # Beginners Note: These 20 columns store the custom graph axes bounds and division intervals.
    # Each axis (Flow, Head, Efficiency, Power, NPSH) has 4 distinct properties:
    #   1. min: lower numerical range boundary
    #   2. max: upper numerical range boundary
    #   3. major: number of major division steps/ticks
    #   4. minor: number of minor subticks per major division
    # Setting a field to None/NULL falls back to automatic scaling by Plotly.

    # Flow (Q) Axis (x-axis)
    axis_flow_min   = db.Column(db.Float, nullable=True)
    axis_flow_max   = db.Column(db.Float, nullable=True)
    axis_flow_major = db.Column(db.Float, nullable=True)
    axis_flow_minor = db.Column(db.Integer, nullable=True)

    # Head (H) Axis (main y-axis)
    axis_head_min   = db.Column(db.Float, nullable=True)
    axis_head_max   = db.Column(db.Float, nullable=True)
    axis_head_major = db.Column(db.Float, nullable=True)
    axis_head_minor = db.Column(db.Integer, nullable=True)

    # Efficiency (η) Axis
    axis_eff_min   = db.Column(db.Float, nullable=True)
    axis_eff_max   = db.Column(db.Float, nullable=True)
    axis_eff_major = db.Column(db.Float, nullable=True)
    axis_eff_minor = db.Column(db.Integer, nullable=True)

    # Power (P) Axis
    axis_power_min   = db.Column(db.Float, nullable=True)
    axis_power_max   = db.Column(db.Float, nullable=True)
    axis_power_major = db.Column(db.Float, nullable=True)
    axis_power_minor = db.Column(db.Integer, nullable=True)

    # NPSH Axis
    axis_npsh_min   = db.Column(db.Float, nullable=True)
    axis_npsh_max   = db.Column(db.Float, nullable=True)
    axis_npsh_major = db.Column(db.Float, nullable=True)
    axis_npsh_minor = db.Column(db.Integer, nullable=True)

    # Beginners Note: Independent polynomial fitting degrees per curve (1 to 5)
    poly_order = db.Column(db.Integer, default=3)      # Global fallback order
    poly_order_hq = db.Column(db.Integer, default=3)   # Head H-Q polynomial degree (default 3 - Cubic)
    poly_order_eff = db.Column(db.Integer, default=3)  # Efficiency polynomial degree (default 3 - Cubic)
    poly_order_npsh = db.Column(db.Integer, default=2) # NPSHr polynomial degree (default 2 - Quadratic)
    poly_order_pow = db.Column(db.Integer, default=2)  # Power polynomial degree (default 2 - Quadratic)

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_curve_labels_list(self):
        """Return list of labels for loaded curves."""
        raw_labels = (self.curve_labels or '').strip()
        if not raw_labels:
            labels = ['Curve 1']
            for idx, c in enumerate(self.get_extra_curves()):
                labels.append(c.get('label') or f'Curve {idx + 2}')
            return labels
        return [x.strip() for x in raw_labels.split(';')]

    def get_curve_diameters_list(self):
        """Return list of dicts for loaded curves: [{'diameter': val, 'unit': unit, 'dia_mm': mm_val}, ...]"""
        raw_dias = (self.curve_diameters or '').strip()

        if not raw_dias:
            items = []
            main_d = self.impeller_dia_mm
            if main_d:
                items.append(f"{main_d};mm")
            for c in self.get_extra_curves():
                d_val = c.get('diameter')
                if d_val is not None and str(d_val).strip() != '':
                    u_val = str(c.get('unit_dia', 'mm')).strip()
                    items.append(f"{str(d_val).strip()};{u_val}")
            raw_dias = '|'.join(items)

        if not raw_dias:
            return []

        entries = [x.strip() for x in raw_dias.split('|') if x.strip()]
        result = []
        for entry in entries:
            parts = [p.strip() for p in entry.split(';')]
            if not parts:
                continue
            try:
                dia_str = parts[0]
                d_val = float(dia_str) if dia_str else None
                unit = parts[1] if len(parts) > 1 else 'mm'
                if d_val is not None:
                    if unit == 'in':
                        d_mm = d_val * 25.4
                    elif unit == 'm':
                        d_mm = d_val * 1000.0
                    else:
                        d_mm = d_val
                else:
                    d_mm = None
                result.append({'diameter': d_val, 'unit': unit, 'dia_mm': d_mm})
            except ValueError:
                pass
        return result

    def sync_curve_fields(self, extra_curves_data=None, raw_main_data=None):
        """Build separated curve fields from main curve + extra curves."""
        labels = []
        dias_units = []
        colors = []
        modes = []
        units = []
        raw_tables = []
        coeffs_list = []

        # ── Main curve (Index 0) ──
        m_lbl = 'Curve 1'
        if self.curve_labels:
            lbl_parts = [x.strip() for x in self.curve_labels.split(';') if x.strip()]
            if lbl_parts:
                m_lbl = lbl_parts[0]
        main_d = ''
        main_dia_unit = 'mm'
        if self.curve_diameters:
            first_dia = self.curve_diameters.split('|')[0]
            parts = first_dia.split(';')
            if parts and parts[0].strip():
                main_d = parts[0].strip()
            if len(parts) > 1:
                main_dia_unit = parts[1].strip()
        if not main_d and self.impeller_dia_mm:
            main_d = str(self.impeller_dia_mm)

        labels.append(m_lbl)
        dias_units.append(f"{main_d};{main_dia_unit}")
        colors.append('#58a6ff')
        modes.append('fit')

        du = self._get_data_units() if hasattr(self, '_get_data_units') else {'q': getattr(self, 'unit_q', 'm3h') or 'm3h', 'h': getattr(self, 'unit_h', 'm') or 'm', 'npsh': getattr(self, 'unit_npsh', 'm') or 'm', 'pow': getattr(self, 'unit_pow', 'kw') or 'kw'}
        units.append(f"{du.get('q','m3h')},{du.get('h','m')},{du.get('npsh','m')},{du.get('pow','kw')}")

        # Main raw table
        main_raw = raw_main_data if raw_main_data is not None else self.get_raw_table()
        if main_raw and isinstance(main_raw, list):
            rows_str = ';'.join([','.join([str(x) for x in r]) for r in main_raw])
            raw_tables.append(rows_str)
        else:
            raw_tables.append('')

        # Main coeffs
        m_c = f"{self.hq_a0 or 0},{self.hq_a1 or 0},{self.hq_a2 or 0},{self.hq_a3 or 0}," \
              f"{self.eff_b0 or 0},{self.eff_b1 or 0},{self.eff_b2 or 0},{self.eff_b3 or 0}," \
              f"{self.npsh_c0 or 0},{self.npsh_c1 or 0},{self.npsh_c2 or 0}," \
              f"{self.pow_p0 or 0},{self.pow_p1 or 0},{self.pow_p2 or 0}," \
              f"{self.q_max or 0},{self.q_bep or 0}"
        coeffs_list.append(m_c)

        # ── Extra curves (Index 1..) ──
        extra_list = extra_curves_data
        if extra_list is None:
            raw = (self.extra_curves_json or '').strip()
            extra_list = []
            if raw:
                try: extra_list = json.loads(raw)
                except Exception: pass
        self.extra_curves_json = ''

        for idx, c in enumerate(extra_list):
            lbl = c.get('label') or f'Curve {idx + 2}'
            labels.append(lbl)

            d_val = c.get('diameter')
            if d_val is not None and str(d_val).strip() != '':
                u_val = str(c.get('unit_dia', 'mm')).strip()
                dias_units.append(f"{str(d_val).strip()};{u_val}")
            else:
                dias_units.append(';mm')

            colors.append(sanitize_hex_color(c.get('color'), '#3fb950'))
            modes.append(c.get('curve_mode', 'fit'))

            uq = c.get('unit_q', 'm3h')
            uh = c.get('unit_h', 'm')
            unpsh = c.get('unit_npsh', 'm')
            upow = c.get('unit_pow', 'kw')
            units.append(f"{uq},{uh},{unpsh},{upow}")

            c_raw = c.get('raw_table', [])
            if c_raw and isinstance(c_raw, list):
                rows_str = ';'.join([','.join([str(x) for x in r]) for r in c_raw])
                raw_tables.append(rows_str)
            else:
                raw_tables.append('')

            c_coeffs = f"{c.get('hq_a0',0)},{c.get('hq_a1',0)},{c.get('hq_a2',0)},{c.get('hq_a3',0)}," \
                       f"{c.get('eff_b0',0)},{c.get('eff_b1',0)},{c.get('eff_b2',0)},{c.get('eff_b3',0)}," \
                       f"{c.get('npsh_c0',0)},{c.get('npsh_c1',0)},{c.get('npsh_c2',0)}," \
                       f"{c.get('pow_p0',0)},{c.get('pow_p1',0)},{c.get('pow_p2',0)}," \
                       f"{c.get('q_max',0)},{c.get('q_bep',0)}"
            coeffs_list.append(c_coeffs)

        if labels: self.curve_labels = ';'.join(labels)
        if dias_units: self.curve_diameters = '|'.join(dias_units)
        if colors: self.curve_colors = ';'.join(colors)
        if modes: self.curve_modes = ';'.join(modes)
        if units: self.curve_units = '|'.join(units)
        if raw_tables: self.curve_raw_tables = '|'.join(raw_tables)
        if coeffs_list: self.curve_coeffs = '|'.join(coeffs_list)

        if extra_list and len(extra_list) > 0:
            self.extra_curves_json = json.dumps(extra_list)

    def get_diameters(self):
        """Return sorted list of impeller diameters or RPM speeds (descending)."""
        fam_t = getattr(self, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
        if fam_t == 'variable_speed':
            raw = (getattr(self, 'graph_rpm_values', None) or getattr(self, 'graph_speed_line_values', None) or '').strip()
        else:
            raw = (getattr(self, 'graph_dia_overlay_values', None) or getattr(self, 'curve_diameters', None) or '').strip()

        dias = []
        if raw:
            try:
                cleaned = re.sub(r'[\[\]"\'\s]+', '', raw)
                parts = [p.strip() for p in re.split(r'[,;\s]+', cleaned) if p.strip()]
                for p in parts:
                    val = float(p)
                    if fam_t != 'variable_speed' and val > 2500:
                        continue
                    dias.append(val)
            except Exception:
                pass

        if not dias:
            base_v = self.speed_rpm if fam_t == 'variable_speed' else self.impeller_dia_mm
            if base_v and base_v > 0:
                dias = [base_v]

        if fam_t != 'variable_speed':
            loaded = self.get_curve_diameters_list()
            for item in loaded:
                d_mm = item.get('dia_mm')
                if d_mm is not None and d_mm <= 2500:
                    if round(d_mm, 2) not in [round(x, 2) for x in dias]:
                        dias.append(round(d_mm, 2))

        if not dias:
            dias = [1000.0 if fam_t == 'variable_speed' else 300.0]

        return sorted(list(set(dias)), reverse=True)

    def get_raw_table(self):
        """Return raw performance table for main curve as list of rows."""
        raw_tbls = (self.curve_raw_tables or '').strip()
        if raw_tbls:
            tables = raw_tbls.split('|')
            if len(tables) > 0 and tables[0].strip():
                rows = []
                for r_str in tables[0].split(';'):
                    if r_str.strip():
                        rows.append([x.strip() for x in r_str.split(',')])
                return rows
        return []

    def get_extra_curves(self):
        """Return list of extra manually-defined curves."""
        if getattr(self, '_transient_extra_curves', None) is not None:
            res = self._transient_extra_curves
            for c in res:
                if isinstance(c, dict) and 'color' in c:
                    c['color'] = sanitize_hex_color(c['color'], '#3fb950')
            return res

        raw_json = (self.extra_curves_json or '').strip()
        if raw_json and raw_json != '[]' and raw_json != '""':
            try:
                curves = json.loads(raw_json)
                if isinstance(curves, list) and len(curves) > 0:
                    for c in curves:
                        if isinstance(c, dict) and 'color' in c:
                            c['color'] = sanitize_hex_color(c['color'], '#3fb950')
                    return curves
            except Exception:
                pass

        raw_labels = (self.curve_labels or '').strip()
        raw_dias   = (self.curve_diameters or '').strip()
        raw_colors = (self.curve_colors or '').strip()
        raw_modes  = (self.curve_modes or '').strip()
        raw_units  = (self.curve_units or '').strip()
        raw_tbls   = (self.curve_raw_tables or '').strip()
        raw_cfs    = (self.curve_coeffs or '').strip()

        if raw_labels or raw_dias or raw_colors or raw_tbls:
            lbl_items = [x.strip() for x in raw_labels.split(';')] if raw_labels else []
            d_items   = [x.strip() for x in raw_dias.split('|')] if raw_dias else []
            col_items = [x.strip() for x in raw_colors.split(';')] if raw_colors else []
            m_items   = [x.strip() for x in raw_modes.split(';')] if raw_modes else []
            u_items   = [x.strip() for x in raw_units.split('|')] if raw_units else []
            t_items   = raw_tbls.split('|') if raw_tbls else []
            c_items   = raw_cfs.split('|') if raw_cfs else []

            max_len = max(len(lbl_items), len(d_items), len(t_items), len(c_items))
            curves = []

            for loaded_idx in range(1, max_len):
                c = {}
                c['label'] = lbl_items[loaded_idx] if loaded_idx < len(lbl_items) else f'Curve {loaded_idx + 1}'

                if loaded_idx < len(d_items):
                    parts = [p.strip() for p in d_items[loaded_idx].split(';')]
                    if parts:
                        c['diameter'] = parts[0] if parts[0] else ''
                        if len(parts) > 1: c['unit_dia'] = parts[1] if parts[1] else 'mm'

                raw_col = col_items[loaded_idx] if loaded_idx < len(col_items) else '#3fb950'
                if raw_col.startswith('custom;') or raw_col.startswith('graph;'):
                    parts = raw_col.split(';')
                    c['style_mode'] = parts[0]
                    c['use_custom_style'] = (parts[0] == 'custom')
                    c['color'] = sanitize_hex_color(parts[1] if len(parts) > 1 else '#3fb950')
                    if len(parts) > 2:
                        sub = parts[2].split(',')
                        try: c['weight'] = float(sub[0])
                        except Exception: pass
                        if len(sub) > 1: c['style'] = sub[1]
                else:
                    c['color'] = sanitize_hex_color(raw_col)

                c['curve_mode'] = m_items[loaded_idx] if loaded_idx < len(m_items) else 'fit'

                if loaded_idx < len(u_items):
                    u_parts = [p.strip() for p in u_items[loaded_idx].split(',') if p.strip()]
                    if len(u_parts) >= 4:
                        c['unit_q'], c['unit_h'], c['unit_npsh'], c['unit_pow'] = u_parts[:4]

                if loaded_idx < len(t_items) and t_items[loaded_idx].strip():
                    r_list = []
                    for r_str in t_items[loaded_idx].split(';'):
                        if r_str.strip():
                            r_list.append([x.strip() for x in r_str.split(',')])
                    c['raw_table'] = r_list

                if loaded_idx < len(c_items) and c_items[loaded_idx].strip():
                    cf_vals = [float(x.strip()) for x in c_items[loaded_idx].split(',') if x.strip()]
                    if len(cf_vals) >= 16:
                        c['hq_a0'], c['hq_a1'], c['hq_a2'], c['hq_a3'] = cf_vals[0:4]
                        c['eff_b0'], c['eff_b1'], c['eff_b2'], c['eff_b3'] = cf_vals[4:8]
                        c['npsh_c0'], c['npsh_c1'], c['npsh_c2'] = cf_vals[8:11]
                        c['pow_p0'], c['pow_p1'], c['pow_p2'] = cf_vals[11:14]
                        c['q_max'], c['q_bep'] = cf_vals[14:16]

                curves.append(c)
            return curves

        raw = (self.extra_curves_json or '').strip()
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    def get_graph_options(self):
        """Return saved graph display options dictionary from individual database columns."""
        try:
            extra_opts = json.loads(self.graph_options_json or '{}')
        except Exception:
            extra_opts = {}
        return {
            'show_eff_iso': self.graph_show_eff_iso if self.graph_show_eff_iso is not None else True,
            'eff_levels': self.graph_eff_levels or '',
            'show_power_iso': bool(self.graph_show_power_iso),
            'power_levels': self.graph_power_levels or '',
            'show_npsh_iso': bool(self.graph_show_npsh_iso),
            'npsh_levels': self.graph_npsh_levels or '',
            'show_npsh_curve': bool(self.graph_show_npsh_curve),
            'npsh_yaxis': self.graph_npsh_yaxis or 'y2',
            'show_speed_lines': bool(self.graph_show_speed_lines),
            'speed_line_values': self.graph_speed_line_values or extra_opts.get('speed_line_values', ''),
            'show_rpm_overlay': bool(getattr(self, 'graph_show_rpm_overlay', False)),
            'rpm_values': getattr(self, 'graph_rpm_values', '') or '',
            'show_dia_overlay': bool(getattr(self, 'graph_show_dia_overlay', False)),
            'dia_overlay_values': getattr(self, 'graph_dia_overlay_values', '') or '',
            'show_hq': self.graph_show_hq if self.graph_show_hq is not None else True,
            'show_other': self.graph_show_other if self.graph_show_other is not None else True,
            'show_eff': self.graph_show_eff if self.graph_show_eff is not None else True,
            'show_power': self.graph_show_power if self.graph_show_power is not None else True,
            'show_npsh': self.graph_show_npsh if self.graph_show_npsh is not None else True,
            'combine_eff_power': self.graph_combine_eff_power if self.graph_combine_eff_power is not None else True,
            'trim_model': self.graph_trim_model or 'fit',
            'trim_penalty': self.graph_trim_penalty if getattr(self, 'graph_trim_penalty', None) is not None else extra_opts.get('trim_penalty'),
            'unit_max_imp': extra_opts.get('unit_max_imp', 'mm'),
            'graph_unit_q': extra_opts.get('graph_unit_q', ''),
            'graph_unit_h': extra_opts.get('graph_unit_h', ''),
            'graph_unit_npsh': extra_opts.get('graph_unit_npsh', ''),
            'graph_unit_pow': extra_opts.get('graph_unit_pow', ''),
            'legend_mode': extra_opts.get('legend_mode', 'each'),
            'label_format': extra_opts.get('label_format', 'percent'),
            'custom_label_pos': self.get_custom_label_pos()
        }

    def get_custom_label_pos(self):
        """Return parsed dictionary of custom dragged label coordinates."""
        if not self.graph_custom_label_pos:
            return {}
        try:
            val = json.loads(self.graph_custom_label_pos)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}

    def set_custom_label_pos(self, pos, overwrite=False):
        """Set or merge graph_custom_label_pos column from dict or JSON string."""
        if overwrite and (pos == {} or pos == '{}'):
            self.graph_custom_label_pos = '{}'
            return

        if isinstance(pos, str):
            try:
                pos = json.loads(pos)
            except Exception:
                return

        if isinstance(pos, dict) and pos:
            existing = self.get_custom_label_pos()
            existing.update(pos)
            self.graph_custom_label_pos = json.dumps(existing)

    def set_graph_options(self, opts):
        """Set individual database columns from an options dictionary."""
        if not isinstance(opts, dict):
            return
        if 'show_eff_iso' in opts: self.graph_show_eff_iso = bool(opts['show_eff_iso'])
        if 'eff_levels' in opts: self.graph_eff_levels = str(opts['eff_levels'])
        if 'show_power_iso' in opts: self.graph_show_power_iso = bool(opts['show_power_iso'])
        if 'power_levels' in opts: self.graph_power_levels = str(opts['power_levels'])
        if 'show_npsh_iso' in opts: self.graph_show_npsh_iso = bool(opts['show_npsh_iso'])
        if 'npsh_levels' in opts: self.graph_npsh_levels = str(opts['npsh_levels'])
        if 'show_npsh_curve' in opts: self.graph_show_npsh_curve = bool(opts['show_npsh_curve'])
        if 'npsh_yaxis' in opts: self.graph_npsh_yaxis = str(opts['npsh_yaxis'])
        if 'show_speed_lines' in opts: self.graph_show_speed_lines = bool(opts['show_speed_lines'])
        if 'speed_line_values' in opts: self.graph_speed_line_values = str(opts['speed_line_values'])

        if 'show_rpm_overlay' in opts: self.graph_show_rpm_overlay = bool(opts['show_rpm_overlay'])
        elif 'graph_show_rpm_overlay' in opts: self.graph_show_rpm_overlay = bool(opts['graph_show_rpm_overlay'])

        if 'rpm_values' in opts: self.graph_rpm_values = str(opts['rpm_values'])
        elif 'graph_rpm_values' in opts: self.graph_rpm_values = str(opts['graph_rpm_values'])

        if 'show_dia_overlay' in opts: self.graph_show_dia_overlay = bool(opts['show_dia_overlay'])
        elif 'graph_show_dia_overlay' in opts: self.graph_show_dia_overlay = bool(opts['graph_show_dia_overlay'])

        if 'dia_overlay_values' in opts: self.graph_dia_overlay_values = str(opts['dia_overlay_values'])
        elif 'graph_dia_overlay_values' in opts: self.graph_dia_overlay_values = str(opts['graph_dia_overlay_values'])
        if 'show_hq' in opts: self.graph_show_hq = bool(opts['show_hq'])
        if 'show_other' in opts: self.graph_show_other = bool(opts['show_other'])
        if 'show_eff' in opts: self.graph_show_eff = bool(opts['show_eff'])
        if 'show_power' in opts: self.graph_show_power = bool(opts['show_power'])
        if 'show_npsh' in opts: self.graph_show_npsh = bool(opts['show_npsh'])
        if 'combine_eff_power' in opts: self.graph_combine_eff_power = bool(opts['combine_eff_power'])
        if 'trim_model' in opts: self.graph_trim_model = str(opts['trim_model'])
        if 'trim_penalty' in opts:
            tp_val = opts['trim_penalty']
            if tp_val is None or str(tp_val).strip() == '':
                self.graph_trim_penalty = None
            else:
                try: self.graph_trim_penalty = float(tp_val)
                except Exception: self.graph_trim_penalty = None
        if 'reset_label_pos' in opts and opts['reset_label_pos']:
            self.graph_custom_label_pos = '{}'
        elif 'custom_label_pos' in opts:
            self.set_custom_label_pos(opts['custom_label_pos'])
        
        try:
            extra_opts = json.loads(self.graph_options_json or '{}')
        except Exception:
            extra_opts = {}

        if 'unit_max_imp' in opts: extra_opts['unit_max_imp'] = opts['unit_max_imp']
        if 'graph_unit_q' in opts: extra_opts['graph_unit_q'] = opts['graph_unit_q']
        if 'graph_unit_h' in opts: extra_opts['graph_unit_h'] = opts['graph_unit_h']
        if 'graph_unit_npsh' in opts: extra_opts['graph_unit_npsh'] = opts['graph_unit_npsh']
        if 'graph_unit_pow' in opts: extra_opts['graph_unit_pow'] = opts['graph_unit_pow']
        if 'legend_mode' in opts: extra_opts['legend_mode'] = opts['legend_mode']
        if 'label_format' in opts: extra_opts['label_format'] = opts['label_format']
        extra_opts['custom_label_pos'] = self.get_custom_label_pos()
        self.graph_options_json = json.dumps(extra_opts)

    def _get_data_units(self):
        """Return input-unit preferences dict derived from curve_units (index 0 for main curve)."""
        defaults = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw', 'op_q': 'm3h'}
        if self.curve_units:
            u_entries = [x.strip() for x in self.curve_units.split('|') if x.strip()]
            if u_entries:
                u_parts = [p.strip() for p in u_entries[0].split(',') if p.strip()]
                if len(u_parts) >= 4:
                    defaults['q'] = u_parts[0]
                    defaults['h'] = u_parts[1]
                    defaults['npsh'] = u_parts[2]
                    defaults['pow'] = u_parts[3]
        if self.unit_op_q:
            defaults['op_q'] = self.unit_op_q
        opts = self.get_graph_options()
        defaults['max_imp'] = str(opts.get('unit_max_imp', 'mm'))
        defaults['graph_q'] = str(opts.get('graph_unit_q', defaults['q']))
        defaults['graph_h'] = str(opts.get('graph_unit_h', defaults['h']))
        defaults['graph_npsh'] = str(opts.get('graph_unit_npsh', defaults['npsh']))
        defaults['graph_pow'] = str(opts.get('graph_unit_pow', defaults['pow']))
        return defaults

    @property
    def data_units_dict(self):
        """Template-friendly alias for _get_data_units()."""
        return self._get_data_units()

    def has_power_poly(self):
        """True when a stored power polynomial is available."""
        return bool(
            getattr(self, 'pow_p0', 0) or
            getattr(self, 'pow_p1', 0) or
            getattr(self, 'pow_p2', 0) or
            getattr(self, 'pow_p3', 0) or
            getattr(self, 'pow_p4', 0) or
            getattr(self, 'pow_p5', 0)
        )

    def has_npsh_poly(self):
        """True when valid stored non-zero NPSH polynomial coefficients are available."""
        return any(abs(getattr(self, f'npsh_c{i}', 0.0) or 0.0) > 1e-6 for i in range(6))

    def to_dict(self):
        return {
            'id': self.id,
            'organisation_id': getattr(self, 'organisation_id', 2) or 2,
            'organisation_name': self.organisation.name if getattr(self, 'organisation', None) else '',
            'name': self.name,
            'manufacturer': self.manufacturer,
            'model_number': self.model_number,
            'size': self.size,
            'speed_rpm': self.speed_rpm,
            'impeller_dia_mm': self.impeller_dia_mm,
            'impeller_diameters': '',
            'hq_a0': getattr(self, 'hq_a0', 0.0), 'hq_a1': getattr(self, 'hq_a1', 0.0),
            'hq_a2': getattr(self, 'hq_a2', 0.0), 'hq_a3': getattr(self, 'hq_a3', 0.0),
            'hq_a4': getattr(self, 'hq_a4', 0.0), 'hq_a5': getattr(self, 'hq_a5', 0.0),
            'eff_b0': getattr(self, 'eff_b0', 0.0), 'eff_b1': getattr(self, 'eff_b1', 0.0),
            'eff_b2': getattr(self, 'eff_b2', 0.0), 'eff_b3': getattr(self, 'eff_b3', 0.0),
            'eff_b4': getattr(self, 'eff_b4', 0.0), 'eff_b5': getattr(self, 'eff_b5', 0.0),
            'npsh_c0': getattr(self, 'npsh_c0', 0.0), 'npsh_c1': getattr(self, 'npsh_c1', 0.0),
            'npsh_c2': getattr(self, 'npsh_c2', 0.0), 'npsh_c3': getattr(self, 'npsh_c3', 0.0),
            'npsh_c4': getattr(self, 'npsh_c4', 0.0), 'npsh_c5': getattr(self, 'npsh_c5', 0.0),
            'pow_p0': getattr(self, 'pow_p0', 0.0), 'pow_p1': getattr(self, 'pow_p1', 0.0),
            'pow_p2': getattr(self, 'pow_p2', 0.0), 'pow_p3': getattr(self, 'pow_p3', 0.0),
            'pow_p4': getattr(self, 'pow_p4', 0.0), 'pow_p5': getattr(self, 'pow_p5', 0.0),
            'q_min': self.q_min, 'q_max': self.q_max, 'q_bep': self.q_bep,
            'hr': self.hr, 'qr': self.qr, 'er': self.er,
            'pump_type': self.pump_type,
            'family_type': self.family_type or 'trimmed_impeller',
            'application': self.application,
            'notes': self.notes,
            'app_modules': self.app_modules or '',
            'impeller_material': self.impeller_material or '',
            'casing_material': self.casing_material or '',
            'number_of_vanes': self.number_of_vanes or 5,
            'suction_size': self.suction_size or '',
            'discharge_size': self.discharge_size or '',
            'unit_suction': self.unit_suction or 'mm',
            'unit_discharge': self.unit_discharge or 'mm',
            'max_solid_size_mm': self.max_solid_size_mm or 0.0,
            'unit_solid': self.unit_solid or 'mm',
            'max_pressure_bar': self.max_pressure_bar or 0.0,
            'unit_pressure': self.unit_pressure or 'bar',
            'max_temp_c': self.max_temp_c or 0.0,
            'unit_temp': self.unit_temp or 'degC',
            'seal_type': self.seal_type or '',
            'drive_type': self.drive_type or '',
            'is_multistage': bool(self.is_multistage),
            'num_stages': self.num_stages or 1,
            'is_double_suction': bool(self.is_double_suction),
            'is_angle_trim': bool(self.is_angle_trim),
            'is_self_priming': bool(self.is_self_priming),
            'is_non_clog': bool(self.is_non_clog),
            'has_inducer': bool(self.has_inducer),
            'is_throttling_capable': bool(self.is_throttling_capable if self.is_throttling_capable is not None else True),
            'min_flow_m3h': self.min_flow_m3h or 0.0,
            'max_orifice_dia_mm': self.max_orifice_dia_mm or 0.0,
            'impeller_eye_area_cm2': self.impeller_eye_area_cm2 or 0.0,
            'vfd_min_hz': self.vfd_min_hz or 30.0,
            'vfd_max_hz': self.vfd_max_hz or 60.0,
            'extra_curves_json': self.extra_curves_json or '',
            'diameters': self.get_diameters(),
            'extra_curves': self.get_extra_curves(),
            'graph_options': self.get_graph_options(),
            'data_units': self._get_data_units(),
            'curve_labels': self.curve_labels or '',
            'curve_diameters': self.curve_diameters or '',
            'curve_colors': self.curve_colors or '',
            'curve_modes': self.curve_modes or '',
            'curve_units': self.curve_units or '',
            'curve_raw_tables': self.curve_raw_tables or '',
            'curve_coeffs': self.curve_coeffs or '',
            'unit_q': self.unit_q or 'm3h',
            'unit_h': self.unit_h or 'm',
            'unit_npsh': self.unit_npsh or 'm',
            'unit_pow': self.unit_pow or 'kw',
            'unit_op_q': self.unit_op_q or 'm3h',
            'head_curve_style': self.head_curve_style or '#58a6ff;2.0,solid',
            'eff_curve_style': self.eff_curve_style or '#3fb950;1.5,dot',
            'power_curve_style': self.power_curve_style or '#f85149;1.5,longdash',
            'npsh_curve_style': self.npsh_curve_style or '#39d3c0;1.5,dashdot',
            'main_curve_style': self.main_curve_style or 'graph',
            # Custom Axis Scale Settings (Flow, Head, Efficiency, Power, NPSH)
            'axis_flow_min': self.axis_flow_min,
            'axis_flow_max': self.axis_flow_max,
            'axis_flow_major': self.axis_flow_major,
            'axis_flow_minor': self.axis_flow_minor,

            'axis_head_min': self.axis_head_min,
            'axis_head_max': self.axis_head_max,
            'axis_head_major': self.axis_head_major,
            'axis_head_minor': self.axis_head_minor,

            'axis_eff_min': self.axis_eff_min,
            'axis_eff_max': self.axis_eff_max,
            'axis_eff_major': self.axis_eff_major,
            'axis_eff_minor': self.axis_eff_minor,

            'axis_power_min': self.axis_power_min,
            'axis_power_max': self.axis_power_max,
            'axis_power_major': self.axis_power_major,
            'axis_power_minor': self.axis_power_minor,

            'axis_npsh_min': self.axis_npsh_min,
            'axis_npsh_max': self.axis_npsh_max,
            'axis_npsh_major': self.axis_npsh_major,
            'axis_npsh_minor': self.axis_npsh_minor,
            'poly_order': self.poly_order or 3,
            'poly_order_hq': self.poly_order_hq or 3,
            'poly_order_eff': self.poly_order_eff or 3,
            'poly_order_npsh': self.poly_order_npsh or 2,
            'poly_order_pow': self.poly_order_pow or 2,
            'catalogue_report_ids': getattr(self, 'catalogue_report_ids', 'all') or 'all',
            'selection_allow_fixed_speed': getattr(self, 'selection_allow_fixed_speed', True),
            'selection_allow_vsd': getattr(self, 'selection_allow_vsd', True),
            **{f'PumpAttribute{i}': getattr(self, f'PumpAttribute{i}', '') or '' for i in range(1, 31)},
        }

    def get_custom_attribute(self, index):
        """
        Beginners Note: Retrieves the custom PumpAttribute value by index (1 to 30).
        """
        try:
            idx = int(index)
            if 1 <= idx <= 30:
                return getattr(self, f'PumpAttribute{idx}', '') or ''
        except (ValueError, TypeError):
            pass
        return ''

    def get_effective_catalogue_reports(self, org=None):
        """
        Beginners Note: Two-level intersection filtering for PDF reports in the Pump Catalogue:
        Level 1: Organisation-allowed reports (org.get_catalogue_reports())
        Level 2: Pump-specific allowed reports (self.catalogue_report_ids)
        A report is available in the catalogue ONLY IF permitted by BOTH Organisation AND this specific Pump.
        """
        if org is None:
            from utils import get_current_organisation
            org = get_current_organisation()

        # Level 1: Organisation-level permitted reports
        org_reports = org.get_catalogue_reports() if org else ReportConfig.query.all()
        if not org_reports:
            return []

        # Level 2: Pump-specific report filter
        raw_pump_reps = getattr(self, 'catalogue_report_ids', '')
        if not raw_pump_reps or not raw_pump_reps.strip() or raw_pump_reps.strip().lower() == 'all':
            return org_reports

        pump_rep_ids = {int(x.strip()) for x in raw_pump_reps.replace(';', ',').split(',') if x.strip().isdigit()}
        
        # Intersection: only reports present in both Level 1 and Level 2
        return [r for r in org_reports if r.id in pump_rep_ids]


class Organisation(db.Model):
    """
    Beginners Note: Organisation Model ('organisations' table)
    Represents an Engineering Organisation or Manufacturer profile, with defaults and multi-organisation visibility rules.
    """
    __tablename__ = 'organisations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    logo_url = db.Column(db.String(255), default='')
    contact_email = db.Column(db.String(100), default='')
    phone = db.Column(db.String(50), default='')
    website = db.Column(db.String(100), default='')
    address = db.Column(db.Text, default='')
    
    # Allowed organisations whose pumps this organisation is permitted to view (comma-separated IDs or 'all')
    allowed_view_org_ids = db.Column(db.String(255), default='')
    
    # Specified reports to display in the Pump Catalogue (comma-separated ReportConfig IDs or 'all')
    catalogue_report_ids = db.Column(db.String(255), default='')
    
    # Defaults for the organisation
    default_unit_flow = db.Column(db.String(10), default='m3h')
    default_unit_head = db.Column(db.String(10), default='m')
    default_unit_power = db.Column(db.String(10), default='kw')
    default_unit_npsh = db.Column(db.String(10), default='m')
    primary_color = db.Column(db.String(20), default='#1e3a8a')
    notes = db.Column(db.Text, default='')

    created_at = db.Column(db.DateTime, default=_utcnow)

    # Relationships
    pumps = db.relationship('Pump', backref='organisation', lazy=True)
    reports = db.relationship('ReportConfig', backref='organisation', lazy=True, cascade='all, delete-orphan', foreign_keys='ReportConfig.organisation_id')

    # Default Reports for Pump Selection
    default_report_fixed_speed_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=True)
    default_report_vsd_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=True)

    # Organisation-level Graph & Chart Visual Styles (Colors, Line Styles, Font Family, Grids)
    graph_styles_json = db.Column(db.Text, default='{}')

    # Custom Pump Details Jinja2 Template Path (served from templates/ directory)
    # e.g., 'details/default_pump_details.html' or 'details/lytrose_pump_details.html'
    pump_details_template = db.Column(db.String(255), default='details/default_pump_details.html')

    # Custom Organisation Pump Attribute Definitions (PumpAttributeName1 to 30)
    PumpAttributeName1  = db.Column(db.String(100), default='')
    PumpAttributeName2  = db.Column(db.String(100), default='')
    PumpAttributeName3  = db.Column(db.String(100), default='')
    PumpAttributeName4  = db.Column(db.String(100), default='')
    PumpAttributeName5  = db.Column(db.String(100), default='')
    PumpAttributeName6  = db.Column(db.String(100), default='')
    PumpAttributeName7  = db.Column(db.String(100), default='')
    PumpAttributeName8  = db.Column(db.String(100), default='')
    PumpAttributeName9  = db.Column(db.String(100), default='')
    PumpAttributeName10 = db.Column(db.String(100), default='')
    PumpAttributeName11 = db.Column(db.String(100), default='')
    PumpAttributeName12 = db.Column(db.String(100), default='')
    PumpAttributeName13 = db.Column(db.String(100), default='')
    PumpAttributeName14 = db.Column(db.String(100), default='')
    PumpAttributeName15 = db.Column(db.String(100), default='')
    PumpAttributeName16 = db.Column(db.String(100), default='')
    PumpAttributeName17 = db.Column(db.String(100), default='')
    PumpAttributeName18 = db.Column(db.String(100), default='')
    PumpAttributeName19 = db.Column(db.String(100), default='')
    PumpAttributeName20 = db.Column(db.String(100), default='')
    PumpAttributeName21 = db.Column(db.String(100), default='')
    PumpAttributeName22 = db.Column(db.String(100), default='')
    PumpAttributeName23 = db.Column(db.String(100), default='')
    PumpAttributeName24 = db.Column(db.String(100), default='')
    PumpAttributeName25 = db.Column(db.String(100), default='')
    PumpAttributeName26 = db.Column(db.String(100), default='')
    PumpAttributeName27 = db.Column(db.String(100), default='')
    PumpAttributeName28 = db.Column(db.String(100), default='')
    PumpAttributeName29 = db.Column(db.String(100), default='')
    PumpAttributeName30 = db.Column(db.String(100), default='')

    # Checkbox flags to enable/disable each attribute definition
    PumpAttributeEnabled1  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled2  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled3  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled4  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled5  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled6  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled7  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled8  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled9  = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled10 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled11 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled12 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled13 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled14 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled15 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled16 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled17 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled18 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled19 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled20 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled21 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled22 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled23 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled24 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled25 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled26 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled27 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled28 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled29 = db.Column(db.Boolean, default=True)
    PumpAttributeEnabled30 = db.Column(db.Boolean, default=True)

    def get_pump_attributes(self):
        """
        Beginners Note: Returns all 30 custom pump attribute slots with index, name, and enabled state.
        """
        attrs = []
        for i in range(1, 31):
            name = (getattr(self, f'PumpAttributeName{i}', '') or '').strip()
            enabled = bool(getattr(self, f'PumpAttributeEnabled{i}', True))
            attrs.append({
                'index': i,
                'name': name,
                'enabled': enabled
            })
        return attrs

    def get_enabled_pump_attributes(self):
        """
        Beginners Note: Returns only defined and enabled pump attribute slots.
        """
        return [attr for attr in self.get_pump_attributes() if attr['name'] and attr['enabled']]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_pump_details_template(self):
        """
        Beginners Note: Returns the Jinja2 template path for the organisation's pump details view.
        Defaults to 'details/default_pump_details.html' if not specified or empty.
        """
        if self.pump_details_template and self.pump_details_template.strip():
            tmpl = self.pump_details_template.strip().replace('\\', '/')
            if not tmpl.endswith('.html'):
                tmpl += '.html'
            if not tmpl.startswith('details/') and '/' not in tmpl:
                tmpl = f'details/{tmpl}'
            return tmpl
        return 'details/default_pump_details.html'

    def get_graph_styles(self):
        """
        Beginners Note: Returns graph visual styles dictionary for this organisation.
        Controls line colors, widths, dash styles, font family, and grid aesthetics
        in the Pump Selection Details chart and across the suite.
        """
        import json
        default_styles = {
            # 1. Per-Graph Curve Styles
            'hq_color': '#58a6ff',
            'hq_width': 2.5,
            'hq_style': 'solid',  # solid, dashed, dot, dashdot
            'eta_color': '#3fb950',
            'eta_width': 2.5,
            'eta_style': 'solid',
            'pow_color': '#f0c040',
            'pow_width': 2.5,
            'pow_style': 'solid',
            'npsh_color': '#bc8cff',
            'npsh_width': 2.5,
            'npsh_style': 'solid',
            
            # 2. Curve Type Hierarchy Styles
            'max_curve_width': 2.5,
            'min_curve_width': 1.8,
            'trim_curve_width': 2.5,
            'trim_curve_style': 'dash',  # dash, dot, dashdot, solid
            'rated_marker_color': '#f85149',
            'rated_marker_size': 12.0,
            'system_curve_color': '#8b949e',
            'system_curve_style': 'dot',

            # 3. Typography & Font Settings
            'font_family': 'Inter, sans-serif',  # Inter, Segoe UI, Roboto, Arial, monospace
            'font_weight': '600',

            # 4. Axes, Grid & Canvas Styles
            'major_grid_color': '#30363d',
            'minor_grid_color': '#21262d',
            'axis_line_color': '#30363d',
            'chart_bg_color': 'rgba(0,0,0,0)'
        }

        raw = getattr(self, 'graph_styles_json', '')
        if raw and str(raw).strip():
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    merged = dict(default_styles)
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return default_styles

    def get_allowed_org_ids(self):
        """
        Beginners Note: Returns list of integer Organisation IDs allowed for viewing.
        If 'all' or empty is configured, returns None (meaning unrestricted/all).
        If specific IDs are set, returns list of integers including own ID.
        """
        raw = getattr(self, 'allowed_view_org_ids', '')
        if not raw or not raw.strip():
            return None
        raw_str = raw.strip().lower()
        if raw_str == 'all':
            return None
        ids = []
        for x in raw_str.replace(';', ',').split(','):
            x = x.strip()
            if x.isdigit():
                ids.append(int(x))
        if self.id and self.id not in ids:
            ids.append(self.id)
        return ids if ids else None

    def get_catalogue_reports(self):
        """
        Beginners Note: Returns the list of ReportConfig objects enabled for display in the Pump Catalogue.
        If specific IDs are configured in catalogue_report_ids, returns those reports.
        Otherwise returns all reports linked to this organisation, or all active reports.
        """
        raw = getattr(self, 'catalogue_report_ids', '')
        if raw and raw.strip():
            if raw.strip().lower() == 'all':
                return ReportConfig.query.all()
            ids = [int(x.strip()) for x in raw.replace(';', ',').split(',') if x.strip().isdigit()]
            if ids:
                reps = ReportConfig.query.filter(ReportConfig.id.in_(ids)).all()
                if reps:
                    return reps
        
        # Fallback to reports linked to this organisation or all available reports
        org_reps = ReportConfig.query.filter_by(organisation_id=self.id).all()
        return org_reps if org_reps else ReportConfig.query.all()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'logo_url': self.logo_url or '',
            'contact_email': self.contact_email or '',
            'phone': self.phone or '',
            'website': self.website or '',
            'address': self.address or '',
            'allowed_view_org_ids': self.allowed_view_org_ids or '',
            'catalogue_report_ids': self.catalogue_report_ids or '',
            'default_unit_flow': self.default_unit_flow or 'm3h',
            'default_unit_head': self.default_unit_head or 'm',
            'default_unit_power': self.default_unit_power or 'kw',
            'default_unit_npsh': self.default_unit_npsh or 'm',
            'primary_color': self.primary_color or '#1e3a8a',
            'notes': self.notes or '',
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'default_report_fixed_speed_id': getattr(self, 'default_report_fixed_speed_id', None),
            'default_report_vsd_id': getattr(self, 'default_report_vsd_id', None),
            'graph_styles': self.get_graph_styles(),
            'graph_styles_json': getattr(self, 'graph_styles_json', '') or '{}',
        }


# Backward compatibility alias
Supplier = Organisation


class ReportConfig(db.Model):
    """
    Beginners Note: ReportConfig Model ('reports' table)
    Stores custom PDF report templates, graph show/hide preferences, header/footer branding,
    and organisation links for generating technical pump datasheets.
    """
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'), nullable=True)
    report_name = db.Column(db.String(100), default='standard')
    title = db.Column(db.String(150), nullable=False, default='Standard Pump Technical Datasheet')
    report_type = db.Column(db.String(100), default='Technical Datasheet')
    description = db.Column(db.Text, default='')
    template_name = db.Column(db.String(100), default='standard_datasheet.html')

    @property
    def supplier_id(self):
        return self.organisation_id

    @supplier_id.setter
    def supplier_id(self, val):
        self.organisation_id = val

    @property
    def supplier(self):
        return self.organisation

    @supplier.setter
    def supplier(self, val):
        self.organisation = val

    # Graph Show/Hide Preferences
    show_head_flow_graph = db.Column(db.Boolean, default=True)
    show_efficiency_graph = db.Column(db.Boolean, default=True)
    show_power_graph = db.Column(db.Boolean, default=True)
    show_npsh_graph = db.Column(db.Boolean, default=True)

    # Advanced Plotting Settings (Matches Pump-Data Options)
    show_eff_isolines = db.Column(db.Boolean, default=True)
    show_power_isolines = db.Column(db.Boolean, default=False)
    show_npsh_curves = db.Column(db.Boolean, default=True)
    show_npsh_isolines = db.Column(db.Boolean, default=False)
    show_speed_lines = db.Column(db.Boolean, default=True)
    show_rpm_overlay = db.Column(db.Boolean, default=False)

    # Unit Settings for the Report (Overrides Pump Base Units)
    unit_flow = db.Column(db.String(10), default='m3h')
    unit_head = db.Column(db.String(10), default='m')
    unit_power = db.Column(db.String(10), default='kw')
    unit_npsh = db.Column(db.String(10), default='m')
    show_dia_overlay = db.Column(db.Boolean, default=False)
    show_additional_graphs = db.Column(db.Boolean, default=True)
    show_legend = db.Column(db.Boolean, default=True)
    legend_position = db.Column(db.String(30), default='top_right')  # 'top_right', 'top_left', 'bottom_right', 'bottom_left'
    legend_mode = db.Column(db.String(30), default='pump_default')  # 'pump_default', 'each', 'hq_only', 'curve_labels'
    label_format = db.Column(db.String(20), default='auto')  # 'auto', 'percent', 'simple'

    # Graph Area Geometry & Dynamic Vertical Layout
    graph_area_top = db.Column(db.String(50), default='4px')
    graph_area_left = db.Column(db.String(50), default='0px')
    graph_area_width = db.Column(db.String(50), default='100%')
    graph_area_height = db.Column(db.String(50), default='auto')
    graph_order = db.Column(db.String(100), default='hq,eta,pow,npsh')
    graph_splits_json = db.Column(db.Text, default='{"1":[100],"2":[55,45],"3":[40,30,30],"4":[30,25,25,20]}')
    graph_styles_json = db.Column(db.Text, default='{}')

    # Visual Branding & Section Toggles
    header_text = db.Column(db.String(200), default='PUMP MASTER PRO - TECHNICAL DATASHEET')
    footer_text = db.Column(db.String(200), default='Generated by Pump Master Pro Engineering Suite')
    primary_color = db.Column(db.String(20), default='#1e3a8a')
    curve_display_mode = db.Column(db.String(20), default='all')  # 'all', 'max_only', 'min_max', 'rated_only'
    show_rated_curve = db.Column(db.Boolean, default=True)  # Checkbox toggle to overlay evaluated rated trim/speed curve
    show_duty_point = db.Column(db.Boolean, default=True)
    show_materials_table = db.Column(db.Boolean, default=True)
    show_extended_specs = db.Column(db.Boolean, default=True)
    show_notes = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, **kwargs):
        # Support supplier_id keyword for backward compatibility
        if 'supplier_id' in kwargs and 'organisation_id' not in kwargs:
            kwargs['organisation_id'] = kwargs.pop('supplier_id')
        super().__init__(**kwargs)

    def get_graph_order(self):
        """Returns the list of graph keys in user-configured display order (e.g. ['hq', 'eta', 'pow', 'npsh'])."""
        raw = getattr(self, 'graph_order', '') or 'hq,eta,pow,npsh'
        valid = ['hq', 'eta', 'pow', 'npsh']
        order = [x.strip().lower() for x in raw.replace(';', ',').split(',') if x.strip().lower() in valid]
        for v in valid:
            if v not in order:
                order.append(v)
        return order

    def get_graph_splits(self):
        """Returns height percentage splits for 1, 2, 3, and 4 active graphs."""
        import json
        default_splits = {
            "1": [100.0],
            "2": [55.0, 45.0],
            "3": [40.0, 30.0, 30.0],
            "4": [30.0, 25.0, 25.0, 20.0]
        }
        raw = getattr(self, 'graph_splits_json', '')
        if raw and raw.strip():
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    res = {}
                    for k in ["1", "2", "3", "4"]:
                        if k in data and isinstance(data[k], list) and len(data[k]) == int(k):
                            res[k] = [float(x) for x in data[k]]
                        else:
                            res[k] = default_splits[k]
                    return res
            except Exception:
                pass
        return default_splits

    def get_graph_styles(self):
        """
        Returns graph visual styles dictionary with comprehensive fallbacks:
        - Per-graph primary curve colors, thickness, line styles
        - Max/Min/Trim curve styles
        - Typography (font family, size scale, weight)
        - Axes and Grid (major/minor grid colors, widths, styles, axis border)
        - Isoline colors & styles
        """
        import json
        default_styles = {
            # 1. Per-Graph Curve Styles
            'hq_color': '#1e3a8a',
            'hq_width': 2.6,
            'hq_style': 'solid',  # solid, dashed, dotted
            'eta_color': '#059669',
            'eta_width': 2.4,
            'eta_style': 'solid',
            'pow_color': '#dc2626',
            'pow_width': 2.4,
            'pow_style': 'solid',
            'npsh_color': '#0284c7',
            'npsh_width': 2.4,
            'npsh_style': 'solid',
            
            # 2. Curve Type Hierarchy Styles
            'max_curve_color': '',  # empty = inherit from chart primary color
            'max_curve_width': 2.6,
            'max_curve_style': 'solid',
            'min_curve_color': '',  # empty = inherit from palette
            'min_curve_width': 2.0,
            'min_curve_style': 'dashed',
            'trim_curve_width': 1.8,
            'trim_curve_style': 'dashed',
            'rated_marker_color': '#dc2626',
            'rated_marker_size': 6.0,

            # 3. Typography & Font Settings
            'font_family': 'Segoe UI',  # Segoe UI, Inter, Roboto, Arial, Helvetica, monospace
            'font_scale': 'standard',  # small, standard, large
            'font_weight': '600',  # normal, 500, 600, 700
            'badge_style': 'pill_white',  # pill_white, subtle_glow, plain

            # 4. Axes, Grid & Canvas Styles
            'major_grid_color': '#cbd5e1',
            'major_grid_width': 1.0,
            'major_grid_style': 'dashed',  # dashed, solid, dotted, none
            'minor_grid_color': '#e2e8f0',
            'minor_grid_width': 0.8,
            'minor_grid_style': 'dotted',  # dotted, dashed, solid, none
            'axis_line_color': '#475569',
            'axis_line_width': 1.5,
            'chart_bg_color': '#ffffff',

            # 5. Isolines Styling
            'iso_eta_color': '#059669',
            'iso_pow_color': '#d97706',
            'iso_npsh_color': '#0284c7',
            'iso_width': 1.3,
            'iso_style': 'dashed'
        }

        raw = getattr(self, 'graph_styles_json', '')
        if raw and str(raw).strip():
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    merged = dict(default_styles)
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return default_styles

    def to_dict(self):
        org = getattr(self, 'organisation', None)
        return {
            'id': self.id,
            'organisation_id': self.organisation_id,
            'supplier_id': self.organisation_id,
            'organisation_name': org.name if org else 'Default / Generic',
            'supplier_name': org.name if org else 'Default / Generic',
            'report_name': getattr(self, 'report_name', 'standard') or 'standard',
            'title': self.title or 'Standard Pump Technical Datasheet',
            'report_type': getattr(self, 'report_type', 'Technical Datasheet') or 'Technical Datasheet',
            'description': self.description or '',
            'template_name': self.template_name or 'standard_datasheet.html',
            'show_head_flow_graph': bool(self.show_head_flow_graph),
            'show_efficiency_graph': bool(self.show_efficiency_graph),
            'show_power_graph': bool(self.show_power_graph),
            'show_npsh_graph': bool(self.show_npsh_graph),
            'show_eff_isolines': bool(self.show_eff_isolines),
            'show_power_isolines': bool(self.show_power_isolines),
            'show_npsh_curves': bool(self.show_npsh_curves),
            'show_npsh_isolines': bool(getattr(self, 'show_npsh_isolines', False)),
            'show_speed_lines': bool(self.show_speed_lines),
            'show_rpm_overlay': bool(getattr(self, 'show_rpm_overlay', False)),
            'show_dia_overlay': bool(getattr(self, 'show_dia_overlay', False)),
            'show_additional_graphs': bool(self.show_additional_graphs),
            'show_legend': bool(self.show_legend),
            'legend_position': self.legend_position or 'top_right',
            'legend_mode': getattr(self, 'legend_mode', 'pump_default') or 'pump_default',
            # Beginners Note: Serialize label_format ('auto', 'percent', 'simple') so the configure modal populates the selected dropdown value
            'label_format': getattr(self, 'label_format', 'auto') or 'auto',
            'graph_area_top': getattr(self, 'graph_area_top', '4px') or '4px',
            'graph_area_left': getattr(self, 'graph_area_left', '0px') or '0px',
            'graph_area_width': getattr(self, 'graph_area_width', '100%') or '100%',
            'graph_area_height': getattr(self, 'graph_area_height', 'auto') or 'auto',
            'graph_order': getattr(self, 'graph_order', 'hq,eta,pow,npsh') or 'hq,eta,pow,npsh',
            'graph_splits': self.get_graph_splits(),
            'graph_splits_json': getattr(self, 'graph_splits_json', '') or '{"1":[100],"2":[55,45],"3":[40,30,30],"4":[30,25,25,20]}',
            'graph_styles': self.get_graph_styles(),
            'graph_styles_json': getattr(self, 'graph_styles_json', '') or '{}',
            'header_text': self.header_text or '',
            'footer_text': self.footer_text or '',
            'primary_color': self.primary_color or '#1e3a8a',
            'curve_display_mode': self.curve_display_mode or 'all',
            'show_rated_curve': self.show_rated_curve if self.show_rated_curve is not None else True,
            'show_duty_point': bool(self.show_duty_point),
            'show_materials_table': bool(self.show_materials_table),
            'show_extended_specs': bool(self.show_extended_specs),
            'show_notes': bool(self.show_notes),
            'is_active': bool(self.is_active),
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'unit_flow': getattr(self, 'unit_flow', None),
            'unit_head': getattr(self, 'unit_head', None),
            'unit_power': getattr(self, 'unit_power', None),
            'unit_npsh': getattr(self, 'unit_npsh', None)
        }
