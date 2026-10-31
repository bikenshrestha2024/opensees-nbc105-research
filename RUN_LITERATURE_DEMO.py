"""Compatibility launcher; use 17_LITERATURE_COMPONENT_DEMO.py for the ordered entry point."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "17_LITERATURE_COMPONENT_DEMO.py"), run_name="__main__")
