"""Readable force-polarity and accidental-eccentricity case selection."""
import re


def label_case(text):
    match=re.search(r'(SLS|ULS)_([XY])([+-])_E([+\-0])',str(text))
    if not match:return str(text)
    state,axis,polarity,ecc=match.groups();return state,polarity+axis,{'0':'centered e=0','+':'eccentricity +5% b','-':'eccentricity -5% b'}[ecc]


def profiles(parent,figures):
    import tkinter as tk
    from tkinter import ttk
    from OpenSees_Research_UI_V123 import embed_figures
    def compare():
        from OpenSees_Results_UI_V127 import esm_side_by_side
        folder=getattr(parent,'_esm_output_folder',None)
        if folder:esm_side_by_side(parent,folder)
    ttk.Button(parent,text='Side-by-side ULS / SLS comparison',command=compare).pack(anchor='w')
    selected=tk.StringVar();description=tk.StringVar();ttk.Label(parent,text='Force direction and eccentricity are independent: +X / -X / +Y / -Y specify the force; e specifies the signed 0.05 x perpendicular plan breadth. E0 is centered. Identical floor-force magnitudes can have different torsional moments.',wraplength=1150).pack(fill='x')
    plot=ttk.Frame(parent)
    mapping={}
    for state in ('SLS','ULS'):
        row=ttk.Frame(parent);row.pack(fill='x');ttk.Label(row,text=state,width=6).pack(side='left');host=ttk.Frame(row);host.pack(side='left',fill='x',expand=True);canvas=tk.Canvas(host,height=31,highlightthickness=0);scroll=ttk.Scrollbar(host,orient='horizontal',command=canvas.xview);canvas.configure(xscrollcommand=scroll.set);canvas.pack(fill='x');scroll.pack(fill='x');buttons=ttk.Frame(canvas);canvas.create_window((0,0),window=buttons,anchor='nw')
        for title,fig in figures:
            parsed=label_case(title)
            if not isinstance(parsed,tuple) or parsed[0]!=state:continue
            mapping[title]=(fig,parsed)
            def choose(title=title):
                fig,case=mapping[title];description.set(case[0]+' | Force '+case[1]+' | '+case[2]);embed_figures(plot,[(description.get(),fig)])
            ttk.Radiobutton(buttons,text=parsed[1]+' | '+parsed[2].replace('eccentricity ','e=').replace('centered ',''),value=title,variable=selected,command=choose).pack(side='left',padx=3)
        buttons.bind('<Configure>',lambda e,c=canvas:c.configure(scrollregion=c.bbox('all')))
    ttk.Label(parent,textvariable=description,font=('Segoe UI',11,'bold')).pack(anchor='w');plot.pack(fill='both',expand=True)
    if mapping:
        title=next(iter(mapping));selected.set(title);fig,case=mapping[title];description.set(case[0]+' | Force '+case[1]+' | '+case[2]);embed_figures(plot,[(description.get(),fig)])
    parent._case_mapping=mapping;return mapping
