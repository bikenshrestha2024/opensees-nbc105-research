import unittest,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from OpenSees_View_Controls_V134 import node_readout,apply_view
from OpenSees_Case_Selection_V134 import label_case
from OpenSees_Transient_Runtime_V133 import acceleration_conversion
from OpenSees_Irregularity_Review_V134 import plan_checks

class V134Checks(unittest.TestCase):
    def test_separate_scale_and_units(self):
        self.assertAlmostEqual(acceleration_conversion('g','m',1.)['total_path_factor'],9.80665)
        self.assertAlmostEqual(acceleration_conversion('g','mm',2.)['total_path_factor'],19613.3)
        self.assertAlmostEqual(acceleration_conversion('m/s2','m',1.)['total_path_factor'],1.)
    def test_case_meaning(self):
        self.assertEqual(label_case('SLS_X+_E-_V111'),('SLS','+X','eccentricity -5% b'))
        self.assertEqual(label_case('ULS_Y-_E0_V111'),('ULS','-Y','centered e=0'))
    def test_missing_rotations_not_zeros(self):
        text=node_readout('6',[0.,0.,-.01]);self.assertIn('Rx=N/A',text);self.assertIn('Uz=-0.01 m',text)
    def test_common_camera(self):
        from matplotlib.figure import Figure
        a=Figure().add_subplot(projection='3d');apply_view(a);self.assertAlmostEqual(a.elev,27.5);self.assertAlmostEqual(a.azim,45.)
    def test_l_plan_reentrant_projection(self):
        coords=[(0,0),(10,0),(10,4),(0,4),(4,4),(4,10),(0,10)];data=dict(nodes={str(i+1):[x,y,3.] for i,(x,y) in enumerate(coords)},shells=[dict(category='FLOOR',nodes=[1,2,3,4]),dict(category='FLOOR',nodes=[4,5,6,7])],diaphragms=[dict(master_xyz=[0.,0.,3.],storey_number=1)])
        rows,geometry=plan_checks(data);self.assertEqual(len(rows),2);self.assertAlmostEqual(rows[0]['value'],.6);self.assertTrue(all(r['status']=='IRREGULAR' for r in rows))
    def test_relative_model_binding(self):
        from OpenSees_Readiness_GUI_V134 import prepare
        from OpenSees_Nonlinear_Time_History_NBC105_V116 import _require_nonlinear_readiness
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as t:
            f=Path(t);model=f/'model.py';model.write_text('# fixture',encoding='utf-8');path=prepare(model);d=json.loads(path.read_text());self.assertFalse(d['approved_for_nltha']);self.assertTrue(all(v is False for v in d['checks'].values()));d.update(model_script='model.py',approved_for_nltha=True,checks=dict.fromkeys(d['checks'],True));path.write_text(json.dumps(d));r=_require_nonlinear_readiness(dict(model_script=str(model),model_readiness_json=str(path)));self.assertEqual(r['model_script'],str(model.resolve()))

if __name__=='__main__':unittest.main()
