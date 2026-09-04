import numpy as np
import sys, os

# Setup path
sys.path.insert(0, os.path.abspath('c:/Users/DELL/Documents/admin/Lytrose/repos/Pump-Master-Pro/Pump-Master-Pro/pump-app'))

from app import app
from models import Pump
from pump_curves import hq_curve, efficiency_curve, power_curve, npsh_curve, bep_point

with app.app_context():
    isf = Pump.query.get(9)
    print("Testing ISF pump:", isf.name, "Base Speed:", isf.speed_rpm)
    
    # Test duty point: Q = 50 m3/h, H = 15 m, Manual speed = 1450 RPM
    q_duty = 50.0
    h_duty = 15.0
    manual_pump_speed_rpm = 1450.0
    base_speed = float(isf.speed_rpm)
    speed_ratio = manual_pump_speed_rpm / base_speed # 0.5
    
    # 1. Flow range check
    q_lo = (isf.q_min or 0.0) * speed_ratio
    q_hi = (isf.q_max or 100.0) * speed_ratio
    print(f"Flow range at 1450 RPM: [{q_lo}, {q_hi * 1.05}], Duty Q: {q_duty}")
    assert q_lo <= q_duty <= q_hi * 1.05, "Flow out of range!"
    
    # 2. Max head at duty flow
    q_eval_max = np.array([q_duty / speed_ratio])
    h_eval_max = float(hq_curve(isf, q_eval_max, 'water', 1.0, 0.0, 0.3, 2650.0)[0])
    h_at_duty_max = h_eval_max * (speed_ratio ** 2)
    print(f"Max head at 1450 RPM for Q={q_duty}: {h_at_duty_max:.2f} m, Duty H: {h_duty} m")
    assert h_at_duty_max >= h_duty, "Head too high for max impeller at 1450 RPM!"
    
    # 3. Bisection for composite_k
    k_low = 0.15
    k_high = 1.25
    for _ in range(30):
        k_mid = (k_low + k_high) / 2.0
        q_eval = np.array([q_duty / k_mid])
        h_eval = float(hq_curve(isf, q_eval, 'water', 1.0, 0.0, 0.3, 2650.0)[0])
        h_calc = h_eval * (k_mid ** 2)
        if h_calc < h_duty:
            k_low = k_mid
        else:
            k_high = k_mid
    composite_k = (k_low + k_high) / 2.0
    
    # Physical diameter trim ratio
    r_dia = composite_k / speed_ratio
    diameters = isf.get_diameters()
    d_max = max(diameters) if diameters else isf.impeller_dia_mm
    trim_dia = d_max * min(1.0, r_dia)
    print(f"Composite k: {composite_k:.4f}, Speed ratio: {speed_ratio:.2f}")
    print(f"Diameter trim ratio: {r_dia:.4f} ({r_dia*100:.1f}%), Trim Dia: {trim_dia:.1f} mm (out of {d_max} mm)")
    
    # 4. Scaled operating point
    q_base_eval = np.array([q_duty / composite_k])
    eta_eval = float(efficiency_curve(isf, q_base_eval, 'water', 1.0, 0.0, 0.3, 2650.0)[0])
    pwr_base_eval = float(power_curve(isf, q_base_eval, 'water', 1000.0, 1.0, 0.0, 0.3, 2650.0)[0])
    pwr_duty = max(0.1, pwr_base_eval * (composite_k ** 3))
    print(f"Duty Power at 1450 RPM: {pwr_duty:.2f} kW (Base unscaled was {pwr_base_eval:.2f} kW), Eta: {eta_eval:.1f}%")
    
    # Verify affinity head hits exactly h_duty
    h_verify = float(hq_curve(isf, q_base_eval, 'water', 1.0, 0.0, 0.3, 2650.0)[0]) * (composite_k ** 2)
    print(f"Verified head produced at duty: {h_verify:.2f} m vs target {h_duty} m")
    assert abs(h_verify - h_duty) < 0.01, "Head verification failed!"
    print("ALL AFFINITY CHECKS PASSED!")
