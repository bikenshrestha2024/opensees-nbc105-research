from pathlib import Path
import sys,tkinter as tk
sys.path.insert(0,str(Path('outputs/OpenSees_NBC105_V144').resolve()))
from OpenSees_Workflow_V144 import launch
r=tk.Tk();r.withdraw();w=launch(r,'D:/Thesis Opensees/Etabs Nodes Export 1');r.update();assert w.winfo_exists();w.destroy();r.destroy();print('Workflow GUI construction PASS')
