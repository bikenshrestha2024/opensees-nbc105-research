from pathlib import Path
import sys
import tkinter as tk
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'OpenSees_Runtime_V118'))
from ETABS_to_OpenSeesPy_Section_Review_V116_NBC105_Area_NLTHA import App
if __name__=='__main__':
    root=tk.Tk()
    from OpenSees_Window_Manager_V129 import install_windows_menu
    install_windows_menu(root)
    app=App(root)
    app.out.set(str(HERE))
    root.mainloop()
