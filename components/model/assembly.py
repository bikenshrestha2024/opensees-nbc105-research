"""Assemble ETABS source audits into one connected model and role-specific entries.

Units: kN, m, s. Source audits remain immutable. The elastic model is a
conversion/check model; a separate nonlinear entry requires calibrated inputs.
CSI GetWall returns WallPropType, ShellType, MatProp, Thickness, ..., ret:
https://docs.csiamerica.com/help-files/etabs-api-2015/html/0fadb96f-4292-6541-f6ed-ab95e8ec92b6.htm
ShellMITC4 node/section convention:
https://openseespydoc.readthedocs.io/en/latest/src/ShellMITC4.html
Beam consistent loads below integrate cubic Hermite displacement functions;
end moments are retained, unlike the old endpoint-force-only load audit.
"""

__release__ = '134'
from OpenSees_Timing_V130 import timed_outputs
from pathlib import Path
import ast
import csv
import json
import math
import shutil
import hashlib

MANIFEST = 'OpenSees_Export_Manifest_V118.json'


def _validate_insertion_point(insertion, obj):
    """CSI: CardinalPoint, Mirror2, StiffTransform, Offset1, Offset2, CSys, ret.

    With StiffTransform=False the insertion assignment is graphical only.
    CSI reference: https://docs.csiamerica.com/help-files/etabs-api-2015/html/af52715a-299d-b81c-7372-03fef249e45f.htm
    Preserve structural offsets as an explicit blocker until mapped to target
    rigid constraints; silently centering them would change member stiffness.
    """
    if not insertion:
        return
    if (not isinstance(insertion, (list, tuple)) or len(insertion) != 7
            or insertion[-1] != 0
            or any(not isinstance(v, (list, tuple)) or len(v) != 3 for v in insertion[3:5])):
        raise ValueError(f'Frame {obj}: invalid or failed ETABS GetInsertionPoint response')
    if not isinstance(insertion[2], (bool, int)) or insertion[2] not in (False, True):
        raise ValueError(f'Frame {obj}: invalid StiffTransform flag')
    if not insertion[2]:
        return  # Display-only cardinal point and offsets do not alter stiffness.
    if int(insertion[0]) not in (5, 10, 11) or any(abs(float(v)) > 1e-8 for a in insertion[3:5] for v in a):
        raise ValueError(f'Frame {obj}: StiffTransform=True requires structural insertion-offset conversion; provide reviewed target offsets')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _write(path, value):
    with Path(path).open('w', encoding='utf-8', newline='\n') as f:
        f.write(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False))


def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _sub(a,b): return [x-y for x,y in zip(a,b)]
def _cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def _unit(a):
    norm=math.sqrt(_dot(a,a))
    if norm<1e-12: raise ValueError('Zero-length member/vector')
    return [x/norm for x in a]


def _positive(x,label):
    x=float(x)
    if not math.isfinite(x) or x<=0: raise ValueError(f'Missing/invalid positive {label}')
    return x


def _wall_panel_nodes(points, object_id):
    """Order a wall quad bottom-first with a deterministic counterclockwise normal."""
    low=min(q[2] for q in points)
    bottom=[i for i,q in enumerate(points) if abs(q[2]-low)<1e-7]
    if len(bottom)!=2:
        raise ValueError(f'Wall {object_id}: inclined/non-horizontal bottom edge needs explicit panel mapping')
    if (bottom[0]+1)%4 not in bottom:
        points=list(reversed(points))
        bottom=[i for i,q in enumerate(points) if abs(q[2]-low)<1e-7]
    start=next(i for i in bottom if (i+1)%4 in bottom)
    points=points[start:]+points[:start]
    normal=_cross(_sub(points[1],points[0]),_sub(points[3],points[0]))
    dominant=max(range(3),key=lambda i:abs(normal[i]))
    if normal[dominant]<0:
        points=[points[1],points[0],points[3],points[2]]
    return points


def _material_table(folder):
    p=folder/'ETABS_Materials.csv'
    result={}
    if p.exists():
        with p.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                try:
                    iso=ast.literal_eval(r['isotropic']); wm=ast.literal_eval(r['weight_mass'])
                    if iso[-1]==0 and wm[-1]==0:
                        result[r['name']]=dict(E=float(iso[0]),nu=float(iso[1]),weight=float(wm[0]))
                except (ValueError,TypeError,KeyError,SyntaxError): pass
    return result


def _area_property(row,materials):
    # Recover saved V116 wall audits using the preserved raw successful API
    # result. Do not accept the old material='1', thickness=None decoding.
    wall=str(row.get('property_type','')).lower()=='wall'
    material=row.get('material_name'); thickness=row.get('thickness_m')
    for name,raw in (row.get('raw_property_api') or {}).items():
        if (wall and name.startswith('GetWall')) or (not wall and name.startswith('GetSlab')):
            try:
                a=ast.literal_eval(raw) if isinstance(raw,str) else raw
                if len(a)>=8 and a[-1]==0 and isinstance(a[2],str):
                    material=a[2]; thickness=a[3]; break
            except (ValueError,SyntaxError,TypeError): pass
    mv=row.get('material_values') or {}
    # Fresh assignment material values outrank an older auxiliary CSV.
    current=dict(E=mv.get('E'),nu=mv.get('poisson_ratio'),weight=mv.get('weight_per_volume'))
    valid_current=all(current[k] is not None for k in ('E','nu','weight')) and float(current['E'])>0 and float(current['weight'])>0
    mat=current if valid_current else materials.get(material) or current
    return dict(property=row.get('assigned_property'),material=material,
                thickness=_positive(thickness,'area thickness'),E=_positive(mat['E'],'area E'),
                nu=float(mat['nu']),weight=_positive(mat['weight'],'area unit weight'))


def _frame_property(row):
    b=_positive(row.get('width_m'),'frame width'); h=_positive(row.get('depth_m'),'frame depth')
    if str(row.get('section_type','')).startswith('tube'):
        tf=_positive(row.get('tube_flange_thickness_m'),'SHS flange thickness')
        tw=_positive(row.get('tube_web_thickness_m'),'SHS web thickness')
        if min(b-2*tw,h-2*tf)<=0: raise ValueError('Invalid SHS inside dimensions')
        area=b*h-(b-2*tw)*(h-2*tf)
        iy=(b*h**3-(b-2*tw)*(h-2*tf)**3)/12
        iz=(h*b**3-(h-2*tf)*(b-2*tw)**3)/12
        j=4*((b-tw)*(h-tf))**2/(2*(b-tw)/tf+2*(h-tf)/tw)
    else:
        if not str(row.get('section_type','')).startswith('rectangle'): raise ValueError('Unsupported frame section family')
        area=b*h; iy=b*h**3/12; iz=h*b**3/12
        a,c=max(b,h),min(b,h)
        j=a*c**3*(1/3-.21*(c/a)*(1-c**4/(12*a**4)))
    return dict(section=row['assigned_section'],A=area,Iy=iy,Iz=iz,J=j,
                E=_positive(row.get('E_kN_m2'),'frame E'),G=_positive(row.get('G_kN_m2'),'frame G'),
                weight=_positive(row.get('weight_per_volume'),'frame unit weight'))


