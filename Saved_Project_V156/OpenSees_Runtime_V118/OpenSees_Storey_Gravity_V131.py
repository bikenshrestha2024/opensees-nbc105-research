"""V131 storey gravity implementation; keep components beside this loader."""
from pathlib import Path
_component_source=Path(__file__).resolve().parent/'components/gravity/storey_loads.py'
exec(compile(_component_source.read_text(encoding='utf-8-sig'),str(_component_source),'exec'),globals(),globals())
