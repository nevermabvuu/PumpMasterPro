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
    # [{"label": str, "color": str, "hq_a0..3": float, "eff_b0..3": float,
    #   "pow_p0..2": float, "npsh_c0..2": float, "q_max": float}]
    extra_curves_json = db.Column(db.Text, default='')

    # Original raw data points entered by the user for the main curve
    # JSON: [[q_display, h_display, eta, npsh_display, pow_display], ...]
    # Values stored in the display unit at the time of saving.
    raw_table_json = db.Column(db.Text, default='')

    # Input-unit preferences for the main performance-data table
    # JSON: {"q": "ls", "h": "m", "npsh": "m", "pow": "kw", "op_q": "ls"}
    data_units = db.Column(db.Text, default='')

    # Saved graph & display options for the curve viewer
    # JSON: {"show_eff_iso": bool, "eff_levels": str, "trim_model": str, ...}
    graph_options_json = db.Column(db.Text, default='')

    # Optional label and measured diameter for the main (first) curve
    main_curve_label  = db.Column(db.String(100), default='')
    main_curve_dia_mm = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_diameters(self):
        """Return sorted list of impeller diameters (descending)."""
        raw = (self.impeller_diameters or '').strip()
        if not raw:
            dias = [self.impeller_dia_mm] if self.impeller_dia_mm else []
        else:
            try:
                diameters = json.loads(raw) if raw.startswith('[') else [float(x) for x in raw.split(',')]
                dias = [float(d) for d in diameters]
            except Exception:
                dias = [self.impeller_dia_mm] if self.impeller_dia_mm else []

        extra = self.get_extra_curves()
        for c in extra:
            d_val = c.get('diameter')
            if d_val is not None and str(d_val).strip() != '':
                try:
                    u = c.get('unit_dia', 'mm')
                    if u == 'in':
                        d_mm = float(d_val) * 25.4
                    elif u == 'm':
                        d_mm = float(d_val) * 1000.0
                    else:
                        d_mm = float(d_val)
                    if round(d_mm, 2) not in [round(x, 2) for x in dias]:
                        dias.append(round(d_mm, 2))
                except (ValueError, TypeError):
                    pass

        if not dias:
            dias = [300.0]
        return sorted(dias, reverse=True)

    def get_extra_curves(self):
        """Return the list of extra manually-defined curves, or []."""
        raw = (self.extra_curves_json or '').strip()
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    def get_graph_options(self):
        """Return saved graph display options dict, or defaults."""
        raw = (self.graph_options_json or '').strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _get_data_units(self):
        """Return the saved input-unit preferences dict, or defaults."""
        raw = (self.data_units or '').strip()
        defaults = {'q': 'm3h', 'h': 'm', 'npsh': 'm', 'pow': 'kw', 'op_q': 'm3h'}
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
            'diameters': self.get_diameters(),
            'extra_curves': self.get_extra_curves(),
            'graph_options': self.get_graph_options(),
            'data_units': self._get_data_units(),
            'main_curve_label': self.main_curve_label or '',
            'main_curve_dia_mm': self.main_curve_dia_mm,
        }
