"""Published RC portal parameters, kN-m-s adaptation; educational nonlinear demo.
Source: OpenSees Example 3.1 + OpenSeesPy RCFrameEarthquake.
Not the selected ETABS building and not an NBC design acceptance analysis.
"""
from pathlib import Path
import json,csv,math,time,re,datetime
import numpy as np
KIP=4.4482216152605;INCH=.0254;KSI=KIP/INCH**2;G=9.80665
SOURCES=[
 'https://github.com/OpenSees/OpenSees/blob/master/EXAMPLES/ExamplePython/Example3.1.py',
 'https://openseespydoc.readthedocs.io/en/latest/src/RCFrameEarthquake.html',
 'https://github.com/bikenshrestha2024/OpenSeesPy-Official-Structural-Examples/blob/main/Reinforced%20Concrete%20Frame%20Earthquake%20Analysis/EQ_analysis.ipynb']
PROFILE=dict(status='LITERATURE_TEACHING_EXAMPLE_NOT_PROJECT_CALIBRATION',units='kN, m, s; stresses kN/m2',
 span_m=360*INCH,height_m=144*INCH,width_m=15*INCH,depth_m=24*INCH,cover_m=1.5*INCH,
 core_Concrete01=[-6*KSI,-.004,-5*KSI,-.014],cover_Concrete01=[-5*KSI,-.002,0.,-.006],
 steel_Steel01=[60*KSI,30000*KSI,.01],bar_area_m2=.6*INCH**2,bars=8,
 gravity_per_roof_node_kN=180*KIP,beam_A_m2=360*INCH**2,beam_E_kN_m2=4030*KSI,beam_I_m4=8640*INCH**4,
 lobatto_points=5,betaKcomm_s=.000625,newmark_gamma=.5,newmark_beta=.25,sources=SOURCES,
 notes='Source numerical teaching parameters, not material-code defaults. Standard g used consistently for mass and motion; all source inch/kip quantities converted once. Elastic beam retained as in source. No strain limit is interpreted as NBC acceptance.')

