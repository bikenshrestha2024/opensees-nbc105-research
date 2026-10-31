"""Common drift, deformation and NBC 5.4 review outputs. Units m, kN."""
from pathlib import Path
import json,csv,math
from OpenSees_Timing_V130 import timed_outputs


def write_csv(path,rows):
    if rows:
        with Path(path).open('w',newline='',encoding='utf-8-sig') as stream:
            w=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));w.writeheader();w.writerows(rows)

def drift_check(rows,limit_state):
    limit={'ULS':.025,'SLS':.006}[limit_state]
    return [dict(**r,limit_state=limit_state,limit_ratio=limit,clause='NBC 105:2025 5.5.3',status='PASS' if abs(float(r['design_drift_ratio']))<=limit else 'EXCEEDS') for r in rows]

def irregularity(data,story_rows=None,capacity_rows=None):
    groups=sorted(data.get('diaphragms',[]),key=lambda g:g['master_xyz'][2]);nodes=data['nodes'];checks=[]
    def add(clause,kind,level,value,threshold,status,note=''):
        checks.append(dict(clause=clause,check=kind,storey=level,value=value,threshold=threshold,status=status,note=note))
    masses=[];widths=[]
    for g in groups:
        lower=max([float(data['base_z_m'])]+[q['master_xyz'][2] for q in groups if q['master_xyz'][2]<g['master_xyz'][2]-1e-7])
        mass=sum(float(m) for n,m in data.get('nodal_mass',{}).items() if lower+1e-7<nodes.get(str(n),nodes.get(n))[2]<=g['master_xyz'][2]+1e-7);masses.append(mass)
        pts=[]
        for e in data.get('frames',[])+data.get('shells',[]):
            if str(e.get('category')).upper() in ('COLUMN','BRACE','SHEAR WALL','SHEARWALL'):
                for n in e['nodes']:
                    xyz=nodes.get(str(n),nodes.get(n))
                    if abs(xyz[2]-g['master_xyz'][2])<1e-6:pts.append(xyz)
        widths.append([max(v[a] for v in pts)-min(v[a] for v in pts) for a in (0,1)] if pts else [None,None])
    for i in range(len(groups)-1):
        level=groups[i]['storey_number'];ratio=max(masses[i],masses[i+1])/min(masses[i],masses[i+1]) if min(masses[i],masses[i+1])>0 else None
        add('5.4.1.5','Mass irregularity',level,ratio,1.5,'IRREGULAR' if ratio and ratio>1.5 else 'PASS' if ratio else 'NOT EVALUATED','Review roof/penthouse/mezzanine exclusions explicitly; no automatic exemption.')
        for axis in (0,1):
            a,b=widths[i][axis],widths[i+1][axis];ratio=max(a,b)/min(a,b) if a and b else None
            add('5.4.1.3','LFRS extent '+('X','Y')[axis],level,ratio,1.3,'IRREGULAR' if ratio and ratio>1.3 else 'PASS' if ratio else 'NOT EVALUATED','Geometry extent screen; continuity/member roles require review.')
    if story_rows:
        for i,r in enumerate(story_rows[:-1]):
            k=r.get('story_stiffness_kN_per_m');ku=story_rows[i+1].get('story_stiffness_kN_per_m')
            if k and ku and k>0 and ku>0 and math.isfinite(k) and math.isfinite(ku):add('5.4.1.2','Soft story adjacent above',r.get('story_number',i+1),k/ku,.7,'IRREGULAR' if k<.7*ku else 'PASS','V/drift secant stiffness from selected static load pattern.')
            if len(story_rows[i+1:i+4])==3:
                vals=[q.get('story_stiffness_kN_per_m') for q in story_rows[i+1:i+4]]
                if k and k>0 and math.isfinite(k) and all(v and v>0 and math.isfinite(v) for v in vals):add('5.4.1.2','Soft story three above',r.get('story_number',i+1),k/(sum(vals)/3),.8,'IRREGULAR' if k<.8*sum(vals)/3 else 'PASS')
    else:add('5.4.1.2','Soft story','ALL',None,None,'NOT EVALUATED','Run a static lateral case or supply reviewed story stiffness.')
    if capacity_rows:
        for a,b in zip(sorted(capacity_rows,key=lambda r:float(r['storey_number'])),sorted(capacity_rows,key=lambda r:float(r['storey_number']))[1:]):
            ratio=float(a['lateral_strength_kN'])/float(b['lateral_strength_kN']);add('5.4.1.1','Weak story',a['storey_number'],ratio,.8,'IRREGULAR' if ratio<.8 else 'PASS')
    else:add('5.4.1.1','Weak story','ALL',None,.8,'NOT EVALUATED','Requires reviewed lateral-strength capacities; elastic stiffness is not strength.')
    for clause,kind in [('5.4.1.4','In-plane discontinuity'),('5.4.2.1','Torsion'),('5.4.2.2','Extreme torsion'),('5.4.2.3','Re-entrant corners'),('5.4.2.4','Diaphragm discontinuity'),('5.4.2.5','Out of plane offset')]:add(clause,kind,'ALL',None,None,'NOT EVALUATED','Requires floor-edge center-of-mass response or reviewed plan/vertical load-path geometry; not inferred from bounding box.')
    return dict(checks=checks,overall='IRREGULAR' if any(r['status']=='IRREGULAR' for r in checks) else 'INCOMPLETE' if any(r['status']=='NOT EVALUATED' for r in checks) else 'NO TRIGGER FOUND',note='A partial screen cannot certify regularity; missing checks remain explicit.')