@timed_outputs('ETABS source metadata','output')
def extract_source_metadata(sap, topology, frame_rows, output):
    """Read support, orientation, releases and offsets without modifying ETABS."""
    data=dict(supports={},frames={},point_loads=[],additional_point_masses={},pattern_types={},errors=[])
    try: data['present_units']=int(sap.GetPresentUnits())
    except Exception as exc: data['errors'].append(f'ETABS present units: {exc}')
    try:
        names=list(sap.LoadPatterns.GetNameList())
        if names[-1]!=0: raise ValueError('GetNameList returned nonzero')
        for name in names[1]:
            result=list(sap.LoadPatterns.GetLoadType(name))
            if result[-1]==0: data['pattern_types'][str(name)]=int(result[0])
    except Exception as exc: data['errors'].append(f'Load-pattern types: {exc}')
    for n in topology.get('node_map',[]):
        try:
            a=list(sap.PointObj.GetRestraint(str(n['etabs_point_name'])))
            flags=next(list(v) for v in a if isinstance(v,(tuple,list)) and len(v)==6)
            if a[-1]!=0: raise ValueError('GetRestraint returned nonzero')
            if any(flags): data['supports'][str(n['opensees_node_tag'])]=[int(bool(x)) for x in flags]
        except Exception as exc: data['errors'].append(f"Point {n['etabs_point_name']} restraint: {exc}")
        try:
            # CSI GetLoadForce: NumberItems, PointName, LoadPat, LcStep,
            # CSys, F1,F2,F3,M1,M2,M3,ret (Global loads transfer directly).
            a=list(sap.PointObj.GetLoadForce(str(n['etabs_point_name'])))
            if a[-1]!=0: raise ValueError('GetLoadForce returned nonzero')
            for k in range(int(a[0])):
                data['point_loads'].append(dict(node=int(n['opensees_node_tag']),pattern=str(a[2][k]),
                    step=int(a[3][k]),coordinate_system=str(a[4][k]),values=[float(a[j][k]) for j in range(5,11)]))
        except Exception as exc: data['errors'].append(f"Point {n['etabs_point_name']} force loads: {exc}")
        try:
            a=list(sap.PointObj.GetMass(str(n['etabs_point_name'])))
            values=next(list(v) for v in a if isinstance(v,(tuple,list)) and len(v)==6)
            if a[-1]==0 and any(values): data['additional_point_masses'][str(n['opensees_node_tag'])]=values
        except Exception as exc: data['errors'].append(f"Point {n['etabs_point_name']} explicit mass: {exc}")
    for row in frame_rows:
        obj=str(row['etabs_object']); r={}
        for method in ('GetLocalAxes','GetReleases','GetInsertionPoint'):
            try: r[method]=list(getattr(sap.FrameObj,method)(obj))
            except Exception as exc: r[method]=dict(error=str(exc))
        data['frames'][obj]=r
    try:
        a=list(sap.LinkObj.GetNameList()); data['source_link_count']=int(a[0]) if a[-1]==0 else None
    except Exception as exc: data['errors'].append(f'ETABS link objects: {exc}')
    _write(output,data)
    return data


def _mesh_areas(source_nodes, records, area_rows, materials, floor_subdivisions=4):
    """Conforming rectangular grid over each source parallelogram.

    All coplanar source-node coordinate lines are used, even when a node is
    outside the individual panel. Adjacent panels therefore share subdivisions.
    No source opening is filled; each mesh cell belongs to an existing polygon.
    """
    nodes=dict(source_nodes); lookup={tuple(round(x,8) for x in p):n for n,p in nodes.items()}
    next_node=max(nodes)+1000; shells=[]; by_object={}
    original=list(source_nodes.values())
    floor_subdivisions=int(floor_subdivisions)
    if not 2<=floor_subdivisions<=16:raise ValueError('floor_subdivisions must be 2..16; one corner-only slab cell cannot resolve beam-span load transfer')
    # Seed the complete floor plane before meshing any panel. Adjacent slabs,
    # supporting walls and frame segments share these coordinates.
    for record in records:
        if record.get('dimension')!='area_polygon' or record.get('category')!='FLOOR':continue
        points=[source_nodes[int(n)] for n in record['node_tags']]
        if len(points)!=4:continue
        for i in range(floor_subdivisions+1):
            for j in range(floor_subdivisions+1):
                u=i/floor_subdivisions;v=j/floor_subdivisions
                original.append([points[0][k]+u*(points[1][k]-points[0][k])+v*(points[3][k]-points[0][k]) for k in range(3)])

    for e in records:
        if e['dimension']!='area_polygon': continue
        obj=str(e['etabs_object']); ns=e['node_tags']
        if len(ns)!=4: raise ValueError(f'Area {obj}: only four-node polygons are supported')
        p=[nodes[int(n)] for n in ns]; a=_sub(p[1],p[0]); b=_sub(p[3],p[0]); cross=_cross(a,b)
        if e['category']=='SHEAR WALL':
            # E-SFI requires bottom-first, counterclockwise node ordering.
            p=_wall_panel_nodes(p,obj); a=_sub(p[1],p[0]); b=_sub(p[3],p[0]); cross=_cross(a,b)
        area=math.sqrt(_dot(cross,cross)); normal=_unit(cross)
        if math.dist([p[1][i]+p[3][i]-p[0][i] for i in range(3)],p[2])>1e-6:
            raise ValueError(f'Area {obj}: non-parallelogram needs the ETABS analysis mesh; no guessed triangulation')
        aa,bb,ab=_dot(a,a),_dot(b,b),_dot(a,b); det=aa*bb-ab*ab
        if det<=1e-12: raise ValueError(f'Area {obj}: degenerate geometry')
        uvals={0.,1.}; vvals={0.,1.}
        for q in original:
            d=_sub(q,p[0])
            if abs(_dot(d,normal))>1e-7: continue
            u=(_dot(d,a)*bb-_dot(d,b)*ab)/det; v=(_dot(d,b)*aa-_dot(d,a)*ab)/det
            if 1e-7<u<1-1e-7: uvals.add(round(u,9))
            if 1e-7<v<1-1e-7: vvals.add(round(v,9))
        uu,vv=sorted(uvals),sorted(vvals); grid={}
        prop=_area_property(area_rows[obj],materials)
        for i,u in enumerate(uu):
            for j,v in enumerate(vv):
                xyz=[p[0][k]+a[k]*u+b[k]*v for k in range(3)]; key=tuple(round(x,8) for x in xyz)
                if key not in lookup:
                    while next_node in nodes: next_node+=1
                    lookup[key]=next_node; nodes[next_node]=xyz; next_node+=1
                grid[i,j]=lookup[key]
        children=[]
        for i in range(len(uu)-1):
            for j in range(len(vv)-1):
                cell=[grid[i,j],grid[i+1,j],grid[i+1,j+1],grid[i,j+1]]
                if e['category']=='FLOOR' and normal[2]<0: cell.reverse()
                child=dict(object=obj,nodes=cell,category=e['category'],properties=prop,
                           area=area*(uu[i+1]-uu[i])*(vv[j+1]-vv[j]))
                shells.append(child); children.append(child)
        by_object[obj]=children
    return nodes,shells,by_object


def _basis(p,q,angle=0.):
    x=_unit(_sub(q,p)); ref=[1.,0.,0.] if abs(x[2])>.99 else [0.,0.,1.]
    y=_unit(_cross(ref,x)); z=_cross(x,y)
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    return x,[c*y[i]+s*z[i] for i in range(3)],[-s*y[i]+c*z[i] for i in range(3)]


