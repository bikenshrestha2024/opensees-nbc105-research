# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# OpenSees primer: unconfined cover
# Source: https://opensees.berkeley.edu/OpenSees/OpenSeesExamples1.1.pdf
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('Concrete01', 960001, -34473.786465841804, -0.002, 0.0, -0.006)
