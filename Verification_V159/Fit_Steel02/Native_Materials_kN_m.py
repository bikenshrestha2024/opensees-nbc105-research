# Units kN, m, s. Stress MPa converted once to kN/m2.
# Reference material definitions; no building assignment or approval.
# SimCenter qfem-0019: fitted single coupon
# Source: https://nheri-simcenter.github.io/quoFEM-Documentation/common/user_manual/examples/desktop/qfem-0019/README.html
def define_materials(ops, base_tag=960001):
    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")
    ops.uniaxialMaterial('Steel02', 960001, 477678.4594629648, 213285977.21361804, 0.017232538850040207, 20.0, 0.8795412124857829, 0.05676345697067946, 0.02344170999823744, 1.0, 0.030778594901764822, 1.0)
