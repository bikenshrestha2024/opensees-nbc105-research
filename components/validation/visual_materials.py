"""Native material/device verification and visual response playback. Not project calibration."""
from pathlib import Path
import csv,json,math,time,argparse,sys
ROOT=Path(__file__).resolve().parents[2]
SOURCES={
'Concrete01':{'documentation':'https://openseespydoc.readthedocs.io/en/latest/src/Concrete01.html','literature':'Kent and Park (1971), Flexural Members with Confined Concrete, ASCE Structural Division 97(7),1969-1990; Karsan and Jirsa (1969), Behavior of Concrete Under Compressive Loadings,95(12),2543-2563. Formulation attribution; illustrative numerical values below are NOT fitted specimen parameters.'},
'Steel02':{'documentation':'https://openseespydoc.readthedocs.io/en/latest/src/steel02.html','literature':'Menegotto and Pinto (1973), IABSE reports13,15-22, https://www.e-periodica.ch/digbib/view?lang=en&pid=bse-re-001%3A1973%3A13%3A%3A9 ; Giuffre-Menegotto-Pinto formulation with isotropic hardening per OpenSees documentation. R0=20,cR1=.925,cR2=.15 are documented transition choices; Fy,E,b in this benchmark are illustrative.'},
'FVD':{'documentation':'https://opensees.berkeley.edu/wiki/index.php?title=ViscousDamper_Material','literature':'Akcelyan, Lignos, Hikino (2018), Adaptive Numerical Method Algorithms for Nonlinear Viscous and Bilinear Oil Damper Models Subjected to Dynamic Loading, Soil Dynamics and Earthquake Engineering113,488-502. Akcelyan et al.(2016), J.Struct.Eng.142(6),04016024. Published command example: K=300kN/mm,Cd=280.3kN(s/mm)^0.3,alpha=.30; sinusoidal amplitudes12/24/36mm,f=.5Hz. Those are example-device parameters, not your damper.'},
'BRB':{'documentation':'https://openseespydoc.readthedocs.io/en/latest/src/steel02.html','literature':'Black, Makris and Aiken (2002), Component Testing, Stability Analysis and Characterization of Buckling-Restrained Unbonded Braces, PEER2002/08, https://peer.berkeley.edu/publications/2002-08. This simplified symmetric Steel02 core is a mechanism illustration, not reproduction of that report or AISC qualification. Effective yielding length, end zones, compression overstrength, fatigue/fracture and casing stability require test data.'}}
SCOPE='Numerical verification / literature-informed examples only. No project calibration, experimental validation or NBC design approval is inferred.'

def write(path,rows):
 with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def ramp(targets,n=80):
 values=[0.]
 for b in targets:
  a=values[-1];values.extend(a+(b-a)*i/n for i in range(1,n+1))
 return values

def uniaxial(name,parameters,values):
 import openseespy.opensees as o
 o.wipe();o.uniaxialMaterial(name,1,*parameters);o.testUniaxialMaterial(1);rows=[]
 for i,e in enumerate(values):
  o.setStrain(float(e));rows.append(dict(step=i,x=float(e),y=float(o.getStress()),tangent=float(o.getTangent())))
 o.wipe();return rows

def concrete(out):
 # Stress MPa in the material coupon only. Structural models use kN,m.
 fc,e0,fu,eu=-30.,-.002,-6.,-.006
 monotonic=uniaxial('Concrete01',[fc,e0,fu,eu],ramp([-.008],400));cyclic=uniaxial('Concrete01',[fc,e0,fu,eu],ramp([-.0005,0.,-.001,0.,-.002,0.,-.004,0.,-.006,0.,.001]))
 def exact(e):
  if e>=0:return 0.
  if e>=e0:return fc*(2*e/e0-(e/e0)**2)
  if e>eu:return fc+(fu-fc)*(e-e0)/(eu-e0)
  return fu
 error=max(abs(r['y']-exact(r['x'])) for r in monotonic)
 write(out/'Concrete01_monotonic.csv',monotonic);write(out/'Concrete01_cyclic.csv',cyclic)
 return dict(parameters=dict(fpc_MPa=fc,epsc0=e0,fpcu_MPa=fu,epsU=eu),checks=dict(monotonic_envelope_max_error_MPa=error,zero_tension_MPa=cyclic[-1]['y']),status='NUMERICAL_ENVELOPE_CHECK',parameter_basis='Illustrative unconfined coupon, not M45 project data',x_label='Strain',y_label='Stress (MPa)',files=['Concrete01_monotonic.csv','Concrete01_cyclic.csv'])

