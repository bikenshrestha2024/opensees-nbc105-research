"""Wall validation GUI; native solver runs in a child process."""
from pathlib import Path
import json,subprocess,sys,tkinter as tk
from tkinter import ttk,filedialog
ROOT=Path(__file__).resolve().parent

def launch(parent=None):
 win=tk.Toplevel(parent) if parent else tk.Tk();win.title('Wall validation: Kolozvari 2023 / Lu 2015');win.geometry('1000x700')
 route=tk.StringVar(value='both');full=tk.BooleanVar(value=False)
 bar=ttk.Frame(win);bar.pack(fill='x')
 ttk.Label(bar,text='Route').pack(side='left');ttk.Combobox(bar,textvariable=route,values=['both','kolozvari2023','lu2015'],state='readonly').pack(side='left')
 ttk.Checkbutton(bar,text='Full Lu cyclic protocol (longer run)',variable=full).pack(side='left')
 ttk.Label(win,text='Numerical verification is not specimen validation or building design approval. Your core has no assumed confined boundaries.',wraplength=950).pack(fill='x')
 text=tk.Text(win,wrap='word');scroll=ttk.Scrollbar(win,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True)
 output=ROOT/'Wall_Validation_Results';state={'process':None,'stream':None}
 def load():
  f=output/'wall_validation.json'
  text.delete('1.0','end');text.insert('end',f.read_text() if f.exists() else 'Run diagnostics first. See WALL_VALIDATION_V147.md for required validation stages.')
 def poll():
  p=state['process']
  if p.poll() is None:win.after(500,poll);return
  state['stream'].close();load();text.insert('end','\nProcess exit '+str(p.returncode)+'\n'+(output/'run.log').read_text(errors='replace'));button.configure(state='normal')
 def run():
  output.mkdir(exist_ok=True);cmd=[sys.executable,str(ROOT/'components/validation/wall_validation.py'),'--output',str(output),'--route',route.get()]
  if full.get():cmd.append('--full-lu-cyclic')
  state['stream']=(output/'run.log').open('w');state['process']=subprocess.Popen(cmd,stdout=state['stream'],stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));button.configure(state='disabled');text.insert('end','\nRunning selected diagnostics...\n');poll()
 button=ttk.Button(bar,text='Run diagnostics',command=run);button.pack(side='left')
 ttk.Button(bar,text='Load report',command=load).pack(side='left')
 ttk.Button(bar,text='Open output folder',command=lambda:__import__('os').startfile(output)).pack(side='left')
 load()
 if not parent:win.mainloop()
 return win
if __name__=='__main__':launch()
