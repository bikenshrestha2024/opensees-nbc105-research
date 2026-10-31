"""Scrollable Tk forms and publication-sized figures. No engineering defaults."""

__release__ = '134'
from OpenSees_Timing_V130 import timed_outputs
from pathlib import Path
import tkinter as tk
from tkinter import ttk


def adaptive_id_ticks(axis, labels):
    """Locate actual categorical positions using the current visible range."""
    from matplotlib.ticker import Locator, FuncFormatter
    import math
    class VisibleIDs(Locator):
        def __call__(self):
            lo,hi=sorted(self.axis.get_view_interval())
            first=max(0,math.ceil(lo));last=min(len(labels)-1,math.floor(hi))
            if last<first:return []
            budget=max(2,int(axis.get_window_extent().width/65))
            step=max(1,math.ceil((last-first+1)/budget))
            return list(range(first,last+1,step))
    axis.xaxis.set_major_locator(VisibleIDs())
    axis.xaxis.set_major_formatter(FuncFormatter(lambda x,pos: labels[round(x)] if abs(x-round(x))<1e-6 and 0<=round(x)<len(labels) else ''))
    axis.tick_params(axis='x',labelrotation=45)


def _deformation_controls(parent, chart, fig):
    """Interpolate the converged static displacement, without inventing steps."""
    import math
    control=fig._deformation_control
    style=ttk.Style(parent);style.configure('PlotCompact.TButton',padding=(4,1),font=('Segoe UI',9))
    row=ttk.Frame(parent);row.pack(fill='x')
    scale=tk.StringVar(value=f"{control['scale']:.6g}")
    phase={'running':False,'value':1.,'frame':0}
    ttk.Label(row,text='Displacement scale ×').pack(side='left')
    ttk.Entry(row,textvariable=scale,width=10).pack(side='left')
    def draw(value=1.):
        try:
            amount=float(scale.get())
            if not math.isfinite(amount) or amount<=0:raise ValueError()
        except ValueError:return
        control['collection'].set_segments([xyz+amount*value*u for xyz,u in control['geometry']])
        phase['value']=value
        control['axis'].set_title(f'Gravity deformation | scale ×{amount:g} | interpolation {value:.0%}')
        if 'refresh_selection' in control:control['refresh_selection']()
        chart.draw_idle()
    def tick():
        if not phase['running']:return
        phase['frame']=(phase['frame']+1)%40
        draw((1-math.cos(2*math.pi*phase['frame']/40))/2)
        chart.draw();parent.after(150,tick)
    def play():
        if not phase['running']:phase['running']=True;tick()
    def stop():phase['running']=False;draw()
    ttk.Button(row,style='PlotCompact.TButton',text='Apply',command=lambda:draw()).pack(side='left')
    ttk.Button(row,style='PlotCompact.TButton',text='Play',command=play).pack(side='left')
    ttk.Button(row,style='PlotCompact.TButton',text='Pause / final state',command=stop).pack(side='left')
    def camera():control['axis'].view_init(elev=27.5,azim=45);chart.draw_idle()

    ids=ttk.Frame(parent);ids.pack(fill='x')
    kind=tk.StringVar(value='OpenSees node');value=tk.StringVar();message=tk.StringVar()
    ttk.Combobox(ids,textvariable=kind,values=['OpenSees node','OpenSees element','ETABS object','ETABS point'],state='readonly',width=19).pack(side='left')
    ttk.Entry(ids,textvariable=value,width=12).pack(side='left')
    from OpenSees_View_Controls_V134 import VIEWS,apply_view
    view=tk.StringVar(value='Isometric');box=ttk.Combobox(row,textvariable=view,values=list(VIEWS),state='readonly',width=14);box.pack(side='left',padx=6)
    box.bind('<<ComboboxSelected>>',lambda e:(apply_view(control['axis'],view.get()),chart.draw_idle()))
    def zoom(factor):
        ax=control['axis']
        for getter,setter in ((ax.get_xlim,ax.set_xlim),(ax.get_ylim,ax.set_ylim),(ax.get_zlim,ax.set_zlim)):
            lo,hi=getter();mid=(lo+hi)/2;setter(mid-(hi-lo)*factor/2,mid+(hi-lo)*factor/2)
        chart.draw_idle()
    ttk.Button(row,text='Zoom +',style='PlotCompact.TButton',command=lambda:zoom(.8)).pack(side='left')
    ttk.Button(row,text='Zoom -',style='PlotCompact.TButton',command=lambda:zoom(1.25)).pack(side='left')
    def highlight():
        tag=value.get().strip();points=[]
        if kind.get()=='ETABS point':tag=str(control['point_map'].get(tag,''))
        if kind.get() in ('OpenSees node','ETABS point'):
            point=control['node_xyz'].get(tag)
            if point is not None:points=[point,point]
        else:
            elements=[tag] if kind.get()=='OpenSees element' else [str(n) for key,ns in control['object_map'].items() if key.split(':',1)[-1]==tag for n in ns]
            segments=[control['element_xyz'][n] for n in elements if n in control['element_xyz']]
            control['highlight'].set_segments(segments)
        if points:
            import numpy as np
            physical=control.get('node_dof',{}).get(tag,[])
            amount=float(scale.get())
            displacement=np.array([(physical[i] if i<len(physical) and physical[i] is not None else 0.) for i in range(3)])
            point=np.array(points[0])+amount*phase['value']*displacement;delta=max(control['axis'].get_zlim())*.004
            control['highlight'].set_segments([[point-np.eye(3)[axis]*delta,point+np.eye(3)[axis]*delta] for axis in range(3)])
        elif kind.get() in ('OpenSees node','ETABS point'):control['highlight'].set_segments([])
        from OpenSees_View_Controls_V134 import node_readout
        if points:
            physical=control.get('node_dof',{}).get(tag,[])
            coordinates=[points[0][i]+(physical[i] if i<len(physical) and physical[i] is not None else 0.) for i in range(3)]
            message.set(node_readout(tag,physical,coordinates,'Gravity final response; readout is unscaled. Marker follows illustrated deformation.'))
        else:message.set('Element highlight uses source geometry; choose a node for its six DOF.')
        chart.draw_idle()
    ttk.Button(ids,style='PlotCompact.TButton',text='Highlight ID',command=highlight).pack(side='left')
    ttk.Button(ids,style='PlotCompact.TButton',text='Clear',command=lambda:(control['highlight'].set_segments([]),chart.draw_idle())).pack(side='left')
    ttk.Label(parent,textvariable=message,wraplength=1050,justify='left').pack(anchor='w')
    ttk.Label(row,text='Static interpolation',font=('Segoe UI',9)).pack(side='left',padx=6)
    control['refresh_selection']=highlight
    parent.bind('<Destroy>',lambda event:phase.update(running=False),add='+')


