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
    settings=ttk.Frame(win);settings.pack(fill='x',padx=8)
    for label,var in [('dt (s)',dt),('Trial duration (s); 0=full record',duration),('Motion scale (units handled separately)',scale)]:ttk.Label(settings,text=label).pack(side='left');ttk.Entry(settings,textvariable=var,width=8).pack(side='left')
    tracked=tk.StringVar(value='100001');ttk.Label(settings,text='Tracked frame solver tag').pack(side='left');ttk.Entry(settings,textvariable=tracked,width=9).pack(side='left')
    full=tk.BooleanVar(value=True);basis=tk.StringVar(value='PUBLISHED_REFERENCE')
    materialbar=ttk.Frame(win);materialbar.pack(fill='x',padx=8)
    ttk.Checkbutton(materialbar,text='Nonlinear FSAM walls (unconfined core web)',variable=full).pack(side='left')
    ttk.Combobox(materialbar,textvariable=basis,values=['PUBLISHED_REFERENCE','M30_FE500_SENSITIVITY'],state='readonly',width=28).pack(side='left')
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
            card=prepare(folder.get(),dest,basis.get())
            messagebox.showinfo('Research draft created',str(dest)+'\n\nWall mappings: '+str(card['fsam_tags'])+'\nParameters remain unapproved. Use this isolated copy for research; the reviewed analysis remains gated.',parent=win)
        except Exception as exc:
            messagebox.showerror('Cannot prepare material draft',str(exc),parent=win)
    ttk.Button(materialbar,text='Prepare wall material + FSAM draft',command=make_material_draft).pack(side='left')
    status=tk.StringVar(value='Short trial recommended to inspect numerical behavior. No readiness approval is auto-created.');ttk.Label(win,textvariable=status,wraplength=1100).pack(anchor='w',padx=8,pady=5)
    from tkinter.scrolledtext import ScrolledText
    log=ScrolledText(win,height=15,wrap='word');log.pack(fill='both',expand=True,padx=8);messages=queue.Queue();state={'running':False,'last':None,'proc':None}
    def start():
        if state['running']:return
        try:
            runner=resolve_runner()
            source=Path(folder.get()).resolve()
            if not (source/'OpenSees_Complete_Model_Data_V118.json').is_file():raise ValueError('Select an assembled export folder')
            dest=Path(out.get())/('EXPLORATORY_FRAME_NL_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));dest.mkdir(parents=True,exist_ok=False)
            config=dict(model_folder=str(source),output_dir=str(dest),x_path=x.get(),y_path=y.get(),dt_s=float(dt.get()),duration_s=float(duration.get()) or None,scale=float(scale.get()),orientations=['XY','YX'] if orientation.get()=='XY + YX' else [orientation.get()],limit_state=ls.get(),tracked_frame_tag=int(tracked.get()),nonlinear_walls=full.get(),material_basis=basis.get())
            configpath=dest/'Requested_Config.json';configpath.write_text(json.dumps(config,indent=2),encoding='utf-8');state.update(running=True,last=dest);button.configure(state='disabled');status.set('Running exploratory model in separate process. Outputs: '+str(dest))
        except Exception as e:messagebox.showerror('Exploratory inputs',str(e),parent=win);return
        def worker():
            try:
                messages.put(('line','[RUNNER] '+str(runner)+'\n'))
                proc=subprocess.Popen([sys.executable,'-u',str(runner),'--config',str(configpath)],cwd=str(runner.parent),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                state['proc']=proc
                with (dest/'Run.log').open('w',encoding='utf-8') as stream:
                    for line in proc.stdout:stream.write(line);stream.flush();messages.put(('line',line))
                code=proc.wait()
                expected=dest/('Research_Batch_Summary_V161.json' if config['limit_state']=='Both' else 'Exploratory_Summary.json')
                if code==0 and not expected.is_file():
                    messages.put(('error','Native process exited without a completion summary; inspect log and last committed state.'))
                else:messages.put(('done',code))
            except Exception as e:messages.put(('error',str(e)))
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
    actions=ttk.Frame(win);actions.pack(fill='x',padx=8,pady=4);button=ttk.Button(actions,text='Run selected building exploratory case',command=start);button.pack(side='left');ttk.Button(actions,text='Inspect saved histories / playback',command=inspect).pack(side='left');ttk.Button(actions,text='Open latest output folder',command=lambda:__import__('os').startfile(str(state['last'] or out.get()))).pack(side='left')
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
                else:state['running']=False;button.configure(state='normal');status.set('Exploratory trial finished; inspect assumptions and truncated/full-record status.' if kind=='done' and value==0 else 'Trial incomplete: '+str(value)+'; inspect Run.log. No completion claimed.')
        except queue.Empty:pass
        if win.winfo_exists():win.after(200,poll)
    win.after(200,poll);return win
