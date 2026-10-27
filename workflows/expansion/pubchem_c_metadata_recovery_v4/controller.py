"""Finite metadata-only52..499 controller; immutable adoption and all-parent costs."""
import argparse,copy,csv,fcntl,io,json,os,socket,stat,time,traceback
from pathlib import Path
from types import SimpleNamespace
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_continuation_alpha_v3 import contracts as A
from secondary_pubchem_screening_alpha_v1 import contracts as C
from pubchem_c_finite500_queue_v2 import controller as LEGACY
from secondary_cpu_readonly_pubchem_cont_v1 import controller as V
from . import state as S
HERE=Q.ROOT/'code/pubchem_c_metadata_recovery_v4';CONTROL=Q.ROOT/'control/secondary_cpu_queue';SCOPE7=C.STORAGE_SCOPE
OLD_KEY='pubchem_raw_feature_shard_alpha_v1';REPAIR_KEY='pubchem_c_resource_phase_shard_alpha_v2'
DENIED=set();CAP=16<<20;RESERVE=65536


def pin(path):
    path=Q.literal(path);Q.need(str(path) not in DENIED and path.suffix in ('.json','.py','.md','.txt','.sbatch')
        and path.stat().st_size<=2<<20,'NAMED_SMALL_METADATA_OR_CODE_ONLY_NOT_SCIENTIFIC_BODY');return Q.ref(path)


def meta(reference,schema=None):
    Q.need(reference['path'] not in DENIED and Path(reference['path']).suffix=='.json','SCIENTIFIC_DATA_NEVER_METADATA')
    Q.need(pin(reference['path'])==reference,'ACTUAL_SMALL_METADATA_PIN');value=Q.load_ref(reference)
    if schema:Q.need(value['schema']==schema,'EXACT_METADATA_SCHEMA:'+schema)
    return value


def data_locator(value):
    from .recovery import register_data_locator
    register_data_locator(value,DENIED)


def durable(path,value,state_dir):
    raw=Q.canonical(value)+b'\n';used=sum(p.stat().st_size for p in state_dir.rglob('*') if p.is_file())
    Q.need(state_dir in Path(path).parents and used+len(raw)+RESERVE<CAP,'FINITE16MIB_METADATA_STOP_NO_DELETE_OR_TRUNCATE')
    r=Q.write_new(path,value);fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return r


def event(state_dir,status,**extra):
    return durable(state_dir/('event_%020d.json'%time.time_ns()),{'schema':'PUBCHEM_CONTINUATION_EVENT_V3','status':status,
        'observed_at':Q.now(),'endpoint':Q.ENDPOINT,'uid':1264,'no_retry_renewal_cancel_or_signal':True,**extra},state_dir)


def available_controller_lock():
    path=Q.literal(CONTROL/'controller.lock');fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        s=os.fstat(fd);Q.need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_nlink==1,'OWN_REGULAR_METADATA_COORDINATION_LOCK')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:os.close(fd);return None
        return fd
    except BaseException:os.close(fd);raise


