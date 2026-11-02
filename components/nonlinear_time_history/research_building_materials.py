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

MATERIAL_OVERRIDE_BOUNDS = {
    'brace.fy_mpa': (1., 1000.),
    'brace.E_mpa': (1000., 1000000.),
    'brace.b': (0., .5),
    'frame.cover_fc_mpa': (1., 150.),
    'frame.cover_epsc0': (-.1, -1e-8),
    'frame.cover_fcu_mpa': (0., 150.),
    'frame.cover_epsU': (-.1, -1e-8),
    'frame.core_fcc_mpa': (1., 150.),
    'frame.core_epsc0': (-.1, -1e-8),
    'frame.core_fpcu_mpa': (0., 150.),
    'frame.core_epsU': (-.1, -1e-8),
    'frame.rebar_fy_mpa': (1., 1500.),
    'frame.E0_mpa': (10000., 300000.),
    'frame.steel_b': (0., .5),
    'frame.steel_R0': (1., 50.),
    'frame.steel_cR1': (.001, 50.),
    'frame.steel_cR2': (.001, 1.),
    'wall.fpcc_mpa': (-300., -1.),
    'wall.epcc': (-.1, -1e-8),
    'wall.Ec_mpa': (1000., 100000.),
    'wall.rc': (.01, 100.),
    'wall.xcrn': (.01, 100.),
    'wall.ft_mpa': (0., 100.),
    'wall.et': (1e-8, .1),
    'wall.rt': (.01, 100.),
    'wall.xcrp': (.01, 100000.),
    'wall.fyp_mpa': (1., 1500.),
    'wall.fyn_mpa': (1., 1500.),
    'wall.E0_mpa': (10000., 300000.),
    'wall.bp': (0., .5),
    'wall.bn': (0., .5),
    'wall.R0': (1., 50.),
    'wall.cR1': (.001, 50.),
    'wall.cR2': (.001, 1.),
    'wall.a1': (0., 10.),
    'wall.a2': (0., 10.),
    'wall.a3': (0., 10.),
    'wall.a4': (0., 10.),
    'wall.rho_x': (.0001, .1),
    'wall.rho_y': (.0001, .1),
    'wall.fsam_nu': (0., 1.),
    'wall.fsam_alpha': (0., 1.),
}

FRAME_OVERRIDE_TARGETS = {
    'frame.cover_fc_mpa': 'cover_fc_mpa',
    'frame.cover_epsc0': 'cover_epsc0',
    'frame.cover_fcu_mpa': 'cover_fcu_mpa',
    'frame.cover_epsU': 'cover_epsU',
    'frame.core_fcc_mpa': 'core_fcc_mpa',
    'frame.core_epsc0': 'core_epsc0',
    'frame.core_fpcu_mpa': 'core_fpcu_mpa',
    'frame.core_epsU': 'core_epsU',
    'frame.rebar_fy_mpa': 'fy_rebar_mpa',
    'frame.E0_mpa': 'E0_mpa',
    'frame.steel_b': 'steel_b',
    'frame.steel_R0': 'steel_R0',
    'frame.steel_cR1': 'steel_cR1',
    'frame.steel_cR2': 'steel_cR2',
}


def validate_frame_section_parameters(section):
    """Reject Concrete01 cover/core curves with incompatible peak/residual points."""
    for label, peak_key, residual_key, peak_strain_key, ultimate_key in (
        ('cover', 'cover_fc_mpa', 'cover_fcu_mpa', 'cover_epsc0', 'cover_epsU'),
        ('core', 'core_fcc_mpa', 'core_fpcu_mpa', 'core_epsc0', 'core_epsU'),
    ):
        if section[residual_key] > section[peak_key]:
            raise ValueError(f'Frame {label} residual strength must not exceed its peak strength.')
        if section[ultimate_key] >= section[peak_strain_key]:
            raise ValueError(f'Frame {label} ultimate strain must be more negative than its peak strain.')


def validate_material_overrides(values):
    """Validate explicit exploratory inputs; values use the units in their names."""
    if not isinstance(values, dict):
        raise ValueError('material_overrides must be an object keyed by supported parameter names')
    result = {}
    for key, raw in values.items():
        if key not in MATERIAL_OVERRIDE_BOUNDS:
            raise ValueError('Unsupported material override: ' + str(key))
        if isinstance(raw, bool):
            raise ValueError('Material override must be numeric: ' + key)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('Material override must be numeric: ' + key) from exc
        low, high = MATERIAL_OVERRIDE_BOUNDS[key]
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} must be finite and between {low:g} and {high:g}')
        result[key] = value
    return result


def brace_steel_parameters(material_overrides=None):
    """Return the user-specified 345 MPa research baseline in model units."""
    overrides = validate_material_overrides(material_overrides or {})
    fy_mpa = overrides.get('brace.fy_mpa', 345.)
    return {
        'fy_mpa': fy_mpa,
        'fy_kN_m2': fy_mpa * 1000.,
        'E_mpa': overrides.get('brace.E_mpa'),
        'hardening_ratio': overrides.get('brace.b', .01),
    }


def _steelmpf_transition(profile):
    if profile=='OPENSEES_DOCUMENTED':
        return dict(R0=20.,cR1=.925,cR2=.0015,
                    basis='OpenSees SteelMPF author-documented transition default; PEER appendix cR1 entry retained as an explicit alternate')
    if profile=='PEER_APPENDIX_EXACT':
        return dict(R0=20.,cR1=18.5,cR2=.0015,
                    basis='PEER 2015/12 Appendix B.3 web card, exact printed transition values')
    raise ValueError('Unknown SteelMPF transition profile')