def motion(path):
    text=Path(path).read_text(encoding='utf-8-sig');m=re.search(r'NPTS\s*=\s*(\d+).*?DT\s*=\s*([.\dEe+-]+)',text)
    if not m:raise ValueError('Expected AT2 NPTS / DT header')
    vals=np.asarray([float(v.replace('D','E')) for v in re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[EeDd][-+]?\d+)?',text[m.end():].split('SEC',1)[-1])]);n=int(m[1])
    if len(vals)!=n:raise ValueError(f'Header NPTS {n}, numeric values {len(vals)}')
    return float(m[2]),vals

def column_section(ops,elastic=False):
    q=PROFILE;y=q['depth_m']/2;z=q['width_m']/2;c=q['cover_m'];patches=[(1,10,1,c-y,c-z,y-c,z-c),(2,10,1,-y,z-c,y,z),(2,10,1,-y,-z,y,c-z),(2,2,1,-y,c-z,c-y,z-c),(2,2,1,y-c,c-z,y,z-c)]
    bars=[(yy,zz) for yy,count in [(y-c,3),(0.,2),(c-y,3)] for zz in np.linspace(z-c,c-z,count)]
    ea=0.;ei=0.
    if not elastic:
        ops.uniaxialMaterial('Concrete01',1,*q['core_Concrete01']);ops.uniaxialMaterial('Concrete01',2,*q['cover_Concrete01']);ops.uniaxialMaterial('Steel01',3,*q['steel_Steel01']);ops.section('Fiber',1)
    for mat,ny,nz,y0,z0,yf,zf in patches:
        if not elastic:ops.patch('rect',mat,ny,nz,y0,z0,yf,zf)
        e=2*q['core_Concrete01'][0]/q['core_Concrete01'][1] if mat==1 else 2*q['cover_Concrete01'][0]/q['cover_Concrete01'][1]
        area=(yf-y0)*(zf-z0)/(ny*nz)
        for yy in y0+(np.arange(ny)+.5)*(yf-y0)/ny:
            ea+=e*area*nz;ei+=e*area*nz*yy*yy
    for yy,zz in bars:
        if not elastic:ops.fiber(yy,zz,q['bar_area_m2'],3)
        ea+=q['steel_Steel01'][1]*q['bar_area_m2'];ei+=q['steel_Steel01'][1]*q['bar_area_m2']*yy*yy
    return ea,ei

def build(elastic=False):
    import openseespy.opensees as ops
    q=PROFILE;ops.wipe();ops.model('basic','-ndm',2,'-ndf',3)
    for tag,x,y in [(1,0,0),(2,q['span_m'],0),(3,0,q['height_m']),(4,q['span_m'],q['height_m'])]:ops.node(tag,x,y)
    for n in (1,2):ops.fix(n,1,1,1)
    ea,ei=column_section(ops,elastic);ops.geomTransf('PDelta',1);ops.geomTransf('Linear',2)
    if not elastic:ops.beamIntegration('Lobatto',1,1,q['lobatto_points'])
    for e,i,j in [(1,1,3),(2,2,4)]:
        if elastic:ops.element('elasticBeamColumn',e,i,j,ea,1.,ei,1)
        else:ops.element('forceBeamColumn',e,i,j,1,1,'-iter',30,1e-12)
    ops.element('elasticBeamColumn',3,3,4,q['beam_A_m2'],q['beam_E_kN_m2'],q['beam_I_m4'],2)
    ops.timeSeries('Linear',1);ops.pattern('Plain',1,1)
    for n in (3,4):ops.load(n,0.,-q['gravity_per_roof_node_kN'],0.)
    ops.constraints('Plain');ops.numberer('RCM');ops.system('BandGeneral');ops.test('NormDispIncr',1e-11,40);ops.algorithm('Newton');ops.integrator('LoadControl',.1);ops.analysis('Static')
    if ops.analyze(10):raise RuntimeError('Benchmark gravity did not converge')
    ops.reactions();vertical=sum(ops.nodeReaction(n,2) for n in (1,2));expected=2*q['gravity_per_roof_node_kN']
    if abs(vertical-expected)>1e-6*expected:raise RuntimeError('Benchmark gravity equilibrium failed')
    ops.loadConst('-time',0.)
    for n in (3,4):ops.mass(n,q['gravity_per_roof_node_kN']/G,q['gravity_per_roof_node_kN']/G,0.)
    periods=[2*math.pi/math.sqrt(v) for v in ops.eigen('-fullGenLapack',2)]
    return ops,periods,vertical

def single(record,out,elastic=False,dt=.0025,factor=1.,log=print):
    start=time.perf_counter();out=Path(out);out.mkdir(parents=True,exist_ok=True);record_dt,acc=motion(record)
    if not math.isfinite(factor) or factor<=0:raise ValueError('Motion scale factor must be finite and positive')
    ops,periods,gravity=build(elastic)
    maxdt=min(record_dt,.01,periods[0]/100.)
    if dt>maxdt+1e-12 or dt<=0:raise ValueError(f'Demo dt must be positive and <= {maxdt:g} s; modal-period screen, not full NBC suite certification')
    ops.timeSeries('Path',2,'-dt',record_dt,'-values',*acc.tolist(),'-factor',G*factor);ops.pattern('UniformExcitation',2,1,'-accel',2)
    ops.rayleigh(0.,0.,0.,PROFILE['betaKcomm_s']);ops.wipeAnalysis();ops.constraints('Plain');ops.numberer('RCM');ops.system('BandGeneral');ops.test('NormDispIncr',1e-10,40);ops.algorithm('Newton');ops.integrator('Newmark',.5,.25);ops.analysis('Transient')
    rows=[];fallbacks=0;end=(len(acc)-1)*record_dt;label='elastic_initial_tangent' if elastic else 'nonlinear_fiber';last=-1
    def capture():
        t=ops.getTime();f=[ops.eleForce(e) for e in (1,2)];restoring=sum(float(v[0]) for v in f);ug=float(np.interp(t,np.arange(len(acc))*record_dt,acc))*G*factor
        row=dict(time_s=t,ground_accel_m_s2=ug,roof_ux_m=ops.nodeDisp(3,1),roof_uy_m=ops.nodeDisp(3,2),roof_rz_rad=ops.nodeDisp(3,3),roof_relative_ax_m_s2=ops.nodeAccel(3,1),roof_absolute_ax_m_s2=ops.nodeAccel(3,1)+ug,restoring_base_shear_kN=restoring,drift_ratio=ops.nodeDisp(3,1)/PROFILE['height_m'])
        row.update(roof4_ux_m=ops.nodeDisp(4,1),roof4_uy_m=ops.nodeDisp(4,2),roof4_rz_rad=ops.nodeDisp(4,3))
        if not elastic:
            steel=ops.eleResponse(1,'section',1,'fiber',PROFILE['depth_m']/2-PROFILE['cover_m'],0.,3,'stressStrain')
            concrete=ops.eleResponse(1,'section',1,'fiber',PROFILE['depth_m']/2-PROFILE['cover_m']-.001,0.,1,'stressStrain')
            row.update(steel_stress_MPa=steel[0]/1000,steel_strain=steel[1],core_stress_MPa=concrete[0]/1000,core_strain=concrete[1])
        rows.append(row)
    capture()
    while ops.getTime()<end-1e-10:
        h=min(dt,end-ops.getTime());ok=ops.analyze(1,h)
        if ok:
            fallbacks+=1;ops.algorithm('NewtonLineSearch');ops.test('NormDispIncr',1e-10,100);ok=ops.analyze(1,h);ops.algorithm('Newton');ops.test('NormDispIncr',1e-10,40)
        if ok:raise RuntimeError(f'{label}: convergence failure at {ops.getTime():g}s; no completion claimed')
        capture();pct=int(ops.getTime()/end*10)
        if pct!=last:last=pct;log(f'[{label}] {ops.getTime():.2f}/{end:.2f} s')
    with (out/(label+'_history.csv')).open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=dict(label=label,status='COMPLETED_DEMONSTRATION_NOT_DESIGN_ACCEPTANCE',duration_s=end,dt_s=dt,periods_initial_s=periods,gravity_reactions_kN=gravity,peak_roof_displacement_m=max(abs(r['roof_ux_m']) for r in rows),peak_drift_ratio=max(abs(r['drift_ratio']) for r in rows),record_scale_factor=factor,unit_conversion_g_to_m_s2=G,total_Path_factor=G*factor,fallback_steps=fallbacks,elapsed_s=time.perf_counter()-start,rows=len(rows),source_record=str(record),betaKcomm_s=PROFILE['betaKcomm_s'],initial_modal_damping_ratios=[PROFILE['betaKcomm_s']*math.pi/t for t in periods])
    if not elastic:summary.update(peak_steel_strain=max(abs(r['steel_strain']) for r in rows),steel_yield_strain=PROFILE['steel_Steel01'][0]/PROFILE['steel_Steel01'][1],peak_core_compressive_strain=min(r['core_strain'] for r in rows))
    (out/(label+'_summary.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8');ops.wipe();return rows,summary

def figure(linear,nonlinear):
    from matplotlib.figure import Figure
    fig=Figure(figsize=(12,8),layout='constrained');ax=fig.subplots(2,2)
    for rows,name in [(linear,'Elastic initial tangent'),(nonlinear,'Nonlinear fibers')]:
        ax[0,0].plot([r['time_s'] for r in rows],[r['roof_ux_m']*1000 for r in rows],label=name,lw=.8)
        ax[0,1].plot([r['roof_ux_m']*1000 for r in rows],[-r['restoring_base_shear_kN'] for r in rows],label=name,lw=.6)
    ax[1,0].plot([r['steel_strain'] for r in nonlinear],[r['steel_stress_MPa'] for r in nonlinear],lw=.7)
    ax[1,1].plot([r['core_strain'] for r in nonlinear],[r['core_stress_MPa'] for r in nonlinear],lw=.7)
    for a in ax.flat:a.grid(alpha=.25)
    ax[0,0].set(xlabel='Time (s)',ylabel='Roof Ux (mm)',title='Same earthquake and initial-section tangent baseline');ax[0,0].legend()
    ax[0,1].set(xlabel='Roof Ux (mm)',ylabel='Lateral restoring action (kN)',title='Force-displacement paths; P-Delta retained');ax[0,1].legend()
    ax[1,0].set(xlabel='Bar strain',ylabel='Steel stress (MPa)',title='Left column base, selected longitudinal fiber')
    ax[1,1].set(xlabel='Core strain',ylabel='Core stress (MPa)',title='Left column base, selected concrete fiber')
    fig.suptitle('Published RC portal teaching model - not your ETABS building / no design PASS')
    return fig

def run_suite(record,out,dt=.0025,factor=1.,log=print):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);start=time.perf_counter();started=datetime.datetime.now().astimezone().isoformat();messages=[]
    def notify(s):messages.append(s);log(s)
    (out/'Literature_RC_Profile.json').write_text(json.dumps(PROFILE,indent=2),encoding='utf-8')
    linear,ls=single(record,out,True,dt,factor,notify);nonlinear,ns=single(record,out,False,dt,factor,notify)
    fig=figure(linear,nonlinear);fig.savefig(out/'RC_Linear_Nonlinear_Comparison.png',dpi=160);fig.savefig(out/'RC_Linear_Nonlinear_Comparison.pdf')
    result=dict(scope=PROFILE['status'],started=started,finished=datetime.datetime.now().astimezone().isoformat(),elapsed_s=time.perf_counter()-start,linear=ls,nonlinear=ns)
    (out/'Demo_Comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(out/'Demo_Run.log').write_text('\n'.join(messages)+f'\nElapsed: {result["elapsed_s"]:.3f} s\n',encoding='utf-8')
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True);parser.add_argument('--out',required=True);parser.add_argument('--dt',type=float,default=.0025);parser.add_argument('--factor',type=float,default=1.)
    args=parser.parse_args();print(json.dumps(run_suite(args.record,args.out,args.dt,args.factor),indent=2))

