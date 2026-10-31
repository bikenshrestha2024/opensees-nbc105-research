from pathlib import Path
import sys,runpy,os
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
runpy.run_path(str(ROOT/'OpenSees_Nonlinear_Time_History_NBC105_V116.py'),run_name='__main__')
