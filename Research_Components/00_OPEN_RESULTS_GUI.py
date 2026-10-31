from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from components.validation.research_results_gui import main
if __name__=='__main__':main()
