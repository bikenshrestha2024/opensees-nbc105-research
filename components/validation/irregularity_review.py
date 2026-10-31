"""NBC 5.4 geometry checks and centered-load stiffness/torsion diagnostics."""
from pathlib import Path
import json,csv,math,hashlib,time
from OpenSees_Timing_V130 import timed_outputs


def plan_checks(data):
    rows=[];outlines=[]
    try:
        from shapely.geometry import Polygon
        from shapely.geometry.polygon import orient
        from shapely.ops import unary_union
    except ImportError:return [dict(clause='5.4.2.3',check='Re-entrant corners',storey='ALL',value=None,threshold=.15,status='NOT EVALUATED',note='Install shapely for exact slab-cell union; bounding boxes alone do not establish the plan boundary.')],[]
    for g in sorted(data['diaphragms'],key=lambda x:x['master_xyz'][2]):
        z=g['master_xyz'][2];cells=[]
        for e in data['shells']:
            pts=[data['nodes'][str(n)] for n in e['nodes']]
            if e.get('category')=='FLOOR' and all(abs(p[2]-z)<1e-6 for p in pts):
                poly=Polygon([(p[0],p[1]) for p in pts])
                if not poly.is_valid:raise ValueError('Invalid source floor polygon at storey '+str(g['storey_number']))
                cells.append(poly)
        if not cells:
            rows.append(dict(clause='5.4.2.3',check='Re-entrant corners',storey=g['storey_number'],value=None,threshold=.15,status='NOT EVALUATED',note='No coplanar source FLOOR cells.'));continue
        union=unary_union(cells).simplify(1e-7,preserve_topology=True);polys=[union] if union.geom_type=='Polygon' else list(union.geoms);bounds=union.bounds;span=[bounds[2]-bounds[0],bounds[3]-bounds[1]];ratios=[0.,0.];corners=[]
        for poly in polys:
            ring=list(orient(poly,sign=1.).exterior.coords)[:-1]
            for i,p in enumerate(ring):
                a=ring[i-1];b=ring[(i+1)%len(ring)];turn=(p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0])
                if turn < -1e-10:
                    projection=[max(abs(a[j]-p[j]),abs(b[j]-p[j])) for j in (0,1)]
                    ratios=[max(ratios[j],projection[j]/span[j]) if span[j]>0 else None for j in (0,1)];corners.append(dict(x=p[0],y=p[1],projection_x_m=projection[0],projection_y_m=projection[1]))
            outlines.append(dict(storey=g['storey_number'],exterior=ring,interior_openings=len(poly.interiors),corners=corners))
        for j,axis in enumerate(('X','Y')):rows.append(dict(clause='5.4.2.3',check='Re-entrant projection '+axis,storey=g['storey_number'],value=ratios[j],threshold=.15,status='IRREGULAR' if ratios[j] is not None and ratios[j]>.15 else 'PASS' if len(polys)==1 and ratios[j] is not None else 'NOT EVALUATED',note='Exterior slab-cell union, adjacent projections at concave corners / overall extent. Internal holes are not exterior re-entrant corners; disconnected floor components require diaphragm/load-path review.'))
    return rows,outlines


