"""View portable component result folders, including pre-existing OR157 runs."""
from pathlib import Path
import json,csv,os,sys,threading,subprocess
ROOT=Path(__file__).resolve().parents[2]
MODELS=('Concrete01','Concrete02','ConcreteCM','Steel02','SteelMPF','FVD','BRB','SFI_MVLEM_3D')
def latest():
 roots=[ROOT/'Research_Components/results',ROOT/'results',ROOT.parent/'OR157/results',ROOT.parent/'Outrigger_Research_Basis_V157/results']
 candidates=[f.parent for root in roots if root.exists() for f in root.glob('Components_*/Run_Summary.json')]
 return max(candidates,key=lambda p:p.stat().st_mtime) if candidates else ROOT/'results'
def launch(parent,folder=None):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 from matplotlib.figure import Figure
 from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
 win=tk.Toplevel(parent);win.title('Integrated component results - V159');win.geometry('1200x850')
 selected=tk.StringVar(value=str(folder or latest()));bar=ttk.Frame(win);bar.pack(fill='x');ttk.Label(bar,text='Completed run folder').pack(side='left');ttk.Entry(bar,textvariable=selected).pack(side='left',fill='x',expand=True)
 status=tk.StringVar();ttk.Label(win,textvariable=status,wraplength=1150).pack(fill='x');ttk.Label(win,text='Native numerical baselines, not experimental or project validation. SFI tab reports the actual formulation: the supplied baseline uses E_SFI_MVLEM_3D.',wraplength=1150).pack(fill='x')
 book=ttk.Notebook(win);book.pack(fill='both',expand=True);panels={}
 for model in MODELS:
  frame=ttk.Frame(book);book.add(frame,text=model);actions=ttk.Frame(frame);actions.pack(fill='x');tabs=ttk.Notebook(frame);tabs.pack(fill='both',expand=True);plot=ttk.Frame(tabs);details=ttk.Frame(tabs);tabs.add(plot,text='Response graphs');tabs.add(details,text='Parameters / sources / report / log')
  text=tk.Text(details,wrap='none');ys=ttk.Scrollbar(details,command=text.yview);xs=ttk.Scrollbar(details,orient='horizontal',command=text.xview);text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);ys.pack(side='right',fill='y');xs.pack(side='bottom',fill='x');text.pack(fill='both',expand=True)
  fig=Figure(figsize=(11,6),layout='constrained');canvas=FigureCanvasTkAgg(fig,master=plot);canvas.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(canvas,plot)
  panel=dict(fig=fig,canvas=canvas,text=text,path=None,model=model);panels[model]=panel
  def open_file(name,p=panel):
   if p['path'] and (p['path']/name).exists():os.startfile(str(p['path']/name))
   else:messagebox.showinfo('Output unavailable','No '+name+' in the selected result.',parent=win)
  ttk.Button(actions,text='Open Excel',command=lambda p=panel:open_file('Parameter_Study.xlsx',p)).pack(side='left');ttk.Button(actions,text='Open CSV',command=lambda p=panel:open_file('response.csv',p)).pack(side='left');ttk.Button(actions,text='Open PNG',command=lambda p=panel:open_file('response.png',p)).pack(side='left')
  def animate(p=panel):
   if not p['path'] or not(p['path']/'response.csv').exists():return
   from components.validation.visual_workbench import playback
   force=p['model'] in ('BRB','FVD','SFI_MVLEM_3D');playback(win,p['path']/'response.csv','Displacement (m)' if force else 'Strain','Force (kN)' if force else 'Stress (MPa)',p['model'])
  ttk.Button(actions,text='Animate / export GIF',command=animate).pack(side='left')
  ttk.Button(actions,text='Copy report / log',command=lambda p=panel:(win.clipboard_clear(),win.clipboard_append(p['text'].get('1.0','end')))).pack(side='left')
 def load(folder=None):
  if folder:selected.set(str(folder))
  base=Path(selected.get()).expanduser();count=0;failures=0
  for model,p in panels.items():
   # Resolve relative to the selected run, never stale absolute paths in the summary.
   path=base/model;p['path']=path;p['fig'].clear();text=p['text'];text.delete('1.0','end')
   report=path/'report.json';failure=path/'failure.json';data={}
   if report.exists():
    data=json.loads(report.read_text(encoding='utf-8-sig'));text.insert('end',json.dumps(data,indent=2));count+=1
   elif failure.exists():text.insert('end',failure.read_text(encoding='utf-8-sig'));failures+=1
   else:text.insert('end','No completed report for '+model+' in this folder.\n')
   log=base/(model+'.log')
   if not log.exists():log=path/'run.log'
   if log.exists():text.insert('end','\n\nRUN LOG\n'+log.read_text(encoding='utf8',errors='replace'))
   curve=path/'response.csv'
   if curve.exists():
    with curve.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    x=[float(r['x']) for r in rows];y=[float(r['y']) for r in rows];force=model in ('FVD','BRB','SFI_MVLEM_3D');unit='kN' if force else 'MPa';a=p['fig'].add_subplot(121);b=p['fig'].add_subplot(122);a.plot(x,y,label='Native response');times=[float(r.get('time_s',r['step'])) for r in rows];b.plot(times,y,label='Native response')
    if rows and 'measured_y' in rows[0]:a.plot(x,[float(r['measured_y']) for r in rows],label='Measured')
    a.set(xlabel='Displacement (m)' if force else 'Strain',ylabel=unit,title='Recorded response path');b.set(xlabel='Time (s)' if rows and 'time_s' in rows[0] else 'Ordered sample',ylabel=unit,title='Response history');a.grid(alpha=.2);b.grid(alpha=.2);a.legend()
    if model=='SFI_MVLEM_3D':a.ticklabel_format(axis='x',style='sci',scilimits=(0,0))
    actual=data.get('input',{}).get('wall_formulation',model) if model=='SFI_MVLEM_3D' else model;p['fig'].suptitle(actual+' - numerical research baseline')
   else:p['fig'].add_subplot().text(.1,.5,'No response CSV. Inspect report/log or select another run.')
   p['canvas'].draw_idle()
  status.set(str(count)+' completed component reports; '+str(failures)+' failed | '+str(base));return count
 def browse():
  path=filedialog.askdirectory(parent=win,title='Select Components_YYYYMMDD_HHMMSS containing material folders')
  if path:load(path)
 ttk.Button(bar,text='Load existing run...',command=browse).pack(side='left');ttk.Button(bar,text='Refresh',command=load).pack(side='left')
 def run():
  runbutton.configure(state='disabled');status.set('Running eight component baselines in isolated processes; previous results remain visible.')
  def worker():
   try:
    proc=subprocess.run([sys.executable,'-u',str(ROOT/'Research_Components/01_RUN_COMPONENT_BASELINES.py'),'--no-gui'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));(ROOT/'results/GUI_Run.log').write_text(proc.stdout+proc.stderr,encoding='utf8')
    if proc.returncode:raise RuntimeError('Runner failed; inspect results/GUI_Run.log')
    win.after(0,lambda:load(latest()))
   except Exception as exc:win.after(0,lambda msg=str(exc):status.set('FAILED: '+msg))
   finally:win.after(0,lambda:runbutton.configure(state='normal'))
  threading.Thread(target=worker,daemon=True).start()
 runbutton=ttk.Button(bar,text='Run new baselines',command=run);runbutton.pack(side='left');load();win._results_load=load;win._results_panels=panels;return win

def main(folder=None):
 import tkinter as tk
 root=tk.Tk();root.withdraw();win=launch(root,folder);win.protocol('WM_DELETE_WINDOW',root.destroy)
 if os.environ.get('OPENSEES_RESULTS_GUI_SMOKE')=='1':root.after(1000,root.destroy)
 root.mainloop()
