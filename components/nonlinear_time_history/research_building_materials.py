"""Literature-informed building parameters. Research assignment, not calibration.

PEER 2015/12 Appendix B.3 supplies the ConcreteCM/SteelMPF web card.
https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf
Kolozvari, Lopez & Massone (2023), Engineering Structures 294, 116700:
https://doi.org/10.1016/j.engstruct.2023.116700
https://kkolozvari.github.io/E-SFI-MVLEM-3D/
The latter supplies the ELEMENT formulation; its SD-06 material calibration
is not claimed. No boundary-confinement enhancement is assigned to this core.
"""
from pathlib import Path
import copy, json, os, math

ROOT=Path(__file__).resolve().parents[2]

def define_building_materials(ops,data,folder):
    import Define_Section_V109 as sections
    basis=os.environ.get('OPENSEES_RESEARCH_MATERIAL_BASIS','PUBLISHED_REFERENCE')
    if basis not in ('PUBLISHED_REFERENCE','M30_FE500_SENSITIVITY'):
        raise ValueError('Unknown research material basis')
    wall_file='PEER_Web_ESFI_Patch.json' if basis=='PUBLISHED_REFERENCE' else 'M30_Fe500_SFI_MVLEM_3D.json'
    wall=json.loads((ROOT/'Material_Catalog'/wall_file).read_text(encoding='utf8'))
    cover=json.loads((ROOT/'Material_Catalog'/'Official_Concrete01.json').read_text(encoding='utf8'))['parameters']
    saved=copy.deepcopy(sections.RC_SECTION_CONFIG)
    try:
        for q in sections.RC_SECTION_CONFIG.values():
            # Retain the existing explicit bar-layout TEMPLATE; do not invent
            # measured project reinforcement or infer it from section dimensions.
            fc=abs(cover['fpc_MPa']) if basis=='PUBLISHED_REFERENCE' else 24.0
            # M30 is a cube grade. 0.8*30 cylinder strength is an ASSUMPTION,
            # not a measured conversion or a published M30 calibration.
            q.update(cover_fc_mpa=fc,core_fcc_mpa=fc,cover_epsc0=-.002,
                     core_epsc0=-.002,cover_fcu_mpa=0.,core_fpcu_mpa=0.,
                     cover_epsU=-.006,core_epsU=-.006,fy_rebar_mpa=500.,
                     E0_mpa=200000.,steel_b=.01,steel_R0=20.,
                     steel_cR1=.925,steel_cR2=.15)
            # Steel02 R0/cR1/cR2 follow recommended command defaults:
            # https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel02.html
            # Fy=500 MPa is NOMINAL Fe500; b=.01 is a sensitivity assumption.
            # No confinement gain is introduced without actual tie details.
        sections.define_all_fiber_sections(ops,unit_system='kN-m')
        frame=copy.deepcopy(sections.RC_SECTION_CONFIG)
    finally:
        sections.RC_SECTION_CONFIG.clear();sections.RC_SECTION_CONFIG.update(saved)
    from components.validation.parameter_studies import CM,MPF
    c=wall['wall_concrete'];s=dict(wall['wall_steel'])
    # Do not transfer Steel02 transition constants to SteelMPF. Use the PEER
    # SteelMPF transition shape in BOTH strength-sensitivity cases.
    s.update(R0=20.,cR1=18.5,cR2=.0015)
    steel_tag=961001;concrete_tag=961002
    ops.uniaxialMaterial('SteelMPF',steel_tag,*[s[k]*(1000. if k in ('fyp','fyn','E0') else 1.) for k in MPF])
    ops.uniaxialMaterial('ConcreteCM',concrete_tag,*[c[k]*(1000. if k in ('fpcc','Ec','ft') else 1.) for k in CM])
    tags={};rows=[]
    walls={e['properties']['property']:e['properties'] for e in data['shells'] if e['category']=='SHEAR WALL'}
    for i,(key,p) in enumerate(sorted(walls.items())):
        # Available layout in the historical project library: two curtains,
        # 20-mm bars at 200-mm spacing. It remains confirmation-pending.
        ratios=sections.wall_reinforcement_ratios(p['thickness']*1000.)
        tag=962000+i;tags[key]=tag
        ops.nDMaterial('FSAM',tag,0.,steel_tag,steel_tag,concrete_tag,
                       ratios['fsam_rouX_horizontal'],ratios['fsam_rouY_vertical'],
                       wall['fsam']['nu'],wall['fsam']['alpha'])
        rows.append(dict(property=key,fsam_tag=tag,thickness_m=p['thickness'],
                         reinforcement=ratios,confinement='UNCONFINED WEB THROUGHOUT'))
    report=dict(basis=basis,scope='LITERATURE_INFORMED_RESEARCH_NOT_PROJECT_CALIBRATION',
        wall_constitutive_source=wall['source'],wall_source_locator=wall['citation'],
        wall_concrete=c,wall_steel=s,fsam=wall['fsam'],wall_regions=rows,
        frame_sections=frame,frame_concrete_source='https://opensees.berkeley.edu/OpenSees/OpenSeesExamples1.1.pdf',
        frame_steel_basis='Nominal Fe500 plus documented Steel02 defaults; b=0.01 assumed, not an experimental Fe500 fit',
        frame_reinforcement_basis='Existing section-layout templates; not verified project bar schedules',
        element_source='https://doi.org/10.1016/j.engstruct.2023.116700',
        stress_units='kN/m2 = MPa*1000 exactly once',approval=False)
    Path(folder,'Research_Material_Assignment_V161.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('[RESEARCH MATERIALS]',basis,'| nonlinear frames AND E_SFI_MVLEM_3D walls | material assignment exported',flush=True)
    return dict(property_tags=tags,report=report)
