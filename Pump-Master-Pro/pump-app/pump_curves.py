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

G = 9.81   # m/s²


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

def _hq_raw(pump, q_array):
    """H-Q curve for max impeller, no derating. Returns clipped-positive array."""
    coeffs = [pump.hq_a0, pump.hq_a1, pump.hq_a2, pump.hq_a3]
    return np.clip(_poly_array(coeffs, q_array), 0, None)


def _eta_raw(pump, q_array):
    """Efficiency curve for max impeller, no derating (0–100%)."""
    coeffs = [pump.eff_b0, pump.eff_b1, pump.eff_b2, pump.eff_b3]
    return np.clip(_poly_array(coeffs, q_array), 0, 100)


def _npsh_raw(pump, q_array):
    """NPSHr curve for max impeller (m)."""
    coeffs = [pump.npsh_c0, pump.npsh_c1, pump.npsh_c2]
    return np.clip(_poly_array(coeffs, q_array), 0, None)


def _pow_raw(pump, q_array, scale=1.0):
    """
    Shaft power from stored polynomial (kW), scaled by `scale` for affinity laws.
    Falls back to None when no polynomial is stored.
    """
    if not pump.has_power_poly():
        return None
    coeffs = [pump.pow_p0, pump.pow_p1, pump.pow_p2]
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
                           force_affinity=False):
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
        elif force_affinity == 'fit':
            eff_mode = 'fit'
        elif matched_extra:
            eff_mode = matched_extra.get('curve_mode', 'fit')
        else:
            eff_mode = 'affinity'

        has_poly = (matched_extra is not None and matched_extra.get('hq_a0') is not None)
        can_fit  = has_poly and d != d_max

        def _make_fitted():
            c = matched_extra
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
                'color': c.get('color')
            }

        def _make_affinity():
            penalty = 40.0 * (1.0 - r)
            eta_trimmed = np.clip(eta_base - penalty, 0, 100)
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
                'bep': _bep_for_ratio(pump, r, h_base, eta_base, pwr_base, q_base),
                'color': matched_extra.get('color') if matched_extra else None
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


def _bep_for_ratio(pump, ratio, h_base, eta_base, pwr_base, q_base):
    """BEP at a given impeller trim ratio."""
    idx = int(np.argmax(eta_base))
    penalty = 40.0 * (1.0 - ratio)
    return {
        'q': round(float(q_base[idx]) * ratio, 2),
        'h': round(float(h_base[idx]) * ratio ** 2, 2),
        'eta': round(float(eta_base[idx]) - penalty, 2),
        'power': round(float(pwr_base[idx]) * ratio ** 3, 2),
    }


# ── Warman-style efficiency isolines ──────────────────────────────────────────

