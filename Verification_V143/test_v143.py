from pathlib import Path
import sys,ast,json,shutil
root=Path('outputs/OpenSees_NBC105_V143').resolve();p=root/'components/validation/case_review.py';s=p.read_text().replace("grouped.setdefault(row['case'],[]).append(row)","grouped.setdefault(row['case']+' '+row.get('axis',''),[]).append(row)").replace("str(r['storey']).isdigit()","str(r['storey']).replace('.','',1).isdigit()").replace("key=lambda r:int(r['storey'])","key=lambda r:float(r['storey'])").replace("[int(r['storey']) for r in valid]","[float(r['storey']) for r in valid]").replace("saved floor-edge deflection","saved deflection (case envelope)").replace("ylabel='Storey')\n            for ax", "ylabel='Storey / elevation (see source workbook)')\n            for ax");p.write_text(s)
for f in (root/'components').rglob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'))
sys.path.insert(0,str(root))
from OpenSees_MRSM_Reports_V134 import saved_cases,figures
cases=saved_cases(Path('D:/Thesis Opensees/Etabs Nodes Export 1/OpenSees_Analysis_Results'));plots=figures(cases);out=Path('work/V143_Checks');out.mkdir(exist_ok=True);plots[-1][1].savefig(out/'MRSM_comparison.png',dpi=120);print('MRSM cases',len(cases),'figures',len(plots))
# Stop immediately at model construction: verify required isolated inputs without a costly FE solve.
import OpenSees_Complete_Export_V118 as assembly
class VerifiedStop(Exception):pass
def verify(folder,**kwargs):
 for name in ('OpenSees_Load_Conversion_Audit.json','OpenSees_Source_Model_Metadata_V118.json'):
  assert (Path(folder)/name).is_file(),name
 raise VerifiedStop()
assembly.build_complete_model=verify
from OpenSees_Building_Exploratory_V138 import run
try:run(dict(model_folder='D:/Thesis Opensees/Etabs Nodes Export 1',output_dir=str(out/'trial'),x_path=str(next((root/'Input_Records_V141').rglob('*.txt'))),y_path=str(next((root/'Input_Records_V141').rglob('*.txt'))),duration_s=.01,dt_s=.005,orientations=['XY']))
except VerifiedStop:print('Isolated input handoff PASS; no transient solve performed')
