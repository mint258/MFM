"""Transport a closed prepared geometry database; never repeat its projection."""
import argparse,json,shutil
from pathlib import Path

def same_source_inputs(left,right):
    operational={'workers','workspace','output'}
    return {k:v for k,v in left.items() if k not in operational}=={k:v for k,v in right.items() if k not in operational}

def stage(fill_plan,source):
    plan=json.loads(Path(fill_plan).read_text())
    data_plan=json.loads(Path(plan['d7_plan']).read_text())
    data_plan.update(workspace=plan['workspace'],output=plan['output'],workers=plan['workers'])
    source=Path(source);out=Path(plan['workspace']);out.mkdir(parents=True,exist_ok=True)
    metadata=json.loads((source/'ready.json').read_text())
    if not same_source_inputs(metadata['plan'],data_plan):raise ValueError('PREPARED_GEOMETRY_SOURCE_INPUTS_CHANGED')
    if (out/'ready.json').exists():
        if json.loads((out/'ready.json').read_text())['plan']!=data_plan:raise ValueError('FILL_PREPARED_PLAN_CHANGED')
        return
    shutil.copyfile(source/'d7.duckdb',out/'d7.duckdb')
    metadata['plan']=data_plan
    (out/'ready.json').write_text(json.dumps(metadata),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fill-plan',required=True);p.add_argument('--source',required=True);a=p.parse_args();stage(a.fill_plan,a.source)