def _consistent_segment_load(length,basis,start,end,w0,w1):
    """Global 12-vector from a signed line load on a segment subinterval."""
    local=[0.]*12
    # Three-point Gauss integrates Hermite (degree 3) times linear pressure.
    for xi,weight in ((-math.sqrt(3/5),5/9),(0.,8/9),(math.sqrt(3/5),5/9)):
        at=(start+end)/2+xi*(end-start)/2; t=at/length
        f=(at-start)/(end-start); w=[w0[i]+f*(w1[i]-w0[i]) for i in range(3)]
        wx,wy,wz=[_dot(w,axis)*weight*(end-start)/2 for axis in basis]
        n1,n2,n3,n4=1-3*t*t+2*t**3,length*(t-2*t*t+t**3),3*t*t-2*t**3,length*(-t*t+t**3)
        for index,value in ((0,(1-t)*wx),(6,t*wx),(1,n1*wy),(7,n3*wy),(5,n2*wy),(11,n4*wy),
                            (2,n1*wz),(8,n3*wz),(4,-n2*wz),(10,-n4*wz)):
            local[index]+=value
    return [sum(local[offset+k]*basis[k][j] for k in range(3))
            for offset in (0,3,6,9) for j in range(3)]


@timed_outputs('Model assembly and export','folder')
def prepare_complete_export(folder, *, runtime_dir=None, frame_mapping=None):
    """Write the assembled data, load ledger, role manifest and runnable entries.

    Numerical source defects block model building with a precise report.
    Nonlinear calibration is never inferred from a section name or benchmark.
    """
    folder=Path(folder).resolve(); runtime_dir=Path(runtime_dir or Path(__file__).parent)
    report=dict(version=118,assembly_errors=[],warnings=[],analysis_ready=False,
                elastic_scope='Connected elastic conversion model; ETABS response comparison required',
                nonlinear_ready=False)
    manifest=dict(version=118,report='OpenSees_Complete_Export_Report_V118.json')
    try:
        topology=_read(folder/'OpenSees_Element_Connectivity.json')
        sections=_read(folder/'OpenSees_Section_Assignment_Audit.json')
        loads=_read(folder/'OpenSees_Load_Conversion_Audit.json')
        source_nodes={int(n['opensees_node_tag']):list(map(float,n['coordinates_m'])) for n in topology['node_map']}
        frame_rows={str(r['etabs_object']):r for r in sections['frame_assignments']}
        area_rows={str(r['etabs_area_object']):r for r in sections['area_assignments']}
        materials=_material_table(folder)
        config_path=folder/'OpenSees_Complete_Model_Config_V118.json'
        default_factors={p:(0. if p.casefold()=='roof live' else .3 if p.casefold()=='live' else 1.)
                         for p in ('Self Weight','Dead','DL','Super Dead','SDead','Floor Finish','Wall','Partition','Live','Roof Live')}
        cfg=_read(config_path) if config_path.exists() else dict(gravity_factors=default_factors,mass_factors=default_factors,
              slab_bending_factor=.25,slab_stiffness_source='IS 16700:2023 Table 5 strength; 0.35 for serviceability',
              frame_section_mapping=frame_mapping or {},nonlinear_parameters_reviewed=False,
              nonlinear_materials_file='',nonlinear_wall_fsam_tags={},section_overrides={},area_property_overrides={})
        cfg.setdefault('floor_subdivisions',4)
        cfg['slab_bending_factor']=.25
        cfg['slab_bending_factor_sls']=.35
        cfg['slab_stiffness_source']='IS 16700:2023 Table 5: Ig factors 0.25 strength / 0.35 serviceability; gross membrane EA retained; physical self-weight uses original thickness'
        if frame_mapping is not None: cfg['frame_section_mapping']=dict(frame_mapping)
        _write(config_path,cfg)
        for obj,row in area_rows.items(): row.update(cfg.get('area_property_overrides',{}).get(row.get('assigned_property'),{}))
        for obj,row in frame_rows.items(): row.update(cfg.get('section_overrides',{}).get(row.get('assigned_section'),{}))
        metadata_path=folder/'OpenSees_Source_Model_Metadata_V118.json'
        meta=_read(metadata_path) if metadata_path.exists() else {}
        if not meta:
            report['warnings'].append('Legacy saved audits do not record local-axis rotations, releases, insertion offsets or direct joint loads. Run a fresh EDB export to obtain that metadata; this saved-audit assembly is a diagnostic conversion model.')
        if meta.get('present_units') not in (None,6): raise ValueError('Complete model expects verified ETABS kN-m-C units (enum 6)')
        if meta.get('additional_point_masses'): raise ValueError('ETABS has additional assigned point masses: reconcile these with load-derived mass in the complete-model config first')
        if meta.get('source_link_count'): raise ValueError('ETABS has LinkObj elements; provide their target device definitions before assembled conversion')
        if meta.get('errors'): report['warnings'].append(f"{len(meta['errors'])} source metadata queries failed; inspect OpenSees_Source_Model_Metadata_V118.json before claiming ETABS equivalence")
        nodes,shells,area_children=_mesh_areas(source_nodes,topology['elements'],area_rows,materials,cfg.get('floor_subdivisions',4))
        frame_elements=[]; segments={}; null_frames=[]
        for e in topology['elements']:
            if e['dimension']!='line_2_node': continue
            obj=str(e['etabs_object']); row=frame_rows[obj]
            if not row.get('assigned_section'):
                null_frames.append(obj); continue  # ETABS None section carries no stiffness or self-weight.
            prop=_frame_property(row); i,j=map(int,e['node_tags']); p,q=nodes[i],nodes[j]
            length=math.dist(p,q); x=_unit(_sub(q,p)); cuts={0.:i,1.:j}
            frame_meta=meta.get('frames',{}).get(obj,{})
            axes=frame_meta.get('GetLocalAxes',[]); angle=float(axes[0]) if isinstance(axes,list) and axes and axes[-1]==0 else 0.
            if isinstance(axes,list) and len(axes)>2 and axes[-1]==0 and bool(axes[1]):
                raise ValueError(f'Frame {obj}: advanced ETABS local axes require explicit orientation mapping')
            identity=f"ETABS frame unique ID {obj} | OpenSees topology tag {e.get('element_tag', 'unassigned')} | OpenSees solver tag pending assembly"
            release=frame_meta.get('GetReleases',[])
            hinged=False
            if isinstance(release,list) and any(any(v) for v in release[:2] if isinstance(v,(list,tuple))):
                hinged=(len(release)==5 and release[-1]==0 and str(e['category']).upper()=='BRACE'
                        and not any(release[0][:3]+release[1][:3])
                        and all(release[0][4:6]+release[1][4:6])
                        and (release[0][3] or release[1][3])
                        and not any(release[2]+release[3]))
                if not hinged: raise ValueError(identity+': unsupported end releases or partial fixity')
                report['warnings'].append(identity+': hinged brace mapped with end My/Mz releases and zero torsional transfer; nonlinear hinge implementation remains gated')
            insertion=frame_meta.get('GetInsertionPoint',[])
            _validate_insertion_point(insertion, identity)
            for n,r in nodes.items():
                d=_sub(r,p); t=_dot(d,x)/length
                if 1e-7<t<1-1e-7 and math.dist(r,[p[k]+t*(q[k]-p[k]) for k in range(3)])<1e-7: cuts[round(t,9)]=n
            cuts=sorted(cuts.items()); children=[]
            for (u,a),(v,b) in zip(cuts,cuts[1:]):
                child=dict(object=obj,nodes=[a,b],length=(v-u)*length,start=u*length,end=v*length,
                           properties=prop,category=e['category'],basis=_basis(p,q,angle),hinged_brace=hinged,release_i=hinged and u==0.,release_j=hinged and v==1.)
                frame_elements.append(child); children.append(child)
            segments[obj]=children
        active={n for e in frame_elements+shells for n in e['nodes']}
        nodes={n:p for n,p in nodes.items() if n in active}
        # Nodal vectors remain separate per unfactored source pattern.
        patterns={}; load_provenance=[]; source_context={}
        def add(pattern,node,values):
            dst=patterns.setdefault(pattern,{}).setdefault(str(node),[0.]*6)
            for k,v in enumerate(values): dst[k]+=v
            if len(values)>2 and values[2]: load_provenance.append(dict(source_context,pattern=pattern,node=int(node),downward_kN=-float(values[2])))
        def surface(pattern,cell,total):
            for n in cell['nodes']: add(pattern,n,[0,0,total/4,0,0,0])
        def line(pattern,seg,w0,w1,start=0.,end=None):
            end=seg['length'] if end is None else end
            f=_consistent_segment_load(seg['length'],seg['basis'],start,end,w0,w1)
            if seg.get('hinged_brace'):
                # Static condensation of released rotations must also modify
                # consistent loads, otherwise artificial joint moments remain.
                import numpy as np
                L=seg['length']; basis=np.array(seg['basis']); local=np.zeros(12)
                for offset in (0,3,6,9): local[offset:offset+3]=basis@np.array(f[offset:offset+3])
                for ids,sign in (([1,5,7,11],1),([2,4,8,10],-1)):
                    k=np.array([[12,6*L,-12,6*L],[6*L,4*L*L,-6*L,2*L*L],[-12,-6*L,12,-6*L],[6*L,2*L*L,-6*L,4*L*L]],float)
                    transform=np.diag([1,sign,1,sign]); k=transform@k@transform
                    released=([1] if seg.get('release_i') else [])+([3] if seg.get('release_j') else [])
                    active=[i for i in range(4) if i not in released]
                    values=local[ids].copy()
                    if released:
                        values[active]-=k[np.ix_(active,released)]@np.linalg.solve(k[np.ix_(released,released)],values[released])
                        values[released]=0.;local[ids]=values
                for offset in (0,3,6,9): f[offset:offset+3]=(basis.T@local[offset:offset+3]).tolist()
            add(pattern,seg['nodes'][0],f[:6]); add(pattern,seg['nodes'][1],f[6:])
        for r in meta.get('point_loads',[]):
            if r['pattern'] not in cfg['gravity_factors']:
                if meta.get('pattern_types',{}).get(r['pattern']) in (5,6) or r['pattern'].startswith('~'): continue
                raise ValueError(f"No explicit gravity/mass factor for point-load pattern {r['pattern']}")
            if r['coordinate_system'].casefold()!='global' or r['step'] not in (0,1): raise ValueError(f"Joint {r['node']}: non-global or staged point load needs explicit transformation")
            if r['node'] not in nodes: raise ValueError(f"Point load on disconnected node {r['node']}")
            source_context=dict(source='JOINT:'+str(r['node']),component='point_load')
            add(r['pattern'],r['node'],r['values'])
        if any(loads.get(key)=='UNVERIFIED' for key in ('uniform_load_sets_status','direct_uniform_loads_status')):
            raise ValueError('Uniform area-load or load-set extraction is unverified. Re-export the source EDB with readable assignment/definition tables; incomplete loads cannot form a verified gravity/mass model.')
        for r in loads.get('applied_area_loads',[]):
            obj=str(r['object']); pat=r['pattern']; direction=int(r['direction_code'])
            if pat not in cfg['gravity_factors'] or pat not in cfg['mass_factors']: raise ValueError(f'No explicit load/mass factor for {pat}')
            if str(r['coordinate_system']).casefold()!='global' or direction not in (6,10): raise ValueError(f'Unsupported area load direction: {obj}')
            source_context=dict(source='AREA:'+obj,component='area_load',load_set=r.get('load_set'),load_set_component=r.get('load_set_component'))
            for cell in area_children[obj]: surface(pat,cell,float(r['value'])*cell['area']*(1 if direction==6 else -1))
        for r in sections.get('frame_distributed_load_assignments',[]):
            pat=r['pattern']; obj=str(r['object'])
            if pat.startswith('~'): continue
            if pat not in cfg['gravity_factors'] or pat not in cfg['mass_factors']: raise ValueError(f'No explicit load/mass factor for frame pattern {pat}')
            if obj not in segments: raise ValueError(f'Frame load on None-section/unconverted object {obj}')
            direction=int(r['direction_code']); vector={4:[1,0,0],5:[0,1,0],6:[0,0,1],10:[0,0,-1]}.get(direction)
            if str(r['coordinate_system']).casefold()!='global' or int(r['load_type'])!=1 or vector is None:
                raise ValueError(f'Unsupported distributed load type/coordinate system on frame {obj}')
            lo=float(r['distance_start']); hi=float(r['distance_end']); length=segments[obj][-1]['end']
            if not 0<=lo<hi<=length+1e-6: raise ValueError(f'Invalid absolute load interval on frame {obj}')
            v0=float(r['value_start']); v1=float(r['value_end'])
            for seg in segments[obj]:
                a=max(lo,seg['start']); b=min(hi,seg['end'])
                if b<=a: continue
                wa=v0+(v1-v0)*(a-lo)/(hi-lo); wb=v0+(v1-v0)*(b-lo)/(hi-lo)
                source_context=dict(source='FRAME:'+obj,component='frame_load')
                line(pat,seg,[wa*x for x in vector],[wb*x for x in vector],a-seg['start'],b-seg['start'])
        for r in loads.get('etabs_load_pattern_self_weight_multipliers',[]):
            mult=r.get('multiplier')
            if mult is None: raise ValueError(f"Missing self-weight multiplier for {r.get('pattern')}")
            if not mult: continue
            pat=r['pattern']
            if pat not in cfg['gravity_factors'] or pat not in cfg['mass_factors']: raise ValueError(f'No load/mass factor for self-weight pattern {pat}')
            for seg in frame_elements:
                source_context=dict(source='FRAME:'+str(seg['object']),component='self_weight_'+str(seg['category']).lower())
                p=seg['properties']; w=-float(mult)*p['A']*p['weight']; line(pat,seg,[0,0,w],[0,0,w])
            for cell in shells:
                source_context=dict(source='AREA:'+str(cell['object']),component='self_weight_'+str(cell['category']).lower())
                p=cell['properties']; surface(pat,cell,-float(mult)*p['thickness']*p['weight']*cell['area'])
        nodal_mass={n:0. for n in nodes}; gravity={}; total=0.; ledger={}
        for pat,values in patterns.items():
            gf=float(cfg['gravity_factors'][pat]); mf=float(cfg['mass_factors'][pat]); ledger[pat]=0.
            if min(gf,mf)<0 or not all(math.isfinite(v) for v in (gf,mf)): raise ValueError('Load/mass factors must be finite and non-negative')
            if mf not in (0.,.3,.6,1.): raise ValueError(f'ESM component ledger does not represent custom mass factor {mf}; supply a separately reconciled story-weight CSV')
            gravity[pat]={}
            for n,vec in values.items():
                gravity[pat][n]=[v*gf for v in vec]; ledger[pat]-=vec[2]*gf
                nodal_mass[int(n)]+=-vec[2]*mf/9.80665
            total+=ledger[pat]
        if any(m<-1e-8 for m in nodal_mass.values()): raise ValueError('Negative nodal seismic mass; reconcile upward loads')
        if total<=0: raise ValueError('Complete gravity load total is not positive')
        supports=meta.get('supports')
        if not supports:
            supports={str(n):[1]*6 for n in loads['base_supports']['node_tags'] if int(n) in nodes}
            report['warnings'].append('Support restraints use the existing audit fixed-base assumption; fresh ETABS extraction records actual restraints.')
        # A fully restrained source boundary remains fully restrained after
        # refinement; otherwise new base-edge nodes would introduce flexibility.
        source_supports=dict(supports)
        for e in topology['elements']:
            if e['dimension']!='area_polygon': continue
            ns=e['node_tags']
            for a,b in zip(ns,ns[1:]+ns[:1]):
                if source_supports.get(str(a))!=[1]*6 or source_supports.get(str(b))!=[1]*6: continue
                p,q=source_nodes[int(a)],source_nodes[int(b)]; v=_sub(q,p); l2=_dot(v,v)
                for n,r in nodes.items():
                    t=_dot(_sub(r,p),v)/l2
                    if -1e-7<=t<=1+1e-7 and math.dist(r,[p[k]+t*v[k] for k in range(3)])<1e-7: supports[str(n)]=[1]*6
        base_z=min(p[2] for p in nodes.values())
        # Mesh nodes on source rigid floors join their floor diaphragm. Original
        # source memberships are retained; extension requires one group/level.
        groups=[]; source_groups=topology.get('rigid_diaphragm_groups',[])
        by_z={}
        for g in source_groups: by_z.setdefault(round(g['master_xyz'][2],7),[]).append(g)
        for z,gg in by_z.items():
            if len(gg)!=1: raise ValueError(f'Multiple diaphragms at Z={z}: explicit generated-node membership required')
            g=dict(gg[0]); master=max(nodes)+1000+len(groups)
            g['master_tag']=master
            source_members={int(n) for n in g.get('slave_node_tags',[])}
            # Raw point assignments can include a physical point at the diaphragm centre
            # that older preview grouping omitted when choosing its synthetic master.
            raw_assignments=topology.get('etabs_point_diaphragm_assignments',{})
            for source_node in topology.get('node_map',[]):
                assignment=raw_assignments.get(str(source_node['etabs_point_name']),{})
                if assignment.get('diaphragm_name')==g.get('diaphragm_name') and abs(source_node['coordinates_m'][2]-z)<1e-7:
                    source_members.add(int(source_node['opensees_node_tag']))
            g['slave_node_tags']=[n for n,p in nodes.items() if abs(p[2]-z)<1e-7 and (n not in source_nodes or n in source_members)]
            groups.append(g)
        payload=dict(config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),nodes=nodes,frames=frame_elements,shells=shells,gravity=gravity,unfactored_patterns=patterns,nodal_mass=nodal_mass,supports=supports,
                     diaphragms=groups,total_downward_load_kN=total,gravity_by_pattern_kN=ledger,base_z_m=base_z)
        payload['load_provenance']=load_provenance
        from OpenSees_Storey_Gravity_V131 import export_storey_gravity
        report['storey_gravity']=export_storey_gravity(folder,payload,cfg,meta.get('pattern_types',{}))
        from OpenSees_Model_Audit_V130 import audit
        report['load_path_audit']=audit(folder,payload,topology,loads)
        _write(folder/'OpenSees_Complete_Model_Data_V118.json',payload)
        report.update(frame_objects=len(segments),frame_segments=len(frame_elements),area_objects=len(area_children),
                      shell_mesh_cells=len(shells),source_nodes=len(source_nodes),mesh_nodes=len(nodes),
                      excluded_none_section_frame_objects=null_frames,total_downward_load_kN=total,
                      total_seismic_weight_including_fixed_nodes_kN=sum(nodal_mass.values())*9.80665,
                      active_horizontal_seismic_weight_kN=sum(m for n,m in nodal_mass.items() if not all(supports.get(str(n),[0]*6)[:2]))*9.80665,gravity_by_pattern_kN=ledger,
                      elastic_assembled=True)
        report['warnings'] += ['Elastic core walls use gross source E/thickness; establish rational cracked-wall stiffness before NBC design use.',
            'Frame EI uses NBC ULS beam 0.35 and column 0.70; source orientation and diaphragm equivalence need ETABS response comparison.',
            'Floor bending uses the configured IS 16700 slab factor; membrane EA is preserved by equivalent E/thickness. Physical thickness controls weight.',
            'Self-weight is integrated from full section volumes once per source multiplier; ETABS joint-volume overlap conventions require reaction/mass reconciliation.',
            'Only extracted distributed frame/area loads are assembled; point loads, temperature, prestress and link actions require explicit additional transfer if assigned.']
    except Exception as exc:
        import traceback
        report['assembly_errors'].append(f'{type(exc).__name__}: {exc}'); report['assembly_traceback']=traceback.format_exc(); payload=None
    from OpenSees_ID_Audit_V120 import export_id_audit
    export_id_audit(folder, payload, report)
    # Always emit stable entries. A blocked entry reports the precise defect;
    # analysis windows do not fall back to a stale skeleton or load-only model.
    runtime=folder/'OpenSees_Runtime_V118'; runtime.mkdir(exist_ok=True)
    if (runtime_dir/'components').is_dir() and (runtime_dir/'components').resolve()!=(runtime/'components').resolve():
        shutil.copytree(runtime_dir/'components',runtime/'components',dirs_exist_ok=True)
    wall_sources=runtime_dir/'wall_validation_sources'
    if wall_sources.is_dir() and wall_sources.resolve()!=(runtime/'wall_validation_sources').resolve():
        shutil.copytree(wall_sources,runtime/'wall_validation_sources',dirs_exist_ok=True)
    books=runtime_dir/'Project_Input_Workbooks'
    target_books=folder/'Project_Input_Workbooks'
    if books.is_dir() and books.resolve()!=target_books.resolve():shutil.copytree(books,target_books,dirs_exist_ok=True)
    for bundle_name in ('Material_Catalog','Research_Components'):
        bundle=runtime_dir/bundle_name
        if bundle.is_dir() and bundle.resolve()!=(runtime/bundle_name).resolve():
            shutil.copytree(bundle,runtime/bundle_name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    for path in runtime_dir.iterdir():
        if path.is_file() and path.suffix in ('.py','.md','.json') and path.parent.resolve()!=runtime.resolve():
            shutil.copy2(path,runtime/path.name)
    specs={'gravity_model_script':('OpenSees_Complete_Gravity_Model.py','elastic',False),
           'modal_model_script':('OpenSees_Complete_Linear_Model.py','elastic',True),
           'linear_model_script':('OpenSees_Complete_Linear_Model.py','elastic',True),
           'nonlinear_model_script':('OpenSees_Complete_Nonlinear_Model.py','nonlinear',True)}
    for role,(filename,mode,preload) in specs.items():
        manifest[role]=filename
        meta_inputs=dict(support_node_tags=[int(n) for n,v in (payload or {}).get('supports',{}).items() if v[2]],
                         total_downward_load_kN=(payload or {}).get('total_downward_load_kN'),load_steps=10,
                         coverage_note='Assembled frame/area distributed loads and self-weight; see V118 report for unsupported source actions and validation limits.')
        _write(folder/filename,"# Generated complete-model entry; units kN, m, s.\nfrom pathlib import Path\nimport sys, json, os\nHERE=Path(__file__).resolve().parent\nsys.path.insert(0,str(HERE/'OpenSees_Runtime_V118'))\nGRAVITY_GUI_INPUTS = "+repr(meta_inputs)+"\nfrom OpenSees_Complete_Export_V118 import build_complete_model\nMODEL_REPORT = build_complete_model(HERE, mode="+repr(mode)+", preload="+repr(preload)+", limit_state=os.environ.get('OPENSEES_LIMIT_STATE','ULS'))\nPD_FILE=HERE/'OpenSees_IS16700_Initial_PDelta_Results.json'\nIS16700_INITIAL_PDELTA_RESULTS=json.loads(PD_FILE.read_text(encoding='utf-8-sig')) if PD_FILE.is_file() else {}\n")
    story_file=folder/'OpenSees_Complete_Story_Masters_V118.csv'
    if payload:
        with story_file.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['story_number','story_name','master_node_tag','height_m','elevation_m']); w.writeheader()
            for g in sorted(payload['diaphragms'],key=lambda g:g['master_xyz'][2]):
                w.writerow(dict(story_number=g['storey_number'],story_name=f"Storey_{g['storey_number']}",master_node_tag=g['master_tag'],height_m=g['master_xyz'][2]-payload['base_z_m'],elevation_m=g['master_xyz'][2]-payload['base_z_m']))
    manifest['story_master_csv']=story_file.name
    manifest['esm_story_weight_csv']='NBC105_ESM_Story_Weights_Assembled_V118.csv'
    if payload:
        # Include wall/column mesh masses between floors. The old ledger only
        # summed diaphragm slaves and silently omitted these source weights.
        # Tributary convention: assign each active node's vertical load/mass
        # to the first floor at or above its elevation. Fixed-base masses are
        # excluded consistently with the horizontal eigenproblem.
        groups=sorted(payload['diaphragms'],key=lambda g:g['master_xyz'][2])
        story_rows=[]
        for g in groups:
            story_rows.append(dict(story_number=g['storey_number'],story_name=f"Storey_{g['storey_number']}",height_m=g['master_xyz'][2]-payload['base_z_m'],master_node_tag=g['master_tag'],dead_load_kN=0.,storage_live_load_kN=0.,other_live_load_kN=0.,roof_live_load_kN_ignored=0.,input_note='All active nodal source weights included; inter-floor mesh weights assigned to next floor above; fixed-base masses excluded. Compare with ETABS tributary conventions.'))
        for pat,values in patterns.items():
            factor=float(cfg['mass_factors'][pat])
            if factor not in (0.,.3,.6,1.):raise ValueError(f'Unsupported story mass factor {factor} for {pat}')
            if factor==0. and pat.casefold()!='roof live':continue
            key='roof_live_load_kN_ignored' if factor==0. else 'other_live_load_kN' if factor==.3 else 'storage_live_load_kN' if factor==.6 else 'dead_load_kN'
            for node,vec in values.items():
                if all(payload['supports'].get(str(node),[0]*6)[:2]):continue
                z=payload['nodes'][int(node)][2] if int(node) in payload['nodes'] else payload['nodes'][str(node)][2]
                index=next((i for i,g in enumerate(groups) if g['master_xyz'][2]>=z-1e-7),len(groups)-1)
                story_rows[index][key]-=float(vec[2])
        represented=sum(r['dead_load_kN']+.6*r['storage_live_load_kN']+.3*r['other_live_load_kN'] for r in story_rows)
        report['story_ledger_active_weight_kN']=represented
        report['story_ledger_mass_error_percent']=100*abs(represented-report['active_horizontal_seismic_weight_kN'])/max(1.,report['active_horizontal_seismic_weight_kN'])
        if report['story_ledger_mass_error_percent']>1e-7:raise ValueError('Story ledger does not reconcile with the assembled active nodal mass.')
        fields=['story_number','story_name','height_m','master_node_tag','dead_load_kN','storage_live_load_kN','other_live_load_kN','roof_live_load_kN_ignored','input_note']
        with (folder/manifest['esm_story_weight_csv']).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(story_rows)
    manifest['readiness_manifest']='OpenSees_Model_Readiness_Template_V116.json'
    template=runtime_dir/manifest['readiness_manifest']
    if template.exists() and not (folder/template.name).exists(): shutil.copy2(template,folder/template.name)
    area_config=folder/'OpenSees_Area_Model_Config_V116.json'
    if not area_config.exists() and (runtime_dir/'OpenSees_Area_Model_Config_TEMPLATE_V116.json').exists():
        shutil.copy2(runtime_dir/'OpenSees_Area_Model_Config_TEMPLATE_V116.json',area_config)
    manifest['elastic_assembled']=bool(payload); manifest['nonlinear_ready']=False
    _write(folder/'RUN_EXPORTED_PROJECT_GUI.py',
        "from pathlib import Path\nimport sys\nimport tkinter as tk\nHERE=Path(__file__).resolve().parent\nsys.path.insert(0,str(HERE/'OpenSees_Runtime_V118'))\nfrom ETABS_to_OpenSeesPy_Section_Review_V116_NBC105_Area_NLTHA import App\nif __name__=='__main__':\n    root=tk.Tk()\n    from OpenSees_Window_Manager_V129 import install_windows_menu\n    install_windows_menu(root)\n    app=App(root)\n    app.out.set(str(HERE))\n    root.mainloop()\n")
    _write(folder/MANIFEST,manifest); _write(folder/manifest['report'],report)
    from OpenSees_Mapping_Audit_V125 import export_excel
    export_excel(folder)
    return manifest,report


