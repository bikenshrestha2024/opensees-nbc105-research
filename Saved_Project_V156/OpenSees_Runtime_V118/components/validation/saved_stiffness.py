"""Reuse only model-matching static stiffness screens, never infer stiffness from periods."""
from pathlib import Path
import json,hashlib

def merge_saved_stiffness(folder,result):
 folder=Path(folder);source=folder/'OpenSees_Complete_Model_Data_V118.json';digest=hashlib.sha256(source.read_bytes()).hexdigest();imported=[];coverage=set()
 for p in sorted((folder/'OpenSees_Analysis_Results').rglob('Irregularity_*_E0_V132.json')):
  d=json.loads(p.read_text(encoding='utf-8-sig'))
  if d.get('model_sha256')!=digest:continue
  state=d.get('limit_state');case=d.get('response_case',p.name);axis='X' if '_X' in case else 'Y' if '_Y' in case else None
  if state not in ('ULS','SLS') or axis is None:continue
  rows=[dict(r) for r in d.get('checks',[]) if r.get('check','').startswith('Soft story') and r.get('value') is not None]
  if not rows:continue
  coverage.add((state,axis))
  for r in rows:r.update(check=state+' '+axis+' '+r['check'],note=str(r.get('note',''))+' | Model-matching centered static result: '+str(p));imported.append(r)
 if imported:
  result['checks']=[r for r in result['checks'] if r.get('clause')!='5.4.1.2']+list({(r['check'],str(r.get('storey'))):r for r in imported}.values())
  for state in ('ULS','SLS'):
   for axis in ('X','Y'):
    if (state,axis) not in coverage:result['checks'].append(dict(clause='5.4.1.2',check=state+' '+axis+' soft-storey coverage',storey='ALL',value=None,threshold=None,status='NOT EVALUATED',note='No matching centered static stiffness result. Calculate selected state(s).'))
 result['overall']='IRREGULAR' if any(r.get('status')=='IRREGULAR' for r in result['checks']) else 'INCOMPLETE' if any(r.get('status')=='NOT EVALUATED' for r in result['checks']) else 'NO TRIGGER FOUND'
 result['stiffness_import_coverage']=sorted([list(x) for x in coverage]);return result
