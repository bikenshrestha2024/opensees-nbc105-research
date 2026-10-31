"""Visual workbench launches native tests in a fresh process, never wipes the building domain."""
from pathlib import Path
import csv,json,subprocess,sys,threading,datetime,webbrowser
ROOT=Path(__file__).resolve().parents[2]
STEPS='''1. Choose a material/device and read its source and parameter basis. Default coupons are illustrative; the FVD nonlinear example is documented, not your device.
2. Run native numerical diagnostics in a separate process. CSV histories, graphs, parameter cards and elapsed times are retained in a timestamped folder.
3. Concrete01: compare the virgin compression envelope with the independent piecewise equation; inspect unloading and zero tensile strength. No concrete tensile-cracking validation is implied.
4. Steel02: verify initial modulus, then inspect reversals and transition curvature. The default a1/a3=0 excludes isotropic growth; actual cyclic steel tests are required to calibrate it.
5. FVD: inspect displacement/force loops for the documented nonlinear Maxwell example. The alpha=1 auxiliary case checks Fdot+(K/C)F=K*udot against a closed-form solution. Inspect motion-enforcement error and time-step sensitivity; a refined step need not reduce penalty-dominated error.
6. BRB: inspect force-extension converted from the Steel02 core. This assumes uniform yielding length; it is not whole-brace effective stiffness, compression-overstrength, low-cycle fatigue or casing-buckling validation.
7. Walls: open the dedicated wall workbench for E-SFI and Lu routes. Short native diagnostics are not SD-06 experimental reproduction. SFI-MVLEM-3D (2021) and E-SFI-MVLEM-3D (2023) are distinct formulations.
8. Import independent measured CSV data only with matching units, protocol, axes and specimen provenance. Compare the same ordered loading path; do not sort cyclic data by displacement. Metrics have no automatic code acceptance threshold.
9. Review monotonic/cyclic response, mesh/time-step sensitivity, axial-load dependence, energy, fatigue, boundary/corner compatibility and independent specimen validation before building transfer. Nothing here automatically approves nonlinear readiness.'''

def read(path):
 with Path(path).open(encoding='utf-8-sig') as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]

def reference_metrics(sim,reference):
 if len(sim)!=len(reference):raise ValueError('Reference must use the same ordered sample count; resampling/alignment needs explicit engineering review.')
 import math
 if not all(math.isfinite(r[k]) for rows in (sim,reference) for r in rows for k in ('step','x','y')):raise ValueError('Reference and simulation require finite step,x,y')
 if any(a['step']!=b['step'] for a,b in zip(sim,reference)):raise ValueError('Protocol step identifiers differ; do not compare different cyclic branches.')
 return dict(status='METRICS_ONLY_NOT_VALIDATED',x_max_absolute_difference=max(abs(a['x']-b['x']) for a,b in zip(sim,reference)),y_RMSE=(sum((a['y']-b['y'])**2 for a,b in zip(sim,reference))/len(sim))**.5,note='Identical row/step IDs are not proof of matching physical protocols. Confirm units, loading, specimen and measurement uncertainties. No universal acceptance tolerance.')

