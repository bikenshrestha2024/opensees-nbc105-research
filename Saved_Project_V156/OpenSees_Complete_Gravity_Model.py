# Generated complete-model entry; units kN, m, s.
from pathlib import Path
import sys, json, os
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'OpenSees_Runtime_V118'))
GRAVITY_GUI_INPUTS = {'support_node_tags': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 8751, 8752, 8753, 9544, 9545, 9546, 10453, 10457, 10468, 10504, 11888, 11892, 12383, 12387, 12398, 12409, 12919, 12923, 13509, 13510, 13511], 'total_downward_load_kN': 286447.78893335, 'load_steps': 10, 'coverage_note': 'Assembled frame/area distributed loads and self-weight; see V118 report for unsupported source actions and validation limits.'}
from OpenSees_Complete_Export_V118 import build_complete_model
MODEL_REPORT = build_complete_model(HERE, mode='elastic', preload=False, limit_state=os.environ.get('OPENSEES_LIMIT_STATE','ULS'))
PD_FILE=HERE/'OpenSees_IS16700_Initial_PDelta_Results.json'
IS16700_INITIAL_PDELTA_RESULTS=json.loads(PD_FILE.read_text(encoding='utf-8-sig')) if PD_FILE.is_file() else {}
