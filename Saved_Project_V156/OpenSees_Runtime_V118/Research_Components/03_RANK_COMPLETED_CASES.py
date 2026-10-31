"""Rank COMPLETE case matrix by paired-record mean normalized edge drift.
Usage: python 03_RANK_COMPLETED_CASES.py completed_matrix.csv ranking.csv
No missing/failed case can be promoted to a feasible optimum.
"""
import csv,sys,math,collections
from pathlib import Path
def rank(source,target):
 with Path(source).open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
 designs=collections.defaultdict(list)
 for r in rows:designs[(r['configuration'],r['outrigger_storey'],r['device'])].append(r)
 results=[]
 for key,rr in designs.items():
  completed={};errors=[]
  for r in rr:
   tag=(r['limit_state'],r['record_pair'],r['orientation'])
   try:
    if r['status']!='COMPLETED_FULL_RECORD':raise ValueError('unfinished/failed')
    value=float(r['peak_edge_drift_ratio'])
    if not math.isfinite(value) or value<0:raise ValueError('invalid drift')
    if tag in completed:raise ValueError('duplicate case')
    completed[tag]=value
   except (ValueError,KeyError):errors.append(tag)
  means={};maxima={}
  for state in ('ULS','SLS'):
   pair=[]
   for n in range(1,9):
    x=(state,f'PAIR_{n:02d}','XY');y=(state,f'PAIR_{n:02d}','YX')
    if x in completed and y in completed:pair.append(max(completed[x],completed[y]))
   if len(pair)==8:means[state]=sum(pair)/8;maxima[state]=max(pair)
  complete=not errors and len(completed)==32 and len(means)==2
  row=dict(configuration=key[0],outrigger_storey=key[1],device=key[2],status='COMPLETE' if complete else 'INCOMPLETE_NOT_RANKED',J='',ULS_pair_mean_drift=means.get('ULS',''),SLS_pair_mean_drift=means.get('SLS',''),ULS_max_drift=maxima.get('ULS',''),SLS_max_drift=maxima.get('SLS',''),conservative_each_run_drift_screen='NOT_EVALUATED',note='Drift ranking only; device capacities, residuals, acceleration and member adequacy still required')
  if complete:
   row['J']=max(means['ULS']/.025,means['SLS']/.006);row['conservative_each_run_drift_screen']='PASS' if maxima['ULS']<=.025 and maxima['SLS']<=.006 else 'FAIL'
  results.append(row)
 results.sort(key=lambda r:float(r['J']) if r['J']!='' else float('inf'))
 with Path(target).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 return results
if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('Usage: 03_RANK_COMPLETED_CASES.py completed_matrix.csv ranking.csv')
 r=rank(*sys.argv[1:]);print('Ranked complete designs:',sum(x['status']=='COMPLETE' for x in r),'of',len(r))
