"""Shared 3D orientation, camera controls and unscaled physical node readouts."""
import math
VIEWS={'Isometric':(27.5,45.),'Top (+Z)':(90.,-90.),'Bottom (-Z)':(-90.,-90.),'Front (-Y)':(0.,-90.),'Back (+Y)':(0.,90.),'Right (+X)':(0.,0.),'Left (-X)':(0.,180.)}


def apply_view(axis,name='Isometric'):
    elev,azim=VIEWS[name];axis.view_init(elev=elev,azim=azim)
    if hasattr(axis,'set_proj_type'):axis.set_proj_type('ortho')


def camera_controls(parent,axis,canvas):
    import tkinter as tk
    from tkinter import ttk
    row=ttk.Frame(parent);row.pack(fill='x');choice=tk.StringVar(value='Isometric')
    ttk.Label(row,text='3D view').pack(side='left');box=ttk.Combobox(row,textvariable=choice,values=list(VIEWS),state='readonly',width=22);box.pack(side='left')
    def change(*unused):apply_view(axis,choice.get());canvas.draw_idle()
    box.bind('<<ComboboxSelected>>',change);ttk.Button(row,text='Reset isometric',command=lambda:(choice.set('Isometric'),change())).pack(side='left');apply_view(axis);return choice


def node_readout(tag,values,coordinates=None,scope='Unscaled physical response'):
    names=['Ux','Uy','Uz','Rx','Ry','Rz'];parts=[]
    for i,name in enumerate(names):
        v=values[i] if i<len(values) else None
        parts.append(name+'='+('N/A (not recorded)' if v is None else f'{float(v):.7g} '+('m' if i<3 else 'rad')))
    xyz=' | deformed XYZ=('+', '.join(f'{float(v):.7g}' for v in coordinates[:3])+') m' if coordinates is not None else ''
    return 'Node '+str(tag)+' | '+' | '.join(parts)+xyz+'\n'+scope
