import unittest,sys,json,math,tempfile
import importlib.util
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from OpenSees_Transient_Runtime_V133 import workload,CaseProfiler,HistoryStream
from OpenSees_History_Inspection_V133 import floor_snapshot,envelope_points
from OpenSees_Nonlinear_Time_History_NBC105_V116 import _advance_nonlinear_interval,_configure_nonlinear_transient

class V133Checks(unittest.TestCase):
    def test_legacy_solver_uses_canonical_implementation(self):
        import OpenSees_Analysis_Stack_V108 as old
        import OpenSees_Analysis_Stack_V110 as current
        self.assertIs(old.configure_nonlinear_transient,current.configure_nonlinear_transient)
    def test_accepted_samples_survive_stream_close(self):
        import csv
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as tmp:
            path=Path(tmp)/'history.csv';stream=HistoryStream(path);stream.append(dict(time_s=.1,u=.02));stream.flush();stream.close()
            with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual(float(rows[0]['u']),.02)
    def test_both_orientations_counted_without_changing_step(self):
        motion=dict(pair_id='a',x=[0.]*11,y=[0.]*21,dt_x=.005,dt_y=.0025)
        cfg=dict(T1_x_s=1.,T1_y_s=2.,Tn_x_s=.05,Tn_y_s=.06)
        r=workload([motion],cfg);self.assertEqual(r['total_cases'],2);self.assertEqual(r['total_requested_steps'],40);self.assertEqual(r['cases'][0]['dt_s'],.0025)
    def test_invalid_bound_rejected(self):
        m=dict(pair_id='a',x=[0.,0.],dt_x=.01,mode='X_ONLY')
        with self.assertRaises(ValueError):workload([m],dict(T1_x_s=0.,Tn_x_s=.1))
    def test_display_decimation_keeps_peak(self):
        x=np.arange(20000);y=np.zeros(20000);y[19876]=12.;y[3]=-20.
        xx,yy=envelope_points(x,y,200);self.assertLessEqual(len(xx),202);self.assertEqual(yy.min(),-20.);self.assertEqual(yy.max(),12.);self.assertTrue(np.all(np.diff(xx)>0))
    def test_snapshot_differing_floor_centers(self):
        d=dict(base_z_m=0.,nodes={'1':[4.,2.,4.5]},diaphragms=[dict(master_tag=10,master_xyz=[0.,0.,3.]),dict(master_tag=20,master_xyz=[1.,1.,6.])])
        stories=[dict(node=10,story_name='A'),dict(node=20,story_name='B')];row=dict(A_UX_m=1.,A_UY_m=2.,A_RZ_rad=.1,B_UX_m=3.,B_UY_m=4.,B_RZ_rad=.2)
        u=floor_snapshot(d,stories,row)['1'];self.assertAlmostEqual(u[0],(.8+2.8)/2);self.assertAlmostEqual(u[1],(2.4+4.6)/2)
    def test_snapshot_rejects_unmatched_masters(self):
        d=dict(base_z_m=0.,nodes={},diaphragms=[dict(master_tag=20,master_xyz=[0.,0.,3.])])
        with self.assertRaises(ValueError):floor_snapshot(d,[dict(node=1,story_name='A')],{})
    def test_every_adaptive_substep_recorded_without_wipe(self):
        class Fake:
            t=0.
            def test(self,*a):pass
            def algorithm(self,*a):pass
            def analyze(self,n,dt):
                if dt>.05:return -1
                self.t+=dt;return 0
            def getTime(self):return self.t
            def getNodeTags(self):return []
        ops=Fake();seen=[];diag={};count=_advance_nonlinear_interval(ops,.1,on_accept=lambda:seen.append(ops.t),diagnostics=diag)
        self.assertEqual(count,2);self.assertEqual(seen,[.05,.1]);self.assertEqual(diag['bisections'],1)
    @unittest.skipUnless(importlib.util.find_spec("openseespy"), "OpenSeesPy is not installed")
    def test_reused_solver_matches_rebuilt_on_cyclic_nonlinear_model(self):
        import openseespy.opensees as ops
        def calculate(rebuild):
            ops.wipe();ops.model('basic','-ndm',1,'-ndf',1);ops.node(1,0.);ops.node(2,0.);ops.fix(1,1);ops.mass(2,1.);ops.uniaxialMaterial('Steel01',1,2.,1000.,.01);ops.element('zeroLength',1,1,2,'-mat',1,'-dir',1)
            values=[6.*math.sin(i*.005*12.) for i in range(401)];ops.timeSeries('Path',1,'-dt',.005,'-values',*values);ops.pattern('Plain',1,1);ops.load(2,1.)
            _configure_nonlinear_transient(ops);out=[]
            for _ in range(400):
                if rebuild:_configure_nonlinear_transient(ops)
                _advance_nonlinear_interval(ops,.005,on_accept=lambda:out.append(ops.nodeDisp(2,1)))
            ops.wipe();return out
        a=calculate(True);b=calculate(False);self.assertGreater(max(abs(v) for v in a),.002);np.testing.assert_allclose(a,b,atol=1e-10,rtol=1e-9)
    def test_case_profile_persists_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as t:
            p=CaseProfiler(t,'fixture','nonlinear');p.finish('failed','fixture');r=json.loads((Path(t)/'fixture_Performance_V133.json').read_text());self.assertEqual(r['status'],'failed');self.assertGreaterEqual(r['elapsed_seconds'],0)

if __name__=='__main__':unittest.main()
