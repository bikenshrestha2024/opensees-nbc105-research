# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# PEER 2015 RW-A15-P10-S78 web steel
# Source: https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('SteelMPF', 960001, 402724.8419211519, 402724.8419211519, 199947961.50188246, 0.02, 0.02, 20.0, 18.5, 0.0015, 0.0, 1.0, 0.0, 1.0)
