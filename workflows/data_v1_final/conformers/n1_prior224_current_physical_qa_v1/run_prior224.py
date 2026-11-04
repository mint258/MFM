"""Closed prior Main224 physical QA; no new Native, old files or global registry writes."""
import argparse,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib,stat,sys
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
SCOPED=ROOT/'repository/workflows/data_v1_final/conformers/n1_current_canonical_physical_qa_v1'
sys.path.insert(0,str(SCOPED))
import main100_runtime as R,scoped_identity as ID
from portable_n1_source_remaining_v1 import contract as C
from portable_n1_source_physical_qa_v1 import identity as OLD_ID
from workflows.data_v1_final.pprime.n1_extra_common_day_v3 import bridge as B,history as H,reduce as D
import prior224_worker as W
HERE=pathlib.Path(__file__).absolute().parent
JOBS={'4521418','4521476','4521479','4521481'}

class View:
    def __init__(self,target,**values):self.target,self.values=target,values
    def __getattr__(self,name):return self.values[name] if name in self.values else getattr(self.target,name)

class BridgeBudget:
    def __init__(self,budget):self.budget=budget;self.proof=budget.proof
    def check(self):return self.budget.check()
    def raw(self,path,body):return self.budget.write(path,body)
    def write(self,path,value):
        value={**value,'canonical_ledger_observation_scope':'ONLY_FOUR_REGISTERED_PRIOR_MAIN_ORIGINS',
            'global_N1_ledger_completeness_claimed':False,'new_UFF_QM_calls':0,'old_once_mutated':False}
        return self.budget.write(path,C.canonical(value)+b'\n')

class OutputBudget(OLD_ID.OutputBudget):
    def write(self,path,value):
        schemas={'COMMON_N1_PPRIME_EXTRA_INDEX_V1':'N1_PRIOR_MAIN224_CURRENT_SOURCE_EXTRA_INDEX_V1',
            'COMMON_N1_PPRIME_FIRST2_ORDER_SIDECAR_V1':'N1_PRIOR_MAIN224_CURRENT_SOURCE_FIRST2_ORDER_SIDECAR_V1'}
        C.need(value['schema'] in schemas,'ONLY_ORIGINAL_EXTRA_AND_ORDER_OUTPUTS')
        value={**value,'schema':schemas[value['schema']],'identity_scope':ID.SCOPE,
            'original_Main_generation_parent_ids':sorted(JOBS),'not_Alpha_import5249':True,
            'historical_noncanonical_coverage':'UNKNOWN','source_only_not_final_Common':True,'D6_canonical_release':False,'READY':False}
        return self.original.write(path,C.canonical(value)+b'\n')


