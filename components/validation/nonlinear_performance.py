"""Explicit nonlinear performance criteria and complete-suite assessment (V151)."""
from pathlib import Path
import csv,json,math,datetime,webbrowser
NBC='https://giwmscdnone.gov.np/media/files/NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf'
NIST='https://nvlpubs.nist.gov/nistpubs/gcr/2017/NIST.GCR.17-917-46v3.pdf'
FIELDS=['pair_id','orientation','status','model_sha256','metric','demand','unit','result_file']

def template(state='ULS'):
 if state not in ('ULS','SLS'):raise ValueError('Choose ULS or SLS')
 criteria=[]
 for axis in ('X','Y'):
  criteria.append(dict(metric='peak_edge_drift_'+axis,limit=.025 if state=='ULS' else .006,unit='ratio',control='deformation',source=NBC,clause='5.5.3; 9.3.3.1 cross-reference discrepancy requires review',reviewed=False))
 for metric,unit,control in [('residual_drift','ratio','deformation'),('plastic_rotation','rad','deformation'),('concrete_compression_strain','strain','deformation'),('steel_strain','strain','deformation'),('wall_shear','kN','force'),('joint_shear','kN','force'),('BRB_ductility','ratio','deformation'),('FVD_stroke','m','deformation'),('FVD_force','kN','force')]:
  criteria.append(dict(metric=metric,limit=None,unit=unit,control=control,source='',clause='',reviewed=False))
 return dict(release='V151',performance_objective='PROJECT INPUT REQUIRED',limit_state=state,model_sha256='',expected_pair_ids=[],orientations=['XY','YX'],torsion_sensitive=True,criteria=criteria,notes='Each metric must identify its member/station/axis when needed. Supply component limits for actual detailing and axial load. No generic IO/LS/CP strains or rotations are assumed. Residual drift is not defined as the last sample of a truncated record. Drift limits are screens pending review of the 9.3.3.1 reference to 5.6, which is accidental eccentricity in this edition.')

def finite(v):
 n=float(v)
 if not math.isfinite(n):raise ValueError('Non-finite demand or limit')
 return n

def assess(config,rows):
 expected=config.get('expected_pair_ids',[]);orientations=config.get('orientations',[]);digest=config.get('model_sha256','');out=[]
 if len(expected)!=len(set(expected)):raise ValueError('Duplicate expected pair IDs')
 if orientations!=['XY','YX']:raise ValueError('Paired 3D assessment requires XY and YX')
 for criterion in config['criteria']:
  q=dict(criterion);q.update(status='NOT EVALUATED',reason='',demand=None,utilization=None)
  try:
   if not expected or not digest:raise ValueError('Supply expected suite and model SHA256')
   if len(digest)!=64 or any(c not in '0123456789abcdefABCDEF' for c in digest):raise ValueError('Model SHA256 must contain 64 hexadecimal characters')
   if any(not isinstance(pair,str) or not pair.strip() for pair in expected):raise ValueError('Pair IDs must be nonempty strings')
   if config.get('torsion_sensitive',True) and len(expected)<3:raise ValueError('NBC 9.3.2.1: three orthogonal pairs required for torsionally sensitive 3D assessment; smaller suite is a trial')
   if not config.get('performance_objective') or 'REQUIRED' in config['performance_objective']:raise ValueError('Specify performance objective')
   if config.get('limit_state') not in ('ULS','SLS'):raise ValueError('Invalid limit state')
   if criterion.get('reviewed') is not True or not criterion.get('source') or not criterion.get('clause'):raise ValueError('Criterion needs reviewed source and clause')
   if criterion.get('control') not in ('force','deformation'):raise ValueError('Specify force/deformation control')
   limit=finite(criterion['limit'])
   if limit<=0:raise ValueError('Positive acceptance limit required')
   values={}
   for r in rows:
    if r['metric']!=criterion['metric']:continue
    if r['pair_id'] not in expected:raise ValueError('Unexpected pair in demand evidence')
    if r['model_sha256']!=digest:raise ValueError('Demand model fingerprint differs')
    if r['unit']!=criterion['unit']:raise ValueError('Demand/limit units differ')
    if r['status']!='COMPLETED_FULL_RECORD':raise ValueError('Failed/truncated case is not full-record evidence')
    if not Path(r['result_file']).is_file():raise ValueError('Missing result evidence')
    key=(r['pair_id'],r['orientation'])
    if key in values:raise ValueError('Duplicate metric/pair/orientation; distinguish member metrics')
    values[key]=abs(finite(r['demand']))
   keys={(pair,o) for pair in expected for o in orientations}
   if set(values)!=keys:raise ValueError('Missing or unexpected pair/orientation demands')
   pair_peaks=[max(values[pair,o] for o in orientations) for pair in expected]
   if len(expected)==7:raise ValueError('Exactly seven: NBC 9.3.3 wording needs interpretation')
   rule=criterion.get('aggregation','NBC_SUITE')
   if rule not in ('NBC_SUITE','MAXIMUM'):raise ValueError('Aggregation must be NBC_SUITE or MAXIMUM')
   demand=max(pair_peaks) if len(expected)<7 or rule=='MAXIMUM' else sum(pair_peaks)/len(pair_peaks)
   q.update(demand=demand,utilization=demand/limit,status='PASS' if demand<=limit else 'FAIL',statistic='maximum' if len(expected)<7 or rule=='MAXIMUM' else 'mean',pair_count=len(expected))
  except (ValueError,TypeError,KeyError) as exc:q['reason']=str(exc)
  out.append(q)
 return dict(overall='FAIL' if any(r['status']=='FAIL' for r in out) else 'INCOMPLETE' if any(r['status']=='NOT EVALUATED' for r in out) else 'SUPPLIED CRITERIA PASS',checks=out,scope='Only supplied metrics assessed. Convergence, drift or coupon PASS is not building acceptance.',finished=datetime.datetime.now().astimezone().isoformat())

