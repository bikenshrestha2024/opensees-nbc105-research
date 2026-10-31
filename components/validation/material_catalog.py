"""Parameter provenance and native OpenSees definition export, without changing project assignments."""
from pathlib import Path
import json,csv,datetime,hashlib
ROOT=Path(__file__).resolve().parents[2]
CAT=ROOT/'Material_Catalog'
def profiles():return json.loads((CAT/'index.json').read_text(encoding='utf8'))
def read_profile(entry):return json.loads((CAT/entry['file']).read_text(encoding='utf-8-sig'))
def parameter_rows(d):
 rows=[]
 for group in ('parameters','wall_concrete','wall_steel','fsam'):
  for key,value in d.get(group,{}).items():
   meta=d.get('provenance',{}).get(key,{}) if group=='parameters' else {}
   unit=meta.get('unit','MPa' if key in ('fpcc','Ec','ft','fyp','fyn','E0') else 'dimensionless')
   rows.append(dict(group=group,parameter=key,value=value,unit=unit,basis=meta.get('basis',d['parameter_basis']),source=meta.get('source',d['source']),locator=meta.get('locator',d['citation'])))
 return rows
FORMULAS={
 'Concrete01':'Compression: eta=eps/epsc0; sigma=fpc*(2*eta-eta^2) up to peak; linear descending branch to (epsU,fpcu); zero tension. Cyclic unloading/reloading is the native Kent-Scott-Park/Karsan-Jirsa implementation. Initial tangent=2*fpc/epsc0.',
 'Concrete02':'Same parabolic/linear compressive backbone; initial tangent=2*fpc/epsc0. Tensile cracking strain=ft/E0; after cracking sigma=max(0,ft-Ets*(eps-ft/E0)). lambda controls cyclic unloading. Native Yassin implementation governs reversals.',
 'ConcreteCM':'Chang-Mander/Tsai backbone: sigma=fpcc*n*x/[1+(n-r/(r-1))*x+x^r/(r-1)], x=eps/epcc, n=Ec*epcc/fpcc. Critical strain and tensile branches plus native cyclic rules use rc,xcrn,ft,et,rt,xcrp. Formula is not a replacement custom solver.',
 'Steel02':'Giuffre-Menegotto-Pinto transition: normalized sigma=b*eps+(1-b)*eps/(1+abs(eps)^R)^(1/R); the native model updates reversal origins, R and isotropic hardening. Fy,E,b,R0,cR1,cR2,a1-a4 are supplied in exact command order.',
 'SteelMPF':'Menegotto-Pinto with Filippou isotropic hardening; different tension/compression yield and hardening and pre-yield reversal treatment. Do not silently equate SteelMPF cR1/cR2 to isotropic a1/a2.',
 'FVD':'Maxwell series model: udot=Fdot/K + sign(F)*(abs(F)/Cd)^(1/alpha). Dashpot F=Cd*abs(v)^alpha*sign(v); not the same as total device velocity when spring deforms. kN/mm to kN/m: K*1000; Cd*1000^alpha.',
 'BRB':'Idealized uniform Steel02 core: strain=extension/Lyield; F=Acore*sigma; initial stiffness=E*Acore/Lyield; nominal yield force=Fy*Acore. This is not complete BRB qualification or Black et al. specimen reproduction; casing, end zones, fatigue and compression overstrength absent.',
 'SFI_MVLEM_3D':'Native E_SFI_MVLEM_3D/SFI_MVLEM_3D elements use ConcreteCM+SteelMPF inside FSAM at wall macro-fibers. Sum(width_i*thickness_i)=wall area. FSAM includes biaxial normal/shear interaction, friction and dowel parameters. CoR=.4 and ThickMod=.63 are author defaults, not NBC wall stiffness prescriptions.'}
