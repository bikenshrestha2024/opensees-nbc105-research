from pathlib import Path
_component_source=Path(__file__).resolve().parent/'components/gravity/load_path_formulas.py'
if not _component_source.is_file():_component_source=Path(__file__).resolve().parent/'OpenSees_Runtime_V118/components/gravity/load_path_formulas.py'
exec(compile(_component_source.read_text(encoding='utf-8'),str(_component_source),'exec'),globals(),globals())