def copyable_log(parent, variable, height=8):
    """Mirror status updates in a selectable, copyable interface log."""
    box=ttk.LabelFrame(parent,text='Run log — select text or copy all');box.pack(fill='both',expand=True,pady=5)
    viewport=ttk.Frame(box);viewport.pack(fill='both',expand=True)
    text=tk.Text(viewport,height=height,wrap='none')
    sy=ttk.Scrollbar(viewport,orient='vertical',command=text.yview)
    sx=ttk.Scrollbar(viewport,orient='horizontal',command=text.xview)
    text.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
    text.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
    viewport.rowconfigure(0,weight=1);viewport.columnconfigure(0,weight=1)
    def update(*_):
        value=variable.get()
        if value:text.insert('end',value+'\n');text.see('end')
    variable.trace_add('write',update);update()
    def copy():text.clipboard_clear();text.clipboard_append(text.get('1.0','end-1c'))
    ttk.Button(box,text='Copy entire log',command=copy).pack(side='left')
    return text


def scrollable_form(window, padding=12, min_width=940):
    """Preserve readable fonts at 100–200% DPI; scroll instead of shrinking."""
    window.update_idletasks()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    # A nested Frame has no wm_minsize/geometry methods. Keep its owner geometry.
    if window == window.winfo_toplevel():
        window.minsize(min(640, sw-60), min(400, sh-100))
        window.geometry(f'{min(1280,sw-80)}x{min(900,sh-140)}')
    host=ttk.Frame(window);host.pack(fill='both',expand=True)
    canvas=tk.Canvas(host,highlightthickness=0)
    vy=ttk.Scrollbar(host,orient='vertical',command=canvas.yview)
    hx=ttk.Scrollbar(host,orient='horizontal',command=canvas.xview)
    canvas.configure(yscrollcommand=vy.set,xscrollcommand=hx.set)
    vy.grid(row=0,column=1,sticky='ns');hx.grid(row=1,column=0,sticky='ew')
    canvas.grid(row=0,column=0,sticky='nsew');host.rowconfigure(0,weight=1);host.columnconfigure(0,weight=1)
    body=ttk.Frame(canvas,padding=padding); item=canvas.create_window((0,0),window=body,anchor='nw')
    body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=max(min_width,e.width)))
    def wheel(event):
        current=window.winfo_containing(event.x_root,event.y_root)
        if current is not None and str(current).startswith(str(host)):
            canvas.yview_scroll(-int(event.delta/120),'units')
    window.bind('<MouseWheel>',wheel,add='+')
    return body


