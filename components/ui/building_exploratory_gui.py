"""Explicit literature-informed route on the selected building."""
from pathlib import Path
import json,sys,subprocess,threading,queue,datetime,importlib.util

def resolve_runner():
    """Resolve the installed facade, whether this code is imported or exec-loaded."""
    spec=importlib.util.find_spec('OpenSees_Building_Exploratory_V138')
    if spec is None or not spec.origin:
        raise FileNotFoundError('Cannot locate OpenSees_Building_Exploratory_V138.py in the active package. Extract the complete package and launch its main script.')
    runner=Path(spec.origin).resolve()
    if not runner.is_file(): raise FileNotFoundError('Nonlinear runner is missing: '+str(runner))
    return runner

def launch(parent,model_folder,output_folder=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    from OpenSees_Input_Records_V130 import LTH_DEFAULT_PEER_PAIRS
    win=tk.Toplevel(parent);win.title('Building nonlinear research history - frames / FSAM walls');win.geometry('1150x800')
    ttk.Label(win,text='CURRENT BUILDING | SELECT LITERATURE MATERIAL BASIS AND WALL FORMULATION',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=8,pady=6)
    ttk.Label(win,text='Uses the selected building geometry, loads and mass in an isolated copy. Full-wall route assigns nonlinear E-SFI-MVLEM-3D and unconfined FSAM web regions, with per-property ratios from the available wall layout. Published constitutive references and M30/Fe500 sensitivity are distinct. Frame bar schedules remain template assumptions. No automatic calibration or design approval.',wraplength=1100).pack(anchor='w',padx=8)
    form=ttk.Frame(win,padding=8);form.pack(fill='x');form.columnconfigure(1,weight=1)
    folder=tk.StringVar(value=str(model_folder));out=tk.StringVar(value=str(output_folder or Path(model_folder)/'OpenSees_Analysis_Results'));x=tk.StringVar();y=tk.StringVar();pair=tk.StringVar(value='RSN1120_KOBE_TAK000');dt=tk.StringVar(value='.005');duration=tk.StringVar(value='0');orientation=tk.StringVar(value='XY + YX');ls=tk.StringVar(value='Both');scale=tk.StringVar(value='1.0')
    entries=[('Assembled export folder',folder,'dir'),('Output base folder',out,'dir'),('X component record',x,'file'),('Y component record',y,'file')]
    for i,(label,var,mode) in enumerate(entries):
        ttk.Label(form,text=label).grid(row=i,column=0,sticky='w');ttk.Entry(form,textvariable=var).grid(row=i,column=1,sticky='ew')
        def choose(v=var,m=mode):
            path=filedialog.askdirectory(parent=win) if m=='dir' else filedialog.askopenfilename(parent=win)
            if path:v.set(path)
        ttk.Button(form,text='Browse',command=choose).grid(row=i,column=2)
    catalogue={r['pair_id']:r for r in LTH_DEFAULT_PEER_PAIRS};bar=ttk.Frame(win);bar.pack(fill='x',padx=8)
    ttk.Label(bar,text='Earthquake').pack(side='left');box=ttk.Combobox(bar,textvariable=pair,values=list(catalogue),state='readonly',width=33);box.pack(side='left')
    def select(*_):
        r=catalogue[pair.get()];x.set(r['x_path']);y.set(r['y_path'])
    box.bind('<<ComboboxSelected>>',select);select()
    for label,var,values,width in [('State',ls,['Both','ULS','SLS'],6),('Orientation',orientation,['XY + YX','XY','YX'],10)]:
        ttk.Label(bar,text=label).pack(side='left');ttk.Combobox(bar,textvariable=var,values=values,state='readonly',width=width).pack(side='left')
    settings=ttk.LabelFrame(win,text='Analysis settings');settings.pack(fill='x',padx=8,pady=(4,0))
    for label,var in [('dt (s)',dt),('Trial duration (s); 0=full record',duration),('Motion scale (units handled separately)',scale)]:ttk.Label(settings,text=label).pack(side='left');ttk.Entry(settings,textvariable=var,width=8).pack(side='left')
    transient_system=tk.StringVar(value='UmfPack')
    gravity_system=tk.StringVar(value='UmfPack')
    ttk.Label(settings,text='Gravity solver').pack(side='left',padx=(10,2))
    ttk.Combobox(settings,textvariable=gravity_system,values=['UmfPack','SparseGeneral'],state='readonly',width=14).pack(side='left')
    ttk.Label(settings,text='SparseGeneral gravity is diagnostic-only; a full-wall test exited natively.',foreground='#8a3412').pack(side='left',padx=4)
    ttk.Label(settings,text='Transient solver').pack(side='left',padx=(10,2))
    ttk.Combobox(settings,textvariable=transient_system,values=['UmfPack','SparseGeneral'],state='readonly',width=14).pack(side='left')
    tracked=tk.StringVar(value='100001');ttk.Label(settings,text='Tracked frame solver tag').pack(side='left');ttk.Entry(settings,textvariable=tracked,width=9).pack(side='left')
    tracked_members=tk.StringVar(value='')
    ttk.Label(settings,text='Additional brace/device tags (comma-separated)').pack(side='left',padx=(8,2))
    ttk.Entry(settings,textvariable=tracked_members,width=22).pack(side='left')
    full=tk.BooleanVar(value=True);basis=tk.StringVar(value='PUBLISHED_REFERENCE')
    steel_transition=tk.StringVar(value='OPENSEES_DOCUMENTED')
    brace_fy=tk.StringVar(value='345');brace_b=tk.StringVar(value='.01')
    materialbar=ttk.LabelFrame(win,text='Material basis and sensitivity');materialbar.pack(fill='x',padx=8,pady=(4,0))
    ttk.Checkbutton(materialbar,text='Nonlinear FSAM walls (unconfined core web)',variable=full).pack(side='left')
    ttk.Combobox(materialbar,textvariable=basis,values=['PUBLISHED_REFERENCE','M30_FE500_SENSITIVITY'],state='readonly',width=28).pack(side='left')
    ttk.Label(materialbar,text='SteelMPF transition').pack(side='left',padx=(8,2))
    ttk.Combobox(materialbar,textvariable=steel_transition,values=['OPENSEES_DOCUMENTED','PEER_APPENDIX_EXACT'],state='readonly',width=23).pack(side='left')
    ttk.Label(materialbar,text='Brace Fy (MPa)').pack(side='left',padx=(8,2))
    ttk.Entry(materialbar,textvariable=brace_fy,width=8).pack(side='left')
    ttk.Label(materialbar,text='Steel01 b').pack(side='left',padx=(6,2))
    ttk.Entry(materialbar,textvariable=brace_b,width=6).pack(side='left')
    sensitivity=ttk.Frame(win);sensitivity.pack(fill='x',padx=8,pady=(2,0))
    sensitivity_parameter=tk.StringVar(value='brace.fy_mpa')
    sensitivity_values=tk.StringVar(value='310.5, 345, 379.5')
    from components.nonlinear_time_history.research_building_materials import MATERIAL_OVERRIDE_BOUNDS
    ttk.Label(sensitivity,text='One-factor parameter').pack(side='left')
    ttk.Combobox(sensitivity,textvariable=sensitivity_parameter,values=list(MATERIAL_OVERRIDE_BOUNDS),state='readonly',width=23).pack(side='left')
    ttk.Label(sensitivity,text='Candidate values (MPa, ratio, strain, etc.; use parameter units)').pack(side='left',padx=(8,2))
    ttk.Entry(sensitivity,textvariable=sensitivity_values,width=36).pack(side='left')
    ttk.Label(win,text='Device history uses localForce component 1 and projected axial extension; check the selected element axis in the exported element map. Results are exploratory, not material calibration or design approval.',wraplength=1100,foreground='#444').pack(anchor='w',padx=8,pady=3)
    def show_parameters():
        target=state.get('last')
        found=list(target.rglob('Research_Material_Assignment_V161.json')) if target else []
        if found:
            from tkinter.scrolledtext import ScrolledText
            details=tk.Toplevel(win);details.title('Actual assigned building parameters / citations')
            details.geometry('1100x750');text=ScrolledText(details,wrap='word');text.pack(fill='both',expand=True)
            text.insert('end',found[0].read_text(encoding='utf8'))
        else:
            from components.validation.material_catalog import launch as show
            show(win,folder.get())
    ttk.Button(materialbar,text='Inspect source parameter cards',command=show_parameters).pack(side='left')
    def make_material_draft():
        try:
            from components.nonlinear_time_history.material_draft import prepare
            dest=Path(out.get())/('Wall_Material_Draft_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            card=prepare(folder.get(),dest,basis.get(),steel_transition.get())
            messagebox.showinfo('Research draft created',str(dest)+'\n\nWall mappings: '+str(card['fsam_tags'])+'\nParameters remain unapproved. Use this isolated copy for research; the reviewed analysis remains gated.',parent=win)
        except Exception as exc:
            messagebox.showerror('Cannot prepare material draft',str(exc),parent=win)
    ttk.Button(materialbar,text='Prepare wall material + FSAM draft',command=make_material_draft).pack(side='left')
    status=tk.StringVar(value='Short trial recommended to inspect numerical behavior. No readiness approval is auto-created.');ttk.Label(win,textvariable=status,wraplength=1100).pack(anchor='w',padx=8,pady=5)
    from tkinter.scrolledtext import ScrolledText
    log=ScrolledText(win,height=15,wrap='word');log.pack(fill='both',expand=True,padx=8);messages=queue.Queue();state={'running':False,'last':None,'proc':None}
    def start(run_sensitivity=False):
        if state['running']:return
        try:
            runner=resolve_runner()
            source=Path(folder.get()).resolve()
            if not (source/'OpenSees_Complete_Model_Data_V118.json').is_file():raise ValueError('Select an assembled export folder')
            dest=Path(out.get())/('EXPLORATORY_FRAME_NL_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));dest.mkdir(parents=True,exist_ok=False)
            extra_tags=[int(value.strip()) for value in tracked_members.get().split(',') if value.strip()]
            config=dict(model_folder=str(source),output_dir=str(dest),x_path=x.get(),y_path=y.get(),dt_s=float(dt.get()),duration_s=float(duration.get()) or None,scale=float(scale.get()),orientations=['XY','YX'] if orientation.get()=='XY + YX' else [orientation.get()],limit_state=ls.get(),tracked_frame_tag=int(tracked.get()),tracked_element_tags=extra_tags,nonlinear_walls=full.get(),material_basis=basis.get(),steelmpf_transition=steel_transition.get(),gravity_system=gravity_system.get(),transient_system=transient_system.get(),material_overrides={'brace.fy_mpa':float(brace_fy.get()),'brace.b':float(brace_b.get())})
            if run_sensitivity:
                values=[float(value.strip()) for value in sensitivity_values.get().split(',') if value.strip()]
                if len(values)<2:raise ValueError('Enter at least two comma-separated sensitivity candidate values.')
                config['sensitivity_parameter']=sensitivity_parameter.get()
                config['sensitivity_values']=values
            configpath=dest/'Requested_Config.json';configpath.write_text(json.dumps(config,indent=2),encoding='utf-8');state.update(running=True,last=dest);button.configure(state='disabled');status.set('Running exploratory model in separate process. Outputs: '+str(dest))
            if run_sensitivity:
                sensitivity_button.configure(state='disabled')
                combinations=len(values)*len(config['orientations'])*(2 if ls.get()=='Both' else 1)
                status.set(f'Running {len(values)} material candidates serially ({combinations} state/orientation cases); each uses the selected duration. Outputs: {dest}')
        except Exception as e:messagebox.showerror('Exploratory inputs',str(e),parent=win);return
        def worker():
            started_at=datetime.datetime.now().astimezone()
            log_path=dest/'Run.log'
            expected=dest/'Material_Sensitivity_Summary.json' if config.get('sensitivity_parameter') else dest/('Research_Batch_Summary_V161.json' if config['limit_state']=='Both' else 'Exploratory_Summary.json')
            try:
                messages.put(('line','[RUNNER] '+str(runner)+'\n'))
                proc=subprocess.Popen([sys.executable,'-u',str(runner),'--config',str(configpath)],cwd=str(runner.parent),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                state['proc']=proc
                with log_path.open('w',encoding='utf-8') as stream:
                    stream.write('[RUN START] '+started_at.isoformat()+'\n')
                    stream.write('[CONFIG] '+str(configpath)+'\n')
                    stream.flush()
                    for line in proc.stdout:stream.write(line);stream.flush();messages.put(('line',line))
                code=proc.wait()
                completed_at=datetime.datetime.now().astimezone()
                summary_exists=expected.is_file()
                status='COMPLETED' if code==0 and summary_exists else 'PROCESS_EXIT_NONZERO' if code!=0 else 'SUMMARY_MISSING'
                execution_report=dict(status=status,exit_code=code,started_at=started_at.isoformat(),finished_at=completed_at.isoformat(),elapsed_seconds=(completed_at-started_at).total_seconds(),config_path=str(configpath),run_log=str(log_path),expected_summary=str(expected),summary_exists=summary_exists)
                (dest/'Process_Exit.json').write_text(json.dumps(execution_report,indent=2),encoding='utf-8')
                if code==0 and not expected.is_file():
                    messages.put(('error','Native process exited without a completion summary; inspect log and last committed state.'))
                else:messages.put(('done',code))
            except Exception as e:
                completed_at=datetime.datetime.now().astimezone()
                execution_report=dict(status='RUNNER_START_OR_LOGGING_FAILURE',error_type=type(e).__name__,error=str(e),started_at=started_at.isoformat(),finished_at=completed_at.isoformat(),elapsed_seconds=(completed_at-started_at).total_seconds(),config_path=str(configpath),run_log=str(log_path))
                (dest/'Process_Exit.json').write_text(json.dumps(execution_report,indent=2),encoding='utf-8')
                messages.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def stop():
        proc=state.get('proc')
        if proc is not None and proc.poll() is None:proc.terminate();status.set('Stopped by user; partial outputs remain incomplete.')
    def inspect():
        target=state['last'] or Path(out.get())
        from OpenSees_History_Inspection_V133 import launch
        launch(win,target)
    def response_plots():
        from OpenSees_Building_Response_V144 import launch as show
        show(win,state['last'] or Path(out.get()))
    actions=ttk.Frame(win);actions.pack(fill='x',padx=8,pady=4);button=ttk.Button(actions,text='Run selected building exploratory case',command=start);button.pack(side='left')
    sensitivity_button=ttk.Button(actions,text='Run material sensitivity sweep',command=lambda:messagebox.askyesno('Run sensitivity cases',f'Run {len([v for v in sensitivity_values.get().split(",") if v.strip()])} candidates serially for the selected state/orientations and duration? A duration of 0 means the full record; a full sweep may take a long time.',parent=win) and start(True));sensitivity_button.pack(side='left',padx=(6,0))
    ttk.Button(actions,text='Inspect saved histories / playback',command=inspect).pack(side='left');ttk.Button(actions,text='Open latest output folder',command=lambda:__import__('os').startfile(str(state['last'] or out.get()))).pack(side='left')
    secondary=ttk.Frame(win);secondary.pack(fill='x',padx=8,pady=4)
    ttk.Button(secondary,text='Stop owned process',command=stop).pack(side='left')
    ttk.Button(secondary,text='Building roof / force / section response plots',command=response_plots).pack(side='left')
    def recover():
        from tkinter import filedialog
        target=filedialog.askdirectory(parent=win,title='Select run folder with saved history and reporting failure')
        if not target:return
        dest=filedialog.askdirectory(parent=win,title='Select separate recovery output folder')
        if not dest:return
        try:
            from OpenSees_Building_Exploratory_V138 import recover_saved_report
            result=recover_saved_report(target,dest)
            messagebox.showinfo('Saved history report recovered',str(len(result['cases']))+' orientation reports recovered. Original data unchanged.',parent=win)
        except Exception as exc:messagebox.showerror('Report recovery',str(exc),parent=win)
    ttk.Button(secondary,text='Recover report from saved trial',command=recover).pack(side='left')
    def poll():
        try:
            while True:
                kind,value=messages.get_nowait()
                if kind=='line':log.insert('end',value);log.see('end')
                elif kind=='error':state['running']=False;button.configure(state='normal');sensitivity_button.configure(state='normal');status.set('Runner/logging failure: '+str(value)+'; inspect Process_Exit.json.')
                else:state['running']=False;button.configure(state='normal');sensitivity_button.configure(state='normal');status.set('Exploratory trial finished; inspect assumptions and truncated/full-record status.' if kind=='done' and value==0 else 'Trial incomplete: '+str(value)+'; inspect Run.log and Process_Exit.json. No completion claimed.')
        except queue.Empty:pass
        if win.winfo_exists():win.after(200,poll)
    win.after(200,poll);return win
