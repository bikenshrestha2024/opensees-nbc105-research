"""Model MRSM: mode-by-mode OpenSees RSA, CQC, NBC force scaling and drift."""
from pathlib import Path
import csv,json,math,time
import numpy as np
from OpenSees_Timing_V130 import timed_outputs
from NBC105_Spectrum_Scaling_V115 import spectral_shape_ch
from OpenSees_Response_Checks_V132 import write_csv,drift_check

def cqc_matrix(omega,zeta=.05):
    w=np.asarray(omega,float);b=w[None,:]/w[:,None]
    rho=8*zeta*zeta*(1+b)*b**1.5/((1-b*b)**2+4*zeta*zeta*b*(1+b)**2)
    np.fill_diagonal(rho,1.)
    return rho

def combine(values,rho):
    a=np.asarray(values,float)
    return np.sqrt(np.maximum(0.,np.einsum('i...,ij,j...->...',a,rho,a)))

def design_cd(T,cfg):
    elastic=spectral_shape_ch(T,cfg['soil'],'dynamic')*float(cfg['Z'])*float(cfg['I'])
    return elastic/(float(cfg['rmu'])*float(cfg['omegau'])) if cfg['limit_state']=='ULS' else .2*elastic/float(cfg['omegas'])

@timed_outputs('Model modal response spectrum analysis','output_dir')
def run_model_spectrum(folder,config,output_dir):
    import openseespy.opensees as ops
    from OpenSees_Complete_Export_V118 import build_complete_model
    from NBC105_Analysis_Settings_V109 import calculate_esm
    from OpenSees_Earthquake_Analysis_NBC105_V111 import read_story_csv
    from OpenSees_Modal_Analysis_NBC105_V111 import run_nbc105_modal_audit
    folder=Path(folder).resolve();out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    data=json.loads((folder/'OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'))
    manifest=json.loads((folder/'OpenSees_Export_Manifest_V118.json').read_text(encoding='utf-8-sig'))
    stories=read_story_csv(folder/manifest['esm_story_weight_csv']);groups=sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2]);state=config['limit_state']
    overrides=folder/'OpenSees_Element_Overrides_V125.json'
    if overrides.is_file() and json.loads(overrides.read_text(encoding='utf-8-sig')).get('active'):raise ValueError('MRSM requires the elastic baseline; nonlinear replacements are unsupported.')
    if not all(math.isfinite(float(config[k])) and float(config[k])>0 for k in ('Z','I','rmu','omegau','omegas','T1_X','T1_Y')):raise ValueError('Spectrum inputs and adopted periods must be positive.')
    if not 0<float(config.get('damping',.05))<=.05:raise ValueError('Damping must be positive and no greater than 5 percent.')
    import hashlib
    from OpenSees_Model_Audit_V130 import implementation_digest,modal_numeric_digest
    source_signature=implementation_digest();numeric_signature=modal_numeric_digest()
    model_signature=hashlib.sha256((folder/'OpenSees_Complete_Model_Data_V118.json').read_bytes()).hexdigest()
    print('[STIFFNESS REVIEW] Production elastic wall shells retain source gross in-plane stiffness. Review NBC Table 3-1 effective wall EI and match ETABS before design use.',flush=True)
    results={}
    for axis,dof in [('X',1),('Y',2)]:
        if axis not in config.get('axes',['X','Y']):continue
        __import__('os').environ['OPENSEES_GRAVITY_PROFILE']=config.get('gravity_profile',__import__('os').environ.get('OPENSEES_GRAVITY_PROFILE','AS_CONFIGURED'))
        print('[MRSM START]',state,axis,flush=True)
        build_complete_model(folder,mode='elastic',preload=True,limit_state=state)
        print('[MRSM STAGE]',state,axis,'gravity converged; solving eigenmodes, then CQC response and NBC force scaling. This is one state of the selected batch.',flush=True)
        from components.modal.analysis import modal_response_nodes
        modal=run_nbc105_modal_audit(
            ops, nmodes=int(config.get('nmodes',40)),
            output_dir=out/('Modal_'+axis),
            story_nodes=modal_response_nodes(data))
        modal.update(limit_state=state,model_sha256=model_signature,implementation_sha256=source_signature,modal_numeric_sha256=numeric_signature)
        cache=folder/'OpenSees_Analysis_Results'/('Modal_'+state+('' if __import__('os').environ.get('OPENSEES_GRAVITY_PROFILE','AS_CONFIGURED')=='AS_CONFIGURED' else '_'+__import__('os').environ['OPENSEES_GRAVITY_PROFILE']));cache.mkdir(parents=True,exist_ok=True)
        from OpenSees_Timing_V130 import StageTimer
        cache_timer=StageTimer(cache,'MRSM modal reference cache export')
        (cache/'NBC105_Modal_V111.json').write_text(json.dumps(modal,indent=2),encoding='utf-8')
        cache_timer.finish('completed')
        rows=modal['rows'];props=ops.modalProperties('-return')
        if float(modal['cumulative_U'+axis+'_percent'] or 0)<90:raise ValueError(axis+' modal mass is below 90 percent; increase modes.')
        if modal['modes_at_or_above_33_Hz']:raise ValueError('Returned modes at/above 33 Hz require a reviewed missing-mass correction, not implemented by this MRSM engine. No design result exported.')
        ns=sorted(map(int,data['nodes']));elements=sorted(ops.getEleTags());support_tags=sorted(int(n) for n,v in data['supports'].items() if any(v))
        display_nodes=dict(data['nodes'],**{str(g['master_tag']):g['master_xyz'] for g in groups});display_ns=sorted(map(int,display_nodes))
        for ecc_sign in ((0,1,-1) if config.get('accidental_torsion',True) else (0,)):
            case_axis=axis+('_Eplus' if ecc_sign==1 else '_Eminus' if ecc_sign==-1 else '_E0')
            modal_u=[];modal_f=[];modal_d=[];modal_edge=[];modal_shear=[];modal_V=[];modal_reactions=[];force_checks=[]
            print('[MRSM CASE START]',state,axis+'_'+('E0' if ecc_sign==0 else 'Eplus' if ecc_sign==1 else 'Eminus'),flush=True)
            for row in rows:
                T=row['period_s'];Sa=design_cd(T,config)*9.80665
                gamma_x=float(props['partiFactorM'+axis][row['mode']-1])
                gm=sum(float(data['nodal_mass'].get(str(n),0.))*sum(float(ops.nodeEigenvector(n,row['mode'],j))**2 for j in (1,2,3)) for n in ns)
                torque_generalized=0.
                if ecc_sign:
                    for g in groups:
                        z=g['master_xyz'][2];lower=max([data['base_z_m']]+[q['master_xyz'][2] for q in groups if q['master_xyz'][2]<z-1e-7])
                        members=[n for n in ns if lower+1e-7<data['nodes'][str(n)][2]<=z+1e-7]
                        floor_nodes=[data['nodes'][str(n)] for n in g['slave_node_tags'] if str(n) in data['nodes']]
                        breadth=max(v[1 if axis=='X' else 0] for v in floor_nodes)-min(v[1 if axis=='X' else 0] for v in floor_nodes)
                        mass=sum(float(data['nodal_mass'].get(str(n),0.)) for n in members)
                        torque_generalized+=ecc_sign*.05*breadth*mass*ops.nodeEigenvector(g['master_tag'],row['mode'],6)
                desired_gamma=gamma_x+(torque_generalized/gm if gm else 0.)
                # Native RSA can generate the same eigenvector displacement using any nonzero participation factor.
                factors=[float(props.get(key,[0.]*len(rows))[row['mode']-1]) for key in ('partiFactorMX','partiFactorMY','partiFactorMZ','partiFactorRMX','partiFactorRMY','partiFactorRMZ')]
                excitation=max(range(6),key=lambda j:abs(factors[j]));input_sa=Sa*desired_gamma/factors[excitation] if abs(factors[excitation])>1e-20 else 0.
                # Exact ordinate at the mode period; the two equal values avoid interpolation error.
                ops.responseSpectrumAnalysis(excitation+1,'-Tn',0.,6.,'-Sa',0.,0.,'-mode',row['mode'])
                baseline=[np.asarray(ops.eleForce(e),float) for e in elements]
                ops.reactions();baseline_reactions=np.asarray([ops.nodeReaction(n) for n in support_tags])
                response_sign=1. if input_sa>=0 else -1.
                ops.responseSpectrumAnalysis(excitation+1,'-Tn',0.,6.,'-Sa',abs(input_sa),abs(input_sa),'-mode',row['mode'])
                ops.reactions();reactions=(np.asarray([ops.nodeReaction(n) for n in support_tags])-baseline_reactions)*response_sign;modal_reactions.append(reactions)
                u=np.asarray([ops.nodeDisp(n) for n in display_ns]);forces=[np.asarray(ops.eleForce(e),float)-b for e,b in zip(elements,baseline)]
                modal_u.append(u*response_sign);modal_f.append(np.concatenate(forces)*response_sign)
                floor=np.asarray([ops.nodeDisp(g['master_tag'],dof) for g in groups]);h=np.diff([0.]+[g['master_xyz'][2]-data['base_z_m'] for g in groups]);modal_d.append(np.diff(np.r_[0.,floor])/h*response_sign)
                edges=[]
                for index,g in enumerate(groups):
                    lower=groups[index-1] if index else None;h=g['master_xyz'][2]-(lower['master_xyz'][2] if lower else data['base_z_m'])
                    pts=[data['nodes'][str(n)] for n in g['slave_node_tags'] if str(n) in data['nodes']];perp=1 if axis=='X' else 0
                    for position in (min(p[perp] for p in pts),max(p[perp] for p in pts)):
                        sign=-1 if axis=='X' else 1
                        upper_u=ops.nodeDisp(g['master_tag'],dof)+sign*ops.nodeDisp(g['master_tag'],6)*(position-g['master_xyz'][perp])
                        lower_u=(ops.nodeDisp(lower['master_tag'],dof)+sign*ops.nodeDisp(lower['master_tag'],6)*(position-lower['master_xyz'][perp])) if lower else 0.
                        edges.append((upper_u-lower_u)/h*response_sign)
                modal_edge.append(edges)
                gamma=desired_gamma;force_by_level=[]
                for g in groups:
                    z=g['master_xyz'][2];lower=max([data['base_z_m']]+[q['master_xyz'][2] for q in groups if q['master_xyz'][2]<z-1e-7]);f=0.
                    for n in ns:
                        p=data['nodes'][str(n)];m=float(data['nodal_mass'].get(str(n),0.))
                        if lower+1e-7<p[2]<=z+1e-7:f+=m*ops.nodeEigenvector(n,row['mode'],dof)*gamma*Sa
                    force_by_level.append(f)
                modal_shear.append(np.cumsum(force_by_level[::-1])[::-1]);modal_V.append(gm*gamma_x*desired_gamma*Sa)
                reaction=float(reactions[:,dof-1].sum());expected=modal_V[-1]
                force_checks.append(dict(mode=row['mode'],modal_inertia_base_shear_kN=expected,modal_support_reaction_kN=reaction,error_kN=reaction+expected,error_percent=100*abs(reaction+expected)/max(1.,abs(expected))))
            rho=cqc_matrix([r['omega_rad_s'] for r in rows],float(config.get('damping',.05)))
            raw_V=float(combine(modal_V,rho));reference=calculate_esm(stories,period_s=float(config['T1_'+axis]),soil_type=config['soil'],zoning_factor_z=float(config['Z']),importance_factor_i=float(config['I']),limit_state=state,r_mu=float(config['rmu']),omega_u=float(config['omegau']),omega_s=float(config['omegas']),irregular=True,diagnostic_reference=True)
            scale=max(1.,reference['base_shear_kN']/raw_V);u=combine(modal_u,rho);d=combine(modal_d,rho);shear=combine(modal_shear,rho)*scale;f=combine(modal_f,rho)*scale
            amp=float(config['rmu']) if state=='ULS' else 1.
            edge_d=combine(modal_edge,rho)*amp
            # NBC force scale is deliberately not applied to displacement/drift; ESM kd is not an MRSM factor.
            story_result=[dict(story_number=g['storey_number'],height_m=g['master_xyz'][2]-data['base_z_m'],elastic_displacement_m=float(u[display_ns.index(int(g['master_tag'])),dof-1]),design_displacement_m=float(u[display_ns.index(int(g['master_tag'])),dof-1]*amp),elastic_drift_ratio=float(d[i]),design_drift_ratio=float(max(edge_d[2*i:2*i+2])),master_design_drift_ratio=float(d[i]*amp),scaled_story_shear_kN=float(shear[i])) for i,g in enumerate(groups)]
            write_csv(out/(state+'_'+case_axis+'_Drift_V132.csv'),drift_check(story_result,state))
            write_csv(out/(state+'_'+case_axis+'_Modal_Force_Equilibrium_V132.csv'),force_checks)
            support_envelope=combine(modal_reactions,rho)*scale
            write_csv(out/(state+'_'+case_axis+'_Support_Reactions_V132.csv'),[dict(node_tag=n,**{('F'+str(j+1)+'_kN' if j<3 else 'M'+str(j-2)+'_kNm'):float(v) for j,v in enumerate(support_envelope[i])}) for i,n in enumerate(support_tags)])
            sizes=[len(v) for v in forces];offset=0;force_rows=[]
            for tag,size in zip(elements,sizes):
                for j,value in enumerate(f[offset:offset+size]):force_rows.append(dict(element_tag=tag,global_component_index=j+1,scaled_modal_force=float(value),unit='kN for translational components; kN m for rotational components',note='CQC seismic envelope only; combine gravity separately and preserve action correlations for member design.'))
                offset+=size
            write_csv(out/(state+'_'+case_axis+'_Element_Force_Envelopes_V132.csv'),force_rows)
            profile_path=out/(state+'_'+case_axis+'_CQC_Story_Response_Profile.csv')
            write_csv(profile_path,[
                dict(story_number=r["story_number"],height_m=r["height_m"],
                     elastic_displacement_m=r["elastic_displacement_m"],
                     design_displacement_m=r["design_displacement_m"],
                     elastic_drift_ratio=r["elastic_drift_ratio"],
                     design_drift_ratio=r["design_drift_ratio"],
                     scaled_story_shear_kN=r["scaled_story_shear_kN"])
                for r in story_result
            ])
            deformation=dict(nodes=display_nodes,limit_state=state,response_case=case_axis,dof_names=['Ux','Uy','Uz','Rx','Ry','Rz'],dof_availability=[True]*6,eccentricity_sign=ecc_sign,elements=[e['nodes'] for e in data['frames']+data['shells']],displacements={str(n):(u[j]*amp).tolist() for j,n in enumerate(display_ns)},note=state+' '+axis+' MRSM component-wise positive CQC envelope; not a simultaneous physical shape. Force base-shear scale is not applied.')
            (out/('Deformation_MRSM_'+state+'_'+case_axis+'_V132.json')).write_text(json.dumps(deformation),encoding='utf-8')
            result=dict(gravity_profile=__import__('os').environ.get('OPENSEES_GRAVITY_PROFILE','AS_CONFIGURED'),limit_state=state,axis=axis,accidental_eccentricity_sign=ecc_sign,unscaled_modal_base_shear_kN=raw_V,reference_ESM_base_shear_kN=reference['base_shear_kN'],force_scale=scale,scaled_modal_base_shear_kN=raw_V*scale,displacement_scale_from_7_5=1.,drift_amplification=amp,combination='CQC, equal modal damping',mass_participation_percent=modal['cumulative_U'+axis+'_percent'],stories=story_result,modal_base_shears_kN=modal_V,modal_rows=rows,units='kN m s; dimensionless Cd converted to m/s2 using 9.80665',scope='Elastic model with inherent torsion plus signed 5 percent per-floor eccentric inertia torque; lumped floor influence vector on unchanged eigenmodes. Orthogonal member design combinations require review; member design not performed.',status='ANALYSIS COMPLETE / DESIGN COMBINATIONS REQUIRE REVIEW')
            relevant=[r['error_percent'] for r in force_checks if abs(r['modal_inertia_base_shear_kN'])>max(1.,max(abs(v) for v in modal_V)*1e-4)]
            result['stiffness_review']='Gross in-plane elastic wall stiffness: review NBC Table 3-1; no compliance certification.'
            result['modal_force_equilibrium_max_relevant_percent']=max(relevant or [0.])
            result['modal_force_equilibrium_note']='Native elastic RSA force diagnostic about a gravity-preloaded geometric model; inspect residuals. 1 percent is an implementation review threshold, not an NBC-prescribed tolerance.'
            if max(relevant or [0.])>1.:result['status']='FORCE EQUILIBRIUM NEEDS REVIEW - do not use member force envelopes for design'
            from components.shared.response_recorders import write_recorder_index
            write_recorder_index(
                out, "modal_response_spectrum",
                [
                    (profile_path.name, [
                        "story displacement", "story drift", "scaled story shear"]),
                    (state+'_'+case_axis+'_Support_Reactions_V132.csv', [
                        "component-wise CQC support reaction envelope"]),
                    (state+'_'+case_axis+'_Element_Force_Envelopes_V132.csv', [
                        "component-wise CQC element force envelope"]),
                    ('Deformation_MRSM_'+state+'_'+case_axis+'_V132.json', [
                        "component-wise CQC nodal displacement envelope"]),
                    ('Modal_'+axis+'/Modal_Story_Mode_Shapes.csv', [
                        "raw and normalized diaphragm/perimeter mode shapes"]),
                ],
                notes=[
                    "CQC displacement, drift, support-reaction and force envelopes are independently combined components; they are not one simultaneous physical response state and must not be interpreted as a hysteresis path.",
                    "Gravity effects and correlated member design combinations require separate review.",
                ],
                filename="Response_Recorder_Index_"+state+"_"+case_axis+".json",
            )
            results[case_axis]=result;print('[MRSM COMPLETE]',state,case_axis,'| '+('centered e=0' if ecc_sign==0 else ('signed eccentricity +5% breadth' if ecc_sign==1 else 'signed eccentricity -5% breadth')),'| Vraw=',raw_V,'| force S=',scale,flush=True)
    (out/'MRSM_Results_V132.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(11,6),layout='constrained')
    for axis,res in results.items():
        z=[r['height_m'] for r in res['stories']];ax[0].plot([r['scaled_story_shear_kN'] for r in res['stories']],z,label=axis);ax[1].plot([r['design_drift_ratio'] for r in res['stories']],z,label=axis)
    ax[0].set(xlabel='Force-scaled storey shear (kN)',ylabel='Height (m)');ax[1].set(xlabel='Unscaled design drift ratio');ax[1].axvline(.025 if state=='ULS' else .006,color='r',ls='--')
    for a in ax:a.grid(alpha=.2);a.legend()
    fig.savefig(out/'MRSM_Profiles_V132.png',dpi=160);plt.close(fig)
    from OpenSees_MRSM_Reports_V134 import export_reports
    export_reports(out)
    return results

def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk,messagebox
    import threading,subprocess,sys
    from OpenSees_Project_Inputs_V123 import import_project_inputs
    from OpenSees_Research_UI_V123 import scrollable_form
    win=tk.Toplevel(parent);win.title('Model MRSM — SLS / ULS, reports and deformation');win.geometry('1100x820');form=scrollable_form(win)
    root=Path(__file__).parent;values=import_project_inputs(root,folder)['values'];fields={}
    defaults=dict(limit_state='Both',soil=values.get('soil',''),Z=values.get('Z',''),I=values.get('I',''),rmu=values.get('rmu',''),omegau=values.get('omegau',''),omegas=values.get('omegas',''),T1_X=values.get('workbook_adopted_tx',''),T1_Y=values.get('workbook_adopted_ty',''),nmodes=40,damping=.05)
    ttk.Label(form,text='Model response spectrum: mode shapes + site spectrum → CQC actions, force scaling, drift and nodal envelopes',wraplength=1000,font=('Segoe UI',12,'bold')).pack(anchor='w')
    grid=ttk.Frame(form);grid.pack(fill='x')
    for i,(name,value) in enumerate(defaults.items()):
        fields[name]=tk.StringVar(value=str(value));r=i//2;c=(i%2)*2;ttk.Label(grid,text=name,width=20).grid(row=r,column=c,sticky='w',pady=4)
        options=['Both','SLS','ULS'] if name=='limit_state' else ['A','B','C','D'] if name=='soil' else None
        widget=ttk.Combobox(grid,textvariable=fields[name],values=options,state='readonly',width=25) if options else ttk.Entry(grid,textvariable=fields[name],width=25);widget.grid(row=r,column=c+1,sticky='ew',padx=6)
    grid.columnconfigure(1,weight=1);grid.columnconfigure(3,weight=1)
    def refresh(*unused):
        state=fields['limit_state'].get()
        if state=='Both':return
        v=import_project_inputs(root,folder,state)['values']
        for name,key in [('soil','soil'),('Z','Z'),('I','I'),('rmu','rmu'),('omegau','omegau'),('omegas','omegas'),('T1_X','workbook_adopted_tx'),('T1_Y','workbook_adopted_ty')]:
            if key in v:fields[name].set(str(v[key]))
    fields['limit_state'].trace_add('write',refresh)
    ttk.Label(form,text='Each state runs X and Y, with E0 / Eplus / Eminus cases (6 cases/state). E0 is centered; Eplus/Eminus are signed 5% perpendicular-breadth eccentric inertia cases. Soil selection requires site evidence. Acceleration conversion is internal for the kN-m-s model. Workbook / PNG / PDF are exported automatically.',wraplength=1000).pack(anchor='w',pady=6)
    actions=ttk.Frame(form);actions.pack(fill='x');output=Path(folder)/'OpenSees_Analysis_Results'
    log_value=tk.StringVar()
    from OpenSees_Research_UI_V123 import copyable_log
    from components.shared.case_status import panel,CaseLedger
    board=panel(form)
    log=copyable_log(form,log_value,height=12)
    def append(line):
        try:win.after(0,lambda:(log.insert('end',line),log.see('end')))
        except (tk.TclError,RuntimeError):pass
    def run():
        try:
            cfg={k:v.get() for k,v in fields.items()};cfg['nmodes']=int(cfg['nmodes'])
            for k in ['Z','I','rmu','omegau','omegas','T1_X','T1_Y','damping']:cfg[k]=float(cfg[k])
            states=['ULS','SLS'] if cfg['limit_state']=='Both' else [cfg['limit_state']];button.configure(state='disabled')
            ledger=CaseLedger(output/"MRSM_Batch_Status_V151.json",[state+" "+axis+"_"+ecc for state in states for axis in ("X","Y") for ecc in ("E0","Eplus","Eminus")]);board["ledger"]=ledger;board["cancelled"]=False
            def worker():
                try:
                    append('[BATCH PLAN] '+', '.join(states)+'; each state runs X and Y, centered and +/-5% eccentricity.\n')
                    for state in states:
                        if board.get("cancelled"):break
                        append('[STATE START] '+state+' | gravity/preload, eigenanalysis, modal RSA, CQC, force scaling, drift and export.\n')
                        current=dict(cfg,limit_state=state,gravity_profile=__import__('os').environ.get('OPENSEES_GRAVITY_PROFILE','AS_CONFIGURED'));out=output/('MRSM_'+state+('' if current['gravity_profile']=='AS_CONFIGURED' else '_'+current['gravity_profile']));out.mkdir(parents=True,exist_ok=True);path=out/'MRSM_Config_V132.json';path.write_text(json.dumps(current,indent=2),encoding='utf-8')
                        script="import sys,json;sys.path.insert(0,"+repr(str(root))+");from OpenSees_Model_Response_Spectrum_V132 import run_model_spectrum;run_model_spectrum("+repr(str(Path(folder).resolve()))+",json.load(open("+repr(str(path.resolve()))+",encoding='utf-8')),"+repr(str(out.resolve()))+")"
                        with (out/'MRSM_Run_V132.log').open('w',encoding='utf-8') as stream:
                            proc=subprocess.Popen([sys.executable,'-u','-c',script],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env={**dict(__import__('os').environ),'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
                            board["process"]=proc
                            for line in proc.stdout:
                                stream.write(line);stream.flush();append(line)
                                if '[MRSM START]' in line:
                                    axis=line.split('[MRSM START]',1)[1].split()[1]
                                    for ecc in ('E0','Eplus','Eminus'):ledger.set(state+' '+axis+'_'+ecc,'PREPARING','Shared model/gravity/eigenanalysis; case RSA queued')
                                if '[MRSM STAGE]' in line:
                                    axis=line.split('[MRSM STAGE]',1)[1].split()[1]
                                    for ecc in ('E0','Eplus','Eminus'):ledger.set(state+' '+axis+'_'+ecc,'PREPARING','Shared sparse eigenanalysis; individual RSA queued')
                                if '[MRSM CASE START]' in line:
                                    parts=line.split('[MRSM CASE START]',1)[1].split();ledger.set(parts[0]+' '+parts[1],'RUNNING','Modal RSA / CQC and response export')
                                if '[MRSM COMPLETE]' in line:
                                    parts=line.split('[MRSM COMPLETE]',1)[1].split();key=parts[0]+' '+parts[1]
                                    if key in ledger.rows:ledger.set(key,'COMPLETED',line.strip())
                            rc=proc.wait();append(state+' EXIT '+str(rc)+'\n')
                            if rc:
                                for key,row in ledger.rows.items():
                                    if key.startswith(state+' ') and row['status']!='COMPLETED':ledger.set(key,'FAILED','State child exit '+str(rc)+'; inspect log. Next state will run independently.')
                except Exception as e:append('[FAILED] '+str(e)+'\n')
                finally:
                    ledger.finish_pending("Batch interrupted or case completion was not reported; inspect state log")
                    try:win.after(0,lambda:button.configure(state='normal'))
                    except (tk.TclError,RuntimeError):pass
            threading.Thread(target=worker,daemon=True).start()
        except Exception as e:messagebox.showerror('MRSM inputs',str(e),parent=win)
    button=ttk.Button(actions,text='Run selected state(s)',command=run);button.pack(side='left')
    ttk.Button(actions,text='Saved SLS / ULS charts + Excel',command=lambda:__import__('OpenSees_MRSM_Reports_V134').launch(win,output)).pack(side='left',padx=4)
    ttk.Button(actions,text='Deformation / node DOFs',command=lambda:__import__('OpenSees_Response_Checks_V132').launch_response_viewer(win,output)).pack(side='left')
    win._mrsm_fields=fields;win._mrsm_log=log;return win
