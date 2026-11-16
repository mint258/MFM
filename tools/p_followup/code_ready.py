from pathlib import Path
from accept_f64_sidecar import baseline_dataset_class
if __name__=='__main__':
 root=Path(__file__).resolve().parents[2]
 for p in (root/'tools/p_followup').glob('*.py'):compile(p.read_text(),str(p),'exec')
 print('BASELINE_LOADER_CLASS',baseline_dataset_class().__module__)
 print('FOLLOWUP_SOURCES_COMPILE')