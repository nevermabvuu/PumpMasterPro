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
                 tolerance=0.15, filters=None, operation_mode='fixed',
                 enabled_attributes=None,
                 fixed_speed_mode='auto',
                 manual_pump_speed_rpm=None,
                 motor_freq_hz=50, motor_poles=4,
                 motor_selection_mode='auto', manual_motor_id=None,
                 manual_motor_speed_rpm=None, manual_speed_tolerance_pct=5.0,
                 motor_margin_pct=15.0, motor_margin_basis='duty',
                 motor_standard=None, motor_efficiency=None, motor_supplier=None,
                 vsd_f_min=30.0, vsd_f_max=50.0,
                 drive_type='direct'):
    """
    Select pumps that can satisfy the duty point.

    Beginners Note:
        This is the main function called by the route handler. It:
        1. Pre-filters pumps by user-specified criteria (type, manufacturer, speed, custom attributes, etc.)
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
        filters: Dict of filter criteria (manufacturer, pump_type, speed_min, speed_max, custom attributes, etc.)
        operation_mode: 'fixed' or 'vsd'
        enabled_attributes: List of enabled custom pump attributes dicts [{'index': 1, 'name': '...'}, ...]

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
            operation_mode, enabled_attributes=enabled_attributes,
            fixed_speed_mode=fixed_speed_mode,
            manual_pump_speed_rpm=manual_pump_speed_rpm,
            motor_freq_hz=motor_freq_hz, motor_poles=motor_poles,
            motor_selection_mode=motor_selection_mode,
            manual_motor_id=manual_motor_id,
            manual_motor_speed_rpm=manual_motor_speed_rpm,
            manual_speed_tolerance_pct=manual_speed_tolerance_pct,
            motor_margin_pct=motor_margin_pct,
            motor_margin_basis=motor_margin_basis,
            motor_standard=motor_standard,
            motor_efficiency=motor_efficiency,
            motor_supplier=motor_supplier,
            vsd_f_min=vsd_f_min, vsd_f_max=vsd_f_max,
            drive_type=drive_type
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
        - attribute_{1-30}, filter_attribute_{1-30}, PumpAttribute{1-30}: Organisation custom pump attribute filters
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
        # Beginners Note: When operating in Fixed Speed manual mode, evaluate the speed filter
        # against the prescribed operating speed rather than the catalogue base speed.
        is_fixed_manual = (operation_mode == 'fixed' and fixed_speed_mode == 'manual' and manual_pump_speed_rpm and float(manual_pump_speed_rpm) > 0)
        eval_speed = float(manual_pump_speed_rpm) if is_fixed_manual else (pump.speed_rpm or 1450.0)

        speed_min = filters.get('speed_min') if filters else None
        if speed_min is not None and speed_min != '':
            try:
                if eval_speed < float(speed_min):
                    continue
            except (ValueError, TypeError):
                pass

        speed_max = filters.get('speed_max') if filters else None
        if speed_max is not None and speed_max != '':
            try:
                if eval_speed > float(speed_max):
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

        # ── Custom Organisation Pump Attributes Filters (attribute_1 to 30) ─────────
        # Beginners Note:
        # Allows engineers to filter pumps by custom organisation specifications
        # (for example: Impeller Type = 'Open', Design Standard = 'ANSI', Impeller Material = 'Rubber').
        #
        # Matching Rules:
        # 1. Accepts keys formatted as 'filter_attribute_{i}', 'attribute_{i}', or 'PumpAttribute{i}'
        # 2. Case-insensitive comparison so selecting 'Open' matches 'open', 'Open', or 'OPEN'
        # 3. Supports partial and substring matches (e.g. 'open' matches 'Open Impeller' or 'Semi-Open')
        # 4. Supports comma-separated multi-value selections (e.g. 'Open, Semi-Open' acts as an OR filter)
        # 5. Pumps without a value for the filtered attribute are excluded
        attr_mismatch = False
        for k, fval in filters.items():
            if not fval or not str(fval).strip():
                continue
            attr_idx = None
            for prefix in ('filter_attribute_', 'attribute_', 'filter_PumpAttribute', 'PumpAttribute'):
                if k.startswith(prefix):
                    suffix = k[len(prefix):]
                    if suffix.isdigit():
                        attr_idx = int(suffix)
                        break
            if attr_idx and 1 <= attr_idx <= 30:
                pump_val = (getattr(pump, f'PumpAttribute{attr_idx}', '') or '').strip().lower()
                target_val = str(fval).strip().lower()
                targets = [t.strip().lower() for t in target_val.split(',') if t.strip()]
                # A pump must have a populated value for this attribute to match
                if not pump_val:
                    attr_mismatch = True
                    break
                # If target list specified, pump attribute must match at least one target option
                if targets and not any(t == pump_val or t in pump_val or pump_val in t for t in targets):
                    attr_mismatch = True
                    break
        if attr_mismatch:
            continue

        filtered.append(pump)

    return filtered


# ── Single Pump Evaluation ────────────────────────────────────────────────────

def _evaluate_pump(pump, q_duty, h_duty, npsh_avail,
                   liquid, rho, viscosity_cSt,
                   slurry_cv, slurry_d50, rho_solid,
                   operation_mode='fixed', enabled_attributes=None,
                   fixed_speed_mode='auto',
                   manual_pump_speed_rpm=None,
                   motor_freq_hz=50, motor_poles=4,
                   motor_selection_mode='auto', manual_motor_id=None,
                   manual_motor_speed_rpm=None, manual_speed_tolerance_pct=5.0,
                   motor_margin_pct=15.0, motor_margin_basis='duty',
                   motor_standard=None, motor_efficiency=None, motor_supplier=None,
                   vsd_f_min=30.0, vsd_f_max=50.0,
                   drive_type='direct'):
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
    base_speed = float(pump.speed_rpm) if pump.speed_rpm else 1450.0
    fam_type = getattr(pump, 'family_type', 'trimmed_impeller') or 'trimmed_impeller'
    is_vsd = (operation_mode == 'vsd')
    is_fixed_manual = (operation_mode == 'fixed' and fixed_speed_mode == 'manual' and manual_pump_speed_rpm and float(manual_pump_speed_rpm) > 0)
    user_pump_rpm = float(manual_pump_speed_rpm) if is_fixed_manual else base_speed
    speed_ratio = (user_pump_rpm / base_speed) if (is_fixed_manual and base_speed > 0) else 1.0

    # ── Check 1: Flow range — duty Q must be within pump's operating range at operating speed ──
    # Beginners Note on Affinity Law Flow Scaling:
    # Under affinity laws, flow scales directly proportional to speed: Q ∝ N (Q_scaled = speed_ratio * Q_base).
    # When a pump is driven at an operating speed N different from its catalogue base speed N_base,
    # its entire allowable flow envelope shifts by speed_ratio = N / N_base.
    # We apply this scaling to both q_min and q_max before evaluating if the duty flow is reachable.
    q_lo = (pump.q_min or 0.0) * speed_ratio
    q_hi = (pump.q_max or 100.0) * speed_ratio
    if q_duty < q_lo or q_duty > q_hi * 1.05:
        return None

    # ── Check 2: Head at duty flow on max impeller at operating speed ──────────
    # Beginners Note on Affinity Law Head Scaling:
    # Under affinity laws, head scales with the square of speed: H ∝ N² (H_scaled = speed_ratio² * H_base).
    # To determine the maximum head the pump can produce at operating speed N_manual with full diameter,
    # we evaluate the catalogue curve at the equivalent base flow Q_base = Q_duty / speed_ratio,
    # and multiply the resulting head by (speed_ratio)².
    # If the duty head exceeds this maximum capacity, the pump cannot achieve the duty point at this speed.
    q_eval_max = np.array([q_duty / speed_ratio])
    h_eval_max = float(hq_curve(pump, q_eval_max, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
    h_at_duty_max = h_eval_max * (speed_ratio ** 2)

    if h_at_duty_max < h_duty:
        return None

    # ── Check 3: Multi-curve envelope evaluation ────────────────────────────
    # Beginners Note: Determine available impeller diameters to assess envelope coverage
    if not is_vsd and fam_type == 'variable_speed':
        d_max = pump.impeller_dia_mm or 300.0
        d_min = d_max
    else:
        diameters = pump.get_diameters()
        d_max = max(diameters) if diameters else (pump.impeller_dia_mm or 300.0)
        d_min = min(diameters) if len(diameters) > 1 else d_max

    if d_min != d_max and d_max > 0:
        r_min = d_min / d_max
        h_at_duty_min = h_at_duty_max * (r_min ** 2)
    else:
        h_at_duty_min = 0.0
        r_min = 0.0

    duty_in_envelope = h_at_duty_min <= h_duty <= h_at_duty_max

    # ── Optimal Trim / Speed Ratio Calculation via Bisection Method ───────
    # Beginners Note on Composite Affinity Solver:
    # When both speed N and impeller diameter D may vary, the combined affinity scaling factor is:
    #     k = (N / N_base) * (D / D_max) = speed_ratio * dia_trim_ratio
    # Affinity laws dictate:
    #     Q_duty = k * Q_base  =>  Q_base = Q_duty / k
    #     H_duty = k² * H_base(Q_base) = k² * H_base(Q_duty / k)
    #
    # We solve f(k) = [ k² * H_base(Q_duty / k) ] - H_duty = 0 using bisection on [0.15, 1.25].
    if h_at_duty_max > 0 and h_duty > 0:
        k_low = 0.15
        k_high = 1.25
        for _ in range(30):
            k_mid = (k_low + k_high) / 2.0
            q_eval = np.array([q_duty / k_mid])
            h_eval = float(hq_curve(pump, q_eval, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
            h_calc = h_eval * (k_mid ** 2)
            if h_calc < h_duty:
                k_low = k_mid
            else:
                k_high = k_mid
        composite_k = (k_low + k_high) / 2.0
    else:
        composite_k = speed_ratio

    # ── Mode-Specific Speed & Impeller Trim Resolution ───────────────────
    if is_vsd:
        # VSD Mode: Impeller is full diameter; speed varies to hit duty point
        optimal_speed_rpm = base_speed * composite_k
        optimal_trim_dia_mm = d_max
        optimal_trim_ratio = round(composite_k, 4)

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
            min_hz = getattr(pump, 'vfd_min_hz', 30.0)
            max_hz = getattr(pump, 'vfd_max_hz', 50.0)
            max_rpm = base_speed
            min_rpm = base_speed * (min_hz / max_hz) if max_hz > 0 else base_speed * 0.6

        if optimal_speed_rpm < min_rpm or optimal_speed_rpm > (max_rpm * 1.05):
            return None

    elif fixed_speed_mode == 'auto':
        # Fixed Speed (Auto Calculate Pump Speed): Full impeller, speed is calculated
        optimal_speed_rpm = round(base_speed * composite_k, 1)
        optimal_trim_dia_mm = d_max
        optimal_trim_ratio = round(composite_k, 4)

        if optimal_speed_rpm < (base_speed * 0.25) or optimal_speed_rpm > (base_speed * 1.35):
            return None

    elif is_fixed_manual:
        # Fixed Speed (Manual User Prescribed Speed):
        # Operating speed is fixed to user_pump_rpm.
        # Impeller diameter trim ratio r_dia = composite_k / speed_ratio.
        r_dia = composite_k / speed_ratio if speed_ratio > 0 else 1.0

        min_trim_allowable = max(0.55, (d_min / d_max) * 0.95) if (d_min and d_max and d_min < d_max) else 0.60
        if r_dia > 1.05 or r_dia < min_trim_allowable:
            return None

        optimal_speed_rpm = round(user_pump_rpm, 1)
        optimal_trim_dia_mm = round(d_max * min(1.0, r_dia), 1)
        optimal_trim_ratio = round(min(1.0, r_dia), 4)

    else:
        # Fixed Speed (Catalogue Rated Base Speed with Impeller Trim):
        r_dia = composite_k
        if r_dia > 1.05 or r_dia < 0.60:
            return None
        optimal_speed_rpm = base_speed
        optimal_trim_dia_mm = round(d_max * min(1.0, r_dia), 1)
        optimal_trim_ratio = round(min(1.0, r_dia), 4)

    # ── Operating Point Performance with Affinity Scaling ────────────────
    # Beginners Note on Hydraulic Performance at Operating Condition:
    # Operating point on base curve is evaluated at equivalent base flow Q_base = Q_duty / composite_k.
    # By affinity laws:
    #   - Shaft Power P ∝ k³: P_duty = k³ * P_base(Q_base)
    #   - NPSHr ∝ k²: NPSHr_duty = k² * NPSHr_base(Q_base)
    #   - Efficiency η is preserved at corresponding affinity point
    q_base_eval = np.array([q_duty / composite_k])
    eta_eval = float(efficiency_curve(pump, q_base_eval, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
    pwr_base_eval = float(power_curve(pump, q_base_eval, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)[0])
    pwr_duty = max(0.1, pwr_base_eval * (composite_k ** 3))

    npsh_base_eval = float(npsh_curve(pump, q_base_eval)[0])
    npsh_req = max(0.0, npsh_base_eval * (composite_k ** 2))

    # NPSH evaluation against available NPSH
    npsh_ok = True
    npsh_margin = None
    if npsh_avail is not None:
        npsh_margin = npsh_avail - npsh_req
        if npsh_avail < 1.1 * npsh_req:
            npsh_ok = False

    # BEP point at operating speed
    bep_base = bep_point(pump, liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
    bep_q = round(bep_base['q'] * composite_k, 2)
    bep_h = round(bep_base['h'] * (composite_k ** 2), 2)
    bep_power = round(bep_base['power'] * (composite_k ** 3), 2)
    bep_eta = bep_base['eta']

    # BEP proximity ratio
    q_ratio = q_duty / bep_q if bep_q > 0 else 1.0
    in_preferred_range = 0.80 <= q_ratio <= 1.20
    in_acceptable_range = 0.65 <= q_ratio <= 1.35

    # Head surplus calculation
    head_surplus = h_at_duty_max - h_duty
    head_surplus_pct = (head_surplus / h_duty) * 100 if h_duty > 0 else 0

    # Suitability rating (0–100)
    rating = _suitability_rating(q_ratio, eta_eval, npsh_ok, head_surplus_pct, optimal_trim_ratio)

    # Mini-chart sparkline data
    mini_chart = _generate_mini_chart(pump, q_duty, h_duty, d_max, d_min, optimal_trim_ratio,
                                      liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid,
                                      speed_ratio=speed_ratio, composite_ratio=composite_k)

    # ── Power Calculations for Motor Sizing Basis ────────────────────────
    duty_power = round(pwr_duty, 2)
    bep_power = round(bep_base['power'] * (composite_k ** 3), 2)

    # Calculate shutoff power (at Q = 0) scaled by composite_k³
    try:
        shutoff_arr = power_curve(pump, np.array([0.0]), liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
        shutoff_power_base = float(shutoff_arr[0]) if shutoff_arr is not None and len(shutoff_arr) > 0 else 0.0
    except Exception:
        shutoff_power_base = 0.0
    if shutoff_power_base <= 0:
        shutoff_power_base = round(bep_base['power'] * 0.40, 2)
    shutoff_power = round(shutoff_power_base * (composite_k ** 3), 2)

    # Calculate end of curve power (at Q_max) scaled by composite_k³
    try:
        q_max_val = float(pump.q_max or (bep_base['q'] * 1.3))
        eoc_arr = power_curve(pump, np.array([q_max_val]), liquid, rho, viscosity_cSt, slurry_cv, slurry_d50, rho_solid)
        eoc_power_base = float(eoc_arr[0]) if eoc_arr is not None and len(eoc_arr) > 0 else 0.0
    except Exception:
        eoc_power_base = 0.0
    if eoc_power_base <= 0:
        eoc_power_base = round(bep_base['power'] * 1.20, 2)
    eoc_power = round(eoc_power_base * (composite_k ** 3), 2)

    # Select base power matching motor_margin_basis
    if motor_margin_basis == 'bep':
        base_power_kw = bep_power
    elif motor_margin_basis == 'shutoff':
        base_power_kw = shutoff_power
    elif motor_margin_basis == 'eoc':
        base_power_kw = eoc_power
    else:
        base_power_kw = duty_power

    # ── Motor Selection & Drive Arrangement Evaluation ───────────────────────
    # Beginners Note:
    # 1. Pump calculation already determines the required pump duty speed (optimal_speed_rpm).
    # 2. Motor speed is determined independently from the motor database based on frequency and poles.
    # 3. For direct coupling: we compare motor rated speed from DB against pump speed and report suitability.
    # 4. For VSD: we calculate the required inverter frequency (Hz) and verify against user limits.
    from motor_selection import evaluate_motor_and_drive
    motor_eval = evaluate_motor_and_drive(
        pump_duty_power_kw=duty_power,
        pump_duty_speed_rpm=optimal_speed_rpm,
        operation_mode=operation_mode,
        drive_type=drive_type,
        motor_freq_hz=motor_freq_hz,
        motor_poles=motor_poles,
        motor_selection_mode=motor_selection_mode,
        manual_motor_id=manual_motor_id,
        manual_motor_speed_rpm=manual_motor_speed_rpm,
        manual_speed_tolerance_pct=manual_speed_tolerance_pct,
        motor_margin_pct=motor_margin_pct,
        motor_margin_basis=motor_margin_basis,
        base_power_kw=base_power_kw,
        motor_standard=motor_standard,
        motor_efficiency=motor_efficiency,
        motor_supplier=motor_supplier,
        vsd_f_min=vsd_f_min,
        vsd_f_max=vsd_f_max
    )

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

        # Performance at duty
        'op_q': q_duty,
        'op_h': round(h_duty, 2),
        'op_eta': round(eta_eval, 2),
        'op_power': duty_power,
        'op_npsh': round(npsh_req, 2),

        # Head surplus
        'head_surplus': round(head_surplus, 2),
        'head_surplus_pct': round(head_surplus_pct, 1),

        # BEP & Limit data
        'bep_q': bep_q,
        'bep_h': bep_h,
        'bep_eta': bep_eta,
        'bep_power': bep_power,
        'shutoff_power': shutoff_power,
        'eoc_power': eoc_power,
        'q_ratio': round(q_ratio, 3),
        'in_preferred_range': in_preferred_range,
        'in_acceptable_range': in_acceptable_range,

        # Trim / speed data
        'optimal_trim_ratio': optimal_trim_ratio,
        'optimal_trim_dia_mm': optimal_trim_dia_mm,
        'optimal_speed_rpm': round(optimal_speed_rpm, 0),
        'composite_ratio': round(composite_k, 4),
        'speed_ratio': round(speed_ratio, 4),
        'is_vsd': is_vsd,
        'fixed_speed_mode': fixed_speed_mode if not is_vsd else None,
        'manual_pump_speed_rpm': manual_pump_speed_rpm if (fixed_speed_mode == 'manual' and not is_vsd) else None,
        'd_max': d_max,
        'd_min': d_min,
        'duty_in_envelope': duty_in_envelope,

        # Motor & Drive Arrangement
        'motor': motor_eval,

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

        # Custom Organisation Pump Attributes (1 to 30)
        'custom_attributes': {
            f'PumpAttribute{i}': getattr(pump, f'PumpAttribute{i}', '') or ''
            for i in range(1, 31)
        },
        'attributes_display': [
            {
                'index': attr['index'],
                'name': attr['name'],
                'value': (getattr(pump, f'PumpAttribute{attr["index"]}', '') or '').strip()
            }
            for attr in (enabled_attributes or [])
            if (getattr(pump, f'PumpAttribute{attr["index"]}', '') or '').strip()
        ],
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
                          liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid,
                          speed_ratio=1.0, composite_ratio=None):
    """
    Generate compact H-Q curve data for inline SVG sparklines.

    Beginners Note:
        Returns a dict with:
        - q_max: Array of flow values for max impeller H-Q curve at operating speed
        - h_max: Array of head values for max impeller H-Q curve at operating speed
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
    q_lo = (pump.q_min or 0.0) * speed_ratio
    q_hi = (pump.q_max or 100.0) * speed_ratio

    # ── Max impeller H-Q curve at operating speed ──────────────────────────
    q_max_arr = np.linspace(q_lo, q_hi, n)
    q_base_arr = q_max_arr / speed_ratio if speed_ratio > 0 else q_max_arr
    h_max_arr = hq_curve(pump, q_base_arr, liquid, viscosity_cSt, slurry_cv, slurry_d50, rho_solid) * (speed_ratio ** 2)

    chart = {
        'q_max': [round(float(v), 2) for v in q_max_arr],
        'h_max': [round(float(v), 2) for v in h_max_arr],
        'q_duty': round(q_duty, 2),
        'h_duty': round(h_duty, 2),
    }

    # ── Min impeller H-Q curve (using affinity laws) ───────────────────────
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
    trim_factor = (composite_ratio / speed_ratio) if (composite_ratio and speed_ratio > 0) else optimal_trim_ratio
    if trim_factor < 0.99:
        q_trim_arr = q_max_arr * trim_factor
        h_trim_arr = h_max_arr * (trim_factor ** 2)
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

