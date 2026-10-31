from pathlib import Path
import sys,json,tempfile,hashlib
p=Path(__file__).resolve().parent;sys.path.insert(0,str(p))
from components.equivalent_static.code_basis import calculate_esm
rows=[dict(height_m=3*i,dead_load_kN=100,storage_live_load_kN=20,other_live_load_kN=10) for i in range(1,7)]
for state in ('ULS','SLS'):
 r=calculate_esm(rows,period_s=1.2,soil_type='C',zoning_factor_z=.35,importance_factor_i=1,limit_state=state,diagnostic_reference=True)
 assert abs(r['total_seismic_weight_kN']-690)<1e-9
 assert abs(r['total_floor_force_kN']-r['base_shear_kN'])<1e-8
for key in ('dead_load_kN','height_m'):
 bad=[dict(rows[0],**{key:float('nan')})]
 try:calculate_esm(bad,period_s=1,soil_type='C',zoning_factor_z=.35,importance_factor_i=1)
 except ValueError:pass
 else:raise AssertionError('nonfinite accepted')
from components.validation.response_inventory import available_response_rows
live=Path('D:/Thesis Opensees/Etabs Nodes Export');d,a=available_response_rows(live);assert d and a;assert all(r['status']!='PASS' for r in a+d)
from components.validation.etabs_comparison import collect,compare
rr=collect(live);assert rr;ref=[{k:str(v) for k,v in r.items()} for r in rr]
# Individual exact-key unit contract, reject mismatched unit.
r=rr[0];assert compare([r],[r])[0]['percent_difference']==0
wrong=dict(r,unit='wrong');assert compare([r],[wrong])[0]['status']=='NO MATCH'
from components.validation.settings_audit import audit
assert audit(live)['overall'].startswith('REVIEW')
from components.response_spectrum.model_analysis import cqc_matrix,combine
import numpy as np
assert np.allclose(cqc_matrix([1,2]),cqc_matrix([1,2]).T)
assert abs(float(combine([3,4],np.eye(2)))-5)<1e-12
from components.validation.saved_stiffness import merge_saved_stiffness
with tempfile.TemporaryDirectory() as td:
 f=Path(td);(f/'OpenSees_Complete_Model_Data_V118.json').write_text('{}');out=f/'OpenSees_Analysis_Results';out.mkdir();sha=hashlib.sha256(b'{}').hexdigest();(out/'Irregularity_ULS_X_E0_V132.json').write_text(json.dumps(dict(model_sha256=sha,limit_state='ULS',response_case='ULS_X_E0',checks=[dict(clause='5.4.1.2',check='Soft story adjacent above',storey=1,value=.6,status='IRREGULAR')])));r=merge_saved_stiffness(f,dict(checks=[]));r=merge_saved_stiffness(f,r);assert len([x for x in r['checks'] if x.get('value')==.6])==1
print('PASS: ESM weight/force balance, finite inputs, response inventory, comparison units, CQC, settings audit, saved-stiffness deduplication;',len(d),'deflection rows;',len(a),'action rows;',len(rr),'comparison rows')
