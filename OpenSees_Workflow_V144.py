"""Numbered workflow and factual input inventory; no automatic calibration approval."""
from pathlib import Path
import json
STEPS=[('1 Export','01_START_ETABS_TO_OPENSEES.py','Select EDB and export folder. Export with load sets; verify load totals and source units.'),('2 Inputs','02_MODEL_INPUTS_AND_READINESS.py','Review inventory, source identity and missing evidence.'),('3 Gravity','03_GRAVITY.py','Compare story dead/live components and support reactions with ETABS. Inspect slab mesh convergence.'),('4 Modal','04_MODAL_ULS_SLS.py','Run Both. Review X/Y/Rz modes, cumulative mass, initial stiffness and damping band.'),('5 Static','05_EQUIVALENT_STATIC.py','Review adopted periods, spectra, eligibility, drift and signed eccentricity cases.'),('6 MRSM','06_RESPONSE_SPECTRUM.py','Run ULS then SLS; inspect CQC envelopes and force-only scale.'),('7 Linear history','07_LINEAR_TIME_HISTORY.py','Select one earthquake pair first; confirm g conversion once, scale and time step.'),('8 Building trial','08_BUILDING_NONLINEAR_TRIAL.py','Exploratory nonlinear frames with elastic walls; use short trial then longer records. Inspect actual recorded response, not portal-demo results.'),('9 Reviewed nonlinear','09_NONLINEAR_REVIEWED_MODEL.py','Requires project materials, reinforcement, FSAM mapping and nonlinear benchmarks. Literature specimen values alone do not establish calibration.')]
GUIDE={
'wall_nonlinear_materials_and_reinforcement_cited_calibrated':'Obtain wall thickness, web/boundary reinforcement ratios, bar grades, concrete strength, confinement and axial load from drawings/tests. Define ConcreteCM + SteelMPF + FSAM per wall region; benchmark cyclic force-drift and axial response against applicable experiments. Enter material file and property-to-FSAM tags in model config. Do not substitute specimen reinforcement for project data.',
'frame_concrete_and_rebar_materials_reviewed':'Read ETABS section dimensions/materials and project reinforcement schedules (bar count, diameter, cover, ties). Replace illustrative M35/Fe550 templates; verify stress units, confinement and cyclic parameters with tests/literature. Run section moment-curvature and a member cyclic benchmark.',
'is16700_initial_pdelta_plus_minus_cases_completed':'Use stability/case progression module to generate signed initial lateral PDelta cases. Solve both signs with stated gravity factors; save convergence and stability results for this exact model hash.',
'device_properties_cited_calibrated_or_devices_disabled':'If FVD/BRB is absent, document disabled scenario. Otherwise obtain manufacturer/test K,Cd,alpha or BRB core area, yield, hardening, overstrength and stroke limits; benchmark device response and check units.',
'rayleigh_damping_and_device_damping_not_double_counted':'Use nonlinear initial eigenperiods to calculate alphaM/betaK. Check modal damping over inspected modes and justify damping allocation with devices. Save coefficients, mode band and source.',
'single_element_and_wall_benchmark_checks_passed':'Run frame/member and wall cyclic tests with your selected constitutive parameters; compare strength, stiffness, pinching, degradation and energy. Attach actual benchmark output and acceptance rationale.',
'wall_opening_and_coupling_beam_mesh_reviewed':'Open 3D connectivity and wall-only view. Check each opening, pier, coupling beam, shared node and local axis against ETABS/drawings; perform mesh sensitivity.',
'area_and_frame_gravity_loads_reconciled_to_etabs':'Export ETABS story/pattern totals and reactions with matching gravity factors. Compare with Source load detail and slab formula workbook, including physical self-weight exactly once.',
'seismic_mass_reconciled_to_etabs_by_storey':'Export ETABS mass summary by story and diaphragm; compare independent total and directional masses with assembled ledger, including live-load fractions and roof treatment.',
'record_pair_units_scales_and_nbc_limits_reviewed':'Use record audit and site spectrum diagnostic. Confirm record units, dt, pair length and matching/scaling band; g-to-m/s2 factor is 9.80665 once, separate from motion scale.'}
def inventory(folder):
    folder=Path(folder);cfgpath=folder/'OpenSees_Complete_Model_Config_V118.json';cfg=json.loads(cfgpath.read_text(encoding='utf-8-sig')) if cfgpath.is_file() else {}
    facts={'folder':str(folder),'config_file':str(cfgpath),'configuration':cfg}
    for name,key in [('OpenSees_Complete_Export_Report_V118.json','assembly'),('OpenSees_Complete_Gravity_Check_V118.json','gravity')]:
        path=folder/name
        if path.is_file():facts[key]=json.loads(path.read_text(encoding='utf-8-sig'))
    data=folder/'OpenSees_Complete_Model_Data_V118.json'
    if data.is_file():
        d=json.loads(data.read_text(encoding='utf-8-sig'));facts['model_counts']={k:len(d.get(k,[])) for k in ['nodes','frames','shells','diaphragms']};facts['gravity_by_pattern_kN']=d.get('gravity_by_pattern_kN');facts['total_downward_load_kN']=d.get('total_downward_load_kN')
    from OpenSees_Readiness_GUI_V134 import available_evidence
    facts['available_evidence']=available_evidence(folder/'OpenSees_Complete_Nonlinear_Model.py');facts['how_to_obtain_missing_values']=GUIDE
    return facts

