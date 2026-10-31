from pathlib import Path
import ast,sys,tkinter as tk
ROOT=Path(__file__).resolve().parents[1];CODE=ROOT/'outputs/OpenSees_NBC105_V116_Area_NLTHA_Integration';sys.path.insert(0,str(CODE))
for path in CODE.glob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'))
stage=ROOT/'work/V124_Project_Check';sys.argv=[sys.argv[0],str(stage)]
from tkinter import messagebox
messagebox.showerror=lambda *a,**kw:print('GUI error',a)
from OpenSees_Earthquake_Analysis_NBC105_V111 import ESMGui
root=tk.Tk();root.withdraw();gui=ESMGui(root);root.update_idletasks()
assert gui.computed_x.get() and gui.computed_y.get();print('Computed period rows:',gui.computed_x.get(),gui.computed_y.get())
from OpenSees_Linear_Time_History_NBC105_V115 import LinearTimeHistoryGUI
from OpenSees_Complete_Export_V118 import autoselect_inputs
th=LinearTimeHistoryGUI(root);th.win.withdraw();autoselect_inputs(th,stage,'linear_model_script')
assert all(getattr(th,key).get() for key in ('p1','p2','t1x','t1y','tnx','tny'))
print('TH populated:',{key:getattr(th,key).get() for key in ('p1','p2','t1x','t1y','tnx','tny')})
from NBC105_Spectrum_Scaling_V115 import SpectrumScalingGUI
from OpenSees_Linear_Autofill_V124 import populate_spectrum
sp=SpectrumScalingGUI(root);sp.win.withdraw();populate_spectrum(sp,th)
assert sp.z.get()=='0.35' and sp.t1x.get() and sp.tnx.get();print('Spectrum autofill PASS')
root.destroy()
