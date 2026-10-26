"""Finite16-worker PM7 cache32 and old256 PM7 projection comparison."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,multiprocessing as mp,pathlib,sys,time
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as C,io as I,core
OPTIONS=('plan','prepared','prepare-accounting','root-preflight','quota-reuse-review','output')


def golden_compare(task,packet):
    if task['golden_packet_reference'] is None:return {'status':'NOT_A_GOLDEN_MEMBER'}
    old=I.read_packet(task['golden_packet_reference'])
    C.need(old['status']=='D7_MOLECULE_PROFILE_COMPLETE' and old['molecule_id']==packet['molecule_id'],'REAL_SAME_MOLECULE_GOLDEN_PACKET')
    C.need(packet['status'].startswith('PM7_GEOMETRY_CACHE_COMPLETE'),'GOLDEN_GEOMETRY_CACHE_NOT_COMPLETE')
    for name in ('pm7_count','pm7_unique','pm7_duplicate_conformer_fraction','heavy_atoms','rotatable_bonds','rings'):C.need(packet[name]==old[name],'GOLDEN_PM7_FIELD_CHANGED:'+name)
    hashes={r['conformer_id']:r['geometry_sha256'] for r in packet['pm7']}
    C.need(hashes==old['geometry_hashes']['pm7'] and packet['orders']['fixed_random']==old['orders']['pm7']['fixed_random']
        and packet['unique_representatives']==old['unique_representatives']['pm7'],'GOLDEN_NATIVE_IDS_FLOAT64_SHA_RANDOM_AND_REPRESENTATIVES_CHANGED')
    energy='NOT_ASSESSED_CANONICAL_HOF_PENDING'
    if packet['hof_mode']=='CANONICAL_VERIFIED' and packet['hof_range_complete']:
        C.need(old['hof_range_complete'] and packet['hof_by_record']==old['hof_by_record']
            and packet['hof_range_kcal_mol']==old['hof_range_kcal_mol']
            and packet['orders']['energy']==old['orders']['pm7']['energy'] and packet['orders']['diversity']==old['orders']['pm7']['diversity'],
            'GOLDEN_CANONICAL_HOF_OR_ENERGY_DIVERSITY_CHANGED')
        energy='ACTUAL_CANONICAL_HOF_AND_TWO_ORDERS_EQUAL'
    return {'status':'ACTUAL_GOLDEN_PM7_GEOMETRY_RANDOM_AND_UNIQUE_EQUAL','energy_comparison':energy,
        'golden_reference':task['golden_packet_reference'],'anchor_signature_not_used_as_new_stereo_authority':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    args=p.parse_args();proof,session=I.admit(__file__,args,OPTIONS,'run32');out=I.new_output(args.output)
    for name in ('starts','molecules','finished','record_events'):(out/name).mkdir()
    budget=I.budget(proof,session,out);C.need(budget.observe() is None,'FRESH_SHARED_ACCOUNT_RESERVATION_BEFORE_BODY');budget.start_monitor()
    try:
        fixtures_ref=I.fixtures(out);plan_ref=I.request_ref(args.root_preflight,args.plan);plan=I.plan(plan_ref,proof)
        prepared_ref=I.request_ref(args.root_preflight,args.prepared);prepared=I.read(prepared_ref)
        C.need(prepared['schema']=='PM7_CACHE32_PREPARED_V1' and prepared['status']=='ACTUAL32_FROZEN_NO_GEOMETRY_COMPUTED'
            and prepared['plan_reference']==plan_ref and len(prepared['tasks'])==32,'ACTUAL_SAME_PLAN32_PREPARATION_REQUIRED')
        account_ref=I.request_ref(args.root_preflight,args.prepare_accounting);account=I.read(account_ref)
        I.authorized(proof,[account['raw_sacct_reference']]);parents=I.F.accounting(account_ref,[prepared['job_id']]);parent=parents[str(prepared['job_id'])]
        C.need(account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and parent['state']=='COMPLETED'
            and parent['exit_code']=='0:0' and int(parent['alloc_cpus'])==16,'REAL_PREPARE_CPU16_C0_ACCOUNTING')
        I.authorized(proof,[prepared['source_authority_reference'],*[r['task_reference'] for r in prepared['tasks']],
            *[r['reference'] for r in prepared['golden_packet_references']]])
        authority=I.read(prepared['source_authority_reference'])
        C.need(authority['schema']=='PM7_PRECOMMON_CACHE32_SOURCE_AUTHORITY_V1' and authority['plan_reference']==plan_ref
            and authority['full_execution_authorized'] is False and authority['common'] is False,'NO_FULL_OR_COMMON_RELEASE')
        tasks={};references={}
        for row in prepared['tasks']:
            reference=row['task_reference'];path=pathlib.Path(reference['path'])
            C.need(path.parent==args.prepared.parent/'tasks','ONLY_EXACT_PREPARED_TASK_LEAVES')
            task=I.read(reference);mid=task['meta']['molecule_id']
            C.need(task['schema']=='PM7_INDEPENDENT_CACHE32_TASK_V1' and mid==row['molecule_id'] and task['cache_key']==row['cache_key']
                and task['source_population_authority']==prepared['source_authority_reference'] and mid not in tasks
                and task['hof_mode']==plan['hof_mode'] and task['meta']['records']==len(task['records'])
                and task['software_bound']==C.software_bound(task['meta']['records'],task['meta']['maximum_total_atoms']),
                'FROZEN_EXACT32_TASKS_AND_ACTUAL_SOURCE_DIMENSION_BOUNDS')
            tasks[mid]=task;references[mid]=reference
        C.need(set(tasks)==set(authority['selected_molecule_ids']) and len(tasks)==32
            and sum(t['golden_packet_reference'] is not None for t in tasks.values())==16,'EXACT32_AND_GOLDEN16_NO_REPLACEMENT')
        records=[];errors=[];active={};queue=list(sorted(tasks));next_index=0;started=time.monotonic()
        try:
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=core.worker_init,initargs=(session,)) as pool:
                while active or next_index<len(queue):
                    budget.observe(list(pool._processes.values()))
                    while budget.stop is None and next_index<len(queue) and len(active)<16:
                        mid=queue[next_index];task=tasks[mid]
                        # The reserve is a byte/working-set upper bound from actual
                        # source N/atom metadata, never a scientific count or forecast.
                        def reserved(item):
                            return item['software_bound']['packet_reserve_bytes'] if item['software_bound']['status']=='WITHIN_SOFTWARE_BOUND' else 4*C.TASK_CAP
                        reserve=sum(reserved(tasks[m]) for m in active.values())+reserved(task)
                        if I.R.disk_bytes(out)+2*reserve+(64<<20)>C.CAP:budget.stop='CACHE_OUTPUT_RESERVATION_STOP_NEW_TASKS';break
                        if budget.observe(list(pool._processes.values())) is not None:break
                        I.json_new(out/('dispatch_'+task['cache_key']+'.json'),{'molecule_id':mid,'task_reference':references[mid],
                            'state':'DURABLE_POOL_SUBMIT_INTENT_WORKER_NOT_YET_OBSERVED','actual_worker_start_required':True,'new_scientific_generation':False},out)
                        next_index+=1 # durable intent exists; a submit exception is UNKNOWN, never proven unstarted
                        future=pool.submit(core.one,(task,references[mid]));active[future]=mid
                    if not active:break
                    done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        mid=active.pop(future)
                        record=None
                        try:
                            record=future.result();packet=I.read_packet(record['packet_reference']);worker=I.read(record['worker_start_reference'])
                            finished=I.read(record['finished_reference'])
                            C.need(packet['molecule_id']==mid and packet['task_reference']==references[mid]
                                and packet['runtime']==record['runtime'] and packet['runtime']['job_id']==str(proof['job_id'])
                                and packet['runtime']['uid']==1278 and packet['runtime']['node']=='compute-0-13'
                                and worker['runtime']==packet['runtime'] and worker['task_reference']==references[mid]
                                and worker['cache_key']==tasks[mid]['cache_key'] and finished['packet_reference']==record['packet_reference']
                                and finished['worker_start_reference']==record['worker_start_reference'],'ACTUAL_WORKER_PACKET_SOURCE_AND_RUNTIME_IDENTITY')
                            record['golden_comparison']=golden_compare(tasks[mid],packet);records.append(record)
                        except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc)[:16000],
                            'durable_record':record,'expected_packet_path':str(out/'molecules'/(tasks[mid]['cache_key']+'.json.gz')),
                            'existing_start_packet_finished_preserved':True})
        except BaseException as exc:
            errors.append({'phase':'pool_or_parent','error':repr(exc)[:16000],'all_durable_starts_events_packets_preserved':True})
            budget.stop=budget.stop or 'UNKNOWN_POOL_OR_PARENT_NO_FABRICATED_RETURN'
        statuses=collections.Counter(r['status'] for r in records);goldens=[r['golden_comparison'] for r in records if r['golden_comparison']['status']!='NOT_A_GOLDEN_MEMBER']
        geometry_complete=sum(r['status'].startswith('PM7_GEOMETRY_CACHE_COMPLETE') for r in records)
        budget.observe();closed=len(records)==geometry_complete==32 and len(goldens)==16 and not(errors or budget.stop)
        report={'schema':'PM7_INDEPENDENT_CACHE32_RECEIPT_V1','status':'ACTUAL32_PM7_GEOMETRY_AND_GOLDEN16_CLOSED_REQUIRES_ROOT_REVIEW' if closed else 'PM7_CACHE32_PENDING_OR_UNKNOWN_NO_SILENT_DROP',
            'job_id':str(proof['job_id']),'plan_reference':plan_ref,'prepared_reference':prepared_ref,'prepare_accounting_reference':account_ref,
            'fixtures_reference':fixtures_ref,'startup_proof_reference':session['proof_reference'],'configured_workers':16,
            'actual_worker_pids':sorted({r['runtime']['pid'] for r in records}),'worker_task_counts':dict(collections.Counter(str(r['runtime']['pid']) for r in records)),
            'expected':32,'geometry_complete':geometry_complete,'completed_packets':len(records),'golden_geometry_equal_count':len(goldens),
            'golden_energy_comparison_counts':dict(collections.Counter(r['energy_comparison'] for r in goldens)),
            'packet_status_counts':dict(statuses),'packets':records,'errors':errors,'unstarted_molecule_ids':queue[next_index:],
            'dispatched_without_validated_return_ids':sorted(set(queue[:next_index])-{r['molecule_id'] for r in records}),
            'elapsed_seconds':time.monotonic()-started,'budget':budget.report(),'actual_parent_terminal_cost':None,
            'actual_parent_accounting_append_required':True,'new_UFF_calls':0,'new_QM_calls':0,
            'common':False,'full_cache_release':False,'physical_int64_or_order_manifest_release':False,
            'Sprime_and_cross_RMSD_and_final_Common_D7':'NOT_COMPUTED_BY_PM7_ONLY_STAGE'}
        I.json_new(out/'receipt.json',report,out);print({'status':report['status'],'geometry_complete':geometry_complete,'goldens':len(goldens)});return 0 if closed else 3
    finally:budget.close_monitor();I.json_new(out/'resource_observations.json',budget.report(),out)


if __name__=='__main__':raise SystemExit(main())
