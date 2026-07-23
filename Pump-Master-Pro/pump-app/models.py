from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)



class Pump(db.Model):
    __tablename__ = 'pumps'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    manufacturer = db.Column(db.String(100), default='')
    model_number = db.Column(db.String(100), default='')
    size = db.Column(db.String(50), default='')
    speed_rpm = db.Column(db.Float, default=1450.0)
    impeller_dia_mm = db.Column(db.Float, default=300.0)

    # Comma/JSON list of available impeller diameters (mm), largest first
    impeller_diameters = db.Column(db.Text, default='')

    # H-Q polynomial: H = hq_a0 + hq_a1*Q + hq_a2*Q^2 + hq_a3*Q^3
    hq_a0 = db.Column(db.Float, nullable=False)
    hq_a1 = db.Column(db.Float, default=0.0)
    hq_a2 = db.Column(db.Float, default=0.0)
    hq_a3 = db.Column(db.Float, default=0.0)

    # Efficiency polynomial: η(%) = eff_b0 + eff_b1*Q + eff_b2*Q^2 + eff_b3*Q^3
    eff_b0 = db.Column(db.Float, default=0.0)
    eff_b1 = db.Column(db.Float, default=0.0)
    eff_b2 = db.Column(db.Float, default=0.0)
    eff_b3 = db.Column(db.Float, default=0.0)

    # NPSH polynomial: NPSHr (m) = npsh_c0 + npsh_c1*Q + npsh_c2*Q^2
    npsh_c0 = db.Column(db.Float, default=1.0)
    npsh_c1 = db.Column(db.Float, default=0.0)
    npsh_c2 = db.Column(db.Float, default=0.0)

    # Power polynomial: P (kW) = pow_p0 + pow_p1*Q + pow_p2*Q^2
    # Fitted with a non-zero shutoff anchor (P≈0.35·P_BEP at Q=0) so the
    # curve rises monotonically without the 1/η singularity at low flow.
    pow_p0 = db.Column(db.Float, default=0.0)
    pow_p1 = db.Column(db.Float, default=0.0)
    pow_p2 = db.Column(db.Float, default=0.0)

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

    # Input-unit preferences for the main performance-data table
    # JSON: {"q": "ls", "h": "m", "npsh": "m", "pow": "kw", "op_q": "ls"}
    data_units = db.Column(db.Text, default='')

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
    graph_show_hq           = db.Column(db.Boolean, default=True)
    graph_show_other        = db.Column(db.Boolean, default=True)
    graph_show_eff          = db.Column(db.Boolean, default=True)
    graph_show_power        = db.Column(db.Boolean, default=True)
    graph_show_npsh         = db.Column(db.Boolean, default=True)
    graph_combine_eff_power = db.Column(db.Boolean, default=True)
    graph_trim_model        = db.Column(db.String(20), default='fit')

    graph_options_json      = db.Column(db.Text, default='')

    # Optional label and measured diameter for the main (first) curve
    main_curve_label  = db.Column(db.String(100), default='')
    main_curve_dia_mm = db.Column(db.Float, nullable=True)

    # Delimited fields for curve metadata & performance tables
    # curve_labels: "curve1;curve2;curve3"
    # curve_diameters: "228;mm|182;mm|300;in"
    # curve_colors: "#58a6ff;#3fb950"
    # curve_modes: "fit;fit"
    # curve_units: "m3h,m,m,kw|m3h,m,m,kw"
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

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_curve_labels_list(self):
        """Return list of labels for loaded curves."""
        raw_labels = (self.curve_labels or '').strip()
        if not raw_labels:
            labels = []
            m_lbl = self.main_curve_label or 'Curve 1'
            labels.append(m_lbl)
            for idx, c in enumerate(self.get_extra_curves()):
                labels.append(c.get('label') or f'Curve {idx + 2}')
            return labels
        return [x.strip() for x in raw_labels.split(';') if x.strip()]

    def get_curve_diameters_list(self):
        """Return list of dicts for loaded curves: [{'diameter': val, 'unit': unit, 'dia_mm': mm_val}, ...]"""
        raw_dias = (self.curve_diameters or '').strip()

        if not raw_dias:
            items = []
            main_d = self.main_curve_dia_mm or self.impeller_dia_mm
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
        m_lbl = self.main_curve_label or 'Curve 1'
        main_d = self.main_curve_dia_mm or self.impeller_dia_mm or ''
        labels.append(m_lbl)
        
        main_dia_unit = 'mm'
        if self.curve_diameters:
            first_dia = self.curve_diameters.split('|')[0]
            parts = first_dia.split(';')
            if len(parts) > 1:
                main_dia_unit = parts[1].strip()
                
        dias_units.append(f"{main_d};{main_dia_unit}")
        colors.append('#58a6ff')
        modes.append('fit')

        du = self._get_data_units()
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

            colors.append(c.get('color', '#3fb950'))
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

    def get_diameters(self):
        """Return sorted list of impeller diameters (descending)."""
        raw = (self.impeller_diameters or '').strip()
        if not raw:
            dias = [self.impeller_dia_mm] if self.impeller_dia_mm else []
        else:
            try:
                diameters = [float(x.strip()) for x in raw.replace(';', ',').replace('[', '').replace(']', '').split(',') if x.strip()]
                dias = [float(d) for d in diameters]
            except Exception:
                dias = [self.impeller_dia_mm] if self.impeller_dia_mm else []

        loaded = self.get_curve_diameters_list()
        for item in loaded:
            d_mm = item['dia_mm']
            if d_mm is not None:
                if round(d_mm, 2) not in [round(x, 2) for x in dias]:
                    dias.append(round(d_mm, 2))

        if not dias:
            dias = [300.0]
        return sorted(dias, reverse=True)

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
        raw_labels = (self.curve_labels or '').strip()
        raw_dias   = (self.curve_diameters or '').strip()
        raw_colors = (self.curve_colors or '').strip()
        raw_modes  = (self.curve_modes or '').strip()
        raw_units  = (self.curve_units or '').strip()
        raw_tbls   = (self.curve_raw_tables or '').strip()
        raw_cfs    = (self.curve_coeffs or '').strip()

        if raw_labels or raw_dias or raw_colors or raw_tbls:
            lbl_items = [x.strip() for x in raw_labels.split(';') if x.strip()] if raw_labels else []
            d_items   = [x.strip() for x in raw_dias.split('|') if x.strip()] if raw_dias else []
            col_items = [x.strip() for x in raw_colors.split(';') if x.strip()] if raw_colors else []
            m_items   = [x.strip() for x in raw_modes.split(';') if x.strip()] if raw_modes else []
            u_items   = [x.strip() for x in raw_units.split('|') if x.strip()] if raw_units else []
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

                c['color'] = col_items[loaded_idx] if loaded_idx < len(col_items) else '#3fb950'
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
            'show_hq': self.graph_show_hq if self.graph_show_hq is not None else True,
            'show_other': self.graph_show_other if self.graph_show_other is not None else True,
            'show_eff': self.graph_show_eff if self.graph_show_eff is not None else True,
            'show_power': self.graph_show_power if self.graph_show_power is not None else True,
            'show_npsh': self.graph_show_npsh if self.graph_show_npsh is not None else True,
            'combine_eff_power': self.graph_combine_eff_power if self.graph_combine_eff_power is not None else True,
            'trim_model': self.graph_trim_model or 'fit',
        }

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
        if 'show_hq' in opts: self.graph_show_hq = bool(opts['show_hq'])
        if 'show_other' in opts: self.graph_show_other = bool(opts['show_other'])
        if 'show_eff' in opts: self.graph_show_eff = bool(opts['show_eff'])
        if 'show_power' in opts: self.graph_show_power = bool(opts['show_power'])
        if 'show_npsh' in opts: self.graph_show_npsh = bool(opts['show_npsh'])
        if 'combine_eff_power' in opts: self.graph_combine_eff_power = bool(opts['combine_eff_power'])
        if 'trim_model' in opts: self.graph_trim_model = str(opts['trim_model'])
        self.graph_options_json = json.dumps(opts)

    def _get_data_units(self):
        """Return input-unit preferences dict from individual columns (with fallback)."""
        defaults = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw', 'op_q': 'm3h'}
        if self.unit_q or self.unit_h:
            return {
                'q': self.unit_q or 'm3h',
                'h': self.unit_h or 'm',
                'npsh': self.unit_npsh or 'm',
                'pow': self.unit_pow or 'kw',
                'op_q': self.unit_op_q or 'm3h',
            }

        raw = (self.data_units or '').strip()
        if not raw:
            return defaults
        try:
            saved = json.loads(raw)
            return {**defaults, **saved}
        except Exception:
            return defaults

    @property
    def data_units_dict(self):
        """Template-friendly alias for _get_data_units()."""
        return self._get_data_units()

    def has_power_poly(self):
        """True when a stored power polynomial is available."""
        return bool(self.pow_p1 or self.pow_p2)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'manufacturer': self.manufacturer,
            'model_number': self.model_number,
            'size': self.size,
            'speed_rpm': self.speed_rpm,
            'impeller_dia_mm': self.impeller_dia_mm,
            'impeller_diameters': self.impeller_diameters or '',
            'hq_a0': self.hq_a0, 'hq_a1': self.hq_a1,
            'hq_a2': self.hq_a2, 'hq_a3': self.hq_a3,
            'eff_b0': self.eff_b0, 'eff_b1': self.eff_b1,
            'eff_b2': self.eff_b2, 'eff_b3': self.eff_b3,
            'npsh_c0': self.npsh_c0, 'npsh_c1': self.npsh_c1, 'npsh_c2': self.npsh_c2,
            'pow_p0': self.pow_p0, 'pow_p1': self.pow_p1, 'pow_p2': self.pow_p2,
            'q_min': self.q_min, 'q_max': self.q_max, 'q_bep': self.q_bep,
            'hr': self.hr, 'qr': self.qr, 'er': self.er,
            'pump_type': self.pump_type,
            'application': self.application,
            'notes': self.notes,
            'extra_curves_json': self.extra_curves_json or '',
            'diameters': self.get_diameters(),
            'extra_curves': self.get_extra_curves(),
            'graph_options': self.get_graph_options(),
            'data_units': self._get_data_units(),
            'main_curve_label': self.main_curve_label or '',
            'main_curve_dia_mm': self.main_curve_dia_mm,
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
        }
