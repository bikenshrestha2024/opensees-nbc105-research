"""Complete history inspection, with paged data and coherent rigid-floor playback."""
from pathlib import Path
import csv,json,math,time
import numpy as np


def envelope_points(x,y,max_points=4000):
    """Display decimation preserving every bin's extrema; original data stay intact."""
    x=np.asarray(x,float);y=np.asarray(y,float)
    if len(x)<=max_points:return x,y
    ids={0,len(x)-1}
    for block in np.array_split(np.arange(len(x)),max(1,max_points//2)):
        ids.add(int(block[np.argmin(y[block])]))
        ids.add(int(block[np.argmax(y[block])]))
    ids=sorted(ids);return x[ids],y[ids]


def floor_snapshot(data,stories,row):
    """Small-rotation floor motion; interpolate point motions between levels."""
    groups=sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2])
    by_node={int(s['node']):s['story_name'] for s in stories}
    if any(int(g['master_tag']) not in by_node for g in groups):raise ValueError('History masters do not match this geometry')
    out={};base=float(data['base_z_m'])
    for n,xyz in data['nodes'].items():
        z=float(xyz[2]);i=next((j for j,g in enumerate(groups) if g['master_xyz'][2]>=z-1e-7),len(groups)-1)
        upper=groups[i];lower=groups[i-1] if i else None;loz=lower['master_xyz'][2] if lower else base
        w=max(0.,min(1.,(z-loz)/(upper['master_xyz'][2]-loz)))
        def at(g):
            if g is None:return [0.,0.]
            name=by_node[int(g['master_tag'])];theta=float(row.get(name+'_RZ_rad',0.))
            return [float(row[name+'_UX_m'])-(xyz[1]-g['master_xyz'][1])*theta,float(row[name+'_UY_m'])+(xyz[0]-g['master_xyz'][0])*theta]
        hi=at(upper);lo=at(lower);theta=(1-w)*(float(row.get(by_node[int(lower['master_tag'])]+'_RZ_rad',0.)) if lower else 0.)+w*float(row.get(by_node[int(upper['master_tag'])]+'_RZ_rad',0.))
        out[str(n)]=[(1-w)*lo[a]+w*hi[a] for a in range(2)]+[0.,0.,0.,theta]
    return out


def find_geometry(history):
    history=Path(history)
    # Prefer selected-run configuration to a coincidental ancestor export.
    configs=list(history.parent.glob('*Time_History_RunConfig*.json'))
    candidates=[]
    for p in configs:
        try:
            model_path=Path(json.loads(p.read_text(encoding='utf-8-sig'))['model_script'])
            if not model_path.is_absolute():model_path=p.parent/model_path
            candidates.append(model_path.parent)
        except (ValueError,KeyError,OSError):pass
    candidates.extend(history.parents)
    for folder in dict.fromkeys(candidates):
        payload=folder/'OpenSees_Complete_Model_Data_V118.json';masters=folder/'OpenSees_Complete_Story_Masters_V118.csv'
        if payload.is_file() and masters.is_file():
            data=json.loads(payload.read_text(encoding='utf-8-sig'))
            with masters.open(encoding='utf-8-sig',newline='') as f:stories=[dict(node=int(r['master_node_tag']),story_name=r['story_name']) for r in csv.DictReader(f)]
            return data,stories,payload
    raise FileNotFoundError('No matching model payload and story-master CSV. Select an assembled-model JSON in the playback window.')


