# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# OpenSees MEFI example: unconfined material 4
# Source: https://openseesdocumentation.readthedocs.io/en/latest/user/manual/model/elements/MEFI.html
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('Concrete02', 960001, -47090.0, -0.00232, 0.0, -0.037, 0.1, 2130.0, 1738330.0)
