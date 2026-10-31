import ast,sys,json,tempfile
from pathlib import Path
p=Path('outputs/OpenSees_NBC105_V151').resolve();sys.path.insert(0,str(p))
for f in (p/'components').rglob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'))
from components.shared.case_status import CaseLedger
with tempfile.TemporaryDirectory(dir=Path('work/tmp151').resolve()) as d:
 l=CaseLedger(Path(d)/'status.json',['ULS','SLS']);assert l.rows['SLS']['status']=='QUEUED';l.set('ULS','RUNNING','eigen');assert l.snapshot()[0]['elapsed_s']>=0;l.set('ULS','COMPLETED','done');l.finish_pending('interrupted');assert l.rows['ULS']['status']=='COMPLETED' and l.rows['SLS']['status']=='NOT COMPLETED'
from components.validation.grade_cards import card,simulate
assert card('Concrete01','M45')['parameters']['fpc_MPa'] is None
with tempfile.TemporaryDirectory(dir=Path('work/tmp151').resolve()) as d:
 c=card('Concrete01','M30');c['parameters']=dict(fpc_MPa=-30,epsc0=-.002,fpcu_MPa=-6,epsU=-.006);assert len(simulate(c,d))>100
import tkinter as tk
root=tk.Tk();root.withdraw()
from components.validation.grade_cards import launch
w=launch(root);root.update();w.destroy()
from components.validation.nonlinear_performance import launch as performance
w=performance(root,p);root.update();w.destroy()
from components.modal.gui_and_reports import ModalAuditGUI
w=tk.Toplevel(root);app=ModalAuditGUI(w);root.update();w.destroy()
root.destroy();print('V151 syntax, ledger transitions, grade card guards/native curve and three GUI construction checks PASS')