def get_filter_options(pumps, enabled_attributes=None):
    """
    Extract unique filter option values from a list of pumps for populating UI dropdowns.

    Beginners Note:
        Scans all pumps and collects unique values for each filterable field,
        including organisation-enabled custom PumpAttributes (1 to 30).
        Used by the route handler to populate the filter panel dropdowns.

    Returns:
        Dict with keys 'manufacturers', 'pump_types', 'sizes', 'speed_range',
        'applications', and 'custom_attributes'
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

    # ── Extract distinct values for enabled organisation custom attributes ────
    # Beginners Note:
    # Scans all visible pumps and identifies unique values for each enabled PumpAttribute slot
    # (e.g. for slot #1 'Impeller Type', finds ['Closed', 'Open']).
    # Values are normalized (e.g., lowercase 'open' becomes 'Open') and deduplicated case-insensitively
    # so dropdown selectors in the UI offer neat, predictable choices for engineers.
    custom_attributes = []
    if enabled_attributes:
        for attr in enabled_attributes:
            idx = attr['index']
            name = attr['name']
            seen_lower = set()
            options = []
            for p in pumps:
                val = (getattr(p, f'PumpAttribute{idx}', '') or '').strip()
                if val:
                    # Clean casing for display (e.g. capitalize 'open' -> 'Open', while preserving acronyms 'ANSI')
                    clean_val = val.capitalize() if val.islower() else val
                    if clean_val.lower() not in seen_lower:
                        seen_lower.add(clean_val.lower())
                        options.append(clean_val)
            options.sort(key=lambda s: s.lower())
            custom_attributes.append({
                'index': idx,
                'name': name,
                'options': options
            })

    return {
        'manufacturers': sorted(manufacturers),
        'pump_types': sorted(pump_types),
        'sizes': sorted(sizes),
        'speed_range': {
            'min': min(speeds) if speeds else 0,
            'max': max(speeds) if speeds else 3600,
        },
        'applications': sorted(applications),
        'custom_attributes': custom_attributes,
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
