"""One real Alpha parent per exact finite N1 shard; no scheduling or retry."""
import argparse,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib
from . import contract as C,runtime as R,storage as S,worker as W
from .source import proof as source_proof,existing_environment


def target(ref,plan):
    value=plan['locator_map'].get(ref['path'],ref)
    C.need(value['bytes']==ref['bytes'] and value['sha256']==ref['sha256'],'EXACT_SOURCE_COPY_LOCATOR');return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--startup-proof',required=True,type=pathlib.Path);a=p.parse_args()
    plan,admission=R.admit(a.plan,a.startup_proof,'run');C.need(plan['endpoint']['id']=='alpha','TRUE_ALPHA_NATIVE_SCIENCE_ONLY')
    science_proof=source_proof();manifest=C.load(target(plan['assignment_manifest_reference'],plan))
    C.need(manifest['schema']=='N1_SOURCE_FINITE_REMAINING_ASSIGNMENTS_V1'
        and manifest['status']=='FROZEN_AWAITING_ROOT_EXACT_FINITE_SCIENCE_REVIEW'
        and manifest['remaining_frozen']==plan['whole_remaining_count'] and 0<manifest['remaining_frozen']<=4631,'EXACT_BOUNDED_ACTUAL_SOURCE_REMAINDER')
    C.need(str(manifest['actual_export_job_id'])==str(plan['actual_export_job_id']),'ACTUAL_EXPORT_PARENT_BOUND_TO_FINITE_SCIENCE_COST')
    selected=[s for s in manifest['shards'] if s['shard_id']==plan['shard_id']];C.need(len(selected)==1,'ONE_EXACT_SHARD');shard=selected[0]
    for key in ('endpoint','cpus','node','wall_seconds','stop_dispatch_before_wall_seconds','output_cap_bytes','output_directory'):
        C.need(shard[key]==plan[key],'FROZEN_NATIVE_RESOURCE_AND_OWNER')
    members=C.load(target(shard['members_reference'],plan),C.ADMIN)
    C.need(len(members)==shard['molecules'] and len(members)>0 and len({m['task_key'] for m in members})==len(members),'WHOLE_NONEMPTY_UNIQUE_MEMBERS')
    by={m['task_key']:m for m in members};review=C.load(plan['root_review_reference'])
    C.need(review['exact_task_keys_sha256']==C.value_sha(sorted(by)) and review['assignment_manifest_reference']==plan['assignment_manifest_reference'],'ROOT_REVIEW_BINDS_ACTUAL_FROZEN_KEYS_NOT_GENERIC_FULL_PERMISSION')
    out=C.literal(plan['output_directory']);C.need(not out.exists(),'NEW_NATIVE_OUTPUT');out.mkdir(parents=True)
    budget=R.Budget(plan,admission,out);budget.check()
    environment=C.load(plan['environment_review_reference']);legacy,compatibility=existing_environment(environment,plan['legacy_control16_deployment_reference'])
    prepared=C.load(target(manifest['source_prepared_reference'],plan))
    ctx={'legacy_deployment':legacy,'endpoint':plan['endpoint'],'job_id':str(admission['job_id']),'cpus':plan['cpus'],
        'node':plan['node'],'out':str(out),'source_population_authority_reference':prepared['source_population_authority'],
        'prepared_manifest_reference':manifest['source_prepared_reference'],'catalog_reference':prepared['catalog'],
        'startup_proof_reference':C.ref(a.startup_proof),'assignment_manifest_reference':plan['assignment_manifest_reference']}
    ctx['expected_versions']=environment['endpoint_versions']['alpha']
    ctx['parent']={'pid':os.getpid(),'start_ticks':R.ticks(os.getpid()),'boot_id':R.boot(),
        'actual_argv':[s.decode() for s in pathlib.Path('/proc/self/cmdline').read_bytes().split(b'\0') if s]}
    tasks=C.verify(target(shard['tasks_reference'],plan),check=budget.check)
    claimroot=C.ALPHA/'artifacts/portable_n1_source_remaining_v1/native_claims';claimroot.mkdir(parents=True,exist_ok=True)
    lockroot=C.ALPHA/'control/portable_n1_source_remaining_v1/shard_locks';lockroot.mkdir(parents=True,exist_ok=True)
    fd=os.open(lockroot/(plan['shard_id']+'.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    import fcntl
    records=[];errors=[];unstarted=[];consumed=[];seen=set();indices=[]
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def flush():
            if records:
                indices.append(budget.write(out/'result_indices'/('part%05d.jsonl'%len(indices)),b''.join(C.canonical(r)+b'\n' for r in records)));records.clear()
        with tasks.open('rb') as stream,cf.ProcessPoolExecutor(max_workers=plan['cpus'],mp_context=mp.get_context('spawn'),initializer=W.initialize,initargs=(ctx,)) as pool:
            active={};eof=False
            while active or not eof:
                while not eof and len(active)<plan['cpus'] and budget.observe()is None:
                    raw=stream.readline((64<<20)+1)
                    if not raw:eof=True;break
                    C.need(len(raw)<=64<<20 and raw.endswith(b'\n'),'COMPLETE_ORIGINAL_PAYLOAD_ENVELOPE')
                    value=json.loads(raw);task=value['task'];key=task['task_key'];C.need(key in by and key not in seen,'EXACT_FROZEN_TASK_STREAM');seen.add(key);member=by[key]
                    C.need(C.value_sha(task)==member['task_sha256']==value['task_sha256']
                        and value['original_Main_assignment_claim_reference']==member['original_Main_assignment_claim_reference'],'EXACT_TASK_AND_MAIN_ASSIGNMENT_RESERVATION')
                    ledger=claimroot/(key+'.json')
                    if ledger.exists():consumed.append({'task_key':key,'claim_reference':C.ref(ledger)});continue
                    if not budget.reserve(key,member['reservation_bytes']):unstarted.append(key);break
                    claim={'schema':'N1_ALPHA_NATIVE_DISPATCH_INTENT_V1','task_key':key,'molecule_id':member['molecule_id'],
                        'seed':member['seed'],'task_sha256':member['task_sha256'],'actual_parent_job_id':str(admission['job_id']),
                        'uid':1264,'endpoint':'218.192.171.238:22','node':plan['node'],'boot_id':admission['boot_id'],
                        'assignment_manifest_reference':plan['assignment_manifest_reference'],
                        'original_Main_assignment_claim_reference':member['original_Main_assignment_claim_reference'],
                        'parent_pid':os.getpid(),'parent_start_ticks':R.ticks(os.getpid()),'automatic_retry':False}
                    try:
                        claim_ref=C.save(ledger,claim);active[pool.submit(W.one,value,member,claim_ref)]=member
                    except BaseException as e:
                        errors.append({'task_key':key,'phase':'CLAIM_OR_SUBMISSION_UNKNOWN','error':repr(e),'automatic_retry':False})
                        budget.stop=budget.stop or 'CLAIM_OR_SUBMISSION_UNKNOWN_NO_RETRY';budget.release(key);break
                if budget.stop and not eof:
                    # Do not decode more scientific input during stop/drain.
                    unstarted.extend(sorted(set(by)-seen));eof=True
                if active:
                    budget.observe([p.pid for p in pool._processes.values()]);done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        member=active.pop(future);key=member['task_key']
                        try:
                            records.append(future.result())
                            if len(records)>=100:flush()
                        except BaseException as e:
                            errors.append({'task_key':key,'phase':'STARTED_NATIVE_UNKNOWN','error':repr(e),'automatic_retry':False})
                            budget.stop=budget.stop or 'STARTED_NATIVE_UNKNOWN_NO_RETRY'
                        finally:budget.release(key)
                elif eof or budget.stop:break
        flush();groups=[[],[r['task_key'] for r in errors],unstarted,[r['task_key'] for r in consumed]]
        for ref in indices:
            with C.verify(ref).open() as f:groups[0].extend(json.loads(line)['task_key'] for line in f)
        flat=sum(groups,[]);C.need(len(flat)==len(set(flat)) and set(flat)==set(by),'EXACT_CLOSED_ERROR_UNSTARTED_CONSUMED_PARTITION')
        receipt={'schema':'N1_FOREIGN_FINITE_SHARD_RECEIPT_V1','status':'NATIVE_DRAINED_ACTUAL_TERMINAL_ACCOUNTING_REQUIRED',
            'actual_parent_job_id':str(admission['job_id']),'endpoint':plan['endpoint'],'cpus':plan['cpus'],'node':plan['node'],
            'assignment_manifest_reference':plan['assignment_manifest_reference'],'shard_id':plan['shard_id'],
            'run_plan_reference':C.ref(a.plan),'startup_proof_reference':C.ref(a.startup_proof),'result_index_references':indices,
            'errors':errors,'unstarted_keys':unstarted,'already_consumed_native_claims':consumed,
            'all_started_native_tasks_drained':True,'signals_sent':False,'automatic_retry':False,'new_QM_calls':0,
            'resource_report':budget.report(),'source_proof':science_proof,'ordinary_N_changed':False,'common_or_physical_map_release':False}
        receipt['existing_environment_acceptance']=compatibility
        budget.write(out/'receipt.json',C.canonical(receipt)+b'\n')
        return 1 if errors else 0
    finally:os.close(fd)


if __name__=='__main__':raise SystemExit(main())
