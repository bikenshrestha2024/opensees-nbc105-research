from pathlib import Path
import ast,sys,shutil,tkinter as tk
p=Path('outputs/OpenSees_NBC105_V147').resolve()
f=p/'components/ui/application.py';f.write_text(f.read_text(encoding='utf-8-sig').replace('V146 running code','V147 running code'),encoding='utf8')
sys.path.insert(0,str(p))
from components.sections.wall_adapters import validate_card,define_lu_layered_section,define_esfi_panel
assert validate_card({'boundary_elements':False,'confined_concrete':False})
class Fake:
 def section(self,*args):self.args=args
 def element(self,*args):self.args=args
fake=Fake()
try:define_lu_layered_section(fake,1,[{'material_tag':1,'thickness_m':.1}]*3,.2)
except ValueError:pass
else:raise AssertionError('Thickness mismatch accepted')
define_lu_layered_section(fake,1,[{'material_tag':1,'thickness_m':.1}]*3,.3);assert fake.args[0]=='LayeredShell'
try:define_esfi_panel(fake,1,[1,2,3,4],[1],[.2],[1])
except ValueError:pass
else:raise AssertionError('One fiber accepted')
from OpenSees_Wall_Validation_V147 import launch
r=tk.Tk();r.withdraw();w=launch(r);r.update();w.destroy();r.destroy()
for f in p.rglob('*.py'):
 if '__pycache__' not in f.parts:ast.parse(f.read_text(encoding='utf-8-sig'))
old=p/'Saved_Project_V146';new=p/'Saved_Project_V147'
if old.exists():old.rename(new)
shutil.copytree(p/'components',new/'OpenSees_Runtime_V118/components',dirs_exist_ok=True)
for f in p.glob('*.py'):shutil.copy2(f,new/'OpenSees_Runtime_V118'/f.name)
shutil.copytree(p/'wall_validation_sources',new/'OpenSees_Runtime_V118/wall_validation_sources',dirs_exist_ok=True)
shutil.copy2(p/'WALL_VALIDATION_V147.md',new/'OpenSees_Runtime_V118/WALL_VALIDATION_V147.md')
print('Input guard checks, layer sums, GUI construction and all Python syntax passed')
