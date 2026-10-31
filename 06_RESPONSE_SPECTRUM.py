from pathlib import Path
import sys,tkinter as tk
from tkinter import filedialog
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
root=tk.Tk();root.withdraw()
folder=filedialog.askdirectory(title='Select assembled export folder')
if folder:
 from OpenSees_Model_Response_Spectrum_V132 import launch
 launch(root,folder);root.mainloop()
