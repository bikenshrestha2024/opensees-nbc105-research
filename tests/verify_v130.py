"""V130 numerical and output-contract checks; no full-building dynamic run."""
import unittest,tempfile,json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import openseespy.opensees as ops
from OpenSees_Timing_V130 import timed_outputs
from OpenSees_Model_Audit_V130 import check_kinematics

class V130(unittest.TestCase):
    def tearDown(self):ops.wipe()
    def test_slab_modifiers_preserve_membrane_and_scale_flexure(self):
        E,t,nu=30e6,.15,.2
        for f in (.25,.35):
            ee=E/math.sqrt(f);tt=t*math.sqrt(f)
            self.assertAlmostEqual(ee*tt,E*t)
            self.assertAlmostEqual((ee*tt**3)/(E*t**3),f)
    def test_rigid_diaphragm_lateral_kinematics(self):
        ops.model('basic','-ndm',3,'-ndf',6);xyz={}
        for i,(x,y) in enumerate(((0,0),(6,0),(6,6),(0,6)),1):
            ops.node(i,x,y,0);ops.fix(i,1,1,1,1,1,1);ops.node(i+4,x,y,3);xyz[str(i+4)]=[x,y,3]
            ops.geomTransf('Linear',i,1,0,0);ops.element('elasticBeamColumn',i,i,i+4,.2,30e6,12.5e6,.01,.01,.01,i)
        ops.node(20,3,3,3);ops.fix(20,0,0,1,1,1,0);ops.rigidDiaphragm(3,20,5,6,7,8)
        ops.timeSeries('Linear',1);ops.pattern('Plain',1,1);ops.load(20,20,5,0,0,0,10)
        ops.constraints('Transformation');ops.numberer('RCM');ops.system('UmfPack');ops.algorithm('Linear');ops.integrator('LoadControl',1);ops.analysis('Static');self.assertEqual(ops.analyze(1),0)
        data=dict(nodes=xyz,diaphragms=[dict(master_tag=20,master_xyz=[3,3,3],slave_node_tags=[5,6,7,8])])
        self.assertLess(check_kinematics(ops,data)['max_inplane_constraint_residual'],1e-12)
    def test_shell_to_perimeter_beams_vertical_equilibrium(self):
        ops.model('basic','-ndm',3,'-ndf',6)
        for j in range(3):
            for i in range(3):ops.node(1+j*3+i,i*3,j*3,0)
        for n in (1,3,7,9):ops.fix(n,1,1,1,1,1,1)
        f=.25;ops.section('ElasticMembranePlateSection',1,30e6/math.sqrt(f),.2,.15*math.sqrt(f),0)
        forces={n:0. for n in range(1,10)}
        for tag,ns in enumerate(((1,2,5,4),(2,3,6,5),(4,5,8,7),(5,6,9,8)),1):
            ops.element('ShellMITC4',tag,*ns,1)
            for n in ns:forces[n]+=-5*9/4
        ops.geomTransf('Linear',1,0,0,1)
        for tag,(i,j) in enumerate(((1,2),(2,3),(3,6),(6,9),(9,8),(8,7),(7,4),(4,1)),10):ops.element('elasticBeamColumn',tag,i,j,.48,30e6,12.5e6,.02,.0256,.0144,1)
        ops.timeSeries('Linear',1);ops.pattern('Plain',1,1)
        for n,p in forces.items():ops.load(n,0,0,p,0,0,0)
        ops.constraints('Transformation');ops.numberer('RCM');ops.system('UmfPack');ops.algorithm('Linear');ops.integrator('LoadControl',1);ops.analysis('Static');self.assertEqual(ops.analyze(1),0);ops.reactions()
        self.assertAlmostEqual(sum(ops.nodeReaction(n,3) for n in (1,3,7,9)),180,places=7)
        for n in (1,3,7,9):self.assertAlmostEqual(ops.nodeReaction(n,3),45,places=6)
        self.assertLess(ops.nodeDisp(5,3),0)
    def test_timing_sidecar_preserves_csv_schema(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as td:
            @timed_outputs('unit stage','out')
            def write(out):Path(out,'data.csv').write_text('x,y\n1,2\n')
            write(td);p=Path(td)
            self.assertEqual((p/'data.csv').read_text(),'x,y\n1,2\n')
            meta=json.loads((p/'data.csv.processing.json').read_text());self.assertEqual(meta['status'],'completed');self.assertGreaterEqual(meta['elapsed_seconds'],0);self.assertTrue(meta['started_at'].endswith('+05:45'))
    def test_timing_failure_is_recorded(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as td:
            @timed_outputs('failure stage','out')
            def write(out):Path(out,'partial.txt').write_text('partial');raise RuntimeError('expected')
            with self.assertRaises(RuntimeError):write(td)
            self.assertEqual(json.loads(Path(td,'partial.txt.processing.json').read_text())['status'],'failed')

if __name__=='__main__':unittest.main()
