import tkinter as tk
from components.validation.parameter_gui import launch
if __name__=='__main__':
 root=tk.Tk();root.withdraw();win=launch(root);win.protocol('WM_DELETE_WINDOW',root.destroy);root.mainloop()
