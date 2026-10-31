"""Wall validation workbench. Numerical verification is distinct from experiment validation.
Run in a separate process: OpenSees wipe() destroys the current domain.
"""
from pathlib import Path
import argparse, ast, csv, hashlib, json, math, sys, time
from datetime import datetime
ROOT=Path(__file__).resolve().parents[2]
SOURCES={
 'kolozvari2023':{'doi':'https://doi.org/10.1016/j.engstruct.2023.116700','documentation':'https://kkolozvari.github.io/E-SFI-MVLEM-3D/','specimens':['SD-06-00','SD-06-45'],'status':'PENDING_EXPERIMENTAL_REPRODUCTION','note':'Author documentation has response figures, not a complete machine-readable specimen/data package. PEER 2015 material card is NOT these specimens.'},
 'lu2015':{'doi':'https://doi.org/10.1016/j.finel.2015.01.006','documentation':'https://openseespydoc.readthedocs.io/en/latest/src/RCshearwall.html','repository':'https://github.com/zhuminjie/OpenSeesPyDoc/tree/master/pyExamples','note':'Published OpenSeesPy conversion with boundary reinforcement, N-m units. Not the project core.'},
 'regularization':{'url':'https://peer.berkeley.edu/sites/default/files/publications/peer_2024_11_final.pdf','note':'Stokley and Lowes: flexure-controlled walls; review mesh and softening regularization before transfer.'}}
CHECKS={
 'formulation_and_native_commands':'Native creation and actual solver return codes',
 'units_and_density':'Stress/force/length/mass conversion; self-weight counted once',
 'material_monotonic_and_cyclic':'Concrete tension/compression, steel reversal, FSAM panel response',
 'axial_equilibrium':'Applied gravity versus support reaction',
 'rigid_body_and_orientation':'Rigid translation/rotation, local axes and reversed panel ordering',
 'elastic_bending_and_shear':'Independent analytical patch tests and deformation partition',
 'cyclic_experiment':'Signed envelope, unloading/reloading, pinching, residual displacement, energy per cycle',
 'mesh_objectivity':'Mesh and macro-fiber refinement with fracture-energy regularization',
 'biaxial_and_torsion':'Nonplanar shared corners, 0/45/90 degree loading and torsion',
 'openings_and_coupling':'Actual openings, coupling members and corner connectivity',
 'out_of_plane_and_instability':'Out-of-plane bending/buckling and geometric nonlinearity applicability',
 'dynamic_convergence':'Time-step refinement, convergence recovery, mass and damping sensitivity',
 'independent_validation':'Different specimen than calibration; applicable axial-load/aspect/detail range',
 'building_transfer':'Actual unconfined core reinforcement/materials and gravity/modal checks'}

def write_csv(path,rows):
 if not rows:return
 with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def analysis(o,step):
 o.constraints('Transformation');o.numberer('RCM');o.system('UmfPack')
 o.test('NormDispIncr',1e-9,80);o.algorithm('Newton');o.integrator('LoadControl',step);o.analysis('Static')

