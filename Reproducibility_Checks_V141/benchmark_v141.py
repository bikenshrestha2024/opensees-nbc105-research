import json,math
from pathlib import Path
import openseespy.opensees as ops
results=[]
for n in (1,2,4,8,16):
 ops.wipe();ops.model('basic','-ndm',3,'-ndf',6);tag=lambda i,j:1+i*(n+1)+j
 for i in range(n+1):
  for j in range(n+1):ops.node(tag(i,j),6*i/n,6*j/n,0)
 master=(n+1)**2+1;ops.node(master,3,3,0);ops.fix(master,1,1,1,1,1,1)
 for i,j in [(0,0),(n,0),(n,n),(0,n)]:ops.fix(tag(i,j),0,0,1,1,1,0)
 ops.rigidDiaphragm(3,master,*range(1,master));ops.section('ElasticMembranePlateSection',1,3e7,.2,.15,0);ops.geomTransf('Linear',1,0,0,1);element=0;nodal={}
 for i in range(n):
  for j in range(n):
   ns=[tag(i,j),tag(i+1,j),tag(i+1,j+1),tag(i,j+1)];element+=1;ops.element('ShellMITC4',element,*ns,1)
   for node in ns:nodal[node]=nodal.get(node,0)+4*(6/n)**2/4
 beam_tags=[]
 for a,b in [(tag(i,0),tag(i+1,0)) for i in range(n)]+[(tag(i,n),tag(i+1,n)) for i in range(n)]+[(tag(0,j),tag(0,j+1)) for j in range(n)]+[(tag(n,j),tag(n,j+1)) for j in range(n)]:
  element+=1;beam_tags.append(element);ops.element('elasticBeamColumn',element,a,b,.48,3e7,1.25e7,.04,.0256,.0144,1)
 ops.timeSeries('Linear',1);ops.pattern('Plain',1,1)
 for node,force in nodal.items():ops.load(node,0,0,-force,0,0,0)
 ops.constraints('Transformation');ops.numberer('RCM');ops.system('UmfPack');ops.integrator('LoadControl',1);ops.algorithm('Linear');ops.analysis('Static');assert ops.analyze(1)==0;ops.reactions();reaction=sum(ops.nodeReaction(tag(i,j),3) for i,j in [(0,0),(n,0),(n,n),(0,n)])
 moment=max(abs(ops.eleResponse(t,'localForce')[index]) for t in beam_tags for index in (4,10));uz=min(ops.nodeDisp(i,3) for i in range(1,master))
 assert math.isclose(reaction,144,abs_tol=1e-5)
 results.append(dict(subdivisions=n,total_load_kN=144,support_reaction_kN=reaction,max_beam_end_bending_kNm=moment,max_downward_Uz_m=uz))
assert results[0]['max_beam_end_bending_kNm']==0 and results[1]['max_beam_end_bending_kNm']>0
Path('work/V141_Slab_Benchmark.json').write_text(json.dumps(dict(scope='6m square elastic shell panel on four edge beams; corner supports; rigid in-plane constraint; q=4 kN/m2. Numerical mesh demonstration, not project validation.',results=results),indent=2));print(json.dumps(results,indent=2));ops.wipe()
