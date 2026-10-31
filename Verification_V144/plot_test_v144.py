from pathlib import Path
import sys,csv
p=Path('outputs/OpenSees_NBC105_V144').resolve();sys.path.insert(0,str(p));from OpenSees_Building_Response_V144 import figure
out=Path('work/V144_Plot_Test.csv');rows=[dict(time_s=i*.005,Storey_25_UX_m=i*1e-5,Storey_25_UY_m=-i*1e-5,selected_frame_N_kN=-100-i,selected_frame_Mz_kNm=i*2,section_axial_strain=-i*1e-7,section_kappa_z_1_per_m=i*1e-6) for i in range(3)]
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig=figure(out);assert all(ax.lines for ax in fig.axes);print('All four recorded-channel plot paths PASS (synthetic parser fixture only)')