@timed_outputs('Static drift, deformation and irregularity export','output')
def export_static_response(ops,model_script,output,story_rows,limit_state,baseline=None,design_factor=1.):
    output=Path(output);source=Path(model_script).parent/'OpenSees_Complete_Model_Data_V118.json'
    if not source.is_file():return
    data=json.loads(source.read_text(encoding='utf-8-sig'));tag=str(story_rows[0].get('limit_state',limit_state))+'_'+str(story_rows[0].get('direction','case'))
    # Unique generated runner output prefix is supplied in the row metadata.
    tag=story_rows[0].get('response_case',tag)
    checks=drift_check(story_rows,limit_state);write_csv(output/('Drift_Check_'+tag+'_V132.csv'),checks)
    if baseline:
        groups=sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2]);edge_rows=[]
        case_axis='Y' if '_Y' in tag else 'X';dof=1 if case_axis=='Y' else 0;perp=0 if case_axis=='Y' else 1;sign=1 if case_axis=='Y' else -1
        for i,g in enumerate(groups):
            below=groups[i-1] if i else None;h=g['master_xyz'][2]-(below['master_xyz'][2] if below else data['base_z_m']);pts=[data['nodes'][str(n)] for n in g['slave_node_tags'] if str(n) in data['nodes']]
            def floor_u(group,position):
                if not group:return 0.
                n=group['master_tag'];u=ops.nodeDisp(n);initial=baseline.get(n,baseline.get(str(n),[0.]*6));return (u[dof]-initial[dof])+sign*(u[5]-initial[5])*(position-group['master_xyz'][perp])
            for end,position in enumerate((min(p[perp] for p in pts),max(p[perp] for p in pts))):
                drift=abs(floor_u(g,position)-floor_u(below,position))/h
                edge_rows.append(dict(story_number=g['storey_number'],axis=case_axis,edge=end+1,floor_displacement_m=floor_u(g,position),height_m=g['master_xyz'][2]-data['base_z_m'],elastic_drift_ratio=drift,design_drift_ratio=drift*design_factor))
        write_csv(output/('Floor_Edge_Drift_'+tag+'_V132.csv'),drift_check(edge_rows,limit_state))
    disp={str(n):list(ops.nodeDisp(int(n))) for n in data['nodes']}
    (output/('Deformation_'+tag+'_V132.json')).write_text(json.dumps(dict(nodes=data['nodes'],elements=[e['nodes'] for e in data['frames']+data['shells']],displacements=disp,note='Total converged displacement including gravity; use design drift CSV for seismic drift acceptance.')),encoding='utf-8')
    review=irregularity(data,story_rows)
    review.update(model_sha256=__import__('hashlib').sha256(source.read_bytes()).hexdigest(),limit_state=limit_state,response_case=tag)
    if baseline and all(abs(r.get('Mz_kNm',0.))<1e-10 for r in story_rows):
        review['checks']=[r for r in review['checks'] if r['check'] not in ('Torsion','Extreme torsion')]
        for g in groups:
            magnitudes=[abs(r['floor_displacement_m']) for r in edge_rows if r['story_number']==g['storey_number']]
            ratio=max(magnitudes)/min(magnitudes) if min(magnitudes)>1e-12 else math.inf if max(magnitudes)>1e-12 else None
            for clause,name,threshold in [('5.4.2.1','Torsion',1.5),('5.4.2.2','Extreme torsion',2.5)]:
                review['checks'].append(dict(clause=clause,check=name,storey=g['storey_number'],value=('UNBOUNDED' if ratio==math.inf else ratio),threshold=threshold,status='IRREGULAR' if ratio and ratio>threshold else 'PASS' if ratio else 'NOT EVALUATED',note='Selected center-loaded static direction; also check the other direction. Extreme torsion requires configuration revision.'))
        review['overall']='IRREGULAR' if any(r['status']=='IRREGULAR' for r in review['checks']) else 'INCOMPLETE' if any(r['status']=='NOT EVALUATED' for r in review['checks']) else 'NO TRIGGER FOUND'

    (output/('Irregularity_'+tag+'_V132.json')).write_text(json.dumps(review,indent=2),encoding='utf-8');write_csv(output/('Irregularity_'+tag+'_V132.csv'),review['checks'])

