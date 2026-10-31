"""Benchmark specimen materials only; not calibrated to the ETABS building."""
from Define_Section_V109 import define_wall_reference_materials
LITERATURE_ONLY = True
PROJECT_CALIBRATED = False
def define_materials(ops):
    return define_wall_reference_materials(ops, unit_system="kN-m")
