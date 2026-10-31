# PEER web material + E-SFI numerical patch

PUBLISHED MATERIAL / ASSUMED PATCH | Only web constitutive values and ratios come from PEER. 1.2 x .3 x .15 m patch, 60 kN axial force and cyclic protocol are numerical choices; neither RW wall nor SD-06 experiment reproduced. No actual core openings/corners.

Native E_SFI_MVLEM_3D/SFI_MVLEM_3D elements use ConcreteCM+SteelMPF inside FSAM at wall macro-fibers. Sum(width_i*thickness_i)=wall area. FSAM includes biaxial normal/shear interaction, friction and dowel parameters. CoR=.4 and ThickMod=.63 are author defaults, not NBC wall stiffness prescriptions.

Source: https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf
Locator: Appendix B.3 web materials; E-SFI formulation Kolozvari et al. (2023)

No experimental equivalence or project approval is inferred. This export does not set nonlinear_parameters_reviewed or change the building configuration.
