"""Acceptance metadata/AST compatibility only; no population scan or QM."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SCRIPTS=ROOT/'scripts'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def functions(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(p).read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();checks=[]
 for old,new,names in [
 ('wp5_acceptance_verify_v9.py','wp5_acceptance_verify_v10.py',('execution_authorities','run_execution_binding','finite','initializer','stratum','issue','read_companions','selected_molecules','authoritative_keys','key','reconstruct','numeric_leaves','raw_expected','check_file')),
 ('wp5_acceptance_recompute_v9.py','wp5_acceptance_recompute_v10.py',('bits_equal','rounding_equal','value_sha','summary','read_rows','precision_manifest','normalized_scientific','init_compare','compare_quantum','compare'))]:
  before=functions(SCRIPTS/old);after=functions(SCRIPTS/new)
  for name in names:
   assert name in before and before[name]==after.get(name),name
   checks.append({'before':old,'after':new,'function':name,'same_AST':True})
 old=(SCRIPTS/'wp5_acceptance_v12.sbatch').read_text();new=(SCRIPTS/'wp5_acceptance_v13.sbatch').read_text()
 expected=old.replace('wp5_acceptance_verify_v9.py','wp5_acceptance_verify_v10.py').replace('wp5_acceptance_recompute_v9.py','wp5_acceptance_recompute_v10.py').replace('wp5_acceptance_pilot.py','wp5_acceptance_pilot_v2.py').replace('#SBATCH --job-name=wp5_acceptance','#SBATCH --job-name=wp5_acceptance\n#SBATCH --chdir=/share/home/zixiao/descriptor_analysis')
 assert new==expected,'DISPATCH_CHANGED_BEYOND_TARGET_NAMES_AND_EXPLICIT_CWD'
 import wp5_acceptance_verify_v10 as V
 import wp5_acceptance_recompute_v10 as C
 from wp5_submit_formal_v14 import validate_current_contract
 contract_path=ROOT/'configs/production_contract_v7.json'
 contract=validate_current_contract(contract_path,ROOT/'gates/wp5_node_replacement_user_approved.json')
 authorities=V.execution_authorities(contract_path)
 assert {r['contract']['path'] for r in authorities.values()}=={str(ROOT/'configs'/('production_contract_v'+str(n)+'.json')) for n in (3,4,5,6,7)}
 assert contract['seeds']['final200']==20261011 and contract['final200_required'] is True
 from wp5_parquet_v2 import MISSING
 assert C.bits_equal(0.,0.) and not C.bits_equal(0.,-0.) and not C.bits_equal(None,0.) and not C.bits_equal(MISSING,None)
 assert C.value_sha(0.)!=C.value_sha(-0.) and C.value_sha(MISSING)!=C.value_sha(None)
 selected=[]
 current=Path(json.loads((ROOT/'reports/phase16_first_single_durable_SCI_proof_v1.json').read_text())['run_json']['path'])
 for path in [ROOT/'runtime/task_cleanup_14/job_4515292_38e2d502/run.json',current]:
  run=json.loads(path.read_text());opt=run['options']
  bound=V.run_execution_binding({'run_root':str(path.parent),'job_id':opt['job_id']},authorities,{})
  assert bound['contract']['path']==opt['production_contract'] and bound['package']['sha256']==opt['reproduction_package_sha256']
  selected.append(bound)
 report={'schema':'WP5_ACCEPTANCE_CONTRACT7_METADATA_AST_BRIDGE_V1','status':'PASS','time':time.time(),'processing_pid':os.getpid(),'current_contract':ref(contract_path),'historical_contracts':list(authorities.values()),'actual_old_and_new_run_metadata_bindings':selected,'unchanged_scientific_function_count':len(checks),'unchanged_scientific_functions':checks,'batch_only_current_entrypoints_and_explicit_cwd':True,'selection_seed':20261011,'exact200_scope_unchanged':True,'NULL_ABSENT_ZERO_signed_zero_checks':True,'population_SCI_raw_LMDB_opened':False,'QM_started':False,'final_acceptance_performed':False,'frozen_production_sources_modified':False,'sources':[ref(SCRIPTS/n) for n in ('wp5_acceptance_verify_v10.py','wp5_acceptance_recompute_v10.py','wp5_acceptance_v13.sbatch','wp5_acceptance_pilot_v2.py')],'source':ref(Path(__file__))}
 assert a.out.resolve().is_relative_to((ROOT/'reports').resolve())
 with a.out.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'status':report['status'],'unchanged_scientific_functions':len(checks),'historical_contracts':len(authorities),'actual_run_metadata_checked':len(selected),'out':str(a.out)}))
if __name__=='__main__':main()