def esfi(out,element='E_SFI_MVLEM_3D'):
 """PEER-2015-material numerical smoke test of the 2023 element, NOT SD-06 validation."""
 import openseespy.opensees as o
 from Define_Section_V109 import define_wall_reference_materials
 o.wipe();o.model('basic','-ndm',3,'-ndf',6)
 for tag,xyz in [(1,(0,0,0)),(2,(1.2,0,0)),(3,(1.2,0,.3)),(4,(0,0,.3))]:o.node(tag,*xyz)
 for n in (1,2):o.fix(n,1,1,1,1,1,1)
 for n in (3,4):o.fix(n,0,1,0,1,0,1);o.mass(n,10,10,10,0,0,0)
 define_wall_reference_materials(o,'kN-m')
 o.element(element,1,1,2,3,4,5,'-thick',*[.15]*5,'-width',*[.24]*5,'-mat',*[906]*5,'-CoR',.4,'-ThickMod',.63,'-Poisson',.25,'-Density',0.)
 o.timeSeries('Linear',1);o.pattern('Plain',1,1)
 for n in (3,4):o.load(n,0,0,-300,0,0,0)
 analysis(o,.1);code=o.analyze(10);o.reactions();reaction=sum(o.nodeReaction(n,3) for n in (1,2))
 if code:raise RuntimeError(element+' gravity failed: '+str(code))
 o.loadConst('-time',0);o.wipeAnalysis()
 o.timeSeries('Path',2,'-dt',.005,'-values',*[.01*math.sin(i*.1) for i in range(101)])
 o.pattern('UniformExcitation',2,1,'-accel',2)
 o.constraints('Plain');o.numberer('RCM');o.system('UmfPack');o.test('NormDispIncr',1e-9,40);o.algorithm('Newton');o.integrator('Newmark',.5,.25);o.analysis('Transient')
 rows=[]
 for i in range(10):
  if o.analyze(1,.005):raise RuntimeError(element+' transient increment did not converge')
  o.reactions();rows.append(dict(displacement_m=o.nodeDisp(3,1),base_shear_kN=-sum(o.nodeReaction(n,1) for n in (1,2))))
 write_csv(out/'esfi_numerical_history.csv',rows)
 o.wipe()
 return {'status':'NUMERICAL_SMOKE_COMPLETED','gravity_relative_error':abs(reaction-600)/600,'history_rows':len(rows),'material_scope':'PEER 2015 RW-A15-P10-S78 web card; not Kolozvari 2023 SD-06 or project calibration','boundary_scope':'Single restrained patch; not a core corner/biaxial benchmark','loading':'0.05 s low-amplitude synthetic acceleration in m/s2; not earthquake validation'}