def apply_gravity_profile(data,cfg,profile,pattern_types=None):
    """Rebuild gravity only from unfactored loads; seismic mass stays unchanged."""
    from OpenSees_Storey_Gravity_V131 import classify
    if profile in ('AS_CONFIGURED','SEISMIC_SOURCE'):
        return dict(profile=profile,factors=dict(cfg['gravity_factors']),scope='Configured gravity preload, separate from mass_factors. NBC 8.1.1.2 / 9.3.1.2 refer TH gravity to 5.2; this is not the 1.2D+1.5L gravity strength combination. Review occupancy, roof and selected analysis purpose.')
    allowed={'GRAVITY_1.2D_1.5L':(1.2,1.5),'UPLIFT_0.9D':(.9,0.)}
    if profile not in allowed:raise ValueError('Unknown gravity profile '+profile)
    if not data.get('unfactored_patterns'):raise ValueError('Case-specific PDelta needs unfactored source patterns')
    dead,live=allowed[profile];factors={};gravity={};ledger={}
    for pattern,nodes in data['unfactored_patterns'].items():
        kind=classify('area_load',pattern,(pattern_types or {}).get(pattern))[1]
        if kind=='UNCLASSIFIED':raise ValueError('Cannot assign DL/LL factor to unclassified pattern '+pattern)
        factor=dead if kind=='DEAD' else live;factors[pattern]=factor
        gravity[pattern]={node:[float(v)*factor for v in values] for node,values in nodes.items()}
        ledger[pattern]=-sum(values[2] for values in gravity[pattern].values())
    data['gravity']=gravity;data['gravity_by_pattern_kN']=ledger;data['total_downward_load_kN']=sum(ledger.values())
    return dict(profile=profile,factors=factors,scope='Fresh combination preload with PDelta transformations; seismic mass retained from source mass factors')


