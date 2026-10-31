import unittest,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from components.validation.nonlinear_performance import template,assess
class Performance(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.file=Path(self.tmp.name)/'history.csv';self.file.write_text('evidence fixture')
  self.c=template();self.c.update(model_sha256='a'*64,performance_objective='ULS project objective',expected_pair_ids=['A','B','C']);self.c['criteria']=self.c['criteria'][:1];self.c['criteria'][0]['reviewed']=True
 def tearDown(self):self.tmp.cleanup()
 def rows(self):
  return [dict(pair_id=p,orientation=o,status='COMPLETED_FULL_RECORD',model_sha256='a'*64,metric='peak_edge_drift_X',demand=.01,unit='ratio',result_file=str(self.file)) for p in self.c['expected_pair_ids'] for o in ['XY','YX']]
 def test_orientation_and_missing(self):
  rows=self.rows();rows[-1]['demand']=.03;self.assertEqual(assess(self.c,rows)['overall'],'FAIL');self.assertEqual(assess(self.c,rows[:-1])['overall'],'INCOMPLETE')
 def test_truncated(self):
  rows=self.rows();rows[0]['status']='COMPLETED_TRUNCATED_TRIAL';self.assertEqual(assess(self.c,rows)['overall'],'INCOMPLETE')
 def test_review_requires_boolean(self):
  self.c['criteria'][0]['reviewed']='false';self.assertEqual(assess(self.c,self.rows())['overall'],'INCOMPLETE')
 def test_mean_and_exact_seven(self):
  self.c['expected_pair_ids']=[str(i) for i in range(8)];rows=self.rows();rows[0]['demand']=.03
  r=assess(self.c,rows)['checks'][0];self.assertAlmostEqual(r['demand'],(.03+7*.01)/8)
  self.c['expected_pair_ids']=self.c['expected_pair_ids'][:7];self.assertEqual(assess(self.c,self.rows())['overall'],'INCOMPLETE')
 def test_units_and_fingerprint(self):
  rows=self.rows();rows[0]['unit']='percent';self.assertEqual(assess(self.c,rows)['overall'],'INCOMPLETE');rows=self.rows();rows[0]['model_sha256']='b'*64;self.assertEqual(assess(self.c,rows)['overall'],'INCOMPLETE')
 def test_small_trial_and_nan(self):
  self.c['expected_pair_ids']=['A'];self.assertEqual(assess(self.c,self.rows())['overall'],'INCOMPLETE');self.c['torsion_sensitive']=False;rows=self.rows();rows[0]['demand']='nan';self.assertEqual(assess(self.c,rows)['overall'],'INCOMPLETE')
if __name__=='__main__':unittest.main()

