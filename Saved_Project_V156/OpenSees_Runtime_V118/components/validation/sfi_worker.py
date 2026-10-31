"""Isolate native SFI failures from the desktop and other validation cases."""
from pathlib import Path
import sys,json,traceback
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
 from components.validation.wall_validation import esfi
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
 try:result=esfi(out,element='SFI_MVLEM_3D')
 except Exception as e:result={'status':'FAILED','error':str(e)};traceback.print_exc()
 (out/'worker_result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