def define_building_materials(ops,data,folder,material_overrides=None):
    import Define_Section_V109 as sections
    material_overrides=validate_material_overrides(material_overrides or {})
    basis=os.environ.get('OPENSEES_RESEARCH_MATERIAL_BASIS','PUBLISHED_REFERENCE')
    if basis not in ('PUBLISHED_REFERENCE','M30_FE500_SENSITIVITY'):
        raise ValueError('Unknown research material basis')
    transition_profile=os.environ.get('OPENSEES_STEELMPF_TRANSITION','OPENSEES_DOCUMENTED')
    transition=_steelmpf_transition(transition_profile)
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
            for key, value in material_overrides.items():
                if key in FRAME_OVERRIDE_TARGETS:
                    q[FRAME_OVERRIDE_TARGETS[key]] = value
            validate_frame_section_parameters(q)
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
    for key, value in material_overrides.items():
        if key.startswith('wall.'):
            ckey=key.split('.',1)[1]
            if ckey in ('fpcc_mpa','Ec_mpa','epcc'):
                target={'fpcc_mpa':'fpcc','Ec_mpa':'Ec','epcc':'epcc'}[ckey]
                c[target]=value
            elif ckey in ('rc','xcrn','ft_mpa','et','rt','xcrp'):
                target={'rc':'rc','xcrn':'xcrn','ft_mpa':'ft','et':'et','rt':'rt','xcrp':'xcrp'}[ckey]
                c[target]=value
    # Keep the PEER appendix value selectable because its cR1 differs from
    # the SteelMPF author-documented transition default.
    s.update(R0=transition['R0'],cR1=transition['cR1'],cR2=transition['cR2'])
    steel_targets={
        'fyp_mpa':'fyp','fyn_mpa':'fyn','E0_mpa':'E0','bp':'bp','bn':'bn',
        'R0':'R0','cR1':'cR1','cR2':'cR2','a1':'a1','a2':'a2','a3':'a3','a4':'a4',
    }
    for key, value in material_overrides.items():
        if key.startswith('wall.') and key.split('.',1)[1] in steel_targets:
            s[steel_targets[key.split('.',1)[1]]]=value
    for key, value in material_overrides.items():
        if key=='wall.fsam_nu':
            wall['fsam']['nu']=value
        elif key=='wall.fsam_alpha':
            wall['fsam']['alpha']=value
    steel_tag=961001;concrete_tag=961002
    ops.uniaxialMaterial('SteelMPF',steel_tag,*[s[k]*(1000. if k in ('fyp','fyn','E0') else 1.) for k in MPF])
    ops.uniaxialMaterial('ConcreteCM',concrete_tag,*[c[k]*(1000. if k in ('fpcc','Ec','ft') else 1.) for k in CM])
    tags={};rows=[]
    walls={e['properties']['property']:e['properties'] for e in data['shells'] if e['category']=='SHEAR WALL'}
    for i,(key,p) in enumerate(sorted(walls.items())):
        # Available layout in the historical project library: two curtains,
        # 20-mm bars at 200-mm spacing. It remains confirmation-pending.
        ratios=sections.wall_reinforcement_ratios(p['thickness']*1000.)
        if 'wall.rho_x' in material_overrides:
            ratios['fsam_rouX_horizontal']=material_overrides['wall.rho_x']
        if 'wall.rho_y' in material_overrides:
            ratios['fsam_rouY_vertical']=material_overrides['wall.rho_y']
        tag=962000+i;tags[key]=tag
        ops.nDMaterial('FSAM',tag,0.,steel_tag,steel_tag,concrete_tag,
                       ratios['fsam_rouX_horizontal'],ratios['fsam_rouY_vertical'],
                       wall['fsam']['nu'],wall['fsam']['alpha'])
        rows.append(dict(property=key,fsam_tag=tag,thickness_m=p['thickness'],
                         reinforcement=ratios,confinement='UNCONFINED WEB THROUGHOUT'))
    brace=brace_steel_parameters(material_overrides)
    report=dict(basis=basis,scope='LITERATURE_INFORMED_RESEARCH_NOT_PROJECT_CALIBRATION',
        wall_constitutive_source=wall['source'],wall_source_locator=wall['citation'],
        wall_concrete=c,wall_steel=s,fsam=wall['fsam'],wall_regions=rows,
        material_overrides=material_overrides,
        brace_steel=dict(model='Steel01 corotTruss axial idealization',
                         fy_mpa=brace['fy_mpa'],
                         fy_kN_m2=brace['fy_kN_m2'],
                         E_mpa_override=brace['E_mpa'],
                         hardening_ratio=brace['hardening_ratio'],
                         basis='User-specified 345 MPa structural-steel baseline; confirm grade certificate. Does not represent BRB core qualification.'),
        steelmpf_transition_profile=transition_profile,
        steelmpf_transition_basis=transition['basis'],
        frame_sections=frame,frame_concrete_source='https://opensees.berkeley.edu/OpenSees/OpenSeesExamples1.1.pdf',
        frame_steel_basis='Nominal Fe500 plus documented Steel02 defaults; b=0.01 assumed, not an experimental Fe500 fit',
        frame_reinforcement_basis='Existing section-layout templates; not verified project bar schedules',
        element_source='https://doi.org/10.1016/j.engstruct.2023.116700',
        stress_units='kN/m2 = MPa*1000 exactly once',approval=False)
    Path(folder,'Research_Material_Assignment_V161.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('[RESEARCH MATERIALS]',basis,'| nonlinear frames AND E_SFI_MVLEM_3D walls | material assignment exported',flush=True)
    return dict(property_tags=tags,report=report,
                brace_fy_mpa=brace['fy_mpa'],
                brace_b=brace['hardening_ratio'],
                material_overrides=material_overrides)
