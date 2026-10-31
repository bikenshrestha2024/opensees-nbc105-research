"""Run isolated component baselines. This does not run or approve a building model."""
from pathlib import Path
import subprocess,sys,json,datetime
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
 out=ROOT/'results'/datetime.datetime.now().strftime('Components_%Y%m%d_%H%M%S');out.mkdir(parents=True)
 results={}
 for model in ('Concrete01','Concrete02','ConcreteCM','Steel02','SteelMPF','FVD','BRB','SFI_MVLEM_3D'):
  print('[START]',model,flush=True)
  run=subprocess.run([sys.executable,'-u','-m','components.validation.parameter_studies',str(ROOT/'cards'/(model+'.json')),str(out/model)],cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace')
  (out/(model+'.log')).write_text(run.stdout+run.stderr,encoding='utf8');results[model]=dict(exit_code=run.returncode,output=str(out/model));print('[COMPLETE]' if not run.returncode else '[FAILED]',model,flush=True)
 (out/'Run_Summary.json').write_text(json.dumps(results,indent=2));print('Results:',out)

 if "--no-gui" not in sys.argv:
  from components.validation.research_results_gui import main
  main(out)
