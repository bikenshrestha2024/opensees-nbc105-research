# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# SteelMPF author command example
# Source: https://opensees.berkeley.edu/wiki/index.php/SteelMPF_-_Menegotto_and_Pinto_%281973%29_Model_Extended_by_Filippou_et_al._%281983%29
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('SteelMPF', 960001, 413685.4375901016, 413685.4375901016, 199947961.50188246, 0.02, 0.02, 20.0, 0.925, 0.15, 0.0, 1.0, 0.0, 1.0)
