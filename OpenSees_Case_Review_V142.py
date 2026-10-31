from pathlib import Path
_component_source=Path(__file__).resolve().parent/'components/validation/case_review.py'
if not _component_source.is_file():_component_source=Path(__file__).resolve().parent/'OpenSees_Runtime_V118/components/validation/case_review.py'
exec(compile(_component_source.read_text(encoding='utf-8'),str(_component_source),'exec'),globals(),globals())
