"""Numerical regression tests for the production Rayleigh period kernel.

No native ETABS/OpenSees model acceptance is implied by these unit tests.
"""
import math
import unittest
from components.modal.rayleigh_kernel import rayleigh_period_s


class RayleighKernelTests(unittest.TestCase):
    def test_single_degree_of_freedom_matches_exact_period(self):
        mass=120.0
        stiffness=4800.0
        displacement=0.02
        weight=mass*9.81
        force=stiffness*displacement
        expected=2*math.pi*math.sqrt(mass/stiffness)
        self.assertAlmostEqual(rayleigh_period_s([weight],[force],[displacement]),
                               expected,places=12)

    def test_linear_reference_force_invariance(self):
        weight=[100,150,200]
        f=[5,10,20]
        d=[0.003,0.006,0.009]
        t0=rayleigh_period_s(weight,f,d)
        for scale in [0.01,0.1,2.0,10.0]:
            t=rayleigh_period_s(weight,
                [scale*v for v in f],[scale*v for v in d])
            self.assertAlmostEqual(t,t0,places=11)

    def test_rejects_mismatched_or_invalid_energy(self):
        invalid=[
            ([1],[1],[]),
            ([1],[0],[1]),
            ([1],[-1],[1]),
            ([0],[1],[1]),
            ([float("nan")],[1],[1]),
            ([1],[1],[float("inf")]),
        ]
        for w,f,d in invalid:
            with self.subTest(w=w,f=f,d=d):
                with self.assertRaises(ValueError):
                    rayleigh_period_s(w,f,d)

    def test_refuses_zero_and_nonfinite_gravity(self):
        for g in [0,-1,float("nan"),True]:
            with self.subTest(g=g):
                with self.assertRaises(ValueError):
                    rayleigh_period_s([1],[1],[1],gravity_m_s2=g)


if __name__=="__main__":
    unittest.main()
