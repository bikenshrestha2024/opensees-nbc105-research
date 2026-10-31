from pathlib import Path
import sys,tkinter as tk,shutil,json,ast
p=Path('outputs/OpenSees_NBC105_V141').resolve();sys.path.insert(0,str(p));folder=Path('work/V141_Project_Rebuild').resolve()
from OpenSees_Results_UI_V127 import library_window
from OpenSees_Load_Path_V141 import launch
root=tk.Tk();root.withdraw();w=library_window(root,folder);root.update();tabs=next(c for c in w.winfo_children() if c.winfo_class()=='TNotebook');assert len(tabs.tabs())==4
launch(root,folder);root.update();print('Native library and load-path mesh GUI PASS');root.destroy()
from OpenSees_Complete_Export_V118 import export_gravity_beam_actions
class Solver:
 def eleResponse(self,tag,query):return list(range(12))
f=export_gravity_beam_actions(Solver(),{'frames':[{'category':'BEAM','object':'A','nodes':[1,2]}]},folder,'TEST','elastic');assert f.is_file();f.unlink()
source=Path(r'D:/Thesis Opensees/Etabs Nodes Export 1');preview=p/'Viewer_Preview_V141';preview.mkdir(exist_ok=True)
for name in ['OpenSees_Structural_Elements_By_Storey.html','OpenSees_Element_Connectivity_3D.html','OpenSees_Element_Connectivity.json','OpenSees_Source_Model_Metadata_V118.json']:shutil.copy2(source/name,preview/name)
from OpenSees_ID_Audit_V120 import export_id_audit
export_id_audit(preview)
for name in ['OpenSees_Structural_Elements_By_Storey.html','OpenSees_Element_Connectivity_3D.html']:assert 'Slab outline overlay (display only)' in (preview/name).read_text(encoding='utf8')
for f in p.rglob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'))
print('View overlay controls, beam action exporter and all Python syntax PASS')
