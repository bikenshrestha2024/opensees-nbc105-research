"""Reproducible specimen-specific deterministic Steel02 calibration; not project approval."""
from pathlib import Path
import json,csv,time,hashlib
import numpy as np
from scipy.optimize import least_squares
import openseespy.opensees as ops
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
ROOT=Path(__file__).resolve().parent

def predict(p,strains):
 fy,E,b,cr1,cr2,a1,a3=p
 ops.wipe();ops.uniaxialMaterial('Steel02',1,fy,E,b,20.,cr1,cr2,a1,1.,a3,1.,0.);ops.testUniaxialMaterial(1);ops.setStrain(0.)
 result=[]
 for e in strains:ops.setStrain(float(e));result.append(ops.getStress())
 ops.wipe();return np.asarray(result)
def metrics(pred,obs):
 r=pred-obs;return dict(RMSE_MPa=float(np.sqrt(np.mean(r*r))),MAE_MPa=float(np.mean(abs(r))),max_absolute_error_MPa=float(max(abs(r))),n=len(r))
def run(output=None):
 start=time.perf_counter();out=Path(output) if output else ROOT/'results';out.mkdir(parents=True,exist_ok=True)
 strain=np.fromstring((ROOT/'data/stress.1.coords').read_text().replace(',',' '),sep=' ');stress=np.fromstring((ROOT/'data/calDataField.csv').read_text().replace(',',' '),sep=' ')
 if len(strain)!=len(stress) or len(strain)!=342:raise ValueError('Unexpected source protocol/data shape')
 # Full history always propagated. Residuals use only first 75%; last quarter withheld from fitting.
 n=int(len(strain)*.75);low=np.array([300,150000,0,.001,.001,0,0]);high=np.array([700,250000,.2,.999,.2,.1,.1]);scale=np.array([500,200000,.02,1,.15,.02,.02]);initial=np.array([500,200000,.01,.925,.15,.01,.01]);fits=[]
 for b in [.01,.03]:
  x=initial.copy();x[2]=b
  fit=least_squares(lambda z:(predict(z*scale,strain)[:n]-stress[:n])/500,x/scale,bounds=(low/scale,high/scale),max_nfev=1200,ftol=1e-9,xtol=1e-9,gtol=1e-9)
  fits.append(fit);print('fit',fit.cost,fit.nfev,flush=True)
 fit=min(fits,key=lambda f:f.cost);params=fit.x*scale;pred=predict(params,strain)
 keys=['Fy_MPa','E_MPa','b','cR1','cR2','a1','a3'];card=dict(model='Steel02',specimen='SimCenter qfem-0019 published single coupon',status='EXPERIMENTAL DATA FIT - PROJECT TRANSFER NOT APPROVED',parameters=dict(zip(keys,map(float,params))),fixed_parameters=dict(R0=20.,a2=1.,a4=1.,sigInit=0.),training=metrics(pred[:n],stress[:n]),withheld_tail=metrics(pred[n:],stress[n:]),full_history=metrics(pred,stress),training_samples=n,withheld_samples=len(strain)-n,validation_scope='Withheld temporal tail of SAME coupon, conditioned on prior loading. Not independent specimen validation. No Fe415/Fe500/Fe550 grade equivalence established.',optimizer=dict(method='bounded nonlinear least squares, two starts',success=bool(fit.success),message=fit.message,nfev=fit.nfev),elapsed_s=time.perf_counter()-start,sources=json.loads((ROOT/'data/provenance.json').read_text()),documentation='https://nheri-simcenter.github.io/quoFEM-Documentation/common/user_manual/examples/desktop/qfem-0019/README.html',units='Stress MPa, strain dimensionless; structural stress kN/m2 = MPa * 1000')
 (out/'Steel02_Calibrated_Coupon.json').write_text(json.dumps(card,indent=2),encoding='utf8')
 with (out/'Steel02_Comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['step','strain','measured_MPa','predicted_MPa','residual_MPa','subset'])
  for i,(e,y,z) in enumerate(zip(strain,stress,pred)):w.writerow([i,e,y,z,z-y,'training' if i<n else 'withheld_tail'])
 fig=Figure(figsize=(12,8),layout='constrained');FigureCanvasAgg(fig);a=fig.subplots(2,2)
 a[0,0].plot(strain,stress,label='Measured',color='black');a[0,0].plot(strain,pred,label='Steel02 fitted',alpha=.75);a[0,0].set(xlabel='Strain',ylabel='Stress (MPa)',title='Experimental coupon cyclic response');a[0,0].legend()
 a[0,1].plot(stress,label='Measured');a[0,1].plot(pred,label='Predicted');a[0,1].axvline(n,color='black',ls='--',label='Withheld tail starts');a[0,1].set(xlabel='Ordered sample',ylabel='Stress (MPa)');a[0,1].legend()
 a[1,0].plot(pred-stress);a[1,0].axvline(n,color='black',ls='--');a[1,0].set(xlabel='Ordered sample',ylabel='Residual (MPa)')
 a[1,1].scatter(stress[:n],pred[:n],s=9,label='Training');a[1,1].scatter(stress[n:],pred[n:],s=9,label='Withheld tail');a[1,1].plot([-750,750],[-750,750],'k--');a[1,1].set(xlabel='Measured (MPa)',ylabel='Predicted (MPa)');a[1,1].legend()
 for ax in a.flat:ax.grid(alpha=.2)
 fig.savefig(out/'Steel02_Experimental_Fit.png',dpi=160)
 # Regenerate the application card and workbook at the selected output location.
 from components.validation.grade_cards import simulate
 with (out/'protocol.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['strain']);w.writerows([[float(e)] for e in strain])
 cp=card['parameters'];fp=card['fixed_parameters'];application=dict(model='Steel02',grade='SimCenter single coupon - calibrated',status=card['status'],parameters=dict(Fy_MPa=cp['Fy_MPa'],E_MPa=cp['E_MPa'],b=cp['b'],R0=fp['R0'],cR1=cp['cR1'],cR2=cp['cR2'],a1=cp['a1'],a2=fp['a2'],a3=cp['a3'],a4=fp['a4']),protocol_csv=str((out/'protocol.csv').resolve()),project_transfer_approved=False)
 (out/'Steel02_Application_Card.json').write_text(json.dumps(application,indent=2),encoding='utf8');simulate(application,out/'Native_Curve_Export')
 print(json.dumps(card,indent=2));return card
if __name__=='__main__':
 import argparse,sys
 sys.path.insert(0,str(ROOT.parent))
 parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args();run(args.output)
