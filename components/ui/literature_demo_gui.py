"""Run an isolated literature teaching model; never changes building readiness."""
from pathlib import Path
import json,csv,sys,subprocess,threading,queue

def launch(parent):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=Path(__file__).resolve().parent;win=tk.Toplevel(parent);win.title('Literature nonlinear direct integration - isolated RC portal');win.geometry('1120x780')
    ttk.Label(win,text='PUBLISHED TEACHING MODEL - separate from your ETABS building',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=10,pady=8)
    ttk.Label(win,text='Concrete01 core/cover + Steel01 bars, forceBeamColumn columns, P-Delta, elastic beam, gravity preload, Newmark 0.5/0.25 and Newton iterations. Motion g is converted once by 9.80665. No building-readiness approval or design PASS is created.',wraplength=1050).pack(anchor='w',padx=10)
    record=tk.StringVar(value=str(root/'benchmarks/elCentro.at2'));out=tk.StringVar(value=str(root/'Literature_Demo_Results'));dt=tk.StringVar(value='.0025');factor=tk.StringVar(value='1.0')
    inputs=ttk.Frame(win,padding=10);inputs.pack(fill='x');inputs.columnconfigure(1,weight=1)
    for i,(label,var,mode) in enumerate([('Recorded AT2 motion',record,'file'),('Demo output folder',out,'dir')]):
        ttk.Label(inputs,text=label).grid(row=i,column=0,sticky='w');ttk.Entry(inputs,textvariable=var).grid(row=i,column=1,sticky='ew')
        def choose(var=var,mode=mode):
            p=filedialog.askdirectory(parent=win) if mode=='dir' else filedialog.askopenfilename(parent=win,filetypes=[('AT2 records','*.at2 *.AT2')])
            if p:var.set(p)
        ttk.Button(inputs,text='Browse',command=choose).grid(row=i,column=2)
    bar=ttk.Frame(win);bar.pack(fill='x',padx=10);ttk.Label(bar,text='Integration dt (s)').pack(side='left');ttk.Entry(bar,textvariable=dt,width=8).pack(side='left');ttk.Label(bar,text='Motion scale (separate from units)').pack(side='left');ttk.Entry(bar,textvariable=factor,width=8).pack(side='left')
    status=tk.StringVar(value='Ready. The bundled El Centro record is not spectrum-matched for your Nepal site.');ttk.Label(win,textvariable=status,wraplength=1050).pack(anchor='w',padx=10,pady=5)
    log=tk.Text(win,height=20,wrap='word');log.pack(fill='both',expand=True,padx=10);messages=queue.Queue();state={'running':False}
    def run():
        if state['running']:return
        try:
            step=float(dt.get());scale=float(factor.get());Path(out.get()).mkdir(parents=True,exist_ok=True)
        except Exception as e:messagebox.showerror('Demo input',str(e),parent=win);return
        state['running']=True;button.configure(state='disabled');status.set('Running separate benchmark process; building model and readiness unchanged.')
        args=[sys.executable,'-u',str(root/'OpenSees_Literature_Demo_V137.py'),'--record',record.get(),'--out',out.get(),'--dt',str(step),'--factor',str(scale)]
        def worker():
            try:
                proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                for line in proc.stdout:messages.put(('line',line))
                messages.put(('done',proc.wait()))
            except Exception as e:messages.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll():
        try:
            while True:
                kind,value=messages.get_nowait()
                if kind=='line':log.insert('end',value);log.see('end')
                else:
                    state['running']=False;button.configure(state='normal');status.set('Demo completed. Inspect response and material loops; no design acceptance implied.' if kind=='done' and value==0 else 'Demo failed: '+str(value))
                    if kind=='done' and value==0:show_results(win,out.get())
        except queue.Empty:pass
        if win.winfo_exists():win.after(150,poll)
    button=ttk.Button(bar,text='Run elastic + nonlinear comparison',command=run);button.pack(side='left',padx=8)
    ttk.Button(bar,text='View saved graphs / animation',command=lambda:show_results(win,out.get())).pack(side='left')
    def cards():
        from OpenSees_Literature_Materials_V137 import export_cards
        export_cards(out.get());messagebox.showinfo('Literature material cards','PEER material cards written to '+out.get()+'. No project maps or approval changed.',parent=win)
    ttk.Button(win,text='Export cited PEER wall material cards',command=cards).pack(anchor='w',padx=10,pady=8)
    win.after(150,poll);return win