def lu(out,full=False):
 """Run checked official model construction; replace unchecked original solver loop."""
 import openseespy.opensees as o
 source=ROOT/'wall_validation_sources/RCshearwall.py'
 tree=ast.parse(source.read_text(encoding='utf-8-sig'))
 allowed={'wipe','model','nDMaterial','uniaxialMaterial','section','node','element','fixY'}
 # Only execute literal model-definition calls; no imports, file writes, plotting or original unchecked analyses.
 env={name:getattr(o,name) for name in allowed};env['ShellType']='ShellNLDKGQ'
 for node in tree.body:
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id in allowed:
   exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),{'__builtins__':{}},env)
 o.timeSeries('Linear',1);o.pattern('Plain',1,1);o.load(53,0,-246000,0,0,0,0)
 analysis(o,.1);o.test('NormDispIncr',1e-4,200);o.algorithm('BFGS','-count',100);code=o.analyze(10);o.reactions();reaction=sum(o.nodeReaction(n,2) for n in range(1,6))
 if code:raise RuntimeError('Lu specimen gravity failed: '+str(code))
 o.loadConst('-time',0);o.wipeAnalysis();o.timeSeries('Linear',2);o.pattern('Plain',2,2);o.load(53,1,0,0,0,0,0)
 o.constraints('Penalty',1e20,1e20);o.numberer('RCM');o.system('BandGeneral');o.test('NormDispIncr',1e-5,1000);o.algorithm('KrylovNewton');o.integrator('DisplacementControl',53,1,1e-5);o.analysis('Static')
 targets=[.0001,-.0001,0.]
 if full:targets=[float(x) for x in (ROOT/'wall_validation_sources/RCshearwall_Load_input.txt').read_text(encoding='utf-8-sig').split()]
 rows=[dict(displacement_m=o.nodeDisp(53,1),base_shear_kN=0.)]
 for target in targets:
  for _ in range(10000):
   remaining=target-o.nodeDisp(53,1)
   if abs(remaining)<1e-10:break
   o.integrator('DisplacementControl',53,1,math.copysign(min(abs(remaining),1e-5),remaining))
   if o.analyze(1):
    write_csv(out/'lu_numerical_history.csv',rows)
    raise RuntimeError('Lu cyclic increment failed at '+str(o.nodeDisp(53,1))+' m; partial converged rows retained')
   o.reactions();rows.append(dict(displacement_m=o.nodeDisp(53,1),base_shear_kN=-sum(o.nodeReaction(n,1) for n in range(1,6))/1000))
  else:raise RuntimeError('Target step bound exceeded')
 write_csv(out/'lu_numerical_history.csv',rows);o.wipe()
 return {'status':'CYCLIC_RUN_COMPLETED' if full else 'NUMERICAL_SMOKE_COMPLETED','gravity_relative_error':abs(reaction-246000)/246000,'history_rows':len(rows),'experimental_validation':'NOT_ACCEPTED: needs protocol alignment, metric review and independent validation','native_units':'N,m,s; outputs converted to kN,m','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'boundary_scope':'Official specimen includes special boundary reinforcement. Do not copy into unconfined core.'}

def compare(reference,simulation,out):
 """Compare signed peaks/whole-path work without unsafe cyclic displacement interpolation."""
 def read(p):
  with Path(p).open(encoding='utf-8-sig') as f:r=list(csv.DictReader(f))
  data=[(float(x['displacement_m']),float(x['base_shear_kN'])) for x in r]
  if len(data)<2 or not all(math.isfinite(v) for row in data for v in row):raise ValueError('At least two finite samples required')
  return data
 a,b=read(reference),read(simulation)
 def metrics(r):return dict(positive_peak_kN=max(y for x,y in r),negative_peak_kN=min(y for x,y in r),net_path_work_kNm=sum(.5*(r[i][1]+r[i-1][1])*(r[i][0]-r[i-1][0]) for i in range(1,len(r))),final_displacement_m=r[-1][0],max_displacement_m=max(x for x,y in r),min_displacement_m=min(x for x,y in r))
 result={'reference':metrics(a),'simulation':metrics(b),'status':'METRICS_ONLY_NO_ACCEPTANCE','note':'Whole-path signed work is not dissipated cycle energy unless the path closes. Match protocol, sign, range and cycles before judging errors. No universal tolerance assumed.'}
 (out/'comparison.json').write_text(json.dumps(result,indent=2));return result

def run(out,route='both',full=False):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
 report={'started_at':datetime.now().astimezone().isoformat(),'sources':SOURCES,'checks':{k:{'status':'NOT_EVALUATED','required_evidence':v} for k,v in CHECKS.items()},'routes':{},'project_design_approval':False}
 for name,func in [('kolozvari2023',esfi),('lu2015',lambda p:lu(p,full))]:
  if route not in ('both',name):continue
  case_start=time.perf_counter()
  try:report['routes'][name]=func(out)
  except Exception as exc:report['routes'][name]={'status':'FAILED','error':str(exc)}
  report['routes'][name]['elapsed_s']=time.perf_counter()-case_start
 report['checks']['formulation_and_native_commands']={'status':'PARTIAL','required_evidence':'See per-route native run results. Creation/convergence alone is not physical validation.'}
 report['checks']['axial_equilibrium']={'status':'MEASURED_NOT_ACCEPTED','required_evidence':'Per-route gravity relative error is reported for completed diagnostics. Set project acceptance criteria separately.'}
 report['elapsed_s']=time.perf_counter()-start
 report['scope']='Numerical diagnostics and validation plan only. Not all checks implemented or passed; project wall remains uncalibrated.'
 (out/'wall_validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 write_csv(out/'validation_matrix.csv',[dict(check=k,**v) for k,v in report['checks'].items()])
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(11,4.5))
 for ax,name,title in zip(axes,['esfi','lu'],['E-SFI: PEER material patch, not SD-06','Lu: official boundary specimen']):
  f=out/(name+'_numerical_history.csv')
  if f.exists():
   with f.open(encoding='utf-8-sig') as s:rows=list(csv.DictReader(s))
   ax.plot([1000*float(r['displacement_m']) for r in rows],[float(r['base_shear_kN']) for r in rows])
  if name=='lu':
   reference=ROOT/'wall_validation_sources/RCshearwall_TestOutput.txt'
   values=[list(map(float,line.split())) for line in reference.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
   ax.plot([v[0] for v in values],[v[1] for v in values],color='gray',alpha=.6,label='Published test, mm/kN');ax.legend()
  ax.set(title=title,xlabel='Displacement (mm)',ylabel='Base shear (kN)');ax.grid()
 fig.tight_layout();fig.savefig(out/'wall_diagnostics.png',dpi=140);plt.close(fig)
 print(json.dumps(report['routes'],indent=2),flush=True);return report

if __name__=='__main__':
 sys.path.insert(0,str(ROOT))
 p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'Wall_Validation_Results'));p.add_argument('--route',choices=['both','kolozvari2023','lu2015'],default='both');p.add_argument('--full-lu-cyclic',action='store_true');a=p.parse_args();run(a.output,a.route,a.full_lu_cyclic)
