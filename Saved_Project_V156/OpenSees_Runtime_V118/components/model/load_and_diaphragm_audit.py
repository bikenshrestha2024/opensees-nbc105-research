"""Auditable shell loading, diaphragm membership and stiffness checks."""

__release__ = '134'
import json,math,collections
from pathlib import Path
from OpenSees_Timing_V130 import timed_outputs

@timed_outputs('Load path and diaphragm assembly audit','folder')
def audit(folder,data,topology,source_loads):
    folder=Path(folder);xyz={int(k):v for k,v in data['nodes'].items()};shells=data['shells'];frames=data['frames']
    frame_nodes={n for e in frames for n in e['nodes']};wall_nodes={n for e in shells if e['category']=='SHEAR WALL' for n in e['nodes']}
    groups=collections.defaultdict(list)
    for e in shells:groups[str(e['object'])].append(e)
    cfg=json.loads((folder/'OpenSees_Complete_Model_Config_V118.json').read_text(encoding='utf-8-sig'))
    records=[];pattern_totals=collections.defaultdict(float)
    for load in source_loads.get('applied_area_loads',[]):
        obj=str(load['object']);cells=groups[obj];q=float(load['value'])*(1 if int(load['direction_code'])==6 else -1)
        area=sum(float(e['area']) for e in cells);fz=q*area;nodal=collections.defaultdict(float)
        for cell in cells:
            for n in cell['nodes']:nodal[n]+=q*cell['area']/4
        centroid=[sum(e['area']*sum(xyz[n][i] for n in e['nodes'])/4 for e in cells)/area for i in range(3)]
        actual=[sum(nodal.values()),sum(xyz[n][1]*f for n,f in nodal.items()),-sum(xyz[n][0]*f for n,f in nodal.items())]
        expected=[fz,fz*centroid[1],-fz*centroid[0]]
        error=max(abs(a-b) for a,b in zip(actual,expected));assert error<1e-7*max(1,abs(fz))
        connected_nodes={n for e in cells for n in e['nodes']}&(frame_nodes|wall_nodes)
        records.append(dict(object=obj,pattern=load['pattern'],area_m2=area,q_global_z_kN_m2=q,unfactored_vertical_force_kN=fz,resultant_and_moment_error=error,beam_wall_connection_nodes=len(connected_nodes),method='Consistent uniform-load nodal vector for supported parallelogram ShellMITC4 cells; one application only'))
        records[-1]['gravity_factor']=cfg['gravity_factors'][load['pattern']]
        records[-1]['seismic_mass_weight_factor']=cfg['mass_factors'][load['pattern']]
        pattern_totals[load['pattern']]+=fz
    membership={};diaphragms=[]
    for g in data['diaphragms']:
        master=g['master_tag'];z=g['master_xyz'][2];slaves=g['slave_node_tags']
        if master in xyz or master in slaves:raise ValueError('Diaphragm master/slave tag collision')
        for node in slaves:
            if node in membership:raise ValueError('Node belongs to multiple diaphragm constraints')
            if abs(xyz[node][2]-z)>1e-7:raise ValueError('Non-coplanar diaphragm slave')
            membership[node]=master
        diaphragms.append(dict(master=master,z_m=z,slaves=len(slaves),constrained_dofs=[1,2,6],unconstrained_slab_vertical_dof=3,kinematics='ux=Ux-dy*Rz; uy=Uy+dx*Rz; rz=Rz (small rotation)'))
    floor_nodes={n for e in shells if e['category']=='FLOOR' for n in e['nodes']}
    coverage=dict(floor_nodes=len(floor_nodes),in_rigid_diaph=sum(n in membership for n in floor_nodes),without_rigid_diaph=sum(n not in membership for n in floor_nodes))
    names={r['pattern'].casefold() for r in source_loads.get('applied_area_loads',[])}
    notes=[]
    if not names&{'roof live','rooflive'}:notes.append('No roof-live area assignment was present in the supplied source audit. No roof-live load was invented. Refresh ETABS extraction if an assignment is expected.')
    result=dict(area_load_records=records,area_unfactored_global_z_kN_by_pattern=dict(pattern_totals),diaphragms=diaphragms,coverage=coverage,notes=notes,load_path='Slab shell flexure to shared beam/wall/column nodes, not a duplicated tributary beam load',limitations=['This connectivity/equilibrium audit does not establish member-by-member ETABS load-sharing equivalence.','Rigid diaphragm constrains in-plane motion only; slab vertical bending remains active.'])
    (folder/'LOAD_PATH_AND_DIAPHRAGM_AUDIT_V130.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def check_kinematics(ops,data):
    worst=0.
    for g in data['diaphragms']:
        m=ops.nodeDisp(g['master_tag']);mx,my,_=g['master_xyz']
        for n in g['slave_node_tags']:
            p=data['nodes'].get(str(n),data['nodes'].get(n));u=ops.nodeDisp(n)
            worst=max(worst,abs(u[0]-(m[0]-(p[1]-my)*m[5])),abs(u[1]-(m[1]+(p[0]-mx)*m[5])),abs(u[5]-m[5]))
    return dict(max_inplane_constraint_residual=worst,units='m for translation, rad for rotation; mixed maximum is diagnostic only')


def implementation_digest(root=None):
    import hashlib
    root=Path(root or Path(__file__).resolve().parent)
    paths=sorted((root/'components').rglob('*.py'))
    return hashlib.sha256(b''.join(str(p.relative_to(root)).encode()+p.read_bytes() for p in paths)).hexdigest()


def modal_numeric_digest(root=None):
    import hashlib
    root=Path(root or Path(__file__).parent)
    paths=['model/assembly.py','gravity/solver_stack.py','sections/definitions.py','modal/analysis.py','model/analysis_basis.py']
    h=hashlib.sha256()
    for name in paths:
        path=root/'components'/name;h.update(name.encode())
        if name=='model/assembly.py':
            import ast
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in tree.body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name!='autoselect_inputs':h.update(ast.dump(node,include_attributes=False).encode())
        else:h.update(path.read_bytes())
    return h.hexdigest()