def export_history_checks(lines,stories,output,case,limit_state,model_script=None):
    rows=[]
    for s in stories:
        for axis in ('X','Y'):
            key=s['story_name']+'_drift_'+axis
            critical=max(lines,key=lambda r:abs(r[key]))
            rows.append(dict(story=s['story_name'],axis=axis,critical_time_s=critical['time_s'],design_drift_ratio=abs(critical[key]),height_m=s['height']))
    write_csv(Path(output)/('Drift_Check_'+case+'_V132.csv'),drift_check(rows,limit_state))
    edge_peaks={};edge_rows=[]
    if model_script:
        path=Path(model_script).parent/'OpenSees_Complete_Model_Data_V118.json'
        if path.is_file():
            data=json.loads(path.read_text(encoding='utf-8-sig'));groups=sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2]);base=data['base_z_m']
            edge_rows=[]
            for i,g in enumerate(groups):
                below=groups[i-1] if i else None;h=g['master_xyz'][2]-(below['master_xyz'][2] if below else base);pts=[data['nodes'][str(n)] for n in g['slave_node_tags'] if str(n) in data['nodes']]
                up=stories[i]['story_name'];low=stories[i-1]['story_name'] if i else None
                for axis,perp,sign in [('X',1,-1),('Y',0,1)]:
                    for end,position in enumerate((min(p[perp] for p in pts),max(p[perp] for p in pts))):
                        def ratio(row):
                            upper=row[up+'_U'+axis+'_m']+sign*row.get(up+'_RZ_rad',0.)*(position-g['master_xyz'][perp])
                            lower=(row[low+'_U'+axis+'_m']+sign*row.get(low+'_RZ_rad',0.)*(position-below['master_xyz'][perp])) if below else 0.
                            return abs(upper-lower)/h
                        critical_edge=max(lines,key=ratio);value=ratio(critical_edge);edge_peaks[axis]=max(value,edge_peaks.get(axis,0.))
                        edge_rows.append(dict(story_number=g['storey_number'],axis=axis,edge=end+1,critical_time_s=critical_edge['time_s'],design_drift_ratio=value))
            write_csv(Path(output)/('Floor_Edge_Drift_'+case+'_V132.csv'),drift_check(edge_rows,limit_state))
            critical=max(lines,key=lambda r:max(abs(r[s['story_name']+'_drift_'+a]) for s in stories for a in ('X','Y')))
            from OpenSees_History_Inspection_V133 import floor_snapshot
            displacement=floor_snapshot(data,stories,critical)
            result=dict(nodes=data['nodes'],dof_availability=[True,True,False,False,False,all(s['story_name']+'_RZ_rad' in lines[0] for s in stories)],elements=[e['nodes'] for e in data['frames']+data['shells']],displacements=displacement,note='Coherent time '+str(critical['time_s'])+' s at peak master drift; rigid-floor lateral reconstruction with inter-floor interpolation, not exact frame/wall curvature or vertical deformation.')
            (Path(output)/('Deformation_'+case+'_V132.json')).write_text(json.dumps(result),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,6),layout='constrained')
    z=[];height=0.
    for s in stories:height+=s['height'];z.append(height)
    for axis in ('X','Y'):
        axes[0].plot([max(abs(r[s['story_name']+'_U'+axis+'_m']) for r in lines) for s in stories],z,label=axis)
        axes[1].plot([max([r['design_drift_ratio'] for r in edge_rows if r['axis']==axis and r['story_number']==groups[i]['storey_number']] or [max(abs(r[s['story_name']+'_drift_'+axis]) for r in lines)]) for i,s in enumerate(stories)] if edge_rows else [max(abs(r[s['story_name']+'_drift_'+axis]) for r in lines) for s in stories],z,label=axis)
    axes[0].set(xlabel='Peak floor displacement (m)',ylabel='Height (m)',title='Independent floor maxima; not a simultaneous shape')
    axes[1].axvline(.025 if limit_state=='ULS' else .006,color='r',ls='--');axes[1].set(xlabel='Drift ratio',title=limit_state+' drift screen')
    for ax in axes:ax.legend();ax.grid(alpha=.2)
    fig.savefig(Path(output)/('Drift_Profile_'+case+'_V132.png'),dpi=160);plt.close(fig)
    return edge_peaks