def export_gravity_beam_actions(ops,data,folder,limit_state,mode):
    """Concurrent solver end actions for the full applied gravity preload."""
    rows=[]
    for tag,e in enumerate(data['frames'],100001):
        if e.get('category')!='BEAM':continue
        values=list(ops.eleResponse(tag,'localForce'))
        if len(values)!=12:continue
        for end,offset in (('I',0),('J',6)):
            rows.append(dict(source_frame=e['object'],solver_tag=tag,end=end,node=e['nodes'][0 if end=='I' else 1],limit_state=limit_state,mode=mode,N_kN=values[offset],Vy_kN=values[offset+1],Vz_kN=values[offset+2],T_kNm=values[offset+3],My_kNm=values[offset+4],Mz_kNm=values[offset+5],scope='Concurrent full gravity preload end actions; NOT unique floor-panel tributary UDL or design load-combination envelope'))
    path=Path(folder)/('Gravity_Beam_End_Actions_'+limit_state+'_V141.csv')
    if rows:
        with path.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return path


@timed_outputs('Model construction and optional gravity preload','folder')
def build_complete_model(folder, *, mode='elastic', preload=False, limit_state='ULS',
                        research_profile=None, gravity_system='UmfPack'):
    """Build all supported structural families, loads, mass and diaphragms."""
    research=research_profile in ('LITERATURE_EXPLORATORY_V138','LITERATURE_FRAME_NL_ELASTIC_WALL_V138','LITERATURE_BUILDING_NL_V161')
    research_elastic_walls=research_profile=='LITERATURE_FRAME_NL_ELASTIC_WALL_V138'
    if research_profile is not None and not research:raise ValueError('Unknown exploratory profile')
    if research and mode!='nonlinear':raise ValueError('Exploratory profile is only for the explicitly nonlinear research route')
    folder=Path(folder); report=_read(folder/'OpenSees_Complete_Export_Report_V118.json')
    if report['assembly_errors']: raise ValueError('Complete export blocked: '+'; '.join(report['assembly_errors']))
    data=_read(folder/'OpenSees_Complete_Model_Data_V118.json'); cfg=_read(folder/'OpenSees_Complete_Model_Config_V118.json')
    load_audit=_read(folder/'OpenSees_Load_Conversion_Audit.json')
    if any(e.get('category')=='FLOOR' for e in data.get('shells',[])) and any(load_audit.get(k)!='READ' for k in ('direct_uniform_loads_status','uniform_load_sets_status')):
        raise ValueError('Stale or unverified area-load extraction: re-export with the current launcher before analysis. Earlier equilibrium/modal PASS does not verify missing slab load sets.')
    import os
    profile=os.environ.get('OPENSEES_GRAVITY_PROFILE','AS_CONFIGURED')
    meta=_read(folder/'OpenSees_Source_Model_Metadata_V118.json')
    gravity_context=apply_gravity_profile(data,cfg,profile,meta.get('pattern_types',{}))
    print('[GRAVITY PROFILE]',json.dumps(gravity_context),flush=True)
    if data.get('config_sha256')!=hashlib.sha256((folder/'OpenSees_Complete_Model_Config_V118.json').read_bytes()).hexdigest():
        raise ValueError('Model config changed after assembly. Use Rebuild from saved export before running analysis.')
    if limit_state not in ('ULS','SLS'):raise ValueError('limit_state must be ULS or SLS')
    if mode not in ('elastic','nonlinear'): raise ValueError('Unknown model mode')
    if gravity_system not in ('UmfPack', 'SparseGeneral'):
        raise ValueError('gravity_system must be UmfPack or SparseGeneral')
    if mode=='nonlinear' and not research and not cfg.get('nonlinear_parameters_reviewed'):
        raise ValueError('Nonlinear model requires reviewed frame and wall constitutive inputs. Set nonlinear_materials_file and nonlinear_wall_fsam_tags in OpenSees_Complete_Model_Config_V118.json after calibration. The elastic assembled model is available for conversion/gravity checks.')
    from OpenSees_Mapping_Audit_V125 import read as read_mapping,OVERRIDES,add_device
    scenario=read_mapping(folder,OVERRIDES)
    overrides=scenario.get('assignments',{}) if scenario.get('active') else {}
    if mode=='elastic' and any(v.get('target') in ('FVD_MAXWELL','BRB_STEEL02') for v in overrides.values()):
        raise ValueError('Active FVD/BRB scenario requires a calibrated nonlinear model. Disable scenario activation to run the unchanged elastic baseline.')
    import openseespy.opensees as ops
    ops.wipe(); ops.model('basic','-ndm',3,'-ndf',6)
    for n,p in data['nodes'].items(): ops.node(int(n),*p)
    for n,flags in data['supports'].items(): ops.fix(int(n),*flags)
    for g in data['diaphragms']:
        ops.node(g['master_tag'],*g['master_xyz']); ops.fix(g['master_tag'],0,0,1,1,1,0)
        if g['slave_node_tags']: ops.rigidDiaphragm(3,g['master_tag'],*g['slave_node_tags'])
    if mode=='nonlinear':
        import runpy
        from Define_Section_V109 import define_all_fiber_sections
        if research_profile=='LITERATURE_BUILDING_NL_V161':
            from components.nonlinear_time_history.research_building_materials import define_building_materials
            research_wall=define_building_materials(ops,data,folder)
        else:
            define_all_fiber_sections(ops,unit_system='kN-m')
        if research and research_profile!='LITERATURE_BUILDING_NL_V161':
            from Define_Section_V109 import define_wall_reference_materials
            research_wall=define_wall_reference_materials(ops,unit_system='kN-m')
        elif not research:
            material_file=Path(cfg['nonlinear_materials_file'])
            if not material_file.is_absolute(): material_file=folder/material_file
            result=runpy.run_path(str(material_file)); result['define_materials'](ops)
    section_tags={'SHS_350x350x16_STEEL_FIBER':701,'RC_BEAM_600x800_FIBER':611,'RC_COLUMN_1100x1100_FIBER':621,'RC_COLUMN_1250x1250_FIBER':631}
    tag=100000; used_sections={}; element_map={}; element_labels={}
    for e in data['frames']:
        tag+=1; p=e['properties']
        element_labels[tag] = dict(
            source_object=str(e['object']), category=e['category'],
            nodes=e['nodes'], property=p.get('section'))
        selection=overrides.get('SOLVER:'+str(tag),overrides.get('FRAME:'+str(e['object']),{}))
        if mode=='nonlinear' and selection.get('target') in ('FVD_MAXWELL','BRB_STEEL02'):
            if 'SOLVER:'+str(tag) not in overrides and sum(q['object']==e['object'] for q in data['frames'])!=1:
                raise ValueError('Segmented brace: assign individual solver segments after reviewing intermediate connections.')
            add_device(ops,tag,e,selection);element_map.setdefault('FRAME:'+e['object'],[]).append(tag);continue
        ops.geomTransf('PDelta',tag,*e['basis'][2])
        if mode=='elastic':
            factor=1. if p['E']>1e8 else (.9 if limit_state=='SLS' else .7) if e['category']=='COLUMN' else (.7 if limit_state=='SLS' else .35)
            # OpenSees release codes: 1=i, 2=j, 3=both. Condensed beam
            # retains transverse-load response; torsion released at either end
            # means no torsion transfer through the member.
            # https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/elasticBeamColumn.html
            rel=int(e.get('release_i',False))+2*int(e.get('release_j',False))
            ops.element('elasticBeamColumn',tag,*e['nodes'],p['A'],p['E'],p['G'],0. if e.get('hinged_brace') else p['J'],p['Iy']*factor,p['Iz']*factor,tag,'-releasey',rel,'-releasez',rel)
        else:
            if e.get('hinged_brace') and research:
                # Explicit idealized axial brace; no buckling/fracture capability claimed.
                mat=800000+tag;ops.uniaxialMaterial('Steel01',mat,345000.,p['E'],.01)
                ops.element('corotTruss',tag,*e['nodes'],p['A'],mat)
                element_map.setdefault('FRAME:'+e['object'],[]).append(tag);continue
            if e.get('hinged_brace'): raise ValueError(f"ETABS frame {e['object']} | OpenSees solver tag {tag}: nonlinear end-release formulation is not implemented")
            target=selection.get('target') or cfg['frame_section_mapping'].get(p['section']); sec=section_tags.get(target)
            if sec is None: raise ValueError(f"No nonlinear section mapping for {p['section']}")
            ops.beamIntegration('Lobatto',tag,sec,5)
            ops.element('forceBeamColumn',tag,*e['nodes'],tag,tag,'-iter',30,1e-10)
        element_map.setdefault('FRAME:'+e['object'],[]).append(tag)
    for e in data['shells']:
        tag+=1; p=e['properties']; key=p['property']
        element_labels[tag] = dict(
            source_object=str(e['object']), category=e['category'],
            nodes=e['nodes'], property=key)
        if mode=='nonlinear' and e['category']=='SHEAR WALL' and not research_elastic_walls:
            fsam=int(research_wall['property_tags'][key] if research_profile=='LITERATURE_BUILDING_NL_V161' else research_wall['tags']['fsam_web'] if research else cfg['nonlinear_wall_fsam_tags'][key]); width=math.dist(data['nodes'][str(e['nodes'][0])],data['nodes'][str(e['nodes'][1])])
            fibers=int(cfg.get('wall_macro_fibers',5))
            if fibers<2:raise ValueError('E_SFI wall needs separated axial macro-fibers; a single centered fiber does not supply in-plane flexural stiffness')
            ops.element('E_SFI_MVLEM_3D',tag,*e['nodes'],fibers,'-thick',*[p['thickness']]*fibers,'-width',*[width/fibers]*fibers,'-mat',*[fsam]*fibers,'-Density',0.)
        else:
            if key not in used_sections:
                sec=500000+len(used_sections); used_sections[key]=sec
                factor=float(cfg.get('slab_bending_factor_sls',.35) if limit_state=='SLS' else cfg['slab_bending_factor']) if e['category']=='FLOOR' else (.7 if limit_state=='SLS' else .5) if research_elastic_walls and e['category']=='SHEAR WALL' else 1.
                root=math.sqrt(_positive(factor,'slab bending factor'))
                ops.section('ElasticMembranePlateSection',sec,p['E']/root,p['nu'],p['thickness']*root,0.)
            ops.element('ShellMITC4',tag,*e['nodes'],used_sections[key])
        element_map.setdefault('AREA:'+e['object'],[]).append(tag)
    for n,m in data['nodal_mass'].items(): ops.mass(int(n),m,m,m,0.,0.,0.)
    for i,(pattern,values) in enumerate(data['gravity'].items(),700001):
        ops.timeSeries('Linear',i); ops.pattern('Plain',i,i)
        for n,vector in values.items(): ops.load(int(n),*vector)
    if preload:
        from OpenSees_Analysis_Stack_V110 import run_gravity_stage
        gravity_system_options = ('-piv',) if gravity_system == 'SparseGeneral' else ()
        diagnostic_path = folder / ('Gravity_Failure_Diagnostics_' + limit_state + '.json')
        print('[GRAVITY SOLVER]', gravity_system,
              'options=' + repr(gravity_system_options),
              '| adaptive=' + str(research_profile == 'LITERATURE_BUILDING_NL_V161'),
              flush=True)
        gravity_report=run_gravity_stage(
            ops, [int(n) for n,v in data['supports'].items() if v[2]],
            data['total_downward_load_kN'], model_nodes=list(map(int,data['nodes'])),
            nsteps=20, system=gravity_system,
            system_options=gravity_system_options,
            diagnostic_path=diagnostic_path,
            element_labels=element_labels,
            adaptive=research_profile=='LITERATURE_BUILDING_NL_V161')
        from OpenSees_Model_Audit_V130 import check_kinematics
        gravity_report['diaphragm_kinematics']=check_kinematics(ops,data)
        gravity_report['gravity_context']=gravity_context
        gravity_report['limit_state']=limit_state
        _write(folder/('Gravity_Profile_'+limit_state+'_'+profile+'_V142.json'),gravity_report)
        _write(folder/'OpenSees_Complete_Gravity_Check_V118.json',gravity_report)
        export_gravity_beam_actions(ops,data,folder,limit_state,mode)
    _write(folder/'OpenSees_Complete_Element_Map_V118.json',element_map)
    return dict(mode=mode,preload_completed=preload,nodes=len(ops.getNodeTags()),elements=len(ops.getEleTags()),analysis_ready=False,research_profile=research_profile,scope='EXPLORATORY_ASSUMED_MATERIALS_NOT_DESIGN_ACCEPTANCE' if research else 'REVIEWED_MODEL_INPUT_GATE')


