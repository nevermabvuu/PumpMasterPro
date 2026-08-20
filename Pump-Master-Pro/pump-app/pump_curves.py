"""
pump_curves.py — Warman-style pump curve mathematics.

All curve families use affinity laws for impeller diameter variation:
  Q ∝ D     H ∝ D²     P ∝ D³     η ≈ constant

Power model
-----------
Power is taken from the stored polynomial (pow_p0..p2) whenever it is
available.  The polynomial is fitted with a non-zero shutoff anchor
(P ≈ 0.35·P_BEP at Q=0) so the curve rises continuously from shutoff
instead of spiking via the 1/η singularity in the derived formula.
If no polynomial is stored, the curve falls back to P = ρgQH/η evaluated
only in the valid operating range (η > 5 %).
"""
import numpy as np
import re

G = 9.81   # m/s²

Q_TO_M3H = {'m3h': 1.0, 'ls': 3.6, 'gpm': 0.2271247, 'lmin': 0.06}
H_TO_M = {'m': 1.0, 'ft': 0.3048}
POW_TO_KW = {'kw': 1.0, 'hp': 0.745699872}


# ── Polynomial evaluation ──────────────────────────────────────────────────────

def eval_poly(coeffs, q):
    """Evaluate polynomial: c₀ + c₁·q + c₂·q² + ..."""
    return sum(c * q ** i for i, c in enumerate(coeffs))


def _poly_array(coeffs, q_array):
    """Vectorised polynomial evaluation."""
    result = np.zeros_like(q_array, dtype=float)
    for i, c in enumerate(coeffs):
        result += c * q_array ** i
    return result


# ── Raw curve evaluation (base diameter) ──────────────────────────────────────

def _safe_deg(val, default_val=3):
    if val is None:
        return default_val
    try:
        i = int(val)
        return i if 1 <= i <= 5 else default_val
    except (TypeError, ValueError):
        return default_val


def _hq_raw(pump, q_array):
    """
    H-Q curve for max impeller, no derating.
    Beginners Note: Evaluates polynomial up to poly_order_hq degree (1 to 5).
    """
    deg = _safe_deg(getattr(pump, 'poly_order_hq', None), _safe_deg(getattr(pump, 'poly_order', 3), 3))
    coeffs = [getattr(pump, 'hq_a0', 0.0), getattr(pump, 'hq_a1', 0.0), getattr(pump, 'hq_a2', 0.0), getattr(pump, 'hq_a3', 0.0), getattr(pump, 'hq_a4', 0.0), getattr(pump, 'hq_a5', 0.0)][:deg + 1]
    return np.clip(_poly_array(coeffs, q_array), 0, None)


def _eta_raw(pump, q_array):
    """
    Efficiency curve for max impeller, no derating (0–100%).
    Beginners Note: Evaluates polynomial up to poly_order_eff degree (1 to 5).
    """
    deg = _safe_deg(getattr(pump, 'poly_order_eff', None), _safe_deg(getattr(pump, 'poly_order', 3), 3))
    coeffs = [getattr(pump, 'eff_b0', 0.0), getattr(pump, 'eff_b1', 0.0), getattr(pump, 'eff_b2', 0.0), getattr(pump, 'eff_b3', 0.0), getattr(pump, 'eff_b4', 0.0), getattr(pump, 'eff_b5', 0.0)][:deg + 1]
    return np.clip(_poly_array(coeffs, q_array), 0, 100)


def _npsh_raw(pump, q_array):
    """
    NPSHr curve for max impeller (m).
    Beginners Note: Evaluates polynomial up to poly_order_npsh degree (1 to 5).
    """
    deg = _safe_deg(getattr(pump, 'poly_order_npsh', None), 2)
    coeffs = [getattr(pump, 'npsh_c0', 0.0), getattr(pump, 'npsh_c1', 0.0), getattr(pump, 'npsh_c2', 0.0), getattr(pump, 'npsh_c3', 0.0), getattr(pump, 'npsh_c4', 0.0), getattr(pump, 'npsh_c5', 0.0)][:deg + 1]
    return np.clip(_poly_array(coeffs, q_array), 0, None)


def _pow_raw(pump, q_array, scale=1.0):
    """
    Shaft power from stored polynomial (kW), scaled by `scale` for affinity laws.
    Beginners Note: Evaluates polynomial up to poly_order_pow degree (1 to 5).
    """
    if not pump.has_power_poly():
        return None
    deg = _safe_deg(getattr(pump, 'poly_order_pow', None), 2)
    coeffs = [getattr(pump, 'pow_p0', 0.0), getattr(pump, 'pow_p1', 0.0), getattr(pump, 'pow_p2', 0.0), getattr(pump, 'pow_p3', 0.0), getattr(pump, 'pow_p4', 0.0), getattr(pump, 'pow_p5', 0.0)][:deg + 1]
    p = _poly_array(coeffs, q_array)
    return np.clip(p * scale, 0, None)


# ── Liquid derating ────────────────────────────────────────────────────────────

