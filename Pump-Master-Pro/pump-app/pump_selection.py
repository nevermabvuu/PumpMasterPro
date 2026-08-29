"""
pump_selection.py — Pump Selection Engine for shortlisting pumps that meet a target duty point.

Beginners Note:
    This module evaluates every pump in the catalogue against a user-specified duty point (Flow Q, Head H)
    and returns a ranked shortlist of pumps that can satisfy the duty, along with performance metrics,
    optimal trim/speed information, and compact chart data for inline visualisation.

Key Features:
    1. Multi-curve envelope check — evaluates across max/min impeller diameters (or speed range)
    2. Optimal trim ratio calculation — finds the diameter/speed that places the duty on the H-Q curve
    3. Pre-filtering — filter by pump type, manufacturer, speed range, application, etc.
    4. Enhanced suitability scoring — weighted rating across efficiency, BEP proximity, NPSH, trim, surplus
    5. Mini-chart data — returns compact H-Q curve arrays for sparkline rendering

Dependencies:
    - pump_curves.py: Provides polynomial evaluation, curve generation, and affinity law scaling
    - models.py: Pump ORM model with multi-curve fields and extra_curves_json
"""

import numpy as np
from pump_curves import (
    hq_curve, efficiency_curve, power_curve, npsh_curve,
    bep_point, operating_point, _slurry_density, _hq_raw
)


# ── Constants ─────────────────────────────────────────────────────────────────
# Beginners Note: Number of points for mini sparkline charts (compact H-Q envelope)
SPARKLINE_POINTS = 30


# ── Main Selection Entry Point ────────────────────────────────────────────────

def select_pumps(pumps, q_duty, h_duty, npsh_avail=None,
                 liquid='water', rho=1000.0, viscosity_cSt=1.0,
                 slurry_cv=0.0, slurry_d50=0.3, rho_solid=2650.0,
                 tolerance=0.15, filters=None, operation_mode='fixed'):
    """
    Select pumps that can satisfy the duty point.

    Beginners Note:
        This is the main function called by the route handler. It:
        1. Pre-filters pumps by user-specified criteria (type, manufacturer, speed, etc.)
        2. For each pump, checks if the duty point falls within the H-Q envelope
        3. Calculates the optimal trim/speed ratio to meet the duty exactly
        4. Scores each pump on suitability (0–100)
        5. Returns a ranked list of matching pump dicts with performance data & mini-charts

    Parameters:
        pumps: List of Pump model objects to evaluate
        q_duty: Target flow rate in m³/h
        h_duty: Target head in metres
        npsh_avail: Available NPSH at pump inlet (m), or None if not specified
        liquid: 'water', 'viscous', or 'slurry'
        rho: Liquid density in kg/m³
        viscosity_cSt: Kinematic viscosity in centistokes (for viscous liquid)
        slurry_cv: Volumetric concentration (for slurry)
        slurry_d50: Median particle size in mm (for slurry)
        rho_solid: Solid particle density in kg/m³ (for slurry)
        tolerance: Head surplus tolerance factor (not currently used for exclusion)
        filters: Dict of filter criteria (manufacturer, pump_type, speed_min, speed_max, etc.)

    Returns:
        List of dicts sorted by rating (descending), each containing pump info,
        performance metrics, trim data, and mini-chart arrays.
    """
    # Beginners Note: Calculate effective slurry density if liquid type is slurry
    if liquid == 'slurry':
        rho = _slurry_density(slurry_cv, rho_solid)

    # ── Step 1: Pre-filter pumps by non-hydraulic criteria ────────────────
    # Beginners Note: Apply user-specified filters to narrow down the pump list before
    # expensive hydraulic evaluation. This improves performance and relevance.
    filtered_pumps = _apply_filters(pumps, filters, operation_mode)

    results = []

    # ── Step 2: Evaluate each pump against the duty point ─────────────────
    for pump in filtered_pumps:
        result = _evaluate_pump(
            pump, q_duty, h_duty, npsh_avail,
            liquid, rho, viscosity_cSt,
            slurry_cv, slurry_d50, rho_solid,
            operation_mode
        )
        if result is not None:
            results.append(result)

    # ── Step 3: Sort results by suitability rating (best first) ───────────
    results.sort(key=lambda x: x['rating'], reverse=True)
    return results


