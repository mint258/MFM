"""Small acceptance metadata/AST bridge only; no population/SCI/raw scan or QM."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SCRIPTS=ROOT/'scripts'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def functions(path):
    tree=ast.parse(Path(path).read_text())
    return {node.name:ast.dump(node,include_attributes=False) for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
def main():
    p=argparse.ArgumentParser();p.add_argument('--production-contract',type=Path,default=ROOT/'configs/production_contract_v6.json')
    p.add_argument('--out',type=Path);a=p.parse_args()
    checks=[]
    rules=[
      ('wp5_acceptance_verify_v8.py','wp5_acceptance_verify_v9.py',
       ('finite','initializer','stratum','issue','read_companions','selected_molecules','authoritative_keys','key','reconstruct','numeric_leaves','raw_expected','check_file')),
      ('wp5_acceptance_recompute_v8.py','wp5_acceptance_recompute_v9.py',
       ('bits_equal','rounding_equal','value_sha','summary','read_rows','precision_manifest','normalized_scientific','init_compare','compare_quantum','compare'))
    ]
    for old,new,names in rules:
        before=functions(SCRIPTS/old);after=functions(SCRIPTS/new)
        for name in names:
            if name not in before or before[name]!=after.get(name):raise ValueError('SCIENTIFIC_FUNCTION_AST_CHANGED:'+name)
            checks.append({'before':old,'after':new,'function':name,'same_AST':True})
    # Only dispatch target versions changed in this batch; shell lifecycle and
    # original catalog3/launch3, selection/retention/precision paths stay intact.
    old=(SCRIPTS/'wp5_acceptance_v10.sbatch').read_bytes()
    new=(SCRIPTS/'wp5_acceptance_v11.sbatch').read_bytes()
    expected=old.replace(b'wp5_acceptance_verify_v8.py',b'wp5_acceptance_verify_v9.py').replace(b'wp5_acceptance_recompute_v8.py',b'wp5_acceptance_recompute_v9.py')
    if new!=expected:raise ValueError('BATCH_CHANGED_BEYOND_TWO_DISPATCH_NAMES')
    import wp5_acceptance_verify_v9 as V
    authorities=V.execution_authorities(a.production_contract)
    current=json.loads(a.production_contract.read_text())
    runners=[ref for name,ref in current['current_runtime'].items() if name.startswith('wp5_runner_v') and name.endswith('.py')]
    if len(runners)!=1:raise ValueError('CURRENT_RUNTIME_RUNNER_NOT_UNIQUE')
    if sha(runners[0]['path'])!=runners[0]['sha256']:raise ValueError('CURRENT_RUNTIME_RUNNER_SHA_CHANGED')
    if current['seeds']['final200']!=20261011 or current['final200_required'] is not True:
        raise ValueError('ORIGINAL_FINAL200_SEED_OR_REQUIREMENT_CHANGED')
    assert V.reference_identity({'path':'p','sha256':'s','bytes':1})=={'path':'p','sha256':'s'}
    refs=[SCRIPTS/x for x in (
      'wp5_acceptance_catalog_v3.py','wp5_acceptance_launch_v3.py','wp5_acceptance_verify_v8.py',
      'wp5_acceptance_verify_v9.py','wp5_acceptance_recompute_v8.py','wp5_acceptance_recompute_v9.py',
      'wp5_acceptance_v10.sbatch','wp5_acceptance_v11.sbatch')]
    report={'schema':'WP5_ACCEPTANCE_CONTRACT6_METADATA_AST_BRIDGE_V1','status':'PASS',
        'source':{'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},
        'created_epoch':time.time(),'processing_pid':os.getpid(),'current_contract':{'path':str(a.production_contract),'sha256':sha(a.production_contract)},
        'execution_authorities':list(authorities.values()),'current_runner':runners[0],
        'unchanged_scientific_function_count':len(checks),'unchanged_scientific_functions':checks,
        'batch_changed_only_dispatch_names':True,'current_and_historical_run_provenance_preserved':True,
        'source_refs':[{'path':str(x),'sha256':sha(x),'bytes':x.stat().st_size} for x in refs],
        'uniform200_seed':20261011,'final200_required':True,
        'population_SCI_labels_raw_LMDB_opened':False,'QM_started':False,'production_queue_opened':False,
        'frozen_production_sources_modified':False,'float32_export_started':False}
    if a.out:
        if not a.out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_METADATA_REPORT_SCOPE_REQUIRED')
        with a.out.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(report,allow_nan=False))
if __name__=='__main__':main()