def playback(parent,file,xlabel,ylabel,title):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 from matplotlib.figure import Figure
 from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
 rows=read(file);x=[r['x'] for r in rows];y=[r['y'] for r in rows];win=tk.Toplevel(parent);win.title('Recorded response playback - '+title);win.geometry('1000x700');bar=ttk.Frame(win);bar.pack(fill='x');status=tk.StringVar();ttk.Label(win,text='Recorded material/device response path. Protocol step is not earthquake time unless the CSV includes time_s. No building deformation is implied.',wraplength=950).pack(fill='x');fig=Figure(figsize=(10,6),layout='constrained');ax=fig.add_subplot();ax.plot(x,y,color='lightgray',label='Full recorded path');line,=ax.plot([],[],color='#bb2457',lw=2,label='Playback');dot,=ax.plot([],[],'o',color='#bb2457');ax.set(xlabel=xlabel,ylabel=ylabel,title=title);ax.legend();ax.grid(alpha=.2);canvas=FigureCanvasTkAgg(fig,master=win);canvas.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(canvas,win);ttk.Label(win,textvariable=status).pack(fill='x');active={'play':False,'index':0};slider=tk.DoubleVar()
 def show(i):
  i=max(0,min(int(i),len(rows)-1));active['index']=i;line.set_data(x[:i+1],y[:i+1]);dot.set_data([x[i]],[y[i]]);status.set('Sample '+str(i)+' | '+xlabel+'='+format(x[i],'.6g')+' | '+ylabel+'='+format(y[i],'.6g'));canvas.draw_idle()
 def tick():
  if not active['play'] or not win.winfo_exists():return
  i=active['index']+max(1,len(rows)//200)
  if i>=len(rows):active['play']=False;i=len(rows)-1
  slider.set(i);show(i)
  if active['play']:win.after(40,tick)
 def play():
  if active['play']:return
  if active['index']>=len(rows)-1:active['index']=0
  active['play']=True;tick()
 def pause():active['play']=False
 ttk.Button(bar,text='Play recorded path',command=play).pack(side='left');ttk.Button(bar,text='Pause',command=pause).pack(side='left');ttk.Scale(bar,from_=0,to=len(rows)-1,variable=slider,command=lambda v:show(float(v))).pack(side='left',fill='x',expand=True)
 def gif():
  target=filedialog.asksaveasfilename(parent=win,defaultextension='.gif',filetypes=[('GIF','*.gif')])
  if not target:return
  pause()
  try:
   from matplotlib.animation import FuncAnimation,PillowWriter
   indices=sorted(set(round(i*(len(rows)-1)/79) for i in range(80)))
   def update(i):line.set_data(x[:i+1],y[:i+1]);dot.set_data([x[i]],[y[i]]);return line,dot
   anim=FuncAnimation(fig,update,frames=indices,interval=50);anim.save(target,writer=PillowWriter(fps=20),dpi=85);status.set('Recorded-path GIF saved: '+target)
  except Exception as e:messagebox.showerror('GIF export',str(e),parent=win)
 ttk.Button(bar,text='Export GIF',command=gif).pack(side='left');show(0);win.protocol('WM_DELETE_WINDOW',lambda:(pause(),win.destroy()));return win

def launch(parent=None):
 import tkinter as tk
 from tkinter import ttk,messagebox,filedialog
 from components.validation.visual_materials import SOURCES,figure,SCOPE
 win=tk.Toplevel(parent) if parent else tk.Tk();win.title('Visual material/device validation - Concrete01 / Steel02 / FVD / BRB / walls');win.geometry('1250x850');output=tk.StringVar(value=str(ROOT/'Material_Validation_Results_V149'));status=tk.StringVar(value=SCOPE);bar=ttk.Frame(win);bar.pack(fill='x');ttk.Entry(bar,textvariable=output,width=85).pack(side='left',fill='x',expand=True)
 def choose():
  f=filedialog.askdirectory(parent=win)
  if f:output.set(f);load()
 ttk.Button(bar,text='M30-M45 / Fe415-Fe550 cards + sources',command=lambda:__import__('components.validation.grade_cards',fromlist=['launch']).launch(win)).pack(side='left')
 ttk.Button(bar,text='Experimental Steel02 calibration',command=lambda:__import__('components.validation.steel_calibration_gui',fromlist=['launch']).launch(win)).pack(side='left')
 ttk.Button(bar,text='Open saved run folder',command=choose).pack(side='left');ttk.Label(win,textvariable=status,wraplength=1200).pack(fill='x');book=ttk.Notebook(win);book.pack(fill='both',expand=True);frames={}
 for name in ('Concrete01','Steel02','FVD','BRB','Walls','Steps and citations','Run log'):
  frame=ttk.Frame(book);book.add(frame,text=name);frames[name]=frame
 notes=tk.Text(frames['Steps and citations'],wrap='word');sy=ttk.Scrollbar(frames['Steps and citations'],command=notes.yview);notes.configure(yscrollcommand=sy.set);sy.pack(side='right',fill='y');notes.pack(fill='both',expand=True);notes.insert('end',STEPS+'\n\n'+json.dumps(SOURCES,indent=2));notes.configure(state='disabled')
 log=tk.Text(frames['Run log'],wrap='word');ls=ttk.Scrollbar(frames['Run log'],command=log.yview);log.configure(yscrollcommand=ls.set);ls.pack(side='right',fill='y');log.pack(fill='both',expand=True)
 def append(text):log.insert('end',text);log.see('end')
 def load():
  from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
  out=Path(output.get());path=out/'Validation_Report_V149.json'
  if not path.exists():status.set('Run diagnostics, or select a saved folder containing Validation_Report_V149.json.');return
  report=json.loads(path.read_text(encoding='utf8'))
  for name in ('Concrete01','Steel02','FVD','BRB'):
   frame=frames[name]
   for c in frame.winfo_children():c.destroy()
   case=report['cases'].get(name,{})
   if case.get('status')=='FAILED':ttk.Label(frame,text=case.get('error','Failed')).pack();continue
   controls=ttk.Frame(frame);controls.pack(fill='x');file=out/case['files'][-1]
   ttk.Button(controls,text='Animate recorded response / export GIF',command=lambda f=file,c=case,n=name:playback(win,f,c['x_label'],c['y_label'],n)).pack(side='left');ttk.Button(controls,text='Open official source',command=lambda n=name:webbrowser.open(SOURCES[n]['documentation'])).pack(side='left')
   def reference(f=file,c=case,n=name):
    csvfile=filedialog.askopenfilename(parent=win,title='Measured reference: step,x,y in matching units',filetypes=[('CSV','*.csv')])
    if not csvfile:return
    from tkinter.simpledialog import askstring
    citation=askstring('Reference provenance','Enter specimen ID, citation/data source and units:',parent=win)
    if not citation:return
    try:
     result=reference_metrics(read(f),read(csvfile));result.update(citation=citation,reference_file=csvfile,simulation_file=str(f));(out/(n+'_Measured_Comparison.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
     from matplotlib.figure import Figure
     from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
     sim=read(f);ref=read(csvfile);fig=Figure(figsize=(9,6),layout='constrained');ax=fig.add_subplot();ax.plot([r['x'] for r in sim],[r['y'] for r in sim],label='Native simulation');ax.plot([r['x'] for r in ref],[r['y'] for r in ref],ls='--',label='Supplied measurement');ax.set(xlabel=c['x_label'],ylabel=c['y_label'],title=n+' | protocol/provenance review required');ax.legend();ax.grid(alpha=.2);fig.savefig(out/(n+'_Measured_Comparison.png'),dpi=140);panel=tk.Toplevel(win);panel.title('Measured reference overlay - no automatic acceptance');canvas=FigureCanvasTkAgg(fig,master=panel);canvas.get_tk_widget().pack(fill='both',expand=True);canvas.draw();messagebox.showinfo('Reference metrics',json.dumps(result,indent=2),parent=win)
    except Exception as e:messagebox.showerror('Reference alignment',str(e),parent=win)
   ttk.Button(controls,text='Compare independent measured CSV',command=reference).pack(side='left');ttk.Label(frame,text=json.dumps(case['parameters'])+' | '+json.dumps(case['checks']),wraplength=1150).pack(fill='x');fig=figure(out,name,case);canvas=FigureCanvasTkAgg(fig,master=frame);canvas.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(canvas,frame);canvas.draw()
  wallreport=report.get('original_SFI_2021',{})
  append('Original SFI patch status: '+json.dumps(wallreport)+'\n')
  status.set('Saved run: '+str(out)+' | elapsed '+str(report.get('elapsed_s'))+' s | '+SCOPE)
 wallframe=frames['Walls'];ttk.Label(wallframe,text='SFI-MVLEM-3D (2021) / E-SFI-MVLEM-3D (2023) and Lu layered-shell route. E-SFI and original SFI patch attempts are reported separately; original SFI may fail convergence and must not be labelled validated. Short diagnostics and full experimental reproduction have different status.',wraplength=1100).pack(fill='x',padx=10,pady=12)
 ttk.Button(wallframe,text='Open wall validation workbench / graphs / specimen sources',command=lambda:__import__('OpenSees_Wall_Validation_V147').launch(win)).pack(anchor='w',padx=10)
 def wall_plot():
  f=Path(output.get())/'Walls/wall_diagnostics.png'
  if not f.exists():messagebox.showinfo('Wall diagnostics','Run all native diagnostics first.',parent=win);return
  from PIL import Image,ImageTk
  panel=tk.Toplevel(win);panel.title('Wall diagnostics - short numerical runs, not validation PASS');im=Image.open(f);im.thumbnail((1150,700));photo=ImageTk.PhotoImage(im);label=ttk.Label(panel,image=photo);label.image=photo;label.pack()
 ttk.Button(wallframe,text='Show latest E-SFI / Lu diagnostic graph',command=wall_plot).pack(anchor='w',padx=10,pady=8)
 def wall_play():
  out=Path(output.get())/'Walls';source=out/'esfi_numerical_history.csv'
  if not source.exists():messagebox.showinfo('Wall diagnostics','Run native wall diagnostics first.',parent=win);return
  with source.open(encoding='utf-8-sig') as f:rr=list(csv.DictReader(f))
  from components.validation.visual_materials import write
  path=out/'esfi_playback.csv';write(path,[dict(step=i,x=float(r['displacement_m']),y=float(r['base_shear_kN'])) for i,r in enumerate(rr)]);playback(win,path,'Patch displacement (m)','Base shear (kN)','E-SFI short response - not wall deformation animation')
 ttk.Button(wallframe,text='Play recorded E-SFI response path',command=wall_play).pack(anchor='w',padx=10)
 def start():
  stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out=ROOT/('Material_Validation_Results_V149_'+stamp);output.set(str(out));out.mkdir(parents=True);button.configure(state='disabled');book.select(frames['Run log'])
  def worker():
   try:
    proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'components/validation/visual_materials.py'),'--output',str(out),'--walls'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',cwd=ROOT)
    with (out/'Native_Run.log').open('w',encoding='utf8') as stream:
     for line in proc.stdout:stream.write(line);stream.flush();win.after(0,lambda line=line:append(line))
    rc=proc.wait();win.after(0,load);win.after(0,lambda:status.set('Native process exit '+str(rc)+'; inspect per-case status. '+SCOPE))
   except Exception as e:win.after(0,lambda text=str(e):status.set(text))
   finally:win.after(0,lambda:button.configure(state='normal'))
  threading.Thread(target=worker,daemon=True).start()
 button=ttk.Button(bar,text='Run all native diagnostics',command=start);button.pack(side='left');ttk.Button(bar,text='Refresh graphs',command=load).pack(side='left');ttk.Button(frames['Run log'],text='Copy log',command=lambda:(win.clipboard_clear(),win.clipboard_append(log.get('1.0','end-1c')))).pack(anchor='w');load();return win
