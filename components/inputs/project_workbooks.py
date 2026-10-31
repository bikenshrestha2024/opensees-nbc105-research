"""Explicit Excel → GUI mapping. Workbook formulas are not evaluated by openpyxl.

Imported data remain attributed project inputs; no import certifies code
compliance or replaces the independent ETABS/OpenSees reconciliation.
"""

__release__ = '134'
from pathlib import Path
import json

CALCULATOR='NBC105_2025_Seismic_Calculator_ETABS_Direct Interaction - Copy.xlsx'
SCALING='ULTIMATE LOAD  - NEPAL - 3 - BELT TRUSS, OUTRIGGER CAP TRUSS_NBC105_RS_Scaling.xlsx'


SERVICE_SCALING='SERVICE LOAD  - NEPAL - 3 - BELT TRUSS, OUTRIGGER CAP TRUSS_NBC105_RS_Scaling_2.xlsx'

def source_workbooks(root, export_dir,limit_state='ULS'):
    root=Path(root);export_dir=Path(export_dir)
    search=[export_dir/'Project_Input_Workbooks',root/'Project_Input_Workbooks',Path(r'D:/Thesis/Main Python Programs/Excel Sheets')]
    selected=export_dir/'NBC105_Workbook_Source.json'
    if selected.is_file():
        names=json.loads(selected.read_text(encoding='utf-8-sig'))
        return [Path(p) for p in names.get('workbooks',[]) if Path(p).is_file()]
    # Named files only: never take the newest workbook from another scenario.
    return [next((d/name for d in search if (d/name).is_file()),None) for name in (CALCULATOR,SERVICE_SCALING if str(limit_state).upper()=='SLS' else SCALING)]


