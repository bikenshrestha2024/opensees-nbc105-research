"""Prepare an isolated, unapproved wall-material draft from an assembled export."""
from pathlib import Path
import json, math, hashlib, shutil

ROOT = Path(__file__).resolve().parents[2]

def prepare(source, destination, basis='PUBLISHED_REFERENCE'):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination == source:
        raise ValueError('Choose a separate destination for the draft.')
    if destination.exists():
        raise FileExistsError('Destination already exists: ' + str(destination))
    names = ['OpenSees_Complete_Model_Data_V118.json', 'OpenSees_Complete_Model_Config_V118.json',
             'OpenSees_Load_Conversion_Audit.json', 'OpenSees_Source_Model_Metadata_V118.json']
    for name in names:
        if not (source / name).is_file(): raise FileNotFoundError(source / name)
    if basis not in ('PUBLISHED_REFERENCE', 'M30_FE500_SENSITIVITY'): raise ValueError('Unknown material basis')
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    data, cfg = read(source / names[0]), read(source / names[1])
    properties = {}
    for e in data['shells']:
        if e['category'] != 'SHEAR WALL': continue
        p = e['properties']; key = p['property']; thickness = float(p['thickness'])
        if thickness <= 0 or (key in properties and properties[key] != thickness):
            raise ValueError('Invalid or inconsistent wall thickness for ' + key)
        properties[key] = thickness
    if not properties: raise ValueError('No shear-wall properties found in this export')
    catalog = 'PEER_Web_ESFI_Patch.json' if basis == 'PUBLISHED_REFERENCE' else 'M30_Fe500_SFI_MVLEM_3D.json'
    reference = read(ROOT / 'Material_Catalog' / catalog)
    tags = {name: 962000+i for i,name in enumerate(sorted(properties))}
    # Historical layout only: two curtains of 20 mm bars at 200 mm spacing.
    # This is not extracted reinforcement and is never represented as verified.
    ratios = {name: 2*math.pi*20**2/4/(200*thickness*1000) for name,thickness in properties.items()}
    s = dict(reference['wall_steel']); s.update(R0=20., cR1=18.5, cR2=.0015)
    card = dict(basis=basis, source=reference['source'], citation=reference['citation'],
                element_source='https://doi.org/10.1016/j.engstruct.2023.116700',
                concrete=reference['wall_concrete'], steel=s, fsam=reference['fsam'],
                thickness_m=properties, fsam_tags=tags, assumed_rho=ratios,
                reinforcement_assumption='Two curtains, 20 mm bars at 200 mm each way; confirm from project drawings.',
                status='RESEARCH DRAFT; NOT PROJECT CALIBRATED OR APPROVED', units='MPa converted to kN/m2 by 1000')
    destination.mkdir(parents=True)
    for name in names: shutil.copy2(source/name, destination/name)
    for name in ('OpenSees_Element_Overrides_V125.json','OpenSees_Complete_Story_Masters_V118.csv'):
        if (source/name).is_file(): shutil.copy2(source/name,destination/name)
    (destination/'Research_Wall_Parameters.json').write_text(json.dumps(card,indent=2),encoding='utf-8')
    material_source = '''"""Unapproved research wall material; see Research_Wall_Parameters.json for sources."""\nfrom pathlib import Path\nimport json\ndef define_materials(ops):\n    d=json.loads((Path(__file__).parent/'Research_Wall_Parameters.json').read_text(encoding='utf-8'))\n    s=d['steel']; c=d['concrete']; f=d['fsam']\n    sk=('fyp','fyn','E0','bp','bn','R0','cR1','cR2','a1','a2','a3','a4')\n    ck=('fpcc','epcc','Ec','rc','xcrn','ft','et','rt','xcrp')\n    ops.uniaxialMaterial('SteelMPF',961001,*[s[k]*(1000 if k in ('fyp','fyn','E0') else 1) for k in sk])\n    ops.uniaxialMaterial('ConcreteCM',961002,*[c[k]*(1000 if k in ('fpcc','Ec','ft') else 1) for k in ck])\n    for name,tag in d['fsam_tags'].items():\n        rho=d['assumed_rho'][name]\n        ops.nDMaterial('FSAM',tag,0.,961001,961001,961002,rho,rho,f['nu'],f['alpha'])\n'''
    (destination/'Research_Wall_Materials.py').write_text(material_source,encoding='utf-8')
    cfg['nonlinear_materials_file']='Research_Wall_Materials.py'; cfg['nonlinear_wall_fsam_tags']=tags
    cfg['nonlinear_parameters_reviewed']=False
    cfgfile=destination/names[1]; cfgfile.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    # The data copy is unchanged other than its config fingerprint; the source is untouched.
    data['config_sha256']=hashlib.sha256(cfgfile.read_bytes()).hexdigest()
    (destination/names[0]).write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    return card
