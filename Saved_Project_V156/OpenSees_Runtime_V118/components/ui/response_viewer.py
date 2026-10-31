"""Case-labelled deformation viewer with actual response readout and common cameras."""
from pathlib import Path
import json,math
import numpy as np


def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from OpenSees_View_Controls_V134 import camera_controls,apply_view,node_readout
    win=tk.Toplevel(parent);win.title('SLS / ULS deformation — case and node response');win.geometry('1250x850')
    paths=sorted(Path(folder).rglob('Deformation_*V132.json'));selected=tk.StringVar();top=ttk.Frame(win);top.pack(fill='x')
    box=ttk.Combobox(top,textvariable=selected,values=[str(p) for p in paths],state='readonly',width=110);box.pack(fill='x',expand=True)
    note=tk.StringVar();note_label=ttk.Label(win,textvariable=note,wraplength=1180,justify='left');note_label.pack(anchor='w')
    controls=ttk.Frame(win);controls.pack(fill='x');actions=ttk.Frame(win);actions.pack(fill='x');kind=tk.StringVar(value='OpenSees node');ident=tk.StringVar();scale=tk.DoubleVar(value=100.)
    ttk.Combobox(controls,textvariable=kind,values=['OpenSees node','OpenSees element','ETABS point','ETABS FRAME','ETABS AREA'],state='readonly',width=21).pack(side='left');ttk.Entry(controls,textvariable=ident,width=12).pack(side='left');ttk.Label(controls,text='Illustration scale').pack(side='left');ttk.Entry(controls,textvariable=scale,width=9).pack(side='left')
    message=tk.StringVar();ttk.Label(win,textvariable=message,wraplength=1180).pack(anchor='w')
    table=ttk.Treeview(win,columns=['State / case','Ux (m)','Uy (m)','Uz (m)','Rx (rad)','Ry (rad)','Rz (rad)'],show='headings',height=2)
    for k in table['columns']:table.heading(k,text=k);table.column(k,width=160,stretch=True)
    table.pack(fill='x')
    fig=Figure(figsize=(10,6),layout='constrained');ax=fig.add_subplot(projection='3d');chart=FigureCanvasTkAgg(fig,master=win)
    state=dict(base_segments=[],delta_segments=[],data=None,source=None,deformed=None,highlight=None,playing=False,frame=0,phase=1.,job=None,point_map={},payload=None,home=None)
    cache={}
    def read(path):
        path=str(path)
        if path not in cache:cache[path]=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        return cache[path]
    def resolved_tag():return state['point_map'].get(ident.get().strip(),'') if kind.get()=='ETABS point' else ident.get().strip()
    def dof(d,tag):
        values=d.get('displacements',{}).get(str(tag),[]);mask=d.get('dof_availability',[True]*len(values))
        return [values[i] if i<len(values) and i<len(mask) and mask[i] else None for i in range(6)]
    def show_node():
        d=state['data']
        if d is None:return
        tag=resolved_tag();table.delete(*table.get_children())
        if state['highlight'] is not None:
            try:state['highlight'].remove()
            except ValueError:pass
            state['highlight']=None
        if kind.get() in ('OpenSees node','ETABS point') and tag in d['nodes']:
            values=dof(d,tag);xyz=d['nodes'][tag];point=np.array(xyz)+float(scale.get())*state['phase']*np.array([v or 0. for v in values[:3]]);delta=max(1.,ax.get_zlim()[1]-ax.get_zlim()[0])*.005
            segments=[[point-np.eye(3)[a]*delta,point+np.eye(3)[a]*delta] for a in range(3)]
            state['highlight']=Line3DCollection(segments,colors='#c000a0',linewidths=3);ax.add_collection3d(state['highlight'],autolim=False)
            physical=[xyz[a]+(values[a] or 0.) for a in range(3)]
            message.set(node_readout(tag,values,physical,'Unscaled response values. MRSM values are non-concurrent CQC component envelopes; illustration is not a recorded history.'))
            for limit in ('SLS','ULS'):
                current=Path(selected.get());candidate=str(current).replace('_ULS','_'+limit).replace('_SLS','_'+limit)
                other=Path(candidate)
                if not other.is_file():
                    other=next((p for p in paths if p.name==Path(candidate).name),None)
                record=read(other) if other is not None and Path(other).is_file() else None
                vals=dof(record,tag) if record else [None]*6
                table.insert('','end',values=[limit+' / '+(record.get('response_case',Path(other).stem) if record else 'not available')]+['N/A' if v is None else f'{float(v):.7g}' for v in vals])
        else:
            payload=state['payload'];segments=[]
            if payload:
                items=payload['frames']+payload['shells']
                for i,e in enumerate(items):
                    if (kind.get()=='OpenSees element' and ident.get().strip()==str(100001+i)) or (kind.get()=='ETABS FRAME' and i<len(payload['frames']) and str(e['object'])==ident.get().strip()) or (kind.get()=='ETABS AREA' and i>=len(payload['frames']) and str(e['object'])==ident.get().strip()):segments.append([payload['nodes'][str(n)] for n in e['nodes']])
            state['highlight']=Line3DCollection(segments,colors='#c000a0',linewidths=3);ax.add_collection3d(state['highlight'],autolim=False);message.set('Choose a node for six-DOF values. Older files with only translations show N/A for unrecorded rotations.')
        chart.draw_idle()
    def draw(phase=None):
        if state['data'] is None:return
        try:amount=float(scale.get())
        except (ValueError,tk.TclError):return
        if not math.isfinite(amount) or amount<=0:return
        if phase is not None:state['phase']=phase
        segments=[base+amount*state['phase']*delta for base,delta in zip(state['base_segments'],state['delta_segments'])]
        state['deformed'].set_segments(segments);show_node();chart.draw_idle()
    def load(*unused):
        pause();d=read(selected.get());state.update(data=d,phase=1.,point_map={},payload=None);ax.clear()
        for ancestor in Path(selected.get()).parents:
            path=ancestor/'OpenSees_Complete_Model_Data_V118.json'
            if path.is_file():
                payload=read(path)
                if all(d['nodes'].get(k)==v for k,v in payload['nodes'].items()):state['payload']=payload
                topo=ancestor/'OpenSees_Element_Connectivity.json'
                if topo.is_file():state['point_map']={str(n['etabs_point_name']):str(n['opensees_node_tag']) for n in read(topo)['node_map']}
                break
        source=[[d['nodes'][str(n)] for n in e+(e[:1] if len(e)>2 else [])] for e in d['elements']]
        state['source']=Line3DCollection(source,colors='gray',alpha=.25,linewidths=.4);ax.add_collection3d(state['source']);state['deformed']=Line3DCollection([],colors='#bb2450',linewidths=.7);ax.add_collection3d(state['deformed'],autolim=False);state['highlight']=None
        state['base_segments']=[np.asarray(edge,dtype=float) for edge in source]
        state['delta_segments']=[np.asarray([[float(v or 0.) for v in d['displacements'].get(str(n),[0.,0.,0.])[:3]] for n in e+(e[:1] if len(e)>2 else [])]) for e in d['elements']]
        pts=np.asarray(list(d['nodes'].values()));span=np.maximum(np.ptp(pts,axis=0),1.)
        for a,setter in enumerate((ax.set_xlim,ax.set_ylim,ax.set_zlim)):setter(float(pts[:,a].min()-.1*span[a]),float(pts[:,a].max()+.1*span[a]))
        ax.set_box_aspect(span);apply_view(ax,view_choice.get());ax.set(xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)');state['home']=(ax.get_xlim(),ax.get_ylim(),ax.get_zlim());note.set(d.get('note','')+' | Animation interpolates 0–100% of this result; it is not earthquake time playback.');draw()
    def pause():
        state['playing']=False
        if state['job'] is not None:
            try:win.after_cancel(state['job'])
            except tk.TclError:pass
            state['job']=None
    def tick():
        if not state['playing']:return
        state['frame']=(state['frame']+1)%30;phase=(1-math.cos(2*math.pi*state['frame']/30))/2;progress.set(100*phase);draw(phase);chart.draw();state['job']=win.after(150,tick)
    def play():
        if not state['playing']:state['playing']=True;tick()
    def zoom(factor):
        for get,setter in ((ax.get_xlim,ax.set_xlim),(ax.get_ylim,ax.set_ylim),(ax.get_zlim,ax.set_zlim)):
            lo,hi=get();mid=(lo+hi)/2;setter(mid-(hi-lo)*factor/2,mid+(hi-lo)*factor/2)
        chart.draw_idle()
    def fit():
        for setter,limits in zip((ax.set_xlim,ax.set_ylim,ax.set_zlim),state.get('home') or []):setter(*limits)
        chart.draw_idle()
    for label,fn in [('Highlight / read node',show_node),('Apply scale',lambda:draw()),('Zoom +',lambda:zoom(.8)),('Zoom -',lambda:zoom(1.25)),('Fit',fit),('Play illustration',play),('Pause / final',lambda:(pause(),draw(1.)))]:ttk.Button(actions,text=label,command=fn).pack(side='left')
    view_choice=camera_controls(win,ax,chart)
    toolbar=ttk.Frame(win);toolbar.pack(side='bottom',fill='x');NavigationToolbar2Tk(chart,toolbar)
    chart.get_tk_widget().pack(fill='both',expand=True)
    progress=tk.DoubleVar(value=100.)
    def scrub(value):
        pause();draw(float(value)/100.)
    ttk.Label(actions,text='0-100%').pack(side='left');ttk.Scale(actions,from_=0,to=100,variable=progress,command=scrub,length=130).pack(side='left')
    win.bind('<Configure>',lambda e:note_label.configure(wraplength=max(450,e.width-24)) if e.widget==win else None,add='+')
    chart.mpl_connect('scroll_event',lambda e:zoom(.8 if e.button=='up' else 1.25) if e.inaxes==ax else None);box.bind('<<ComboboxSelected>>',load)
    win.bind('<Destroy>',lambda e:pause() if e.widget==win else None,add='+')
    win._response_state=state;win._response_ident=ident;win._response_highlight=show_node
    if paths:selected.set(str(paths[0]));load()
    else:note.set('No saved deformation files in this output tree. Run an analysis first.')
    return win
