"""Transient workload and measured timings; never change integration bounds to save time."""
from pathlib import Path
import json,math,time
from OpenSees_Timing_V130 import stamp


def workload(motions,config):
    rows=[]
    for m in motions:
        single=m.get('mode')=='X_ONLY'
        digit=m['dt_x'] if single else min(m['dt_x'],m['dt_y'])
        axes=('x',) if single else ('x','y')
        bounds=dict(digitization=digit,T1_over_100=min(float(config['T1_'+a+'_s']) for a in axes)/100,Tn=min(float(config['Tn_'+a+'_s']) for a in axes),absolute_maximum=.01)
        if not all(math.isfinite(v) and v>0 for v in bounds.values()):raise ValueError('Time-step bounds must be positive and finite')
        dt=min(bounds.values());duration=(len(m['x'])-1)*m['dt_x'] if single else max((len(m['x'])-1)*m['dt_x'],(len(m['y'])-1)*m['dt_y'])
        for orient in (('X_ONLY',) if single else ('XY','YX')):
            rows.append(dict(case=m['pair_id']+'_'+orient,dt_s=dt,duration_s=duration,requested_steps=math.ceil(duration/dt),controlling_bounds=[k for k,v in bounds.items() if math.isclose(v,dt)],bounds_s=bounds))
    return dict(cases=rows,total_cases=len(rows),total_requested_steps=sum(r['requested_steps'] for r in rows),note='One selected pair runs both XY and YX. Nonlinear substeps/iterations are additional; elapsed nonlinear time cannot be inferred from linear time alone.')


def save_workload(motions,config):
    report=workload(motions,config);path=Path(config['output_dir'])/'Transient_Workload_V133.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"[WORKLOAD] {report['total_cases']} cases | {report['total_requested_steps']} requested steps | integration bounds retained",flush=True)
    return report


class CaseProfiler:
    def __init__(self,folder,case,kind):
        self.folder=Path(folder);self.case=case;self.kind=kind;self.started=stamp();self.clock=time.perf_counter();self.stages={};self.internal_steps=0;self.sample_seconds=0.;self.solve_clock=None;self.complete=False;self.solver_diagnostics={}
    def add(self,name,started):self.stages[name]=self.stages.get(name,0.)+time.perf_counter()-started
    def progress(self,done,total):
        elapsed=time.perf_counter()-self.solve_clock if self.solve_clock else 0.;rate=done/elapsed if elapsed>0 else 0.;eta=(total-done)/rate if rate else None
        print(f"[PERFORMANCE] {self.case}: {done}/{total} | {rate:.2f} requested steps/s | elapsed={elapsed:.1f}s | case ETA={eta:.1f}s" if eta is not None else f'[PERFORMANCE] {self.case}: preparing',flush=True)
    def finish(self,status='completed',error=None):
        if self.complete:return
        self.complete=True;elapsed=time.perf_counter()-self.clock
        result=dict(case=self.case,analysis=self.kind,status=status,error=error,started_at=self.started,finished_at=stamp(),elapsed_seconds=elapsed,stages_seconds=self.stages,accepted_internal_steps=self.internal_steps,recording_seconds=self.sample_seconds,solver_diagnostics=self.solver_diagnostics,scope='Measured wall time on this machine; solve stages include native solver and Python call overhead. ETA is current-case extrapolation, not a nonlinear suite guarantee.')
        path=self.folder/(self.case+'_Performance_V133.json');path.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(f'[CASE TIMING] {self.case} | {status} | elapsed={elapsed:.3f}s | stages='+json.dumps(self.stages),flush=True)
        return result


def history_metadata(path,model,stories,limit_state,status="completed"):
    import hashlib
    payload=Path(model).parent/'OpenSees_Complete_Model_Data_V118.json'
    report=dict(status=status,model_script=str(Path(model).resolve()),limit_state=limit_state,stories=stories,model_data_sha256=hashlib.sha256(payload.read_bytes()).hexdigest() if payload.is_file() else None,displacement_reference='Gravity-preloaded baseline subtracted',sample_scope='All accepted adaptive substeps for nonlinear; every accepted step for linear',units=dict(translation='m',rotation='rad',time='s'))
    Path(str(path)+'.metadata.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


class HistoryStream:
    """Keep accepted samples on disk even when a later interval fails."""
    def __init__(self,path):
        import csv
        self.path=Path(path);self.file=self.path.open('w',newline='',encoding='utf-8-sig');self.writer=None;self.csv=csv
    def append(self,row):
        if self.writer is None:
            self.writer=self.csv.DictWriter(self.file,fieldnames=list(row));self.writer.writeheader()
        self.writer.writerow(row)
    def flush(self):
        if not self.file.closed:self.file.flush()
    def close(self):
        if not self.file.closed:self.file.close()


def acceleration_conversion(units,model_length_unit,scale):
    if model_length_unit not in ('m','mm') or units not in ('g','m/s2'):raise ValueError('Explicit g or m/s2 input and m or mm model length are required')
    scale=float(scale)
    if not math.isfinite(scale) or scale<=0:raise ValueError('Motion scale must be finite and positive')
    unit=(9.80665 if units=='g' else 1.)*(1000. if model_length_unit=='mm' else 1.)
    return dict(source_units=units,model_acceleration_units=model_length_unit+'/s2',record_scale_factor=scale,unit_conversion=unit,total_path_factor=unit*scale)
