from pathlib import Path
import sys,runpy,os
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
runpy.run_path(str(ROOT/'RUN_ETABS_TO_OPENSEES.py'),run_name='__main__')
