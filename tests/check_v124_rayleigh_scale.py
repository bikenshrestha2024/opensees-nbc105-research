from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];CODE=ROOT/'outputs/OpenSees_NBC105_V116_Area_NLTHA_Integration';sys.path.insert(0,str(CODE))
from OpenSees_Rayleigh_Preliminary_V123 import run
stage=ROOT/'work/V124_Project_Check';out=stage/'OpenSees_Analysis_Results'
old=json.loads((out/'NBC105_Rayleigh_Preliminary_V123.json').read_text())
new=run(stage,old['X']['Aw_m2'],old['Y']['Aw_m2'],reference_fraction=.02)
differences={axis:abs(new[axis]['period_s']/old[axis]['period_s']-1) for axis in ('X','Y')}
print('Relative period changes when doubling reference force:',differences,flush=True)
assert max(differences.values())<1e-5,differences
(out/'Rayleigh_Amplitude_Check_V124.json').write_text(json.dumps(dict(reference_fractions=[.01,.02],relative_period_changes=differences),indent=2))
