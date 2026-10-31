"""Own building geometry with explicitly assumed research constitutive models.
This does not approve or modify the calibrated production-model workflow.
"""
from pathlib import Path
import json,math,time,csv,shutil,hashlib,datetime
import numpy as np
PROFILE='LITERATURE_FRAME_NL_ELASTIC_WALL_V138'
TRANSIENT_SYSTEMS=('UmfPack','SparseGeneral')

def configure_transient_system(ops,system):
    """Select a supported transient matrix solver without silent fallbacks."""
    if system not in TRANSIENT_SYSTEMS:
        raise ValueError('transient_system must be one of: '+', '.join(TRANSIENT_SYSTEMS))
    if system=='SparseGeneral':ops.system('SparseGeneral','-piv')
    else:ops.system('UmfPack')

def run(config):
    if config.get('limit_state')=='Both':
        base=Path(config['output_dir']);base.mkdir(parents=True,exist_ok=True);results={}
        for state in ('ULS','SLS'):
            print('[RESEARCH STATE START]',state,flush=True)
            results[state]=run(dict(config,limit_state=state,output_dir=str(base/state)))
            (base/'Research_Batch_Summary_V161.json').write_text(json.dumps(results,indent=2),encoding='utf8')
        return results
    transient_system=config.get('transient_system','UmfPack')
    if transient_system not in TRANSIENT_SYSTEMS:
        raise ValueError('transient_system must be one of: '+', '.join(TRANSIENT_SYSTEMS))
    gravity_system=config.get('gravity_system','UmfPack')
    if gravity_system not in TRANSIENT_SYSTEMS:
        raise ValueError('gravity_system must be one of: '+', '.join(TRANSIENT_SYSTEMS))
    from OpenSees_Complete_Export_V118 import build_complete_model
    from OpenSees_Input_Records_V130 import _read_peer_text_record
    from OpenSees_Nonlinear_Time_History_NBC105_V116 import _advance_nonlinear_interval,_configure_nonlinear_transient
    from OpenSees_Step13_Analysis_Basis_V115 import rayleigh_coefficients
    from OpenSees_Response_Checks_V132 import export_history_checks
    full_wall=bool(config.get('nonlinear_walls',False))
    profile='LITERATURE_BUILDING_NL_V161' if full_wall else PROFILE
    import os
    os.environ['OPENSEES_RESEARCH_MATERIAL_BASIS']=config.get('material_basis','PUBLISHED_REFERENCE')
    source=Path(config['model_folder']).resolve();out=Path(config['output_dir']).resolve();out.mkdir(parents=True,exist_ok=True)
    if source==out or source in out.parents and out==source:raise ValueError('Use a separate output scenario')
    model=out/'isolated_model';model.mkdir(exist_ok=True)
    for name in ('OpenSees_Complete_Model_Data_V118.json','OpenSees_Complete_Model_Config_V118.json','OpenSees_Complete_Export_Report_V118.json','OpenSees_Load_Conversion_Audit.json','OpenSees_Source_Model_Metadata_V118.json'):shutil.copy2(source/name,model/name)
    if (source/'OpenSees_Complete_Story_Masters_V118.csv').exists():shutil.copy2(source/'OpenSees_Complete_Story_Masters_V118.csv',model/'OpenSees_Complete_Story_Masters_V118.csv')
    for name in ('OpenSees_Element_Overrides_V125.json',):
        if (source/name).is_file():shutil.copy2(source/name,model/name)
    data=json.loads((model/'OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'));start=time.perf_counter();unit_factor={'g':9.80665,'m/s2':1.};records=[]
    for key in ('x_path','y_path'):
        values,step,units=_read_peer_text_record(config[key]);records.append((np.asarray(values),step,units))
    if abs(records[0][1]-records[1][1])>1e-10 or len(records[0][0])!=len(records[1][0]):raise ValueError('Pair duration/digitization mismatch; reconcile records explicitly')
    record_end=(len(records[0][0])-1)*records[0][1];end=record_end if not config.get('duration_s') else min(float(config['duration_s']),record_end)
    if end<=0:raise ValueError('Duration must be positive')
    dt=float(config.get('dt_s',.005));scale=float(config.get('scale',1.))
    if not math.isfinite(dt) or dt<=0 or dt>min(.01,records[0][1]):raise ValueError('dt must be positive and no larger than record dt or 0.01 s')
    if not math.isfinite(scale) or scale<=0:raise ValueError('Scale must be finite and positive')
    assumptions=dict(profile=profile,scope='EXPLORATORY_ASSUMED_MATERIALS_NOT_DESIGN_ACCEPTANCE',source_model_sha256=hashlib.sha256((source/'OpenSees_Complete_Model_Data_V118.json').read_bytes()).hexdigest(),frame_materials='Existing illustrative M35 / Fe550 RC templates; not source M45 project calibration',wall_materials='ELASTIC WALLS: source E/thickness; flexural factor ULS0.5 / SLS0.7 through plate modifier. Frame-nonlinear exploratory model; full FSAM wall trial failed and is not substituted silently.',braces='112 hinged SHS objects: corotTruss / Steel01, source area and E, assumed fy345MPa,b0.01; no flexural buckling/fatigue/fracture',floors='Source geometry, IS16700 ULS0.25/SLS0.35 elastic slab bending and gross membrane stiffness',gravity='Assembled source preload and nodal masses retained',limitation='Exploratory response and runtime only. No NBC design acceptance, reinforcement or collapse assessment.',records=[dict(path=str(config[k]),source_units=r[2],unit_conversion=unit_factor[r[2]],motion_scale=scale,total_Path_factor=unit_factor[r[2]]*scale) for k,r in zip(('x_path','y_path'),records)])
    if full_wall:
        assumptions.update(frame_materials='Literature unconfined Concrete01 + nominal Fe500 Steel02; existing bar-layout templates remain assumptions',wall_materials='Nonlinear E_SFI_MVLEM_3D + ConcreteCM / SteelMPF / FSAM; exact selected parameters exported per property',material_basis=config.get('material_basis','PUBLISHED_REFERENCE'),limitation='Research material transfer and reinforcement templates, not experimental building calibration or NBC design acceptance')
    from Define_Section_V109 import RC_SECTION_CONFIG
    assumptions['RC_template_inputs']=RC_SECTION_CONFIG
    (out/'ASSUMPTIONS_NOT_DESIGN.json').write_text(json.dumps(assumptions,indent=2),encoding='utf-8');(out/'RunConfig.json').write_text(json.dumps(config,indent=2),encoding='utf-8');summary=[]
    for orientation in config.get('orientations',['XY','YX']):
        if orientation not in ('XY','YX'):raise ValueError('Orientation must be XY or YX')
        case=out/orientation;case.mkdir(exist_ok=True);print('[EXPLORATORY START]',orientation,'no calibration or design approval implied',flush=True)
        build_complete_model(
            model, mode='nonlinear', preload=True,
            limit_state=config.get('limit_state','ULS'),
            research_profile=profile, gravity_system=gravity_system)
        import openseespy.opensees as ops
        if full_wall:
            shutil.copy2(model/'Research_Material_Assignment_V161.json',case/'Research_Material_Assignment_V161.json')
        groups=sorted(data['diaphragms'],key=lambda r:r['master_xyz'][2]);baseline={g['master_tag']:list(ops.nodeDisp(g['master_tag'])) for g in groups}
        print('[EXPLORATORY MODAL] Computing 20 initial nonlinear modes; transient has not started',flush=True)
        from components.shared.eigen_solver import solve_eigen
        eigenvalues=solve_eigen(ops,20);periods=[2*math.pi/math.sqrt(v) for v in eigenvalues if v>0]
        if len(periods)!=20:raise ValueError('Inspected nonlinear modes incomplete')
        bound=min(records[0][1],.01,periods[0]/100.,periods[-1])
        if dt>bound:raise ValueError(f'Chosen dt {dt} exceeds inspected-mode screen {bound:g}s; reduce dt')
        alpha,beta=rayleigh_coefficients(max(periods),min(periods),.05)
        if config.get('diagnostic_mass_damping'):alpha,beta=2*.05*min(math.sqrt(v) for v in eigenvalues),0.
        (case/'Initial_Modal_Damping.json').write_text(json.dumps(dict(eigenvalues=eigenvalues,periods_s=periods,alphaM=alpha,betaKcomm=beta,dt_screen_s=bound),indent=2))
        ops.rayleigh(alpha,0.,0.,beta)
        for direction,r in enumerate(records if orientation=='XY' else records[::-1],1):
            values,step,units=r;tag=900000+direction;ops.timeSeries('Path',tag,'-dt',step,'-values',*values.tolist(),'-factor',unit_factor[units]*scale);ops.pattern('UniformExcitation',tag,direction,'-accel',tag)
        _configure_nonlinear_transient(ops)
        configure_transient_system(ops,transient_system)
        diag={};rows=[];last=time.perf_counter();case_start=last
        stories=[dict(node=g['master_tag'],story_name='Storey_'+str(g['storey_number']),height=g['master_xyz'][2]-(groups[i-1]['master_xyz'][2] if i else data['base_z_m'])) for i,g in enumerate(groups)]
        wall_tags=[100001+len(data['frames'])+i for i,e in enumerate(data['shells']) if e['category']=='SHEAR WALL']
        tracked_wall=int(config.get('tracked_wall_tag',wall_tags[0])) if wall_tags else None
        tracked=int(config.get('tracked_frame_tag',100001))
        if not 100001<=tracked<100001+len(data['frames']):raise ValueError('Tracked frame solver tag is outside the assembled frame range')
        def capture():
            row={'time_s':ops.getTime()};previous=[0.]*6
            for story,g in zip(stories,groups):
                u=[a-b for a,b in zip(ops.nodeDisp(g['master_tag']),baseline[g['master_tag']])];name=story['story_name']
                for j,axis in enumerate(('X','Y','Z')):row[name+'_U'+axis+'_m']=u[j]
                for j,axis in enumerate(('X','Y','Z'),3):row[name+'_R'+axis+'_rad']=u[j]
                row[name+'_RZ_rad']=u[5]
                for j,axis in enumerate(('X','Y')):row[name+'_drift_'+axis]=(u[j]-previous[j])/story['height']
                previous=u
            force=list(ops.eleResponse(tracked,'localForce'))
            section=list(ops.eleResponse(tracked,'section',1,'deformation'))
            if len(force)==12:
                row['selected_frame_N_kN']=force[0];row['selected_frame_My_kNm']=force[4];row['selected_frame_Mz_kNm']=force[5]
            if len(section)>=3:
                row['section_axial_strain']=section[0];row['section_kappa_z_1_per_m']=section[1];row['section_kappa_y_1_per_m']=section[2]
            if full_wall and tracked_wall is not None:
                for response,label in [('panel_strain','wall_panel_strain'),('panel_stress','wall_panel_stress_kN_m2')]:
                    values=list(ops.eleResponse(tracked_wall,'RCPanel',1,response))
                    for j,value in enumerate(values):row[label+'_'+str(j+1)]=value
                for response,label in [('ShearDef','wall_shear_deformation'),('Curvature','wall_curvature')]:
                    values=list(ops.eleResponse(tracked_wall,response))
                    for j,value in enumerate(values):row[label+'_'+str(j+1)]=value
            rows.append(row)
        history=case/'Building_Nonlinear_history.csv'
        with history.open('w',newline='',encoding='utf-8-sig') as stream:
            capture();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerow(rows[-1]);stream.flush()
            try:
                while ops.getTime()<end-1e-10:
                    before=len(rows);_advance_nonlinear_interval(ops,min(dt,end-ops.getTime()),on_accept=capture,diagnostics=diag)
                    writer.writerows(rows[before:])
                    if time.perf_counter()-last>5:last=time.perf_counter();stream.flush();print(f'[EXPLORATORY PROGRESS] {orientation}: t={ops.getTime():.3f}/{end:.3f}s | wall={last-case_start:.1f}s',flush=True)
            except Exception:
                (case/'FAILED.json').write_text(json.dumps(dict(status='INCOMPLETE',time_s=ops.getTime(),elapsed_s=time.perf_counter()-case_start,scope=profile)));raise
        (case/'NBC105_Exploratory_Time_History_RunConfig_V138.json').write_text(json.dumps(dict(model_script='../isolated_model/OpenSees_Complete_Model_Data_V118.json',scope=assumptions['scope'])),encoding='utf-8')
        export_history_checks(rows,stories,case,'EXPLORATORY_'+orientation,config.get('limit_state','ULS'),model_script=str(model/'OpenSees_Complete_Model_Data_V118.json'))
        # Every reported criterion retains the staged-model scope.
        for file in list(case.glob('Drift_Check_*.csv'))+list(case.glob('Floor_Edge_Drift_*.csv')):
            with file.open(encoding='utf-8-sig',newline='') as stream:checks=list(csv.DictReader(stream))
            if checks:
                for check in checks:check['model_scope']=profile
                with file.open('w',encoding='utf-8-sig',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(checks[0]));writer.writeheader();writer.writerows(checks)
        action_rows=[]
        for element in range(100001,100001+len(data['frames'])):
            force=list(ops.eleResponse(element,'localForce'))
            if len(force)==12:
                for end_label,values in [('I',force[:6]),('J',force[6:])]:action_rows.append(dict(element_tag=element,end=end_label,time_s=ops.getTime(),N_kN=values[0],Vy_kN=values[1],Vz_kN=values[2],T_kNm=values[3],My_kNm=values[4],Mz_kNm=values[5],scope=assumptions['scope']))
        if action_rows:
            with (case/'Concurrent_Final_Frame_Actions.csv').open('w',newline='',encoding='utf-8-sig') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(action_rows[0]));writer.writeheader();writer.writerows(action_rows)
        deformation={str(n):list(ops.nodeDisp(int(n))) for n in data['nodes']}
        (case/('Deformation_EXPLORATORY_'+orientation+'_V132.json')).write_text(json.dumps(dict(nodes=data['nodes'],elements=[e['nodes'] for e in data['frames']+data['shells']],displacements=deformation,dof_availability=[True]*6,note='EXPLORATORY assumed literature materials; total final response at t='+str(ops.getTime())+' s. Not design acceptance.')),encoding='utf-8')
        result=dict(orientation=orientation,wall_model='E_SFI_MVLEM_3D' if full_wall else 'ELASTIC',frame_model='LITERATURE_CONCRETE01_NOMINAL_FE500' if full_wall else 'NONLINEAR_ILLUSTRATIVE_RC_FIBERS',gravity_system=gravity_system,transient_system=transient_system,status='COMPLETED_TRUNCATED_TRIAL' if end<record_end else 'COMPLETED_EXPLORATORY_RECORD',physical_time_s=end,full_record_duration_s=record_end,elapsed_s=time.perf_counter()-case_start,peak_roof_UX_m=max(abs(r[stories[-1]['story_name']+'_UX_m']) for r in rows),peak_roof_UY_m=max(abs(r[stories[-1]['story_name']+'_UY_m']) for r in rows),periods_inspected_s=periods,initial_damping_ratios=[alpha/(2*math.sqrt(v))+beta*math.sqrt(v)/2 for v in eigenvalues],diagnostics=diag,scope=assumptions['scope'])
        from OpenSees_Building_Response_V144 import plot_response
        plot_response(history,case,tracked)
        (case/'Case_Summary.json').write_text(json.dumps(result,indent=2));summary.append(result);print('[EXPLORATORY COMPLETE]',json.dumps(result),flush=True);ops.wipe()
    result=dict(cases=summary,elapsed_s=time.perf_counter()-start,scope=assumptions['scope']);(out/'Exploratory_Summary.json').write_text(json.dumps(result,indent=2));return result

