"""Allocated Main CPU: original4631 task-roster anti-join and lossless export0UFF."""
import argparse,base64,concurrent.futures as cf,fcntl,json,multiprocessing as mp,os,pathlib,sqlite3,time,traceback
from . import contract as C,runtime as R,storage as S
from .source import proof as source_proof


def keys():
    result=set()
    for p in C.MAIN_LEDGER.iterdir():
        C.need(p.is_file() and not p.is_symlink() and p.suffix=='.json' and len(p.stem)==64,'ONLY_CANONICAL_N1_CLAIMS')
        result.add(p.stem)
    return result


def envelope(item):
    row,authority=item;task=C.load(row['task_reference'],8<<20);base=C.load(row['baseline_reference'],8<<20)
    C.validate_task(task,authority);C.need(task['task_key']==row['task_key'] and task['meta']['molecule_id']==row['molecule_id']
        and base['original_row']==task['existing_conformers'][0] and task['baseline_row_sha256']==row['baseline_row_sha256'],'EXACT_FROZEN_TASK_AND_BASELINE')
    p=task['records'][0];path=pathlib.Path(p['source_path'])
    if not path.is_absolute():path=C.MAIN.parent.parent/path
    import lmdb
    with lmdb.open(str(path),subdir=False,readonly=True,lock=False,create=False,readahead=False,max_readers=1024) as env:
        with env.begin() as tx:raw=tx.get(f"{int(p['real_index']):09d}".encode())
    C.need(raw is not None and C.sha(raw)==p['record_payload_sha256'],'EXACT_ORIGINAL_LMDB_PICKLE_BYTES')
    value={'task':task,'task_sha256':C.value_sha(task),'record_payloads':[{'pointer_sha256':C.value_sha(p),'payload_bytes':len(raw),
        'payload_sha256':C.sha(raw),'original_pickle_base64':base64.b64encode(raw).decode()}],
        'original_task_reference':row['task_reference'],'original_baseline_reference':row['baseline_reference']}
    return value,C.reserve_task(task),len(task['source_atomic_numbers'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--startup-proof',required=True,type=pathlib.Path);a=p.parse_args()
    plan,admission=R.admit(a.plan,a.startup_proof,'freeze');C.need(plan['endpoint']['id']=='main' and plan['cpus']==16,'MAIN_REAL16_ZERO_SCI_EXPORT')
    plan_ref=C.ref(a.plan,2<<20)
    proof=source_proof();prepared=C.load(plan['prepared_reference']);review=C.load(plan['pilot_review_reference'])
    C.need(prepared['schema']=='N1_PPRIME2_SOURCE_FULL_PREPARED_V1' and prepared['status']=='ACTUAL_FULL_SOURCE_TASKS_FROZEN_NO_GENERATION'
        and prepared['selected_count']==4631 and prepared['imported_count']==32 and prepared['new_attempt_count']==4599
        and prepared['science_cost_review_reference']==plan['pilot_review_reference'] and prepared['once_ledger_root']==str(C.MAIN_LEDGER),'ORIGINAL_FROZEN4631_SOURCE_DOMAIN_NOT_COMMON')
    C.need(review['status']=='APPROVED_FOR_SOURCE_FULL_N1_IMPLEMENTATION_AND_BOUNDED_PLANNING'
        and review['formal_full_source_job_authorized_by_this_review']is False and review['actual_real_second_geometry']==32
        and review['actual_optimizer_calls_finished']==308,'OLD_REAL_N1_PILOT_AND_HELD_FULL_GATE_PRESERVED')
    account=C.load(plan['prepare_accounting_reference']);C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
        and account['query_returncode']==0 and any(str(r['job_id'])==str(prepared['job_id']) and r['state']=='COMPLETED'
        and r['exit_code']=='0:0' and r['alloc_cpus']==16 for r in account['parents']),'ACTUAL_OLD_PREPARE_C0')
    C.verify(account['raw_sacct_reference'],2<<20)
    legacy=C.load(plan['legacy_disabled_reference']);C.need(legacy['reviewer']=='root' and legacy['all_N1_generation_parents_terminal']is True
        and legacy['legacy_N1_generation_disabled']is True and legacy['all_existing_claims_preserved_no_retry']is True,'NO_CONCURRENT_OR_FUTURE_LEGACY_N1_DISPATCH')
    out=C.literal(plan['output_directory']);C.need(not out.exists(),'NEW_EXPORT_DIRECTORY');out.mkdir(parents=True)
    budget=R.Budget(plan,admission,out);budget.check();C.validate_shards(plan['shards'])
    C.need(plan['output_cap_bytes']<=16<<30 and plan['metadata_cap_bytes']==8<<30,'BOUNDED_SHARED_EXPORT')
    lock_path=C.REGISTRY.parent/'freeze.lock';lock_path.parent.mkdir(parents=True,exist_ok=True);fd=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);first=keys();start=time.monotonic()
        while time.monotonic()-start<30:budget.check();time.sleep(1)
        C.need(first==keys(),'LEGACY_CLAIM_KEYS_CHANGED_NO_NEW_ASSIGNMENTS')
        roster=C.verify(prepared['source_task_roster'],check=budget.check);rows=[];seen=set();consumed=[]
        with roster.open() as f:
            for raw in f:
                C.need(len(raw.encode())<=64<<10,'BOUNDED_ORIGINAL_ROSTER_ROW');row=json.loads(raw);key=row['task_key']
                C.need(key==C.task_key(row['molecule_id']) and key not in seen,'ORIGINAL_N1_KEY_AND_UNIQUE_ROSTER');seen.add(key)
                if key in first:consumed.append(key)
                else:
                    C.need(row['state']=='UNCONSUMED_NEW_ATTEMPT_NOT_AUTHORIZED_UNTIL_FINITE_ROOT_REVIEW','IMPORTED_OR_UNKNOWN_TASK_WITHOUT_CLAIM_HOLD')
                    rows.append(row)
        C.need(len(seen)==4631 and first<=seen,'ALL_CANONICAL_CLAIMS_REVERSE_JOIN_OR_HOLD')
        registry=sqlite3.connect(C.REGISTRY);registry.execute('CREATE TABLE IF NOT EXISTS assigned(k TEXT PRIMARY KEY,mid TEXT UNIQUE,shard TEXT,freeze_plan_sha TEXT)')
        registry.execute('PRAGMA max_page_count='+str((16<<20)//registry.execute('PRAGMA page_size').fetchone()[0]))
        prior={r[0] for r in registry.execute('SELECT k FROM assigned')};rows=[r for r in rows if r['task_key']not in prior]
        streams={};counts={};load={};members=[];C.need(len(plan['shards'])==2 and {s['cpus'] for s in plan['shards']}=={16,64},'TWO_ALPHA_SHARDS')
        for shard in plan['shards']:
            sid=shard['shard_id'];directory=out/sid;directory.mkdir();streams[sid]=((directory/'tasks.jsonl').open('xb'),directory)
            counts[sid]=0;load[sid]=0
        # IO worker16; numerical initialization/graph/embedding never called.
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn')) as pool:
            pending={};cursor=0
            while pending or cursor<len(rows):
                while cursor<len(rows) and len(pending)<16:
                    budget.check();row=rows[cursor];cursor+=1;pending[pool.submit(envelope,(row,prepared['source_population_authority']))]=row
                done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    row=pending.pop(future);value,reservation,n=future.result();budget.check();key=row['task_key']
                    shard=min(plan['shards'],key=lambda s:(load[s['shard_id']]/s['cpus'],s['shard_id']));sid=shard['shard_id']
                    C.need(not (C.MAIN_LEDGER/(key+'.json')).exists(),'LATE_ORIGINAL_CLAIM_PREVENTS_FOREIGN_ASSIGNMENT')
                    # Explicit assignment reservation, not a fake worker/start/job.
                    claim={'schema':'N1_FOREIGN_ASSIGNMENT_RESERVED_V1','task_key':key,'molecule_id':row['molecule_id'],
                        'seed':C.seed(row['molecule_id']),'original_task_reference':row['task_reference'],
                        'assignment_freeze_plan_reference':plan_ref,'actual_Main_export_job_id':str(admission['job_id']),
                        'owner_endpoint':shard['endpoint'],'shard_id':sid,'scientific_attempt_started':False,'automatic_retry':False}
                    C.need(len(C.canonical(claim))+1<=8<<10,'FINITE_CANONICAL_ASSIGNMENT_AUX_WITHIN64M_ADMIN')
                    claim_ref=C.save(C.MAIN_LEDGER/(key+'.json'),claim)
                    value['original_Main_assignment_claim_reference']=claim_ref;raw=C.canonical(value)+b'\n'
                    C.need(len(raw)<=64<<20,'COMPLETE_PORTABLE_TASK_ENVELOPE_CAP');S.charge_external(out,len(raw))
                    streams[sid][0].write(raw);counts[sid]+=1;load[sid]+=n*n
                    member={'task_key':key,'molecule_id':row['molecule_id'],'task_sha256':value['task_sha256'],'seed':C.seed(row['molecule_id']),
                        'reservation_bytes':reservation,'original_Main_assignment_claim_reference':claim_ref,'shard_id':sid,'endpoint_id':'alpha'}
                    C.need(reservation*shard['cpus']+2*C.ADMIN<=shard['output_cap_bytes'],'ALL_ACTIVE_ORIGINAL_INPUT_RESERVATIONS_FIT')
                    members.append(member);registry.execute('INSERT INTO assigned VALUES(?,?,?,?)',(key,row['molecule_id'],sid,plan_ref['sha256']));registry.commit()
        shards=[]
        for shard in plan['shards']:
            sid=shard['shard_id'];stream,directory=streams[sid];stream.flush();os.fsync(stream.fileno());stream.close()
            member_ref=budget.write(directory/'members.json',C.canonical([m for m in members if m['shard_id']==sid])+b'\n')
            chosen=[m for m in members if m['shard_id']==sid]
            shards.append({**shard,'molecules':counts[sid],'members_reference':member_ref,'tasks_reference':C.ref(directory/'tasks.jsonl',check=budget.check),
                'task_keys_sha256':C.value_sha(sorted(m['task_key'] for m in chosen))})
        registry.close();C.need(len(members)==len(rows),'EXACT_EXPORTED_REMAINDER_CONSERVATION')
        report={'schema':'N1_SOURCE_FINITE_REMAINING_ASSIGNMENTS_V1','status':'FROZEN_AWAITING_ROOT_EXACT_FINITE_SCIENCE_REVIEW',
            'source_prepared_reference':plan['prepared_reference'],'pilot_review_reference':plan['pilot_review_reference'],
            'legacy_disabled_reference':plan['legacy_disabled_reference'],'actual_export_job_id':str(admission['job_id']),
            'freeze_plan_reference':plan_ref,'shards':shards,'original_source_roster':4631,'existing_canonical_claims_before_export':len(first),
            'consumed_existing_keys':consumed,'prior_assigned_keys_excluded':len(prior),'remaining_frozen':len(members),
            'new_UFF_QM_calls':0,'source_proof':proof,'ordinary_Sprime_counts_changed':False,'common':False,'physical_ids_assigned':False,
            'source_N':1,'candidate_requested':10,'desired_real_UFF':2,'seed_domain':'sprime-ETKDGv3-v1-n1-pprime2:',
            'descriptive_comparable_allocated_core_seconds':45*len(members),'two_times_includes_export_and_both_native_parents':True,
            'raw_pkl_reencoded_as_numbers':False,'Main_claims_are_explicit_foreign_assignment_reservations_not_started_science':True}
        budget.write(out/'assignments.json',C.canonical(report)+b'\n')
    except BaseException as error:
        for stream,directory in locals().get('streams',{}).values():
            if not stream.closed:stream.flush();os.fsync(stream.fileno());stream.close()
        budget.write(out/'failure.json',C.canonical({'schema':'N1_ZERO_UFF_EXPORT_INCOMPLETE_V1','status':'INCOMPLETE_NO_NATIVE_RELEASE',
            'actual_export_job_id':str(admission['job_id']),'error':repr(error),'traceback':traceback.format_exc(),
            'new_UFF_QM_calls':0,'existing_and_new_assignment_claims_preserved_no_reset':True})+b'\n')
        raise
    finally:os.close(fd)
    return 0


if __name__=='__main__':raise SystemExit(main())
