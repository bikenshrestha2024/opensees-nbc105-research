"""Read-only connectivity evidence. Run with model export folder as argument.

Shared node tags are a necessary connectivity check, not proof of correct
load distribution, stiffness, or agreement with ETABS. No input is modified.
"""
import json, sys
from pathlib import Path
from collections import defaultdict

def audit(folder):
    folder=Path(folder)
    data=json.loads((folder/'OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'))
    groups=defaultdict(set); counts=defaultdict(int)
    for e in data['shells']:
        key=(e['category'],str(e['object'])); groups[key].update(e['nodes']); counts[key]+=1
    frame_nodes=defaultdict(set)
    for e in data['frames']: frame_nodes[e['category']].update(e['nodes'])
    wall_objects={obj:nodes for (cat,obj),nodes in groups.items() if cat=='SHEAR WALL'}
    walls=set().union(*(ns for (cat,_),ns in groups.items() if cat=='SHEAR WALL'))
    supports=set(map(int,data['supports']))
    known_nodes=set(map(int,data['nodes']))
    element_rows=[('FRAME',e) for e in data['frames']]+[('SHELL',e) for e in data['shells']]
    missing_node_references=[
        {'kind':kind,'object':str(e['object']),'category':e['category'],
         'nodes':[int(node) for node in e['nodes'] if int(node) not in known_nodes]}
        for kind,e in element_rows if any(int(node) not in known_nodes for node in e['nodes'])
    ]
    result={'folder':str(folder),
            'scope':'Direct node-ID evidence only. Missing direct sharing does not prove a disconnected load path where constraints, links or generated connectivity are present. Geometry, element stiffness, end forces, mesh convergence and ETABS comparison require independent verification.',
            'slabs':[], 'walls':[], 'wall_object_connectivity':[],
            'missing_node_references':missing_node_references}
    for (cat,obj), ns in groups.items():
        if cat=='FLOOR':
            row={'object':obj,'cells':counts[(cat,obj)],'shared_beam_nodes':len(ns & frame_nodes['BEAM']),'shared_wall_nodes':len(ns & walls),'shared_column_nodes':len(ns & frame_nodes['COLUMN']),'shared_brace_nodes':len(ns & frame_nodes['BRACE'])}
            result['slabs'].append(row)
        elif cat=='SHEAR WALL':
            other_wall_nodes=set().union(*(other for other_obj,other in wall_objects.items() if other_obj!=obj))
            row={'object':obj,'cells':counts[(cat,obj)],'shared_frame_nodes':len(ns & set().union(*frame_nodes.values())),'shared_brace_nodes':len(ns & frame_nodes['BRACE']),'supported_nodes':len(ns & supports),'shared_other_wall_object_nodes':len(ns & other_wall_nodes)}
            result['walls'].append(row)
            result['wall_object_connectivity'].append({'object':obj,'cells':counts[(cat,obj)],'shared_other_wall_object_nodes':row['shared_other_wall_object_nodes'],'status':'shared node IDs found' if row['shared_other_wall_object_nodes'] else 'no direct shared node IDs; inspect constraints and load path'})
    result['summary']={'slab_objects':len(result['slabs']),'slabs_without_direct_beam_or_wall_node':sum(not (x['shared_beam_nodes'] or x['shared_wall_nodes']) for x in result['slabs']),'wall_objects':len(result['walls']),'wall_objects_without_direct_shared_wall_nodes':sum(not x['shared_other_wall_object_nodes'] for x in result['walls']),'missing_node_reference_count':sum(len(x['nodes']) for x in missing_node_references),'gravity_total_kN':data.get('total_downward_load_kN'),'gravity_by_pattern_kN':data.get('gravity_by_pattern_kN')}
    return result

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python 20_AUDIT_LOAD_CONNECTIONS.py <export folder>')
    print(json.dumps(audit(sys.argv[1]),indent=2))
