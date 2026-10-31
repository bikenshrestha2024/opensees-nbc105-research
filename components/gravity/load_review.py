"""Interactive source gravity breakdown without changing applied loads."""
from pathlib import Path
import json


def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk,messagebox
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
    from OpenSees_Storey_Gravity_V131 import COLUMNS
    win=tk.Toplevel(parent);win.title('Gravity source loads by storey — dead / live / source components');win.geometry('1250x800')
    folder=Path(folder);file=folder/'Gravity_Storey_Load_Breakdown_V131.json'
    if not file.is_file():ttk.Label(win,text='Rebuild this export to generate the exact source ledger. '+str(file)).pack();return win
    data=json.loads(file.read_text(encoding='utf-8-sig'));tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True);plots=ttk.Frame(tabs);details=ttk.Frame(tabs);audit=tk.Text(tabs,wrap='word')
    tabs.add(plots,text='Storey load charts');tabs.add(details,text='Source detail filters');tabs.add(audit,text='Load path / diaphragm evidence')
    choice=tk.StringVar(value='Classified components (unfactored)');bar=ttk.Frame(plots);bar.pack(fill='x');box=ttk.Combobox(bar,textvariable=choice,values=['Classified components (unfactored)','Dead / live (unfactored)','Applied gravity factors'],state='readonly',width=40);box.pack(side='left')
    fig=Figure(layout='constrained');ax=fig.add_subplot();chart=FigureCanvasTkAgg(fig,master=plots);chart.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(chart,plots)
    def draw(*unused):
        ax.clear();rows=data['rows'];labels=[r['storey'] for r in rows];mode=choice.get()
        keys=COLUMNS if mode.startswith('Classified') else ['dead_total_kN','live_total_kN','unclassified_kN'] if mode.startswith('Dead') else ['applied_dead_kN','applied_live_kN','applied_unclassified_kN']
        positive=[0.]*len(rows);negative=[0.]*len(rows)
        for key in keys:
            vals=[float(r.get(key,0.)) for r in rows]
            if not any(abs(v)>1e-10 for v in vals):continue
            left=[positive[i] if v>=0 else negative[i] for i,v in enumerate(vals)];ax.barh(labels,vals,left=left,label=key.replace('_kN','').replace('_',' '))
            for i,v in enumerate(vals):
                if v>=0:positive[i]+=v
                else:negative[i]+=v
        ax.set(xlabel='Load (kN), downward positive',title=mode);ax.grid(axis='x',alpha=.2);ax.legend(fontsize=8,loc='best');chart.draw_idle()
    box.bind('<<ComboboxSelected>>',draw);draw()
    ttk.Label(plots,text=data['convention'],wraplength=1150).pack(anchor='w')
    controls=ttk.Frame(details);controls.pack(fill='x');variables={}
    for key in ['storey','load_class','classification','pattern']:
        ttk.Label(controls,text=key).pack(side='left');var=tk.StringVar(value='All');variables[key]=var;box=ttk.Combobox(controls,textvariable=var,values=['All']+sorted({str(r[key]) for r in data['details']}),state='readonly',width=22);box.pack(side='left')
        box.bind('<<ComboboxSelected>>',lambda e:refresh())
    grid=ttk.Frame(details);grid.pack(fill='both',expand=True);tree=ttk.Treeview(grid,show='headings');sx=ttk.Scrollbar(grid,orient='horizontal',command=tree.xview);sy=ttk.Scrollbar(grid,command=tree.yview);tree.configure(xscrollcommand=sx.set,yscrollcommand=sy.set);grid.columnconfigure(0,weight=1);grid.rowconfigure(0,weight=1);tree.grid(row=0,column=0,sticky='nsew');sx.grid(row=1,column=0,sticky='ew');sy.grid(row=0,column=1,sticky='ns');total=tk.StringVar();ttk.Label(details,textvariable=total).pack(anchor='w')
    keys=list(data['details'][0]) if data['details'] else [];tree.configure(columns=keys)
    for key in keys:tree.heading(key,text=key);tree.column(key,width=160,stretch=False)
    def refresh():
        selected=[r for r in data['details'] if all(v.get()=='All' or str(r[k])==v.get() for k,v in variables.items())];tree.delete(*tree.get_children())
        for row in selected:tree.insert('','end',values=[row[k] for k in keys])
        total.set(f"{len(selected)} source rows | unfactored={sum(r['unfactored_kN'] for r in selected):,.3f} kN | applied={sum(r['applied_kN'] for r in selected):,.3f} kN")
    refresh()
    for name in ['LOAD_PATH_AND_DIAPHRAGM_AUDIT_V130.json','OpenSees_Complete_Gravity_Check_V118.json']:
        path=folder/name
        if path.is_file():audit.insert('end',name+'\n'+path.read_text(encoding='utf-8-sig')+'\n\n')
    audit.insert('end','Area-load route: one shell load vector, shared slab/beam/wall nodes, physical slab bending. The in-plane rigid diaphragm does not constrain vertical shell flexure. Adding a second tributary beam load duplicates that source. This audit does not establish member-by-member ETABS equivalence.\n');audit.configure(state='disabled');return win