def load_prior(plan,budget):
    header=C.load(plan['prior_Main224_inputs_reference'])
    C.need(header['schema']=='ROOT_N1_PRIOR_MAIN224_CLOSED_SOURCE_INPUTS_CANDIDATE_V1'
        and header['expected_registered_tasks']==224 and set(header['actual_original_parent_ids'])==JOBS,
        'EXACT_PRIOR_MAIN224_INPUT_SCOPE')
    manifest=dict(header['history']);registrations=[]
    for old in manifest['registered_generation_roots']:
        item=dict(old);C.need(item['job_id'] in JOBS,'ONLY_FOUR_ACTUAL_MAIN_ORIGINS')
        C.load(item['startup_proof_reference'])
        if item['producer_receipt_reference'] is None:
            path=C.literal(item['closed_receipt_locator'])
            request=C.load(item['request_reference']);root=B.argument(request,'output')
            C.need(path==root/'receipt.json','ONLY_REGISTERED_CLOSED_RECEIPT_LOCATOR')
            if path.exists():item['producer_receipt_reference']=C.ref(path,2<<20,check=budget.check)
        registrations.append(item)
    manifest['registered_generation_roots']=registrations
    desc,unused_data,unused_sources=B.describe(manifest,header['actual32_review_reference'])
    keys=set()
    for entry in desc['entries']:
        if entry['mode']=='pilot32_v4':
            local=[C.load(ref,8<<20)['task_key'] for ref in entry['prepared']['tasks']]
            C.need(len(local)==32,'WHOLE_ORIGINAL_PILOT32')
        else:
            batch=C.load(entry['batch_reference']);local=[row['task_key'] for row in batch['tasks']]
            C.need(len(local)==64,'WHOLE_ORIGINAL_FINITE64_NOT_A_NEW_SAMPLE')
        C.need(len(local)==len(set(local)) and not(keys&set(local)),'DISJOINT_ORIGINAL_NATIVE_TASK_KEYS');keys.update(local)
    C.need(len(keys)==224 and {e['job_id'] for e in desc['entries']}==JOBS,'ALL_PRIOR224_REGISTERED_KEYS_AND_FOUR_ORIGINS')
    def scoped_keys():
        # Explicit source domain, not a scan pretending the later4407 foreign
        # assignments do not exist. Original claim files are only read.
        result=set()
        for key in keys:
            path=H.C.LEDGER/(key+'.json')
            if path.exists():
                state=path.lstat();C.need(stat.S_ISREG(state.st_mode) and state.st_uid==1278 and not path.is_symlink(),
                    'ORIGINAL_OWN_PRIOR_MAIN_CANONICAL_CLAIM');result.add(key)
        return result
    scoped_history=View(H,ledger_keys=scoped_keys)
    bridge=R.private(B.execute,H=scoped_history)
    runtime_history,census=bridge({'old_history_bridge':desc,'history':manifest},budget.out,BridgeBudget(budget))
    pilot_entry=next(e for e in desc['entries'] if e['mode']=='pilot32_v4')
    load=R.private(H.load,ledger_keys=scoped_keys)
    claims,closed,audit=load(runtime_history,BridgeBudget(budget),
        {'pilot':pilot_entry['producer_receipt'],'pilot_prepared':pilot_entry['prepared']})
    records={}
    for line in C.verify(runtime_history['attempt_registry_references'][0],check=budget.check).read_text().splitlines():
        row=json.loads(line);C.need(row['task_key'] not in records,'ONE_CLOSED_SOURCE_STATE_PER_REGISTERED_TASK');records[row['task_key']]=row
    C.need(set(records)==keys,'EXACT224_STATE_CONSERVATION_NOT_ONLY_SUCCESSFUL_PACKETS')
    for key,value in closed.items():
        value.update(task_key=key,molecule_id=value['task']['meta']['molecule_id'],
            origin_startup_proof_reference=C.triple(value['packet']['startup_proof_reference']))
    return header,records,closed,audit,census


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,type=pathlib.Path);parser.add_argument('--startup-proof',required=True,type=pathlib.Path)
    args=parser.parse_args();plan,proof=R.admit(args.plan,args.startup_proof,'physical_qa')
    C.need(plan['schema']=='N1_PRIOR_MAIN224_CURRENT_PHYSICAL_QA_PLAN_V1','EXPLICIT_NEW_MAIN224_NOT_ALPHA4407_PLAN')
    pins=proof['request']['source_references']
    for name in ('run_prior224.py','prior224_worker.py','metadata.py','README.md'):
        C.need(C.ref(HERE/name,2<<20) in pins,'CURRENT_MAIN224_SOURCE_PIN:'+name)
    out=C.literal(plan['output_directory']);C.need(ID.OUTPUT in out.parents and not out.exists(),'FRESH_CURRENT_SCOPE_OUTPUT')
    out.mkdir(parents=True);budget=R.Budget(plan,proof,out);budget.check()
    header,records,closed,audit,census=load_prior(plan,budget)
    authority=ID.authority(plan['physical_identity_authority_reference'])
    chosen={key:value for key,value in closed.items() if value['packet']['supplement'] is not None}
    identities=ID.census(authority,[e['molecule_id'] for e in chosen.values()],budget) if chosen else {}
    context=dict(plan=plan,graph_source=C.load(plan['catalog_reference'])['references']['graph_stereo_rmsd'],
        parent=dict(pid=os.getpid(),start_ticks=R.ORIGINAL.ticks(os.getpid()),boot_id=R.ORIGINAL.boot(),job_id=str(proof['job_id']),argv=plan['execution_argv']))
    results=[]
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=W.initialize,initargs=(context,)) as pool:
        active={};items=iter(sorted(chosen.items()));finished=False
        while active or not finished:
            budget.check()
            while not finished and len(active)<16:
                try:key,entry=next(items)
                except StopIteration:finished=True;break
                active[pool.submit(W.one,(entry,identities[entry['molecule_id']]))]=key
            if active:
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                budget.observe([p.pid for p in pool._processes.values()])
                for future in done:
                    key=active.pop(future);value=future.result();C.need(value['task_key']==key,'ONE_INDEPENDENT_QA_RETURN_PER_SOURCE_KEY');results.append(value)
    by={r['task_key']:r for r in results};outcomes=[]
    for key,row in sorted(records.items()):
        if key in by:outcomes.append({k:v for k,v in by[key].items() if k!='accepted'})
        else:outcomes.append(dict(task_key=key,molecule_id=row['molecule_id'],status='ORIGINAL_SOURCE_STATE_RETAINED_NO_NEW_ID',
            original_state=row['state'],original_observation=row,physical_ID_registered=False,automatic_retry=False))
    C.need(len(outcomes)==len({r['task_key'] for r in outcomes})==224,'WHOLE224_FINAL_STATE_CONSERVATION')
    states=budget.write(out/'physical_QA_all224_states.jsonl',b''.join(C.canonical(r)+b'\n' for r in outcomes))
    complete=len(results)==len(chosen) and all(r['accepted'] is not None for r in results)
    artifacts=D.output(out,[r['accepted'] for r in sorted(results,key=lambda x:x['task_key'])],OutputBudget(budget)) if complete and results else {}
    receipt=dict(schema='N1_PRIOR_MAIN224_CURRENT_PHYSICAL_QA_RECEIPT_V1',
        status='PHYSICAL_ID_SIDECAR_PENDING_ROOT_D6_INTEGRATION' if complete else 'PHYSICAL_QA_UNRESOLVED_NO_ID_REGISTRATION',
        job_id=str(proof['job_id']),uid=1278,identity_scope=ID.SCOPE,plan_reference=C.ref(args.plan),startup_proof_reference=C.ref(args.startup_proof),
        prior_Main224_inputs_reference=plan['prior_Main224_inputs_reference'],original_Main_generation_parent_ids=sorted(JOBS),
        actual_original_native_uid=1278,actual_original_native_node='compute-0-13',source_was_Alpha_import5249=False,
        physical_identity_authority_reference=plan['physical_identity_authority_reference'],registered_source_states=224,
        source_packets_closed=len(closed),real_second_source_packets=len(chosen),independent_QA_passed=sum(r['accepted'] is not None for r in results),
        all224_states_reference=states,original_source_census_reference=census,source_readback_audit=audit,
        existing4400_repeated_QA=False,ordinary_Sprime_N_D5_and_order_tables_modified=False,
        canonical_physical_registry_rewritten=False,Common_or_D6_training_release=False,READY=False,
        new_UFF_calls=0,new_QM_calls=0,automatic_retry=False,historical_noncanonical_coverage='UNKNOWN',**artifacts)
    budget.write(out/'receipt.json',C.canonical(receipt)+b'\n')
    return 0 if complete else 3

if __name__=='__main__':raise SystemExit(main())