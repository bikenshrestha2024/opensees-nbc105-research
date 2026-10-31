# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# ConcreteCM author command example
# Source: https://opensees.berkeley.edu/wiki/index.php/ConcreteCM_-_Complete_Concrete_Model_by_Chang_and_Mander_%281994%29
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('ConcreteCM', 960001, -42747.49521764384, -0.0021, 31026407.819257624, 7.0, 1.035, 2068.427187950508, 8e-05, 1.2, 10000.0)
