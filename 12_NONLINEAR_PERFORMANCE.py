import tkinter as tk
from pathlib import Path
from components.validation.nonlinear_performance import launch
if __name__=='__main__':
 root=tk.Tk();root.withdraw();win=launch(root,Path(__file__).resolve().parent);win.protocol('WM_DELETE_WINDOW',root.destroy);root.mainloop()
