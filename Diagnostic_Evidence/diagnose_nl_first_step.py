"""Isolated research diagnostic: frozen-gravity transient, no motions or damping."""
from pathlib import Path
import sys, time, json
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'outputs'/'OpenSees_NBC105_V163_Research'))
from components.model.assembly import build_complete_model
import openseespy.opensees as ops
model = (root/'work'/'test160_model').resolve()
build_complete_model(model, mode='nonlinear', preload=True, limit_state='ULS', research_profile='LITERATURE_BUILDING_NL_V161')
if '--eigen' in sys.argv:
    from components.shared.eigen_solver import solve_eigen
    print('[DIAGNOSTIC] running eigenanalysis before transient', flush=True)
    solve_eigen(ops, 20)
ops.rayleigh(0., 0., 0., 0.)
if '--motion' in sys.argv:
    from OpenSees_Input_Records_V130 import _read_peer_text_record
    files = [r'D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_RSN1120_KOBE_TAK000.txt', r'D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_RSN1120_KOBE_TAK090.txt']
    for axis,path in enumerate(files, 1):
        values, dt, unit = _read_peer_text_record(path)
        factor = {'g': 9.80665, 'm/s2': 1.0}[unit]
        tag = 900000 + axis
        ops.timeSeries('Path', tag, '-dt', dt, '-values', *values, '-factor', factor)
        ops.pattern('UniformExcitation', tag, axis, '-accel', tag)
        print('[DIAGNOSTIC INPUT]', axis, len(values), dt, unit, factor, flush=True)
ops.wipeAnalysis()
ops.constraints('Transformation'); ops.numberer('RCM'); ops.system('UmfPack')
ops.test('NormDispIncr', 1.e-7, 40, 0); ops.algorithm('Newton')
ops.integrator('Newmark', .5, .25); ops.analysis('Transient')
print('[DIAGNOSTIC] motion=' + str('--motion' in sys.argv) + ', zero damping, eigenanalysis=' + str('--eigen' in sys.argv) + '; attempting one 0.005 s step', flush=True)
start=time.perf_counter(); result=int(ops.analyze(1, .005))
print('[DIAGNOSTIC RESULT]',json.dumps({'return_code':result,'time_s':ops.getTime(),'elapsed_s':time.perf_counter()-start}),flush=True)