def import_project_inputs(root, export_dir,limit_state='ULS'):
    from openpyxl import load_workbook
    values={};audit=[];notes=[];gross_spans={}
    def put(key,value,path,sheet,cell):
        if value is None or str(value).startswith('='):return
        values[key]=value;audit.append(dict(field=key,value=value,source=str(path),sheet=sheet,cell=cell))
    for path in source_workbooks(root,export_dir,limit_state):
        if path is None:continue
        wb=load_workbook(path,data_only=True,read_only=True)
        if 'NBC Calculator' in wb:
            ws=wb['NBC Calculator']
            for key,cell in {'soil':'B9','Z':'B10','I':'B11','period_factor':'B15','system_excel':'E10'}.items():put(key,ws[cell].value,path,ws.title,cell)
            system=ws['E10'].value
            if 'NBC Parameters' in wb:
                for row in wb['NBC Parameters'].iter_rows(min_row=16,max_row=36,max_col=4):
                    if row[0].value==system:
                        for key,c in zip(('rmu','omegau','omegas'),row[1:]):put(key,c.value,path,'NBC Parameters',c.coordinate)
            # B16/B17 are ambiguously labelled ETABS/Rayleigh in the workbook.
            # Import neither as Rayleigh without its force/displacement evidence.
            if ws['B16'].value or ws['B17'].value:notes.append('Workbook B16/B17 need a method/source classification; not assigned as Rayleigh periods.')
        if 'SCALING SUMMARY' in wb:
            ws=wb['SCALING SUMMARY']
            for key,cell in {'awx':'B14','awy':'B15','workbook_adopted_tx':'C14','workbook_adopted_ty':'C15','reference_base_shear_X':'E7','reference_base_shear_Y':'E8','source_edb':'B4'}.items():put(key,ws[cell].value,path,ws.title,cell)
        if 'ETABS MASTER IMPORT' in wb:
            for row in wb['ETABS MASTER IMPORT'].iter_rows(min_row=6,max_col=7,values_only=True):
                if row[0] in ('X','Y') and isinstance(row[4],(int,float)) and row[4]>0:
                    gross_spans.setdefault(row[0],set()).add(float(row[4])/1000.)
        wb.close()
    folder=Path(export_dir)
    topology=folder/'OpenSees_Element_Connectivity.json'
    if topology.is_file():
        topo=json.loads(topology.read_text(encoding='utf-8-sig'));xyz=[n['coordinates_m'] for n in topo.get('node_map',[])]
        if xyz:
            values['breadth_X']=max(p[1] for p in xyz)-min(p[1] for p in xyz)
            values['breadth_Y']=max(p[0] for p in xyz)-min(p[0] for p in xyz)
            notes.append('Plan breadth is computed from the selected source geometry; confirm per-floor accidental eccentricity for setbacks.')
            # Recalculate net first-story wall areas from the CURRENT export.
            # Gross bay wall lengths come from the explicitly supplied master
            # workbook. No arbitrary grouping of piers across openings is
            # inferred when those gross spans are absent or nonuniform.
            try:
                from OpenSees_Complete_Export_V118 import _area_property
                assignments=json.loads((folder/'OpenSees_Section_Assignment_Audit.json').read_text(encoding='utf-8-sig'))
                area_rows={str(r.get('etabs_area_object')):r for r in assignments['area_assignments']}
                coords={n['opensees_node_tag']:n['coordinates_m'] for n in topo['node_map']}
                base=min(p[2] for p in xyz);roof=max(p[2] for p in xyz);H=roof-base
                levels=sorted({g['master_xyz'][2] for g in topo['rigid_diaphragm_groups'] if g['master_xyz'][2]>base+1e-6})
                first=levels[0];lines={}
                for e in topo['elements']:
                    if e['category']!='SHEAR WALL':continue
                    q=[coords[n] for n in e['node_tags']]
                    if abs(min(p[2] for p in q)-base)>1e-6 or max(p[2] for p in q)<first-1e-6:continue
                    dx=max(p[0] for p in q)-min(p[0] for p in q);dy=max(p[1] for p in q)-min(p[1] for p in q)
                    if dx>1e-6 and dy<1e-6:axis='X';along=0;across=1
                    elif dy>1e-6 and dx<1e-6:axis='Y';along=1;across=0
                    else:raise ValueError('Non-axis-aligned wall: directional projected properties need separate review.')
                    thickness=_area_property(area_rows[str(e['etabs_object'])],{})['thickness']
                    lines.setdefault((axis,round(q[0][across],6),thickness),[]).append((min(p[along] for p in q),max(p[along] for p in q)))
                aw={'X':0.,'Y':0.};segments=[]
                for (axis,plane,t),intervals in lines.items():
                    spans=gross_spans.get(axis,set())
                    if len(spans)!=1:raise ValueError('A single reviewed gross wall-bay span per direction is required for automatic wall grouping.')
                    length=next(iter(spans));start=min(a for a,b in intervals);end=max(b for a,b in intervals)
                    import math
                    count=round((end-start)/length)
                    if count<1 or abs(start+count*length-end)>1e-5:raise ValueError('Source wall extents do not match the workbook gross-bay spans.')
                    for i in range(count):
                        lo=start+i*length;hi=lo+length
                        pieces=sorted((max(a,lo),min(b,hi)) for a,b in intervals if min(b,hi)>max(a,lo)+1e-8)
                        merged=[]
                        for a,b in pieces:
                            if merged and a<=merged[-1][1]+1e-8:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                            else:merged.append((a,b))
                        net=sum(b-a for a,b in merged);area=t*net;contribution=area*(.2+min(length/H,.9)**2)
                        aw[axis]+=contribution;segments.append(dict(axis=axis,plane_m=plane,bay_start_m=lo,bay_end_m=hi,thickness_m=t,net_wall_length_m=net,net_area_m2=area,gross_wall_length_m=length,Aw_contribution_m2=contribution))
                if not all(v>0 for v in aw.values()):raise ValueError('Both directions need recognized first-story walls.')
                for axis in ('X','Y'):
                    key='aw'+axis.lower()
                    if key in values:values['workbook_'+key]=values[key]
                    put(key,aw[axis],topology,'first-story wall geometry','Σ t·Lnet·[0.2+min(Lgross/H,0.9)^2]')
                values['wall_geometry_segments']=segments
                notes.append('Aw recalculated from current full-first-story wall piers; opening gaps are excluded. Uniform gross bay spans are from ETABS MASTER IMPORT. Review this grouping if wall layouts, basement exclusions or bay spans change.')
            except Exception as exc:
                notes.append('Live wall Aw reconstruction unavailable; imported workbook Aw remains a review input: '+str(exc))
    ray=folder/'OpenSees_Analysis_Results/NBC105_Rayleigh_Preliminary_V123.json'
    data=folder/'OpenSees_Complete_Model_Data_V118.json'
    if ray.is_file() and data.is_file():
        import hashlib
        result=json.loads(ray.read_text(encoding='utf-8-sig'))
        ledger=folder/'NBC105_ESM_Story_Weights_Assembled_V118.csv'
        if (result.get('method_version',0)>=124 and result.get('model_sha256')==hashlib.sha256(data.read_bytes()).hexdigest() and ledger.is_file() and result.get('story_weights_sha256')==hashlib.sha256(ledger.read_bytes()).hexdigest()):
            for axis in ('X','Y'):put('rayleigh_t'+axis.lower(),result[axis]['period_s'],ray,axis,'period_s')
        else:notes.append('Saved Rayleigh results are stale after a model rebuild; rerun the preliminary analysis.')
    notes.append('Regularity is not inferred from Excel or model symmetry. Confirm NBC §5.4 for the asymmetric building.')
    return dict(values=values,audit=audit,notes=notes)