def playback(parent,history):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from bisect import bisect_left
    with Path(history).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if not rows:raise ValueError('Empty history')
    win=tk.Toplevel(parent);win.title('Recorded floor-motion playback — '+Path(history).name);win.geometry('1150x820')
    bar=ttk.Frame(win);bar.pack(fill='x');status=tk.StringVar();amount=tk.DoubleVar(value=20.);speed=tk.DoubleVar(value=1.);cursor=tk.DoubleVar(value=0.)
    fig=Figure(layout='constrained');ax=fig.add_subplot(projection='3d');chart=FigureCanvasTkAgg(fig,master=win)
    state=dict(playing=False,job=None,data=None,stories=None,edges=[],deformed=None,highlight=None,frame=0)
    levelvar=tk.StringVar(value='All storeys');typevar=tk.StringVar(value='All types')
    times=[float(r['time_s']) for r in rows]
    def pause():
        state['playing']=False
        if state['job'] is not None:win.after_cancel(state['job']);state['job']=None
    def draw(value=None):
        if state['data'] is None:return
        try:scale=float(amount.get());index=max(0,min(len(rows)-1,int(float(cursor.get()))))
        except (ValueError,tk.TclError):return
        if not math.isfinite(scale) or scale<=0:return
        d=state['data'];u=floor_snapshot(d,state['stories'],rows[index]);state['displacements']=u;edges=state['edges']
        segments=[[[v+scale*u[str(n)][a] for a,v in enumerate(d['nodes'][str(n)])] for n in edge] for edge in edges]
        items=d['frames']+d['shells'];levels=sorted(d['diaphragms'],key=lambda g:g['master_xyz'][2])
        ids=[]
        for j,e in enumerate(items):
            mid=sum(d['nodes'][str(n)][2] for n in e['nodes'])/len(e['nodes']);level=next((g['storey_number'] for g in levels if g['master_xyz'][2]>=mid-1e-7),levels[-1]['storey_number'])
            if (typevar.get()=='All types' or e.get('category','Other')==typevar.get()) and (levelvar.get()=='All storeys' or str(level)==levelvar.get()):ids.append(j)
        state['deformed'].set_segments([segments[j] for j in ids]);state['source'].set_segments([[d['nodes'][str(n)] for n in edges[j]] for j in ids]);state['visible_points']=[p for j in ids for p in segments[j]];state['frame']=index
        status.set(f"t={times[index]:.5f} s | sample {index+1}/{len(rows)} | scale x{scale:g} | {state.get('run_status','legacy metadata unavailable')}")
        if ident.get().strip():highlight()
        chart.draw_idle()
    def setup(data,stories,path):
        meta=Path(str(history)+'.metadata.json')
        if meta.is_file():
            import hashlib
            metadata=json.loads(meta.read_text(encoding='utf-8-sig'));expected=metadata.get('model_data_sha256');state['run_status']=metadata.get('status','unknown')
            if expected and hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected:raise ValueError('Geometry fingerprint differs from the selected history run. Select its original unchanged model payload.')
        floor_snapshot(data,stories,rows[0]);state.update(data=data,stories=stories)
        edges=[e['nodes']+(e['nodes'][:1] if len(e['nodes'])>2 else []) for e in data['frames']+data['shells']];state['edges']=edges
        ax.clear();state['source']=Line3DCollection([[data['nodes'][str(n)] for n in e] for e in edges],colors='gray',alpha=.22,linewidths=.4);ax.add_collection3d(state['source'])
        levelbox['values']=['All storeys']+[str(g['storey_number']) for g in sorted(data['diaphragms'],key=lambda g:g['master_xyz'][2])];typebox['values']=['All types']+sorted({e.get('category','Other') for e in data['frames']+data['shells']})
        state['deformed']=Line3DCollection([],colors='#bb2450',linewidths=.8);ax.add_collection3d(state['deformed'],autolim=False)
        pts=np.asarray(list(data['nodes'].values()));span=np.maximum(np.ptp(pts,axis=0),1.)
        for a,setter in enumerate((ax.set_xlim,ax.set_ylim,ax.set_zlim)):setter(float(pts[:,a].min()-span[a]*.15),float(pts[:,a].max()+span[a]*.15))
        __import__('OpenSees_View_Controls_V134').apply_view(ax)
        ax.set_box_aspect(span);ax.set(xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)',title='Rigid-floor lateral reconstruction; no member curvature or vertical deformation')
        state['home']=(ax.get_xlim(),ax.get_ylim(),ax.get_zlim());draw()
    def choose():
        path=filedialog.askopenfilename(parent=win,title='Select assembled model data JSON',filetypes=[('Model data','*Model_Data*.json')])
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8-sig'));master=Path(path).with_name('OpenSees_Complete_Story_Masters_V118.csv')
            with master.open(encoding='utf-8-sig',newline='') as f:stories=[dict(node=int(r['master_node_tag']),story_name=r['story_name']) for r in csv.DictReader(f)]
            setup(data,stories,path)
        except Exception as e:messagebox.showerror('Geometry',str(e),parent=win)
    def tick():
        if not state['playing']:return
        try:target=state['sim_start']+(time.perf_counter()-state['wall_start'])*max(.01,float(speed.get()))
        except (ValueError,tk.TclError):pause();return
        i=min(len(rows)-1,bisect_left(times,target));cursor.set(i);draw()
        if i==len(rows)-1:pause()
        else:state['job']=win.after(80,tick)
    def play():
        pause()
        if int(cursor.get())>=len(rows)-1:cursor.set(0)
        state.update(playing=True,sim_start=times[int(cursor.get())],wall_start=time.perf_counter());tick()
    def zoom(factor):
        for get,setter in ((ax.get_xlim,ax.set_xlim),(ax.get_ylim,ax.set_ylim),(ax.get_zlim,ax.set_zlim)):
            lo,hi=get();mid=(lo+hi)/2;setter(mid-(hi-lo)*factor/2,mid+(hi-lo)*factor/2)
        chart.draw_idle()
    def fit():
        for setter,lim in zip((ax.set_xlim,ax.set_ylim,ax.set_zlim),state.get('home',[])):setter(*lim)
        chart.draw_idle()
    ttk.Button(bar,text='Play',command=play).pack(side='left');ttk.Button(bar,text='Pause',command=pause).pack(side='left');ttk.Label(bar,text='Speed').pack(side='left');ttk.Entry(bar,textvariable=speed,width=6).pack(side='left')
    ttk.Label(bar,text='Scale').pack(side='left');ttk.Entry(bar,textvariable=amount,width=7).pack(side='left');ttk.Button(bar,text='Apply',command=draw).pack(side='left')
    for label,fn in [('Zoom +',lambda:zoom(.8)),('Zoom -',lambda:zoom(1.25)),('Fit',fit),('Select geometry',choose)]:ttk.Button(bar,text=label,command=fn).pack(side='left')
    filterbar=ttk.Frame(win);filterbar.pack(fill='x');idkind=tk.StringVar(value='OpenSees node');ident=tk.StringVar()
    ttk.Combobox(filterbar,textvariable=idkind,values=['OpenSees node','OpenSees element','ETABS FRAME','ETABS AREA'],state='readonly',width=23).pack(side='left');ttk.Entry(filterbar,textvariable=ident,width=15).pack(side='left')
    def highlight():
        d=state['data']
        if d is None:return
        if state['highlight'] is not None:
            try:state['highlight'].remove()
            except ValueError:pass
        tag=ident.get().strip();kind=idkind.get();segments=[]
        if kind=='OpenSees node' and tag in d['nodes']:
            physical=state.get('displacements',{}).get(tag,[0.]*6)
            from OpenSees_View_Controls_V134 import node_readout
            values=[physical[0],physical[1],None,None,None,physical[5] if len(physical)>5 and all(story['story_name']+'_RZ_rad' in rows[state['frame']] for story in state['stories']) else None]
            node_values.set(node_readout(tag,values,scope='Rigid-floor lateral reconstruction at the selected recorded time. Uz, Rx and Ry are unrecorded, not zeros.'))
            point=[v+float(amount.get())*physical[i] for i,v in enumerate(d['nodes'][tag])];delta=max(1.,np.ptp(np.asarray(list(d['nodes'].values()))[:,2]))*.005
            segments=[[[v-(delta if a==axis else 0.) for a,v in enumerate(point)],[v+(delta if a==axis else 0.) for a,v in enumerate(point)]] for axis in range(3)]
        else:
            items=d['frames']+d['shells']
            selected=[e for i,e in enumerate(items) if (kind=='OpenSees element' and tag==str(100001+i)) or (kind=='ETABS FRAME' and i<len(d['frames']) and tag==str(e['object'])) or (kind=='ETABS AREA' and i>=len(d['frames']) and tag==str(e['object']))]
            segments=[[d['nodes'][str(n)] for n in e['nodes']+(e['nodes'][:1] if len(e['nodes'])>2 else [])] for e in selected]
        state['highlight']=Line3DCollection(segments,colors='#6210b5',linewidths=4);ax.add_collection3d(state['highlight'],autolim=False);chart.draw_idle()
    node_values=tk.StringVar()
    ttk.Label(win,textvariable=node_values,wraplength=1140).pack(anchor='w')
    ttk.Button(filterbar,text='Highlight ID / show DOFs',command=highlight).pack(side='left')
    levelbox=ttk.Combobox(filterbar,textvariable=levelvar,state='readonly',width=13);levelbox.pack(side='left');levelbox.bind('<<ComboboxSelected>>',draw)
    typebox=ttk.Combobox(filterbar,textvariable=typevar,state='readonly',width=17);typebox.pack(side='left');typebox.bind('<<ComboboxSelected>>',draw)
    def fit_visible():
        pts=np.asarray(state.get('visible_points',[]))
        if not len(pts):return
        for a,setter in enumerate((ax.set_xlim,ax.set_ylim,ax.set_zlim)):
            lo=float(pts[:,a].min());hi=float(pts[:,a].max());pad=max(.1,(hi-lo)*.1);setter(lo-pad,hi+pad)
        chart.draw_idle()
    ttk.Button(filterbar,text='Fit filtered',command=fit_visible).pack(side='left')
    ttk.Scale(win,from_=0,to=max(0,len(rows)-1),variable=cursor,command=draw).pack(fill='x');ttk.Label(win,textvariable=status).pack(anchor='w')
    __import__('OpenSees_View_Controls_V134').camera_controls(win,ax,chart)
    chart.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(chart,win)
    chart.mpl_connect('scroll_event',lambda e:zoom(.8 if e.button=='up' else 1.25) if e.inaxes==ax else None)
    def close():pause();win.destroy()
    win.protocol('WM_DELETE_WINDOW',close)
    try:setup(*find_geometry(history))
    except Exception as e:status.set(str(e))
    win._playback_state=state;win._draw_frame=draw;return win


