from pathlib import Path
import runpy,os
os.environ['OPENSEES_PROJECT_FOLDER']=str(Path(__file__).resolve().parent)
runpy.run_path(str(Path(__file__).resolve().parent/'OpenSees_Runtime_V118/RUN_ETABS_TO_OPENSEES.py'),run_name='__main__')