def launch(parent,folder):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 win=tk.Toplevel(parent);win.title('Nonlinear performance objectives and acceptance - V151');win.geometry('1150x780')
 root=Path(folder);state=tk.StringVar(value='ULS');bar=ttk.Frame(win);bar.pack(fill='x');ttk.Combobox(bar,textvariable=state,values=['ULS','SLS'],state='readonly',width=8).pack(side='left')
 ttk.Label(win,text='Define objective, actual model SHA, expected earthquake pairs, and sourced component limits. Import completed full-record metric evidence. No automatic project approval.',wraplength=1100).pack(fill='x')
 tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True);editframe=ttk.Frame(tabs);resultframe=ttk.Frame(tabs);tabs.add(editframe,text='Editable criteria JSON');tabs.add(resultframe,text='Assessment')
 text=tk.Text(editframe,wrap='none');ys=ttk.Scrollbar(editframe,command=text.yview);xs=ttk.Scrollbar(editframe,orient='horizontal',command=text.xview);text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);text.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');editframe.rowconfigure(0,weight=1);editframe.columnconfigure(0,weight=1)
 output=tk.Text(resultframe,wrap='word');output.pack(fill='both',expand=True);current={'rows':[]}
 objective=tk.StringVar(value='PROJECT INPUT REQUIRED')
 ttk.Combobox(win,textvariable=objective,values=['PROJECT INPUT REQUIRED','Operational','Immediate Occupancy (IO)','Life Safety (LS)','Collapse Prevention (CP)'],state='readonly').pack(fill='x',before=tabs)
 def reset():text.delete('1.0','end');text.insert('1.0',json.dumps(template(state.get()),indent=2))
 def apply_objective(*args):
  try:
   data=json.loads(text.get('1.0','end'));data['performance_objective']=objective.get();data['acceptance_basis']='Supply applicable component standard/table, hazard level, detailing, axial load and deformation definition; objective label supplies no numerical limits.';text.delete('1.0','end');text.insert('1.0',json.dumps(data,indent=2))
  except Exception:pass
 objective.trace_add('write',apply_objective)
 def load():
  path=filedialog.askopenfilename(parent=win,filetypes=[('JSON','*.json')])
  if path:text.delete('1.0','end');text.insert('1.0',Path(path).read_text(encoding='utf-8-sig'))
 def save():
  try:
   data=json.loads(text.get('1.0','end'));path=filedialog.asksaveasfilename(parent=win,defaultextension='.json',initialfile='Nonlinear_Performance_V151.json')
   if path:Path(path).write_text(json.dumps(data,indent=2),encoding='utf8')
  except Exception as e:messagebox.showerror('Criteria',str(e),parent=win)
 def demands():
  path=filedialog.askopenfilename(parent=win,filetypes=[('Metric demands CSV','*.csv')])
  if path:
   with Path(path).open(encoding='utf-8-sig',newline='') as stream:current['rows']=list(csv.DictReader(stream))
 def csv_template():
  path=filedialog.asksaveasfilename(parent=win,defaultextension='.csv',initialfile='Nonlinear_Metric_Demands_V151.csv')
  if path:
   with Path(path).open('w',encoding='utf-8-sig',newline='') as stream:csv.writer(stream).writerow(FIELDS)
 def evaluate():
  try:
   report=assess(json.loads(text.get('1.0','end')),current['rows']);output.delete('1.0','end');output.insert('1.0',json.dumps(report,indent=2));tabs.select(resultframe)
   path=filedialog.asksaveasfilename(parent=win,defaultextension='.json',initialfile='Nonlinear_Performance_Report_V151.json')
   if path:Path(path).write_text(json.dumps(report,indent=2),encoding='utf8')
  except Exception as e:messagebox.showerror('Performance inputs',str(e),parent=win)
 for label,fn in [('New state template',reset),('Load criteria',load),('Save criteria',save),('Demand CSV template',csv_template),('Load demands',demands),('Assess / export JSON',evaluate)]:ttk.Button(bar,text=label,command=fn).pack(side='left')
 ttk.Button(win,text='NBC 105:2025 source',command=lambda:webbrowser.open(NBC)).pack(anchor='w');ttk.Button(win,text='NIST RC nonlinear modelling and acceptance guidance',command=lambda:webbrowser.open(NIST)).pack(anchor='w');reset();return win