def hq_curve(pump, q_array, liquid='water', viscosity_cSt=1.0,
             slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    h = _hq_raw(pump, q_array)
    if liquid == 'slurry':
        hr, _, _ = _slurry_factors(pump, slurry_cv, slurry_d50, rho_solid)
        h = h * hr
    elif liquid == 'viscous' and viscosity_cSt > 1.0:
        ch, _, _ = _viscosity_correction(viscosity_cSt)
        h = h * ch
    return h


def efficiency_curve(pump, q_array, liquid='water', viscosity_cSt=1.0,
                     slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    eta = _eta_raw(pump, q_array)
    if liquid == 'slurry':
        _, _, er = _slurry_factors(pump, slurry_cv, slurry_d50, rho_solid)
        eta = eta * er
    elif liquid == 'viscous' and viscosity_cSt > 1.0:
        _, _, ce = _viscosity_correction(viscosity_cSt)
        eta = eta * ce
    return np.clip(eta, 0, 100)


def power_curve(pump, q_array, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650, _pow_scale=1.0):
    """
    Shaft power (kW).

    Uses the stored power polynomial when available — this gives a physically
    correct curve that starts at a non-zero shutoff value and rises with flow.

    Falls back to P = ρ·g·H·Q / η only in the mid-range where η > 5 %,
    to avoid the 1/η singularity near shutoff and runout.
    """
    if liquid == 'slurry':
        rho = _slurry_density(slurry_cv, rho_solid)

    stored = _pow_raw(pump, q_array, scale=_pow_scale)
    if stored is not None:
        if liquid == 'slurry':
            _, _, er = _slurry_factors(pump, slurry_cv, slurry_d50, rho_solid)
            stored = stored * er
        elif liquid == 'viscous' and viscosity_cSt > 1.0:
            _, _, ce = _viscosity_correction(viscosity_cSt)
            stored = stored * ce
        return stored

    h = hq_curve(pump, q_array, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta = efficiency_curve(pump, q_array, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    return np.where(eta > 5, rho * G * h * (q_array / 3600.0) / (eta / 100.0) / 1000.0, 0.0)


def npsh_curve(pump, q_array):
    return _npsh_raw(pump, q_array)


# ── BEP / operating point ──────────────────────────────────────────────────────

def bep_point(pump, liquid='water', rho=1000.0, viscosity_cSt=1.0,
              slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    q_arr = np.linspace(pump.q_min or 0, pump.q_max, 500)
    eta = efficiency_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    idx = int(np.argmax(eta))
    h_arr = hq_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    p_arr = power_curve(pump, q_arr, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    return {
        'q': round(float(q_arr[idx]), 2),
        'h': round(float(h_arr[idx]), 2),
        'eta': round(float(eta[idx]), 2),
        'power': round(float(p_arr[idx]), 2),
    }


def operating_point(pump, q_duty, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                    slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    q_arr = np.array([float(q_duty)])
    h = float(hq_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
    eta = float(efficiency_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
    p = float(power_curve(pump, q_arr, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
    npsh = float(npsh_curve(pump, q_arr)[0])
    return {'q': q_duty, 'h': round(h, 2), 'eta': round(eta, 2),
            'power': round(p, 2), 'npsh': round(npsh, 2)}


# ── Single-diameter curve bundle ───────────────────────────────────────────────

def full_curve_data(pump, n_points=80, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                    slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    q_arr = np.linspace(pump.q_min or 0, pump.q_max, n_points)
    h    = hq_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta  = efficiency_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    pwr  = power_curve(pump, q_arr, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    npsh = npsh_curve(pump, q_arr)

    h_clean = eta_clean = pwr_clean = None
    if liquid in ('slurry', 'viscous'):
        h_clean   = hq_curve(pump, q_arr, 'water').tolist()
        eta_clean = efficiency_curve(pump, q_arr, 'water').tolist()
        pwr_clean = power_curve(pump, q_arr, 'water', 1000.0).tolist()

    return {
        'q': q_arr.tolist(), 'h': h.tolist(), 'eta': eta.tolist(),
        'power': pwr.tolist(), 'npsh': npsh.tolist(),
        'h_clean': h_clean, 'eta_clean': eta_clean, 'power_clean': pwr_clean,
        'liquid': liquid,
    }


# ── Affinity-law family of curves (multiple impeller diameters) ────────────────

def family_curves_diameter(pump, n_points=100, liquid='water', rho=1000.0,
                           viscosity_cSt=1.0, slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                           force_affinity=False, trim_penalty=None):
    """
    Return a list of curve dicts — one per impeller diameter.
    Evaluates fitted polynomial curves for extra curves when mode is 'fit' (unless force_affinity is True),
    otherwise scales from max-dia base curve by affinity laws.
    """
    diameters = pump.get_diameters()
    if not diameters:
        diameters = [pump.impeller_dia_mm or 300.0]
    d_max = max(diameters)

    q_base = np.linspace(pump.q_min or 0, pump.q_max, n_points)
    h_base   = hq_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta_base = efficiency_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    pwr_base = power_curve(pump, q_base, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    npsh_base = npsh_curve(pump, q_base)

    extra_curves = pump.get_extra_curves()
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    if fam_type == 'variable_speed':
        trim_penalty_coeff = 0.0
    elif trim_penalty is not None:
        try: trim_penalty_coeff = float(trim_penalty)
        except (ValueError, TypeError): trim_penalty_coeff = 20.0
    elif getattr(pump, 'graph_trim_penalty', None) is not None:
        try: trim_penalty_coeff = float(pump.graph_trim_penalty)
        except (ValueError, TypeError): trim_penalty_coeff = 20.0
    else:
        min_eta = None
        min_r = None
        for c in extra_curves:
            raw_t = c.get('raw_table', [])
            d_val = c.get('diameter')
            if raw_t and d_val:
                try:
                    u = c.get('unit_dia', 'mm')
                    d_mm = float(d_val) * (25.4 if u == 'in' else (1000.0 if u == 'm' else 1.0))
                    r_c = d_mm / d_max
                    etas = [float(row[2]) for row in raw_t if isinstance(row, list) and len(row) >= 3 and row[2] != '' and row[2] is not None]
                    if etas:
                        max_e = max(etas)
                        if min_r is None or r_c < min_r:
                            min_r = r_c
                            min_eta = max_e
                except (ValueError, TypeError):
                    pass
        eta_base_max = float(np.max(eta_base)) if len(eta_base) > 0 else 80.0
        if min_eta is not None and min_r is not None and min_r < 0.99 and eta_base_max > min_eta:
            calc_coeff = (eta_base_max - min_eta) / (1.0 - min_r)
            trim_penalty_coeff = max(5.0, min(calc_coeff, 22.0))
        else:
            trim_penalty_coeff = 20.0

    extra_map = {}
    for c in extra_curves:
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
                extra_map[round(d_mm, 2)] = c
            except (ValueError, TypeError):
                pass

    family = []
    for d in diameters:
        d_round = round(d, 2)
        r = d / d_max
        matched_extra = extra_map.get(d_round)

        # Determine effective mode
        if force_affinity == 'affinity' or force_affinity is True:
            eff_mode = 'affinity'
        elif force_affinity == 'both':
            eff_mode = 'both'
        elif matched_extra:
            eff_mode = matched_extra.get('curve_mode', 'fit')
        elif force_affinity == 'fit':
            eff_mode = 'fit'
        else:
            eff_mode = 'affinity'

        if matched_extra and (not matched_extra.get('hq_a0') or matched_extra.get('hq_a0') == 0):
            raw_t = matched_extra.get('raw_table', [])
            u_q = matched_extra.get('unit_q', 'm3h')
            u_h = matched_extra.get('unit_h', 'm')
            u_p = matched_extra.get('unit_pow', 'kw')
            f_q = Q_TO_M3H.get(u_q, 1.0)
            f_h = H_TO_M.get(u_h, 1.0)
            f_p = POW_TO_KW.get(u_p, 1.0)

            q_h, q_eta, q_p = [], [], []
            for row in raw_t:
                if isinstance(row, list) and len(row) >= 2:
                    try:
                        q_v, h_v = float(row[0]) * f_q, float(row[1]) * f_h
                        q_h.append([q_v, h_v])
                        if len(row) >= 3 and row[2] != '' and row[2] is not None: q_eta.append([q_v, float(row[2])])
                        if len(row) >= 5 and row[4] != '' and row[4] is not None: q_p.append([q_v, float(row[4]) * f_p])
                    except (ValueError, TypeError):
                        pass
            if len(q_h) >= 3:
                try:
                    res = fit_pump_polynomials(q_h=q_h, q_eta=q_eta or None, q_p=q_p or None)
                    matched_extra.update(res)
                except Exception:
                    pass

        has_poly = (matched_extra is not None and matched_extra.get('hq_a0') is not None and matched_extra.get('hq_a0') != 0)
        can_fit  = has_poly and d != d_max

        def _make_fitted():
            c = matched_extra or {}
            q_m = float(c.get('q_max') or (pump.q_max * r))
            q_arr = np.linspace(0, q_m, n_points)

            hq_coeffs = [c.get('hq_a0', 0), c.get('hq_a1', 0), c.get('hq_a2', 0), c.get('hq_a3', 0)]
            eff_coeffs = [c.get('eff_b0', 0), c.get('eff_b1', 0), c.get('eff_b2', 0), c.get('eff_b3', 0)]
            pwr_coeffs = [c.get('pow_p0', 0), c.get('pow_p1', 0), c.get('pow_p2', 0)]
            npsh_coeffs = [c.get('npsh_c0', 0), c.get('npsh_c1', 0), c.get('npsh_c2', 0)]

            h_arr = np.clip(_poly_array(hq_coeffs, q_arr), 0, None)
            eta_arr = np.clip(_poly_array(eff_coeffs, q_arr), 0, 100)
            pwr_arr = np.clip(_poly_array(pwr_coeffs, q_arr), 0, None)
            if npsh_coeffs[1] != 0 or npsh_coeffs[2] != 0:
                npsh_arr = np.clip(_poly_array(npsh_coeffs, q_arr), 0, None)
            else:
                npsh_arr = np.clip(npsh_curve(pump, q_arr) * r**2, 0, None)

            if liquid == 'slurry':
                hr, _, er = _slurry_factors(pump, slurry_cv, slurry_d50, rho_solid)
                h_arr = h_arr * hr
                eta_arr = np.clip(eta_arr * er, 0, 100)
                pwr_arr = pwr_arr * er
            elif liquid == 'viscous' and viscosity_cSt > 1.0:
                ch, _, ce = _viscosity_correction(viscosity_cSt)
                h_arr = h_arr * ch
                eta_arr = np.clip(eta_arr * ce, 0, 100)
                pwr_arr = pwr_arr * ce

            idx_bep = int(np.argmax(eta_arr))
            bep_dict = {
                'q': round(float(q_arr[idx_bep]), 2),
                'h': round(float(h_arr[idx_bep]), 2),
                'eta': round(float(eta_arr[idx_bep]), 2),
                'power': round(float(pwr_arr[idx_bep]), 2)
            }

            c_use_custom = c.get('use_custom_style', False) or (c.get('style_mode') == 'custom')
            return {
                'dia': d,
                'is_max': False,
                'ratio': round(r, 4),
                'curve_mode': 'fit',
                'q': q_arr.tolist(),
                'h': h_arr.tolist(),
                'eta': eta_arr.tolist(),
                'power': pwr_arr.tolist(),
                'npsh': npsh_arr.tolist(),
                'bep': bep_dict,
                'color': c.get('color'),
                'use_custom_style': c_use_custom,
                'style_mode': 'custom' if c_use_custom else 'graph',
                'weight': c.get('weight'),
                'style': c.get('style')
            }

        def _make_affinity():
            fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
            penalty = 0.0 if fam_type == 'variable_speed' else trim_penalty_coeff * (1.0 - r)
            eta_trimmed = np.clip(eta_base - penalty, 0, 100)
            use_custom = False
            c_color = None
            c_weight = None
            c_style = None

            if d == d_max:
                main_style = getattr(pump, 'main_curve_style', 'graph') or 'graph'
                if main_style.startswith('custom;'):
                    use_custom = True
                    parts = main_style.split(';')
                    if len(parts) >= 2:
                        c_color = parts[1].strip()
                    if len(parts) >= 3:
                        sub = parts[2].split(',')
                        try: c_weight = float(sub[0].strip())
                        except Exception: pass
                        if len(sub) >= 2: c_style = sub[1].strip()
            elif matched_extra:
                use_custom = matched_extra.get('use_custom_style', False) or (matched_extra.get('style_mode') == 'custom')
                c_color = matched_extra.get('color')
                c_weight = matched_extra.get('weight')
                c_style = matched_extra.get('style')

            return {
                'dia': d,
                'is_max': d == d_max,
                'ratio': round(r, 4),
                'curve_mode': 'affinity',
                'q': (q_base * r).tolist(),
                'h': (h_base * r ** 2).tolist(),
                'eta': eta_trimmed.tolist(),
                'power': (pwr_base * r ** 3).tolist(),
                'npsh': (npsh_base * r ** 2).tolist(),
                'bep': _bep_for_ratio(pump, r, h_base, eta_base, pwr_base, q_base, trim_penalty_coeff),
                'color': c_color,
                'use_custom_style': use_custom,
                'style_mode': 'custom' if use_custom else 'graph',
                'weight': c_weight,
                'style': c_style
            }

        if eff_mode == 'both' and can_fit:
            family.append(_make_fitted())
            aff_item = _make_affinity()
            aff_item['label_tag'] = ' (Affinity)'
            family.append(aff_item)
        elif eff_mode == 'fit' and can_fit:
            family.append(_make_fitted())
        else:
            family.append(_make_affinity())

    return family


def _bep_for_ratio(pump, ratio, h_base, eta_base, pwr_base, q_base, trim_penalty_coeff=20.0):
    """BEP at a given impeller trim ratio."""
    idx = int(np.argmax(eta_base))
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    penalty = 0.0 if fam_type == 'variable_speed' else trim_penalty_coeff * (1.0 - ratio)
    return {
        'q': round(float(q_base[idx]) * ratio, 2),
        'h': round(float(h_base[idx]) * ratio ** 2, 2),
        'eta': round(float(eta_base[idx]) - penalty, 2),
        'power': round(float(pwr_base[idx]) * ratio ** 3, 2),
    }


# Warman-style efficiency isolines

def efficiency_isolines(pump, liquid='water', viscosity_cSt=1.0,
                        slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                        iso_levels=None, n_ratio_steps=100, n_base=400,
                        trim_penalty=None, override_r_min=None,
                        override_trim_penalty=None):
    """
    Generate smooth, parabolic Warman-style efficiency isolines across the pump operating envelope.

    Scans a dense 2D grid (Q, ratio) to produce smooth continuous U-loops for closed
    efficiency contours, and smooth continuous rays for open efficiency contours.

    Args:
        override_r_min: When set, overrides the computed minimum ratio (e.g. from RPM overlay range).
        override_trim_penalty: When set, forces a specific trim penalty coefficient
                               (use 0 for RPM-based isolines on trimmed impeller pumps).
    """
    diameters = pump.get_diameters()
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    if override_r_min is not None:
        r_min = override_r_min
    elif diameters and len(diameters) >= 2 and max(diameters) > min(diameters):
        d_max = max(diameters)
        d_min = min(diameters)
        r_min = d_min / d_max if d_max > 0 else 0.70
    else:
        d_max = max(diameters) if diameters else (pump.speed_rpm if fam_type == 'variable_speed' else (pump.impeller_dia_mm or 300.0))
        d_min = d_max * 0.70
        r_min = 0.70

    q_base = np.linspace(pump.q_min or 0.01, pump.q_max, n_base)
    h_base   = hq_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta_base = efficiency_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    valid = (h_base > 0) & (eta_base > 0)
    if not np.any(valid):
        return []

    q_v = q_base[valid]
    h_v = h_base[valid]
    eta_v = eta_base[valid]

    eta_max = float(np.max(eta_v))
    bep_idx = int(np.argmax(eta_v))
    bep_q = float(q_v[bep_idx])
    bep_h = float(h_v[bep_idx])

    # Calculate dynamic trim penalty coefficient
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    if override_trim_penalty is not None:
        try: trim_penalty_coeff = float(override_trim_penalty)
        except (ValueError, TypeError): trim_penalty_coeff = 0.0
    elif fam_type == 'variable_speed':
        trim_penalty_coeff = 0.0
    elif trim_penalty is not None:
        try: trim_penalty_coeff = float(trim_penalty)
        except (ValueError, TypeError): trim_penalty_coeff = 20.0
    elif getattr(pump, 'graph_trim_penalty', None) is not None:
        try: trim_penalty_coeff = float(pump.graph_trim_penalty)
        except (ValueError, TypeError): trim_penalty_coeff = 20.0
    else:
        extra_curves = pump.get_extra_curves()
        min_eta = None
        min_r = None
        for c in extra_curves:
            raw_t = c.get('raw_table', [])
            d_val = c.get('diameter')
            if raw_t and d_val:
                try:
                    u = c.get('unit_dia', 'mm')
                    d_mm = float(d_val) * (25.4 if u == 'in' else (1000.0 if u == 'm' else 1.0))
                    r_c = d_mm / d_max
                    etas = [float(row[2]) for row in raw_t if isinstance(row, list) and len(row) >= 3 and row[2] != '' and row[2] is not None]
                    if etas:
                        max_e = max(etas)
                        if min_r is None or r_c < min_r:
                            min_r = r_c
                            min_eta = max_e
                except (ValueError, TypeError):
                    pass
        if min_eta is not None and min_r is not None and min_r < 0.99 and eta_max > min_eta:
            calc_coeff = (eta_max - min_eta) / (1.0 - min_r)
            trim_penalty_coeff = max(5.0, min(calc_coeff, 22.0))
        else:
            trim_penalty_coeff = 20.0

    if not iso_levels:
        lo = max(20, int((eta_max * 0.40) // 5) * 5)
        hi = int(eta_max // 5) * 5
        iso_levels = [float(x) for x in range(lo, hi, 5)]
        if eta_max - hi >= 1.5:
            iso_levels.append(round(eta_max, 1))

    ratios = np.linspace(1.0, r_min, n_ratio_steps)
    isolines = []

    for eta_t in iso_levels:
        # BEP marker
        is_bep = abs(eta_t - eta_max) < 0.5 or eta_t >= eta_max
        if is_bep:
            ratios_line = np.linspace(1.0, r_min, 40)
            isolines.append({
                'eta': round(eta_max, 1),
                'q': (bep_q * ratios_line).tolist(),
                'h': (bep_h * ratios_line ** 2).tolist(),
                'label_q': round(bep_q, 2),
                'label_h': round(bep_h, 2),
                'label_text': "BEP " + str(round(eta_max)) + "%",
                'is_closed': False
            })
            continue

        left_pts = []   # (Q, H, r)
        right_pts = []  # (Q, H, r)

        for r in ratios:
            eta_r = eta_v - trim_penalty_coeff * (1.0 - r)

            # Left crossing (Q < BEP)
            diff_l = eta_r[:bep_idx + 1] - eta_t
            for i in range(len(diff_l) - 1):
                if diff_l[i] * diff_l[i + 1] <= 0:
                    denom = diff_l[i + 1] - diff_l[i]
                    t = (0 - diff_l[i]) / denom if denom != 0 else 0.5
                    q_c = float(q_v[i] + t * (q_v[i + 1] - q_v[i]))
                    h_c = float(h_v[i] + t * (h_v[i + 1] - h_v[i]))
                    left_pts.append((q_c * r, h_c * (r ** 2), r))
                    break

            # Right crossing (Q > BEP)
            diff_r = eta_r[bep_idx:] - eta_t
            for i in range(len(diff_r) - 1):
                if diff_r[i] * diff_r[i + 1] <= 0:
                    denom = diff_r[i + 1] - diff_r[i]
                    t = (0 - diff_r[i]) / denom if denom != 0 else 0.5
                    idx = bep_idx + i
                    q_c = float(q_v[idx] + t * (q_v[idx + 1] - q_v[idx]))
                    h_c = float(h_v[idx] + t * (h_v[idx + 1] - h_v[idx]))
                    right_pts.append((q_c * r, h_c * (r ** 2), r))
                    break

        if not left_pts and not right_pts:
            continue

        r_deepest_l = left_pts[-1][2] if left_pts else 1.0
        r_deepest_r = right_pts[-1][2] if right_pts else 1.0
        r_deepest = min(r_deepest_l, r_deepest_r)

        # Closed loop forms if the isoline closes BEFORE reaching the min diameter
        is_closed = (r_deepest > r_min + 0.005) and len(left_pts) >= 2 and len(right_pts) >= 2

        if is_closed:
            # U-loop: path goes down left branch, across parabolic bottom arc, up right branch
            q_l_bot, h_l_bot = left_pts[-1][0], left_pts[-1][1]
            q_r_bot, h_r_bot = right_pts[-1][0], right_pts[-1][1]

            n_arc = 14
            bottom_arc_q = []
            bottom_arc_h = []
            for k in range(1, n_arc):
                t = k / float(n_arc)
                q_arc = q_l_bot + t * (q_r_bot - q_l_bot)
                # Smooth parabolic dip at bottom vertex
                h_arc = h_l_bot + t * (h_r_bot - h_l_bot) - 0.3 * (1.0 - (2.0 * t - 1.0) ** 2)
                bottom_arc_q.append(q_arc)
                bottom_arc_h.append(h_arc)

            loop_q = [p[0] for p in left_pts] + bottom_arc_q + [p[0] for p in reversed(right_pts)]
            loop_h = [p[1] for p in left_pts] + bottom_arc_h + [p[1] for p in reversed(right_pts)]

            isolines.append({
                'eta': eta_t,
                'q': loop_q, 'h': loop_h,
                'label_q': round(left_pts[0][0], 2),
                'label_h': round(left_pts[0][1], 2),
                'label_text': str(round(eta_t)) + "%",
                'is_closed': True
            })
        else:
            # Open branches: isoline extends down to the minimum diameter
            if len(left_pts) >= 2:
                l_q = [p[0] for p in left_pts]
                l_h = [p[1] for p in left_pts]
                isolines.append({
                    'eta': eta_t,
                    'branch': 'left',
                    'q': l_q, 'h': l_h,
                    'label_q': round(l_q[0], 2),
                    'label_h': round(l_h[0], 2),
                    'label_text': str(round(eta_t)) + "%",
                    'is_closed': False
                })
            if len(right_pts) >= 2:
                r_q = [p[0] for p in right_pts]
                r_h = [p[1] for p in right_pts]
                isolines.append({
                    'eta': eta_t,
                    'branch': 'right',
                    'q': r_q, 'h': r_h,
                    'label_q': round(r_q[0], 2),
                    'label_h': round(r_h[0], 2),
                    'label_text': str(round(eta_t)) + "%",
                    'is_closed': False
                })

    return isolines



# ── Power isolines (constant power lines) ─────────────────────────────────────

def power_isolines(pump, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                   slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                   n_power_lines=5, n_ratio_steps=40, n_base=1000,
                   power_levels=None, override_r_min=None):
    """Constant shaft-power lines across the H-Q family.

    Args:
        override_r_min: When set, overrides the computed minimum ratio (e.g. from RPM overlay range).
    """
    diameters = pump.get_diameters()
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    if override_r_min is not None:
        r_min = override_r_min
    elif diameters and len(diameters) >= 2 and max(diameters) > min(diameters):
        d_max = max(diameters)
        d_min = min(diameters)
        r_min = d_min / d_max if d_max > 0 else 0.70
    else:
        d_max = max(diameters) if diameters else (pump.speed_rpm if fam_type == 'variable_speed' else (pump.impeller_dia_mm or 300.0))
        d_min = d_max * 0.70
        r_min = 0.70

    ratios = np.linspace(r_min, 1.0, n_ratio_steps)

    q_base = np.linspace(pump.q_min or 0.01, pump.q_max, n_base)
    pwr_max_arr = power_curve(pump, q_base, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    p_max_base = float(np.max(pwr_max_arr))

    if power_levels:
        p_levels = power_levels
    else:
        p_levels = np.linspace(p_max_base * 0.2, p_max_base * 0.95, n_power_lines)

    pwr_lines = []
    for p_target in p_levels:
        pts_q, pts_h = [], []
        for r in ratios:
            p_base_target = p_target / r ** 3
            pwr_base_arr = power_curve(pump, q_base, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
            diffs = pwr_base_arr - p_base_target
            for i in range(len(diffs) - 1):
                if diffs[i] * diffs[i + 1] < 0:
                    t = diffs[i] / (diffs[i] - diffs[i + 1])
                    q_b = float(q_base[i] + t * (q_base[i + 1] - q_base[i]))
                    h_b_arr = hq_curve(pump, np.array([q_b]), liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
                    h_b = float(h_b_arr[0])
                    pts_q.append(q_b * r)
                    pts_h.append(h_b * r ** 2)
                    break

        if len(pts_q) >= 2:
            pwr_lines.append({
                'power': round(float(p_target), 1),
                'q': pts_q,
                'h': pts_h,
            })

    return pwr_lines


# ── NPSH isolines (constant NPSHr lines) ──────────────────────────────────────

def npsh_isolines(pump, liquid='water', viscosity_cSt=1.0,
                  slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                  iso_levels=None, n_ratio_steps=40, n_base=1000,
                  override_r_min=None):
    """Constant NPSHr lines across the H-Q family.

    Args:
        override_r_min: When set, overrides the computed minimum ratio (e.g. from RPM overlay range).
    """
    diameters = pump.get_diameters()
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    if override_r_min is not None:
        r_min = override_r_min
    elif diameters and len(diameters) >= 2 and max(diameters) > min(diameters):
        d_max = max(diameters)
        d_min = min(diameters)
        r_min = d_min / d_max if d_max > 0 else 0.70
    else:
        d_max = max(diameters) if diameters else (pump.speed_rpm if fam_type == 'variable_speed' else (pump.impeller_dia_mm or 300.0))
        d_min = d_max * 0.70
        r_min = 0.70

    ratios = np.linspace(r_min, 1.0, n_ratio_steps)

    q_base = np.linspace(pump.q_min or 0.01, pump.q_max, n_base)
    npsh_base_arr = npsh_curve(pump, q_base)
    npsh_max_val = float(np.max(npsh_base_arr))

    if not iso_levels:
        iso_levels = np.linspace(npsh_max_val * 0.2, npsh_max_val * 0.95, 5).tolist()

    npsh_lines = []
    for npsh_target in iso_levels:
        pts_q, pts_h = [], []
        for r in ratios:
            if r <= 0:
                continue
            npsh_base_target = npsh_target / r ** 2
            diffs = npsh_base_arr - npsh_base_target
            # Search from right to left to get the high-flow crossing on the rising branch
            for i in range(len(diffs) - 2, -1, -1):
                if diffs[i] * diffs[i + 1] < 0:
                    t = diffs[i] / (diffs[i] - diffs[i + 1])
                    q_b = float(q_base[i] + t * (q_base[i + 1] - q_base[i]))
                    h_b_arr = hq_curve(pump, np.array([q_b]), liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
                    h_b = float(h_b_arr[0])
                    pts_q.append(q_b * r)
                    pts_h.append(h_b * r ** 2)
                    break

        if len(pts_q) >= 2:
            sorted_pts = sorted(zip(pts_q, pts_h), key=lambda x: x[0])
            npsh_lines.append({
                'npsh': round(float(npsh_target), 2),
                'q': [p[0] for p in sorted_pts],
                'h': [p[1] for p in sorted_pts],
            })

    return npsh_lines


# ── Full Warman performance map data ──────────────────────────────────────────

def speed_lines(pump, ratios=(0.70, 0.80, 0.90, 1.00), values_str=None, n_points=100,
                liquid='water', viscosity_cSt=1.0,
                slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    """
    H-Q overlay lines using affinity laws:
    - Variable Speed Mode: generates speed RPM curves (from user values or % of rated speed)
    - Trimmed Impeller Mode: generates trimmed impeller curves (from user values or % of max diameter)
    """
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    is_var_speed = (fam_type == 'variable_speed')

    parsed_items = []
    if values_str and isinstance(values_str, str) and values_str.strip():
        cleaned_str = re.sub(r'[,;\s]+', ',', values_str.strip())
        parts = [p.strip() for p in cleaned_str.split(',') if p.strip()]
        for p in parts:
            try:
                parsed_items.append(float(p))
            except ValueError:
                pass

    d_max = pump.impeller_dia_mm if (pump.impeller_dia_mm and pump.impeller_dia_mm > 0) else 300.0
    rpm_max = pump.speed_rpm if (pump.speed_rpm and pump.speed_rpm > 0) else 1450.0
    if parsed_items and max(parsed_items) > rpm_max:
        rpm_max = max(parsed_items)

    items_to_process = []
    if parsed_items:
        for rpm in parsed_items:
            k = rpm / rpm_max if rpm_max > 0 else 1.0
            rpm_fmt = f"{int(round(rpm))}" if abs(rpm - round(rpm)) < 1e-4 else f"{rpm:g}"
            items_to_process.append((k, rpm, f"{rpm_fmt} RPM ({round(k * 100)}%)"))
    else:
        for k in ratios:
            rpm_val = round(rpm_max * k)
            items_to_process.append((k, rpm_val, f"{rpm_val} RPM ({round(k * 100)}%)"))

    q_base = np.linspace(0, pump.q_max or 100.0, n_points)
    H_base = hq_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta_base = efficiency_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    pwr_base = power_curve(pump, q_base, liquid, 1000.0, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    npsh_base = npsh_curve(pump, q_base)

    result = []
    for k, val, label in items_to_process:
        Q_k = q_base * k
        H_k = np.clip(H_base * (k ** 2), 0, None)
        P_k = np.clip(pwr_base * (k ** 3), 0, None)
        NPSH_k = np.clip(npsh_base * (k ** 2), 0, None)
        eta_k = np.clip(eta_base, 0, 100)

        bep_idx = int(np.argmax(eta_k[:int(n_points * 0.95)])) if len(eta_k) > 0 else 0

        result.append({
            'dia': (pump.impeller_dia_mm or 300.0) if is_var_speed else val,
            'rpm': val if is_var_speed else (pump.speed_rpm or 1450.0),
            'ratio': round(float(k), 4),
            'label': label,
            'q': [round(v, 3) for v in Q_k.tolist()],
            'h': [round(v, 3) for v in H_k.tolist()],
            'eta': [round(v, 2) for v in eta_k.tolist()],
            'pow': [round(v, 3) for v in P_k.tolist()],
            'npsh': [round(v, 3) for v in NPSH_k.tolist()],
            'bep_q': round(float(Q_k[bep_idx]), 2) if len(Q_k) > bep_idx else 0.0,
            'bep_h': round(float(H_k[bep_idx]), 2) if len(H_k) > bep_idx else 0.0,
            'bep_eta': round(float(eta_k[bep_idx]), 2) if len(eta_k) > bep_idx else 0.0,
        })
    return result


def _compute_iso_override(pump, show_rpm_overlay=False, show_dia_overlay=False):
    """Determine isoline override parameters based on test basis and active overlays.

    Returns (override_r_min, override_trim_penalty) — both None if no override needed.

    Rules:
        Trimmed Impeller: isolines follow diameter (default). Switch to RPM only when
                          RPM overlay is ON and diameter overlay is OFF.
        Variable Speed:   isolines follow RPM (default). Switch to diameter only when
                          diameter overlay is ON and RPM overlay is OFF.
    """
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    is_var_speed = (fam_type == 'variable_speed')

    if is_var_speed and show_dia_overlay and not show_rpm_overlay:
        # Variable speed pump showing only diameter overlay → isolines based on diameter ratios
        dia_str = (getattr(pump, 'graph_dia_overlay_values', '') or '').strip()
        if dia_str:
            parsed = []
            cleaned = re.sub(r'[,;\s]+', ',', dia_str)
            for p in cleaned.split(','):
                p = p.strip()
                if p:
                    try: parsed.append(float(p))
                    except ValueError: pass
            if parsed:
                d_max_imp = pump.impeller_dia_mm or 300.0
                d_max = max(max(parsed), d_max_imp)
                d_min = min(parsed)
                r_min = d_min / d_max if d_max > 0 else 0.70
                # Diameter-based isolines on a variable speed pump use a trim penalty
                return r_min, 20.0
        return None, None

    elif not is_var_speed and show_rpm_overlay and not show_dia_overlay:
        # Trimmed impeller pump showing only RPM overlay → isolines based on RPM ratios
        rpm_str = (getattr(pump, 'graph_rpm_values', '') or
                   getattr(pump, 'graph_speed_line_values', '') or '').strip()
        if rpm_str:
            parsed = []
            cleaned = re.sub(r'[,;\s]+', ',', rpm_str)
            for p in cleaned.split(','):
                p = p.strip()
                if p:
                    try: parsed.append(float(p))
                    except ValueError: pass
            if parsed:
                rpm_max = pump.speed_rpm or 1450.0
                if max(parsed) > rpm_max:
                    rpm_max = max(parsed)
                rpm_min = min(parsed)
                r_min = rpm_min / rpm_max if rpm_max > 0 else 0.70
                # RPM-based isolines have no trim penalty (speed change, not diameter trim)
                return r_min, 0.0
        return None, None

    # Default: no override needed — isolines follow the pump's primary family type
    return None, None


def warman_chart_data(pump, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                      slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                      eff_levels=None, power_levels=None, npsh_levels=None,
                      force_affinity=False, trim_penalty=None,
                      show_rpm_overlay=False, show_dia_overlay=False):
    """Return everything needed to render a Warman performance map."""
    family   = family_curves_diameter(pump, n_points=100, liquid=liquid, rho=rho,
                                      viscosity_cSt=viscosity_cSt, slurry_cv=slurry_cv,
                                      slurry_d50=slurry_d50, rho_solid=rho_solid,
                                      force_affinity=force_affinity, trim_penalty=trim_penalty)

    # Determine isoline override based on test basis + active overlay combination
    iso_r_min, iso_trim = _compute_iso_override(pump, show_rpm_overlay, show_dia_overlay)

    isolines = efficiency_isolines(pump, liquid=liquid, viscosity_cSt=viscosity_cSt,
                                   slurry_cv=slurry_cv, slurry_d50=slurry_d50,
                                   rho_solid=rho_solid, iso_levels=eff_levels,
                                   trim_penalty=trim_penalty,
                                   override_r_min=iso_r_min,
                                   override_trim_penalty=iso_trim)
    pwr_iso  = power_isolines(pump, liquid=liquid, rho=rho, viscosity_cSt=viscosity_cSt,
                              slurry_cv=slurry_cv, slurry_d50=slurry_d50, rho_solid=rho_solid,
                              power_levels=power_levels, override_r_min=iso_r_min)
    npsh_iso = npsh_isolines(pump, liquid=liquid, viscosity_cSt=viscosity_cSt,
                             slurry_cv=slurry_cv, slurry_d50=slurry_d50,
                             rho_solid=rho_solid, iso_levels=npsh_levels,
                             override_r_min=iso_r_min)
    bep_max  = bep_point(pump, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    # RPM overlay lines (uses graph_rpm_values — always RPM values)
    rpm_vals_str = getattr(pump, 'graph_rpm_values', '') or ''
    # Backward compat: if no new rpm_values, fall back to old graph_speed_line_values
    if not rpm_vals_str.strip():
        rpm_vals_str = getattr(pump, 'graph_speed_line_values', '') or ''
    rpm_overlay = speed_lines(pump, ratios=(0.70, 0.80, 0.90, 1.00), values_str=rpm_vals_str,
                              liquid=liquid, viscosity_cSt=viscosity_cSt,
                              slurry_cv=slurry_cv, slurry_d50=slurry_d50, rho_solid=rho_solid)

    # Diameter overlay lines (uses graph_dia_overlay_values — always diameter mm values)
    dia_vals_str = getattr(pump, 'graph_dia_overlay_values', '') or ''
    dia_overlay = _dia_overlay_lines(pump, dia_vals_str, n_points=100,
                                      liquid=liquid, viscosity_cSt=viscosity_cSt,
                                      slurry_cv=slurry_cv, slurry_d50=slurry_d50, rho_solid=rho_solid)

    # Compute default calculated trim penalty coeff for UI placeholder display
    dias = pump.get_diameters()
    d_max = max(dias) if dias else (pump.impeller_dia_mm or 300.0)
    fam_t = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    if fam_t == 'variable_speed':
        default_trim_penalty = 0.0
    else:
        extra_c = pump.get_extra_curves()
        min_eta = None
        min_r = None
        for c in extra_c:
            raw_t = c.get('raw_table', [])
            d_val = c.get('diameter')
            if raw_t and d_val:
                try:
                    u = c.get('unit_dia', 'mm')
                    d_mm = float(d_val) * (25.4 if u == 'in' else (1000.0 if u == 'm' else 1.0))
                    r_c = d_mm / d_max
                    etas = [float(row[2]) for row in raw_t if isinstance(row, list) and len(row) >= 3 and row[2] != '' and row[2] is not None]
                    if etas:
                        max_e = max(etas)
                        if min_r is None or r_c < min_r:
                            min_r = r_c
                            min_eta = max_e
                except (ValueError, TypeError):
                    pass
        q_b = np.linspace(pump.q_min or 0.01, pump.q_max, 100)
        eta_b = efficiency_curve(pump, q_b, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
        eta_m = float(np.max(eta_b)) if len(eta_b) > 0 else 80.0
        if min_eta is not None and min_r is not None and min_r < 0.99 and eta_m > min_eta:
            calc_coeff = (eta_m - min_eta) / (1.0 - min_r)
            default_trim_penalty = round(max(5.0, min(calc_coeff, 22.0)), 1)
        else:
            default_trim_penalty = 20.0

    return {
        'pump': pump.to_dict(),
        'family': family,
        'isolines': isolines,
        'power_isolines': pwr_iso,
        'npsh_isolines': npsh_iso,
        'speed_lines': rpm_overlay,      # backward compat key
        'rpm_overlay': rpm_overlay,
        'dia_overlay': dia_overlay,
        'bep': bep_max,
        'liquid': liquid,
        'default_trim_penalty': default_trim_penalty,
    }


def _dia_overlay_lines(pump, values_str, n_points=100,
                       liquid='water', viscosity_cSt=1.0,
                       slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    """Generate diameter-based overlay curves (Ø mm labels) using affinity laws."""
    parsed = []
    if values_str and isinstance(values_str, str) and values_str.strip():
        cleaned = re.sub(r'[,;\s]+', ',', values_str.strip())
        for p in cleaned.split(','):
            p = p.strip()
            if p:
                try:
                    parsed.append(float(p))
                except ValueError:
                    pass
    if not parsed:
        return []

    d_max = max(parsed) if parsed else (pump.impeller_dia_mm or 300.0)
    if pump.impeller_dia_mm and pump.impeller_dia_mm > d_max:
        d_max = pump.impeller_dia_mm

    q_base = np.linspace(0, pump.q_max or 100.0, n_points)
    H_base = hq_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta_base = efficiency_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    pwr_base = power_curve(pump, q_base, liquid, 1000.0, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    npsh_base = npsh_curve(pump, q_base)

    result = []
    for d in parsed:
        k = d / d_max if d_max > 0 else 1.0
        Q_k = q_base * k
        H_k = np.clip(H_base * (k ** 2), 0, None)
        P_k = np.clip(pwr_base * (k ** 3), 0, None)
        NPSH_k = np.clip(npsh_base * (k ** 2), 0, None)
        eta_k = np.clip(eta_base, 0, 100)

        d_fmt = f"{int(round(d))}" if abs(d - round(d)) < 1e-4 else f"{d:g}"
        label = f"Ø{d_fmt} mm ({round(k * 100)}%)"

        result.append({
            'dia': d,
            'ratio': round(float(k), 4),
            'label': label,
            'q': [round(v, 3) for v in Q_k.tolist()],
            'h': [round(v, 3) for v in H_k.tolist()],
            'eta': [round(v, 2) for v in eta_k.tolist()],
            'pow': [round(v, 3) for v in P_k.tolist()],
            'npsh': [round(v, 3) for v in NPSH_k.tolist()],
        })
    return result


# ── Polynomial curve fitting from data points ──────────────────────────────────

def fit_pump_polynomials(q_h, q_eta, q_npsh=None, q_p=None, rho=1000.0, poly_order=3, poly_order_hq=None, poly_order_eff=None, poly_order_npsh=None, poly_order_pow=None):
    """
    Fit polynomial performance curves from user-provided data points.

    Beginners Note:
      Allows independent polynomial fitting orders for each curve:
        - poly_order_hq   (Head H-Q curve, 1 to 5, default 3)
        - poly_order_eff  (Efficiency curve, 1 to 5, default 3)
        - poly_order_npsh (NPSHr curve, 1 to 5, default 2)
        - poly_order_pow  (Power curve, 1 to 5, default 2)
    """
    if len(q_h) < 2 or len(q_eta) < 2:
        raise ValueError("At least 2 data points required for curve fitting.")

    q_h   = np.array(q_h,   dtype=float)
    q_eta = np.array(q_eta, dtype=float)

    q_hq_pts  = q_h[:, 0]
    h_pts     = q_h[:, 1]
    q_eta_pts = q_eta[:, 0]
    eta_pts   = q_eta[:, 1]

    # Beginners Note: Validate and bound per-curve fitting degrees by available points - 1
    def_o = int(poly_order) if poly_order and 1 <= int(poly_order) <= 5 else 3
    deg_hq_target   = int(poly_order_hq) if poly_order_hq and 1 <= int(poly_order_hq) <= 5 else def_o
    deg_eff_target  = int(poly_order_eff) if poly_order_eff and 1 <= int(poly_order_eff) <= 5 else def_o
    deg_npsh_target = int(poly_order_npsh) if poly_order_npsh and 1 <= int(poly_order_npsh) <= 5 else min(2, def_o)
    deg_pow_target  = int(poly_order_pow) if poly_order_pow and 1 <= int(poly_order_pow) <= 5 else min(2, def_o)

    deg_hq  = min(deg_hq_target, max(1, len(q_hq_pts) - 1))
    deg_eta = min(deg_eff_target, max(1, len(q_eta_pts) - 1))

    # ── H-Q polynomial ──
    c_hq = np.polyfit(q_hq_pts, h_pts, deg_hq)
    # np.polyfit returns highest-degree first → reverse to [a0, a1, a2, a3, ...]
    a = [float(v) for v in reversed(c_hq)]

    # ── Efficiency polynomial ──
    c_eta = np.polyfit(q_eta_pts, eta_pts, deg_eta)
    b = [float(v) for v in reversed(c_eta)]

    # ── Derive Q_max (where H→0) and Q_BEP (peak η) ──
    q_dense = np.linspace(0, max(q_hq_pts) * 1.1, 500)
    H_dense = np.clip(_poly_array(a, q_dense), 0, None)
    eta_dense = _poly_array(b, q_dense)

    q_max_fit = float(max(q_hq_pts))
    for i in range(len(H_dense) - 1):
        if H_dense[i] > 0 and H_dense[i + 1] <= 0:
            q_max_fit = float(q_dense[i])
            break

    eta_dense_clipped = np.clip(eta_dense, 0, 100)
    bep_idx = int(np.argmax(eta_dense_clipped[:int(len(q_dense) * 0.95)]))
    q_bep_fit = float(q_dense[bep_idx])
    h_bep_fit = float(H_dense[bep_idx])
    eta_bep_fit = float(eta_dense_clipped[bep_idx])

    # ── NPSH polynomial ──
    npsh_c = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    if q_npsh and len(q_npsh) >= 2:
        q_npsh_arr = np.array(q_npsh, dtype=float)
        if np.max(q_npsh_arr[:, 1]) > 1e-3:
            deg_npsh = min(deg_npsh_target, max(1, len(q_npsh_arr) - 1))
            c_npsh = np.polyfit(q_npsh_arr[:, 0], q_npsh_arr[:, 1], deg_npsh)
            npsh_c = ([float(v) for v in reversed(c_npsh)] + [0.0] * 6)[:6]

    # ── Power polynomial ──
    p_pad = _fit_power_from_data(
        q_p, a, b, q_bep_fit, h_bep_fit, eta_bep_fit, q_max_fit, rho, deg_pow_target)

    # ── R² quality metrics ──
    h_pred = _poly_array(a, q_hq_pts)
    r2_hq  = _r2(h_pts, h_pred)
    eta_pred = _poly_array(b, q_eta_pts)
    r2_eta  = _r2(eta_pts, eta_pred)

    # Output standard a0..a5 & b0..b5 (padded to 6 terms)
    a_pad = (a + [0.0] * 6)[:6]
    b_pad = (b + [0.0] * 6)[:6]

    return {
        'poly_order': def_o,
        'poly_order_hq': deg_hq_target,
        'poly_order_eff': deg_eff_target,
        'poly_order_npsh': deg_npsh_target,
        'poly_order_pow': deg_pow_target if poly_order_pow else 2,
        'hq_a0': round(a_pad[0], 6), 'hq_a1': round(a_pad[1], 8),
        'hq_a2': round(a_pad[2], 10), 'hq_a3': round(a_pad[3], 12),
        'hq_a4': round(a_pad[4], 14), 'hq_a5': round(a_pad[5], 16),
        'eff_b0': round(b_pad[0], 6), 'eff_b1': round(b_pad[1], 8),
        'eff_b2': round(b_pad[2], 10), 'eff_b3': round(b_pad[3], 12),
        'eff_b4': round(b_pad[4], 14), 'eff_b5': round(b_pad[5], 16),
        'npsh_c0': round(npsh_c[0], 6), 'npsh_c1': round(npsh_c[1], 8),
        'npsh_c2': round(npsh_c[2], 10), 'npsh_c3': round(npsh_c[3], 12),
        'npsh_c4': round(npsh_c[4], 14), 'npsh_c5': round(npsh_c[5], 16),
        'pow_p0': round(p_pad[0], 4), 'pow_p1': round(p_pad[1], 6),
        'pow_p2': round(p_pad[2], 8), 'pow_p3': round(p_pad[3], 10),
        'pow_p4': round(p_pad[4], 12), 'pow_p5': round(p_pad[5], 14),
        'q_max': round(q_max_fit, 2),
        'q_bep': round(q_bep_fit, 2),
        'h_shutoff': round(a_pad[0], 2),
        'eta_bep': round(eta_bep_fit, 1),
        'r2_hq': round(r2_hq, 4),
        'r2_eta': round(r2_eta, 4),
    }


def _fit_power_from_data(q_p, hq_coeffs, eff_coeffs, q_bep, h_bep, eta_bep, q_max, rho, deg_pow_target=2):
    """
    Fit a power quadratic P = p0 + p1*Q + p2*Q² using three exact anchor points:

      Q=0       → P_shutoff = 0.35 · P_BEP   (disc-friction estimate)
      Q=Q_BEP   → P_BEP     = ρgH_BEP·Q_BEP/η_BEP
      Q=Q_max   → P_runout  = 1.10 · P_BEP   (typical centrifugal runout)

    This guarantees a smooth, physically rising curve without singularity issues.
    User-supplied Q-P pairs (≥2 points) override the derived anchors.
    """
    if eta_bep <= 0:
        return [0.0] * 6

    P_bep = rho * G * h_bep * (q_bep / 3600.0) / (eta_bep / 100.0) / 1000.0

    if q_p and len(q_p) >= 2:
        q_p_arr = np.array(q_p, dtype=float)
        deg_pow = min(deg_pow_target, max(1, len(q_p_arr) - 1))
        c = np.polyfit(q_p_arr[:, 0], q_p_arr[:, 1], deg_pow)
        return ([float(v) for v in reversed(c)] + [0.0] * 6)[:6]

    # Three-anchor exact quadratic solve
    P_shutoff = 0.35 * P_bep
    P_runout  = 1.10 * P_bep

    Q1, P1 = 0.0,   P_shutoff
    Q2, P2 = q_bep, P_bep
    Q3, P3 = q_max, P_runout

    A = np.array([
        [1.0, Q1, Q1 ** 2],
        [1.0, Q2, Q2 ** 2],
        [1.0, Q3, Q3 ** 2],
    ])
    try:
        p0, p1, p2 = np.linalg.solve(A, [P1, P2, P3])
        return [float(p0), float(p1), float(p2), 0.0, 0.0, 0.0]
    except np.linalg.LinAlgError:
        return [round(P_shutoff, 4), round((P_runout - P_shutoff) / q_max, 6), 0.0, 0.0, 0.0, 0.0]


def _r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 1.0


# ── System curve ───────────────────────────────────────────────────────────────

def system_curve_points(static_head, pipe_resistance, q_array):
    return (static_head + pipe_resistance * np.array(q_array) ** 2).tolist()


# ── Slurry / viscosity helpers ─────────────────────────────────────────────────

def _slurry_density(cv, rho_solid=2650):
    return 1000.0 * (1 - cv) + rho_solid * cv


def _slurry_factors(pump, cv, d50_mm=0.3, rho_solid=2650):
    hr = getattr(pump, 'hr', 1.0) or 1.0
    qr = getattr(pump, 'qr', 1.0) or 1.0
    er = getattr(pump, 'er', 1.0) or 1.0
    if cv > 0:
        size_f = min(1.0, d50_mm / 0.3)
        cf = cv * 10
        hr = hr * max(0.50, 1.0 - 0.030 * cf * (1 + size_f))
        qr = qr * max(0.60, 1.0 - 0.020 * cf)
        er = er * max(0.40, 1.0 - 0.050 * cf * (1 + 0.5 * size_f))
    return hr, qr, er


def _viscosity_correction(viscosity_cSt):
    log_v = np.log10(max(viscosity_cSt, 1.0))
    ch = max(0.50, 1.0 - 0.015 * log_v * (viscosity_cSt / 100) ** 0.5)
    cq = max(0.50, 1.0 - 0.010 * log_v * (viscosity_cSt / 100) ** 0.4)
    ce = max(0.20, 1.0 - 0.035 * log_v * (viscosity_cSt / 100) ** 0.6)
    return ch, cq, ce


# ── Power polynomial helper for seed / import ─────────────────────────────────

def compute_power_poly(hq_a, eff_b, q_bep, q_max, rho=1000.0):
    """
    Compute power polynomial coefficients from stored H-Q and efficiency
    polynomials.  Used by seed_data to pre-fill pow_p0/p1/p2.
    Returns (p0, p1, p2).
    """
    H_bep = float(np.clip(_poly_array(hq_a, np.array([q_bep])), 0, None)[0])
    eta_bep = float(np.clip(_poly_array(eff_b, np.array([q_bep])), 0, 100)[0])
    if eta_bep <= 0:
        return 0.0, 0.0, 0.0
    p0, p1, p2 = _fit_power_from_data(
        None, hq_a, eff_b, q_bep, H_bep, eta_bep, q_max, rho)
    return round(p0, 4), round(p1, 8), round(p2, 10)
