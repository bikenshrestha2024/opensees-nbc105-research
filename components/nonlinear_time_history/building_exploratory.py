"""Own building geometry with explicitly assumed research constitutive models.
This does not approve or modify the calibrated production-model workflow.
"""
from pathlib import Path
import json,math,time,csv,shutil,hashlib,datetime
import traceback
import numpy as np
PROFILE='LITERATURE_FRAME_NL_ELASTIC_WALL_V138'
TRANSIENT_SYSTEMS=('UmfPack','SparseGeneral')
_RUN_CONTEXT={}

def configure_transient_system(ops,system):
    """Select a supported transient matrix solver without silent fallbacks."""
    if system not in TRANSIENT_SYSTEMS:
        raise ValueError('transient_system must be one of: '+', '.join(TRANSIENT_SYSTEMS))
    if system=='SparseGeneral':ops.system('SparseGeneral','-piv')
    else:ops.system('UmfPack')

def profile_for_config(config):
    """Return the research profile selected by the exploratory configuration."""
    return 'LITERATURE_BUILDING_NL_V161' if bool(config.get('nonlinear_walls',False)) else PROFILE


def validate_output_separation(source, output):
    source_path=Path(source).resolve()
    output_path=Path(output).resolve()
    if output_path==source_path:
        raise ValueError('Choose a separate output folder; it may be a subfolder of the model export folder.')
    return source_path,output_path


def diagnostic_record_inputs(records,orientation,excitation):
    """Return records assigned to global X/Y, zeroing only inactive probe axes."""
    if orientation not in ('XY','YX'):
        raise ValueError('orientation must be XY or YX')
    excitation=str(excitation).upper()
    if excitation not in ('XY','X','Y','ZERO'):
        raise ValueError('diagnostic_excitation must be XY, X, Y or ZERO')
    ordered=records if orientation=='XY' else records[::-1]
    result=[]
    for direction,(values,step,units) in enumerate(ordered,1):
        active=excitation=='XY' or excitation=='X' and direction==1 or excitation=='Y' and direction==2
        result.append((values if active else np.zeros_like(values),step,units))
    return result

def _set_run_stage(stage,**details):
    _RUN_CONTEXT['stage']=stage
    _RUN_CONTEXT.update(details)

def _write_failure_report(folder,config,exc,*,filename='INCOMPLETE.json',details=None):
    source=config.get('model_folder')
    output=config.get('output_dir')
    if source and output:
        try:
            validate_output_separation(source,output)
        except ValueError:
            print('[FAILURE REPORT NOT WRITTEN] Output directory must be separate from the source model folder.',flush=True)
            return None
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    report=dict(
        status='INCOMPLETE',
        failed_at=datetime.datetime.now().astimezone().isoformat(),
        profile=profile_for_config(config),
        stage=_RUN_CONTEXT.get('stage','unknown'),
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(),
        config=config,
        context=dict(_RUN_CONTEXT),
    )
    if details:
        report.update(details)
    target=folder/filename
    target.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print('[FAILURE REPORT]',str(target),flush=True)
    return target

def run(config):
    _RUN_CONTEXT.clear()
    _RUN_CONTEXT.update(stage='configuration_validation',output_dir=str(config.get('output_dir','')))
    try:
        return _run(config)
    except Exception as exc:
        try:
            _write_failure_report(config.get('output_dir') or '.',config,exc)
        except OSError as report_error:
            print('[FAILURE REPORT ERROR]',repr(report_error),flush=True)
        raise