def account_row(reference,jid):
    value=meta(reference,'SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1');p=value['actual_parent'];LEGACY.actual_raw(value['raw_sacct_reference'],p)
    Q.need(value['endpoint']==Q.ENDPOINT and value['uid']==1264 and value['query_returncode']==0 and p['JobIDRaw']==jid
        and p['UID']=='1264' and p['State'] in S.TERMINAL and p['AllocCPUS']=='16' and p['NodeList'] in Q.NODES
        and p['Partition']=='cpu' and value['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,'ALL_REAL_TERMINAL_PARENT_COSTS')
    return value,p


def close_new(folder,request,submission,account_ref,root,grant,partition):
    jid=submission['job_id'];account,p=account_row(account_ref,jid);plan_ref=request['adapter']['input_reference'];plan=meta(plan_ref);i=plan['shard_index']
    Q.need(52<=i<=499 and request['scope_key']==A.KEY and plan['continuation_range_review_reference']==grant
        and request['adapter']['producer_plan_reference']==plan_ref,'ONLY_THIS_REGISTERED_NEW_RANGE_PARENT')
    expected=partition['shards'][i];Q.need(all(plan[k]==expected[k] for k in ('shard_index','first_part','last_part','first_ordinal','last_ordinal')),'ORIGINAL_WHOLE_SHARD_BOUNDS')
    base={'shard_index':i,'job_id':jid,'status':'FAILED','actual_state':p['State'],'actual_exit':p['ExitCode'],
        'expected_rows':expected['last_ordinal']-expected['first_ordinal']+1,'actual_allocated_core_seconds':account['allocated_core_seconds_observed'],
        'accounting_reference':account_ref,'queue_request_reference':pin(folder/'request.json'),'submission_reference':pin(folder/'submission.json'),
        'queue_control_directory':str(folder),'root_range_review_reference':grant}
    if p['State']!='COMPLETED' or p['ExitCode']!='0:0':return base
    receipt_ref=pin(Path(plan['output_directory'])/'receipt.json');receipt=meta(receipt_ref,'ALPHA_PUBCHEM_ORDINAL_FEATURE_SHARD_RECEIPT_V1')
    actual,proof=A.proof_chain(receipt,plan_ref,A.PROOF,A.KEY);A.validate(actual);result=receipt['result'];counts=result['counts'];n=base['expected_rows']
    Q.need(receipt['status']=='ALPHA_ORDINAL_SHARD_ROWS_CLOSED_NO_POOL_RELEASE' and receipt['resource_phase']=='CONTINUATION52_499'
        and receipt['source_references']==plan['source_references'] and receipt['scope_parameters']==plan['scope_parameters']
        and receipt['source_row_conservation'] is True and receipt['unread_rows']==0 and receipt['expected_rows']==n
        and result['completed_rows']==result['dispatched_rows']==result['actual_input_rows_dispatched']==n
        and result['last_dispatched_ordinal']==result['last_completed_ordinal']==expected['last_ordinal']
        and set(counts)=={'accepted','chemReject','technicalUnresolved'} and all(type(v) is int and v>=0 for v in counts.values())
        and sum(counts.values())==n and result['journal_precedes_parquet'] is True
        and receipt['technical_unknown_is_chemical_exclusion'] is result['technical_unknown_is_chemical_exclusion'] is False
        and receipt['full_source_pool_release_authorized'] is False and receipt['guide_filtered_dedup_1M_reference_completed'] is False,
        'REAL_COMPLETE_ROW_CLOSURE_NOT_POOL_OR_CHEMICAL_SUCCESS')
    t=receipt['resource_fixtures'];Q.need(A.pure_counts(receipt['fixtures'],5) and A.pure_counts(t,6)
        and A.pure_counts(t['v2_resource_fixtures'],3) and A.pure_counts(t['v3_continuation_fixtures'],3)
        and receipt['source_inverse_proof']['status']=='EXACT_CONTINUATION_MAIN_GUARD_BYTES_AST_INVERSE','ACTUAL_ALL11_AND_NEW_MAIN_SOURCE_INVERSE')
    claim=meta(receipt['claim_reference']);Q.need(claim['manifest_reference']==root['full_shard_manifest_reference'] and claim['range']==expected
        and claim['job_id']==jid and claim['plan_reference']==plan_ref and claim['uid']==1264 and claim['node']==p['NodeList']==plan['node'],
        'REAL_UNCHANGED_ORIGINAL_ORDINAL_CLAIM')
    for r in (result['full_dispatch_and_result_journal'],result['features']):data_locator(r)
    return dict(base,status='CLOSED',counts=counts,receipt_reference=receipt_ref,startup_proof_reference=receipt['startup_proof_reference'],
        claim_reference=receipt['claim_reference'],data_output_references=[result['full_dispatch_and_result_journal'],result['features']],scientific_or_pool_release=False)


def actual_imports(root,grant):
    frozen=meta(root['metadata_freeze_receipt_reference']);partition=meta(root['full_shard_manifest_reference']);S.check_partition(partition['shards'])
    Q.need(partition['status']=='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST' and partition['pool_release_authorized'] is False,'ORIGINAL_FROZEN500_PARTITION')
    legacy={}
    Q.need(len(root['legacy0_50_closure_references'])==51,'EXACT51_OLD_CLOSURE_REFERENCES')
    for ref in root['legacy0_50_closure_references']:
        old=meta(ref);i=old['shard_index'];Q.need(i not in legacy and 0<=i<=50 and old['status']=='CLOSED','NO_DUPLICATE_OR_UNCLOSED_IMPORT')
        rr=old['queue_request_reference'];request=meta(rr);folder=Path(rr['path']).parent;sub=meta(old['submission_reference'])
        for r in request['adapter']['data_reference_locators_only']:data_locator(r)
        row=LEGACY.terminal(folder,request,sub,old['accounting_reference'],root,old['root_range_review_reference'],frozen,partition)
        Q.need(row['status']=='CLOSED' and row['job_id']==old['job_id'] and row['receipt_reference']==old['receipt_reference']
            and row['accounting_reference']==old['accounting_reference'],'REAL_OLD_PARENT_AND_PRODUCER_CLOSURE_REVALIDATED_NO_SCIENCE')
        row['imported_actual_closure_reference']=ref;legacy[i]=row
    _,receipt,plan=A.prerequisites(root);account,p=account_row(root['repaired51_accounting_reference'],'1884855')
    repaired={'shard_index':51,'job_id':'1884855','status':'CLOSED','actual_state':p['State'],'actual_exit':p['ExitCode'],
        'expected_rows':250000,'actual_allocated_core_seconds':account['allocated_core_seconds_observed'],'counts':receipt['result']['counts'],
        'receipt_reference':root['repaired51_receipt_reference'],'startup_proof_reference':receipt['startup_proof_reference'],
        'queue_request_reference':root['repaired51_request_reference'],'submission_reference':root['repaired51_submission_reference'],
        'accounting_reference':root['repaired51_accounting_reference'],'claim_reference':receipt['claim_reference']}
    req=meta(repaired['queue_request_reference']);sub=meta(repaired['submission_reference']);Q.need(sub['job_id']=='1884855' and sub['sbatch_returncode']==0
        and req['scope_key']==REPAIR_KEY and req['adapter']['input_reference']==receipt['plan_reference']
        and sub['queue_request_reference']==repaired['queue_request_reference'],'ACTUAL_REPAIRED51_REGISTRATION_NOT_OLD_FAILED_CACHE')
    failed={'shard_index':51,'job_id':'1884853','status':'FAILED','actual_state':'FAILED','actual_exit':'1:0','expected_rows':250000,
        'actual_allocated_core_seconds':336,'accounting_reference':root['failed51_accounting_reference'],'historical_only_not_population_closure':True}
    population,attempts=S.adoption(legacy,repaired,failed)
    qa_account,qp=account_row(root['qa0_accounting_reference'],'1884854')
    attempts['1884854']={'job_id':'1884854','role':'RESOURCE_QA0_NO_POPULATION_ROWS','status':'CLOSED',
        'actual_allocated_core_seconds':qa_account['allocated_core_seconds_observed'],'accounting_reference':root['qa0_accounting_reference']}
    return frozen,partition,population,attempts,plan


def materialize_one(root,grant,base,partition,index,node,derived):
    Q.need(52<=index<=499 and root['authorized_unix_seconds']<=derived<root['deadline_unix_seconds'],'FINITE_ROOT_TEMPLATE_DERIVATION_ONLY')
    tag='pubchem_cont_v3_%04d'%index;folder=CONTROL/'continuation_specs_v3'/tag;output=Q.ROOT/'artifacts/pubchem_continuation_alpha_v3'/('shard-%04d'%index)
    proof=Q.ROOT/'control/secondary_startup'/(tag+'.json');queue=CONTROL/tag
    for path in (folder,output,proof,proof.with_suffix(proof.suffix+'.controller_ready.json'),queue):Q.need(not path.exists() and not path.is_symlink(),'ANY_EXISTING_ARTIFACT_REQUIRES_HOLD_NO_RETRY')
    folder.mkdir(parents=True,mode=0o700);plan_path=folder/'plan.json';plan=copy.deepcopy(base);row=partition['shards'][index]
    plan.update(schema=A.PLAN,producer_key=A.KEY,scope_key=A.KEY,stage=A.STAGE,resource_phase='CONTINUATION52_499',
        scope_mode='EXCLUSIVE_ORDINAL_FEATURE_SHARD',kind='analysis',pilot=False,performance_profile=False,node=node,cpus=16,memory_policy=Q.POLICY,
        wall_seconds=root['wall_seconds'],output_cap_bytes=root['output_cap_bytes'],startup_proof_path=str(proof),output_directory=str(output),
        continuation_range_review_reference=grant,derived_unix_seconds=derived,**row)
    plan['scope_parameters']=A.parameters(plan);plan['execution_argv']=[plan['python'],'-B','-m',A.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof)]
    plan['parent_evidence_references']=A.merge([*base['parent_evidence_references'],*root['parent_evidence_references'],grant])
    plan['source_references']=A.merge([*base['source_references'],*A.sources(),*root['frozen_dependency_source_references'],
        *plan['parent_evidence_references'],root['base_controller_review_reference']])
    review={k:copy.deepcopy(plan[k]) for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
        'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')}
    review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='APPROVED_FOR_EXACT_STAGE',reviewer='root',
        approved_source_references=plan['source_references'],actual_profile_equivalence_and_cost_reviewed=True,
        continuation_range_review_reference=grant,derived_from_exact_Root_range_template=True,
        independent_approval_created_by_controller=False,root_review_reason=root['delegated_template_reason'])
    plan['root_review_reference']=Q.write_new(folder/'root_review.json',review);Q.write_new(plan_path,plan)
    return tag,folder,plan_path,queue


