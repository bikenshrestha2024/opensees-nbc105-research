"""Logged fresh-process startup. Errors remain visible after the launcher exits."""
from pathlib import Path
import sys,subprocess,os,runpy,datetime,traceback
ROOT=Path(__file__).resolve().parent

def main():
    logs=ROOT/'Startup_Logs';logs.mkdir(exist_ok=True)
    if '--fresh-child' not in sys.argv:
        stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        log=logs/('startup_'+stamp+'.log')
        env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONUTF8':'1','OPENSEES_STARTUP_LOG':str(log)}
        with log.open('w',encoding='utf8') as stream:
            stream.write('V155 startup | '+sys.executable+'\nRoot: '+str(ROOT)+'\n');stream.flush()
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--fresh-child'],cwd=str(ROOT),env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (logs/'LATEST.txt').write_text(str(log),encoding='utf8')
        code=child.wait()
        if code:
            import tkinter as tk
            from tkinter import messagebox
            root=tk.Tk();root.withdraw();messagebox.showerror('OpenSees startup failed','Exit code: '+str(code)+'\nDetails saved in:\n'+str(log)+'\n\n'+log.read_text(encoding='utf8',errors='replace')[-3000:],parent=root);root.destroy()
        return code
    try:
        sys.path.insert(0,str(ROOT))
        runpy.run_path(str(ROOT/'ETABS_to_OpenSeesPy_Section_Review_V116_NBC105_Area_NLTHA.py'),run_name='__main__')
        return 0
    except BaseException:
        traceback.print_exc();return 1
if __name__=='__main__':sys.exit(main())