def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk,messagebox,filedialog
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
    folder=Path(folder);win=tk.Toplevel(parent);win.title('Time histories — full data, spectra, playback and timing');win.geometry('1250x850')
    top=ttk.Frame(win);top.pack(fill='x');choice=tk.StringVar();series=tk.StringVar();groupvar=tk.StringVar(value='All');search=tk.StringVar();page=tk.IntVar(value=1);info=tk.StringVar()
    files=ttk.Combobox(top,textvariable=choice,state='readonly',width=72);files.pack(side='left',fill='x',expand=True)
    fields=ttk.Combobox(top,textvariable=series,state='readonly',width=30);fields.pack(side='left');groups=ttk.Combobox(top,textvariable=groupvar,state='readonly',width=15);groups.pack(side='left')
    tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True);plot=ttk.Frame(tabs);tableframe=ttk.Frame(tabs);notes=tk.Text(tabs,wrap='none');perf=tk.Text(tabs,wrap='word')
    for f,title in [(plot,'Response / input plot'),(tableframe,'All numeric rows'),(notes,'Configurations / logs'),(perf,'Measured performance')]:tabs.add(f,text=title)
    fig=Figure(layout='constrained');ax=fig.add_subplot();chart=FigureCanvasTkAgg(fig,master=plot);chart.get_tk_widget().pack(fill='both',expand=True);NavigationToolbar2Tk(chart,plot)
    nav=ttk.Frame(tableframe);nav.pack(fill='x');ttk.Label(nav,text='Text filter').pack(side='left');ttk.Entry(nav,textvariable=search,width=35).pack(side='left');ttk.Label(nav,text='Page').pack(side='left');ttk.Entry(nav,textvariable=page,width=7).pack(side='left');ttk.Label(nav,textvariable=info).pack(side='left',padx=8)
    grid=ttk.Frame(tableframe);grid.pack(fill='both',expand=True);tree=ttk.Treeview(grid,show='headings');sy=ttk.Scrollbar(grid,command=tree.yview);sx=ttk.Scrollbar(grid,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set);grid.rowconfigure(0,weight=1);grid.columnconfigure(0,weight=1);tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
    state=dict(rows=[],paths={},keys=[],group=None)
    def selected_rows():
        token=search.get().strip().casefold();group=state['group']
        return [r for r in state['rows'] if (groupvar.get()=='All' or str(r.get(group,''))==groupvar.get()) and (not token or any(token in str(v).casefold() for v in r.values()))]
    def table():
        rows=selected_rows();pages=max(1,math.ceil(len(rows)/500))
        try:current=max(1,min(pages,int(page.get())))
        except (ValueError,tk.TclError):current=1
        page.set(current);tree.delete(*tree.get_children())
        for r in rows[(current-1)*500:current*500]:tree.insert('','end',values=[r.get(k,'') for k in state['keys']])
        info.set(f'{len(rows):,} matching / {len(state["rows"]):,} total rows; page {current}/{pages}')
    def draw(*unused):
        ax.clear();key=series.get();rows=selected_rows();group=state['group']
        subsets={str(r.get(group,'')) for r in rows} if group and groupvar.get()=='All' else {None}
        for label in sorted(subsets,key=str):
            xy=[]
            for i,r in enumerate(rows):
                if label is not None and str(r.get(group,''))!=label:continue
                try:xy.append((float(r.get('time_s',r.get('time',i))),float(r[key])))
                except (KeyError,ValueError,TypeError):pass
            if xy:
                x,y=envelope_points(*zip(*xy));ax.plot(x,y,lw=.8,label=label)
        if len(subsets)>1 and len(subsets)<=20:ax.legend()
        ax.set(title=choice.get(),xlabel='Time (s)' if rows and 'time_s' in rows[0] else 'Row / time',ylabel=key);ax.grid(alpha=.25);chart.draw_idle();table()
    def load(*unused):
        try:
            item=state['paths'][choice.get()]
            if isinstance(item,dict):
                from OpenSees_Input_Records_V130 import _read_peer_text_record
                values,dt,units=_read_peer_text_record(item['source_path']);factor=float(item['path_acceleration_factor_to_model_units'])
                rows=[dict(time_s=i*dt,source_acceleration=float(v),applied_acceleration_model_units=float(v)*factor) for i,v in enumerate(values)]
            else:
                with Path(item).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            keys=list(rows[0]) if rows else [];state.update(rows=rows,keys=keys,group=next((k for k in ('story','storey','story_name','story_id','node_tag','axis') if k in keys),None))
            tree.configure(columns=keys)
            for key in keys:tree.heading(key,text=key);tree.column(key,width=155,stretch=False)
            numeric=[]
            for key in keys:
                try:float(rows[0][key]);numeric.append(key)
                except (ValueError,TypeError):pass
            fields['values']=numeric;series.set(next((k for k in numeric if k not in ('time_s','time')),numeric[0] if numeric else ''));groups['values']=['All']+sorted({str(r[state['group']]) for r in rows}) if state['group'] else ['All'];groupvar.set('All');page.set(1);draw()
        except Exception as e:messagebox.showerror('History data',str(e),parent=win)
    def export():
        path=filedialog.asksaveasfilename(parent=win,defaultextension='.csv',title='Export all filtered rows')
        if path:
            from OpenSees_Timing_V130 import StageTimer
            timer=StageTimer(Path(path).parent,'Filtered history export')
            with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=state['keys']);writer.writeheader();writer.writerows(selected_rows())
            timer.finish('completed')
    def animate():
        item=state['paths'].get(choice.get())
        if isinstance(item,Path) and item.name.endswith('history.csv'):
            try:playback(win,item)
            except Exception as e:messagebox.showerror('Playback',str(e),parent=win)
        else:messagebox.showinfo('Playback','Select a response history CSV first.',parent=win)
    def spectrum():
        item=state['paths'].get(choice.get())
        if not isinstance(item,dict):messagebox.showinfo('Input spectrum','Select an INPUT component from the file list.',parent=win);return
        try:
            from NBC105_Spectrum_Scaling_V115 import response_spectrum_5pct
            from OpenSees_Input_Records_V130 import _read_peer_text_record
            values,dt,units=_read_peer_text_record(item['source_path']);acc=np.asarray(values,float)*(1. if units=='g' else 1./9.80665)*float(item['scale_factor'])
            periods=np.geomspace(.05,6.,80);sa=response_spectrum_5pct(acc,dt,periods)
            ax.clear();ax.plot(periods,sa,label='Applied component');ax.set(xlabel='Period (s)',ylabel='5% damped pseudo-acceleration Sa (g)',title='Input spectrum diagnostic; no automatic record matching');ax.grid(alpha=.25);ax.legend();chart.draw_idle();tabs.select(plot)
        except Exception as e:messagebox.showerror('Spectrum',str(e),parent=win)
    def refresh():
        old=choice.get();paths={str(p.relative_to(folder)):p for p in sorted(folder.rglob('*.csv')) if p.name.endswith('history.csv') or p.name.startswith(('Drift_','Floor_Edge_Drift_'))}
        for p in sorted(folder.rglob('*Input_Record_Audit*.csv')):
            paths[str(p.relative_to(folder))]=p
            try:
                with p.open(encoding='utf-8-sig',newline='') as f:
                    for r in csv.DictReader(f):paths[str(p.parent.relative_to(folder))+' / INPUT '+r['record_or_pair_id']+' / '+r['component']]=r
            except (OSError,KeyError):pass
        state['paths']=paths;files['values']=list(paths);notes.delete('1.0','end');perf.delete('1.0','end')
        for p in sorted(folder.rglob('*Time_History*')):
            if p.suffix.lower() in ('.json','.log','.txt'):notes.insert('end',str(p)+'\n'+p.read_text(encoding='utf-8-sig',errors='replace')+'\n\n')
        for p in sorted(folder.rglob('*Performance_V133.json')):perf.insert('end',str(p)+'\n'+p.read_text(encoding='utf-8-sig')+'\n\n')
        perf.insert('end','No fixed nonlinear/linear runtime multiplier is assumed. Select one earthquake pair first; compare measured model, eigenanalysis, solve and recording stages. XY and YX remain separate rebuilt cases. Adaptive nonlinear substeps add work. No time-step limit is relaxed.\n')
        if paths:choice.set(old if old in paths else next(iter(paths)));load()
        else:info.set('No saved histories / input audits. Refresh after a case finishes.')
    for label,fn in [('Previous',lambda:(page.set(max(1,page.get()-1)),table())),('Next',lambda:(page.set(page.get()+1),table())),('Apply filter / page',draw),('Export filtered rows',export)]:ttk.Button(nav,text=label,command=fn).pack(side='left')
    actions=ttk.Frame(win);actions.pack(fill='x')
    for label,fn in [('Refresh',refresh),('Animate selected history',animate),('Input response spectrum',spectrum)]:ttk.Button(actions,text=label,command=fn).pack(side='left')
    from OpenSees_Results_UI_V127 import history_summary
    ttk.Button(actions,text='Run summary X / Y',command=lambda:history_summary(win,folder)).pack(side='left')
    files.bind('<<ComboboxSelected>>',load);fields.bind('<<ComboboxSelected>>',draw);groups.bind('<<ComboboxSelected>>',draw);refresh()
    win._history_state=state;return win
