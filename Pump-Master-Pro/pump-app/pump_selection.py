import numpy as np
from pump_curves import (
    hq_curve, efficiency_curve, power_curve, npsh_curve,
    bep_point, operating_point, _slurry_density
)


def select_pumps(pumps, q_duty, h_duty, npsh_avail=None,
                 liquid='water', rho=1000.0, viscosity_cSt=1.0,
                 slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650,
                 tolerance=0.15):
    """
    Select pumps that can satisfy the duty point.

    Returns a list of dicts with pump info + performance at duty point.
    tolerance: allow duty point within ±(tolerance*100)% of BEP flow range.
    """
    if liquid == 'slurry':
        rho = _slurry_density(slurry_cv, rho_solid)

    results = []

    for pump in pumps:
        # Check if duty flow is within pump range
        q_lo = (pump.q_min or 0.0)
        q_hi = pump.q_max
        if q_duty < q_lo or q_duty > q_hi:
            continue

        # Evaluate H at duty flow
        q_arr = np.array([q_duty])
        h_arr = hq_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
        h_at_duty = float(h_arr[0])

        # Pump must produce head >= required head
        if h_at_duty < h_duty:
            continue

        # Check NPSH margin (require NPSHa > 1.1 * NPSHr)
        npsh_req = float(npsh_curve(pump, q_arr)[0])
        npsh_ok = True
        npsh_margin = None
        if npsh_avail is not None:
            npsh_margin = npsh_avail - npsh_req
            if npsh_avail < 1.1 * npsh_req:
                npsh_ok = False

        # Get full operating point
        op = operating_point(pump, q_duty, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

        # Get BEP
        bep = bep_point(pump, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

        # Operating ratio (how close to BEP)
        q_ratio = q_duty / bep['q'] if bep['q'] > 0 else 1.0
        in_preferred_range = 0.80 <= q_ratio <= 1.20
        in_acceptable_range = 0.65 <= q_ratio <= 1.35

        # Head surplus at duty flow
        head_surplus = h_at_duty - h_duty
        head_surplus_pct = (head_surplus / h_duty) * 100 if h_duty > 0 else 0

        # Suitability rating (0–100)
        rating = _suitability_rating(q_ratio, op['eta'], npsh_ok, head_surplus_pct)

        results.append({
            'pump_id': pump.id,
            'pump_name': pump.name,
            'manufacturer': pump.manufacturer,
            'model_number': pump.model_number,
            'size': pump.size,
            'speed_rpm': pump.speed_rpm,
            'impeller_dia_mm': pump.impeller_dia_mm,
            'op_q': op['q'],
            'op_h': op['h'],
            'op_eta': op['eta'],
            'op_power': op['power'],
            'op_npsh': npsh_req,
            'head_surplus': round(head_surplus, 2),
            'head_surplus_pct': round(head_surplus_pct, 1),
            'bep_q': bep['q'],
            'bep_h': bep['h'],
            'bep_eta': bep['eta'],
            'bep_power': bep['power'],
            'q_ratio': round(q_ratio, 3),
            'in_preferred_range': in_preferred_range,
            'in_acceptable_range': in_acceptable_range,
            'npsh_ok': npsh_ok,
            'npsh_margin': round(npsh_margin, 2) if npsh_margin is not None else None,
            'npsh_req': round(npsh_req, 2),
            'rating': rating,
            'rating_label': _rating_label(rating),
            'notes': pump.notes or '',
        })

    # Sort by rating descending
    results.sort(key=lambda x: x['rating'], reverse=True)
    return results


def _suitability_rating(q_ratio, eta, npsh_ok, head_surplus_pct):
    """Score 0–100 for pump suitability."""
    score = 0.0

    # Efficiency (max 40 pts)
    score += min(40, eta * 0.5)

    # BEP proximity (max 40 pts)
    deviation = abs(q_ratio - 1.0)
    if deviation <= 0.05:
        score += 40
    elif deviation <= 0.15:
        score += 30
    elif deviation <= 0.25:
        score += 20
    elif deviation <= 0.35:
        score += 10
    else:
        score += 0

    # NPSH (max 10 pts)
    if npsh_ok:
        score += 10

    # Head surplus (max 10 pts) — small surplus is better
    if 0 <= head_surplus_pct <= 5:
        score += 10
    elif head_surplus_pct <= 15:
        score += 7
    elif head_surplus_pct <= 30:
        score += 4
    else:
        score += 1

    return int(min(100.0, score))


def _rating_label(score):
    if score >= 80:
        return 'Excellent'
    elif score >= 65:
        return 'Good'
    elif score >= 50:
        return 'Acceptable'
    else:
        return 'Marginal'