def commands(d,tag=960001):
 p=d['parameters'];m=d['model'];lines=[]
 from components.validation.parameter_studies import SCHEMAS,CM,MPF,STEEL
 def uni(name,t,keys,values,stress):
  args=[values[k]*(1000 if k in stress else 1) for k in keys]
  return "ops.uniaxialMaterial("+repr(name)+", "+str(t)+", "+', '.join(repr(v) for v in args)+")"
 if m in ('Concrete01','Concrete02','ConcreteCM','Steel02','SteelMPF'):
  stress={'fpc_MPa','fpcu_MPa','ft_MPa','Ets_MPa','fpcc','Ec','ft','Fy_MPa','E_MPa','fyp','fyn','E0'}
  lines.append(uni(m,tag,list(SCHEMAS[m][0]),p,stress))
 elif m=='FVD':lines.append("ops.uniaxialMaterial('ViscousDamper', "+str(tag)+", "+', '.join(repr(p[k]) for k in ('K_kN_m','Cd','alpha'))+")")
 elif m=='BRB':
  lines.append(uni('Steel02',tag,list(STEEL),p,{'Fy_MPa','E_MPa'}));lines.append('# Core area = '+repr(p['core_area_m2'])+' m2; yielding length = '+repr(p['yielding_length_m'])+' m. Element connectivity must be supplied separately.')
 else:
  steel=dict(d['wall_steel']);steel.update(fyp=p['steel_Fy_MPa'],fyn=p['steel_Fy_MPa'],E0=p['steel_E_MPa']);c=dict(d['wall_concrete']);c['fpcc']=p['concrete_fc_MPa']
  lines.extend([uni('SteelMPF',tag,list(MPF),steel,{'fyp','fyn','E0'}),uni('ConcreteCM',tag+1,list(CM),c,{'fpcc','Ec','ft'}),"ops.nDMaterial('FSAM', "+str(tag+2)+", 0.0, "+str(tag)+", "+str(tag)+", "+str(tag+1)+", "+', '.join(repr(v) for v in [p['rho_x'],p['rho_y'],d['fsam']['nu'],d['fsam']['alpha']])+")",'# Wall FSAM tag = '+str(tag+2)+'; actual element '+d['wall_formulation']+' requires reviewed geometry, connectivity and macro-fiber layout.'])
 return '\n'.join(lines)