@timed_outputs('NBC irregularity centered model response and plan review','output_dir')
def run_model_review(folder,output_dir,states=('SLS','ULS'),review_file=None):
    import openseespy.opensees as ops
    from OpenSees_Complete_Export_V118 import build_complete_model
    from OpenSees_Response_Checks_V132 import irregularity,write_csv
    from OpenSees_Project_Inputs_V123 import import_project_inputs
    folder=Path(folder);out=Path(output_dir);out.mkdir(parents=True,exist_ok=True);source=folder/'OpenSees_Complete_Model_Data_V118.json';data=json.loads(source.read_text(encoding='utf-8-sig'));groups=sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2]);review={}
    if review_file:
        path=Path(review_file)
        if path.suffix.lower()=='.json':review=json.loads(path.read_text(encoding='utf-8-sig'))
        else:
            with path.open(encoding='utf-8-sig',newline='') as f:review['capacity_rows']=list(csv.DictReader(f))
    checks=irregularity(data)['checks'];checks=[r for r in checks if r['check'] not in ('Soft story','Torsion','Extreme torsion','Re-entrant corners','Weak story')];plans,outlines=plan_checks(data);checks.extend(plans);responses=[]
    if any(str(r.get('lateral_strength_kN','')).strip() and r.get('axis','').upper() not in ('X','Y') for r in review.get('capacity_rows',[])):raise ValueError('Each strength row requires explicit axis X or Y')
    for axis in ('X','Y'):
        caps=[r for r in review.get('capacity_rows',[]) if r.get('axis','').upper()==axis and str(r.get('lateral_strength_kN','')).strip()]
        if any(not r.get('evidence') or not math.isfinite(float(r['lateral_strength_kN'])) or float(r['lateral_strength_kN'])<=0 for r in caps):raise ValueError('Each capacity requires finite positive strength and evidence.')
        by_level={int(r['storey_number']):r for r in caps}
        if len(by_level)!=len(caps):raise ValueError('Duplicate strength storey for '+axis)
        for low,high in zip(groups,groups[1:]):
            a=by_level.get(low['storey_number']);b=by_level.get(high['storey_number'])
            ratio=float(a['lateral_strength_kN'])/float(b['lateral_strength_kN']) if a and b else None
            checks.append(dict(clause='5.4.1.1',check='Weak storey '+axis,storey=low['storey_number'],value=ratio,threshold=.8,status='NOT EVALUATED' if ratio is None else 'IRREGULAR' if ratio<.8 else 'PASS',note='Requires reviewed strength at this and the immediately higher storey; omitted levels are not skipped. '+str(a.get('evidence','') if a else 'Missing capacity evidence.')))
    for state in states:
        for axis,dof,perp in [('X',0,1),('Y',1,0)]:
            print('[IRREGULARITY START]',state,axis,'center-of-mass reference forces, no accidental eccentricity',flush=True)
            build_complete_model(folder,mode='elastic',preload=True,limit_state=state);ops.loadConst('-time',0.);baseline={g['master_tag']:list(ops.nodeDisp(g['master_tag'])) for g in groups};supports=[int(n) for n,v in data['supports'].items() if any(v)];ops.reactions();r0=sum(ops.nodeReaction(n,dof+1) for n in supports)
            masses=[];centers=[];heights=[]
            for i,g in enumerate(groups):
                low=groups[i-1]['master_xyz'][2] if i else data['base_z_m'];members=[(data['nodes'][str(n)],float(m)) for n,m in data['nodal_mass'].items() if low+1e-7<data['nodes'][str(n)][2]<=g['master_xyz'][2]+1e-7];mass=sum(m for p,m in members)
                if mass<=0:raise ValueError('Nonpositive effective floor mass at '+str(g['storey_number']))
                masses.append(mass);centers.append([sum(p[j]*m for p,m in members)/mass for j in (0,1)]);heights.append(g['master_xyz'][2]-data['base_z_m'])
            values=import_project_inputs(Path(__file__).parent,folder,state)['values'];period=values.get('workbook_adopted_t'+axis.lower());k=1. if period is None else max(1.,min(2.,1.+(float(period)-.5)/2.));shape=[m*h**k for m,h in zip(masses,heights)];base_force=.01*sum(masses)*9.80665;forces=[base_force*v/sum(shape) for v in shape]
            ops.timeSeries('Linear',880001);ops.pattern('Plain',880001,880001)
            for g,cm,force in zip(groups,centers,forces):
                f=[0.]*6;f[dof]=force;f[5]=-(cm[1]-g['master_xyz'][1])*force if axis=='X' else (cm[0]-g['master_xyz'][0])*force;ops.load(g['master_tag'],*f)
            ops.wipeAnalysis();ops.constraints('Transformation');ops.numberer('RCM');ops.system('UmfPack');ops.test('NormDispIncr',1e-9,40);ops.algorithm('Newton');ops.integrator('LoadControl',.2);ops.analysis('Static')
            for step in range(5):
                if ops.analyze(1)!=0:raise RuntimeError('Centered reference solve failed for '+state+' '+axis)
            ops.reactions();reaction=sum(ops.nodeReaction(n,dof+1) for n in supports)-r0;error=abs(reaction+base_force)/max(base_force,1.);story_rows=[];below_u=0.
            if error>1e-5:raise RuntimeError('Reference lateral equilibrium failed: '+str(error))
            for i,g in enumerate(groups):
                u=[a-b for a,b in zip(ops.nodeDisp(g['master_tag']),baseline[g['master_tag']])];delta=u[dof]-below_u;below_u=u[dof];shear=sum(forces[i:]);K=shear/abs(delta) if abs(delta)>1e-12 else None;story_rows.append(dict(story_number=g['storey_number'],story_stiffness_kN_per_m=K))
                pts=[data['nodes'][str(n)] for n in g['slave_node_tags']];end=[abs(u[dof]+(-1 if axis=='X' else 1)*u[5]*(position-g['master_xyz'][perp])) for position in (min(p[perp] for p in pts),max(p[perp] for p in pts))];ratio=max(end)/min(end) if min(end)>1e-12 else math.inf if max(end)>1e-12 else None
                responses.append(dict(limit_state=state,axis=axis,storey=g['storey_number'],master_displacement_m=u[dof],master_rotation_rad=u[5],interstorey_displacement_m=delta,story_stiffness_kN_per_m=K,reference_story_shear_kN=shear,end_min_m=min(end),end_max_m=max(end),torsion_ratio='UNBOUNDED' if ratio==math.inf else ratio,reference_base_shear_kN=base_force,equilibrium_relative_error=error))
                for clause,name,threshold in [('5.4.2.1','Torsion',1.5),('5.4.2.2','Extreme torsion',2.5)]:checks.append(dict(clause=clause,check=state+' '+axis+' '+name,storey=g['storey_number'],value='UNBOUNDED' if ratio==math.inf else ratio,threshold=threshold,status='IRREGULAR' if ratio is not None and ratio>threshold else 'PASS' if ratio is not None else 'NOT EVALUATED',note='Centered CM reference loading; end displacement ratio. Extreme torsion requires configuration revision.'))
            soft=[r for r in irregularity(data,story_rows)['checks'] if r['check'].startswith('Soft story')]
            for row in soft:row['check']=state+' '+axis+' '+row['check'];row['note']='V/interstorey displacement under 1% W height-distributed perturbation about gravity. Numerical stiffness screen; not a strength capacity.'
            checks.extend(soft);print('[IRREGULARITY COMPLETE]',state,axis,'equilibrium error=',error,flush=True);ops.wipe()
    for item in review.get('plan_and_continuity_checks',[]):
        if not item.get('evidence') or item.get('status') not in ('PASS','IRREGULAR','NOT EVALUATED'):raise ValueError('Reviewed plan check requires evidence and a valid status')
        checks=[r for r in checks if r['check']!=item['check']];checks.append(item)
    result=dict(checks=checks,responses=responses,plan_outlines=outlines,model_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),states=list(states),overall='IRREGULAR' if any(r['status']=='IRREGULAR' for r in checks) else 'INCOMPLETE' if any(r['status']=='NOT EVALUATED' for r in checks) else 'NO TRIGGER FOUND',scope='Available geometry and elastic response evaluated. Weak-storey strength and load-path discontinuity require reviewed capacity/detailing evidence. Numerical response checks do not establish design approval.')
    (out/'NBC105_Irregularity_Review_V134.json').write_text(json.dumps(result,indent=2),encoding='utf-8');write_csv(out/'NBC105_Irregularity_Review_V134.csv',checks);write_csv(out/'NBC105_Irregularity_Response_V134.csv',responses)
    from matplotlib.figure import Figure
    fig=Figure(figsize=(11,6),layout='constrained');axes=fig.subplots(1,2)
    for state in states:
        for axis in ('X','Y'):
            selected=[r for r in responses if r['limit_state']==state and r['axis']==axis];axes[0].plot([r['story_stiffness_kN_per_m'] for r in selected],[r['storey'] for r in selected],label=state+' '+axis);axes[1].plot([float(r['torsion_ratio']) if isinstance(r['torsion_ratio'],(float,int)) else math.nan for r in selected],[r['storey'] for r in selected],label=state+' '+axis)
    axes[0].set(xlabel='Reference secant storey stiffness (kN/m)',ylabel='Storey');axes[1].set(xlabel='Max/min centered floor end displacement',ylabel='Storey');axes[1].axvline(1.5,color='orange',ls='--');axes[1].axvline(2.5,color='red',ls='--')
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    fig.savefig(out/'NBC105_Irregularity_Profiles_V134.png',dpi=160)
    if outlines:plan_figure(result,outlines[0]['storey']).savefig(out/'NBC105_Reentrant_Plan_V134.png',dpi=160)
    return result

