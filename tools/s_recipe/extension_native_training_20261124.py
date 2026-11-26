"""Validate extension scope, then reuse the tested native/takeover providers."""
import argparse
import json
from pathlib import Path
from extension_training_20261124 import validate, REPO


def bound(c):
    source=REPO/'configs/s_recipe'/('screening/S-R1.json' if c.get('extension_kind')=='E1'
                                  else 'confirmation/S-final.json')
    return validate(c,json.loads(source.read_text()),json.loads(Path(c['population']).read_text()))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--task',type=Path,required=True)
    p.add_argument('--mode',choices=('native','takeover'),default='native')
    args=p.parse_args()
    task=json.loads(args.task.read_text())
    bound(task['configuration'])
    if args.mode=='native':
        from native_training_20261123 import run
        print(json.dumps(run(task)),flush=True)
    else:
        from native_takeover_20261123 import main
        main(args.task)
