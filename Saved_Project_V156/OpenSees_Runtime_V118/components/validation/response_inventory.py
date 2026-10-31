"""Saved response inventory. Missing design capacities remain explicit."""
from pathlib import Path
import json,math

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def available_response_rows(folder):
 root=Path(folder);out=root/'OpenSees_Analysis_Results';deflections=[];actions=[]
 gravity=out/'Gravity_Result_V110.json'
 if gravity.exists():
  d=read(gravity);nodes=d.get('nodes',[])
  for z in sorted(set(round(n['z_m'],6) for n in nodes)):
   level=[n for n in nodes if abs(n['z_m']-z)<1e-5]
   critical=min(level,key=lambda n:n['uz_m'])
   deflections.append(dict(limit_state='AS_CONFIGURED',case='Gravity preload',member='NODE:'+str(critical['tag']),check='Recorded total vertical displacement',demand=abs(critical['uz_m']),limit=None,unit='m',status='LIMIT REQUIRED',reason='Total displacement, not beam chord-relative or long-term deflection. Supply span/support reference, load combination and project criterion.',result_file=str(gravity)))
  for row in d.get('local_forces',[]):
   actions.append(dict(limit_state='AS_CONFIGURED',case='Gravity preload',member='ELEMENT:'+str(row['tag']),check='Concurrent local end actions available',status='CAPACITY REQUIRED',reason='Not a DL-only basis or ULS/SLS combination. P-M-M, shear, stability and detailing require actual reinforcement/capacities.',result_file=str(gravity),**{k:v for k,v in row.items() if k!='tag'}))
 for p in sorted(out.rglob('Deformation_*_V132.json')):
  try:
   d=read(p);state=d.get('limit_state') or ('ULS' if '_ULS_' in p.name else 'SLS' if '_SLS_' in p.name else 'UNKNOWN')
   values=[(n,u) for n,u in d.get('displacements',{}).items() if len(u)>=2 and all(math.isfinite(float(v)) for v in u[:2])]
   for j,axis in [(0,'X'),(1,'Y')]:
    if values:
     n,u=max(values,key=lambda pair:abs(float(pair[1][j])))
     deflections.append(dict(limit_state=state,case=p.stem,member='NODE:'+str(n),check='Saved displacement '+axis,demand=abs(float(u[j])),limit=None,unit='m',status='LIMIT REQUIRED',reason=d.get('note','')+' | Existing result provenance must be reviewed; no standalone global displacement limit assumed.',result_file=str(p)))
  except (ValueError,KeyError,TypeError):continue
 return deflections,actions
