"""Dependency inventory, never automatic approval of physical calibration."""
from pathlib import Path
import json,hashlib,importlib.util,datetime

def inventory(folder):
    folder=Path(folder).resolve();name='OpenSees_Complete_Model_Config_V118.json'
    path=folder/name;cfg=json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    refs=['OpenSees_Complete_Model_Data_V118.json','OpenSees_Load_Conversion_Audit.json','OpenSees_Complete_Story_Masters_V118.csv',name,'OpenSees_Complete_Nonlinear_Model.py']
    files=[dict(file=n,exists=(folder/n).is_file()) for n in refs]
    material=cfg.get('nonlinear_materials_file')
    mp=Path(material) if material else None
    if mp and not mp.is_absolute():mp=folder/mp
    missing=[x['file'] for x in files if not x['exists']]
    if not mp or not mp.is_file():missing.append('Project nonlinear material definitions file')
    if not cfg.get('nonlinear_wall_fsam_tags'):missing.append('Project wall property-to-FSAM region tags')
    if cfg.get('nonlinear_parameters_reviewed') is not True:missing.append('Reviewed project reinforcement, confinement and cyclic parameters')
    modules={n:importlib.util.find_spec(n) is not None for n in ['openseespy','numpy','scipy','threadpoolctl','openpyxl','matplotlib']}
    return dict(created_at=datetime.datetime.now().astimezone().isoformat(),folder=str(folder),files=files,python_dependencies=modules,material_file=str(mp) if mp else None,wall_fsam_mappings=cfg.get('nonlinear_wall_fsam_tags',{}),blockers=missing,approval=False,scope='Dependency discovery only. Literature cards are reference inputs, not project reinforcement or accepted calibration.',next_steps=['Use literature profiles to inspect native commands and source parameters.','Enter actual frame bar layout and wall reinforcement/regions; export material definitions and map FSAM tags.','Run applicable member/wall cyclic comparisons, nonlinear initial modal audit, gravity and signed P-Delta checks.','Rebind the changed model as an UNAPPROVED draft; review evidence then save the model-bound checklist.'])

def launch(parent,folder):
    import tkinter as tk
    from tkinter import ttk
    report=inventory(folder);win=tk.Toplevel(parent);win.title('Nonlinear dependency preflight - available files and missing project inputs');win.geometry('1000x650')
    from tkinter.scrolledtext import ScrolledText
    box=ScrolledText(win,wrap='word');box.pack(fill='both',expand=True);box.insert('end',json.dumps(report,indent=2))
    def save():
        out=Path(folder)/'OpenSees_Analysis_Results'/'Nonlinear_Dependency_Preflight_V160.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf8')
    ttk.Button(win,text='Save dependency inventory (does not approve model)',command=save).pack(anchor='w')
    return win