def show_results(parent,folder):
    import tkinter as tk
    from tkinter import ttk,messagebox
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
    import numpy as np
    from OpenSees_Literature_Demo_V137 import figure,PROFILE
    folder=Path(folder)
    def rows(name):
        with (folder/name).open(encoding='utf-8-sig',newline='') as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
    try:linear=rows('elastic_initial_tangent_history.csv');nonlinear=rows('nonlinear_fiber_history.csv')
    except Exception as e:messagebox.showerror('Saved demo results',str(e),parent=parent);return
    win=tk.Toplevel(parent);win.title('Actual nonlinear benchmark response - history and yielding');win.geometry('1200x850');tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True)
    first=ttk.Frame(tabs);tabs.add(first,text='Elastic / nonlinear + material loops')
    from OpenSees_Research_UI_V123 import embed_figures
    embed_figures(first,[('Recorded benchmark',figure(linear,nonlinear))])
    playtab=ttk.Frame(tabs);tabs.add(playtab,text='Actual recorded response playback')
    ttk.Label(playtab,text='Two-dimensional portal; actual recorded nodal translations. Straight member chords illustrate nodal movement, not distributed fiber curvature. Scale changes display only.',wraplength=1100).pack(anchor='w')
    bar=ttk.Frame(playtab);bar.pack(fill='x');scale=tk.DoubleVar(value=15.);clock=tk.DoubleVar(value=0.);readout=tk.StringVar();ttk.Label(bar,text='Display scale').pack(side='left');ttk.Entry(bar,textvariable=scale,width=8).pack(side='left')
    fig=Figure(figsize=(10,6),layout='constrained');ax=fig.add_subplot();chart=FigureCanvasTkAgg(fig,master=playtab);toolbar=ttk.Frame(playtab);toolbar.pack(side='bottom',fill='x');NavigationToolbar2Tk(chart,toolbar);chart.get_tk_widget().pack(fill='both',expand=True)
    w,h=PROFILE['span_m'],PROFILE['height_m'];source=np.array([[0,0],[0,h],[w,h],[w,0]]);ax.plot(source[:,0],source[:,1],color='gray',alpha=.6);line,=ax.plot([],[],color='#be2450',lw=2);ax.set(xlim=(-2,w+2),ylim=(-1,h+2),aspect='equal',xlabel='X (m)',ylabel='Y (m)');ax.grid(alpha=.2)
    times=np.array([r['time_s'] for r in nonlinear]);state={'playing':False,'job':None}
    def draw(value):
        t=float(value);r=nonlinear[min(np.searchsorted(times,t),len(times)-1)]
        try:a=float(scale.get())
        except Exception:return
        points=np.array([[0.,0.],[a*r['roof_ux_m'],h+a*r['roof_uy_m']],[w+a*r.get('roof4_ux_m',r['roof_ux_m']),h+a*r.get('roof4_uy_m',r['roof_uy_m'])],[w,0.]])
        line.set_data(points[:,0],points[:,1]);readout.set(f"t={r['time_s']:.3f} s | roof Ux={r['roof_ux_m']*1000:.3f} mm | steel strain={r['steel_strain']:.5g}");chart.draw_idle()
    def stop():state['playing']=False
    def tick():
        if not state['playing']:return
        t=clock.get()+.1
        if t>times[-1]:stop();return
        clock.set(t);draw(t);chart.draw();state['job']=win.after(100,tick)
    def play():
        if not state['playing']:state['playing']=True;tick()
    ttk.Button(bar,text='Play',command=play).pack(side='left');ttk.Button(bar,text='Pause',command=stop).pack(side='left');ttk.Scale(bar,from_=0,to=times[-1],variable=clock,command=draw,length=500).pack(side='left',fill='x',expand=True);ttk.Label(playtab,textvariable=readout).pack(anchor='w')
    win.bind('<Destroy>',lambda e:stop() if e.widget==win else None,add='+');draw(0.);return win