def launch_response_viewer(parent,folder):
    from OpenSees_Response_Viewer_V134 import launch
    return launch(parent,folder)


def launch_irregularity_legacy(parent,folder):
    import tkinter as tk
    from tkinter import ttk,messagebox,filedialog
    folder=Path(folder);win=tk.Toplevel(parent);win.title('NBC 105:2025 clause 5.4 structural irregularity review');win.geometry('1200x700')
    text=tk.Text(win,wrap='word',height=4);text.pack(fill='x');text.insert('end','Geometry/mass are read from the assembled model. Soft-story checks need a static response; weak-story checks need capacities. Torsion, discontinuity and re-entrant geometry require reviewed evidence. Missing input is INCOMPLETE, not regular. Optional reviewed-input JSON can supply explicit capacity and plan checks.');text.configure(state='disabled')
    frame=ttk.Frame(win);frame.pack(fill='both',expand=True);tree=ttk.Treeview(frame,columns=('clause','check','storey','value','threshold','status','note'),show='headings')
    for k in tree['columns']:tree.heading(k,text=k);tree.column(k,width=150,stretch=False)
    sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);sy=ttk.Scrollbar(frame,command=tree.yview);tree.configure(xscrollcommand=sx.set,yscrollcommand=sy.set);sx.pack(side='bottom',fill='x');sy.pack(side='right',fill='y');tree.pack(fill='both',expand=True)
    current={'result':None}
    source_choice=tk.StringVar(value='Geometry / reviewed inputs only')
    source_box=ttk.Combobox(win,textvariable=source_choice,state='readonly',width=130);source_box.pack(fill='x')
    def sources():
        values=['Geometry / reviewed inputs only']+[str(p.relative_to(folder)) for p in sorted((folder/'OpenSees_Analysis_Results').rglob('Irregularity_*_E0_V132.json'))]
        source_box['values']=values
        if source_choice.get() not in values:source_choice.set(values[0])
    sources()
    def run(review_path=None):
        try:
            data=json.loads((folder/'OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'));review=json.loads(Path(review_path).read_text(encoding='utf-8-sig')) if review_path else {}
            for rows_key,value_key in [('story_stiffness_rows','story_stiffness_kN_per_m'),('capacity_rows','lateral_strength_kN')]:
                for row in review.get(rows_key,[]):
                    if not math.isfinite(float(row[value_key])) or float(row[value_key])<=0:raise ValueError(rows_key+' requires finite positive values')
                    if not row.get('evidence'):raise ValueError(rows_key+' requires a project evidence reference on each row')
            result=irregularity(data,review.get('story_stiffness_rows'),review.get('capacity_rows'))
            if source_choice.get()!='Geometry / reviewed inputs only':
                selected=folder/source_choice.get();saved=json.loads(selected.read_text(encoding='utf-8-sig'))
                fingerprint=__import__('hashlib').sha256((folder/'OpenSees_Complete_Model_Data_V118.json').read_bytes()).hexdigest()
                if saved.get('model_sha256')!=fingerprint:raise ValueError('Static review has no matching current-model fingerprint. Rerun the centered ESM case using V133 before importing it.')
                result['checks']=[r for r in result['checks'] if r['check'] not in ('Torsion','Extreme torsion') and not r['check'].startswith('Soft story')]
                result['checks'].extend(r for r in saved['checks'] if r['check'] in ('Torsion','Extreme torsion') or r['check'].startswith('Soft story'))
                result['source_static_case']=str(selected)
                result['checks'].append(dict(clause='5.4',check='Other-direction static response coverage',storey='ALL',value=None,threshold=None,status='NOT EVALUATED',note='Selected centered case '+saved.get('response_case','')+'; review the other loading direction and both applicable stiffness states separately.'))
            for item in review.get('plan_and_continuity_checks',[]):
                if not item.get('evidence'):raise ValueError('Reviewed plan/continuity check requires an evidence reference.')
                if item.get('status') not in ('PASS','IRREGULAR','NOT EVALUATED'):raise ValueError('Reviewed status must be PASS, IRREGULAR or NOT EVALUATED')
                result['checks']=[r for r in result['checks'] if r['check']!=item['check']]
                result['checks'].append(item)
            result['overall']='IRREGULAR' if any(r['status']=='IRREGULAR' for r in result['checks']) else 'INCOMPLETE' if any(r['status']=='NOT EVALUATED' for r in result['checks']) else 'NO TRIGGER FOUND'
            for row in tree.get_children():tree.delete(row)
            for row in result['checks']:tree.insert('','end',values=[row.get(k,'') for k in tree['columns']])
            current['result']=result;out=folder/'OpenSees_Analysis_Results';out.mkdir(exist_ok=True);from OpenSees_Timing_V130 import StageTimer;timer=StageTimer(out,'Irregularity review export');(out/'NBC105_Irregularity_V132.json').write_text(json.dumps(result,indent=2),encoding='utf-8');write_csv(out/'NBC105_Irregularity_V132.csv',result['checks']);timer.finish('completed')
            win.title('NBC 5.4 review: '+result['overall'])
        except Exception as exc:messagebox.showerror('Irregularity input',str(exc),parent=win)
    def load():
        path=filedialog.askopenfilename(parent=win,filetypes=[('Reviewed evidence JSON','*.json')])
        if path:run(path)
    source_box.bind('<<ComboboxSelected>>',lambda event:run())
    ttk.Button(win,text='Refresh from assembled model / saved centered cases',command=lambda:(sources(),run())).pack(anchor='w');ttk.Button(win,text='Load reviewed stiffness/capacity/plan input JSON',command=load).pack(anchor='w');run();return win


def launch_irregularity(parent,folder):
    from OpenSees_Irregularity_Review_V134 import launch
    return launch(parent,folder)
