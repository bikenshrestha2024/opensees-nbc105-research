from pathlib import Path
import sys,runpy,os
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import tkinter as tk
from tkinter import filedialog
root=tk.Tk();root.withdraw()
folder=filedialog.askdirectory(title='Select your assembled export folder')
if folder:
 from OpenSees_Building_Exploratory_GUI_V138 import launch
 launch(root,folder);root.mainloop()
