# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# PEER web material + E-SFI numerical patch
# Source: https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('SteelMPF', 960001, 402724.8419211519, 402724.8419211519, 199947961.50188246, 0.02, 0.02, 20.0, 18.5, 0.0015, 0.0, 1.0, 0.0, 1.0)
    ops.uniaxialMaterial('ConcreteCM', 960002, -55778.58650173204, -0.002371, 37253871.19627273, 15.0, 1.022, 2315.2457095313493, 8e-05, 1.2, 10000.0)
    ops.nDMaterial('FSAM', 960003, 0.0, 960001, 960001, 960002, 0.0074, 0.0074, 0.8, 0.01)
    # Wall FSAM tag = 960003; actual element E_SFI_MVLEM_3D requires reviewed geometry, connectivity and macro-fiber layout.
