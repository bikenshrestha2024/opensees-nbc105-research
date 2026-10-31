# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# ViscousDamper author example
# Source: https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('ViscousDamper', 960001, 300000.0, 2226.502041932161, 0.3)
