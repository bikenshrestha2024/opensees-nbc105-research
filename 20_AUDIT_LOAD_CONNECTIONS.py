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
    walls=set().union(*(ns for (cat,_),ns in groups.items() if cat=='SHEAR WALL'))
    supports=set(map(int,data['supports']))
    result={'folder':str(folder),'scope':'Shared node IDs only; geometry, element stiffness, end forces, mesh convergence and ETABS comparison require independent verification.', 'slabs':[], 'walls':[]}
    for (cat,obj), ns in groups.items():
        if cat=='FLOOR':
            row={'object':obj,'cells':counts[(cat,obj)],'shared_beam_nodes':len(ns & frame_nodes['BEAM']),'shared_wall_nodes':len(ns & walls),'shared_column_nodes':len(ns & frame_nodes['COLUMN'])}
            result['slabs'].append(row)
        elif cat=='SHEAR WALL':
            row={'object':obj,'cells':counts[(cat,obj)],'shared_frame_nodes':len(ns & set().union(*frame_nodes.values())),'supported_nodes':len(ns & supports)}
            result['walls'].append(row)
    result['summary']={'slab_objects':len(result['slabs']),'slabs_without_direct_beam_or_wall_node':sum(not (x['shared_beam_nodes'] or x['shared_wall_nodes']) for x in result['slabs']),'wall_objects':len(result['walls']),'gravity_total_kN':data.get('total_downward_load_kN'),'gravity_by_pattern_kN':data.get('gravity_by_pattern_kN')}
    return result

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python 20_AUDIT_LOAD_CONNECTIONS.py <export folder>')
    print(json.dumps(audit(sys.argv[1]),indent=2))
