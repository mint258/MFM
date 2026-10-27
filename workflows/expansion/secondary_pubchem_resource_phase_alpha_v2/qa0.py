"""Fresh-guard zero-science resource QA; same fixed main with early QA return."""
import argparse
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q

def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True)
    a=p.parse_args();Q.need(Q.load(a.plan).get('resource_phase')=='QA0','ONLY_QA0_PRIMARY_NO_SCIENTIFIC_BODY')
    from .run import main as run
    return run()

if __name__=='__main__':raise SystemExit(main())