def _run(config):
    _set_run_stage('configuration_validation',output_dir=str(config.get('output_dir','')))
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
    excitation=str(config.get('diagnostic_excitation','XY')).upper()
    if excitation not in ('XY','X','Y','ZERO'):
        raise ValueError('diagnostic_excitation must be XY, X, Y or ZERO')
    if config.get('diagnostic_zero_damping') and config.get('diagnostic_mass_damping'):
        raise ValueError('Select only one diagnostic damping override')
    _set_run_stage('loading_analysis_dependencies')
    from OpenSees_Complete_Export_V118 import build_complete_model
    from OpenSees_Input_Records_V130 import _read_peer_text_record
    from OpenSees_Nonlinear_Time_History_NBC105_V116 import _advance_nonlinear_interval,_configure_nonlinear_transient
    from OpenSees_Step13_Analysis_Basis_V115 import rayleigh_coefficients
    from OpenSees_Response_Checks_V132 import export_history_checks
    from components.shared.response_recorders import (
        append_base_shear, support_resultants, write_base_shear_roof_curve,
        write_recorder_index, write_rows,
    )
    full_wall=bool(config.get('nonlinear_walls',False))
    profile=profile_for_config(config)
    _RUN_CONTEXT.update(profile=profile,diagnostic_excitation=excitation,
                        transient_system=transient_system,gravity_system=gravity_system,
                        nonlinear_walls=full_wall,
                        diagnostic_zero_damping=bool(config.get('diagnostic_zero_damping')),
                        diagnostic_mass_damping=bool(config.get('diagnostic_mass_damping')))
    import os
    os.environ['OPENSEES_RESEARCH_MATERIAL_BASIS']=config.get('material_basis','PUBLISHED_REFERENCE')
    os.environ['OPENSEES_STEELMPF_TRANSITION']=config.get('steelmpf_transition','OPENSEES_DOCUMENTED')
    source,out=validate_output_separation(config['model_folder'],config['output_dir'])
    out.mkdir(parents=True,exist_ok=True)
    model=out/'isolated_model';model.mkdir(exist_ok=True)
    _set_run_stage('reading_records_and_model_inputs')
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
        assumptions.update(frame_materials='Literature unconfined Concrete01 + nominal Fe500 Steel02; existing bar-layout templates remain assumptions',wall_materials='Nonlinear E_SFI_MVLEM_3D + ConcreteCM / SteelMPF / FSAM; exact selected parameters exported per property',material_basis=config.get('material_basis','PUBLISHED_REFERENCE'),steelmpf_transition_profile=config.get('steelmpf_transition','OPENSEES_DOCUMENTED'),limitation='Research material transfer and reinforcement templates, not experimental building calibration or NBC design acceptance')
    from Define_Section_V109 import RC_SECTION_CONFIG
    assumptions['RC_template_inputs']=RC_SECTION_CONFIG
    (out/'ASSUMPTIONS_NOT_DESIGN.json').write_text(json.dumps(assumptions,indent=2),encoding='utf-8');(out/'RunConfig.json').write_text(json.dumps(config,indent=2),encoding='utf-8');summary=[]
    for orientation in config.get('orientations',['XY','YX']):
        if orientation not in ('XY','YX'):raise ValueError('Orientation must be XY or YX')
        case=out/orientation;case.mkdir(exist_ok=True);print('[EXPLORATORY START]',orientation,'no calibration or design approval implied',flush=True)
        _set_run_stage('model_build_and_gravity',orientation=orientation,case_output_dir=str(case))
        build_complete_model(
            model, mode='nonlinear', preload=True,
            limit_state=config.get('limit_state','ULS'),
            research_profile=profile, gravity_system=gravity_system)
        import openseespy.opensees as ops
        support_nodes=[
            int(node) for node,flags in data['supports'].items()
            if any(bool(value) for value in flags[:3])
        ]
        if not support_nodes:
            raise ValueError('The assembled model export has no support nodes for base-shear recording.')
        base_reaction_reference=support_resultants(ops,support_nodes)
        if full_wall:
            shutil.copy2(model/'Research_Material_Assignment_V161.json',case/'Research_Material_Assignment_V161.json')
        groups=sorted(data['diaphragms'],key=lambda r:r['master_xyz'][2]);baseline={g['master_tag']:list(ops.nodeDisp(g['master_tag'])) for g in groups}
        print('[EXPLORATORY MODAL] Computing 20 initial nonlinear modes; transient has not started',flush=True)
        _set_run_stage('modal_analysis',orientation=orientation,case_output_dir=str(case))
        from components.shared.eigen_solver import solve_eigen
        eigenvalues=solve_eigen(ops,20);periods=[2*math.pi/math.sqrt(v) for v in eigenvalues if v>0]
        if len(periods)!=20:raise ValueError('Inspected nonlinear modes incomplete')
        bound=min(records[0][1],.01,periods[0]/100.,periods[-1])
        if dt>bound:raise ValueError(f'Chosen dt {dt} exceeds inspected-mode screen {bound:g}s; reduce dt')
        alpha,beta=rayleigh_coefficients(max(periods),min(periods),.05)
        if config.get('diagnostic_mass_damping'):alpha,beta=2*.05*min(math.sqrt(v) for v in eigenvalues),0.
        if config.get('diagnostic_zero_damping'):alpha,beta=0.,0.
        print('[TRANSIENT PROBE]', 'excitation='+excitation, 'zero_damping='+str(bool(config.get('diagnostic_zero_damping'))), 'system='+transient_system, flush=True)
        (case/'Initial_Modal_Damping.json').write_text(json.dumps(dict(eigenvalues=eigenvalues,periods_s=periods,alphaM=alpha,betaKcomm=beta,dt_screen_s=bound),indent=2))
        ops.rayleigh(alpha,0.,0.,beta)
        _set_run_stage('transient_setup',orientation=orientation,case_output_dir=str(case))
        for direction,r in enumerate(diagnostic_record_inputs(records,orientation,excitation),1):
            values,step,units=r
            tag=900000+direction
            ops.timeSeries('Path',tag,'-dt',step,'-values',*values.tolist(),'-factor',unit_factor[units]*scale)
            ops.pattern('UniformExcitation',tag,direction,'-accel',tag)
        _configure_nonlinear_transient(ops)
        configure_transient_system(ops,transient_system)
        diag={
            'evidence_output_path':str(case/'First_Step_Failure_Evidence.json'),
            'element_map_path':str(model/'OpenSees_Complete_Element_Map_V118.json'),
        };rows=[];last=time.perf_counter();case_start=last
        stories=[dict(node=g['master_tag'],story_name='Storey_'+str(g['storey_number']),height=g['master_xyz'][2]-(groups[i-1]['master_xyz'][2] if i else data['base_z_m'])) for i,g in enumerate(groups)]
        wall_tags=[100001+len(data['frames'])+i for i,e in enumerate(data['shells']) if e['category']=='SHEAR WALL']
        tracked_wall=int(config.get('tracked_wall_tag',wall_tags[0])) if wall_tags else None
        tracked=int(config.get('tracked_frame_tag',100001))
        if not 100001<=tracked<100001+len(data['frames']):raise ValueError('Tracked frame solver tag is outside the assembled frame range')
        def capture():
            row={'time_s':ops.getTime()};previous=[0.]*6
            for story,g in zip(stories,groups):
                u=[a-b for a,b in zip(ops.nodeDisp(g['master_tag']),baseline[g['master_tag']])];name=story['story_name']
                acceleration=list(ops.nodeAccel(g['master_tag']))
                for j,axis in enumerate(('X','Y','Z')):row[name+'_U'+axis+'_m']=u[j]
                row[name+'_UX_relative_accel_m_s2']=acceleration[0]
                row[name+'_UY_relative_accel_m_s2']=acceleration[1]
                for j,axis in enumerate(('X','Y','Z'),3):row[name+'_R'+axis+'_rad']=u[j]
                row[name+'_RZ_rad']=u[5]
                for j,axis in enumerate(('X','Y')):row[name+'_drift_'+axis]=(u[j]-previous[j])/story['height']
                previous=u
            append_base_shear(
                row,ops,support_nodes,base_reaction_reference)
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
        _set_run_stage('transient_analysis',orientation=orientation,case_output_dir=str(case),
                       requested_duration_s=end,record_duration_s=record_end,
                       integration_step_s=dt,started_at=datetime.datetime.now().astimezone().isoformat())
        with history.open('w',newline='',encoding='utf-8-sig') as stream:
            capture();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerow(rows[-1]);stream.flush()
            try:
                while ops.getTime()<end-1e-10:
                    before=len(rows);_advance_nonlinear_interval(ops,min(dt,end-ops.getTime()),on_accept=capture,diagnostics=diag)
                    writer.writerows(rows[before:])
                    if time.perf_counter()-last>5:last=time.perf_counter();stream.flush();print(f'[EXPLORATORY PROGRESS] {orientation}: t={ops.getTime():.3f}/{end:.3f}s | wall={last-case_start:.1f}s',flush=True)
            except Exception as exc:
                try:
                    _write_failure_report(
                        case,config,exc,filename='FAILED.json',
                        details=dict(orientation=orientation,time_s=ops.getTime(),
                                     elapsed_s=time.perf_counter()-case_start,
                                     accepted_history_rows=len(rows),
                                     solver_diagnostics=diag,analysis_scope=assumptions['scope']))
                except OSError as report_error:
                    print('[FAILURE REPORT ERROR]',repr(report_error),flush=True)
                raise
        _set_run_stage('response_postprocessing',orientation=orientation,case_output_dir=str(case),
                       accepted_history_rows=len(rows),completed_time_s=ops.getTime())
        (case/'NBC105_Exploratory_Time_History_RunConfig_V138.json').write_text(json.dumps(dict(model_script='../isolated_model/OpenSees_Complete_Model_Data_V118.json',scope=assumptions['scope'])),encoding='utf-8')
        export_history_checks(rows,stories,case,'EXPLORATORY_'+orientation,config.get('limit_state','ULS'),model_script=str(model/'OpenSees_Complete_Model_Data_V118.json'))
        base_curve_path=write_base_shear_roof_curve(
            case/('BaseShear_RoofDisplacement_'+orientation+'.csv'),
            rows,stories[-1]['story_name'])
        tracked_frame_curve=[]
        for row in rows:
            if 'selected_frame_My_kNm' in row and 'section_kappa_z_1_per_m' in row:
                tracked_frame_curve.append(dict(
                    time_s=row['time_s'],
                    selected_frame_N_kN=row.get('selected_frame_N_kN'),
                    selected_frame_My_kNm=row['selected_frame_My_kNm'],
                    section_axial_strain=row.get('section_axial_strain'),
                    section_kappa_z_1_per_m=row['section_kappa_z_1_per_m'],
                    section_kappa_y_1_per_m=row.get('section_kappa_y_1_per_m')))
        tracked_frame_path=None
        if tracked_frame_curve:
            tracked_frame_path=write_rows(
                case/'Tracked_Frame_Moment_Curvature.csv',
                tracked_frame_curve)
        tracked_wall_curve=[]
        wall_indexes=sorted({
            int(key.rsplit('_',1)[1])
            for key in rows[0]
            if key.startswith('wall_panel_strain_')
        })
        for row in rows:
            for index in wall_indexes:
                strain_key='wall_panel_strain_'+str(index)
                stress_key='wall_panel_stress_kN_m2_'+str(index)
                if strain_key in row and stress_key in row:
                    tracked_wall_curve.append(dict(
                        time_s=row['time_s'],panel_component=index,
                        strain=row[strain_key],
                        stress_kN_m2=row[stress_key]))
        tracked_wall_path=None
        if tracked_wall_curve:
            tracked_wall_path=write_rows(
                case/'Tracked_Wall_Stress_Strain.csv',tracked_wall_curve)
        recorder_files=[
            (history.name,[
                'accepted adaptive substep time','all-story Ux/Uy/Uz/Rx/Ry/Rz',
                'all-story relative UX/UY acceleration',
                'all-story drift X/Y','incremental support reactions',
                'signed base shear X/Y','tracked frame forces/section strains',
                'tracked E-SFI panel response']),
            (base_curve_path.name,[
                'time_s','roof_UX_m','roof_UY_m',
                'base_shear_X_kN','base_shear_Y_kN']),
            ('Concurrent_Final_Frame_Actions.csv',[
                'final-time frame end axial/shear/torsion/moments']),
        ]
        if tracked_frame_path:
            recorder_files.append((tracked_frame_path.name,[
                'selected frame My versus section curvature',
                'selected frame axial force and section axial strain']))
        if tracked_wall_path:
            recorder_files.append((tracked_wall_path.name,[
                'selected E-SFI wall panel stress-strain histories']))
        write_recorder_index(
            case,'nonlinear_time_history',
            recorder_files,
            notes=[
                'Support reactions and base shear are incremental relative to the gravity-frozen state.',
                'The base-shear/roof-displacement file preserves synchronized accepted states and can be plotted as a hysteresis history.',
                'Tracked member and wall channels are controlled by tracked_frame_tag and tracked_wall_tag; the final frame-action table covers all frame elements.',
            ],
        )
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
        result=dict(orientation=orientation,wall_model='E_SFI_MVLEM_3D' if full_wall else 'ELASTIC',frame_model='LITERATURE_CONCRETE01_NOMINAL_FE500' if full_wall else 'NONLINEAR_ILLUSTRATIVE_RC_FIBERS',gravity_system=gravity_system,transient_system=transient_system,diagnostic_excitation=excitation,diagnostic_zero_damping=bool(config.get('diagnostic_zero_damping')),diagnostic_mass_damping=bool(config.get('diagnostic_mass_damping')),rayleigh_alphaM=alpha,rayleigh_betaKcomm=beta,status='COMPLETED_TRUNCATED_TRIAL' if end<record_end else 'COMPLETED_EXPLORATORY_RECORD',physical_time_s=end,full_record_duration_s=record_end,elapsed_s=time.perf_counter()-case_start,peak_roof_UX_m=max(abs(r[stories[-1]['story_name']+'_UX_m']) for r in rows),peak_roof_UY_m=max(abs(r[stories[-1]['story_name']+'_UY_m']) for r in rows),periods_inspected_s=periods,initial_damping_ratios=[alpha/(2*math.sqrt(v))+beta*math.sqrt(v)/2 for v in eigenvalues],diagnostics=diag,scope=assumptions['scope'])
        from OpenSees_Building_Response_V144 import plot_response
        plot_response(history,case,tracked)
        (case/'Case_Summary.json').write_text(json.dumps(result,indent=2));summary.append(result);print('[EXPLORATORY COMPLETE]',json.dumps(result),flush=True);ops.wipe()
    result=dict(cases=summary,elapsed_s=time.perf_counter()-start,scope=assumptions['scope']);(out/'Exploratory_Summary.json').write_text(json.dumps(result,indent=2));_set_run_stage('completed',output_dir=str(out));return result

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
    run(config)