def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    import subprocess,threading,sys
    folder=Path(folder);out=folder/'OpenSees_Analysis_Results';win=tk.Toplevel(parent);win.title('NBC 5.4 — calculated geometry, soft-storey and torsion review');win.geometry('1250x850');states=tk.StringVar(value='Both');review=tk.StringVar();status=tk.StringVar(value='Run model review to calculate soft-storey and torsion; exterior geometry supplies re-entrant checks.')
    controls=ttk.Frame(win);controls.pack(fill='x');ttk.Combobox(controls,textvariable=states,values=['Both','SLS','ULS'],state='readonly',width=12).pack(side='left');ttk.Entry(controls,textvariable=review,width=58).pack(side='left')
    def browse():
        path=filedialog.askopenfilename(parent=win,title='Reviewed strengths or continuity evidence',filetypes=[('Reviewed CSV / JSON','*.csv *.json')])
        if path:review.set(path)
    ttk.Button(controls,text='Capacity / review file',command=browse).pack(side='left')
    ttk.Label(win,textvariable=status,wraplength=1180).pack(anchor='w');frame=ttk.Frame(win);frame.pack(fill='both',expand=True);columns=('clause','check','storey','value','threshold','status','note');tree=ttk.Treeview(frame,columns=columns,show='headings');sy=ttk.Scrollbar(frame,command=tree.yview);sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set);frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1);tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
    for key in columns:tree.heading(key,text=key);tree.column(key,width=110 if key in ('clause','storey','value','threshold','status') else 340,stretch=False)
    detail=tk.Text(win,height=4,wrap='word');detail.pack(fill='x')
    from OpenSees_Research_UI_V123 import copyable_log
    log=copyable_log(win,tk.StringVar(),height=5)
    def show(*unused):
        selected=tree.selection()
        if selected:detail.delete('1.0','end');detail.insert('end','\n'.join(str(k)+': '+str(v) for k,v in zip(columns,tree.item(selected[0],'values'))))
    tree.bind('<<TreeviewSelect>>',show)
    def load():
        path=out/'NBC105_Irregularity_Review_V134.json'
        if not path.exists():
            source=folder/'OpenSees_Complete_Model_Data_V118.json'
            if not source.is_file():
                status.set('No assembled model or saved review found in '+str(folder));return
            from OpenSees_Response_Checks_V132 import irregularity
            data=json.loads(source.read_text(encoding='utf-8-sig'));result=irregularity(data);plans,outlines=plan_checks(data)
            result['checks']=[r for r in result['checks'] if r['check']!='Re-entrant corners']+plans
            result.update(plan_outlines=outlines,overall='IRREGULAR' if any(r['status']=='IRREGULAR' for r in result['checks']) else 'INCOMPLETE',scope='Geometry preview only. Modal results do not supply soft-storey/torsion responses. Calculate selected states for centered lateral response; reviewed strengths needed for weak-storey checks.')
        else:
            try:result=json.loads(path.read_text(encoding='utf-8-sig'))
            except Exception as exc:
                status.set('Saved irregularity file cannot be read: '+str(exc));return
        from components.validation.saved_stiffness import merge_saved_stiffness
        result=merge_saved_stiffness(folder,result)
        tree.delete(*tree.get_children())
        for row in result['checks']:tree.insert('','end',values=[f'{row.get(k):.6g}' if isinstance(row.get(k),float) else row.get(k,'') for k in columns])
        pending=[r for r in result['checks'] if r.get('status')=='NOT EVALUATED']
        status.set('Overall: '+result['overall']+' | '+str(len(pending))+' checks pending. Soft-storey/torsion: Calculate selected state(s). Weak storey: provide strength capacities. Discontinuities: provide reviewed load-path evidence. | '+result['scope']);win._irregularity_result=result
    def run():
        button.configure(state='disabled');out.mkdir(parents=True,exist_ok=True);selected=['ULS','SLS'] if states.get()=='Both' else [states.get()];root=Path(__file__).parent
        script='import sys;sys.path.insert(0,'+repr(str(root))+');from OpenSees_Irregularity_Review_V134 import run_model_review;run_model_review('+repr(str(folder.resolve()))+','+repr(str(out.resolve()))+','+repr(selected)+','+repr(review.get().strip() or None)+')'
        def worker():
            try:
                proc=subprocess.Popen([sys.executable,'-u','-c',script],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env={**dict(__import__('os').environ),'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
                with (out/'NBC105_Irregularity_Run_V134.log').open('w',encoding='utf-8') as stream:
                    for line in proc.stdout:stream.write(line);stream.flush();win.after(0,lambda line=line:(log.insert('end',line),log.see('end')))
                rc=proc.wait()
                if not rc:win.after(0,load)
                else:win.after(0,lambda:status.set('Model review failed; inspect the persistent run log.'))
            finally:
                try:win.after(0,lambda:button.configure(state='normal'))
                except (tk.TclError,RuntimeError):pass
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(controls,text='Calculate stiffness + torsion (selected states)',command=run);button.pack(side='left');ttk.Button(controls,text='Load saved results',command=load).pack(side='left');ttk.Button(controls,text='Inspect plan corners',command=lambda:show_plans(win,out,getattr(win,'_irregularity_result',None))).pack(side='left')
    def template():
        path=filedialog.asksaveasfilename(parent=win,title='Strength input template; empty strengths remain unevaluated',defaultextension='.csv')
        if path:
            data=json.loads((folder/'OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'))
            with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f);writer.writerow(['axis','storey_number','lateral_strength_kN','evidence'])
                for axis in ('X','Y'):
                    for g in sorted(data['diaphragms'],key=lambda g:g['storey_number']):writer.writerow([axis,g['storey_number'],'',''])
    ttk.Button(win,text='Create storey strength input template',command=template).pack(anchor='w');load();win._irregularity_tree=tree;return win

def plan_figure(result,storey):
    from matplotlib.figure import Figure
    fig=Figure(figsize=(9,7),layout='constrained');ax=fig.add_subplot()
    for shape in result['plan_outlines']:
        if str(shape['storey'])!=str(storey):continue
        ring=shape['exterior']+[shape['exterior'][0]];ax.plot([p[0] for p in ring],[p[1] for p in ring],color='#285580')
        for corner in shape['corners']:ax.scatter([corner['x']],[corner['y']],color='#c00050');ax.annotate(f"X projection {corner['projection_x_m']:g} m; Y {corner['projection_y_m']:g} m",(corner['x'],corner['y']),xytext=(6,8),textcoords='offset points',bbox=dict(facecolor='white',alpha=.85,edgecolor='none'),fontsize=8)
    ax.set(xlabel='Global X (m)',ylabel='Global Y (m)',title='Storey '+str(storey)+' exterior floor boundary / re-entrant projections');ax.set_aspect('equal');ax.grid(alpha=.2);return fig


def show_plans(parent,folder,result=None):
    import tkinter as tk
    from tkinter import ttk
    from OpenSees_Research_UI_V123 import embed_figures
    if result is None:
        source=Path(folder)/'NBC105_Irregularity_Review_V134.json'
        if not source.exists():
            from tkinter import messagebox
            messagebox.showinfo('Plan review','Select an assembled model or calculate geometry first.',parent=parent);return
        result=json.loads(source.read_text(encoding='utf-8-sig'))
    if not result.get('plan_outlines'):
        from tkinter import messagebox
        messagebox.showinfo('Plan review','No floor outlines available; inspect the geometry review notes.',parent=parent);return
    win=tk.Toplevel(parent);win.title('Source floor boundaries — re-entrant corner inspection');win.geometry('1100x800');levels=sorted({r['storey'] for r in result['plan_outlines']});choice=tk.StringVar(value=str(levels[0]) if levels else '');box=ttk.Combobox(win,textvariable=choice,values=[str(v) for v in levels],state='readonly');box.pack(anchor='w');body=ttk.Frame(win);body.pack(fill='both',expand=True)
    def draw(*unused):
        if choice.get():embed_figures(body,[('Floor plan '+choice.get(),plan_figure(result,choice.get()))])
    box.bind('<<ComboboxSelected>>',draw);draw();return win
