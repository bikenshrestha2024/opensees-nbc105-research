"""Stage timing associated with every created/changed output, without corrupting CSV schemas."""

__release__ = '134'
import functools,inspect,json,time,traceback
from pathlib import Path
from datetime import datetime,timezone,timedelta
NEPAL=timezone(timedelta(hours=5,minutes=45))
def stamp():return datetime.now(NEPAL).isoformat(timespec='milliseconds')
def timed_outputs(stage,argument):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args,**kwargs):
            bound=inspect.signature(function).bind(*args,**kwargs);bound.apply_defaults();value=bound.arguments.get(argument)
            if isinstance(value,dict):value=value.get('output_dir')
            folder=Path(value).resolve() if value else None
            if folder and (folder.is_file() or (not folder.exists() and folder.suffix)):folder=folder.parent
            started=stamp();clock=time.perf_counter();wall_ns=time.time_ns();status='completed';failure=None
            try:return function(*args,**kwargs)
            except BaseException as exc:
                status='failed';failure=f'{type(exc).__name__}: {exc}';raise
            finally:
                elapsed=time.perf_counter()-clock
                metadata=dict(stage=stage,started_at=started,finished_at=stamp(),elapsed_seconds=elapsed,status=status,error=failure,time_scope='Entire named processing stage, not individual file-write latency')
                if folder and folder.exists():
                    try:
                        files=[p for p in folder.rglob('*') if p.is_file() and p.stat().st_mtime_ns>=wall_ns and not p.name.endswith('.processing.json') and p.name not in ('Processing_Timings_V130.jsonl','OUTPUT_TIMING_INDEX_V130.json') and '__pycache__' not in p.parts]
                        index_path=folder/'OUTPUT_TIMING_INDEX_V130.json'
                        try:index=json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
                        except Exception:index={}
                        for path in files:
                            sidecar=path.with_name(path.name+'.processing.json');record=dict(metadata,artifact=str(path.relative_to(folder)),size_bytes=path.stat().st_size)
                            sidecar.write_text(json.dumps(record,indent=2),encoding='utf-8');index[str(path.relative_to(folder))]=record
                        index_path.write_text(json.dumps(index,indent=2),encoding='utf-8')
                        with (folder/'Processing_Timings_V130.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(dict(metadata,artifact_count=len(files)))+'\n')
                    except Exception as exc:print(f'[TIMING METADATA ERROR] {stage}: {exc}',flush=True)
                print(f'[TIMING] {stage} | {status} | elapsed={elapsed:.3f} s | start={started} | finish={metadata["finished_at"]}',flush=True)
        return wrapped
    return decorate


class StageTimer:
    def __init__(self,folder,stage):
        self.folder=Path(folder);self.stage=stage;self.clock=time.perf_counter();self.started=stamp();self.finished=False
    def finish(self,status='unconfirmed — inspect solver exit log'):
        if self.finished:return
        self.finished=True;elapsed=time.perf_counter()-self.clock
        data=dict(stage=self.stage,started_at=self.started,finished_at=stamp(),elapsed_seconds=elapsed,status=status,time_scope='Entire processing stage, not individual write latency')
        self.folder.mkdir(parents=True,exist_ok=True)
        threshold=time.time()-elapsed
        try:index=json.loads(self.folder.joinpath('OUTPUT_TIMING_INDEX_V130.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):index={}
        for path in list(self.folder.glob('*')):
            if not path.is_file() or path.stat().st_mtime<threshold or path.name.endswith('.processing.json') or path.name.startswith(('OUTPUT_TIMING_INDEX','Processing_Timings')):continue
            record=dict(data,artifact=path.name,size_bytes=path.stat().st_size);path.with_name(path.name+'.processing.json').write_text(json.dumps(record,indent=2),encoding='utf-8');index[path.name]=record
        self.folder.joinpath('OUTPUT_TIMING_INDEX_V130.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
        with self.folder.joinpath('Processing_Timings_V130.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(data)+'\n')
        print(f'[TIMING] {self.stage} | {status} | elapsed={elapsed:.3f}s | start={self.started} | finish={data["finished_at"]}',flush=True)
