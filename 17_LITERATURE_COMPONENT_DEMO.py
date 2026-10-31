"""Launch the isolated published-parameter nonlinear demonstration."""
import tkinter as tk
from OpenSees_Literature_Demo_GUI_V137 import launch
if __name__ == '__main__':
    root=tk.Tk();root.withdraw();window=launch(root)
    window.protocol('WM_DELETE_WINDOW',root.destroy)
    root.mainloop()