def registry(state_dir,root,grant,partition,initial,initial_attempts):
    population=dict(initial);attempts=dict(initial_attempts);folders={};seen={}
    for path in sorted((CONTROL/'claims').glob('*.json')):
        registration=Q.load(path);rr=registration['queue_request_reference'];request=meta(rr);key=request.get('scope_key')
        if key not in (OLD_KEY,REPAIR_KEY,A.KEY):continue
        plan=meta(request['adapter']['input_reference']);i=plan['shard_index'];folder=Path(rr['path']).parent
        if key==OLD_KEY:
            Q.need(i<=51,'UNEXPECTED_OLD_SCOPE_REGISTRATION_IN52_499_HOLD')
            Q.need(i!=51 or (folder/'submission.json').exists(),'OLD51_SUBMISSION_REQUIRED')
            sub=Q.load(folder/'submission.json');jid=sub.get('job_id');expected='1884853' if i==51 else initial[i]['job_id']
            Q.need(jid==expected and jid in attempts,'ONLY_EXACT_IMPORTED_OLD_REGISTRATIONS');continue
        if key==REPAIR_KEY:
            sub=Q.load(folder/'submission.json');Q.need(i==51 and sub.get('job_id')=='1884855','ONLY_REAL_REPAIRED51_NOT_ANOTHER_PRODUCTION_ATTEMPT');continue
        Q.need(52<=i<=499 and i not in seen and plan['continuation_range_review_reference']==grant,'EXACT_NEW_RANGE_NO_DUPLICATE_REGISTRATION')
        seen[i]=rr;folders[i]=(folder,request)
        for r in request['adapter']['data_reference_locators_only']:data_locator(r)
        cache=state_dir/('terminal_%04d.json'%i)
        if cache.exists():
            row=meta(pin(cache));Q.need(row['queue_request_reference']==rr and row['root_range_review_reference']==grant,'SAME_ACTUAL_TERMINAL_CACHE')
            for k in ('accounting_reference','queue_request_reference','submission_reference'):Q.verify(row[k])
            if row['status']=='CLOSED':Q.verify(row['receipt_reference']);Q.verify(row['startup_proof_reference'])
        elif not (folder/'submission.json').exists():row={'shard_index':i,'status':'UNKNOWN','queue_control_directory':str(folder)}
        else:
            sub=Q.load(folder/'submission.json');jid=sub.get('job_id')
            if sub.get('sbatch_returncode')!=0 or not isinstance(jid,str) or not jid.isdecimal():row={'shard_index':i,'status':'UNKNOWN','queue_control_directory':str(folder)}
            else:
                q=Q.query(['sacct','-j',jid,'--format=JobIDRaw,UID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition','-P'])
                rows=[v for v in csv.DictReader(io.StringIO(q['stdout']),delimiter='|') if v.get('JobIDRaw')==jid]
                Q.need(len(rows)==1 and rows[0]['UID']=='1264','ONE_ACTUAL_REGISTERED_C_PARENT');current=Q.state(rows[0]['State'])
                if current not in S.TERMINAL:row={'shard_index':i,'status':current,'job_id':jid,'queue_control_directory':str(folder)}
                else:
                    before=set(folder.glob('accounting_*.json'));V.account(folder);after=set(folder.glob('accounting_*.json'))-before
                    Q.need(len(after)==1,'ONE_NEW_ACTUAL_TERMINAL_ACCOUNTING');account_ref=pin(after.pop())
                    row=close_new(folder,request,sub,account_ref,root,grant,partition);durable(cache,row,state_dir)
        population[i]=row
        if 'actual_allocated_core_seconds' in row:
            Q.need(row['job_id'] not in attempts,'NO_PARENT_DOUBLE_COUNT');attempts[row['job_id']]=row
    return population,attempts,folders


