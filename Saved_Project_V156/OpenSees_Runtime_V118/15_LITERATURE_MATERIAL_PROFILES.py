from pathlib import Path
import sys,tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parent))
from components.validation.material_catalog import launch
if __name__=='__main__':
 root=tk.Tk();root.withdraw();window=launch(root);window.protocol('WM_DELETE_WINDOW',root.destroy)
 import os
 if os.environ.get('OPENSEES_GUI_SMOKE')=='1':root.after(1500,root.destroy)
 root.mainloop()