def steel(out,brb=False):
 fy,E,b=355.,200000.,.01
 values=ramp([.0005,-.0005,.002,-.002,.005,-.005,.01,-.01,0.])
 rr=uniaxial('Steel02',[fy,E,b,20.,.925,.15,0.,1.,0.,1.],values)
 name='BRB' if brb else 'Steel02'
 initial=rr[1]['y']/rr[1]['x'];checks=dict(initial_modulus_MPa=initial,initial_modulus_reference_MPa=E,initial_modulus_relative_error=abs(initial-E)/E)
 if brb:
  A,L=.002,3. # selected illustration; uniform yielding length, not full brace work-point calibration
  for r in rr:r.update(x=r['x']*L,y=r['y']*1000*A)
  params=dict(Fy_MPa=fy,E_MPa=E,b=b,R0=20,cR1=.925,cR2=.15,a1=0,a2=1,a3=0,a4=1,core_area_m2=A,yielding_length_m=L)
  checks.update(yield_force_reference_kN=fy*1000*A,elastic_axial_stiffness_kN_m=E*1000*A/L)
  import openseespy.opensees as o
  o.wipe();o.model('basic','-ndm',2,'-ndf',2);o.node(1,0.,0.);o.node(2,L,0.);o.fix(1,1,1);o.fix(2,0,1)
  o.uniaxialMaterial('Steel02',1,fy*1000,E*1000,b,20.,.925,.15,0.,1.,0.,1.);o.element('corotTruss',1,1,2,A,1)
  o.timeSeries('Linear',1);o.pattern('Plain',1,1);o.load(2,1.,0.);o.constraints('Plain');o.numberer('RCM');o.system('BandGeneral');o.test('NormDispIncr',1e-10,25);o.algorithm('Newton');o.integrator('DisplacementControl',2,1,1e-6);o.analysis('Static')
  errors=[]
  for row in rr:
   delta=row['x']-o.nodeDisp(2,1)
   if abs(delta)>1e-15:
    o.integrator('DisplacementControl',2,1,delta)
    if o.analyze(1):raise RuntimeError('BRB idealized core displacement increment failed')
   force=float(o.eleResponse(1,'forces')[2]);errors.append(abs(force-row['y']));row['native_corotTruss_force_kN']=force
  checks['coupon_vs_corotTruss_max_error_kN']=max(errors);o.wipe()

 else:params=dict(Fy_MPa=fy,E_MPa=E,b=b,R0=20,cR1=.925,cR2=.15,a1=0,a2=1,a3=0,a4=1)
 write(out/(name+'_cyclic.csv'),rr)
 return dict(parameters=params,checks=checks,status='IDEALIZED_CORE_RESPONSE' if brb else 'NUMERICAL_COUPON_RESPONSE',parameter_basis='Illustrative values; not manufacturer/test calibration',x_label='Core extension (m)' if brb else 'Strain',y_label='Axial force (kN)' if brb else 'Stress (MPa)',files=[name+'_cyclic.csv'])

