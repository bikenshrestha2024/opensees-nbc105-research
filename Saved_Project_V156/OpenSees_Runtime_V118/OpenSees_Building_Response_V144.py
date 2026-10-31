"""Recorded current-building trial plots; no invented fiber stresses or elastic baseline."""
from pathlib import Path
import csv,re

def figure(history,tracked='recorded member'):
    from matplotlib.figure import Figure
    with Path(history).open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    if not rows:raise ValueError('History has no recorded rows')
    fig=Figure(figsize=(12,8),layout='constrained');axes=fig.subplots(2,2);keys=list(rows[0]);roof=max((k for k in keys if re.match(r'Storey_\d+_UX_m$',k)),key=lambda k:int(k.split('_')[1]));time=[float(r['time_s']) for r in rows]
    for key,label in [(roof,'X'),(roof.replace('_UX_','_UY_'),'Y')]:axes[0,0].plot(time,[float(r[key])*1000 for r in rows],label=label)
    axes[0,0].set(title='Recorded roof response',xlabel='Time (s)',ylabel='Relative translation (mm)');axes[0,0].legend()
    def plot(ax,x,y,title,xlabel,ylabel,xfactor=1):
        if x in rows[0] and y in rows[0]:ax.plot([float(r[x])*xfactor for r in rows],[float(r[y]) for r in rows],lw=.8)
        else:ax.text(.08,.5,'Not recorded in this run; rerun V144 to capture\nselected member / section response.',transform=ax.transAxes)
        ax.set(title=title,xlabel=xlabel,ylabel=ylabel)
    plot(axes[0,1],roof,'selected_frame_Mz_kNm','Selected member end Mz vs roof Ux','Roof Ux (mm)','Local Mz (kN m)',1000)
    plot(axes[1,0],'section_kappa_z_1_per_m','selected_frame_Mz_kNm','Section-end curvature / moment','Curvature z (1/m)','End Mz (kN m)')
    plot(axes[1,1],'section_axial_strain','selected_frame_N_kN','Section-end axial strain / force','Axial strain','End N (kN)')
    for ax in axes.flat:ax.grid(alpha=.25)
    fig.suptitle('CURRENT BUILDING exploratory | nonlinear frames / elastic walls | member '+str(tracked)+'\nRecorded response only; local end-force sign convention. No design PASS or material-fiber stress claim.')
    return fig

def plot_response(history,out,tracked='recorded member'):
    fig=figure(history,tracked)
    for ext in ('png','pdf'):fig.savefig(Path(out)/('Building_Response_V144.'+ext),dpi=150)
    return fig

def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk
    from OpenSees_Research_UI_V123 import embed_figures
    win=tk.Toplevel(parent);win.title('Current building recorded nonlinear response');win.geometry('1200x820');files=sorted(Path(folder).rglob('Building_Nonlinear_history.csv'));value=tk.StringVar(value=str(files[-1]) if files else '');bar=ttk.Frame(win);bar.pack(fill='x');ttk.Combobox(bar,textvariable=value,values=[str(p) for p in files],width=120,state='readonly').pack(side='left',fill='x',expand=True);body=ttk.Frame(win);body.pack(fill='both',expand=True)
    def refresh():
        for child in body.winfo_children():child.destroy()
        if value.get():embed_figures(body,[('Recorded building response',plot_response(value.get(),Path(value.get()).parent))])
        else:ttk.Label(body,text='Run step 8 on your current building first. No building response has been invented.').pack()
    ttk.Button(bar,text='Plot / export PNG PDF',command=refresh).pack(side='left');refresh();return win
