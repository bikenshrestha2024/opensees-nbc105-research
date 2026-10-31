"""Main-program integration for isolated experimental coupon calibration."""
from pathlib import Path
import json,csv,sys,subprocess,threading,datetime,os
ROOT=Path(__file__).resolve().parents[2]
def launch(parent,folder=None):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 from matplotlib.figure import Figure
 from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
 win=tk.Toplevel(parent);win.title('Experimental Steel02 calibration - V155');win.geometry('1150x820')
 bar=ttk.Frame(win);bar.pack(fill='x');base=Path(folder)/'OpenSees_Analysis_Results' if folder else ROOT/'Calibration_Steel02';out=tk.StringVar(value=str(base/'Steel02_Calibration'));ttk.Label(bar,text='Output folder').pack(side='left');ttk.Entry(bar,textvariable=out).pack(side='left',fill='x',expand=True)
 def browse():
  name=filedialog.askdirectory(parent=win)
  if name:out.set(name)
 ttk.Button(bar,text='Browse',command=browse).pack(side='left')
 ttk.Label(win,text='Published single coupon: 342 ordered samples; fit first256, withhold last86. Same-coupon tail is not independent specimen validation. No Fe-grade substitution or automatic project assignment.',wraplength=1100).pack(fill='x',pady=4)
 actions=ttk.Frame(win);actions.pack(fill='x');state=tk.StringVar(value='Ready. Bundled experimental fit available for inspection.');ttk.Label(win,textvariable=state,wraplength=1100).pack(fill='x')
 book=ttk.Notebook(win);book.pack(fill='both',expand=True);plot=ttk.Frame(book);params=ttk.Frame(book);logs=ttk.Frame(book);book.add(plot,text='Measured / predicted / residuals');book.add(params,text='Parameters and fit metrics');book.add(logs,text='Run log')
 text=tk.Text(params,wrap='word');text.pack(fill='both',expand=True);log=tk.Text(logs,wrap='none');ys=ttk.Scrollbar(logs,command=log.yview);xs=ttk.Scrollbar(logs,orient='horizontal',command=log.xview);log.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);log.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');logs.rowconfigure(0,weight=1);logs.columnconfigure(0,weight=1)
 fig=Figure(figsize=(11,6),layout='constrained');canvas=FigureCanvasTkAgg(fig,master=plot);canvas.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(canvas,plot);current={'path':ROOT/'Calibration_Steel02/results'}
 def load(path=None):
  try:
   path=Path(path or out.get());r=json.loads((path/'Steel02_Calibrated_Coupon.json').read_text(encoding='utf-8-sig'))
   with (path/'Steel02_Comparison.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
   x=[float(a['strain']) for a in rows];y=[float(a['measured_MPa']) for a in rows];z=[float(a['predicted_MPa']) for a in rows];n=r['training_samples'];fig.clear();ax=fig.subplots(2,2)
   ax[0,0].plot(x,y,label='Measured',color='black');ax[0,0].plot(x,z,label='Steel02 fit',alpha=.75);ax[0,0].set(xlabel='Strain',ylabel='Stress MPa');ax[0,0].legend()
   ax[0,1].plot(y,label='Measured');ax[0,1].plot(z,label='Predicted');ax[0,1].axvline(n,color='black',ls='--');ax[0,1].set(xlabel='Ordered sample',ylabel='Stress MPa');ax[0,1].legend()
   ax[1,0].plot([b-a for a,b in zip(y,z)]);ax[1,0].axvline(n,color='black',ls='--');ax[1,0].set(xlabel='Ordered sample',ylabel='Residual MPa');ax[1,1].scatter(y,z,s=8);ax[1,1].plot([-750,750],[-750,750],'k--');ax[1,1].set(xlabel='Measured MPa',ylabel='Predicted MPa')
   for a in ax.flat:a.grid(alpha=.2)
   canvas.draw_idle();text.delete('1.0','end');text.insert('1.0',json.dumps(r,indent=2));current['path']=path;state.set('Loaded '+str(path)+' | training RMSE '+format(r['training']['RMSE_MPa'],'.3f')+' MPa; withheld tail '+format(r['withheld_tail']['RMSE_MPa'],'.3f')+' MPa')
  except Exception as e:messagebox.showerror('Calibration results',str(e),parent=win)
 def run():
  path=Path(out.get()).expanduser().resolve()/datetime.datetime.now().strftime('Run_%Y%m%d_%H%M%S_%f');button.configure(state='disabled');state.set('Running isolated OpenSees material tester and bounded least squares...');book.select(logs)
  def worker():
   try:
    path.mkdir(parents=True,exist_ok=True)
    with (path/'Calibration_Run.log').open('w',encoding='utf8') as f:
     proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'Calibration_Steel02/01_CALIBRATE_STEEL02.py'),'--output',str(path)],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
     for line in proc.stdout:
      f.write(line);f.flush();win.after(0,lambda line=line:(log.insert('end',line),log.see('end')))
     code=proc.wait()
    if code:raise RuntimeError('Calibration exit '+str(code)+'; see '+str(path/'Calibration_Run.log'))
    win.after(0,lambda:(load(path),book.select(plot)))
   except Exception as exc:
    win.after(0,lambda msg=str(exc):state.set('FAILED: '+msg))
   finally:win.after(0,lambda:button.configure(state='normal'))
  threading.Thread(target=worker,daemon=True).start()
 button=ttk.Button(actions,text='Run experimental calibration',command=run);button.pack(side='left')
 ttk.Button(actions,text='Load selected output',command=load).pack(side='left');ttk.Button(actions,text='Show bundled fit',command=lambda:load(ROOT/'Calibration_Steel02/results')).pack(side='left')
 ttk.Button(actions,text='Excel / CSV / JSON folder',command=lambda:os.startfile(str(current['path']))).pack(side='left')
 def animate():
  from components.validation.visual_workbench import playback
  path=current['path']/'Native_Curve_Export/cyclic.csv'
  if not path.is_file():messagebox.showinfo('Playback','Run calibration first to generate native playback data.',parent=win);return
  playback(win,path,'Strain','Stress (MPa)','Calibrated Steel02: recorded coupon path')
 ttk.Button(actions,text='Animate fitted curve / export GIF',command=animate).pack(side='left')
 ttk.Button(actions,text='Copy log',command=lambda:(win.clipboard_clear(),win.clipboard_append(log.get('1.0','end')))).pack(side='left');load(ROOT/'Calibration_Steel02/results');win._calibration_run=run;win._calibration_button=button;win._calibration_current=current;return win
