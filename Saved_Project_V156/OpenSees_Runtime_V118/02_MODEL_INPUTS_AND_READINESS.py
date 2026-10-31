from pathlib import Path
import sys,runpy,os
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from OpenSees_Workflow_V144 import launch
launch()
