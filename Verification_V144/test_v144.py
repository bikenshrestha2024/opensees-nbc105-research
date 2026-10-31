from pathlib import Path
import ast,sys,csv,json
p=Path('outputs/OpenSees_NBC105_V144').resolve();sys.path.insert(0,str(p))
for f in p.rglob('*.py'):
 if '__pycache__' not in f.parts:ast.parse(f.read_text(encoding='utf-8-sig'))
from OpenSees_Workflow_V144 import inventory,STEPS
facts=inventory('D:/Thesis Opensees/Etabs Nodes Export 1');assert facts['model_counts']['nodes']>1000
for _,name,_ in STEPS:assert (p/name).is_file(),name
from OpenSees_Building_Response_V144 import figure
files=list(Path('D:/Thesis Opensees/Etabs Nodes Export 1/OpenSees_Analysis_Results').rglob('Building_Nonlinear_history.csv'));assert files
fig=figure(files[0]);fig.savefig('work/V144_Response_Legacy_Check.png',dpi=100)
print('Syntax, 9 numbered launcher targets, actual input inventory and legacy-history plot PASS')
