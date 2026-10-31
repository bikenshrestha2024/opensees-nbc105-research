"""V132 compatibility entry. Implementation: components/model/assembly.py.
Historical module names remain valid for previously exported model scripts.
"""
from pathlib import Path as _FacadePath
_component_source = _FacadePath(__file__).resolve().parent / 'components' / 'model/assembly.py'
if not _component_source.is_file():
    _component_source = _FacadePath(__file__).resolve().parent / 'OpenSees_Runtime_V118' / 'components' / _component_source.relative_to(_FacadePath(__file__).resolve().parent / 'components')
exec(compile(_component_source.read_text(encoding='utf-8'), str(_component_source), 'exec'), globals(), globals())
