from pathlib import Path
import sys,ast,tkinter as tk,json
p=Path('outputs/OpenSees_NBC105_V146').resolve();sys.path.insert(0,str(p))
for f in (p/'components').rglob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'))
r=tk.Tk();r.withdraw()
from ETABS_to_OpenSeesPy_Section_Review_V116_NBC105_Area_NLTHA import App
app=App(r);r.update()
def walk(w):
 yield w
 for c in w.winfo_children():yield from walk(c)
views=[w for w in walk(r) if w.winfo_class()=='TButton' and w.cget('text') in ('3D connectivity','3D structural frames / storeys','3D area + frame loads','Floor load / diaphragm plan')];assert len(views)==4
assert all('ETABS IMPORTS' in w.master.cget('text') for w in views)
from OpenSees_Results_UI_V127 import modal_results
w=modal_results(r,Path('D:/Thesis Opensees/Etabs Nodes Export/OpenSees_Analysis_Results'));r.update();tabs=next(c for c in w.winfo_children() if c.winfo_class()=='TNotebook');assert 'ULS / SLS comparison' in [tabs.tab(t,'text') for t in tabs.tabs()];w.destroy()
from OpenSees_Linear_Autofill_V124 import populate_linear
class G:pass
g=G()
for attr in ('t1x','t1y','p1','p2','tnx','tny'):setattr(g,attr,tk.StringVar(r))
g.ls=tk.StringVar(r,value='ULS');g.output=tk.StringVar(r,value='D:/Thesis Opensees/Etabs Nodes Export/OpenSees_Analysis_Results');g.nmodes=tk.StringVar(r,value='20')
audit=populate_linear(g,Path('D:/Thesis Opensees/Etabs Nodes Export'));assert all(float(getattr(g,k).get())>0 for k in ('p1','p2','tnx','tny'));assert 'modal_reference_status' in audit
print('Autofill', {k:getattr(g,k).get() for k in ('p1','p2','tnx','tny')},g.modal_reference_status)
r.destroy();print('Syntax, main views placement, modal comparison tab, reference autofill PASS')