def workflow_status(folder):
    """File-presence indicators only: no claim of matching model or valid result."""
    root=Path(folder); out=root/'OpenSees_Analysis_Results'
    def present(p): return p.is_file()
    def candidates(pattern): return list(out.glob(pattern)) if out.is_dir() else []
    modal=[state for state in ('ULS','SLS') if present(out/('Modal_'+state)/'NBC105_Modal_V111.json')]
    mrsm=[state for state in ('ULS','SLS') if (out/('MRSM_'+state)).is_dir() and any((out/('MRSM_'+state)).glob('*.json'))]
    checks=[present(root/'OpenSees_Complete_Export_Report_V118.json'),present(root/'OpenSees_Complete_Model_Config_V118.json'),present(root/'OpenSees_Complete_Gravity_Check_V118.json'),bool(modal),bool(candidates('NBC105_ESM_Calculation_*.json')),bool(mrsm),bool(candidates('LTH_*/*Summary*.json')),bool(candidates('EXPLORATORY_*/*Summary*.json')),bool(candidates('NLTH_*/*Summary*.json'))]
    details={3:'saved modal states: '+(', '.join(modal) or 'none'),5:'saved MRSM state folders: '+(', '.join(mrsm) or 'none'),6:'summary file found does not guarantee completion',7:'summary file found does not guarantee completion; a short trial is not a complete history',8:'summary file found does not guarantee completion or approval'}
    return [(('SAVED FILE FOUND - VERIFY CURRENT MODEL AND STATUS' if found else 'NO MATCHING RESULT FILE FOUND'),details.get(i,'')) for i,found in enumerate(checks)]
def launch(parent=None,folder=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    win=tk.Toplevel(parent) if parent else tk.Tk();win.title('1–9 workflow | available inputs and how to obtain values');win.geometry('1100x800')
    path=tk.StringVar(value=str(folder or ''));bar=ttk.Frame(win);bar.pack(fill='x');ttk.Entry(bar,textvariable=path).pack(side='left',fill='x',expand=True)
    ttk.Button(bar,text='Select export',command=lambda:path.set(filedialog.askdirectory(parent=win))).pack(side='left')
    tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True)
    def page(title):
        frame=ttk.Frame(tabs);tabs.add(frame,text=title);text=tk.Text(frame,wrap='word');scroll=ttk.Scrollbar(frame,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);return text
    guide=page('1–9 run order')
    values=page('Available values / provenance');missing=page('Obtain missing values');missing.insert('end','\n\n'.join(k.replace('_',' ')+'\n'+v for k,v in GUIDE.items()))
    def refresh():
        if not path.get():return
        try:
            facts=inventory(path.get());values.delete('1.0','end');values.insert('end',json.dumps(facts,indent=2))
            statuses=workflow_status(path.get());guide.delete('1.0','end');guide.insert('end','Status indicates saved file presence only; verify provenance, completion, and the selected model. Linear time history is an optional comparison, not a prerequisite for nonlinear execution.\n\n'+'\n\n'.join(a+' — '+b+'\n'+statuses[i][0]+' | '+statuses[i][1]+'\n'+c for i,(a,b,c) in enumerate(STEPS)));return facts
        except Exception as exc:messagebox.showerror('Inventory',str(exc),parent=win)
    def export():
        facts=refresh()
        if facts:
            target=Path(path.get())/'Available_Inputs_And_Steps_V144.json';target.write_text(json.dumps(facts,indent=2),encoding='utf8');messagebox.showinfo('Saved',str(target),parent=win)
    ttk.Button(bar,text='Refresh available data',command=refresh).pack(side='left');ttk.Button(bar,text='Export inventory + steps',command=export).pack(side='left');refresh()
    if parent is None:win.mainloop()
    return win