# ── Pre-Filtering ─────────────────────────────────────────────────────────────

def _apply_filters(pumps, filters, operation_mode):
    """
    Apply non-hydraulic filters and operation_mode constraint to narrow down the pump list before evaluation.

    Beginners Note:
        Filters are applied in order of cheapness (string comparisons before numeric).
        Each filter is optional — if not specified, all pumps pass that criterion.

    Supported filter keys:
        - manufacturer: Comma-separated manufacturer names (OR logic)
        - pump_type: Comma-separated pump types (OR logic)
        - speed_min: Minimum speed RPM
        - speed_max: Maximum speed RPM
        - application: Comma-separated application module keys (AND logic — pump must have all)
        - size: Pump size string (partial match)
    """
    if not filters:
        return pumps

    filtered = []
    for pump in pumps:
        # Check operation mode compatibility
        if operation_mode == 'vsd' and not getattr(pump, 'selection_allow_vsd', True):
            continue
        if operation_mode == 'fixed' and not getattr(pump, 'selection_allow_fixed_speed', True):
            continue
            
        # Manufacturer filter
        if filters and filters.get('manufacturer'):
            mfr_list = [m.strip().lower() for m in filters['manufacturer'].split(',') if m.strip()]
            if mfr_list and (pump.manufacturer or '').lower() not in mfr_list:
                continue

        # Pump type filter
        if filters and filters.get('pump_type'):
            type_list = [t.strip().lower() for t in filters['pump_type'].split(',') if t.strip()]
            if type_list and (pump.pump_type or '').lower() not in type_list:
                continue

        # Speed range filter
        speed_min = filters.get('speed_min') if filters else None
        if speed_min is not None and speed_min != '':
            try:
                if pump.speed_rpm < float(speed_min):
                    continue
            except (ValueError, TypeError):
                pass

        speed_max = filters.get('speed_max') if filters else None
        if speed_max is not None and speed_max != '':
            try:
                if pump.speed_rpm > float(speed_max):
                    continue
            except (ValueError, TypeError):
                pass

        # Application module filter (pump must have ALL specified modules)
        if filters and filters.get('application'):
            req_apps = [a.strip().lower() for a in filters['application'].split(',') if a.strip()]
            pump_apps = [a.strip().lower() for a in (pump.app_modules or '').split(',') if a.strip()]
            if req_apps and not all(ra in pump_apps for ra in req_apps):
                continue

        # Size filter (partial match)
        if filters and filters.get('size'):
            size_filter = filters['size'].strip().lower()
            if size_filter and size_filter not in (pump.size or '').lower():
                continue

        filtered.append(pump)

    return filtered


# ── Single Pump Evaluation ────────────────────────────────────────────────────

