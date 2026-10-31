"""NBC 105:2025 §5.1.1 force/displacement Rayleigh estimate.

Reference: https://giwmscdnone.gov.np/media/files/NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf
The small reference lateral forces determine a displacement shape. Their
amplitude cancels in the Rayleigh quotient for a fixed linear stiffness.
This is a period-estimation diagnostic, not a ULS ESM eligibility override,
nor evidence that IS 16700 initial combination cases have been completed.
"""

from OpenSees_Timing_V130 import timed_outputs

__release__ = '134'
from pathlib import Path
import csv
import json
import math
import hashlib


@timed_outputs('Preliminary Rayleigh X-Y analysis','folder')
def run(folder, awx, awy, reference_fraction=.01):
    import openseespy.opensees as ops
    from OpenSees_Complete_Export_V118 import build_complete_model
    from OpenSees_Analysis_Stack_V110 import configure_nonlinear_static
    from openpyxl import Workbook
    from matplotlib.figure import Figure
    folder=Path(folder);out=folder/'OpenSees_Analysis_Results';out.mkdir(exist_ok=True)
    reference_fraction=float(reference_fraction)
    if not math.isfinite(reference_fraction) or reference_fraction<=0:raise ValueError('Reference fraction must be finite and positive.')
    model=folder/'OpenSees_Complete_Model_Data_V118.json'
    with (folder/'NBC105_ESM_Story_Weights_Assembled_V118.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
    rows.sort(key=lambda r:float(r['height_m']))
    weights=[float(r['dead_load_kN'])+.6*float(r['storage_live_load_kN'])+.3*float(r['other_live_load_kN']) for r in rows]
    if any(w<=0 for w in weights):raise ValueError('Positive reconciled seismic story weights are required.')
    H=max(float(r['height_m']) for r in rows);result={'story_weights_sha256':hashlib.sha256((folder/'NBC105_ESM_Story_Weights_Assembled_V118.csv').read_bytes()).hexdigest(),'standard':'NBC 105:2025 §5.1.1','model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'gravity_state':'assembled sustained gravity','torsion':'diaphragm rotations restrained during reference lateral perturbation','diagnostic_only':True}
    wb=Workbook();summary=wb.active;summary.title='Summary';summary.append(['Axis','Aw (m2)','Empirical T (s)','Amplified empirical T (s)','Rayleigh T (s)','Adopted T (s)'])
    fig=Figure(figsize=(11,6),layout='constrained');axes=fig.subplots(1,2)
    for axis,aw in [('X',awx),('Y',awy)]:
        aw=float(aw)
        if aw<=0:raise ValueError('Directional Aw must be positive and reviewed against first-story walls/openings.')
        empirical=.075/math.sqrt(aw)*H**.75
        k=1. if empirical<=.5 else 2. if empirical>=2.5 else 1.+(empirical-.5)/2.
        shape=[w*float(r['height_m'])**k for w,r in zip(weights,rows)]
        forces=[reference_fraction*sum(weights)*s/sum(shape) for s in shape]
        build_complete_model(folder,mode='elastic',preload=True)
        dof=1 if axis=='X' else 2
        masters=[int(r['master_node_tag']) for r in rows]
        # Establish the torsion-suppressed gravity equilibrium BEFORE taking
        # the baseline. Adding SP constraints with the lateral loads mixes a
        # gravity redistribution into di and makes the quotient amplitude-dependent.
        ops.timeSeries('Constant',990000);ops.pattern('Plain',990000,990000)
        for n in masters:ops.sp(n,6,0.)
        configure_nonlinear_static(ops,system='UmfPack',tolerance=1e-8,max_iterations=100)
        ops.integrator('LoadControl',0.)
        if ops.analyze(1)!=0:raise RuntimeError('Torsion-suppressed gravity equilibration failed.')
        ops.loadConst('-time',0.)
        baseline=[ops.nodeDisp(n,dof) for n in masters]
        tag=990001;ops.timeSeries('Linear',tag);ops.pattern('Plain',tag,tag)
        for n,f in zip(masters,forces):
            load=[0.]*6;load[dof-1]=f;ops.load(n,*load)
        ops.wipeAnalysis();configure_nonlinear_static(ops,system='UmfPack',tolerance=1e-8,max_iterations=100)
        ops.integrator('LoadControl',.1)
        if ops.analyze(10)!=0:raise RuntimeError(f'{axis} preliminary lateral analysis did not converge; no Rayleigh value was accepted.')
        u=[ops.nodeDisp(n,dof)-b for n,b in zip(masters,baseline)]
        denominator=9.80665*sum(f*d for f,d in zip(forces,u))
        if denominator<=0:raise ValueError(f'{axis} Rayleigh denominator is nonpositive; inspect displacement signs and constraints.')
        period=2*math.pi*math.sqrt(sum(w*d*d for w,d in zip(weights,u))/denominator)
        result[axis]=dict(Aw_m2=aw,empirical_period_s=empirical,amplified_empirical_s=1.25*empirical,period_s=period,adopted_period_s=min(period,1.25*empirical),rows=[dict(story=r['story_name'],height_m=float(r['height_m']),master_node=n,weight_kN=w,force_kN=f,displacement_m=d) for r,n,w,f,d in zip(rows,masters,weights,forces,u)])
        sheet=wb.create_sheet(axis+' Rayleigh');sheet.append(['Story','Height (m)','Master node','Wi (kN)','Fi (kN)','di (m)','Wi di2 (kN m2)','Fi di (kN m)'])
        for r in result[axis]['rows']:sheet.append([r['story'],r['height_m'],r['master_node'],r['weight_kN'],r['force_kN'],r['displacement_m'],r['weight_kN']*r['displacement_m']**2,r['force_kN']*r['displacement_m']])
        summary.append([axis,aw,empirical,1.25*empirical,period,min(period,1.25*empirical)])
        heights=[float(r['height_m']) for r in rows]
        axes[0].plot([v*1000 for v in u],heights,label=f'{axis}: T_R={period:.3f} s')
        axes[1].plot(forces,heights,label=axis)
    for ax in axes:ax.grid(alpha=.25);ax.legend();ax.set_ylabel('Elevation (m)')
    axes[0].set(title='Reference lateral displacement profiles',xlabel='Incremental translation (mm)')
    axes[1].set(title='Reference lateral floor forces',xlabel='Reference force Fi (kN)')
    fig.suptitle('NBC 105:2025 Rayleigh period estimate | preliminary elastic perturbation')
    for ext in ('png','pdf'):fig.savefig(out/('NBC105_Rayleigh_Preliminary_V123.'+ext),dpi=300)
    for sheet in wb:sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
    wb.save(out/'NBC105_Rayleigh_Preliminary_V123.xlsx')
    result['method_version']=124
    result['reference_fraction']=reference_fraction
    result['baseline_method']='Equilibrate torsion-suppressed gravity before applying reference forces; use incremental translation.'
    (out/'NBC105_Rayleigh_Preliminary_V123.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    import sys
    print(json.dumps(run(sys.argv[1],float(sys.argv[2]),float(sys.argv[3])),indent=2))
