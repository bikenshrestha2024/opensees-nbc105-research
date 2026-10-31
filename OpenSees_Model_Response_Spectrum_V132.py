from pathlib import Path
_component_source=Path(__file__).resolve().parent/'components/response_spectrum/model_analysis.py'
exec(compile(_component_source.read_text(encoding='utf-8-sig'),str(_component_source),'exec'),globals(),globals())
