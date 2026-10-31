"""Search source IDs independently of model assembly success. Units: kN, m, s."""

__release__ = '134'
from pathlib import Path
import json
import html

def export_id_audit(folder, payload=None, report=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    folder=Path(folder)
    read=lambda name: json.loads((folder/name).read_text(encoding="utf-8-sig")) if (folder/name).is_file() else {}
    topology=read("OpenSees_Element_Connectivity.json")
    metadata=read("OpenSees_Source_Model_Metadata_V118.json")
    nodes=topology.get("node_map",[])
    reverse={str(n["opensees_node_tag"]):str(n["etabs_point_name"]) for n in nodes}
    rows=[]
    assembled={}
    for index,element in enumerate((payload or {}).get("frames",[]),100001):
        assembled.setdefault(str(element.get("object")),[]).append(index)
    assembled_area={}
    for index,element in enumerate((payload or {}).get('shells',[]),100001+len((payload or {}).get('frames',[]))):
        assembled_area.setdefault(str(element.get('object')),[]).append(index)
    for e in topology.get("elements",[]):
        rows.append([str(e.get("etabs_object","")),e.get("dimension"),e.get("category"),e.get("storey_number"),e.get("assigned_section",e.get("assigned_property","")),e.get("element_tag"),json.dumps(e.get("node_names",[])),json.dumps(e.get("node_tags",[])),json.dumps(assembled.get(str(e.get("etabs_object")),[])) if payload else "NOT ASSEMBLED"])
    wb=Workbook();ws=wb.active;ws.title="Read me"
    for row in [["ETABS / OpenSees identifier audit"],["ETABS unique object name is not an OpenSees element tag."],["Preview tags describe exported topology; assembled tags describe solver elements."],["Gravity support input uses OpenSees node tags, never ETABS point names."],["Support rows are source restraints even if assembly fails; they do not prove a runnable model."],["Assembly errors",json.dumps((report or {}).get("assembly_errors",[]))]]:ws.append(row)
    def sheet(name,headers,data):
        s=wb.create_sheet(name);s.append(headers)
        for row in data:s.append(row)
        s.freeze_panes="A2";s.auto_filter.ref=s.dimensions
        for c in s[1]:c.font=Font(bold=True,color="FFFFFF");c.fill=PatternFill("solid",fgColor="17365D")
        for column in s.columns:s.column_dimensions[column[0].column_letter].width=min(65,max(18,max(len(str(c.value or "")) for c in column)+2))
    headers=["ETABS unique object name","Dimension","Category","Storey number","ETABS section","OpenSees topology preview tag","ETABS end point names","OpenSees end node tags","Assembled frame element tags"]
    sheet("Elements",headers,rows)
    sheet("Nodes",["ETABS point name","OpenSees node tag","Storey","X m","Y m","Z m"],[[n["etabs_point_name"],n["opensees_node_tag"],n.get("etabs_storey_number"),*n["coordinates_m"]] for n in nodes])
    sheet("Supports",["OpenSees node tag","ETABS point name","UX fixed","UY fixed","UZ fixed","RX fixed","RY fixed","RZ fixed"],[[int(tag),reverse.get(str(tag),"generated mesh node"),*flags] for tag,flags in metadata.get("supports",{}).items() if any(flags)])
    wb.save(folder/"OpenSees_ID_and_Support_Audit.xlsx")
    body="""<!doctype html><meta charset=utf-8><title>ETABS / OpenSees ID lookup</title><style>body{font:15px Arial;margin:24px}input{padding:10px;width:280px}td,th{padding:8px;border:1px solid #ddd}table{border-collapse:collapse}th{background:#eef}tr.hide{display:none}</style><h2>ETABS / OpenSees exact ID lookup</h2><p>ETABS object unique names and OpenSees tags are independent. Preview tags are not assembled solver tags.</p><label>ETABS unique object name <input id=e placeholder='e.g. 251'></label> <label>OpenSees preview element tag <input id=o></label><button onclick="e.value='';o.value='';filter()">Clear</button><p id=count></p><table><thead><tr>"""+"".join("<th>"+html.escape(h)+"</th>" for h in headers)+"</tr></thead><tbody>"+"".join("<tr>"+"".join("<td>"+html.escape(str(v or ""))+"</td>" for v in r)+"</tr>" for r in rows)+"""</tbody></table><script>const e=document.getElementById('e'),o=document.getElementById('o');function filter(){let n=0;document.querySelectorAll('tbody tr').forEach(r=>{let ok=(!e.value.trim()||r.cells[0].textContent===e.value.trim())&&(!o.value.trim()||r.cells[5].textContent===o.value.trim());r.classList.toggle('hide',!ok);if(ok)n++});document.getElementById('count').textContent=n+' matching objects'}e.oninput=o.oninput=filter;filter()</script>"""
    (folder/"OpenSees_ID_Lookup.html").write_text(body,encoding="utf-8")

    # Same ID selection overlay in every Plotly export, independent of each
    # view's trace grouping (loads, connectivity, floor plans or structure).
    nodes=list(nodes)
    known={str(n['opensees_node_tag']) for n in nodes}
    for tag,point in (payload or {}).get('nodes',{}).items():
        if str(tag) not in known:nodes.append(dict(opensees_node_tag=int(tag),etabs_point_name='generated mesh',coordinates_m=point))
    xyz={str(n["opensees_node_tag"]):n["coordinates_m"] for n in nodes}
    selector_data=dict(nodes=nodes,elements=topology.get("elements",[]),xyz=xyz,assembled=assembled,assembled_area=assembled_area)
    script="""<script id="shared-id-selector-v121">window.addEventListener('load',()=>{const D=__DATA__;const bar=document.getElementById('shared-id-controls-v122');const gd=document.querySelector('.plotly-graph-div');if(!gd){bar.textContent='ID controls: plot container not found. Regenerate this view.';return;}bar.innerHTML='<b>V160 | Highlight IDs in this view</b> <select id="idKind"><option value="object">ETABS element unique ID</option><option value="preview">OpenSees topology element tag</option><option value="solver">OpenSees assembled element tag</option><option value="point">ETABS point name</option><option value="node" selected>OpenSees node tag</option></select> <input id="idValue" placeholder="Exact ID"> <button id="idFind">Select</button> <button id="idClear">Clear highlight</button><a href="OpenSees_Property_Element_Load_Audit_V125.xlsx">Excel audit</a> <button id="viewZoomIn">Zoom +</button> <button id="viewZoomOut">Zoom -</button> <button id="viewFit">Reset view</button> <select id="viewPreset"><option>Isometric</option><option>Top (+Z)</option><option>Bottom (-Z)</option><option>Front (-Y)</option><option>Back (+Y)</option><option>Right (+X)</option><option>Left (-X)</option></select> <span id="idResult"></span>';const is3d=gd.data.some(t=>t.type==='scatter3d'||t.type==='mesh3d');const floorEdges=gd.data.map((t,i)=>({t,i})).filter(o=>String(o.t.name||'').startsWith('FLOOR |')).map(o=>o.i);if(is3d&&floorEdges.length){const label=document.createElement('label');label.innerHTML='<input type="checkbox"> Slab outline overlay (display only)';bar.appendChild(label);const check=label.querySelector('input');check.onchange=()=>Plotly.restyle(gd,{opacity:check.checked?.35:0},floorEdges);check.onchange();}let zoom=1;function cameraZoom(factor){if(!is3d){const update={};['xaxis','yaxis'].forEach(k=>{const r=gd._fullLayout[k].range,c=(r[0]+r[1])/2,h=(r[1]-r[0])*factor/2;update[k+'.range']=[c-h,c+h]});Plotly.relayout(gd,update);return;}const eye=(gd.layout&&gd.layout.scene&&gd.layout.scene.camera&&gd.layout.scene.camera.eye)||{x:1.7,y:1.7,z:1.25};Plotly.relayout(gd,{'scene.camera.eye':{x:eye.x*factor,y:eye.y*factor,z:eye.z*factor}})}bar.querySelector('#viewZoomIn').onclick=()=>cameraZoom(.8);bar.querySelector('#viewZoomOut').onclick=()=>cameraZoom(1.25);bar.querySelector('#viewFit').onclick=()=>Plotly.relayout(gd,{'scene.camera.eye':{x:1.7,y:1.7,z:1.25},'scene.camera.center':{x:0,y:0,z:0}});const preset=bar.querySelector('#viewPreset');preset.onchange=()=>{const views={'Isometric':[1.7,1.7,1.25],'Top (+Z)':[0,0,2.7],'Bottom (-Z)':[0,0,-2.7],'Front (-Y)':[0,-2.7,0],'Back (+Y)':[0,2.7,0],'Right (+X)':[2.7,0,0],'Left (-X)':[-2.7,0,0]};const p=views[preset.value],up=p[0]===0&&p[1]===0?{x:0,y:1,z:0}:{x:0,y:0,z:1};Plotly.relayout(gd,{'scene.aspectmode':'data','scene.camera':{eye:{x:p[0],y:p[1],z:p[2]},up:up,center:{x:0,y:0,z:0},projection:{type:'orthographic'}}})};bar.querySelector('#viewFit').onclick=()=>{preset.value='Isometric';preset.onchange()};if(is3d){preset.onchange()}else{preset.disabled=true;bar.querySelector('#viewFit').onclick=()=>Plotly.relayout(gd,{'xaxis.autorange':true,'yaxis.autorange':true});}const category=document.createElement('select');category.id='selectionCategory';category.innerHTML='<option value="node">Node selection</option><option value="frame">Frame element selection</option><option value="area">Area selection</option>';bar.insertBefore(category,bar.querySelector('#idKind'));const originalOptions=[...bar.querySelector('#idKind').options].map(o=>({value:o.value,text:o.text}));function setCategory(){const k=bar.querySelector('#idKind');k.innerHTML='';originalOptions.filter(o=>category.value==='node'?['node','point'].includes(o.value):['object','preview','solver'].includes(o.value)).forEach(o=>k.add(new Option(o.text,o.value)));bar.querySelector('#idValue').value='';bar.querySelector('#idResult').textContent='Choose '+category.value+' ID namespace and enter exact ID';}category.onchange=setCategory;setCategory();let overlay=null;function clear(){if(overlay!==null){Plotly.deleteTraces(gd,overlay);overlay=null}}bar.querySelector('#idClear').onclick=clear;bar.querySelector('#idFind').onclick=()=>{clear();let kind=bar.querySelector('#idKind').value,id=bar.querySelector('#idValue').value.trim(),coords=[],labels=[];if(kind==='node'||kind==='point'){D.nodes.filter(n=>String(kind==='node'?n.opensees_node_tag:n.etabs_point_name)===id).forEach(n=>{coords.push(n.coordinates_m);labels.push('ETABS point '+n.etabs_point_name+' / OpenSees node '+n.opensees_node_tag)})}else{D.elements.filter(e=>(category.value==='frame'?e.dimension==='line_2_node':e.dimension!=='line_2_node')).filter(e=>kind==='object'?String(e.etabs_object)===id:kind==='preview'?String(e.element_tag)===id:((e.dimension==='line_2_node'?D.assembled:D.assembled_area)[String(e.etabs_object)]||[]).map(String).includes(id)).forEach(e=>{let ns=e.node_tags||[];ns.forEach(n=>{coords.push(D.xyz[String(n)]);labels.push('ETABS '+e.etabs_object+' / topology '+e.element_tag)});if(ns.length>2){coords.push(D.xyz[String(ns[0])]);labels.push('ETABS '+e.etabs_object)}coords.push(null);labels.push('')})}bar.querySelector('#idResult').textContent=coords.filter(Boolean).length?' Highlighted matching source geometry':' No matching ID (solver tags require successful assembly)';if(!coords.filter(Boolean).length)return;overlay=gd.data.length;Plotly.addTraces(gd,{type:gd.data.some(t=>t.type==='scatter3d')?'scatter3d':'scatter',mode:'lines+markers',x:coords.map(p=>p?p[0]:null),y:coords.map(p=>p?p[1]:null),z:coords.map(p=>p?p[2]:null),text:labels,hovertemplate:'%{text}<extra></extra>',line:{color:'#ec008c',width:10},marker:{size:7,color:'#ec008c'},name:'ID selection',showlegend:false})};const query=new URLSearchParams(window.location.search);if(query.has('idValue')){category.value=['point','node'].includes(query.get('idKind')||'node')?'node':(query.get('category')||'frame');setCategory();bar.querySelector('#idKind').value=query.get('idKind')||'node';bar.querySelector('#idValue').value=query.get('idValue');bar.querySelector('#idFind').onclick();}});</script>""".replace('__DATA__',json.dumps(selector_data))
    import re
    for path in folder.glob('*.html'):
        content=path.read_text(encoding='utf-8-sig')
        if 'plotly-graph-div' not in content: continue
        content=re.sub(r'<script id="shared-id-selector-v121">.*?</script>','',content,flags=re.S)
        # Render the controls container in HTML before the plot. It remains
        # visible while Plotly initializes, and startup failures are explicit.
        content=re.sub(r'<div id="shared-id-controls-v122"[^>]*>.*?</div>','',content,flags=re.S)
        container='<div id="shared-id-controls-v122" style="padding:12px;background:#edf5ff;position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;gap:6px;align-items:center;font:14px Arial;border-bottom:1px solid #cbd5e1">ETABS / OpenSees exact node and element ID controls — initializing...</div>'
        content=re.sub(r'(<body[^>]*>)',lambda m:m.group(1)+container,content,count=1,flags=re.I)
        safe_script=script
        path.write_text(content.replace('</body>',safe_script+'</body>'),encoding='utf-8')
