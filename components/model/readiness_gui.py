"""Model-bound readiness drafts and transparent missing prerequisites."""
from pathlib import Path
import json,hashlib


def prepare(model_script,template=None):
    model=Path(model_script).resolve()
    if not model.is_file():raise FileNotFoundError('Select an existing nonlinear model-builder script first')
    from OpenSees_Nonlinear_Time_History_NBC105_V116 import _require_nonlinear_readiness
    keys=next(c for c in _require_nonlinear_readiness.__code__.co_consts if isinstance(c,tuple) and c and c[0]=='etabs_topology_and_story_mapping_reviewed')
    data=dict(schema='OpenSees_NLTHA_Readiness_V134',model_script=str(model),model_script_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),approved_for_nltha=False,checks=dict.fromkeys(keys,False),evidence={})
    path=model.with_name('OpenSees_Model_Readiness_Draft_'+model.stem+'_V134.json')
    if not path.exists():path.write_text(json.dumps(data,indent=2),encoding='utf-8')
    return path


def available_evidence(model_script):
    """Inventory saved facts; presence never certifies review or calibration."""
    model=Path(model_script).resolve();folder=model.parent;out=folder/'OpenSees_Analysis_Results';result={}
    def add(key,paths,note):
        found=[str(p.resolve()) for p in paths if p.is_file()]
        if found:result[key]='AVAILABLE FOR REVIEW: '+note+' | '+'; '.join(found)
    add('etabs_topology_and_story_mapping_reviewed',[folder/'OpenSees_Complete_Model_Data_V118.json',folder/'OpenSees_Complete_Story_Masters_V118.csv'],'source geometry / story mapping')
    add('wall_opening_and_coupling_beam_mesh_reviewed',[folder/'OpenSees_Area_Section_Assignment_Audit.json'],'area geometry audit; opening/coupling mesh still needs review')
    add('area_and_frame_gravity_loads_reconciled_to_etabs',[folder/'OpenSees_Load_Conversion_Audit.json',folder/'Gravity_Storey_Load_Breakdown_V131.json'],'load inventory only; load-set completeness and ETABS comparison required')
    add('seismic_mass_reconciled_to_etabs_by_storey',[folder/'OpenSees_Complete_Model_Data_V118.json'],'nodal mass inventory; independent ETABS reconciliation required')
    add('support_conditions_and_foundation_assumptions_reviewed',[folder/'OpenSees_Source_Model_Metadata_V118.json'],'exported restraints; foundation assumptions not certified')
    add('p_delta_and_gravity_preload_completed',[folder/'OpenSees_Complete_Gravity_Check_V118.json'],'saved gravity result; verify nonlinear model identity and P-Delta basis')
    add('modal_periods_modes_and_mass_participation_reviewed',[out/'Modal_ULS/NBC105_Modal_V111.json',out/'Modal_SLS/NBC105_Modal_V111.json'],'saved elastic modal results; not nonlinear initial-stiffness validation')
    add('brace_fvd_brb_case_matches_selected_scenario',[folder/'OpenSees_Complete_Model_Config_V118.json'],'configuration available; scenario needs review')
    add('slab_and_diaphragm_idealization_compatible',[folder/'OpenSees_Complete_Model_Config_V118.json',folder/'LOAD_PATH_AND_DIAPHRAGM_AUDIT_V130.json'],'configured slab modifiers and constraints; compatibility needs engineering review')
    add('is16700_initial_pdelta_plus_minus_cases_completed',list(out.glob('*PDelta*.json')),'saved files only; verify both signed cases and convergence')
    add('record_pair_units_scales_and_nbc_limits_reviewed',list(out.glob('LTH*/*RunConfig*.json')),'saved input configuration; unit/spectrum compatibility requires review')
    cfg=folder/'OpenSees_Complete_Model_Config_V118.json'
    if cfg.is_file():
        config=json.loads(cfg.read_text(encoding='utf-8-sig'));material=config.get('nonlinear_materials_file')
        if material:
            path=Path(material);path=path if path.is_absolute() else folder/path
            add('wall_nonlinear_materials_and_reinforcement_cited_calibrated',[path],'material definitions found; calibration not inferred')
            add('frame_concrete_and_rebar_materials_reviewed',[path],'material definitions found; reinforcement calibration not inferred')
    return result