def populate(gui, root, folder):
    state=getattr(gui,'ls',getattr(gui,'limit_state',getattr(gui,'state',None)))
    state=state.get() if state is not None else 'ULS'
    data=import_project_inputs(root,folder,state);v=data['values']
    for key in ('soil','Z','I','awx','awy','rmu','omegau','omegas','period_factor','rayleigh_tx','rayleigh_ty'):
        var=getattr(gui,key,None)
        if var is not None and key in v:var.set(str(v[key]))
    # The project's explicitly stated location, not a municipality inferred
    # from a filename or an unverified zoning lookup.
    if hasattr(gui,'location') and not gui.location.get():gui.location.set('Kirtipur')
    if 'Dual' in str(v.get('system_excel','')) and 'Shear wall' in str(v.get('system_excel','')):
        if hasattr(gui,'system'):gui.system.set('RC dual system with shear wall')
    for target,source in [('aw_x','awx'),('aw_y','awy'),('tr_x','rayleigh_tx'),('tr_y','rayleigh_ty')]:
        if hasattr(gui,target) and source in v:getattr(gui,target).set(str(v[source]))
    if hasattr(gui,'bdim'):
        gui.bdim.set(str(v.get('breadth_'+gui.direction.get(),'')))
    gui.project_input_audit=data
    return data


def connect_etabs():
    """Use CSI Helper attachment first; tolerate ROT registration differences."""
    import comtypes.client
    errors=[]
    try:
        helper=comtypes.client.CreateObject('ETABSv1.Helper')
        try:
            from comtypes.gen import ETABSv1
            helper=helper.QueryInterface(ETABSv1.cHelper)
        except ImportError:pass
        etabs=helper.GetObject('CSI.ETABS.API.ETABSObject')
        if etabs is not None:return etabs
    except Exception as exc:errors.append(str(exc))
    try:return comtypes.client.GetActiveObject('CSI.ETABS.API.ETABSObject')
    except Exception as exc:raise RuntimeError('ETABS attachment failed. Use the same Windows account and elevation for ETABS and Python. Cached workbook inputs remain available. '+str(exc)+'; '+ '; '.join(errors)) from exc