def context(path):
    grant=pin(path);root=A.range_review(grant);Q.need(root['allowed_nodes']==list(S.NODES),'EXACT_ORIGINAL_REVIEWED_THREE_NODE_POOL')
    for r in root['frozen_dependency_source_references']:Q.verify(r)
    Q.authority(root['resource_authority_reference']['path']);Q.source_review(root['base_controller_review_reference']['path'])
    Q.need(root['storage_scope_review_reference']['path']==str(SCOPE7),'EXACT_FRESH_STORAGE7_NOT_NEW_OR_FAKE_SCOPE')
    frozen,partition,initial,attempts,base=actual_imports(root,grant)
    return root,grant,frozen,partition,initial,attempts,base


def run(args):
    Q.need(args.root_run_reviewed_continuation and args.reason and args.reason.strip(),'EXPLICIT_ROOT_FINITE_CONTINUATION_INVOCATION')
    from .recovery import require_recovery_review
    require_recovery_review(args)
    root,grant,frozen,partition,initial,initial_attempts,base=context(args.root_range_review);state_dir=Q.literal(args.state_directory)
    Q.need(CONTROL in state_dir.parents and state_dir.name=='pubchem_C_continuation52_v3','NEW_CONTINUATION_STATE_ROOT_NOT_OLD_CACHE')
    state_dir.mkdir(parents=True,exist_ok=True,mode=0o700);fd=V.lock(CONTROL/'pubchem_C_finite500_global.lock')
    try:
        binding=state_dir/'binding.json'
        if binding.exists():Q.need(meta(pin(binding))['root_range_review_reference']==grant,'SAME_IMMUTABLE_RANGE_NO_AUTOMATIC_RENEWAL')
        else:
            durable(binding,{'root_range_review_reference':grant,'deadline_unix_seconds':root['deadline_unix_seconds'],
                'old_state_directory_unchanged':True,'created_at':Q.now(),'actual_pid':os.getpid(),
                'actual_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'reason':args.reason},state_dir)
            durable(state_dir/'adoption.json',{'population_by_shard':initial,'all_parent_attempts':initial_attempts,
                'old51_FAILED_retained_separately':True,'actual_imported_rows':13000000,'root_range_review_reference':grant},state_dir)
        last=None
        while True:
            population,attempts,folders=registry(state_dir,root,grant,partition,initial,initial_attempts)
            attempted={int(p.stem.split('_')[-1]) for p in state_dir.glob('attempt_*.json')}
            free={n:Q.free_cpus({'node':n})['free_cpus'] for n in S.NODES}
            action,index,node=S.decision(population,attempted,free,time.time(),root['deadline_unix_seconds'])
            totals={k:sum(v.get('counts',{}).get(k,0) for v in population.values() if v['status']=='CLOSED') for k in ('accepted','chemReject','technicalUnresolved')}
            compact={'action':action,'index':index,'node':node,'closed':sum(v['status']=='CLOSED' for v in population.values()),
                'active_or_unknown':{str(i):{'status':v['status'],'job_id':v.get('job_id')} for i,v in population.items() if v['status']!='CLOSED'},
                'counts':totals,'actual_unique_parent_core_seconds':sum(v['actual_allocated_core_seconds'] for v in attempts.values()),
                'reported_cost_scope':'C_PRODUCTION_PHYSICAL_PARENTS_PLUS_QA0_NOT_A_GLOBAL_LEDGER_TOTAL',
                'state_fixture_cost_evidence_reference':root['state_fixture_evidence_reference'],
                'all_actual_parent_ids':sorted(attempts),'old51_FAILED336cs_included':True,'pool_release_authorized':False}
            encoded=Q.canonical(compact)
            if encoded!=last:event(state_dir,'ACTUAL_STATE_SNAPSHOT',**compact);last=encoded
            # Already registered held/running jobs retain their exact identity.
            # Re-observe is metadata continuation of the same parent, not retry.
            if action.startswith('HOLD') or action.startswith('ALL500') or action.startswith('FINITE_'):return 0 if action.startswith('ALL500') else 2
            for i,(folder,request) in folders.items():
                if population[i]['status'] in S.TERMINAL or population[i]['status']=='CLOSED' or Path(request['ready_path']).exists():continue
                current={n:Q.free_cpus({'node':n})['free_cpus'] for n in S.NODES};after=dict(current);after[request['node']]-=16
                if current[request['node']]>=16 and max(after.values())>=16:
                    lockfd=available_controller_lock()
                    if lockfd is not None:
                        try:V.observe(folder,folder/'request.json',request,Q.load(folder/'submission.json'),30)
                        finally:os.close(lockfd)
            if action=='ELIGIBLE' and not args.observe_only:
                lockfd=available_controller_lock()
                if lockfd is None:
                    if args.single_cycle:return 0
                    time.sleep(min(30,max(0,root['deadline_unix_seconds']-time.time())));continue
                try:
                    fresh,fees,_=registry(state_dir,root,grant,partition,initial,initial_attempts);cpus={n:Q.free_cpus({'node':n})['free_cpus'] for n in S.NODES}
                    a2,i2,n2=S.decision(fresh,attempted,cpus,time.time(),root['deadline_unix_seconds'])
                    if a2=='ELIGIBLE':
                        target=C.ROOT/'control/pubchem_ordinal_claims'/C.RAW_SHA/('shard_%06d.json'%i2)
                        Q.need(not target.exists() and not target.is_symlink(),'EXISTING_PHYSICAL_CLAIM_NO_AUTOMATIC_RETRY')
                        durable(state_dir/('attempt_%04d.json'%i2),{'shard_index':i2,'root_range_review_reference':grant,'node':n2,
                            'status':'INTENT_BEFORE_PLAN_SUBMISSION','no_automatic_retry':True,'created_at':Q.now()},state_dir)
                        tag,folder,plan_path,queue=materialize_one(root,grant,base,partition,i2,n2,time.time())
                        call=SimpleNamespace(reviewer='root',controller_review=Path(root['base_controller_review_reference']['path']),authority=Path(root['resource_authority_reference']['path']),
                            storage_review=SCOPE7,producer='readonly',deployment=None,input=plan_path,node=n2,wall_seconds=28800,job_name='dv1_pubchem_cont_v3_%04d'%i2,output=queue)
                        qfolder,rp,request=V.prepare(call);sub=V.submit_held(qfolder,rp,request)
                        event(state_dir,'ACTUAL_HELD_SUBMISSION_NO_RETRY',shard_index=i2,submission_reference=pin(qfolder/'submission.json'))
                finally:os.close(lockfd)
            if args.single_cycle:return 0
            time.sleep(min(30,max(0,root['deadline_unix_seconds']-time.time())))
    except Exception as exc:
        event(state_dir,'HOLD_EXCEPTION_NO_RETRY_NO_RENEWAL_NO_SIGNALS',error=repr(exc),traceback=traceback.format_exc(),actual_all_parent_costs_retained=True);raise
    finally:os.close(fd)


def candidate(args):
    Q.need(args.legacy_state_directory and args.qa0_receipt and args.qa0_accounting and args.repaired51_receipt and args.repaired51_accounting
        and args.repaired51_request and args.repaired51_submission and args.failed51_accounting and args.controller_review
        and args.authority and args.storage_review and args.state_fixture_evidence and args.deadline_unix_seconds,'ACTUAL_C0_AND_ALL_OLD_EVIDENCE_BEFORE_RANGE_CANDIDATE')
    out=Q.literal(args.output);Q.need(Q.ROOT/'control' in out.parents and not out.exists(),'NEW_UNSIGNED_CANDIDATE_METADATA_ONLY');out.mkdir(parents=True,mode=0o700)
    qa_ref=pin(args.qa0_receipt);qa=meta(qa_ref);repair_ref=pin(args.repaired51_receipt);repair=meta(repair_ref);base=meta(repair['plan_reference'])
    accounts=[pin(args.failed51_accounting),pin(args.qa0_accounting),pin(args.repaired51_accounting)];parents=[*base['parent_evidence_references'],qa_ref,repair_ref,qa['startup_proof_reference'],qa['plan_reference'],
        repair['startup_proof_reference'],repair['plan_reference'],repair['claim_reference'],*accounts,pin(args.repaired51_request),pin(args.repaired51_submission)]
    for r in accounts:parents.append(meta(r)['raw_sacct_reference'])
    closures=[pin(args.legacy_state_directory/('terminal_%04d.json'%i)) for i in range(51)];parents.extend(closures)
    fixture_ref=pin(args.state_fixture_evidence);fixture=meta(fixture_ref);parents.extend((fixture_ref,fixture['raw_sacct_reference']))
    now=time.time();Q.need(now<args.deadline_unix_seconds<=now+72000,'ROOT_MUST_SET_FIXED_ABSOLUTE_MAX20H_NOT_RENEWABLE')
    deps=[*A.P.sources(),pin(S.OLD_PATH),pin(Path(LEGACY.__file__))]
    root={'schema':A.RANGE,'status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED','proposed_runtime_status':'ROOT_APPROVED','endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),
        'first_shard':52,'last_shard':499,'population_N':C.N,'allowed_nodes':list(S.NODES),'max_nonterminal_C_parents':6,'reserved_non_C_cpus':16,
        'maximum_foreground_seconds':72000,'authorized_unix_seconds':now,'deadline_unix_seconds':args.deadline_unix_seconds,'poll_seconds':30,
        'wall_seconds':28800,'output_cap_bytes':8<<30,'controller_metadata_cap_bytes':CAP,'cost_overrun_action':'REPORT_AND_CONTINUE','scientific_or_pool_release':False,
        'source_references':A.sources(),'frozen_dependency_source_references':A.merge(deps),'parent_evidence_references':A.merge(parents),
        'qa0_receipt_reference':qa_ref,'qa0_accounting_reference':accounts[1],'failed51_accounting_reference':accounts[0],
        'repaired51_receipt_reference':repair_ref,'repaired51_accounting_reference':accounts[2],'repaired51_request_reference':pin(args.repaired51_request),
        'repaired51_submission_reference':pin(args.repaired51_submission),'legacy0_50_closure_references':closures,
        'metadata_freeze_receipt_reference':base['metadata_freeze_receipt_reference'],'full_shard_manifest_reference':base['full_shard_manifest_reference'],
        'base_controller_review_reference':pin(args.controller_review),'resource_authority_reference':pin(args.authority),'storage_scope_review_reference':pin(args.storage_review),
        'state_fixture_evidence_reference':fixture_ref,
        'delegate_exact_per_shard_metadata_template':True,'no_automatic_retry':True,'no_automatic_renewal':True,'no_signals_or_cancel':True,
        'old_failed51_cost_retained':True,'original_claim_namespace_unchanged':True,'all11_fixtures_before_Budget':True,
        'delegated_template_reason':None,'Root_approval_or_submission_created':False}
    A.prerequisites(root);actual_imports(root,None)
    Q.write_new(out/'range_candidate.json',root)


def main():
    Q.login();Q.need(Path(__file__).absolute()==HERE/'controller.py','ACTUAL_NEW_CONTROLLER_PRIMARY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('template','candidate','run'))
    for name in ('metadata-recovery-review','root-range-review','state-directory','legacy-state-directory','qa0-receipt','qa0-accounting','repaired51-receipt','repaired51-accounting','repaired51-request',
        'repaired51-submission','failed51-accounting','controller-review','authority','storage-review','state-fixture-evidence','output'):p.add_argument('--'+name,type=Path)
    p.add_argument('--deadline-unix-seconds',type=float);p.add_argument('--root-run-reviewed-continuation',action='store_true');p.add_argument('--reason')
    p.add_argument('--single-cycle',action='store_true');p.add_argument('--observe-only',action='store_true');a=p.parse_args()
    if a.action=='template':
        Q.need(a.output and Q.ROOT/'control' in Q.literal(a.output).parents and not a.output.exists(),'NEW_CONTROL_TEMPLATE_ONLY');Q.write_new(a.output,{'schema':'UNSIGNED_PUBCHEM_CONTINUATION_REQUIRED_EVIDENCE_V3',
            'executable':False,'root_review':None,'actual_repaired51_C0':None,'future_proof_or_account_hashes_created':False,
            'required':['actualQA0C0/proof','actual1884855C0/proof/claim','legacy0..50C0closures','1884853FAILED336cs','actualsource13','Rootfixeddeadline<=20h','Rootexactsource/storage review']});return 0
    if a.action=='candidate':candidate(a);return 0
    Q.need(a.root_range_review and a.state_directory,'ACTUAL_RANGE_REVIEW_AND_NEW_STATE');return run(a)


if __name__=='__main__':raise SystemExit(main())
