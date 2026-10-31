"""Select complete earthquake pairs for trial or suite executions."""

__release__ = '134'
from pathlib import Path
import csv
import tkinter as tk
from tkinter import ttk

class PairSelector:
    def __init__(self,parent,manifest,defaults):
        self.manifest=manifest;self.defaults=defaults;self.source=None;self.rows=[]
        self.frame=ttk.LabelFrame(parent,text='Earthquakes to run — complete X/Y pairs',padding=6);self.frame.pack(fill='x',pady=5)
        self.trial=tk.BooleanVar(value=True);self.summary=tk.StringVar()
        ttk.Checkbutton(self.frame,text='Preliminary run / setup check (allows one pair; not a completed suite assessment)',variable=self.trial).pack(anchor='w')
        self.list=tk.Listbox(self.frame,selectmode='extended',exportselection=False,height=5)
        sy=ttk.Scrollbar(self.frame,command=self.list.yview);sy.pack(side='right',fill='y');self.list.configure(yscrollcommand=sy.set);self.list.pack(fill='x',expand=True)
        bar=ttk.Frame(self.frame);bar.pack(fill='x')
        for label,fn in [('Reload available pairs',lambda:self.refresh(force=True)),('Select all',self.all),('Clear',self.clear)]:ttk.Button(bar,text=label,command=fn).pack(side='left',padx=3)
        ttk.Label(self.frame,textvariable=self.summary).pack(anchor='w')
        ttk.Label(self.frame,text='Ctrl-click or Shift-click to select several. Every selected pair runs XY and YX; scale, duration and integration settings are retained.').pack(anchor='w')
        self.list.bind('<<ListboxSelect>>',lambda e:self.update())
        self.manifest.trace_add('write',lambda *args:self.refresh())
        self.refresh()
    def refresh(self,force=False):
        source=self.manifest.get().strip()
        if source==self.source and not force:return
        previous={self.rows[i]['pair_id'] for i in self.list.curselection()} if self.rows else set()
        self.source=source
        try:
            if source:
                with Path(source).open(encoding='utf-8-sig',newline='') as f:self.rows=[r for r in csv.DictReader(f) if str(r.get('pair_id','')).strip()]
            else:self.rows=list(self.defaults)
            self.list.delete(0,'end')
            for row in self.rows:self.list.insert('end',row['pair_id']+' | '+row.get('field_type','Custom'))
            for i,row in enumerate(self.rows):
                if row['pair_id'] in previous:self.list.selection_set(i)
            if not self.list.curselection() and self.rows:self.list.selection_set(0)
            self.update()
        except Exception as exc:
            self.rows=[];self.list.delete(0,'end');self.summary.set('Cannot load pairs: '+str(exc))
    def update(self):
        n=len(self.list.curselection());self.summary.set(f'{n} of {len(self.rows)} earthquakes selected = {2*n} bidirectional orientation analyses for this stiffness case.')
    def all(self):self.list.selection_set(0,'end');self.update()
    def clear(self):self.list.selection_clear(0,'end');self.update()
    def config(self):
        self.refresh();ids=[self.rows[i]['pair_id'] for i in self.list.curselection()]
        if not ids:raise ValueError('Select at least one earthquake pair.')
        if len(set(ids))!=len(ids):raise ValueError('Available pair IDs must be unique.')
        return dict(selected_pair_ids=ids,preliminary_selection=bool(self.trial.get()),available_pair_count=len(self.rows))

def filter_pairs(rows,config):
    selected=config.get('selected_pair_ids')
    if selected is None:return list(rows)
    if not selected:raise ValueError('No earthquake pairs selected.')
    ids={str(x).strip() for x in selected};known={str(r['pair_id']).strip() for r in rows}
    missing=ids-known
    if missing:raise ValueError('Selected pair IDs not found: '+', '.join(sorted(missing)))
    return [r for r in rows if str(r['pair_id']).strip() in ids]
