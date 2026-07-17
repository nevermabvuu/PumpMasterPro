---
name: Efficiency isoline quadratic coefficients
description: How to compute efficiency polynomial coefficients that produce proper closed isolines on Warman performance maps.
---

For Warman-style efficiency isolines to work, the efficiency curve must:
1. Be negative (clipped → 0) at Q=0
2. Peak at Q_bep
3. Fall back to 0 at Q_max (so both left and right crossings exist within the valid H-Q range)

**Closed-form quadratic (b3=0):**
```python
def eff_quadratic(eta_peak, Q_bep, Q_max):
    # Requires Q_bep > Q_max / 2
    den = (Q_max - Q_bep)**2
    b2  = -eta_peak / den
    b1  =  2 * eta_peak * Q_bep / den
    b0  =  eta_peak * Q_max * (Q_max - 2*Q_bep) / den
    return b0, b1, b2, 0.0
```

**Why:** When Q_bep ≤ Q_max/2, b0 becomes positive meaning η(0) > 0 and no left crossing exists for low isoline levels. Setting Q_bep ≈ 0.55 * Q_max works for all pump types.

**H-Q companion:** Use parabolic shutoff `H = H0 * (1 - (Q/Q_max)²)` so the H valid region closes at the same Q_max as the efficiency, ensuring both crossings are always in the valid region.
