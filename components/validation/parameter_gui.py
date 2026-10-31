"""Separate material/device setup panels; native tests always use child processes."""
from pathlib import Path
import json,sys,os,subprocess,threading,datetime
ROOT=Path(__file__).resolve().parents[2]
def launch(parent,folder=None,initial_card=None):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 from components.validation.parameter_studies import SCHEMAS,card
 win=tk.Toplevel(parent);win.title('Individual material and component setup / validation / tuning - V159');win.geometry('1200x850')
 out=tk.StringVar(value=str(Path(folder or ROOT)/'Material_Parameter_Studies'));bar=ttk.Frame(win);bar.pack(fill='x');ttk.Label(bar,text='Output').pack(side='left');ttk.Entry(bar,textvariable=out).pack(side='left',fill='x',expand=True)
 def choose_out():
  path=filedialog.askdirectory(parent=win)
  if path:out.set(path)
 ttk.Button(bar,text='Browse',command=choose_out).pack(side='left')
 ttk.Label(win,text='Each tab has its own card and results. Starting values are illustrative, not grade-specific experimental calibrations. Stress uses MPa for coupons; component force uses kN and length m. Fit requires ordered measured x,y CSV and specimen/citation. Wall and FVD use manual tuning; no automatic project assignment.',wraplength=1150).pack(fill='x')
 book=ttk.Notebook(win);book.pack(fill='both',expand=True);panels={}
 for model in SCHEMAS:
  frame=ttk.Frame(book);book.add(frame,text=model)
  buttons=ttk.Frame(frame);buttons.pack(fill='x');state=tk.StringVar(value='Ready - no run performed');ttk.Label(frame,textvariable=state,wraplength=1150).pack(fill='x')
  panes=ttk.Panedwindow(frame,orient='horizontal');panes.pack(fill='both',expand=True);left=ttk.Frame(panes);right=ttk.Frame(panes);panes.add(left,weight=2);panes.add(right,weight=3)
  edit=tk.Text(left,wrap='none',width=48);ys=ttk.Scrollbar(left,orient='vertical',command=edit.yview);xs=ttk.Scrollbar(left,orient='horizontal',command=edit.xview);edit.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);ys.pack(side='right',fill='y');xs.pack(side='bottom',fill='x');edit.pack(fill='both',expand=True);edit.insert('1.0',json.dumps(card(model),indent=2))
  tabs=ttk.Notebook(right);tabs.pack(fill='both',expand=True);graph=ttk.Frame(tabs);logs=ttk.Frame(tabs);tabs.add(graph,text='Graph');tabs.add(logs,text='Log / report')
  log=tk.Text(logs,wrap='none');ys=ttk.Scrollbar(logs,command=log.yview);xs=ttk.Scrollbar(logs,orient='horizontal',command=log.xview);log.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);ys.pack(side='right',fill='y');xs.pack(side='bottom',fill='x');log.pack(fill='both',expand=True)
  panel=dict(edit=edit,state=state,graph=graph,log=log,tabs=tabs,latest=None,busy=False,model=model);panels[model]=panel
  def set_card(data,p=panel):p['edit'].delete('1.0','end');p['edit'].insert('1.0',json.dumps(data,indent=2))
  def load_card(p=panel):
   path=filedialog.askopenfilename(parent=win,filetypes=[('JSON','*.json')])
   if path:
    try:
     data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
     if data['model']!=p['model']:raise ValueError('Card model does not match this tab')
     p['edit'].delete('1.0','end');p['edit'].insert('1.0',json.dumps(data,indent=2))
    except Exception as exc:messagebox.showerror('Card',str(exc),parent=win)
  def save_card(p=panel):
   try:
    data=json.loads(p['edit'].get('1.0','end'));path=filedialog.asksaveasfilename(parent=win,defaultextension='.json')
    if path:Path(path).write_text(json.dumps(data,indent=2),encoding='utf8')
   except Exception as exc:messagebox.showerror('Card',str(exc),parent=win)
  def data_file(key,p=panel):
   path=filedialog.askopenfilename(parent=win,title='Ordered CSV: x,y; x is strain or component displacement, y is MPa or kN',filetypes=[('CSV','*.csv')])
   if path:
    try:
     data=json.loads(p['edit'].get('1.0','end'));data[key]=path;p['edit'].delete('1.0','end');p['edit'].insert('1.0',json.dumps(data,indent=2))
    except Exception as exc:messagebox.showerror('Card',str(exc),parent=win)
  def display(path,p=panel):
   from PIL import Image,ImageTk
   for child in p['graph'].winfo_children():child.destroy()
   im=Image.open(path/'response.png');im.thumbnail((720,600));photo=ImageTk.PhotoImage(im);label=ttk.Label(p['graph'],image=photo);label.image=photo;label.pack(fill='both',expand=True)
   p['latest']=path;p['tabs'].select(p['graph']);p['state'].set('Completed: '+str(path)+' - see report for comparison scope')
  def run(p=panel):
   if p['busy']:return
   try:
    from components.validation.parameter_studies import check
    data=json.loads(p['edit'].get('1.0','end'))
    if data['model']!=p['model']:raise ValueError('Card model does not match tab')
    check(data)
    path=Path(out.get()).resolve()/p['model']/datetime.datetime.now().strftime('Run_%Y%m%d_%H%M%S_%f');path.mkdir(parents=True);cfg=path/'input.json';cfg.write_text(json.dumps(data,indent=2),encoding='utf8')
   except Exception as exc:messagebox.showerror('Parameter input',str(exc),parent=win);return
   p['busy']=True;p['state'].set('RUNNING isolated native analysis / tuning');p['tabs'].select(p['log'].master)
   def worker():
    try:
     proc=subprocess.Popen([sys.executable,'-u','-m','components.validation.parameter_studies',str(cfg),str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
     with (path/'run.log').open('w',encoding='utf8') as stream:
      for line in proc.stdout:stream.write(line);stream.flush();win.after(0,lambda s=line:(p['log'].insert('end',s),p['log'].see('end')))
     code=proc.wait()
     if code:raise RuntimeError('Native run failed; inspect '+str(path/'run.log'))
     win.after(0,lambda:display(path,p))
    except Exception as exc:win.after(0,lambda msg=str(exc):p['state'].set('FAILED: '+msg))
    finally:p['busy']=False
   threading.Thread(target=worker,daemon=True).start()
  def animate(p=panel):
   if not p['latest']:return
   from components.validation.visual_workbench import playback
   force=p['model'] in ('FVD','BRB','SFI_MVLEM_3D');playback(win,p['latest']/'response.csv','Displacement (m)' if force else 'Strain','Force (kN)' if force else 'Stress (MPa)',p['model'])
  ttk.Button(buttons,text='Reset example',command=lambda m=model,p=panel:(p['edit'].delete('1.0','end'),p['edit'].insert('1.0',json.dumps(card(m),indent=2)))).pack(side='left')
  ttk.Button(buttons,text='Load card',command=load_card).pack(side='left');ttk.Button(buttons,text='Save card',command=save_card).pack(side='left');ttk.Button(buttons,text='Measured CSV',command=lambda p=panel:data_file('measured_csv',p)).pack(side='left');ttk.Button(buttons,text='Run / tune',command=run).pack(side='left');ttk.Button(buttons,text='Animate / GIF',command=animate).pack(side='left');ttk.Button(buttons,text='Outputs',command=lambda p=panel:os.startfile(str(p['latest'])) if p['latest'] else None).pack(side='left')
  panel['run']=run;panel['display']=display
  if model=='Steel02':ttk.Button(frame,text='Open published single-coupon experimental calibration',command=lambda:__import__('components.validation.steel_calibration_gui',fromlist=['launch']).launch(win,folder)).pack(fill='x')
  if model=='SFI_MVLEM_3D':ttk.Button(frame,text='Open full wall validation plan / Lu / E-SFI routes',command=lambda:__import__('OpenSees_Wall_Validation_V147').launch(win)).pack(fill='x')
  ttk.Label(frame,text='Manual tuning: edit parameters and rerun. Automatic fit: set fit_bounds, for example {"b": [0.001, 0.05]}, and supply measured CSV, citation and specimen_id. CSV order is preserved. Defaults are not experimental acceptance limits.',wraplength=1150).pack(fill='x')
 if initial_card is not None:
  import copy
  initial_card=copy.deepcopy(initial_card);panel=panels[initial_card['model']];panel['edit'].delete('1.0','end');panel['edit'].insert('1.0',json.dumps(initial_card,indent=2));book.select(list(panels).index(initial_card['model']))
 win._parameter_panels=panels;return win