def export_bundle(d,folder):
 out=Path(folder);out.mkdir(parents=True,exist_ok=True);(out/'Selected_Card.json').write_text(json.dumps(d,indent=2),encoding='utf8');rows=parameter_rows(d)
 with (out/'Parameter_Provenance.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 text='# Units kN, m, s. Stress MPa converted once to kN/m2.\n# Reference material definitions; no building assignment or approval.\n# '+d['specimen_id']+'\n# Source: '+d['source']+'\ndef define_materials(ops, base_tag=960001):\n'
 text+='    if base_tag != 960001: raise ValueError("Use the exported tag map or regenerate with a different tag")\n'
 text+='\n'.join('    '+line for line in commands(d).splitlines())+'\n'
 (out/'Native_Materials_kN_m.py').write_text(text,encoding='utf8')
 (out/'Basis.md').write_text('# '+d['specimen_id']+'\n\n'+d['parameter_basis']+'\n\n'+FORMULAS[d['model']]+'\n\nSource: '+d['source']+'\nLocator: '+d['citation']+'\n\nNo experimental equivalence or project approval is inferred. This export does not set nonlinear_parameters_reviewed or change the building configuration.\n',encoding='utf8')
 return out

def launch(parent,folder=None):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 import os,subprocess,sys,threading
 win=tk.Toplevel(parent);win.title('Literature materials / exact parameters / research setup - V159');win.geometry('1250x850');base=Path(folder or ROOT)/'Material_Research_V159';entries=profiles();model=tk.StringVar(value='Concrete01');choice=tk.StringVar();status=tk.StringVar();bar=ttk.Frame(win);bar.pack(fill='x')
 ttk.Label(bar,text='Formulation').pack(side='left');models=ttk.Combobox(bar,textvariable=model,values=list(FORMULAS),state='readonly',width=20);models.pack(side='left');select=ttk.Combobox(bar,textvariable=choice,state='readonly',width=75);select.pack(side='left',fill='x',expand=True)
 ttk.Label(win,text='Published example, experimental fit and nominal research baseline are distinct. Parameters below are the actual native solver inputs. Select a profile before exporting or running. No automatic project assignment.',wraplength=1200).pack(fill='x');ttk.Label(win,textvariable=status,wraplength=1200).pack(fill='x');tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True);data=ttk.Frame(tabs);detail=ttk.Frame(tabs);tabs.add(data,text='Values / units / provenance');tabs.add(detail,text='Formulation / commands / limitations')
 cols=('group','parameter','value','unit','basis','source','locator');tree=ttk.Treeview(data,columns=cols,show='headings');ys=ttk.Scrollbar(data,command=tree.yview);xs=ttk.Scrollbar(data,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);ys.pack(side='right',fill='y');xs.pack(side='bottom',fill='x');tree.pack(fill='both',expand=True)
 for c in cols:tree.heading(c,text=c);tree.column(c,width=155 if c not in ('basis','source','locator') else 400,stretch=False)
 text=tk.Text(detail,wrap='word');scroll=ttk.Scrollbar(detail,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);state={'card':None,'out':None,'busy':False}
 def load(event=None):
  e=next(e for e in entries if e['id']==choice.get());d=read_profile(e);state['card']=d;tree.delete(*tree.get_children())
  for r in parameter_rows(d):tree.insert('','end',values=[r[c] for c in cols])
  text.delete('1.0','end');text.insert('end',d['parameter_basis']+'\n\nFORMULATION\n'+FORMULAS[d['model']]+'\n\nNATIVE kN-m COMMANDS\n'+commands(d)+'\n\nSOURCE\n'+d['source']+'\n'+d['citation']+'\n\nSOURCE-UNIT VALUES\n'+json.dumps(d.get('source_native_values',{}),indent=2)+'\n\nFULL CARD\n'+json.dumps(d,indent=2));status.set(e['status']+' | '+e['label'])
 def change(event=None):
  valid=[e['id'] for e in entries if e['model']==model.get()];select.configure(values=valid);choice.set(next((v for v in valid if not v.startswith('M30_')),valid[0]));load()
 models.bind('<<ComboboxSelected>>',change);select.bind('<<ComboboxSelected>>',load)
 def export():
  out=export_bundle(state['card'],base/state['card']['profile_id']/datetime.datetime.now().strftime('Export_%Y%m%d_%H%M%S_%f'));state['out']=out;status.set('Exported exact inputs and native definitions: '+str(out));return out
 def tune():
  from components.validation.parameter_gui import launch as setup
  setup(win,folder,initial_card=state['card'])
 def run():
  if state['busy']:return
  out=export();used_card=json.loads(json.dumps(state['card']));state['busy']=True;runbutton.configure(state='disabled');status.set('Running isolated native '+state['card']['model']+'; source values retained in Selected_Card.json')
  def worker():
   proc=subprocess.run([sys.executable,'-u','-m','components.validation.parameter_studies',str(out/'Selected_Card.json'),str(out)],cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));(out/'run.log').write_text(proc.stdout+proc.stderr,encoding='utf8')
   def done():
    state['busy']=False;runbutton.configure(state='normal');status.set(('COMPLETED' if proc.returncode==0 else 'FAILED; inspect failure.json and run.log')+' | '+str(out))
    if proc.returncode==0:
     from components.validation.parameter_gui import launch as setup
     w=setup(win,folder,initial_card=used_card);panel=w._parameter_panels[used_card['model']];panel['display'](out)
   win.after(0,done)
  threading.Thread(target=worker,daemon=True).start()
 actions=ttk.Frame(win);actions.pack(fill='x');ttk.Button(actions,text='Export exact card / native definitions / provenance',command=export).pack(side='left');runbutton=ttk.Button(actions,text='Run selected native profile',command=run);runbutton.pack(side='left');ttk.Button(actions,text='Edit / tune selected card',command=tune).pack(side='left');ttk.Button(actions,text='Open last output',command=lambda:os.startfile(str(state['out'])) if state['out'] else None).pack(side='left');ttk.Button(actions,text='Open saved 8-component graphs',command=lambda:__import__('components.validation.research_results_gui',fromlist=['launch']).launch(win)).pack(side='left')
 change();win._catalog_state=state;win._catalog_model=model;win._catalog_choice=choice;win._catalog_change=change;win._catalog_load=load;win._catalog_tree=tree;return win
