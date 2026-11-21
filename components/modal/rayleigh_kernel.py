"""Pure, independently testable NBC 105:2025 §5.1.1 Rayleigh quotient.

This arithmetic kernel does not certify ETABS/OpenSees model equivalence,
seismic-weight mapping, diaphragm constraints, or solved displacements.
"""
from __future__ import annotations

import math


def rayleigh_period_s(weights_kN, forces_kN, incremental_displacements_m,
                      gravity_m_s2=9.81):
    """Return 2*pi*sqrt(sum(Wi*di**2)/(g*sum(Fi*di))).

    Forces and displacements must be from the same perturbation load case;
    use *incremental* displacements relative to the equilibrated gravity state.
    [REF NBC105-2025 §5.1.1, printed p.28]
    """
    w=list(weights_kN)
    f=list(forces_kN)
    d=list(incremental_displacements_m)
    if not w or len(w)!=len(f) or len(w)!=len(d):
        raise ValueError("Rayleigh vectors must have matching nonzero length")
    if isinstance(gravity_m_s2,bool):
        raise ValueError("Gravity acceleration must be finite positive")
    try:
        g=float(gravity_m_s2)
        w=[float(v) for v in w]
        f=[float(v) for v in f]
        d=[float(v) for v in d]
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Non-numeric Rayleigh input") from exc
    if (not math.isfinite(g) or g<=0 or
        any(not math.isfinite(v) or v<=0 for v in w) or
        any(not math.isfinite(v) for v in f+d)):
        raise ValueError("Rayleigh weights/gravity must be positive; all values finite")
    numerator=math.fsum(wi*di*di for wi,di in zip(w,d))
    denominator=g*math.fsum(fi*di for fi,di in zip(f,d))
    if (not math.isfinite(numerator) or not math.isfinite(denominator)
        or numerator<=0 or denominator<=0):
        raise ValueError("Rayleigh energy/work terms must be finite positive")
    t=2*math.pi*math.sqrt(numerator/denominator)
    if not math.isfinite(t) or t<=0:
        raise ValueError("Rayleigh period must be finite positive")
    return t
