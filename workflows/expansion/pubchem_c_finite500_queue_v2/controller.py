"""Root-invoked finite20h metadata controller for one immutable PubChem500 range.

Only old M.plan_one and v13 control functions perform preparation/submission.
Scientific bodies, chemistry, claims, workers, tolerances and old source bytes
are untouched. Unknown or failed attempts cannot be automatically retried.
"""
import argparse,copy,csv,io,json,os,time,traceback
from pathlib import Path
from types import SimpleNamespace
from secondary_cpu_queue_v1 import common as Q
from . import state as S

HERE=Q.ROOT/'code/pubchem_c_finite500_queue_v2'
FILES=('__init__.py','controller.py','state.py','test_state.py','README.md','review_schema.json')
CONTROL=Q.ROOT/'control/secondary_cpu_queue'
SCOPE7=CONTROL/'storage_scope_v7_pubchem_uniform_index_copy_v1.json'
FREEZE={'path':str(Q.ROOT/'control/pubchem_C_frozen_metadata_v1/freeze_receipt.json'),
 'bytes':9775,'sha256':'9bf78c8baaea5a8f75a5931221b8089755c698e3b6d514e5613b7b9010e124a5'}
DENIED=set()


def pin(path):
    path=Q.literal(path);Q.need(str(path) not in DENIED and path.suffix in {'.json','.py','.md','.txt','.sbatch'},'NAMED_SMALL_METADATA_OR_SOURCE_ONLY')
    return Q.ref(path)


def meta(r,schema=None):
    Q.normalized(r);Q.need(r['path'] not in DENIED and Path(r['path']).suffix=='.json','NO_SCIENTIFIC_BODY_IN_METADATA')
    value=Q.load_ref(r)
    if schema:Q.need(value['schema']==schema,'EXACT_METADATA_SCHEMA:'+schema)
    return value


def data_locator(r):
    Q.need(set(r)=={'path','bytes','sha256'} and type(r['bytes']) is int and r['bytes']>0
        and len(r['sha256'])==64 and all(c in '0123456789abcdef' for c in r['sha256']),'PRODUCER_DATA_LOCATOR_ONLY')
    Q.literal(r['path']);DENIED.add(r['path'])


def event(folder,status,**extra):
    # Each record is new and durable. No checkpoint/event is overwritten.
    r=Q.write_new(folder/('event_%020d.json'%time.time_ns()),{'schema':'PUBCHEM_C_FINITE500_EVENT_V1','status':status,
        'observed_at':Q.now(),'endpoint':Q.ENDPOINT,'uid':1264,'no_retry_cancel_or_signal':True,**extra})
    Q.event(status,finite_event_reference=r);return r


