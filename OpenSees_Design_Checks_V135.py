from pathlib import Path
_component_source=Path(__file__).resolve().parent/'components/validation/design_checks.py'
exec(compile(_component_source.read_text(encoding='utf-8-sig'),str(_component_source),'exec'),globals(),globals())