def embed_figures(parent, figures):
    """Compact controls, maximum responsive plot area, fixed navigation row."""
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
    for child in parent.winfo_children():child.destroy()
    ttk.Style(parent).configure('PlotCompact.TButton',padding=(4,1),font=('Segoe UI',9))
    notebook=ttk.Notebook(parent);notebook.pack(fill='both',expand=True)
    for title,fig in figures:
        tab=ttk.Frame(notebook);notebook.add(tab,text=title)
        tab.columnconfigure(0,weight=1);tab.rowconfigure(1,weight=1)
        controls=ttk.Frame(tab);controls.grid(row=0,column=0,sticky='ew')
        nav=ttk.Frame(tab);nav.grid(row=2,column=0,sticky='ew')
        chart=FigureCanvasTkAgg(fig,master=tab);widget=chart.get_tk_widget();widget.configure(width=600,height=450);widget.grid(row=1,column=0,sticky='nsew')
        toolbar=NavigationToolbar2Tk(chart,nav,pack_toolbar=False);toolbar.pack(side='left',fill='x',expand=True)
        if hasattr(fig,'_deformation_control'):
            _deformation_controls(controls,chart,fig)
            ax=fig._deformation_control['axis']
            legend=ax.get_legend()
            if legend:
                for label in legend.get_texts():label.set_fontsize(8)
            ax.set_position([.02,.02,.96,.94]);ax.set_box_aspect(ax.get_box_aspect(),zoom=1.2)
        def fit(fig=fig,chart=chart,widget=widget):
            width,height=widget.winfo_width(),widget.winfo_height()
            if width>200 and height>150:fig.set_size_inches(width/fig.dpi,height/fig.dpi,forward=False);chart.draw_idle()
        ttk.Button(nav,text='Fit',style='PlotCompact.TButton',command=fit).pack(side='right')
        widget.bind('<Map>',lambda e,fn=fit:fn(),add='+');chart.draw_idle()