def recover_saved_report(folder,output_dir):
    """Recover postprocessing from accepted CSV rows; never rerun/approve a solver."""
    source=Path(folder).resolve();out=Path(output_dir).resolve()
    if out==source or source in out.parents:raise ValueError('Recovery output must be outside the original run folder')
    out.mkdir(parents=True,exist_ok=True)
    config=json.loads((source/'RunConfig.json').read_text(encoding='utf-8-sig'))
    assumptions=json.loads((source/'ASSUMPTIONS_NOT_DESIGN.json').read_text(encoding='utf-8-sig'))
    data=json.loads((source/'isolated_model/OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'))
    groups=sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2])
    cases=[]
    for orientation in config.get('orientations',['XY','YX']):
        history=source/orientation/'Building_Nonlinear_history.csv'
        if not history.is_file():continue
        with history.open(encoding='utf-8-sig',newline='') as stream:rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
        if not rows or any(not math.isfinite(r['time_s']) for r in rows):raise ValueError('Invalid saved history')
        if any(b['time_s']<=a['time_s'] for a,b in zip(rows,rows[1:])):raise ValueError('History times must strictly increase')
        case=out/orientation;case.mkdir(exist_ok=True);shutil.copy2(history,case/history.name)
        roof='Storey_'+str(groups[-1]['storey_number']);t=rows[-1]['time_s'];requested=float(config.get('duration_s') or 0)
        result=dict(orientation=orientation,status='RECOVERED_SAVED_HISTORY_REPORT',recorded_time_s=t,requested_trial_duration_s=requested,requested_trial_reached=bool(requested and t>=requested-1e-8),accepted_rows=len(rows),peak_roof_UX_m=max(abs(r[roof+'_UX_m']) for r in rows),peak_roof_UY_m=max(abs(r[roof+'_UY_m']) for r in rows),scope=assumptions['scope'],note='Postprocessing recovery only. Original run ended with reporting exception. No missing solver diagnostics, full-record completion, calibration or design acceptance inferred.')
        from OpenSees_Building_Response_V144 import plot_response
        plot_response(history,case,int(config.get('tracked_frame_tag',100001)))
        (case/'Case_Summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');cases.append(result)
        from matplotlib.figure import Figure
        fig=Figure(figsize=(11,6),layout='constrained');axes=fig.subplots(2,1)
        for axis,ax in zip(('X','Y'),axes):ax.plot([r['time_s'] for r in rows],[r[roof+'_U'+axis+'_m']*1000 for r in rows]);ax.set(xlabel='Time (s)',ylabel='Roof U'+axis+' (mm)',title='Recovered '+orientation+' saved trial / nonlinear frames, elastic walls');ax.grid(alpha=.25)
        fig.savefig(case/'Recovered_Roof_History.png',dpi=150)
    report=dict(cases=cases,source_run=str(source),scope=assumptions['scope'],recovered_at=datetime.datetime.now().astimezone().isoformat())
    (out/'Recovered_Summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args();config=json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
    try:run(config)
    except Exception as exc:
        out=Path(config['output_dir']);out.mkdir(parents=True,exist_ok=True)
        (out/'INCOMPLETE.json').write_text(json.dumps(dict(status='INCOMPLETE',error=str(exc),profile=PROFILE),indent=2));raise
