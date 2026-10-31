from pathlib import Path
import shutil,json,hashlib,datetime
RELEASE='V142'
def regenerate_floor_view(folder):
    import plotly.graph_objects as go
    folder=Path(folder);audit=json.loads((folder/'OpenSees_Load_Conversion_Audit.json').read_text(encoding='utf-8-sig'))
    figure=go.Figure();coords=audit['coordinates'];connections=audit['area_connectivity'];meta=[]
    for item in audit.get('applied_area_loads',[]):
        points=[coords[str(n)] for n in connections.get(str(item['object']),[])]
        if len(points)<3:continue
        points.append(points[0]);index=len(figure.data);z=sum(p[2] for p in points[:-1])/(len(points)-1)
        figure.add_trace(go.Scatter(x=[p[0] for p in points],y=[p[1] for p in points],mode='lines',fill='toself',name=item['pattern'],showlegend=False,opacity=.45,hovertext='Area '+str(item['object'])+' | '+item['pattern']+' | '+str(item['value'])+' kN/m2',hoverinfo='text'))
        meta.append(dict(index=index,pattern=item['pattern'],z=round(z,5)))
    figure.update_layout(title='V142 saved area assignments | '+str(len(meta))+' load components',yaxis=dict(scaleanchor='x'),height=850)
    js="""(()=>{const gd=document.getElementById('{plot_id}'),meta=__META__;const bar=document.createElement('div');bar.style='padding:14px;background:#eef5ff;font:16px Arial';bar.innerHTML='V142 | Pattern <select><option value="all">All patterns</option></select> Elevation (m) <select><option value="all">All floors</option></select> <b></b>';gd.before(bar);const [p,z]=bar.querySelectorAll('select');[...new Set(meta.map(r=>r.pattern))].forEach(v=>p.add(new Option(v,v)));[...new Set(meta.map(r=>r.z))].sort((a,b)=>a-b).forEach(v=>z.add(new Option(v,v)));function update(){const keep=meta.map(r=>(p.value==='all'||p.value===r.pattern)&&(z.value==='all'||Number(z.value)===r.z));Plotly.restyle(gd,{visible:keep});bar.querySelector('b').textContent=keep.filter(Boolean).length+' load areas'+(!meta.length?' — no loads in this saved audit: re-export with V142; no prior results are certified':'')}p.onchange=z.onchange=update;update()})();""".replace('__META__',json.dumps(meta))
    path=folder/'OpenSees_Load_Assignment_Floor_Plan.html';figure.write_html(path,include_plotlyjs=True,div_id='floorPlotV142',post_script=js)
    return len(meta)

def repair(release,folder):
    release=Path(release).resolve();folder=Path(folder).resolve()
    if not (folder/'OpenSees_Complete_Model_Data_V118.json').is_file():raise ValueError('Select an existing exported model folder')
    runtime=folder/'OpenSees_Runtime_V118';runtime.mkdir(exist_ok=True)
    if release!=runtime:
        for path in release.glob('*.py'):shutil.copy2(path,runtime/path.name)
        shutil.copytree(release/'components',runtime/'components',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    launcher="from pathlib import Path\nimport runpy,os\nos.environ['OPENSEES_PROJECT_FOLDER']=str(Path(__file__).resolve().parent)\nrunpy.run_path(str(Path(__file__).resolve().parent/'OpenSees_Runtime_V118/RUN_ETABS_TO_OPENSEES.py'),run_name='__main__')\n"
    (folder/'RUN_LATEST_V142.py').write_text(launcher,encoding='utf-8')
    stamp=dict(release=RELEASE,release_path=str(release),runtime_path=str(runtime),updated_at=datetime.datetime.now().astimezone().isoformat(),model_sha256=hashlib.sha256((folder/'OpenSees_Complete_Model_Data_V118.json').read_bytes()).hexdigest())
    stamp['saved_area_components']=regenerate_floor_view(folder)
    from OpenSees_ID_Audit_V120 import export_id_audit
    export_id_audit(folder)
    (folder/'RELEASE_HEALTH_V142.json').write_text(json.dumps(stamp,indent=2),encoding='utf-8');return stamp
