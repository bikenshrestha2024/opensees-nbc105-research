# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# PEER 2015 RW-A15-P10-S78 web concrete
# Source: https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('ConcreteCM', 960001, -55778.58650173204, -0.002371, 37253871.19627273, 15.0, 1.022, 2315.2457095313493, 8e-05, 1.2, 10000.0)
