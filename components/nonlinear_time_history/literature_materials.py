"""Verified literature cards and a separate E-SFI element capability demonstration."""
from pathlib import Path
import json,math,time
PEER='https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf'

def export_cards(out):
    from Define_Section_V109 import WALL_REFERENCE_PROFILE,define_wall_reference_materials
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    profile=dict(WALL_REFERENCE_PROFILE);profile.update(verification='Compared source values against PEER 2015/12 Appendix B.3, printed pp.90-92, PDF pages 102-104 (1-based).',verified_source_pdf=PEER,verified_on='2026-10-24',usage='Benchmark material definitions only. No project configuration, approvals or wall-property maps are edited.')
    k=profile['ksi_to_mpa'];profile['derived_MPa']={name:float(value)*k for name,value in {'unconfined_fc':profile['concrete_unconfined']['fc_ksi'],'confined_fc':profile['concrete_confined']['fc_ksi'],'web_fy':profile['steel']['fy_web_y_ksi'],'boundary_fy':profile['steel']['fy_boundary_y_ksi'],'steel_E':profile['steel']['E0_ksi']}.items()}
    (out/'PEER_Wall_Material_Card.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    (out/'Literature_Wall_Materials.py').write_text('''"""Benchmark specimen materials only; not calibrated to the ETABS building."""
from Define_Section_V109 import define_wall_reference_materials
LITERATURE_ONLY = True
PROJECT_CALIBRATED = False
def define_materials(ops):
    return define_wall_reference_materials(ops, unit_system="kN-m")
''',encoding='utf-8')
    return profile

def probe(out):
    """One four-node planar cell. Numerical capability check, not specimen test."""
    import openseespy.opensees as ops
    from Define_Section_V109 import define_wall_reference_materials
    out=Path(out);export_cards(out);start=time.perf_counter();inch=.0254
    ops.wipe();ops.model('basic','-ndm',3,'-ndf',6)
    for n,xyz in [(1,(0,0,0)),(2,(48*inch,0,0)),(3,(48*inch,0,12*inch)),(4,(0,0,12*inch))]:ops.node(n,*xyz)
    for n in (1,2):ops.fix(n,1,1,1,1,1,1)
    for n in (3,4):ops.fix(n,0,1,0,1,0,1)
    mats=define_wall_reference_materials(ops,'kN-m');tags=mats['tags'];mapping=[tags['fsam_boundary'],tags['fsam_web'],tags['fsam_web'],tags['fsam_web'],tags['fsam_boundary']]
    ops.element('E_SFI_MVLEM_3D',1,1,2,3,4,5,'-thick',*[6*inch]*5,'-width',*[v*inch for v in (9,10,10,10,9)],'-mat',*mapping,'-CoR',.4,'-ThickMod',.63,'-Poisson',.25,'-Density',0.)
    ops.timeSeries('Linear',1);ops.pattern('Plain',1,1)
    for n in (3,4):ops.load(n,.5,0.,0.,0.,0.,0.)
    ops.constraints('Plain');ops.numberer('RCM');ops.system('BandGeneral');ops.test('NormDispIncr',1e-10,50);ops.algorithm('Newton');ops.integrator('LoadControl',.1);ops.analysis('Static');rc=ops.analyze(10)
    d=[ops.nodeDisp(3,i) for i in range(1,7)];response=ops.eleResponse(1,'globalForce')
    result=dict(scope='ELEMENT_COMMAND_AND_SMALL_LOAD_SMOKE_CHECK_ONLY_NOT_EXPERIMENTAL_VALIDATION',element='E_SFI_MVLEM_3D',status='COMPLETED' if rc==0 and all(math.isfinite(x) for x in d+response) else 'FAILED',displacement_node3=d,global_force=response,macro_fiber_FSAM_tags=mapping,material_tags=tags,units='kN-m-s',elapsed_s=time.perf_counter()-start,explanation='One 12-inch-high cell uses the PEER specimen material/width partition. Three-dimensional geometry adapter, out-of-plane defaults and 1-kN horizontal probe are numerical choices; not the complete published specimen, not the project wall.',sources=[PEER,'https://kkolozvari.github.io/E-SFI-MVLEM-3D/'])
    (out/'Wall_Element_Capability.json').write_text(json.dumps(result,indent=2),encoding='utf-8');ops.wipe()
    if result['status']!='COMPLETED':raise RuntimeError('Wall capability probe failed: '+str(result))
    return result
