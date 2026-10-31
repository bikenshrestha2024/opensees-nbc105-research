"""Actual signed elastic stability checks; diagnostic EL profile, kN-m-s.

The reference EL is explicitly not an eligible high-rise ULS ESM design case.
Every sign/direction builds a fresh domain; the caller rebuilds its final state.
"""

__release__ = '134'
from OpenSees_Timing_V130 import timed_outputs
from pathlib import Path
import hashlib
import json
import math


@timed_outputs('Initial signed P-Delta checks','folder')
def ensure_initial_checks(folder):
    folder=Path(folder)
    names=['OpenSees_Complete_Model_Data_V118.json','OpenSees_Complete_Model_Config_V118.json','OpenSees_Initial_PDelta_Input_V124.json']
    import OpenSees_Complete_Export_V118 as assembly
    import OpenSees_Analysis_Stack_V110 as analysis
    digest=hashlib.sha256(b''.join((folder/name).read_bytes() for name in names)+Path(globals().get('_component_source',__file__)).read_bytes()+Path(getattr(assembly,'_component_source',assembly.__file__)).read_bytes()+Path(getattr(analysis,'_component_source',analysis.__file__)).read_bytes()).hexdigest()
    output=folder/'OpenSees_IS16700_Initial_PDelta_Results.json'
    if output.is_file():
        old=json.loads(output.read_text(encoding='utf-8-sig'))
        if all(old.get(f'PD_INIT_EL_{axis}_{sign}',{}).get('input_sha256')==digest and old[f'PD_INIT_EL_{axis}_{sign}'].get('converged') for axis in ('X','Y') for sign in ('PLUS','MINUS')):
            print('IS 16700: reusing four converged cases with matching input fingerprints.',flush=True)
            return old
    data=json.loads((folder/names[0]).read_text(encoding='utf-8-sig'))
    cfg=json.loads((folder/names[1]).read_text(encoding='utf-8-sig'))
    reference=json.loads((folder/names[2]).read_text(encoding='utf-8-sig'))
    raw=data.get('unfactored_patterns')
    if not raw:raise ValueError('Rebuild the assembled export with V124 to retain unfactored D/IL pattern loads.')
    factors={}
    for pattern in raw:
        mass=cfg['mass_factors'].get(pattern)
        if mass==1:factors[pattern]=1.2
        elif mass in (.3,.6) or 'live' in pattern.lower():factors[pattern]=.5
        else:raise ValueError(f'Classify {pattern!r} explicitly as dead or imposed load before initial P-Delta checks.')
    import openseespy.opensees as ops
    from OpenSees_Complete_Export_V118 import build_complete_model
    from OpenSees_Analysis_Stack_V110 import run_gravity_stage
    outcomes={}
    for axis in ('X','Y'):
        profile=reference[axis]
        for label,sign in [('PLUS',1),('MINUS',-1)]:
            name=f'PD_INIT_EL_{axis}_{label}'
            print(name+': building 1.2D + 0.5IL '+('+' if sign>0 else '-')+' 1.5EL reference',flush=True)
            build_complete_model(folder,preload=False)
            for tag in range(700001,700001+len(data['gravity'])):ops.remove('loadPattern',tag)
            ops.timeSeries('Linear',970001);ops.pattern('Plain',970001,970001)
            total=0.
            for pattern,values in raw.items():
                factor=factors[pattern]
                for node,vector in values.items():ops.load(int(node),*[factor*v for v in vector]);total-=factor*vector[2]
            gravity=run_gravity_stage(ops,[int(n) for n,v in data['supports'].items() if v[2]],total,model_nodes=list(map(int,data['nodes'])),nsteps=20,system='UmfPack')
            ops.timeSeries('Linear',970002);ops.pattern('Plain',970002,970002)
            for row in profile['stories']:
                force=sign*1.5*row['lateral_force_kN']
                ops.load(int(row['master_node_tag']),force if axis=='X' else 0.,force if axis=='Y' else 0.,0.,0.,0.,0.)
            ops.wipeAnalysis();ops.constraints('Transformation');ops.numberer('RCM');ops.system('UmfPack')
            ops.test('NormDispIncr',1e-8,40);ops.algorithm('Newton');ops.integrator('LoadControl',.05);ops.analysis('Static')
            steps=0
            for i in range(20):
                code=ops.analyze(1)
                if code!=0:raise RuntimeError(f'{name} failed at lateral increment {i+1}, code {code}')
                steps+=1
            ops.reactions()
            dof=1 if axis=='X' else 2
            reaction=sum(ops.nodeReaction(int(n),dof) for n,flags in data['supports'].items() if flags[dof-1])
            applied=sign*1.5*sum(r['lateral_force_kN'] for r in profile['stories'])
            error=abs(reaction+applied)/abs(applied)*100
            displacements={str(g['master_tag']):ops.nodeDisp(g['master_tag']) for g in data['diaphragms']}
            if not math.isfinite(error) or error>.01:raise RuntimeError(f'{name}: horizontal equilibrium error {error}%')
            outcomes[name]=dict(converged=True,input_sha256=digest,result_file=str(output),combination='1.2D+0.5IL'+('+' if sign>0 else '-')+'1.5EL',
                diagnostic_EL_reference=True,EL_basis=profile['basis'],period_s=profile['period_s'],pattern_factors=factors,
                gravity=gravity,lateral_steps=steps,applied_horizontal_kN=applied,support_horizontal_kN=reaction,equilibrium_error_percent=error,master_displacements_m_rad=displacements,
                result_note='Actual fresh-domain elastic PDelta analysis; high-rise ULS ESM design eligibility is not established. Wind cases require separate project wind loads.')
            print(f'{name}: PASS | V={applied:.6f} kN | equilibrium error={error:.6g}%',flush=True)
    output.write_text(json.dumps(outcomes,indent=2),encoding='utf-8')
    return outcomes
