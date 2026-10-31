"""Thread-safe analysis case ledger and live GUI view; no inferred completion."""
import json,time,threading,datetime
from pathlib import Path
class CaseLedger:
 def __init__(self,path,ids):
  self.path=Path(path);self.lock=threading.RLock();self.rows={i:dict(case=i,status='QUEUED',stage='Waiting',elapsed_s=0.) for i in ids};self.save()
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True)
  temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(dict(updated_at=datetime.datetime.now().astimezone().isoformat(),cases=list(self.rows.values())),indent=2),encoding='utf8');temp.replace(self.path)
 def set(self,key,status,stage):
  with self.lock:
   row=self.rows[key]
   if status in ('RUNNING','PREPARING') and '_start' not in row:row['_start']=time.monotonic()
   row.update(status=status,stage=stage)
   if '_start' in row:row['elapsed_s']=time.monotonic()-row['_start']
   self.save()
 def snapshot(self):
  with self.lock:
   return [dict(r,elapsed_s=time.monotonic()-r['_start'] if r['status'] in ('RUNNING','PREPARING') else r['elapsed_s']) if '_start' in r else dict(r) for r in self.rows.values()]
 def finish_pending(self,reason):
  for key,row in self.rows.items():
   if row['status'] in ('QUEUED','RUNNING','PREPARING'):self.set(key,'NOT COMPLETED',reason)
def panel(parent):
 from tkinter import ttk
 box=ttk.LabelFrame(parent,text='Selected batch: case status (elapsed wall time, not solver percent)');box.pack(fill='x',pady=4)
 tree=ttk.Treeview(box,columns=('case','status','stage','elapsed'),show='headings',height=5)
 for c,w in [('case',150),('status',120),('stage',580),('elapsed',100)]:tree.heading(c,text=c);tree.column(c,width=w,stretch=c=='stage')
 tree.pack(fill='x');holder={'ledger':None,'process':None,'cancelled':False}
 def stop():
  holder['cancelled']=True
  proc=holder.get('process')
  if proc is not None and proc.poll() is None:proc.terminate()
  if holder.get('ledger'):holder['ledger'].finish_pending('Stopped by user; no completion claimed')
 ttk.Button(box,text='Stop selected batch',command=stop).pack(anchor='w')
 def tick():
  if not tree.winfo_exists():return
  ledger=holder['ledger']
  if ledger:
   for r in ledger.snapshot():
    vals=(r['case'],r['status'],r['stage'],format(r['elapsed_s'],'.1f')+' s')
    if tree.exists(r['case']):tree.item(r['case'],values=vals)
    else:tree.insert('', 'end',iid=r['case'],values=vals)
  tree.after(1000,tick)
 tick();return holder