def damper_history(K,C,alpha,dt=.002,analytic=False):
 import openseespy.opensees as o
 o.wipe();o.model('basic','-ndm',1,'-ndf',1)
 for n in (1,2,3):o.node(n,0.)
 o.fix(1,1);o.mass(3,1.)
 o.uniaxialMaterial('ViscousDamper',1,K,C,alpha);o.uniaxialMaterial('Elastic',2,1.)
 o.element('zeroLength',1,1,2,'-mat',1,'-dir',1);o.element('zeroLength',2,1,3,'-mat',2,'-dir',1)
 # Dummy uncoupled oscillator keeps the equation system nonempty; its motion stays zero.
 amplitudes=[.012] if analytic else [.012,.024,.036];duration=4.*len(amplitudes);count=round(duration/dt);w=math.pi
 def imposed(t):
  if analytic:return amplitudes[0]*(1-math.cos(w*t))
  seg=min(int(t/4.),len(amplitudes)-1);return amplitudes[seg]*math.sin(w*(t-4*seg))
 values=[imposed(i*dt) for i in range(count+1)]
 o.timeSeries('Path',1,'-dt',dt,'-values',*values);o.pattern('Plain',1,1);o.sp(2,1,1.)
 # Penalty enforces the prescribed motion while retaining consistent velocity at the device DOF.
 # Transformation SP eliminates this velocity in the tested build and is unsuitable for this driver.
 o.constraints('Penalty',1e12,1e12);o.numberer('RCM');o.system('BandGeneral');o.test('NormDispIncr',1e-10,25);o.algorithm('Newton');o.integrator('Newmark',.5,.25);o.analysis('Transient');rr=[dict(step=0,time_s=0.,x=0.,y=0.,velocity_m_s=0.,reference_kN=0.,prescribed_m=0.)]
 for i in range(1,count+1):
  rc=o.analyze(1,dt)
  if rc:raise RuntimeError('Damper transient failed at step '+str(i)+' code '+str(rc))
  t=o.getTime();force=float(o.eleResponse(1,'force')[1]);reference=0.
  if analytic:
   a=K/C;reference=K*.012*w/(a*a+w*w)*(a*math.sin(w*t)-w*math.cos(w*t)+w*math.exp(-a*t))
  rr.append(dict(step=i,time_s=t,x=o.nodeDisp(2,1),y=force,velocity_m_s=o.nodeVel(2,1),reference_kN=reference,prescribed_m=imposed(t)))
 o.wipe();return rr

def fvd(out):
 K=300.*1000;C=280.3*1000**.3
 linear=damper_history(K,5000.,1.,analytic=True);fine=damper_history(K,5000.,1.,dt=.001,analytic=True);nonlinear=damper_history(K,C,.3)
 for name,r in [('FVD_linear_reference.csv',linear),('FVD_linear_refined.csv',fine),('FVD_nonlinear.csv',nonlinear)]:write(out/name,r)
 err=lambda rows:max(abs(r['y']-r['reference_kN']) for r in rows)
 cycle=[r for r in linear if r['time_s']>=2.-1e-9];work=sum(.5*(a['y']+b['y'])*(b['x']-a['x']) for a,b in zip(cycle,cycle[1:]));expected_work=math.pi*.012**2*5000.*math.pi*K*K/(K*K+(5000.*math.pi)**2)
 return dict(parameters=dict(K_kN_m=K,Cd_kN_s_m_alpha=C,alpha=.3,frequency_Hz=.5,amplitudes_m=[.012,.024,.036],dt_s=.002,penalty_kN_m=1e12),checks=dict(linear_steady_cycle_work_kNm=work,linear_steady_cycle_reference_kNm=expected_work,linear_cycle_work_relative_error=abs(work-expected_work)/expected_work,linear_Maxwell_error_kN=err(linear),refined_error_kN=err(fine),prescribed_motion_error_m=max(abs(r['x']-r['prescribed_m']) for r in nonlinear)),status='NUMERICAL_LINEAR_REFERENCE_AND_NONLINEAR_EXAMPLE',parameter_basis='Nonlinear values from official ViscousDamper example converted from mm to m. Linear alpha=1,C=5000 selected for independent analytical ODE check, not experimental device.',x_label='Device extension (m)',y_label='Device force (kN)',files=['FVD_linear_reference.csv','FVD_nonlinear.csv'])

