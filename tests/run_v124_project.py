from pathlib import Path
import sys,json,hashlib,runpy
ROOT=Path(__file__).resolve().parents[1];CODE=ROOT/'outputs/OpenSees_NBC105_V116_Area_NLTHA_Integration'
sys.path.insert(0,str(CODE));stage=ROOT/'work/V124_Project_Check';out=stage/'OpenSees_Analysis_Results'
from OpenSees_Complete_Export_V118 import prepare_complete_export
manifest,report=prepare_complete_export(stage,runtime_dir=CODE)
assert not report['assembly_errors'];print('Assembly PASS',flush=True)
from OpenSees_Project_Inputs_V123 import import_project_inputs
v=import_project_inputs(CODE,stage)['values']
from OpenSees_Rayleigh_Preliminary_V123 import run
saved=out/'NBC105_Rayleigh_Preliminary_V123.json'
if not saved.is_file() or json.loads(saved.read_text()).get('model_sha256')!=hashlib.sha256((stage/'OpenSees_Complete_Model_Data_V118.json').read_bytes()).hexdigest():run(stage,v['awx'],v['awy'])
print('Rayleigh X/Y complete',flush=True)
from OpenSees_Earthquake_Analysis_NBC105_V111 import read_story_csv,write_outputs
from NBC105_Analysis_Settings_V109 import calculate_esm
rows=read_story_csv(stage/manifest['esm_story_weight_csv'])
ray=json.loads((out/'NBC105_Rayleigh_Preliminary_V123.json').read_text())
references={};runners=[]
for axis in ('X','Y'):
    period=ray[axis]['adopted_period_s']
    kwargs=dict(period_s=period,soil_type=v['soil'],zoning_factor_z=v['Z'],importance_factor_i=v['I'],r_mu=v['rmu'],omega_u=v['omegau'],omega_s=v['omegas'])
    ref=calculate_esm(rows,limit_state='ULS',diagnostic_reference=True,**kwargs)
    references[axis]=dict(period_s=period,stories=ref['stories'],basis='NBC ULS coefficient reference for elastic stability diagnostics only; not an eligible high-rise ULS ESM design case.')
    result=calculate_esm(rows,limit_state='SLS',**kwargs)
    for sign in (1,-1):
        for ecc in (1,-1):
            paths=write_outputs(stage/manifest['esm_story_weight_csv'],rows,result,axis,sign,True,(v['breadth_'+axis],ecc),out,stage/manifest['linear_model_script'])
            runners.append(str(paths[2]))
    print(f'{axis}: adopted T={period:.9g}s; SLS base shear={result["base_shear_kN"]:.9g}kN',flush=True)
(stage/'OpenSees_Initial_PDelta_Input_V124.json').write_text(json.dumps(references,indent=2))
from OpenSees_Initial_PDelta_V124 import ensure_initial_checks
ensure_initial_checks(stage)
(stage/'V124_Runners.json').write_text(json.dumps(runners,indent=2))
for path in runners:
    print('Running '+Path(path).name,flush=True)
    runpy.run_path(path,run_name='__main__')
print('ALL EIGHT SLS STATIC CASES COMPLETED',flush=True)
