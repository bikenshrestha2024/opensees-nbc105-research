from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent/'OpenSees_Wall_Validation_V147.py'),run_name='__main__')