def actual_raw(reference,parent):
    Q.normalized(reference);Q.need(Path(reference['path']).suffix=='.txt' and reference['bytes']<=65536,'SMALL_ACTUAL_SACCT_TEXT')
    raw=Q.read_small(Q.verify(reference)).decode('utf-8','strict')
    rows=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r.get('JobIDRaw')==parent['JobIDRaw']]
    Q.need(len(rows)==1 and all(rows[0][k]==parent[k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition')),'ACTUAL_RAW_PARENT_FIELDS')


def fixture_evidence(root):
    f=meta(root['state_fixture_evidence_reference'],'ROOT_REVIEWED_ACTUAL_FINITE500_STATE_FIXTURES_V1')
    Q.need(f['status']=='PASS' and f['reviewer']=='root' and f['tests_run']==4 and f['scientific_body_reads']==0
        and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
        and f['source_references']==root['controller_source_references'] and f['actual_runtime']==root['state_fixture_expected_runtime'],
        'ACTUAL_CPU_FOUR_STATE_FIXTURES_REQUIRED_NOT_INVENTED')
    p=f['actual_parent'];runtime=f['actual_runtime'];Q.need(p['JobIDRaw']==runtime['job_id'] and p['UID']==str(runtime['uid'])
        and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['AllocCPUS']=='16' and runtime['cpus']==16
        and int(p['ElapsedRaw'])>=0 and f['allocated_core_seconds_observed']==16*int(p['ElapsedRaw']),'ACTUAL_FIXTURE_C0_ACCOUNTING')
    actual_raw(f['raw_sacct_reference'],p)  # Main fixtures retain their actual endpoint/UID; never called Alpha execution.


def context(path):
    reference=pin(path);root=meta(reference,'ROOT_APPROVED_PUBCHEM_C_FINITE500_QUEUE_RANGE_V1')
    Q.need(root['status']=='ROOT_APPROVED' and root['reviewer']=='root' and root['endpoint']==Q.ENDPOINT and root['uid']==1264
        and root['run_root']==str(Q.ROOT) and root['freeze_receipt_reference']==FREEZE,'ACTUAL_ROOT_ONE_RANGE_REVIEW')
    own=[pin(HERE/name) for name in FILES]
    Q.need(root['controller_source_references']==own and root['allowed_nodes']==list(S.NODES)
        and root['first_shard']==0 and root['last_shard']==499 and root['population_N']==S.N
        and type(root['max_nonterminal_C_parents']) is int and 2<=root['max_nonterminal_C_parents']<=6 and root['reserved_non_C_cpus']==16
        and root['maximum_foreground_seconds'] in (43200,72000) and root['poll_seconds']==30
        and root['controller_metadata_cap_bytes']==16<<20
        and root['wall_seconds']==28800 and root['output_cap_bytes']==8<<30
        and root['storage_scope_review_reference']['path']==str(SCOPE7),'EXACT500_ROOT_SLOT_CAP_DIAGNOSIS_RESERVE_AND_FINITE_DURATION')
    for key in ('delegate_exact_single_shard_metadata_template','automatic_retry_forbidden','cancel_or_signals_forbidden',
                'initial_two_actual_C0_and_complete_rows_required','scientific_quality_thresholds_unchanged'):
        Q.need(root[key] is True,'EXPLICIT_ROOT_RANGE_DECISION:'+key)
    Q.need(root['cost_overrun_action']=='REPORT_AND_CONTINUE' and root['pool_decontamination_or_filtered_dedup1M_release'] is False,'COST_AND_RELEASE_SCOPE_UNCHANGED')
    Q.need(len(root['initial_two_actual_closures'])==2 and [r['shard_index'] for r in root['initial_two_actual_closures']]==[0,1], 'ROOT_ACTUAL_INITIAL_TWO_NOT_FUTURE_PINS')
    for r in root['materializer_source_references']:Q.need(pin(r['path'])==r,'ACTUAL_FROZEN_MATERIALIZER_SOURCE')
    from pubchem_c_root_materializer_v1 import materialize as M
    expected=[pin(M.HERE/name) for name in M.FILES]
    Q.need(len(root['materializer_source_references'])==len(expected) and {Q.canonical(r) for r in root['materializer_source_references']}=={Q.canonical(r) for r in expected},'EXACT_FROZEN_SIX_MATERIALIZER_SOURCE_SET')
    f=meta(FREEZE,'PUBCHEM_C_METADATA_FREEZE_RECEIPT_V1');partition=meta(f['full_shard_manifest_reference'])
    S.check_partition(partition['shards']);budget=meta(f['profile_output_budget_reference'])
    Q.need(f['status']=='ROOT_REVIEWED_BUDGET_AND500_PARTITION_METADATA_CLOSED_NO_SUBMISSION' and f['shards']==500
        and partition['status']=='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST' and partition['pool_release_authorized'] is False
        and all(r['wall_seconds']==28800 and r['output_cap_bytes']==8<<30 for r in budget['reviewed_shards']), 'ACTUAL_FIXED_FREEZE_BUDGET_NOT_PROPOSAL')
    fr=meta(f['root_approval_reference']);ctx=M.context(fr)
    for r in (ctx['a']['inventory']['source_index'],ctx['a']['raw_reference']):data_locator(r)
    bp=ctx['b_plan'];template=root['single_shard_approval_template']
    Q.need(template['schema']=='ROOT_APPROVED_SINGLE_PUBCHEM_C_SHARD_PLAN_V1' and template['status']=='ROOT_APPROVED'
        and template['reviewer']=='root' and template['endpoint']==Q.ENDPOINT and template['uid']==1264
        and template['run_root']==str(Q.ROOT) and template['generator_source_references']==root['materializer_source_references']
        and template['single_shard_only_no_submission'] is True and template['freeze_receipt_reference']==FREEZE
        and template['wall_seconds']==28800 and template['output_cap_bytes']==8<<30 and template['python']==bp['python'],
        'ROOT_SUPPLIED_APPROVED_TEMPLATE_NOT_CONTROLLER_SELF_APPROVAL')
    Q.need(not any(k in template for k in ('shard_index','node','output_directory','startup_proof_path')),'ONLY_FIXED_RANGE_FIELDS_MAY_BE_FILLED')
    cat=meta(template['supplemental_source_catalog_reference'],'ROOT_APPROVED_PUBCHEM_C_SOURCE_CATALOG_V1')
    Q.need(cat['status']=='ROOT_APPROVED' and cat['reviewer']=='root','ACTUAL_PREAPPROVED_V13_SOURCE_CATALOG')
    pair=[r for r in cat['source_references'] if Path(r['path']).parent==Q.ROOT/'code/secondary_cpu_readonly_queue_v13']
    Q.need({Path(r['path']).name for r in pair}=={'adapters.py','controller.py'},'EXACT_FROZEN_V13_PAIR')
    for r in pair:Q.need(pin(r['path'])==r,'V13_BYTES_UNCHANGED')
    from secondary_cpu_readonly_queue_v13 import controller as V
    Q.need(bp['resource_authority_reference']==root['resource_authority_reference'],'SAME_ACTUAL_AUTHORITY')
    Q.authority(root['resource_authority_reference']['path']);Q.source_review(root['base_controller_review_reference']['path'])
    for r in (root['resource_authority_reference'],root['base_controller_review_reference'],root['storage_scope_review_reference']):Q.need(pin(r['path'])==r,'CURRENT_ACTUAL_ROOT_ADMISSION_METADATA')
    fixture_evidence(root)
    return root,reference,f,partition,bp,M,V


def terminal(folder,request,submission,account_ref,root,grant,frozen,partition):
    account=meta(account_ref,'SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1');p=account['actual_parent'];jid=submission['job_id']
    Q.need(account['uid']==1264 and account['endpoint']==Q.ENDPOINT and account['query_returncode']==0
        and p['JobIDRaw']==jid and p['UID']=='1264' and p['State'] in S.TERMINAL,'ACTUAL_OWN_TERMINAL_ACCOUNTING')
    actual_raw(account['raw_sacct_reference'],p)
    plan=meta(request['adapter']['input_reference']);i=plan['shard_index'];expected=partition['shards'][i]
    base={'shard_index':i,'job_id':jid,'actual_state':p['State'],'actual_exit':p['ExitCode'],
        'queue_control_directory':str(folder),'queue_request_reference':pin(folder/'request.json'),
        'submission_reference':pin(folder/'submission.json'),'accounting_reference':account_ref,
        'actual_allocated_core_seconds':account['allocated_core_seconds_observed'],'root_range_review_reference':grant,
        'status':'FAILED','expected_rows':expected['last_ordinal']-expected['first_ordinal']+1}
    Q.need(account['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*int(p['AllocCPUS']),'ACTUAL_COST_INCLUDING_FAILED_AND_STARTUP_PARENTS')
    if p['State']!='COMPLETED' or p['ExitCode']!='0:0':return base
    Q.need(p['AllocCPUS']=='16' and p['NodeList']==plan['node'] and plan['metadata_freeze_receipt_reference']==FREEZE
        and plan['full_shard_manifest_reference']==frozen['full_shard_manifest_reference']
        and all(plan[k]==expected[k] for k in ('shard_index','first_part','last_part','first_ordinal','last_ordinal')),'EXACT_TERMINAL_SHARD_PLAN')
    receipt_ref=pin(Path(plan['output_directory'])/'receipt.json');receipt=meta(receipt_ref,'ALPHA_PUBCHEM_ORDINAL_FEATURE_SHARD_RECEIPT_V1')
    proof_ref=receipt['startup_proof_reference'];proof=meta(proof_ref,'SECONDARY_PUBCHEM_ORDINAL_FEATURE_SHARD_STARTUP_V1')
    result=receipt['result'];counts=result['counts'];n=base['expected_rows']
    Q.need(receipt['status']=='ALPHA_ORDINAL_SHARD_ROWS_CLOSED_NO_POOL_RELEASE' and receipt['job_id']==jid and receipt['mode']=='full_shard'
        and receipt['endpoint']==Q.ENDPOINT and receipt['uid']==1264 and receipt['node']==plan['node']==proof['node']
        and proof['endpoint']==Q.ENDPOINT and proof['uid']==1264 and proof['request']['cpus']==16
        and proof['request']['kind']=='analysis' and proof['request']['pilot'] is False and proof['request']['wall_seconds']==28800
        and receipt['plan_reference']==request['adapter']['input_reference']==proof['plan_reference'] and str(proof['job_id'])==jid
        and receipt['scope_parameters']==plan['scope_parameters'] and receipt['source_references']==plan['source_references']
        and receipt['source_row_conservation'] is True and receipt['unread_rows']==0 and receipt['expected_rows']==n
        and receipt['first_ordinal']==expected['first_ordinal'] and receipt['last_ordinal']==expected['last_ordinal']
        and result['dispatched_rows']==result['completed_rows']==result['actual_input_rows_dispatched']==n
        and result['last_dispatched_ordinal']==result['last_completed_ordinal']==expected['last_ordinal']
        and set(counts)=={'accepted','chemReject','technicalUnresolved'} and all(type(v) is int and v>=0 for v in counts.values())
        and sum(counts.values())==n and result['journal_precedes_parquet'] is True
        and receipt['technical_unknown_is_chemical_exclusion'] is result['technical_unknown_is_chemical_exclusion'] is False
        and receipt['full_source_pool_release_authorized'] is False and receipt['guide_filtered_dedup_1M_reference_completed'] is False,
        'COMPLETE_CPU_PRODUCER_ROW_CLOSURE_NOT_EFFECTIVE_MOLECULE_OR_POOL_ACCEPTANCE')
    f=receipt['fixtures'];Q.need(f['tests_run']==5 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_FIVE_OLD_FIXTURES')
    for r in frozen['same_scientific_core_source_references']:Q.need(r in receipt['source_references'] and pin(r['path'])==r,'SAME_ACTUAL_B19_SCIENTIFIC_SOURCE_BYTES')
    claim=meta(receipt['claim_reference']);Q.need(claim['manifest_reference']==frozen['full_shard_manifest_reference'] and claim['job_id']==jid
        and claim['plan_reference']==receipt['plan_reference'] and claim['range']==expected and claim['uid']==1264 and claim['node']==plan['node'],'EXACT_SINGLE_RUNTIME_ORDINAL_CLAIM')
    for r in (result['full_dispatch_and_result_journal'],result['features']):data_locator(r)
    return dict(base,status='CLOSED',counts=counts,receipt_reference=receipt_ref,startup_proof_reference=proof_ref,
        data_output_references=[result['full_dispatch_and_result_journal'],result['features']],
        closure_basis='ACTUAL_CPU_PRODUCER_DURABLE_ROW_COUNTS_AND_PARENT_C0_NOT_NEW_CONTROLLER_BODY_REHASH',
        scientific_or_pool_release=False)


def registry(state_dir,root,grant,frozen,partition,V):
    observed={};folders={}
    for path in sorted((CONTROL/'claims').glob('*.json')):
        claim=Q.load(path);rr=claim['queue_request_reference'];request=meta(rr)
        if request.get('scope_key')!='pubchem_raw_feature_shard_alpha_v1':continue
        plan=meta(request['adapter']['input_reference']);Q.need(plan['full_shard_manifest_reference']==frozen['full_shard_manifest_reference'],'OTHER_C_MANIFEST_REQUIRES_ROOT_HOLD')
        i=plan['shard_index'];Q.need(type(i) is int and 0<=i<500 and i not in observed,'DUPLICATE_C_SHARD_REGISTRATION_REQUIRES_ROOT_HOLD')
        folder=Path(rr['path']).parent;folders[i]=(folder,request);cache=state_dir/('terminal_%04d.json'%i)
        if cache.exists():
            row=Q.load(cache);Q.need(row['queue_request_reference']==rr and row['root_range_review_reference']==grant,'SAME_TERMINAL_PARENT_AND_RANGE_REVIEW')
            for key in ('queue_request_reference','submission_reference','accounting_reference'):Q.verify(row[key])
            if row['status']=='CLOSED':Q.verify(row['receipt_reference']);Q.verify(row['startup_proof_reference'])
            observed[i]=row;continue
        if not (folder/'submission.json').exists():observed[i]={'status':'UNKNOWN','queue_control_directory':str(folder)};continue
        sub=Q.load(folder/'submission.json');jid=sub.get('job_id')
        if sub.get('sbatch_returncode')!=0 or not isinstance(jid,str) or not jid.isdecimal():
            observed[i]={'status':'UNKNOWN','queue_control_directory':str(folder),'actual_cost':'PENDING_UNRESOLVED_SUBMISSION'};continue
        q=Q.query(['sacct','-j',jid,'--format=JobIDRaw,UID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition','-P'])
        rows=[r for r in csv.DictReader(io.StringIO(q['stdout']),delimiter='|') if r.get('JobIDRaw')==jid]
        Q.need(len(rows)==1 and rows[0]['UID']=='1264','ACTUAL_REGISTERED_C_PARENT_VISIBILITY_REQUIRED')
        current=Q.state(rows[0]['State'])
        if current not in S.TERMINAL:observed[i]={'status':current,'job_id':jid,'queue_control_directory':str(folder)};continue
        if i in (0,1):account_ref=root['initial_two_actual_closures'][i]['accounting_reference']
        else:
            before=set(folder.glob('accounting_*.json'));V.account(folder);after=set(folder.glob('accounting_*.json'))-before
            Q.need(len(after)==1,'ONE_ACTUAL_TERMINAL_ACCOUNTING_PUBLICATION');account_ref=pin(after.pop())
        row=terminal(folder,request,sub,account_ref,root,grant,frozen,partition);Q.write_new(cache,row);observed[i]=row
    return observed,folders


def cpu_snapshot():
    return {node:Q.free_cpus({'node':node}) for node in S.NODES}


def run(review_path,state_dir):
    root,grant,frozen,partition,bp,M,V=context(review_path);state_dir=Q.literal(state_dir)
    Q.need(CONTROL in state_dir.parents and state_dir.name=='pubchem_C_finite500_v1','EXACT_NEW_OR_RESUMED_FINITE_STATE_LEAF')
    state_dir.mkdir(parents=True,mode=0o700,exist_ok=True);fd=V.lock(CONTROL/'pubchem_C_finite500_global.lock')
    try:
        binding=state_dir/'binding.json'
        if binding.exists():Q.need(Q.load(binding)['root_range_review_reference']==grant,'RESUME_SAME_ACTUAL_ROOT_REVIEW_ONLY')
        else:Q.write_new(binding,{'root_range_review_reference':grant,'freeze_receipt_reference':FREEZE,'created_at':Q.now()})
        started=time.monotonic();last=None;maximum=root['maximum_foreground_seconds']
        with Q.Heartbeat():
            while time.monotonic()-started<maximum:
                Q.need(sum(p.stat().st_size for p in state_dir.glob('*.json'))<(16<<20)-65536,'FINITE_CONTROLLER16MIB_METADATA_RESERVE_HOLD')
                observed,folders=registry(state_dir,root,grant,frozen,partition,V)
                initial={i:observed[i] for i in (0,1) if i in observed}
                # Independently pinned initial evidence is mandatory, not future/runtime guessed input.
                for i,row in initial.items():
                    expected=root['initial_two_actual_closures'][i]
                    Q.need(expected['shard_index']==i and row.get('receipt_reference')==expected['receipt_reference']
                        and row.get('job_id')==expected['job_id'] and row.get('accounting_reference')==expected['accounting_reference'], 'ROOT_REVIEWED_ACTUAL_INITIAL_TWO_COMPLETE_EVIDENCE')
                attempted={int(p.stem.split('_')[-1]) for p in state_dir.glob('attempt_*.json')}
                decision,index=S.next_shard(observed,attempted,initial,root['max_nonterminal_C_parents'])
                if decision!=last:event(state_dir,decision,known_registered_C=len(observed));last=decision
                if decision.startswith('HOLD') or decision.startswith('ALL500'):
                    closed=[v for v in observed.values() if v['status']=='CLOSED'];counts={k:sum(v['counts'][k] for v in closed) for k in ('accepted','chemReject','technicalUnresolved')}
                    if decision.startswith('ALL500'):Q.need(sum(counts.values())==S.N,'EXACT_TOTAL124857440_PHYSICAL_ROWS_NOT_POOL_RELEASE')
                    event(state_dir,decision,closed_shards=len(closed),closed_physical_rows=sum(counts.values()),counts=counts,
                        known_terminal_allocated_core_seconds=sum(v.get('actual_allocated_core_seconds',0) for v in observed.values()),
                        nonterminal_or_unknown_costs_pending=[i for i,v in observed.items() if v['status']!='CLOSED' and 'actual_allocated_core_seconds' not in v],
                        terminal_records=[pin(p) for p in sorted(state_dir.glob('terminal_*.json'))],
                        full_population_released=False,new_controller_scientific_body_reads=0)
                    return 0 if decision.startswith('ALL500') else 3
                cpus=cpu_snapshot();free={k:v['free_cpus'] for k,v in cpus.items()};node=S.choose_node(free)
                # Resume only existing known held/gate parents; ready scientific jobs are never revalidated as new output leaves.
                for i,(folder,request) in folders.items():
                    if observed[i]['status'] in S.TERMINAL or observed[i]['status']=='CLOSED' or Path(request['ready_path']).exists():continue
                    free_now={k:v['free_cpus'] for k,v in cpu_snapshot().items()};assigned=request['node'];after=dict(free_now);after[assigned]-=16
                    if observed[i]['status']!='RUNNING' and (free_now[assigned]<16 or max(after.values())<16):continue
                    lockfd=V.lock(CONTROL/'controller.lock')
                    try:V.observe(folder,folder/'request.json',request,Q.load(folder/'submission.json'),30)
                    finally:os.close(lockfd)
                if decision=='ELIGIBLE' and node is not None:
                    lockfd=V.lock(CONTROL/'controller.lock')
                    try:
                        fresh,_=registry(state_dir,root,grant,frozen,partition,V)
                        decision2,index2=S.next_shard(fresh,attempted,{i:fresh[i] for i in (0,1) if i in fresh},root['max_nonterminal_C_parents'])
                        latest_cpus=cpu_snapshot();free={k:v['free_cpus'] for k,v in latest_cpus.items()};node=S.choose_node(free)
                        if decision2!='ELIGIBLE' or index2!=index or node is None:continue
                        names={'plan':Q.ROOT/'control/readonly_specs'/('pubchem_C_shard_%04d_v1'%index),
                            'queue':CONTROL/('pubchem_C_shard_%04d_v1'%index),
                            'approval':CONTROL/('pubchem_C_shard_%04d_finite_root_approval_v1.json'%index),
                            'output':Q.ROOT/'artifacts/pubchem_C_alpha_v1'/('shard-%04d'%index),
                            'proof':Q.ROOT/'control/secondary_startup'/('pubchem_C_shard_%04d_v1.json'%index)}
                        Q.need(all(not p.exists() for p in names.values()),'ANY_EXISTING_SHARD_PATH_REQUIRES_ROOT_NO_RETRY')
                        Q.write_new(state_dir/('attempt_%04d.json'%index),{'shard_index':index,'root_range_review_reference':grant,
                            'node':node,'cpu_observations':latest_cpus,'status':'INTENT_BEFORE_ANY_PLAN_OR_SUBMISSION','no_automatic_retry':True})
                        approval=copy.deepcopy(root['single_shard_approval_template'])
                        approval.update(shard_index=index,node=node,output_directory=str(names['output']),startup_proof_path=str(names['proof']),
                            actual_root_range_review_reference=grant,derived_from_explicit_single_range_review_not_new_independent_approval=True)
                        Q.write_new(names['approval'],approval);M.plan_one(names['approval'],names['plan'])
                        args=SimpleNamespace(reviewer='root',controller_review=Path(root['base_controller_review_reference']['path']),
                            authority=Path(root['resource_authority_reference']['path']),storage_review=SCOPE7,producer='readonly',deployment=None,
                            input=names['plan']/'plan.json',node=node,wall_seconds=28800,job_name='dv1_pubchem_c_%04d_alpha_v1'%index,output=names['queue'])
                        folder,rp,request=V.prepare(args);submission=V.submit_held(folder,rp,request)
                        event(state_dir,'ACTUAL_SINGLE_HELD_SUBMISSION_NO_RETRY',shard_index=index,submission_reference=pin(folder/'submission.json'))
                        free_now={k:v['free_cpus'] for k,v in cpu_snapshot().items()};after=dict(free_now);after[node]-=16
                        if free_now[node]>=16 and max(after.values())>=16:V.observe(folder,rp,request,submission,30)
                    finally:os.close(lockfd)
                time.sleep(min(30,max(0,maximum-(time.monotonic()-started))))
            event(state_dir,'FINITE_ROOT_DURATION_DEADLINE_RESUME_SAME_STATE_NO_CANCEL',maximum_foreground_seconds=maximum,all_live_jobs_retained=True,actual_cost_ledger_not_final=True);return 2
    except Exception as exc:
        event(state_dir,'HOLD_EXCEPTION_NO_RETRY_NO_SIGNALS',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc(),
            all_actual_parents_and_outputs_retained=True,actual_cost_reconciliation_pending=True);raise
    finally:os.close(fd)


def main():
    Q.login();Q.need(Path(__file__).absolute()==HERE/'controller.py','EXACT_DEPLOYED_FINITE_CONTROLLER_PRIMARY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root-range-review',type=Path,required=True);p.add_argument('--state-directory',type=Path,required=True)
    args=p.parse_args();return run(args.root_range_review,args.state_directory)


if __name__=='__main__':raise SystemExit(main())
