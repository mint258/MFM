"""Resume closed D7 checkpoints with a different actual CPU worker allocation."""
import argparse,json,types
from pathlib import Path
from workflows.data_v1_final.conformers.window2_population_v1 import d7 as original

def same_inputs(left,right):
    # Worker count is an operational choice, not a molecule, seed or recipe.
    return {k:v for k,v in left.items()if k!='workers'}=={k:v for k,v in right.items()if k!='workers'}

def prepare(plan,workspace):
    import duckdb
    ready=Path(workspace)/'ready.json'
    if not ready.exists():return original.prepare(plan,workspace)
    if not same_inputs(original.read(ready)['plan'],plan):raise ValueError('D7_RESUME_SCIENTIFIC_INPUTS_DIFFER')
    db=duckdb.connect(str(Path(workspace)/'d7.duckdb'));db.execute('SET threads='+str(plan['workers']))
    return db,original.read(plan['common'])

RAW_RMSD = None
DISTANCES = {}

def cached_rmsd(mol, xyz, reference):
    # Directed identity key: preserve the exact original call orientation and
    # all SVD/reduction arithmetic. Arrays stay alive for this one molecule.
    key = (id(mol), id(xyz), id(reference))
    if key not in DISTANCES:
        DISTANCES[key] = RAW_RMSD(mol, xyz, reference)
    return DISTANCES[key]

def initialize(science_path):
    global RAW_RMSD
    original.initialize(science_path)
    RAW_RMSD = original.SCIENCE.rmsd
    original.SCIENCE.rmsd = cached_rmsd

def safe_one(task):
    DISTANCES.clear()
    try:
        return original.safe_one(task)
    finally:
        DISTANCES.clear()

def run(plan):
    manifest=Path(plan['output'])/'manifest.json'
    if manifest.exists():
        print('D7_ALREADY_CLOSED',original.read(manifest)['status'],flush=True);return
    function=original.run
    namespace=dict(function.__globals__,prepare=prepare,initialize=initialize,safe_one=safe_one)
    current=types.FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
    current.__kwdefaults__=function.__kwdefaults__
    return current(plan)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();run(json.loads(Path(a.plan).read_text()))