def autoselect_inputs(gui, export_dir, role):
    """Populate only files named by the current export manifest."""
    folder=Path(export_dir).expanduser().resolve(); path=folder/MANIFEST
    if not path.is_file(): return False
    manifest=_read(path); model=folder/manifest[role]
    if not model.is_file(): return False
    variable=getattr(gui,'model_var',None) or getattr(gui,'model',None) or getattr(gui,'model_script',None)
    if getattr(variable,'get',lambda:None)()!=str(model):variable.set(str(model))
    for attr in ('output_var','output','outdir'):
        var=getattr(gui,attr,None)
        if var is not None: var.set(str(folder/'OpenSees_Analysis_Results'))
    for attr,key in (('stories','story_master_csv'),('readiness','readiness_manifest')):
        var=getattr(gui,attr,None); target=folder/manifest.get(key,'')
        draft=folder/('OpenSees_Model_Readiness_Draft_'+model.stem+'_V134.json')
        if attr=='readiness' and draft.is_file():target=draft
        if attr=='readiness' and (folder/'OpenSees_Model_Readiness_V116.json').is_file():target=folder/'OpenSees_Model_Readiness_V116.json'
        if var is not None and target.is_file(): var.set(str(target))
    unit_var=getattr(gui,'model_length_unit',None)
    if unit_var is not None:unit_var.set('m')  # These manifest entries are generated in kN-m-s.
    path_var=getattr(gui,'path',None)
    story_weights=folder/manifest.get('esm_story_weight_csv','')
    if path_var is not None and story_weights.is_file():
        path_var.set(str(story_weights))
        if hasattr(gui,'_load_story_metadata'): gui._load_story_metadata(str(story_weights))
    if hasattr(gui,'_read_code_inputs'): gui._read_code_inputs(show_error=False)
    height=getattr(gui,'height',None)
    data_file=folder/'OpenSees_Complete_Model_Data_V118.json'
    if height is not None and data_file.is_file():
        data=_read(data_file); height.set(str(max(p[2] for p in data['nodes'].values())-data['base_z_m']))
    try:
        from OpenSees_Project_Inputs_V123 import populate
        if role=='modal_model_script' and hasattr(gui,'aw_x'):populate(gui,Path(__file__).parent,folder)
        if role in ('linear_model_script','nonlinear_model_script') and hasattr(gui,'t1x'):
            from OpenSees_Linear_Autofill_V124 import populate_linear
            populate_linear(gui,folder)
    except Exception as exc:
        status=getattr(gui,'status',None)
        if status is not None:status.set('Project input import: '+str(exc))
    return True
