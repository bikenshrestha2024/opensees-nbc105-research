"""Focused V124 numerical and UI data checks; run with OpenSeesPy Python."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class V124Checks(unittest.TestCase):
    def test_axial_shortening_NL_over_EA(self):
        import openseespy.opensees as ops
        ops.wipe();ops.model('basic','-ndm',3,'-ndf',6)
        ops.node(1,0,0,0);ops.node(2,0,0,3.8)
        ops.fix(1,1,1,1,1,1,1);ops.fix(2,1,1,0,1,1,1)
        ops.geomTransf('Linear',1,1,0,0)
        ops.element('elasticBeamColumn',1,1,2,1.,25e6,10e6,.1,.1,.1,1)
        ops.timeSeries('Linear',1);ops.pattern('Plain',1,1);ops.load(2,0,0,-1000,0,0,0)
        ops.constraints('Plain');ops.numberer('Plain');ops.system('BandSPD');ops.integrator('LoadControl',1.)
        ops.algorithm('Linear');ops.analysis('Static');self.assertEqual(ops.analyze(1),0)
        self.assertAlmostEqual(-ops.nodeDisp(2,3),1000*3.8/(25e6*1.),places=12)
        ops.reactions();self.assertAlmostEqual(ops.nodeReaction(1,3),1000.,places=9);ops.wipe()

    def test_high_rise_reference_keeps_ineligible_label(self):
        from NBC105_Analysis_Settings_V109 import calculate_esm
        rows=[dict(height_m=95,dead_load_kN=100,storage_live_load_kN=0,other_live_load_kN=0)]
        kwargs=dict(period_s=2.,soil_type='C',zoning_factor_z=.35,importance_factor_i=1.)
        with self.assertRaises(ValueError):calculate_esm(rows,**kwargs)
        ref=calculate_esm(rows,diagnostic_reference=True,**kwargs)
        self.assertFalse(ref['code_eligible']);self.assertTrue(ref['diagnostic_reference_only'])

    def test_zoom_reveals_all_visible_support_ids(self):
        from matplotlib.figure import Figure
        from OpenSees_Research_UI_V123 import adaptive_id_ticks
        ax=Figure().add_subplot();adaptive_id_ticks(ax,list(map(str,range(1,78))))
        ax.set_xlim(-.1,6.1);self.assertEqual(list(ax.xaxis.get_major_locator()()),list(range(7)))
        ax.set_xlim(-.5,76.5);self.assertLess(len(ax.xaxis.get_major_locator()()),20)

if __name__=='__main__':unittest.main(verbosity=2)