def _evaluate_pump(pump, q_duty, h_duty, npsh_avail,
                   liquid, rho, viscosity_cSt,
                   slurry_cv, slurry_d50, rho_solid,
                   operation_mode='fixed'):
    """
    Evaluate a single pump against the duty point.

    Beginners Note:
        This function performs a multi-step evaluation:
        1. Check if duty flow is within the pump's operating range
        2. Evaluate head at duty flow (max impeller) — pump must produce head >= required
        3. Find the H-Q envelope (max and min impeller curves) and check coverage
        4. Calculate optimal trim ratio to place duty on the H-Q curve
        5. Check NPSH margin
        6. Calculate BEP proximity and suitability score
        7. Generate mini-chart sparkline data

    Returns:
        Dict with pump info and performance data, or None if pump can't meet duty.
    """
    # ── Check 1: Flow range — duty Q must be within pump's operating range ──
    # Beginners Note: Use a generous range check since trimmed impellers shift Q range
    q_lo = pump.q_min or 0.0
    q_hi = pump.q_max
    # Allow some flow range flexibility — trimmed impellers reduce max Q proportionally
    if q_duty < q_lo or q_duty > q_hi * 1.05:
        return None

    # ── Check 2: Head at duty flow on max impeller ──────────────────────────
    # Beginners Note: Evaluate the H-Q polynomial at the duty flow rate
    q_arr = np.array([q_duty])
    h_at_duty_max = float(hq_curve(pump, q_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])

    # Pump must produce at least the required head on max impeller
    if h_at_duty_max < h_duty:
        return None

    # ── Check 3: Multi-curve envelope evaluation ────────────────────────────
    # Beginners Note: Get the pump's available impeller diameters (or speeds for VSD pumps)
    # and find the minimum impeller head at duty flow to determine the pump's full envelope
    diameters = pump.get_diameters()
    d_max = max(diameters) if diameters else (pump.impeller_dia_mm or 300.0)
    d_min = min(diameters) if len(diameters) > 1 else d_max

    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    is_vsd = (operation_mode == 'vsd')

    # Calculate head at duty for minimum impeller/speed using affinity laws
    if d_min != d_max and d_max > 0:
        r_min = d_min / d_max
        h_at_duty_min = h_at_duty_max * (r_min ** 2)
    else:
        h_at_duty_min = 0.0
        r_min = 0.0

    # Check if duty head falls within the envelope [h_min, h_max]
    duty_in_envelope = h_at_duty_min <= h_duty <= h_at_duty_max
    # Even if duty is above the min curve head, max impeller must cover it (already checked)

    # ── Calculate optimal trim ratio ────────────────────────────────────────
    # Beginners Note: The trim ratio (D/D_max or N/N_max) that would make the pump's
    # H-Q curve pass exactly through the duty point. Using affinity law: H ∝ D² (or N²)
    # So: h_duty = h_at_duty_max * r² → r = sqrt(h_duty / h_at_duty_max)
    if h_at_duty_max > 0:
        optimal_trim_ratio = min(1.0, (h_duty / h_at_duty_max) ** 0.5)
    else:
        optimal_trim_ratio = 1.0

    # Calculate the corresponding physical diameter or speed
    optimal_trim_dia_mm = d_max * optimal_trim_ratio
    
    if is_vsd:
        # User constraint: VSD speed must be within min and max bounds
        base_speed = pump.speed_rpm if pump.speed_rpm else 1450.0
        optimal_speed_rpm = base_speed * optimal_trim_ratio
        
        # Parse RPM bounds
        rpm_str = getattr(pump, 'graph_rpm_values', '') or ''
        rpm_vals = []
        for v in rpm_str.replace(',', ' ').replace(';', ' ').replace('|', ' ').split():
            try:
                rpm_vals.append(float(v))
            except ValueError:
                pass
        
        if rpm_vals:
            max_rpm = max(rpm_vals)
            min_rpm = min(rpm_vals)
        else:
            # Fallback to VFD Hz bounds if RPM values aren't explicitly given
            min_hz = getattr(pump, 'vfd_min_hz', 30.0)
            max_hz = getattr(pump, 'vfd_max_hz', 50.0)
            max_rpm = base_speed
            min_rpm = base_speed * (min_hz / max_hz) if max_hz > 0 else base_speed * 0.6
            
        # Reject pump if the required VSD speed is outside bounds
        if optimal_speed_rpm < min_rpm or optimal_speed_rpm > (max_rpm * 1.05):  # 5% tolerance on max
            return None
    else:
        optimal_speed_rpm = pump.speed_rpm

    # ── NPSH evaluation ────────────────────────────────────────────────────
    # Beginners Note: NPSHr (required) must be less than NPSHa (available) with safety margin
    npsh_req = float(npsh_curve(pump, q_arr)[0])
    npsh_ok = True
    npsh_margin = None
    if npsh_avail is not None:
        npsh_margin = npsh_avail - npsh_req
        # Require NPSHa >= 1.1 × NPSHr (10% safety margin per industry standard)
        if npsh_avail < 1.1 * npsh_req:
            npsh_ok = False

    # ── Operating point at duty flow ───────────────────────────────────────
    # Beginners Note: Get full performance (H, η, P, NPSH) at the duty flow rate
    op = operating_point(pump, q_duty, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    # ── BEP point ──────────────────────────────────────────────────────────
    # Beginners Note: Best Efficiency Point — the flow rate where the pump runs most efficiently
    bep = bep_point(pump, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    # ── Calculate BEP proximity ratio ──────────────────────────────────────
    # Beginners Note: How close the duty flow is to BEP flow (1.0 = exactly at BEP)
    q_ratio = q_duty / bep['q'] if bep['q'] > 0 else 1.0
    in_preferred_range = 0.80 <= q_ratio <= 1.20
    in_acceptable_range = 0.65 <= q_ratio <= 1.35

    # ── Head surplus calculation ───────────────────────────────────────────
    # Beginners Note: How much extra head the pump produces above what's needed at max impeller
    head_surplus = h_at_duty_max - h_duty
    head_surplus_pct = (head_surplus / h_duty) * 100 if h_duty > 0 else 0

    # ── Suitability rating (0–100) ─────────────────────────────────────────
    rating = _suitability_rating(q_ratio, op['eta'], npsh_ok, head_surplus_pct, optimal_trim_ratio)

    # ── Mini-chart sparkline data ──────────────────────────────────────────
    # Beginners Note: Generate compact H-Q curve arrays for inline SVG sparklines
    mini_chart = _generate_mini_chart(pump, q_duty, h_duty, d_max, d_min, optimal_trim_ratio,
                                       liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    # ── Build result dict ──────────────────────────────────────────────────
    return {
        # Pump identity
        'pump_id': pump.id,
        'pump_name': pump.name,
        'manufacturer': pump.manufacturer or '',
        'model_number': pump.model_number or '',
        'size': pump.size or '',
        'speed_rpm': pump.speed_rpm,
        'impeller_dia_mm': pump.impeller_dia_mm,
        'pump_type': pump.pump_type or 'centrifugal',
        'family_type': fam_type,

        # Performance at duty (max impeller)
        'op_q': op['q'],
        'op_h': op['h'],
        'op_eta': op['eta'],
        'op_power': op['power'],
        'op_npsh': npsh_req,

        # Head surplus
        'head_surplus': round(head_surplus, 2),
        'head_surplus_pct': round(head_surplus_pct, 1),

        # BEP data
        'bep_q': bep['q'],
        'bep_h': bep['h'],
        'bep_eta': bep['eta'],
        'bep_power': bep['power'],
        'q_ratio': round(q_ratio, 3),
        'in_preferred_range': in_preferred_range,
        'in_acceptable_range': in_acceptable_range,

        # Trim / speed data
        'optimal_trim_ratio': round(optimal_trim_ratio, 4),
        'optimal_trim_dia_mm': round(optimal_trim_dia_mm, 1),
        'optimal_speed_rpm': round(optimal_speed_rpm, 0),
        'is_vsd': is_vsd,
        'd_max': d_max,
        'd_min': d_min,
        'duty_in_envelope': duty_in_envelope,

        # NPSH data
        'npsh_ok': npsh_ok,
        'npsh_margin': round(npsh_margin, 2) if npsh_margin is not None else None,
        'npsh_req': round(npsh_req, 2),

        # Rating & label
        'rating': rating,
        'rating_label': _rating_label(rating),

        # Mini sparkline chart data
        'mini_chart': mini_chart,

        # Notes
        'notes': pump.notes or '',
        
        # Default report ID for PDF generation
        'default_report_id': _get_default_report_id(pump, operation_mode),
    }


# ── Suitability Scoring ──────────────────────────────────────────────────────

def _suitability_rating(q_ratio, eta, npsh_ok, head_surplus_pct, trim_ratio=1.0):
    """
    Score 0–100 for pump suitability.

    Beginners Note:
        The score is a weighted sum of five criteria:
        1. Efficiency at duty (max 30 pts) — higher efficiency = better
        2. BEP proximity (max 35 pts) — closer to BEP flow = better
        3. NPSH margin (max 15 pts) — sufficient margin = safe
        4. Head surplus (max 10 pts) — small surplus is ideal, too much or too little is penalised
        5. Trim closeness to max (max 10 pts) — less trimming = less efficiency loss

    Weighting rationale:
        - BEP proximity is weighted highest because operating far from BEP causes vibration,
          cavitation, bearing wear, and reduced pump life
        - Efficiency is next most important for energy cost
        - NPSH is safety-critical
        - Head surplus and trim ratio are secondary optimisation criteria
    """
    score = 0.0

    # ── 1. Efficiency at duty (max 30 pts) ─────────────────────────────────
    # Beginners Note: Scale linearly — 80% efficiency = 30 pts, 0% = 0 pts
    score += min(30, eta * 0.375)

    # ── 2. BEP proximity (max 35 pts) ──────────────────────────────────────
    # Beginners Note: The closer to BEP (q_ratio ≈ 1.0), the higher the score
    deviation = abs(q_ratio - 1.0)
    if deviation <= 0.05:
        score += 35        # Within 5% of BEP — excellent
    elif deviation <= 0.10:
        score += 30        # Within 10% of BEP — very good
    elif deviation <= 0.20:
        score += 22        # Within 20% of BEP — good
    elif deviation <= 0.30:
        score += 14        # Within 30% of BEP — acceptable
    elif deviation <= 0.40:
        score += 7         # Within 40% of BEP — marginal
    else:
        score += 0         # Beyond 40% of BEP — poor

    # ── 3. NPSH margin (max 15 pts) ────────────────────────────────────────
    # Beginners Note: Full points if NPSH margin is adequate
    if npsh_ok:
        score += 15

    # ── 4. Head surplus (max 10 pts) ───────────────────────────────────────
    # Beginners Note: Small positive surplus (0-10%) is ideal for the optimal trim scenario.
    # Large surplus means more trimming needed. Negative means can't meet duty (shouldn't reach here).
    if 0 <= head_surplus_pct <= 5:
        score += 10        # Very close match — minimal trimming needed
    elif head_surplus_pct <= 15:
        score += 8
    elif head_surplus_pct <= 30:
        score += 5
    elif head_surplus_pct <= 60:
        score += 3
    else:
        score += 1         # Very large surplus — significant oversizing

    # ── 5. Trim closeness to max (max 10 pts) ──────────────────────────────
    # Beginners Note: Prefer pumps that need less trimming (trim_ratio closer to 1.0).
    # Trimmed impellers lose efficiency proportional to trim amount.
    if trim_ratio >= 0.97:
        score += 10        # Virtually no trim needed
    elif trim_ratio >= 0.90:
        score += 8
    elif trim_ratio >= 0.82:
        score += 5
    elif trim_ratio >= 0.70:
        score += 3
    else:
        score += 1         # Heavy trim — significant efficiency penalty

    return int(min(100.0, score))


# ── Rating Label ──────────────────────────────────────────────────────────────

def _rating_label(score):
    """
    Convert numeric rating to human-readable label.

    Beginners Note:
        - Excellent (80+): Pump is an ideal match for the duty
        - Good (65-79): Pump is well suited with minor trade-offs
        - Acceptable (50-64): Pump can work but has notable compromises
        - Marginal (<50): Pump is not well suited, consider alternatives
    """
    if score >= 80:
        return 'Excellent'
    elif score >= 65:
        return 'Good'
    elif score >= 50:
        return 'Acceptable'
    else:
        return 'Marginal'


# ── Mini Sparkline Chart Data ─────────────────────────────────────────────────

def _generate_mini_chart(pump, q_duty, h_duty, d_max, d_min, optimal_trim_ratio,
                          liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid):
    """
    Generate compact H-Q curve data for inline SVG sparklines.

    Beginners Note:
        Returns a dict with:
        - q_max: Array of flow values for max impeller H-Q curve
        - h_max: Array of head values for max impeller H-Q curve
        - q_min: Array of flow values for min impeller H-Q curve (if applicable)
        - h_min: Array of head values for min impeller H-Q curve (if applicable)
        - q_trim: Array of flow values for optimal trim H-Q curve
        - h_trim: Array of head values for optimal trim H-Q curve
        - q_duty: Duty flow point
        - h_duty: Duty head point
        - q_range: [min_q, max_q] for axis scaling
        - h_range: [min_h, max_h] for axis scaling

        All arrays are compact (SPARKLINE_POINTS values) for lightweight rendering.
    """
    n = SPARKLINE_POINTS
    q_lo = pump.q_min or 0.0
    q_hi = pump.q_max

    # ── Max impeller H-Q curve ─────────────────────────────────────────────
    q_max_arr = np.linspace(q_lo, q_hi, n)
    h_max_arr = hq_curve(pump, q_max_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)

    chart = {
        'q_max': [round(float(v), 2) for v in q_max_arr],
        'h_max': [round(float(v), 2) for v in h_max_arr],
        'q_duty': round(q_duty, 2),
        'h_duty': round(h_duty, 2),
    }

    # ── Min impeller H-Q curve (using affinity laws) ───────────────────────
    # Beginners Note: For trimmed impeller pumps, scale by D²/D ratio. For VSD, by N²/N ratio.
    if d_min != d_max and d_max > 0:
        r_min = d_min / d_max
        q_min_arr = q_max_arr * r_min
        h_min_arr = h_max_arr * (r_min ** 2)
        chart['q_min'] = [round(float(v), 2) for v in q_min_arr]
        chart['h_min'] = [round(float(v), 2) for v in h_min_arr]
    else:
        chart['q_min'] = []
        chart['h_min'] = []

    # ── Optimal trim H-Q curve ─────────────────────────────────────────────
    # Beginners Note: The curve at the calculated optimal trim ratio
    if optimal_trim_ratio < 0.99:
        q_trim_arr = q_max_arr * optimal_trim_ratio
        h_trim_arr = h_max_arr * (optimal_trim_ratio ** 2)
        chart['q_trim'] = [round(float(v), 2) for v in q_trim_arr]
        chart['h_trim'] = [round(float(v), 2) for v in h_trim_arr]
    else:
        chart['q_trim'] = []
        chart['h_trim'] = []

    # ── Axis ranges for scaling ────────────────────────────────────────────
    all_q = list(q_max_arr) + [q_duty]
    all_h = list(h_max_arr) + [h_duty]
    chart['q_range'] = [0, round(float(max(all_q)) * 1.05, 1)]
    chart['h_range'] = [0, round(float(max(all_h)) * 1.1, 1)]

    return chart


# ── Filter Options Helper ─────────────────────────────────────────────────────

def get_filter_options(pumps):
    """
    Extract unique filter option values from a list of pumps for populating UI dropdowns.

    Beginners Note:
        Scans all pumps and collects unique values for each filterable field.
        Used by the route handler to populate the filter panel dropdowns.

    Returns:
        Dict with keys 'manufacturers', 'pump_types', 'sizes', 'speed_range', 'applications'
    """
    manufacturers = set()
    pump_types = set()
    sizes = set()
    speeds = []
    applications = set()

    for p in pumps:
        if p.manufacturer:
            manufacturers.add(p.manufacturer.strip())
        if p.pump_type:
            pump_types.add(p.pump_type.strip())
        if p.size:
            sizes.add(p.size.strip())
        if p.speed_rpm:
            speeds.append(p.speed_rpm)
        if p.app_modules:
            for app in p.app_modules.split(','):
                if app.strip():
                    applications.add(app.strip())

    return {
        'manufacturers': sorted(manufacturers),
        'pump_types': sorted(pump_types),
        'sizes': sorted(sizes),
        'speed_range': {
            'min': min(speeds) if speeds else 0,
            'max': max(speeds) if speeds else 3600,
        },
        'applications': sorted(applications),
    }

def _get_default_report_id(pump, operation_mode):
    """
    Get the default report ID for a pump based on the selected operation mode.
    First checks the organisation's explicit default for that mode.
    If not set, attempts to find 'standard_vsd' or 'standard'.
    """
    reports = pump.get_effective_catalogue_reports()
    if not reports:
        return 1
        
    org = pump.organisation
    if org:
        if operation_mode == 'vsd' and org.default_report_vsd_id:
            if any(r.id == org.default_report_vsd_id for r in reports):
                return org.default_report_vsd_id
        elif operation_mode == 'fixed' and org.default_report_fixed_speed_id:
            if any(r.id == org.default_report_fixed_speed_id for r in reports):
                return org.default_report_fixed_speed_id
                
    # Fallback heuristics
    target_name = 'standard_vsd' if operation_mode == 'vsd' else 'standard'
    for r in reports:
        if (r.report_name or '').lower() == target_name:
            return r.id
            
    return reports[0].id