def figure(out,name,case):
 from matplotlib.figure import Figure
 fig=Figure(figsize=(11,7),layout='constrained');ax=fig.add_subplot(221);history=fig.add_subplot(222);scheme=fig.add_subplot(223);notes=fig.add_subplot(224)
 for file in case['files']:
  with (out/file).open(encoding='utf-8-sig') as f:rr=list(csv.DictReader(f))
  x=[float(r['x']) for r in rr];y=[float(r['y']) for r in rr];ax.plot(x,y,label=file);history.plot([float(r.get('time_s',r['step'])) for r in rr],y,label=file)
  if name=='BRB':ax.plot(x,[float(r['native_corotTruss_force_kN']) for r in rr],ls='--',label='Native corotTruss core verification')
  if name=='FVD' and 'linear_reference' in file:ax.plot(x,[float(r['reference_kN']) for r in rr],ls='--',label='Independent linear Maxwell solution')
 ax.set(xlabel=case['x_label'],ylabel=case['y_label'],title=name+' response path');history.set(xlabel='Time (s) for FVD; protocol step otherwise',ylabel=case['y_label'],title='Recorded native response');ax.legend(fontsize=7);ax.grid(alpha=.25);history.grid(alpha=.25)
 scheme.set(xlim=(0,10),ylim=(-2,2),title='Idealization schematic (not specimen photograph)')
 from matplotlib.patches import Rectangle
 if name=='FVD':
  scheme.plot([1,2],[0,0],color='#35617c');scheme.plot([2+i*.25 for i in range(9)],[0]+[.28*(-1)**i for i in range(7)]+[0],color='#35617c',lw=2);scheme.plot([4,5],[0,0],color='#35617c');scheme.add_patch(Rectangle((5,-.4),2,.8,fill=False,lw=2));scheme.plot([6,6],[-.3,.3],color='#bb2457',lw=3);scheme.plot([6,9],[0,0],color='#35617c',lw=2);scheme.text(2, .55,'K');scheme.text(5,.55,'Cd, alpha')
 else:
  scheme.add_patch(Rectangle((2,-.22),6,.44,fill=False,lw=2,edgecolor='#35617c'));scheme.plot([1,9],[0,0],lw=3,color='#35617c')
  if name=='BRB':scheme.add_patch(Rectangle((2,-.55),6,1.1,fill=False,lw=2,edgecolor='gray',linestyle='--'));scheme.text(2,.7,'Casing shown; restraint not explicitly solved',fontsize=8)
 scheme.scatter([1,9],[0,0],s=100);scheme.annotate('Imposed strain / extension',(8,0),xytext=(5,1),arrowprops=dict(arrowstyle='->'));scheme.text(2,-1,'Coupon' if name in ('Concrete01','Steel02') else 'Uniform yielding core; casing not solved' if name=='BRB' else 'Spring K + nonlinear dashpot in series');scheme.axis('off')
 import textwrap
 notes.axis('off');notes.text(0,1,'\n'.join(textwrap.wrap(case['parameter_basis']+' '+SCOPE,58)),va='top',fontsize=9);fig.suptitle(name+' | '+case['status'],fontsize=13);return fig

def run(out,wall=False):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);start=time.perf_counter();report=dict(scope=SCOPE,sources=SOURCES,cases={},started=__import__('datetime').datetime.now().astimezone().isoformat())
 for name,func in [('Concrete01',concrete),('Steel02',steel),('FVD',fvd),('BRB',lambda p:steel(p,True))]:
  t=time.perf_counter();print('[VALIDATION START]',name,flush=True)
  try:
   case=func(out);case['elapsed_s']=time.perf_counter()-t;report['cases'][name]=case
   fig=figure(out,name,case);fig.savefig(out/(name+'.png'),dpi=150)
   print('[VALIDATION COMPLETE]',name,case['checks'],flush=True)
  except Exception as e:report['cases'][name]=dict(status='FAILED',error=str(e),elapsed_s=time.perf_counter()-t)
 if wall:
  from components.validation.wall_validation import run as wall_run
  report['walls']=wall_run(out/'Walls',route='both')
  from components.validation.wall_validation import esfi
  original=out/'Walls/SFI_original';original.mkdir(exist_ok=True)
  import subprocess
  worker=ROOT/'components/validation/sfi_worker.py'
  completed=subprocess.run([sys.executable,str(worker),str(original.resolve())],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace')
  (original/'native_process.log').write_text(completed.stdout,encoding='utf8')
  result_file=original/'worker_result.json'
  report['original_SFI_2021']=json.loads(result_file.read_text(encoding='utf8')) if result_file.is_file() else dict(status='FAILED',error='Native worker terminated without a result',exit_code=completed.returncode)
  report['original_SFI_2021']['native_exit_code']=completed.returncode
 report['original_SFI_source']='Kolozvari et al.(2021), Journal of Building Engineering44,102946; https://kkolozvari.github.io/SFI-MVLEM-3D/. Native patch attempt is separate from E-SFI2023; failure remains reported.'
 report['elapsed_s']=time.perf_counter()-start;report['finished']=__import__('datetime').datetime.now().astimezone().isoformat();report['project_approved']=False
 (out/'Validation_Report_V149.json').write_text(json.dumps(report,indent=2),encoding='utf8');(out/'Validation_V149.log').write_text(json.dumps(report,indent=2),encoding='utf8');return report

if __name__=='__main__':
 sys.path.insert(0,str(ROOT));parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'Material_Validation_Results_V149'));parser.add_argument('--walls',action='store_true');a=parser.parse_args();run(a.output,a.walls)