def efficiency_isolines(pump, liquid='water', viscosity_cSt=1.0,
                        slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                        iso_levels=None, n_ratio_steps=40, n_base=2000):
    """
    Generate closed efficiency isolines for the Warman performance map.

    Each isoline is a closed polygon on the (Q, H) plane bounding the region
    where η ≥ η_target across the full impeller-diameter family.
    """
    diameters = pump.get_diameters()
    d_max = max(diameters)
    d_min = min(diameters)
    r_min = d_min / d_max

    q_base = np.linspace(pump.q_min or 0.01, pump.q_max, n_base)
    h_base = hq_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta_base = efficiency_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    valid = h_base > 0
    q_v, h_v, eta_v = q_base[valid], h_base[valid], eta_base[valid]

    if not iso_levels:
        eta_max = float(np.max(eta_v))
        lo = max(25, int((eta_max * 0.55) // 5) * 5)
        hi = int((eta_max * 0.97) // 5) * 5
        iso_levels = list(range(lo, hi + 1, 5))

    ratios = np.linspace(r_min, 1.0, n_ratio_steps)

    isolines = []
    for eta_t in iso_levels:
        left_pts = []
        right_pts = []

        # Check at r=1.0 if the runout efficiency is below target eta_t
        # If runout efficiency is higher than eta_t, then there is no right-side crossing
        # (efficiency never drops below target in the flow range).
        diff_1 = eta_v - eta_t
        has_right_branch = (diff_1[-1] < 0)

        for r in ratios[::-1]:
            q_r = q_v * r
            h_r = h_v * r ** 2
            penalty = 40.0 * (1.0 - r)
            eta_r = np.clip(eta_v - penalty, 0, 100)

            diff = eta_r - eta_t
            crossings = []
            for i in range(len(diff) - 1):
                if diff[i] * diff[i + 1] <= 0 and not (diff[i] == 0 and diff[i + 1] == 0):
                    t = diff[i] / (diff[i] - diff[i + 1]) if (diff[i] - diff[i + 1]) != 0 else 0
                    q_c = float(q_r[i] + t * (q_r[i + 1] - q_r[i]))
                    h_c = float(h_r[i] + t * (h_r[i + 1] - h_r[i]))
                    crossings.append((q_c, h_c))

            if has_right_branch:
                if len(crossings) == 1 and diff[-1] >= 0:
                    # If right crossing is cut off by flow range, cap at runout point
                    crossings.append((float(q_r[-1]), float(h_r[-1])))

                if len(crossings) >= 2:
                    crossings.sort(key=lambda x: x[0])
                    left_pts.append(crossings[0])
                    right_pts.append(crossings[-1])
                else:
                    break
            else:
                if len(crossings) >= 1:
                    crossings.sort(key=lambda x: x[0])
                    left_pts.append(crossings[0])
                else:
                    break

        if len(left_pts) == 0:
            continue

        left_q = [p[0] for p in left_pts]
        left_h = [p[1] for p in left_pts]
        right_q = [p[0] for p in right_pts]
        right_h = [p[1] for p in right_pts]

        if not has_right_branch or len(right_q) == 0:
            # Single-crossing line running all the way down
            # Extrapolate/generate across all ratios
            q_c, h_c = left_pts[0]
            iso_q = (q_c * ratios[::-1]).tolist()
            iso_h = (h_c * ratios[::-1] ** 2).tolist()
            isolines.append({
                'eta': eta_t,
                'q': iso_q,
                'h': iso_h,
                'label_q': round(q_c, 2),
                'label_h': round(h_c, 2),
            })
            continue

        # Always return left branch and right branch as two separate lines (contour style)
        # This prevents drawing flat horizontal lines along the lowest ratio's boundary
        # which causes isolines to cross or run along head curves.
        if len(left_q) > 0:
            isolines.append({
                'eta': eta_t,
                'q': left_q,
                'h': left_h,
                'label_q': round(left_q[0], 2),
                'label_h': round(left_h[0], 2),
            })
        if len(right_q) > 0:
            isolines.append({
                'eta': eta_t,
                'q': right_q,
                'h': right_h,
                'label_q': round(right_q[0], 2),
                'label_h': round(right_h[0], 2),
            })

    return isolines


# ── Power isolines (constant power lines) ─────────────────────────────────────

def power_isolines(pump, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                   slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                   n_power_lines=5, n_ratio_steps=40, n_base=1000,
                   power_levels=None):
    """Constant shaft-power lines across the H-Q family."""
    diameters = pump.get_diameters()
    d_max = max(diameters)
    d_min = min(diameters)
    r_min = d_min / d_max

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
                  iso_levels=None, n_ratio_steps=40, n_base=1000):
    """Constant NPSHr lines across the H-Q family."""
    diameters = pump.get_diameters()
    d_max = max(diameters)
    d_min = min(diameters)
    r_min = d_min / d_max

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
            npsh_lines.append({
                'npsh': round(float(npsh_target), 2),
                'q': pts_q,
                'h': pts_h,
            })

    return npsh_lines


# ── Full Warman performance map data ──────────────────────────────────────────

def speed_lines(pump, ratios=(0.70, 0.80, 0.90, 1.00), n_points=100,
                liquid='water', viscosity_cSt=1.0,
                slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650):
    """
    H-Q curves at different speed ratios using affinity laws:
      Q_k = Q_base · k       (k = n / n_rated)
      H_k = H_base · k²
      η   ≈ constant (does not change with speed at same duty point)

    Returns a list of dicts (one per speed ratio), each containing:
      speed_ratio, speed_rpm, q[], h[], bep{q,h}
    """
    q_base = np.linspace(0, pump.q_max, n_points)
    H_base = hq_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    eta_base = efficiency_curve(pump, q_base, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    result = []
    for k in ratios:
        Q_k = q_base * k
        H_k = np.clip(H_base * k ** 2, 0, None)
        bep_idx = int(np.argmax(eta_base[:int(n_points * 0.95)]))
        result.append({
            'speed_ratio': round(float(k), 2),
            'speed_rpm':   int(round(pump.speed_rpm * k)),
            'q':   [round(float(v), 2) for v in Q_k],
            'h':   [round(float(v), 3) for v in H_k],
            'bep': {
                'q': round(float(Q_k[bep_idx]), 2),
                'h': round(float(H_k[bep_idx]), 2),
            },
        })
    return result


def warman_chart_data(pump, liquid='water', rho=1000.0, viscosity_cSt=1.0,
                      slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                      eff_levels=None, power_levels=None, npsh_levels=None,
                      force_affinity=False):
    """Return everything needed to render a Warman performance map."""
    family   = family_curves_diameter(pump, n_points=100, liquid=liquid, rho=rho,
                                      viscosity_cSt=viscosity_cSt, slurry_cv=slurry_cv,
                                      slurry_d50=slurry_d50, rho_solid=rho_solid,
                                      force_affinity=force_affinity)
    isolines = efficiency_isolines(pump, liquid=liquid, viscosity_cSt=viscosity_cSt,
                                   slurry_cv=slurry_cv, slurry_d50=slurry_d50,
                                   rho_solid=rho_solid, iso_levels=eff_levels)
    pwr_iso  = power_isolines(pump, liquid=liquid, rho=rho, viscosity_cSt=viscosity_cSt,
                              slurry_cv=slurry_cv, slurry_d50=slurry_d50, rho_solid=rho_solid,
                              power_levels=power_levels)
    npsh_iso = npsh_isolines(pump, liquid=liquid, viscosity_cSt=viscosity_cSt,
                             slurry_cv=slurry_cv, slurry_d50=slurry_d50,
                             rho_solid=rho_solid, iso_levels=npsh_levels)
    bep_max  = bep_point(pump, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    spd_lines = speed_lines(pump, ratios=(0.70, 0.80, 0.90, 1.00),
                            liquid=liquid, viscosity_cSt=viscosity_cSt,
                            slurry_cv=slurry_cv, slurry_d50=slurry_d50, rho_solid=rho_solid)

    return {
        'pump': pump.to_dict(),
        'family': family,
        'isolines': isolines,
        'power_isolines': pwr_iso,
        'npsh_isolines': npsh_iso,
        'speed_lines': spd_lines,
        'bep': bep_max,
        'liquid': liquid,
    }


# ── Polynomial curve fitting from data points ──────────────────────────────────

def fit_pump_polynomials(q_h, q_eta, q_npsh=None, q_p=None, rho=1000.0):
    """
    Fit polynomial curves from tabular performance data.

    Parameters
    ----------
    q_h   : list of [Q, H] pairs (at least 3 required)
    q_eta : list of [Q, η%] pairs (at least 3 required)
    q_npsh: list of [Q, NPSHr] pairs (optional)
    q_p   : list of [Q, P_kW] pairs (optional — overrides derived power)
    rho   : fluid density kg/m³ (for power derivation, default 1000)

    Returns
    -------
    dict with all polynomial coefficients and derived key values.
    """
    if len(q_h) < 3 or len(q_eta) < 3:
        raise ValueError("At least 3 data points required for H-Q and efficiency curves.")

    q_h   = np.array(q_h,   dtype=float)
    q_eta = np.array(q_eta, dtype=float)

    q_hq_pts  = q_h[:, 0]
    h_pts     = q_h[:, 1]
    q_eta_pts = q_eta[:, 0]
    eta_pts   = q_eta[:, 1]

    # ── H-Q polynomial (degree 2 or 3 based on point count) ──
    deg_hq = min(3, len(q_hq_pts) - 1)
    c_hq = np.polyfit(q_hq_pts, h_pts, deg_hq)
    # np.polyfit returns highest-degree first → reverse to [a0, a1, a2, a3]
    a = np.zeros(4)
    for i, v in enumerate(reversed(c_hq)):
        a[i] = v

    # ── Efficiency polynomial (degree 2 or 3) ──
    deg_eta = min(3, len(q_eta_pts) - 1)
    c_eta = np.polyfit(q_eta_pts, eta_pts, deg_eta)
    b = np.zeros(4)
    for i, v in enumerate(reversed(c_eta)):
        b[i] = v

    # ── Derive Q_max (where H→0) and Q_BEP (peak η) ──
    q_dense = np.linspace(0, max(q_hq_pts) * 1.1, 500)
    H_dense = np.clip(_poly_array(a.tolist(), q_dense), 0, None)
    eta_dense = _poly_array(b.tolist(), q_dense)

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

    # ── NPSH polynomial (degree 2) ──
    c0_npsh, c1_npsh, c2_npsh = 1.0, 0.0, 0.0
    if q_npsh and len(q_npsh) >= 2:
        q_npsh_arr = np.array(q_npsh, dtype=float)
        c_npsh = np.polyfit(q_npsh_arr[:, 0], q_npsh_arr[:, 1], min(2, len(q_npsh_arr) - 1))
        c_npsh_full = np.zeros(3)
        for i, v in enumerate(reversed(c_npsh)):
            c_npsh_full[i] = v
        c0_npsh, c1_npsh, c2_npsh = c_npsh_full[0], c_npsh_full[1], c_npsh_full[2]

    # ── Power polynomial ──
    p0, p1, p2 = _fit_power_from_data(
        q_p, a.tolist(), b.tolist(), q_bep_fit, h_bep_fit, eta_bep_fit, q_max_fit, rho)

    # ── R² quality metrics ──
    h_pred = _poly_array(a.tolist(), q_hq_pts)
    r2_hq  = _r2(h_pts, h_pred)
    eta_pred = _poly_array(b.tolist(), q_eta_pts)
    r2_eta  = _r2(eta_pts, eta_pred)

    return {
        'hq_a0': round(float(a[0]), 6), 'hq_a1': round(float(a[1]), 8),
        'hq_a2': round(float(a[2]), 10), 'hq_a3': round(float(a[3]), 12),
        'eff_b0': round(float(b[0]), 6), 'eff_b1': round(float(b[1]), 8),
        'eff_b2': round(float(b[2]), 10), 'eff_b3': round(float(b[3]), 12),
        'npsh_c0': round(c0_npsh, 6), 'npsh_c1': round(c1_npsh, 8), 'npsh_c2': round(c2_npsh, 10),
        'pow_p0': round(p0, 4), 'pow_p1': round(p1, 6), 'pow_p2': round(p2, 8),
        'q_max': round(q_max_fit, 2),
        'q_bep': round(q_bep_fit, 2),
        'h_shutoff': round(float(a[0]), 2),
        'eta_bep': round(eta_bep_fit, 1),
        'r2_hq': round(r2_hq, 4),
        'r2_eta': round(r2_eta, 4),
    }


def _fit_power_from_data(q_p, hq_coeffs, eff_coeffs, q_bep, h_bep, eta_bep, q_max, rho):
    """
    Fit a power quadratic P = p0 + p1*Q + p2*Q² using three exact anchor points:

      Q=0       → P_shutoff = 0.35 · P_BEP   (disc-friction estimate)
      Q=Q_BEP   → P_BEP     = ρgH_BEP·Q_BEP/η_BEP
      Q=Q_max   → P_runout  = 1.10 · P_BEP   (typical centrifugal runout)

    This guarantees a smooth, physically rising curve without singularity issues.
    User-supplied Q-P pairs (≥3 points) override the derived anchors.
    """
    if eta_bep <= 0:
        return 0.0, 0.0, 0.0

    P_bep = rho * G * h_bep * (q_bep / 3600.0) / (eta_bep / 100.0) / 1000.0

    if q_p and len(q_p) >= 3:
        q_p_arr = np.array(q_p, dtype=float)
        c = np.polyfit(q_p_arr[:, 0], q_p_arr[:, 1], min(2, len(q_p_arr) - 1))
        c_full = np.zeros(3)
        for i, v in enumerate(reversed(c)):
            c_full[i] = v
        return float(c_full[0]), float(c_full[1]), float(c_full[2])

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
        return float(p0), float(p1), float(p2)
    except np.linalg.LinAlgError:
        return round(P_shutoff, 4), round((P_runout - P_shutoff) / q_max, 6), 0.0


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