def launch(parent,model_script,readiness_variable):
    import tkinter as tk
    from tkinter import ttk,messagebox
    model=Path(model_script).resolve();path=prepare(model);data=json.loads(path.read_text(encoding='utf-8-sig'))
    if str(Path(data['model_script']).resolve())!=str(model):raise ValueError('Draft bound to another model; select the correct draft')
    win=tk.Toplevel(parent);win.title('Nonlinear model readiness — evidence and model binding');win.geometry('1180x820');readiness_variable.set(str(path))
    ttk.Label(win,text='Selected nonlinear builder: '+str(model)+'\nChecklist: '+str(path)+'\nThis is a draft, not automatic approval. A source/material model must exist and checks require real evidence.',wraplength=1120).pack(anchor='w')
    cfg=model.with_name('OpenSees_Complete_Model_Config_V118.json')
    if cfg.exists():
        config=json.loads(cfg.read_text(encoding='utf-8-sig'));ttk.Label(win,text='Current model configuration: nonlinear_parameters_reviewed='+str(config.get('nonlinear_parameters_reviewed'))+'; materials file='+str(config.get('nonlinear_materials_file') or 'MISSING')+'; wall FSAM mappings='+str(len(config.get('nonlinear_wall_fsam_tags',{}))),wraplength=1100,foreground='#9a3e1d').pack(anchor='w')
    from OpenSees_Research_UI_V123 import scrollable_form
    footer=ttk.Frame(win);footer.pack(side='bottom',fill='x',padx=8,pady=8)
    body=ttk.Frame(win);body.pack(fill='both',expand=True);form=scrollable_form(body,min_width=850);checks={};evidence={}
    for key,value in data['checks'].items():
        checks[key]=tk.BooleanVar(value=value is True);evidence[key]=tk.StringVar(value=data.get('evidence',{}).get(key,''));ttk.Checkbutton(form,text=key.replace('_',' '),variable=checks[key]).pack(anchor='w');ttk.Entry(form,textvariable=evidence[key],width=110).pack(fill='x')
    def refresh_evidence():
        available=available_evidence(model)
        populated=0
        for key,value in available.items():
            if key in evidence and not evidence[key].get().strip():evidence[key].set(value);populated+=1
        from OpenSees_Workflow_V144 import GUIDE
        for key,var in evidence.items():
            if not var.get().strip():var.set('INPUT / REVIEW REQUIRED: '+GUIDE.get(key,'Open step 2 workflow inventory; inspect source model, analysis results and applicable project evidence for this exact requirement. No saved evidence was found.'))
        win._available_evidence=available
        return populated
    ttk.Button(footer,text='Refresh available evidence references (does not approve checks)',command=refresh_evidence).pack(anchor='w')
    ttk.Button(footer,text='Available parameter values + how to obtain missing inputs',command=lambda:__import__('OpenSees_Workflow_V144').launch(win,model.parent)).pack(anchor='w')
    refresh_evidence()
    approved=tk.BooleanVar(value=data.get('approved_for_nltha') is True);ttk.Checkbutton(footer,text='I have reviewed the evidence and approve this specific nonlinear model for NLTHA',variable=approved).pack(anchor='w')
    def rebind_draft():
        data.update(model_script_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),approved_for_nltha=False,checks={k:False for k in checks})
        for var in checks.values():var.set(False)
        approved.set(False)
        path.write_text(json.dumps(data,indent=2),encoding='utf8')
        messagebox.showinfo('Draft rebound','Current script fingerprint saved. Existing evidence retained; approvals reset because the model changed.',parent=win)
    ttk.Button(footer,text='Rebind changed model as UNAPPROVED draft',command=rebind_draft).pack(anchor='w')
    def save():
        try:
            missing=[k for k,v in checks.items() if v.get() and (not evidence[k].get().strip() or evidence[k].get().startswith('INPUT / REVIEW REQUIRED:'))]
            if missing:raise ValueError('Checked items need an evidence reference: '+', '.join(missing))
            if approved.get() and not all(v.get() for v in checks.values()):raise ValueError('Approval requires every prerequisite checked and evidenced')
            data.update(model_script=str(model),model_script_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),approved_for_nltha=approved.get(),checks={k:v.get() for k,v in checks.items()},evidence={k:v.get().strip() for k,v in evidence.items()});path.write_text(json.dumps(data,indent=2),encoding='utf-8');readiness_variable.set(str(path));messagebox.showinfo('Readiness saved','Draft saved. Missing model/material prerequisites are not bypassed.',parent=win)
        except Exception as e:messagebox.showerror('Readiness input',str(e),parent=win)
    ttk.Button(footer,text='Save model-bound checklist',command=save).pack(anchor='w')
    ttk.Button(footer,text='Open separate literature demo / material cards',command=lambda:__import__('OpenSees_Literature_Demo_GUI_V137').launch(win)).pack(anchor='w')
    win._readiness_checks=checks;win._readiness_evidence=evidence
    return win