@timed_outputs('Gravity figures and action pages','output')
def gravity_figures(payload, output, all_pages=False):
    """Show every end action in a paginated PDF; preview the critical 24 only.

    End signs are local resisting-force signs, not a continuous BMD. Sampling
    for the preview is explicitly ranked by maximum absolute end action.
    """
    import numpy as np
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.lines import Line2D
    out=Path(output); figures=[];paths=[]
    def new(title,xlabel,ylabel):
        f=Figure(figsize=(10,6.5),dpi=110,layout='constrained');ax=f.add_subplot()
        ax.set(title=title,xlabel=xlabel,ylabel=ylabel);ax.grid(alpha=.2,axis='both')
        return f,ax
    def save(fig,name):
        for ext in ('png','pdf'):
            p=out/(name+'.'+ext);fig.savefig(p,dpi=300,bbox_inches='tight');paths.append(p)
    nodes=payload['nodes'];bytag={n['tag']:n for n in nodes};rep=payload['report']
    f=Figure(figsize=(9,8),dpi=110,layout='constrained');ax=f.add_subplot(projection='3d')
    disp=max((max(abs(n[k]) for k in ('ux_m','uy_m','uz_m')) for n in nodes),default=0)
    span=max(max(n[k] for n in nodes)-min(n[k] for n in nodes) for k in ('x_m','y_m','z_m'))
    scale=max(1.,.12*span/disp) if disp else 1.
    animated=[];undeformed=[]
    for e in payload['elements']:
        ns=[bytag[n] for n in e['nodes'] if n in bytag]
        if len(ns)<2:continue
        if len(ns)>2:ns=ns+[ns[0]]
        xyz=np.array([[n[k+'_m'] for k in ('x','y','z')] for n in ns]);u=np.array([[n['u'+k+'_m'] for k in ('x','y','z')] for n in ns])
        undeformed.append(xyz);animated.append((xyz,u))
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    ax.add_collection3d(Line3DCollection(undeformed,colors='#94a3b8',linewidths=.35,alpha=.5))
    deformed=Line3DCollection([xyz+scale*u for xyz,u in animated],colors='#b2182b',linewidths=.5)
    ax.add_collection3d(deformed)
    for index,key in enumerate(('x_m','y_m','z_m')):
        values=[n[key] for n in nodes];lo=min(values);hi=max(values);pad=max((hi-lo)*.05,.5)
        (ax.set_xlim,ax.set_ylim,ax.set_zlim)[index](lo-pad,hi+pad)
    ax.set(xlabel='Global X (m)',ylabel='Global Y (m)',zlabel='Elevation Z (m)',title=f'Gravity deformation | displacement scale ×{scale:.0f}')
    ax.legend(handles=[Line2D([],[],color='#94a3b8',label='Undeformed'),Line2D([],[],color='#b2182b',label='Deformed (magnified)')],loc='upper left')
    ax.set_box_aspect([max(n[k] for n in nodes)-min(n[k] for n in nodes) for k in ('x_m','y_m','z_m')])
    from OpenSees_View_Controls_V134 import apply_view
    apply_view(ax)
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4));ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    highlight=Line3DCollection([],colors='#ec008c',linewidths=4)
    ax.add_collection3d(highlight,autolim=False)
    object_map={};point_map={}
    import json
    model_folder=Path(payload.get('model_script','')).parent
    try:
        object_map=json.loads((model_folder/'OpenSees_Complete_Element_Map_V118.json').read_text(encoding='utf-8-sig'))
        topology=json.loads((model_folder/'OpenSees_Element_Connectivity.json').read_text(encoding='utf-8-sig'))
        point_map={str(n['etabs_point_name']):n['opensees_node_tag'] for n in topology['node_map']}
    except (OSError,ValueError,KeyError):pass
    fig_control={'axis':ax,'geometry':animated,'collection':deformed,'scale':scale,'highlight':highlight,
                 'node_xyz':{str(n['tag']):[n[k] for k in ('x_m','y_m','z_m')] for n in nodes},
                 'element_xyz':{str(e['tag']):[[bytag[n][k] for k in ('x_m','y_m','z_m')] for n in e['nodes'] if n in bytag] for e in payload['elements']},
                 'object_map':object_map,'point_map':point_map}
    fig_control['node_dof']={str(n['tag']):[n.get(k) for k in ('ux_m','uy_m','uz_m','rx_rad','ry_rad','rz_rad')] for n in nodes}
    f._deformation_control=fig_control
    figures.append(('Deformation',f));save(f,'Gravity_Deformation_V123')
    f,ax=new('Vertical support reactions under gravity','Support order (see Excel for node tags)','Global reaction Rz (kN)')
    reactions=payload['reactions'];x=np.arange(len(reactions));ax.bar(x,[r['rz_kN'] for r in reactions],color='#2166ac',label='Upward support reaction')
    adaptive_id_ticks(ax,[str(r['node_tag']) for r in reactions])
    ax.set_xlabel('OpenSees support NODE tag (labels adapt to zoom)');ax.legend()
    figures.append(('Reactions',f));save(f,'Gravity_Reactions_V123')
    f,ax=new('Vertical displacement envelope (not tracked member shortening)','Minimum vertical displacement Uz (mm)','Elevation Z (m)')
    floors={}
    for n in nodes:floors.setdefault(round(n['z_m'],5),[]).append(n['uz_m']*1000)
    heights=sorted(floors);ax.plot([min(floors[z]) for z in heights],heights,color='#762a83',lw=1.5,label='Most downward Uz at each elevation');ax.legend()
    figures.append(('Shortening',f));save(f,'Gravity_Shortening_V123')
    # Continuous vertical frame lines avoid switching the governing node at
    # every mesh elevation. Includes bending-induced vertical displacement;
    # N L / EA is a separate pure-axial benchmark, not an identity here.
    import csv
    tracks={}
    for e in payload['elements']:
        if len(e['nodes'])!=2:continue
        a,b=[bytag.get(tag) for tag in e['nodes']]
        if a is None or b is None:continue
        if abs(a['x_m']-b['x_m'])<1e-6 and abs(a['y_m']-b['y_m'])<1e-6:
            key=(round(a['x_m'],6),round(a['y_m'],6))
            tracks.setdefault(key,{})[a['tag']]=a;tracks[key][b['tag']]=b
    f,ax=new('Tracked vertical frame-line displacements','Uz relative to lowest tracked node (mm)','Elevation Z (m)')
    ranked=sorted(tracks.items(),key=lambda item:min(n['uz_m'] for n in item[1].values()))
    profile_rows=[]
    for index,(xy,track) in enumerate(ranked):
        ordered=sorted(track.values(),key=lambda n:n['z_m']);base=ordered[0]
        if index<6:ax.plot([(n['uz_m']-base['uz_m'])*1000 for n in ordered],[n['z_m'] for n in ordered],label=f'X={xy[0]:g}, Y={xy[1]:g} m')
        for n in ordered:profile_rows.append(dict(x_m=xy[0],y_m=xy[1],node_tag=n['tag'],elevation_m=n['z_m'],relative_Uz_mm=(n['uz_m']-base['uz_m'])*1000))
    if profile_rows:
        path=out/'Gravity_Tracked_Vertical_Lines_V124.csv'
        with path.open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(profile_rows[0]));writer.writeheader();writer.writerows(profile_rows)
        paths.append(path);ax.legend(fontsize=8)
        figures.append(('Tracked vertical lines',f));save(f,'Gravity_Tracked_Vertical_Lines_V124')
    f,ax=new('Vertical equilibrium of the assembled gravity load state','Quantity','Vertical load (kN)')
    ax.bar(['Applied downward load','Summed upward reactions'],[rep['applied_vertical_load_kN'],rep['support_vertical_reaction_kN']],color=['#e69f00','#009e73'])
    ax.text(.5,.93,f"Relative imbalance = {rep['equilibrium_error_percent']:.3g}%",transform=ax.transAxes,ha='center')
    figures.append(('Equilibrium',f));save(f,'Gravity_Equilibrium_V123')
    records=payload.get('local_forces',[])
    pairs=[('N_i_kN','N_j_kN','Axial end action N','kN'),('Vy_i_kN','Vy_j_kN','Local shear Vy','kN'),('Vz_i_kN','Vz_j_kN','Local shear Vz','kN'),('T_i_kNm','T_j_kNm','Torsional end action T','kN·m'),('My_i_kNm','My_j_kNm','Local bending end action My','kN·m'),('Mz_i_kNm','Mz_j_kNm','Local bending end action Mz','kN·m')]
    def actions(rows,pair,note):
        ki,kj,title,unit=pair;fig,axis=new(title+' | '+note,'OpenSees solver ELEMENT tag',f'{title} ({unit})')
        x=np.arange(len(rows));axis.bar(x-.19,[q[ki] for q in rows],.38,label='End i',color='#2166ac');axis.bar(x+.19,[q[kj] for q in rows],.38,label='End j',color='#e69f00')
        adaptive_id_ticks(axis,[str(q['tag']) for q in rows]);axis.axhline(0,color='black',lw=.6);axis.legend(ncol=2)
        fig.supxlabel('Local resisting-force sign convention. End actions only; not a continuous member diagram.',fontsize=9)
        return fig
    for pair in pairs:
        if not records:continue
        ranked=sorted(records,key=lambda q:max(abs(q[pair[0]]),abs(q[pair[1]])),reverse=True)[:24]
        fig=actions(ranked,pair,'24 largest absolute end actions');figures.append((pair[2],fig));save(fig,'Gravity_Critical_'+pair[0]+'_V123')
    pdf=out/('Gravity_All_Local_End_Actions_V123.pdf' if all_pages else 'Gravity_Critical_Local_End_Actions_V123.pdf')
    with PdfPages(pdf) as document:
        for pair in pairs:
            selected=records if all_pages else sorted(records,key=lambda q:max(abs(q[pair[0]]),abs(q[pair[1]])),reverse=True)[:24]
            for start in range(0,len(selected),24):
                fig=actions(selected[start:start+24],pair,(f'elements {start+1}–{min(start+24,len(selected))} of {len(selected)}' if all_pages else '24 critical elements; full results in Excel'))
                document.savefig(fig,bbox_inches='tight');fig.clear()
    paths.append(pdf)
    return figures,paths,scale
