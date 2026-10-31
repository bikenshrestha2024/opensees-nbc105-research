"""Property → source object → solver element mapping with source provenance."""

__release__ = '134'
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk,messagebox
import webbrowser
from OpenSees_Mapping_Audit_V125 import collect,library,save_assignment,export_excel


class MappingGUI:
    def __init__(self,parent,folder):
        from OpenSees_Research_UI_V123 import scrollable_form
        self.folder=Path(folder);self.win=tk.Toplevel(parent);self.win.title('V126 — Properties, individual elements and device assignments')
        outer=scrollable_form(self.win,min_width=1180)
        ttk.Label(outer,text='ETABS properties and individual OpenSees elements',font=('Segoe UI',15,'bold')).pack(anchor='w')
        ttk.Label(outer,text='Select a property group, source object or individual solver segment. Candidate device selections preserve the elastic baseline until the scenario is activated.').pack(anchor='w')
        tools=ttk.Frame(outer);tools.pack(fill='x',pady=5)
        self.category=tk.StringVar(value='All');self.search=tk.StringVar();self.target=tk.StringVar(value='KEEP_SOURCE_ELASTIC')
        ttk.Combobox(tools,textvariable=self.category,values=('All','BRACE','SHEAR WALL','FLOOR','BEAM','COLUMN'),state='readonly',width=17).pack(side='left')
        ttk.Entry(tools,textvariable=self.search,width=28).pack(side='left',padx=5)
        ttk.Button(tools,text='Reload source audit',command=self.reload).pack(side='left')
        ttk.Button(tools,text='Export / open Excel audit',command=self.excel).pack(side='left',padx=5)
        ttk.Button(tools,text='Highlight selected ID in 3D',command=self.highlight).pack(side='left')
        ttk.Button(tools,text='Parameter citations',command=lambda:show_parameter_sources(self.win)).pack(side='left',padx=5)
        pane=ttk.Frame(outer);pane.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(pane,columns=('category','etabs','topology','solver','nodes','target'),height=18,selectmode='extended')
        self.tree.heading('#0',text='Property / source object / solver segment');self.tree.column('#0',width=310)
        for key,title,width in [('category','Type',90),('etabs','ETABS ID',85),('topology','Topology tag',95),('solver','Solver tag(s)',130),('nodes','Node tags',140),('target','Selected target',210)]:
            self.tree.heading(key,text=title);self.tree.column(key,width=width)
        sy=ttk.Scrollbar(pane,orient='vertical',command=self.tree.yview);sx=ttk.Scrollbar(pane,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        self.tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        pane.columnconfigure(0,weight=1);pane.rowconfigure(0,weight=1)
        preview=ttk.LabelFrame(pane,text='3D source geometry — selection highlights automatically');preview.grid(row=0,column=2,rowspan=2,sticky='nsew',padx=(7,0))
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
        self.figure=Figure(figsize=(4.8,4.8),dpi=90,layout='constrained');self.axis=self.figure.add_subplot(projection='3d')
        self.chart=FigureCanvasTkAgg(self.figure,master=preview);self.chart.get_tk_widget().pack(fill='both',expand=True)
        NavigationToolbar2Tk(self.chart,preview).update()
        from OpenSees_View_Controls_V134 import camera_controls
        camera_controls(preview,self.axis,self.chart)
        viewtools=ttk.Frame(preview);viewtools.pack(fill='x')
        for label,callback in [('Zoom +',lambda:self.zoom_view(.8)),('Zoom -',lambda:self.zoom_view(1.25)),('Fit model',self.fit_model),('Fit selection',self.fit_selection),('Isometric',lambda:self.set_camera(27.5,45))]:
            ttk.Button(viewtools,text=label,command=callback).pack(side='left',padx=2)
        ttk.Label(preview,text='Wheel: zoom | Left drag: rotate | Fit selection: focus highlight').pack(anchor='w')
        self.chart.mpl_connect('scroll_event',self.scroll_zoom)
        self.chart.get_tk_widget().bind('<MouseWheel>',lambda event:'break',add='+')
        self.selected_points=[]
        pick=ttk.Frame(outer);pick.pack(fill='x',pady=3)
        self.id_kind=tk.StringVar(value='OpenSees node');self.id_value=tk.StringVar(value='1')
        ttk.Combobox(pick,textvariable=self.id_kind,values=('OpenSees node','OpenSees solver element','ETABS object'),state='readonly',width=24).pack(side='left')
        ttk.Entry(pick,textvariable=self.id_value,width=14).pack(side='left',padx=5)
        ttk.Button(pick,text='Highlight ID',command=self.highlight_inline_id).pack(side='left')
        controls=ttk.LabelFrame(outer,text='Mapping and device library',padding=7);controls.pack(fill='x',pady=5)
        ttk.Combobox(controls,textvariable=self.target,values=[r['name'] for r in library()],state='readonly',width=42).grid(row=0,column=0,sticky='w')
        ttk.Button(controls,text='Assign selected objects / segments',command=self.assign).grid(row=0,column=1,padx=5)
        self.active=tk.BooleanVar(value=False);self.weight=tk.BooleanVar(value=False)
        ttk.Checkbutton(controls,text='Activate mapped scenario (devices require nonlinear model)',variable=self.active).grid(row=0,column=2,sticky='w')
        ttk.Label(controls,text='Device parameters (kN–m–s; missing values stay null)').grid(row=1,column=0,sticky='w')
        self.parameters=tk.Text(controls,height=5,width=85,wrap='word');self.parameters.grid(row=2,column=0,columnspan=2,sticky='ew')
        self.citation=tk.StringVar()
        ttk.Label(controls,text='Project test / manufacturer citation').grid(row=1,column=2,sticky='w')
        ttk.Entry(controls,textvariable=self.citation,width=58).grid(row=2,column=2,sticky='ew')
        ttk.Checkbutton(controls,text='Physical device weight / retained load model reviewed',variable=self.weight).grid(row=3,column=2,sticky='w')
        ttk.Button(controls,text='Open selected formulation reference',command=self.reference).grid(row=3,column=0,sticky='w')
        ttk.Button(controls,text='Load published FVD example (reference only)',command=self.load_benchmark).grid(row=3,column=1,sticky='w')
        self.details=tk.Text(outer,height=10,wrap='word');self.details.pack(fill='x')
        self.status=tk.StringVar();ttk.Label(outer,textvariable=self.status,wraplength=1150).pack(anchor='w')
        self.tree.bind('<<TreeviewSelect>>',self.selection_details)
        self.category.trace_add('write',lambda *_:self.populate());self.search.trace_add('write',lambda *_:self.populate())
        self.target.trace_add('write',lambda *_:self.parameter_template())
        self.reload();self.parameter_template()

    def reload(self):
        try:
            self.data=collect(self.folder);self.active.set(self.data['selections'].get('active',False));self.populate();self.draw_source();self.highlight_inline_id()
            path=export_excel(self.folder)
            self.status.set(f"Loaded {len(self.data['properties'])} source property groups and {len(self.data['elements'])} objects. Excel audit populated: {path}")
        except Exception as exc:self.status.set(str(exc))

    def populate(self):
        if not hasattr(self,'data'):return
        self.tree.delete(*self.tree.get_children());self.item_keys={};self.record_items={}
        groups={};self.bykey={r['key']:r for r in self.data['elements']}
        for r in self.data['elements']:
            if self.category.get()!='All' and r['category']!=self.category.get():continue
            if self.search.get().strip().lower() not in json.dumps(r).lower():continue
            group=r['category']+' / '+r['property']
            if group not in groups:
                prop=next(p for p in self.data['properties'] if p['group']==group)
                title=f"{group} ({prop['count']} objects) | {prop['material'] or 'material pending'}"
                groups[group]=self.tree.insert('','end',text=title,open=True);self.item_keys[groups[group]]=[]
            parent=groups[group];self.item_keys[parent].append(r['key'])
            iid=self.tree.insert(parent,'end',text=f"{r['key']} / Storey {r['storey']}",values=(r['category'],r['etabs_object'],r['topology_tag'],','.join(map(str,r['solver_tags'])),','.join(map(str,r['node_tags'])),r['target']))
            self.item_keys[iid]=[r['key']];self.record_items[iid]=r
            for tag in r['solver_tags']:
                sr=next((s for s in self.data['solver_elements'] if s['solver_tag']==tag),None)
                target=self.data['selections'].get('assignments',{}).get(f'SOLVER:{tag}',{}).get('target',r['target'])
                child=self.tree.insert(iid,'end',text=f'Solver element {tag}',values=(r['category'],r['etabs_object'],r['topology_tag'],tag,','.join(map(str,sr['node_tags'])) if sr else '',target))
                self.item_keys[child]=[f'SOLVER:{tag}'];self.record_items[child]=r

    def parameter_template(self):
        target=self.target.get()
        if target=='FVD_MAXWELL':p=dict(K=None,Cd=None,alpha=None)
        elif target=='BRB_STEEL02':p=dict(core_area=None,Fy=None,E0=None,b=None,R0=20.,cR1=.925,cR2=.15,a1=None,a2=None,a3=None,a4=None)
        else:p={}
        self.parameters.delete('1.0','end');self.parameters.insert('1.0',json.dumps(p,indent=2))

    def load_benchmark(self):
        from OpenSees_Mapping_Audit_V125 import FVD_EXAMPLE
        self.target.set('FVD_MAXWELL');self.active.set(False);self.weight.set(False)
        p=dict(K=25000.,Cd=20.74*1000**.35,alpha=.35,reference_only=True)
        self.parameters.delete('1.0','end');self.parameters.insert('1.0',json.dumps(p,indent=2));self.citation.set(FVD_EXAMPLE)
        self.status.set('Loaded published one-storey FVD example with kN-mm → kN-m unit conversion. It is reference-only and cannot activate the project device scenario.')

    def selected_keys(self):
        return list(dict.fromkeys(k for iid in self.tree.selection() for k in self.item_keys.get(iid,[])))

    def assign(self):
        try:
            keys=self.selected_keys()
            if not keys:raise ValueError('Select a property group, object or solver segment first.')
            p=json.loads(self.parameters.get('1.0','end'));p['weight_reviewed']=self.weight.get()
            save_assignment(self.folder,keys,self.target.get(),p,self.citation.get(),self.active.get())
            self.reload();self.status.set(f'Saved {len(keys)} assignments. Rebuild the selected model before using an activated scenario. Inactive selections retain the baseline.')
        except Exception as exc:messagebox.showerror('Mapping needs review',str(exc),parent=self.win)

    def selection_details(self,_event=None):
        keys=self.selected_keys();self.details.delete('1.0','end')
        self.highlight_keys(keys)
        for key in keys[:3]:
            owner=next((r['key'] for r in self.data['solver_elements'] if key==f"SOLVER:{r['solver_tag']}"),key)
            r=self.bykey.get(owner,{})
            prop=next((p for p in self.data['properties'] if p['property']==r.get('property') and p['category']==r.get('category')), {})
            self.details.insert('end',json.dumps(dict(element=r,source_properties=prop),indent=2,ensure_ascii=False)+'\n')
        self.details.insert('end','\nNumeric source properties are imported. RC template confinement and device parameters are not automatically calibrated. Select a formulation and open its reference; see Excel Library parameters for value-level status.')

    def draw_source(self):
        from mpl_toolkits.mplot3d.art3d import Line3DCollection
        from matplotlib.ticker import MaxNLocator
        self.axis.clear();self.xyz={str(n['opensees_node_tag']):n['coordinates_m'] for n in self.data['nodes']}
        paths=[]
        for r in self.data['elements']:
            points=[self.xyz[str(n)] for n in r['node_tags'] if str(n) in self.xyz]
            if len(points)>2:points.append(points[0])
            if len(points)>1:paths.append(points)
        if paths:self.axis.add_collection3d(Line3DCollection(paths,colors='#94a3b8',linewidths=.3,alpha=.45))
        self.selection_line=Line3DCollection([],colors='#d00080',linewidths=3);self.axis.add_collection3d(self.selection_line,autolim=False)
        if self.xyz:
            spans=[]
            for i in range(3):
                values=[p[i] for p in self.xyz.values()];lo=min(values);hi=max(values);pad=max(.5,(hi-lo)*.03)
                (self.axis.set_xlim,self.axis.set_ylim,self.axis.set_zlim)[i](lo-pad,hi+pad);spans.append(max(hi-lo,1))
            self.axis.set_box_aspect(spans)
        __import__('OpenSees_View_Controls_V134').apply_view(self.axis);self.axis.set(xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)')
        self.axis.xaxis.set_major_locator(MaxNLocator(nbins=3));self.axis.yaxis.set_major_locator(MaxNLocator(nbins=3));self.annotations=[]
        self.chart.draw_idle()

    def highlight_keys(self,keys):
        if not hasattr(self,'selection_line'):return
        paths=[]
        for key in keys:
            if key.startswith('NODE:'):
                point=self.xyz.get(key.split(':')[1])
                if point:
                    for i in range(3):
                        a=list(point);b=list(point);a[i]-=.3;b[i]+=.3;paths.append([a,b])
            else:
                if key.startswith('SOLVER:'):
                    r=next((r for r in self.data['solver_elements'] if key==f"SOLVER:{r['solver_tag']}"),{})
                else:r=self.bykey.get(key,{})
                points=[self.xyz[str(n)] for n in r.get('node_tags',[]) if str(n) in self.xyz]
                if len(points)>2:points.append(points[0])
                if len(points)>1:paths.append(points)
        self.selected_points=[point for path in paths for point in path]
        self.selection_line.set_segments(paths)
        for text in self.annotations:text.remove()
        self.annotations=[]
        if paths and keys:self.annotations.append(self.axis.text2D(.02,.98,f'{len(keys)} selected: '+', '.join(keys[:2]),transform=self.axis.transAxes,va='top',fontsize=8,color='#9b0058',clip_on=True))
        self.chart.draw_idle()

    def zoom_view(self,factor):
        for get,setter in [(self.axis.get_xlim3d,self.axis.set_xlim3d),(self.axis.get_ylim3d,self.axis.set_ylim3d),(self.axis.get_zlim3d,self.axis.set_zlim3d)]:
            lo,hi=get();middle=(lo+hi)/2;half=max(abs(hi-lo)*factor/2,.001)
            setter(middle-half,middle+half)
        self.chart.draw_idle()

    def scroll_zoom(self,event):
        if event.inaxes is self.axis:self.zoom_view(.8 if event.button=='up' else 1.25)

    def fit_points(self,points):
        if not points:return
        spans=[]
        for i,setter in enumerate((self.axis.set_xlim3d,self.axis.set_ylim3d,self.axis.set_zlim3d)):
            lo=min(p[i] for p in points);hi=max(p[i] for p in points);pad=max(.5,(hi-lo)*.08)
            setter(lo-pad,hi+pad);spans.append(hi-lo+2*pad)
        self.axis.set_box_aspect(spans);self.chart.draw_idle()

    def fit_model(self):
        self.fit_points(list(getattr(self,'xyz',{}).values()))

    def fit_selection(self):
        self.fit_points(self.selected_points)

    def set_camera(self,elev,azim):
        self.axis.view_init(elev=elev,azim=azim);self.chart.draw_idle()

    def highlight_inline_id(self):
        if not hasattr(self,'data'):return
        value=self.id_value.get().strip();kind=self.id_kind.get()
        if kind=='OpenSees node':keys=['NODE:'+value]
        elif kind=='OpenSees solver element':keys=['SOLVER:'+value]
        else:keys=[r['key'] for r in self.data['elements'] if r['etabs_object']==value]
        self.highlight_keys(keys)

    def reference(self):
        row=next(r for r in library() if r['name']==self.target.get())
        if row['source'].startswith('https://'):webbrowser.open(row['source'])

    def highlight(self):
        from urllib.parse import urlencode
        keys=self.selected_keys()
        if not keys:return
        key=keys[0];kind='solver' if key.startswith('SOLVER:') else 'object';value=key.split(':')[1]
        path=self.folder/'OpenSees_Element_Connectivity_3D.html'
        if path.is_file():webbrowser.open(path.resolve().as_uri()+'?'+urlencode(dict(idKind=kind,idValue=value)))

    def excel(self):
        import os
        try:os.startfile(export_excel(self.folder))
        except Exception as exc:messagebox.showerror('Excel audit',str(exc),parent=self.win)


def launch(parent,folder):return MappingGUI(parent,folder)


def show_parameter_sources(parent):
    from OpenSees_Mapping_Audit_V125 import parameter_sources
    from OpenSees_Research_UI_V123 import scrollable_form
    win=tk.Toplevel(parent);win.title('Material parameter values and citation status')
    outer=scrollable_form(win,min_width=1150)
    ttk.Label(outer,text='A cited constitutive model does not validate numerical project inputs. Values below retain their actual source status.',wraplength=1050).pack(anchor='w')
    text=tk.Text(outer,width=140,height=32,wrap='word');text.pack(fill='both',expand=True)
    for row in parameter_sources():
        text.insert('end',f"{row['family']} / {row['parameter']}: {row['value'] if row['value'] is not None else 'REQUIRED'} {row['unit']}\n{row['status']}\n{row['source']}\n\n")
    text.configure(state='disabled')
    return win


def show_load_audit(parent,folder):
    import os
    from OpenSees_Research_UI_V123 import scrollable_form
    data=collect(folder);win=tk.Toplevel(parent);win.title('Current ETABS source and assembled OpenSees load audit')
    outer=scrollable_form(win,min_width=1050)
    ttk.Label(outer,text='Current source-to-OpenSees load transfer',font=('Segoe UI',15,'bold')).pack(anchor='w')
    report=data['assembly'];text=tk.Text(outer,height=28,wrap='word');text.pack(fill='both',expand=True)
    text.insert('end','SOURCE EDB\n'+str(data['source_edb'])+'\n\n')
    text.insert('end','ASSEMBLED MODEL\n'+json.dumps({key:report.get(key) for key in ('elastic_assembled','assembly_errors','total_downward_load_kN','active_horizontal_seismic_weight_kN','gravity_by_pattern_kN')},indent=2)+'\n\n')
    text.insert('end','The assembled export integrates source frame/area loads and geometric self-weight using source pattern multipliers. The topology-only preview is a separate audit. Compare reactions, source weight conventions and mass against ETABS.\n\n')
    text.insert('end','WARNINGS\n'+'\n'.join(report.get('warnings',[])))
    bar=ttk.Frame(outer);bar.pack(fill='x',pady=5)
    ttk.Button(bar,text='Populate / open Excel audit',command=lambda:os.startfile(export_excel(folder))).pack(side='left')
    ttk.Button(bar,text='Property and individual-element mapping',command=lambda:launch(win,folder)).pack(side='left',padx=5)
    ttk.Button(bar,text='3D loads with ID highlight',command=lambda:os.startfile(Path(folder)/'OpenSees_Load_Assignment_3D.html')).pack(side='left')
    ttk.Button(bar,text='Copy text',command=lambda:(win.clipboard_clear(),win.clipboard_append(text.get('1.0','end-1c')))).pack(side='left')
    export_excel(folder)
    return win
